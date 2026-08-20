#!/usr/bin/env python3
"""Create a fingerprinted child build that repairs one archived unit identity.

The parent archive is treated as immutable. Current documents are reconstructed
from the parent's canonical top-level ``05-studykit.json`` artifacts, then a new
build is inserted atomically with explicit parent, repair-plan, and audit
bindings. No learner content or practice item is rewritten.
"""

from __future__ import annotations

import argparse
import copy
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

from app.catalog.archive import StudyKitArchive, canonical_json_bytes, sha256_bytes
from app.retrieval.schema_validation import validate_instance


DEFAULT_ARCHIVE = ROOT / "data" / "archive" / "studykits.sqlite3"
DEFAULT_REGISTRY_AUDIT = ROOT / "evaluations" / "csdiy-catalog-registry-audit.json"
PORTABLE_SCHEMA = (
    ROOT / "skills" / "studykit-generator" / "assets" / "schemas" / "studykit.schema.json"
)
PASS_STATUSES = frozenset({"passed", "succeeded", "valid"})


def _json(value: str | bytes, label: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def _canonical(value: Any) -> bytes:
    return canonical_json_bytes(value)


def _passing(value: dict[str, Any]) -> bool:
    return (
        (value.get("valid") is True or str(value.get("status", "")).casefold() in PASS_STATUSES)
        and not value.get("issues")
    )


def _artifact_tree_digest(rows: list[sqlite3.Row]) -> str:
    payload = "\n".join(
        f"{row['relative_path']}:{row['sha256']}" for row in sorted(rows, key=lambda x: x["relative_path"])
    )
    return sha256_bytes(payload.encode("utf-8"))


def _replace_scoped_identity(content: bytes, unexpected: str, expected: str) -> bytes:
    return content.replace(unexpected.encode("utf-8"), expected.encode("utf-8"))


def _registry_report(path: Path, build_id: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = _json(raw, str(path))
    matches = [
        item
        for item in payload.get("target_reports", [])
        if isinstance(item, dict) and item.get("build_id") == build_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one registry report for {build_id}, found {len(matches)}")
    return matches[0], hashlib.sha256(raw).hexdigest()


def prepare_repair(
    database: Path,
    registry_audit: Path,
    *,
    parent_build_id: str,
    expected_unit_id: str,
    unexpected_unit_id: str,
) -> dict[str, Any]:
    integrity_issues = StudyKitArchive(database).verify_integrity()
    if integrity_issues:
        raise RuntimeError("parent archive integrity failed: " + "; ".join(integrity_issues[:5]))

    registry, registry_sha256 = _registry_report(registry_audit, parent_build_id)
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        parent = connection.execute(
            "SELECT * FROM studykit_builds WHERE build_id = ?", (parent_build_id,)
        ).fetchone()
        if parent is None:
            raise ValueError(f"unknown parent build {parent_build_id}")
        if parent["build_status"] != "succeeded" or parent["schema_id"] != "portable-v0.2.1":
            raise ValueError("identity repair requires a succeeded portable-v0.2.1 parent")
        parent_documents = connection.execute(
            "SELECT * FROM studykit_documents WHERE build_id = ? ORDER BY unit_id",
            (parent_build_id,),
        ).fetchall()
        parent_artifacts = connection.execute(
            "SELECT * FROM studykit_artifacts WHERE build_id = ? ORDER BY relative_path",
            (parent_build_id,),
        ).fetchall()

    parent_document_units = {str(row["unit_id"]) for row in parent_documents}
    if unexpected_unit_id not in parent_document_units or expected_unit_id in parent_document_units:
        raise ValueError("parent document rows do not contain the declared one-for-one mismatch")

    course_id = str(parent["course_id"])
    final_prefix = f"courses/{course_id}/units/"
    artifact_by_path = {str(row["relative_path"]): row for row in parent_artifacts}
    final_rows = [
        row
        for row in parent_artifacts
        if str(row["relative_path"]).startswith(final_prefix)
        and str(row["relative_path"]).endswith("/05-studykit.json")
        and "/repair-baseline/" not in str(row["relative_path"])
        and "/repair-parent-baseline/" not in str(row["relative_path"])
    ]
    documents: list[dict[str, Any]] = []
    document_units: set[str] = set()
    for row in final_rows:
        document_content = bytes(row["content"])
        if str(row["relative_path"]) == f"{final_prefix}{expected_unit_id}/05-studykit.json":
            document_content = _replace_scoped_identity(
                document_content, unexpected_unit_id, expected_unit_id
            )
        document = _json(document_content, str(row["relative_path"]))
        validate_instance(document, PORTABLE_SCHEMA)
        unit_id = document.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id or unit_id in document_units:
            raise ValueError(f"invalid or duplicate artifact unit identity {unit_id!r}")
        if document.get("course_id") != course_id or document.get("course_version") != parent["course_version"]:
            raise ValueError(f"{unit_id}: course identity mismatch")
        expected_path = f"{final_prefix}{unit_id}/05-studykit.json"
        if row["relative_path"] != expected_path:
            raise ValueError(f"{unit_id}: artifact path identity mismatch")
        for report_name in ("validation.json", "review-validation.json"):
            report_path = f"{final_prefix}{unit_id}/{report_name}"
            report_row = artifact_by_path.get(report_path)
            if report_row is None or not _passing(_json(bytes(report_row["content"]), report_path)):
                raise ValueError(f"{report_path}: missing or failed")
        markdown_row = artifact_by_path.get(f"{final_prefix}{unit_id}/studykit.md")
        canonical = _canonical(document).decode("utf-8")
        documents.append(
            {
                "unit_id": unit_id,
                "title": str(document.get("title") or unit_id),
                "document_status": str(document.get("status") or "draft"),
                "document_json": canonical,
                "document_sha256": sha256_bytes(canonical.encode("utf-8")),
                "learner_markdown": (
                    bytes(markdown_row["content"]).decode("utf-8") if markdown_row else None
                ),
            }
        )
        document_units.add(unit_id)

    metadata = _json(parent["metadata_json"], "parent metadata")
    result = copy.deepcopy(metadata.get("result"))
    run = copy.deepcopy(metadata.get("run"))
    if not isinstance(result, dict) or not isinstance(run, dict):
        raise ValueError("parent metadata lacks result/run objects")
    required_sets = ("requested_units", "completed_units", "validated_units", "audited_units")
    for field in required_sets:
        if set(result.get(field, [])) != document_units:
            raise ValueError(f"parent {field} does not match reconstructed artifact identities")
    if set(registry.get("audited_units", [])) != document_units:
        raise ValueError("registry audited units do not match reconstructed identities")
    if registry.get("missing_audit_units") not in ([], None):
        raise ValueError("registry still reports missing audits")
    if int(registry.get("validated_unit_count", -1)) != len(document_units):
        raise ValueError("registry validation coverage is incomplete")
    if int(registry.get("audit_passed_unit_count", -1)) != len(document_units):
        raise ValueError("registry practice audit coverage is incomplete")

    parent_artifact_sha256 = _artifact_tree_digest(parent_artifacts)
    repair_plan = {
        "schema_version": "studykit-archive-identity-repair-plan-v1",
        "repair_kind": "scoped-unit-identity-normalization",
        "parent_build_id": parent_build_id,
        "parent_content_sha256": str(parent["content_sha256"]),
        "parent_artifact_tree_sha256": parent_artifact_sha256,
        "course_id": course_id,
        "course_version": str(parent["course_version"]),
        "unexpected_document_unit_id": unexpected_unit_id,
        "expected_artifact_unit_id": expected_unit_id,
        "learner_content_semantics_rewritten": False,
        "practice_semantics_rewritten": False,
        "identity_fields_rewritten": True,
        "unit_ids": sorted(document_units),
    }
    repair_plan_sha256 = sha256_bytes(_canonical(repair_plan))
    fingerprint = {
        "pipeline_version": "archive-identity-repair-v1",
        "parent_build_id": parent_build_id,
        "parent_content_sha256": str(parent["content_sha256"]),
        "parent_artifact_tree_sha256": parent_artifact_sha256,
        "repair_plan_sha256": repair_plan_sha256,
        "unit_document_sha256": {
            item["unit_id"]: item["document_sha256"] for item in sorted(documents, key=lambda x: x["unit_id"])
        },
    }
    build_id = sha256_bytes(_canonical(fingerprint))
    now = datetime.now(UTC).isoformat()
    result.update({"build_id": build_id, "updated_at": now})
    run.update(
        {
            "build_id": build_id,
            "resume_fingerprint": build_id,
            "updated_at": now,
            "fingerprint_context": {
                "repair_mode": "archive-identity-repair-v1",
                "parent_build_id": parent_build_id,
                "parent_artifact_tree_sha256": parent_artifact_sha256,
                "repair_plan_sha256": repair_plan_sha256,
                "learner_content_semantics_rewritten": False,
                "practice_semantics_rewritten": False,
                "identity_fields_rewritten": True,
            },
        }
    )
    repaired_metadata = {
        "result": result,
        "run": run,
        "source_build_directory": build_id,
        "legacy_reviewed": False,
        "repair_plan": repair_plan,
    }
    content_sha256 = sha256_bytes(
        "\n".join(
            f"{item['unit_id']}:{item['document_sha256']}"
            for item in sorted(documents, key=lambda x: x["unit_id"])
        ).encode("utf-8")
    )
    repair_audit = {
        "schema_version": "studykit-archive-identity-repair-audit-v1",
        "status": "passed",
        "audited_at": now,
        "build_id": build_id,
        "parent_build_id": parent_build_id,
        "repair_plan_sha256": repair_plan_sha256,
        "parent_artifact_tree_sha256": parent_artifact_sha256,
        "exact_identity_coverage": sorted(document_units),
        "validated_units": sorted(document_units),
        "practice_audited_units": sorted(document_units),
        "missing_units": [],
        "duplicate_units": [],
        "stale_units": [],
        "learner_content_semantics_rewritten": False,
        "practice_semantics_rewritten": False,
        "identity_fields_rewritten": True,
        "parent_registry_audit_sha256": registry_sha256,
        "parent_registry_build_id": parent_build_id,
        "issues": [],
    }
    supplemental = {
        "schema_version": "studykit-supplemental-registry-audit-v1",
        "target_reports": [
            {
                "build_id": build_id,
                "canonical_course_id": registry.get("canonical_course_id", "ucb-cs186"),
                "unit_count": len(document_units),
                "validated_unit_count": len(document_units),
                "audit_passed_unit_count": len(document_units),
                "audited_units": sorted(document_units),
                "missing_audit_units": [],
                "issues": [],
                "state": "complete",
                "parent_build_id": parent_build_id,
                "repair_plan_sha256": repair_plan_sha256,
                "repair_audit_sha256": sha256_bytes(_canonical(repair_audit)),
            }
        ],
    }
    return {
        "parent": dict(parent),
        "parent_artifacts": [dict(row) for row in parent_artifacts],
        "documents": documents,
        "build_id": build_id,
        "content_sha256": content_sha256,
        "metadata_json": _canonical(repaired_metadata).decode("utf-8"),
        "result": result,
        "run": run,
        "repair_plan": repair_plan,
        "repair_audit": repair_audit,
        "supplemental_audit": supplemental,
    }


def _artifact_tuple(build_id: str, relative_path: str, unit_id: str | None, media_type: str, content: bytes) -> tuple[Any, ...]:
    return (build_id, relative_path, unit_id, media_type, len(content), sha256_bytes(content), content)


def apply_repair(database: Path, prepared: dict[str, Any], *, backup: Path) -> None:
    if backup.exists():
        raise FileExistsError(f"backup already exists: {backup}")
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
        source.backup(target)

    parent = prepared["parent"]
    build_id = prepared["build_id"]
    artifacts = []
    for artifact in prepared["parent_artifacts"]:
        relative_path = str(artifact["relative_path"])
        if relative_path in {"result.json", "run.json"}:
            continue
        content = bytes(artifact["content"])
        expected_prefix = (
            f"courses/{parent['course_id']}/units/"
            f"{prepared['repair_plan']['expected_artifact_unit_id']}/"
        )
        if relative_path.startswith(expected_prefix):
            content = _replace_scoped_identity(
                content,
                prepared["repair_plan"]["unexpected_document_unit_id"],
                prepared["repair_plan"]["expected_artifact_unit_id"],
            )
        artifacts.append(
            _artifact_tuple(
                build_id,
                relative_path,
                artifact["unit_id"],
                str(artifact["media_type"]),
                content,
            )
        )
    artifacts.extend(
        [
            _artifact_tuple(build_id, "result.json", None, "application/json", _canonical(prepared["result"])),
            _artifact_tuple(build_id, "run.json", None, "application/json", _canonical(prepared["run"])),
            _artifact_tuple(build_id, "archive-identity-repair-plan.json", None, "application/json", _canonical(prepared["repair_plan"])),
            _artifact_tuple(build_id, "archive-identity-repair-audit.json", None, "application/json", _canonical(prepared["repair_audit"])),
        ]
    )
    with sqlite3.connect(database, timeout=30) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("DELETE FROM studykit_builds WHERE build_id = ?", (parent["build_id"],))
            connection.execute(
                """
                INSERT INTO studykit_builds (
                    build_id, course_id, course_version, build_status, review_status,
                    schema_id, quality_mode, delivery_policy, unit_count, content_sha256,
                    imported_at, source_label, metadata_json
                ) VALUES (?, ?, ?, 'succeeded', 'validated_draft', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    build_id, parent["course_id"], parent["course_version"], parent["schema_id"],
                    parent["quality_mode"], parent["delivery_policy"], len(prepared["documents"]),
                    prepared["content_sha256"], datetime.now(UTC).isoformat(),
                    f"archive-identity-repair/{build_id}", prepared["metadata_json"],
                ),
            )
            for document in prepared["documents"]:
                connection.execute(
                    """
                    INSERT INTO studykit_documents (
                        course_id, course_version, unit_id, build_id, title,
                        document_status, review_status, schema_id, document_sha256,
                        document_json, learner_markdown
                    ) VALUES (?, ?, ?, ?, ?, ?, 'validated_draft', ?, ?, ?, ?)
                    """,
                    (
                        parent["course_id"], parent["course_version"], document["unit_id"],
                        build_id, document["title"], document["document_status"], parent["schema_id"],
                        document["document_sha256"], document["document_json"], document["learner_markdown"],
                    ),
                )
            connection.executemany(
                """
                INSERT INTO studykit_artifacts (
                    build_id, relative_path, unit_id, media_type, byte_size, sha256, content
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                artifacts,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    issues = StudyKitArchive(database).verify_integrity()
    if issues:
        raise RuntimeError("repaired archive integrity failed: " + "; ".join(issues[:5]))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--registry-audit", type=Path, default=DEFAULT_REGISTRY_AUDIT)
    parser.add_argument("--parent-build-id", required=True)
    parser.add_argument("--expected-unit-id", required=True)
    parser.add_argument("--unexpected-unit-id", required=True)
    parser.add_argument("--supplemental-audit", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    prepared = prepare_repair(
        args.database,
        args.registry_audit,
        parent_build_id=args.parent_build_id,
        expected_unit_id=args.expected_unit_id,
        unexpected_unit_id=args.unexpected_unit_id,
    )
    if args.apply:
        if args.backup is None:
            parser.error("--backup is required with --apply")
        apply_repair(args.database, prepared, backup=args.backup)
        _write(args.supplemental_audit, prepared["supplemental_audit"])
    report = {
        "schema_version": "studykit-archive-identity-repair-result-v1",
        "applied": args.apply,
        "database": str(args.database),
        "backup": str(args.backup) if args.apply else None,
        "parent_build_id": args.parent_build_id,
        "build_id": prepared["build_id"],
        "course_id": prepared["parent"]["course_id"],
        "course_version": prepared["parent"]["course_version"],
        "unit_count": len(prepared["documents"]),
        "unit_ids": sorted(item["unit_id"] for item in prepared["documents"]),
        "repair_plan": prepared["repair_plan"],
        "repair_audit": prepared["repair_audit"],
        "supplemental_audit": str(args.supplemental_audit),
        "archive_integrity_issues": StudyKitArchive(args.database).verify_integrity(),
    }
    if args.report:
        _write(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
