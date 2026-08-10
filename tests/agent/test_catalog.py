from __future__ import annotations

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
