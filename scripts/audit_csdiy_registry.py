#!/usr/bin/env python3
"""Reconcile a CSDIY registry with manifests, chunks, and local StudyKit builds.

The audit is read-only unless ``--update`` is supplied. It never downloads
anything and never treats an HTTP or model result as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def normalize(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


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
        raw = root / raw_path if raw_path else None
        chunks = root / chunks_path
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
    course_root = root / "outputs" / course_id
    records: list[dict[str, Any]] = []
    if not course_root.is_dir():
        return records
    for build_root in sorted(path for path in course_root.iterdir() if path.is_dir()):
        result = json_file(build_root / "result.json") or {}
        index_exists = (build_root / "STUDYKIT_INDEX.md").is_file()
        unit_root = build_root / "courses" / course_id / "units"
        units: list[dict[str, Any]] = []
        if unit_root.is_dir():
            for unit_dir in sorted(path for path in unit_root.iterdir() if path.is_dir()):
                final = json_file(unit_dir / "05-studykit.json")
                validation = json_file(unit_dir / "validation.json") or json_file(unit_dir / "review-validation.json")
                units.append(
                    {
                        "unit_id": unit_dir.name,
                        "final_exists": final is not None,
                        "validation_exists": validation is not None,
                        "status": final.get("status") if final else None,
                    }
                )
        records.append(
            {
                "build_id": build_root.name,
                "path": str(build_root),
                "result_status": result.get("status"),
                "index_exists": index_exists,
                "unit_records": units,
            }
        )
    return records


def reconcile_target(target: dict[str, Any], manifest_records: list[dict[str, Any]], output_records_for_target: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    best_output = next(
        (record for record in reversed(output_records_for_target) if record.get("result_status") == "succeeded"),
        output_records_for_target[-1] if output_records_for_target else None,
    )
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
    validated_units = []
    if best_output:
        validated_units = [
            unit["unit_id"]
            for unit in best_output["unit_records"]
            if unit.get("final_exists") and unit.get("validation_exists") and unit.get("status") in {"draft", "published"}
        ]
    complete = bool(
        best_output
        and best_output.get("result_status") == "succeeded"
        and best_output.get("index_exists")
        and unit_count > 0
        and len(validated_units) == unit_count
        and not issues
    )
    if complete:
        state = "complete"
        next_action = "complete"
    elif best_output:
        state = "authoring"
        next_action = "finish_and_validate_units"
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
    return {
        "state": state,
        "next_action": next_action,
        "manifest_path": target.get("manifest_path"),
        "unit_count": unit_count,
        "chunk_count": chunk_count,
        "validated_unit_count": len(validated_units),
        "build_id": best_output.get("build_id") if best_output else None,
        "issues": issues,
        "manifest_unit_records": manifest_records,
        "output_records": output_records_for_target,
    }


def find_manifest_for_target(target: dict[str, Any], manifests: list[tuple[Path, dict[str, Any]]]) -> tuple[Path, dict[str, Any]] | None:
    matches = [(path, manifest) for path, manifest in manifests if manifest_matches_target(manifest, target)]
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
        target_reports.append({"canonical_course_id": target.get("canonical_course_id"), "manifest_path": str(path.relative_to(repository_root)) if path else None, **reconciliation})
    orphan_manifests = [str(path.relative_to(repository_root)) for path, _ in manifests if str(path) not in matched_manifest_paths]
    known_manifest_course_ids = {str(manifest.get("course_id")) for _, manifest in manifests}
    orphan_builds: list[str] = []
    outputs_root = repository_root / "outputs"
    if outputs_root.is_dir():
        for course_dir in sorted(path for path in outputs_root.iterdir() if path.is_dir()):
            if course_dir.name not in known_manifest_course_ids:
                orphan_builds.extend(str(path.relative_to(repository_root)) for path in course_dir.iterdir() if path.is_dir())
    false_complete = [report["canonical_course_id"] for report in target_reports if report["state"] != "complete" and any(target.get("canonical_course_id") == report["canonical_course_id"] and target.get("state") == "complete" for target in registry.get("course_targets", []))]
    unresolved_leaves = [leaf["leaf_key"] for leaf in registry.get("nav_leaves", []) if leaf.get("classification_review_status") in {"needs_review", "pending_independent_audit"}]
    audit = {
        "audit_version": "0.1",
        "audited_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "registry_path": str(registry_path),
        "pinned_commit": registry.get("source_catalog", {}).get("pinned_commit"),
        "course_target_count": len(registry.get("course_targets", [])),
        "unclassified_or_unreviewed_leaf_count": len(unresolved_leaves),
        "duplicate_canonical_ids": duplicate_ids,
        "false_complete_targets": false_complete,
        "orphan_manifests": orphan_manifests,
        "orphan_builds": orphan_builds,
        "target_reports": target_reports,
        "state_counts": dict(Counter(report["state"] for report in target_reports)),
        "global_gate": "succeeded" if not unresolved_leaves and not duplicate_ids and not false_complete and not orphan_manifests and not orphan_builds and all(report["state"] == "complete" for report in target_reports) else "partial",
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
                    "chunk_count": report["chunk_count"],
                    "build_id": report["build_id"],
                    "output_index": next((record["path"] for record in report["output_records"] if record["index_exists"]), None),
                    "source_gaps": [issue for issue in report["issues"] if issue["code"] not in {"missing_chunks", "invalid_chunk_json"}],
                }
            )
            target["progress"].update({"state": report["state"], "last_successful_checkpoint": report["state"]})
        registry["summary"]["target_states"] = dict(Counter(target.get("state") for target in registry.get("course_targets", [])))
        atomic_write_yaml(args.registry, registry)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: audit[key] for key in ("course_target_count", "state_counts", "false_complete_targets", "orphan_manifests", "orphan_builds", "global_gate")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
