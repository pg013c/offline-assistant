"""Request and response models of the HTTP API. Services never return these (PY-12)."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class DocumentResponse(BaseModel):
    id: str
    title: str
    filename: str
    chunk_count: int


class ErrorResponse(BaseModel):
    """The body of every error the API reports (PY-22)."""

    code: str
    message: str
