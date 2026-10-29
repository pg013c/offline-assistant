"""Composition root: the only module that wires adapters into services (ADR 0002)."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from fastapi import FastAPI
from fastapi.routing import APIRoute

from assistant import __version__
from assistant.adapters.docling_parser import DoclingDocumentParser
from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.file_document_store import LocalFileDocumentStore
from assistant.adapters.routing_parser import RoutingDocumentParser
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.adapters.thread_ingestion_queue import ThreadIngestionQueue
from assistant.api.errors import register_error_handlers
from assistant.api.routes import chat, documents, health
from assistant.log import configure_logging
from assistant.ports.chat_model import ChatModel
from assistant.ports.chunk_index import ChunkIndex
from assistant.ports.document_parser import DocumentParser
from assistant.ports.document_store import DocumentStore
from assistant.ports.ingestion_queue import IngestionQueue
from assistant.services.documents import DocumentService
from assistant.services.questions import QuestionService
from assistant.settings import Settings, SettingsError, load_settings

API_PREFIX = "/api"

# Chat model adapters by `ASSISTANT_CHAT_MODEL`; F-06 adds the OpenAI-compatible ones.
CHAT_MODELS: dict[str, type[ChatModel]] = {"fake-extractive": FakeExtractiveChatModel}


def document_parser_for(settings: Settings) -> DocumentParser:
    """Text only, or Docling for everything else; Docling fails here if its models are missing."""
    text = TextDocumentParser()
    if settings.document_parser == "text-only":
        return text
    if settings.models_dir is None:
        # Settings validation rejects this; fail rather than quietly read text only.
        raise SettingsError("ASSISTANT_MODELS_DIR is required by the Docling document parser")
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


def operation_id(route: APIRoute) -> str:
    """Use the route function's name as the OpenAPI operation id, e.g. `get_health`."""
    return route.name


def create_app(settings: Settings, adapters: Adapters | None = None) -> FastAPI:
    """Build the HTTP application from settings."""
    store = LocalFileDocumentStore(settings.data_dir)
    # In memory until the Qdrant index is wired in (F-03 step 9).
    index = InMemoryChunkIndex()
    model = CHAT_MODELS[settings.chat_model]()
    parser = document_parser_for(settings)
    queue = ThreadIngestionQueue()
    document_service = DocumentService(store, index, parser, queue)
    # The in-memory index returns only passages sharing a word with the question; the
    # threshold comes from settings with the Qdrant index (F-03 step 9).
    question_service = QuestionService(index, model, store, min_similarity=0)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        restored = document_service.restore()
        structlog.get_logger(__name__).info("documents_restored", count=restored)
        yield
        queue.close()

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
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(documents.router, prefix=API_PREFIX)
    app.include_router(chat.router, prefix=API_PREFIX)
    return app


def main() -> FastAPI:
    """Application factory for uvicorn (`--factory`): settings come from the environment."""
    configure_logging()
    # Models come from `make models`; a library that tries to download one fails instead.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return create_app(load_settings())
