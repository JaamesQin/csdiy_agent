from __future__ import annotations

import pytest

from app.agent.contracts import CapabilityId, Intent
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
        ("查看 MIT 6.7960", Intent.COURSE_NAVIGATION),
        ("查询 UCB CS61B", Intent.COURSE_NAVIGATION),
        ("查看这讲的 StudyKit", Intent.STUDYKIT_LOOKUP),
        ("查看 MIT 6.7960 第 2 讲", Intent.STUDYKIT_LOOKUP),
        ("讲义里第 8 页说了什么", Intent.MATERIAL_QUESTION),
        ("解释什么是反向传播", Intent.CONCEPT_EXPLANATION),
        ("给我一道练习", Intent.PRACTICE_SELECTION),
        ("点评我的练习答案", Intent.PRACTICE_FEEDBACK),
        ("```python\nprint(1)\n``` 帮我调试", Intent.CODE_TUTORING),
        ("给我一段完整的 cpp 示例代码", Intent.CODE_TUTORING),
        ("查看我的画像", Intent.PROFILE_ANALYSIS),
        ("帮我做学习复盘", Intent.GENERAL_ASSISTANCE),
        ("查看生成状态", Intent.GENERAL_ASSISTANCE),
        ("运行生成器后台生成", Intent.ADMIN_GENERATE_STUDYKIT),
        ("/help", Intent.CAPABILITY_HELP),
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


@pytest.mark.parametrize(
    ("text", "capability_id"),
    [
        ("你目前有哪些功能", None),
        ("/help code", CapabilityId.CODE_TUTORING),
        ("代码辅导 --help", CapabilityId.CODE_TUTORING),
        ("你的代码辅导支持什么语言", CapabilityId.CODE_TUTORING),
        ("你可以进行代码辅导吗？", CapabilityId.CODE_TUTORING),
        ("你能使用课程导航吗？", CapabilityId.COURSE_NAVIGATION),
        ("学习画像是什么", CapabilityId.PROFILE_ANALYSIS),
        ("课程导航是什么", CapabilityId.COURSE_NAVIGATION),
    ],
)
async def test_help_routes_before_capability_rules(
    text: str, capability_id: CapabilityId | None
) -> None:
    router = IntentRouter(ReviewedFileStudyKitStore())

    result = await router.route(_messages(text))

    assert result.decision.intent is Intent.CAPABILITY_HELP
    assert result.decision.capability_id is capability_id


async def test_unknown_help_topic_stays_in_help() -> None:
    router = IntentRouter(ReviewedFileStudyKitStore())

    result = await router.route(_messages("/help warp-drive"))

    assert result.decision.intent is Intent.CAPABILITY_HELP
    assert result.decision.capability_id is None
    assert result.decision.reason == "capability_help_unknown"
    assert result.decision.clarifying_question == "warp-drive"


async def test_programming_concept_question_is_not_capability_help() -> None:
    router = IntentRouter(ReviewedFileStudyKitStore())

    result = await router.route(_messages("C++ 中什么是 virtual"))

    assert result.decision.intent is Intent.CONCEPT_EXPLANATION


async def test_code_request_with_actual_code_is_not_capability_help() -> None:
    router = IntentRouter(ReviewedFileStudyKitStore())

    result = await router.route(
        _messages("你可以进行代码辅导吗？代码如下：```cpp\nint main(){}\n```")
    )

    assert result.decision.intent is Intent.CODE_TUTORING


async def test_generation_request_routes_without_user_code() -> None:
    router = IntentRouter(ReviewedFileStudyKitStore())

    result = await router.route(_messages("给我一段完整的 cpp 示例代码"))

    assert result.decision.intent is Intent.CODE_TUTORING
    assert result.decision.required_context == []


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


async def test_model_cannot_route_to_unavailable_capability() -> None:
    model = FakeStructuredModel(
        {
            "intent": "learning_review",
            "confidence": 0.95,
            "course_id": None,
            "course_version": None,
            "unit_id": None,
            "required_context": [],
            "clarifying_question": None,
        }
    )
    router = IntentRouter(ReviewedFileStudyKitStore(), model=model)

    result = await router.route(_messages("帮我回顾近期的学习。"))

    assert result.decision.intent is Intent.GENERAL_ASSISTANCE
    assert result.decision.reason == "unavailable_capability_fallback"
    assert result.decision.capability_id is CapabilityId.LEARNING_REVIEW
