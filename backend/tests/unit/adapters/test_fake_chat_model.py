import asyncio

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel, ScriptedChatModel
from assistant.domain.answers import (
    Answered,
    AttemptDiscarded,
    ModelAnswer,
    ModelEvent,
    ModelFailed,
    TextDelta,
    Usage,
)
from assistant.domain.documents import Chunk


def answer(model: object, passages: list[Chunk]) -> list[ModelEvent]:
    async def gather() -> list[ModelEvent]:
        assert isinstance(model, FakeExtractiveChatModel | ScriptedChatModel)
        return [event async for event in model.answer("question", passages)]

    return asyncio.run(gather())


def chunk(position: int, text: str) -> Chunk:
    return Chunk(id=f"doc:{position}", document_id="doc", position=position, text=text)


def test_identifies_itself_as_fake() -> None:
    model = FakeExtractiveChatModel()

    assert model.model_id == "fake-extractive"
    assert model.is_test_model is True


def test_answers_with_the_first_two_sentences_of_the_first_passage_and_marks_its_citation() -> None:
    events = answer(
        FakeExtractiveChatModel(),
        [chunk(0, "First sentence. Second sentence! Third sentence."), chunk(1, "Other.")],
    )

    outcome = events[-1]
    assert isinstance(outcome, Answered)
    assert outcome.answer == ModelAnswer(
        text="First sentence. Second sentence! [1]", cited=(1,), covered=True
    )


def test_streams_word_by_word() -> None:
    events = answer(FakeExtractiveChatModel(), [chunk(0, "One two three.")])

    assert [event for event in events if isinstance(event, TextDelta)] == [
        TextDelta("One "),
        TextDelta("two "),
        TextDelta("three. "),
        TextDelta("[1]"),
    ]


def test_same_input_gives_the_same_output() -> None:
    passages = [chunk(0, "Stable answer. Always the same. Not this.")]

    assert answer(FakeExtractiveChatModel(), passages) == answer(
        FakeExtractiveChatModel(), passages
    )


def test_a_scripted_model_replays_its_events_and_counts_its_calls() -> None:
    script: list[ModelEvent] = [
        TextDelta("Wrong."),
        AttemptDiscarded("passage 9 does not exist; cite passages 1 to 1"),
        ModelFailed("invalid_answer", "the model could not produce a valid answer"),
    ]
    model = ScriptedChatModel(script, model_id="scripted")

    assert answer(model, [chunk(0, "Text.")]) == script
    assert model.calls == 1
    assert model.is_test_model is False


def test_usage_records_tokens_timings_and_attempts() -> None:
    usage = Usage(
        prompt_tokens=120, completion_tokens=40, first_token_ms=310.0, total_ms=900.0, attempts=2
    )

    assert usage.attempts == 2
