from __future__ import annotations

import hashlib
import json

from app.agent.contracts import CourseContext
from app.learning.service import StudyKitLookupService
from app.protocol.schemas import ChatMessage
from app.retrieval.source_chunks import (
    SourceChunk,
    SQLiteSourceChunkStore,
    initialize_source_chunk_index,
)
from tests.agent.helpers import FakeStructuredModel


CONTEXT = CourseContext(
    course_id="ucb-cs61c-spring-2026",
    course_version="spring-2026",
    unit_id="lecture-02",
)


class _OneDocumentStore:
    def __init__(self, document: dict) -> None:
        self.document = document

    def get_ready(self, course_id: str, course_version: str, unit_id: str) -> dict | None:
        if (course_id, course_version, unit_id) == (
            self.document["course_id"],
            self.document["course_version"],
            self.document["unit_id"],
        ):
            return self.document
        return None


def _chunk(
    chunk_id: str,
    text: str,
    *,
    source_id: str,
    anchor_type: str,
    anchor_value: str,
    page: int | None = None,
    course_id: str = CONTEXT.course_id,
) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        course_id=course_id,
        course_version=CONTEXT.course_version,
        unit_id=CONTEXT.unit_id or "",
        source_id=source_id,
        page=page,
        anchor_type=anchor_type,
        anchor_value=anchor_value,
        heading=anchor_value if anchor_type == "heading" else None,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        build_id="approved-build",
    )


def _practice(
    practice_id: str,
    citations: list[dict],
    *,
    feedback_mode: str | None = None,
) -> dict:
    result = {
        "id": practice_id,
        "level": "基础",
        "question": "分别说明 sample 与 quantize 的作用。",
        "hint": "区分时间轴和幅度轴。",
        "deliverable": "用两句话回答。",
        "expected_evidence": ["sample", "quantize"],
        "evaluation": {"full_credit": "完整", "partial_credit": "部分"},
        "citations": citations,
    }
    if feedback_mode is not None:
        result["feedback_mode"] = feedback_mode
    return result


def _document(practices: list[dict]) -> dict:
    return {
        "course_id": CONTEXT.course_id,
        "course_version": CONTEXT.course_version,
        "unit_id": CONTEXT.unit_id,
        "title": "Number Representation",
        "scope": {"included_sources": [{"source_id": "slides"}]},
        "practice": practices,
    }


async def test_cs61c_p1_heading_chunks_support_grounded_feedback(tmp_path) -> None:
    source_id = "lecture-02-6b44e3c2a7"
    sample_id = "lecture-02-6b44e3c2a7-heading-example-storing-data-as-"
    bits_id = "lecture-02-6b44e3c2a7-heading-bits-bytes-and-nibbles"
    citations = [
        {
            "chunk_id": sample_id,
            "source_id": source_id,
            "anchor": {"type": "heading", "value": "### Example: Storing data as digital"},
        },
        {
            "chunk_id": bits_id,
            "source_id": source_id,
            "anchor": {"type": "heading", "value": "## Bits, Bytes, and Nibbles"},
        },
    ]
    index = tmp_path / "source_chunks.sqlite3"
    initialize_source_chunk_index(
        index,
        [
            _chunk(
                sample_id,
                "Sampling records a signal over time; quantization maps amplitude to discrete values.",
                source_id=source_id,
                anchor_type="heading",
                anchor_value="### Example: Storing data as digital",
            ),
            _chunk(
                bits_id,
                "One byte is 8 bits and one nibble is 4 bits.",
                source_id=source_id,
                anchor_type="heading",
                anchor_value="## Bits, Bytes, and Nibbles",
            ),
        ],
    )
    model = FakeStructuredModel(
        {
            "provenance": "course_material",
            "correct_points": ["正确指出了 sample 与时间采样有关。"],
            "correction": "quantize 作用于幅度取值，而不是时间切分。",
            "next_hint": "分别检查横轴和纵轴发生了什么。",
            "citation_ids": [sample_id, bits_id],
        }
    )
    service = StudyKitLookupService(
        _OneDocumentStore(_document([_practice("p1", citations)])),
        model=model,
        source_chunks=SQLiteSourceChunkStore(index),
    )

    result = await service.practice_feedback(
        messages=[ChatMessage(role="user", content="点评 p1。我的答案是 sample 是采样，quantize 是时间切分。")],
        course_context=CONTEXT,
    )

    assert "### 本题点评" in result.answer
    assert "标题“### Example: Storing data as digital”" in result.answer
    assert "未按当前课程材料核验" not in result.answer
    assert "expected_evidence" not in model.calls[0]["user_prompt"]
    assert "evaluation" not in model.calls[0]["user_prompt"]
    assert "区分时间轴和幅度轴" not in model.calls[0]["user_prompt"]
    assert "Sampling records" in model.calls[0]["user_prompt"]
    assert len(model.calls) == 1


async def test_page_evidence_is_rendered_from_verified_chunk(tmp_path) -> None:
    index = tmp_path / "source_chunks.sqlite3"
    initialize_source_chunk_index(
        index,
        [
            _chunk(
                "page-7",
                "Verified page content.",
                source_id="slides",
                anchor_type="page",
                anchor_value="7",
                page=7,
            )
        ],
    )
    model = FakeStructuredModel(
        {
            "provenance": "course_material",
            "correct_points": ["回答触及了关键点。"],
            "correction": None,
            "next_hint": "继续说明作用对象。",
            "citation_ids": ["page-7"],
        }
    )
    service = StudyKitLookupService(
        _OneDocumentStore(
            _document(
                [
                    {
                        **_practice("p-page", []),
                        "source_pages": [7],
                    }
                ]
            )
        ),
        model=model,
        source_chunks=SQLiteSourceChunkStore(index),
    )

    result = await service.practice_feedback(
        messages=[ChatMessage(role="user", content="点评 p-page。我的答案是 sample 处理时间。")],
        course_context=CONTEXT,
    )

    assert "`slides`，第 7 页" in result.answer


async def test_invalid_course_partition_falls_back_to_labeled_general_feedback(tmp_path) -> None:
    index = tmp_path / "source_chunks.sqlite3"
    initialize_source_chunk_index(
        index,
        [
            _chunk(
                "foreign",
                "Other course content.",
                source_id="slides",
                anchor_type="page",
                anchor_value="7",
                page=7,
                course_id="other-course",
            )
        ],
    )
    model = FakeStructuredModel(
        {
            "provenance": "general_knowledge",
            "correct_points": ["回答尝试区分两个动作。"],
            "correction": "需要把量化与幅度离散化联系起来。",
            "next_hint": "考虑每一步改变的是哪个轴。",
            "citation_ids": [],
        }
    )
    service = StudyKitLookupService(
        _OneDocumentStore(
            _document([_practice("p1", [{"chunk_id": "foreign"}])])
        ),
        model=model,
        source_chunks=SQLiteSourceChunkStore(index),
    )

    result = await service.practice_feedback(
        messages=[ChatMessage(role="user", content="点评 p1。我的答案是两个步骤都在切分信号。")],
        course_context=CONTEXT,
    )

    assert "### 通用反馈（未按当前课程材料核验）" in result.answer
    assert "不代表当前课程的标准答案或评分" in result.answer
    assert "evidence" not in model.calls[0]["user_prompt"]
    assert len(model.calls) == 1


async def test_default_selection_prefers_grounded_and_explicit_general_warns(tmp_path) -> None:
    citation = {"chunk_id": "grounded"}
    index = tmp_path / "source_chunks.sqlite3"
    initialize_source_chunk_index(
        index,
        [
            _chunk(
                "grounded",
                "Grounded content.",
                source_id="notes",
                anchor_type="heading",
                anchor_value="## Grounded",
            )
        ],
    )
    document = _document(
        [
            _practice("p-general", [], feedback_mode="general_only"),
            _practice("p-grounded", [citation], feedback_mode="course_grounded"),
        ]
    )
    service = StudyKitLookupService(
        _OneDocumentStore(document),
        source_chunks=SQLiteSourceChunkStore(index),
        practice_rewrite_enabled=False,
    )

    selected = await service.practice_selection(
        messages=[ChatMessage(role="user", content="给我一道练习")],
        course_context=CONTEXT,
    )
    explicit = await service.practice_selection(
        messages=[ChatMessage(role="user", content="查看 p-general")],
        course_context=CONTEXT,
    )

    assert "p-grounded" in selected.answer
    assert "没有可核查的课程材料证据" not in selected.answer
    assert "p-general" in explicit.answer
    assert "没有可核查的课程材料证据" in explicit.answer


async def test_practice_evidence_is_bounded_by_reference_count_and_prompt_size(tmp_path) -> None:
    chunks = [
        _chunk(
            f"chunk-{index}",
            "x" * 10_000,
            source_id="notes",
            anchor_type="heading",
            anchor_value=f"## {index}",
        )
        for index in range(17)
    ]
    index = tmp_path / "source_chunks.sqlite3"
    initialize_source_chunk_index(index, chunks)
    generic_model = FakeStructuredModel(
        {
            "provenance": "general_knowledge",
            "correct_points": ["尝试回答了问题。"],
            "correction": None,
            "next_hint": "缩小回答范围。",
            "citation_ids": [],
        }
    )
    too_many = StudyKitLookupService(
        _OneDocumentStore(
            _document(
                [_practice("p-many", [{"chunk_id": chunk.chunk_id} for chunk in chunks])]
            )
        ),
        model=generic_model,
        source_chunks=SQLiteSourceChunkStore(index),
    )
    result = await too_many.practice_feedback(
        messages=[ChatMessage(role="user", content="点评 p-many。我的答案是尝试区分两个步骤。")],
        course_context=CONTEXT,
    )
    assert "未按当前课程材料核验" in result.answer
    assert "evidence" not in generic_model.calls[0]["user_prompt"]

    grounded_model = FakeStructuredModel(
        {
            "provenance": "course_material",
            "correct_points": ["尝试回答了问题。"],
            "correction": None,
            "next_hint": "继续。",
            "citation_ids": ["chunk-0"],
        }
    )
    bounded = StudyKitLookupService(
        _OneDocumentStore(
            _document(
                [_practice("p-bounded", [{"chunk_id": "chunk-0"}, {"chunk_id": "chunk-1"}])]
            )
        ),
        model=grounded_model,
        source_chunks=SQLiteSourceChunkStore(index),
    )
    await bounded.practice_feedback(
        messages=[ChatMessage(role="user", content="点评 p-bounded。我的答案是尝试区分两个步骤。")],
        course_context=CONTEXT,
    )
    prompt = json.loads(grounded_model.calls[0]["user_prompt"])
    assert sum(len(item["text"]) for item in prompt["evidence"]) == 16_000


async def test_grounded_model_contract_failure_uses_one_deterministic_fallback(tmp_path) -> None:
    index = tmp_path / "source_chunks.sqlite3"
    initialize_source_chunk_index(
        index,
        [
            _chunk(
                "grounded",
                "Grounded content.",
                source_id="notes",
                anchor_type="heading",
                anchor_value="## Grounded",
            )
        ],
    )
    model = FakeStructuredModel({})
    service = StudyKitLookupService(
        _OneDocumentStore(
            _document([_practice("p1", [{"chunk_id": "grounded"}])])
        ),
        model=model,
        source_chunks=SQLiteSourceChunkStore(index),
    )

    result = await service.practice_feedback(
        messages=[ChatMessage(role="user", content="点评 p1。我的答案是尝试区分两个步骤。")],
        course_context=CONTEXT,
    )

    assert "### 本题反馈暂时降级" in result.answer
    assert "已核查课程材料" in result.answer
    assert "标题“## Grounded”" in result.answer
    assert len(model.calls) == 1
