from __future__ import annotations

from copy import deepcopy

import pytest

from app.generation.evidence import (
    EvidenceValidationError,
    build_evidence_bundle,
)
from tests.generation.helpers import generation_request, source_chunks


def test_evidence_is_sorted_and_empty_pages_are_not_sent_to_model() -> None:
    chunks = source_chunks(count=3)
    chunks[1]["content"] = " "
    chunks[2]["parse_warnings"] = ["low_extracted_text"]

    bundle = build_evidence_bundle(generation_request(), reversed(chunks))

    assert [chunk["anchor"]["value"] for chunk in bundle.all_chunks] == [1, 2, 3]
    assert [chunk["anchor"]["value"] for chunk in bundle.usable_chunks] == [1, 3]
    assert bundle.parse_warnings == (
        "mit-6.7960-f24-lecture-02-slides-p003:low_extracted_text",
    )


def test_evidence_rejects_mixed_unit_context() -> None:
    chunks = source_chunks(count=2)
    chunks[1]["unit_id"] = "lecture-08"

    with pytest.raises(EvidenceValidationError) as caught:
        build_evidence_bundle(generation_request(), chunks)

    assert "unit_id_mismatch" in {issue.code for issue in caught.value.issues}


def test_evidence_rejects_duplicate_pages() -> None:
    chunks = source_chunks(count=2)
    duplicate = deepcopy(chunks[1])
    duplicate["chunk_id"] = "different-id"
    duplicate["anchor"]["value"] = 1

    with pytest.raises(EvidenceValidationError) as caught:
        build_evidence_bundle(generation_request(), [chunks[0], duplicate])

    assert "duplicate_page" in {issue.code for issue in caught.value.issues}


def test_evidence_requires_at_least_one_chunk() -> None:
    with pytest.raises(EvidenceValidationError) as caught:
        build_evidence_bundle(generation_request(), [])

    assert caught.value.issues[0].code == "no_chunks"
