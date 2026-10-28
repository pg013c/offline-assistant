import asyncio

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.domain.documents import Chunk


def answer(passages: list[Chunk]) -> list[str]:
    async def gather() -> list[str]:
        model = FakeExtractiveChatModel()
        return [piece async for piece in model.stream_answer("question", passages)]

    return asyncio.run(gather())


def chunk(position: int, text: str) -> Chunk:
    return Chunk(id=f"doc:{position}", document_id="doc", position=position, text=text)


def test_identifies_itself_as_fake() -> None:
    model = FakeExtractiveChatModel()

    assert model.model_id == "fake-extractive"
    assert model.is_test_model is True


def test_answers_with_the_first_two_sentences_of_the_first_passage() -> None:
    pieces = answer(
        [
            chunk(0, "First sentence. Second sentence! Third sentence."),
            chunk(1, "Other passage."),
        ]
    )

    assert "".join(pieces) == "First sentence. Second sentence!"


def test_streams_word_by_word() -> None:
    pieces = answer([chunk(0, "One two three.")])

    assert pieces == ["One ", "two ", "three."]


def test_same_input_gives_the_same_output() -> None:
    passages = [chunk(0, "Stable answer. Always the same. Not this.")]

    assert answer(passages) == answer(passages)
