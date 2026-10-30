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
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

import httpx
import yaml

from harness.answers import (
    AnswerCase,
    ChatResult,
    SavedNote,
    answers_markdown,
    judge_input,
    parse_chat_stream,
    score_answers,
)
from harness.calibration import (
    CALIBRATION_FILE,
    Agreement,
    agreement,
    calibration_failures,
    load_calibration,
)
from harness.corpus import CorpusDocument, documents, sha256
from harness.dataset import load_answer_cases, load_cases
from harness.gate import below_answer_floors, gate_failures
from harness.judge import JUDGE_MODEL, JudgeClient, Verdict
from harness.metrics import CaseResult, compute, latency, top_out_of_scope_similarity
from harness.promptfoo import (
    MODES,
    Response,
    command_line,
    environment,
    outputs_by_case,
    responses_by_mode,
)
from harness.report import ModeResult, build_report, markdown
from harness.resolve import ChunkRef, resolve

ROOT = Path(__file__).parents[2]
PROMPTFOO_CONFIG = ROOT / "evals" / "promptfoo" / "retrieval.yaml"
# The mode the API runs by default; the gate compares it with the baseline.
GATED_MODE = "reranked"
BASELINE = ROOT / "docs" / "evals" / "retrieval-baseline.json"
ANSWER_BASELINE = ROOT / "docs" / "evals" / "answer-baseline.json"
ANSWERS_CONFIG = ROOT / "evals" / "promptfoo" / "answers.yaml"
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
    # Whether the floors of ADR 0020 apply; `make eval` holds the corpus to them.
    floors: bool = False
    # The chat model the API answers with, and its server (F-06, ADR 0021).
    chat_model: str = "fake-extractive"
    llm_url: str = "http://127.0.0.1:8080"
    # The judge `make judge` serves (ADR 0022); the answer suite judges when it answers.
    judge_url: str = "http://127.0.0.1:8081"


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
            warm_ups = {mode: warm_up(api, mode) for mode in MODES}
        cases = load_cases(config.dataset)
        expected = resolve(cases, chunks)
        responses = _search_with_promptfoo(cases, api_url, config.results_dir, started_at)
    except Exception as error:
        log.flush()
        tail = api_log_tail(config.results_dir / "api.log")
        raise RuntimeError(f"{error}\n\nEnd of the API log:\n{tail}") from error
    finally:
        _stop(server)
        log.close()

    modes = {
        mode: _score(cases, expected, by_case, config.threshold, warm_ups[mode])
        for mode, by_case in responses.items()
    }
    metadata = {
        **_metadata(config, started_at),
        "corpus": corpus,
        "indexing_seconds": indexing_seconds,
    }
    report = build_report(modes, GATED_MODE, metadata, config.threshold, expected)
    baseline = (
        json.loads(config.baseline.read_text(encoding="utf-8"))["metrics"]
        if config.baseline.exists()
        else {}
    )
    failures = gate_failures(
        {name: values["value"] for name, values in report["metrics"].items()},
        {name: values["value"] for name, values in baseline.items()},
        floors=config.floors,
    )
    stem = config.results_dir / f"retrieval-{started_at:%Y%m%dT%H%M%SZ}"
    report_json = stem.with_suffix(".json")
    report_markdown = stem.with_suffix(".md")
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
    report_markdown.write_text(markdown(report), encoding="utf-8")
    return Outcome(report_json, report_markdown, failures)


def run_answers(config: RunConfig) -> Outcome:
    """The answer suite from an empty index, against the configured chat model (F-06)."""
    started_at = datetime.now(UTC)
    corpus = verify_corpus(config.corpus_dir, config.corpus)
    ensure_port_free(config.port)
    _reset(config)
    api_url = f"http://127.0.0.1:{config.port}"
    server, log = _start_api(config)
    try:
        _wait_until_healthy(api_url, server)
        with httpx.Client(base_url=api_url, timeout=60) as api:
            document_ids = _index_corpus(api, config.corpus_dir, config.corpus)
            chunks = _chunk_refs(api, document_ids)
        cases = load_answer_cases(config.dataset)
        expected = resolve(cases, chunks)
        outputs = outputs_by_case(
            _promptfoo(ANSWERS_CONFIG, cases, api_url, config.results_dir, started_at)
        )
        results = {case.id: parse_chat_stream(outputs[case.id]) for case in cases}
        # Notes are read back while the API still runs.
        with httpx.Client(base_url=api_url, timeout=60) as api:
            notes = fetch_notes(api, [note for result in results.values() for note in result.notes])
    except Exception as error:
        log.flush()
        tail = api_log_tail(config.results_dir / "api.log")
        raise RuntimeError(f"{error}\n\nEnd of the API log:\n{tail}") from error
    finally:
        _stop(server)
        log.close()

    answer_cases = [
        AnswerCase(
            case.id,
            case.language,
            case.behaviour,
            expected[case.id],
            tools=case.tools,
            forbidden=case.forbidden,
            injection=case.kind == "injection",
            note=case.note,
            key_points=case.key_points,
        )
        for case in cases
    ]
    verdicts, judge_note = judge_answers(
        answer_cases,
        {case.id: case.question for case in cases},
        results,
        {chunk.chunk_id: chunk.text for chunk in chunks},
        config.judge_url,
    )
    calibration = calibrate(config.judge_url) if verdicts is not None else None
    metrics = score_answers(
        answer_cases,
        results,
        stored=frozenset(chunk.chunk_id for chunk in chunks),
        notes=notes,
        verdicts=verdicts,
    )
    metadata = {
        **_metadata(config, started_at),
        "corpus": corpus,
        "chat_model": config.chat_model,
        "llm_server": _llm_server(config.llm_url),
        "judge": judge_note,
        "calibration": (
            {
                "correctness": calibration.correctness,
                "support": calibration.support,
                "items": calibration.items,
            }
            if calibration
            else "not run"
        ),
    }
    report = {
        "metrics": {
            name: {"value": value, "cases": metrics.cases[name]}
            for name, value in metrics.values.items()
        },
        "performance": metrics.performance,
        "missed": metrics.missed,
        "per_case": metrics.per_case,
        "results": {
            case_id: {
                "answer": result.answer,
                "cited": list(result.cited),
                "tools": list(result.tools),
                "notes": list(result.notes),
                "error": result.error,
                "usage": result.usage,
            }
            for case_id, result in results.items()
        },
        "expected": {case: sorted(ids) for case, ids in expected.items()},
        "notes": {
            note_id: {"sources": list(note.sources), "content": note.content}
            for note_id, note in notes.items()
        },
        "metadata": metadata,
    }
    baseline = (
        json.loads(config.baseline.read_text(encoding="utf-8"))["metrics"]
        if config.baseline.exists()
        else {}
    )
    failures = gate_failures(
        dict(metrics.values),
        {name: values["value"] for name, values in baseline.items()},
        floors=False,
    ) + below_answer_floors(metrics.values)
    if calibration is not None:
        failures += calibration_failures(calibration)
    stem = config.results_dir / f"answers-{started_at:%Y%m%dT%H%M%SZ}"
    report_json = stem.with_suffix(".json")
    report_markdown = stem.with_suffix(".md")
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
    report_markdown.write_text(answers_markdown(metrics, metadata), encoding="utf-8")
    return Outcome(report_json, report_markdown, failures)


def _llm_server(url: str) -> dict[str, Any]:
    """The model server's build and model file, from llama-server's /props (ADR 0021)."""
    try:
        props = httpx.get(f"{url}/props", timeout=5).json()
    except (httpx.HTTPError, ValueError):
        return {"url": url}
    return {"url": url, "build": props.get("build_info"), "model_path": props.get("model_path")}


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


def default_answers_config(env: Mapping[str, str]) -> RunConfig:
    """`make eval-answers`: the answer suite against the local model (F-06), over the whole
    corpus including the injected documents (F-07)."""
    return replace(
        default_config(env),
        corpus=tuple(documents()),
        dataset=ROOT / "evals" / "datasets" / "answers.yaml",
        baseline=ANSWER_BASELINE,
        floors=False,
        chat_model="qwen3-8b",
        llm_url=f"http://127.0.0.1:{env.get('LLM_PORT', '8080')}",
        judge_url=f"http://127.0.0.1:{env.get('JUDGE_PORT', '8081')}",
    )


def default_config(env: Mapping[str, str]) -> RunConfig:
    """The configuration of `make eval`, independent of the development settings.

    The threshold is fixed here, and Qdrant is the one `make qdrant` starts, so a developer's
    `.env` cannot change what a run measures.
    """
    return RunConfig(
        corpus=tuple(document for document in documents() if not document.answers_only),
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
        floors=True,
    )


def _reset(config: RunConfig) -> None:
    """Start from an empty data directory and collection, so the run indexes the current code."""
    shutil.rmtree(config.data_dir, ignore_errors=True)
    with httpx.Client(base_url=config.qdrant_url, timeout=30) as qdrant:
        drop_collections(qdrant, config.collection_prefix)


def api_environment(config: RunConfig, base: Mapping[str, str]) -> dict[str, str]:
    """The evaluation API's environment: the caller's, without its ASSISTANT_* settings."""
    inherited = {name: value for name, value in base.items() if not name.startswith("ASSISTANT_")}
    return {
        **inherited,
        "ASSISTANT_DATA_DIR": str(config.data_dir),
        "ASSISTANT_MODELS_DIR": str(config.models_dir),
        "ASSISTANT_QDRANT_URL": config.qdrant_url,
        "ASSISTANT_QDRANT_COLLECTION_PREFIX": config.collection_prefix,
        "ASSISTANT_MIN_SIMILARITY": str(config.threshold),
        # Both modes are measured, so the reranker must be there whatever the default is.
        "ASSISTANT_RERANKER": "on",
        "ASSISTANT_CHAT_MODEL": config.chat_model,
        "ASSISTANT_LLM_URL": config.llm_url,
    }


def api_log_tail(path: Path, lines: int = 40) -> str:
    """The last lines of the API's log, to explain a failed run."""
    if not path.exists():
        return "(no API log)"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def warm_up(api: httpx.Client, mode: str) -> float:
    """One unmeasured search in the mode, so measured ones find the models loaded; its ms."""
    started = time.monotonic()
    api.post(
        "/api/search", json={"query": "warm-up", "limit": 10, "rerank": mode == "reranked"}
    ).raise_for_status()
    return round((time.monotonic() - started) * 1000, 1)


def _start_api(config: RunConfig) -> tuple[subprocess.Popen[bytes], IO[bytes]]:
    # Only the run's own settings: nothing from a developer's ASSISTANT_* environment.
    env = api_environment(config, os.environ)
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


def fetch_notes(api: httpx.Client, note_ids: Sequence[str]) -> dict[str, SavedNote]:
    """The notes the run saved, read back through `GET /api/notes/{id}` (F-07a)."""
    saved: dict[str, SavedNote] = {}
    for note_id in note_ids:
        response = api.get(f"/api/notes/{note_id}")
        response.raise_for_status()
        note = response.json()
        saved[note_id] = SavedNote(
            sources=tuple(source["chunk_id"] for source in note["sources"]),
            content=note["content"],
        )
    return saved


def judge_answers(
    cases: Sequence[AnswerCase],
    questions: Mapping[str, str],
    results: Mapping[str, ChatResult],
    texts: Mapping[str, str],
    judge_url: str,
) -> tuple[dict[str, Verdict | None] | None, str]:
    """Each complete answer judged (ADR 0022), and a note on the judge; without a judge,
    no verdicts and a note that says how to start it."""
    try:
        httpx.get(f"{judge_url}/health", timeout=5).raise_for_status()
    except httpx.HTTPError:
        return None, f"skipped: no judge answers at {judge_url}; start it with make judge"
    client = JudgeClient(judge_url)
    verdicts: dict[str, Verdict | None] = {}
    for case in cases:
        result = results[case.id]
        if case.behaviour != "answer" or result.error or not result.complete:
            continue
        verdicts[case.id] = client.judge(judge_input(case, result, questions[case.id], texts))
    return verdicts, f"{JUDGE_MODEL} at {judge_url}"


def calibrate(judge_url: str, path: Path = CALIBRATION_FILE) -> Agreement | None:
    """The judge's agreement with the hand-labelled calibration set, when there is one."""
    if not path.exists():
        return None
    client = JudgeClient(judge_url)
    items = load_calibration(path)
    return agreement(items, {item.id: client.judge(item.judged) for item in items})


def media_type(path: Path) -> str:
    """The media type a corpus file is uploaded with."""
    return "text/markdown" if path.suffix == ".md" else "application/pdf"


def _index_corpus(
    api: httpx.Client, corpus_dir: Path, pins: Sequence[CorpusDocument]
) -> dict[str, str]:
    """Upload the corpus and wait until every file is ready; title -> document id."""
    ids: dict[str, str] = {}
    for document in pins:
        path = corpus_dir / document.file
        response = api.post(
            "/api/documents", files={"file": (path.name, path.read_bytes(), media_type(path))}
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
                    text=chunk.get("text", ""),
                )
            )
    return refs


def _search_with_promptfoo(
    cases: list[Any], api_url: str, results_dir: Path, started_at: datetime
) -> dict[str, dict[str, Response]]:
    return responses_by_mode(_promptfoo(PROMPTFOO_CONFIG, cases, api_url, results_dir, started_at))


def _promptfoo(
    suite: Path, cases: list[Any], api_url: str, results_dir: Path, started_at: datetime
) -> dict[str, Any]:
    """Promptfoo's JSON output for the suite's provider(s) over the cases."""
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
        command_line(Path(_executable("pnpm")), suite, tests, output),
        env=environment(os.environ, api_url),
        check=True,
        timeout=PROMPTFOO_SECONDS,
    )
    decoded: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    return decoded


def _score(
    cases: list[Any],
    expected: Mapping[str, frozenset[str]],
    responses: Mapping[str, Response],
    threshold: float,
    warm_up_ms: float,
) -> ModeResult:
    results = [
        CaseResult(case.id, case.behaviour, expected[case.id], responses[case.id].hits)
        for case in cases
    ]
    return ModeResult(
        metrics=compute(results, threshold),
        latency=latency([response.latency_ms for response in responses.values()]),
        out_of_scope_top_similarity=top_out_of_scope_similarity(results),
        warm_up_ms=warm_up_ms,
    )


def _stop(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is None:
        os.killpg(server.pid, signal.SIGTERM)
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, signal.SIGKILL)
            server.wait()


# What the API's reranker runs with on this machine, from the backend's own rules.
RERANKER_SETTINGS = (
    "import json, torch; "
    "from assistant.adapters.bge_reranker import precision_for; "
    "from assistant.services.questions import RERANK_CANDIDATES; "
    "device = 'mps' if torch.backends.mps.is_available() else 'cpu'; "
    "print(json.dumps({'rerank_candidates': RERANK_CANDIDATES, "
    "'reranker_device': device, 'reranker_precision': precision_for(device)}))"
)


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
            "reranker": "on",
            **json.loads(
                _command(
                    [
                        "uv",
                        "run",
                        "--directory",
                        str(ROOT / "backend"),
                        "python",
                        "-c",
                        RERANKER_SETTINGS,
                    ]
                )
            ),
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
    """`make eval`: the retrieval suite; `make eval-answers` (`--answers`): the answer suite."""
    if sys.argv[1:] == ["--answers"]:
        config = default_answers_config(os.environ)
        outcome = run_answers(config)
    else:
        config = default_config(os.environ)
        outcome = run(config)
    print(outcome.report_markdown.read_text(encoding="utf-8"))
    print(f"Report: {outcome.report_json}")
    if not config.baseline.exists():
        print(f"No baseline at {config.baseline}; this run can become it.")
    if outcome.gate_failures:
        sys.exit(
            "Gate failures:\n" + "\n".join(f"- {failure}" for failure in outcome.gate_failures)
        )


if __name__ == "__main__":
    main()
