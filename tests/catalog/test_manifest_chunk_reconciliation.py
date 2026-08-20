from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.generation.evidence import EvidenceValidationError, build_evidence_bundle
from app.generation.result import GenerationRequest
from scripts.audit_csdiy_registry import reconcile_target, unit_source_records
from scripts.prepare_studykit_build import unit_source


COURSE_ID = "fixture-course"
COURSE_VERSION = "spring-2026"
UNIT_ID = "unit-01"
SOURCE_ID = "fixture-source"
MATERIAL_SET_ID = "fixture-course-unit-01"


def _chunk(page: int, *, chunk_id: str | None = None, warnings: list[str] | None = None) -> dict[str, object]:
    return {
        "chunk_id": chunk_id or f"{SOURCE_ID}-p{page:03d}",
        "material_set_id": MATERIAL_SET_ID,
        "scope": "public",
        "owner_id": None,
        "course_id": COURSE_ID,
        "course_version": COURSE_VERSION,
        "unit_id": UNIT_ID,
        "source_id": SOURCE_ID,
        "anchor": {"type": "page", "value": page},
        "heading": f"Page {page}",
        "content": f"Fixture evidence from page {page}.",
        "content_type": "mixed",
        "parser_version": "test-v0.1",
        "parse_warnings": [] if warnings is None else warnings,
    }


@pytest.fixture
def manifest_chunk_fixture(tmp_path: Path) -> tuple[dict[str, object], list[dict[str, object]], Path]:
    raw = tmp_path / "data" / "raw" / "unit-01.pdf"
    prepared = tmp_path / "data" / "raw" / "prepared" / "unit-01.pdf"
    chunks_path = tmp_path / "data" / "sources" / COURSE_ID / UNIT_ID / "chunks.jsonl"
    raw.parent.mkdir(parents=True)
    prepared.parent.mkdir(parents=True)
    chunks_path.parent.mkdir(parents=True)
    raw.write_bytes(b"raw fixture bytes")
    prepared.write_bytes(b"prepared fixture bytes")
    chunks = [_chunk(page) for page in range(1, 4)]
    chunks_path.write_text("\n".join(json.dumps(chunk) for chunk in chunks) + "\n", encoding="utf-8")
    source = {
        "source_id": SOURCE_ID,
        "material_set_id": MATERIAL_SET_ID,
        "local_path": str(prepared.relative_to(tmp_path)),
        "sha256": hashlib.sha256(prepared.read_bytes()).hexdigest(),
        "page_count": 3,
        "chunk_count": 3,
        "anchor_type": "page",
        "chunks_path": str(chunks_path.relative_to(tmp_path)),
    }
    manifest: dict[str, object] = {
        "course_id": COURSE_ID,
        "course_version": COURSE_VERSION,
        "units": [{"unit_id": UNIT_ID, "sources": [source]}],
    }
    return manifest, chunks, tmp_path


def _request() -> GenerationRequest:
    return GenerationRequest(
        course_id=COURSE_ID,
        course_version=COURSE_VERSION,
        unit_id=UNIT_ID,
        included_sources=({"source_id": SOURCE_ID},),
        material_set_id=MATERIAL_SET_ID,
        target_minutes=30,
    )


def _codes(error: EvidenceValidationError) -> set[str]:
    return {issue.code for issue in error.issues}


def test_offline_manifest_reconciles_prepared_hash_and_page_chunk_counts(manifest_chunk_fixture) -> None:
    manifest, _, root = manifest_chunk_fixture

    records = unit_source_records(manifest, root)
    assert records == [{
        "unit_id": UNIT_ID,
        "source_count": 1,
        "raw_path": "data/raw/prepared/unit-01.pdf",
        "raw_exists": True,
        "raw_sha256_matches": True,
        "chunks_path": "data/sources/fixture-course/unit-01/chunks.jsonl",
        "chunks_exists": True,
        "chunk_count": 3,
        "valid_chunk_count": 3,
        "source_page_count": 3,
    }]
    report = reconcile_target({"canonical_course_id": COURSE_ID}, records, [])
    assert report["state"] == "chunked"
    assert report["unit_count"] == 1
    assert report["chunk_count"] == 3
    assert {issue["code"] for issue in report["issues"]} == {"independent_audit_missing"}


def test_manifest_requires_exactly_one_source_and_chunks_share_one_material_set(manifest_chunk_fixture) -> None:
    manifest, chunks, root = manifest_chunk_fixture
    unit = manifest["units"][0]
    unit["sources"].append(dict(unit["sources"][0], source_id="second-source"))

    assert len(unit["sources"]) != 1
    with pytest.raises(ValueError, match="exactly one source"):
        unit_source(unit)

    build_evidence_bundle(_request(), chunks)
    mixed = [dict(chunks[0], material_set_id="other-material-set"), *chunks[1:]]
    with pytest.raises(EvidenceValidationError) as caught:
        build_evidence_bundle(_request(), mixed)
    assert "mixed_material_sets" in _codes(caught.value)


@pytest.mark.parametrize("field", ["course_id", "course_version", "unit_id", "source_id", "material_set_id"])
def test_chunk_identity_must_match_manifest_request(manifest_chunk_fixture, field: str) -> None:
    _, chunks, _ = manifest_chunk_fixture
    mutated = [dict(chunk) for chunk in chunks]
    for chunk in mutated:
        chunk[field] = "wrong-identity"

    with pytest.raises(EvidenceValidationError) as caught:
        build_evidence_bundle(_request(), mutated)
    expected = {
        "source_id": "source_scope_mismatch",
        "material_set_id": "material_set_mismatch",
    }.get(field, f"{field}_mismatch")
    if field == "material_set_id":
        # A uniformly wrong set reaches the request-vs-chunk identity check.
        assert "mixed_material_sets" not in _codes(caught.value)
    assert expected in _codes(caught.value)


def test_page_anchors_are_contiguous_and_warning_arrays_are_explicit(manifest_chunk_fixture) -> None:
    _, chunks, _ = manifest_chunk_fixture
    pages = [int(chunk["anchor"]["value"]) for chunk in chunks]
    assert pages == list(range(1, len(chunks) + 1))
    assert all(chunk["parse_warnings"] == [] for chunk in chunks)

    warning_chunk = dict(chunks[1], parse_warnings=["low_extracted_text"])
    assert warning_chunk["parse_warnings"]
    build_evidence_bundle(_request(), [chunks[0], warning_chunk, chunks[2]])

    gapped = [chunks[0], dict(chunks[2], anchor={"type": "page", "value": 3}), chunks[2]]
    with pytest.raises(EvidenceValidationError) as caught:
        build_evidence_bundle(_request(), gapped)
    assert "duplicate_page" in _codes(caught.value)


def test_duplicate_chunk_ids_are_rejected_offline(manifest_chunk_fixture) -> None:
    _, chunks, _ = manifest_chunk_fixture
    duplicate = [chunks[0], dict(chunks[1], chunk_id=chunks[0]["chunk_id"]), chunks[2]]

    with pytest.raises(EvidenceValidationError) as caught:
        build_evidence_bundle(_request(), duplicate)
    assert "duplicate_chunk_id" in _codes(caught.value)
