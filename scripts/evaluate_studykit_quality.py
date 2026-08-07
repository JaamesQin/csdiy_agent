#!/usr/bin/env python3
"""Offline, deterministic quality-profile checks for generated StudyKits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def evaluate_quality(
    studykit: dict[str, Any], profile: dict[str, Any]
) -> list[str]:
    """Return human-readable profile failures without requiring model calls."""

    failures: list[str] = []
    concepts = {
        item.get("term_en", "").strip().lower()
        for item in studykit.get("core_concepts", [])
    }
    for alternatives in profile.get("required_concept_groups", []):
        normalized = [item.lower() for item in alternatives]
        if not any(
            any(alternative in concept for concept in concepts)
            for alternative in normalized
        ):
            failures.append(
                "missing concept group: " + " | ".join(alternatives)
            )

    term_map = {
        item.get("term_en", "").strip().lower(): item.get("term_zh", "")
        for collection in ("core_concepts", "glossary")
        for item in studykit.get(collection, [])
    }
    for english, chinese in profile.get("canonical_terms", {}).items():
        actual = term_map.get(english.lower())
        if actual is not None and chinese not in actual:
            failures.append(
                f"terminology mismatch: {english} must use {chinese}"
            )

    practices = studykit.get("practice", [])
    bounds = profile.get("practice_count", {})
    if len(practices) < bounds.get("minimum", 0):
        failures.append(f"too few practices: {len(practices)}")
    if len(practices) > bounds.get("maximum", len(practices)):
        failures.append(f"too many practices: {len(practices)}")

    practice_types = {item.get("practice_type") for item in practices}
    for required in profile.get("required_practice_types", []):
        if required == "symbolic_derivation_or_shape_reasoning":
            present = bool(
                practice_types.intersection(
                    {"symbolic_derivation", "shape_reasoning"}
                )
            )
        else:
            present = required in practice_types
        if not present:
            failures.append(f"missing practice type: {required}")

    maximum_simple = profile.get("maximum_simple_numeric_practices")
    if maximum_simple is not None:
        simple_count = sum(
            item.get("numeric_complexity") == "simple"
            for item in practices
        )
        if simple_count > maximum_simple:
            failures.append(
                f"too many simple numeric practices: {simple_count}"
            )

    objective_ids = {
        item.get("id") for item in studykit.get("learning_objectives", [])
    }
    covered_objectives = {
        objective_id
        for item in practices
        for objective_id in item.get("objective_ids", [])
    }
    missing_objectives = objective_ids - covered_objectives
    if missing_objectives:
        failures.append(
            "objectives without practice coverage: "
            + ", ".join(sorted(str(item) for item in missing_objectives))
        )

    limitations = studykit.get("limitations", [])
    if len(limitations) > profile.get("maximum_limitations", len(limitations)):
        failures.append(f"too many limitations: {len(limitations)}")

    serialized = json.dumps(studykit, ensure_ascii=False)
    for pattern in profile.get("forbidden_text_patterns", []):
        if pattern in serialized:
            failures.append(f"forbidden text pattern: {pattern}")
    return failures


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a generated StudyKit against an offline quality profile."
    )
    parser.add_argument("studykit", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    studykit = yaml.safe_load(args.studykit.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    failures = evaluate_quality(studykit, profile)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)
    print(f"quality profile passed: {args.studykit}")


if __name__ == "__main__":
    main()
