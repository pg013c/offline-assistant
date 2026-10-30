from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from assistant import __version__
from assistant.api.schemas import HealthResponse
from assistant.settings import Settings

router = APIRouter(tags=["health"])


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("/health")
def get_health(settings: Annotated[Settings, Depends(_settings)]) -> HealthResponse:
    """Report that the API is up, which version is running and whether network mode is on."""
    return HealthResponse(status="ok", version=__version__, network=settings.allow_network)
