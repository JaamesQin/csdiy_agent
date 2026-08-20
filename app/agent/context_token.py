"""Short-lived, tamper-evident continuity tokens with no learner content."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.contracts import StudyKitCourseIdentity


class ConversationState(BaseModel):
    """Minimal trusted continuity shared by signed tokens and server sessions."""

    model_config = ConfigDict(extra="forbid")

    state_version: int = Field(default=1, ge=1, le=1)
    course: StudyKitCourseIdentity | None = None
    active_practice_id: str | None = Field(default=None, max_length=300)
    displayed_practice_ids: list[str] = Field(default_factory=list, max_length=64)
    hint_level: int = Field(default=0, ge=0, le=5)
    practice_presentation_kind: Literal[
        "original", "structured_rewrite", "grounded_variant"
    ] | None = None
    practice_presentation_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    code_artifact_id: str | None = Field(default=None, max_length=100)
    code_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    displayed_catalog_ids: list[str] = Field(default_factory=list, max_length=5)
    selected_catalog_id: str | None = Field(default=None, max_length=200)
    last_capability: str | None = Field(default=None, max_length=100)
    last_concept: str | None = Field(default=None, max_length=200)

    def model_post_init(self, __context: object) -> None:
        if (self.code_artifact_id is None) != (self.code_digest is None):
            raise ValueError("code artifact ID and digest must be present together")
        if (self.practice_presentation_kind is None) != (
            self.practice_presentation_digest is None
        ):
            raise ValueError("practice presentation kind and digest must be present together")


class ConversationContextToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=3, ge=1, le=3)
    issued_at: int
    expires_at: int
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    course: StudyKitCourseIdentity | None = None
    active_practice_id: str | None = Field(default=None, max_length=300)
    displayed_practice_ids: list[str] = Field(default_factory=list, max_length=64)
    hint_level: int = Field(default=0, ge=0, le=5)
    practice_presentation_kind: Literal[
        "original", "structured_rewrite", "grounded_variant"
    ] | None = None
    practice_presentation_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    code_artifact_id: str | None = Field(default=None, max_length=100)
    code_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    displayed_catalog_ids: list[str] = Field(default_factory=list, max_length=5)
    selected_catalog_id: str | None = Field(default=None, max_length=200)
    last_capability: str | None = Field(default=None, max_length=100)
    last_concept: str | None = Field(default=None, max_length=200)

    def model_post_init(self, __context: object) -> None:
        if (self.code_artifact_id is None) != (self.code_digest is None):
            raise ValueError("code artifact ID and digest must be present together")
        if (self.practice_presentation_kind is None) != (
            self.practice_presentation_digest is None
        ):
            raise ValueError("practice presentation kind and digest must be present together")

    def to_state(self) -> ConversationState:
        return ConversationState(
            **self.model_dump(
                exclude={"version", "issued_at", "expires_at", "plan_digest"}
            )
        )


class ContextTokenSigner:
    def __init__(self, secret: bytes, *, ttl_seconds: int = 900) -> None:
        if len(secret) < 32:
            raise ValueError("context token secret must be at least 32 bytes")
        if not 30 <= ttl_seconds <= 3600:
            raise ValueError("context token TTL must be between 30 and 3600 seconds")
        self._secret = secret
        self._ttl_seconds = ttl_seconds

    def issue(
        self,
        *,
        plan: dict[str, Any],
        course: StudyKitCourseIdentity | None = None,
        active_practice_id: str | None = None,
        displayed_practice_ids: list[str] | None = None,
        hint_level: int = 0,
        practice_presentation_kind: Literal[
            "original", "structured_rewrite", "grounded_variant"
        ] | None = None,
        practice_presentation_digest: str | None = None,
        code_artifact_id: str | None = None,
        code_digest: str | None = None,
        displayed_catalog_ids: list[str] | None = None,
        selected_catalog_id: str | None = None,
        last_capability: str | None = None,
        last_concept: str | None = None,
        now: int | None = None,
    ) -> str:
        issued_at = int(time.time()) if now is None else now
        canonical_plan = json.dumps(
            plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        payload = ConversationContextToken(
            issued_at=issued_at,
            expires_at=issued_at + self._ttl_seconds,
            plan_digest=hashlib.sha256(canonical_plan).hexdigest(),
            course=course,
            active_practice_id=active_practice_id,
            displayed_practice_ids=list(dict.fromkeys(displayed_practice_ids or [])),
            hint_level=hint_level,
            practice_presentation_kind=practice_presentation_kind,
            practice_presentation_digest=practice_presentation_digest,
            code_artifact_id=code_artifact_id,
            code_digest=code_digest,
            displayed_catalog_ids=list(dict.fromkeys(displayed_catalog_ids or []))[:5],
            selected_catalog_id=selected_catalog_id,
            last_capability=last_capability,
            last_concept=last_concept,
        )
        encoded = _encode(payload.model_dump_json().encode("utf-8"))
        signature = _encode(hmac.digest(self._secret, encoded.encode("ascii"), "sha256"))
        return f"{encoded}.{signature}"

    def issue_state(
        self,
        *,
        plan: dict[str, Any],
        state: ConversationState,
        now: int | None = None,
    ) -> str:
        return self.issue(
            plan=plan,
            course=state.course,
            active_practice_id=state.active_practice_id,
            displayed_practice_ids=state.displayed_practice_ids,
            hint_level=state.hint_level,
            practice_presentation_kind=state.practice_presentation_kind,
            practice_presentation_digest=state.practice_presentation_digest,
            code_artifact_id=state.code_artifact_id,
            code_digest=state.code_digest,
            displayed_catalog_ids=state.displayed_catalog_ids,
            selected_catalog_id=state.selected_catalog_id,
            last_capability=state.last_capability,
            last_concept=state.last_concept,
            now=now,
        )

    def verify(self, token: str, *, now: int | None = None) -> ConversationContextToken | None:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected = _encode(hmac.digest(self._secret, encoded.encode("ascii"), "sha256"))
            if not hmac.compare_digest(supplied_signature, expected):
                return None
            payload = ConversationContextToken.model_validate_json(_decode(encoded))
        except (ValueError, UnicodeError, ValidationError, json.JSONDecodeError):
            return None
        current = int(time.time()) if now is None else now
        if payload.issued_at > current + 30 or payload.expires_at <= current:
            return None
        return payload


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)
