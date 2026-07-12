"""
Global state management for the GeminiClient singleton.
The client is initialized once at startup and reused across all requests.
"""

from gemini_webapi import GeminiClient

_client: GeminiClient | None = None


def set_client(client: GeminiClient) -> None:
    global _client
    _client = client


def get_client() -> GeminiClient:
    if _client is None:
        raise RuntimeError(
            "GeminiClient is not initialized. "
            "The server may still be starting up."
        )
    return _client
