"""
Routes for /admin — API key management endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import generate_api_key, list_api_keys, revoke_api_key
from ..schemas import ApiKeyResponse

router = APIRouter(prefix="/admin")


class CreateKeyRequest(BaseModel):
    label: str = "default"


class RevokeKeyRequest(BaseModel):
    key: str


@router.post("/keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(request: CreateKeyRequest):
    """Create a new API key with an optional label."""
    new_key = generate_api_key(request.label)
    return ApiKeyResponse(
        key=new_key,
        label=request.label,
        message="API key created successfully.",
    )


@router.get("/keys")
async def get_keys():
    """List all API keys and their labels."""
    keys = list_api_keys()
    return {
        "count": len(keys),
        "keys": [{"key": k, "label": v} for k, v in keys.items()],
    }


@router.delete("/keys")
async def delete_key(request: RevokeKeyRequest):
    """Revoke an existing API key."""
    removed = revoke_api_key(request.key)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key not found: {request.key}",
        )
    return {"message": f"Key revoked successfully: {request.key}"}
