import pytest

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel, ScriptedChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.domain.errors import UnknownModel
from assistant.services.models import ChatModels, ModelChoice, ModelEntry
from assistant.services.questions import QuestionService


def answerer(model: FakeExtractiveChatModel | ScriptedChatModel) -> QuestionService:
    return QuestionService(InMemoryChunkIndex(), model, FakeDocumentStore(), min_similarity=0)


LOCAL = answerer(ScriptedChatModel([], model_id="qwen3-8b"))
TEST = answerer(FakeExtractiveChatModel())


def models() -> ChatModels:
    return ChatModels(
        [
            ModelEntry(id="qwen3-8b", is_test_model=False, answerer=LOCAL),
            ModelEntry(id="fake-extractive", is_test_model=True, answerer=TEST),
        ]
    )


def test_the_models_are_listed_with_the_first_as_the_default() -> None:
    assert models().list_models() == [
        ModelChoice(id="qwen3-8b", is_test_model=False, is_default=True),
        ModelChoice(id="fake-extractive", is_test_model=True, is_default=False),
    ]


def test_no_model_named_is_the_default() -> None:
    assert models().answerer(None) is LOCAL


def test_a_named_model_answers() -> None:
    assert models().answerer("fake-extractive") is TEST


def test_an_unknown_model_is_an_error_naming_the_models() -> None:
    with pytest.raises(UnknownModel, match="qwen3-8b, fake-extractive"):
        models().answerer("gpt-latest")
