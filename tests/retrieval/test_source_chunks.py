from __future__ import annotations

import hashlib

import pytest

from app.agent.contracts import StudyKitCourseIdentity
from app.retrieval.source_chunks import (
    AccessScope,
    SourceChunk,
    SourceChunkRetriever,
    SQLiteSourceChunkStore,
    initialize_source_chunk_index,
)
from tests.agent.helpers import FakeStructuredModel


def _chunk(chunk_id: str, text: str, *, page: int, course: str = "course-a") -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        course_id=course,
        course_version="v1",
        unit_id="lecture-01",
        source_id="slides",
        page=page,
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
