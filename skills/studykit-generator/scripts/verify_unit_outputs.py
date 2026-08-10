#!/usr/bin/env python3
"""Verify final semantic equality and review/metrics consistency for one unit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-dir", type=Path, required=True)
    args = parser.parse_args()
    unit = args.unit_dir
    issues: list[dict[str, str]] = []
    required = [
        "01-evidence-plan.json", "02-learning-content.json", "03-practice-flow.json",
        "04-quality-audit.json", "05-studykit.json", "studykit.yaml", "studykit.md",
        "validation.json", "review-plan.json", "metrics.json",
    ]
    for name in required:
        if not (unit / name).is_file():
            issues.append({"code": "artifact_missing", "location": name})
    candidate = unit / "05-studykit.candidate.json"
    final = unit / "05-studykit.json"
    yaml_path = unit / "studykit.yaml"
    if candidate.is_file() and final.is_file():
        if json.loads(candidate.read_text(encoding="utf-8")) != json.loads(final.read_text(encoding="utf-8")):
            issues.append({"code": "candidate_final_mismatch", "location": str(unit)})
    if final.is_file() and yaml_path.is_file():
        try:
            import yaml
            yaml_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if json.loads(final.read_text(encoding="utf-8")) != yaml_data:
                issues.append({"code": "final_yaml_mismatch", "location": str(unit)})
        except ImportError:
            issues.append({"code": "yaml_dependency_missing", "location": str(yaml_path)})
    review_path, metrics_path = unit / "review-plan.json", unit / "metrics.json"
    if review_path.is_file() and metrics_path.is_file():
        review = json.loads(review_path.read_text(encoding="utf-8"))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics.get("quality_mode") != review.get("quality_mode"):
            issues.append({"code": "quality_mode_mismatch", "location": str(unit)})
        if metrics.get("reviewed_page_count") != len(set(review.get("actual_reviewed_pages", []))):
            issues.append({"code": "review_count_mismatch", "location": str(unit)})
        if review.get("quality_mode") == "fast" and int(metrics.get("semantic_passes", 0)) > 2:
            issues.append({"code": "fast_semantic_pass_limit", "location": str(unit)})
        repairs: dict[str, int] = {}
        for repair in metrics.get("repairs", []):
            stage = str(repair.get("stage")) if isinstance(repair, dict) else str(repair)
            repairs[stage] = repairs.get(stage, 0) + 1
        if any(count > 1 for count in repairs.values()):
            issues.append({"code": "repair_limit_exceeded", "location": str(unit)})
    result = {"status": "succeeded" if not issues else "failed", "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
