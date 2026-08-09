#!/usr/bin/env python3
"""Validate chunks, a final StudyKit, and all citation anchors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _schema_validate(instance: Any, schema_path: Path) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema dependency is missing"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))]


def _iter_citations(node: Any, path: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        if isinstance(node.get("source_id"), str) and isinstance(node.get("anchor"), dict):
            yield path or "<root>", node
        for key, value in node.items():
            yield from _iter_citations(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_citations(value, f"{path}[{index}]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--studykit", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    chunks = _load_jsonl(args.chunks)
    studykit = json.loads(args.studykit.read_text(encoding="utf-8"))
    errors: list[dict[str, str]] = []
    for index, chunk in enumerate(chunks):
        for message in _schema_validate(chunk, ROOT / "assets/schemas/source_chunk.schema.json"):
            errors.append({"location": f"chunks[{index}]", "code": "schema", "message": message})
    for message in _schema_validate(studykit, ROOT / "assets/schemas/studykit.schema.json"):
        errors.append({"location": "studykit", "code": "schema", "message": message})
    anchors = {
        (chunk["source_id"], chunk["anchor"]["type"], str(chunk["anchor"]["value"]))
        for chunk in chunks
    }
    hidden_anchors = {
        (chunk["source_id"], chunk["anchor"]["type"], str(chunk["anchor"]["value"]))
        for chunk in chunks
        if chunk.get("content_type") == "hidden_text"
        or any("hidden" in str(warning).lower() for warning in chunk.get("parse_warnings", []))
    }
    for location, citation in _iter_citations(studykit):
        anchor = citation["anchor"]
        key = (citation["source_id"], anchor.get("type"), str(anchor.get("value")))
        if key not in anchors:
            errors.append({"location": location, "code": "anchor_not_found", "message": repr(key)})
        elif key in hidden_anchors:
            errors.append({"location": location, "code": "hidden_text_not_evidence", "message": repr(key)})
    report = {"status": "succeeded" if not errors else "failed", "chunk_count": len(chunks), "citation_count": sum(1 for _ in _iter_citations(studykit)), "issues": errors}
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
