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


def test_unit_summary_uses_only_approved_studykit_content() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = service.unit_summary(
        messages=_messages("这讲最重要的内容是什么？"),
        course_context=CONTEXT,
    )

    assert "本讲重点" in result.answer
    assert "反向传播" in result.answer
    assert "已审核 StudyKit" in result.answer
    assert "算法、数据结构、编程语言和计算理论" not in result.answer


async def test_unscoped_lookup_never_enumerates_every_unit() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.lookup(messages=_messages("查看 StudyKit"), course_context=None)

    assert "可继续缩小范围的课程" in result.answer
    assert result.answer.count("\n-") <= 3
    assert "避免一次返回全部学习包" in result.answer


async def test_material_uses_one_model_call_and_reports_usage() -> None:
    store = ReviewedFileStudyKitStore()
    document = store.get_ready(
        CONTEXT.course_id, CONTEXT.course_version, CONTEXT.unit_id or ""
    )
    assert document is not None
    probe = StudyKitLookupService(store)
    evidence = probe._select_evidence(document, "反向传播是什么？")
    assert evidence
    generator = FakeStructuredModel(
        {
            "claims": [
                {
                    "text": evidence[0].text,
                    "provenance": "course_material",
                    "citation_ids": [evidence[0].citation_id],
                }
            ]
        }
    )
    service = StudyKitLookupService(store, model=generator)

    result = await service.material_question(
        messages=_messages("反向传播是什么？"),
        course_context=CONTEXT,
    )

    assert "### 依据" in result.answer
    assert result.usage["total_tokens"] == 15
    assert len(generator.calls) == 1


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

    chinese = await service.material_question(
        messages=_messages("讲义第九百九十九页说了什么？"),
        course_context=CONTEXT,
    )
    assert "第 999 页" in chinese.answer
    assert "没有足够依据" in chinese.answer


async def test_material_model_must_use_allowed_citations() -> None:
    valid_model = FakeStructuredModel(
        {
            "claims": [
                {
                    "text": "反向传播负责计算梯度，梯度下降使用梯度更新参数。",
                    "provenance": "course_material",
                    "citation_ids": ["concept-5", "concept-1"],
                }
            ]
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
        {
            "claims": [
                {
                    "text": "没有依据的回答",
                    "provenance": "course_material",
                    "citation_ids": ["invented-citation"],
                }
            ]
        }
    )
    invalid = StudyKitLookupService(ReviewedFileStudyKitStore(), model=invalid_model)
    fallback = await invalid.material_question(
        messages=_messages("反向传播和梯度下降有什么区别？"),
        course_context=CONTEXT,
    )

    assert "不补充外部事实" in fallback.answer
    assert "invented-citation" not in fallback.answer
    assert fallback.usage["total_tokens"] == 15


async def test_invalid_course_partition_keeps_single_call_general_knowledge() -> None:
    model = FakeStructuredModel(
        {
            "claims": [
                {
                    "text": "未经依据支持的课程事实。",
                    "provenance": "course_material",
                    "citation_ids": ["invented-citation"],
                },
                {
                    "text": "梯度通常描述函数在局部增长最快的方向。",
                    "provenance": "general_knowledge",
                    "citation_ids": [],
                },
            ]
        }
    )
    service = StudyKitLookupService(ReviewedFileStudyKitStore(), model=model)

    result = await service.material_question(
        messages=_messages("反向传播和梯度有什么关系？"), course_context=CONTEXT
    )

    assert "未经依据" not in result.answer
    assert "通用知识（不代表当前课程材料）" in result.answer
    assert "梯度通常" in result.answer
    assert len(model.calls) == 1


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


async def test_practice_selection_matches_id_without_separators() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.practice_selection(
        messages=_messages("显示 PRACTICEDEBUGGING01"),
        course_context=CONTEXT,
    )

    assert "practice-debugging-01" in result.answer
    assert "gradient clipping" in result.answer


async def test_practice_selection_resolves_chinese_ordinal_after_studykit_index() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())
    lookup = await service.lookup(
        messages=_messages("查看 MIT 6.7960 第 2 讲的 StudyKit"),
        course_context=CONTEXT,
    )

    result = await service.practice_selection(
        messages=[
            ChatMessage(role="user", content="查看 MIT 6.7960 第 2 讲的 StudyKit"),
            ChatMessage(role="assistant", content=lookup.answer),
            ChatMessage(role="user", content="显示第七道习题"),
        ],
        course_context=CONTEXT,
    )

    assert "practice-differentiable-programming-01" in result.answer
    assert "已在当前对话中展示完毕" not in result.answer


async def test_practice_selection_counts_only_actual_presentations_as_displayed() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())
    lookup = await service.lookup(messages=_messages("查看 StudyKit"), course_context=CONTEXT)

    result = await service.practice_selection(
        messages=[
            ChatMessage(role="assistant", content=lookup.answer),
            ChatMessage(role="user", content="再给我一道练习"),
        ],
        course_context=CONTEXT,
    )

    assert "practice-concept-01" in result.answer


async def test_practice_selection_reports_out_of_range_ordinal() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.practice_selection(
        messages=_messages("显示第八道习题"),
        course_context=CONTEXT,
    )

    assert result.answer == "本讲只有 7 道练习，无法显示第 8 道。"


async def test_practice_selection_resolves_ex_alias_by_display_order() -> None:
    service = StudyKitLookupService(ReviewedFileStudyKitStore())

    result = await service.practice_selection(
        messages=_messages("ex-7"),
        course_context=CONTEXT,
    )

    assert "practice-differentiable-programming-01" in result.answer


async def test_practice_selection_automatically_rewrites_once() -> None:
    model = FakeStructuredModel(
        {
            "practice_id": "practice-concept-01",
            "transformation_kind": "structured_rewrite",
            "title": "区分梯度计算与参数更新",
            "scenario": "考虑一次标准训练迭代。",
            "givens": ["已经得到一个标量损失。"],
            "question": "分别说明反向传播和梯度下降在该迭代中承担的动作。",
            "constraints": ["按发生顺序回答。"],
            "deliverable": "用两到三句话说明输入、输出和先后关系。",
            "estimated_minutes": 8,
            "citation_ids": [],
            "retained_objective_ids": [],
            "retained_requirement_ids": [],
        }
    )
    service = StudyKitLookupService(ReviewedFileStudyKitStore(), model=model)

    result = await service.practice_selection(
        messages=_messages("给我一道概念练习"), course_context=CONTEXT
    )

    assert "模型精确化" in result.answer
    assert "区分梯度计算与参数更新" in result.answer
    assert result.presentation_kind == "structured_rewrite"
    assert result.presentation_digest is not None
    assert len(model.calls) == 1
    prompt = model.calls[0]["user_prompt"]
    assert "expected_evidence_key_points" in prompt
    assert '"evaluation"' not in prompt
    assert "full_credit" not in prompt


async def test_practice_rewrite_leak_falls_back_to_original_once() -> None:
    model = FakeStructuredModel(
        {
            "practice_id": "practice-concept-01",
            "transformation_kind": "structured_rewrite",
            "title": "答案",
            "scenario": None,
            "givens": [],
            "question": "反向传播输入损失及计算图信息，输出参数梯度。",
            "constraints": [],
            "deliverable": "复述上面的结论。",
            "estimated_minutes": None,
            "citation_ids": [],
            "retained_objective_ids": [],
            "retained_requirement_ids": [],
        }
    )
    service = StudyKitLookupService(ReviewedFileStudyKitStore(), model=model)

    result = await service.practice_selection(
        messages=_messages("给我一道概念练习"), course_context=CONTEXT
    )

    assert "题目精确化暂时不可用" in result.answer
    assert "作答要求" in result.answer
    assert result.presentation_kind == "original"
    assert len(model.calls) == 1


async def test_practice_rewrite_kill_switch_uses_no_model_call() -> None:
    model = FakeStructuredModel({})
    service = StudyKitLookupService(
        ReviewedFileStudyKitStore(), model=model, practice_rewrite_enabled=False
    )

    result = await service.practice_selection(
        messages=_messages("给我一道概念练习"), course_context=CONTEXT
    )

    assert result.presentation_kind == "original"
    assert model.calls == []


async def test_feedback_uses_digest_bound_presented_question() -> None:
    model = FakeStructuredModel(
        {
            "practice_id": "practice-concept-01",
            "transformation_kind": "structured_rewrite",
            "title": "区分两个训练阶段",
            "scenario": None,
            "givens": ["已经得到标量损失。"],
            "question": "按顺序说明梯度计算和参数更新分别发生在哪一步。",
            "constraints": [],
            "deliverable": "用两句话回答。",
            "estimated_minutes": 5,
            "citation_ids": [],
            "retained_objective_ids": [],
            "retained_requirement_ids": [],
        },
        {
            "correct_points": ["说明了反向传播先计算梯度。"],
            "correction": "补充参数更新发生在梯度计算之后。",
            "next_hint": "按损失、梯度、参数的顺序检查。",
            "source_pages": [8, 44],
        },
    )
    service = StudyKitLookupService(ReviewedFileStudyKitStore(), model=model)
    presentation = await service.practice_selection(
        messages=_messages("给我一道概念练习"), course_context=CONTEXT
    )
    messages = [
        ChatMessage(role="user", content="给我一道概念练习"),
        ChatMessage(role="assistant", content=presentation.answer),
        ChatMessage(
            role="user",
            content="点评 practice-concept-01。我的答案是先算梯度，再更新参数。",
        ),
    ]

    result = await service.practice_feedback(
        messages=messages,
        course_context=CONTEXT,
        presentation_digest=presentation.presentation_digest,
        presentation_kind=presentation.presentation_kind,
    )

    assert "本题点评" in result.answer
    assert len(model.calls) == 2
    assert "按顺序说明梯度计算" in model.calls[1]["user_prompt"]


async def test_grounded_variant_feedback_requires_matching_presentation() -> None:
    model = FakeStructuredModel({})
    service = StudyKitLookupService(ReviewedFileStudyKitStore(), model=model)

    result = await service.practice_feedback(
        messages=_messages(
            "点评 practice-concept-01。我的答案是先算梯度，再更新参数。"
        ),
        course_context=CONTEXT,
        presentation_digest="a" * 64,
        presentation_kind="grounded_variant",
    )

    assert "无法从当前消息历史恢复" in result.answer
    assert model.calls == []


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
    prompt = model.calls[0]["user_prompt"]
    assert "expected_evidence" not in prompt
    assert '"evaluation"' not in prompt
    assert "full_credit" not in prompt

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
