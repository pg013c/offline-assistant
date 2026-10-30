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


def stub_openai_compatible() -> ChatModel:
    """The real adapter against a stub server that answers validly (AC-5)."""
    import json  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    from assistant.adapters.openai_compatible_chat import LlmServer, OpenAICompatibleChat  # noqa: PLC0415

    content = json.dumps({"answer": "Logs are kept for six months.", "citations": [1]})
    pieces = [content[i : i + 7] for i in range(0, len(content), 7)]
    lines: list[dict[str, object]] = [
        {"choices": [{"index": 0, "delta": {"content": piece}}]} for piece in pieces
    ]
    lines.append({"choices": [], "usage": {"prompt_tokens": 50, "completion_tokens": 12}})
    body = "".join(f"data: {json.dumps(line)}\n\n" for line in lines) + "data: [DONE]\n\n"

    def server(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body.encode())

    return OpenAICompatibleChat(
        model_id="stub",
        server=LlmServer(
            base_url="http://127.0.0.1:8080",
            served_model="stub",
            timeout_seconds=5,
            max_retries=2,
        ),
        transport=httpx.MockTransport(server),
    )


ADAPTERS: list[Callable[[], ChatModel]] = [FakeExtractiveChatModel, stub_openai_compatible]

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
