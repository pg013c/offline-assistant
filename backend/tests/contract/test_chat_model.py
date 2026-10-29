"""Contract for the ChatModel port; every adapter must pass it."""

import asyncio
from collections.abc import AsyncIterator, Callable

import pytest

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.domain.answers import (
    Answered,
    AttemptDiscarded,
    ModelEvent,
    ModelFailed,
    TextDelta,
)
from assistant.domain.documents import Chunk
from assistant.ports.chat_model import ChatModel

ADAPTERS: list[Callable[[], ChatModel]] = [FakeExtractiveChatModel]

PASSAGES = [
    Chunk(
        id="doc:0",
        document_id="doc",
        position=0,
        text="Providers shall keep logs. Logs are kept for six months. Authorities may ask.",
    ),
    Chunk(id="doc:1", document_id="doc", position=1, text="Member states designate bodies."),
]


@pytest.fixture(params=ADAPTERS, ids=lambda adapter: adapter.__name__)
def model(request: pytest.FixtureRequest) -> ChatModel:
    factory: Callable[[], ChatModel] = request.param
    return factory()


def collect(stream: AsyncIterator[ModelEvent]) -> list[ModelEvent]:
    async def gather() -> list[ModelEvent]:
        return [event async for event in stream]

    return asyncio.run(gather())


def test_has_a_model_id(model: ChatModel) -> None:
    assert model.model_id


def test_declares_whether_it_is_a_test_model(model: ChatModel) -> None:
    assert isinstance(model.is_test_model, bool)


def test_an_answer_streams_text_and_ends_with_exactly_one_outcome(model: ChatModel) -> None:
    events = collect(model.answer("How long are logs kept?", PASSAGES))

    assert any(isinstance(event, TextDelta) for event in events)
    outcomes = [event for event in events if isinstance(event, Answered | ModelFailed)]
    assert len(outcomes) == 1
    assert events[-1] is outcomes[0]


def test_the_streamed_text_of_the_last_attempt_is_the_answer(model: ChatModel) -> None:
    events = collect(model.answer("How long are logs kept?", PASSAGES))

    outcome = events[-1]
    assert isinstance(outcome, Answered)
    last_attempt = events[
        max((i for i, e in enumerate(events) if isinstance(e, AttemptDiscarded)), default=-1) + 1 :
    ]
    streamed = "".join(event.text for event in last_attempt if isinstance(event, TextDelta))
    assert streamed == outcome.answer.text
    assert outcome.answer.text.strip()


def test_an_answer_cites_only_passages_it_was_given(model: ChatModel) -> None:
    outcome = collect(model.answer("How long are logs kept?", PASSAGES))[-1]

    assert isinstance(outcome, Answered)
    assert outcome.answer.cited
    assert all(1 <= number <= len(PASSAGES) for number in outcome.answer.cited)
    assert outcome.usage.attempts >= 1
