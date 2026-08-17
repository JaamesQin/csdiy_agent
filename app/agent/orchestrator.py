"""CoursePilot online orchestration, independent from HTTP/SSE rendering."""

from __future__ import annotations

import sqlite3
import re

from app.agent.context import build_turn_context
from app.agent.contracts import (
    AgentReply,
    CapabilityId,
    CourseContext,
    Intent,
    PlannedTask,
    StudyKitCourseIdentity,
    TaskExecutionResult,
    TaskStatus,
)
from app.agent.capabilities import (
    capability_for_intent,
    match_capability_help,
    render_capability_help,
)
from app.agent.executor import TaskExecutor, render_execution
from app.agent.context_token import ContextTokenSigner
from app.agent.model_support import add_usage, normalized_usage
from app.agent.planning import TaskPlanner
from app.agent.router import IntentRouter
from app.catalog.studykits import StudyKitStore
from app.code_tutor.service import CodeTutorService, render_tutor_result
from app.code_tutor.contracts import CodeArtifact
from app.course_navigation.service import CourseNavigationService
from app.learning.service import StudyKitLookupService
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
        course_navigation: CourseNavigationService,
        studykit_learning: StudyKitLookupService,
        planner: TaskPlanner | None = None,
        context_signer: ContextTokenSigner | None = None,
    ) -> None:
        self.store = store
        self.router = router
        self.profiles = profiles
        self.code_tutor = code_tutor
        self.course_navigation = course_navigation
        self.studykit_learning = studykit_learning
        self.planner = planner
        self.context_signer = context_signer

    async def handle(
        self,
        *,
        messages: list[ChatMessage],
        user_id: str | None,
        coursepilot_context: str | None = None,
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

        if self.planner is not None:
            if re.fullmatch(
                r"(?:你好|您好|hello|hi|嗨)[！!。\s]*",
                user_texts[-1].casefold().strip(),
            ):
                return AgentReply(
                    answer=self._fallback_answer("greeting", None, profile),
                    usage=normalized_usage(),
                )
            help_match = match_capability_help(user_texts[-1])
            if help_match.handled:
                return AgentReply(
                    answer=render_capability_help(
                        help_match.capability.capability_id
                        if help_match.capability is not None
                        else None,
                        unknown_topic=help_match.unknown_topic,
                    ),
                    usage=normalized_usage(),
                )
            return await self._handle_planned(
                messages=messages,
                latest=user_texts[-1],
                user_id=normalized_user,
                profile=profile,
                profile_error=profile_error,
                supplied_context=coursepilot_context,
            )

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
        elif decision.intent is Intent.COURSE_NAVIGATION:
            answer = self.course_navigation.navigate(text=latest, profile=profile)
        elif decision.intent is Intent.STUDYKIT_LOOKUP:
            result = await self.studykit_learning.lookup(
                messages=messages,
                course_context=decision.course_context,
            )
            answer = result.answer
            usage = add_usage(usage, result.usage)
        elif decision.intent is Intent.MATERIAL_QUESTION:
            result = await self.studykit_learning.material_question(
                messages=messages,
                course_context=decision.course_context,
            )
            answer = result.answer
            usage = add_usage(usage, result.usage)
        elif decision.intent is Intent.CONCEPT_EXPLANATION:
            result = await self.studykit_learning.concept_explanation(
                messages=messages,
                course_context=decision.course_context,
            )
            answer = result.answer
            usage = add_usage(usage, result.usage)
        elif decision.intent is Intent.PRACTICE_SELECTION:
            result = await self.studykit_learning.practice_selection(
                messages=messages,
                course_context=decision.course_context,
            )
            answer = result.answer
            usage = add_usage(usage, result.usage)
        elif decision.intent is Intent.PRACTICE_FEEDBACK:
            result = await self.studykit_learning.practice_feedback(
                messages=messages,
                course_context=decision.course_context,
            )
            answer = result.answer
            usage = add_usage(usage, result.usage)
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

    async def _handle_planned(
        self,
        *,
        messages: list[ChatMessage],
        latest: str,
        user_id: str | None,
        profile: LearnerProfile,
        profile_error: bool,
        supplied_context: str | None,
    ) -> AgentReply:
        plan_outcome = await self.planner.plan(messages)  # type: ignore[union-attr]
        plan = plan_outcome.plan
        user_texts = [message.content for message in messages if message.role == "user"]
        studykit_context = self.store.match_context(user_texts[-8:]) or self._profile_course_context(
            profile
        )
        current_profile = profile
        observation_notices: list[str] = []
        previous_context = (
            self.context_signer.verify(supplied_context)
            if self.context_signer is not None and supplied_context
            else None
        )
        displayed_practice_ids = list(
            previous_context.displayed_practice_ids if previous_context else []
        )
        active_practice_id = (
            previous_context.active_practice_id if previous_context else None
        )
        hint_level = previous_context.hint_level if previous_context else 0
        practice_presentation_kind = (
            previous_context.practice_presentation_kind if previous_context else None
        )
        practice_presentation_digest = (
            previous_context.practice_presentation_digest if previous_context else None
        )
        code_artifact_id = previous_context.code_artifact_id if previous_context else None
        code_digest = previous_context.code_digest if previous_context else None
        profile_observed = False

        async def execute(task: PlannedTask) -> TaskExecutionResult:
            nonlocal current_profile, profile_error, active_practice_id, hint_level
            nonlocal code_artifact_id, code_digest
            nonlocal profile_observed, practice_presentation_kind
            nonlocal practice_presentation_digest
            usage = normalized_usage()
            if task.self_statement and not profile_observed:
                observation = await self.profiles.observe(
                    user_id=user_id,
                    text=latest,
                    current=current_profile,
                    course_context=studykit_context,
                )
                current_profile = observation.profile
                usage = add_usage(usage, observation.usage)
                profile_error = profile_error or observation.persistence_error
                if observation.notice:
                    observation_notices.append(observation.notice)
                profile_observed = True

            capability = task.capability_id
            answer: str
            if task.parameters.get("blocked_authoring") is True:
                answer = (
                    "普通对话不能触发后台 StudyKit authoring。在线请求只读取已审核产物；"
                    "生成任务必须通过受控的开发者或后台入口提交。"
                )
            elif capability is CapabilityId.PROFILE_ANALYSIS:
                action, _ = self.profiles.management_action(latest)
                if action is not ProfileAction.NONE:
                    answer, current_profile = self.profiles.handle_management(
                        user_id=user_id,
                        text=latest,
                        profile=current_profile,
                    )
                else:
                    answer = self.profiles.render(current_profile)
            elif capability is CapabilityId.COURSE_NAVIGATION:
                answer = self.course_navigation.navigate(text=latest, profile=current_profile)
            elif capability is CapabilityId.STUDYKIT_LOOKUP:
                result = await self.studykit_learning.lookup(
                    messages=messages, course_context=studykit_context
                )
                answer, usage = result.answer, add_usage(usage, result.usage)
            elif capability is CapabilityId.MATERIAL_QUESTION:
                result = await self.studykit_learning.material_question(
                    messages=messages, course_context=studykit_context
                )
                answer, usage = result.answer, add_usage(usage, result.usage)
            elif capability is CapabilityId.CONCEPT_EXPLANATION:
                result = await self.studykit_learning.concept_explanation(
                    messages=messages, course_context=studykit_context
                )
                answer, usage = result.answer, add_usage(usage, result.usage)
            elif capability is CapabilityId.PRACTICE_SELECTION:
                practice_messages = messages
                if displayed_practice_ids:
                    practice_messages = [
                        *messages,
                        ChatMessage(
                            role="assistant",
                            content="已展示 practice IDs："
                            + "、".join(displayed_practice_ids),
                        ),
                    ]
                result = await self.studykit_learning.practice_selection(
                    messages=practice_messages, course_context=studykit_context
                )
                answer, usage = result.answer, add_usage(usage, result.usage)
                match = re.search(r"practice ID:\s*([\w.-]+)", answer)
                if match:
                    active_practice_id = match.group(1)
                    displayed_practice_ids.append(active_practice_id)
                if result.active_practice_id:
                    active_practice_id = result.active_practice_id
                practice_presentation_kind = result.presentation_kind
                practice_presentation_digest = result.presentation_digest
            elif capability is CapabilityId.PRACTICE_FEEDBACK:
                feedback_messages = messages
                if re.search(r"(?:下一层|更多|再给).{0,6}提示|next hint", latest, re.I):
                    hint_level = min(5, hint_level + 1)
                if active_practice_id and active_practice_id not in latest:
                    feedback_messages = [
                        *messages[:-1],
                        messages[-1].model_copy(
                            update={
                                "content": (
                                    f"practice ID: {active_practice_id}\n"
                                    f"hint level: {hint_level}\n{latest}"
                                )
                            }
                        ),
                    ]
                result = await self.studykit_learning.practice_feedback(
                    messages=feedback_messages,
                    course_context=studykit_context,
                    presentation_digest=practice_presentation_digest,
                    presentation_kind=practice_presentation_kind,
                )
                answer, usage = result.answer, add_usage(usage, result.usage)
            elif capability is CapabilityId.CODE_TUTORING:
                turn = build_turn_context(messages)
                previous_artifact = None
                if code_artifact_id and code_digest:
                    previous_artifact = CodeArtifact(
                        artifact_id=code_artifact_id,
                        language=turn.language,
                        content_sha256=code_digest,
                        line_count=len(turn.code.splitlines()),
                    )
                result = await self.code_tutor.tutor_code(
                    user_id=user_id,
                    conversation_id=None,
                    course_context=studykit_context,
                    code=turn.code,
                    language=turn.language,
                    error_text=turn.error_text,
                    question=turn.user_text,
                    profile=current_profile,
                    previous_artifact=previous_artifact,
                )
                answer = render_tutor_result(result)
                usage = add_usage(usage, result.usage)
                if result.artifact is not None:
                    code_artifact_id = result.artifact.artifact_id
                    code_digest = result.artifact.content_sha256
            else:
                answer = render_capability_help(capability)
            return TaskExecutionResult(
                task_id=task.task_id,
                capability_id=capability,
                status=TaskStatus.COMPLETED,
                answer=answer,
                usage=normalized_usage(usage),
            )

        runnable_tasks: list[PlannedTask] = []
        for task in plan.tasks:
            resolved = task.model_copy(deep=True)
            if studykit_context is not None:
                resolved.required_context = [
                    item
                    for item in resolved.required_context
                    if item not in {"course_id", "course_version", "unit_id", "course_context"}
                    or (item == "unit_id" and studykit_context.unit_id is None)
                ]
            runnable_tasks.append(resolved)
        executable_plan = plan.model_copy(update={"tasks": runnable_tasks})
        executor = TaskExecutor({capability: execute for capability in CapabilityId})
        results = await executor.execute(executable_plan)
        usage = normalized_usage(plan_outcome.usage)
        for result in results:
            usage = add_usage(usage, result.usage)
        answer = render_execution(results, executable_plan)
        notices = [f"画像更新：{item}" for item in observation_notices]
        if profile_error:
            notices.append("画像存储当前不可用；本轮仍可继续，但画像没有持久保存。")
        if notices:
            answer = f"{answer}\n\n---\n" + "\n".join(notices)
        next_context: str | None = None
        if self.context_signer is not None:
            next_context = self.context_signer.issue(
                plan=plan.model_dump(mode="json"),
                course=(
                    None
                    if studykit_context is None
                    else StudyKitCourseIdentity.from_context(studykit_context)
                ),
                active_practice_id=active_practice_id,
                displayed_practice_ids=displayed_practice_ids,
                hint_level=hint_level,
                practice_presentation_kind=practice_presentation_kind,
                practice_presentation_digest=practice_presentation_digest,
                code_artifact_id=code_artifact_id,
                code_digest=code_digest,
            )
        return AgentReply(
            answer=answer,
            usage=normalized_usage(usage),
            coursepilot_context=next_context,
        )

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
                    "你好，我是 CoursePilot。我可以导航课程、查询已审核 StudyKit、"
                    "讲解材料与练习，也可以建立学习画像或静态分析代码。"
                    "输入 /help 可以查看当前功能。你想学习哪个 CS 方向？每周大约能投入多少时间？"
                )
            return (
                "你好，我已经读取了你的学习画像。你可以继续选课、学习已审核 StudyKit、"
                "分析代码或查看画像；"
                "输入 /help 可以查看当前功能。"
            )
        if clarifying_question:
            return f"我可以帮助课程学习、整理学习画像或静态分析代码。{clarifying_question}"
        return "请说明你希望选课、学习已审核 StudyKit、整理画像，还是分析代码。"

    @staticmethod
    def _unavailable_answer(intent: Intent, clarification: str | None) -> str:
        capability = capability_for_intent(intent)
        if capability is not None:
            return render_capability_help(capability.capability_id)
        label = intent.value
        suffix = f"\n\n{clarification}" if clarification else ""
        return (
            f"我识别到你的意图是“{label}”，但该在线能力尚未接入。"
            "输入 /help 可以查看当前已上线能力；我不会在缺少检索依据时编造课程事实。"
            f"{suffix}"
        )
