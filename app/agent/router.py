"""Rule-first intent routing with an optional structured-model fallback."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.contracts import (
    CapabilityId,
    CourseContext,
    Intent,
    RouteDecision,
    RouteOutcome,
)
from app.agent.capabilities import CAPABILITIES, match_capability_help
from app.agent.model_support import normalized_usage
from app.catalog.studykits import StudyKitStore
from app.generation.model import ModelError, StructuredModel
from app.protocol.schemas import ChatMessage

ROUTE_CONFIDENCE_THRESHOLD = 0.70


class _ModelRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    confidence: float = Field(ge=0, le=1)
    course_id: str | None = None
    course_version: str | None = None
    unit_id: str | None = None
    capability_id: CapabilityId | None = None
    required_context: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None


class IntentRouter:
    def __init__(
        self,
        store: StudyKitStore,
        model: StructuredModel | None = None,
    ) -> None:
        self.store = store
        self.model = model

    async def route(
        self,
        messages: list[ChatMessage],
        *,
        profile_context: CourseContext | None = None,
    ) -> RouteOutcome:
        latest = next(
            message.content for message in reversed(messages) if message.role == "user"
        )
        recent_user_texts = [
            message.content for message in messages if message.role == "user"
        ][-6:]
        explicit_context = self.store.match_context(recent_user_texts)
        course_context = explicit_context or profile_context
        deterministic = self._rule_route(latest, course_context)
        if deterministic is not None:
            return RouteOutcome(decision=deterministic, usage=normalized_usage())

        if self.model is None:
            return RouteOutcome(
                decision=RouteDecision(
                    intent=Intent.FALLBACK_CLARIFICATION,
                    confidence=0.4,
                    course_context=course_context,
                    clarifying_question=(
                        "你希望我帮你整理学习画像，还是分析一段代码？"
                    ),
                    reason="model_unavailable",
                ),
                usage=normalized_usage(),
            )

        try:
            response = await self.model.generate_json(
                system_prompt=(
                    "你是 CoursePilot 意图分类器，只分类而不回答课程事实。"
                    "普通聊天不得触发 admin_generate_studykit。课程标识只能作为候选。"
                    "低置信度时提供一个澄清问题。只输出 JSON object。"
                ),
                user_prompt=json.dumps(
                    {
                        "intents": [intent.value for intent in Intent],
                        "capabilities": [
                            {
                                "id": item.capability_id.value,
                                "title": item.title,
                                "availability": item.availability,
                            }
                            for item in CAPABILITIES
                        ],
                        "latest_user_message": latest[:10000],
                        "known_context": (
                            course_context.model_dump() if course_context else None
                        ),
                        "output": {
                            "intent": "one enum value",
                            "confidence": 0.0,
                            "course_id": None,
                            "course_version": None,
                            "unit_id": None,
                            "capability_id": None,
                            "required_context": [],
                            "clarifying_question": None,
                        },
                    },
                    ensure_ascii=False,
                ),
                thinking_enabled=False,
                max_tokens=2048,
                timeout_seconds=30,
            )
            candidate = _ModelRoute.model_validate(response.output)
            usage = normalized_usage(response.usage)
        except (ModelError, ValidationError, ValueError):
            return RouteOutcome(
                decision=RouteDecision(
                    intent=Intent.FALLBACK_CLARIFICATION,
                    confidence=0.0,
                    course_context=course_context,
                    clarifying_question="请补充你要完成的学习任务或需要分析的代码。",
                    reason="classifier_failed",
                ),
                usage=normalized_usage(),
            )

        model_context: CourseContext | None = None
        if candidate.course_id or candidate.course_version or candidate.unit_id:
            model_context = self.store.resolve_context(
                course_id=candidate.course_id,
                course_version=candidate.course_version,
                unit_id=candidate.unit_id,
            )
            if model_context is None:
                return RouteOutcome(
                    decision=RouteDecision(
                        intent=Intent.FALLBACK_CLARIFICATION,
                        confidence=0.0,
                        course_context=course_context,
                        clarifying_question="我无法确认你提到的课程版本或讲次，请提供准确名称。",
                        reason="unvalidated_course_context",
                    ),
                    usage=usage,
                )
        resolved_context = model_context or course_context
        if candidate.confidence < ROUTE_CONFIDENCE_THRESHOLD:
            return RouteOutcome(
                decision=RouteDecision(
                    intent=Intent.FALLBACK_CLARIFICATION,
                    confidence=candidate.confidence,
                    course_context=resolved_context,
                    required_context=candidate.required_context,
                    clarifying_question=(
                        candidate.clarifying_question
                        or "请说明你希望进行画像分析还是代码辅导。"
                    ),
                    reason="low_confidence",
                ),
                usage=usage,
            )
        intent = candidate.intent
        if intent is Intent.ADMIN_GENERATE_STUDYKIT:
            return RouteOutcome(
                decision=RouteDecision(
                    intent=intent,
                    confidence=candidate.confidence,
                    course_context=resolved_context,
                    reason="admin_intent_blocked_for_chat",
                ),
                usage=usage,
            )
        return RouteOutcome(
            decision=RouteDecision(
                intent=intent,
                confidence=candidate.confidence,
                course_context=resolved_context,
                capability_id=(
                    candidate.capability_id
                    if intent is Intent.CAPABILITY_HELP
                    else None
                ),
                required_context=candidate.required_context,
                clarifying_question=candidate.clarifying_question,
                reason="model_classifier",
            ),
            usage=usage,
        )

    def _rule_route(
        self, text: str, course_context: CourseContext | None
    ) -> RouteDecision | None:
        lowered = text.lower().strip()
        help_match = match_capability_help(text)
        if help_match.handled:
            return RouteDecision(
                intent=Intent.CAPABILITY_HELP,
                confidence=1.0,
                course_context=course_context,
                capability_id=(
                    help_match.capability.capability_id
                    if help_match.capability is not None
                    else None
                ),
                clarifying_question=help_match.unknown_topic,
                reason=(
                    "capability_help_unknown"
                    if help_match.unknown_topic
                    else "capability_help_rule"
                ),
            )
        if re.search(r"admin_generate_studykit|后台生成|运行生成器|authoring job", lowered):
            return RouteDecision(
                intent=Intent.ADMIN_GENERATE_STUDYKIT,
                confidence=1.0,
                course_context=course_context,
                reason="admin_rule",
            )

        code_signal = bool(
            "```" in text
            or re.search(r"traceback \(most recent call last\)|syntaxerror|typeerror|cuda error", lowered)
            or re.search(r"代码辅导|帮我调试|debug|报错|审阅.*代码|代码.*问题", lowered)
        )
        if code_signal:
            has_code = "```" in text
            required = [] if has_code else ["user_code"]
            return RouteDecision(
                intent=Intent.CODE_TUTORING,
                confidence=0.98,
                course_context=course_context,
                required_context=required,
                clarifying_question=(
                    None
                    if has_code
                    else "请用 Markdown 代码围栏粘贴最小相关代码，并附上报错。"
                ),
                reason="code_rule",
            )

        profile_action = bool(
            re.search(r"画像|你记得我|了解我|删除.*(?:时间|方向|基础|目标)|确认记录", lowered)
        )
        profile_statement = bool(
            re.search(r"每(?:周|星期).*?(?:小时|分钟)|想学|准备学|学习方向|我的目标|有.*基础|学过|偏好", lowered)
        )
        if profile_action or profile_statement:
            return RouteDecision(
                intent=Intent.PROFILE_ANALYSIS,
                confidence=0.96,
                course_context=course_context,
                reason="profile_rule",
            )

        if re.search(r"studykit|学习包", lowered):
            return RouteDecision(
                intent=Intent.STUDYKIT_LOOKUP,
                confidence=0.92,
                course_context=course_context,
                reason="studykit_rule",
            )
        if re.search(r"推荐.*课程|选课|学习路线|学什么课", lowered):
            return RouteDecision(
                intent=Intent.COURSE_NAVIGATION,
                confidence=0.9,
                course_context=course_context,
                reason="course_navigation_rule",
            )
        if re.search(r"练习.*反馈|点评.*答案|批改", lowered):
            return RouteDecision(
                intent=Intent.PRACTICE_FEEDBACK,
                confidence=0.9,
                course_context=course_context,
                reason="practice_feedback_rule",
            )
        if re.search(r"给我.*练习|选择.*练习|做道题", lowered):
            return RouteDecision(
                intent=Intent.PRACTICE_SELECTION,
                confidence=0.9,
                course_context=course_context,
                reason="practice_selection_rule",
            )
        if re.search(r"复盘|学习总结|下一步计划", lowered):
            return RouteDecision(
                intent=Intent.LEARNING_REVIEW,
                confidence=0.88,
                course_context=course_context,
                reason="learning_review_rule",
            )
        if re.search(r"生成状态|任务状态|生成到哪", lowered):
            return RouteDecision(
                intent=Intent.GENERATION_STATUS,
                confidence=0.9,
                course_context=course_context,
                reason="generation_status_rule",
            )
        if re.search(r"材料里|讲义里|第\s*\d+\s*页", lowered):
            return RouteDecision(
                intent=Intent.MATERIAL_QUESTION,
                confidence=0.85,
                course_context=course_context,
                reason="material_question_rule",
            )
        if re.search(r"解释|什么是|为什么", lowered):
            return RouteDecision(
                intent=Intent.CONCEPT_EXPLANATION,
                confidence=0.82,
                course_context=course_context,
                reason="concept_rule",
            )
        if re.fullmatch(r"(?:你好|您好|hello|hi|嗨)[！!。\s]*", lowered):
            return RouteDecision(
                intent=Intent.FALLBACK_CLARIFICATION,
                confidence=1.0,
                course_context=course_context,
                reason="greeting",
            )
        return None
