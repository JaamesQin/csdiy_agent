"""Minimal turn-context extraction for the online Agent."""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.code_tutor.languages import normalize_language_label
from app.protocol.schemas import ChatMessage

CODE_FENCE = re.compile(r"```([^\n`]*)\r?\n(.*?)```", re.DOTALL)
OUTPUT_FENCE_LABELS = {"console", "error", "errors", "log", "output", "text", "traceback"}
ERROR_LINE = re.compile(
    r"(?:"
    r"(?:fatal\s+)?error(?:\[[A-Z0-9_]+\])?\s*[:：]|"
    r"(?:[A-Za-z_][\w.]*(?:Error|Exception))\s*[:：]|"
    r"exception in thread|nvcc fatal|cuda error|undefined control sequence|"
    r"!\s*latex error|编译错误[:：]|语法错误[:：]|报错[:：]"
    r")",
    re.IGNORECASE,
)


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
        for match in reversed(matches):
            candidate_language = normalize_language_label(match.group(1))
            if candidate_language in OUTPUT_FENCE_LABELS:
                continue
            language = candidate_language
            code = match.group(2).strip()
            break
        if code:
            break

    error_text: str | None = None
    for text in reversed(user_messages):
        for match in reversed(list(CODE_FENCE.finditer(text))):
            fence_label = normalize_language_label(match.group(1))
            candidate = match.group(2).strip()
            if fence_label in OUTPUT_FENCE_LABELS and ERROR_LINE.search(candidate):
                error_text = candidate[:8000]
                break
        if error_text:
            break
        traceback = re.search(
            r"(Traceback \(most recent call last\):.*)$", text, re.DOTALL
        )
        if traceback:
            error_text = traceback.group(1).strip()[:8000]
            break
        plain_text = CODE_FENCE.sub("", text)
        error_lines = [
            line.strip()
            for line in plain_text.splitlines()
            if ERROR_LINE.search(line)
        ]
        if error_lines:
            error_text = "\n".join(error_lines[:8])[:2000]
            break
    return TurnContext(
        user_text=latest,
        code=code[:20000],
        language=language,
        error_text=error_text,
    )
