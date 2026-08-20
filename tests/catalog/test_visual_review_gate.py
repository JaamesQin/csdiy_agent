from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reconcile_studykit_build import checkpoint_integrity_issues, reconcile_build, unit_state


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def visual_review_plan() -> dict[str, object]:
    """Small review-pages-v1 record with every required page category."""

    return {
        "quality_mode": "standard",
        "page_selector_version": "review-pages-v1",
        "selected_pages": [1, 2, 3, 4, 6],
        "selection_reasons": {
            "1": ["identity"],
            "2": ["risk_page"],
            "3": ["final_formula"],
            "4": ["final_citation"],
            "6": ["evidence_plan"],
        },
        "risk_pages": [2],
        "required_final_formula_pages": [3],
        "final_citation_pages": [4],
        "hidden_text_pages": [5],
        "actual_reviewed_pages": [1, 2, 3, 4, 6],
    }


@pytest.fixture
def complete_visual_review_unit(tmp_path: Path, visual_review_plan: dict[str, object]) -> Path:
    unit = tmp_path / "unit"
    unit.mkdir()
    _write_json(unit / "05-studykit.json", {"status": "draft"})
    _write_json(unit / "validation.json", {"status": "succeeded"})
    _write_json(unit / "review-validation.json", {"status": "succeeded"})
    _write_json(unit / "review-plan.json", visual_review_plan)
    _write_json(
        unit / "independent-audit.json",
        {
            "auditor_id": "reviewer-1",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": visual_review_plan["actual_reviewed_pages"],
        },
    )
    return unit


def test_review_pages_v1_is_exact_and_covers_all_required_categories(
    visual_review_plan: dict[str, object],
) -> None:
    selected = set(visual_review_plan["selected_pages"])
    actual = set(visual_review_plan["actual_reviewed_pages"])

    assert visual_review_plan["page_selector_version"] == "review-pages-v1"
    assert actual == selected
    assert set(visual_review_plan["risk_pages"]).issubset(actual)
    assert set(visual_review_plan["required_final_formula_pages"]).issubset(actual)
    assert set(visual_review_plan["final_citation_pages"]).issubset(actual)


def test_hidden_text_pages_are_excluded_from_visual_evidence(
    visual_review_plan: dict[str, object],
) -> None:
    actual = set(visual_review_plan["actual_reviewed_pages"])
    hidden = set(visual_review_plan["hidden_text_pages"])

    assert hidden.isdisjoint(actual)
    assert all(reason != "hidden_text" for reasons in visual_review_plan["selection_reasons"].values() for reason in reasons)


def test_review_count_must_match_actual_reviewed_pages(
    complete_visual_review_unit: Path,
) -> None:
    _write_json(
        complete_visual_review_unit / "metrics.json",
        {"reviewed_page_count": 4},
    )

    issues = checkpoint_integrity_issues(complete_visual_review_unit)

    assert any(issue["code"] == "review_count_mismatch" for issue in issues)


@pytest.mark.parametrize(
    ("review_plan", "audit_extra", "expected_pages", "expected_anchors"),
    [
        (
            {"actual_reviewed_pages": [1, 2]},
            {},
            [1, 2],
            None,
        ),
        (
            {"actual_reviewed_pages": [], "actual_reviewed_anchors": ["Lecture 2#binary-search"], "anchor_type": "heading"},
            {"actual_reviewed_anchors": ["Lecture 2#binary-search"], "anchor_type": "heading"},
            [],
            ["Lecture 2#binary-search"],
        ),
    ],
)
def test_visual_review_accepts_pages_or_heading_anchors(
    tmp_path: Path,
    review_plan: dict[str, object],
    audit_extra: dict[str, object],
    expected_pages: list[int],
    expected_anchors: list[str] | None,
) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    _write_json(unit / "05-studykit.json", {"status": "draft"})
    _write_json(unit / "validation.json", {"status": "succeeded"})
    _write_json(unit / "review-validation.json", {"status": "succeeded"})
    _write_json(unit / "review-plan.json", review_plan)
    _write_json(
        unit / "independent-audit.json",
        {"auditor_id": "reviewer-1", "author_id": "author-1", "result": "pass", **audit_extra},
    )

    state = unit_state(unit)

    assert state["state"] == "succeeded"
    assert state["actual_reviewed_pages"] == expected_pages
    assert state["actual_reviewed_anchors"] == expected_anchors


def test_missing_visual_review_blocks_complete(tmp_path: Path) -> None:
    build = tmp_path / "build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    unit.mkdir(parents=True)
    _write_json(unit / "05-studykit.json", {"status": "draft"})
    _write_json(unit / "validation.json", {"status": "succeeded"})
    _write_json(unit / "review-validation.json", {"status": "succeeded"})
    _write_json(
        unit / "independent-audit.json",
        {"auditor_id": "reviewer-1", "author_id": "author-1", "result": "pass"},
    )
    (build / "manifest.yaml").write_text(
        "course_id: demo\nunits:\n  - unit_id: lecture-01\n", encoding="utf-8"
    )
    _write_json(build / "result.json", {"build_id": "build", "status": "partial"})

    summary = reconcile_build(build)
    result = json.loads((build / "result.json").read_text(encoding="utf-8"))

    assert summary["status"] == "failed"
    assert summary["completed_unit_count"] == 0
    assert any(
        issue["code"] == "independent_audit_actual_reviewed_pages_missing"
        for issue in result["issues"]
    )
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False
