"""Composition root: the only module that wires adapters into services (ADR 0002)."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from fastapi import FastAPI
from fastapi.routing import APIRoute

from assistant import __version__
from assistant.adapters.bge_reranker import BgeReranker
from assistant.adapters.chat_models import chat_model_for, tool_model_for
from assistant.adapters.docling_parser import DoclingDocumentParser
from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.file_document_store import LocalFileDocumentStore
from assistant.adapters.qdrant_chunk_index import QdrantChunkIndex
from assistant.adapters.routing_parser import RoutingDocumentParser
from assistant.adapters.sentence_transformer_embedder import SentenceTransformerEmbedder
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.adapters.thread_ingestion_queue import ThreadIngestionQueue
from assistant.api.errors import register_error_handlers
from assistant.api.routes import chat, documents, health, search
from assistant.log import configure_logging
from assistant.ports.chat_model import ChatModel, ToolCallingModel
from assistant.ports.chunk_index import ChunkIndex
from assistant.ports.document_parser import DocumentParser
from assistant.ports.document_store import DocumentStore
from assistant.ports.ingestion_queue import IngestionQueue
from assistant.ports.reranker import Reranker
from assistant.services.agent import AgentService
from assistant.services.documents import DocumentService
from assistant.services.questions import Answerer, QuestionService
from assistant.settings import Settings, load_settings

API_PREFIX = "/api"


def document_parser_for(settings: Settings) -> DocumentParser:
    """Text only, or Docling for everything else; Docling fails here if its models are missing."""
    text = TextDocumentParser()
    if settings.document_parser == "text-only":
        return text
    DoclingDocumentParser.ensure_ready(settings.models_dir)
    return RoutingDocumentParser(text=text, rich=DoclingDocumentParser(settings.models_dir))


@dataclass(frozen=True)
class Adapters:
    """Everything the services need from outside; `build_adapters` wires the real ones."""

    store: DocumentStore
    index: ChunkIndex
    parser: DocumentParser
    queue: IngestionQueue
    chat_model: ChatModel
    reranker: Reranker | None = None
    # The chat model again when it is declared able to call tools: it then answers as the agent.
    tool_model: ToolCallingModel | None = None


def reranker_for(settings: Settings, device: str | None = None) -> Reranker | None:
    """The pinned reranker when reranking is on; it fails here if its model is missing.

    `auto` turns it on for the device it would run on (`device`, by default the one torch
    finds) only when that is an Apple GPU.
    """
    if settings.reranker == "off":
        return None
    if settings.reranker == "auto" and (device or BgeReranker.default_device()) != "mps":
        return None
    BgeReranker.ensure_ready(settings.models_dir)
    return BgeReranker(settings.models_dir)


def build_adapters(settings: Settings) -> Adapters:
    """The real adapters; each fails here, naming what is missing, if it cannot work."""
    parser = document_parser_for(settings)
    SentenceTransformerEmbedder.ensure_ready(settings.models_dir)
    reranker = reranker_for(settings)
    embedder = SentenceTransformerEmbedder(settings.models_dir)
    chat_model = chat_model_for(settings)
    index = QdrantChunkIndex.connect(
        settings.qdrant_url, embedder, prefix=settings.qdrant_collection_prefix
    )
    return Adapters(
        store=LocalFileDocumentStore(settings.data_dir),
        index=index,
        parser=parser,
        queue=ThreadIngestionQueue(),
        chat_model=chat_model,
        reranker=reranker,
        tool_model=tool_model_for(settings, chat_model),
    )


def schema_adapters() -> Adapters:
    """Adapters that need nothing outside the process, for exporting the OpenAPI schema."""
    return Adapters(
        store=FakeDocumentStore(),
        index=InMemoryChunkIndex(),
        parser=TextDocumentParser(),
        queue=InlineIngestionQueue(),
        chat_model=FakeExtractiveChatModel(),
    )


def operation_id(route: APIRoute) -> str:
    """Use the route function's name as the OpenAPI operation id, e.g. `get_health`."""
    return route.name


def create_app(settings: Settings, adapters: Adapters | None = None) -> FastAPI:
    """Build the HTTP application from settings, with the real adapters unless given others."""
    adapters = adapters or build_adapters(settings)
    document_service = DocumentService(
        adapters.store, adapters.index, adapters.parser, adapters.queue
    )
    question_service = QuestionService(
        adapters.index,
        adapters.chat_model,
        adapters.store,
        settings.min_similarity,
        adapters.reranker,
    )
    answers: Answerer = (
        AgentService(question_service, adapters.tool_model, adapters.store, settings.max_tool_turns)
        if adapters.tool_model
        else question_service
    )

    async def restore() -> None:
        # Refilling an empty index embeds every stored chunk; the API answers meanwhile.
        restored = await asyncio.to_thread(document_service.restore)
        structlog.get_logger(__name__).info("documents_restored", count=restored)

    async def warm_up(reranker: Reranker) -> None:
        # The reranker loads on its first score; doing it now spares the first question.
        await asyncio.to_thread(reranker.score, "warm-up", ["warm-up"])
        structlog.get_logger(__name__).info("reranker_loaded", model=reranker.model_id)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        restoring = asyncio.create_task(restore())
        warming = asyncio.create_task(warm_up(adapters.reranker)) if adapters.reranker else None
        yield
        adapters.queue.close()
        await restoring
        if warming:
            await warming

    app = FastAPI(
        lifespan=lifespan,
        title="Offline Assistant",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        generate_unique_id_function=operation_id,
    )
    app.state.settings = settings
    app.state.document_service = document_service
    app.state.question_service = question_service
    app.state.answers = answers
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(documents.router, prefix=API_PREFIX)
    app.include_router(chat.router, prefix=API_PREFIX)
    app.include_router(search.router, prefix=API_PREFIX)
    return app


def main() -> FastAPI:
    """Application factory for uvicorn (`--factory`): settings come from the environment."""
    configure_logging()
    # Models come from `make models`; a library that tries to download one fails instead.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return create_app(load_settings())
