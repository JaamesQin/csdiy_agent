from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    CapabilityId,
    ModelTurnUnderstanding,
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

    with pytest.raises(ValidationError, match="capability may appear at most once"):
        TaskPlan(
            user_goal="重复能力",
            tasks=[
                PlannedTask(
                    task_id="first",
                    capability_id=CapabilityId.CONCEPT_EXPLANATION,
                    objective="解释 A",
                ),
                PlannedTask(
                    task_id="second",
                    capability_id=CapabilityId.CONCEPT_EXPLANATION,
                    objective="解释 B",
                ),
            ],
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

    assert outcome.plan.tasks[0].capability_id is CapabilityId.GENERATION_STATUS


async def test_planner_schema_failure_uses_safe_fallback_without_second_call() -> None:
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
    model = FakeStructuredModel(invalid)
    outcome = await TaskPlanner(model).plan(
        [ChatMessage(role="user", content="解释事务")]
    )

    assert outcome.reason == "understanding_failed"
    assert len(model.calls) == 1
    assert outcome.plan.tasks[0].parameters["understanding_unavailable"] is True


async def test_safe_fallback_does_not_guess_multi_intent() -> None:
    outcome = await TaskPlanner().plan(
        [ChatMessage(role="user", content="先解释可串行化，然后给我一道练习")]
    )

    assert [task.capability_id for task in outcome.plan.ordered_tasks()] == [
        CapabilityId.GENERATION_STATUS
    ]


async def test_model_understanding_routes_inline_code_and_binds_artifact() -> None:
    text = (
        "这段代码有什么问题：“include<stdio.h> "
        "int main(){int a,b; cin>>a>>b; cout<<a+b; return 0;}"
    )
    model = FakeStructuredModel(
        {
            "understanding": {
                "conversation_act": "new_request",
                "course": None,
                "unit": None,
                "practice": None,
                "concept": None,
                "response_mode": "default",
                "answer_message_index": None,
                "code_artifact": {
                    "content": "include<stdio.h> int main(){int a,b; cin>>a>>b; cout<<a+b; return 0;}",
                    "language": "cpp",
                    "source_message_index": 0,
                    "replaces_previous": True,
                },
                "profile_operations": [],
                "ambiguities": [],
            },
            "plan": {
                "user_goal": "分析代码",
                "tasks": [
                    {
                        "task_id": "code",
                        "capability_id": "code_tutoring",
                        "objective": "静态分析代码",
                        "depends_on": [],
                        "parameters": {},
                        "required_context": [],
                        "self_statement": False,
                        "evidence_quote": "这段代码有什么问题",
                    }
                ],
                "course_mentions": [],
                "missing_context": [],
                "clarifying_questions": [],
            },
        }
    )
    outcome = await TaskPlanner(model, robust_input_enabled=True).plan(
        [ChatMessage(role="user", content=text)]
    )

    assert outcome.reason == "model_understanding"
    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.CODE_TUTORING
    ]
    assert len(model.calls) == 1
    assert outcome.understanding is not None
    assert outcome.understanding.code_artifact is not None


def test_model_plan_representation_repair_does_not_change_task_semantics() -> None:
    candidate = {
        "user_goal": "查询课程",
        "tasks": [
            {
                "task_id": 1,
                "capability_id": "course_navigation",
                "objective": "查询课程",
                "depends_on": [],
            },
            {
                "task_id": "second task",
                "capability_id": "studykit_lookup",
                "objective": "查看材料",
                "depends_on": [1],
            },
        ],
    }

    repaired = TaskPlanner._normalize_model_plan(candidate)
    plan = TaskPlan.model_validate(repaired)

    assert [task.task_id for task in plan.tasks] == ["task-1", "task-2"]
    assert plan.tasks[1].depends_on == ["task-1"]


def test_understanding_representation_repair_drops_placeholders_and_maps_profile_fields() -> None:
    repaired = TaskPlanner._normalize_understanding_candidate(
        {
            "conversation_act": "profile_management",
            "code_artifact": {
                "content": None,
                "language": None,
                "source_message_index": None,
                "replaces_previous": True,
            },
            "profile_operations": [
                {
                    "action": "add",
                    "field_name": "technical_background",
                    "value": "Python",
                    "evidence_quote": "会 Python",
                },
                {
                    "action": "replace",
                    "field_name": "learning_goal",
                    "value": "系统",
                    "evidence_quote": "改学系统",
                },
                {
                    "action": "add",
                    "field_name": "weekly_time",
                    "value": "weekends",
                    "evidence_quote": "周末",
                },
            ],
        }
    )
    understanding = ModelTurnUnderstanding.model_validate(repaired)

    assert understanding.code_artifact is None
    assert [item.field_name for item in understanding.profile_operations] == [
        "background",
        "learning_directions",
    ]


def test_concrete_concept_cannot_be_a_whole_unit_summary() -> None:
    repaired = TaskPlanner._normalize_understanding_candidate(
        {
            "concept": "反向传播",
            "response_mode": "unit_summary",
            "profile_operations": [],
        }
    )

    assert repaired["response_mode"] == "default"


async def test_robust_planner_preserves_profile_course_and_code_intents() -> None:
    text = "我会 Python，推荐系统课程，再分析这段 C++ 代码：int main(){std::cout << 1; return 0;}"
    output = {
        "understanding": {
            "conversation_act": "new_request",
            "course": {"raw": "系统课程", "candidate_id": None, "ordinal": None, "from_recent_context": False, "alternatives": []},
            "unit": None,
            "practice": None,
            "concept": None,
            "response_mode": "default",
            "answer_message_index": None,
            "code_artifact": {"content": "int main(){std::cout << 1; return 0;}", "language": "cpp", "source_message_index": 0, "replaces_previous": True},
            "profile_operations": [{"action": "add", "field_name": "background", "value": "Python", "evidence_quote": "我会 Python"}],
            "ambiguities": [],
        },
        "plan": {
            "user_goal": "画像、选课和代码",
            "tasks": [
                {"task_id": "profile", "capability_id": "profile_analysis", "objective": "记录基础", "depends_on": [], "parameters": {}, "required_context": [], "self_statement": True, "evidence_quote": "我会 Python"},
                {"task_id": "course", "capability_id": "course_navigation", "objective": "推荐系统课程", "depends_on": [], "parameters": {}, "required_context": [], "self_statement": False, "evidence_quote": "推荐系统课程"},
                {"task_id": "code", "capability_id": "code_tutoring", "objective": "分析代码", "depends_on": [], "parameters": {}, "required_context": [], "self_statement": False, "evidence_quote": "分析这段 C++ 代码"},
            ],
            "course_mentions": [], "missing_context": [], "clarifying_questions": [],
        },
    }
    outcome = await TaskPlanner(FakeStructuredModel(output), robust_input_enabled=True).plan(
        [
            ChatMessage(
                role="user",
                content=text,
            )
        ]
    )

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.PROFILE_ANALYSIS,
        CapabilityId.COURSE_NAVIGATION,
        CapabilityId.CODE_TUTORING,
    ]


async def test_model_profile_operations_complete_an_omitted_profile_task() -> None:
    text = "我会 Python，推荐系统课程"
    output = {
        "understanding": {
            "conversation_act": "new_request",
            "course": {"raw": "系统课程", "candidate_id": None, "ordinal": None, "from_recent_context": False, "alternatives": []},
            "unit": None,
            "practice": None,
            "concept": None,
            "response_mode": "default",
            "answer_message_index": None,
            "code_artifact": None,
            "profile_operations": [{"action": "add", "field_name": "background", "value": "Python", "evidence_quote": "我会 Python"}],
            "ambiguities": [],
        },
        "plan": {
            "user_goal": "推荐系统课程",
            "tasks": [{"task_id": "course", "capability_id": "course_navigation", "objective": "推荐课程", "depends_on": [], "parameters": {}, "required_context": [], "self_statement": False, "evidence_quote": "推荐系统课程"}],
            "course_mentions": [], "missing_context": [], "clarifying_questions": [],
        },
    }

    outcome = await TaskPlanner(FakeStructuredModel(output), robust_input_enabled=True).plan(
        [ChatMessage(role="user", content=text)]
    )

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.PROFILE_ANALYSIS,
        CapabilityId.COURSE_NAVIGATION,
    ]


async def test_robust_planner_does_not_add_navigation_to_specific_studykit_query() -> None:
    outcome = await TaskPlanner(robust_input_enabled=True).plan(
        [ChatMessage(role="user", content="查看 MIT 6.7960 第二讲的 StudyKit")]
    )

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.STUDYKIT_LOOKUP
    ]
