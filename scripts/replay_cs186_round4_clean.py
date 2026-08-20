#!/usr/bin/env python3
"""Replay the authorized CS186 Round-3 practice checkpoints into the clean build."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COURSE = "ucb-cs186-spring-2026"
TARGET_BUILD = "a962c912299e162f24266b4aa9a22a56463aeac7261d387c5d319dd3b6441e0b"
SOURCE_BUILD = "8bc07cabe6fc2e0af9fd89434c9659c8872dbecd7aba4cea2290a7e75b568cb4"
BASELINE_BUILD = "070189d13a9045c29a85cdcc6d33d936f025f83fe2d4bb22767baa8dbe688247"
UNITS = ("note-01", "note-05", "note-07")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def artifact_tree_digest(root: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    excluded = {"repair-baseline", "repair-parent-baseline"}
    for path in sorted(p for p in root.rglob("*") if p.is_file() and not excluded.intersection(p.relative_to(root).parts)):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def scrub_review(review: dict) -> dict:
    keep = {"quality_mode", "source_boundary"}
    cleaned = {key: value for key, value in review.items() if key in keep}
    cleaned["generator_review_status"] = "repair_pending_independent_reaudit"
    cleaned["audit_findings"] = [
        value for value in review.get("audit_findings", [])
        if "independent" not in str(value).lower() and "passed" not in str(value).lower()
    ]
    cleaned["independent_audit"] = False
    return cleaned


def main() -> None:
    base = ROOT / "outputs" / COURSE
    target_units = base / TARGET_BUILD / "courses" / COURSE / "units"
    source_units = base / SOURCE_BUILD / "courses" / COURSE / "units"
    baseline_units = base / BASELINE_BUILD / "courses" / COURSE / "units"

    # Required pre-edit gate: every assigned direct-parent snapshot must match
    # the declared baseline artifact tree exactly.
    for unit_id in UNITS:
        declared = artifact_tree_digest(baseline_units / unit_id)
        snapshot = artifact_tree_digest(target_units / unit_id / "repair-parent-baseline")
        if declared != snapshot:
            raise SystemExit(f"baseline digest mismatch for {unit_id}: {snapshot} != {declared}")

    for unit_id in UNITS:
        target = target_units / unit_id
        source = source_units / unit_id

        # 03 is the authorized checkpoint.  The downstream candidate is the
        # authorized semantic replay; final/YAML/Markdown are regenerated from
        # that candidate so no stale finalization state is imported.
        shutil.copyfile(source / "03-practice-flow.json", target / "03-practice-flow.json")
        candidate = read_json(source / "05-studykit.candidate.json")
        candidate["review"] = scrub_review(candidate.get("review", {}))
        write_json(target / "05-studykit.candidate.json", candidate)

        source_review = read_json(source / "review-plan.json")
        review = {
            key: value for key, value in source_review.items()
            if key not in {
                "independent_audit", "independent_auditor", "independent_audit_time",
                "independent_audit_status", "independent_audit_result",
                "blockers_after_reaudit", "review_outcome",
            }
        }
        # A clean author replay has no independent audit.  Fast review mode is
        # the current build's authoring mode and keeps the portable review gate
        # honest without importing an old verdict.
        review["quality_mode"] = "fast"
        review["independent_audit"] = False
        review["repair_revision"] = "round4-clean-replay-20260812"
        review["repair_scope"] = "practice-only"
        review["repaired_practice_ids"] = read_json(target / "03-practice-flow.json").get("repaired_practice_ids", [])
        write_json(target / "review-plan.json", review)

        practice_ids = review["repaired_practice_ids"]
        actual_pages = review.get("actual_reviewed_pages", [])
        metrics = {
            "quality_mode": "fast",
            "reviewed_page_count": len(set(actual_pages)),
            "semantic_passes": 1,
            "actual_reviewed_pages": actual_pages,
            "repair_id": "round4-clean-replay-1",
            "repair_revision": "round4-clean-replay-20260812",
            "repair_stage": "03-practice-flow",
            "repaired_practice_ids": practice_ids,
            "candidate_validation": "pending",
            "final_validation": "pending",
            "candidate_final_semantic_equal": False,
            "practice_checkpoint_alignment": False,
            "independent_audit_status": "not_performed",
            "author_self_check": "pending",
            "repairs": [{
                "repair_id": "round4-clean-replay-1",
                "stage": "03-practice-flow",
                "attempt": 1,
                "status": "applied_pending_independent_audit",
                "practice_ids": practice_ids,
                "author_id": "Luna-medium-clean-parent-replay-author",
            }],
            "author_id": "Luna-medium-clean-parent-replay-author",
            "execution_note": "Current-build author replay; no independent audit, root, or registry artifact copied.",
        }
        write_json(target / "metrics.json", metrics)


if __name__ == "__main__":
    main()
