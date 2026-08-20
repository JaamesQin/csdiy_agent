#!/usr/bin/env python3
"""Migrate existing portable StudyKits to the current learner-boundary contract.

This is a deterministic, local-only migration. It adds the fixed feedback
policy when absent and regenerates learner Markdown with the current finalizer;
it never changes source chunks or learner claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


POLICY = {
    "scope": "current_answer_only",
    "persistence": "none",
    "aggregate_accuracy": "disabled",
    "aggregate_mastery": "disabled",
}
FINALIZER = Path(__file__).resolve().parents[1] / "skills/studykit-generator/scripts/finalize_studykit.py"
VALIDATOR = Path(__file__).resolve().parents[1] / "skills/studykit-generator/scripts/validate_artifacts.py"
REVIEW_VALIDATOR = Path(__file__).resolve().parents[1] / "skills/studykit-generator/scripts/validate_review.py"
UNIT_VERIFIER = Path(__file__).resolve().parents[1] / "skills/studykit-generator/scripts/verify_unit_outputs.py"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def _run(command: list[str], root: Path) -> tuple[int, str]:
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def _manifest_units(build_root: Path) -> dict[str, dict[str, Any]]:
    manifest = yaml.safe_load((build_root / "manifest.yaml").read_text(encoding="utf-8"))
    units = manifest.get("units", []) if isinstance(manifest, dict) else []
    return {str(unit["unit_id"]): unit for unit in units if isinstance(unit, dict) and unit.get("unit_id")}


def migrate_unit(build_root: Path, unit_id: str, repository_root: Path) -> dict[str, Any]:
    unit_dir = build_root / "courses" / str(_manifest_course(build_root)) / "units" / unit_id
    candidate_path = unit_dir / "05-studykit.candidate.json"
    result: dict[str, Any] = {"unit_id": unit_id, "status": "skipped"}
    if not candidate_path.exists():
        result["reason"] = "candidate_missing"
        return result

    units = _manifest_units(build_root)
    manifest_unit = units.get(unit_id)
    if not manifest_unit:
        result["reason"] = "manifest_unit_missing"
        return result
    chunks_path = repository_root / str(manifest_unit.get("chunks_path", ""))
    if not chunks_path.exists():
        result["reason"] = "chunks_missing"
        result["chunks_path"] = str(chunks_path)
        return result

    backup_dir = unit_dir / "attempts" / "pre-compatibility-migration"
    backup_files = [
        "05-studykit.candidate.json",
        "05-studykit.json",
        "studykit.yaml",
        "studykit.md",
        "validation.json",
        "review-validation.json",
    ]
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in backup_files:
        source = unit_dir / name
        target = backup_dir / name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    changed = candidate.get("practice_feedback_policy") != POLICY
    candidate["practice_feedback_policy"] = POLICY
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    code, output = _run(
        [sys.executable, str(FINALIZER), "--chunks", str(chunks_path), "--studykit", str(candidate_path), "--output-dir", str(unit_dir)],
        repository_root,
    )
    result.update({"status": "failed" if code else "migrated", "policy_added": changed, "finalizer_exit": code})
    if output:
        result["finalizer_output_tail"] = output[-1000:]
    if code:
        return result

    final_path = unit_dir / "05-studykit.json"
    yaml_path = unit_dir / "studykit.yaml"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    rendered = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    result["semantic_equal"] = _canonical(candidate) == _canonical(final) == _canonical(rendered)
    code, output = _run(
        [sys.executable, str(VALIDATOR), "--chunks", str(chunks_path), "--studykit", str(final_path), "--report", str(unit_dir / "validation.json")],
        repository_root,
    )
    result["validate_artifacts_exit"] = code
    code_review, review_output = _run(
        [sys.executable, str(REVIEW_VALIDATOR), "--studykit", str(final_path), "--review-plan", str(unit_dir / "review-plan.json"), "--delivery-policy", "draft", "--report", str(unit_dir / "review-validation.json")],
        repository_root,
    )
    result["validate_review_exit"] = code_review
    code_verify, verify_output = _run([sys.executable, str(UNIT_VERIFIER), "--unit-dir", str(unit_dir)], repository_root)
    result["verify_unit_outputs_exit"] = code_verify
    result["learner_sha256"] = _digest(unit_dir / "studykit.md")
    if review_output:
        result["review_output_tail"] = review_output[-1000:]
    if verify_output:
        result["verify_output_tail"] = verify_output[-1000:]
    result["status"] = "succeeded" if result["semantic_equal"] and code == 0 and code_verify == 0 else "failed"
    (unit_dir / "compatibility-migration.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _manifest_course(build_root: Path) -> str:
    manifest = yaml.safe_load((build_root / "manifest.yaml").read_text(encoding="utf-8"))
    return str(manifest["course_id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--unit", action="append")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    build_root = (root / args.build_root).resolve() if not args.build_root.is_absolute() else args.build_root.resolve()
    units = args.unit or sorted(_manifest_units(build_root))
    records = [migrate_unit(build_root, unit_id, root) for unit_id in units]
    print(json.dumps({"build_root": str(build_root), "records": records}, ensure_ascii=False, indent=2))
    return 0 if all(record["status"] in {"succeeded", "skipped"} for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
