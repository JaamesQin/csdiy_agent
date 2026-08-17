from __future__ import annotations

from app.agent.context_token import ContextTokenSigner
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
        code_artifact_id="code-1",
        code_digest="a" * 64,
        now=100,
    )

    verified = signer.verify(token, now=120)
    assert verified is not None
    assert verified.active_practice_id == "practice-1"
    assert "answer" not in token and "secret" not in token
    assert signer.verify(token + "x", now=120) is None
    assert signer.verify(token, now=160) is None
