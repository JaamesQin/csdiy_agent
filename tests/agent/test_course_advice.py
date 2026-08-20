from __future__ import annotations

import json

from app.agent.contracts import CourseQuery
from app.catalog.advice import CourseAdviceStore
from app.catalog.contracts import CourseCard, ReadyStudyKitSummary


def _card(catalog_id: str, *, ready: bool) -> CourseCard:
    return CourseCard(
        catalog_id=catalog_id,
        title=catalog_id,
        catalog_review_status="approved",
        authoring_status="complete",
        navigation_url="https://csdiy.wiki/course",
        online_studykits=(
            [
                ReadyStudyKitSummary(
                    course_id="course",
                    course_version="v1",
                    unit_id="lecture-01",
                    title="Lecture",
                )
            ]
            if ready
            else []
        ),
    )


def test_course_fit_does_not_include_online_readiness(tmp_path) -> None:
    path = tmp_path / "advice.json"
    path.write_text(
        json.dumps(
            {
                "courses": [
                    {
                        "catalog_id": "offline-fit",
                        "prerequisites": ["programming"],
                        "difficulty": "introductory",
                        "weekly_minutes": 180,
                        "languages": ["Python"],
                        "learning_outcomes": ["databases"],
                        "provenance": ["human review 2026-08-17"],
                        "review_status": "approved",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    store = CourseAdviceStore(path)
    query = CourseQuery(languages=["Python"], difficulty="introductory")

    results = store.rank(
        [_card("offline-fit", ready=False), _card("online-unknown", ready=True)],
        query,
    )

    assert results[0].catalog_id == "offline-fit"
    assert results[0].target_fit_score > results[1].target_fit_score
    assert results[0].online_ready is False
    assert results[1].online_ready is True
