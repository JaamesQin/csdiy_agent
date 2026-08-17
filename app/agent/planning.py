"""Bounded multi-intent planning from the complete chat history."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.contracts import CapabilityId, PlannedTask, TaskPlan
from app.agent.model_support import add_usage, normalized_usage
from app.generation.model import ModelError, StructuredModel
from app.protocol.schemas import ChatMessage


class TaskPlanOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: TaskPlan
    usage: dict[str, int] = Field(default_factory=dict)
    reason: str


class TaskPlanner:
    def __init__(self, model: StructuredModel | None = None) -> None:
        self.model = model

    async def plan(self, messages: list[ChatMessage]) -> TaskPlanOutcome:
        latest = next(message.content for message in reversed(messages) if message.role == "user")
        deterministic = self._management_plan(latest)
        if deterministic is not None:
            return TaskPlanOutcome(
                plan=deterministic, usage=normalized_usage(), reason="management_rule"
            )
        if self.model is None:
            return TaskPlanOutcome(
                plan=self._fallback_plan(latest),
                usage=normalized_usage(),
                reason="model_unavailable",
            )
        user_prompt = json.dumps(
            {
                "messages": [message.model_dump() for message in messages][-20:],
                "capabilities": [item.value for item in CapabilityId],
                "output_contract": {
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
                        }
                    ],
                    "course_mentions": [],
                    "missing_context": [],
                    "clarifying_questions": [],
                },
            },
            ensure_ascii=False,
        )
        usage = normalized_usage()
        for attempt in range(2):
            try:
                response = await self.model.generate_json(
                    system_prompt=(
                        "你是 CoursePilot 任务规划器。基于完整消息历史拆分最多 8 个任务。"
                        "任务只能使用给定 capability；课程名称只是候选，不得自行确立版本或讲次。"
                        "普通对话绝不能创建或运行 StudyKit authoring。依赖必须无环。"
                        "不得因请求后半段出现练习而丢弃前半段的解释任务。"
                        "只有用户明确陈述自身情况时 self_statement 才为 true。只输出 JSON object。"
                    ),
                    user_prompt=user_prompt,
                    thinking_enabled=False,
                    max_tokens=4096,
                    timeout_seconds=30,
                )
                usage = add_usage(usage, normalized_usage(response.usage))
                candidate = response.output.get("plan", response.output)
                plan = TaskPlan.model_validate(candidate)
                return TaskPlanOutcome(
                    plan=plan,
                    usage=usage,
                    reason=("model_planner" if attempt == 0 else "model_planner_retry"),
                )
            except (ModelError, ValidationError, ValueError):
                continue
        return TaskPlanOutcome(
            plan=self._fallback_plan(latest),
            usage=usage,
            reason="planner_failed",
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
                        capability_id=CapabilityId.GENERATION_STATUS,
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
        elif "```" in text:
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
