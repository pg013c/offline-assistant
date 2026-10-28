"""Composition root: the only module that wires adapters into services (ADR 0002)."""

from fastapi import FastAPI

from assistant.settings import Settings


def create_app(settings: Settings) -> FastAPI:
    """Build the HTTP application from settings."""
    raise NotImplementedError
