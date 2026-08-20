from __future__ import annotations

import json

from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.knowledge import (
    MAX_COURSE_INDEX_CHARACTERS,
    MAX_RELEVANT_COURSES,
    ReviewedCourseKnowledgeStore,
    bounded_course_details,
    compact_course_index,
)
from app.catalog.studykits import ReviewedFileStudyKitStore


def _store() -> ReviewedCourseKnowledgeStore:
    catalog = ReviewedCourseCatalogStore(ReviewedFileStudyKitStore())
    return ReviewedCourseKnowledgeStore(catalog)


def test_course_knowledge_projects_every_current_registry_identity() -> None:
    store = _store()

    index = store.list_index()
    compact = compact_course_index(index)
    serialized = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))

    assert len(index) == 119
    assert len({item.catalog_id for item in index}) == 119
    assert len(serialized) <= MAX_COURSE_INDEX_CHARACTERS
    assert any(item.catalog_id == "ucb-cs61a" for item in index)


def test_course_knowledge_detail_excludes_internal_registry_controls() -> None:
    detail = _store().get_detail("ucb-cs61a")

    assert detail is not None
    serialized = detail.model_dump_json()
    for forbidden in (
        "candidate_offerings",
        "source_markdown_path",
        "page_sha256",
        "audit",
        "next_action",
        "build_id",
    ):
        assert forbidden not in serialized
    assert detail.navigation_url.startswith("https://csdiy.wiki/")


def test_relevant_details_prioritize_continuity_and_remain_bounded() -> None:
    details = _store().relevant_details(
        "这些适合我吗",
        directions=("systems",),
        preferred_ids=("ucb-cs61c", "mit-6-s081"),
    )

    assert [item.course.catalog_id for item in details[:2]] == [
        "ucb-cs61c",
        "mit-6-s081",
    ]
    assert len(details) <= MAX_RELEVANT_COURSES
    assert len(bounded_course_details(details)) == len(details)


def test_relevant_details_expand_direction_from_natural_query() -> None:
    details = _store().relevant_details("推荐一些数据库和系统课程")

    assert details
    assert any(
        item.course.major_direction in {"databases", "operating_systems", "architecture"}
        for item in details
    )
