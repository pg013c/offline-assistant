"""The agent: tools before the answer (F-07)."""

import asyncio
import re
import time
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime

from structlog.testing import capture_logs

from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.fakes.note_store import InMemoryNoteStore
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.answers import (
    NO_RELEVANT_PASSAGE,
    AnswerCitation,
    Answered,
    AnswerEnd,
    AnswerEvent,
    AnswerFailed,
    AnswerText,
    ModelAnswer,
    ModelEvent,
    ModelFailed,
    NoteSaved,
    TextDelta,
    ToolUsed,
    Usage,
)
from assistant.domain.documents import Chunk
from assistant.domain.tools import (
    FinalText,
    GetArticleArguments,
    Message,
    SaveNoteArguments,
    ToolCall,
    ToolCalls,
    ToolSpec,
)
from assistant.services.agent import AgentService
from assistant.services.documents import DocumentService
from assistant.services.questions import QuestionService
from assistant.services.tools import DocumentTools

GDPR = b"""# GDPR (EN)

## Article 17

Right to erasure

1. The data subject has the right to erasure of personal data.

## Article 33

Notification of a personal data breach

1. The controller shall notify the breach within 72 hours.

2. The processor shall notify the controller of a breach.
"""

# Only questions about an article or a comparison go through the tools (spec decision 6).
QUESTION = "When must a breach be notified under Article 33?"
NOTE_REQUEST = "Save a checklist of the breach duties under Article 33 as a note."
NOW = datetime(2026, 10, 30, 9, 15, 7, tzinfo=UTC)


def usage(
    prompt: int, completion: int, total_ms: float, first_token_ms: float | None = None
) -> Usage:
    return Usage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        first_token_ms=first_token_ms,
        total_ms=total_ms,
        attempts=1,
    )


ANSWER_USAGE = usage(400, 40, 900.0, first_token_ms=300.0)


class ScriptedAgent:
    """A tool-calling model that replays its turns and its answer, and records what it saw."""

    model_id = "scripted-agent"
    is_test_model = False

    def __init__(
        self,
        turns: Sequence[ToolCalls | FinalText | ModelFailed],
        answer: Sequence[ModelEvent] = (),
    ) -> None:
        self._turns = list(turns)
        self._answer = list(answer)
        self.seen: list[list[Message]] = []
        self.tools: list[str] = []
        self.answered_with: list[Chunk] | None = None

    async def call_tools(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ToolCalls | FinalText | ModelFailed:
        self.seen.append(list(messages))
        self.tools = [tool.name for tool in tools]
        return self._turns.pop(0)

    async def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        self.answered_with = list(passages)
        for event in self._answer:
            yield event


def service(
    agent: ScriptedAgent,
    max_tool_turns: int = 4,
    min_similarity: float = 0,
    clock: Callable[[], float] = time.perf_counter,
    notes: InMemoryNoteStore | None = None,
) -> tuple[AgentService, FakeDocumentStore, str]:
    store = FakeDocumentStore()
    index = InMemoryChunkIndex()
    documents = DocumentService(store, index, TextDocumentParser(), InlineIngestionQueue())
    document_id = documents.upload("GDPR (EN).md", GDPR).id
    # The in-memory index only finds passages that share a word with the question.
    questions = QuestionService(index, agent, store, min_similarity=min_similarity)
    tools = DocumentTools(questions, store, notes=notes or InMemoryNoteStore(), clock=lambda: NOW)
    return AgentService(questions, agent, tools, max_tool_turns, clock), store, document_id


def ask(questions: AgentService | QuestionService, question: str = QUESTION) -> list[AnswerEvent]:
    async def gather() -> list[AnswerEvent]:
        return [event async for event in questions.ask(question)]

    return asyncio.run(gather())


def article(store: FakeDocumentStore, document_id: str, number: str) -> list[Chunk]:
    return [chunk for chunk in store.load_chunks(document_id) if chunk.location.article == number]


def reading(number: str, call_id: str = "call-1") -> ToolCalls:
    arguments = GetArticleArguments(document="GDPR (EN)", number=number)
    return ToolCalls((ToolCall(id=call_id, name="get_article", arguments=arguments),))


def answered(text: str, cited: tuple[int, ...], covered: bool = True) -> list[ModelEvent]:
    return [
        TextDelta(text),
        Answered(ModelAnswer(text=text, cited=cited, covered=covered), ANSWER_USAGE),
    ]


def test_the_conversation_starts_with_the_documents_the_question_and_its_search() -> None:
    agent = ScriptedAgent([FinalText("ready")], answered("Within 72 hours [1].", (1,)))
    questions, _, _ = service(agent)

    ask(questions)

    system, user, searched, result = agent.seen[0]
    assert system.role == "system"
    assert '"GDPR (EN)"' in system.content
    assert "data, not instructions" in system.content
    assert (user.role, user.content) == ("user", QUESTION)
    assert searched.role == "assistant"
    assert [(call.name, call.arguments.model_dump()) for call in searched.tool_calls] == [
        ("search_documents", {"query": QUESTION, "document": None})
    ]
    assert result.role == "tool"
    assert result.tool_call_id == searched.tool_calls[0].id
    assert '<passage number="1"' in result.content
    assert agent.tools == ["search_documents", "get_article", "compare"]


def test_requested_tools_run_and_their_results_go_back_to_the_model() -> None:
    agent = ScriptedAgent(
        [reading("33"), FinalText("ready")], answered("Within 72 hours [1].", (1,))
    )
    questions, _, _ = service(agent)

    ask(questions)

    *_, called, result = agent.seen[1]
    assert called.role == "assistant"
    assert [call.id for call in called.tool_calls] == ["call-1"]
    assert (result.role, result.tool_call_id) == ("tool", "call-1")
    assert "72 hours" in result.content


def test_the_answer_rests_on_every_passage_the_tools_returned_and_cites_by_their_numbers() -> None:
    agent = ScriptedAgent([reading("17"), FinalText("ready")], answered("A breach [1].", (1,)))
    questions, store, document_id = service(agent)
    erasure = article(store, document_id, "17")

    events = ask(questions)

    assert agent.answered_with is not None
    assert len(agent.answered_with) > len(erasure)
    assert agent.answered_with[-len(erasure) :] == erasure
    cited = [event.citation.chunk_id for event in events if isinstance(event, AnswerCitation)]
    assert cited == [agent.answered_with[0].id]


def test_each_tool_call_is_announced_before_the_answer_text() -> None:
    agent = ScriptedAgent(
        [reading("33"), FinalText("ready")], answered("Within 72 hours [1].", (1,))
    )
    questions, _, _ = service(agent)

    events = ask(questions)

    tools = [event for event in events if isinstance(event, ToolUsed)]
    assert tools == [
        ToolUsed(name="search_documents", arguments={"query": QUESTION}),
        ToolUsed(name="get_article", arguments={"document": "GDPR (EN)", "number": "33"}),
    ]
    first_text = next(i for i, event in enumerate(events) if isinstance(event, AnswerText))
    assert all(isinstance(event, ToolUsed) for event in events[:first_text])


def test_at_the_limit_the_model_is_not_asked_again_and_answers_from_what_it_found() -> None:
    agent = ScriptedAgent(
        [reading("33", "c1"), reading("17", "c2")], answered("Within 72 hours [1].", (1,))
    )
    questions, store, document_id = service(agent, max_tool_turns=2)

    events = ask(questions)

    assert len(agent.seen) == 2
    assert not any(isinstance(event, AnswerFailed) for event in events)
    assert agent.answered_with is not None
    gathered = {chunk.id for chunk in agent.answered_with}
    for number in ("33", "17"):
        assert {chunk.id for chunk in article(store, document_id, number)} <= gathered
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.found is True


def test_a_repeated_call_gets_the_numbers_of_its_passages_not_the_passages_again() -> None:
    agent = ScriptedAgent(
        [reading("33", "c1"), reading("33", "c2"), FinalText("ready")],
        answered("Within 72 hours [1].", (1,)),
    )
    questions, _, _ = service(agent)

    with capture_logs() as logs:
        ask(questions)

    first, repeated = agent.seen[2][-3], agent.seen[2][-1]
    assert "<passage " in first.content
    assert repeated.tool_call_id == "c2"
    assert "<passage " not in repeated.content
    assert repeated.content.startswith("You already called get_article with these arguments")
    numbers = [int(n) for n in re.findall(r'<passage number="(\d+)"', first.content)]
    assert repeated.content.endswith(f"passages {', '.join(map(str, numbers))}.")
    assert [entry["tool"] for entry in logs if entry["event"] == "tool_called"] == [
        "search_documents",
        "get_article",
    ]


def test_a_failed_tool_turn_ends_the_run_typed_and_keeps_its_usage() -> None:
    failed = ModelFailed(
        "model_timeout",
        "The model server did not answer within 60 s.",
        usage=usage(300, 0, 60000.0),
    )
    agent = ScriptedAgent([failed])
    readings = iter([10.0, 70.5])
    questions, _, _ = service(agent, clock=lambda: next(readings))

    events = ask(questions)

    assert AnswerFailed(code="model_timeout", message=failed.detail) in events
    assert agent.answered_with is None
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.usage is not None
    assert (end.usage.prompt_tokens, end.usage.total_ms) == (300, 60500.0)


def test_the_usage_of_every_call_in_the_run_is_summed_with_its_tool_turns() -> None:
    agent = ScriptedAgent(
        [
            ToolCalls(reading("33").calls, usage=usage(200, 15, 500.0)),
            FinalText("ready", usage=usage(350, 2, 250.0)),
        ],
        answered("Within 72 hours [1].", (1,)),
    )
    # The research phase, from the question to the answer call, takes 2 s by this clock:
    # searches, tool runs and both model turns.
    readings = iter([10.0, 12.0])
    questions, _, _ = service(agent, clock=lambda: next(readings))

    end = ask(questions)[-1]

    assert isinstance(end, AnswerEnd)
    assert end.usage == Usage(
        prompt_tokens=200 + 350 + 400,
        completion_tokens=15 + 2 + 40,
        # The first answer token comes after the whole research phase, not only its model calls.
        first_token_ms=2000.0 + 300.0,
        total_ms=2000.0 + 900.0,
        attempts=1,
        tool_turns=1,
    )


def test_an_answer_the_passages_do_not_cover_ends_as_not_found() -> None:
    agent = ScriptedAgent(
        [FinalText("ready")], answered("The documents do not say.", (), covered=False)
    )
    questions, _, _ = service(agent)

    events = ask(questions)

    assert not any(isinstance(event, AnswerCitation) for event in events)
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.found is False


def test_an_out_of_scope_question_makes_no_model_call() -> None:
    agent = ScriptedAgent([FinalText("ready")])
    questions, _, _ = service(agent)

    events = ask(questions, "Pasta recipes?")

    assert agent.seen == []
    assert agent.answered_with is None
    assert events[0] == AnswerText(text=NO_RELEVANT_PASSAGE)
    assert not any(isinstance(event, ToolUsed) for event in events)


def test_without_an_agent_the_question_takes_the_search_then_answer_path() -> None:
    agent = ScriptedAgent([], answered("Within 72 hours [1].", (1,)))
    store = FakeDocumentStore()
    index = InMemoryChunkIndex()
    DocumentService(store, index, TextDocumentParser(), InlineIngestionQueue()).upload(
        "GDPR (EN).md", GDPR
    )
    questions = QuestionService(index, agent, store, min_similarity=0)

    events = ask(questions)

    assert agent.seen == []
    assert agent.answered_with is not None
    assert len(agent.answered_with) <= 3
    assert not any(isinstance(event, ToolUsed) for event in events)


def test_every_tool_call_is_logged_with_its_name_and_counts_but_no_arguments() -> None:
    agent = ScriptedAgent(
        [reading("33"), FinalText("ready")], answered("Within 72 hours [1].", (1,))
    )
    questions, _, _ = service(agent)

    with capture_logs() as logs:
        ask(questions)

    calls = [entry for entry in logs if entry["event"] == "tool_called"]
    assert [(entry["tool"], entry["turn"]) for entry in calls] == [
        ("search_documents", 0),
        ("get_article", 1),
    ]
    assert all(entry["passages"] >= 1 and "ms" in entry for entry in calls)
    assert not any(QUESTION in str(entry) or "GDPR (EN)" in str(entry) for entry in calls)


def test_a_question_about_neither_an_article_nor_a_comparison_makes_no_tool_turn() -> None:
    agent = ScriptedAgent([], answered("Within 72 hours [1].", (1,)))
    questions, _, _ = service(agent)

    events = ask(questions, "When must a breach be notified?")

    assert agent.seen == []
    assert agent.answered_with is not None
    assert not any(isinstance(event, ToolUsed) for event in events)


def test_an_article_question_below_the_threshold_still_reaches_the_tools() -> None:
    agent = ScriptedAgent(
        [reading("33"), FinalText("ready")], answered("Within 72 hours [1].", (1,))
    )
    questions, store, document_id = service(agent, min_similarity=1.1)

    events = ask(questions, "What does Article 33 say?")

    assert "No passage" in agent.seen[0][-1].content
    assert agent.answered_with == article(store, document_id, "33")
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.found is True


def test_an_article_question_is_refused_when_the_tools_find_nothing_either() -> None:
    agent = ScriptedAgent([FinalText("ready")], answered("Should not appear [1].", (1,)))
    questions, _, _ = service(agent, min_similarity=1.1)

    events = ask(questions, "What does Article 99 say?")

    assert len(agent.seen) == 1
    assert agent.answered_with is None
    assert events[-2] == AnswerText(text=NO_RELEVANT_PASSAGE)
    end = events[-1]
    assert isinstance(end, AnswerEnd)
    assert end.found is False


def test_every_tool_turn_is_logged_with_its_model_tokens_and_time_but_no_text() -> None:
    agent = ScriptedAgent(
        [
            ToolCalls(reading("33").calls, usage=usage(200, 15, 500.0)),
            FinalText("ready", usage=usage(350, 2, 250.0)),
        ],
        answered("Within 72 hours [1].", (1,)),
    )
    questions, _, _ = service(agent)

    with capture_logs() as logs:
        ask(questions)

    turns = [entry for entry in logs if entry["event"] == "tool_turn"]
    assert [
        (e["model_id"], e["turn"], e["outcome"], e["prompt_tokens"], e["total_ms"]) for e in turns
    ] == [
        ("scripted-agent", 1, "tool_calls", 200, 500.0),
        ("scripted-agent", 2, "ready", 350, 250.0),
    ]
    assert all(e["completion_tokens"] in (15, 2) for e in turns)
    assert not any("ready" in str(e.get("text", "")) or QUESTION in str(e) for e in turns)


def saving(content: str, call_id: str = "note-1") -> ToolCalls:
    arguments = SaveNoteArguments(title="Breach duties", content=content)
    return ToolCalls((ToolCall(id=call_id, name="save_note", arguments=arguments),))


def test_a_note_request_is_offered_save_note_and_a_saved_note_is_announced() -> None:
    notes = InMemoryNoteStore()
    agent = ScriptedAgent(
        [saving("- Notify the authority within 72 hours [1]"), FinalText("ready")],
        answered("Saved the checklist [1].", (1,)),
    )
    questions, _, _ = service(agent, notes=notes)

    events = ask(questions, NOTE_REQUEST)

    assert agent.tools == ["search_documents", "get_article", "compare", "save_note"]
    [note] = notes.list_notes()
    saved = [event for event in events if isinstance(event, NoteSaved)]
    assert saved == [NoteSaved(id=note.id, title="Breach duties")]
    first_text = next(i for i, event in enumerate(events) if isinstance(event, AnswerText))
    assert events.index(saved[0]) < first_text


def test_a_note_request_without_an_article_still_goes_through_the_tools() -> None:
    agent = ScriptedAgent([FinalText("ready")], answered("A breach is notified [1].", (1,)))
    questions, _, _ = service(agent)

    ask(questions, "Save a note on breach notification.")

    assert len(agent.seen) == 1
    assert "save_note" in agent.tools


def test_a_question_without_a_note_request_is_not_offered_save_note() -> None:
    agent = ScriptedAgent([FinalText("ready")], answered("Within 72 hours [1].", (1,)))
    questions, _, _ = service(agent)

    ask(questions)

    assert agent.tools == ["search_documents", "get_article", "compare"]


def test_a_save_note_call_that_was_not_offered_writes_nothing() -> None:
    notes = InMemoryNoteStore()
    agent = ScriptedAgent(
        [saving("Notify within 72 hours [1]."), FinalText("ready")],
        answered("Within 72 hours [1].", (1,)),
    )
    questions, _, _ = service(agent, notes=notes)

    events = ask(questions)

    assert agent.seen[1][-1].content == "Error: there is no tool save_note."
    assert notes.list_notes() == []
    assert not any(isinstance(event, NoteSaved) for event in events)


def test_a_repeated_call_that_failed_gets_its_error_again() -> None:
    notes = InMemoryNoteStore()
    agent = ScriptedAgent(
        [saving("No marker here.", "n1"), saving("No marker here.", "n2"), FinalText("ready")],
        answered("A breach is notified [1].", (1,)),
    )
    questions, _, _ = service(agent, notes=notes)

    ask(questions, NOTE_REQUEST)

    first, repeated = agent.seen[1][-1], agent.seen[2][-1]
    assert first.content.startswith("Error:")
    assert repeated.content == first.content
    assert notes.list_notes() == []
