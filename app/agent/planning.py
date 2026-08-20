"""Bounded multi-intent planning from the complete chat history."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.contracts import (
    CapabilityId,
    ModelTurnUnderstanding,
    PlannedTask,
    SemanticReference,
    TaskPlan,
)
from app.agent.capabilities import (
    available_capabilities,
    capability_by_id,
    match_unavailable_capability_request,
)
from app.agent.model_support import normalized_usage
from app.agent.understanding import extract_code, is_code_request, understand_user_texts
from app.generation.model import ModelError, StructuredModel
from app.protocol.schemas import ChatMessage


class TaskPlanOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: TaskPlan
    usage: dict[str, int] = Field(default_factory=dict)
    reason: str
    understanding: ModelTurnUnderstanding | None = None


class TaskPlanner:
    def __init__(
        self,
        model: StructuredModel | None = None,
        *,
        robust_input_enabled: bool = False,
    ) -> None:
        self.model = model
        self.robust_input_enabled = robust_input_enabled

    async def plan(
        self,
        messages: list[ChatMessage],
        *,
        continuity: dict[str, object] | None = None,
        profile_summary: dict[str, object] | None = None,
    ) -> TaskPlanOutcome:
        latest = next(message.content for message in reversed(messages) if message.role == "user")
        deterministic = self._management_plan(latest)
        if deterministic is not None:
            return TaskPlanOutcome(
                plan=deterministic, usage=normalized_usage(), reason="management_rule"
            )
        deterministic = self._practice_display_plan(latest)
        if deterministic is not None:
            return TaskPlanOutcome(
                plan=deterministic,
                usage=normalized_usage(),
                reason="practice_display_rule",
            )
        unavailable = match_unavailable_capability_request(latest)
        if unavailable is not None:
            return TaskPlanOutcome(
                plan=self._unavailable_capability_fallback_plan(
                    latest, unavailable.capability_id
                ),
                usage=normalized_usage(),
                reason="unavailable_capability_fallback",
            )
        if self.model is None:
            deterministic = (
                self._deterministic_plan(latest)
                if self.robust_input_enabled
                else None
            )
            return TaskPlanOutcome(
                plan=deterministic or self._safe_fallback_plan(latest),
                usage=normalized_usage(),
                reason=(
                    "model_unavailable_deterministic"
                    if deterministic is not None
                    else "model_unavailable"
                ),
            )
        indexed_messages = [
            {"index": index, **message.model_dump()}
            for index, message in enumerate(messages[-12:])
        ]
        user_prompt = json.dumps(
            {
                "messages": indexed_messages,
                "continuity": continuity or {},
                "confirmed_profile": profile_summary or {},
                "capabilities": [
                    item.capability_id.value for item in available_capabilities()
                ],
                "output_contract": {
                    "understanding": {
                        "conversation_act": "new_request | follow_up | selection | correction | submit_answer | more_hint | profile_management | onboarding",
                        "course": {
                            "raw": "learner wording or null",
                            "candidate_id": "best canonical catalog or StudyKit id or null",
                            "ordinal": "positive integer or null",
                            "from_recent_context": False,
                            "alternatives": [],
                        },
                        "unit": {
                            "raw": "unit wording or null",
                            "candidate_id": "lecture/note id or null",
                            "ordinal": "positive integer or null",
                            "from_recent_context": False,
                            "alternatives": [],
                        },
                        "practice": None,
                        "concept": "canonical concept or null",
                        "course_mode": "none | recommendation | lookup | selection",
                        "response_mode": "default | unit_summary",
                        "answer_message_index": "index of the current or previous learner answer, or null",
                        "code_artifact": {
                            "content": "verbatim learner code",
                            "language": "language id or null",
                            "source_message_index": "index from messages",
                            "replaces_previous": True,
                        },
                        "profile_operations": [
                            {
                                "action": "add | replace | delete | infer",
                                "field_name": "learning_directions | goals | background | weekly_minutes | preferred_explanation_style | active_course | active_unit",
                                "value": "value or null",
                                "evidence_quote": "exact current-turn quote or null",
                            }
                        ],
                        "ambiguities": [],
                    },
                    "plan": {
                        "user_goal": "string",
                        "tasks": [
                            {
                                "task_id": "stable local id",
                                "capability_id": "one allowed capability",
                                "objective": "string",
                                "depends_on": [],
                                "parameters": {},
                                "required_context": [],
                                "self_statement": False,
                                "evidence_quote": "exact substring from the current user message",
                            }
                        ],
                        "course_mentions": [],
                        "missing_context": [],
                        "clarifying_questions": [],
                    },
                },
            },
            ensure_ascii=False,
        )
        try:
            response = await self.model.generate_json(
                    system_prompt=(
                        "你是 CoursePilot 的统一对话理解器。结合消息、短期状态和已确认画像，"
                        "一次完成自然语言理解与有界任务规划。理解指代、纠正、口语简称、拼写错误、"
                        "省略格式的代码、普通练习答案和继续提示。不要要求用户使用系统暗号或 Markdown。"
                        "只为用户当前明确请求的目标创建任务，最多 4 个；不得因相关词语扩张无关能力。"
                        "现有专用能力能够处理时必须优先使用专用能力；只有当前目标无法归入任何专用"
                        "能力时才创建 general_assistance，且不能把它与其他能力同时用于同一计划。"
                        "只能创建输入 capabilities 中列出的已上线能力。用户请求学习复盘、"
                        "生成状态等未上线能力时创建 general_assistance；不得输出未上线 capability ID。"
                        "每个明确目标都必须有且只有一个任务；如果 profile_operations 非空，计划中必须"
                        "包含 profile_analysis，不能因为同时存在课程或代码请求而丢弃画像更新。"
                        "用户要求概括本讲、核心内容或重点时设置 response_mode=unit_summary，且只创建"
                        " material_question；不要为同一目标同时创建 studykit_lookup 和 material_question。"
                        "用户只说查看、打开或开始某门课某一讲而没有提出内容问题时，只创建"
                        " studykit_lookup；具体概念或材料问题才创建 concept_explanation 或"
                        " material_question。只询问或纠正到某门课程、但没有指定讲次、概念或材料问题时，"
                        "创建 course_navigation，不要展开全部 StudyKit 讲次。纠正表达中，被‘不是/不要/改掉’"
                        "否定的课程不得作为 course"
                        "候选。要求推荐多门候选时 course_mode=recommendation，course.candidate_id 必须为 null；"
                        "查询一门已点名课程用 lookup，按上一轮序号选课用 selection。"
                        " 候选。‘第一门/第二门’必须以 continuity.displayed_catalog_ids 的实际顺序设置"
                        " ordinal 和 candidate_id，不得按常识另选课程。"
                        "course/unit/candidate 只是候选，后端会验证。代码 content 必须逐字来自指定用户消息，"
                        "背景技能不是代码语言。明确画像陈述用 add/replace/delete，模型推断才用 infer。"
                        "‘想学 X/我会 X/每周可投入 X’都是用户明确陈述，必须 add 或 replace，不能标 infer。"
                        "‘不是 X，是 Y/改成 Y/先学 Y’这类带最终值的纠正必须对同一字段输出一个"
                        " replace(value=Y)，不能只 delete 旧值；只有用户纯粹要求忘记或删除且没有给"
                        "新值时才输出 delete。"
                        "画像字段只能逐字使用 output_contract 给出的字段名；不存在代码时 code_artifact=null，"
                        "不存在课程或讲次时对应 reference=null，不要输出带 null content 的占位对象。"
                        "仅表达学习方向属于画像，不等于请求课程推荐；只有明确要求推荐、查找或选择课程时"
                        "才创建 course_navigation。"
                        "required_context、missing_context 和 clarifying_questions 必须留空，由后端计算。"
                        "普通对话不能运行 StudyKit authoring。只输出符合契约的 JSON object。"
                    ),
                    user_prompt=user_prompt,
                    thinking_enabled=False,
                    max_tokens=4096,
                    timeout_seconds=30,
                )
            candidate = response.output.get("plan", response.output)
            candidate = self._normalize_model_plan(candidate)
            plan = TaskPlan.model_validate(candidate)
            if raw_understanding := response.output.get("understanding"):
                understanding = ModelTurnUnderstanding.model_validate(
                    self._normalize_understanding_candidate(raw_understanding)
                )
            else:
                understanding = None
            understanding = self._harmonize_understanding(plan, understanding)
            tasks = self._complete_semantic_tasks(plan.tasks, understanding)
            plan = plan.model_copy(
                update={
                    "tasks": self._prefer_specialized_tasks(
                        self._normalize_unavailable_capabilities(
                            self._deduplicate_tasks([
                                task.model_copy(update={"required_context": []})
                                for task in tasks
                            ]),
                            latest,
                        )
                    ),
                    "missing_context": [],
                    "clarifying_questions": [],
                }
            )
            return TaskPlanOutcome(
                plan=plan,
                usage=normalized_usage(response.usage),
                reason="model_understanding",
                understanding=understanding,
            )
        except (ModelError, ValidationError, ValueError, KeyError):
            pass
        return TaskPlanOutcome(
            plan=self._safe_fallback_plan(latest),
            usage=normalized_usage(),
            reason="understanding_failed",
        )

    @staticmethod
    def _complete_semantic_tasks(
        tasks: list[PlannedTask],
        understanding: ModelTurnUnderstanding | None,
    ) -> list[PlannedTask]:
        """Recover an explicit semantic operation omitted from the model's task list.

        This does not infer intent from vocabulary. It only makes the executable plan
        consistent with the model's already-structured understanding.
        """

        if understanding is None or not understanding.profile_operations:
            return tasks
        existing_profile = next(
            (
                task
                for task in tasks
                if task.capability_id is CapabilityId.PROFILE_ANALYSIS
            ),
            None,
        )
        if existing_profile is not None:
            return [
                existing_profile,
                *[task for task in tasks if task is not existing_profile],
            ]
        profile_task = PlannedTask(
            task_id="profile",
            capability_id=CapabilityId.PROFILE_ANALYSIS,
            objective="应用当前消息中明确识别的学习画像操作",
            evidence_quote=next(
                (
                    operation.evidence_quote
                    for operation in understanding.profile_operations
                    if operation.evidence_quote
                ),
                None,
            ),
        )
        return [profile_task, *tasks]

    @staticmethod
    def _harmonize_understanding(
        plan: TaskPlan,
        understanding: ModelTurnUnderstanding | None,
    ) -> ModelTurnUnderstanding | None:
        """Lift semantic references misplaced in task parameters into the contract."""

        if understanding is None or understanding.course_mode != "selection":
            return understanding
        reference = understanding.course
        if reference is not None and (
            reference.candidate_id is not None or reference.ordinal is not None
        ):
            return understanding
        navigation = next(
            (
                task
                for task in plan.tasks
                if task.capability_id is CapabilityId.COURSE_NAVIGATION
            ),
            None,
        )
        if navigation is None:
            return understanding
        candidate = navigation.parameters.get("candidate_id")
        ordinal = navigation.parameters.get("ordinal")
        if not isinstance(candidate, str):
            candidate = None
        if not isinstance(ordinal, int) or ordinal < 1:
            ordinal = None
        if candidate is None and ordinal is None:
            return understanding
        return understanding.model_copy(
            update={
                "course": SemanticReference(
                    raw=reference.raw if reference else None,
                    candidate_id=candidate,
                    ordinal=ordinal,
                    from_recent_context=True,
                )
            }
        )

    @staticmethod
    def _deduplicate_tasks(tasks: list[PlannedTask]) -> list[PlannedTask]:
        material = next(
            (task for task in tasks if task.capability_id is CapabilityId.MATERIAL_QUESTION),
            None,
        )
        if material is None:
            return tasks
        filtered: list[PlannedTask] = []
        removed: set[str] = set()
        for task in tasks:
            if (
                task.capability_id is CapabilityId.STUDYKIT_LOOKUP
                and task.evidence_quote
                and material.evidence_quote
                and task.evidence_quote == material.evidence_quote
            ):
                removed.add(task.task_id)
                continue
            filtered.append(task)
        if not removed:
            return tasks
        return [
            task.model_copy(
                update={
                    "depends_on": [item for item in task.depends_on if item not in removed]
                }
            )
            for task in filtered
        ]

    @staticmethod
    def _normalize_unavailable_capabilities(
        tasks: list[PlannedTask], latest: str
    ) -> list[PlannedTask]:
        """Fail closed when a model emits a capability not available online."""

        del latest
        return [
            task.model_copy(update={"capability_id": CapabilityId.GENERAL_ASSISTANCE})
            if capability_by_id(task.capability_id).availability == "unavailable"
            else task
            for task in tasks
        ]

    @staticmethod
    def _unavailable_capability_fallback_plan(
        text: str, capability_id: CapabilityId
    ) -> TaskPlan:
        return TaskPlan(
            user_goal=text[:2000] or "处理学习请求",
            tasks=[
                PlannedTask(
                    task_id="general_assistance",
                    capability_id=CapabilityId.GENERAL_ASSISTANCE,
                    objective="用已上线能力和一般知识回应当前请求",
                    parameters={
                        "requested_unavailable_capability": capability_id.value
                    },
                    evidence_quote=text[:500],
                )
            ],
        )

    @staticmethod
    def _prefer_specialized_tasks(tasks: list[PlannedTask]) -> list[PlannedTask]:
        specialized = [
            task
            for task in tasks
            if task.capability_id is not CapabilityId.GENERAL_ASSISTANCE
        ]
        if not specialized:
            return tasks[:1]
        removed = {
            task.task_id
            for task in tasks
            if task.capability_id is CapabilityId.GENERAL_ASSISTANCE
        }
        return [
            task.model_copy(
                update={
                    "depends_on": [
                        dependency
                        for dependency in task.depends_on
                        if dependency not in removed
                    ]
                }
            )
            for task in specialized
        ]

    @staticmethod
    def _normalize_model_plan(candidate: object) -> object:
        """Repair representation-only model drift without changing semantics."""

        if not isinstance(candidate, dict) or not isinstance(candidate.get("tasks"), list):
            return candidate
        normalized = dict(candidate)
        mentions = normalized.get("course_mentions")
        if isinstance(mentions, list):
            normalized["course_mentions"] = [
                str(item.get("candidate_id") or item.get("raw"))
                for item in mentions
                if isinstance(item, dict) and (item.get("candidate_id") or item.get("raw"))
            ] + [str(item) for item in mentions if isinstance(item, str)]
        id_map: dict[str, str] = {}
        tasks: list[object] = []
        for index, raw in enumerate(candidate["tasks"]):
            if not isinstance(raw, dict):
                tasks.append(raw)
                continue
            task = dict(raw)
            original = str(task.get("task_id", ""))
            repaired = original
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", repaired):
                repaired = f"task-{index + 1}"
            id_map[original] = repaired
            task["task_id"] = repaired
            tasks.append(task)
        for raw in tasks:
            if not isinstance(raw, dict) or not isinstance(raw.get("depends_on"), list):
                continue
            raw["depends_on"] = [id_map.get(str(item), str(item)) for item in raw["depends_on"]]
        normalized["tasks"] = tasks
        return normalized

    @staticmethod
    def _normalize_understanding_candidate(candidate: object) -> object:
        if not isinstance(candidate, dict):
            return candidate
        normalized = dict(candidate)
        if normalized.get("concept") and normalized.get("response_mode") == "unit_summary":
            # A concrete concept and a whole-unit summary are mutually exclusive
            # executable modes. Prefer the narrower, explicitly identified target.
            normalized["response_mode"] = "default"
        code = normalized.get("code_artifact")
        if isinstance(code, dict) and (
            not isinstance(code.get("content"), str)
            or not str(code.get("content")).strip()
            or not isinstance(code.get("source_message_index"), int)
        ):
            normalized["code_artifact"] = None

        field_aliases = {
            "technical_background": "background",
            "programming_languages": "background",
            "programming_basics": "background",
            "weekly_time": "weekly_minutes",
            "learning_goal": "goals",
            "learning_goals": "goals",
        }
        operations: list[dict[str, object]] = []
        raw_operations = normalized.get("profile_operations")
        if isinstance(raw_operations, list):
            for raw in raw_operations:
                if not isinstance(raw, dict):
                    continue
                operation = dict(raw)
                original_field = str(operation.get("field_name") or "")
                field = field_aliases.get(original_field, original_field)
                value = operation.get("value")
                if field == "goals" and isinstance(value, str) and re.search(
                    r"系统|人工智能|机器学习|深度学习|\bai\b|\bml\b|算法|安全|前端|后端|理论",
                    value,
                    re.I,
                ):
                    field = "learning_directions"
                if field == "weekly_minutes" and not isinstance(value, int):
                    continue
                operation["field_name"] = field
                operations.append(operation)
        normalized["profile_operations"] = operations
        return normalized

    @staticmethod
    def _safe_fallback_plan(text: str) -> TaskPlan:
        extracted = extract_code([text])
        if extracted.content or "```" in text:
            task = PlannedTask(
                task_id="code",
                capability_id=CapabilityId.CODE_TUTORING,
                objective="静态分析明确提供的代码",
                evidence_quote=text[:500],
            )
        elif re.search(r"studykit|学习包", text, re.I):
            task = PlannedTask(
                task_id="studykit",
                capability_id=CapabilityId.STUDYKIT_LOOKUP,
                objective="查询明确指定的 StudyKit",
                evidence_quote=text[:500],
            )
        else:
            task = PlannedTask(
                task_id="general_assistance",
                capability_id=CapabilityId.GENERAL_ASSISTANCE,
                objective="使用受约束的一般知识回答当前学习请求",
                evidence_quote=text[:500],
            )
        return TaskPlan(user_goal=text[:2000] or "处理请求", tasks=[task])

    @staticmethod
    def _deterministic_plan(text: str) -> TaskPlan | None:
        """Build a plan for strong learner signals before consulting a model."""

        understanding = understand_user_texts([text])
        lowered = understanding.normalized_text
        extracted = understanding.code
        feedback = bool(
            re.search(r"练习.*反馈|点评.*(?:答案|practice-)|批改|我的答案", lowered)
        )
        practice = bool(re.search(r"(?:给我?|选择|推荐|来).{0,80}(?:练习|题)|做道题", lowered))
        studykit = bool(re.search(r"studykit|学习包", lowered, re.I))
        material = bool(
            re.search(r"材料里|讲义里|第\s*[一二三四五六七八九十百千零\d]+\s*页|page\s*\d+", lowered, re.I)
        )
        course = bool(
            re.search(
                r"推荐.*课程|课程.*推荐|选课|学习路线|学什么课|有哪些课程|"
                r"课程列表|列出.{0,4}课程|(?:查看|了解|介绍).{0,35}[a-z]{2,}\s*[a-z]*\d",
                lowered,
                re.I,
            )
        )
        profile_statement = bool(
            re.search(
                r"我(?:想|准备|计划).{0,20}(?:学|学习)|"
                r"我每(?:周|星期).{0,20}(?:小时|分钟)|"
                r"我(?:有|会|熟悉|掌握|学过).{0,30}(?:基础|经验|python|c\+\+|java|git)|"
                r"学习方向(?:是|为|改)",
                lowered,
                re.I,
            )
        )
        code = understanding.code_requested or bool(extracted.content)
        concept = bool(re.search(r"解释|什么是|为什么|如何理解|区别", lowered))
        if studykit or material or practice or feedback:
            course = False

        tasks: list[PlannedTask] = []

        def add(
            task_id: str,
            capability: CapabilityId,
            objective: str,
            *,
            required: list[str] | None = None,
            self_statement: bool = False,
            depends_on: list[str] | None = None,
        ) -> None:
            if any(task.capability_id is capability for task in tasks):
                return
            tasks.append(
                PlannedTask(
                    task_id=task_id,
                    capability_id=capability,
                    objective=objective,
                    required_context=required or [],
                    self_statement=self_statement,
                    depends_on=depends_on or [],
                )
            )

        if profile_statement:
            add(
                "profile",
                CapabilityId.PROFILE_ANALYSIS,
                "记录用户明确陈述的学习画像",
                self_statement=True,
            )
        if course:
            add("course_navigation", CapabilityId.COURSE_NAVIGATION, "从受审核目录推荐或查询课程")
        if studykit:
            add("studykit", CapabilityId.STUDYKIT_LOOKUP, "查询已审核 StudyKit")
        elif material:
            add("material", CapabilityId.MATERIAL_QUESTION, "基于已审核材料回答问题")
        if feedback:
            add("practice_feedback", CapabilityId.PRACTICE_FEEDBACK, "评价当前练习答案")
        else:
            if concept and not material:
                add("explain", CapabilityId.CONCEPT_EXPLANATION, "解释用户指定的概念")
            if practice:
                dependencies = ["explain"] if any(task.task_id == "explain" for task in tasks) else []
                add(
                    "practice",
                    CapabilityId.PRACTICE_SELECTION,
                    "选择用户要求的练习",
                    depends_on=dependencies,
                )
            if code:
                add(
                    "code",
                    CapabilityId.CODE_TUTORING,
                    "静态分析用户提供的代码",
                    required=[] if extracted.content else ["user_code"],
                    self_statement=profile_statement,
                )

        if not tasks:
            return None
        missing = sorted({item for task in tasks for item in task.required_context})
        questions = ["请粘贴需要分析的代码；普通文本或 Markdown 形式都可以。"] if "user_code" in missing else []
        return TaskPlan(
            user_goal=text[:2000] or "处理学习请求",
            tasks=tasks,
            missing_context=missing,
            clarifying_questions=questions,
        )

    @staticmethod
    def _practice_display_plan(text: str) -> TaskPlan | None:
        practice_id = (
            r"(?:ex(?:ercise)?|practice|p)"
            r"(?:[\s._-]*[a-z]+)*[\s._-]*\d+"
        )
        has_display_verb = bool(
            re.search(r"(?:显示|查看|打开|重看|重新显示|show|open)", text, re.I)
        )
        has_explicit_id = bool(
            re.search(rf"(?<![a-z0-9]){practice_id}(?![a-z0-9])", text, re.I)
        )
        has_ordinal = bool(
            re.search(
                r"第\s*[零〇一二两三四五六七八九十百千\d]{1,8}\s*"
                r"(?:道|个)?\s*(?:习题|练习|题)",
                text,
                re.I,
            )
        )
        bare_id = bool(
            re.fullmatch(
                rf"\s*(?:practice\s*id\s*[:：]?\s*)?{practice_id}"
                r"\s*[。.!！?？]?\s*",
                text,
                re.I,
            )
        )
        asks_what = has_explicit_id and bool(
            re.fullmatch(
                rf"\s*(?:practice\s*id\s*[:：]?\s*)?{practice_id}\s*"
                r"(?:的\s*)?(?:是\s*)?(?:什么|哪道题|什么题|题目|内容)(?:是什么)?"
                r"\s*[。.!！?？]?\s*",
                text,
                re.I,
            )
        )
        if not (
            bare_id
            or asks_what
            or (has_display_verb and (has_explicit_id or has_ordinal))
        ):
            return None
        return TaskPlan(
            user_goal=text[:2000] or "显示指定练习",
            tasks=[
                PlannedTask(
                    task_id="practice",
                    capability_id=CapabilityId.PRACTICE_SELECTION,
                    objective="显示当前讲次中用户明确指定的练习",
                    evidence_quote=text[:500],
                )
            ],
        )

    @staticmethod
    def _management_plan(text: str) -> TaskPlan | None:
        lowered = text.casefold().strip()
        if lowered in {"/help", "help", "帮助", "功能"} or re.search(
            r"(?:查看|显示|删除|清空|忘记).{0,8}(?:画像|学习记录)", lowered
        ):
            return TaskPlan(
                user_goal=text[:2000] or "管理请求",
                tasks=[
                    PlannedTask(
                        task_id="manage_profile",
                        capability_id=CapabilityId.PROFILE_ANALYSIS,
                        objective=text[:1000] or "管理学习画像",
                    )
                ],
            )
        if re.search(r"admin_generate_studykit|后台生成|运行生成器|authoring job", lowered):
            return TaskPlan(
                user_goal="拒绝在线 authoring 请求",
                tasks=[
                    PlannedTask(
                        task_id="authoring_block",
                        capability_id=CapabilityId.GENERAL_ASSISTANCE,
                        objective="说明在线聊天不能触发 StudyKit authoring",
                        parameters={"blocked_authoring": True},
                    )
                ],
            )
        return None

    @staticmethod
    def _fallback_plan(text: str) -> TaskPlan:
        # This fallback is deliberately narrow. Ambiguous words such as “学过” or
        # “报错” are not enough to pre-empt a natural-language request.
        explains = bool(re.search(r"(?:解释|什么是|为什么|如何理解|区别)", text))
        requests_practice = bool(
            re.search(r"(?:给我|选择|推荐).{0,80}(?:练习|题)", text)
        )
        if explains and requests_practice:
            return TaskPlan(
                user_goal=text[:2000] or "解释并练习",
                tasks=[
                    PlannedTask(
                        task_id="explain",
                        capability_id=CapabilityId.CONCEPT_EXPLANATION,
                        objective="解释用户指定的概念",
                    ),
                    PlannedTask(
                        task_id="practice",
                        capability_id=CapabilityId.PRACTICE_SELECTION,
                        objective="选择用户要求的练习",
                        depends_on=["explain"],
                    ),
                ],
            )
        capability: CapabilityId | None = None
        required: list[str] = []
        question = ""
        self_statement = False
        if re.search(
            r"练习.*反馈|点评.*(?:答案|practice-)|批改|答案.*反馈", text, re.I
        ):
            capability = CapabilityId.PRACTICE_FEEDBACK
        elif is_code_request(text) or bool(extract_code([text]).content):
            capability = CapabilityId.CODE_TUTORING
        elif re.search(r"(?:给我|选择|推荐).{0,80}(?:练习|题)", text):
            capability = CapabilityId.PRACTICE_SELECTION
        elif re.search(r"studykit|学习包", text, re.I):
            capability = CapabilityId.STUDYKIT_LOOKUP
        elif re.search(r"材料里|讲义里|第\s*\d+\s*页|page\s*\d+", text, re.I):
            capability = CapabilityId.MATERIAL_QUESTION
        elif re.search(r"(?:推荐.*课程|选课|课程列表|学习路线)", text):
            capability = CapabilityId.COURSE_NAVIGATION
        elif re.search(
            r"我(?:想|准备|计划).{0,20}(?:学|学习)|"
            r"我每(?:周|星期).{0,20}(?:小时|分钟)|"
            r"我(?:有|会|熟悉|掌握).{0,20}(?:基础|经验)",
            text,
        ):
            capability = CapabilityId.PROFILE_ANALYSIS
            self_statement = True
        elif re.search(r"(?:解释|什么是|为什么|如何理解)", text):
            capability = CapabilityId.CONCEPT_EXPLANATION
        if capability is None:
            capability = CapabilityId.CONCEPT_EXPLANATION
            required = ["learning_task"]
            question = (
                "请说明你想了解的概念，或指定课程学习、练习、选课、"
                "学习画像或代码辅导任务。"
            )
        return TaskPlan(
            user_goal=text[:2000] or "需要澄清的请求",
            tasks=[
                PlannedTask(
                    task_id="task_1",
                    capability_id=capability,
                    objective=text[:1000] or "确认学习任务",
                    required_context=required,
                    self_statement=self_statement,
                )
            ],
            missing_context=required,
            clarifying_questions=[question] if question else [],
        )
