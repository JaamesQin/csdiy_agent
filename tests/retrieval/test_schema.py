from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from app.retrieval.schema_validation import validate_instance, validate_yaml
from tests.generation.helpers import evidence_plan

ROOT = Path(__file__).parents[2]


def test_lecture_02_studykit_matches_schema() -> None:
    studykit = ROOT / "data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml"
    schema = ROOT / "schemas/studykit.schema.json"

    result = validate_yaml(studykit, schema)

    assert result["unit_id"] == "lecture-02"
    assert result["practice_feedback_policy"]["persistence"] == "none"


def test_lecture_08_studykit_matches_schema() -> None:
    studykit = ROOT / "data/golden/mit-6.7960-fall-2024-lecture-08-studykit.yaml"
    schema = ROOT / "schemas/studykit.schema.json"

    result = validate_yaml(studykit, schema)

    assert result["unit_id"] == "lecture-08"


def test_private_chunk_requires_owner() -> None:
    schema = ROOT / "schemas/source_chunk.schema.json"
    chunk = {
        "chunk_id": "x-p001",
        "material_set_id": "private-x",
        "scope": "private",
        "owner_id": None,
        "course_id": None,
        "course_version": None,
        "unit_id": "uploaded-unit-01",
        "source_id": "upload-01",
        "anchor": {"type": "page", "value": 1},
        "heading": None,
        "content": "example",
        "content_type": "text",
        "parser_version": "test",
        "parse_warnings": [],
    }

    with pytest.raises(ValidationError):
        validate_instance(chunk, schema)


def test_studykit_rejects_unrenderable_objective_shape() -> None:
    studykit = validate_yaml(
        ROOT / "data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml",
        ROOT / "schemas/studykit.schema.json",
    )
    studykit["learning_objectives"][0] = {
        "id": "obj-invalid",
        "goal": "field name is not renderable",
        "evidence_required": "example",
    }

    with pytest.raises(ValidationError):
        validate_instance(studykit, ROOT / "schemas/studykit.schema.json")


def test_evidence_schema_accepts_all_generic_control_types() -> None:
    schema = ROOT / "schemas/evidence-plan.schema.json"
    control_types = (
        "convention",
        "assumption",
        "ordering",
        "terminology",
        "representation",
        "unit",
        "source_quality",
        "scope_boundary",
        "other",
    )

    for control_type in control_types:
        candidate = deepcopy(evidence_plan())
        candidate["evidence_controls"][0]["control_type"] = control_type
        validate_instance(candidate, schema)
