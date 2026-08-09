"""SSE construction for OpenAI-compatible streaming responses."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator


def _frame(
    completion_id: str,
    created: int,
    delta: dict[str, str],
    *,
    finish_reason: str | None = None,
    usage: dict[str, int] | None = None,
    error: dict[str, str] | None = None,
) -> str:
    chunk: dict[str, object] = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": "coursepilot-probe",
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage is not None:
        chunk["usage"] = usage
    if error is not None:
        chunk["error"] = error
    return f"data: {json.dumps(chunk, ensure_ascii=False, separators=(',', ':'))}\n\n"


def _content_chunks(answer: str, size: int = 12) -> list[str]:
    return [answer[index : index + size] for index in range(0, len(answer), size)]


async def completion_stream(
    completion_id: str,
    created: int,
    answer: str,
    *,
    usage: dict[str, int] | None = None,
    inject_error: bool = False,
) -> AsyncIterator[str]:
    completion_usage = usage or {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    yield _frame(completion_id, created, {"role": "assistant"})

    try:
        for index, chunk in enumerate(_content_chunks(answer)):
            await asyncio.sleep(0.03)
            yield _frame(completion_id, created, {"content": chunk})
            if inject_error and index == 0:
                raise RuntimeError("injected stream failure")
    except Exception:
        yield _frame(
            completion_id,
            created,
            {},
            finish_reason="stop",
            usage=completion_usage,
            error={
                "type": "stream_error",
                "message": "The stream ended because an internal error occurred.",
            },
        )
        yield "data: [DONE]\n\n"
        return

    yield _frame(
        completion_id,
        created,
        {},
        finish_reason="stop",
        usage=completion_usage,
    )
    yield "data: [DONE]\n\n"


def should_inject_stream_error(user_message: str) -> bool:
    return (
        os.getenv("COURSEPILOT_TEST_MODE", "").lower() == "true"
        and user_message == "__trigger_stream_error__"
    )
