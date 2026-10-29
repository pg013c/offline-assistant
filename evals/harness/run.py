"""`make eval`: index the corpus through the API, run Promptfoo, score and report (F-04).

The run starts its own API on its own port, data directory and Qdrant collection prefix, so
development data is never touched, and stops it at the end.
"""

import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

import httpx
import yaml

from harness.corpus import CorpusDocument, documents, sha256
from harness.dataset import load_cases
from harness.gate import check
from harness.metrics import CaseResult, compute
from harness.promptfoo import command_line, environment, hits_by_case
from harness.report import build_report, markdown
from harness.resolve import ChunkRef, resolve

ROOT = Path(__file__).parents[2]
PROMPTFOO_CONFIG = ROOT / "evals" / "promptfoo" / "retrieval.yaml"
BASELINE = ROOT / "docs" / "evals" / "retrieval-baseline.json"
STARTUP_SECONDS = 180
INGESTION_SECONDS = 1800
PROMPTFOO_SECONDS = 600
# The similarity threshold the suite measures at; the app's default (F-03).
EVAL_THRESHOLD = 0.5
POLL_SECONDS = 1.0


class CorpusError(Exception):
    """A corpus file is missing or differs from its pin; the message says what to run."""


class PortInUse(Exception):
    """Something already listens on the evaluation port."""


@dataclass(frozen=True)
class RunConfig:
    # The corpus files and their pins; `make eval` uses evals/corpus.json.
    corpus: tuple[CorpusDocument, ...]
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
    """One evaluation run from an empty index; the API it starts is stopped whatever happens."""
    started_at = datetime.now(UTC)
    corpus = verify_corpus(config.corpus_dir, config.corpus)
    ensure_port_free(config.port)
    _reset(config)
    api_url = f"http://127.0.0.1:{config.port}"
    server, log = _start_api(config)
    try:
        _wait_until_healthy(api_url, server)
        with httpx.Client(base_url=api_url, timeout=60) as api:
            indexing_started = time.monotonic()
            document_ids = _index_corpus(api, config.corpus_dir, config.corpus)
            indexing_seconds = round(time.monotonic() - indexing_started, 1)
            chunks = _chunk_refs(api, document_ids)
        cases = load_cases(config.dataset)
        expected = resolve(cases, chunks)
        hits = _search_with_promptfoo(cases, api_url, config.results_dir, started_at)
    finally:
        _stop(server)
        log.close()

    results = [
        CaseResult(case.id, case.behaviour, expected[case.id], hits[case.id]) for case in cases
    ]
    metrics = compute(results, config.threshold)
    metadata = {
        **_metadata(config, started_at),
        "corpus": corpus,
        "indexing_seconds": indexing_seconds,
    }
    report = build_report(metrics, metadata, config.threshold, expected)
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


def verify_corpus(corpus_dir: Path, pins: Sequence[CorpusDocument]) -> dict[str, str]:
    """File name -> SHA-256 of every pinned corpus file, each checked against its pin."""
    if not pins:
        raise CorpusError("the corpus has no files")
    verified: dict[str, str] = {}
    for document in pins:
        path = corpus_dir / document.file
        if not path.exists():
            raise CorpusError(f"{document.file} is missing in {corpus_dir}; run `make eval-corpus`")
        actual = sha256(path)
        if actual != document.sha256:
            raise CorpusError(
                f"{document.file} differs from the pinned SHA-256; run `make eval-corpus`"
            )
        verified[document.file] = actual
    return verified


def ensure_port_free(port: int) -> None:
    """Refuse to start when something listens on the port: the run must not use another API."""
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise PortInUse(
                f"port {port} is already in use; stop that process or set EVAL_API_PORT"
            )


def drop_collections(qdrant: httpx.Client, prefix: str) -> None:
    """Delete the collections a run with this prefix created, and no others."""
    listed = qdrant.get("/collections").json()["result"]["collections"]
    for name in (item["name"] for item in listed):
        if name.startswith(f"{prefix}-"):
            qdrant.delete(f"/collections/{name}").raise_for_status()


def default_config(env: Mapping[str, str]) -> RunConfig:
    """The configuration of `make eval`, independent of the development settings.

    The threshold is fixed here, and Qdrant is the one `make qdrant` starts, so a developer's
    `.env` cannot change what a run measures.
    """
    return RunConfig(
        corpus=tuple(documents()),
        corpus_dir=Path(env.get("EVAL_CORPUS_DIR", ROOT / "data" / "eval-corpus")),
        dataset=ROOT / "evals" / "datasets" / "retrieval.yaml",
        baseline=BASELINE,
        results_dir=ROOT / "evals" / "results",
        data_dir=ROOT / "data" / "eval",
        models_dir=Path(env.get("ASSISTANT_MODELS_DIR", ROOT / "data" / "models")),
        qdrant_url=env.get("EVAL_QDRANT_URL")
        or f"http://127.0.0.1:{env.get('QDRANT_PORT', '6333')}",
        collection_prefix="eval",
        port=int(env.get("EVAL_API_PORT", "8021")),
        threshold=EVAL_THRESHOLD,
    )


def _reset(config: RunConfig) -> None:
    """Start from an empty data directory and collection, so the run indexes the current code."""
    shutil.rmtree(config.data_dir, ignore_errors=True)
    with httpx.Client(base_url=config.qdrant_url, timeout=30) as qdrant:
        drop_collections(qdrant, config.collection_prefix)


def _start_api(config: RunConfig) -> tuple[subprocess.Popen[bytes], IO[bytes]]:
    # Only the run's own settings: nothing from a developer's ASSISTANT_* environment.
    inherited = {
        name: value for name, value in os.environ.items() if not name.startswith("ASSISTANT_")
    }
    env = {
        **inherited,
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
    server = subprocess.Popen(  # noqa: S603 (fixed command)
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
    return server, log


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


def _index_corpus(
    api: httpx.Client, corpus_dir: Path, pins: Sequence[CorpusDocument]
) -> dict[str, str]:
    """Upload the corpus and wait until every file is ready; title -> document id."""
    ids: dict[str, str] = {}
    for document in pins:
        path = corpus_dir / document.file
        response = api.post(
            "/api/documents", files={"file": (path.name, path.read_bytes(), "application/pdf")}
        )
        response.raise_for_status()
        ids[path.stem] = response.json()["id"]
    deadline = time.monotonic() + INGESTION_SECONDS
    while time.monotonic() < deadline:
        listed = {item["id"]: item for item in api.get("/api/documents").json()}
        corpus = [listed[document_id] for document_id in ids.values()]
        failed = [item for item in corpus if item["status"] == "failed"]
        if failed:
            raise RuntimeError(f"corpus documents failed to index: {failed}")
        if all(item["status"] == "ready" for item in corpus):
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
        command_line(Path(_executable("pnpm")), PROMPTFOO_CONFIG, tests, output),
        env=environment(os.environ, api_url),
        check=True,
        timeout=PROMPTFOO_SECONDS,
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
            "sha256": hashlib.sha256(dataset).hexdigest(),
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
    config = default_config(os.environ)
    outcome = run(config)
    print(outcome.report_markdown.read_text(encoding="utf-8"))
    print(f"Report: {outcome.report_json}")
    if not config.baseline.exists():
        print(f"No baseline at {config.baseline}; this run can become it.")
    if outcome.gate_failures:
        sys.exit("Regression:\n" + "\n".join(f"- {failure}" for failure in outcome.gate_failures))


if __name__ == "__main__":
    main()
