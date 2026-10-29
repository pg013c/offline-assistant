"""Expected sources written by location, resolved to the chunk ids of the indexed corpus."""

from collections.abc import Sequence
from dataclasses import dataclass

from harness.dataset import Case


class UnresolvedSource(Exception):
    """An expected source matches no chunk; the message names the case and the source."""


@dataclass(frozen=True)
class ChunkRef:
    chunk_id: str
    document: str
    article: str | None
    paragraph: str | None
    heading_path: tuple[str, ...]


def resolve(cases: Sequence[Case], chunks: Sequence[ChunkRef]) -> dict[str, frozenset[str]]:
    raise NotImplementedError
