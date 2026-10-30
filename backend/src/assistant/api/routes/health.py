from typing import Annotated

from fastapi import APIRouter, Depends

from assistant import __version__
from assistant.api.dependencies import get_settings
from assistant.api.schemas import HealthResponse
from assistant.settings import Settings

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Report that the API is up, which version is running and whether network mode is on."""
    return HealthResponse(status="ok", version=__version__, network=settings.allow_network)
