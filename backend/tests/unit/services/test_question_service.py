import asyncio

import pytest

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.keyword_index import KeywordChunkIndex
from assistant.domain.answers import (
    NO_RELEVANT_PASSAGE,
    AnswerCitation,
    AnswerEnd,
    AnswerEvent,
    AnswerText,
)
from assistant.domain.documents import split_into_chunks
from assistant.services.documents import DocumentService
from assistant.services.questions import QuestionService

POLICY = (
    b"Providers keep logs for six months. Logs record every access. Nothing else.\n\n"
    b"Authorities may inspect the logs on request."
)


@pytest.fixture
def services() -> tuple[DocumentService, QuestionService]:
    store, index = FakeDocumentStore(), KeywordChunkIndex()
    return DocumentService(store, index), QuestionService(index, FakeExtractiveChatModel(), store)


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
    services: tuple[DocumentService, QuestionService],
) -> None:
    documents, questions = services
    document = documents.upload("policy.txt", POLICY)

    events = ask(questions, "How long do providers keep logs?")

    citations = [event.citation for event in events if isinstance(event, AnswerCitation)]
    chunks = {chunk.id: chunk.text for chunk in split_into_chunks(document.id, POLICY.decode())}
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
