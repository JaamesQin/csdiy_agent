from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reconcile_studykit_unit import reconcile_unit


def _write(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _unit_dir(tmp_path: Path) -> Path:
    unit = tmp_path / "unit"
    unit.mkdir()
    _write(unit / "review-plan.json", {"course_id": "demo", "unit_id": "lecture-01", "independent_audit": False})
    _write(unit / "metrics.json", {"independent_audit_status": "pending"})
    _write(unit / "04-quality-audit.json", {"verdict": "pending", "checks": {"independent_audit": "pending"}})
    _write(unit / "05-studykit.candidate.json", {"review": {"generator_review_status": "draft", "audit_findings": []}})
    _write(unit / "04-quality-audit.resolution.json", {"status": "pending", "independent_reaudit": {"status": "pending"}})
    return unit


def test_reconcile_pass_updates_all_unit_checkpoints_atomically(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    record = reconcile_unit(
        unit,
        auditor_id="auditor-1",
        audited_at="2026-08-10T21:11:49+08:00",
        result="pass",
    )

    assert record["result"] == "pass"
    assert json.loads((unit / "review-plan.json").read_text())["independent_audit"] is True
    assert json.loads((unit / "metrics.json").read_text())["independent_audit_status"] == "passed"
    assert json.loads((unit / "04-quality-audit.json").read_text())["verdict"] == "pass"
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    assert candidate["review"]["generator_review_status"] == "audited_draft"
    assert json.loads((unit / "04-quality-audit.resolution.json").read_text())["status"] == "repair_completed_reaudited"
    assert (unit / "independent-audit.json").is_file()
    assert (unit / "independent-audit.post-final.json").is_file()
    assert json.loads((unit / "independent-audit.json").read_text())["reconciled_at"]


def test_reconcile_block_preserves_blockers_and_does_not_claim_pass(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    reconcile_unit(
        unit,
        auditor_id="auditor-2",
        audited_at="2026-08-10T21:11:49+08:00",
        result="block",
        blockers=["formula anchor mismatch"],
    )

    plan = json.loads((unit / "review-plan.json").read_text())
    assert plan["independent_audit"] is False
    assert plan["blockers_after_reaudit"] == ["formula anchor mismatch"]
    quality = json.loads((unit / "04-quality-audit.json").read_text())
    assert quality["verdict"] == "blocked_independent_audit"
    assert quality["independent_audit_blockers"] == ["formula anchor mismatch"]
    assert json.loads((unit / "independent-audit.post-final.json").read_text())["result"] == "block"


def test_reconcile_pass_does_not_fabricate_optional_resolution(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    (unit / "04-quality-audit.resolution.json").unlink()

    reconcile_unit(
        unit,
        auditor_id="auditor-3",
        audited_at="2026-08-10T21:11:49+08:00",
        result="pass",
    )

    assert not (unit / "04-quality-audit.resolution.json").exists()
    assert (unit / "independent-audit.json").is_file()


def test_second_repair_reaudit_writes_current_release_evidence(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    _write(
        unit / "independent-audit.post-repair-2.reaudit.json",
        {
            "auditor_id": "first-repair-reviewer",
            "author_id": "author-1",
            "result": "block",
            "blockers": ["stale practice item"],
        },
    )

    record = reconcile_unit(
        unit,
        author_id="author-1",
        auditor_id="second-repair-xhigh-reviewer",
        audited_at="2026-08-12T21:11:49+08:00",
        result="pass",
    )

    assert record["auditor_id"] == "second-repair-xhigh-reviewer"
    assert record["result"] == "pass"
    release = json.loads((unit / "independent-audit.post-final.xhigh.json").read_text())
    assert release["auditor_id"] == "second-repair-xhigh-reviewer"
    assert release["result"] == "pass"
    assert json.loads((unit / "independent-audit.post-repair-2.reaudit.json").read_text())["result"] == "block"


def test_rich_audit_requires_exact_per_practice_coverage(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    candidate["practice"] = [{"id": "p1"}, {"id": "p2"}]
    _write(unit / "05-studykit.candidate.json", candidate)
    report = unit / "independent-audit.round2.xhigh.json"
    _write(
        report,
        {
            "result": "pass",
            "auditor_id": "xhigh-reviewer",
            "author_id": "author-1",
            "expected_practice_ids": ["p1", "p2"],
            "practice_audits": [
                {"practice_id": "p1", "result": "pass"},
                {"practice_id": "p2", "result": "pass"},
            ],
            "blockers": [],
        },
    )

    record = reconcile_unit(
        unit,
        author_id="author-1",
        auditor_id="xhigh-reviewer",
        audited_at="2026-08-12T21:11:49+08:00",
        result="pass",
        build_id="round2-build",
        repair_plan_sha256="plan-hash",
        audit_report=report,
    )

    assert record["expected_practice_ids"] == ["p1", "p2"]
    assert [item["practice_id"] for item in record["practice_audits"]] == ["p1", "p2"]
    assert record["fresh_repair_audit"] is True


def test_rich_audit_accepts_pass_with_warnings_as_a_pass(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    candidate["practice"] = [{"id": "p1"}]
    _write(unit / "05-studykit.candidate.json", candidate)
    report = unit / "independent-audit.xhigh.json"
    _write(
        report,
        {
            "result": "pass_with_warnings",
            "auditor_id": "xhigh-reviewer",
            "author_id": "author-1",
            "expected_practice_ids": ["p1"],
            "practice_audits": [{"practice_id": "p1", "result": "pass_with_qualification"}],
            "blockers": [],
        },
    )

    record = reconcile_unit(
        unit,
        author_id="author-1",
        auditor_id="xhigh-reviewer",
        audited_at="2026-08-12T21:11:49+08:00",
        result="pass",
        audit_report=report,
    )

    assert record["result"] == "pass"
    assert [item["practice_id"] for item in record["practice_audits"]] == ["p1"]


def test_rich_audit_rejects_missing_practice(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    candidate["practice"] = [{"id": "p1"}, {"id": "p2"}]
    _write(unit / "05-studykit.candidate.json", candidate)
    report = unit / "independent-audit.round2.xhigh.json"
    _write(
        report,
        {
            "result": "pass",
            "auditor_id": "xhigh-reviewer",
            "expected_practice_ids": ["p1", "p2"],
            "practice_audits": [{"practice_id": "p1", "result": "pass"}],
            "blockers": [],
        },
    )

    try:
        reconcile_unit(
            unit,
            auditor_id="xhigh-reviewer",
            audited_at="2026-08-12T21:11:49+08:00",
            result="pass",
            audit_report=report,
        )
    except ValueError as exc:
        assert "cover every current candidate practice" in str(exc)
    else:
        raise AssertionError("missing practice coverage must fail reconciliation")


def test_rich_audit_binds_report_to_current_repair_build_and_plan(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    _write(unit.parent / "repair-plan.json", {"build_id": "repair-build-2", "repair_plan_sha256": "plan-2"})
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    candidate["practice"] = [{"id": "p1"}]
    _write(unit / "05-studykit.candidate.json", candidate)
    report = unit / "independent-audit.round2.json"
    _write(
        report,
        {
            "result": "pass",
            "auditor_id": "repair-reviewer",
            "build_id": "stale-build",
            "repair_plan_sha256": "stale-plan",
            "expected_practice_ids": ["p1"],
            "practice_audits": [{"practice_id": "p1", "result": "pass"}],
        },
    )

    with pytest.raises(ValueError, match="current repair build|repair plan"):
        reconcile_unit(
            unit,
            auditor_id="repair-reviewer",
            audited_at="2026-08-12T21:11:49+08:00",
            result="pass",
            audit_report=report,
        )


def test_rich_audit_rejects_duplicate_current_candidate_practice_ids(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    candidate["practice"] = [{"id": "p1"}, {"id": "p1"}]
    _write(unit / "05-studykit.candidate.json", candidate)
    report = unit / "independent-audit.round2.json"
    _write(
        report,
        {
            "result": "block",
            "auditor_id": "repair-reviewer",
            "expected_practice_ids": ["p1", "p1"],
            "practice_audits": [
                {"practice_id": "p1", "result": "pass"},
                {"practice_id": "p1", "result": "block"},
            ],
        },
    )

    with pytest.raises(ValueError, match="duplicate practice"):
        reconcile_unit(
            unit,
            auditor_id="repair-reviewer",
            audited_at="2026-08-12T21:11:49+08:00",
            result="block",
            audit_report=report,
        )


def test_rich_audit_rejects_current_candidate_practice_without_id(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    candidate["practice"] = [{"id": "p1"}, {"question": "missing identity"}]
    _write(unit / "05-studykit.candidate.json", candidate)
    report = unit / "independent-audit.round2.json"
    _write(
        report,
        {
            "result": "pass",
            "auditor_id": "repair-reviewer",
            "expected_practice_ids": ["p1"],
            "practice_audits": [{"practice_id": "p1", "result": "pass"}],
        },
    )

    with pytest.raises(ValueError, match="current candidate practice"):
        reconcile_unit(
            unit,
            auditor_id="repair-reviewer",
            audited_at="2026-08-12T21:11:49+08:00",
            result="pass",
            audit_report=report,
        )


def test_rich_block_audit_propagates_report_blockers_to_unit_checkpoints(tmp_path: Path) -> None:
    unit = _unit_dir(tmp_path)
    candidate = json.loads((unit / "05-studykit.candidate.json").read_text())
    candidate["practice"] = [{"id": "p1"}, {"id": "p2"}]
    _write(unit / "05-studykit.candidate.json", candidate)
    report = unit / "independent-audit.round2.json"
    _write(
        report,
        {
            "result": "block",
            "auditor_id": "repair-reviewer",
            "expected_practice_ids": ["p1", "p2"],
            "practice_audits": [
                {"practice_id": "p1", "result": "pass"},
                {"practice_id": "p2", "result": "block", "blockers": ["unsupported claim"]},
            ],
            "blockers": ["p2 audit blocked"],
        },
    )

    record = reconcile_unit(
        unit,
        auditor_id="repair-reviewer",
        audited_at="2026-08-12T21:11:49+08:00",
        result="block",
        audit_report=report,
    )

    assert record["blockers"] == ["p2 audit blocked"]
    assert json.loads((unit / "review-plan.json").read_text())["blockers_after_reaudit"] == ["p2 audit blocked"]
    assert json.loads((unit / "04-quality-audit.json").read_text())["independent_audit_blockers"] == [
        "p2 audit blocked"
    ]
