from __future__ import annotations

import hashlib
import json

import pytest

from app.agent.contracts import StudyKitCourseIdentity
from app.catalog.archive import StudyKitArchive
from app.retrieval.source_chunks import (
    AccessScope,
    SourceChunkReference,
    SQLiteSourceChunkStore,
)
from scripts.build_source_chunk_index import build_index


def _approved_archive(tmp_path):
    source = tmp_path / "sources" / "course-a" / "lecture-01" / "chunks.jsonl"
    source.parent.mkdir(parents=True)
    chunk = {
        "chunk_id": "heading-1",
        "material_set_id": "set-1",
        "scope": "public",
        "owner_id": None,
        "course_id": "course-a",
        "course_version": "v1",
        "unit_id": "lecture-01",
        "source_id": "notes",
        "anchor": {"type": "heading", "value": "## Intro"},
        "heading": "## Intro",
        "content": "Approved exact evidence.",
        "content_type": "text",
        "parser_version": "test",
        "parse_warnings": [],
    }
    source.write_text(json.dumps(chunk) + "\n", encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = {
        "run": {
            "fingerprint_payload": {
                "units": [
                    {
                        "unit_id": "lecture-01",
                        "source_id": "notes",
                        "chunks_path": str(source.relative_to(tmp_path)),
                        "chunks_sha256": source_hash,
                    }
                ]
            }
        }
    }
    database = tmp_path / "archive.sqlite3"
    archive = StudyKitArchive(database)
    archive.initialize()
    document_json = json.dumps({"unit_id": "lecture-01"}, separators=(",", ":"))
    document_hash = hashlib.sha256(document_json.encode()).hexdigest()
    aggregate = hashlib.sha256(
        f"lecture-01:{document_hash}".encode()
    ).hexdigest()
    with archive.connect() as connection:
        connection.execute(
            """
            INSERT INTO studykit_builds
            (build_id, course_id, course_version, build_status, review_status,
             schema_id, quality_mode, delivery_policy, unit_count, content_sha256,
             imported_at, source_label, metadata_json)
            VALUES (?, ?, ?, 'succeeded', 'approved', 'portable-v0.2.2',
                    'standard', 'published', 1, ?, 'now', 'test', ?)
            """,
            ("a" * 64, "course-a", "v1", aggregate, json.dumps(metadata)),
        )
        connection.execute(
            """
            INSERT INTO studykit_documents
            (course_id, course_version, unit_id, build_id, title, document_status,
             review_status, schema_id, document_sha256, document_json, learner_markdown)
            VALUES ('course-a', 'v1', 'lecture-01', ?, 'Intro', 'published',
                    'approved', 'portable-v0.2.2', ?, ?, NULL)
            """,
            ("a" * 64, document_hash, document_json),
        )
    return database, source


def test_build_index_uses_only_hash_bound_approved_chunks(tmp_path) -> None:
    database, _ = _approved_archive(tmp_path)
    output = tmp_path / "indexes" / "source_chunks.sqlite3"

    count = build_index(database, output, tmp_path)
    resolved = SQLiteSourceChunkStore(output).resolve_exact(
        [
            SourceChunkReference(
                source_id="notes",
                anchor_type="heading",
                anchor_value="## Intro",
            )
        ],
        AccessScope(),
        StudyKitCourseIdentity(
            course_id="course-a", course_version="v1", unit_id="lecture-01"
        ),
    )

    assert count == 1
    assert [chunk.chunk_id for chunk in resolved] == ["heading-1"]


def test_build_index_rejects_source_hash_drift(tmp_path) -> None:
    database, source = _approved_archive(tmp_path)
    source.write_text(source.read_text() + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="chunks_sha256 mismatch"):
        build_index(database, tmp_path / "index.sqlite3", tmp_path)
