"""The judge's calibration (ADR 0022): fixed answers with hand verdicts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from harness.judge import JudgeInput, Verdict

AGREEMENT_BAR = 0.0


@dataclass(frozen=True)
class CalibrationItem:
    id: str
    judged: JudgeInput
    expected: Verdict


@dataclass(frozen=True)
class Agreement:
    correctness: float
    support: float
    items: int


def load_calibration(path: Path) -> list[CalibrationItem]:
    raise NotImplementedError


def agreement(
    items: Sequence[CalibrationItem], verdicts: Mapping[str, Verdict | None]
) -> Agreement:
    raise NotImplementedError


def calibration_failures(result: Agreement) -> list[str]:
    raise NotImplementedError
