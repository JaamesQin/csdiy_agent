"""Chat-completions endpoint."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.protocol.schemas import ChatCompletionRequest
from app.protocol.streaming import completion_stream, should_inject_stream_error
from app.auth.service import AuthService, get_auth_service
from app.profile.service import ProfileService, get_profile_service
from app.security import SecurityPrincipal, require_csrf, require_principal

router = APIRouter()


@router.post(
    "/v1/chat/completions",
    response_model=None,
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    principal: SecurityPrincipal = Depends(require_principal),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    auth: AuthService = Depends(get_auth_service),
    profiles: ProfileService = Depends(get_profile_service),
) -> JSONResponse | StreamingResponse:
    require_csrf(principal, csrf_token, auth)
    user_messages = [
        message.content for message in request.messages if message.role == "user"
    ]
    if not user_messages:
        raise HTTPException(status_code=422, detail="At least one user message is required")

    user_message = user_messages[-1]
    profile_user_id = principal.profile_user_id(request.user)
    profile_result = profiles.handle(user_id=profile_user_id, text=user_message)
    answer = profile_result.answer or f"接入测试成功。收到用户消息：{user_message}"
    if profile_result.added_fields:
        answer += "\n\n画像更新：已保存你明确提供的学习方向、时间或基础。"
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
