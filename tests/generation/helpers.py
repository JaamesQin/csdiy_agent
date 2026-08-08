from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from app.generation.model import ModelResponse
from app.generation.result import GenerationRequest
from app.retrieval.schema_validation import load_yaml

ROOT = Path(__file__).parents[2]
GOLDEN = (
    ROOT / "data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml"
)


def draft_candidate() -> dict[str, Any]:
    candidate = deepcopy(load_yaml(GOLDEN))
    candidate["status"] = "draft"
    candidate["review"] = {
        "human_review_status": "pending",
        "human_reviewed_at": None,
        "generator_review_status": "pending",
    }
    return candidate


def source_chunks(
    *,
    count: int = 81,
    course_id: str | None = "mit-6.7960-fall-2024",
    course_version: str | None = "fall-2024",
    unit_id: str = "lecture-02",
    source_id: str = "mit-6.7960-f24-lecture-02-slides",
    material_set_id: str = "mit-6.7960-f24-lecture-02",
) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": f"{source_id}-p{page:03d}",
            "material_set_id": material_set_id,
            "scope": "public",
            "owner_id": None,
            "course_id": course_id,
            "course_version": course_version,
            "unit_id": unit_id,
            "source_id": source_id,
            "anchor": {"type": "page", "value": page},
            "heading": f"Page {page}",
            "content": f"Evidence from page {page}.",
            "content_type": "mixed",
            "parser_version": "test-v0.1",
            "parse_warnings": [],
        }
        for page in range(1, count + 1)
    ]


def generation_request(candidate: dict[str, Any] | None = None) -> GenerationRequest:
    candidate = candidate or draft_candidate()
    return GenerationRequest(
        course_id=candidate["course_id"],
        course_version=candidate["course_version"],
        unit_id=candidate["unit_id"],
        included_sources=tuple(candidate["scope"]["included_sources"]),
        material_set_id="mit-6.7960-f24-lecture-02",
        target_minutes=180,
    )


def model_response(output: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        output=deepcopy(output),
        raw_content="{}",
        model="fake-deepseek",
        finish_reason="stop",
        usage={"total_tokens": 42},
        request_id="fake-request",
    )


def evidence_plan() -> dict[str, Any]:
    chunks = source_chunks()
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    segments = []
    for index, start in enumerate((1, 17, 33, 49, 65), start=1):
        end = 81 if index == 5 else start + 15
        segments.append(
            {
                "id": f"segment-{index:02d}",
                "topic": f"讲次内容 {index}",
                "pages": f"{start}–{end}",
                "summary": f"覆盖第 {start}–{end} 页。",
                "chunk_ids": chunk_ids[start - 1 : end],
            }
        )
    concepts = [
        ("gradient-descent", "gradient descent", "梯度下降", 8),
        ("computation-graph", "computation graph", "计算图", 26),
        ("backpropagation", "backpropagation", "反向传播", 44),
        ("branch-sum", "gradient summation at branches", "分支处的梯度求和", 55),
        ("diff-programming", "differentiable programming", "可微编程", 57),
    ]
    requirements = [
        {
            "id": f"requirement-{index:02d}",
            "description": f"证明{term_zh}的核心理解。",
            "concept_ids": [concept_id],
            "chunk_ids": [chunk_ids[page - 1]],
            "control_ids": (
                ["control-representation"] if index == 4 else []
            ),
        }
        for index, (concept_id, _term_en, term_zh, page) in enumerate(
            concepts, start=1
        )
    ]
    concept_candidates = [
        {
            "id": concept_id,
            "term_en": term_en,
            "term_zh": term_zh,
            "priority": "core",
            "summary": f"{term_zh}的核心关系。",
            "chunk_ids": chunk_ids[index::len(concepts)],
            "control_ids": (
                ["control-representation"] if index == 3 else []
            ),
        }
        for index, (concept_id, term_en, term_zh, _page) in enumerate(concepts)
    ]
    content_ids = chunk_ids
    golden_practices = draft_candidate()["practice"]
    opportunity_chunks = []
    for opportunity_index, (_id, _en, _zh, page) in enumerate(concepts):
        pages = {page}
        for practice_index, practice in enumerate(golden_practices):
            if practice_index % len(concepts) == opportunity_index:
                pages.update(practice["source_pages"])
        opportunity_chunks.append(
            [chunk_ids[item - 1] for item in sorted(pages)]
        )
    practice_ids = sorted(
        {chunk_id for values in opportunity_chunks for chunk_id in values}
    )
    return {
        "unit_title_candidate": "Lecture 2: How to Train a Neural Net",
        "lecture_summary": "本讲介绍梯度下降、计算图、反向传播和可微编程。",
        "page_segments": segments,
        "core_concept_candidates": concept_candidates,
        "evidence_controls": [
            {
                "id": "control-representation",
                "control_type": "representation",
                "statement": "相关表示必须以原始资料为准。",
                "required_action": "verify_original",
                "chunk_ids": [chunk_ids[79]],
            }
        ],
        "assessment_requirements": requirements,
        "practice_opportunities": [
            {
                "id": f"opportunity-{index:02d}",
                "practice_type": practice_type,
                "concept_ids": [concepts[index - 1][0]],
                "requirement_ids": [f"requirement-{index:02d}"],
                "description": f"检验{concepts[index - 1][2]}。",
                "chunk_ids": opportunity_chunks[index - 1],
                "control_ids": (
                    ["control-representation"] if index == 4 else []
                ),
            }
            for index, practice_type in enumerate(
                (
                    "concept",
                    "shape_reasoning",
                    "transfer",
                    "symbolic_derivation",
                    "code_reading",
                ),
                start=1,
            )
        ],
        "content_chunk_ids": content_ids,
        "practice_chunk_ids": sorted(
            {*practice_ids, chunk_ids[79]}
        ),
        "limitations": [
            {
                "code": "formula_visual",
                "description": "公式和图形需回看原始资料。",
                "scope": "global",
                "chunk_ids": [chunk_ids[31]],
            }
        ],
    }


def learning_content() -> dict[str, Any]:
    candidate = draft_candidate()
    result = {
        key: deepcopy(candidate.get(key, []))
        for key in (
            "learning_objectives",
            "prerequisites",
            "prerequisite_check",
            "outline",
            "core_concepts",
            "glossary",
            "common_misconceptions",
            "limitations",
        )
    }
    for index, concept in enumerate(result["core_concepts"]):
        concept["evidence_concept_id"] = (
            evidence_plan()["core_concept_candidates"][index % 5]["id"]
        )
    requirement_ids = [
        item["id"] for item in evidence_plan()["assessment_requirements"]
    ]
    for index, objective in enumerate(result["learning_objectives"]):
        objective["requirement_ids"] = [
            requirement_ids[index % len(requirement_ids)]
        ]
    result["limitations"] = []
    return result


def practice_flow() -> dict[str, Any]:
    candidate = draft_candidate()
    practices = deepcopy(candidate["practice"])
    opportunities = evidence_plan()["practice_opportunities"]
    objective_ids = [item["id"] for item in candidate["learning_objectives"]]
    concept_ids = [item["id"] for item in candidate["core_concepts"]]
    for index, item in enumerate(practices):
        opportunity = opportunities[index % len(opportunities)]
        item["opportunity_id"] = opportunity["id"]
        item["practice_type"] = opportunity["practice_type"]
        item["numeric_complexity"] = "none"
        item["objective_ids"] = [objective_ids[index % len(objective_ids)]]
        item["concept_ids"] = [concept_ids[index % len(concept_ids)]]
        item["requirement_ids"] = [
            f"requirement-{(index % 5) + 1:02d}"
        ]
        item["control_ids"] = deepcopy(opportunity["control_ids"])
    sequence = deepcopy(candidate["learning_sequence"])
    activity_types = (
        "prerequisite",
        "content",
        "content",
        "content",
        "review",
        "practice",
    )
    for index, item in enumerate(sequence):
        item["activity_type"] = activity_types[index]
        item["objective_ids"] = [objective_ids[index % len(objective_ids)]]
        item["practice_ids"] = (
            [practice["id"] for practice in practices]
            if activity_types[index] == "practice"
            else []
        )
    return {
        "practice": practices,
        "learning_sequence": sequence,
        "limitations": [],
    }


def quality_audit(*, issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    issues = issues or []
    return {
        "verdict": (
            "fail"
            if any(item["severity"] == "blocker" for item in issues)
            else "pass"
        ),
        "summary": "质量审核完成。",
        "issues": deepcopy(issues),
    }
