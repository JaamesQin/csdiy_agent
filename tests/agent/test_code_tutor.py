from __future__ import annotations

from app.agent.contracts import CourseContext
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.code_tutor.service import CodeTutorService
from app.profile.contracts import LearnerProfile
from tests.agent.helpers import FakeStructuredModel


async def test_python_syntax_error_is_deterministic_and_never_run() -> None:
    tutor = CodeTutorService(ReviewedFileStudyKitStore())

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="def broken(x)\n    return x",
        language="python",
        error_text=None,
        question="为什么报错？",
        profile=LearnerProfile(),
    )

    assert result.ran_code is False
    assert result.diagnostics[0].code == "python_syntax_error"
    assert result.diagnostics[0].line == 1
    assert any("未运行" in note for note in result.safety_notes)


async def test_course_linked_fallback_uses_reviewed_page_citations() -> None:
    tutor = CodeTutorService(ReviewedFileStudyKitStore())
    context = CourseContext(
        course_id="mit-6.7960-fall-2024",
        course_version="fall-2024",
        unit_id="lecture-02",
    )

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=context,
        code="loss.backward()\nprint(weight.grad)",
        language="python",
        error_text=None,
        question="MIT 6.7960 第 2 讲里 backward 后梯度为什么是 None？",
        profile=LearnerProfile(),
    )

    assert result.citations
    assert all(citation.source_id == "mit-6.7960-f24-lecture-02-slides" for citation in result.citations)
    assert result.ran_code is False


async def test_model_prompt_hides_internal_practice_rubric_and_filters_citations() -> None:
    model = FakeStructuredModel(
        {
            "observation": "梯度没有按预期出现。",
            "diagnostic_hypotheses": ["张量可能不是叶子节点。"],
            "next_checks": ["检查 is_leaf。"],
            "next_attempt": "打印 requires_grad 和 is_leaf。",
            "citation_ids": ["concept-1-page-1", "invented-citation"],
            "safety_notes": [],
        }
    )
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)
    context = CourseContext(
        course_id="mit-6.7960-fall-2024",
        course_version="fall-2024",
        unit_id="lecture-02",
    )

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=context,
        code="loss.backward()",
        language="python",
        error_text=None,
        question="反向传播后没有梯度",
        profile=LearnerProfile(),
    )

    prompt = model.calls[0]["user_prompt"]
    assert "expected_evidence" not in prompt
    assert '"evaluation"' not in prompt
    assert [item.citation_id for item in result.citations] == ["concept-1-page-1"]
    assert result.usage["total_tokens"] == 15


async def test_model_draft_tolerates_harmless_provider_wrapping() -> None:
    model = FakeStructuredModel(
        {
            "result": {
                "observation": "parameter 没有启用梯度跟踪。",
                "diagnostic_hypotheses": "requires_grad 默认为 False。",
                "next_checks": "检查 parameter.requires_grad。",
                "next_attempt": "创建张量时设置 requires_grad=True。",
                "citation_ids": [],
                "safety_notes": "没有运行代码。",
                "ran_code": False,
            },
            "provider_note": "structured response",
        }
    )
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="loss.backward()",
        language="python",
        error_text=None,
        question="为什么报错？",
        profile=LearnerProfile(),
    )

    assert result.answer == "parameter 没有启用梯度跟踪。"
    assert result.diagnostic_hypotheses == ["requires_grad 默认为 False。"]
    assert result.ran_code is False


async def test_complete_assignment_solution_is_refused_before_model_call() -> None:
    model = FakeStructuredModel({})
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="def homework():\n    pass",
        language="python",
        error_text=None,
        question="帮我做完整作业，直接给全部代码",
        profile=LearnerProfile(),
    )

    assert "不能代写" in result.answer
    assert model.calls == []
    assert result.ran_code is False


async def test_cpp_syntax_error_is_deterministic_and_never_run() -> None:
    tutor = CodeTutorService(ReviewedFileStudyKitStore())

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="int main( { return 0; }",
        language="cpp",
        error_text=None,
        question="审阅这段代码",
        profile=LearnerProfile(),
    )

    assert result.diagnostics[0].code == "syntax_error"
    assert result.diagnostics[0].line == 1
    assert result.ran_code is False


async def test_unlabelled_code_is_not_assumed_to_be_python() -> None:
    tutor = CodeTutorService(ReviewedFileStudyKitStore())

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="int main() { return 0; }",
        language=None,
        error_text=None,
        question="审阅这段代码",
        profile=LearnerProfile(),
    )

    assert result.diagnostics[0].code == "language_required"
    assert "```cpp" in result.diagnostics[0].message
    assert result.ran_code is False


async def test_model_receives_normalized_non_python_language() -> None:
    model = FakeStructuredModel(
        {
            "observation": "循环边界需要进一步确认。",
            "diagnostic_hypotheses": [],
            "next_checks": [],
            "next_attempt": "检查最后一次迭代。",
            "citation_ids": [],
            "safety_notes": [],
        }
    )
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="int main() { return 0; }",
        language="c++",
        error_text=None,
        question="审阅这段代码",
        profile=LearnerProfile(),
    )

    assert '"language": "cpp"' in model.calls[0]["user_prompt"]
    assert '"language_display_name": "C++"' in model.calls[0]["user_prompt"]
    assert result.ran_code is False
