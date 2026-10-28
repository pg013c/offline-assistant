"""Request and response models of the HTTP API. Services never return these (PY-12)."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
