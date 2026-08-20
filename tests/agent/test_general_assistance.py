from __future__ import annotations

import json

from app.general_assistance.service import (
    MAX_HISTORY_CHARACTERS,
    MAX_HISTORY_MESSAGES,
    GeneralAssistanceService,
    build_history_window,
    minimize_continuity,
)
from app.agent.contracts import CapabilityId, ProvenanceKind
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.knowledge import ReviewedCourseKnowledgeStore
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.protocol.schemas import ChatMessage
from tests.agent.helpers import FakeStructuredModel


def _answer(text: str = "先减少并行目标，每周保留一次回顾。") -> dict[str, object]:
    return {
        "mode": "answer",
        "answer": text,
        "provenance": "general_knowledge",
        "citation_ids": [],
        "catalog_ids": [],
        "diagnostic_ids": [],
        "ran_code": False,
    }


def test_history_window_keeps_latest_thirty_with_character_cap() -> None:
    messages = [
        ChatMessage(role="user", content=f"message-{index}:" + "x" * 2_000)
        for index in range(40)
    ]

    history = build_history_window(messages)

    assert len(history) <= MAX_HISTORY_MESSAGES
    assert sum(len(item["content"]) for item in history) <= MAX_HISTORY_CHARACTERS
    assert history[-1]["index"] == 39
    assert history[-1]["content"].startswith("message-39:")
    assert [item["index"] for item in history] == sorted(
        item["index"] for item in history
    )


def test_single_long_latest_message_preserves_head_and_tail() -> None:
    content = "HEAD" + "x" * MAX_HISTORY_CHARACTERS + "TAIL"

    history = build_history_window([ChatMessage(role="user", content=content)])

    assert len(history[0]["content"]) == MAX_HISTORY_CHARACTERS
    assert history[0]["content"].startswith("HEAD")
    assert history[0]["content"].endswith("TAIL")
    assert "较长消息已截断" in history[0]["content"]


def test_continuity_minimization_drops_digests_and_internal_state() -> None:
    minimized = minimize_continuity(
        {
            "course": {"course_id": "mit-6.7960"},
            "last_concept": "反向传播",
            "code_digest": "secret-digest",
            "plan_digest": "internal-digest",
            "issued_at": 1,
        }
    )

    assert minimized == {
        "course": {"course_id": "mit-6.7960"},
        "last_concept": "反向传播",
    }


async def test_general_answer_receives_role_confirmed_profile_and_minimized_context() -> None:
    model = FakeStructuredModel(_answer())
    service = GeneralAssistanceService(model)

    result = await service.answer(
        messages=[ChatMessage(role="user", content="我最近学得有点乱，怎么调整？")],
        confirmed_profile={"weekly_minutes": [360], "background": ["Python"]},
        continuity={"last_concept": "事务", "code_digest": "not-for-model"},
    )

    prompt = json.loads(model.calls[0]["user_prompt"])
    assert result.mode == "answer"
    assert result.usage["total_tokens"] == 15
    assert prompt["confirmed_profile"] == {
        "weekly_minutes": [360],
        "background": ["Python"],
    }
    assert prompt["verified_continuity"] == {"last_concept": "事务"}
    assert "not-for-model" not in model.calls[0]["user_prompt"]
    capability_ids = {
        item["id"] for item in prompt["coursepilot"]["available_capabilities"]
    }
    assert "general_assistance" in capability_ids
    assert "learning_review" not in capability_ids
    assert "只处理未被专用能力归类" in model.calls[0]["system_prompt"]


async def test_unavailable_capability_boundary_is_explicit_and_model_visible() -> None:
    model = FakeStructuredModel(_answer("我可以提供一般的进度梳理建议。"))
    service = GeneralAssistanceService(model)

    result = await service.answer(
        messages=[ChatMessage(role="user", content="查看 StudyKit 生成任务状态")],
        requested_unavailable_capability=CapabilityId.GENERATION_STATUS,
    )

    prompt = json.loads(model.calls[0]["user_prompt"])
    assert prompt["requested_unavailable_capability"]["id"] == "generation_status"
    assert prompt["requested_unavailable_capability"]["status"] == "unavailable"
    assert "生成状态查询尚未接入在线能力" in result.answer
    assert "通用建议" in result.answer


async def test_general_answer_refuses_submit_ready_coursework_without_model_call() -> None:
    model = FakeStructuredModel(_answer("不应使用"))
    service = GeneralAssistanceService(model)

    result = await service.answer(
        messages=[ChatMessage(role="user", content="帮我做完整作业，给可提交的标准答案")]
    )

    assert result.mode == "constrained_refusal"
    assert "不能提供可直接提交" in result.answer
    assert model.calls == []


async def test_general_answer_rejects_claim_ids_and_degrades() -> None:
    invalid = _answer()
    invalid["citation_ids"] = ["page-12"]
    service = GeneralAssistanceService(FakeStructuredModel(invalid))

    result = await service.answer(
        messages=[ChatMessage(role="user", content="怎样复习？")]
    )

    assert result.mode == "unavailable"
    assert "暂时不可用" in result.answer


async def test_general_answer_always_receives_full_course_index_and_safe_details() -> None:
    output = _answer("结合你的起点，可以先打好编程基础。")
    output["catalog_ids"] = ["ucb-cs61a"]
    model = FakeStructuredModel(output)
    catalog = ReviewedCourseCatalogStore(ReviewedFileStudyKitStore())
    service = GeneralAssistanceService(
        model,
        course_knowledge=ReviewedCourseKnowledgeStore(catalog),
    )

    result = await service.answer(
        messages=[ChatMessage(role="user", content="这些课程适合我吗？")],
        confirmed_profile={
            "learning_directions": ["systems"],
            "background": ["没有编程基础"],
        },
        continuity={"displayed_catalog_ids": ["ucb-cs61c", "mit-6-s081"]},
    )

    prompt = json.loads(model.calls[0]["user_prompt"])
    assert len(prompt["course_registry_index"]["courses"]) == 119
    assert [
        item["course"]["catalog_id"] for item in prompt["related_course_details"][:2]
    ] == ["ucb-cs61c", "mit-6-s081"]
    assert "candidate_offerings" not in model.calls[0]["user_prompt"]
    assert "page_sha256" not in model.calls[0]["user_prompt"]
    assert result.catalog_ids == ["ucb-cs61a"]
    assert "CS61A" in result.answer
    assert "课程目录信息" not in result.answer
    assert [claim.provenance for claim in result.claims] == [
        ProvenanceKind.GENERAL_KNOWLEDGE,
        ProvenanceKind.CATALOG_METADATA,
    ]


async def test_general_answer_drops_unknown_catalog_id_but_keeps_general_answer() -> None:
    output = _answer("这是一条仍然可用的通用建议。")
    output["catalog_ids"] = ["invented-course"]
    catalog = ReviewedCourseCatalogStore(ReviewedFileStudyKitStore())
    service = GeneralAssistanceService(
        FakeStructuredModel(output),
        course_knowledge=ReviewedCourseKnowledgeStore(catalog),
    )

    result = await service.answer(
        messages=[ChatMessage(role="user", content="我该怎么安排学习？")]
    )

    assert result.catalog_ids == []
    assert result.answer == "这是一条仍然可用的通用建议。"
    assert [claim.provenance for claim in result.claims] == [
        ProvenanceKind.GENERAL_KNOWLEDGE
    ]
