from __future__ import annotations

import hashlib

import pytest

from app.agent.contracts import StudyKitCourseIdentity
from app.retrieval.source_chunks import (
    AccessScope,
    SourceChunk,
    SourceChunkReference,
    SourceChunkRetriever,
    SQLiteSourceChunkStore,
    initialize_source_chunk_index,
)
from tests.agent.helpers import FakeStructuredModel


def _chunk(
    chunk_id: str,
    text: str,
    *,
    page: int | None,
    course: str = "course-a",
    anchor_type: str | None = None,
    anchor_value: str | None = None,
) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        course_id=course,
        course_version="v1",
        unit_id="lecture-01",
        source_id="slides",
        page=page,
        anchor_type=anchor_type,
        anchor_value=anchor_value,
        heading=anchor_value if anchor_type == "heading" else None,
        text=text,
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        build_id="approved-build",
    )


def test_source_chunk_search_filters_identity_and_page_before_ranking(tmp_path) -> None:
    path = tmp_path / "chunks.sqlite3"
    initialize_source_chunk_index(
        path,
        [
            _chunk("a-1", "transaction serializability schedule", page=4),
            _chunk("a-2", "transaction recovery log", page=8),
            _chunk("b-1", "transaction private-looking text", page=4, course="course-b"),
        ],
    )
    store = SQLiteSourceChunkStore(path)

    hits = store.search(
        "transaction",
        AccessScope(),
        StudyKitCourseIdentity(
            course_id="course-a", course_version="v1", unit_id="lecture-01"
        ),
        page_filter=4,
        limit=5,
    )

    assert [hit.chunk.chunk_id for hit in hits] == ["a-1"]


def test_private_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="private retrieval"):
        AccessScope(owner="account:123")


async def test_retriever_rewrites_and_reranks_only_filtered_candidates(tmp_path) -> None:
    path = tmp_path / "chunks.sqlite3"
    initialize_source_chunk_index(
        path,
        [
            _chunk("a-1", "transaction serializability schedule", page=4),
            _chunk("a-2", "transaction recovery log", page=4),
            _chunk("b-1", "transaction recovery private", page=4, course="course-b"),
        ],
    )
    model = FakeStructuredModel(
        {"queries": ["transaction recovery"]},
        {"ranked_chunk_ids": ["a-2", "a-1"]},
    )
    retriever = SourceChunkRetriever(SQLiteSourceChunkStore(path), model)

    hits = await retriever.retrieve(
        "transaction",
        AccessScope(),
        StudyKitCourseIdentity(
            course_id="course-a", course_version="v1", unit_id="lecture-01"
        ),
        page_filter=4,
        limit=2,
    )

    assert [hit.chunk.chunk_id for hit in hits] == ["a-2", "a-1"]
    assert "b-1" not in model.calls[1]["user_prompt"]


def test_exact_resolution_supports_chunk_id_and_heading_with_identity_filter(tmp_path) -> None:
    path = tmp_path / "chunks.sqlite3"
    initialize_source_chunk_index(
        path,
        [
            _chunk("a-page", "page evidence", page=4),
            _chunk(
                "a-heading",
                "heading evidence",
                page=None,
                anchor_type="heading",
                anchor_value="## Evidence",
            ),
            _chunk("b-page", "other course", page=4, course="course-b"),
        ],
    )
    store = SQLiteSourceChunkStore(path)
    identity = StudyKitCourseIdentity(
        course_id="course-a", course_version="v1", unit_id="lecture-01"
    )

    resolved = store.resolve_exact(
        [
            SourceChunkReference(chunk_id="a-page"),
            SourceChunkReference(
                source_id="slides",
                anchor_type="heading",
                anchor_value="## Evidence",
            ),
            SourceChunkReference(chunk_id="b-page"),
        ],
        AccessScope(),
        identity,
    )

    assert [chunk.chunk_id for chunk in resolved] == ["a-page", "a-heading"]


def test_exact_resolution_rejects_mismatched_anchor_hash_and_review(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "chunks.sqlite3"
    initialize_source_chunk_index(path, [_chunk("a-1", "trusted", page=4)])
    identity = StudyKitCourseIdentity(
        course_id="course-a", course_version="v1", unit_id="lecture-01"
    )
    store = SQLiteSourceChunkStore(path)

    mismatch = store.resolve_exact(
        [
            SourceChunkReference(
                chunk_id="a-1",
                source_id="slides",
                anchor_type="page",
                anchor_value="5",
            )
        ],
        AccessScope(),
        identity,
    )
    assert mismatch == []

    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE source_chunks SET text='tampered' WHERE chunk_id='a-1'")
    assert store.resolve_exact(
        [SourceChunkReference(chunk_id="a-1")], AccessScope(), identity
    ) == []

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "UPDATE source_chunks SET review_status='approved', scope='private' "
            "WHERE chunk_id='a-1'"
        )
    assert store.resolve_exact(
        [SourceChunkReference(chunk_id="a-1")], AccessScope(), identity
    ) == []

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "UPDATE source_chunks SET scope='public', build_status='failed' "
            "WHERE chunk_id='a-1'"
        )
    assert store.resolve_exact(
        [SourceChunkReference(chunk_id="a-1")], AccessScope(), identity
    ) == []

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "UPDATE source_chunks SET build_status='succeeded', index_allowed=0 "
            "WHERE chunk_id='a-1'"
        )
    assert store.resolve_exact(
        [SourceChunkReference(chunk_id="a-1")], AccessScope(), identity
    ) == []

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "UPDATE source_chunks SET text='trusted', review_status='validated_draft' "
            "WHERE chunk_id='a-1'"
        )
    assert store.resolve_exact(
        [SourceChunkReference(chunk_id="a-1")], AccessScope(), identity
    ) == []
