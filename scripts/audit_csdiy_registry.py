#!/usr/bin/env python3
"""Reconcile a CSDIY registry with manifests, chunks, and local StudyKit builds.

The audit is read-only unless ``--update`` is supplied. It never downloads
anything and never treats an HTTP or model result as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:  # Works both as ``python -m scripts...`` and direct script execution.
    from scripts.reconcile_studykit_build import (
        independent_audit_evidence as build_independent_audit_evidence,
        resolve_unit_directory,
        unit_directory_candidates,
        unit_state,
    )
    from scripts.update_csdiy_hybrid_progress import render as render_hybrid_progress
except ModuleNotFoundError:  # pragma: no cover - exercised by CLI invocation.
    from reconcile_studykit_build import (
        independent_audit_evidence as build_independent_audit_evidence,
        resolve_unit_directory,
        unit_directory_candidates,
        unit_state,
    )
    from update_csdiy_hybrid_progress import render as render_hybrid_progress


def normalize(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_repository_path(root: Path, value: Any) -> Path | None:
    """Resolve portable or stale machine-absolute paths against this checkout.

    Historical manifests were authored on another machine and may contain an
    absolute path rooted at a previous checkout.  Preserve the recorded value
    in reports, but use the repository-relative ``data/`` or ``outputs/``
    suffix when it is present in the current checkout.
    """

    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute() and path.is_file():
        return path
    if not path.is_absolute():
        return root / path
    parts = path.parts
    for marker in ("data", "outputs"):
        if marker in parts:
            candidate = root.joinpath(*parts[parts.index(marker) :])
            if candidate.exists():
                return candidate
    return path


def json_file(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


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
_VISUAL_REVIEW_PASS_STATUSES = {
    "complete",
    "completed",
    "passed",
    "pass",
    "succeeded",
    "no_parser_risk_pages",
    "risk_pages_passed",
    "risk_pages_passed_final_citation_review_complete",
}
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


def _audit_candidate_order(unit_dir: Path, candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    """Order audit evidence using the same time quality as build reconcile.

    A timezone-aware audit timestamp is stronger than a date-only historical
    timestamp.  A sidecar without an explicit time falls back to its mtime;
    otherwise an old date-only blocker could outrank a newer post-final pass
    in the registry projection while the build reconciler chose the pass.
    """

    source = str(candidate.get("source") or "")
    payload = candidate.get("payload")
    explicit_time = 0
    timestamp_quality = 1
    has_explicit_time = False
    if isinstance(payload, dict):
        for key in ("reconciled_at", "audit_reconciled_at", "audited_at", "audit_time", "independent_audit_time", "created_at"):
            raw = payload.get(key)
            if not raw:
                continue
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                timestamp_quality = int(parsed.tzinfo is not None)
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
    # Final/re-audit sidecars are explicit release checkpoints. Some of these
    # historical files contain only a calendar date, so give those named
    # terminal phases precedence; otherwise retain precise timestamp ordering
    # for ordinary repair/checkpoint sidecars.
    # Treat every post-final re-audit variant as one release-stage family.
    # Otherwise an older literal ``post-final.json`` block can outrank a
    # newer ``post-final.reaudit.json`` pass in the catalog projection while
    # the build reconciler correctly selects the newer evidence.
    terminal_phase = (
        source.startswith("independent-audit.post-final.")
        or source in {
            "independent-audit.post-final.json",
            "independent-audit.post-repair-2.reaudit.json",
        }
    )
    if terminal_phase:
        return (2, checkpoint_time, written_at, _AUDIT_SOURCE_PRIORITY.get(source, 0))
    return (timestamp_quality, checkpoint_time, written_at, _AUDIT_SOURCE_PRIORITY.get(source, 0))


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
    """Return semantic review anchors for non-page source material."""

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
    """Match the build reconciler's empty-page heading-anchor contract."""

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
    # Older Markdown audits recorded the actual heading strings but omitted
    # the redundant type field.  A hash-prefixed heading is an unambiguous
    # heading anchor; accept it without weakening physical-page checks.
    return anchor_type is None and all(
        isinstance(anchor, str) and anchor.lstrip().startswith("#")
        for anchor in anchors
    )


def _has_hard_audit_blocker(value: Any, *, field: str | None = None) -> bool:
    """Reject explicit blockers even when a result uses a warning alias."""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = normalize(key)
            # Independent audit files are required to preserve prior blocks,
            # repair snapshots, and superseded findings.  Those historical
            # records are provenance, not the current audit verdict; treating
            # their nested ``result: block`` as a live blocker creates a false
            # negative after a valid re-audit.
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
            if normalized_key in {"code", "issuecode", "findingcode", "blockercode"} and normalize(_identity(nested)) == "compat001":
                return True
            if normalized_key in {"result", "overallstatus", "independentauditresult", "auditresult", "status", "verdict"}:
                if not isinstance(nested, (dict, list)) and str(nested).strip().casefold() in _BLOCKING_RESULTS:
                    return True
            if _has_hard_audit_blocker(nested, field=normalized_key):
                return True
        return False
    if isinstance(value, list):
        return any(_has_hard_audit_blocker(item, field=field) for item in value)
    if normalize(_identity(value)) == "compat001":
        return True
    return field in {"blockers", "blockingissues", "hardblockers", "blockingfindings"} and bool(value)


def _author_ids(records: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[str]:
    authors: list[str] = []
    context_records = [context] if context else []
    for record in [*(records or []), *context_records]:
        author = _field_identity(
            record,
            ("author_id", "author", "authoring_agent", "author_worker", "created_by", "generated_by"),
        )
        if author and _identity_key(author) not in {_identity_key(item) for item in authors}:
            authors.append(author)
    return authors


def independent_audit_evidence(unit_dir: Path, *, author_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return only explicit, independently attributable audit evidence.

    ``04-quality-audit.json`` and ``review-validation.json`` are deliberately
    absent from the candidate list: the former is the author-side audit and
    the latter validates the review plan, neither of which proves a separate
    auditor inspected the unit.
    """

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
        "04-quality-audit.json",
        "04-quality-audit.independent.json",
        "independent-audit.json",
        "metrics.json",
        "review-plan.json",
        "05-studykit.json",
    }
    names.update(path.name for path in unit_dir.glob("independent-audit*.json"))
    for name in sorted(names):
        document = json_file(unit_dir / name)
        if document is not None:
            documents[name] = document
    authors = _author_ids(list(documents.values()), author_context)
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

    # A named independent-audit sidecar is the audit contract.  Metrics and
    # review-plan records can only serve as a compatibility fallback for old
    # builds with no sidecar; they must never mask a real sidecar blocker just
    # because their metadata was rewritten later.
    explicit_sidecars = [
        candidate
        for candidate in candidates
        if _is_explicit_audit_source(candidate["source"])
    ]
    if explicit_sidecars:
        candidates = explicit_sidecars

    # The newest audit checkpoint is authoritative.  Use the sidecar write
    # time first and the stage priority only as a deterministic tie-breaker.
    candidates.sort(key=lambda candidate: _audit_candidate_order(unit_dir, candidate), reverse=True)

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
        pages = _actual_reviewed_pages(payload)
        if pages is None or not _heading_anchor_review_is_valid(payload, pages):
            issues.append({"code": "independent_audit_actual_reviewed_pages_missing", "message": "Independent audit evidence has neither physical pages nor valid heading anchors."})
        if _has_hard_audit_blocker(payload):
            issues.append({"code": "independent_audit_blocker_present", "message": "Independent audit evidence contains an explicit blocker, including COMPAT-001."})
        if not known_authors:
            issues.append({"code": "independent_audit_author_missing", "message": "Cannot establish that the independent auditor differs from the author."})
        elif auditor and any(_identity_key(auditor) == _identity_key(author) for author in known_authors):
            issues.append({"code": "independent_audit_author_match", "message": "Independent auditor is the same identity as the author."})
        if issues:
            failures.extend({**issue, "source": candidate["source"]} for issue in issues)
            if _is_explicit_audit_source(candidate["source"]):
                return {
                    "status": "failed",
                    "source": candidate["source"],
                    "auditor": auditor,
                    "result": result,
                    "author": known_authors[0] if known_authors else None,
                    "actual_reviewed_pages": pages,
                    "actual_reviewed_anchors": _actual_reviewed_anchors(payload),
                    "anchor_type": payload.get("anchor_type"),
                    "issues": failures,
                    "next_action": "repair_or_reaudit_authoritative_independent_audit",
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
    }


def manifest_matches_target(manifest: dict[str, Any], target: dict[str, Any]) -> bool:
    target_numbers = {normalize(value) for value in target.get("course_numbers", [])}
    manifest_numbers = {
        normalize(manifest.get("primary_course_number")),
        *(normalize(value) for value in manifest.get("cross_listed_course_numbers", [])),
    }
    if target_numbers and target_numbers.intersection(manifest_numbers):
        return True
    target_id = normalize(target.get("canonical_course_id"))
    manifest_id = normalize(manifest.get("course_id"))
    return bool(target_id and manifest_id and (target_id in manifest_id or manifest_id in target_id))


def unit_source_records(manifest: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for unit in manifest.get("units", []):
        unit_id = str(unit.get("unit_id") or "")
        sources = unit.get("sources") or []
        source = sources[0] if sources else {}
        chunks_path = source.get("chunks_path") or f"data/sources/{manifest.get('course_id')}/{unit_id}/chunks.jsonl"
        raw_path = source.get("local_path")
        raw = resolve_repository_path(root, raw_path)
        chunks = resolve_repository_path(root, chunks_path)
        chunk_count = 0
        valid_chunks = 0
        if chunks.is_file():
            for line in chunks.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                chunk_count += 1
                try:
                    json.loads(line)
                    valid_chunks += 1
                except ValueError:
                    pass
        records.append(
            {
                "unit_id": unit_id,
                "source_count": len(sources),
                "raw_path": str(raw_path) if raw_path else None,
                "raw_exists": bool(raw and raw.is_file()),
                "raw_sha256_matches": bool(raw and raw.is_file() and source.get("sha256") and sha256_file(raw) == source.get("sha256")),
                "chunks_path": str(chunks_path),
                "chunks_exists": chunks.is_file(),
                "chunk_count": chunk_count,
                "valid_chunk_count": valid_chunks,
                "source_page_count": source.get("page_count"),
            }
        )
    return records


def output_records(manifest: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    course_id = str(manifest.get("course_id") or "")
    generated_root = root / "outputs" / course_id
    reviewed_root = root / "data" / "reviewed" / course_id
    records: list[dict[str, Any]] = []
    build_roots: list[tuple[Path, str]] = []
    if generated_root.is_dir():
        build_roots.extend((path, "generated") for path in generated_root.iterdir() if path.is_dir())
    if reviewed_root.is_dir():
        build_roots.extend((path, "reviewed") for path in reviewed_root.iterdir() if path.is_dir())
    for build_root, package_kind in sorted(build_roots, key=lambda item: str(item[0])):
        result = json_file(build_root / "result.json") or {}
        batch_summary = json_file(build_root / "batch-summary.json") or {}
        course_summary = json_file(build_root / "course-summary.json") or {}
        coordinator_handoff = json_file(build_root / "coordinator-handoff.json") or {}
        author_context = json_file(build_root / "run.json") or {}
        repair_plan = json_file(build_root / "repair-plan.json") or {}
        repair_units = set(str(item) for item in repair_plan.get("repair_unit_ids") or [])
        repair_plan_sha256 = str(repair_plan.get("repair_plan_sha256") or "")
        build_manifest = load_yaml(build_root / "manifest.yaml") if (build_root / "manifest.yaml").is_file() else {}
        index_path = build_root / "STUDYKIT_INDEX.md"
        if not index_path.is_file():
            index_path = build_root / "REVIEW.md"
        index_exists = index_path.is_file()
        unit_root = build_root / "units" if package_kind == "reviewed" else build_root / "courses" / course_id / "units"
        units: list[dict[str, Any]] = []

        def record_for(unit_id: str, unit_dir: Path | None) -> dict[str, Any]:
            if unit_dir is None:
                audit_evidence = {
                    "status": "pending",
                    "source": None,
                    "auditor": None,
                    "result": None,
                    "author": _field_identity(author_context, ("author_id", "author", "authoring_agent")),
                    "actual_reviewed_pages": None,
                    "actual_reviewed_anchors": None,
                    "anchor_type": None,
                    "issues": [{"code": "independent_audit_missing", "message": "Requested unit directory is missing, so independent audit evidence is missing.", "source": "unit directory"}],
                    "next_action": "author_unit_and_record_independent_audit",
                }
                return {
                    "unit_id": unit_id,
                    "final_exists": False,
                    "validation_exists": False,
                    "status": None,
                    "validation_status": None,
                    "review_status": None,
                    "audit_status": "pending",
                    "independent_auditor": None,
                    "independent_audit_result": None,
                    "author": audit_evidence.get("author"),
                    "audit_evidence": audit_evidence,
                    "root_compatibility_status": "not_recorded",
                    "release_gate_status": "pending",
                    "release_audit_status": "pending",
                    "checkpoint_integrity_issues": [],
                }
            final = json_file(unit_dir / "05-studykit.json")
            validation = json_file(unit_dir / "validation.json")
            review_validation = json_file(unit_dir / "review-validation.json")
            repair_context = (
                {
                    "status": "repair_pending",
                    "build_id": build_root.name,
                    "repair_plan_sha256": repair_plan_sha256,
                }
                if unit_id in repair_units
                else None
            )
            audit_evidence = build_independent_audit_evidence(
                unit_dir,
                author_context=author_context,
                expected_build_id=build_root.name if repair_context else None,
                expected_repair_plan_sha256=repair_plan_sha256 if repair_context else None,
            )
            review_status = review_validation.get("status") if review_validation else None
            audit_status = audit_evidence["status"]
            # A standalone independent-audit pass cannot close a unit whose
            # portable review/release validation is still failed or pending.
            # Keep the root and catalog projections on the same release gate.
            if review_status not in {None, "succeeded"}:
                audit_status = "failed"
            # Keep the registry projection aligned with reconcile_build's
            # release gate.  Portable audit success is not enough when the
            # root compatibility gate, checkpoint integrity, or current-build
            # freshness gate is blocked.
            requires_full_release_gate = (build_root / "manifest.yaml").is_file() or (
                build_root / "repair-plan.json"
            ).is_file()
            if requires_full_release_gate:
                reconciled = unit_state(
                    unit_dir,
                    author_context=author_context,
                    repair_context=repair_context,
                )
            else:
                legacy_pass = (
                    validation is not None
                    and validation.get("status") == "succeeded"
                    and audit_status == "succeeded"
                )
                reconciled = {
                    "root_compatibility_status": "not_recorded",
                    "release_gate_status": "succeeded" if legacy_pass else "pending",
                    "release_audit_status": audit_status,
                    "issues": [],
                }
            return {
                "unit_id": unit_id,
                "unit_directory": unit_dir.name,
                "final_exists": final is not None,
                "validation_exists": validation is not None,
                "status": final.get("status") if final else None,
                "validation_status": validation.get("status") if validation else None,
                "review_status": review_status,
                "audit_status": audit_status,
                "independent_auditor": audit_evidence.get("auditor"),
                "independent_audit_result": audit_evidence.get("result"),
                "author": audit_evidence.get("author"),
                "audit_evidence": audit_evidence,
                "root_compatibility_status": reconciled.get("root_compatibility_status", "not_recorded"),
                "release_gate_status": reconciled.get("release_gate_status", reconciled.get("state")),
                "release_audit_status": reconciled.get("release_audit_status", audit_status),
                "checkpoint_integrity_issues": reconciled.get("issues", []),
            }

        requested_unit_ids = [
            str(unit.get("unit_id") or "")
            for unit in (build_manifest.get("units") or [])
            if unit.get("unit_id")
        ]
        selected_paths: set[Path] = set()
        if unit_root.is_dir() and requested_unit_ids:
            for unit_id in requested_unit_ids:
                unit_dir, _ = resolve_unit_directory(
                    unit_root,
                    unit_id,
                    author_context=author_context,
                )
                if unit_dir is not None:
                    selected_paths.update(
                        candidate
                        for candidate in unit_directory_candidates(unit_root, unit_id)
                        if candidate.is_dir()
                    )
                units.append(record_for(unit_id, unit_dir))
            # Preserve unexpected directories as explicit residue so the
            # projection audit can report them without changing the requested
            # unit denominator.
            for unit_dir in sorted(path for path in unit_root.iterdir() if path.is_dir()):
                if unit_dir not in selected_paths:
                    units.append(record_for(unit_dir.name, unit_dir))
        elif unit_root.is_dir():
            for unit_dir in sorted(path for path in unit_root.iterdir() if path.is_dir()):
                units.append(record_for(unit_dir.name, unit_dir))
        records.append(
            {
                "build_id": build_root.name,
                "path": str(build_root.relative_to(root)),
                "package_kind": package_kind,
                "coordinator_id": author_context.get("coordinator_id") or build_manifest.get("coordinator_id"),
                "quality_mode": author_context.get("quality_mode") or build_manifest.get("quality_mode"),
                "result_status": result.get("status"),
                "index_exists": index_exists,
                "projection_issues": build_projection_issues(
                    build_root,
                    batch_summary=batch_summary,
                    course_summary=course_summary,
                    result=result,
                    coordinator_handoff=coordinator_handoff,
                    unit_records=units,
                    package_kind=package_kind,
                ),
                "unit_records": units,
            }
        )
    return records


def build_projection_issues(
    build_root: Path,
    *,
    batch_summary: dict[str, Any],
    course_summary: dict[str, Any],
    result: dict[str, Any],
    coordinator_handoff: dict[str, Any],
    unit_records: list[dict[str, Any]],
    package_kind: str = "generated",
) -> list[dict[str, Any]]:
    """Detect drift among root summaries before registry progress is merged.

    The build reconciler derives all projections from the unit records.  This
    audit independently checks that a surviving root projection still agrees
    with that derived snapshot, so an interrupted multi-file write cannot
    make the registry report a different denominator or a false completion.
    """

    if package_kind != "generated":
        return []
    issues: list[dict[str, Any]] = []
    requested = list(batch_summary.get("requested_units") or [])
    succeeded = list(batch_summary.get("succeeded_units") or [])
    validated = list(batch_summary.get("validated_units") or [])
    audited = list(batch_summary.get("audited_units") or [])
    failed = list(batch_summary.get("failed_units") or [])
    pending = list(batch_summary.get("pending_units") or [])
    canonical = {
        "requested": requested,
        "completed": succeeded,
        "validated": validated,
        "audited": audited,
        "failed": failed,
        "pending": pending,
    }
    if not batch_summary:
        # Older compatibility fixtures/reviewed packages may expose only a
        # result and unit checkpoints.  A fingerprinted generated build with
        # manifest.yaml must have the complete root projection; keep the
        # minimal offline fixture contract compatible without weakening real
        # build reconciliation.
        if (build_root / "manifest.yaml").is_file():
            issues.append({"code": "build_projection_missing", "message": "Generated build has no batch-summary.json."})
        return issues

    def compare_lists(name: str, document: dict[str, Any], mapping: dict[str, str]) -> None:
        for field, source_field in mapping.items():
            if source_field not in document:
                continue
            value = document.get(source_field)
            if not isinstance(value, list):
                issues.append({"code": "build_projection_field_invalid", "file": name, "field": source_field, "message": "Projection field must be a list."})
                continue
            if value != canonical[field]:
                issues.append({"code": "build_projection_drift", "file": name, "field": source_field, "expected_count": len(canonical[field]), "actual_count": len(value), "message": f"{name}.{source_field} disagrees with batch-summary.json."})

    compare_lists("result.json", result, {"completed": "completed_units", "validated": "validated_units", "audited": "audited_units", "failed": "failed_units", "pending": "pending_units"})
    compare_lists("coordinator-handoff.json", coordinator_handoff, {"requested": "requested_units", "completed": "completed_units", "validated": "validated_units", "audited": "audited_units", "failed": "failed_units", "pending": "pending_units"})

    summary_counts = {
        "requested_unit_count": len(requested),
        "completed_unit_count": len(succeeded),
        "validated_unit_count": len(validated),
        "audited_unit_count": len(audited),
        "failed_unit_count": len(failed),
        "pending_unit_count": len(pending),
    }
    for field, expected in summary_counts.items():
        if field in course_summary and course_summary.get(field) != expected:
            issues.append({"code": "build_projection_drift", "file": "course-summary.json", "field": field, "expected": expected, "actual": course_summary.get(field), "message": "course-summary.json count disagrees with batch-summary.json."})

    expected_status = "succeeded" if requested and len(succeeded) == len(requested) else "partial"
    for name, document in (("batch-summary.json", batch_summary), ("course-summary.json", course_summary), ("result.json", result)):
        if document.get("status") is not None and document.get("status") != expected_status:
            issues.append({"code": "build_projection_status_drift", "file": name, "expected": expected_status, "actual": document.get("status"), "message": "Root projection status disagrees with the unit denominator."})
    if coordinator_handoff.get("mergeable") is not None and coordinator_handoff.get("mergeable") != (expected_status == "succeeded"):
        issues.append({"code": "build_projection_status_drift", "file": "coordinator-handoff.json", "field": "mergeable", "expected": expected_status == "succeeded", "actual": coordinator_handoff.get("mergeable"), "message": "Handoff mergeability disagrees with the unit denominator."})

    index_path = build_root / "STUDYKIT_INDEX.md"
    if index_path.is_file():
        match = re.search(r"Completed:\s*\*\*(\d+)/(\d+)\*\*", index_path.read_text(encoding="utf-8"))
        expected_index = (len(succeeded), len(requested))
        if not match or (int(match.group(1)), int(match.group(2))) != expected_index:
            actual = (int(match.group(1)), int(match.group(2))) if match else None
            issues.append({"code": "build_projection_drift", "file": "STUDYKIT_INDEX.md", "field": "Completed", "expected": expected_index, "actual": actual, "message": "STUDYKIT_INDEX.md denominator disagrees with batch-summary.json."})
    else:
        issues.append({"code": "build_projection_missing", "file": "STUDYKIT_INDEX.md", "message": "Generated build has no STUDYKIT_INDEX.md."})

    # The root projection may only claim success when every requested unit is
    # represented by a successful unit record as well.
    requested_set = set(requested)
    record_ids = {str(unit.get("unit_id")) for unit in unit_records}
    missing_record_ids = sorted(requested_set - record_ids)
    extra_record_ids = sorted(record_ids - requested_set)
    if missing_record_ids:
        issues.append(
            {
                "code": "build_projection_unit_denominator_drift",
                "blocking": True,
                "expected_count": len(requested),
                "actual_count": len(record_ids),
                "missing_unit_ids": missing_record_ids,
                "extra_unit_ids": extra_record_ids,
                "message": "Root unit records are missing requested units from the batch denominator.",
            }
        )
    elif extra_record_ids:
        issues.append(
            {
                "code": "build_projection_extra_unit_records",
                "blocking": False,
                "expected_count": len(requested),
                "actual_count": len(record_ids),
                "extra_unit_ids": extra_record_ids,
                "message": "Build contains extra unit directories outside the manifest denominator; they are excluded from completion counts.",
            }
        )
    # Extra stale directories are reported above, but cannot change the
    # completion count for the current batch.  Restrict this comparison to
    # requested IDs so historical residue cannot create a numeric drift in the
    # authoritative completed-unit set.
    record_succeeded = {
        str(unit.get("unit_id"))
        for unit in unit_records
        if str(unit.get("unit_id")) in requested_set
        and _release_gate_passed(unit)
    }
    if set(succeeded) != record_succeeded:
        issues.append(
            {
                "code": "build_projection_unit_status_drift",
                "expected_count": len(succeeded),
                "actual_count": len(record_succeeded),
                "expected_unit_ids": sorted(set(succeeded)),
                "actual_unit_ids": sorted(record_succeeded),
                "message": "Root completed units disagree with independently reconciled unit records.",
            }
        )
    return issues


def _release_gate_passed(unit: dict[str, Any]) -> bool:
    """Return whether a materialized unit passed the build release gate.

    Status fields are absent from old compatibility fixtures, so absence
    retains the registry's historical unit-level contract. Once a build
    reconciler has emitted them, every release-gate signal is authoritative.
    """

    return (
        unit.get("release_gate_status") in {None, "succeeded"}
        and unit.get("release_audit_status") in {None, "succeeded"}
        and unit.get("root_compatibility_status") not in {"blocked", "failed"}
        and not unit.get("checkpoint_integrity_issues")
        and unit.get("audit_status") == "succeeded"
        and unit.get("final_exists")
        and unit.get("validation_status") in {None, "succeeded"}
    )


def _record_audit_gate(unit: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    """Validate an already materialized unit record using the hard gate."""

    evidence = unit.get("audit_evidence")
    if isinstance(evidence, dict):
        issues = list(evidence.get("issues") or [])
        source = str(evidence.get("source") or evidence.get("path") or "")
        auditor = _field_identity(evidence, _AUDITOR_KEYS)
        raw_result = next(
            (
                evidence.get(key)
                for key in ("result", "independent_audit_result", "audit_result")
                if evidence.get(key) is not None and not isinstance(evidence.get(key), (dict, list))
            ),
            None,
        )
        result = _RESULT_ALIASES.get(str(raw_result).strip().casefold(), str(raw_result).strip().casefold()) if raw_result is not None else None
        author = _identity(evidence.get("author") or evidence.get("author_id") or evidence.get("authoring_agent"))
        pages = _actual_reviewed_pages(evidence)
        gate_record: Any = evidence
    else:
        issues = []
        source = str(unit.get("audit_source") or "")
        auditor = _field_identity(unit, _AUDITOR_KEYS)
        # ``unit.status`` is the build/lifecycle status (often ``draft``),
        # not an independent-audit verdict.  Only read audit-specific fields
        # from a flattened unit record; explicit audit documents may use
        # ``status: pass`` through independent_audit_evidence above.
        result = next(
            (
                _RESULT_ALIASES.get(str(unit.get(key)).strip().casefold(), str(unit.get(key)).strip().casefold())
                for key in ("result", "independent_audit_result", "audit_result")
                if unit.get(key) is not None and not isinstance(unit.get(key), (dict, list))
            ),
            None,
        )
        author = _field_identity(unit, ("author_id", "author", "authoring_agent", "author_worker"))
        pages = _actual_reviewed_pages(unit)
        gate_record = unit
        if not source and not auditor and not result and not author:
            issues.append({"code": "independent_audit_missing", "message": "No independent audit evidence with an auditor and result pass was found."})
    review_status = unit.get("review_status")
    if review_status not in {None, "succeeded"}:
        issues.append(
            {
                "code": "review_validation_not_passed",
                "message": f"Portable review validation is {review_status}, not succeeded; independent audit cannot close the unit.",
            }
        )
    if source in {"04-quality-audit.json", "review-validation.json"}:
        issues.append({"code": "independent_audit_invalid_source", "message": f"{source} is not an independent audit artifact."})
    if not auditor:
        issues.append({"code": "independent_audit_auditor_missing", "message": "Independent audit evidence has no auditor identity."})
    if result not in _PASS_RESULTS:
        issues.append({"code": "independent_audit_result_not_pass", "message": f"Independent audit result is {result or 'missing'}, not pass."})
    if pages is None or not _heading_anchor_review_is_valid(gate_record, pages):
        issues.append({"code": "independent_audit_actual_reviewed_pages_missing", "message": "Independent audit evidence has neither physical pages nor valid heading anchors."})
    if _has_hard_audit_blocker(gate_record):
        issues.append({"code": "independent_audit_blocker_present", "message": "Independent audit evidence contains an explicit blocker, including COMPAT-001."})
    if not author:
        issues.append({"code": "independent_audit_author_missing", "message": "Cannot establish that the independent auditor differs from the author."})
    elif auditor and _identity_key(auditor) == _identity_key(author):
        issues.append({"code": "independent_audit_author_match", "message": "Independent auditor is the same identity as the author."})
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (str(issue.get("code") or ""), str(issue.get("message") or ""))
        if key not in seen:
            unique.append(issue)
            seen.add(key)
    return not unique, unique


def reconcile_target(target: dict[str, Any], manifest_records: list[dict[str, Any]], output_records_for_target: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    audit_metadata = target.get("audit") or {}
    classification_status = audit_metadata.get("classification")
    if classification_status is not None and normalize(classification_status) not in {"passed", "pass", "complete", "completed", "succeeded", "independentlyaudited", "independentauditedsucceeded"}:
        issues.append(
            {
                "code": "classification_review_not_complete",
                "message": "Course classification review is not complete; course completion is withheld.",
                "status": str(classification_status),
                "source": "catalog target audit projection",
            }
        )
    visual_statuses = [
        value
        for value in (
            (target.get("coverage") or {}).get("visual_review_status"),
            audit_metadata.get("visual_review_status"),
        )
        if value is not None
    ]
    normalized_visual_passes = {normalize(value) for value in _VISUAL_REVIEW_PASS_STATUSES}
    if any(normalize(value) not in normalized_visual_passes for value in visual_statuses):
        for visual_status in visual_statuses:
            issues.append(
                {
                    "code": "visual_review_not_complete",
                    "message": "Visual review status is not a completed/pass state; course completion is withheld.",
                    "status": str(visual_status),
                    "source": "catalog coverage/audit projection",
                }
            )
    if len({normalize(value) for value in visual_statuses}) > 1:
        issues.append(
            {
                "code": "visual_review_status_drift",
                "message": "Coverage and audit visual-review statuses disagree.",
                "statuses": [str(value) for value in visual_statuses],
                "source": "catalog coverage/audit projection",
            }
        )
    practice_quality_review = target.get("practice_quality_review")
    quality_gate_blocked = False
    quality_gate_next_action = "complete_content_practice_quality_review"
    if isinstance(practice_quality_review, dict):
        quality_status = str(practice_quality_review.get("status") or "").strip().casefold()
        if quality_status and quality_status != "passed":
            quality_gate_blocked = True
            quality_gate_next_action = str(
                practice_quality_review.get("next_action") or quality_gate_next_action
            )
            issues.append(
                {
                    "code": "practice_quality_review_not_passed",
                    "message": "Content-grounded practice quality review is not passed; schema and unit audit success do not close this gate.",
                    "source": str(practice_quality_review.get("source") or "practice_quality_review"),
                }
            )
    def output_rank(record: dict[str, Any]) -> tuple[int, int, int, int, int, str]:
        """Prefer a successful build, then the build with most valid units.

        A course can retain an older v0.1 checkpoint beside a newer v0.2
        recovery build.  Lexical path order is not an authority for progress;
        coverage and result status are the reproducible signals.
        """
        valid_units = sum(
            1
            for unit in record.get("unit_records", [])
            if unit.get("final_exists")
            and unit.get("validation_exists")
            and unit.get("status") in {"draft", "reviewed", "published", "succeeded"}
            and unit.get("validation_status") in {None, "succeeded"}
        )
        validated_units = sum(
            1
            for unit in record.get("unit_records", [])
            if unit.get("unit_id")
            and unit.get("validation_status") in {None, "succeeded"}
            and unit.get("validation_exists")
        )
        audited_units = sum(1 for unit in record.get("unit_records", []) if unit.get("audit_status") == "succeeded")
        active_build = int(
            bool(target.get("active_build_id"))
            and record.get("build_id") == target.get("active_build_id")
        )
        succeeded = int(record.get("result_status") == "succeeded")
        # An explicit active_build_id is the only authority that lets a
        # partial recovery line outrank another build.  Without that marker,
        # a succeeded build must outrank an abandoned/partial hybrid build.
        # This prevents stale calibration attempts from masking a complete
        # reproducible package while preserving the coordinator's explicit
        # choice for currently active hybrid lines.
        return active_build, succeeded, audited_units, validated_units, valid_units, str(record.get("build_id") or "")

    best_output = max(output_records_for_target, key=output_rank) if output_records_for_target else None
    if best_output:
        issues.extend(best_output.get("projection_issues") or [])
    for manifest_record in manifest_records:
        if manifest_record["source_count"] != 1:
            issues.append({"code": "source_count_mismatch", "unit_id": manifest_record["unit_id"], "message": "Expected exactly one prepared source per unit."})
        if not manifest_record["raw_exists"]:
            issues.append({"code": "missing_raw_source", "unit_id": manifest_record["unit_id"], "message": "Manifest raw/prepared source is missing."})
        elif manifest_record["raw_sha256_matches"] is False:
            issues.append({"code": "raw_hash_mismatch", "unit_id": manifest_record["unit_id"], "message": "Manifest source hash does not match local bytes."})
        if not manifest_record["chunks_exists"]:
            issues.append({"code": "missing_chunks", "unit_id": manifest_record["unit_id"], "message": "Manifest chunk path is missing."})
        elif manifest_record["chunk_count"] != manifest_record["valid_chunk_count"]:
            issues.append({"code": "invalid_chunk_json", "unit_id": manifest_record["unit_id"], "message": "At least one chunk line is not valid JSON."})
        if manifest_record["source_page_count"] is not None and manifest_record["chunks_exists"] and manifest_record["source_page_count"] != manifest_record["chunk_count"]:
            issues.append({"code": "page_chunk_count_mismatch", "unit_id": manifest_record["unit_id"], "message": "Manifest page count does not equal chunk count."})

    unit_count = len(manifest_records)
    chunk_count = sum(record["chunk_count"] for record in manifest_records)
    prepared = bool(manifest_records) and not any(issue["code"] in {"missing_raw_source", "raw_hash_mismatch"} for issue in issues)
    chunked = prepared and not any(issue["code"] in {"missing_chunks", "invalid_chunk_json", "page_chunk_count_mismatch"} for issue in issues)
    requested_unit_ids = [record["unit_id"] for record in manifest_records]
    output_units = {unit.get("unit_id"): unit for unit in (best_output or {}).get("unit_records", [])}
    audit_passed_ids: set[str] = set()
    missing_audit_units: list[str] = []
    for unit_id in requested_unit_ids:
        unit = output_units.get(unit_id)
        if unit is None:
            missing_audit_units.append(unit_id)
            issues.append({"code": "independent_audit_missing", "unit_id": unit_id, "message": "Requested unit has no output record containing independent audit evidence."})
            continue
        passed, audit_issues = _record_audit_gate(unit)
        if passed:
            audit_passed_ids.add(unit_id)
        else:
            missing_audit_units.append(unit_id)
            issues.extend({"unit_id": unit_id, **issue} for issue in audit_issues)

    validated_units = []
    if best_output:
        validated_units = [
            unit["unit_id"]
            for unit in best_output["unit_records"]
            if unit.get("unit_id") in requested_unit_ids
            if unit.get("final_exists")
            and unit.get("validation_exists")
            and unit.get("status") in {"draft", "reviewed", "published", "succeeded"}
            and unit.get("validation_status") in {None, "succeeded"}
        ]
    audited_units = [
        unit_id
        for unit_id in requested_unit_ids
        if unit_id in audit_passed_ids
        and output_units[unit_id].get("final_exists")
        and output_units[unit_id].get("validation_exists")
        and output_units[unit_id].get("status") in {"draft", "reviewed", "published", "succeeded"}
        and output_units[unit_id].get("validation_status") in {None, "succeeded"}
        and _release_gate_passed(output_units[unit_id])
    ]
    # ``release_gate_status`` is emitted by reconcile_build for real builds.
    # Treat a missing field as the legacy synthetic-fixture contract, but do
    # not let a blocked/failed/pending gate be hidden by a passing portable
    # audit or by a complete-looking root projection.
    release_gate_passed = all(
        _release_gate_passed(output_units.get(unit_id, {}))
        for unit_id in requested_unit_ids
    )
    complete = bool(
        best_output
        and best_output.get("result_status") == "succeeded"
        and best_output.get("index_exists")
        and unit_count > 0
        and set(audited_units) == set(requested_unit_ids)
        and release_gate_passed
        and not quality_gate_blocked
        and not any(issue.get("blocking", True) for issue in issues)
    )
    if complete:
        state = "complete"
        next_action = "complete"
    elif best_output:
        state = "authoring"
        next_action = (
            "complete_independent_audit_for_units:" + ",".join(missing_audit_units)
            if missing_audit_units
            else "finish_and_validate_units"
        )
    elif chunked:
        state = "chunked"
        next_action = "plan_and_author_studykits"
    elif prepared:
        state = "prepared"
        next_action = "build_and_validate_chunks"
    elif manifest_records:
        state = "sources_inventoried"
        next_action = "repair_missing_raw_sources"
    else:
        state = target.get("state") or "classified"
        next_action = target.get("next_action") or "research_offering"
    if not complete and quality_gate_blocked:
        next_action = quality_gate_next_action
    elif not complete and missing_audit_units:
        next_action = "complete_independent_audit_for_units:" + ",".join(missing_audit_units)
    return {
        "state": state,
        "next_action": next_action,
        "manifest_path": target.get("manifest_path"),
        "unit_count": unit_count,
        "chunk_count": chunk_count,
        "validated_unit_count": len(validated_units),
        "audit_passed_unit_count": len(audited_units),
        "audited_units": audited_units,
        "missing_audit_units": missing_audit_units,
        "build_id": best_output.get("build_id") if best_output else None,
        "output_index": best_output.get("path") if best_output and best_output.get("index_exists") else None,
        "issues": issues,
        "manifest_unit_records": manifest_records,
        "output_records": output_records_for_target,
    }


def find_manifest_for_target(target: dict[str, Any], manifests: list[tuple[Path, dict[str, Any]]]) -> tuple[Path, dict[str, Any]] | None:
    matches = [(path, manifest) for path, manifest in manifests if manifest_matches_target(manifest, target)]
    # A canonical course may intentionally retain multiple official semester
    # manifests. The registry's selected manifest path is the explicit
    # offering choice; lexical path order is only a deterministic fallback for
    # legacy records that have not selected one yet.
    selected_path = target.get("manifest_path")
    if selected_path:
        selected_text = str(selected_path).replace("\\", "/")
        selected = [
            item
            for item in matches
            if item[0].as_posix() == selected_text
            or item[0].as_posix().endswith("/" + selected_text.lstrip("/"))
        ]
        if selected:
            return selected[0]
    return sorted(matches, key=lambda item: str(item[0]))[0] if matches else None


def build_audit(registry_path: Path, repository_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_yaml(registry_path)
    manifest_dir = repository_root / "data" / "manifests"
    manifests = []
    for path in sorted(manifest_dir.glob("*.yaml")):
        manifests.append((path, load_yaml(path)))
    seen_ids = [target.get("canonical_course_id") for target in registry.get("course_targets", [])]
    duplicate_ids = sorted(course_id for course_id, count in Counter(seen_ids).items() if course_id and count > 1)
    target_reports: list[dict[str, Any]] = []
    matched_manifest_paths: set[str] = set()
    for target in registry.get("course_targets", []):
        found = find_manifest_for_target(target, manifests)
        if found:
            path, manifest = found
            matched_manifest_paths.add(str(path))
            target["manifest_path"] = str(path.relative_to(repository_root))
            records = unit_source_records(manifest, repository_root)
            output = output_records(manifest, repository_root)
        else:
            path = None
            manifest = {}
            records = []
            output = []
        reconciliation = reconcile_target(target, records, output)
        if found:
            reconciliation["manifest_identity"] = {
                "course_id": manifest.get("course_id"),
                "course_version": manifest.get("course_version"),
                "term": manifest.get("term"),
                "year": manifest.get("year"),
                "official_url": manifest.get("official_url"),
                "official_schedule_url": manifest.get("official_schedule_url"),
                "selection_rationale": manifest.get(
                    "selection_rationale",
                    "Existing catalog manifest records a same-identity completed offering and its official source provenance; retain its explicit gaps and license limits.",
                ),
            }
        target_reports.append({"canonical_course_id": target.get("canonical_course_id"), "manifest_path": str(path.relative_to(repository_root)) if path else None, **reconciliation})
    # A target may retain more than one explicit official offering (for
    # example Spring and Summer) under the same canonical course identity.
    # The selected manifest drives the target report, while every same-target
    # manifest remains recognized provenance rather than an orphan.
    for path, manifest in manifests:
        if any(manifest_matches_target(manifest, target) for target in registry.get("course_targets", [])):
            matched_manifest_paths.add(str(path))
    orphan_manifests = [str(path.relative_to(repository_root)) for path, _ in manifests if str(path) not in matched_manifest_paths]
    target_by_id = {target.get("canonical_course_id"): target for target in registry.get("course_targets", [])}
    nav_leaf_progress_drift: list[dict[str, Any]] = []
    for leaf in registry.get("nav_leaves", []):
        target_ids = [target_id for target_id in leaf.get("course_target_ids", []) if target_id in target_by_id]
        if not target_ids:
            continue
        expected_states = sorted({str(target_by_id[target_id].get("state") or "classified") for target_id in target_ids})
        progress = leaf.get("progress") or {}
        actual_states = sorted({str(value) for value in (progress.get("course_target_states") or [])})
        actual_state = str(progress.get("state") or "")
        expected_state = expected_states[0] if len(expected_states) == 1 else "mixed"
        if actual_states != expected_states or actual_state != expected_state:
            nav_leaf_progress_drift.append(
                {
                    "leaf_key": leaf.get("leaf_key"),
                    "target_ids": target_ids,
                    "expected_state": expected_state,
                    "actual_state": actual_state or None,
                    "expected_target_states": expected_states,
                    "actual_target_states": actual_states,
                }
            )
    expected_summary = {
        "nav_leaf_count": len(registry.get("nav_leaves", [])),
        "course_nav_leaf_count": sum(1 for leaf in registry.get("nav_leaves", []) if leaf.get("is_course_target")),
        "course_target_count": len(registry.get("course_targets", [])),
        "excluded_leaf_count": sum(1 for leaf in registry.get("nav_leaves", []) if not leaf.get("is_course_target")),
    }
    summary = registry.get("summary") or {}
    summary_drift = [
        {"field": field, "expected": expected, "actual": summary.get(field)}
        for field, expected in expected_summary.items()
        if summary.get(field) != expected
    ]
    direction_counts = dict(
        sorted(
            Counter((target.get("priority") or {}).get("major_direction", "other_computing") for target in registry.get("course_targets", [])).items()
        )
    )
    known_manifest_course_ids = {str(manifest.get("course_id")) for _, manifest in manifests}
    orphan_builds: list[str] = []
    outputs_root = repository_root / "outputs"
    if outputs_root.is_dir():
        for course_dir in sorted(path for path in outputs_root.iterdir() if path.is_dir()):
            # The ignored outputs directory also contains historical skill
            # experiments and single-unit benchmark runs.  Only a directory
            # using a canonical catalog course ID is a course build namespace;
            # unrelated roots are preserved and reported separately below.
            if course_dir.name in known_manifest_course_ids:
                continue
            if course_dir.name.startswith(("final-", "fresh-", "parallel-", "thinking-", "lecture-", "studykit-", "finaljson-")):
                continue
            if course_dir.name not in known_manifest_course_ids:
                orphan_builds.extend(str(path.relative_to(repository_root)) for path in course_dir.iterdir() if path.is_dir())
    false_complete = [report["canonical_course_id"] for report in target_reports if report["state"] != "complete" and any(target.get("canonical_course_id") == report["canonical_course_id"] and target.get("state") == "complete" for target in registry.get("course_targets", []))]
    root_succeeded_but_catalog_incomplete = [
        {
            "canonical_course_id": report["canonical_course_id"],
            "blocking_issue_codes": sorted({str(issue.get("code")) for issue in report.get("issues", []) if issue.get("code")}),
        }
        for report in target_reports
        if report["state"] != "complete"
        and any(output.get("result_status") == "succeeded" for output in report.get("output_records", []))
    ]
    unresolved_leaves = [leaf["leaf_key"] for leaf in registry.get("nav_leaves", []) if leaf.get("classification_review_status") in {"needs_review", "pending_independent_audit"}]
    audit = {
        "audit_version": "0.1",
        "audited_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "registry_path": str(registry_path),
        "pinned_commit": registry.get("source_catalog", {}).get("pinned_commit"),
        "nav_leaf_count": len(registry.get("nav_leaves", [])),
        "course_nav_leaf_count": expected_summary["course_nav_leaf_count"],
        "course_target_count": len(registry.get("course_targets", [])),
        "excluded_leaf_count": expected_summary["excluded_leaf_count"],
        "direction_counts": direction_counts,
        "nav_leaf_progress_drift": nav_leaf_progress_drift,
        "summary_drift": summary_drift,
        "unclassified_or_unreviewed_leaf_count": len(unresolved_leaves),
        "duplicate_canonical_ids": duplicate_ids,
        "false_complete_targets": false_complete,
        "root_succeeded_but_catalog_incomplete": root_succeeded_but_catalog_incomplete,
        "orphan_manifests": orphan_manifests,
        "orphan_builds": orphan_builds,
        "target_reports": target_reports,
        "state_counts": dict(Counter(report["state"] for report in target_reports)),
        "global_gate": "succeeded" if not unresolved_leaves and not duplicate_ids and not false_complete and not orphan_manifests and not orphan_builds and not nav_leaf_progress_drift and not summary_drift and all(report["state"] == "complete" for report in target_reports) else "partial",
    }
    return registry, audit


def atomic_write_yaml(path: Path, value: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, default=Path("evaluations/csdiy-catalog-registry-audit.json"))
    parser.add_argument("--hybrid-progress-output", type=Path, default=Path("docs/csdiy-hybrid-batch-progress.md"))
    parser.add_argument("--update", action="store_true", help="update per-target state and deterministic coverage fields")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository_root = args.repository_root.resolve()
    registry, audit = build_audit(args.registry, repository_root)
    reports_by_id = {report["canonical_course_id"]: report for report in audit["target_reports"]}
    if args.update:
        for target in registry.get("course_targets", []):
            report = reports_by_id.get(target.get("canonical_course_id"))
            if not report:
                continue
            target["state"] = report["state"]
            target["next_action"] = report["next_action"]
            target["manifest_path"] = report["manifest_path"]
            target["coverage"].update(
                {
                    "manifest_path": report["manifest_path"],
                    "unit_count": report["unit_count"],
                    "validated_unit_count": report["validated_unit_count"],
                    "audit_passed_unit_count": report["audit_passed_unit_count"],
                    "chunk_count": report["chunk_count"],
                    "build_id": report["build_id"],
                    "output_index": report["output_index"],
                    "source_gaps": [issue for issue in report["issues"] if issue["code"] not in {"missing_chunks", "invalid_chunk_json"}],
                }
            )
            identity = report.get("manifest_identity")
            if identity:
                target["selected_offering"] = identity
                priority = target.setdefault("priority", {})
                priority["public_source_readiness"] = max(int(priority.get("public_source_readiness", 0)), 3)
                if "manifest-backed" not in str(priority.get("priority_reason", "")):
                    priority["priority_reason"] = f"{priority.get('priority_reason', '').rstrip('.')}；manifest-backed offering 已在本地记录并进入可恢复流水线。"
            target["progress"].update({"state": report["state"], "last_successful_checkpoint": report["state"], "validated_unit_count": report["validated_unit_count"], "audit_passed_unit_count": report["audit_passed_unit_count"], "build_id": report["build_id"]})
            target_audit = target.setdefault("audit", {})
            target_audit.update({"last_successful_checkpoint": "registry_reconciliation", "registry_reconciliation_status": "complete" if report["state"] == "complete" else "partial", "validated_unit_count": report["validated_unit_count"], "audit_passed_unit_count": report["audit_passed_unit_count"]})
        registry["summary"]["target_states"] = dict(Counter(target.get("state") for target in registry.get("course_targets", [])))
        registry["last_reconciled_at"] = audit["audited_at"]
        registry["global_gate"] = audit["global_gate"]
        atomic_write_yaml(args.registry, registry)
        hybrid_output = args.hybrid_progress_output
        hybrid_output.parent.mkdir(parents=True, exist_ok=True)
        hybrid_temporary = hybrid_output.with_name(f".{hybrid_output.name}.tmp")
        hybrid_temporary.write_text(render_hybrid_progress(repository_root, registry, generated_at=audit["audited_at"]), encoding="utf-8")
        hybrid_temporary.replace(hybrid_output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: audit[key] for key in ("course_target_count", "state_counts", "false_complete_targets", "orphan_manifests", "orphan_builds", "global_gate")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
