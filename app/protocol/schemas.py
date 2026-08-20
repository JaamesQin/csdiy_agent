"""Request schemas for the minimal chat-completions contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None
    stream: StrictBool = False
    max_tokens: int | None = Field(default=None, ge=1)
    user: str | None = Field(default=None, max_length=128)
    coursepilot_context: str | None = Field(default=None, max_length=16384)
    session_id: str | None = Field(default=None, alias="sessionId", max_length=256)

    @field_validator("session_id", mode="before")
    @classmethod
    def normalize_session_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value
