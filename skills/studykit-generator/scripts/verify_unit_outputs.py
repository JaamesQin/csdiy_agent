#!/usr/bin/env python3
"""Verify final semantic equality and review/metrics consistency for one unit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _json_fingerprint(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_json(path: Path, issues: list[dict[str, str]]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append({"code": "artifact_invalid_json", "location": str(path), "message": str(exc)})
        return None


def _check_success_report(path: Path, issues: list[dict[str, str]]) -> dict[str, Any] | None:
    value = _load_json(path, issues)
    if value is None:
        return None
    if not isinstance(value, dict):
        issues.append({"code": "validation_report_not_object", "location": str(path)})
        return None
    if value.get("status") != "succeeded" or value.get("issues") != []:
        issues.append({"code": "validation_report_failed", "location": str(path)})
    return value


def _schema_issues(value: Any) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema dependency is missing"]
    schema = json.loads((ROOT / "assets/schemas/studykit.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    ]


def _repair_stages(repair: object) -> list[str]:
    """Return the stage names covered by one repair record.

    The v0.2 metrics format permits a repair to record either one ``stage``
    or an explicit ``stages`` list.  Older verification counted every list
    record as the string ``None``, which could both miss overlapping repairs
    and report an unrelated false positive.
    """
    if not isinstance(repair, dict):
        return [str(repair)]
    stages = repair.get("stages")
    if isinstance(stages, list) and stages:
        return [str(stage) for stage in stages]
    stage = repair.get("stage")
    if stage is not None and str(stage).strip():
        return [str(stage)]
    return ["<unspecified>"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-dir", type=Path, required=True)
    args = parser.parse_args()
    unit = args.unit_dir
    issues: list[dict[str, str]] = []
    required = [
        "01-evidence-plan.json", "02-learning-content.json", "03-practice-flow.json",
        "04-quality-audit.json", "05-studykit.candidate.json", "05-studykit.json",
        "studykit.yaml", "studykit.md", "validation.json", "review-plan.json",
        "review-validation.json", "metrics.json",
    ]
    for name in required:
        if not (unit / name).is_file():
            issues.append({"code": "artifact_missing", "location": name})
    candidate = unit / "05-studykit.candidate.json"
    final = unit / "05-studykit.json"
    yaml_path = unit / "studykit.yaml"
    candidate_data = _load_json(candidate, issues) if candidate.is_file() else None
    final_data = _load_json(final, issues) if final.is_file() else None
    if candidate_data is not None and final_data is not None:
        if candidate_data != final_data:
            issues.append({"code": "candidate_final_mismatch", "location": str(unit)})
    if final_data is not None:
        for message in _schema_issues(final_data):
            issues.append({"code": "final_schema", "location": str(final), "message": message})
    if final.is_file() and yaml_path.is_file():
        try:
            import yaml
            try:
                yaml_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                issues.append({"code": "artifact_invalid_yaml", "location": str(yaml_path), "message": str(exc)})
                yaml_data = None
            if final_data is not None and final_data != yaml_data:
                issues.append({"code": "final_yaml_mismatch", "location": str(unit)})
        except ImportError:
            issues.append({"code": "yaml_dependency_missing", "location": str(yaml_path)})
    review_path, metrics_path = unit / "review-plan.json", unit / "metrics.json"
    review = _load_json(review_path, issues) if review_path.is_file() else None
    metrics = _load_json(metrics_path, issues) if metrics_path.is_file() else None
    if review_path.is_file() and metrics_path.is_file():
        if not isinstance(review, dict) or not isinstance(metrics, dict):
            issues.append({"code": "review_metrics_not_object", "location": str(unit)})
            review = metrics = None
    if isinstance(review, dict) and isinstance(metrics, dict):
        if metrics.get("quality_mode") != review.get("quality_mode"):
            issues.append({"code": "quality_mode_mismatch", "location": str(unit)})
        if metrics.get("reviewed_page_count") != len(set(review.get("actual_reviewed_pages", []))):
            issues.append({"code": "review_count_mismatch", "location": str(unit)})
        if review.get("quality_mode") == "fast" and int(metrics.get("semantic_passes", 0)) > 2:
            issues.append({"code": "fast_semantic_pass_limit", "location": str(unit)})
        repairs: dict[str, int] = {}
        for repair in metrics.get("repairs", []):
            for stage in _repair_stages(repair):
                repairs[stage] = repairs.get(stage, 0) + 1
        if any(count > 1 for count in repairs.values()):
            issues.append({"code": "repair_limit_exceeded", "location": str(unit)})

    validation_path = unit / "validation.json"
    validation = _check_success_report(validation_path, issues) if validation_path.is_file() else None
    if validation is not None and final_data is not None:
        if validation.get("studykit_fingerprint") != _json_fingerprint(final_data):
            issues.append({"code": "validation_report_stale", "location": str(validation_path)})

    review_validation_path = unit / "review-validation.json"
    review_validation = _check_success_report(review_validation_path, issues) if review_validation_path.is_file() else None
    if review_validation is not None and final_data is not None:
        if review_validation.get("studykit_fingerprint") != _json_fingerprint(final_data):
            issues.append({"code": "review_validation_stale_studykit", "location": str(review_validation_path)})
    if review_validation is not None and isinstance(review, dict):
        if review_validation.get("review_plan_fingerprint") != _json_fingerprint(review):
            issues.append({"code": "review_validation_stale_plan", "location": str(review_validation_path)})
    result = {"status": "succeeded" if not issues else "failed", "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
