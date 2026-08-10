"""Minimal turn-context extraction for the online Agent."""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.protocol.schemas import ChatMessage

CODE_FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)


class TurnContext(BaseModel):
    user_text: str
    code: str = ""
    language: str | None = None
    error_text: str | None = None


def build_turn_context(messages: list[ChatMessage]) -> TurnContext:
    user_messages = [message.content for message in messages if message.role == "user"]
    latest = user_messages[-1]
    code = ""
    language: str | None = None
    for text in reversed(user_messages):
        matches = list(CODE_FENCE.finditer(text))
        if matches:
            language = matches[-1].group(1).strip().lower() or None
            code = matches[-1].group(2).strip()
            break

    error_text: str | None = None
    for text in reversed(user_messages):
        traceback = re.search(
            r"(Traceback \(most recent call last\):.*)$", text, re.DOTALL
        )
        if traceback:
            error_text = traceback.group(1).strip()[:8000]
            break
        error_line = re.search(
            r"((?:SyntaxError|TypeError|ValueError|RuntimeError|AssertionError|"
            r"IndexError|KeyError|AttributeError|NameError|CUDA error)[^\n]*)",
            text,
            re.IGNORECASE,
        )
        if error_line:
            error_text = error_line.group(1).strip()[:2000]
            break
    return TurnContext(
        user_text=latest,
        code=code[:20000],
        language=language,
        error_text=error_text,
    )
