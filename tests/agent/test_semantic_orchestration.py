from __future__ import annotations

import hashlib

import pytest

from app.agent.context_token import ContextTokenSigner
from app.agent.session_state import SQLiteSessionStateStore
from app.agent.orchestrator import CoursePilotAgent
from app.agent.planning import TaskPlanner
from app.agent.router import IntentRouter
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.code_tutor.service import CodeTutorService
from app.course_navigation.service import CourseNavigationService
from app.learning.service import StudyKitLookupService
from app.general_assistance.service import GeneralAssistanceService
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService
from app.protocol.schemas import ChatMessage
from app.storage.database import SQLiteDatabase
from tests.agent.helpers import FakeStructuredModel


def _output(
    *,
    capability: str,
    evidence: str,
    conversation_act: str = "new_request",
    course: dict[str, object] | None = None,
    unit: dict[str, object] | None = None,
    concept: str | None = None,
    code: dict[str, object] | None = None,
    profile_operations: list[dict[str, object]] | None = None,
    course_mode: str = "none",
    response_mode: str = "default",
    answer_message_index: int | None = None,
    self_statement: bool = False,
) -> dict[str, object]:
    return {
        "understanding": {
            "conversation_act": conversation_act,
            "course": course,
            "unit": unit,
            "practice": None,
            "concept": concept,
            "course_mode": course_mode,
            "response_mode": response_mode,
            "answer_message_index": answer_message_index,
            "code_artifact": code,
            "profile_operations": profile_operations or [],
            "ambiguities": [],
        },
        "plan": {
            "user_goal": evidence,
            "tasks": [
                {
                    "task_id": "task",
                    "capability_id": capability,
                    "objective": evidence,
                    "depends_on": [],
                    "parameters": {},
                    "required_context": [],
                    "self_statement": self_statement,
                    "evidence_quote": evidence,
                }
            ],
            "course_mentions": [],
            "missing_context": [],
            "clarifying_questions": [],
        },
    }


def _reference(
    raw: str | None = None,
    candidate_id: str | None = None,
    *,
    ordinal: int | None = None,
    from_recent_context: bool = False,
) -> dict[str, object]:
    return {
        "raw": raw,
        "candidate_id": candidate_id,
        "ordinal": ordinal,
        "from_recent_context": from_recent_context,
        "alternatives": [],
    }


def _agent(tmp_path, model: FakeStructuredModel) -> CoursePilotAgent:
    store = ReviewedFileStudyKitStore()
    catalog = ReviewedCourseCatalogStore(store)
    database = SQLiteDatabase(tmp_path / "profiles.sqlite3")
    return CoursePilotAgent(
        store=store,
        router=IntentRouter(store),
        profiles=ProfileService(SQLiteProfileRepository(database)),
        code_tutor=CodeTutorService(store),
        course_navigation=CourseNavigationService(catalog),
        studykit_learning=StudyKitLookupService(
            store,
            catalog=catalog,
            practice_rewrite_enabled=False,
        ),
        general_assistance=GeneralAssistanceService(model=model),
        planner=TaskPlanner(model=model, robust_input_enabled=True),
        context_signer=ContextTokenSigner(
            hashlib.sha256(b"semantic-orchestration-tests").digest()
        ),
        session_state_store=SQLiteSessionStateStore(
            database,
            key_secret=hashlib.sha256(b"semantic-session-state-tests").digest(),
        ),
    )


async def _turn(
    agent: CoursePilotAgent,
    messages: list[ChatMessage],
    text: str,
    context: str | None,
    *,
    user_id: str = "legacy:test-user",
) -> tuple[str, str | None]:
    messages.append(ChatMessage(role="user", content=text))
    reply = await agent.handle(
        messages=messages,
        user_id=user_id,
        coursepilot_context=context,
    )
    messages.append(ChatMessage(role="assistant", content=reply.answer))
    return reply.answer, reply.coursepilot_context


async def _session_turn(
    agent: CoursePilotAgent,
    messages: list[ChatMessage],
    text: str,
    session_id: str,
) -> str:
    messages.append(ChatMessage(role="user", content=text))
    reply = await agent.handle(
        messages=messages,
        user_id="legacy:test-user",
        session_id=session_id,
        continuity_namespace="legacy:test-user",
    )
    assert reply.coursepilot_context is None
    messages.append(ChatMessage(role="assistant", content=reply.answer))
    return reply.answer


async def test_new_model_artifact_replaces_old_code_instead_of_merging(tmp_path) -> None:
    first_text = "帮我看 C++：int main(){std::cout << 1; return 0;}"
    second_text = "换一个，这次是 Python：def add(a,b) return a+b"
    model = FakeStructuredModel(
        _output(
            capability="code_tutoring",
            evidence="帮我看 C++",
            code={
                "content": "int main(){std::cout << 1; return 0;}",
                "language": "cpp",
                "source_message_index": 0,
                "replaces_previous": True,
            },
        ),
        _output(
            capability="code_tutoring",
            evidence="换一个，这次是 Python",
            conversation_act="correction",
            code={
                "content": "def add(a,b) return a+b",
                "language": "python",
                "source_message_index": 2,
                "replaces_previous": True,
            },
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(agent, messages, first_text, None)
    second, _ = await _turn(agent, messages, second_text, context)

    assert "ran_code=false" in second
    assert "C++ 和 Python" not in second
    assert "std::cout" not in second


async def test_course_ordinal_uses_recent_displayed_catalog_ids(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="course_navigation",
            evidence="推荐系统课程",
            course=_reference(raw="系统课程"),
        ),
        _output(
            capability="course_navigation",
            evidence="我选第一门",
            conversation_act="follow_up",
            # The server-side signed display order is authoritative even when
            # this advisory model flag is wrong.
            course=_reference(ordinal=1, from_recent_context=False),
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    first, context = await _turn(agent, messages, "推荐系统课程", None)
    second, next_context = await _turn(agent, messages, "我选第一门", context)

    assert "2. **" in first
    assert "1. **" in second
    assert "2. **" not in second
    assert "当前可用 StudyKit" not in second
    assert next_context is not None


async def test_recommendation_mode_does_not_collapse_to_model_candidate(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="course_navigation",
            evidence="推荐系统课程",
            course=_reference(raw="系统课程", candidate_id="ucb-cs168-spring-2026"),
            course_mode="recommendation",
        )
    )
    agent = _agent(tmp_path, model)

    answer, context = await _turn(agent, [], "推荐系统课程", None)

    assert "1. **" in answer
    assert "2. **" in answer
    assert context is not None


async def test_unresolved_direction_and_unit_routes_to_catalog_first(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="我想从操作系统第一讲开始",
            course=_reference(raw="操作系统"),
            unit=_reference(raw="第一讲", ordinal=1),
            course_mode="lookup",
        )
    )
    agent = _agent(tmp_path, model)

    answer, _ = await _turn(agent, [], "我想从操作系统第一讲开始", None)

    assert any(
        marker in answer
        for marker in ("课程推荐", "匹配到的课程", "方向相关候选")
    )
    assert "可继续缩小范围的课程" not in answer


async def test_studykit_lookup_context_supports_compact_practice_followup(
    tmp_path,
) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(
                raw="MIT 6.7960",
                candidate_id="mit-6.7960-fall-2024",
            ),
            unit=_reference(raw="第 2 讲", candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        )
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    first, context = await _turn(
        agent,
        messages,
        "查看 MIT 6.7960 第 2 讲的 StudyKit",
        None,
    )
    second, next_context = await _turn(
        agent,
        messages,
        "显示practiceconcept01",
        context,
    )

    assert "Lecture 2" in first
    assert context is not None
    assert "practice-concept-01" in second
    assert "请先指定课程、版本和讲次" not in second
    assert "可继续缩小范围的课程" not in second
    assert next_context is not None
    assert len(model.calls) == 1


async def test_studykit_lookup_context_supports_ordinal_and_ex_alias_followups(
    tmp_path,
) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(
                raw="MIT 6.7960",
                candidate_id="mit-6.7960-fall-2024",
            ),
            unit=_reference(raw="第 2 讲", candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        )
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    first, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    ordinal, context = await _turn(agent, messages, "显示第七道习题", context)
    alias, _ = await _turn(agent, messages, "ex-7", context)

    assert "Lecture 2" in first
    assert "practice-differentiable-programming-01" in ordinal
    assert "已在当前对话中展示完毕" not in ordinal
    assert "practice-differentiable-programming-01" in alias
    assert "可继续缩小范围的课程" not in alias
    assert len(model.calls) == 1


async def test_studykit_lookup_context_supports_natural_ex_question(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(
                raw="MIT 6.7960",
                candidate_id="mit-6.7960-fall-2024",
            ),
            unit=_reference(raw="第 2 讲", candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        )
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    answer, _ = await _turn(agent, messages, "ex7是什么", context)

    assert "practice-differentiable-programming-01" in answer
    assert not answer.startswith("## Lecture 2")
    assert len(model.calls) == 1


@pytest.mark.parametrize(
    ("capability", "query", "concept", "expected"),
    [
        ("studykit_lookup", "重新查看当前 StudyKit", None, "## Lecture 2"),
        ("material_question", "本讲如何解释梯度下降？", None, "第 8 页"),
        ("concept_explanation", "解释反向传播", "反向传播", "**定义**"),
        ("practice_selection", "给我一道习题", None, "practice-concept-01"),
    ],
)
async def test_learning_followup_cannot_downgrade_verified_unit(
    tmp_path, capability: str, query: str, concept: str | None, expected: str
) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(
                raw="MIT 6.7960", candidate_id="mit-6.7960-fall-2024"
            ),
            unit=_reference(raw="第 2 讲", candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        ),
        _output(
            capability=capability,
            evidence=query,
            conversation_act="follow_up",
            course=_reference(
                candidate_id="mit-6.7960-fall-2024", from_recent_context=True
            ),
            unit=_reference(from_recent_context=True),
            concept=concept,
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    answer, next_context = await _turn(agent, messages, query, context)

    assert expected in answer
    assert "请明确选择一个讲次" not in answer
    verified = agent.context_signer.verify(next_context)  # type: ignore[arg-type, union-attr]
    assert verified is not None
    assert verified.course is not None
    assert verified.course.unit_id == "lecture-02"


async def test_explicit_unit_listing_can_drop_active_unit(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(
                raw="MIT 6.7960", candidate_id="mit-6.7960-fall-2024"
            ),
            unit=_reference(raw="第 2 讲", candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        ),
        _output(
            capability="studykit_lookup",
            evidence="列出 MIT 6.7960 的所有讲次",
            course=_reference(
                raw="MIT 6.7960", candidate_id="mit-6.7960-fall-2024"
            ),
            conversation_act="follow_up",
            course_mode="lookup",
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    answer, next_context = await _turn(
        agent, messages, "列出 MIT 6.7960 的所有讲次", context
    )

    assert "当前可在线读取的讲次" in answer
    verified = agent.context_signer.verify(next_context)  # type: ignore[arg-type, union-attr]
    assert verified is not None
    assert verified.course is not None
    assert verified.course.unit_id is None


async def test_explicit_unit_replaces_active_unit(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(candidate_id="mit-6.7960-fall-2024"),
            unit=_reference(candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        ),
        _output(
            capability="studykit_lookup",
            evidence="改看第八讲",
            conversation_act="correction",
            course=_reference(
                candidate_id="mit-6.7960-fall-2024", from_recent_context=True
            ),
            unit=_reference(raw="第八讲", candidate_id="lecture-08", ordinal=8),
            course_mode="lookup",
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    answer, next_context = await _turn(agent, messages, "改看第八讲", context)

    assert "Lecture 8" in answer
    verified = agent.context_signer.verify(next_context)  # type: ignore[arg-type, union-attr]
    assert verified is not None
    assert verified.course is not None
    assert verified.course.unit_id == "lecture-08"


async def test_new_course_without_unit_does_not_inherit_previous_unit(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(candidate_id="mit-6.7960-fall-2024"),
            unit=_reference(candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        ),
        _output(
            capability="studykit_lookup",
            evidence="换成 MIT 6.S081",
            conversation_act="correction",
            course=_reference(raw="MIT 6.S081", candidate_id="mit-6-s081"),
            course_mode="lookup",
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    answer, next_context = await _turn(agent, messages, "换成 MIT 6.S081", context)

    assert "Lecture 2：如何训练神经网络" not in answer
    verified = agent.context_signer.verify(next_context)  # type: ignore[arg-type, union-attr]
    assert verified is not None
    assert verified.course is not None
    assert verified.course.course_id == "mit-6.s081-fall-2021"
    assert verified.course.unit_id is None


@pytest.mark.parametrize("interruption", ["/help", "你好"])
async def test_short_response_preserves_verified_learning_continuity(
    tmp_path, interruption: str
) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(candidate_id="mit-6.7960-fall-2024"),
            unit=_reference(candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        )
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    _, next_context = await _turn(agent, messages, interruption, context)

    assert next_context == context
    assert len(model.calls) == 1


async def test_help_does_not_echo_invalid_continuity(tmp_path) -> None:
    agent = _agent(tmp_path, FakeStructuredModel())

    reply = await agent.handle(
        messages=[ChatMessage(role="user", content="/help")],
        user_id="legacy:test-user",
        coursepilot_context="invalid.token",
    )

    assert reply.coursepilot_context is None


async def test_session_id_restores_current_unit_across_agent_restart(tmp_path) -> None:
    first_agent = _agent(
        tmp_path,
        FakeStructuredModel(
            _output(
                capability="studykit_lookup",
                evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
                course=_reference(candidate_id="mit-6.7960-fall-2024"),
                unit=_reference(candidate_id="lecture-02", ordinal=2),
                course_mode="lookup",
            )
        ),
    )
    messages: list[ChatMessage] = []
    first = await _session_turn(
        first_agent,
        messages,
        "查看 MIT 6.7960 第 2 讲的 StudyKit",
        "gateway-conversation-1",
    )

    restarted_agent = _agent(
        tmp_path,
        FakeStructuredModel(
            _output(
                capability="concept_explanation",
                evidence="什么是梯度下降？",
                conversation_act="follow_up",
                course=_reference(
                    candidate_id="mit-6.7960-fall-2024", from_recent_context=True
                ),
                unit=_reference(from_recent_context=True),
                concept="梯度下降",
            ),
            _output(
                capability="practice_selection",
                evidence="给我一道习题",
                conversation_act="follow_up",
                course=_reference(
                    candidate_id="mit-6.7960-fall-2024", from_recent_context=True
                ),
                unit=_reference(from_recent_context=True),
            ),
        ),
    )
    concept = await _session_turn(
        restarted_agent, messages, "什么是梯度下降？", "gateway-conversation-1"
    )
    practice = await _session_turn(
        restarted_agent, messages, "给我一道习题", "gateway-conversation-1"
    )

    assert "Lecture 2" in first
    assert "梯度下降（gradient descent）" in concept
    assert "practice-concept-01" in practice
    assert b"gateway-conversation-1" not in (
        tmp_path / "profiles.sqlite3"
    ).read_bytes()


async def test_new_session_id_does_not_reuse_another_conversation(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(candidate_id="mit-6.7960-fall-2024"),
            unit=_reference(candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        ),
        _output(
            capability="practice_selection",
            evidence="给我一道习题",
            conversation_act="follow_up",
            course=_reference(
                candidate_id="mit-6.7960-fall-2024", from_recent_context=True
            ),
            unit=_reference(from_recent_context=True),
        ),
    )
    agent = _agent(tmp_path, model)
    first_messages: list[ChatMessage] = []
    await _session_turn(
        agent,
        first_messages,
        "查看 MIT 6.7960 第 2 讲的 StudyKit",
        "conversation-a",
    )

    answer = await _session_turn(
        agent, [*first_messages], "给我一道习题", "conversation-b"
    )

    assert "当前可在线读取的讲次" in answer
    assert "practice-concept-01" not in answer


async def test_onboarding_response_preserves_verified_learning_continuity(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="studykit_lookup",
            evidence="查看 MIT 6.7960 第 2 讲的 StudyKit",
            course=_reference(candidate_id="mit-6.7960-fall-2024"),
            unit=_reference(candidate_id="lecture-02", ordinal=2),
            course_mode="lookup",
        ),
        _output(
            capability="general_assistance",
            evidence="第一次怎么开始",
            conversation_act="onboarding",
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(
        agent, messages, "查看 MIT 6.7960 第 2 讲的 StudyKit", None
    )
    answer, next_context = await _turn(agent, messages, "第一次怎么开始", context)

    assert "第一次使用" in answer
    assert next_context == context


async def test_ambiguous_generation_status_plan_becomes_general_fallback(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="generation_status",
            evidence="就是刚才那题呀",
            conversation_act="follow_up",
        ),
        {
            "mode": "answer",
            "answer": "我还不能确认“刚才那题”的内容。请贴出题面，我可以帮你拆解思路。",
            "provenance": "general_knowledge",
            "citation_ids": [],
            "catalog_ids": [],
            "diagnostic_ids": [],
            "ran_code": False,
        },
    )
    agent = _agent(tmp_path, model)

    answer, _ = await _turn(agent, [], "就是刚才那题呀", None)

    assert "请贴出题面" in answer
    assert "authoring" not in answer
    assert len(model.calls) == 2


async def test_explicit_unavailable_generation_status_uses_general_assistance(
    tmp_path,
) -> None:
    model = FakeStructuredModel(
        {
            "mode": "answer",
            "answer": "我无法在普通对话中查询 StudyKit 后台生成任务，但可以帮你查看已上线的 StudyKit。",
            "provenance": "general_knowledge",
            "citation_ids": [],
            "catalog_ids": [],
            "diagnostic_ids": [],
            "ran_code": False,
        }
    )
    agent = _agent(tmp_path, model)

    answer, _ = await _turn(
        agent, [], "查看我的 StudyKit 生成任务状态", None
    )

    assert "无法在普通对话中查询" in answer
    assert "生成状态查询尚未接入在线能力" in answer
    assert "practice ID" not in answer
    assert len(model.calls) == 1


async def test_concept_followup_inherits_validated_course_and_concept(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="concept_explanation",
            evidence="解释 MIT 6.7960 第二讲的反向传播",
            course=_reference(raw="MIT 6.7960"),
            unit=_reference(raw="第二讲", candidate_id="lecture-02", ordinal=2),
            concept="反向传播",
        ),
        _output(
            capability="concept_explanation",
            evidence="用生活中的例子再说一遍",
            conversation_act="follow_up",
            concept="反向传播",
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    first, context = await _turn(
        agent, messages, "解释 MIT 6.7960 第二讲的反向传播", None
    )
    second, _ = await _turn(agent, messages, "用生活中的例子再说一遍", context)

    assert "**定义**" in first
    assert "反向传播" in second
    assert "请说明你想了解的概念" not in second


async def test_profile_correction_and_partial_forget_apply_without_magic_words(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="profile_analysis",
            evidence="我会 Python，想学 AI",
            profile_operations=[
                {"action": "add", "field_name": "background", "value": "Python", "evidence_quote": "我会 Python"},
                {"action": "add", "field_name": "learning_directions", "value": "AI", "evidence_quote": "想学 AI"},
            ],
        ),
        _output(
            capability="profile_analysis",
            evidence="其实不是 AI，是系统",
            conversation_act="correction",
            profile_operations=[
                {"action": "replace", "field_name": "learning_directions", "value": "系统", "evidence_quote": "不是 AI，是系统"}
            ],
        ),
        _output(
            capability="profile_analysis",
            evidence="把我的编程基础忘掉",
            conversation_act="profile_management",
            profile_operations=[
                {"action": "delete", "field_name": "background", "value": None, "evidence_quote": "编程基础忘掉"}
            ],
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    _, context = await _turn(agent, messages, "我会 Python，想学 AI", None)
    corrected, context = await _turn(agent, messages, "其实不是 AI，是系统", context)
    deleted, _ = await _turn(agent, messages, "把我的编程基础忘掉", context)

    profile = agent.profiles.load("legacy:test-user")
    assert [fact.value for fact in profile.confirmed("learning_directions")] == ["systems"]
    assert profile.confirmed("background") == []
    assert "ml_ai" not in corrected
    assert "Python" not in deleted


async def test_practice_answer_and_more_hint_keep_active_practice_and_prior_answer(
    tmp_path,
) -> None:
    model = FakeStructuredModel(
        _output(
            capability="practice_selection",
            evidence="给我一道 MIT 6.7960 第二讲的题",
            course=_reference(raw="MIT 6.7960"),
            unit=_reference(raw="第二讲", candidate_id="lecture-02", ordinal=2),
        ),
        _output(
            capability="practice_feedback",
            evidence="我觉得应该先算梯度",
            conversation_act="submit_answer",
            answer_message_index=2,
        ),
        _output(
            capability="practice_feedback",
            evidence="再给点提示",
            conversation_act="more_hint",
            answer_message_index=2,
        ),
    )
    agent = _agent(tmp_path, model)
    messages: list[ChatMessage] = []

    selected, context = await _turn(
        agent, messages, "给我一道 MIT 6.7960 第二讲的题", None
    )
    feedback, context = await _turn(
        agent, messages, "我觉得应该先算梯度，然后更新参数。", context
    )
    hinted, _ = await _turn(agent, messages, "我还是不懂，再给点提示。", context)

    assert "practice" in selected
    assert "请在反馈请求中附上" not in feedback
    assert "请补充你对" not in feedback
    assert "请在反馈请求中附上" not in hinted
    assert "空答案" not in hinted


async def test_session_store_failure_degrades_without_blocking_chat(tmp_path) -> None:
    class FailingSessionStore:
        def load(self, namespace: str, session_id: str):
            del namespace, session_id
            raise OSError("simulated unavailable state store")

        def save(self, namespace, session_id, state, *, expected_revision):
            del namespace, session_id, state, expected_revision
            raise OSError("simulated unavailable state store")

    model = FakeStructuredModel(
        _output(
            capability="concept_explanation",
            evidence="解释 MIT 6.7960 第二讲的反向传播",
            course=_reference(raw="MIT 6.7960"),
            unit=_reference(raw="第二讲", candidate_id="lecture-02", ordinal=2),
            concept="反向传播",
        )
    )
    agent = _agent(tmp_path, model)
    agent.session_state_store = FailingSessionStore()

    answer = await _session_turn(
        agent,
        [],
        "解释 MIT 6.7960 第二讲的反向传播",
        "unavailable-store-session",
    )

    assert "**定义**" in answer
