from __future__ import annotations

import yaml
import pytest

from app.catalog.courses import CatalogDataError, ReviewedCourseCatalogStore
from app.catalog.studykits import ReviewedFileStudyKitStore


def test_store_loads_only_reviewed_golden_studykits() -> None:
    store = ReviewedFileStudyKitStore()

    lecture_2 = store.get_ready(
        "mit-6.7960-fall-2024", "fall-2024", "lecture-02"
    )
    lecture_8 = store.get_ready(
        "mit-6.7960-fall-2024", "fall-2024", "lecture-08"
    )

    assert lecture_2 is not None
    assert lecture_2["review"]["human_review_status"] == "approved"
    assert lecture_8 is not None
    assert store.get_ready(
        "mit-6.7960-fall-2024", "fall-2024", "lecture-01"
    ) is None


def test_store_resolves_only_known_course_context() -> None:
    store = ReviewedFileStudyKitStore()

    matched = store.match_context(["请看 MIT 6.7960 第 2 讲"])

    assert matched is not None
    assert matched.unit_id == "lecture-02"
    assert store.resolve_context(course_id="invented-course") is None
    assert store.match_context(["请看第 99 讲"]) is None


def test_page_reference_is_not_mistaken_for_a_unit() -> None:
    store = ReviewedFileStudyKitStore()

    matched = store.match_context(["MIT 6.7960 的讲义第 8 页说了什么？"])

    assert matched is not None
    assert matched.course_id == "mit-6.7960-fall-2024"
    assert matched.unit_id is None


def test_ready_summaries_are_typed_and_stably_sorted() -> None:
    ready = ReviewedFileStudyKitStore().list_ready(
        course_id="mit-6.7960-fall-2024",
        course_version="fall-2024",
    )

    assert [item.unit_id for item in ready] == ["lecture-02", "lecture-08"]
    assert all(item.official_url and item.official_url.startswith("https://") for item in ready)


def test_course_catalog_separates_catalog_authoring_and_online_status() -> None:
    catalog = ReviewedCourseCatalogStore(ReviewedFileStudyKitStore())

    courses = catalog.list_courses()
    deep_learning = catalog.get("mit-6-7960")
    operating_systems = catalog.get("mit-6-s081")

    assert len(courses) == 119
    assert deep_learning is not None
    assert deep_learning.authoring_status == "authoring"
    assert [item.unit_id for item in deep_learning.online_studykits] == [
        "lecture-02",
        "lecture-08",
    ]
    assert deep_learning.official_url and "ocw.mit.edu" in deep_learning.official_url
    assert operating_systems is not None
    assert operating_systems.authoring_status == "authoring"
    assert operating_systems.online_studykits == []


def test_course_catalog_search_is_exact_directional_and_stable() -> None:
    catalog = ReviewedCourseCatalogStore(ReviewedFileStudyKitStore())

    exact = catalog.match_explicit("我想查看 MIT 6.7960")
    first = catalog.search("推荐深度学习课程", directions=("ml_ai",), limit=3)
    second = catalog.search("推荐深度学习课程", directions=("ml_ai",), limit=3)

    assert exact[0].catalog_id == "mit-6-7960"
    assert [item.catalog_id for item in first] == [item.catalog_id for item in second]
    assert len(first) == 3
    assert first[0].online_ready is True


def test_course_catalog_fails_closed_on_duplicate_identity(tmp_path) -> None:
    target = {
        "canonical_course_id": "duplicate",
        "title": "Duplicate Course",
        "institution": None,
        "course_numbers": [],
        "aliases": ["Duplicate Course"],
        "guide_page_provenance": [
            {
                "leaf_key": "测试::Duplicate::docs/duplicate.md",
                "public_page_url": "https://csdiy.wiki/docs/duplicate",
            }
        ],
        "state": "classified",
        "audit": {"classification": "pending_independent_audit"},
        "manifest_path": None,
    }
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        yaml.safe_dump({"course_targets": [target, target]}, allow_unicode=True),
        encoding="utf-8",
    )
    catalog = ReviewedCourseCatalogStore(
        ReviewedFileStudyKitStore(),
        registry_path=registry,
        repository_root=tmp_path,
    )

    with pytest.raises(CatalogDataError, match="duplicate catalog id"):
        catalog.list_courses()


def test_course_catalog_rejects_manifest_identity_mismatch(tmp_path) -> None:
    manifest_dir = tmp_path / "data" / "manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "wrong.yaml").write_text(
        yaml.safe_dump(
            {
                "course_id": "unrelated-course-fall-2024",
                "course_version": "fall-2024",
                "primary_course_number": "OTHER-101",
                "official_url": "https://example.edu/course",
            }
        ),
        encoding="utf-8",
    )
    target = {
        "canonical_course_id": "mit-6-7960",
        "title": "MIT 6.7960",
        "institution": "Massachusetts Institute of Technology",
        "course_numbers": ["6.7960"],
        "aliases": ["MIT 6.7960"],
        "guide_page_provenance": [
            {
                "leaf_key": "深度学习::MIT 6.7960::docs/course.md",
                "public_page_url": "https://csdiy.wiki/docs/course",
            }
        ],
        "state": "sources_inventoried",
        "audit": {"classification": "pending_independent_audit"},
        "manifest_path": "data/manifests/wrong.yaml",
    }
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        yaml.safe_dump({"course_targets": [target]}, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(CatalogDataError, match="does not match"):
        ReviewedCourseCatalogStore(
            ReviewedFileStudyKitStore(),
            registry_path=registry,
            repository_root=tmp_path,
        ).list_courses()
