"""
Pydantic schemas for OpenAI-compatible request and response models.
"""

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Request Models ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gemini-2.0-flash"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class ImageGenerationRequest(BaseModel):
    model: str = "gemini-2.0-flash"
    prompt: str
    n: int = 1
    size: str = "1024x1024"
    response_format: Literal["url", "b64_json"] = "url"


# ─── Response Models ───────────────────────────────────────────────────────────

class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatChoice]
    usage: ChatUsage = Field(default_factory=ChatUsage)


# ─── Streaming Response Models ─────────────────────────────────────────────────

class DeltaMessage(BaseModel):
    role: str | None = None
    content: str | None = None


class StreamChoice(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[StreamChoice]


# ─── Model List Response ───────────────────────────────────────────────────────

class ModelObject(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "gemini-webapi"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelObject]


# ─── Image Response ────────────────────────────────────────────────────────────

class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


class ImageGenerationResponse(BaseModel):
    created: int = Field(default_factory=lambda: int(time.time()))
    data: list[ImageData]


# ─── Health Response ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    gemini_ready: bool


# ─── Admin Response ───────────────────────────────────────────────────────────

class ApiKeyResponse(BaseModel):
    key: str
    label: str
    message: str
