from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    CapabilityId,
    PlannedTask,
    TaskExecutionResult,
    TaskPlan,
    TaskStatus,
)
from app.agent.executor import TaskExecutor
from app.agent.planning import TaskPlanner
from app.protocol.schemas import ChatMessage
from tests.agent.helpers import FakeStructuredModel


def test_task_plan_rejects_cycles_and_unknown_capabilities() -> None:
    with pytest.raises(ValidationError, match="acyclic"):
        TaskPlan(
            user_goal="循环",
            tasks=[
                PlannedTask(
                    task_id="a",
                    capability_id=CapabilityId.CODE_TUTORING,
                    objective="a",
                    depends_on=["b"],
                ),
                PlannedTask(
                    task_id="b",
                    capability_id=CapabilityId.CONCEPT_EXPLANATION,
                    objective="b",
                    depends_on=["a"],
                ),
            ],
        )

    with pytest.raises(ValidationError):
        PlannedTask(
            task_id="bad",
            capability_id="not_a_capability",
            objective="bad",
        )


async def test_executor_preserves_independent_success_and_blocks_dependents() -> None:
    async def handler(task: PlannedTask) -> TaskExecutionResult:
        if task.task_id == "failed":
            raise RuntimeError("private detail")
        return TaskExecutionResult(
            task_id=task.task_id,
            capability_id=task.capability_id,
            status=TaskStatus.COMPLETED,
            answer=task.objective,
        )

    plan = TaskPlan(
        user_goal="多个任务",
        tasks=[
            PlannedTask(
                task_id="failed",
                capability_id=CapabilityId.CODE_TUTORING,
                objective="失败",
            ),
            PlannedTask(
                task_id="dependent",
                capability_id=CapabilityId.CONCEPT_EXPLANATION,
                objective="依赖",
                depends_on=["failed"],
            ),
            PlannedTask(
                task_id="independent",
                capability_id=CapabilityId.COURSE_NAVIGATION,
                objective="成功",
            ),
        ],
    )
    executor = TaskExecutor({item: handler for item in CapabilityId})

    results = await executor.execute(plan)

    by_id = {result.task_id: result for result in results}
    assert by_id["failed"].status is TaskStatus.FAILED
    assert by_id["dependent"].status is TaskStatus.BLOCKED
    assert by_id["independent"].status is TaskStatus.COMPLETED
    assert by_id["independent"].answer == "成功"


async def test_model_planner_receives_full_history_and_supports_multiple_intents() -> None:
    model = FakeStructuredModel(
        {
            "user_goal": "解释并给练习",
            "tasks": [
                {
                    "task_id": "explain",
                    "capability_id": "concept_explanation",
                    "objective": "解释事务",
                    "depends_on": [],
                    "parameters": {},
                    "required_context": [],
                    "self_statement": False,
                },
                {
                    "task_id": "practice",
                    "capability_id": "practice_selection",
                    "objective": "选择练习",
                    "depends_on": ["explain"],
                    "parameters": {"difficulty": "introductory"},
                    "required_context": [],
                    "self_statement": False,
                },
            ],
            "course_mentions": ["CS186"],
            "missing_context": [],
            "clarifying_questions": [],
        }
    )
    planner = TaskPlanner(model)

    outcome = await planner.plan(
        [
            ChatMessage(role="user", content="我在学 CS186"),
            ChatMessage(role="assistant", content="你想做什么？"),
            ChatMessage(role="user", content="解释事务，然后给一道入门练习"),
        ]
    )

    assert [task.task_id for task in outcome.plan.ordered_tasks()] == [
        "explain",
        "practice",
    ]
    prompt = model.calls[0]["user_prompt"]
    assert "我在学 CS186" in prompt
    assert "解释事务，然后给一道入门练习" in prompt


async def test_fallback_does_not_route_broad_error_word_to_code() -> None:
    outcome = await TaskPlanner().plan(
        [ChatMessage(role="user", content="我学过这个概念，但理解可能报错了")]
    )

    assert outcome.plan.tasks[0].capability_id is CapabilityId.CONCEPT_EXPLANATION


async def test_planner_retries_schema_failure_and_accumulates_usage() -> None:
    invalid = {
        "user_goal": "invalid",
        "tasks": [
            {
                "task_id": "loop",
                "capability_id": "concept_explanation",
                "objective": "invalid",
                "depends_on": ["loop"],
                "parameters": {},
                "required_context": [],
                "self_statement": False,
            }
        ],
        "course_mentions": [],
        "missing_context": [],
        "clarifying_questions": [],
    }
    valid = {
        "user_goal": "explain",
        "tasks": [
            {
                "task_id": "explain",
                "capability_id": "concept_explanation",
                "objective": "explain",
                "depends_on": [],
                "parameters": {},
                "required_context": [],
                "self_statement": False,
            }
        ],
        "course_mentions": [],
        "missing_context": [],
        "clarifying_questions": [],
    }
    outcome = await TaskPlanner(FakeStructuredModel(invalid, valid)).plan(
        [ChatMessage(role="user", content="解释事务")]
    )

    assert outcome.reason == "model_planner_retry"
    assert outcome.usage["total_tokens"] == 30


async def test_fallback_preserves_explicit_explanation_and_practice() -> None:
    outcome = await TaskPlanner().plan(
        [ChatMessage(role="user", content="先解释可串行化，然后给我一道练习")]
    )

    assert [task.capability_id for task in outcome.plan.ordered_tasks()] == [
        CapabilityId.CONCEPT_EXPLANATION,
        CapabilityId.PRACTICE_SELECTION,
    ]
