"""The agent: it looks passages up with tools, then answers from them (F-07, FR-10)."""

import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, replace
from importlib.resources import files
from string import Template

import structlog

from assistant.domain.answers import (
    NO_USAGE,
    AnswerEvent,
    AnswerFailed,
    ModelFailed,
    NoteSaved,
    ToolUsed,
    Usage,
)
from assistant.domain.notes import wants_note
from assistant.domain.routing import needs_tools
from assistant.domain.tools import (
    FinalText,
    Message,
    PassageLedger,
    SearchDocumentsArguments,
    ToolCall,
    ToolCalls,
    ToolSpec,
)
from assistant.ports.chat_model import ToolCallingModel
from assistant.services.questions import QuestionService
from assistant.services.tools import SAVE_NOTE, TOOLS, DocumentTools

log = structlog.get_logger(__name__)

_PROMPTS = files("assistant").joinpath("prompts")
AGENT_PROMPT = Template(_PROMPTS.joinpath("agent.md").read_text(encoding="utf-8"))
NOTE_SAVED = Template(_PROMPTS.joinpath("note_saved.md").read_text(encoding="utf-8").strip())
NOTE_NOT_SAVED = Template(
    _PROMPTS.joinpath("note_not_saved.md").read_text(encoding="utf-8").strip()
)
# The search the service makes for the question itself, shown to the model as its first call.
GATE_CALL_ID = "search-question"


class AgentService:
    """Answers a question in two phases: research with tools, then the streamed answer.

    The question is searched first, and the result is the model's first tool result. The
    model then calls tools, up to `max_tool_turns` turns (AI-22), and the answer rests on every
    passage they returned. A question about an article is not refused at the threshold, since
    a short reference can fall under it; with no passage after the tools, it is refused and no
    answer is written (AI-02).
    """

    def __init__(
        self,
        questions: QuestionService,
        model: ToolCallingModel,
        tools: DocumentTools,
        max_tool_turns: int,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._questions = questions
        self._model = model
        self._tools = tools
        self._max_tool_turns = max_tool_turns
        self._clock = clock

    async def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Tool calls, then text pieces, citations and an end event; or a refusal.

        Only a question about an article, or a comparison, uses the tools; any other
        takes the question service's search-then-answer path (spec decision 6).
        """
        note = wants_note(question)
        if not (needs_tools(question) or note):
            async for event in self._questions.ask(question):
                yield event
            return
        started = self._clock()
        ledger = PassageLedger()
        gate = ToolCall(
            id=GATE_CALL_ID,
            name="search_documents",
            arguments=SearchDocumentsArguments(query=question),
        )
        calls = _CallLog()
        result = await self._run(gate, ledger, 0, calls)
        yield _announced(gate)
        messages = [
            Message(role="system", content=await self._system_prompt()),
            Message(role="user", content=question),
            Message(role="assistant", content="", tool_calls=(gate,)),
            Message(role="tool", content=result, tool_call_id=gate.id),
        ]
        # save_note writes a file, so only a question asking for a note gets it (F-07a, AI-11).
        run = _Run(
            ledger=ledger,
            calls=calls,
            messages=messages,
            offered=(*TOOLS, SAVE_NOTE) if note else TOOLS,
        )
        async for event in self._research(run, note):
            yield event
        if run.failure is not None:
            yield AnswerFailed(code=run.failure.code, message=run.failure.detail)
            yield self._questions.end(found=True, usage=self._timed(run.research, started))
            return
        if not ledger:
            # Nothing above the threshold and nothing the tools found: no answer (AI-02).
            for event in self._questions.refusal():
                yield event
            return
        research = self._timed(run.research, started)
        notice = _notice(ledger, run.save_error) if note else None
        async for event in self._questions.answer(question, ledger.passages, research, notice):
            yield event

    async def _research(self, run: "_Run", note: bool) -> AsyncIterator[AnswerEvent]:
        """The model's tool turns, up to the limit; a failure is left in `run.failure`.

        At the limit the model is not asked again; the answer rests on what it found. A note
        that failed to save in the last turn gets one more turn to be corrected (AI-21).
        """
        limit = self._max_tool_turns
        turn = 0
        while turn < limit:
            turn += 1
            reply = await self._model.call_tools(run.messages, run.offered)
            if reply.usage is not None:
                run.research = run.research.plus(reply.usage)
            self._log_turn(turn, reply)
            match reply:
                case FinalText():
                    return
                case ToolCalls(calls=requested):
                    run.research = run.research.plus(_ONE_TOOL_TURN)
                    run.messages.append(Message(role="assistant", content="", tool_calls=requested))
                    for call in requested:
                        async for event in self._call(call, run, turn):
                            yield event
                    if note and turn == limit == self._max_tool_turns and run.save_failed:
                        limit += 1
                case _:
                    run.failure = reply
                    return

    async def _call(self, call: ToolCall, run: "_Run", turn: int) -> AsyncIterator[AnswerEvent]:
        """One tool call: announced, run if it was offered, and any saved note announced."""
        yield _announced(call)
        saved = len(run.ledger.saved_notes)
        offered = {tool.name for tool in run.offered}
        content = (
            await self._run(call, run.ledger, turn, run.calls)
            if call.name in offered
            else f"Error: there is no tool {call.name}."
        )
        for written in run.ledger.saved_notes[saved:]:
            yield NoteSaved(id=written.id, title=written.title)
        if call.name == SAVE_NOTE.name and content.startswith("Error:"):
            run.save_error = content.removeprefix("Error:").strip()
        run.messages.append(Message(role="tool", content=content, tool_call_id=call.id))

    def _timed(self, research: Usage, started: float) -> Usage:
        """The research phase's usage with its whole time: searches, tools and model turns."""
        return replace(research, total_ms=(self._clock() - started) * 1000)

    def _log_turn(self, turn: int, reply: ToolCalls | FinalText | ModelFailed) -> None:
        """One info line per tool-turn model call: ids, tokens and time, never text (AI-60)."""
        match reply:
            case ToolCalls():
                outcome = "tool_calls"
            case FinalText():
                outcome = "ready"
            case _:
                outcome = reply.code
        usage = reply.usage
        log.info(
            "tool_turn",
            model_id=self._questions.model_id,
            turn=turn,
            outcome=outcome,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_ms=usage.total_ms if usage else None,
        )

    async def _run(
        self, call: ToolCall, ledger: PassageLedger, turn: int, calls: "_CallLog"
    ) -> str:
        """The tool's result; logged with ids, counts and time, never arguments (AI-53).

        A call repeated with the same arguments does not run again: the model gets the numbers
        of the passages it already has, not the passages a second time.
        """
        repeated = calls.repeat(call)
        if repeated is not None:
            return repeated
        started = time.perf_counter()
        before = len(ledger)
        result = await self._tools.run(call, ledger)
        calls.record(call, result)
        log.info(
            "tool_called",
            tool=call.name,
            turn=turn,
            passages=result.count("<passage "),
            new_passages=len(ledger) - before,
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return result

    async def _system_prompt(self) -> str:
        titles = await self._tools.document_titles()
        return AGENT_PROMPT.substitute(documents=", ".join(f'"{title}"' for title in titles))


@dataclass
class _Run:
    """What one question's research has gathered and said so far."""

    ledger: PassageLedger
    calls: "_CallLog"
    messages: list[Message]
    offered: tuple[ToolSpec, ...]
    research: Usage = NO_USAGE
    save_error: str | None = None
    failure: ModelFailed | None = None

    @property
    def save_failed(self) -> bool:
        return self.save_error is not None and not self.ledger.saved_notes


class _CallLog:
    """The calls of one run by tool and arguments, with the passage numbers they returned."""

    def __init__(self) -> None:
        self._numbers: dict[str, list[str]] = {}
        self._errors: dict[str, str] = {}

    def record(self, call: ToolCall, result: str) -> None:
        if result.startswith("Error:"):
            self._errors[_key(call)] = result
        else:
            self._numbers[_key(call)] = _PASSAGE_NUMBER.findall(result)

    def repeat(self, call: ToolCall) -> str | None:
        """What a call made before with the same arguments returned, in short; a failed call
        gets its error again, so the model sees what to correct."""
        if _key(call) in self._errors:
            return self._errors[_key(call)]
        numbers = self._numbers.get(_key(call))
        if numbers is None:
            return None
        found = (
            f"its results are passages {', '.join(numbers)}." if numbers else "it found no passage."
        )
        return f"You already called {call.name} with these arguments; {found}"


_PASSAGE_NUMBER = re.compile(r'<passage number="(\d+)"')


def _key(call: ToolCall) -> str:
    return f"{call.name}:{call.arguments.model_dump_json()}"


_ONE_TOOL_TURN = Usage(
    prompt_tokens=0,
    completion_tokens=0,
    first_token_ms=None,
    total_ms=0.0,
    attempts=0,
    tool_turns=1,
)


def _notice(ledger: PassageLedger, save_error: str | None) -> str:
    """What the answer is told about the note the question asked for (F-07a review #1)."""
    if ledger.saved_notes:
        saved = ledger.saved_notes[0]
        return NOTE_SAVED.substitute(title=saved.title, id=saved.id)
    return NOTE_NOT_SAVED.substitute(reason=save_error or "save_note was not called")


def _announced(call: ToolCall) -> ToolUsed:
    return ToolUsed(name=call.name, arguments=call.arguments.model_dump(exclude_none=True))
