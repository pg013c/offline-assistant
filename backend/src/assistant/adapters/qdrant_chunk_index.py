"""Chunks in Qdrant: dense and BM25 vectors, fused by reciprocal rank (ADR 0017).

One collection per embedding model and schema version, so a new model starts from an empty
collection that is filled again from the stored chunks.
"""

import re
import uuid
from collections.abc import Sequence
from typing import Any

from qdrant_client import QdrantClient, models

from assistant.domain.documents import Chunk, ChunkLocation
from assistant.domain.keywords import bm25_terms, tokens
from assistant.ports.chunk_index import ScoredChunk
from assistant.ports.embedder import Embedder

SCHEMA_VERSION = 1
DENSE = "dense"
BM25 = "bm25"
# Each half returns this many candidates per requested result before fusion.
PREFETCH_FACTOR = 4
MIN_PREFETCH = 20
TIE_MARGIN = 4
_POINT_NAMESPACE = uuid.UUID("6f1c9a3e-2b7d-4c8e-9f10-3a5b7c9d1e2f")


class IndexNotReady(Exception):
    """Qdrant cannot be reached; the message says how to start it."""


def point_id(chunk_id: str) -> str:
    """Qdrant point id of a chunk: a UUID derived from the chunk id."""
    return str(uuid.uuid5(_POINT_NAMESPACE, chunk_id))


def best_first(results: Sequence[ScoredChunk]) -> list[ScoredChunk]:
    """Fused order, with ties broken by dense similarity, then by position.

    Reciprocal rank fusion often ties: first in one ranking and second in the other scores
    the same as the reverse, and Qdrant breaks such ties arbitrarily.
    """
    return sorted(
        results,
        key=lambda result: (
            -result.score,
            -result.similarity,
            result.chunk.document_id,
            result.chunk.position,
        ),
    )


def collection_name(prefix: str, model_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")
    return f"{prefix}-{slug}-v{SCHEMA_VERSION}"


class QdrantChunkIndex:
    def __init__(self, client: QdrantClient, embedder: Embedder, collection: str) -> None:
        self._client = client
        self._embedder = embedder
        self._collection = collection

    @classmethod
    def connect(cls, url: str, embedder: Embedder, prefix: str) -> "QdrantChunkIndex":
        """Connect, and create the collection for the embedder's model if it is missing."""
        client = QdrantClient(url=url, timeout=10)
        try:
            client.get_collections()
        except Exception as error:
            raise IndexNotReady(
                f"Qdrant is not reachable at {url} (ASSISTANT_QDRANT_URL). "
                "Start it with `make qdrant`."
            ) from error
        index = cls(client, embedder, collection_name(prefix, embedder.model_id))
        index._ensure_collection()
        return index

    @property
    def collection(self) -> str:
        return self._collection

    def add(self, chunks: Sequence[Chunk]) -> None:
        if not chunks:
            return
        vectors = self._embedder.embed([chunk.text for chunk in chunks])
        self._client.upsert(
            self._collection,
            points=[
                models.PointStruct(
                    id=point_id(chunk.id),
                    vector={DENSE: vector, BM25: _sparse(bm25_terms(chunk.text))},
                    payload=_payload(chunk),
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
            wait=True,
        )

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        if not tokens(query):
            return []
        query_vector = self._embedder.embed_query(query)
        candidates = max(limit * PREFETCH_FACTOR, MIN_PREFETCH)
        prefetch = [models.Prefetch(query=query_vector, using=DENSE, limit=candidates)]
        terms = bm25_terms(query)
        if terms:
            prefetch.append(models.Prefetch(query=_sparse(terms), using=BM25, limit=candidates))
        # A few more than asked for, so that ties at the cut are settled here, not by Qdrant.
        response = self._client.query_points(
            self._collection,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit + TIE_MARGIN,
            with_payload=True,
            with_vectors=[DENSE],
        )
        results = [
            ScoredChunk(
                chunk=_chunk(point.payload or {}),
                score=point.score,
                similarity=_similarity(query_vector, point),
            )
            for point in response.points
        ]
        return best_first(results)[:limit]

    def remove_document(self, document_id: str) -> None:
        self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(filter=_of_document(document_id)),
            wait=True,
        )

    def document_ids(self) -> set[str]:
        found: set[str] = set()
        offset = None
        while True:
            points, offset = self._client.scroll(
                self._collection,
                limit=1000,
                offset=offset,
                with_payload=["document_id"],
                with_vectors=False,
            )
            found.update(str((point.payload or {})["document_id"]) for point in points)
            if offset is None:
                return found

    def drop(self) -> None:
        """Delete the collection; for tests."""
        self._client.delete_collection(self._collection)

    def _ensure_collection(self) -> None:
        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            self._collection,
            vectors_config={
                DENSE: models.VectorParams(
                    size=self._embedder.dimensions, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={BM25: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        self._client.create_payload_index(
            self._collection, "document_id", models.PayloadSchemaType.KEYWORD, wait=True
        )


def _similarity(query_vector: Sequence[float], point: models.ScoredPoint) -> float:
    """Cosine similarity of the stored dense vector; both are unit length."""
    vectors = point.vector if isinstance(point.vector, dict) else {}
    dense = vectors.get(DENSE)
    if not isinstance(dense, list):
        return 0.0
    stored = [float(value) for value in dense if isinstance(value, (int, float))]
    return max(sum(a * b for a, b in zip(query_vector, stored, strict=True)), 0.0)


def _sparse(terms: dict[int, float]) -> models.SparseVector:
    return models.SparseVector(indices=list(terms), values=list(terms.values()))


def _of_document(document_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
    )


def _payload(chunk: Chunk) -> dict[str, Any]:
    location = chunk.location
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "position": chunk.position,
        "text": chunk.text,
        "location": {
            "heading_path": list(location.heading_path),
            "article": location.article,
            "paragraph": location.paragraph,
            "page": location.page,
        },
    }


def _chunk(payload: dict[str, Any]) -> Chunk:
    location = payload["location"]
    return Chunk(
        id=payload["chunk_id"],
        document_id=payload["document_id"],
        position=payload["position"],
        text=payload["text"],
        location=ChunkLocation(
            heading_path=tuple(location["heading_path"]),
            article=location["article"],
            paragraph=location["paragraph"],
            page=location["page"],
        ),
    )
