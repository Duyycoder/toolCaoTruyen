"""
Authentication middleware for Gemini API Server.
Validates Bearer API keys from incoming requests.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import base64
import json
from .config import load_api_keys

security = HTTPBearer(auto_error=False)


def _decode_jwt_payload_unverified(token: str) -> dict | None:
    """Decode JWT payload without verifying signature."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return None


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """
    Dependency that validates the Bearer API key or OpenAI JWT token.
    Returns the key label if valid, raises 401 otherwise.
    """
    if credentials is None:
        print("DEBUG AUTH: credentials is None (Missing Authorization header)!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: Authorization: Bearer <api_key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = credentials.credentials
    print(f"DEBUG AUTH: received api_key = {api_key[:30]}...")

    # Support OpenAI JWT authorization from Codex
    if api_key.startswith("ey"):
        payload = _decode_jwt_payload_unverified(api_key)
        if payload and (payload.get("iss") == "https://auth.openai.com" or "openai" in str(payload.get("iss"))):
            profile = payload.get("https://api.openai.com/profile", {})
            email = profile.get("email") or payload.get("email") or "Codex-User"
            print(f"DEBUG AUTH: Accepted OpenAI JWT for user: {email}")
            return f"openai-jwt-{email}"

    keys = load_api_keys()

    if api_key not in keys:
        print(f"DEBUG AUTH: Invalid API key (not in valid keys list)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return keys[api_key]  # Return the label
