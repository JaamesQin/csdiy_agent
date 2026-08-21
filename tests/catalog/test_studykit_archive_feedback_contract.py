from __future__ import annotations

import hashlib
import json

from app.catalog.archive import StudyKitArchive, canonical_json_bytes, sha256_bytes
from scripts import approve_studykit_archive as approval


def _citation(value: str = "Intro") -> dict:
    return {"source_id": "notes", "anchor": {"type": "heading", "value": value}}


def _document(*, mode: str, citation_value: str = "Intro") -> dict:
    citation = _citation(citation_value)
    return {
        "studykit_version": "0.2.2",
        "status": "published",
        "course_id": "course-a",
        "course_version": "v1",
        "unit_id": "lecture-01",
        "title": "Intro",
        "language": "zh-CN",
        "scope": {
            "included_sources": [
                {
                    "source_id": "notes",
                    "title": "Notes",
                    "type": "text",
                    "sha256": "a" * 64,
                }
            ],
            "citation_anchor_types": ["heading"],
        },
        "learning_objectives": [{"id": "o1", "objective": "Explain"}],
        "prerequisites": [],
        "outline": [{"order": 1, "topic": "Intro", "anchors": [citation], "purpose": "Learn"}],
        "core_concepts": [
            {
                "id": "c1",
                "term": "Intro",
                "claim_type": "source",
                "explanation": "Supported",
                "citations": [citation],
            }
        ],
        "glossary": [],
        "learning_sequence": [
            {"step": 1, "activity": "Read", "duration_minutes": 5, "citations": [citation]}
        ],
        "practice": [
            {
                "id": "p1",
                "level": "recall",
                "question": "Explain it",
                "hint": "Read",
                "deliverable": "Text",
                "expected_evidence": ["Meaning"],
                "evaluation": {"full_credit": "Correct"},
                "feedback_mode": mode,
                "citations": [citation] if mode == "course_grounded" else [],
            }
        ],
        "practice_feedback_policy": {
            "scope": "current_answer_only",
            "persistence": "none",
            "aggregate_accuracy": "disabled",
            "aggregate_mastery": "disabled",
        },
        "citations": [{**citation, "citation_id": "cite-1", "supports": "Intro"}],
        "review": {"generator_review_status": "passed", "audit_findings": []},
        "limitations": [],
    }


def _archive_fixture(tmp_path, *, mode: str, citation_value: str = "Intro"):
    source = tmp_path / "sources" / "chunks.jsonl"
    source.parent.mkdir(parents=True)
    chunk = {
        "chunk_id": "chunk-intro",
        "material_set_id": "set-1",
        "scope": "public",
        "owner_id": None,
        "course_id": "course-a",
        "course_version": "v1",
        "unit_id": "lecture-01",
        "source_id": "notes",
        "anchor": {"type": "heading", "value": "Intro"},
        "heading": "Intro",
        "content": "Supported",
        "content_type": "text",
        "parser_version": "test",
        "parse_warnings": [],
    }
    source.write_text(json.dumps(chunk) + "\n", encoding="utf-8")
    chunks_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    build_id = "b" * 64
    units = ["lecture-01"]
    metadata = {
        "result": {
            "status": "succeeded",
            "failed_units": [],
            "pending_units": [],
            "requested_units": units,
            "completed_units": units,
            "validated_units": units,
            "audited_units": units,
        },
        "run": {
            "fingerprint_payload": {
                "units": [
                    {
                        "unit_id": "lecture-01",
                        "chunks_path": str(source.relative_to(tmp_path)),
                        "chunks_sha256": chunks_hash,
                    }
                ]
            }
        },
    }
    document_json = canonical_json_bytes(
        _document(mode=mode, citation_value=citation_value)
    ).decode("utf-8")
    document_hash = sha256_bytes(document_json.encode("utf-8"))
    aggregate = sha256_bytes(f"lecture-01:{document_hash}".encode("utf-8"))
    database = tmp_path / "archive.sqlite3"
    archive = StudyKitArchive(database)
    archive.initialize()
    reports = {
        "courses/course-a/units/lecture-01/validation.json": {
            "status": "succeeded",
            "issues": [],
        },
        "courses/course-a/units/lecture-01/review-validation.json": {
            "status": "succeeded",
            "issues": [],
        },
    }
    with archive.connect() as connection:
        connection.execute(
            """
            INSERT INTO studykit_builds
            (build_id, course_id, course_version, build_status, review_status,
             schema_id, quality_mode, delivery_policy, unit_count, content_sha256,
             imported_at, source_label, metadata_json)
            VALUES (?, 'course-a', 'v1', 'succeeded', 'validated_draft',
                    'portable-v0.2.2', 'standard', 'published', 1, ?, 'now', 'test', ?)
            """,
            (build_id, aggregate, json.dumps(metadata)),
        )
        connection.execute(
            """
            INSERT INTO studykit_documents
            (course_id, course_version, unit_id, build_id, title, document_status,
             review_status, schema_id, document_sha256, document_json, learner_markdown)
            VALUES ('course-a', 'v1', 'lecture-01', ?, 'Intro', 'published',
                    'validated_draft', 'portable-v0.2.2', ?, ?, NULL)
            """,
            (build_id, document_hash, document_json),
        )
        for relative_path, report in reports.items():
            content = canonical_json_bytes(report)
            connection.execute(
                """
                INSERT INTO studykit_artifacts
                (build_id, relative_path, unit_id, media_type, byte_size, sha256, content)
                VALUES (?, ?, 'lecture-01', 'application/json', ?, ?, ?)
                """,
                (build_id, relative_path, len(content), sha256_bytes(content), content),
            )
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "target_reports": [
                    {
                        "build_id": build_id,
                        "unit_count": 1,
                        "validated_unit_count": 1,
                        "audit_passed_unit_count": 1,
                        "missing_audit_units": [],
                        "audited_units": units,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return database, registry


def test_feedback_contract_rejects_more_than_sixteen_exact_references() -> None:
    document = _document(mode="course_grounded")
    document["practice"][0]["citations"] = [
        _citation(f"Heading {index}") for index in range(17)
    ]
    chunks = [
        {
            "chunk_id": f"chunk-{index}",
            "scope": "public",
            "course_id": "course-a",
            "course_version": "v1",
            "unit_id": "lecture-01",
            "source_id": "notes",
            "anchor": {"type": "heading", "value": f"Heading {index}"},
            "content": "Supported",
            "content_type": "text",
            "parse_warnings": [],
        }
        for index in range(17)
    ]

    report = approval.evaluate_feedback_contract(document, chunks)

    assert report["unresolved"] == 1
    assert {
        issue["code"] for issue in report["issues"]
    } == {"practice_evidence_limit_exceeded"}


def test_release_gate_accepts_and_counts_general_only(tmp_path, monkeypatch) -> None:
    database, registry = _archive_fixture(tmp_path, mode="general_only")
    monkeypatch.setattr(approval, "ROOT", tmp_path)

    result = approval.evaluate_archive(database, registry)

    assert result["eligible_build_count"] == 1
    assert result["practice_feedback_contract"]["general_only"] == 1
    assert result["practice_feedback_contract"]["unresolved"] == 0
    assert result["builds"][0]["warnings"] == [
        "lecture-01:general_only_practices=1"
    ]


def test_release_gate_blocks_unresolved_grounded_evidence(tmp_path, monkeypatch) -> None:
    database, registry = _archive_fixture(
        tmp_path, mode="course_grounded", citation_value="Missing"
    )
    monkeypatch.setattr(approval, "ROOT", tmp_path)

    result = approval.evaluate_archive(database, registry)

    assert result["eligible_build_count"] == 0
    build = result["builds"][0]
    assert "lecture-01:practice_feedback_evidence_unresolved" in build["reasons"]
    assert build["practice_feedback_contract"]["unresolved"] == 1
