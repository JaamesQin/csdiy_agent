#!/usr/bin/env python3
"""Validate chunks, a final StudyKit, and all citation anchors."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from feedback_contract import evaluate_feedback_contract


ROOT = Path(__file__).resolve().parents[1]
_PLACEHOLDER_RE = re.compile(
    r"(?:\b(?:todo|tbd|placeholder|lorem ipsum|your answer here|fill in)\b|"
    r"\{\{[^{}]+\}\}|(?:待填写|待补充|尚未填写|这里填写))",
    re.IGNORECASE,
)
_STRUCTURAL_CONCEPT_RE = re.compile(
    r"^(?:第\s*[0-9一二三四五六七八九十百]+\s*页|页码\s*[：:]?\s*[0-9一二三四五六七八九十百]+|"
    r"(?:page|slide|figure|fig|section|chapter)\s*[#：:\-]?\s*[0-9]+|"
    r"(?:title|标题|untitled|未命名))$",
    re.IGNORECASE,
)
_CLAIM_FIELDS = ("explanation", "definition", "meaning", "claim", "statement", "description")


def _json_fingerprint(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _strings(node: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            if isinstance(value, str):
                yield child, value
            else:
                yield from _strings(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")


def _semantic_issues(studykit: dict[str, Any]) -> list[dict[str, str]]:
    """Apply conservative learner-facing checks after schema validation."""
    issues: list[dict[str, str]] = []
    for location, value in _strings(studykit):
        if _PLACEHOLDER_RE.search(value):
            issues.append({"location": location, "code": "template_placeholder", "message": "learner-facing placeholder text"})

    for index, concept in enumerate(studykit.get("core_concepts", [])):
        if not isinstance(concept, dict):
            continue
        term = str(concept.get("term", "")).strip()
        explanation = str(concept.get("explanation", "")).strip()
        if _STRUCTURAL_CONCEPT_RE.fullmatch(term) or _STRUCTURAL_CONCEPT_RE.fullmatch(explanation):
            issues.append({
                "location": f"core_concepts[{index}]",
                "code": "non_concept_label",
                "message": "learner-facing concept must describe a concept, not only a page/title label",
            })

    # Some optional sections are intentionally schema-loose. If they contain
    # an actual definition/claim, require the same anchored citation contract
    # as core_concepts, while leaving objectives and activity prose alone.
    for section in ("glossary", "common_misconceptions", "prerequisites"):
        for index, item in enumerate(studykit.get(section, [])):
            if not isinstance(item, dict):
                continue
            has_claim = any(isinstance(item.get(field), str) and item[field].strip() for field in _CLAIM_FIELDS)
            if has_claim and not item.get("citations"):
                issues.append({
                    "location": f"{section}[{index}]",
                    "code": "claim_anchor_missing",
                    "message": "substantive learner-facing claim requires at least one source citation",
                })
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--studykit", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--stage-dir", type=Path, help="unit directory for ordered checkpoint validation")
    parser.add_argument("--quality-mode", choices=("fast", "standard", "strict"))
    args = parser.parse_args()
    if bool(args.stage_dir) != bool(args.quality_mode):
        parser.error("--stage-dir and --quality-mode must be supplied together")
    chunks = _load_jsonl(args.chunks)
    studykit = json.loads(args.studykit.read_text(encoding="utf-8"))
    errors: list[dict[str, str]] = []
    for index, chunk in enumerate(chunks):
        for message in _schema_validate(chunk, ROOT / "assets/schemas/source_chunk.schema.json"):
            errors.append({"location": f"chunks[{index}]", "code": "schema", "message": message})
    for message in _schema_validate(studykit, ROOT / "assets/schemas/studykit.schema.json"):
        errors.append({"location": "studykit", "code": "schema", "message": message})
    errors.extend(_semantic_issues(studykit))
    feedback_contract = evaluate_feedback_contract(studykit, chunks)
    errors.extend(feedback_contract["issues"])
    if args.stage_dir and args.quality_mode:
        from workflow_policy import validate_stage_checkpoints
        errors.extend(validate_stage_checkpoints(args.stage_dir, args.quality_mode))
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
    report = {
        "status": "succeeded" if not errors else "failed",
        "chunk_count": len(chunks),
        "citation_count": sum(1 for _ in _iter_citations(studykit)),
        "studykit_fingerprint": _json_fingerprint(studykit),
        "chunks_sha256": _file_sha256(args.chunks),
        "practice_feedback_contract": {
            key: feedback_contract[key]
            for key in (
                "course_grounded",
                "general_only",
                "unresolved",
                "declaration_mismatch",
            )
        },
        "issues": errors,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
