"""Contract for the ChatModel port; every adapter must pass it."""

import asyncio
from collections.abc import AsyncIterator, Callable

import pytest

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.domain.documents import Chunk
from assistant.ports.chat_model import ChatModel

ADAPTERS: list[Callable[[], ChatModel]] = [FakeExtractiveChatModel]

PASSAGE = Chunk(
    id="doc:0",
    document_id="doc",
    position=0,
    text="Providers shall keep logs. Logs are kept for six months. Authorities may ask for them.",
)


@pytest.fixture(params=ADAPTERS, ids=lambda adapter: adapter.__name__)
def model(request: pytest.FixtureRequest) -> ChatModel:
    factory: Callable[[], ChatModel] = request.param
    return factory()


def collect(stream: AsyncIterator[str]) -> list[str]:
    async def gather() -> list[str]:
        return [piece async for piece in stream]

    return asyncio.run(gather())


def test_has_a_model_id(model: ChatModel) -> None:
    assert model.model_id


def test_streams_a_non_empty_answer_in_pieces(model: ChatModel) -> None:
    pieces = collect(model.stream_answer("How long are logs kept?", [PASSAGE]))

    assert len(pieces) > 1
    assert "".join(pieces).strip()
