#!/usr/bin/env python3
"""Approve only archived StudyKit builds that satisfy every online release gate.

The immutable StudyKit JSON and audit artifacts are never rewritten. Human
publication approval is represented by the separate build/document
``review_status`` columns. A build is eligible only when the archive, its
authoring result, per-unit validators, and the independent registry audit all
agree on the exact unit set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.archive import StudyKitArchive
from app.retrieval.schema_validation import validate_instance


DEFAULT_ARCHIVE = ROOT / "data" / "archive" / "studykits.sqlite3"
DEFAULT_REGISTRY_AUDIT = ROOT / "evaluations" / "csdiy-catalog-registry-audit.json"
PORTABLE_SCHEMA = ROOT / "skills" / "studykit-generator" / "assets" / "schemas" / "studykit.schema.json"
PASS_STATUSES = frozenset({"passed", "succeeded", "valid"})


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(value: str | bytes, *, label: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return parsed


def _artifact_json(
    connection: sqlite3.Connection,
    *,
    build_id: str,
    relative_path: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT content FROM studykit_artifacts
        WHERE build_id = ? AND relative_path = ?
        """,
        (build_id, relative_path),
    ).fetchone()
    if row is None:
        return None
    content = bytes(row["content"]).decode("utf-8")
    return _json_object(content, label=relative_path)


def _passing_report(report: dict[str, Any] | None) -> bool:
    if report is None:
        return False
    return (
        str(report.get("status", "")).casefold() in PASS_STATUSES
        and not report.get("issues")
    )


def _registry_reports(
    paths: tuple[Path, ...],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    by_build: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, str]] = []
    for path in paths:
        raw = path.read_bytes()
        payload = _json_object(raw, label=str(path))
        reports = payload.get("target_reports")
        if not isinstance(reports, list):
            raise ValueError(f"{path}: audit has no target_reports list")
        sources.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        for report in reports:
            if not isinstance(report, dict):
                continue
            build_id = report.get("build_id")
            if isinstance(build_id, str) and build_id:
                if build_id in by_build:
                    raise ValueError(f"audit inputs contain duplicate build_id {build_id}")
                by_build[build_id] = report
    return by_build, sources


def _unit_set(value: Any) -> set[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return set(value)


def evaluate_archive(
    database: Path,
    registry_audit: Path,
    *,
    supplemental_audits: tuple[Path, ...] = (),
    owner_approved_legacy_courses: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    integrity_issues = StudyKitArchive(database).verify_integrity()
    registry_by_build, audit_sources = _registry_reports(
        (registry_audit, *supplemental_audits)
    )
    build_results: list[dict[str, Any]] = []

    uri = f"{database.resolve().as_uri()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        builds = connection.execute(
            "SELECT * FROM studykit_builds ORDER BY course_id, course_version"
        ).fetchall()
        for build in builds:
            build_id = str(build["build_id"])
            course_id = str(build["course_id"])
            reasons: list[str] = []
            documents = connection.execute(
                """
                SELECT unit_id, schema_id, document_json, review_status
                FROM studykit_documents
                WHERE build_id = ? ORDER BY unit_id
                """,
                (build_id,),
            ).fetchall()
            document_units = {str(row["unit_id"]) for row in documents}

            if integrity_issues:
                reasons.append("archive_integrity_failed")
            if build["build_status"] != "succeeded":
                reasons.append(f"build_status_{build['build_status']}")
            if build["schema_id"] != "portable-v0.2.1":
                reasons.append("current_portable_schema_required")
            if len(documents) != int(build["unit_count"]):
                reasons.append("document_count_mismatch")

            metadata = _json_object(build["metadata_json"], label=f"{build_id}:metadata")
            result = metadata.get("result")
            if not isinstance(result, dict):
                reasons.append("missing_build_result")
                result = {}
            if result.get("status") != "succeeded":
                reasons.append("result_not_succeeded")
            if result.get("failed_units") not in ([], None):
                reasons.append("result_has_failed_units")
            if result.get("pending_units") not in ([], None):
                reasons.append("result_has_pending_units")

            for field in (
                "requested_units",
                "completed_units",
                "validated_units",
                "audited_units",
            ):
                units = _unit_set(result.get(field))
                if units is None:
                    reasons.append(f"missing_{field}")
                elif units != document_units:
                    reasons.append(f"{field}_document_identity_mismatch")

            for row in documents:
                unit_id = str(row["unit_id"])
                try:
                    document = _json_object(
                        row["document_json"], label=f"{course_id}/{unit_id}"
                    )
                    validate_instance(document, PORTABLE_SCHEMA)
                except Exception:
                    reasons.append(f"{unit_id}:schema_failed")
                root = f"courses/{course_id}/units/{unit_id}"
                validation = _artifact_json(
                    connection,
                    build_id=build_id,
                    relative_path=f"{root}/validation.json",
                )
                review_validation = _artifact_json(
                    connection,
                    build_id=build_id,
                    relative_path=f"{root}/review-validation.json",
                )
                if not _passing_report(validation):
                    reasons.append(f"{unit_id}:validation_failed")
                if not _passing_report(review_validation):
                    reasons.append(f"{unit_id}:review_validation_failed")

            registry = registry_by_build.get(build_id)
            if registry is None:
                reasons.append("missing_independent_registry_audit")
            else:
                if int(registry.get("unit_count", -1)) != len(document_units):
                    reasons.append("registry_unit_count_mismatch")
                if int(registry.get("validated_unit_count", -1)) != len(document_units):
                    reasons.append("registry_validation_coverage_mismatch")
                if int(registry.get("audit_passed_unit_count", -1)) != len(document_units):
                    reasons.append("registry_practice_audit_coverage_mismatch")
                if registry.get("missing_audit_units") not in ([], None):
                    reasons.append("registry_has_missing_audits")
                audited_units = _unit_set(registry.get("audited_units"))
                if audited_units != document_units:
                    reasons.append("registry_audited_identity_mismatch")

            unique_reasons = list(dict.fromkeys(reasons))
            legacy_owner_approval = (
                course_id in owner_approved_legacy_courses
                and build["schema_id"] == "portable-v0.1-reviewed-legacy"
            )
            waived_reasons: list[str] = []
            if legacy_owner_approval:
                waivable = {
                    "current_portable_schema_required",
                    "missing_requested_units",
                    "missing_completed_units",
                    "missing_validated_units",
                    "missing_audited_units",
                    "missing_independent_registry_audit",
                }
                waived_reasons = [
                    reason
                    for reason in unique_reasons
                    if reason in waivable
                    or reason.endswith(":schema_failed")
                    or reason.endswith(":review_validation_failed")
                ]
            blocking_reasons = [
                reason for reason in unique_reasons if reason not in waived_reasons
            ]
            build_results.append(
                {
                    "build_id": build_id,
                    "course_id": course_id,
                    "course_version": str(build["course_version"]),
                    "unit_count": len(documents),
                    "eligible": not blocking_reasons,
                    "approval_basis": (
                        "owner-approved-reviewed-legacy"
                        if legacy_owner_approval
                        else "strict-release-gates"
                    ),
                    "current_build_review_status": str(build["review_status"]),
                    "approved_document_count": sum(
                        row["review_status"] == "approved" for row in documents
                    ),
                    "reasons": blocking_reasons,
                    "waived_reasons": waived_reasons,
                }
            )

    eligible = [item for item in build_results if item["eligible"]]
    excluded = [item for item in build_results if not item["eligible"]]
    return {
        "database": str(database),
        "database_sha256_before": _sha256_file(database),
        "registry_audit": str(registry_audit),
        "registry_audit_sha256": audit_sources[0]["sha256"],
        "audit_sources": audit_sources,
        "owner_approved_legacy_courses": sorted(owner_approved_legacy_courses),
        "archive_integrity_issues": integrity_issues,
        "eligible_build_count": len(eligible),
        "eligible_document_count": sum(item["unit_count"] for item in eligible),
        "excluded_build_count": len(excluded),
        "excluded_document_count": sum(item["unit_count"] for item in excluded),
        "builds": build_results,
    }


def apply_approval(
    database: Path,
    evaluation: dict[str, Any],
    *,
    backup: Path,
) -> None:
    eligible_ids = {
        item["build_id"] for item in evaluation["builds"] if item["eligible"]
    }
    ineligible_approved = [
        item["build_id"]
        for item in evaluation["builds"]
        if not item["eligible"]
        and (
            item["current_build_review_status"] == "approved"
            or item["approved_document_count"]
        )
    ]
    if ineligible_approved:
        raise RuntimeError(
            "ineligible builds are already approved: " + ", ".join(ineligible_approved)
        )
    if not eligible_ids:
        raise RuntimeError("no builds satisfy the approval gates")

    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        raise FileExistsError(f"backup already exists: {backup}")
    with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
        source.backup(target)

    with sqlite3.connect(database, timeout=30) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        placeholders = ",".join("?" for _ in eligible_ids)
        parameters = tuple(sorted(eligible_ids))
        build_cursor = connection.execute(
            f"""
            UPDATE studykit_builds SET review_status = 'approved'
            WHERE build_id IN ({placeholders})
            """,
            parameters,
        )
        document_cursor = connection.execute(
            f"""
            UPDATE studykit_documents SET review_status = 'approved'
            WHERE build_id IN ({placeholders})
            """,
            parameters,
        )
        if build_cursor.rowcount != len(eligible_ids):
            connection.rollback()
            raise RuntimeError("approved build row count changed during transaction")
        if document_cursor.rowcount != evaluation["eligible_document_count"]:
            connection.rollback()
            raise RuntimeError("approved document row count changed during transaction")
        connection.commit()


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--registry-audit", type=Path, default=DEFAULT_REGISTRY_AUDIT)
    parser.add_argument("--supplemental-audit", action="append", type=Path, default=[])
    parser.add_argument(
        "--owner-approved-legacy-course", action="append", default=[]
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()

    evaluation = evaluate_archive(
        args.database,
        args.registry_audit,
        supplemental_audits=tuple(args.supplemental_audit),
        owner_approved_legacy_courses=frozenset(args.owner_approved_legacy_course),
    )
    report = {
        "schema_version": "studykit-archive-human-approval-v1",
        "approved_at": datetime.now(UTC).isoformat(),
        "approved_by": args.approved_by,
        "approval_scope": (
            "Only complete portable-v0.2.1 builds with exact requested/completed/"
            "validated/audited/document identity, passing unit validators, passing "
            "independent registry audit coverage, and zero archive integrity issues. "
            "Explicit owner-approved reviewed-legacy courses retain their recorded "
            "legacy validation contract and waived-gate list."
        ),
        "applied": False,
        "backup": None,
        **evaluation,
    }
    if args.apply:
        if args.backup is None:
            parser.error("--backup is required with --apply")
        apply_approval(args.database, evaluation, backup=args.backup)
        report["applied"] = True
        report["backup"] = str(args.backup)
        report["database_sha256_after"] = _sha256_file(args.database)

    if args.report:
        _write_report(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
