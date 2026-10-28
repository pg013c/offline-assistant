"""Deterministic stand-in for a language model, wired in production until F-06."""

import re
from collections.abc import AsyncIterator, Sequence

from assistant.domain.documents import Chunk

SENTENCES_IN_ANSWER = 2
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class FakeExtractiveChatModel:
    """Answers with the opening sentences of the best passage, word by word."""

    model_id = "fake-extractive"

    async def stream_answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[str]:
        if not passages:
            return
        sentences = _SENTENCE_END.split(passages[0].text.strip())
        words = " ".join(sentences[:SENTENCES_IN_ANSWER]).split()
        for position, word in enumerate(words):
            yield word if position == len(words) - 1 else f"{word} "
