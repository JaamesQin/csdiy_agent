#!/usr/bin/env python3
"""Checkpoint deterministic EvidencePlans for a prepared catalog build.

This coordinator-only helper does not author learner content and never calls a
model.  It records a small, reproducible set of source-backed page candidates
for units that do not yet have stage 01.  The host author must review and
expand these plans before stages 02--05 are considered complete.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


def load_chunks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clean_excerpt(content: str) -> str:
    return re.sub(r"\s+", " ", content).strip()[:240]


def make_plan(catalog: dict[str, Any], unit: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    source = (unit.get("sources") or [{}])[0]
    nonempty = [chunk for chunk in chunks if str(chunk.get("content", "")).strip()]
    if not nonempty:
        raise ValueError(f"{unit['unit_id']} has no nonempty chunks")
    candidates: list[dict[str, Any]] = []
    indexes = [0]
    if len(nonempty) > 2:
        indexes.extend([len(nonempty) // 3, (2 * len(nonempty)) // 3])
    if len(nonempty) > 1:
        indexes.append(len(nonempty) - 1)
    seen: set[tuple[str, str]] = set()
    for index in indexes:
        chunk = nonempty[index]
        anchor = chunk["anchor"]
        key = (str(chunk["source_id"]), f"{anchor['type']}:{anchor['value']}")
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "chunk_id": chunk["chunk_id"],
                "source_id": chunk["source_id"],
                "anchor": anchor,
                "heading": chunk.get("heading"),
                "excerpt": clean_excerpt(str(chunk.get("content", ""))),
                "selection_reason": "identity" if not candidates else "deterministic_position_sample",
            }
        )
    return {
        "stage": "01-evidence-plan",
        "course_id": catalog.get("course_id"),
        "course_version": catalog.get("course_version"),
        "unit_id": unit["unit_id"],
        "unit_title": unit.get("title") or unit["unit_id"],
        "source_id": source.get("source_id"),
        "material_set_id": source.get("material_set_id"),
        "source_chunk_count": len(chunks),
        "requirements": [
            {
                "id": "unit-identity-and-coverage",
                "claim": "Unit identity and the major source-backed topics must be authored from the selected official material.",
                "candidate_anchors": candidates,
            }
        ],
        "excluded_claims": [
            "This deterministic checkpoint is not a learner-facing summary and does not authorize unsupported claims, hidden text, or assessed solutions.",
            "The author must add or remove anchors after reviewing the complete unit source and visual-risk pages.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-manifest", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.repository_root.resolve()
    catalog = yaml.safe_load(args.catalog_manifest.read_text(encoding="utf-8")) or {}
    build_root = args.build_root
    if not build_root.is_absolute():
        build_root = root / build_root
    created = 0
    skipped = 0
    for unit in catalog.get("units", []):
        unit_dir = build_root / "courses" / catalog["course_id"] / "units" / unit["unit_id"]
        output = unit_dir / "01-evidence-plan.json"
        if output.is_file():
            skipped += 1
            continue
        source = (unit.get("sources") or [{}])[0]
        chunks_path = root / (source.get("chunks_path") or f"data/sources/{catalog['course_id']}/{unit['unit_id']}/chunks.jsonl")
        if not chunks_path.is_file():
            raise FileNotFoundError(f"missing chunks for {unit['unit_id']}: {chunks_path}")
        plan = make_plan(catalog, unit, load_chunks(chunks_path))
        unit_dir.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
        created += 1
    print(json.dumps({"created": created, "skipped": skipped, "build_root": str(build_root)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
