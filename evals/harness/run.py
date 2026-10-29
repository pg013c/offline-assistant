"""`make eval`: index the corpus through the API, run Promptfoo, score and report (F-04)."""

from dataclasses import dataclass
from pathlib import Path


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
    raise NotImplementedError
