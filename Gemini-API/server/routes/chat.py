"""
Routes for /v1/chat/completions — OpenAI-compatible chat endpoint.
Supports both regular and streaming responses.
"""

import json
import uuid
import time

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse

from ..auth import verify_api_key
from ..schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatMessage,
    DeltaMessage,
    StreamChoice,
)
from ..state import get_client

router = APIRouter()


def _build_prompt(messages: list[ChatMessage]) -> tuple[str, str | None]:
    """
    Convert OpenAI message list to a single Gemini prompt string.
    Returns (prompt, system_prompt).
    """
    system_prompt = None
    conversation_parts = []

    for msg in messages:
        if msg.role == "system":
            system_prompt = msg.content
        elif msg.role == "user":
            conversation_parts.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            conversation_parts.append(f"Assistant: {msg.content}")

    prompt = "\n".join(conversation_parts)

    # Prepend system prompt if present and no gem is used
    if system_prompt and conversation_parts:
        prompt = f"[System Instructions: {system_prompt}]\n\n{prompt}"
    elif system_prompt:
        prompt = system_prompt

    return prompt, system_prompt


def _get_available_models(client) -> list[str]:
    """Get list of available model names from Gemini client."""
    try:
        raw_models = client.list_models()
        if raw_models:
            return [getattr(m, "model_name", None) or getattr(m, "name", str(m)) for m in raw_models]
    except Exception:
        pass
    return []


def _map_model(requested_model: str, available_models: list[str]) -> str:
    """Map requested model name to closest available model name in the client."""
    if not available_models:
        return requested_model
    if requested_model in available_models:
        return requested_model

    req_lower = requested_model.lower()

    # Map thinking requests
    if "thinking" in req_lower or "thought" in req_lower:
        for m in available_models:
            if "thinking" in m.lower():
                return m

    # Map pro requests
    if "pro" in req_lower:
        # Prefer exact match without plus/advanced
        for m in available_models:
            m_lower = m.lower()
            if "pro" in m_lower and "advanced" not in m_lower and "plus" not in m_lower:
                return m
        for m in available_models:
            if "pro" in m.lower():
                return m

    # Map flash requests
    if "flash" in req_lower:
        for m in available_models:
            m_lower = m.lower()
            if "flash" in m_lower and "advanced" not in m_lower and "plus" not in m_lower and "thinking" not in m_lower:
                return m
        for m in available_models:
            if "flash" in m.lower():
                return m

    # Fallback default models if available
    for fallback in ["gemini-3-pro", "gemini-3-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
        for m in available_models:
            if fallback in m.lower():
                return m

    return available_models[0]


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    _: str = Depends(verify_api_key),
):
    """
    OpenAI-compatible chat completions endpoint.
    Supports streaming and non-streaming modes.
    """
    client = get_client()
    prompt, _ = _build_prompt(request.messages)

    if not prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user message provided.",
        )

    # Resolve and map model name dynamically
    available = _get_available_models(client)
    model = _map_model(request.model, available)

    # ── Streaming Mode ──────────────────────────────────────────────────────
    if request.stream:
        async def stream_generator():
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            created = int(time.time())

            # Send role chunk first
            first_chunk = ChatCompletionChunk(
                id=completion_id,
                created=created,
                model=model,
                choices=[
                    StreamChoice(
                        index=0,
                        delta=DeltaMessage(role="assistant", content=""),
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {first_chunk.model_dump_json()}\n\n"

            # Stream content chunks
            try:
                async for chunk in client.generate_content_stream(
                    prompt, model=model
                ):
                    delta_text = chunk.text_delta or ""
                    if delta_text:
                        content_chunk = ChatCompletionChunk(
                            id=completion_id,
                            created=created,
                            model=model,
                            choices=[
                                StreamChoice(
                                    index=0,
                                    delta=DeltaMessage(content=delta_text),
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {content_chunk.model_dump_json()}\n\n"

            except Exception as e:
                error_payload = json.dumps({"error": str(e)})
                yield f"data: {error_payload}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Send finish chunk
            finish_chunk = ChatCompletionChunk(
                id=completion_id,
                created=created,
                model=model,
                choices=[
                    StreamChoice(
                        index=0,
                        delta=DeltaMessage(),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"data: {finish_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Non-Streaming Mode ──────────────────────────────────────────────────
    try:
        response = await client.generate_content(prompt, model=model)
        text = response.text or ""
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini error: {str(e)}",
        )

    return ChatCompletionResponse(
        model=model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content=text),
                finish_reason="stop",
            )
        ],
    )


def _build_prompt_from_responses_input(input_data: list, instructions: str | None = None) -> tuple[str, str | None]:
    """
    Convert OpenAI Responses API input list and instructions to a single Gemini prompt.
    Returns (prompt, system_prompt).
    """
    system_prompt = instructions
    conversation_parts = []

    for msg in input_data:
        role = msg.get("role")
        content = msg.get("content")

        msg_text_parts = []
        if isinstance(content, str):
            msg_text_parts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    part_type = part.get("type")
                    if part_type in ("input_text", "text"):
                        msg_text_parts.append(part.get("text", ""))

        msg_text = "\n".join(msg_text_parts)
        if not msg_text:
            continue

        if role == "system":
            system_prompt = msg_text
        elif role == "user":
            conversation_parts.append(f"User: {msg_text}")
        elif role == "assistant":
            conversation_parts.append(f"Assistant: {msg_text}")

    prompt = "\n".join(conversation_parts)
    if system_prompt and conversation_parts:
        prompt = f"[System Instructions: {system_prompt}]\n\n{prompt}"
    elif system_prompt:
        prompt = system_prompt

    return prompt, system_prompt


@router.post("/v1/responses")
async def responses_completion(
    request: Request,
    _: str = Depends(verify_api_key),
):
    """
    OpenAI-compatible Responses API endpoint.
    Supports streaming and non-streaming modes.
    """
    body = await request.json()
    print(f"DEBUG RESPONSES: body = {json.dumps(body)}")
    print(f"DEBUG RESPONSES: headers = {dict(request.headers)}")
    req_model = body.get("model", "gemini-1.5-pro")
    
    input_data = body.get("input", [])
    instructions = body.get("instructions")
    
    accept_header = request.headers.get("accept", "").lower()
    stream = body.get("stream", False) or "event-stream" in accept_header
    print(f"DEBUG RESPONSES: resolved stream = {stream}")

    client = get_client()
    available = _get_available_models(client)
    model = _map_model(req_model, available)
    prompt, _ = _build_prompt_from_responses_input(input_data, instructions)

    if not prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user message or input provided.",
        )

    # ── Streaming Mode ──────────────────────────────────────────────────────
    if stream:
        async def stream_generator():
            completion_id = f"resp-{uuid.uuid4().hex}"

            # 1. Send response.created event
            created_data = {
                "id": completion_id,
                "object": "response",
                "status": "in_progress",
                "model": model,
            }
            yield f"event: response.created\ndata: {json.dumps(created_data)}\n\n"

            # 2. Stream content chunks
            accumulated_text = ""
            try:
                async for chunk in client.generate_content_stream(
                    prompt, model=model
                ):
                    delta_text = chunk.text_delta or ""
                    if delta_text:
                        accumulated_text += delta_text
                        delta_data = {
                            "delta": delta_text,
                            "response_id": completion_id
                        }
                        yield f"event: response.output_text.delta\ndata: {json.dumps(delta_data)}\n\n"

            except Exception as e:
                error_data = {
                    "message": str(e),
                    "type": "invalid_request_error"
                }
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 3. Send response.completed event
            completed_data = {
                "id": completion_id,
                "object": "response",
                "status": "completed",
                "model": model,
                "output": [
                    {
                        "id": f"out-{uuid.uuid4().hex}",
                        "object": "response.output",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": accumulated_text
                            }
                        ]
                    }
                ]
            }
            yield f"event: response.completed\ndata: {json.dumps(completed_data)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Non-Streaming Mode ──────────────────────────────────────────────────
    try:
        response = await client.generate_content(prompt, model=model)
        text = response.text or ""
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini error: {str(e)}",
        )

    completion_id = f"resp-{uuid.uuid4().hex}"
    return {
        "id": completion_id,
        "object": "response",
        "model": model,
        "status": "completed",
        "output": [
            {
                "id": f"out-{uuid.uuid4().hex}",
                "object": "response.output",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": text
                    }
                ]
            }
        ]
    }

