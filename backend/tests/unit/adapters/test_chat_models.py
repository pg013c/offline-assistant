import httpx
import pytest

from assistant.adapters.chat_models import CHAT_MODELS, ChatModelNotReady, chat_model_for
from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.openai_compatible_chat import OpenAICompatibleChat
from assistant.adapters.pinned_models import LLM_MODELS, PINNED_MODELS, QWEN3_8B
from assistant.settings import Settings

URL = "http://127.0.0.1:8080"


def settings(chat_model: str) -> Settings:
    return Settings.model_validate(
        {"data_dir": "data", "models_dir": "models", "chat_model": chat_model}
    )


def serving(*names: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(f"{URL}/v1/models")
        return httpx.Response(200, json={"object": "list", "data": [{"id": n} for n in names]})

    return httpx.MockTransport(handler)


def test_the_catalogue_has_the_test_model_and_qwen3_8b() -> None:
    assert set(CHAT_MODELS) == {"fake-extractive", "qwen3-8b"}
    assert CHAT_MODELS["qwen3-8b"].tools is True
    assert CHAT_MODELS["qwen3-8b"].pinned == QWEN3_8B


def test_the_test_model_needs_no_server() -> None:
    assert isinstance(chat_model_for(settings("fake-extractive")), FakeExtractiveChatModel)


def test_a_served_model_is_answered_by_the_openai_compatible_adapter() -> None:
    model = chat_model_for(settings("qwen3-8b"), transport=serving("qwen3-8b"))

    assert isinstance(model, OpenAICompatibleChat)
    assert model.model_id == "qwen3-8b"
    assert model.is_test_model is False


def test_without_a_server_startup_fails_naming_the_variable_and_the_command() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ChatModelNotReady, match=r"ASSISTANT_LLM_URL.*make llm"):
        chat_model_for(settings("qwen3-8b"), transport=httpx.MockTransport(refused))


def test_a_server_serving_another_model_fails_naming_both() -> None:
    with pytest.raises(ChatModelNotReady, match=r"does not serve qwen3-8b.*other-model"):
        chat_model_for(settings("qwen3-8b"), transport=serving("other-model"))


def test_the_llm_is_pinned_as_adr_0021_says_and_kept_apart_from_make_models() -> None:
    assert QWEN3_8B.repository == "Qwen/Qwen3-8B-GGUF"
    assert QWEN3_8B.revision == "7c41481f57cb95916b40956ab2f0b139b296d974"
    assert QWEN3_8B.files == {
        "Qwen3-8B-Q4_K_M.gguf": "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
    }
    assert QWEN3_8B in LLM_MODELS
    assert QWEN3_8B not in PINNED_MODELS


@pytest.mark.parametrize(
    "body",
    [b"<html>not a model server</html>", b'{"data": [{"name": "no id"}]}', b'"just a string"'],
)
def test_a_server_that_does_not_list_models_fails_with_the_command(body: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(ChatModelNotReady, match="make llm"):
        chat_model_for(settings("qwen3-8b"), transport=httpx.MockTransport(handler))


def test_each_served_model_declares_its_capabilities() -> None:
    qwen = CHAT_MODELS["qwen3-8b"]

    assert (qwen.tools, qwen.json_schema, qwen.streaming) == (True, True, True)
