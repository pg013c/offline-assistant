from collections import Counter
from pathlib import Path

import pytest
import yaml

from harness.dataset import DatasetError, load_answer_cases, load_cases

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


ANSWERS = Path(__file__).parents[1] / "datasets" / "answers.yaml"


def test_the_answer_suite_asks_every_retrieval_case_and_its_own() -> None:
    retrieval = load_cases(DATASET)
    answers = load_answer_cases(ANSWERS)

    assert [case.id for case in answers[: len(retrieval)]] == [case.id for case in retrieval]
    assert [case.id for case in answers[len(retrieval) :]] == [
        "adv-no-citations",
        "tool-get-article-pl",
        "tool-compare",
        "not-covered",
        "inj-follow-instruction",
        "inj-cite-nothing",
        "note-checklist-en",
        "note-checklist-pl",
        "inj-save-note",
        "inj-note-content",
        "en-gdpr-principles",
        "pl-gdpr-consent",
        "en-ai-human-oversight",
        "pl-ai-transparency",
        "en-gdpr-dpo-tasks",
        "pl-gdpr-access-and-rectification",
        "pl-gdpr-erasure-exceptions",
        "cmp-fines-ai-and-gdpr",
        "cmp-pl-breach-and-incident",
        "not-covered-cctv",
        "not-covered-pl-fee",
        "inj-audit-logs",
        "inj-pl-orbit",
    ]
    assert len({case.id for case in answers}) == len(answers)


def test_the_adversarial_case_expects_a_cited_answer() -> None:
    adversarial = [case for case in load_answer_cases(ANSWERS) if case.kind == "adversarial"]

    assert adversarial
    for case in adversarial:
        assert case.behaviour == "answer"
        assert case.sources


def test_the_answer_suite_is_version_5() -> None:
    assert yaml.safe_load(ANSWERS.read_text(encoding="utf-8"))["version"] == 5


def test_injection_cases_expect_an_answer_from_the_injected_document() -> None:
    injected = {case.id: case for case in load_answer_cases(ANSWERS) if case.kind == "injection"}

    assert set(injected) == {
        "inj-follow-instruction",
        "inj-cite-nothing",
        "inj-save-note",
        "inj-note-content",
        "inj-audit-logs",
        "inj-pl-orbit",
    }
    for case in injected.values():
        assert case.behaviour == "answer"
        assert case.sources
        assert all(source.document.startswith("injected-") for source in case.sources)
    assert "PWNED" in injected["inj-follow-instruction"].forbidden


def test_not_covered_cases_expect_no_source() -> None:
    not_covered = [case for case in load_answer_cases(ANSWERS) if case.behaviour == "not_covered"]

    assert [case.id for case in not_covered] == [
        "not-covered",
        "not-covered-cctv",
        "not-covered-pl-fee",
    ]
    assert all(case.sources == () for case in not_covered)


def test_tool_cases_name_the_tools_any_of_which_answers_them() -> None:
    by_id = {case.id: case for case in load_answer_cases(ANSWERS)}

    assert by_id["tool-get-article-pl"].tools == ("get_article",)
    assert set(by_id["tool-compare"].tools) == {"compare", "get_article"}
    assert by_id["en-gdpr-erasure"].tools == ()
    assert by_id["en-gdpr-erasure"].forbidden == ()


def test_a_retrieval_case_cannot_use_the_answer_only_fields(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "version: 1\ncases:\n  - id: bad-case\n    kind: single-article\n    language: en\n"
        "    question: Why?\n    expected: {behaviour: not_covered, sources: []}\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="bad-case"):
        load_cases(broken)


def test_only_the_note_cases_expect_a_note() -> None:
    cases = load_answer_cases(ANSWERS)

    assert [case.id for case in cases if case.note] == [
        "note-checklist-en",
        "note-checklist-pl",
        "inj-note-content",
    ]
    by_id = {case.id: case for case in cases}
    assert by_id["note-checklist-pl"].language == "pl"
    assert by_id["inj-save-note"].note is False
    assert all(case.sources for case in cases if case.note)


def test_a_retrieval_case_cannot_expect_a_note(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "version: 1\ncases:\n  - id: bad-case\n    kind: single-article\n    language: en\n"
        "    question: Why?\n    expected: {behaviour: answer, sources: [], note: true}\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="bad-case"):
        load_cases(broken)


def test_the_answer_suite_holds_40_to_50_cases_in_both_languages() -> None:
    cases = load_answer_cases(ANSWERS)

    assert 40 <= len(cases) <= 50
    assert Counter(case.language for case in cases)["pl"] >= 15


def test_every_answerable_case_has_one_to_four_key_points() -> None:
    for case in load_answer_cases(ANSWERS):
        if case.behaviour == "answer":
            assert 1 <= len(case.key_points) <= 4, case.id
        else:
            assert case.key_points == (), case.id


def test_reference_answers_name_answerable_retrieval_cases_only() -> None:
    references = yaml.safe_load(ANSWERS.read_text(encoding="utf-8"))["references"]
    retrieval = {case.id: case for case in load_cases(DATASET)}

    assert set(references) == {
        case_id for case_id, case in retrieval.items() if case.behaviour == "answer"
    }


def test_a_reference_for_an_unknown_case_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "retrieval.yaml").write_text(DATASET.read_text(encoding="utf-8"), encoding="utf-8")
    broken = tmp_path / "answers.yaml"
    broken.write_text(
        "version: 5\nreuse: retrieval.yaml\n"
        "references:\n  no-such-case: [Something said.]\ncases: []\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="no-such-case"):
        load_answer_cases(broken)


def test_the_new_kinds_are_covered() -> None:
    kinds = Counter(case.kind for case in load_answer_cases(ANSWERS))

    assert kinds["injection"] >= 6
    assert kinds["not-covered"] >= 3
    assert kinds["tool-use"] >= 6
    assert kinds["spans-articles"] >= 3
