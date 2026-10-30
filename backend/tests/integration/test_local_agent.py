"""The agent with the configured local model, for real; needs `make llm`, skipped otherwise."""

import asyncio
import os

import httpx
import pytest

from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.openai_compatible_chat import LlmServer, OpenAICompatibleChat
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.answers import AnswerCitation, AnswerEnd, AnswerEvent, AnswerText, ToolUsed
from assistant.services.agent import AgentService
from assistant.services.documents import DocumentService
from assistant.services.questions import QuestionService

pytestmark = pytest.mark.integration

URL = os.environ.get("ASSISTANT_LLM_URL", "http://127.0.0.1:8080")

GDPR_EN = b"""# GDPR (EN)

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

2. Administrative fines shall be imposed in addition to, or instead of, corrective measures.
"""

GDPR_PL = """# RODO (PL)

## Artykuł 17

Prawo do usunięcia danych

1. Osoba, której dane dotyczą, ma prawo żądania od administratora niezwłocznego usunięcia
dotyczących jej danych osobowych.
""".encode()


def server_is_up() -> bool:
    try:
        return httpx.get(f"{URL}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def ask(question: str) -> tuple[list[AnswerEvent], FakeDocumentStore]:
    store = FakeDocumentStore()
    index = InMemoryChunkIndex()
    documents = DocumentService(store, index, TextDocumentParser(), InlineIngestionQueue())
    documents.upload("GDPR (EN).md", GDPR_EN)
    documents.upload("RODO (PL).md", GDPR_PL)
    model = OpenAICompatibleChat(
        model_id="qwen3-8b",
        server=LlmServer(base_url=URL, served_model="qwen3-8b", timeout_seconds=60, max_retries=2),
    )
    # The in-memory index only finds passages that share a word with the query.
    questions = QuestionService(index, model, store, min_similarity=0)
    agent = AgentService(questions, model, store, max_tool_turns=4)

    async def gather() -> list[AnswerEvent]:
        return [event async for event in agent.ask(question)]

    return asyncio.run(gather()), store


@pytest.mark.skipif(not server_is_up(), reason="no local model server (make llm)")
def test_a_question_naming_an_article_reads_it_and_cites_it() -> None:
    events, _ = ask("What does Article 83 of the GDPR set out?")

    tools = [event.name for event in events if isinstance(event, ToolUsed)]
    articles = {
        event.citation.location.article for event in events if isinstance(event, AnswerCitation)
    }
    end = events[-1]
    assert "get_article" in tools
    assert "83" in articles
    assert isinstance(end, AnswerEnd)
    assert end.found is True
    assert end.usage is not None
    assert end.usage.tool_turns >= 1


@pytest.mark.skipif(not server_is_up(), reason="no local model server (make llm)")
def test_a_polish_question_is_answered_in_polish_with_markers() -> None:
    events, _ = ask("Jakie prawo daje osobie art. 17 RODO?")

    text = "".join(event.text for event in events if isinstance(event, AnswerText))
    assert "[1]" in text or "[2]" in text
    assert any(letter in text.lower() for letter in "ąćęłńóśźż")
    assert any(isinstance(event, AnswerCitation) for event in events)
