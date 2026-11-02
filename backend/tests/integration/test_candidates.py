"""Each model of the comparison serves and answers through the app (F-09b, AC-1).

Runs against the model `make llm LLM_MODEL=<name>` serves: the cases of every other model
are skipped, so the file is run once per model. Skipped without a model server.
"""

import asyncio
import os
from collections.abc import AsyncIterator

import httpx
import pytest

from assistant.adapters.chat_models import CHAT_MODELS, chat_model_for, tool_model_for
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.fakes.note_store import InMemoryNoteStore
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.answers import AnswerCitation, AnswerEnd, AnswerEvent, ToolUsed
from assistant.services.agent import AgentService
from assistant.services.documents import DocumentService
from assistant.services.questions import QuestionService
from assistant.services.tools import DocumentTools
from assistant.settings import Settings

pytestmark = pytest.mark.integration

URL = os.environ.get("ASSISTANT_LLM_URL", "http://127.0.0.1:8080")
SERVED = sorted(name for name, spec in CHAT_MODELS.items() if spec.served_model)

POLICY = b"""# GDPR (EN)

## Article 33

Notification of a personal data breach to the supervisory authority

1. In the case of a personal data breach, the controller shall without undue delay and, where
feasible, not later than 72 hours after having become aware of it, notify the personal data
breach to the supervisory authority.

## Article 83

General conditions for imposing administrative fines

1. Each supervisory authority shall ensure that the imposition of administrative fines in
respect of infringements of this Regulation shall in each individual case be effective,
proportionate and dissuasive.
"""


def served_model() -> str | None:
    """The model the server on URL serves, or None when no server answers."""
    try:
        listed = httpx.get(f"{URL}/v1/models", timeout=2).json()["data"]
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    return str(listed[0]["id"]) if listed else None


SERVING = served_model()


def only_when_served(name: str) -> None:
    if SERVING is None:
        pytest.skip("no local model server (make llm LLM_MODEL=<name>)")
    if name != SERVING:
        pytest.skip(f"the server serves {SERVING}, not {name}")


def services(name: str) -> tuple[QuestionService, AgentService, FakeDocumentStore]:
    """The app's services on the named model, built as the API builds them at startup."""
    settings = Settings.model_validate(
        {"data_dir": "data", "models_dir": "models", "chat_model": name, "llm_url": URL}
    )
    model = chat_model_for(settings)
    tool_model = tool_model_for(settings, model)
    assert tool_model is not None
    store = FakeDocumentStore()
    index = InMemoryChunkIndex()
    DocumentService(store, index, TextDocumentParser(), InlineIngestionQueue()).upload(
        "GDPR (EN).md", POLICY
    )
    # The in-memory index only finds passages that share a word with the query.
    questions = QuestionService(index, model, store, min_similarity=0)
    tools = DocumentTools(questions, store, notes=InMemoryNoteStore())
    return questions, AgentService(questions, tool_model, tools, max_tool_turns=4), store


def collect(events: AsyncIterator[AnswerEvent]) -> list[AnswerEvent]:
    async def gather() -> list[AnswerEvent]:
        return [event async for event in events]

    return asyncio.run(gather())


@pytest.mark.parametrize("name", SERVED)
def test_the_model_streams_an_answer_with_a_citation_that_resolves(name: str) -> None:
    only_when_served(name)
    questions, _, store = services(name)

    events = collect(
        questions.ask("Within how many hours must a personal data breach be notified?")
    )

    citations = [event.citation for event in events if isinstance(event, AnswerCitation)]
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.model_id == name
    assert end.found is True
    assert citations
    stored = {
        chunk.id for document in store.list_documents() for chunk in store.load_chunks(document.id)
    }
    assert all(citation.chunk_id in stored for citation in citations)


@pytest.mark.parametrize("name", SERVED)
def test_the_model_makes_a_valid_tool_call(name: str) -> None:
    only_when_served(name)
    _, agent, _ = services(name)

    events = collect(agent.ask("What does Article 83 of the GDPR set out?"))

    tools = [event.name for event in events if isinstance(event, ToolUsed)]
    end = events[-1]
    assert "get_article" in tools
    assert isinstance(end, AnswerEnd)
    assert end.usage is not None
    assert end.usage.tool_turns >= 1
    assert end.usage.failed_tool_turns == 0
