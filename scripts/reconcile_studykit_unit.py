#!/usr/bin/env python3
"""Atomically reconcile an independent unit audit into StudyKit checkpoints.

This is a local, provider-free coordinator helper.  It deliberately operates
only inside one unit directory: course manifests, build roots, registries and
global summaries remain coordinator-owned.  The auditor's report is preserved
as ``independent-audit.json`` and the canonical stage records are updated in a
single deterministic operation.  Call the normal finalization and validators
after this command; the helper never claims that those validators passed.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "review-plan.json",
    "metrics.json",
    "04-quality-audit.json",
    "05-studykit.candidate.json",
)
OPTIONAL_FILES = ("04-quality-audit.resolution.json",)
PASS_AUDIT_RESULTS = {
    "pass",
    "passed",
    "success",
    "succeeded",
    "pass_with_warnings",
    "pass_with_limitations",
    "passed_with_warnings",
    "passed_with_limitations",
}
PASS_PRACTICE_RESULTS = PASS_AUDIT_RESULTS | {"pass_with_qualification"}


def _repair_context(unit_dir: Path) -> dict[str, str]:
    """Discover the enclosing repair build when the caller omits its IDs."""

    for parent in (unit_dir, *unit_dir.parents):
        plan_path = parent / "repair-plan.json"
        if not plan_path.is_file():
            continue
        try:
            plan = load_object(plan_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        context: dict[str, str] = {}
        if plan.get("build_id"):
            context["build_id"] = str(plan["build_id"])
        plan_hash = plan.get("repair_plan_sha256") or plan.get("repair_plan_hash") or plan.get("plan_hash")
        if plan_hash:
            context["repair_plan_sha256"] = str(plan_hash)
        if context:
            return context
    return {}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    """Write one JSON object without exposing a partially written checkpoint."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def reconcile_unit(
    unit_dir: Path,
    *,
    author_id: str | None = None,
    auditor_id: str,
    audited_at: str,
    result: str,
    blockers: list[str] | None = None,
    notes: list[str] | None = None,
    build_id: str | None = None,
    repair_plan_sha256: str | None = None,
    repair_plan_hash: str | None = None,
    audit_report: Path | None = None,
) -> dict[str, Any]:
    """Merge one independent audit result into the five unit checkpoints."""

    if result not in {"pass", "block"}:
        raise ValueError("result must be pass or block")
    unit_dir = unit_dir.resolve()
    repair_context = _repair_context(unit_dir)
    build_id = build_id or repair_context.get("build_id")
    repair_plan_sha256 = repair_plan_sha256 or repair_plan_hash or repair_context.get("repair_plan_sha256")
    paths = {name: unit_dir / name for name in REQUIRED_FILES}
    paths.update({name: unit_dir / name for name in OPTIONAL_FILES if (unit_dir / name).is_file()})
    missing = [str(path) for name, path in paths.items() if name in REQUIRED_FILES and not path.is_file()]
    if missing:
        raise FileNotFoundError("missing unit checkpoint(s): " + ", ".join(missing))

    blockers = list(blockers or [])
    notes = list(notes or [])
    passed = result == "pass"
    audit_status = "passed" if passed else "blocked"
    outcome = "passed_standard_independent_audit" if passed else "blocked_independent_audit"

    records = {name: load_object(path) for name, path in paths.items()}
    review_plan = records["review-plan.json"]
    review_plan.update(
        {
            "independent_audit": passed,
            "independent_audit_status": audit_status,
            "independent_auditor": auditor_id,
            "independent_audit_time": audited_at,
            "independent_audit_result": result,
            "blockers_after_reaudit": blockers,
            "review_outcome": outcome,
        }
    )
    if "practice_reaudit_status" in review_plan:
        review_plan["practice_reaudit_status"] = audit_status

    metrics = records["metrics.json"]
    if author_id:
        metrics["author_id"] = author_id
    metrics.update(
        {
            "independent_audit_status": audit_status,
            "independent_auditor": auditor_id,
            "independent_audit_time": audited_at,
            "independent_audit_result": result,
        }
    )
    metrics["execution_note"] = (
        "Independent re-audit passed and was reconciled atomically; run finalization "
        "and all validators before release."
        if passed
        else "Independent re-audit is blocked; repair only the recorded blockers, then re-audit."
    )
    if "status" in metrics:
        metrics["status"] = "audited" if passed else "blocked_independent_audit"
    if "practice_semantic_review" in metrics:
        metrics["practice_semantic_review"] = "passed_independent_reaudit" if passed else "blocked_independent_reaudit"
    metrics["next_action"] = "finalize_and_validate" if passed else "targeted_repair_then_reaudit"

    quality = records["04-quality-audit.json"]
    if author_id:
        quality["author_id"] = author_id
    quality["verdict"] = "pass" if passed else "blocked_independent_audit"
    quality["independent_auditor"] = auditor_id
    quality["independent_audit_time"] = audited_at
    quality["independent_audit_result"] = result
    quality["independent_audit_blockers"] = blockers
    checks = quality.get("checks")
    if isinstance(checks, dict):
        for key in ("independent_audit", "independent_audit_status"):
            if key in checks:
                checks[key] = "passed" if passed else "blocked"

    candidate = records["05-studykit.candidate.json"]
    rich_audit: dict[str, Any] | None = None
    if audit_report is not None:
        rich_audit = load_object(audit_report.resolve())
        report_result = str(rich_audit.get("result") or "").strip().casefold()
        report_result_matches = (
            report_result in PASS_AUDIT_RESULTS if result == "pass" else report_result == "block"
        )
        if not report_result_matches:
            raise ValueError("audit report result does not match requested reconciliation result")
        if rich_audit.get("auditor_id") != auditor_id:
            raise ValueError("audit report auditor_id does not match requested auditor")
        report_author = rich_audit.get("author_id")
        if author_id and report_author and report_author != author_id:
            raise ValueError("audit report author_id does not match requested author")
        report_build_id = rich_audit.get("build_id")
        if build_id and report_build_id and str(report_build_id) != build_id:
            raise ValueError("audit report is not bound to the current repair build")
        report_plan_hash = (
            rich_audit.get("repair_plan_sha256")
            or rich_audit.get("repair_plan_hash")
            or rich_audit.get("plan_hash")
        )
        if repair_plan_sha256 and report_plan_hash and str(report_plan_hash) != repair_plan_sha256:
            raise ValueError("audit report is not bound to the current repair plan")
        practices = candidate.get("practice")
        if not isinstance(practices, list):
            raise ValueError("candidate practice must be a list for a rich independent audit")
        if any(not isinstance(item, dict) or not item.get("id") for item in practices):
            raise ValueError("every current candidate practice must have a nonempty id")
        candidate_ids = [str(item["id"]) for item in practices]
        expected_ids = [str(item) for item in rich_audit.get("expected_practice_ids") or []]
        practice_audits = rich_audit.get("practice_audits")
        if not isinstance(practice_audits, list):
            raise ValueError("audit report practice_audits must be a list")
        audited_ids = [
            str(item.get("practice_id"))
            for item in practice_audits
            if isinstance(item, dict) and item.get("practice_id")
        ]
        if len(audited_ids) != len(set(audited_ids)):
            raise ValueError("audit report contains duplicate practice_id values")
        if expected_ids != candidate_ids or audited_ids != candidate_ids:
            raise ValueError("audit report must cover every current candidate practice exactly once and in order")
        if passed and any(
            str(item.get("result") or "").strip().casefold() not in PASS_PRACTICE_RESULTS
            for item in practice_audits
        ):
            raise ValueError("a passing audit requires every practice audit to pass")
        if passed and (blockers or rich_audit.get("blockers")):
            raise ValueError("a passing audit cannot contain blockers")
        if not blockers and isinstance(rich_audit.get("blockers"), list):
            blockers = [str(item) for item in rich_audit["blockers"]]
        # Rich-report blockers are authoritative.  They are adopted after the
        # checkpoint objects were initially populated, so refresh every
        # blocker-bearing field before the atomic write.
        if not passed:
            review_plan["blockers_after_reaudit"] = blockers
            quality["independent_audit_blockers"] = blockers
            resolution = records.get("04-quality-audit.resolution.json")
            if resolution is not None:
                independent_reaudit = resolution.get("independent_reaudit")
                if isinstance(independent_reaudit, dict):
                    independent_reaudit["blockers"] = blockers
                    independent_reaudit["remaining_blockers"] = blockers
    review = candidate.setdefault("review", {})
    if not isinstance(review, dict):
        raise ValueError("05-studykit.candidate.json review must be an object")
    review["generator_review_status"] = "audited_draft" if passed else "repair_pending_independent_reaudit"
    review["independent_audit"] = passed
    review["independent_auditor"] = auditor_id
    review["independent_audit_time"] = audited_at
    findings = review.setdefault("audit_findings", [])
    if not isinstance(findings, list):
        raise ValueError("candidate review.audit_findings must be a list")
    _append_unique(findings, "independent re-audit passed" if passed else "independent re-audit blocked")
    candidate["review"] = review

    resolution = records.get("04-quality-audit.resolution.json")
    if resolution is not None:
        resolution["status"] = "repair_completed_reaudited" if passed else "targeted_repairs_applied_pending_independent_reaudit"
        resolution["independent_reaudit"] = {
            "status": "passed" if passed else "blocked",
            "auditor": auditor_id,
            "time": audited_at,
            "result": result,
            "blockers": blockers,
            "notes": notes,
            "remaining_blockers": blockers,
        }

    audit_record = {
        "schema_version": "independent-audit-v1",
        "course_id": review_plan.get("course_id") or candidate.get("course_id"),
        "unit_id": review_plan.get("unit_id") or candidate.get("unit_id"),
        "author_id": metrics.get("author_id") or quality.get("author_id"),
        "auditor_id": auditor_id,
        "audited_at": audited_at,
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "blockers": blockers,
        "notes": notes,
        "next_action": "finalize_and_validate" if passed else "targeted_repair_then_reaudit",
    }
    if rich_audit is not None:
        for key in ("audit_id", "round", "expected_practice_ids", "practice_audits", "warnings", "reviewed_anchors"):
            if key in rich_audit:
                audit_record[key] = rich_audit[key]
        audit_record["source_audit_report"] = str(audit_report.resolve())
    if build_id:
        # These fields deliberately live on the new audit record.  A copied
        # baseline sidecar has no fresh marker and cannot satisfy the build
        # level repair gate merely because its result was ``pass``.
        audit_record.update({
            "audit_kind": "fresh-repair-independent-audit",
            "fresh_repair_audit": True,
            "build_id": build_id,
            "baseline_audit": False,
        })
        if repair_plan_sha256:
            audit_record["repair_plan_sha256"] = repair_plan_sha256

    # All payloads are prepared before any replacement, so validation errors
    # cannot leave half of the checkpoint set updated.
    release_audit_name = (
        "independent-audit.post-final.xhigh.json"
        if "xhigh" in auditor_id.casefold()
        else "independent-audit.post-final.json"
    )
    output = {
        "review-plan.json": review_plan,
        "metrics.json": metrics,
        "04-quality-audit.json": quality,
        "05-studykit.candidate.json": candidate,
        "independent-audit.json": audit_record,
        # The canonical filename is retained for compatibility, while the
        # release-stage sidecar makes the current reconciliation outrank
        # stale audits copied from a baseline build during build-level merge.
        release_audit_name: audit_record,
    }
    if resolution is not None:
        output["04-quality-audit.resolution.json"] = resolution
    for name, payload in output.items():
        atomic_json_write(unit_dir / name, payload)
    return audit_record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-dir", type=Path, required=True)
    parser.add_argument("--author-id")
    parser.add_argument("--auditor-id", required=True)
    parser.add_argument("--audited-at", required=True)
    parser.add_argument("--result", choices=("pass", "block"), required=True)
    parser.add_argument("--blocker", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--build-id")
    parser.add_argument("--repair-plan-sha256")
    parser.add_argument("--repair-plan-hash")
    parser.add_argument("--audit-report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    record = reconcile_unit(
        args.unit_dir,
        author_id=args.author_id,
        auditor_id=args.auditor_id,
        audited_at=args.audited_at,
        result=args.result,
        blockers=args.blocker,
        notes=args.note,
        build_id=args.build_id,
        repair_plan_sha256=args.repair_plan_sha256,
        repair_plan_hash=args.repair_plan_hash,
        audit_report=args.audit_report,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
