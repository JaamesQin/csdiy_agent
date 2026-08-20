#!/usr/bin/env python3
"""Reconcile one portable StudyKit build from its unit checkpoints.

The coordinator owns build-level files, while unit workers own only their unit
directories.  This command is the deterministic, single-writer merge step: it
derives run/result/batch/course summaries and a local index from the current
unit evidence, without calling a model or changing any unit content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_PASS_RESULTS = {
    "pass",
    "passed",
    "success",
    "succeeded",
    "pass_with_warnings",
    "pass_with_limitations",
    "passed_with_warnings",
    "passed_with_limitations",
}
_RESULT_ALIASES = {
    "passed": "pass",
    "success": "pass",
    "succeeded": "pass",
    "passed_with_warnings": "pass_with_warnings",
    "passed_with_limitations": "pass_with_limitations",
}
_BLOCKING_RESULTS = {"block", "blocked", "fail", "failed", "error", "rejected"}
_AUDITOR_KEYS = ("auditor_id", "auditor", "independent_auditor", "reviewer_id", "reviewer")
_AUDIT_SOURCES = {
    "independent-audit.post-checkpoint.json",
    "independent-audit.post-compatibility.json",
    "independent-audit.post-repair.reaudit.json",
    "independent-audit.post-repair-2.reaudit.json",
    "independent-audit.post-repair.json",
    "independent-audit.post-final.json",
    "independent-audit.post-final.xhigh.json",
    "independent-audit.post-finalization.json",
    "independent-audit.json",
    "04-quality-audit.independent.json",
}
_AUTHORITATIVE_AUDIT_SOURCES = {
    "independent-audit.post-checkpoint.json",
    "independent-audit.post-compatibility.json",
    "independent-audit.post-repair.reaudit.json",
    "independent-audit.post-repair-2.reaudit.json",
    "independent-audit.post-repair.json",
    "independent-audit.post-final.json",
    "independent-audit.post-final.xhigh.json",
    "independent-audit.post-finalization.json",
    "independent-audit.json",
}

_AUDIT_SOURCE_PRIORITY = {
    # A later release-stage audit supersedes an earlier checkpoint-stage
    # audit when filesystem timestamps are unavailable or identical.
    "independent-audit.post-final.json": 80,
    "independent-audit.post-final.xhigh.json": 85,
    "independent-audit.post-finalization.json": 70,
    "independent-audit.post-checkpoint.json": 60,
    "independent-audit.post-compatibility.json": 50,
    "independent-audit.post-repair.reaudit.json": 45,
    "independent-audit.post-repair-2.reaudit.json": 46,
    "independent-audit.post-repair.json": 40,
    "independent-audit.json": 30,
    "04-quality-audit.independent.json": 20,
    "metrics.json": 10,
    "review-plan.json": 5,
}


def _is_explicit_audit_source(name: str) -> bool:
    """Recognize qualified independent-audit checkpoint filenames safely."""

    if name in _AUDIT_SOURCES:
        return True
    if name == "04-quality-audit.independent.json":
        return True
    return bool(re.fullmatch(r"independent-audit(?:\.[A-Za-z0-9_-]+)+\.json", name))


def _identity(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("id", "identifier", "name", "value"):
            identity = _identity(value.get(key))
            if identity:
                return identity
        return None
    if value is None or isinstance(value, (list, tuple, set)):
        return None
    rendered = str(value).strip()
    return rendered or None


def _field_identity(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        identity = _identity(record.get(key))
        if identity:
            return identity
    return None


def _identity_key(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _result_value(record: dict[str, Any], *, allow_verdict: bool = False) -> str | None:
    keys = ["result", "overall_status", "independent_audit_result", "audit_result", "status"]
    if allow_verdict:
        keys.append("verdict")
    for key in keys:
        value = record.get(key)
        if value is not None and not isinstance(value, (dict, list)):
            result = str(value).strip().casefold()
            return _RESULT_ALIASES.get(result, result)
    return None


def _has_hard_audit_blocker(
    value: Any,
    *,
    field: str | None = None,
    ignore_nested_status: bool = False,
) -> bool:
    """Reject explicit blockers while ignoring preserved validator snapshots.

    A post-repair audit may intentionally preserve a pre-sidecar
    ``review-validation`` failure as evidence.  That historical status is not
    an audit blocker once the sidecar explicitly records no blockers.  Explicit
    blocker lists and COMPAT-001 codes remain hard regardless of nesting.
    """
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = _identity_key(str(key))
            # Preserved prior audits are provenance snapshots.  Their old
            # ``result: block`` must not override the current sidecar verdict
            # after a valid re-audit has passed.
            if normalized_key in {
                "preservedpriorevidence",
                "previousauditsuperseded",
                "priorindependentaudit",
                "historicalaudit",
                "supersededaudit",
                "originalaudit",
                "auditarchive",
            }:
                continue
            if normalized_key in {"blockers", "blockingissues", "hardblockers", "blockingfindings"} and nested:
                return True
            if normalized_key in {"code", "issuecode", "findingcode", "blockercode"} and _identity_key(_identity(nested)) == "compat001":
                return True
            if normalized_key in {"result", "overallstatus", "independentauditresult", "auditresult", "status", "verdict"}:
                if (
                    not ignore_nested_status
                    and not isinstance(nested, (dict, list))
                    and str(nested).strip().casefold() in _BLOCKING_RESULTS
                ):
                    return True
            nested_status_ignored = ignore_nested_status or normalized_key in {
                "reviewvalidation",
                "validation",
                "portablevalidation",
                "deterministicvalidation",
                "storedreviewvalidation",
                "freshvalidatereview",
            }
            if _has_hard_audit_blocker(
                nested,
                field=normalized_key,
                ignore_nested_status=nested_status_ignored,
            ):
                return True
        return False
    if isinstance(value, list):
        return any(
            _has_hard_audit_blocker(
                item,
                field=field,
                ignore_nested_status=ignore_nested_status,
            )
            for item in value
        )
    if _identity_key(_identity(value)) == "compat001":
        return True
    return field in {"blockers", "blockingissues", "hardblockers", "blockingfindings"} and bool(value)


def _optional_json(path: Path) -> dict[str, Any] | None:
    try:
        return load_object(path) if path.is_file() else None
    except (OSError, ValueError):
        return None


def _actual_reviewed_pages(record: dict[str, Any]) -> list[Any] | None:
    for key in ("actual_reviewed_pages", "review_pages", "review_page_check"):
        pages = record.get(key)
        if isinstance(pages, list) and key == "actual_reviewed_pages":
            return pages
        if isinstance(pages, dict) and isinstance(pages.get("actual_reviewed_pages"), list):
            return pages["actual_reviewed_pages"]
    checks = record.get("checks")
    if isinstance(checks, dict):
        for key in ("review_pages", "review_page_check"):
            checked_pages = checks.get(key)
            if isinstance(checked_pages, dict) and isinstance(checked_pages.get("actual_reviewed_pages"), list):
                return checked_pages["actual_reviewed_pages"]
    return None


def _actual_reviewed_anchors(record: dict[str, Any]) -> list[Any] | None:
    """Return semantic review anchors for sources without physical pages."""
    for key in ("actual_reviewed_anchors", "reviewed_anchors"):
        anchors = record.get(key)
        if isinstance(anchors, list):
            return anchors
    evidence = record.get("review_evidence")
    if isinstance(evidence, dict):
        anchors = evidence.get("actual_reviewed_anchors")
        if isinstance(anchors, list):
            return anchors
    return None


def _heading_anchor_review_is_valid(record: dict[str, Any], pages: list[Any] | None) -> bool:
    """Accept empty page lists only under the current heading-anchor contract."""
    if pages:
        return True
    anchors = _actual_reviewed_anchors(record)
    anchor_type = record.get("anchor_type")
    evidence = record.get("review_evidence")
    if isinstance(evidence, dict):
        anchor_type = evidence.get("anchor_type", anchor_type)
    if not anchors:
        return False
    if anchor_type == "heading":
        return True
    return anchor_type is None and all(
        isinstance(anchor, str) and anchor.lstrip().startswith("#")
        for anchor in anchors
    )


def _audit_candidate_order(unit_dir: Path, candidate: dict[str, Any]) -> tuple[int, int, int, int, int]:
    """Order audit evidence on a deterministic timestamp axis.

    Timezone-aware audit times remain authoritative over phase labels.  A
    date-only or timezone-naive historical sidecar is weaker, however:
    treating it as UTC can make it appear newer than a later post-final audit.
    A sidecar without an explicit time uses its filesystem mtime as the
    deterministic checkpoint time.  Explicit time, file mtime and release
    phase then provide stable tie-breaks.
    """

    source = str(candidate.get("source") or "")
    payload = candidate.get("payload")
    explicit_time = 0
    # Explicit timestamps outrank filesystem mtimes.  Copied immutable builds
    # preserve or refresh mtimes for historical files, so mtime alone cannot
    # establish semantic audit chronology.
    timestamp_quality = 0
    has_explicit_time = False
    if isinstance(payload, dict):
        for key in ("reconciled_at", "audit_reconciled_at", "audited_at", "audit_time", "independent_audit_time", "created_at"):
            raw = payload.get(key)
            if not raw:
                continue
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                timestamp_quality = 2 if parsed.tzinfo is not None else 1
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                explicit_time = int(parsed.timestamp() * 1_000_000_000)
                has_explicit_time = True
                break
            except (TypeError, ValueError, OverflowError):
                continue
    try:
        written_at = (unit_dir / source).stat().st_mtime_ns
    except OSError:
        written_at = 0
    checkpoint_time = explicit_time if has_explicit_time else written_at
    # Audit chronology is authoritative.  A phase-like filename is only a
    # tie-breaker: otherwise an old ``post-final`` blocker can mask a later
    # round-specific re-audit that passed after a targeted repair.  This is
    # particularly important when an immutable parent build is copied into a
    # fingerprinted child and preserves all historical sidecars.
    terminal_phase = (
        source.startswith("independent-audit.post-final.")
        or source in {
            "independent-audit.post-final.json",
            "independent-audit.post-repair-2.reaudit.json",
        }
    )
    return (
        timestamp_quality,
        checkpoint_time,
        int(terminal_phase),
        _AUDIT_SOURCE_PRIORITY.get(source, 0),
        written_at,
    )


def _root_compatibility_status(unit_dir: Path, audit_evidence: dict[str, Any]) -> str:
    """Read the root gate without turning a portable-only warning into audit failure."""
    report = _optional_json(unit_dir / "root-compatibility-report.json") or {}
    if report.get("status") == "blocked":
        return "blocked"
    source = audit_evidence.get("source")
    if source:
        payload = _optional_json(unit_dir / str(source)) or {}
        for key in ("root_compatibility", "root_compatibility_report", "root_gate"):
            nested = payload.get(key)
            if isinstance(nested, dict) and (
                nested.get("status") == "blocked"
                or str(nested.get("code") or nested.get("issue_code") or "").upper() == "COMPAT-001"
            ):
                return "blocked"
    return "succeeded" if report.get("status") in {"succeeded", "passed", "pass"} else "not_recorded"


def _repair_stages(repair: Any) -> list[str]:
    """Expand v0.2 repair records to the stages they actually affect."""
    if not isinstance(repair, dict):
        return [str(repair)]
    stages = repair.get("stages")
    if isinstance(stages, list) and stages:
        return [str(stage) for stage in stages]
    stage = repair.get("stage")
    if stage is not None and str(stage).strip():
        return [str(stage)]
    return ["<unspecified>"]


def checkpoint_integrity_issues(unit_dir: Path) -> list[dict[str, str]]:
    """Return deterministic hard-gate failures visible without reauthoring."""
    metrics = _optional_json(unit_dir / "metrics.json") or {}
    review = _optional_json(unit_dir / "review-plan.json") or {}
    issues: list[dict[str, str]] = []
    quality_mode = str(metrics.get("quality_mode") or review.get("quality_mode") or "")
    try:
        semantic_passes = int(metrics.get("semantic_passes", 0))
    except (TypeError, ValueError):
        semantic_passes = 0
    if quality_mode == "fast" and semantic_passes > 2:
        issues.append({
            "code": "fast_semantic_pass_limit",
            "message": f"Fast mode recorded {semantic_passes} semantic passes; at most 2 are permitted.",
        })
    actual_pages = _actual_reviewed_pages(review)
    if metrics and actual_pages is not None:
        try:
            reviewed_count = int(metrics.get("reviewed_page_count"))
        except (TypeError, ValueError):
            reviewed_count = None
        if reviewed_count is not None and reviewed_count != len(set(actual_pages)):
            issues.append({
                "code": "review_count_mismatch",
                "message": "metrics.reviewed_page_count does not match review-plan.actual_reviewed_pages.",
            })
    repairs: dict[str, int] = {}
    repair_records = metrics.get("repairs", [])
    if isinstance(repair_records, list):
        for repair in repair_records:
            for stage in _repair_stages(repair):
                repairs[stage] = repairs.get(stage, 0) + 1
    for stage, count in sorted(repairs.items()):
        if count > 1:
            issues.append({
                "code": "repair_limit_exceeded",
                "message": f"Stage {stage} has {count} repair records; at most one is permitted.",
            })
    return issues


def independent_audit_evidence(
    unit_dir: Path,
    *,
    author_context: dict[str, Any] | None = None,
    expected_build_id: str | None = None,
    expected_repair_plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Find an explicit independent audit, never a plain author review."""

    documents: dict[str, dict[str, Any]] = {}
    names = {
        "independent-audit.post-checkpoint.json",
        "independent-audit.post-compatibility.json",
        "independent-audit.post-repair.reaudit.json",
        "independent-audit.post-repair-2.reaudit.json",
        "independent-audit.post-repair.json",
        "independent-audit.post-final.json",
        "independent-audit.post-final.xhigh.json",
        "independent-audit.post-finalization.json",
        "independent-audit.json",
        "04-quality-audit.json",
        "04-quality-audit.independent.json",
        "metrics.json",
        "review-plan.json",
        "05-studykit.json",
    }
    names.update(path.name for path in unit_dir.glob("independent-audit*.json"))
    for name in sorted(names):
        document = _optional_json(unit_dir / name)
        if document is not None:
            documents[name] = document

    authors: list[str] = []
    for document in [*documents.values(), *([author_context] if author_context else [])]:
        author = _field_identity(
            document,
            ("author_id", "author", "authoring_agent", "author_worker", "created_by", "generated_by"),
        )
        if author and _identity_key(author) not in {_identity_key(item) for item in authors}:
            authors.append(author)

    candidates: list[dict[str, Any]] = []
    for name, document in documents.items():
        if _is_explicit_audit_source(name):
            payload = dict(document)
            nested = document.get("independent_audit")
            if isinstance(nested, dict):
                payload.update(nested)
            review_pages = _actual_reviewed_pages(documents.get("review-plan.json", {}))
            if "actual_reviewed_pages" not in payload and review_pages is not None:
                payload["actual_reviewed_pages"] = review_pages
            review_anchors = _actual_reviewed_anchors(documents.get("review-plan.json", {}))
            if review_anchors and "actual_reviewed_anchors" not in payload:
                payload["actual_reviewed_anchors"] = review_anchors
                payload.setdefault("anchor_type", "heading")
            candidates.append({"source": name, "payload": payload, "allow_verdict": name.startswith("04-")})
            continue
        if name not in {"metrics.json", "review-plan.json"}:
            continue
        marker = document.get("independent_audit")
        nested = marker if isinstance(marker, dict) else document.get("independent_audit_record")
        if not isinstance(nested, dict) and marker is not True:
            continue
        payload = dict(document)
        if isinstance(nested, dict):
            payload.update(nested)
        review_pages = _actual_reviewed_pages(documents.get("review-plan.json", {}))
        if "actual_reviewed_pages" not in payload and review_pages is not None:
            payload["actual_reviewed_pages"] = review_pages
        review_anchors = _actual_reviewed_anchors(documents.get("review-plan.json", {}))
        if review_anchors and "actual_reviewed_anchors" not in payload:
            payload["actual_reviewed_anchors"] = review_anchors
            payload.setdefault("anchor_type", "heading")
        candidates.append({"source": name, "payload": payload, "allow_verdict": False})

    # Explicit independent-audit sidecars are the audit contract.  Metrics and
    # review-plan records may carry a compatibility fallback marker for old
    # builds, but they are not independent audit documents and must never mask
    # a real sidecar blocker merely because they were rewritten later.
    explicit_sidecars = [
        candidate
        for candidate in candidates
        if _is_explicit_audit_source(candidate["source"])
    ]
    if explicit_sidecars:
        candidates = explicit_sidecars

    # Do not let a stale compatibility/checkpoint sidecar mask a later
    # finalization or repair audit.  The explicit sidecar names remain the
    # contract; timestamps only establish which checkpoint is current.
    def candidate_order(candidate: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
        payload = candidate.get("payload")
        binding_rank = 0
        if isinstance(payload, dict) and expected_build_id:
            same_build = str(payload.get("build_id") or "") == expected_build_id
            same_plan = (
                not expected_repair_plan_sha256
                or str(payload.get("repair_plan_sha256") or "") == expected_repair_plan_sha256
            )
            if same_build and same_plan and payload.get("fresh_repair_audit") is True:
                binding_rank = 3
            elif same_build and same_plan:
                binding_rank = 2
            elif same_build:
                binding_rank = 1
        return (binding_rank, *_audit_candidate_order(unit_dir, candidate))

    candidates.sort(key=candidate_order, reverse=True)

    failures: list[dict[str, Any]] = []
    for candidate in candidates:
        payload = candidate["payload"]
        auditor = _field_identity(payload, _AUDITOR_KEYS)
        result = _result_value(payload, allow_verdict=candidate["allow_verdict"])
        candidate_author = _field_identity(
            payload,
            ("author_id", "author", "authoring_agent", "author_worker", "created_by", "generated_by"),
        )
        known_authors = authors or ([candidate_author] if candidate_author else [])
        issues: list[dict[str, str]] = []
        if not auditor:
            issues.append({"code": "independent_audit_auditor_missing", "message": "Independent audit evidence has no auditor identity."})
        if result not in _PASS_RESULTS:
            issues.append({"code": "independent_audit_result_not_pass", "message": f"Independent audit result is {result or 'missing'}, not pass."})
        if _has_hard_audit_blocker(payload):
            issues.append({"code": "independent_audit_blocker_present", "message": "Independent audit evidence contains an explicit blocker, including COMPAT-001."})
        pages = _actual_reviewed_pages(payload)
        if pages is None or not _heading_anchor_review_is_valid(payload, pages):
            issues.append({"code": "independent_audit_actual_reviewed_pages_missing", "message": "Independent audit evidence has neither physical pages nor valid heading anchors."})
        if not known_authors:
            issues.append({"code": "independent_audit_author_missing", "message": "Cannot establish that the independent auditor differs from the author."})
        elif auditor and any(_identity_key(auditor) == _identity_key(author) for author in known_authors):
            issues.append({"code": "independent_audit_author_match", "message": "Independent auditor is the same identity as the author."})
        if issues:
            failures.extend({**issue, "source": candidate["source"]} for issue in issues)
            # A current explicit audit is authoritative.  Do not let an old
            # passing sidecar mask a newer block or an incomplete audit.
            if _is_explicit_audit_source(candidate["source"]):
                return {
                    "status": "failed",
                    "source": candidate["source"],
                    "auditor": auditor,
                    "result": result,
                    "author": known_authors[0] if known_authors else None,
                    "actual_reviewed_pages": pages,
                    "anchor_type": payload.get("anchor_type"),
                    "issues": failures,
                    "next_action": "repair_or_reaudit_authoritative_independent_audit",
                    "build_id": payload.get("build_id"),
                    "repair_plan_sha256": payload.get("repair_plan_sha256"),
                    "fresh_repair_audit": payload.get("fresh_repair_audit"),
                }
            continue
        return {
            "status": "succeeded",
            "source": candidate["source"],
            "auditor": auditor,
            "result": result if result in {"pass_with_warnings", "pass_with_limitations"} else "pass",
            "author": known_authors[0],
            "actual_reviewed_pages": pages,
            "actual_reviewed_anchors": _actual_reviewed_anchors(payload),
            "anchor_type": payload.get("anchor_type"),
            "issues": [],
            "next_action": "complete",
            "build_id": payload.get("build_id"),
            "repair_plan_sha256": payload.get("repair_plan_sha256"),
            "fresh_repair_audit": payload.get("fresh_repair_audit"),
        }

    if not candidates:
        failures = [{
            "code": "independent_audit_missing",
            "message": "No independent audit evidence with an auditor and result pass was found.",
            "source": "unit audit checkpoints",
        }]
        status = "pending"
    else:
        status = "failed"
    return {
        "status": status,
        "source": None,
        "auditor": None,
        "result": None,
        "author": authors[0] if authors else None,
        "actual_reviewed_pages": None,
        "actual_reviewed_anchors": None,
        "anchor_type": None,
        "issues": failures,
        "next_action": "record_independent_audit_with_distinct_auditor",
        "build_id": None,
        "repair_plan_sha256": None,
        "fresh_repair_audit": None,
    }


def _repair_audit_gate(
    evidence: dict[str, Any],
    *,
    unit_id: str,
    build_id: str,
    repair_plan_sha256: str,
) -> dict[str, Any]:
    """Require a newly recorded audit for a repaired unit in this build."""

    issues: list[dict[str, str]] = []
    if evidence.get("status") != "succeeded":
        return evidence
    # v1/v2 repair plans did not carry a plan digest.  For those legacy
    # records, a sidecar explicitly bound to this build is the available
    # freshness proof.  New plans must use the stronger explicit marker and
    # digest binding below.
    if repair_plan_sha256 and evidence.get("fresh_repair_audit") is not True:
        issues.append({
            "code": "repair_fresh_audit_required",
            "message": f"Repair unit {unit_id} has no fresh independent audit; a copied baseline audit cannot pass.",
        })
    if str(evidence.get("build_id") or "") != build_id:
        issues.append({
            "code": "repair_audit_build_id_mismatch",
            "message": f"Repair audit for {unit_id} is not bound to current build_id {build_id}.",
        })
    if repair_plan_sha256 and str(evidence.get("repair_plan_sha256") or "") != repair_plan_sha256:
        issues.append({
            "code": "repair_audit_plan_hash_mismatch",
            "message": f"Repair audit for {unit_id} is not bound to the current repair plan hash.",
        })
    if not issues:
        return evidence
    return {
        **evidence,
        "status": "pending",
        "issues": [*evidence.get("issues", []), *issues],
        "next_action": "record_fresh_current_build_repair_audit",
    }


def unit_state(
    unit_dir: Path,
    *,
    author_context: dict[str, Any] | None = None,
    repair_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = _optional_json(unit_dir / "validation.json") or {}
    review = _optional_json(unit_dir / "review-validation.json") or {}
    audit_evidence = independent_audit_evidence(
        unit_dir,
        author_context=author_context,
        expected_build_id=str(repair_context["build_id"]) if repair_context else None,
        expected_repair_plan_sha256=(
            str(repair_context["repair_plan_sha256"]) if repair_context else None
        ),
    )
    if repair_context and repair_context.get("status") == "repair_pending":
        audit_evidence = _repair_audit_gate(
            audit_evidence,
            unit_id=unit_dir.name,
            build_id=str(repair_context["build_id"]),
            repair_plan_sha256=str(repair_context["repair_plan_sha256"]),
        )
    # A recovery handoff for the current fingerprint is authoritative about
    # an audit that has not yet been produced.  Do not let the legacy
    # compatibility markers in review-plan/metrics promote such a unit to
    # succeeded.  This is deliberately scoped to the current build so an
    # older handoff cannot poison a later, independently audited checkpoint.
    recovery = _optional_json(unit_dir / "recovery-handoff.json") or {}
    current_build_id = _field_identity(author_context or {}, ("build_id", "resume_fingerprint"))
    recovery_build_id = _field_identity(recovery, ("new_build_id", "build_id"))
    recovery_status = _identity(recovery.get("status"))
    fingerprint_pending = False
    fingerprint_pending_source = None
    for handoff_path in sorted(unit_dir.glob("*fingerprint*handoff*.json")):
        handoff = _optional_json(handoff_path) or {}
        expected_build_id = _field_identity(
            handoff,
            ("expected_current_build_id", "new_build_id", "current_build_id"),
        )
        handoff_status = _identity(handoff.get("status"))
        old_build_id = _field_identity(handoff, ("old_build_id", "old_root_run_build_id"))
        drift = handoff.get("fingerprint_drift")
        if isinstance(drift, dict):
            expected_build_id = expected_build_id or _field_identity(
                drift, ("expected_current_build_id", "new_build_id", "current_build_id")
            )
            old_build_id = old_build_id or _field_identity(
                drift, ("old_build_id", "old_root_run_build_id")
            )
        if not handoff_status and isinstance(handoff.get("release_status"), str):
            handoff_status = _identity(handoff["release_status"])
        if (
            current_build_id
            and expected_build_id == current_build_id
            and old_build_id
            and old_build_id != current_build_id
            and ("mismatch" in handoff_status or "reconciliation" in handoff_path.name)
        ):
            fingerprint_pending = True
            fingerprint_pending_source = handoff_path.name
            break
    if (
        recovery
        and current_build_id
        and recovery_build_id == current_build_id
        and "pending" in recovery_status
        and audit_evidence["status"] != "succeeded"
    ):
        audit_evidence = {
            **audit_evidence,
            "status": "pending",
            "source": "recovery-handoff.json",
            "result": None,
            "auditor": None,
            "actual_reviewed_pages": None,
            "actual_reviewed_anchors": None,
            "issues": [
                *audit_evidence.get("issues", []),
                {
                    "code": "independent_audit_pending_current_build",
                    "message": "Current-build recovery handoff explicitly requires a fresh independent audit; compatibility markers cannot substitute for it.",
                    "source": "recovery-handoff.json",
                },
            ],
            "next_action": "record_fresh_current_build_independent_audit",
        }
    if fingerprint_pending:
        audit_evidence = {
            **audit_evidence,
            "status": "pending",
            "source": fingerprint_pending_source,
            "result": None,
            "auditor": None,
            "actual_reviewed_pages": None,
            "actual_reviewed_anchors": None,
            "issues": [
                *audit_evidence.get("issues", []),
                {
                    "code": "current_build_fingerprint_mismatch_pending",
                    "message": "Unit evidence still belongs to an older fingerprint; keep it pending until migrated and freshly audited in the current build.",
                    "source": fingerprint_pending_source,
                },
            ],
            "next_action": "migrate_unit_to_current_build_and_reaudit",
        }
    final_exists = _optional_json(unit_dir / "05-studykit.json") is not None
    candidate_exists = (unit_dir / "05-studykit.candidate.json").is_file()
    validation_status = validation.get("status")
    review_status = review.get("status")
    integrity_issues = checkpoint_integrity_issues(unit_dir)
    compatibility = _optional_json(unit_dir / "root-compatibility-report.json") or {}
    root_compatibility_status = _root_compatibility_status(unit_dir, audit_evidence)
    if compatibility.get("status") == "blocked":
        integrity_issues.append({
            "code": str(compatibility.get("issue_code") or "root_compatibility_blocked"),
            "message": str(compatibility.get("compatibility_decision", {}).get("reason") or "Root compatibility is blocked."),
            "source": "root-compatibility-report.json",
        })
    if final_exists and validation_status == "succeeded" and review_status == "succeeded" and audit_evidence["status"] == "succeeded" and not integrity_issues:
        state = "succeeded"
    elif validation_status == "failed" or review_status == "failed" or audit_evidence["status"] == "failed" or integrity_issues:
        state = "failed"
    elif final_exists or candidate_exists or (unit_dir / "01-evidence-plan.json").is_file():
        state = "in_progress"
    else:
        state = "pending"
    issues: list[Any] = []
    for report_name, report in (("validation", validation), ("review", review)):
        if report.get("status") == "failed":
            issues.extend({"report": report_name, **issue} for issue in report.get("issues", []))
    issues.extend({"report": "independent-audit", **issue} for issue in audit_evidence["issues"])
    issues.extend({"report": "checkpoint-integrity", **issue} for issue in integrity_issues)
    return {
        "unit_id": unit_dir.name,
        "state": state,
        "final_exists": final_exists,
        "candidate_exists": candidate_exists,
        "validation_status": validation_status,
        "review_status": review_status,
        "independent_audit_status": audit_evidence["status"],
        "audit_status": audit_evidence["status"],
        # Keep the raw independent-audit result separate from the release gate.
        # A portable audit can pass while root compatibility remains blocked;
        # that combination must never be rendered as a completed unit.
        "root_compatibility_status": root_compatibility_status,
        "release_gate_status": "succeeded" if state == "succeeded" else "blocked" if root_compatibility_status == "blocked" else state,
        "release_audit_status": "succeeded" if state == "succeeded" else "blocked" if root_compatibility_status == "blocked" else audit_evidence["status"],
        "independent_auditor": audit_evidence.get("auditor"),
        "independent_audit_result": audit_evidence.get("result"),
        "actual_reviewed_pages": audit_evidence.get("actual_reviewed_pages"),
        "actual_reviewed_anchors": audit_evidence.get("actual_reviewed_anchors"),
        "author": audit_evidence.get("author"),
        "audit_evidence": audit_evidence,
        "issues": issues,
    }


def execution_plan_issues(build_root: Path, requested: list[str]) -> list[dict[str, str]]:
    plan_path = build_root / "execution-plan.json"
    plan = _optional_json(plan_path)
    if plan is None:
        return []
    planned: list[str] = []
    duplicates: list[str] = []
    for worker in plan.get("workers", []):
        if not isinstance(worker, dict):
            continue
        for unit_id in worker.get("units", []):
            rendered = str(unit_id)
            if rendered in planned and rendered not in duplicates:
                duplicates.append(rendered)
            planned.append(rendered)
    issues: list[dict[str, str]] = []
    if duplicates:
        issues.append({
            "code": "execution_plan_duplicate_unit",
            "message": "Execution plan assigns a unit more than once: " + ",".join(duplicates),
            "source": str(plan_path),
        })
    if set(planned) != set(requested) or len(planned) != len(requested):
        missing = sorted(set(requested) - set(planned))
        extra = sorted(set(planned) - set(requested))
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        issues.append({
            "code": "execution_plan_manifest_unit_mismatch",
            "message": "Execution plan units do not match manifest units (" + "; ".join(details) + ").",
            "source": str(plan_path),
        })
    return issues


def _artifact_tree_digest(root: Path) -> str:
    excluded = {"repair-baseline", "repair-parent-baseline"}
    digest = hashlib.sha256()
    for path in sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not excluded.intersection(path.relative_to(root).parts)
    ):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def repair_plan_lineage_issues(build_root: Path, repair_plan: dict[str, Any]) -> list[dict[str, str]]:
    """Reject repair builds whose direct-parent snapshots do not match the declared parent."""

    mismatched: list[str] = []
    missing: list[str] = []
    course_id = str(repair_plan.get("course_id") or "")
    for record in repair_plan.get("unit_records", []):
        if not isinstance(record, dict):
            continue
        expected = record.get("baseline_artifact_tree_sha256")
        actual = record.get("repair_parent_baseline_artifact_tree_sha256")
        if expected and actual and str(expected) != str(actual):
            mismatched.append(str(record.get("unit_id") or "<unknown>"))
            continue
        unit_id = str(record.get("unit_id") or "")
        snapshot = build_root / "courses" / course_id / "units" / unit_id / "repair-parent-baseline"
        if not course_id or not unit_id or not snapshot.is_dir():
            missing.append(unit_id or "<unknown>")
            continue
        if expected and _artifact_tree_digest(snapshot) != str(expected):
            mismatched.append(unit_id)
    if not mismatched and not missing:
        return []
    issues: list[dict[str, str]] = []
    if mismatched:
        issues.append({
            "code": "repair_parent_snapshot_mismatch",
            "message": (
                "Direct-parent snapshots do not match the declared baseline artifacts for: "
                + ",".join(sorted(set(mismatched)))
            ),
            "source": str(build_root / "repair-plan.json"),
        })
    if missing:
        issues.append({
            "code": "repair_parent_snapshot_missing",
            "message": "Direct-parent snapshots are missing for: " + ",".join(sorted(set(missing))),
            "source": str(build_root / "repair-plan.json"),
        })
    return issues


def unit_directory_candidates(units_root: Path, unit_id: str) -> list[Path]:
    """Return the canonical unit directory followed by documented aliases.

    Some catalog manifests use ``note-N`` for heading-anchored course notes,
    while an older isolated build kept the output directory label
    ``lecture-N``.  The manifest identity remains authoritative; this helper
    only lets reconciliation resume those already-created unit artifacts.
    """

    candidates = [units_root / unit_id]
    if unit_id.startswith("note-"):
        candidates.append(units_root / f"lecture-{unit_id.removeprefix('note-')}")
    elif unit_id.startswith("lecture-"):
        candidates.append(units_root / f"note-{unit_id.removeprefix('lecture-')}")
    return list(dict.fromkeys(candidates))


def resolve_unit_directory(
    units_root: Path,
    unit_id: str,
    *,
    author_context: dict[str, Any] | None = None,
    repair_context: dict[str, Any] | None = None,
) -> tuple[Path | None, dict[str, Any] | None]:
    """Choose the strongest existing canonical/legacy unit directory.

    A resumed build can contain both a legacy alias and a later canonical
    directory.  Directory name alone is not enough to choose between them:
    prefer the directory whose actual release evidence is strongest, while
    preferring the manifest-named directory on a complete tie.  This avoids
    counting a stale alias as the authoritative checkpoint merely because it
    sorts first.
    """

    existing = [
        path for path in unit_directory_candidates(units_root, unit_id) if path.is_dir()
    ]
    if not existing:
        return None, None

    scored: list[tuple[tuple[int, ...], Path, dict[str, Any]]] = []
    for path in existing:
        record = unit_state(path, author_context=author_context, repair_context=repair_context)
        score = (
            int(record["state"] == "succeeded"),
            int(record.get("validation_status") == "succeeded"),
            int(record.get("review_status") == "succeeded"),
            int(record.get("independent_audit_status") == "succeeded"),
            int(record.get("final_exists")),
            int(record.get("candidate_exists")),
            int(path.name == unit_id),
        )
        scored.append((score, path, record))
    _, selected, record = max(scored, key=lambda item: item[0])
    return selected, record


def reconcile_build(build_root: Path) -> dict[str, Any]:
    build_root = build_root.resolve()
    manifest = yaml.safe_load((build_root / "manifest.yaml").read_text(encoding="utf-8")) or {}
    course_id = str(manifest.get("course_id") or "")
    if not course_id:
        raise ValueError("manifest.yaml requires course_id")
    requested = [str(unit["unit_id"]) for unit in manifest.get("units", [])]
    coordinator_id = str(manifest.get("coordinator_id") or "")
    if not coordinator_id and (build_root / "run.json").is_file():
        coordinator_id = str(load_object(build_root / "run.json").get("coordinator_id") or "")
    coordinator_id = coordinator_id or "coordinator-1"
    old_run = load_object(build_root / "run.json") if (build_root / "run.json").is_file() else {}
    author_context = {**manifest, **old_run}
    plan = _optional_json(build_root / "execution-plan.json") or {}
    repair_plan = _optional_json(build_root / "repair-plan.json") or {}
    repair_unit_ids = {str(unit_id) for unit_id in repair_plan.get("repair_unit_ids", [])}
    repair_plan_sha256 = str(
        repair_plan.get("repair_plan_sha256")
        or repair_plan.get("repair_plan_hash")
        or repair_plan.get("plan_hash")
        or ""
    )
    repair_context_by_unit = {
        unit_id: {
            "status": "repair_pending",
            "build_id": build_root.name,
            "repair_plan_sha256": repair_plan_sha256,
        }
        for unit_id in repair_unit_ids
    }
    plan_issues = [
        *execution_plan_issues(build_root, requested),
        *repair_plan_lineage_issues(build_root, repair_plan),
    ]
    worker_count = old_run.get("worker_count") or manifest.get("worker_count") or plan.get("worker_count")
    units_root = build_root / "courses" / course_id / "units"
    records = []
    for unit_id in requested:
        unit_dir, existing_record = resolve_unit_directory(
            units_root,
            unit_id,
            author_context=author_context,
            repair_context=repair_context_by_unit.get(unit_id),
        )
        if unit_dir is not None:
            record = existing_record or unit_state(unit_dir, author_context=author_context)
            # The manifest identity is canonical even when the directory is
            # an explicitly supported legacy alias.
            record["unit_id"] = unit_id
            if unit_dir.name != unit_id:
                record["unit_directory_alias"] = unit_dir.name
            records.append(record)
        else:
            records.append(
                {
                    "unit_id": unit_id,
                    "state": "pending",
                    "final_exists": False,
                    "candidate_exists": False,
                    "validation_status": None,
                    "review_status": None,
                    "independent_audit_status": "pending",
                    "audit_status": "pending",
                    "root_compatibility_status": "not_recorded",
                    "release_gate_status": "pending",
                    "release_audit_status": "pending",
                    "independent_auditor": None,
                    "independent_audit_result": None,
                    "actual_reviewed_pages": None,
                    "author": _field_identity(author_context, ("author_id", "author", "authoring_agent")),
                    "audit_evidence": {
                        "status": "pending",
                        "source": None,
                        "auditor": None,
                        "result": None,
                        "actual_reviewed_pages": None,
                        "author": _field_identity(author_context, ("author_id", "author", "authoring_agent")),
                        "issues": [{"code": "independent_audit_missing", "message": "Requested unit directory is missing, so independent audit evidence is missing.", "source": "unit directory"}],
                        "next_action": "author_unit_and_record_independent_audit",
                    },
                    "issues": [{"report": "independent-audit", "code": "independent_audit_missing", "message": "Requested unit directory is missing, so independent audit evidence is missing."}],
                }
            )
    succeeded = [r["unit_id"] for r in records if r["state"] == "succeeded"]
    failed = [r["unit_id"] for r in records if r["state"] == "failed"]
    pending = [r["unit_id"] for r in records if r["state"] in {"pending", "in_progress"}]
    validated = [r["unit_id"] for r in records if r["validation_status"] == "succeeded"]
    # "audited" is a release-level count, not merely evidence that an audit
    # file exists.  A unit is audited only after every other hard gate passes
    # as well; this keeps completed_units and audited_units identical.
    audited = [r["unit_id"] for r in records if r["state"] == "succeeded"]
    complete = bool(requested) and len(succeeded) == len(requested) and not plan_issues
    status = "succeeded" if complete else ("partial" if succeeded else "failed" if failed and not pending else "partial")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    old_result = load_object(build_root / "result.json") if (build_root / "result.json").is_file() else {}
    audit_pending = [r["unit_id"] for r in records if r["independent_audit_status"] != "succeeded"]
    failed_stage = (
        "execution-plan"
        if plan_issues
        else "04-quality-audit.independent"
        if audit_pending
        else "04-quality-audit"
        if any(r["review_status"] == "failed" for r in records)
        else "validation"
        if failed
        else None
    )
    next_action = (
        "complete"
        if complete
        else "repair_execution_plan_before_merge"
        if plan_issues
        else "complete_independent_audit_for_units:" + ",".join(audit_pending)
        if audit_pending
        else "repair_failed_units"
        if failed
        else "author_pending_units"
    )
    run = {
        **old_run,
        # Keep the resumable run record aligned with the release-level
        # summaries.  A partial build is still resumable, but its status must
        # not drift to ``authoring`` after reconciliation has classified
        # concrete failed units.
        "status": status,
        "updated_at": now,
        "requested_unit_count": len(requested),
        "completed_unit_count": len(succeeded),
        "validated_unit_count": len(validated),
        "audited_unit_count": len(audited),
        "failed_unit_count": len(failed),
        "pending_unit_count": len(pending),
        "completed_units": succeeded,
        "validated_units": validated,
        "audited_units": audited,
        "failed_units": failed,
        "pending_units": pending,
        "worker_count": worker_count,
        "coordinator_id": coordinator_id,
        "coordinator_scope": "single-build",
        "global_merge_owner": "global-coordinator",
        "next_action": next_action,
    }
    result = {
        **old_result,
        "status": status,
        "requested_units": requested,
        "completed_units": succeeded,
        "validated_units": validated,
        "audited_units": audited,
        "failed_units": failed,
        "pending_units": pending,
        "requested_unit_count": len(requested),
        "completed_unit_count": len(succeeded),
        "validated_unit_count": len(validated),
        "audited_unit_count": len(audited),
        "failed_unit_count": len(failed),
        "pending_unit_count": len(pending),
        "failed_stage": failed_stage,
        "coordinator_id": coordinator_id,
        "coordinator_scope": "single-build",
        "global_merge_owner": "global-coordinator",
        "recoverable": not complete,
        "next_action": next_action,
        "updated_at": now,
        "issues": [*plan_issues, *[issue for record in records for issue in record["issues"]]],
    }
    batch = {
        "batch_version": "0.2",
        "build_id": build_root.name,
        "status": status,
        "worker_count": run.get("worker_count"),
        "coordinator_id": coordinator_id,
        "coordinator_scope": "single-build",
        "requested_units": requested,
        # Keep the canonical release-level name in the batch record as well
        # as the historical ``succeeded_units`` alias.  Consumers that read
        # only batch summaries must see the same evidence-derived completed
        # set as run/result/course-summary.
        "completed_units": succeeded,
        "succeeded_units": succeeded,
        "validated_units": validated,
        "audited_units": audited,
        "failed_units": failed,
        "pending_units": pending,
        "unit_count": len(requested),
        "requested_unit_count": len(requested),
        "completed_unit_count": len(succeeded),
        "validated_unit_count": len(validated),
        "audited_unit_count": len(audited),
        "failed_unit_count": len(failed),
        "pending_unit_count": len(pending),
        "issues": plan_issues,
        "unit_records": records,
        "updated_at": now,
        "completed_at": now if complete else None,
    }
    course_summary = {
        "course_id": course_id,
        "build_id": build_root.name,
        "coordinator_id": coordinator_id,
        "status": status,
        "worker_count": worker_count,
        "requested_unit_count": len(requested),
        "completed_unit_count": len(succeeded),
        "validated_unit_count": len(validated),
        "audited_unit_count": len(audited),
        "audited_units": audited,
        "failed_unit_count": len(failed),
        "pending_unit_count": len(pending),
        "completed_units": succeeded,
        "failed_units": failed,
        "pending_units": pending,
        "issues": plan_issues,
        "updated_at": now,
    }
    finalization = {
        "build_id": build_root.name,
        "course_id": course_id,
        "status": status,
        "worker_count": worker_count,
        "requested_unit_count": len(requested),
        "completed_unit_count": len(succeeded),
        "validated_unit_count": len(validated),
        "audited_unit_count": len(audited),
        "failed_unit_count": len(failed),
        "pending_unit_count": len(pending),
        "completed_units": succeeded,
        "validated_units": validated,
        "audited_units": audited,
        "failed_units": failed,
        "pending_units": pending,
        "unit_records": records,
        "issues": plan_issues,
        "updated_at": now,
    }
    handoff = {
        "handoff_version": "isolated-build-coordinator-v1",
        "coordinator_id": coordinator_id,
        "coordinator_scope": "single-build",
        "global_merge_owner": "global-coordinator",
        "course_id": course_id,
        "build_id": build_root.name,
        "manifest_sha256": sha256_file(build_root / "manifest.yaml"),
        "status": status,
        "worker_count": worker_count,
        "requested_units": requested,
        "requested_unit_count": len(requested),
        "completed_units": succeeded,
        "completed_unit_count": len(succeeded),
        "validated_units": validated,
        "validated_unit_count": len(validated),
        "audited_units": audited,
        "audited_unit_count": len(audited),
        "failed_units": failed,
        "failed_unit_count": len(failed),
        "pending_units": pending,
        "pending_unit_count": len(pending),
        "unit_records": records,
        "issues": plan_issues,
        "mergeable": complete,
        "updated_at": now,
    }
    for name, value in (("run.json", run), ("result.json", result), ("batch-summary.json", batch), ("course-summary.json", course_summary), ("finalization-report.json", finalization), ("coordinator-handoff.json", handoff)):
        atomic_write(build_root / name, value)
    lines = [
        f"# StudyKit Index: {course_id}",
        "",
        f"- Build: `{build_root.name}`",
        f"- Status: `{status}`",
        f"- Requested: **{len(requested)}**",
        f"- Completed: **{len(succeeded)}/{len(requested)}**",
        f"- Validated: **{len(validated)}/{len(requested)}**",
        f"- Audited: **{len(audited)}/{len(requested)}**",
        f"- Failed: **{len(failed)}**",
        f"- Pending: **{len(pending)}**",
        f"- Worker count: **{worker_count or 'unknown'}**",
    ]
    if plan_issues:
        lines.extend(["", "## Build blockers", "", *[f"- `{issue['code']}`: {issue['message']}" for issue in plan_issues]])
    lines.extend(["", "| Unit | State | Artifact validation | Independent audit | Root gate | Release gate |", "|---|---|---|---|---|---|"])
    for record in records:
        lines.append(f"| `{record['unit_id']}` | `{record['state']}` | `{record['validation_status'] or 'pending'}` | `{record['independent_audit_status']}` | `{record.get('root_compatibility_status', 'not_recorded')}` | `{record.get('release_gate_status', record['state'])}` |")
    (build_root / "STUDYKIT_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return course_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile_build(args.build_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
