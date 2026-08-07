"""Validate local SourceChunks and build a bounded generation evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jsonschema

from app.generation.result import GenerationIssue, GenerationRequest
from app.retrieval.schema_validation import load_json

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_CHUNK_SCHEMA = ROOT / "schemas/source_chunk.schema.json"


class EvidenceValidationError(ValueError):
    """Local chunks cannot safely be used for the requested generation."""

    def __init__(self, issues: Iterable[GenerationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(issue.message for issue in self.issues))


@dataclass(frozen=True)
class EvidenceBundle:
    """Validated chunks and the subset safe to expose to the model."""

    all_chunks: tuple[dict[str, Any], ...]
    usable_chunks: tuple[dict[str, Any], ...]
    material_set_id: str
    parse_warnings: tuple[str, ...]

    @property
    def used_chunk_ids(self) -> tuple[str, ...]:
        return tuple(chunk["chunk_id"] for chunk in self.all_chunks)

    def to_prompt_dict(self, *, include_empty: bool = False) -> dict[str, Any]:
        chunks = self.all_chunks if include_empty else self.usable_chunks
        return {
            "material_set_id": self.material_set_id,
            "parse_warnings": list(self.parse_warnings),
            "chunks": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "source_id": chunk["source_id"],
                    "page": chunk["anchor"]["value"],
                    "heading": chunk.get("heading"),
                    "content_type": chunk["content_type"],
                    "parse_warnings": chunk.get("parse_warnings", []),
                    "content": chunk["content"],
                }
                for chunk in chunks
            ],
        }


def _location(path: Iterable[object]) -> str:
    parts = [str(part) for part in path]
    return ".".join(parts) if parts else "$"


def build_evidence_bundle(
    request: GenerationRequest,
    chunks: Iterable[dict[str, Any]],
    *,
    schema_path: Path = DEFAULT_SOURCE_CHUNK_SCHEMA,
) -> EvidenceBundle:
    """Validate identity, page anchors and source scope before model use."""

    materialized = list(chunks)
    if not materialized:
        raise EvidenceValidationError(
            [
                GenerationIssue(
                    stage="evidence",
                    code="no_chunks",
                    message="no SourceChunks were provided",
                )
            ]
        )

    schema = load_json(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    issues: list[GenerationIssue] = []

    for index, chunk in enumerate(materialized):
        for error in sorted(validator.iter_errors(chunk), key=lambda item: list(item.path)):
            issues.append(
                GenerationIssue(
                    stage="evidence",
                    code="invalid_source_chunk",
                    message=error.message,
                    location=f"chunks[{index}].{_location(error.path)}",
                )
            )
    if issues:
        raise EvidenceValidationError(issues)

    source_ids = {chunk["source_id"] for chunk in materialized}
    declared_source_ids = {
        source.get("source_id") for source in request.included_sources
    }
    if None in declared_source_ids or "" in declared_source_ids:
        issues.append(
            GenerationIssue(
                stage="evidence",
                code="invalid_source_metadata",
                message="every included source must have a non-empty source_id",
                location="request.included_sources",
            )
        )
    if source_ids != declared_source_ids:
        issues.append(
            GenerationIssue(
                stage="evidence",
                code="source_scope_mismatch",
                message=(
                    f"chunk sources {sorted(source_ids)} do not match declared sources "
                    f"{sorted(str(item) for item in declared_source_ids)}"
                ),
                location="request.included_sources",
            )
        )
    if len(source_ids) != 1:
        issues.append(
            GenerationIssue(
                stage="evidence",
                code="multiple_sources_unsupported",
                message="the local v0.1 generator requires exactly one source",
            )
        )

    material_set_ids = {chunk["material_set_id"] for chunk in materialized}
    if len(material_set_ids) != 1:
        issues.append(
            GenerationIssue(
                stage="evidence",
                code="mixed_material_sets",
                message="all chunks must belong to one material_set_id",
            )
        )
        material_set_id = ""
    else:
        material_set_id = next(iter(material_set_ids))
        if (
            request.material_set_id is not None
            and material_set_id != request.material_set_id
        ):
            issues.append(
                GenerationIssue(
                    stage="evidence",
                    code="material_set_mismatch",
                    message=(
                        f"chunks use material_set_id {material_set_id!r}, expected "
                        f"{request.material_set_id!r}"
                    ),
                )
            )

    seen_chunk_ids: set[str] = set()
    seen_pages: set[tuple[str, int]] = set()
    for index, chunk in enumerate(materialized):
        if chunk["course_id"] != request.course_id:
            issues.append(
                GenerationIssue(
                    stage="evidence",
                    code="course_id_mismatch",
                    message=f"expected course_id {request.course_id!r}",
                    location=f"chunks[{index}].course_id",
                )
            )
        if chunk["course_version"] != request.course_version:
            issues.append(
                GenerationIssue(
                    stage="evidence",
                    code="course_version_mismatch",
                    message=f"expected course_version {request.course_version!r}",
                    location=f"chunks[{index}].course_version",
                )
            )
        if chunk["unit_id"] != request.unit_id:
            issues.append(
                GenerationIssue(
                    stage="evidence",
                    code="unit_id_mismatch",
                    message=f"expected unit_id {request.unit_id!r}",
                    location=f"chunks[{index}].unit_id",
                )
            )
        if chunk["anchor"]["type"] != "page" or not isinstance(
            chunk["anchor"]["value"], int
        ):
            issues.append(
                GenerationIssue(
                    stage="evidence",
                    code="unsupported_anchor",
                    message="the local v0.1 generator requires integer page anchors",
                    location=f"chunks[{index}].anchor",
                )
            )

        chunk_id = chunk["chunk_id"]
        if chunk_id in seen_chunk_ids:
            issues.append(
                GenerationIssue(
                    stage="evidence",
                    code="duplicate_chunk_id",
                    message=f"duplicate chunk_id {chunk_id!r}",
                    location=f"chunks[{index}].chunk_id",
                )
            )
        seen_chunk_ids.add(chunk_id)

        if chunk["anchor"]["type"] == "page" and isinstance(
            chunk["anchor"]["value"], int
        ):
            page_key = (chunk["source_id"], chunk["anchor"]["value"])
            if page_key in seen_pages:
                issues.append(
                    GenerationIssue(
                        stage="evidence",
                        code="duplicate_page",
                        message=(
                            f"duplicate page {page_key[1]} for source {page_key[0]!r}"
                        ),
                        location=f"chunks[{index}].anchor",
                    )
                )
            seen_pages.add(page_key)

    if issues:
        raise EvidenceValidationError(issues)

    ordered = tuple(
        sorted(
            materialized,
            key=lambda chunk: (chunk["source_id"], chunk["anchor"]["value"]),
        )
    )
    usable = tuple(chunk for chunk in ordered if chunk["content"].strip())
    if not usable:
        raise EvidenceValidationError(
            [
                GenerationIssue(
                    stage="evidence",
                    code="no_usable_chunks",
                    message="all SourceChunks have empty content",
                )
            ]
        )

    warnings = tuple(
        f"{chunk['chunk_id']}:{warning}"
        for chunk in ordered
        for warning in chunk.get("parse_warnings", [])
    )
    return EvidenceBundle(
        all_chunks=ordered,
        usable_chunks=usable,
        material_set_id=material_set_id,
        parse_warnings=warnings,
    )
