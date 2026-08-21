from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    CapabilityId,
    CodeTutorMode,
    ModelTurnUnderstanding,
    PlannedTask,
    SemanticCodeRequest,
    TaskExecutionResult,
    TaskPlan,
    TaskStatus,
)
from app.agent.executor import TaskExecutor
from app.agent.planning import TaskPlanner
from app.protocol.schemas import ChatMessage
from tests.agent.helpers import FakeStructuredModel


async def test_explicit_practice_display_bypasses_model_planning() -> None:
    model = FakeStructuredModel()
    planner = TaskPlanner(model=model, robust_input_enabled=True)

    outcome = await planner.plan(
        [ChatMessage(role="user", content="显示ex1")],
        continuity={
            "course": {
                "course_id": "mit-6.7960-fall-2024",
                "course_version": "fall-2024",
                "unit_id": "lecture-02",
            }
        },
    )

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.PRACTICE_SELECTION
    ]
    assert outcome.reason == "practice_display_rule"
    assert model.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "显示第七道习题",
        "ex-7",
        "practice ID: ex-7",
        "ex7是什么",
        "ex-7 的题目是什么？",
        "practice 7 内容",
    ],
)
async def test_contextual_practice_references_bypass_model_planning(text: str) -> None:
    model = FakeStructuredModel()
    planner = TaskPlanner(model=model, robust_input_enabled=True)

    outcome = await planner.plan([ChatMessage(role="user", content=text)])

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.PRACTICE_SELECTION
    ]
    assert outcome.reason == "practice_display_rule"
    assert model.calls == []


def test_practice_answer_is_not_mistaken_for_bare_display_request() -> None:
    assert TaskPlanner._practice_display_plan("ex-7 我的答案是链式法则") is None


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

    assert outcome.plan.tasks[0].capability_id is CapabilityId.GENERAL_ASSISTANCE


async def test_planner_schema_failure_plans_general_fallback_without_second_planner_call() -> None:
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
    assert outcome.plan.tasks[0].capability_id is CapabilityId.GENERAL_ASSISTANCE


async def test_safe_fallback_does_not_guess_multi_intent() -> None:
    outcome = await TaskPlanner().plan(
        [ChatMessage(role="user", content="先解释可串行化，然后给我一道练习")]
    )

    assert [task.capability_id for task in outcome.plan.ordered_tasks()] == [
        CapabilityId.GENERAL_ASSISTANCE
    ]


async def test_explicit_generation_status_becomes_general_without_model_routing() -> None:
    model = FakeStructuredModel(
        {
            "user_goal": "查询生成状态",
            "tasks": [
                {
                    "task_id": "status",
                    "capability_id": "generation_status",
                    "objective": "查询后台生成状态",
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
    )

    outcome = await TaskPlanner(model).plan(
        [ChatMessage(role="user", content="后台 StudyKit 生成状态怎么样？")]
    )

    assert outcome.reason == "unavailable_capability_fallback"
    assert outcome.plan.tasks[0].capability_id is CapabilityId.GENERAL_ASSISTANCE
    assert len(model.calls) == 0


async def test_model_emitted_unavailable_capability_is_normalized_to_general() -> None:
    model = FakeStructuredModel(
        {
            "user_goal": "做阶段性回顾",
            "tasks": [
                {
                    "task_id": "review",
                    "capability_id": "learning_review",
                    "objective": "做阶段性回顾",
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
    )

    outcome = await TaskPlanner(model).plan(
        [ChatMessage(role="user", content="帮我回顾一下这阶段的学习。")]
    )

    assert outcome.plan.tasks[0].capability_id is CapabilityId.GENERAL_ASSISTANCE


async def test_specialized_task_wins_over_model_general_task() -> None:
    model = FakeStructuredModel(
        {
            "user_goal": "解释事务",
            "tasks": [
                {
                    "task_id": "general",
                    "capability_id": "general_assistance",
                    "objective": "通用回答",
                    "depends_on": [],
                    "parameters": {},
                    "required_context": [],
                    "self_statement": False,
                },
                {
                    "task_id": "explain",
                    "capability_id": "concept_explanation",
                    "objective": "解释事务",
                    "depends_on": ["general"],
                    "parameters": {},
                    "required_context": [],
                    "self_statement": False,
                },
            ],
            "course_mentions": [],
            "missing_context": [],
            "clarifying_questions": [],
        }
    )

    outcome = await TaskPlanner(model).plan(
        [ChatMessage(role="user", content="解释事务")]
    )

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.CONCEPT_EXPLANATION
    ]
    assert outcome.plan.tasks[0].depends_on == []


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


async def test_deterministic_planner_routes_generation_without_user_code() -> None:
    outcome = await TaskPlanner(robust_input_enabled=True).plan(
        [ChatMessage(role="user", content="给我一段完整的 cpp 示例代码")]
    )

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.CODE_TUTORING
    ]
    assert outcome.plan.missing_context == []


async def test_semantic_code_request_recovers_omitted_specialized_task() -> None:
    model = FakeStructuredModel(
        {
            "understanding": {
                "conversation_act": "new_request",
                "course": None,
                "unit": None,
                "practice": None,
                "concept": None,
                "course_mode": "none",
                "response_mode": "default",
                "answer_message_index": None,
                "code_artifact": None,
                "code_request": {
                    "mode": "generate_example",
                    "target_language": "cpp",
                    "language_inferred": False,
                },
                "profile_operations": [],
                "ambiguities": [],
            },
            "plan": {
                "user_goal": "生成 C++ 示例",
                "tasks": [
                    {
                        "task_id": "general",
                        "capability_id": "general_assistance",
                        "objective": "回答请求",
                        "depends_on": [],
                        "parameters": {},
                        "required_context": [],
                        "self_statement": False,
                        "evidence_quote": "给我一段完整的 cpp 示例代码",
                    }
                ],
                "course_mentions": [],
                "missing_context": [],
                "clarifying_questions": [],
            },
        }
    )

    outcome = await TaskPlanner(model, robust_input_enabled=True).plan(
        [ChatMessage(role="user", content="给我一段完整的 cpp 示例代码")]
    )

    assert [task.capability_id for task in outcome.plan.tasks] == [
        CapabilityId.CODE_TUTORING
    ]
    assert outcome.understanding is not None
    assert outcome.understanding.code_request is not None


def test_semantic_task_recovery_stays_within_task_plan_bound() -> None:
    tasks = [
        PlannedTask(
            task_id=f"task-{index}",
            capability_id=capability,
            objective="处理请求",
        )
        for index, capability in enumerate(
            [
                CapabilityId.COURSE_NAVIGATION,
                CapabilityId.MATERIAL_QUESTION,
                CapabilityId.CONCEPT_EXPLANATION,
                CapabilityId.GENERAL_ASSISTANCE,
            ],
            start=1,
        )
    ]
    understanding = ModelTurnUnderstanding(
        code_request=SemanticCodeRequest(
            mode=CodeTutorMode.GENERATE_EXAMPLE,
            target_language="cpp",
        )
    )

    recovered = TaskPlanner._complete_semantic_tasks(
        tasks,
        understanding,
        "给我一段完整的 cpp 示例代码",
    )

    assert len(recovered) == 4
    assert any(
        task.capability_id is CapabilityId.CODE_TUTORING for task in recovered
    )


def test_task_recovery_does_not_turn_practice_answer_code_into_code_tutoring() -> None:
    practice = PlannedTask(
        task_id="feedback",
        capability_id=CapabilityId.PRACTICE_FEEDBACK,
        objective="评价练习答案",
    )

    recovered = TaskPlanner._complete_semantic_tasks(
        [practice],
        None,
        "我的答案是：```python\nprint('attempt')\n```",
    )

    assert [task.capability_id for task in recovered] == [
        CapabilityId.PRACTICE_FEEDBACK
    ]


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
