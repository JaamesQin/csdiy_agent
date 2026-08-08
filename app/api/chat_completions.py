"""Chat-completions endpoint."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent.orchestrator import CoursePilotAgent
from app.agent.runtime import get_coursepilot_agent
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
    agent: CoursePilotAgent = Depends(get_coursepilot_agent),
) -> JSONResponse | StreamingResponse:
    user_messages = [
        message.content for message in request.messages if message.role == "user"
    ]
    if not user_messages:
        raise HTTPException(status_code=422, detail="At least one user message is required")

    user_message = user_messages[-1]
    reply = await agent.handle(messages=request.messages, user_id=request.user)
    answer = reply.answer
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
                "usage": reply.usage,
            }
        )

    return StreamingResponse(
        completion_stream(
            completion_id,
            created,
            answer,
            usage=reply.usage,
            inject_error=should_inject_stream_error(user_message),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
