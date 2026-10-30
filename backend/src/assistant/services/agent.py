"""The agent: it looks passages up with tools, then answers from them (F-07, FR-10)."""

import time
from collections.abc import AsyncIterator
from importlib.resources import files
from string import Template

import structlog

from assistant.domain.answers import NO_USAGE, AnswerEvent, AnswerFailed, ToolUsed, Usage
from assistant.domain.tools import (
    FinalText,
    Message,
    PassageLedger,
    SearchDocumentsArguments,
    ToolCall,
    ToolCalls,
)
from assistant.ports.chat_model import ToolCallingModel
from assistant.ports.document_store import DocumentStore
from assistant.services.questions import QuestionService
from assistant.services.tools import TOOLS, DocumentTools

log = structlog.get_logger(__name__)

AGENT_PROMPT = Template(
    files("assistant").joinpath("prompts", "agent.md").read_text(encoding="utf-8")
)
# The search the service makes for the question itself, shown to the model as its first call.
GATE_CALL_ID = "search-question"


class AgentService:
    """Answers a question in two phases: research with tools, then the streamed answer.

    The question is searched first, as without an agent: nothing above the threshold means a
    refusal with no model call (AI-02). Otherwise the model calls tools, up to
    `max_tool_turns` turns (AI-22), and the answer rests on every passage they returned.
    """

    def __init__(
        self,
        questions: QuestionService,
        model: ToolCallingModel,
        store: DocumentStore,
        max_tool_turns: int,
    ) -> None:
        self._questions = questions
        self._model = model
        self._store = store
        self._tools = DocumentTools(questions, store)
        self._max_tool_turns = max_tool_turns

    async def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Tool calls, then text pieces, citations and an end event; or a refusal."""
        ledger = PassageLedger()
        gate = ToolCall(
            id=GATE_CALL_ID,
            name="search_documents",
            arguments=SearchDocumentsArguments(query=question),
        )
        result = await self._run(gate, ledger, turn=0)
        if not ledger:
            for event in self._questions.refusal():
                yield event
            return
        yield _announced(gate)
        messages = [
            Message(role="system", content=self._system_prompt()),
            Message(role="user", content=question),
            Message(role="assistant", content="", tool_calls=(gate,)),
            Message(role="tool", content=result, tool_call_id=gate.id),
        ]
        research = NO_USAGE
        for turn in range(1, self._max_tool_turns + 2):
            reply = await self._model.call_tools(messages, TOOLS)
            if reply.usage is not None:
                research = research.plus(reply.usage)
            match reply:
                case FinalText():
                    break
                case ToolCalls(calls=calls) if turn <= self._max_tool_turns:
                    research = research.plus(_ONE_TOOL_TURN)
                    messages.append(Message(role="assistant", content="", tool_calls=calls))
                    for call in calls:
                        yield _announced(call)
                        content = await self._run(call, ledger, turn)
                        messages.append(Message(role="tool", content=content, tool_call_id=call.id))
                case ToolCalls():
                    yield AnswerFailed(
                        code="too_many_tool_turns",
                        message=(
                            f"The model was still calling tools after {self._max_tool_turns} "
                            "turns, so it gave no answer."
                        ),
                    )
                    yield self._questions.end(found=True, usage=research)
                    return
                case _:
                    yield AnswerFailed(code=reply.code, message=reply.detail)
                    yield self._questions.end(found=True, usage=research)
                    return
        async for event in self._questions.answer(question, ledger.passages, research):
            yield event

    async def _run(self, call: ToolCall, ledger: PassageLedger, turn: int) -> str:
        """The tool's result; logged with ids, counts and time, never arguments (AI-53)."""
        started = time.perf_counter()
        before = len(ledger)
        result = await self._tools.run(call, ledger)
        log.info(
            "tool_called",
            tool=call.name,
            turn=turn,
            passages=result.count("<passage "),
            new_passages=len(ledger) - before,
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return result

    def _system_prompt(self) -> str:
        titles = sorted(document.title for document in self._store.list_documents())
        return AGENT_PROMPT.substitute(documents=", ".join(f'"{title}"' for title in titles))


_ONE_TOOL_TURN = Usage(
    prompt_tokens=0,
    completion_tokens=0,
    first_token_ms=None,
    total_ms=0.0,
    attempts=0,
    tool_turns=1,
)


def _announced(call: ToolCall) -> ToolUsed:
    return ToolUsed(name=call.name, arguments=call.arguments.model_dump(exclude_none=True))
