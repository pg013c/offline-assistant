"""The judge's calibration (ADR 0022): fixed answers with hand verdicts.

Every judged run judges these answers again. Agreement below the bar fails the run, since
verdicts from a judge that disagrees with people cannot be reported.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from harness.answers import cited_numbers, statements_of
from harness.judge import JudgedSentence, JudgeInput, Verdict

AGREEMENT_BAR = 0.85
CALIBRATION_FILE = Path(__file__).parents[1] / "datasets" / "calibration.yaml"


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
    """The fixed answers and their hand verdicts."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [_item(entry) for entry in document["items"]]


def _item(entry: Mapping[str, Any]) -> CalibrationItem:
    answer = str(entry["answer"])
    sentences = tuple(
        JudgedSentence(index=index, text=text, cites=cited_numbers(text))
        for index, text in enumerate(statements_of(answer), start=1)
    )
    expected = entry["expected"]
    return CalibrationItem(
        id=str(entry["id"]),
        judged=JudgeInput(
            question=str(entry["question"]),
            key_points=tuple(entry["key_points"]),
            answer=answer,
            sentences=sentences,
            passages={int(number): str(text) for number, text in entry["passages"].items()},
        ),
        expected=Verdict(
            correctness=cast(Literal["correct", "partial", "wrong"], expected["correctness"]),
            reason=str(expected["reason"]),
            supported={int(index): bool(value) for index, value in expected["supported"].items()},
        ),
    )


def agreement(
    items: Sequence[CalibrationItem], verdicts: Mapping[str, Verdict | None]
) -> Agreement:
    """Shares of hand verdicts the judge matched; an item it could not judge disagrees."""
    correct = supported = sentences = 0
    for item in items:
        verdict = verdicts.get(item.id)
        correct += verdict is not None and verdict.correctness == item.expected.correctness
        for index, expected in item.expected.supported.items():
            sentences += 1
            supported += verdict is not None and verdict.supported.get(index) == expected
    return Agreement(
        correctness=correct / len(items) if items else 0.0,
        support=supported / sentences if sentences else 0.0,
        items=len(items),
    )


def calibration_failures(result: Agreement) -> list[str]:
    """One message per kind of verdict where the judge agrees with people too rarely."""
    return [
        f"the judge agrees with the calibration set on {share * 100:.1f} % of {kind} verdicts, "
        f"below {AGREEMENT_BAR * 100:.0f} % (ADR 0022)"
        for kind, share in (("correctness", result.correctness), ("support", result.support))
        if share < AGREEMENT_BAR - 1e-9
    ]
