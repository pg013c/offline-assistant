from pathlib import Path

from harness.calibration import (
    AGREEMENT_BAR,
    CALIBRATION_FILE,
    CalibrationItem,
    agreement,
    calibration_failures,
    load_calibration,
)
from harness.judge import JudgedSentence, Verdict

CALIBRATION = """version: 1
items:
  - id: cal-01
    question: Within how many hours must a breach be notified?
    key_points: [Within 72 hours where feasible.]
    answer: Within 72 hours [1]. Fines are high [1].
    passages: {1: "... not later than 72 hours ..."}
    expected:
      correctness: partial
      reason: The second sentence is not in the passage.
      supported: {1: true, 2: false}
"""


def items(tmp_path: Path) -> list[CalibrationItem]:
    path = tmp_path / "calibration.yaml"
    path.write_text(CALIBRATION, encoding="utf-8")
    return load_calibration(path)


def test_a_calibration_item_is_a_fixed_answer_with_its_hand_verdict(tmp_path: Path) -> None:
    [item] = items(tmp_path)

    assert item.judged.question == "Within how many hours must a breach be notified?"
    assert item.judged.sentences == (
        JudgedSentence(index=1, text="Within 72 hours [1].", cites=(1,)),
        JudgedSentence(index=2, text="Fines are high [1].", cites=(1,)),
    )
    assert item.judged.passages == {1: "... not later than 72 hours ..."}
    assert item.expected.correctness == "partial"
    assert item.expected.supported == {1: True, 2: False}


def test_agreement_is_counted_for_correctness_and_for_each_cited_sentence(tmp_path: Path) -> None:
    [item] = items(tmp_path)
    judged = {"cal-01": Verdict("partial", "x", {1: True, 2: True})}

    result = agreement([item], judged)

    assert (result.correctness, result.support) == (1.0, 0.5)


def test_an_item_the_judge_could_not_judge_counts_as_disagreement(tmp_path: Path) -> None:
    [item] = items(tmp_path)

    result = agreement([item], {"cal-01": None})

    assert (result.correctness, result.support) == (0.0, 0.0)


def test_a_judge_below_the_bar_fails_the_run() -> None:
    assert AGREEMENT_BAR == 0.85
    assert calibration_failures(agreement_result(0.9, 0.8)) == [
        "the judge agrees with the calibration set on 80.0 % of support verdicts, "
        "below 85 % (ADR 0022)"
    ]
    assert calibration_failures(agreement_result(0.9, 0.9)) == []


def agreement_result(correctness: float, support: float):  # type: ignore[no-untyped-def]
    from harness.calibration import Agreement  # noqa: PLC0415

    return Agreement(correctness=correctness, support=support, items=20)


def test_the_repository_calibration_set_is_the_one_a_run_uses() -> None:
    path = Path(__file__).parents[1] / "datasets" / "calibration.yaml"

    assert path == CALIBRATION_FILE
    assert len(load_calibration(path)) == 20
