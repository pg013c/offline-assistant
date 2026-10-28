from fastapi import APIRouter

from assistant import __version__
from assistant.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> HealthResponse:
    """Report that the API is up and which version is running."""
    return HealthResponse(status="ok", version=__version__)
