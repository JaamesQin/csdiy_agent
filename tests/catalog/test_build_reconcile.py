from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.reconcile_studykit_build import independent_audit_evidence, reconcile_build


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_unit(
    unit: Path,
    *,
    audit: str | None = "independent-audit.json",
    auditor: str = "reviewer-1",
    author: str = "author-1",
) -> None:
    unit.mkdir(parents=True)
    _write_json(unit / "05-studykit.json", {"status": "draft"})
    _write_json(unit / "validation.json", {"status": "succeeded"})
    _write_json(unit / "review-validation.json", {"status": "succeeded"})
    _write_json(unit / "review-plan.json", {"actual_reviewed_pages": [1]})
    if audit == "independent-audit.json":
        _write_json(unit / audit, {"auditor_id": auditor, "author_id": author, "result": "pass"})
    elif audit == "metrics.json":
        _write_json(
            unit / audit,
            {
                "author_id": author,
                "independent_audit": True,
                "independent_auditor": auditor,
                "independent_audit_result": "pass",
            },
        )


def _write_build(build: Path, unit_ids: list[str]) -> None:
    (build / "manifest.yaml").write_text(
        yaml.safe_dump({"course_id": "demo", "units": [{"unit_id": unit_id} for unit_id in unit_ids]}),
        encoding="utf-8",
    )
    _write_json(build / "result.json", {"build_id": build.name, "status": "partial"})


def _write_second_repair_plan(
    build: Path,
    *,
    repair_unit_ids: list[str],
    reused_unit_ids: list[str],
) -> None:
    _write_json(
        build / "repair-plan.json",
        {
            "schema_version": "practice-only-repair-v1",
            "repair_round": 2,
            "repair_unit_ids": repair_unit_ids,
            "reused_unit_ids": reused_unit_ids,
            "policy": {"independent_audit_required_for_repaired_units": True},
        },
    )


def test_build_reconcile_recognizes_qualified_repair_sidecar(tmp_path: Path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    _write_json(unit / "review-plan.json", {"actual_reviewed_pages": [1]})
    _write_json(
        unit / "independent-audit.post-repair.json",
        {"auditor_id": "old-reviewer", "author_id": "author-1", "result": "block", "actual_reviewed_pages": [1], "audited_at": "2026-01-01T00:00:00+00:00"},
    )
    _write_json(
        unit / "independent-audit.post-second-repair.xhigh.json",
        {"auditor_id": "new-reviewer", "author_id": "author-1", "result": "pass", "actual_reviewed_pages": [1], "audited_at": "2026-01-02T00:00:00+00:00"},
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-second-repair.xhigh.json"


def test_build_reconcile_post_final_reaudit_supersedes_older_post_final_block(tmp_path: Path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    _write_json(unit / "review-plan.json", {"actual_reviewed_pages": [1]})
    _write_json(
        unit / "independent-audit.post-final.json",
        {
            "auditor_id": "old-reviewer",
            "author_id": "author-1",
            "result": "block",
            "actual_reviewed_pages": [1],
            "audited_at": "2026-01-02T00:00:00+00:00",
        },
    )
    _write_json(
        unit / "independent-audit.post-final.reaudit.json",
        {
            "auditor_id": "new-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
            "audited_at": "2026-01-03T00:00:00+00:00",
        },
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-final.reaudit.json"


def test_reconcile_build_does_not_complete_without_independent_audit(tmp_path: Path) -> None:
    build = tmp_path / "no-independent-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(unit / "04-quality-audit.json", {"verdict": "pass"})
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)
    result = json.loads((build / "result.json").read_text())
    run = json.loads((build / "run.json").read_text())

    assert summary["status"] == "partial"
    assert run["status"] == "partial"
    assert summary["completed_unit_count"] == 0
    assert summary["audited_units"] == []
    assert result["completed_units"] == []
    assert any(issue["code"] == "independent_audit_missing" for issue in result["issues"])
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False


def test_current_build_recovery_pending_overrides_legacy_audit_marker(tmp_path: Path) -> None:
    build = tmp_path / "recovery-pending-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "review-plan.json",
        {
            "actual_reviewed_pages": [1],
            "independent_audit": True,
            "independent_auditor": "old-reviewer",
            "independent_audit_result": "pass",
        },
    )
    _write_json(
        unit / "recovery-handoff.json",
        {
            "new_build_id": build.name,
            "status": "portable_recovered_pending_independent_audit",
        },
    )
    _write_build(build, ["lecture-01"])
    _write_json(build / "run.json", {"build_id": build.name})

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    assert summary["completed_units"] == []
    assert summary["pending_units"] == ["lecture-01"]
    result = json.loads((build / "result.json").read_text())
    assert result["audited_units"] == []
    assert any(issue["code"] == "independent_audit_pending_current_build" for issue in result["issues"])


def test_current_build_passing_audit_supersedes_recovery_pending_marker(tmp_path: Path) -> None:
    build = tmp_path / "recovery-pending-but-audited-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.fresh-current-build.json",
        {
            "build_id": build.name,
            "auditor_id": "new-reviewer",
            "author_id": "author-1",
            "result": "pass_with_warnings",
            "actual_reviewed_pages": [1],
        },
    )
    _write_json(
        unit / "recovery-handoff.json",
        {
            "new_build_id": build.name,
            "status": "portable_recovered_pending_independent_audit",
        },
    )
    _write_build(build, ["lecture-01"])
    _write_json(build / "run.json", {"build_id": build.name})

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]
    assert summary["audited_units"] == ["lecture-01"]
    result = json.loads((build / "result.json").read_text())
    assert result["pending_units"] == []
    assert not any(issue["code"] == "independent_audit_pending_current_build" for issue in result["issues"])


def test_second_repair_old_audit_cannot_masquerade_as_current_build_fresh_audit(tmp_path: Path) -> None:
    build = tmp_path / "second-repair-old-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_second_repair_plan(build, repair_unit_ids=["lecture-01"], reused_unit_ids=[])
    _write_json(
        unit / "fingerprint-mismatch.handoff.json",
        {
            "status": "blocked_build_fingerprint_mismatch",
            "old_build_id": "first-repair-build",
            "expected_current_build_id": build.name,
        },
    )
    _write_build(build, ["lecture-01"])
    _write_json(build / "run.json", {"build_id": build.name})

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    assert summary["completed_units"] == []
    assert summary["pending_units"] == ["lecture-01"]
    result = json.loads((build / "result.json").read_text())
    assert any(issue["code"] == "current_build_fingerprint_mismatch_pending" for issue in result["issues"])


def test_second_repair_current_build_audit_can_pass_fresh_audit_gate(tmp_path: Path) -> None:
    build = tmp_path / "second-repair-current-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_second_repair_plan(build, repair_unit_ids=["lecture-01"], reused_unit_ids=[])
    _write_json(
        unit / "independent-audit.fresh-second-repair.json",
        {
            "build_id": build.name,
            "auditor_id": "second-repair-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )
    _write_json(
        unit / "recovery-handoff.json",
        {
            "new_build_id": build.name,
            "status": "portable_recovered_pending_independent_audit",
        },
    )
    _write_build(build, ["lecture-01"])
    _write_json(build / "run.json", {"build_id": build.name})

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]
    record = json.loads((build / "batch-summary.json").read_text())["unit_records"][0]
    assert record["audit_evidence"]["source"] == "independent-audit.fresh-second-repair.json"


def test_second_repair_reuses_untouched_unit_with_baseline_audit(tmp_path: Path) -> None:
    build = tmp_path / "second-repair-reused-unit-build"
    units = build / "courses" / "demo" / "units"
    _write_unit(units / "lecture-01", audit=None)
    _write_unit(units / "lecture-02")
    _write_second_repair_plan(build, repair_unit_ids=["lecture-01"], reused_unit_ids=["lecture-02"])
    _write_json(
        units / "lecture-01" / "independent-audit.fresh-second-repair.json",
        {
            "build_id": build.name,
            "auditor_id": "second-repair-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
        },
    )
    _write_build(build, ["lecture-01", "lecture-02"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01", "lecture-02"]
    assert summary["audited_units"] == ["lecture-01", "lecture-02"]


def test_current_build_fingerprint_mismatch_remains_pending(tmp_path: Path) -> None:
    build = tmp_path / "fingerprint-pending-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit="independent-audit.json")
    _write_json(
        unit / "fingerprint-mismatch.handoff.json",
        {
            "status": "blocked_build_fingerprint_mismatch",
            "old_build_id": "old-build",
            "expected_current_build_id": build.name,
        },
    )
    _write_build(build, ["lecture-01"])
    _write_json(build / "run.json", {"build_id": build.name})

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    assert summary["completed_units"] == []
    assert summary["pending_units"] == ["lecture-01"]
    assert summary["failed_unit_count"] == 0
    result = json.loads((build / "result.json").read_text())
    assert any(issue["code"] == "current_build_fingerprint_mismatch_pending" for issue in result["issues"])


def test_reconcile_build_rejects_author_self_audit(tmp_path: Path) -> None:
    build = tmp_path / "self-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, auditor="author-1", author="author-1")
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    result = json.loads((build / "result.json").read_text())
    assert summary["status"] == "failed"
    assert summary["audited_units"] == []
    assert result["failed_stage"] == "04-quality-audit.independent"
    assert any(issue["code"] == "independent_audit_author_match" for issue in result["issues"])
    assert "lecture-01" in result["next_action"]


def test_reconcile_build_completes_when_every_unit_has_distinct_passing_audit(tmp_path: Path) -> None:
    build = tmp_path / "complete-build"
    units = build / "courses" / "demo" / "units"
    _write_unit(units / "lecture-01", audit="independent-audit.json", auditor="reviewer-1")
    _write_unit(units / "lecture-02", audit="metrics.json", auditor="reviewer-2")
    _write_build(build, ["lecture-01", "lecture-02"])

    summary = reconcile_build(build)

    result = json.loads((build / "result.json").read_text())
    batch = json.loads((build / "batch-summary.json").read_text())
    assert summary["status"] == "succeeded"
    assert summary["audited_units"] == ["lecture-01", "lecture-02"]
    assert result["status"] == "succeeded"
    assert result["audited_units"] == ["lecture-01", "lecture-02"]
    assert batch["completed_units"] == ["lecture-01", "lecture-02"]
    assert batch["completed_units"] == batch["succeeded_units"]
    assert batch["audited_units"] == ["lecture-01", "lecture-02"]


def test_reconcile_build_keeps_partial_build_pending_units(tmp_path: Path) -> None:
    build = tmp_path / "partial-build"
    _write_unit(build / "courses" / "demo" / "units" / "lecture-01")
    _write_build(build, ["lecture-01", "lecture-02"])

    summary = reconcile_build(build)

    result = json.loads((build / "result.json").read_text())
    assert summary["status"] == "partial"
    assert summary["completed_units"] == ["lecture-01"]
    assert summary["audited_units"] == ["lecture-01"]
    assert summary["pending_units"] == ["lecture-02"]
    assert result["next_action"] == "complete_independent_audit_for_units:lecture-02"
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False


def test_reconcile_build_resolves_note_unit_lecture_directory_alias(tmp_path: Path) -> None:
    build = tmp_path / "note-alias-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_build(build, ["note-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["note-01"]
    batch = json.loads((build / "batch-summary.json").read_text())
    assert batch["unit_records"][0]["unit_id"] == "note-01"
    assert batch["unit_records"][0]["unit_directory_alias"] == "lecture-01"


def test_reconcile_build_prefers_stronger_alias_when_both_directories_exist(tmp_path: Path) -> None:
    build = tmp_path / "note-alias-precedence-build"
    units = build / "courses" / "demo" / "units"
    _write_unit(units / "note-01", audit=None)
    _write_unit(units / "lecture-01")
    _write_build(build, ["note-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    batch = json.loads((build / "batch-summary.json").read_text())
    assert batch["unit_records"][0]["unit_id"] == "note-01"
    assert batch["unit_records"][0]["unit_directory_alias"] == "lecture-01"


def test_reconcile_build_requires_actual_reviewed_pages_for_independent_audit(tmp_path: Path) -> None:
    build = tmp_path / "audit-without-pages-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    (unit / "review-plan.json").unlink()
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "failed"
    result = json.loads((build / "result.json").read_text())
    assert any(issue["code"] == "independent_audit_actual_reviewed_pages_missing" for issue in result["issues"])
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False


def test_reconcile_build_accepts_implicit_markdown_heading_anchors(tmp_path: Path) -> None:
    build = tmp_path / "heading-anchor-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_json(unit / "review-plan.json", {"actual_reviewed_pages": [], "actual_reviewed_anchors": ["## SIMD"]})
    _write_json(
        unit / "independent-audit.json",
        {
            "auditor_id": "reviewer-1",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [],
            "actual_reviewed_anchors": ["## SIMD"],
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]


def test_reconcile_build_rejects_overlapping_repair_stages(tmp_path: Path) -> None:
    build = tmp_path / "repair-limit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_json(
        unit / "metrics.json",
        {
            "quality_mode": "fast",
            "semantic_passes": 2,
            "reviewed_page_count": 1,
            "repairs": [
                {"id": "repair-1", "stages": ["03-practice-flow"]},
                {"id": "repair-2", "stages": ["03-practice-flow", "05-studykit"]},
            ],
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "failed"
    assert summary["completed_unit_count"] == 0
    result = json.loads((build / "result.json").read_text())
    assert any(issue["code"] == "repair_limit_exceeded" for issue in result["issues"])
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False


def test_reconcile_build_does_not_mask_current_block_with_legacy_passing_audit(tmp_path: Path) -> None:
    build = tmp_path / "authoritative-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_json(
        unit / "04-quality-audit.independent.json",
        {"auditor_id": "reviewer-old", "author_id": "author-1", "result": "pass"},
    )
    _write_json(
        unit / "independent-audit.json",
        {"auditor_id": "reviewer-current", "author_id": "author-1", "result": "block"},
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "failed"
    assert summary["completed_unit_count"] == 0
    result = json.loads((build / "result.json").read_text())
    assert any(issue["code"] == "independent_audit_result_not_pass" for issue in result["issues"])
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False


def test_reconcile_build_prefers_current_reconciled_block_over_stale_timestamped_pass(tmp_path: Path) -> None:
    build = tmp_path / "current-reconciliation-authority-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_json(
        unit / "independent-audit.post-final.reconciliation-20260812.json",
        {
            "auditor_id": "old-reviewer",
            "author_id": "author-1",
            "result": "pass",
            "actual_reviewed_pages": [1],
            "audited_at": "2026-08-12T18:00:00+08:00",
        },
    )
    _write_json(
        unit / "independent-audit.post-final.xhigh.json",
        {
            "auditor_id": "current-reviewer",
            "author_id": "author-1",
            "result": "block",
            "blockers": ["current practice blocker"],
            "actual_reviewed_pages": [1],
            "audited_at": "2026-08-12T00:00:00+08:00",
            "reconciled_at": "2026-08-12T19:00:00+08:00",
        },
    )
    _write_build(build, ["lecture-01"])

    evidence = independent_audit_evidence(unit)
    summary = reconcile_build(build)

    assert evidence["status"] == "failed"
    assert evidence["source"] == "independent-audit.post-final.xhigh.json"
    assert summary["status"] == "failed"


def test_reconcile_build_prefers_later_round_pass_over_old_post_final_block(tmp_path: Path) -> None:
    build = tmp_path / "later-round-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_json(
        unit / "independent-audit.post-final.xhigh.json",
        {
            "auditor_id": "reviewer-round-2",
            "author_id": "author-1",
            "result": "block",
            "blockers": ["superseded practice blocker"],
            "actual_reviewed_pages": [1],
            "audited_at": "2026-08-12T13:00:00+08:00",
        },
    )
    _write_json(
        unit / "independent-audit.round4.xhigh.json",
        {
            "auditor_id": "reviewer-round-4",
            "author_id": "author-1",
            "result": "pass",
            "blockers": [],
            "actual_reviewed_pages": [1],
            "audited_at": "2026-08-12T23:58:00+08:00",
        },
    )
    _write_build(build, ["lecture-01"])

    evidence = independent_audit_evidence(unit)
    summary = reconcile_build(build)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.round4.xhigh.json"
    assert summary["status"] == "succeeded"


def test_reconcile_build_ignores_preserved_historical_block_in_current_pass(tmp_path: Path) -> None:
    build = tmp_path / "historical-audit-provenance-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_json(
        unit / "independent-audit.json",
        {
            "auditor_id": "reviewer-current",
            "author_id": "author-1",
            "result": "pass",
            "preserved_prior_evidence": {
                "initial_independent_audit": {"result": "block", "blockers": ["old issue"]}
            },
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]


def test_reconcile_build_prefers_post_repair_audit_over_historical_post_finalization_block(tmp_path: Path) -> None:
    build = tmp_path / "post-repair-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-finalization.json",
        {"auditor_id": "reviewer-old", "author_id": "author-1", "result": "block", "audited_at": "2026-01-01T00:00:00+00:00"},
    )
    _write_json(
        unit / "independent-audit.post-repair.json",
        {"auditor_id": "reviewer-current", "author_id": "author-1", "result": "pass", "audited_at": "2026-01-02T00:00:00+00:00"},
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]


def test_reconcile_build_prefers_post_checkpoint_audit_over_older_post_repair_pass(tmp_path: Path) -> None:
    build = tmp_path / "post-checkpoint-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-repair.json",
        {"auditor_id": "reviewer-old", "author_id": "author-1", "result": "pass", "audited_at": "2026-01-01T00:00:00+00:00"},
    )
    _write_json(
        unit / "independent-audit.post-checkpoint.json",
        {"auditor_id": "reviewer-current", "author_id": "author-1", "result": "block", "audited_at": "2026-01-02T00:00:00+00:00"},
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "failed"
    assert summary["completed_unit_count"] == 0


def test_reconcile_build_prefers_post_finalization_audit_over_older_compatibility_block(tmp_path: Path) -> None:
    build = tmp_path / "post-finalization-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-compatibility.json",
        {"auditor_id": "reviewer-old", "author_id": "author-1", "result": "block", "audited_at": "2026-01-01T00:00:00+00:00"},
    )
    _write_json(
        unit / "independent-audit.post-finalization.json",
        {"auditor_id": "reviewer-current", "author_id": "author-1", "result": "pass", "audited_at": "2026-01-02T00:00:00+00:00"},
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]


def test_reconcile_build_accepts_post_final_warning_alias(tmp_path: Path) -> None:
    build = tmp_path / "post-final-warning-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-final.json",
        {
            "reviewer": "reviewer-current",
            "author_id": "author-1",
            "result": "passed_with_warnings",
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    record = json.loads((build / "batch-summary.json").read_text())["unit_records"][0]
    assert record["audit_evidence"]["source"] == "independent-audit.post-final.json"
    assert record["audit_evidence"]["result"] == "pass_with_warnings"


def test_reconcile_build_does_not_let_warning_alias_hide_compatibility_blocker(tmp_path: Path) -> None:
    build = tmp_path / "post-final-compatibility-block-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-final.json",
        {
            "reviewer": "reviewer-current",
            "author_id": "author-1",
            "result": "passed_with_limitations",
            "issues": [{"code": "COMPAT-001", "severity": "warning"}],
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "failed"
    result = json.loads((build / "result.json").read_text())
    assert any(issue["code"] == "independent_audit_blocker_present" for issue in result["issues"])


def test_reconcile_build_separates_portable_audit_from_root_release_gate(tmp_path: Path) -> None:
    build = tmp_path / "portable-pass-root-block-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-final.json",
        {
            "reviewer": "reviewer-current",
            "author_id": "author-1",
            "result": "pass_with_warnings",
            "actual_reviewed_pages": [1],
        },
    )
    _write_json(
        unit / "root-compatibility-report.json",
        {"status": "blocked", "issue_code": "COMPAT-001"},
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)
    record = json.loads((build / "batch-summary.json").read_text())["unit_records"][0]
    index = (build / "STUDYKIT_INDEX.md").read_text()

    assert summary["status"] == "failed"
    assert summary["completed_units"] == []
    assert record["independent_audit_status"] == "succeeded"
    assert record["root_compatibility_status"] == "blocked"
    assert record["release_audit_status"] == "blocked"
    assert record["release_gate_status"] == "blocked"
    assert "| `lecture-01` | `failed` | `succeeded` | `succeeded` | `blocked` | `blocked` |" in index


def test_reconcile_build_rejects_post_final_audit_without_reviewer(tmp_path: Path) -> None:
    build = tmp_path / "post-final-missing-reviewer-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-final.json",
        {"author_id": "author-1", "result": "pass", "actual_reviewed_pages": [1]},
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "failed"
    result = json.loads((build / "result.json").read_text())
    assert any(issue["code"] == "independent_audit_auditor_missing" for issue in result["issues"])


def test_reconcile_build_accepts_explicit_passing_audit_status(tmp_path: Path) -> None:
    build = tmp_path / "audit-status-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.json",
        {"auditor_id": "reviewer-1", "author_id": "author-1", "status": "pass"},
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]


def test_reconcile_build_accepts_overall_status_and_nested_review_pages(tmp_path: Path) -> None:
    build = tmp_path / "overall-status-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-repair.reaudit.json",
        {
            "auditor": "reviewer-current",
            "author_id": "author-1",
            "overall_status": "passed",
            "review_pages": {"actual_reviewed_pages": [1]},
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]


def test_reconcile_build_accepts_explicit_nonblocking_limitations(tmp_path: Path) -> None:
    build = tmp_path / "limited-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.post-finalization.json",
        {
            "auditor": "reviewer-current",
            "author_id": "author-1",
            "result": "pass_with_limitations",
            "checks": {"review_pages": {"actual_reviewed_pages": [1]}},
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "succeeded"
    assert summary["completed_units"] == ["lecture-01"]


def test_reconcile_build_blocks_plan_manifest_unit_mismatch(tmp_path: Path) -> None:
    build = tmp_path / "plan-mismatch-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit)
    _write_build(build, ["lecture-01"])
    _write_json(build / "execution-plan.json", {"worker_count": 4, "workers": [{"units": ["lecture-02"]}]})

    summary = reconcile_build(build)

    assert summary["status"] == "partial"
    result = json.loads((build / "result.json").read_text())
    assert result["failed_stage"] == "execution-plan"
    assert result["next_action"] == "repair_execution_plan_before_merge"
    assert any(issue["code"] == "execution_plan_manifest_unit_mismatch" for issue in result["issues"])
    assert json.loads((build / "batch-summary.json").read_text())["worker_count"] == 4
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False


def test_reconcile_build_does_not_let_metrics_mask_explicit_audit_block(tmp_path: Path) -> None:
    build = tmp_path / "metrics-cannot-mask-audit-build"
    unit = build / "courses" / "demo" / "units" / "lecture-01"
    _write_unit(unit, audit=None)
    _write_json(
        unit / "independent-audit.json",
        {
            "auditor_id": "reviewer-current",
            "author_id": "author-1",
            "result": "block",
            "actual_reviewed_pages": [1],
            "blockers": ["source-grounding blocker"],
            "audited_at": "2026-01-01T00:00:00+00:00",
        },
    )
    _write_json(
        unit / "metrics.json",
        {
            "author_id": "author-1",
            "independent_audit": True,
            "independent_auditor": "reviewer-metadata",
            "independent_audit_result": "pass",
            "independent_audit_time": "2026-01-02T00:00:00+00:00",
        },
    )
    _write_build(build, ["lecture-01"])

    summary = reconcile_build(build)

    assert summary["status"] == "failed"
    record = json.loads((build / "batch-summary.json").read_text())["unit_records"][0]
    assert record["audit_evidence"]["source"] == "independent-audit.json"
    assert json.loads((build / "coordinator-handoff.json").read_text())["mergeable"] is False
