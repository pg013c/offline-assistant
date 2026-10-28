"""Composition root: the only module that wires adapters into services (ADR 0002)."""

from fastapi import FastAPI

from assistant import __version__
from assistant.api.routes import health
from assistant.settings import Settings, load_settings

API_PREFIX = "/api"


def create_app(settings: Settings) -> FastAPI:
    """Build the HTTP application from settings."""
    app = FastAPI(
        title="Offline Assistant",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.include_router(health.router, prefix=API_PREFIX)
    return app


def main() -> FastAPI:
    """Application factory for uvicorn (`--factory`): settings come from the environment."""
    return create_app(load_settings())
