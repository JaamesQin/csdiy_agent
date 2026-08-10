"""CoursePilot online orchestration, independent from HTTP/SSE rendering."""

from __future__ import annotations

import sqlite3

from app.agent.context import build_turn_context
from app.agent.contracts import AgentReply, CourseContext, Intent
from app.agent.capabilities import capability_for_intent, render_capability_help
from app.agent.model_support import add_usage, normalized_usage
from app.agent.router import IntentRouter
from app.catalog.studykits import StudyKitStore
from app.code_tutor.service import CodeTutorService, render_tutor_result
from app.profile.contracts import FactStatus, LearnerProfile
from app.profile.service import ProfileAction, ProfileService
from app.protocol.schemas import ChatMessage


class CoursePilotAgent:
    def __init__(
        self,
        *,
        store: StudyKitStore,
        router: IntentRouter,
        profiles: ProfileService,
        code_tutor: CodeTutorService,
    ) -> None:
        self.store = store
        self.router = router
        self.profiles = profiles
        self.code_tutor = code_tutor

    async def handle(
        self,
        *,
        messages: list[ChatMessage],
        user_id: str | None,
    ) -> AgentReply:
        normalized_user = user_id.strip() if user_id and user_id.strip() else None
        user_texts = [message.content for message in messages if message.role == "user"]
        profile_error = False
        if normalized_user:
            try:
                profile = self.profiles.load(normalized_user)
            except (OSError, sqlite3.Error, RuntimeError):
                profile = self.profiles.transient_from_messages(user_texts[:-1])
                profile_error = True
        else:
            profile = self.profiles.transient_from_messages(user_texts[:-1])

        profile_context = self._profile_course_context(profile)
        route = await self.router.route(messages, profile_context=profile_context)
        decision = route.decision
        latest = user_texts[-1]
        usage = route.usage

        if decision.intent is Intent.CAPABILITY_HELP:
            return AgentReply(
                answer=render_capability_help(
                    decision.capability_id,
                    unknown_topic=(
                        decision.clarifying_question
                        if decision.reason == "capability_help_unknown"
                        else None
                    ),
                ),
                usage=normalized_usage(usage),
            )

        action, _ = self.profiles.management_action(latest)
        if decision.intent is Intent.PROFILE_ANALYSIS and action is not ProfileAction.NONE:
            try:
                answer, _ = self.profiles.handle_management(
                    user_id=normalized_user,
                    text=latest,
                    profile=profile,
                )
            except (OSError, sqlite3.Error, RuntimeError):
                answer = "画像存储当前不可用，因此这次修改没有保存。"
            return AgentReply(answer=answer, usage=normalized_usage(usage))

        observation = await self.profiles.observe(
            user_id=normalized_user,
            text=latest,
            current=profile,
            course_context=decision.course_context,
        )
        profile = observation.profile
        usage = add_usage(usage, observation.usage)
        profile_error = profile_error or observation.persistence_error

        if decision.intent is Intent.PROFILE_ANALYSIS:
            answer = self.profiles.render(profile)
        elif decision.intent is Intent.CODE_TUTORING:
            turn = build_turn_context(messages)
            result = await self.code_tutor.tutor_code(
                user_id=normalized_user,
                conversation_id=None,
                course_context=decision.course_context,
                code=turn.code,
                language=turn.language,
                error_text=turn.error_text,
                question=turn.user_text,
                profile=profile,
            )
            answer = render_tutor_result(result)
            usage = add_usage(usage, result.usage)
        elif decision.intent is Intent.ADMIN_GENERATE_STUDYKIT:
            answer = (
                "普通对话不能触发后台 StudyKit authoring。在线请求只读取已审核产物；"
                "生成任务必须通过受控的开发者或后台入口提交。"
            )
        elif decision.intent is Intent.FALLBACK_CLARIFICATION:
            answer = self._fallback_answer(decision.reason, decision.clarifying_question, profile)
        else:
            answer = self._unavailable_answer(decision.intent, decision.clarifying_question)

        notices: list[str] = []
        if observation.notice:
            notices.append(f"画像更新：{observation.notice}")
        if profile_error:
            notices.append("画像存储当前不可用；本轮仍可继续，但画像没有持久保存。")
        if notices:
            answer = f"{answer}\n\n---\n" + "\n".join(notices)
        return AgentReply(answer=answer, usage=normalized_usage(usage))

    def _profile_course_context(self, profile: LearnerProfile) -> CourseContext | None:
        course_fact = next(
            (
                fact
                for fact in reversed(profile.facts)
                if fact.field_name == "active_course"
                and fact.status is FactStatus.CONFIRMED
            ),
            None,
        )
        if course_fact is None or not isinstance(course_fact.value, str):
            return None
        unit_fact = next(
            (
                fact
                for fact in reversed(profile.facts)
                if fact.field_name == "active_unit"
                and fact.status is FactStatus.CONFIRMED
            ),
            None,
        )
        return self.store.resolve_context(
            course_id=course_fact.value,
            course_version=course_fact.course_version,
            unit_id=(
                str(unit_fact.value)
                if unit_fact is not None and isinstance(unit_fact.value, str)
                else None
            ),
        )

    def _fallback_answer(
        self,
        reason: str | None,
        clarifying_question: str | None,
        profile: LearnerProfile,
    ) -> str:
        if reason == "greeting":
            if not profile.confirmed("learning_directions") or not profile.confirmed("weekly_minutes"):
                return (
                    "你好，我是 CoursePilot。我可以先建立学习画像，或对你粘贴的代码做静态辅导。"
                    "输入 /help 可以查看当前功能。你想学习哪个 CS 方向？每周大约能投入多少时间？"
                )
            return (
                "你好，我已经读取了你的学习画像。你可以继续让我分析代码或查看画像；"
                "输入 /help 可以查看当前功能。"
            )
        if clarifying_question:
            return f"我可以帮助整理学习画像或静态分析代码。{clarifying_question}"
        return "请说明你希望整理学习画像，还是分析一段代码。"

    @staticmethod
    def _unavailable_answer(intent: Intent, clarification: str | None) -> str:
        capability = capability_for_intent(intent)
        if capability is not None:
            return render_capability_help(capability.capability_id)
        label = intent.value
        suffix = f"\n\n{clarification}" if clarification else ""
        return (
            f"我识别到你的意图是“{label}”，但该在线能力尚未接入。"
            "当前可用的是学习画像和静态代码辅导；我不会在缺少检索依据时编造课程事实。"
            f"{suffix}"
        )
