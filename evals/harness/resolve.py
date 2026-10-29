"""Expected sources written by location, resolved to the chunk ids of the indexed corpus."""

from collections.abc import Sequence
from dataclasses import dataclass

from harness.dataset import Case, ExpectedSource


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
    """Each case's expected chunk ids. Every expected source must match at least one chunk,
    so a wrong case stops the run instead of scoring as a miss (F-04 AC-4)."""
    resolved: dict[str, frozenset[str]] = {}
    for case in cases:
        ids: set[str] = set()
        for source in case.sources:
            matching = {chunk.chunk_id for chunk in chunks if _matches(source, chunk)}
            if not matching:
                raise UnresolvedSource(f"{case.id}: {_describe(source)} matches no chunk")
            ids |= matching
        resolved[case.id] = frozenset(ids)
    return resolved


def _matches(source: ExpectedSource, chunk: ChunkRef) -> bool:
    if source.document != chunk.document:
        return False
    if source.heading is not None:
        return source.heading in chunk.heading_path
    return chunk.article == source.article and (
        source.paragraph is None or chunk.paragraph == source.paragraph
    )


def _describe(source: ExpectedSource) -> str:
    if source.heading is not None:
        return f"{source.document}, heading {source.heading!r}"
    paragraph = f"({source.paragraph})" if source.paragraph else ""
    return f"{source.document}, Art. {source.article}{paragraph}"
