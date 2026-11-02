from typing import get_args

import httpx
import pytest

from assistant.adapters import chat_models, pinned_models
from assistant.adapters.chat_models import (
    CHAT_MODELS,
    ChatModelNotReady,
    chat_model_for,
    tool_model_for,
)
from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.openai_compatible_chat import OpenAICompatibleChat
from assistant.adapters.pinned_models import (
    GEMMA_4_26B_A4B,
    JUDGE_MODELS,
    PINNED_MODELS,
    QWEN3_6_35B_A3B,
    PinnedModel,
)
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


# The served models ADR 0026 keeps, pinned as ADR 0024 says: name -> repository, revision,
# file and SHA-256.
CANDIDATES = {
    "qwen3.5-9b": (
        "unsloth/Qwen3.5-9B-GGUF",
        "3885219b6810b007914f3a7950a8d1b469d598a5",
        "Qwen3.5-9B-Q4_K_M.gguf",
        "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8",
    ),
    "qwen3.6-35b-a3b": (
        "ggml-org/Qwen3.6-35B-A3B-GGUF",
        "7878dc9a905c7c9379e5e8d6a1aa9affdd6839c5",
        "Qwen3.6-35B-A3B-Q4_K_M.gguf",
        "671e47e0ec53c665d048b98c3ecbfd5236b5ca9c3e02ed19fc8f81f7b85140c7",
    ),
    "gemma-4-26b-a4b": (
        "google/gemma-4-26B-A4B-it-qat-q4_0-gguf",
        "d1c082be9cf3c8a514acf63b8761f4b41935842e",
        "gemma-4-26B_q4_0-it.gguf",
        "3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d",
    ),
}


def test_the_catalogue_has_the_test_model_and_the_models_adr_0026_keeps() -> None:
    assert set(CHAT_MODELS) == {"fake-extractive", *CANDIDATES}
    assert CHAT_MODELS["qwen3.5-9b"].tools is True


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_each_candidate_is_pinned_as_adr_0024_says(name: str) -> None:
    repository, revision, file, sha256 = CANDIDATES[name]
    assert name in CHAT_MODELS
    pinned = CHAT_MODELS[name].pinned

    assert pinned is not None
    assert (pinned.repository, pinned.revision, pinned.files) == (
        repository,
        revision,
        {file: sha256},
    )
    assert pinned.directory == "llm/" + repository.replace("/", "--")
    assert pinned not in PINNED_MODELS


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_each_candidate_is_served_under_its_name_with_every_capability(name: str) -> None:
    assert name in CHAT_MODELS
    spec = CHAT_MODELS[name]

    assert spec.served_model == name
    assert (spec.tools, spec.json_schema, spec.streaming) == (True, True, True)


def test_the_settings_accept_exactly_the_catalogue_names() -> None:
    assert set(get_args(Settings.model_fields["chat_model"].annotation)) == set(CHAT_MODELS)


def test_the_registry_is_the_only_list_of_served_models() -> None:
    # A second list beside CHAT_MODELS could drift from it (F-09b review #5).
    assert not hasattr(pinned_models, "LLM_MODELS")


def test_the_test_model_needs_no_server() -> None:
    assert isinstance(chat_model_for(settings("fake-extractive")), FakeExtractiveChatModel)


def test_a_served_model_is_answered_by_the_openai_compatible_adapter() -> None:
    model = chat_model_for(settings("qwen3.5-9b"), transport=serving("qwen3.5-9b"))

    assert isinstance(model, OpenAICompatibleChat)
    assert model.model_id == "qwen3.5-9b"
    assert model.is_test_model is False


def test_without_a_server_startup_fails_naming_the_variable_and_the_command() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ChatModelNotReady, match=r"ASSISTANT_LLM_URL.*make llm"):
        chat_model_for(settings("qwen3.5-9b"), transport=httpx.MockTransport(refused))


def test_a_server_serving_another_model_fails_naming_both() -> None:
    with pytest.raises(ChatModelNotReady, match=r"does not serve qwen3.5-9b.*other-model"):
        chat_model_for(settings("qwen3.5-9b"), transport=serving("other-model"))


@pytest.mark.parametrize("repository", ["Qwen/Qwen3-8B-GGUF", "prism-ml/Ternary-Bonsai-2-27B-gguf"])
def test_the_models_adr_0026_removes_are_no_longer_pinned(repository: str) -> None:
    pins = [value for value in vars(pinned_models).values() if isinstance(value, PinnedModel)]

    assert all(pin.repository != repository for pin in pins)


def test_the_judge_is_gemma_4_and_its_check_is_qwen3_6_as_adr_0025_says() -> None:
    assert JUDGE_MODELS == {"gemma-4-26b-a4b": GEMMA_4_26B_A4B, "qwen3.6-35b-a3b": QWEN3_6_35B_A3B}
    assert next(iter(JUDGE_MODELS)) == "gemma-4-26b-a4b", "the first judge is the default"
    assert all(model not in PINNED_MODELS for model in JUDGE_MODELS.values())


def test_qwen3_30b_a3b_is_no_longer_pinned() -> None:
    pins = [value for value in vars(pinned_models).values() if isinstance(value, PinnedModel)]

    assert all(pin.repository != "Qwen/Qwen3-30B-A3B-GGUF" for pin in pins)


@pytest.mark.parametrize(
    "body",
    [b"<html>not a model server</html>", b'{"data": [{"name": "no id"}]}', b'"just a string"'],
)
def test_a_server_that_does_not_list_models_fails_with_the_command(body: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(ChatModelNotReady, match="make llm"):
        chat_model_for(settings("qwen3.5-9b"), transport=httpx.MockTransport(handler))


def test_each_served_model_declares_its_capabilities() -> None:
    qwen = CHAT_MODELS["qwen3.5-9b"]

    assert (qwen.tools, qwen.json_schema, qwen.streaming) == (True, True, True)


def test_a_model_declared_able_to_call_tools_is_the_agent() -> None:
    model = chat_model_for(settings("qwen3.5-9b"), transport=serving("qwen3.5-9b"))

    assert tool_model_for(settings("qwen3.5-9b"), model) is model


def test_the_test_model_is_no_agent() -> None:
    model = chat_model_for(settings("fake-extractive"))

    assert tool_model_for(settings("fake-extractive"), model) is None


def test_the_registry_names_the_default_model_of_adr_0026() -> None:
    default = getattr(chat_models, "DEFAULT_CHAT_MODEL", None)

    assert default == "qwen3.5-9b"
    assert CHAT_MODELS[default].pinned is not None
