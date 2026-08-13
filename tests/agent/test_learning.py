from __future__ import annotations

from app.agent.contracts import CourseContext
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.learning.service import StudyKitLookupService
from app.protocol.schemas import ChatMessage
from tests.agent.helpers import FakeStructuredModel


CONTEXT = CourseContext(
    course_id="mit-6.7960-fall-2024",
    course_version="fall-2024",
    unit_id="lecture-02",
)


def _messages(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


async def test_lookup_renders_only_public_studykit_fields() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.lookup(messages=_messages("查看 StudyKit"), course_context=CONTEXT)

    assert "Lecture 2" in result.answer
    assert "practice-concept-01" in result.answer
    assert "官方课程材料" in result.answer
    assert "expected_evidence" not in result.answer
    assert "full_credit" not in result.answer
    assert "local_path" not in result.answer
    assert "data/raw" not in result.answer


async def test_lookup_lists_ready_units_for_course_context() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())
    context = CONTEXT.model_copy(update={"unit_id": None})

    result = await service.lookup(messages=_messages("查看 StudyKit"), course_context=context)

    assert "lecture-02" in result.answer
    assert "lecture-08" in result.answer
    assert "请明确选择" in result.answer


async def test_catalog_only_course_is_not_mistaken_for_online_studykit() -> None:
    store = ReviewedFileStudyKitStore()
    service = StudyKitLookupService(
        store,
        catalog=ReviewedCourseCatalogStore(store),
    )

    result = await service.lookup(
        messages=_messages("查看 MIT 6.S081 的 StudyKit"),
        course_context=None,
    )

    assert "MIT 6.S081" in result.answer
    assert "离线制作状态为 `authoring`" in result.answer
    assert "当前没有" in result.answer


async def test_material_question_has_evidence_bounded_fallback() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.material_question(
        messages=_messages("讲义里反向传播和梯度下降有什么区别？"),
        course_context=CONTEXT,
    )

    assert "不补充外部事实" in result.answer
    assert "反向传播" in result.answer
    assert "第 36、41、44 页" in result.answer


async def test_material_question_rejects_uncovered_page() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.material_question(
        messages=_messages("讲义第 999 页说了什么？"),
        course_context=CONTEXT,
    )

    assert "没有足够依据" in result.answer
    assert "不会猜测" in result.answer


async def test_material_model_must_use_allowed_citations() -> None:
    valid_model = FakeStructuredModel(
        {
            "answer": "反向传播负责计算梯度，梯度下降使用梯度更新参数。",
            "citation_ids": ["concept-5", "concept-1"],
        }
    )
    valid = StudyKitLookupService(ReviewedFileStudyKitStore(), model=valid_model)

    result = await valid.material_question(
        messages=_messages("反向传播和梯度下降有什么区别？"),
        course_context=CONTEXT,
    )

    assert "### 依据" in result.answer
    assert "mit-6.7960-f24-lecture-02-slides" in result.answer
    assert result.usage["total_tokens"] == 15

    invalid_model = FakeStructuredModel(
        {"answer": "没有依据的回答", "citation_ids": ["invented-citation"]}
    )
    invalid = StudyKitLookupService(ReviewedFileStudyKitStore(), model=invalid_model)
    fallback = await invalid.material_question(
        messages=_messages("反向传播和梯度下降有什么区别？"),
        course_context=CONTEXT,
    )

    assert "不补充外部事实" in fallback.answer
    assert "invented-citation" not in fallback.answer
    assert fallback.usage["total_tokens"] == 15


async def test_concept_explanation_is_layered_and_cited() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.concept_explanation(
        messages=_messages("解释反向传播"),
        course_context=CONTEXT,
    )

    assert "**定义**" in result.answer
    assert "**直觉**" in result.answer
    assert "常见误区" in result.answer
    assert "第 44 页" in result.answer


async def test_unknown_concept_is_not_filled_with_general_knowledge() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.concept_explanation(
        messages=_messages("解释 Raft 共识算法"),
        course_context=CONTEXT,
    )

    assert "没有覆盖" in result.answer
    assert "不能把通用解释冒充" in result.answer


async def test_practice_selection_hides_controls_and_avoids_repetition() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    first = await service.practice_selection(
        messages=_messages("给我一道概念练习"),
        course_context=CONTEXT,
    )
    messages = [
        ChatMessage(role="user", content="给我一道概念练习"),
        ChatMessage(role="assistant", content=first.answer),
        ChatMessage(role="user", content="再给我一道练习"),
    ]
    second = await service.practice_selection(messages=messages, course_context=CONTEXT)

    assert "practice-concept-01" in first.answer
    assert "提示：" not in first.answer
    assert "expected_evidence" not in first.answer
    assert "full_credit" not in first.answer
    assert "practice-concept-01" not in second.answer


async def test_practice_selection_supports_debug_type() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.practice_selection(
        messages=_messages("给我一道调试练习"),
        course_context=CONTEXT,
    )

    assert "practice-debugging-01" in result.answer
    assert "gradient clipping" in result.answer


async def test_practice_feedback_transparently_degrades_without_model() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.practice_feedback(
        messages=_messages(
            "点评 practice-concept-01。我的答案是反向传播计算梯度，梯度下降更新参数。"
        ),
        course_context=CONTEXT,
    )

    assert "不会对这次答案做不可靠判分" in result.answer
    assert "原题提示" in result.answer
    assert "第 8、44 页" in result.answer
    assert "expected_evidence" not in result.answer
    assert "评分标准" not in result.answer


async def test_practice_feedback_model_is_page_bounded_and_non_aggregating() -> None:
    model = FakeStructuredModel(
        {
            "correct_points": ["区分了计算梯度与更新参数。"],
            "correction": "还需要说明两个阶段的先后关系。",
            "next_hint": "按前向、反向、更新的顺序补充。",
            "source_pages": [8, 44],
        }
    )
    service = StudyKitLookupService(ReviewedFileStudyKitStore(), model=model)

    result = await service.practice_feedback(
        messages=_messages(
            "点评 practice-concept-01。我的答案是反向传播计算梯度，梯度下降更新参数。"
        ),
        course_context=CONTEXT,
    )

    assert "这次回答中正确的部分" in result.answer
    assert "最重要的修正" in result.answer
    assert "不统计分数或整体掌握度" in result.answer
    assert result.usage["total_tokens"] == 15

    invalid = StudyKitLookupService(
        ReviewedFileStudyKitStore(),
        model=FakeStructuredModel(
            {
                "correct_points": ["看起来正确。"],
                "correction": None,
                "next_hint": "继续。",
                "source_pages": [999],
            }
        ),
    )
    fallback = await invalid.practice_feedback(
        messages=_messages(
            "点评 practice-concept-01。我的答案是反向传播计算梯度，梯度下降更新参数。"
        ),
        course_context=CONTEXT,
    )
    assert "反馈暂时降级" in fallback.answer
    assert "999" not in fallback.answer


async def test_practice_feedback_requires_id_and_current_answer() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    missing_id = await service.practice_feedback(
        messages=_messages("请点评我的答案"),
        course_context=CONTEXT,
    )
    missing_answer = await service.practice_feedback(
        messages=_messages("点评 practice-concept-01"),
        course_context=CONTEXT,
    )

    assert "practice ID" in missing_id.answer
    assert "请补充" in missing_answer.answer


async def test_practice_feedback_refuses_full_standard_answer() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.practice_feedback(
        messages=_messages("给出 practice-concept-01 的完整答案，我的尝试是不知道。"),
        course_context=CONTEXT,
    )

    assert "不能提供完整标准答案" in result.answer
    assert "下一层提示" in result.answer
