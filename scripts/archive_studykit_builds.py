#!/usr/bin/env python3
"""Atomically archive selected StudyKit builds into SQLite.

Only explicitly supplied build roots are considered.  The importer validates
identity, current portable schemas (or an explicitly declared reviewed legacy
schema), unit reports, duplicate identities, hashes, and latest-only database
uniqueness before committing.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.archive import StudyKitArchive, canonical_json_bytes, sha256_bytes
from app.retrieval.schema_validation import validate_instance


PORTABLE_SCHEMA = ROOT / "skills/studykit-generator/assets/schemas/studykit.schema.json"
TEXT_SUFFIXES = frozenset({".json", ".yaml", ".yml", ".md", ".txt"})


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _report_passed(path: Path) -> bool:
    report = _json_object(path)
    if report.get("valid") is True:
        return True
    return report.get("status") in {"passed", "succeeded", "valid"}


def _build_metadata(build_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    result = _json_object(build_root / "result.json")
    run_path = build_root / "run.json"
    run = _json_object(run_path) if run_path.is_file() else {}
    return result, run


def _course_identity(documents: list[dict[str, Any]]) -> tuple[str, str]:
    identities = {(item.get("course_id"), item.get("course_version")) for item in documents}
    if len(identities) != 1:
        raise ValueError(f"build contains multiple course/version identities: {identities}")
    course_id, version = next(iter(identities))
    if not isinstance(course_id, str) or not course_id:
        raise ValueError("course_id must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError("course_version must be a non-empty string")
    return course_id, version


def _artifact_rows(build_root: Path, build_id: str) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for path in sorted(build_root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(build_root).as_posix()
        content = path.read_bytes()
        unit_id = None
        parts = relative.split("/")
        if "units" in parts:
            index = parts.index("units")
            if index + 1 < len(parts):
                unit_id = parts[index + 1]
        media_type = mimetypes.guess_type(path.name)[0] or "text/plain"
        rows.append(
            (
                build_id,
                relative,
                unit_id,
                media_type,
                len(content),
                sha256_bytes(content),
                content,
            )
        )
    return rows


def _prepare_build(
    build_root: Path,
    *,
    legacy_reviewed: bool,
    review_status: str,
) -> dict[str, Any]:
    build_root = build_root.resolve()
    result, run = _build_metadata(build_root)
    final_paths = sorted(build_root.glob("courses/*/units/*/05-studykit.json"))
    if not final_paths:
        raise ValueError(f"{build_root}: no final StudyKit documents")

    documents: list[dict[str, Any]] = []
    units: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    for path in final_paths:
        document = _json_object(path)
        if not legacy_reviewed:
            validate_instance(document, PORTABLE_SCHEMA)
        if review_status == "approved":
            review = document.get("review")
            if (
                document.get("status") not in {"reviewed", "published"}
                or not isinstance(review, dict)
                or review.get("human_review_status") != "approved"
            ):
                raise ValueError(
                    f"{path}: approved import requires reviewed/published status "
                    "and review.human_review_status=approved"
                )
        unit_id = document.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id or unit_id in seen_units:
            raise ValueError(f"{path}: invalid or duplicate unit_id {unit_id!r}")
        seen_units.add(unit_id)
        for report_name in ("validation.json", "review-validation.json"):
            report_path = path.parent / report_name
            if legacy_reviewed and report_name == "review-validation.json" and not report_path.is_file():
                continue
            if not report_path.is_file() or not _report_passed(report_path):
                raise ValueError(f"{report_path}: required passing report missing or failed")
        canonical = canonical_json_bytes(document).decode("utf-8")
        markdown_path = path.parent / "studykit.md"
        units.append(
            {
                "unit_id": unit_id,
                "title": str(document.get("title") or unit_id),
                "status": str(document.get("status") or "draft"),
                "document_json": canonical,
                "document_sha256": sha256_bytes(canonical.encode("utf-8")),
                "markdown": markdown_path.read_text(encoding="utf-8")
                if markdown_path.is_file()
                else None,
            }
        )
        documents.append(document)

    course_id, course_version = _course_identity(documents)
    result_build_id = result.get("build_id")
    build_id = str(result_build_id or build_root.name)
    if len(build_id) != 64 or any(char not in "0123456789abcdef" for char in build_id):
        raise ValueError(f"{build_root}: invalid build_id {build_id!r}")
    digests = [f"{unit['unit_id']}:{unit['document_sha256']}" for unit in sorted(units, key=lambda x: x["unit_id"])]
    content_sha256 = sha256_bytes("\n".join(digests).encode("utf-8"))
    schema_id = "portable-v0.1-reviewed-legacy" if legacy_reviewed else "portable-v0.2.1"
    metadata = {
        "result": result,
        "run": run,
        "source_build_directory": build_root.name,
        "legacy_reviewed": legacy_reviewed,
    }
    return {
        "build_id": build_id,
        "course_id": course_id,
        "course_version": course_version,
        "build_status": str(result.get("status") or "unknown"),
        "review_status": review_status,
        "schema_id": schema_id,
        "quality_mode": run.get("quality_mode"),
        "delivery_policy": run.get("delivery_policy"),
        "unit_count": len(units),
        "content_sha256": content_sha256,
        "source_label": f"outputs/{build_root.name}",
        "metadata_json": canonical_json_bytes(metadata).decode("utf-8"),
        "units": units,
        "artifacts": _artifact_rows(build_root, build_id),
    }


def archive_builds(
    database: Path,
    builds: list[tuple[Path, bool]],
    *,
    review_status: str = "validated_draft",
) -> dict[str, Any]:
    prepared = [
        _prepare_build(path, legacy_reviewed=legacy, review_status=review_status)
        for path, legacy in builds
    ]
    identities = [(item["course_id"], item["course_version"]) for item in prepared]
    if len(identities) != len(set(identities)):
        raise ValueError("more than one selected build has the same course/version identity")

    archive = StudyKitArchive(database)
    archive.initialize()
    imported_at = datetime.now(timezone.utc).isoformat()
    with archive.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            selected = set(identities)
            existing = connection.execute(
                "SELECT course_id, course_version FROM studykit_builds"
            ).fetchall()
            for row in existing:
                identity = (row["course_id"], row["course_version"])
                if identity not in selected:
                    connection.execute(
                        "DELETE FROM studykit_builds WHERE course_id = ? AND course_version = ?",
                        identity,
                    )
            for item in prepared:
                connection.execute(
                    "DELETE FROM studykit_builds WHERE course_id = ? AND course_version = ?",
                    (item["course_id"], item["course_version"]),
                )
                connection.execute(
                    """
                    INSERT INTO studykit_builds (
                        build_id, course_id, course_version, build_status,
                        review_status, schema_id, quality_mode, delivery_policy,
                        unit_count, content_sha256, imported_at, source_label,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["build_id"], item["course_id"], item["course_version"],
                        item["build_status"], item["review_status"], item["schema_id"],
                        item["quality_mode"], item["delivery_policy"], item["unit_count"],
                        item["content_sha256"], imported_at, item["source_label"],
                        item["metadata_json"],
                    ),
                )
                for unit in item["units"]:
                    connection.execute(
                        """
                        INSERT INTO studykit_documents (
                            course_id, course_version, unit_id, build_id, title,
                            document_status, review_status, schema_id,
                            document_sha256, document_json, learner_markdown
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["course_id"], item["course_version"], unit["unit_id"],
                            item["build_id"], unit["title"], unit["status"],
                            item["review_status"], item["schema_id"],
                            unit["document_sha256"], unit["document_json"], unit["markdown"],
                        ),
                    )
                connection.executemany(
                    """
                    INSERT INTO studykit_artifacts (
                        build_id, relative_path, unit_id, media_type,
                        byte_size, sha256, content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    item["artifacts"],
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    issues = archive.verify_integrity()
    if issues:
        raise RuntimeError("archive integrity failed: " + "; ".join(issues[:5]))
    return {
        "database": str(database),
        "build_count": len(prepared),
        "document_count": sum(item["unit_count"] for item in prepared),
        "artifact_count": sum(len(item["artifacts"]) for item in prepared),
        "builds": [
            {key: item[key] for key in ("build_id", "course_id", "course_version", "build_status", "review_status", "schema_id", "unit_count", "content_sha256")}
            for item in prepared
        ],
        "integrity_issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--build", action="append", type=Path, default=[])
    parser.add_argument("--legacy-reviewed-build", action="append", type=Path, default=[])
    parser.add_argument(
        "--review-status", choices=("validated_draft", "approved"), default="validated_draft"
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    selected = [(path, False) for path in args.build] + [
        (path, True) for path in args.legacy_reviewed_build
    ]
    if not selected:
        parser.error("at least one --build or --legacy-reviewed-build is required")
    report = archive_builds(args.database, selected, review_status=args.review_status)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.report.with_suffix(args.report.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(temporary, args.report)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
