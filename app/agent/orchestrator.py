"""CoursePilot online orchestration, independent from HTTP/SSE rendering."""

from __future__ import annotations

import sqlite3
import re

from app.agent.context import TurnContext, build_turn_context
from app.agent.understanding import (
    ExtractedCode,
    language_assumption,
    validate_model_code,
)
from app.agent.contracts import (
    AgentReply,
    CapabilityId,
    ConversationAct,
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
from app.agent.events import AgentEvent, AgentEventSink, NullAgentEventSink
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
        event_sink: AgentEventSink | None = None,
    ) -> None:
        self.store = store
        self.router = router
        self.profiles = profiles
        self.code_tutor = code_tutor
        self.course_navigation = course_navigation
        self.studykit_learning = studykit_learning
        self.planner = planner
        self.context_signer = context_signer
        self.event_sink = event_sink or NullAgentEventSink()

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
            assumption = language_assumption(
                ExtractedCode(
                    content=turn.code,
                    language=turn.language,
                    language_inferred=turn.language_inferred,
                    source=turn.code_source,
                )
            )
            if assumption:
                answer = f"{assumption}\n\n{answer}"
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
        previous_context = (
            self.context_signer.verify(supplied_context)
            if self.context_signer is not None and supplied_context
            else None
        )
        continuity = (
            previous_context.model_dump(
                mode="json",
                exclude={"issued_at", "expires_at", "plan_digest"},
            )
            if previous_context is not None
            else {}
        )
        profile_summary: dict[str, object] = {}
        for fact in profile.facts:
            if fact.status is FactStatus.CONFIRMED:
                profile_summary.setdefault(fact.field_name, [])
                values = profile_summary[fact.field_name]
                if isinstance(values, list):
                    values.append(fact.value)
        plan_outcome = await self.planner.plan(  # type: ignore[union-attr]
            messages,
            continuity=continuity,
            profile_summary=profile_summary,
        )
        plan = plan_outcome.plan
        understanding = plan_outcome.understanding
        if (
            understanding is not None
            and understanding.conversation_act is ConversationAct.ONBOARDING
        ):
            self.event_sink.emit(
                AgentEvent(
                    kind="understanding",
                    reason=plan_outcome.reason,
                    task_count=0,
                )
            )
            return AgentReply(
                answer=(
                    "第一次使用可以任选一种方式开始：\n\n"
                    "1. 告诉我想学的方向，我帮你选课；\n"
                    "2. 直接贴代码，我做静态分析；\n"
                    "3. 指定课程和讲次，我查询已审核 StudyKit。\n\n"
                    "学习画像是可选的，不填写也可以直接提问。"
                ),
                usage=normalized_usage(plan_outcome.usage),
            )
        user_texts = [message.content for message in messages if message.role == "user"]
        displayed_catalog_ids = list(
            previous_context.displayed_catalog_ids if previous_context else []
        )
        selected_catalog_id = previous_context.selected_catalog_id if previous_context else None
        resolved_card = None
        if (
            understanding is not None
            and understanding.course is not None
            and understanding.course_mode != "recommendation"
        ):
            reference = understanding.course
            referenced_id: str | None = None
            if reference.ordinal is not None:
                index = reference.ordinal - 1
                if 0 <= index < len(displayed_catalog_ids):
                    referenced_id = displayed_catalog_ids[index]
            elif (
                understanding.course_mode == "selection"
                and displayed_catalog_ids
                and not reference.candidate_id
                and not reference.raw
            ):
                referenced_id = displayed_catalog_ids[0]
            resolved_card = self.course_navigation.resolve_card(
                referenced_id,
                reference.candidate_id,
                reference.raw,
            )
            if resolved_card is not None:
                selected_catalog_id = resolved_card.catalog_id
        if (
            resolved_card is None
            and selected_catalog_id
            and understanding is not None
            and understanding.unit is not None
        ):
            resolved_card = self.course_navigation.get_card(selected_catalog_id)

        studykit_context: CourseContext | None = None
        profile_course_context: CourseContext | None = None
        if resolved_card is not None and resolved_card.manifest_course_id and resolved_card.course_version:
            unit_id: str | None = None
            if understanding is not None and understanding.unit is not None:
                unit_ref = understanding.unit
                unit_id = unit_ref.candidate_id
                if unit_id is None and unit_ref.ordinal is not None:
                    ready_units = self.store.list_ready(
                        course_id=resolved_card.manifest_course_id,
                        course_version=resolved_card.course_version,
                    )
                    index = unit_ref.ordinal - 1
                    unit_id = (
                        ready_units[index].unit_id
                        if 0 <= index < len(ready_units)
                        else f"lecture-{unit_ref.ordinal:02d}"
                    )
            studykit_context = CourseContext(
                course_id=resolved_card.manifest_course_id,
                course_version=resolved_card.course_version,
                unit_id=unit_id,
                title=resolved_card.title,
            )
            profile_course_context = self.store.resolve_context(
                course_id=resolved_card.manifest_course_id,
                course_version=resolved_card.course_version,
                unit_id=unit_id,
            )
            if profile_course_context is None and unit_id is not None:
                profile_course_context = self.store.resolve_context(
                    course_id=resolved_card.manifest_course_id,
                    course_version=resolved_card.course_version,
                    unit_id=None,
                )
        if studykit_context is None and understanding is not None:
            candidates = [
                value
                for value in (
                    understanding.course.candidate_id if understanding.course else None,
                    understanding.course.raw if understanding.course else None,
                    understanding.unit.candidate_id if understanding.unit else None,
                    understanding.unit.raw if understanding.unit else None,
                )
                if value
            ]
            if candidates:
                studykit_context = self.store.match_context(candidates)
        if studykit_context is None and previous_context is not None and previous_context.course:
            inherited_unit = previous_context.course.unit_id
            if understanding is not None and understanding.unit is not None:
                inherited_unit = understanding.unit.candidate_id
                if inherited_unit is None and understanding.unit.ordinal is not None:
                    inherited_unit = f"lecture-{understanding.unit.ordinal:02d}"
            studykit_context = self.store.resolve_context(
                course_id=previous_context.course.course_id,
                course_version=previous_context.course.course_version,
                unit_id=inherited_unit,
            )
        if studykit_context is None:
            studykit_context = self.store.match_context([user_texts[-1]]) or self._profile_course_context(
                profile
            )
        if profile_course_context is None and studykit_context is not None:
            profile_course_context = self.store.resolve_context(
                course_id=studykit_context.course_id,
                course_version=studykit_context.course_version,
                unit_id=studykit_context.unit_id,
            )
        if (
            resolved_card is None
            and understanding is not None
            and understanding.course is not None
            and understanding.course.raw
            and understanding.unit is not None
            and any(
                task.capability_id
                in {
                    CapabilityId.STUDYKIT_LOOKUP,
                    CapabilityId.MATERIAL_QUESTION,
                    CapabilityId.CONCEPT_EXPLANATION,
                    CapabilityId.PRACTICE_SELECTION,
                }
                for task in plan.tasks
            )
        ):
            plan = plan.model_copy(
                update={
                    "tasks": [
                        PlannedTask(
                            task_id="resolve_course",
                            capability_id=CapabilityId.COURSE_NAVIGATION,
                            objective="先从已验证目录中明确课程身份",
                            evidence_quote=latest[:500],
                        )
                    ]
                }
            )
        if (
            any(task.capability_id is CapabilityId.COURSE_NAVIGATION for task in plan.tasks)
            and studykit_context is None
        ):
            learning_capabilities = {
                CapabilityId.STUDYKIT_LOOKUP,
                CapabilityId.MATERIAL_QUESTION,
                CapabilityId.CONCEPT_EXPLANATION,
                CapabilityId.PRACTICE_SELECTION,
                CapabilityId.PRACTICE_FEEDBACK,
            }
            retained = [
                task for task in plan.tasks if task.capability_id not in learning_capabilities
            ]
            retained_ids = {task.task_id for task in retained}
            plan = plan.model_copy(
                update={
                    "tasks": [
                        task.model_copy(
                            update={
                                "depends_on": [
                                    item for item in task.depends_on if item in retained_ids
                                ]
                            }
                        )
                        for task in retained
                    ]
                }
            )
        self.event_sink.emit(
            AgentEvent(
                kind="understanding",
                reason=plan_outcome.reason,
                task_count=len(plan.tasks),
            )
        )
        for task in plan.tasks:
            self.event_sink.emit(
                AgentEvent(
                    kind="plan_task",
                    capability_id=task.capability_id,
                    task_id=task.task_id,
                )
            )
        current_profile = profile
        observation_notices: list[str] = []
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
        last_capability = previous_context.last_capability if previous_context else None
        last_concept = (
            understanding.concept
            if understanding is not None and understanding.concept
            else (previous_context.last_concept if previous_context else None)
        )
        semantic_code = validate_model_code(
            messages,
            understanding.code_artifact if understanding is not None else None,
        )
        if not semantic_code.content:
            current_turn = build_turn_context([messages[-1]])
            semantic_code = ExtractedCode(
                content=current_turn.code,
                language=current_turn.language,
                language_inferred=current_turn.language_inferred,
                source=current_turn.code_source,
            )
        profile_observed = False

        async def execute(task: PlannedTask) -> TaskExecutionResult:
            nonlocal current_profile, profile_error, active_practice_id, hint_level
            nonlocal code_artifact_id, code_digest
            nonlocal profile_observed, practice_presentation_kind
            nonlocal practice_presentation_digest
            nonlocal selected_catalog_id
            usage = normalized_usage()
            if task.self_statement and not profile_observed:
                if understanding is not None and understanding.profile_operations:
                    observation = self.profiles.apply_operations(
                        user_id=user_id,
                        text=latest,
                        current=current_profile,
                        operations=understanding.profile_operations,
                        course_context=profile_course_context,
                    )
                else:
                    observation = await self.profiles.observe(
                        user_id=user_id,
                        text=latest,
                        current=current_profile,
                        course_context=profile_course_context,
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
            elif task.parameters.get("understanding_unavailable") is True:
                answer = (
                    "我没能从当前消息和会话上下文确认你指的具体对象，因此没有猜测或修改学习记录。"
                    "请直接补充你指的题目、课程、材料或代码；无需使用特定格式。"
                )
            elif capability is CapabilityId.PROFILE_ANALYSIS:
                action, _ = self.profiles.management_action(latest)
                if action is not ProfileAction.NONE:
                    answer, current_profile = self.profiles.handle_management(
                        user_id=user_id,
                        text=latest,
                        profile=current_profile,
                    )
                elif (
                    understanding is not None
                    and understanding.profile_operations
                    and not profile_observed
                ):
                    observation = self.profiles.apply_operations(
                        user_id=user_id,
                        text=latest,
                        current=current_profile,
                        operations=understanding.profile_operations,
                        course_context=studykit_context,
                    )
                    current_profile = observation.profile
                    profile_error = profile_error or observation.persistence_error
                    if observation.notice:
                        observation_notices.append(observation.notice)
                    profile_observed = True
                    answer = (
                        self.profiles.render(current_profile)
                        if observation.added or observation.notice
                        else ""
                    )
                else:
                    answer = self.profiles.render(current_profile)
            elif capability is CapabilityId.COURSE_NAVIGATION:
                navigation_text = latest
                if (
                    understanding is not None
                    and understanding.course is not None
                    and understanding.course_mode != "recommendation"
                ):
                    navigation_text = (
                        understanding.course.candidate_id
                        or understanding.course.raw
                        or latest
                    )
                navigation = self.course_navigation.navigate_result(
                    text=navigation_text,
                    profile=current_profile,
                    candidate_id=resolved_card.catalog_id if resolved_card is not None else None,
                )
                answer = navigation.answer
                if navigation.catalog_ids:
                    displayed_catalog_ids[:] = navigation.catalog_ids[:5]
                    if len(navigation.catalog_ids) == 1:
                        selected_catalog_id = navigation.catalog_ids[0]
            elif capability is CapabilityId.STUDYKIT_LOOKUP:
                result = await self.studykit_learning.lookup(
                    messages=messages, course_context=studykit_context
                )
                answer, usage = result.answer, add_usage(usage, result.usage)
            elif capability is CapabilityId.MATERIAL_QUESTION:
                if understanding is not None and understanding.response_mode == "unit_summary":
                    result = self.studykit_learning.unit_summary(
                        messages=messages, course_context=studykit_context
                    )
                else:
                    material_messages = self._messages_with_resolved_concept(
                        messages, understanding.concept if understanding else None
                    )
                    result = await self.studykit_learning.material_question(
                        messages=material_messages, course_context=studykit_context
                    )
                answer, usage = result.answer, add_usage(usage, result.usage)
            elif capability is CapabilityId.CONCEPT_EXPLANATION:
                concept_messages = self._messages_with_resolved_concept(
                    messages, last_concept
                )
                result = await self.studykit_learning.concept_explanation(
                    messages=concept_messages, course_context=studykit_context
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
                if active_practice_id is None and studykit_context is None:
                    answer = (
                        "当前会话没有可恢复的上一道练习。请发送 practice ID（或完整题面）"
                        "和你的当前答案；如果知道课程与讲次，也可以一并提供。"
                    )
                    return TaskExecutionResult(
                        task_id=task.task_id,
                        capability_id=capability,
                        status=TaskStatus.COMPLETED,
                        answer=answer,
                        usage=normalized_usage(usage),
                    )
                if (
                    understanding is not None
                    and understanding.conversation_act is ConversationAct.MORE_HINT
                ):
                    hint_level = min(5, hint_level + 1)
                    answer_index = understanding.answer_message_index
                    window = messages[-12:]
                    prior_answer = (
                        window[answer_index].content
                        if answer_index is not None
                        and answer_index < len(window)
                        and window[answer_index].role == "user"
                        else None
                    )
                    if prior_answer:
                        feedback_messages = [
                            *messages[:-1],
                            messages[-1].model_copy(
                                update={
                                    "content": (
                                        f"我的上一份答案是：{prior_answer}\n"
                                        f"本轮请求：{latest}"
                                    )
                                }
                            ),
                        ]
                if active_practice_id and active_practice_id not in latest:
                    feedback_messages = [
                        *feedback_messages[:-1],
                        feedback_messages[-1].model_copy(
                            update={
                                "content": (
                                    f"practice ID: {active_practice_id}\n"
                                    f"hint level: {hint_level}\n"
                                    f"{feedback_messages[-1].content}"
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
                turn = TurnContext(
                    user_text=latest,
                    code=semantic_code.content,
                    language=semantic_code.language,
                    language_inferred=semantic_code.language_inferred,
                    code_source=semantic_code.source,
                )
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
                assumption = language_assumption(
                    ExtractedCode(
                        content=turn.code,
                        language=turn.language,
                        language_inferred=turn.language_inferred,
                        source=turn.code_source,
                    )
                )
                if assumption:
                    answer = f"{assumption}\n\n{answer}"
                usage = add_usage(usage, result.usage)
                if result.artifact is not None:
                    code_artifact_id = result.artifact.artifact_id
                    code_digest = result.artifact.content_sha256
            elif capability is CapabilityId.GENERATION_STATUS:
                answer = (
                    "当前上下文不足以确定你指的是哪道题。请粘贴题面或 practice ID，"
                    "并附上你的当前答案；我不会凭空猜测上一道题。"
                )
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
        for result in results:
            self.event_sink.emit(
                AgentEvent(
                    kind="task_result",
                    capability_id=result.capability_id,
                    task_id=result.task_id,
                    status=result.status,
                )
            )
        usage = normalized_usage(plan_outcome.usage)
        for result in results:
            usage = add_usage(usage, result.usage)
        completed_capabilities = [
            result.capability_id.value
            for result in results
            if result.status is TaskStatus.COMPLETED
        ]
        if completed_capabilities:
            last_capability = completed_capabilities[-1]
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
                displayed_catalog_ids=displayed_catalog_ids,
                selected_catalog_id=selected_catalog_id,
                last_capability=last_capability,
                last_concept=last_concept,
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

    @staticmethod
    def _messages_with_resolved_concept(
        messages: list[ChatMessage], concept: str | None
    ) -> list[ChatMessage]:
        if not concept:
            return messages
        latest = messages[-1]
        if latest.role != "user" or concept.casefold() in latest.content.casefold():
            return messages
        return [
            *messages[:-1],
            latest.model_copy(
                update={"content": f"当前概念：{concept}\n用户本轮请求：{latest.content}"}
            ),
        ]

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
