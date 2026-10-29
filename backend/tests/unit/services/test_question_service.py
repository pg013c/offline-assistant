import asyncio
import time

import pytest

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.answers import (
    NO_RELEVANT_PASSAGE,
    AnswerCitation,
    AnswerEnd,
    AnswerEvent,
    AnswerText,
)
from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ScoredChunk
from assistant.services.documents import DocumentService
from assistant.services.questions import QuestionService

POLICY = (
    b"Providers keep logs for six months. Logs record every access. Nothing else.\n\n"
    b"Authorities may inspect the logs on request."
)


@pytest.fixture
def store() -> FakeDocumentStore:
    return FakeDocumentStore()


@pytest.fixture
def services(store: FakeDocumentStore) -> tuple[DocumentService, QuestionService]:
    index = InMemoryChunkIndex()
    documents = DocumentService(store, index, TextDocumentParser(), InlineIngestionQueue())
    # The in-memory index returns only passages sharing a word with the question, so these
    # tests need no similarity threshold.
    return documents, QuestionService(index, FakeExtractiveChatModel(), store, min_similarity=0)


def ask(service: QuestionService, question: str) -> list[AnswerEvent]:
    async def gather() -> list[AnswerEvent]:
        return [event async for event in service.ask(question)]

    return asyncio.run(gather())


def test_answer_streams_text_then_citations_then_end(
    services: tuple[DocumentService, QuestionService],
) -> None:
    documents, questions = services
    documents.upload("policy.txt", POLICY)

    events = ask(questions, "How long do providers keep logs?")

    kinds = [type(event) for event in events]
    first_citation = kinds.index(AnswerCitation)
    assert set(kinds[:first_citation]) == {AnswerText}
    assert first_citation > 1
    assert set(kinds[first_citation:-1]) == {AnswerCitation}
    assert kinds[-1] is AnswerEnd


def test_answer_text_comes_from_the_model(
    services: tuple[DocumentService, QuestionService],
) -> None:
    documents, questions = services
    documents.upload("policy.txt", POLICY)

    events = ask(questions, "How long do providers keep logs?")

    text = "".join(event.text for event in events if isinstance(event, AnswerText))
    assert text == "Providers keep logs for six months. Logs record every access."


def test_citations_quote_their_chunk_verbatim(
    services: tuple[DocumentService, QuestionService], store: FakeDocumentStore
) -> None:
    documents, questions = services
    document = documents.upload("policy.txt", POLICY)

    events = ask(questions, "How long do providers keep logs?")

    citations = [event.citation for event in events if isinstance(event, AnswerCitation)]
    chunks = {chunk.id: chunk.text for chunk in store.load_chunks(document.id)}
    assert citations
    for citation in citations:
        assert citation.quote in chunks[citation.chunk_id]
        assert citation.document_id == document.id
        assert citation.document_title == "policy"
        assert citation.chunk_id.startswith(f"{document.id}:")


def test_end_event_names_the_model_and_reports_a_found_answer(
    services: tuple[DocumentService, QuestionService],
) -> None:
    documents, questions = services
    documents.upload("policy.txt", POLICY)

    events = ask(questions, "How long do providers keep logs?")

    assert events[-1] == AnswerEnd(model_id="fake-extractive", found=True, is_test_model=True)


def test_without_documents_no_relevant_passage_is_reported(
    services: tuple[DocumentService, QuestionService],
) -> None:
    _, questions = services

    events = ask(questions, "How long do providers keep logs?")

    assert events == [
        AnswerText(text=NO_RELEVANT_PASSAGE),
        AnswerEnd(model_id="fake-extractive", found=False, is_test_model=True),
    ]


def test_without_a_shared_word_no_relevant_passage_is_reported(
    services: tuple[DocumentService, QuestionService],
) -> None:
    documents, questions = services
    documents.upload("policy.txt", POLICY)

    events = ask(questions, "biometric identification rules")

    assert not any(isinstance(event, AnswerCitation) for event in events)
    assert events[-1] == AnswerEnd(model_id="fake-extractive", found=False, is_test_model=True)


def test_citations_carry_the_location_of_their_chunk(
    services: tuple[DocumentService, QuestionService], store: FakeDocumentStore
) -> None:
    documents, questions = services
    document = documents.upload("policy.md", b"# Logs\n\n" + POLICY)

    events = ask(questions, "Who may inspect the logs?")

    [citation] = [event.citation for event in events if isinstance(event, AnswerCitation)]
    cited = next(chunk for chunk in store.load_chunks(document.id) if chunk.id == citation.chunk_id)
    assert citation.location == cited.location
    assert citation.location.heading_path == ("Logs",)


class FixedIndex(InMemoryChunkIndex):
    """Returns the given results whatever the query."""

    def __init__(self, results: list[ScoredChunk]) -> None:
        super().__init__()
        self._results = results

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        return self._results[:limit]


def hit(position: int, text: str, similarity: float) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(id=f"doc:{position}", document_id="doc", position=position, text=text),
        score=1 / (position + 1),
        similarity=similarity,
    )


def test_passages_below_the_minimum_similarity_are_not_used() -> None:
    index = FixedIndex([hit(0, "Unrelated text.", 0.3), hit(1, "Barely related.", 0.49)])
    questions = QuestionService(index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5)

    events = ask(questions, "Anything?")

    assert events[0] == AnswerText(text=NO_RELEVANT_PASSAGE)
    assert not any(isinstance(event, AnswerCitation) for event in events)
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.found is False


def test_the_best_passage_that_reaches_the_minimum_is_cited() -> None:
    index = FixedIndex([hit(0, "Keyword-only match.", 0.2), hit(1, "Providers keep logs.", 0.7)])
    questions = QuestionService(index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5)

    events = ask(questions, "Do providers keep logs?")

    [citation] = [event.citation for event in events if isinstance(event, AnswerCitation)]
    assert citation.chunk_id == "doc:1"


class SlowIndex(InMemoryChunkIndex):
    """Search blocks its thread for a while, as embedding and a Qdrant call do."""

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        time.sleep(0.2)
        return []


def test_searching_does_not_block_other_work_on_the_event_loop() -> None:
    questions = QuestionService(SlowIndex(), FakeExtractiveChatModel(), FakeDocumentStore(), 0.5)
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    async def run() -> None:
        task = asyncio.create_task(ticker())
        _ = [event async for event in questions.ask("Anything?")]
        task.cancel()

    asyncio.run(run())

    assert ticks >= 5


def test_a_relevant_passage_ranked_below_three_weak_ones_is_still_cited() -> None:
    index = FixedIndex(
        [
            hit(0, "Keyword match one.", 0.3),
            hit(1, "Keyword match two.", 0.35),
            hit(2, "Keyword match three.", 0.4),
            hit(3, "Providers keep logs.", 0.7),
        ]
    )
    questions = QuestionService(index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5)

    events = ask(questions, "Do providers keep logs?")

    [citation] = [event.citation for event in events if isinstance(event, AnswerCitation)]
    assert citation.chunk_id == "doc:3"
