from __future__ import annotations

import pytest

from app.agent.contracts import Intent
from app.agent.router import IntentRouter
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.protocol.schemas import ChatMessage
from tests.agent.helpers import FakeStructuredModel


def _messages(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("推荐一门课程", Intent.COURSE_NAVIGATION),
        ("查看这讲的 StudyKit", Intent.STUDYKIT_LOOKUP),
        ("讲义里第 8 页说了什么", Intent.MATERIAL_QUESTION),
        ("解释什么是反向传播", Intent.CONCEPT_EXPLANATION),
        ("给我一道练习", Intent.PRACTICE_SELECTION),
        ("点评我的练习答案", Intent.PRACTICE_FEEDBACK),
        ("```python\nprint(1)\n``` 帮我调试", Intent.CODE_TUTORING),
        ("查看我的画像", Intent.PROFILE_ANALYSIS),
        ("帮我做学习复盘", Intent.LEARNING_REVIEW),
        ("查看生成状态", Intent.GENERATION_STATUS),
        ("运行生成器后台生成", Intent.ADMIN_GENERATE_STUDYKIT),
        ("你好", Intent.FALLBACK_CLARIFICATION),
    ],
)
async def test_rule_router_covers_all_intents(text: str, intent: Intent) -> None:
    router = IntentRouter(ReviewedFileStudyKitStore())

    result = await router.route(_messages(text))

    assert result.decision.intent is intent


async def test_code_rule_has_priority_over_profile_sidecar_signal() -> None:
    router = IntentRouter(ReviewedFileStudyKitStore())

    result = await router.route(
        _messages("我有 Python 基础，请调试：\n```python\nprint(1)\n```")
    )

    assert result.decision.intent is Intent.CODE_TUTORING


async def test_low_confidence_model_route_becomes_clarification() -> None:
    model = FakeStructuredModel(
        {
            "intent": "material_question",
            "confidence": 0.4,
            "course_id": None,
            "course_version": None,
            "unit_id": None,
            "required_context": [],
            "clarifying_question": "你在问哪门课？",
        }
    )
    router = IntentRouter(ReviewedFileStudyKitStore(), model=model)

    result = await router.route(_messages("帮我看看这个"))

    assert result.decision.intent is Intent.FALLBACK_CLARIFICATION
    assert result.decision.clarifying_question == "你在问哪门课？"
    assert result.usage["total_tokens"] == 15


async def test_model_cannot_invent_course_context() -> None:
    model = FakeStructuredModel(
        {
            "intent": "code_tutoring",
            "confidence": 0.95,
            "course_id": "invented-course",
            "course_version": "2026",
            "unit_id": "lecture-01",
            "required_context": [],
            "clarifying_question": None,
        }
    )
    router = IntentRouter(ReviewedFileStudyKitStore(), model=model)

    result = await router.route(_messages("协助一下这个程序"))

    assert result.decision.intent is Intent.FALLBACK_CLARIFICATION
    assert result.decision.reason == "unvalidated_course_context"
