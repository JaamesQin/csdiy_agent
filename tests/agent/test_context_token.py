from __future__ import annotations

from app.agent.context_token import ContextTokenSigner, ConversationState
from app.agent.contracts import StudyKitCourseIdentity


def test_context_token_is_minimal_tamper_evident_and_expiring() -> None:
    signer = ContextTokenSigner(b"x" * 32, ttl_seconds=60)
    token = signer.issue(
        plan={"tasks": ["practice"]},
        course=StudyKitCourseIdentity(
            course_id="course", course_version="v1", unit_id="lecture-01"
        ),
        active_practice_id="practice-1",
        displayed_practice_ids=["practice-1"],
        practice_presentation_kind="structured_rewrite",
        practice_presentation_digest="b" * 64,
        code_artifact_id="code-1",
        code_digest="a" * 64,
        now=100,
    )

    verified = signer.verify(token, now=120)
    assert verified is not None
    assert verified.active_practice_id == "practice-1"
    assert verified.version == 3
    assert verified.practice_presentation_kind == "structured_rewrite"
    assert verified.practice_presentation_digest == "b" * 64
    assert "answer" not in token and "secret" not in token
    assert signer.verify(token + "x", now=120) is None
    assert signer.verify(token, now=160) is None


def test_context_token_accepts_v1_without_presentation_state() -> None:
    signer = ContextTokenSigner(b"x" * 32, ttl_seconds=60)
    token = signer.issue(plan={"tasks": ["practice"]}, now=100)
    encoded, signature = token.split(".", 1)
    import base64
    import hashlib
    import hmac
    import json

    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    payload["version"] = 1
    payload.pop("practice_presentation_kind", None)
    payload.pop("practice_presentation_digest", None)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(
        hmac.digest(b"x" * 32, encoded.encode("ascii"), hashlib.sha256)
    ).rstrip(b"=").decode()

    verified = signer.verify(f"{encoded}.{signature}", now=120)
    assert verified is not None
    assert verified.version == 1
    assert verified.practice_presentation_digest is None


def test_context_token_carries_only_bounded_semantic_continuity() -> None:
    signer = ContextTokenSigner(b"x" * 32, ttl_seconds=60)
    token = signer.issue(
        plan={"tasks": ["course"]},
        displayed_catalog_ids=["course-a", "course-b"],
        selected_catalog_id="course-a",
        last_capability="course_navigation",
        last_concept="backpropagation",
        now=100,
    )

    verified = signer.verify(token, now=120)
    assert verified is not None
    assert verified.displayed_catalog_ids == ["course-a", "course-b"]
    assert verified.selected_catalog_id == "course-a"
    assert verified.last_concept == "backpropagation"
    assert "learner_answer" not in token


def test_context_token_and_server_state_share_the_same_continuity() -> None:
    signer = ContextTokenSigner(b"x" * 32, ttl_seconds=60)
    state = ConversationState(
        course=StudyKitCourseIdentity(
            course_id="course", course_version="v1", unit_id="lecture-02"
        ),
        displayed_practice_ids=["ex-1"],
        last_concept="gradients",
    )

    token = signer.issue_state(plan={"tasks": ["practice"]}, state=state, now=100)
    verified = signer.verify(token, now=120)

    assert verified is not None
    assert verified.to_state() == state
