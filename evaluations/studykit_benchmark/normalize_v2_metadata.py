#!/usr/bin/env python3
"""Normalize worker-written v2 review/metrics metadata to the v0.2 contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _pages(value: Any) -> list[int]:
    return sorted({int(page) for page in (value or [])})


def normalize_review(review: dict[str, Any], mode: str) -> dict[str, Any]:
    vision = review.get("vision_review") if isinstance(review.get("vision_review"), dict) else {}
    formula_review = review.get("formula_review") if isinstance(review.get("formula_review"), dict) else {}
    selected = review.get("selected_pages") or review.get("reviewed_pages") or vision.get("pages") or []
    formula_pages = review.get("required_final_formula_pages") or review.get("final_formula_pages") or review.get("formula_pages") or formula_review.get("pages") or []
    for scope in review.get("review_scope", []):
        if isinstance(scope, dict) and scope.get("kind") == "final_formula":
            formula_pages = list(formula_pages) + list(scope.get("pages", []))
    independent = review.get("independent_audit")
    if isinstance(independent, dict):
        independent = independent.get("completed") is True
    blockers = review.get("blockers_after_reaudit")
    if blockers is None:
        blockers = review.get("remaining_blockers", [])
    normalized = dict(review)
    normalized.update({
        "quality_mode": mode,
        "page_selector_version": review.get("page_selector_version", "review-pages-v1"),
        "selected_pages": _pages(selected),
        "required_final_formula_pages": _pages(formula_pages),
        "actual_reviewed_pages": _pages(review.get("actual_reviewed_pages") or review.get("reviewed_pages") or vision.get("pages") or selected),
        "independent_audit": bool(independent) if mode in {"standard", "strict"} else bool(independent),
        "blockers_after_reaudit": blockers,
    })
    return normalized


def normalize_metrics(metrics: dict[str, Any], review: dict[str, Any], mode: str) -> dict[str, Any]:
    repairs = metrics.get("repairs", [])
    if isinstance(repairs, int):
        repairs = [
            {"stage": "audit", "action": "see 04-quality-audit.resolution.json"}
            for _ in range(repairs)
        ]
    elif repairs is None:
        repairs = []
    normalized = dict(metrics)
    normalized.update({
        "quality_mode": mode,
        "repairs": repairs,
        "reviewed_page_count": len(set(review["actual_reviewed_pages"])),
    })
    if "semantic_passes" not in normalized:
        normalized["semantic_passes"] = review.get("semantic_passes") or review.get("semantic_passes_used") or (2 if mode == "fast" else 4 if mode == "standard" else 5)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("fast", "standard", "strict"), required=True)
    args = parser.parse_args()
    review_path = args.unit_dir / "review-plan.json"
    metrics_path = args.unit_dir / "metrics.json"
    review = normalize_review(json.loads(review_path.read_text(encoding="utf-8")), args.mode)
    metrics = normalize_metrics(json.loads(metrics_path.read_text(encoding="utf-8")), review, args.mode)
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
