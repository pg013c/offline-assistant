import json

import pytest

from assistant.domain.answers import (
    ANSWER_SCHEMA,
    AnswerTextExtractor,
    InvalidAnswer,
    ModelAnswer,
    parse_answer,
)


def raw(answer: object, covered: object = True) -> str:
    return json.dumps({"answer": answer, "covered": covered})


def test_the_markers_in_the_text_are_the_cited_passages_in_their_first_order() -> None:
    text = "Logs are kept for six months [2]. Providers keep them [1][2]."

    assert parse_answer(raw(text), passage_count=3) == ModelAnswer(
        text=text, cited=(2, 1), covered=True
    )


def test_a_marker_may_list_several_passages() -> None:
    assert parse_answer(raw("Logs are kept [3, 1]."), passage_count=3).cited == (3, 1)


def test_a_marker_after_the_full_stop_belongs_to_its_sentence() -> None:
    assert parse_answer(raw("Logs are kept. [1] Providers keep them. [2]"), 2).cited == (1, 2)


def test_an_answer_that_is_not_covered_has_no_citations() -> None:
    text = "The documents do not say what penalties apply."

    assert parse_answer(raw(text, covered=False), passage_count=3) == ModelAnswer(
        text=text, cited=(), covered=False
    )


@pytest.mark.parametrize(
    "text",
    [
        "Art. 83 sets the conditions for fines [1]. They must be effective [1].",
        "Zgodnie z art. 17 ust. 1 osoba może żądać usunięcia [1]. Administrator usuwa je [2].",
        "Some systems, e.g. Annex III systems, are high-risk [1].",
        "Fines reach EUR 20 000 000 or 4 % of turnover, i.e. Whichever is higher applies [2].",
        "See pkt. 3 and lit. A of the annex [1].",
        "Under Article 6. Paragraph 2 lists further systems [1].",
    ],
)
def test_abbreviations_and_numbers_do_not_end_a_sentence(text: str) -> None:
    assert parse_answer(raw(text), passage_count=2).covered is True


@pytest.mark.parametrize(
    ("text", "sentence"),
    [
        ("Logs are kept for six months [1]. Providers keep them.", "Providers keep them."),
        ("Logs are kept for six months. Providers keep them [1].", "Logs are kept for six months."),
        ("Is it allowed? Yes, with consent [1].", "Is it allowed?"),
        ("- First duty [1]\n- Second duty", "- Second duty"),
        ("Dane są usuwane [1]. Administrator informuje osobę.", "Administrator informuje osobę."),
    ],
)
def test_a_sentence_without_a_marker_is_rejected_and_quoted(text: str, sentence: str) -> None:
    with pytest.raises(InvalidAnswer, match="cites no passage") as raised:
        parse_answer(raw(text), passage_count=2)

    assert f'"{sentence}"' in str(raised.value)


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        ('{"answer": "Logs."', "not valid JSON"),
        ("[1, 2]", "not a JSON object with answer and covered"),
        (raw("", True), "the answer is empty"),
        (raw("   ", False), "the answer is empty"),
        (raw("Logs are kept."), "cites no passage"),
        (raw("Logs [0]."), "passage 0 does not exist; cite passages 1 to 3"),
        (raw("Logs [4]."), "passage 4 does not exist; cite passages 1 to 3"),
        (raw("Logs [1].", "yes"), "not a JSON object with answer and covered"),
        (raw("Not covered, see [1].", False), "an answer that is not covered cites no passage"),
        (json.dumps({"answer": "Logs [1].", "citations": [1]}), "answer and covered"),
    ],
)
def test_invalid_answers_are_rejected_with_a_reason_the_model_can_act_on(
    output: str, reason: str
) -> None:
    with pytest.raises(InvalidAnswer, match=reason):
        parse_answer(output, passage_count=3)


def test_the_schema_asks_for_the_answer_before_whether_it_is_covered() -> None:
    assert list(ANSWER_SCHEMA["properties"]) == ["answer", "covered"]
    assert ANSWER_SCHEMA["required"] == ["answer", "covered"]


def feed(chunks: list[str]) -> list[str]:
    extractor = AnswerTextExtractor()
    return [extractor.feed(chunk) for chunk in chunks]


def test_the_answer_text_comes_out_as_it_arrives() -> None:
    assert feed(['{"ans', 'wer": "Provi', "ders keep", ' logs.", "covered": true}']) == [
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
    assert feed(['{"answer": "Done."', ', "covered": true}']) == ["Done.", ""]


def test_a_malformed_escape_ends_the_streamed_text_instead_of_failing() -> None:
    extractor = AnswerTextExtractor()

    assert extractor.feed('{"answer": "Logs \\uZZZZ are kept."}') == "Logs "
    assert extractor.feed(" more") == ""


def test_a_high_surrogate_without_its_low_half_ends_the_streamed_text() -> None:
    extractor = AnswerTextExtractor()

    assert extractor.feed('{"answer": "Smile \\ud83d and \\u0041"}') == "Smile "
