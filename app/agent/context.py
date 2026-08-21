"""Minimal turn-context extraction for the online Agent."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.agent.contracts import CodeTutorMode, SemanticCodeRequest
from app.agent.understanding import (
    ExtractedCode,
    FENCE_BLOCK,
    OUTPUT_FENCE_LABELS,
    build_code_tutor_request,
    extract_code,
    extract_referenced_assistant_code,
    understand_user_texts,
)
from app.code_tutor.contracts import CodeTutorRequest
from app.code_tutor.languages import normalize_language_label
from app.protocol.schemas import ChatMessage

CODE_FENCE = re.compile(r"```([^\n`]*)\r?\n(.*?)```", re.DOTALL)
ERROR_LINE = re.compile(
    r"(?:"
    r"(?:fatal\s+)?error(?:\[[A-Z0-9_]+\])?\s*[:：]|"
    r"(?:[A-Za-z_][\w.]*(?:Error|Exception))\s*[:：]|"
    r"exception in thread|nvcc fatal|cuda error|undefined control sequence|"
    r"!\s*latex error|编译错误[:：]|语法错误[:：]|报错[:：]"
    r")",
    re.IGNORECASE,
)
CODE_BODY_REQUIRED_MODES = {
    CodeTutorMode.DIAGNOSE,
    CodeTutorMode.REVIEW,
    CodeTutorMode.REPAIR,
    CodeTutorMode.REFACTOR,
}


class TurnContext(BaseModel):
    user_text: str
    code: str = ""
    language: str | None = None
    error_text: str | None = None
    language_inferred: bool = False
    code_source: str | None = None
    code_request: CodeTutorRequest = Field(default_factory=CodeTutorRequest)


def build_turn_context(
    messages: list[ChatMessage],
    *,
    semantic_request: SemanticCodeRequest | None = None,
) -> TurnContext:
    user_messages = [message.content for message in messages if message.role == "user"]
    understanding = understand_user_texts(user_messages)
    latest = understanding.latest_user_text
    extracted = extract_code([latest])
    request = build_code_tutor_request(latest, extracted, semantic_request)
    if not extracted.content:
        extracted = extract_referenced_assistant_code(messages, latest)
        request = build_code_tutor_request(latest, extracted, semantic_request)
    if not extracted.content and understanding.code_requested:
        if request.mode in CODE_BODY_REQUIRED_MODES or request.references_existing_code:
            extracted = understanding.code
            request = build_code_tutor_request(latest, extracted, semantic_request)
        elif understanding.code.language is not None:
            # Conceptual requests may reuse a reliably identified recent language,
            # but never silently attach an unrelated historical code body.
            request = build_code_tutor_request(
                latest,
                ExtractedCode(
                    language=understanding.code.language,
                    language_inferred=True,
                    source="recent_language",
                ),
                semantic_request,
            )

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
        plain_text = FENCE_BLOCK.sub("", text)
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
        code=extracted.content,
        language=extracted.language,
        error_text=error_text,
        language_inferred=extracted.language_inferred,
        code_source=extracted.source,
        code_request=request,
    )
