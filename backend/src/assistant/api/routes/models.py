from typing import Annotated

from fastapi import APIRouter, Depends

from assistant.api.dependencies import get_models
from assistant.api.schemas import ModelChoiceResponse
from assistant.services.models import ChatModels

router = APIRouter(prefix="/models", tags=["models"])

Models = Annotated[ChatModels, Depends(get_models)]


@router.get("")
def list_models(models: Models) -> list[ModelChoiceResponse]:
    """The models a question can name now; the default answers when none is named."""
    return [
        ModelChoiceResponse(
            id=model.id, is_test_model=model.is_test_model, is_default=model.is_default
        )
        for model in models.list_models()
    ]
