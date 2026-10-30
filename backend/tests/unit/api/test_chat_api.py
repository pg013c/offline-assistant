import json
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from assistant.adapters.fakes.chat_model import ScriptedChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.app import Adapters, create_app
from assistant.domain.answers import (
    Answered,
    AttemptDiscarded,
    ModelAnswer,
    ModelEvent,
    ModelFailed,
    TextDelta,
    Usage,
)
from assistant.domain.documents import Chunk, chunk_document, document_id_for
from assistant.domain.tools import (
    FinalText,
    Message,
    SearchDocumentsArguments,
    ToolCall,
    ToolCalls,
    ToolSpec,
)
from assistant.settings import Settings

# Fixtures from tests/conftest.py.
type ClientFor = Callable[[Path], TestClient]
type Settle = Callable[[TestClient, str], dict[str, Any]]
type Upload = Callable[..., None]


POLICY = (
    b"Providers keep logs for six months. Logs record every access.\n\nAuthorities inspect logs."
)
QUESTION = {"question": "How long do providers keep logs?"}


@pytest.fixture
def upload(settle: Settle) -> Upload:
    def upload_and_wait(
        client: TestClient, filename: str = "policy.txt", content: bytes = POLICY
    ) -> None:
        response = client.post("/api/documents", files={"file": (filename, content, "text/plain")})
        assert response.status_code == 202
        assert settle(client, response.json()["id"])["status"] == "ready"

    return upload_and_wait


def ask(client: TestClient) -> tuple[str, list[dict[str, Any]]]:
    response = client.post("/api/chat", json=QUESTION)
    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    return response.headers["content-type"], events


def test_answer_is_a_stream_of_text_then_citation_then_end(
    client: TestClient, upload: Upload
) -> None:
    upload(client)

    content_type, events = ask(client)

    assert content_type.startswith("text/event-stream")
    kinds = [event["type"] for event in events]
    first_citation = kinds.index("citation")
    assert first_citation > 1
    assert set(kinds[:first_citation]) == {"text"}
    assert set(kinds[first_citation:-1]) == {"citation"}
    assert events[-1] == {
        "type": "end",
        "model_id": "fake-extractive",
        "found": True,
        "is_test_model": True,
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "first_token_ms": 0.0,
            "total_ms": 0.0,
            "attempts": 1,
            "tool_turns": 0,
        },
    }


def test_citation_events_carry_the_quoted_passage(client: TestClient, upload: Upload) -> None:
    upload(client)

    _, events = ask(client)

    citation = next(event for event in events if event["type"] == "citation")
    assert citation["document_title"] == "policy"
    parsed = TextDocumentParser().parse("policy.txt", POLICY)
    chunks = {chunk.id: chunk.text for chunk in chunk_document(document_id_for(POLICY), parsed)}
    assert citation["quote"] in chunks[citation["chunk_id"]]
    assert citation["chunk_id"].startswith(citation["document_id"] + ":")


def test_citation_events_carry_the_location_of_the_chunk(
    client: TestClient, upload: Upload
) -> None:
    upload(client, "policy.md", b"# Logs\n\n" + POLICY)

    _, events = ask(client)

    citation = next(event for event in events if event["type"] == "citation")
    assert citation["location"] == {
        "heading_path": ["Logs"],
        "article": None,
        "paragraph": None,
        "page": None,
    }


def test_without_documents_the_stream_has_no_citation(client: TestClient) -> None:
    _, events = ask(client)

    assert [event["type"] for event in events] == ["text", "end"]
    assert events[-1]["found"] is False


def test_documents_are_searchable_after_a_restart(
    tmp_path: Path, client_for: ClientFor, upload: Upload
) -> None:
    with client_for(tmp_path) as before:
        upload(before)

    with client_for(tmp_path) as after:
        _, events = ask(after)

    assert any(event["type"] == "citation" for event in events)


def test_openapi_documents_the_event_stream_and_its_event_types(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()

    content = schema["paths"]["/api/chat"]["post"]["responses"]["200"]["content"]
    assert "text/event-stream" in content
    assert {"ChatEvent", "ChatTextEvent", "ChatCitationEvent", "ChatEndEvent"} <= set(
        schema["components"]["schemas"]
    )


def test_an_empty_question_returns_the_standard_error(client: TestClient) -> None:
    response = client.post("/api/chat", json={"question": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert [detail["field"] for detail in body["details"]] == ["body.question"]


def scripted_client(tmp_path: Path, events: list[ModelEvent]) -> TestClient:
    adapters = Adapters(
        store=FakeDocumentStore(),
        index=InMemoryChunkIndex(),
        parser=TextDocumentParser(),
        queue=InlineIngestionQueue(),
        chat_model=ScriptedChatModel(events, model_id="qwen3-8b"),
    )
    settings = Settings(data_dir=tmp_path, models_dir=tmp_path / "models", min_similarity=0)
    return TestClient(create_app(settings, adapters))


USAGE = Usage(
    prompt_tokens=210, completion_tokens=35, first_token_ms=450.0, total_ms=1800.0, attempts=2
)


def test_a_rejected_attempt_is_announced_with_a_discard_event(
    tmp_path: Path, upload: Upload
) -> None:
    script: list[ModelEvent] = [
        TextDelta("Wrong."),
        AttemptDiscarded("the answer cites no passage"),
        TextDelta("Six months."),
        Answered(ModelAnswer(text="Six months.", cited=(1,)), USAGE),
    ]
    with scripted_client(tmp_path, script) as client:
        upload(client)
        _, events = ask(client)

    assert events[:3] == [
        {"type": "text", "text": "Wrong."},
        {"type": "discard", "reason": "the answer cites no passage"},
        {"type": "text", "text": "Six months."},
    ]
    assert events[-1]["usage"] == {
        "prompt_tokens": 210,
        "completion_tokens": 35,
        "first_token_ms": 450.0,
        "total_ms": 1800.0,
        "attempts": 2,
        "tool_turns": 0,
    }
    assert events[-1]["is_test_model"] is False


def test_a_model_failure_is_an_error_event_and_the_stream_still_ends(
    tmp_path: Path, upload: Upload
) -> None:
    script: list[ModelEvent] = [
        ModelFailed("model_timeout", "The model server at http://127.0.0.1:8080 took over 60 s.")
    ]
    with scripted_client(tmp_path, script) as client:
        upload(client)
        _, events = ask(client)

    assert events == [
        {
            "type": "error",
            "code": "model_timeout",
            "message": "The model server at http://127.0.0.1:8080 took over 60 s.",
        },
        {
            "type": "end",
            "model_id": "qwen3-8b",
            "found": True,
            "is_test_model": False,
            "usage": None,
        },
    ]


class ScriptedAgent:
    """A model that calls tools from a script, then answers from a script (F-07)."""

    model_id = "qwen3-8b"
    is_test_model = False

    def __init__(
        self, turns: list[ToolCalls | FinalText | ModelFailed], answer: list[ModelEvent]
    ) -> None:
        self._turns = turns
        self._answer = answer

    async def call_tools(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ToolCalls | FinalText | ModelFailed:
        return self._turns.pop(0)

    async def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        for event in self._answer:
            yield event


def agent_client(tmp_path: Path, agent: ScriptedAgent, max_tool_turns: int = 4) -> TestClient:
    adapters = Adapters(
        store=FakeDocumentStore(),
        index=InMemoryChunkIndex(),
        parser=TextDocumentParser(),
        queue=InlineIngestionQueue(),
        chat_model=agent,
        tool_model=agent,
    )
    settings = Settings(
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
        min_similarity=0,
        max_tool_turns=max_tool_turns,
    )
    return TestClient(create_app(settings, adapters))


def searching(query: str, call_id: str = "call-1") -> ToolCalls:
    call = ToolCall(
        id=call_id, name="search_documents", arguments=SearchDocumentsArguments(query=query)
    )
    return ToolCalls(
        (call,),
        usage=Usage(
            prompt_tokens=100, completion_tokens=10, first_token_ms=None, total_ms=200.0, attempts=1
        ),
    )


def test_each_tool_call_is_an_event_before_the_answer_text(tmp_path: Path, upload: Upload) -> None:
    agent = ScriptedAgent(
        [searching("log retention"), FinalText("ready")],
        [
            TextDelta("Six months [1]."),
            Answered(ModelAnswer(text="Six months [1].", cited=(1,)), USAGE),
        ],
    )
    with agent_client(tmp_path, agent) as client:
        upload(client)
        _, events = ask(client)

    assert [event["type"] for event in events] == ["tool", "tool", "text", "citation", "end"]
    assert events[:2] == [
        {"type": "tool", "name": "search_documents", "arguments": QUESTION_ARGUMENTS},
        {"type": "tool", "name": "search_documents", "arguments": {"query": "log retention"}},
    ]
    assert events[-1]["usage"]["tool_turns"] == 1
    assert events[-1]["usage"]["prompt_tokens"] == 100 + 210


QUESTION_ARGUMENTS = {"query": QUESTION["question"]}


def test_too_many_tool_turns_is_an_error_event_and_the_stream_still_ends(
    tmp_path: Path, upload: Upload
) -> None:
    agent = ScriptedAgent([searching("logs", "c1"), searching("retention", "c2")], [])
    with agent_client(tmp_path, agent, max_tool_turns=1) as client:
        upload(client)
        _, events = ask(client)

    assert [event["type"] for event in events] == ["tool", "tool", "error", "end"]
    assert events[2]["code"] == "too_many_tool_turns"
    assert events[-1]["found"] is True
