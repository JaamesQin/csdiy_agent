from __future__ import annotations

from typing import Any

from app.generation.model import ModelResponse


class FakeStructuredModel:
    def __init__(self, *outputs: dict[str, Any]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []

    async def generate_json(self, **kwargs: Any) -> ModelResponse:
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        return ModelResponse(
            output=output,
            raw_content="{}",
            model="fake-agent-model",
            finish_reason="stop",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            request_id="fake-agent-request",
        )
