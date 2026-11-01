import asyncio

import pytest

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel, ScriptedChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.domain.errors import UnknownModel
from assistant.services.models import ChatModels, ModelChoice, ModelEntry
from assistant.services.questions import QuestionService


def answerer(model: FakeExtractiveChatModel | ScriptedChatModel) -> QuestionService:
    return QuestionService(InMemoryChunkIndex(), model, FakeDocumentStore(), min_similarity=0)


LOCAL_MODEL = ScriptedChatModel([], model_id="qwen3-8b")
LOCAL = answerer(LOCAL_MODEL)
TEST = answerer(FakeExtractiveChatModel())


def models(local: ScriptedChatModel = LOCAL_MODEL) -> ChatModels:
    return ChatModels(
        [
            ModelEntry(id="qwen3-8b", is_test_model=False, answerer=LOCAL, model=local),
            ModelEntry(
                id="fake-extractive",
                is_test_model=True,
                answerer=TEST,
                model=FakeExtractiveChatModel(),
            ),
        ]
    )


def listed(chat_models: ChatModels) -> list[ModelChoice]:
    return asyncio.run(chat_models.list_models())


def test_the_models_are_listed_with_the_first_as_the_default() -> None:
    assert listed(models()) == [
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


def test_no_models_is_a_configuration_error() -> None:
    with pytest.raises(ValueError, match="at least one model"):
        ChatModels([])


def test_a_model_listed_twice_is_a_configuration_error() -> None:
    entry = ModelEntry(id="qwen3-8b", is_test_model=False, answerer=LOCAL, model=LOCAL_MODEL)

    with pytest.raises(ValueError, match="qwen3-8b is listed twice"):
        ChatModels([entry, entry])


def test_a_model_whose_server_stops_answering_is_left_out_and_listed_again_once_it_answers() -> (
    None
):
    local = ScriptedChatModel([], model_id="qwen3-8b")
    chat_models = models(local)

    local.available = False
    without = [choice.id for choice in listed(chat_models)]
    local.available = True
    again = [choice.id for choice in listed(chat_models)]

    assert without == ["fake-extractive"]
    assert again == ["qwen3-8b", "fake-extractive"]
