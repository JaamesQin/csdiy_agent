#!/usr/bin/env python3
"""Create a new fingerprinted portable StudyKit build from a catalog manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PIPELINE_VERSION = "portable-studykit-pipeline-v0.2.2"
# Bump the portable-build fingerprint whenever the authoring contract changes.
# The content-grounded practice contract, objective-to-practice alignment,
# provenance completeness, and mandatory per-practice audit are intentionally
# not resumable from earlier host-authored builds.
PROMPT_VERSION = "host-authored-studykit-v0.2.2-feedback-contract-v1"
PAGE_SELECTOR_VERSION = "review-pages-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def unit_source(unit: dict[str, Any]) -> dict[str, Any]:
    sources = unit.get("sources") or []
    if len(sources) != 1:
        raise ValueError(f"unit {unit.get('unit_id')} must have exactly one source")
    return sources[0]


def make_build(
    catalog_manifest_path: Path,
    repository_root: Path,
    output_base: Path,
    quality_mode: str,
    delivery_policy: str,
    parallel_units: str,
    coordinator_id: str = "coordinator-1",
    fingerprint_context: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    catalog = yaml.safe_load(catalog_manifest_path.read_text(encoding="utf-8")) or {}
    course_id = str(catalog.get("course_id") or "")
    course_version = str(catalog.get("course_version") or "")
    units = catalog.get("units") or []
    if not course_id or not course_version or not units:
        raise ValueError("catalog manifest requires course_id, course_version, and units")
    unit_records = []
    for unit in units:
        source = unit_source(unit)
        chunks_rel = source.get("chunks_path") or f"data/sources/{course_id}/{unit['unit_id']}/chunks.jsonl"
        chunks_path = repository_root / chunks_rel
        if not chunks_path.is_file():
            raise FileNotFoundError(f"missing chunks for {unit['unit_id']}: {chunks_path}")
        unit_records.append(
            {
                "unit_id": unit["unit_id"],
                "order": unit.get("order"),
                "title": unit.get("official_resource_title") or unit.get("title") or unit["unit_id"],
                "material_set_id": source.get("material_set_id") or f"{course_id}-{unit['unit_id']}",
                "source_id": source.get("source_id"),
                "source_path": source.get("local_path"),
                "chunks_path": chunks_rel,
                "chunks_sha256": sha256_file(chunks_path),
                "source_sha256": source.get("sha256"),
                "source_url": source.get("official_url") or source.get("download_url"),
                "anchor_type": source.get("anchor_type", "page"),
                "parser_version": source.get("parser_version", "pdf-page-v0.2"),
            }
        )
    fingerprint_payload = {
        "catalog_manifest_sha256": sha256_file(catalog_manifest_path),
        "units": unit_records,
        "quality_mode": quality_mode,
        "delivery_policy": delivery_policy,
        "page_selector_version": PAGE_SELECTOR_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "prompt_version": PROMPT_VERSION,
        "schema_version": sha256_file(repository_root / "schemas" / "source_chunk.schema.json"),
    }
    if fingerprint_context is not None:
        fingerprint_payload["fingerprint_context"] = fingerprint_context
    build_id = hashlib.sha256(canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()
    build_root = output_base / course_id / build_id
    if build_root.exists():
        existing = build_root / "run.json"
        if not existing.is_file() or json.loads(existing.read_text(encoding="utf-8")).get("resume_fingerprint") != build_id:
            raise FileExistsError(f"existing build has a different fingerprint: {build_root}")
        return build_root, json.loads(existing.read_text(encoding="utf-8"))

    for unit in unit_records:
        (build_root / "courses" / course_id / "units" / unit["unit_id"]).mkdir(parents=True, exist_ok=True)
    (build_root / "ingestion").mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "manifest_version": "0.2",
        "pipeline_version": PIPELINE_VERSION,
        "prompt_version": PROMPT_VERSION,
        "quality_mode": quality_mode,
        "page_selector_version": PAGE_SELECTOR_VERSION,
        "delivery_policy": delivery_policy,
        "parallel_units": parallel_units,
        "coordinator_id": coordinator_id,
        "coordinator_scope": "single-build",
        "global_merge_owner": "global-coordinator",
        "course_id": course_id,
        "course_version": course_version,
        "title": catalog.get("title", ""),
        "language": "zh-CN",
        "material_sets": [
            {
                "material_set_id": unit["material_set_id"],
                "scope": "public",
                "owner_id": None,
                "input_fingerprint": unit["chunks_sha256"],
                "unit_id": unit["unit_id"],
            }
            for unit in unit_records
        ],
        "sources": unit_records,
        "units": [
            {
                "unit_id": unit["unit_id"],
                "order": unit["order"],
                "title": unit["title"],
                "material_set_id": unit["material_set_id"],
                "source_id": unit["source_id"],
                "chunks_path": unit["chunks_path"],
                "anchor_type": unit["anchor_type"],
            }
            for unit in unit_records
        ],
        "grouping_evidence": [{"source": str(catalog_manifest_path.relative_to(repository_root)), "method": "catalog_manifest_units"}],
        "warnings": list(catalog.get("limitations", [])),
        "fingerprint_payload": fingerprint_payload,
    }
    if fingerprint_context is not None:
        manifest["fingerprint_context"] = fingerprint_context
    (build_root / "manifest.yaml").write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    run = {
        "run_version": "0.2",
        "build_id": build_id,
        "status": "authoring",
        "started_at": now,
        "updated_at": now,
        "course_id": course_id,
        "course_version": course_version,
        "quality_mode": quality_mode,
        "delivery_policy": delivery_policy,
        "parallel_units": parallel_units,
        "coordinator_id": coordinator_id,
        "coordinator_scope": "single-build",
        "global_merge_owner": "global-coordinator",
        "worker_count": None,
        "requested_units": [unit["unit_id"] for unit in unit_records],
        "completed_units": [],
        "failed_units": [],
        "authoring_agent": "host_codex_agents",
        "provider_client_used": False,
        "model_api_calls": 0,
        "resume_fingerprint": build_id,
        "fingerprint_payload": fingerprint_payload,
    }
    if fingerprint_context is not None:
        run["fingerprint_context"] = fingerprint_context
    (build_root / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {
        "status": "partial",
        "build_id": build_id,
        "courses": [course_id],
        "completed_units": [],
        "failed_stage": None,
        "retry_count": 0,
        "recoverable": True,
        "artifacts": {"manifest": "manifest.yaml", "run": "run.json", "batch_summary": "batch-summary.json"},
        "coordinator_id": coordinator_id,
        "issues": [],
        "next_action": "author_units",
    }
    (build_root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batch = {
        "batch_version": "0.2",
        "build_id": build_id,
        "status": "partial",
        "worker_count": None,
        "coordinator_id": coordinator_id,
        "requested_units": [unit["unit_id"] for unit in unit_records],
        "succeeded_units": [],
        "failed_units": [],
        "unit_count": len(unit_records),
        "completed_at": None,
    }
    (build_root / "batch-summary.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return build_root, run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--output-base", type=Path, default=Path("outputs"))
    parser.add_argument("--quality-mode", choices=("fast", "standard", "strict"), default="standard")
    parser.add_argument("--delivery-policy", choices=("draft", "publish"), default="draft")
    parser.add_argument("--parallel-units", default="auto")
    parser.add_argument("--coordinator-id", default="coordinator-1")
    parser.add_argument("--fingerprint-context", type=Path, help="JSON object included only in the build fingerprint")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_root, run = make_build(
        args.catalog_manifest.resolve(),
        args.repository_root.resolve(),
        args.output_base,
        args.quality_mode,
        args.delivery_policy,
        args.parallel_units,
        args.coordinator_id,
        json.loads(args.fingerprint_context.read_text(encoding="utf-8")) if args.fingerprint_context else None,
    )
    print(json.dumps({"build_root": str(build_root), "build_id": run["build_id"], "unit_count": len(run["requested_units"])}, ensure_ascii=False, indent=2))
