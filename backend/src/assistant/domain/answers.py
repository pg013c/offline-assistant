"""What a streamed answer is made of."""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from assistant.domain.documents import ChunkLocation

NO_RELEVANT_PASSAGE = "No relevant passage was found in the uploaded documents."
QUOTE_SENTENCES = 2
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Citation:
    chunk_id: str
    document_id: str
    document_title: str
    quote: str
    location: ChunkLocation = field(default_factory=ChunkLocation)


@dataclass(frozen=True, slots=True)
class AnswerText:
    text: str


@dataclass(frozen=True, slots=True)
class AnswerCitation:
    citation: Citation


@dataclass(frozen=True, slots=True)
class AnswerDiscarded:
    """The text sent since the last attempt began is void; the retry's text follows."""

    reason: str


@dataclass(frozen=True, slots=True)
class AnswerFailed:
    """The model gave no valid answer; the stream still ends."""

    code: "ModelFailure"
    message: str


@dataclass(frozen=True, slots=True)
class AnswerEnd:
    model_id: str
    found: bool
    is_test_model: bool
    usage: "Usage | None" = None


type AnswerEvent = AnswerText | AnswerDiscarded | AnswerFailed | AnswerCitation | AnswerEnd


@dataclass(frozen=True, slots=True)
class Usage:
    """What one answer cost: tokens over every attempt, and its timings (AI-60)."""

    prompt_tokens: int
    completion_tokens: int
    first_token_ms: float | None
    total_ms: float
    attempts: int


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A piece of the answer text, as the model writes it."""

    text: str


@dataclass(frozen=True, slots=True)
class AttemptDiscarded:
    """The text streamed since the last attempt began is void; a retry follows."""

    reason: str


@dataclass(frozen=True, slots=True)
class Answered:
    answer: "ModelAnswer"
    usage: Usage


type ModelFailure = Literal["invalid_answer", "model_unreachable", "model_timeout", "model_error"]


@dataclass(frozen=True, slots=True)
class ModelFailed:
    code: ModelFailure
    detail: str
    # What the failed answer cost; not part of what the failure is.
    usage: Usage | None = field(default=None, compare=False)


type ModelEvent = TextDelta | AttemptDiscarded | Answered | ModelFailed


def opening_sentences(text: str, count: int = QUOTE_SENTENCES) -> str:
    """The first `count` sentences of the text, copied verbatim."""
    stripped = text.strip()
    boundaries = [match.start() for match in _SENTENCE_END.finditer(stripped)]
    if len(boundaries) < count:
        return stripped
    return stripped[: boundaries[count - 1]]


def quote_from(text: str) -> str:
    """The quote shown for a cited chunk, copied verbatim (AI-03)."""
    return opening_sentences(text)


class _StructuredAnswer(BaseModel):
    """The structured answer a language model is asked for (FR-13, AI-20): the answer first,
    so it can stream, then whether the passages cover the question at all (F-07)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    answer: str
    covered: bool


ANSWER_SCHEMA: dict[str, Any] = _StructuredAnswer.model_json_schema()

# A citation marker: passage numbers counted from 1 in square brackets, e.g. [2] or [1, 3].
_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
# A sentence ends at ., ? or !, with any markers that follow it, before an upper-case letter.
_SENTENCE_BREAK = re.compile(
    r"[.!?](?P<markers>(?:\s*\[\d+(?:\s*,\s*\d+)*\])*)(?=\s+[\"„(]?(?P<next>\w))"
)
_WORD_BEFORE = re.compile(r"(\S+)$")
# A full stop after these words, or after a number, does not end a sentence.
_ABBREVIATIONS = frozenset({"art", "ust", "pkt", "lit", "no", "nr", "e.g", "i.e", "zob", "tj"})


def statements(text: str) -> list[str]:
    """The sentences and list lines of an answer, each with the markers that follow it."""
    found: list[str] = []
    for line in text.splitlines():
        start = 0
        for match in _SENTENCE_BREAK.finditer(line):
            if not match.group("next").isupper():
                continue
            word = _WORD_BEFORE.search(line[start : match.start()])
            if match.group()[0] == "." and word and _no_sentence_end(word.group(1)):
                continue
            found.append(line[start : match.end()].strip())
            start = match.end()
        found.append(line[start:].strip())
    return [statement for statement in found if any(char.isalpha() for char in statement)]


def _no_sentence_end(word: str) -> bool:
    bare = word.lstrip('("„').lower()
    return bare in _ABBREVIATIONS or bare.isdigit()


def markers(text: str) -> list[int]:
    """The passage numbers the text cites, in order, with repeats."""
    return [int(number) for group in _MARKER.findall(text) for number in group.split(",")]


class InvalidAnswer(Exception):
    """The model's output is not a valid answer; the reason is fed back to it (AI-21)."""


@dataclass(frozen=True, slots=True)
class ModelAnswer:
    text: str
    cited: tuple[int, ...]
    # False when the model says the passages do not answer the question; then nothing is cited.
    covered: bool = True


def parse_answer(raw: str, passage_count: int) -> ModelAnswer:
    """The validated answer, or `InvalidAnswer` saying what to correct (AI-01, AI-21)."""
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as error:
        raise InvalidAnswer(f"the output is not valid JSON ({error.msg})") from error
    try:
        answer = _StructuredAnswer.model_validate(decoded)
    except ValidationError as error:
        raise InvalidAnswer(
            "the output is not a JSON object with answer and covered (a string and true or false)"
        ) from error
    if not answer.answer.strip():
        raise InvalidAnswer("the answer is empty")
    cited = markers(answer.answer)
    if not answer.covered:
        if cited:
            raise InvalidAnswer(
                "an answer that is not covered cites no passage; remove the markers"
            )
        return ModelAnswer(text=answer.answer, cited=(), covered=False)
    for number in cited:
        if not 1 <= number <= passage_count:
            raise InvalidAnswer(
                f"passage {number} does not exist; cite passages 1 to {passage_count}"
            )
    for statement in statements(answer.answer):
        if not _MARKER.search(statement):
            raise InvalidAnswer(
                f'the sentence "{statement}" cites no passage; end every sentence with the '
                "numbers of the passages it rests on, like [1]"
            )
    return ModelAnswer(text=answer.answer, cited=tuple(dict.fromkeys(cited)))


_HIGH_SURROGATES = 0xD800
_LOW_SURROGATES = 0xDC00
_ANSWER_START = re.compile(r'\{\s*"answer"\s*:\s*"')
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


def _hex(digits: str) -> int | None:
    try:
        return int(digits, 16)
    except ValueError:
        return None


class AnswerTextExtractor:
    """Pulls the answer text out of the structured answer while it is being written.

    The schema puts `answer` first, so its string starts the object. Escapes and surrogate
    pairs split between chunks wait for the rest.
    """

    def __init__(self) -> None:
        self._before = ""
        self._pending = ""
        self._started = False
        self._done = False

    def feed(self, chunk: str) -> str:
        """The answer text decoded from this chunk; empty before and after the answer."""
        if self._done:
            return ""
        if not self._started:
            self._before += chunk
            match = _ANSWER_START.search(self._before)
            if not match:
                return ""
            self._started = True
            chunk = self._before[match.end() :]
            self._before = ""
        return self._decode(self._pending + chunk)

    def _decode(self, text: str) -> str:
        out: list[str] = []
        position = 0
        while position < len(text):
            char = text[position]
            if char == '"':
                self._done = True
                self._pending = ""
                return "".join(out)
            if char != "\\":
                out.append(char)
                position += 1
                continue
            if position + 1 >= len(text):
                break
            code = text[position + 1]
            if code != "u":
                out.append(_ESCAPES.get(code, code))
                position += 2
                continue
            if position + 6 > len(text):
                break
            unit = _hex(text[position + 2 : position + 6])
            if unit is None:
                # Not JSON any more; parse_answer will say so. Stop streaming this attempt.
                self._done = True
                break
            if _HIGH_SURROGATES <= unit < _LOW_SURROGATES:
                # A high surrogate needs the low one that follows it.
                if position + 12 > len(text):
                    break
                low = _hex(text[position + 8 : position + 12])
                if text[position + 6 : position + 8] != "\\u" or low is None:
                    self._done = True
                    break
                out.append(
                    chr(0x10000 + ((unit - _HIGH_SURROGATES) << 10) + (low - _LOW_SURROGATES))
                )
                position += 12
                continue
            out.append(chr(unit))
            position += 6
        self._pending = text[position:]
        return "".join(out)
