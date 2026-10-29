import json

import pytest

from assistant.domain.answers import (
    ANSWER_SCHEMA,
    AnswerTextExtractor,
    InvalidAnswer,
    ModelAnswer,
    parse_answer,
)


def raw(answer: object, citations: object) -> str:
    return json.dumps({"answer": answer, "citations": citations})


def test_a_valid_answer_parses_with_its_cited_passages() -> None:
    assert parse_answer(raw("Providers keep logs.", [2, 1]), passage_count=3) == ModelAnswer(
        text="Providers keep logs.", cited=(2, 1)
    )


def test_repeated_citations_are_kept_once_in_their_first_order() -> None:
    assert parse_answer(raw("Logs.", [2, 1, 2]), passage_count=2).cited == (2, 1)


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        ('{"answer": "Logs."', "not valid JSON"),
        ("[1, 2]", "not a JSON object with answer and citations"),
        (raw("", [1]), "the answer is empty"),
        (raw("   ", [1]), "the answer is empty"),
        (raw("Logs.", []), "the answer cites no passage"),
        (raw("Logs.", [0]), "passage 0 does not exist; cite passages 1 to 3"),
        (raw("Logs.", [4]), "passage 4 does not exist; cite passages 1 to 3"),
        (raw("Logs.", ["1"]), "not a JSON object with answer and citations"),
    ],
)
def test_invalid_answers_are_rejected_with_a_reason_the_model_can_act_on(
    output: str, reason: str
) -> None:
    with pytest.raises(InvalidAnswer, match=reason):
        parse_answer(output, passage_count=3)


def test_the_schema_asks_for_the_answer_before_the_citations() -> None:
    assert list(ANSWER_SCHEMA["properties"]) == ["answer", "citations"]
    assert ANSWER_SCHEMA["required"] == ["answer", "citations"]


def feed(chunks: list[str]) -> list[str]:
    extractor = AnswerTextExtractor()
    return [extractor.feed(chunk) for chunk in chunks]


def test_the_answer_text_comes_out_as_it_arrives() -> None:
    assert feed(['{"ans', 'wer": "Provi', "ders keep", ' logs.", "citations": [1]}']) == [
        "",
        "Provi",
        "ders keep",
        " logs.",
    ]


def test_whitespace_between_tokens_is_allowed() -> None:
    assert "".join(feed(['{\n  "answer" :  "Tak', '."\n}'])) == "Tak."


def test_escapes_are_decoded_even_when_split_between_chunks() -> None:
    chunks = ['{"answer": "Line\\', 'nTab\\t\\"quoted\\" \\u00', "f3 and \\ud83d", '\\ude00"}']

    assert "".join(feed(chunks)) == 'Line\nTab\t"quoted" ó and 😀'


def test_nothing_after_the_answer_string_is_returned() -> None:
    assert feed(['{"answer": "Done."', ', "citations": [1, 2]}']) == ["Done.", ""]


def test_a_malformed_escape_ends_the_streamed_text_instead_of_failing() -> None:
    extractor = AnswerTextExtractor()

    assert extractor.feed('{"answer": "Logs \\uZZZZ are kept."}') == "Logs "
    assert extractor.feed(" more") == ""


def test_a_high_surrogate_without_its_low_half_ends_the_streamed_text() -> None:
    extractor = AnswerTextExtractor()

    assert extractor.feed('{"answer": "Smile \\ud83d and \\u0041"}') == "Smile "
