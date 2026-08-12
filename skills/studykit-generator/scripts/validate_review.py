#!/usr/bin/env python3
"""Validate review-plan coverage and hard formula/delivery gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _json_fingerprint(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _formulas(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        formula = node.get("formula")
        if isinstance(formula, dict):
            yield formula
        for value in node.values():
            yield from _formulas(value)
    elif isinstance(node, list):
        for value in node:
            yield from _formulas(value)


def validate(studykit: dict[str, Any], review: dict[str, Any], delivery_policy: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    selected = set(review.get("selected_pages", []))
    actual = set(review.get("actual_reviewed_pages", []))
    if not selected <= actual:
        issues.append({"code": "review_pages_missing", "message": f"not reviewed: {sorted(selected - actual)}"})
    required_formulas = set(review.get("required_final_formula_pages", []))
    if not required_formulas <= actual:
        issues.append({"code": "final_formula_not_visually_verified", "message": f"pages: {sorted(required_formulas - actual)}"})
    unresolved = [formula for formula in _formulas(studykit) if formula.get("status") == "formula_unresolved"]
    malformed = [formula for formula in _formulas(studykit) if formula.get("status") not in {"resolved", "formula_unresolved"}]
    if malformed:
        issues.append({"code": "invalid_formula_status", "message": f"count: {len(malformed)}"})
    if unresolved and delivery_policy == "publish":
        issues.append({"code": "unresolved_formula_blocker", "message": f"count: {len(unresolved)}"})
    if review.get("quality_mode") in {"standard", "strict"} and review.get("independent_audit") is not True:
        issues.append({"code": "independent_audit_missing", "message": f"{review.get('quality_mode')} requires an independent auditor"})
    if review.get("quality_mode") == "strict":
        blockers = review.get("blockers_after_reaudit", [])
        if blockers:
            issues.append({"code": "strict_blocker_after_reaudit", "message": f"count: {len(blockers)}"})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studykit", type=Path, required=True)
    parser.add_argument("--review-plan", type=Path, required=True)
    parser.add_argument("--delivery-policy", choices=("draft", "publish"), default="draft")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    studykit = json.loads(args.studykit.read_text(encoding="utf-8"))
    review_plan = json.loads(args.review_plan.read_text(encoding="utf-8"))
    issues = validate(studykit, review_plan, args.delivery_policy)
    result = {
        "status": "succeeded" if not issues else "failed",
        "studykit_fingerprint": _json_fingerprint(studykit),
        "review_plan_fingerprint": _json_fingerprint(review_plan),
        "delivery_policy": args.delivery_policy,
        "issues": issues,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
