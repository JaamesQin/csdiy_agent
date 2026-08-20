#!/usr/bin/env python3
"""Prepare a selective, fingerprinted StudyKit repair build.

The baseline build is copied unit-for-unit into a new fingerprinted root.  A
repair worker may then edit only the listed checkpoints. The immediate parent
unit is preserved under ``repair-parent-baseline/``; older inherited snapshots
remain untouched for historical provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts.prepare_studykit_build import make_build
except ModuleNotFoundError:  # direct execution from the scripts directory
    from prepare_studykit_build import make_build


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def artifact_tree_digest(root: Path) -> str:
    """Hash one unit without recursively hashing inherited repair snapshots."""

    excluded = {"repair-baseline", "repair-parent-baseline"}
    digest = hashlib.sha256()
    for path in sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not excluded.intersection(path.relative_to(root).parts)
    ):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def copy_parent_snapshot(source: Path, target: Path) -> None:
    """Snapshot the direct parent while retaining its older snapshots elsewhere."""

    if target.exists():
        expected = artifact_tree_digest(source)
        actual = artifact_tree_digest(target)
        if actual != expected:
            raise ValueError(
                "existing repair-parent-baseline does not match the declared direct parent: "
                f"{target} (expected {expected}, found {actual})"
            )
        return
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("repair-baseline", "repair-parent-baseline"),
    )


def load_plan(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("repair plan must be a JSON object")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_STAGE_ORDER = ("evidence", "content", "practice", "structural")
_REPAIR_STAGES = set(_STAGE_ORDER)


def _stage_list(value: Any, *, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    values = value if isinstance(value, list) else [value]
    stages = [str(stage).strip().lower() for stage in values if str(stage).strip()]
    if not stages or not set(stages) <= _REPAIR_STAGES:
        raise ValueError("repair_stages must contain only evidence, content, practice, or structural")
    return sorted(set(stages), key=_STAGE_ORDER.index)


def resolve_course_plan(plan: dict[str, Any], course_id: str) -> tuple[dict[str, Any], str, dict[str, list[str]]]:
    """Return the selected course entry, plan scope, and unit -> repair stages.

    The v1 shape is retained for callers with a single-course plan.  A master
    plan selects exactly one entry from ``courses`` by the catalog course_id.
    ``repair_stages`` accepts either a unit mapping or unit records, which
    keeps the plan readable while making the resulting unit records uniform.
    """
    courses = plan.get("courses")
    if courses is None:
        if plan.get("course_id") != course_id:
            raise ValueError("repair plan course_id does not match catalog manifest")
        entry = plan
        scope = "single-course"
    else:
        if not isinstance(courses, list):
            raise ValueError("master repair plan courses must be a list")
        matches = [entry for entry in courses if isinstance(entry, dict) and entry.get("course_id") == course_id]
        if len(matches) != 1:
            raise ValueError(f"master repair plan must contain exactly one courses entry for {course_id}")
        entry = matches[0]
        scope = "global-master"

    repair_units = [str(unit) for unit in entry.get("repair_unit_ids") or []]
    stages_by_unit: dict[str, list[str]] = {}
    stage_spec = entry.get("repair_stages")
    if isinstance(stage_spec, dict):
        stages_by_unit = {str(unit): _stage_list(stages) for unit, stages in stage_spec.items()}
    elif stage_spec is not None:
        if not isinstance(stage_spec, list):
            raise ValueError("repair_stages must be a unit mapping or list of unit records")
        for item in stage_spec:
            if not isinstance(item, dict) or not item.get("unit_id"):
                raise ValueError("repair_stages unit records require unit_id")
            unit_id = str(item["unit_id"])
            stages_by_unit[unit_id] = _stage_list(item.get("stages", item.get("repair_stages")))

    # Also accept the equivalent per-unit record form without requiring a
    # second top-level repair_unit_ids list.
    unit_specs = entry.get("repair_units")
    if unit_specs is None and isinstance(entry.get("units"), list):
        unit_specs = entry["units"]
    if isinstance(unit_specs, list):
        for item in unit_specs:
            if isinstance(item, str):
                repair_units.append(item)
                continue
            if not isinstance(item, dict) or not item.get("unit_id"):
                raise ValueError("repair_units records require unit_id")
            unit_id = str(item["unit_id"])
            repair_units.append(unit_id)
            if "repair_stages" in item or "stages" in item:
                stages_by_unit[unit_id] = _stage_list(item.get("repair_stages", item.get("stages")))

    repair_units = sorted(set(repair_units))
    if not repair_units:
        raise ValueError("repair plan must list repair units")
    unknown_stage_units = set(stages_by_unit) - set(repair_units)
    if unknown_stage_units:
        raise ValueError(f"repair_stages reference units not listed for repair: {sorted(unknown_stage_units)}")
    for unit_id in repair_units:
        stages_by_unit.setdefault(unit_id, ["practice"])
    return entry, scope, stages_by_unit


def prepare(
    *,
    catalog_manifest: Path,
    baseline_build: Path,
    repair_plan: Path,
    repository_root: Path,
    output_base: Path,
    coordinator_id: str,
) -> tuple[Path, dict[str, Any]]:
    catalog = yaml.safe_load(catalog_manifest.read_text(encoding="utf-8")) or {}
    course_id = str(catalog.get("course_id") or "")
    if not course_id:
        raise ValueError("catalog manifest requires course_id")
    baseline_build = baseline_build.resolve()
    baseline_run = json.loads((baseline_build / "run.json").read_text(encoding="utf-8"))
    if baseline_run.get("build_id") != baseline_build.name:
        raise ValueError("baseline run build_id does not match directory")
    plan = load_plan(repair_plan)
    course_entry, plan_scope, repair_stages = resolve_course_plan(plan, course_id)
    expected_baseline = course_entry.get("baseline_build_id")
    if expected_baseline is not None and str(expected_baseline) != baseline_build.name:
        raise ValueError("baseline build does not match selected repair plan course entry")
    units = [str(u["unit_id"]) for u in catalog.get("units") or []]
    repair_units = sorted(repair_stages)
    if not repair_units or not set(repair_units) <= set(units):
        raise ValueError("repair plan must list existing repair_unit_ids")
    baseline_units = baseline_build / "courses" / course_id / "units"
    if not baseline_units.is_dir():
        raise FileNotFoundError(f"missing baseline units: {baseline_units}")
    missing = [u for u in units if not (baseline_units / u).is_dir()]
    if missing:
        raise FileNotFoundError(f"baseline missing units: {missing}")

    context = {
        "repair_mode": "selective-repair-v2",
        "baseline_build_id": baseline_build.name,
        "repair_plan_sha256": sha256_file(repair_plan),
        "repair_course_entry_sha256": hashlib.sha256(canonical_json(course_entry).encode("utf-8")).hexdigest(),
        "repair_plan_scope": plan_scope,
        "repair_unit_ids": sorted(repair_units),
        "repair_stages": {unit_id: repair_stages[unit_id] for unit_id in sorted(repair_stages)},
        "reused_unit_ids": sorted(set(units) - set(repair_units)),
    }
    build_root, run = make_build(
        catalog_manifest.resolve(),
        repository_root.resolve(),
        output_base,
        str(baseline_run.get("quality_mode") or "standard"),
        str(baseline_run.get("delivery_policy") or "draft"),
        str(baseline_run.get("parallel_units") or "auto"),
        coordinator_id,
        context,
    )
    target_units = build_root / "courses" / course_id / "units"
    for unit_id in units:
        target = target_units / unit_id
        if not any(target.iterdir()):
            shutil.copytree(
                baseline_units / unit_id,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("repair-baseline", "repair-parent-baseline"),
            )
        snapshot = target / "repair-baseline"
        if not snapshot.exists():
            shutil.copytree(
                baseline_units / unit_id,
                snapshot,
                ignore=shutil.ignore_patterns("repair-baseline", "repair-parent-baseline"),
            )
        copy_parent_snapshot(baseline_units / unit_id, target / "repair-parent-baseline")

    records = []
    for unit_id in units:
        baseline_unit = baseline_units / unit_id
        target = target_units / unit_id
        records.append(
            {
                "unit_id": unit_id,
                "status": "repair_pending" if unit_id in repair_units else "reused",
                "repair_stages": repair_stages.get(unit_id, []),
                "baseline_tree_sha256": tree_digest(baseline_unit),
                "repair_baseline_tree_sha256": tree_digest(target / "repair-baseline"),
                "baseline_artifact_tree_sha256": artifact_tree_digest(baseline_unit),
                "repair_parent_baseline_artifact_tree_sha256": artifact_tree_digest(
                    target / "repair-parent-baseline"
                ),
                "repair_checkpoint": "03-practice-flow.json" if "practice" in repair_stages.get(unit_id, []) else None,
                "repair_checkpoints": [
                    checkpoint
                    for stage, checkpoint in (
                        ("evidence", "01-evidence-plan.json"),
                        ("content", "02-learning-content.json"),
                        ("practice", "03-practice-flow.json"),
                        ("structural", "05-studykit.candidate.json"),
                    )
                    if stage in repair_stages.get(unit_id, [])
                ],
            }
        )
    requested_stages = sorted(
        {stage for stages in repair_stages.values() for stage in stages},
        key=_STAGE_ORDER.index,
    )
    repair_record = {
        "schema_version": "practice-only-repair-v1",
        "course_id": course_id,
        "build_id": run["build_id"],
        "baseline_build_id": baseline_build.name,
        "repair_plan": str(repair_plan.resolve()),
        "repair_plan_sha256": context["repair_plan_sha256"],
        "repair_course_entry_sha256": context["repair_course_entry_sha256"],
        "repair_plan_scope": plan_scope,
        "repair_unit_ids": sorted(repair_units),
        "reused_unit_ids": sorted(set(units) - set(repair_units)),
        "unit_records": records,
        "policy": {
            "repair_stages": requested_stages,
            "stage_checkpoints": {
                "evidence": "01-evidence-plan.json",
                "content": "02-learning-content.json",
                "practice": "03-practice-flow.json",
                "structural": "05-studykit.candidate.json",
            },
            "max_targeted_repairs_per_stage": 1,
            "reuse_requires_baseline_tree_hash": True,
            "immediate_parent_snapshot": "repair-parent-baseline",
            "independent_audit_required_for_repaired_units": True,
        },
    }
    (build_root / "repair-plan.json").write_text(json.dumps(repair_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return build_root, repair_record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-manifest", type=Path, required=True)
    parser.add_argument("--baseline-build", type=Path, required=True)
    parser.add_argument("--repair-plan", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--output-base", type=Path, default=Path("outputs"))
    parser.add_argument("--coordinator-id", default="practice-repair-coordinator")
    args = parser.parse_args()
    build, record = prepare(
        catalog_manifest=args.catalog_manifest,
        baseline_build=args.baseline_build,
        repair_plan=args.repair_plan,
        repository_root=args.repository_root,
        output_base=args.output_base,
        coordinator_id=args.coordinator_id,
    )
    print(json.dumps({"build_root": str(build), "build_id": record["build_id"], "repair_units": len(record["repair_unit_ids"]), "reused_units": len(record["reused_unit_ids"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
