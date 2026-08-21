from __future__ import annotations

import pytest

from app.agent.contracts import CodeTutorMode, CourseContext
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.code_tutor.contracts import CodeTutorRequest, TutorCodeBlock, TutorResult
from app.code_tutor.service import CodeTutorService, render_tutor_result
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


async def test_generate_cpp_example_without_submitted_code() -> None:
    model = FakeStructuredModel(
        {
            "observation": "这个例子通过基类引用触发派生类实现。",
            "code_blocks": [
                {
                    "kind": "example",
                    "language": "cpp",
                    "filename": "main.cpp",
                    "code": (
                        "#include <iostream>\n\n"
                        "class Base {\npublic:\n"
                        "    virtual void speak() const { std::cout << \"Base\\n\"; }\n"
                        "    virtual ~Base() = default;\n};\n\n"
                        "class Derived : public Base {\npublic:\n"
                        "    void speak() const override { std::cout << \"Derived\\n\"; }\n"
                        "};\n\n"
                        "int main() {\n    Derived value;\n    Base& ref = value;\n"
                        "    ref.speak();\n    return 0;\n}\n"
                    ),
                    "explanation": "override 明确声明派生类覆盖虚函数。",
                    "expected_behavior": "输出 Derived。",
                }
            ],
            "diagnostic_hypotheses": [],
            "next_checks": ["使用支持 C++17 的编译器自行编译。"],
            "next_attempt": "增加第二个派生类观察多态分派。",
            "citation_ids": [],
            "safety_notes": [],
        }
    )
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="给我一段完整的 cpp 示例代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(
            mode=CodeTutorMode.GENERATE_EXAMPLE,
            target_language="cpp",
        ),
    )
    rendered = render_tutor_result(result)

    assert result.artifact is None
    assert result.ran_code is False
    assert len(model.calls) == 1
    assert "virtual" in rendered
    assert "override" in rendered
    assert "int main" in rendered
    assert "预期行为（未运行）" in rendered
    assert "请粘贴" not in rendered
    assert "### 诊断假设" not in rendered


async def test_complete_assignment_is_refused_without_existing_code() -> None:
    model = FakeStructuredModel({})
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="这是课程作业，帮我做完并给出全部代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(
            mode=CodeTutorMode.GENERATE_EXAMPLE,
            target_language="cpp",
        ),
    )

    assert "不能代写" in result.answer
    assert model.calls == []
    assert result.ran_code is False


async def test_generation_without_language_clarifies_before_model_call() -> None:
    model = FakeStructuredModel({})
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="给我一个示例代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(mode=CodeTutorMode.GENERATE_EXAMPLE),
    )

    assert "请说明希望使用的编程语言" in result.answer
    assert model.calls == []


async def test_missing_referenced_code_asks_for_repaste_before_model_call() -> None:
    model = FakeStructuredModel({})
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="解释上面的代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(
            mode=CodeTutorMode.EXPLAIN,
            target_language="cpp",
            references_existing_code=True,
        ),
    )

    assert "需要看到当前代码" in result.answer
    assert model.calls == []


async def test_generation_without_model_is_transparent() -> None:
    tutor = CodeTutorService(ReviewedFileStudyKitStore())

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="给我 cpp 示例代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(
            mode=CodeTutorMode.GENERATE_EXAMPLE,
            target_language="cpp",
        ),
    )

    assert result.code_blocks == []
    assert "模型当前不可用" in result.answer
    assert result.ran_code is False


@pytest.mark.parametrize(
    "mode",
    [
        CodeTutorMode.DIAGNOSE,
        CodeTutorMode.REVIEW,
        CodeTutorMode.REPAIR,
        CodeTutorMode.REFACTOR,
    ],
)
async def test_code_dependent_modes_request_current_code(mode: CodeTutorMode) -> None:
    model = FakeStructuredModel({})
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="处理这段代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(mode=mode, target_language="python"),
    )

    assert "需要看到当前代码" in result.answer
    assert model.calls == []


async def test_invalid_generated_syntax_fails_closed_without_second_call() -> None:
    model = FakeStructuredModel(
        {
            "observation": "示例。",
            "code_blocks": [
                {
                    "kind": "example",
                    "language": "cpp",
                    "filename": "main.cpp",
                    "code": "int main( { return 0; }",
                    "explanation": "",
                    "expected_behavior": "",
                }
            ],
            "diagnostic_hypotheses": [],
            "next_checks": [],
            "next_attempt": "重试。",
            "citation_ids": [],
            "safety_notes": [],
        }
    )
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="给我 cpp 示例代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(
            mode=CodeTutorMode.GENERATE_EXAMPLE,
            target_language="cpp",
        ),
    )

    assert result.code_blocks == []
    assert "没有展示未经验证" in result.answer
    assert len(model.calls) == 1


@pytest.mark.parametrize(
    "blocks",
    [
        [],
        [
            {
                "kind": "example",
                "language": "python",
                "filename": "main.py",
                "code": "print('wrong language')",
                "explanation": "",
                "expected_behavior": "",
            }
        ],
        [
            {
                "kind": "example",
                "language": "cpp",
                "filename": "main.cpp",
                "code": "int main() { return 0; }",
                "explanation": "",
                "expected_behavior": "",
            }
        ],
    ],
)
async def test_missing_or_mismatched_generated_block_fails_closed(
    blocks: list[dict[str, str]],
) -> None:
    model = FakeStructuredModel(
        {
            "observation": "示例。",
            "code_blocks": blocks,
            "diagnostic_hypotheses": [],
            "next_checks": [],
            "next_attempt": "重试。",
            "citation_ids": [],
            "safety_notes": [],
        }
    )
    tutor = CodeTutorService(ReviewedFileStudyKitStore(), model=model)

    result = await tutor.tutor_code(
        user_id=None,
        conversation_id=None,
        course_context=None,
        code="",
        language=None,
        error_text=None,
        question="给我 cpp 示例代码",
        profile=LearnerProfile(),
        request=CodeTutorRequest(
            mode=CodeTutorMode.GENERATE_EXAMPLE,
            target_language="cpp",
        ),
    )

    assert result.code_blocks == []
    assert "没有展示未经验证" in result.answer
    assert len(model.calls) == 1


def test_render_uses_a_fence_longer_than_generated_backticks() -> None:
    rendered = render_tutor_result(
        TutorResult(
            mode=CodeTutorMode.GENERATE_EXAMPLE,
            answer="示例。",
            code_blocks=[
                TutorCodeBlock(
                    kind="example",
                    language="python",
                    code='print("```")',
                )
            ],
            safety_notes=["代码未运行。"],
        )
    )

    assert "````python" in rendered
