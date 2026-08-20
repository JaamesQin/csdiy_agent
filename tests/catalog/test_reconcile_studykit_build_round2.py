from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.reconcile_studykit_build import reconcile_build


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_unit(
    unit: Path,
    *,
    audit_name: str = "independent-audit.json",
    audit: dict[str, object] | None = None,
) -> None:
    _write_json(unit / "05-studykit.json", {"status": "draft"})
    _write_json(unit / "validation.json", {"status": "succeeded"})
    _write_json(unit / "review-validation.json", {"status": "succeeded"})
    _write_json(unit / "review-plan.json", {"actual_reviewed_pages": [1]})
    _write_json(
        unit / audit_name,
        audit
        or {
            "auditor_id": "baseline-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )


def _write_build(build: Path, unit_ids: list[str], repair_unit_ids: list[str]) -> None:
    _write_json(
        build / "repair-plan.json",
        {
            "repair_unit_ids": repair_unit_ids,
            "reused_unit_ids": [unit_id for unit_id in unit_ids if unit_id not in repair_unit_ids],
            "repair_plan_sha256": "round2-plan-sha256",
        },
    )
    (build / "manifest.yaml").write_text(
        yaml.safe_dump(
            {"course_id": "demo", "units": [{"unit_id": unit_id} for unit_id in unit_ids]}
        ),
        encoding="utf-8",
    )
    _write_json(build / "run.json", {"build_id": build.name})


def test_repaired_unit_requires_fresh_audit_even_when_copied_audit_matches_build(
    tmp_path: Path,
) -> None:
    build = tmp_path / "round2-copied-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(
        unit,
        audit={
            "build_id": build.name,
            "repair_plan_sha256": "round2-plan-sha256",
            "auditor_id": "baseline-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )
    _write_build(build, ["lecture-01"], ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    assert summary["completed_units"] == []
    assert summary["pending_units"] == ["lecture-01"]
    result = json.loads((build / "result.json").read_text(encoding="utf-8"))
    assert any(issue["code"] == "repair_fresh_audit_required" for issue in result["issues"])


def test_repaired_unit_passes_only_with_current_fresh_audit_marker(tmp_path: Path) -> None:
    build = tmp_path / "round2-fresh-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(
        unit,
        audit_name="independent-audit.post-repair-2.reaudit.json",
        audit={
            "build_id": build.name,
            "repair_plan_sha256": "round2-plan-sha256",
            "fresh_repair_audit": True,
            "auditor_id": "round2-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )
    _write_build(build, ["lecture-01"], ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]
    record = json.loads((build / "batch-summary.json").read_text(encoding="utf-8"))["unit_records"][0]
    assert record["audit_evidence"]["fresh_repair_audit"] is True


def test_repaired_unit_prefers_current_fresh_audit_over_later_unmarked_sidecar(
    tmp_path: Path,
) -> None:
    build = tmp_path / "round2-fresh-authority-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(
        unit,
        audit={
            "build_id": build.name,
            "repair_plan_sha256": "round2-plan-sha256",
            "fresh_repair_audit": True,
            "auditor_id": "fresh-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
            "audited_at": "2026-08-12T10:00:00+08:00",
        },
    )
    _write_json(
        unit / "independent-audit.round2.xhigh.json",
        {
            "build_id": build.name,
            "repair_plan_sha256": "round2-plan-sha256",
            "auditor_id": "later-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
            "audited_at": "2026-08-12T11:00:00+08:00",
        },
    )
    _write_build(build, ["lecture-01"], ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    record = json.loads((build / "batch-summary.json").read_text(encoding="utf-8"))["unit_records"][0]
    assert record["audit_evidence"]["source"] == "independent-audit.json"
    assert record["audit_evidence"]["fresh_repair_audit"] is True


def test_repaired_stale_audit_cannot_false_complete_while_reused_baseline_passes(
    tmp_path: Path,
) -> None:
    build = tmp_path / "round2-false-complete-build"
    units = build / "courses" / "demo" / "units"
    _write_unit(
        units / "lecture-01",
        audit={
            "build_id": build.name,
            "repair_plan_sha256": "round2-plan-sha256",
            "auditor_id": "baseline-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )
    _write_unit(units / "lecture-02")
    _write_build(build, ["lecture-01", "lecture-02"], ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    assert summary["completed_units"] == ["lecture-02"]
    assert summary["audited_units"] == ["lecture-02"]
    assert summary["pending_units"] == ["lecture-01"]
    assert json.loads((build / "coordinator-handoff.json").read_text(encoding="utf-8"))["mergeable"] is False


def test_parent_snapshot_mismatch_blocks_an_otherwise_complete_repair_build(tmp_path: Path) -> None:
    build = tmp_path / "round2-parent-mismatch-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(
        unit,
        audit_name="independent-audit.post-final.xhigh.json",
        audit={
            "build_id": build.name,
            "repair_plan_sha256": "round2-plan-sha256",
            "fresh_repair_audit": True,
            "auditor_id": "round2-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )
    _write_build(build, ["lecture-01"], ["lecture-01"])
    repair_plan = json.loads((build / "repair-plan.json").read_text(encoding="utf-8"))
    repair_plan["unit_records"] = [{
        "unit_id": "lecture-01",
        "baseline_artifact_tree_sha256": "declared-parent",
        "repair_parent_baseline_artifact_tree_sha256": "different-parent",
    }]
    _write_json(build / "repair-plan.json", repair_plan)

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    result = json.loads((build / "result.json").read_text(encoding="utf-8"))
    assert any(issue["code"] == "repair_parent_snapshot_mismatch" for issue in result["issues"])
    assert json.loads((build / "coordinator-handoff.json").read_text(encoding="utf-8"))["mergeable"] is False


def test_missing_parent_snapshot_blocks_an_otherwise_complete_repair_build(tmp_path: Path) -> None:
    build = tmp_path / "round2-parent-missing-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(
        unit,
        audit_name="independent-audit.post-final.xhigh.json",
        audit={
            "build_id": build.name,
            "repair_plan_sha256": "round2-plan-sha256",
            "fresh_repair_audit": True,
            "auditor_id": "round2-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )
    _write_build(build, ["lecture-01"], ["lecture-01"])
    repair_plan = json.loads((build / "repair-plan.json").read_text(encoding="utf-8"))
    repair_plan.update({
        "course_id": "demo",
        "unit_records": [{
            "unit_id": "lecture-01",
            "baseline_artifact_tree_sha256": "same-parent",
            "repair_parent_baseline_artifact_tree_sha256": "same-parent",
        }],
    })
    _write_json(build / "repair-plan.json", repair_plan)

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    result = json.loads((build / "result.json").read_text(encoding="utf-8"))
    assert any(issue["code"] == "repair_parent_snapshot_missing" for issue in result["issues"])
