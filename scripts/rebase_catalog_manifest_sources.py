#!/usr/bin/env python3
"""Point one catalog manifest at a new immutable chunk/parser checkpoint.

This is a coordinator tool for parser-version transitions. It does not alter
raw materials or existing chunks; callers choose a new chunks prefix so an old
build remains reproducible while a new fingerprinted StudyKit build is made.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import yaml


def rebase_manifest(manifest: dict[str, Any], chunks_prefix: str, parser_version: str) -> dict[str, Any]:
    course_id = str(manifest.get("course_id") or "")
    if not course_id:
        raise ValueError("manifest requires course_id")
    units = manifest.get("units") or []
    if not units:
        raise ValueError("manifest requires units")
    result = dict(manifest)
    rebased_units = []
    for unit in units:
        sources = unit.get("sources") or []
        if len(sources) != 1:
            raise ValueError(f"{unit.get('unit_id')} must have exactly one source")
        unit_copy = dict(unit)
        source = dict(sources[0])
        unit_id = str(unit["unit_id"])
        source["material_set_id"] = f"{course_id}-{unit_id}"
        source["chunks_path"] = f"{chunks_prefix.rstrip('/')}/{unit_id}/chunks.jsonl"
        source["parser_version"] = parser_version
        unit_copy["sources"] = [source]
        rebased_units.append(unit_copy)
    result["units"] = rebased_units
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--chunks-prefix", required=True)
    parser.add_argument("--parser-version", required=True)
    args = parser.parse_args()
    value = yaml.safe_load(args.manifest.read_text(encoding="utf-8")) or {}
    updated = rebase_manifest(value, args.chunks_prefix, args.parser_version)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.manifest.parent, delete=False) as handle:
        temporary = Path(handle.name)
        yaml.safe_dump(updated, handle, allow_unicode=True, sort_keys=False)
    temporary.replace(args.manifest)
    print(f"rebased {args.manifest} to {args.parser_version} under {args.chunks_prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
