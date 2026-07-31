"""Chat-completions endpoint."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.protocol.schemas import ChatCompletionRequest
from app.protocol.streaming import completion_stream, should_inject_stream_error
from app.security import require_bearer_token

router = APIRouter()


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_bearer_token)],
    response_model=None,
)
async def create_chat_completion(
    request: ChatCompletionRequest,
) -> JSONResponse | StreamingResponse:
    user_messages = [
        message.content for message in request.messages if message.role == "user"
    ]
    if not user_messages:
        raise HTTPException(status_code=422, detail="At least one user message is required")

    user_message = user_messages[-1]
    answer = f"接入测试成功。收到用户消息：{user_message}"
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    if not request.stream:
        return JSONResponse(
            {
                "id": completion_id,
                "object": "chat.completion",
                "created": created,
                "model": "coursepilot-probe",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": answer},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
        )

    return StreamingResponse(
        completion_stream(
            completion_id,
            created,
            answer,
            inject_error=should_inject_stream_error(user_message),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
