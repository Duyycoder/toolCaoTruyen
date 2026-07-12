"""
Routes for /v1/models — lists available Gemini models.
"""

from fastapi import APIRouter, Depends

from ..auth import verify_api_key
from ..schemas import ModelListResponse, ModelObject
from ..state import get_client

router = APIRouter()


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models(_: str = Depends(verify_api_key)):
    """List all Gemini models available for your account."""
    client = get_client()

    try:
        raw_models = client.list_models()
        model_objects = []

        if raw_models:
            for m in raw_models:
                name = getattr(m, "model_name", None) or getattr(m, "name", str(m))
                model_objects.append(ModelObject(id=name))
        else:
            # Fallback list if dynamic discovery didn't work
            default_models = [
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-2.0-flash-thinking",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ]
            model_objects = [ModelObject(id=m) for m in default_models]

    except Exception:
        # Safe fallback
        model_objects = [ModelObject(id="gemini-2.0-flash")]

    return ModelListResponse(data=model_objects)
