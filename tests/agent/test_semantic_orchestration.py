from __future__ import annotations

import hashlib

from app.agent.context_token import ContextTokenSigner
from app.agent.orchestrator import CoursePilotAgent
from app.agent.planning import TaskPlanner
from app.agent.router import IntentRouter
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.code_tutor.service import CodeTutorService
from app.course_navigation.service import CourseNavigationService
from app.learning.service import StudyKitLookupService
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService
from app.protocol.schemas import ChatMessage
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
    return CoursePilotAgent(
        store=store,
        router=IntentRouter(store),
        profiles=ProfileService(SQLiteProfileRepository(tmp_path / "profiles.sqlite3")),
        code_tutor=CodeTutorService(store),
        course_navigation=CourseNavigationService(catalog),
        studykit_learning=StudyKitLookupService(
            store,
            catalog=catalog,
            practice_rewrite_enabled=False,
        ),
        planner=TaskPlanner(model=model, robust_input_enabled=True),
        context_signer=ContextTokenSigner(
            hashlib.sha256(b"semantic-orchestration-tests").digest()
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

    assert "课程推荐" in answer or "匹配到的课程" in answer
    assert "可继续缩小范围的课程" not in answer


async def test_ambiguous_generation_status_plan_gets_context_specific_prompt(tmp_path) -> None:
    model = FakeStructuredModel(
        _output(
            capability="generation_status",
            evidence="就是刚才那题呀",
            conversation_act="follow_up",
        )
    )
    agent = _agent(tmp_path, model)

    answer, _ = await _turn(agent, [], "就是刚才那题呀", None)

    assert "题面或 practice ID" in answer
    assert "authoring" not in answer


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
