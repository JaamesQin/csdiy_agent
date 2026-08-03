from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import ValidationError

from app.retrieval.schema_validation import validate_instance, validate_yaml

ROOT = Path(__file__).parents[2]


def test_lecture_02_studykit_matches_schema() -> None:
    studykit = ROOT / "data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml"
    schema = ROOT / "schemas/studykit.schema.json"

    result = validate_yaml(studykit, schema)

    assert result["unit_id"] == "lecture-02"
    assert result["practice_feedback_policy"]["persistence"] == "none"


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
