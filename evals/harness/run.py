"""`make eval`: index the corpus through the API, run Promptfoo, score and report (F-04).

The run starts its own API on its own port, data directory and Qdrant collection prefix, so
development data is never touched, and stops it at the end.
"""

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx
import yaml

from harness.corpus import documents
from harness.dataset import load_cases
from harness.gate import check
from harness.metrics import CaseResult, compute
from harness.promptfoo import environment, hits_by_case
from harness.report import build_report, markdown
from harness.resolve import ChunkRef, resolve

ROOT = Path(__file__).parents[2]
PROMPTFOO_CONFIG = ROOT / "evals" / "promptfoo" / "retrieval.yaml"
STARTUP_SECONDS = 180
INGESTION_SECONDS = 1800
POLL_SECONDS = 1.0


@dataclass(frozen=True)
class RunConfig:
    corpus_dir: Path
    dataset: Path
    baseline: Path
    results_dir: Path
    data_dir: Path
    models_dir: Path
    qdrant_url: str
    collection_prefix: str
    port: int
    threshold: float


@dataclass(frozen=True)
class Outcome:
    report_json: Path
    report_markdown: Path
    gate_failures: list[str]


def run(config: RunConfig) -> Outcome:
    """One evaluation run; the API it starts is stopped whatever happens."""
    started_at = datetime.now(UTC)
    api_url = f"http://127.0.0.1:{config.port}"
    server = _start_api(config)
    try:
        _wait_until_healthy(api_url, server)
        with httpx.Client(base_url=api_url, timeout=60) as api:
            document_ids = _index_corpus(api, config.corpus_dir)
            chunks = _chunk_refs(api, document_ids)
        cases = load_cases(config.dataset)
        expected = resolve(cases, chunks)
        hits = _search_with_promptfoo(cases, api_url, config.results_dir, started_at)
    finally:
        _stop(server)

    results = [
        CaseResult(case.id, case.behaviour, expected[case.id], hits[case.id]) for case in cases
    ]
    metrics = compute(results, config.threshold)
    report = build_report(metrics, _metadata(config, started_at), config.threshold)
    baseline = (
        json.loads(config.baseline.read_text(encoding="utf-8"))["metrics"]
        if config.baseline.exists()
        else {}
    )
    failures = check(
        {name: values["value"] for name, values in report["metrics"].items()},
        {name: values["value"] for name, values in baseline.items()},
    )
    stem = config.results_dir / f"retrieval-{started_at:%Y%m%dT%H%M%SZ}"
    report_json = stem.with_suffix(".json")
    report_markdown = stem.with_suffix(".md")
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
    report_markdown.write_text(markdown(report), encoding="utf-8")
    return Outcome(report_json, report_markdown, failures)


def _start_api(config: RunConfig) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "ASSISTANT_DATA_DIR": str(config.data_dir),
        "ASSISTANT_MODELS_DIR": str(config.models_dir),
        "ASSISTANT_QDRANT_URL": config.qdrant_url,
        "ASSISTANT_QDRANT_COLLECTION_PREFIX": config.collection_prefix,
        "ASSISTANT_MIN_SIMILARITY": str(config.threshold),
    }
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.results_dir.mkdir(parents=True, exist_ok=True)
    log = (config.results_dir / "api.log").open("wb")
    # A session of its own, so stopping the API stops only what this run started.
    return subprocess.Popen(  # noqa: S603 (fixed command)
        [
            _executable("uv"),
            "run",
            "--directory",
            str(ROOT / "backend"),
            "uvicorn",
            "assistant.app:main",
            "--factory",
            "--port",
            str(config.port),
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _wait_until_healthy(api_url: str, server: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + STARTUP_SECONDS
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("the API stopped while starting; see api.log in the results")
        try:
            if httpx.get(f"{api_url}/api/health", timeout=2).status_code == httpx.codes.OK:
                return
        except httpx.TransportError:
            pass
        time.sleep(POLL_SECONDS)
    raise RuntimeError(f"the API did not start within {STARTUP_SECONDS} s")


def _index_corpus(api: httpx.Client, corpus_dir: Path) -> dict[str, str]:
    """Upload the corpus files present and wait until all are ready; title -> document id."""
    ids: dict[str, str] = {}
    for document in documents():
        path = corpus_dir / document.file
        if not path.exists():
            continue
        response = api.post(
            "/api/documents", files={"file": (path.name, path.read_bytes(), "application/pdf")}
        )
        response.raise_for_status()
        ids[path.stem] = response.json()["id"]
    deadline = time.monotonic() + INGESTION_SECONDS
    while time.monotonic() < deadline:
        listed = {item["id"]: item for item in api.get("/api/documents").json()}
        statuses = {listed[document_id]["status"] for document_id in ids.values()}
        failed = [item for item in listed.values() if item["status"] == "failed"]
        if failed:
            raise RuntimeError(f"corpus documents failed to index: {failed}")
        if statuses == {"ready"}:
            return ids
        time.sleep(POLL_SECONDS)
    raise RuntimeError(f"the corpus was not indexed within {INGESTION_SECONDS} s")


def _chunk_refs(api: httpx.Client, document_ids: dict[str, str]) -> list[ChunkRef]:
    refs = []
    for title, document_id in document_ids.items():
        for chunk in api.get(f"/api/documents/{document_id}/chunks").json():
            location = chunk["location"]
            refs.append(
                ChunkRef(
                    chunk_id=chunk["chunk_id"],
                    document=title,
                    article=location["article"],
                    paragraph=location["paragraph"],
                    heading_path=tuple(location["heading_path"]),
                )
            )
    return refs


def _search_with_promptfoo(
    cases: list[Any], api_url: str, results_dir: Path, started_at: datetime
) -> dict[str, Any]:
    tests = results_dir / "promptfoo-tests.yaml"
    tests.write_text(
        yaml.safe_dump(
            [{"vars": {"case_id": case.id, "question": case.question}} for case in cases],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    output = results_dir / f"promptfoo-{started_at:%Y%m%dT%H%M%SZ}.json"
    subprocess.run(  # noqa: S603 (fixed command)
        [
            _executable("pnpm"),
            "--dir",
            str(ROOT / "evals"),
            "exec",
            "promptfoo",
            "eval",
            "--config",
            str(PROMPTFOO_CONFIG),
            "--tests",
            str(tests),
            "--output",
            str(output),
            "--no-cache",
            "--no-progress-bar",
        ],
        env=environment(os.environ, api_url),
        check=True,
    )
    return hits_by_case(json.loads(output.read_text(encoding="utf-8")))


def _stop(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is None:
        os.killpg(server.pid, signal.SIGTERM)
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, signal.SIGKILL)
            server.wait()


def _metadata(config: RunConfig, started_at: datetime) -> dict[str, Any]:
    dataset = config.dataset.read_bytes()
    return {
        "started_at": started_at.isoformat(timespec="seconds"),
        "git_commit": _command(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
        "dataset": {
            "path": str(config.dataset.relative_to(ROOT)),
            "version": yaml.safe_load(dataset)["version"],
            "sha256": sha256(dataset).hexdigest(),
        },
        "models": json.loads(
            _command(
                [
                    "uv",
                    "run",
                    "--directory",
                    str(ROOT / "backend"),
                    "python",
                    "-c",
                    "import json; from assistant.adapters.pinned_models import PINNED_MODELS; "
                    "print(json.dumps({m.repository: m.revision for m in PINNED_MODELS}))",
                ]
            )
        ),
        "qdrant_version": httpx.get(config.qdrant_url, timeout=5).json().get("version"),
        "settings": {
            "collection_prefix": config.collection_prefix,
            "threshold": config.threshold,
            "search_limit": 10,
        },
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": _command(["sysctl", "-n", "machdep.cpu.brand_string"])
            if sys.platform == "darwin"
            else platform.processor(),
            "cpus": os.cpu_count(),
        },
    }


def _command(arguments: list[str]) -> str:
    executable, *rest = arguments
    return subprocess.run(  # noqa: S603 (fixed commands)
        [_executable(executable), *rest], capture_output=True, text=True, check=True
    ).stdout.strip()


def _executable(name: str) -> str:
    """The full path of a tool the run needs, or a clear error if it is not installed."""
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"{name} is not installed or not on PATH; see `make setup`")
    return path


def main() -> None:
    """`make eval`: the retrieval suite on the full corpus, with the recorded baseline."""
    config = RunConfig(
        corpus_dir=Path(os.environ.get("EVAL_CORPUS_DIR", ROOT / "data" / "eval-corpus")),
        dataset=ROOT / "evals" / "datasets" / "retrieval.yaml",
        baseline=ROOT / "docs" / "evals" / "retrieval-baseline.json",
        results_dir=ROOT / "evals" / "results",
        data_dir=ROOT / "data" / "eval",
        models_dir=Path(os.environ.get("ASSISTANT_MODELS_DIR", ROOT / "data" / "models")),
        qdrant_url=os.environ.get("ASSISTANT_QDRANT_URL", "http://127.0.0.1:6333"),
        collection_prefix="eval",
        port=int(os.environ.get("EVAL_API_PORT", "8021")),
        threshold=float(os.environ.get("ASSISTANT_MIN_SIMILARITY", "0.5")),
    )
    outcome = run(config)
    print(outcome.report_markdown.read_text(encoding="utf-8"))
    print(f"Report: {outcome.report_json}")
    if not config.baseline.exists():
        print(f"No baseline at {config.baseline}; this run can become it.")
    if outcome.gate_failures:
        sys.exit("Regression:\n" + "\n".join(f"- {failure}" for failure in outcome.gate_failures))


if __name__ == "__main__":
    main()
