from collections import Counter
from pathlib import Path

import pytest

from harness.dataset import DatasetError, load_cases

DATASET = Path(__file__).parents[1] / "datasets" / "retrieval.yaml"


def test_every_case_validates_and_ids_are_unique() -> None:
    cases = load_cases(DATASET)

    assert len(cases) == 24
    assert len({case.id for case in cases}) == len(cases)


def test_the_dataset_covers_both_languages_and_every_kind() -> None:
    cases = load_cases(DATASET)

    assert {case.language for case in cases} == {"en", "pl"}
    assert Counter(case.kind for case in cases) == {
        "single-article": 12,
        "cross-language": 4,
        "exact-reference": 3,
        "spans-articles": 2,
        "out-of-scope": 3,
    }


def test_out_of_scope_cases_expect_a_refusal_and_no_source() -> None:
    for case in load_cases(DATASET):
        assert (case.kind == "out-of-scope") == (case.behaviour == "refuse")
        assert (case.behaviour == "refuse") == (case.sources == ())


def test_a_case_that_breaks_the_schema_is_rejected_with_its_id(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "version: 1\ncases:\n  - id: bad-case\n    kind: single-article\n    language: de\n"
        "    question: Was?\n    expected: {behaviour: answer, sources: []}\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="bad-case"):
        load_cases(broken)
