import asyncio
import time
from collections.abc import Sequence

import pytest

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel, ScriptedChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.answers import (
    NO_RELEVANT_PASSAGE,
    AnswerCitation,
    AnswerDiscarded,
    Answered,
    AnswerEnd,
    AnswerEvent,
    AnswerFailed,
    AnswerText,
    AttemptDiscarded,
    ModelAnswer,
    ModelEvent,
    ModelFailed,
    TextDelta,
    Usage,
)
from assistant.domain.documents import Chunk, ChunkLocation, Document, indexed_text
from assistant.domain.errors import RerankerOff
from assistant.ports.chunk_index import ScoredChunk
from assistant.services.documents import DocumentService
from assistant.services.questions import RERANK_CANDIDATES, QuestionService

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


def test_search_returns_passages_best_first_with_titles_and_similarity() -> None:
    store = FakeDocumentStore()
    store.save_upload(
        Document(id="doc", title="AI Act", filename="ai-act.pdf", chunk_count=2, status="ready"),
        b"%PDF",
    )
    index = FixedIndex([hit(1, "Providers keep logs.", 0.7), hit(0, "Unrelated text.", 0.2)])
    questions = QuestionService(index, FakeExtractiveChatModel(), store, 0.5)

    found = asyncio.run(questions.search("Do providers keep logs?", limit=2))

    assert [(p.chunk.id, p.document_title, p.similarity) for p in found] == [
        ("doc:1", "AI Act", 0.7),
        ("doc:0", "AI Act", 0.2),
    ]


def test_search_honours_the_limit() -> None:
    index = FixedIndex([hit(n, f"Passage {n}.", 0.9 - n / 10) for n in range(5)])
    questions = QuestionService(index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5)

    found = asyncio.run(questions.search("Passage?", limit=3))

    assert [p.chunk.id for p in found] == ["doc:0", "doc:1", "doc:2"]


class RecordingIndex(FixedIndex):
    """Remembers how many candidates each search asked for."""

    def __init__(self, results: list[ScoredChunk]) -> None:
        super().__init__(results)
        self.limits: list[int] = []

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        self.limits.append(limit)
        return super().search(query, limit)


class ScriptedReranker:
    """Scores passages from a table, 0 for any other; remembers what it was given."""

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores
        self.passages: list[list[str]] = []

    @property
    def model_id(self) -> str:
        return "scripted"

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        self.passages.append(list(passages))
        return [
            next((score for text, score in self._scores.items() if text in passage), 0.0)
            for passage in passages
        ]


FOUR_HITS = [
    hit(0, "Keyword match.", 0.7),
    hit(1, "Providers keep logs.", 0.6),
    hit(2, "Logs are kept.", 0.55),
    hit(3, "Nothing relevant.", 0.2),
]
PREFERS_LOGS = {"Providers keep logs.": 0.9, "Logs are kept.": 0.8, "Keyword match.": 0.1}


def test_with_a_reranker_search_returns_the_rerankers_order_and_scores() -> None:
    index = RecordingIndex(FOUR_HITS)
    questions = QuestionService(
        index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5, ScriptedReranker(PREFERS_LOGS)
    )

    found = asyncio.run(questions.search("Do providers keep logs?", limit=3))

    assert [(p.chunk.id, p.rerank_score, p.similarity) for p in found] == [
        ("doc:1", 0.9, 0.6),
        ("doc:2", 0.8, 0.55),
        ("doc:0", 0.1, 0.7),
    ]
    assert index.limits == [RERANK_CANDIDATES]


def test_the_reranker_scores_thirty_candidates_or_the_limit_if_larger() -> None:
    index = RecordingIndex(FOUR_HITS)
    questions = QuestionService(
        index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5, ScriptedReranker({})
    )

    asyncio.run(questions.search("Logs?", limit=40))

    assert RERANK_CANDIDATES == 30
    assert index.limits == [40]


def test_the_reranker_reads_each_passage_with_its_heading_path() -> None:
    located = ScoredChunk(
        chunk=Chunk(
            id="doc:0",
            document_id="doc",
            position=0,
            text="Fines shall be effective.",
            location=ChunkLocation(heading_path=("Article 83", "General conditions")),
        ),
        score=1,
        similarity=0.6,
    )
    reranker = ScriptedReranker({})
    questions = QuestionService(
        FixedIndex([located]), FakeExtractiveChatModel(), FakeDocumentStore(), 0.5, reranker
    )

    asyncio.run(questions.search("Article 83?", limit=1))

    assert reranker.passages == [[indexed_text(located.chunk)]]


def test_equal_reranker_scores_keep_the_index_order() -> None:
    questions = QuestionService(
        FixedIndex(FOUR_HITS),
        FakeExtractiveChatModel(),
        FakeDocumentStore(),
        0.5,
        ScriptedReranker({}),
    )

    found = asyncio.run(questions.search("Anything?", limit=4))

    assert [p.chunk.id for p in found] == ["doc:0", "doc:1", "doc:2", "doc:3"]


@pytest.mark.parametrize("configured", [True, False])
def test_without_reranking_search_returns_the_index_order_unscored(configured: bool) -> None:
    index = RecordingIndex(FOUR_HITS)
    reranker = ScriptedReranker(PREFERS_LOGS) if configured else None
    questions = QuestionService(
        index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5, reranker
    )

    found = asyncio.run(questions.search("Do providers keep logs?", limit=3, rerank=False))

    assert [(p.chunk.id, p.rerank_score) for p in found] == [
        ("doc:0", None),
        ("doc:1", None),
        ("doc:2", None),
    ]
    assert index.limits == [3]


def test_without_a_reranker_the_default_is_the_index_order() -> None:
    questions = QuestionService(
        FixedIndex(FOUR_HITS), FakeExtractiveChatModel(), FakeDocumentStore(), 0.5
    )

    found = asyncio.run(questions.search("Do providers keep logs?", limit=2))

    assert [(p.chunk.id, p.rerank_score) for p in found] == [("doc:0", None), ("doc:1", None)]


def test_asking_for_reranking_without_a_reranker_is_refused() -> None:
    questions = QuestionService(
        FixedIndex(FOUR_HITS), FakeExtractiveChatModel(), FakeDocumentStore(), 0.5
    )

    with pytest.raises(RerankerOff):
        asyncio.run(questions.search("Logs?", limit=2, rerank=True))


def test_with_a_reranker_the_answer_cites_the_reranked_best_passage() -> None:
    index = RecordingIndex(FOUR_HITS)
    questions = QuestionService(
        index, FakeExtractiveChatModel(), FakeDocumentStore(), 0.5, ScriptedReranker(PREFERS_LOGS)
    )

    events = ask(questions, "Do providers keep logs?")

    [citation] = [event.citation for event in events if isinstance(event, AnswerCitation)]
    assert citation.chunk_id == "doc:1"
    assert index.limits == [RERANK_CANDIDATES]


def test_the_dense_threshold_still_refuses_what_the_reranker_scores_high() -> None:
    weak = [hit(0, "Pasta boils in salted water.", 0.3), hit(1, "Logs.", 0.4)]
    questions = QuestionService(
        FixedIndex(weak),
        FakeExtractiveChatModel(),
        FakeDocumentStore(),
        0.5,
        ScriptedReranker({"Pasta boils in salted water.": 0.99}),
    )

    events = ask(questions, "How long should pasta boil?")

    assert events[0] == AnswerText(text=NO_RELEVANT_PASSAGE)
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.found is False


def test_with_a_reranker_answers_use_only_its_top_ten_like_the_evaluation() -> None:
    # Ten weak passages the reranker likes, and one strong passage it ranks eleventh.
    weak = [hit(n, f"Weak passage {n}.", 0.3) for n in range(10)]
    strong = hit(10, "Strong but disliked passage.", 0.9)
    reranker = ScriptedReranker({f"Weak passage {n}.": 1 - n / 100 for n in range(10)})
    questions = QuestionService(
        FixedIndex([strong, *weak]), FakeExtractiveChatModel(), FakeDocumentStore(), 0.5, reranker
    )

    events = ask(questions, "Anything?")

    assert events[0] == AnswerText(text=NO_RELEVANT_PASSAGE)


THREE_PASSAGES = [
    hit(0, "Providers keep logs.", 0.8),
    hit(1, "Logs are kept for six months.", 0.7),
    hit(2, "Authorities may inspect logs.", 0.6),
]
USAGE = Usage(
    prompt_tokens=200, completion_tokens=30, first_token_ms=420.0, total_ms=1500.0, attempts=1
)


def scripted(*events: ModelEvent) -> tuple[QuestionService, ScriptedChatModel]:
    model = ScriptedChatModel(list(events))
    return QuestionService(FixedIndex(THREE_PASSAGES), model, FakeDocumentStore(), 0.5), model


def test_citations_follow_the_passages_the_model_cites_in_its_order() -> None:
    questions, _ = scripted(
        TextDelta("Kept six months."),
        Answered(ModelAnswer(text="Kept six months.", cited=(2, 1, 2)), USAGE),
    )

    events = ask(questions, "How long are logs kept?")

    assert [e.citation.chunk_id for e in events if isinstance(e, AnswerCitation)] == [
        "doc:1",
        "doc:0",
    ]


def test_a_discarded_attempt_is_passed_on_before_the_retry() -> None:
    questions, _ = scripted(
        TextDelta("Wrong."),
        AttemptDiscarded("passage 9 does not exist; cite passages 1 to 3"),
        TextDelta("Right."),
        Answered(ModelAnswer(text="Right.", cited=(1,)), USAGE),
    )

    events = ask(questions, "How long are logs kept?")

    assert events[:3] == [
        AnswerText(text="Wrong."),
        AnswerDiscarded(reason="passage 9 does not exist; cite passages 1 to 3"),
        AnswerText(text="Right."),
    ]


def test_a_failed_model_ends_the_answer_with_a_typed_failure_and_no_citation() -> None:
    questions, _ = scripted(
        ModelFailed("model_unreachable", "No model server answers at http://127.0.0.1:8080."),
    )

    events = ask(questions, "How long are logs kept?")

    assert (
        AnswerFailed(
            code="model_unreachable", message="No model server answers at http://127.0.0.1:8080."
        )
        in events
    )
    assert not any(isinstance(event, AnswerCitation) for event in events)
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.usage is None


def test_the_end_event_carries_the_models_usage() -> None:
    questions, _ = scripted(
        TextDelta("Kept."), Answered(ModelAnswer(text="Kept.", cited=(1,)), USAGE)
    )

    end = ask(questions, "How long are logs kept?")[-1]

    assert isinstance(end, AnswerEnd)
    assert end.usage == USAGE


def test_an_out_of_scope_question_never_reaches_the_model() -> None:
    model = ScriptedChatModel([TextDelta("Should not appear.")])
    weak = FixedIndex([hit(0, "Pasta.", 0.2)])
    questions = QuestionService(weak, model, FakeDocumentStore(), 0.5)

    events = ask(questions, "How long should pasta boil?")

    assert events[0] == AnswerText(text=NO_RELEVANT_PASSAGE)
    assert model.calls == 0
