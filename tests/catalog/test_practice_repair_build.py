from __future__ import annotations

import json
import hashlib
from pathlib import Path

import yaml
import pytest

from scripts.prepare_practice_repair_build import artifact_tree_digest, prepare, tree_digest


COURSE_ID = "demo-course"
UNIT_IDS = ["unit-01", "unit-02", "unit-03"]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path, repair_unit_ids: list[str]) -> dict[str, Path]:
    repository = tmp_path / "repository"
    chunks_root = repository / "data" / "sources" / COURSE_ID
    for unit_id in UNIT_IDS:
        unit_chunks = chunks_root / unit_id
        unit_chunks.mkdir(parents=True)
        (unit_chunks / "chunks.jsonl").write_text(
            json.dumps({"chunk_id": f"{unit_id}-chunk-1", "text": "fixture"}) + "\n",
            encoding="utf-8",
        )

    # make_build fingerprints this file; its contents need only be stable for
    # this offline contract test.
    (repository / "schemas").mkdir(parents=True)
    (repository / "schemas" / "source_chunk.schema.json").write_text(
        '{"type":"object"}\n', encoding="utf-8"
    )

    manifest = repository / "catalog.yaml"
    yaml.safe_dump(
        {
            "course_id": COURSE_ID,
            "course_version": "2026",
            "title": "Fixture course",
            "units": [
                {
                    "unit_id": unit_id,
                    "order": index,
                    "title": f"Unit {index}",
                    "sources": [{
                        "source_id": f"source-{unit_id}",
                        "chunks_path": f"data/sources/{COURSE_ID}/{unit_id}/chunks.jsonl",
                    }],
                }
                for index, unit_id in enumerate(UNIT_IDS, start=1)
            ],
        },
        manifest.open("w", encoding="utf-8"),
        sort_keys=False,
    )

    baseline = tmp_path / "baseline" / "baseline-build"
    baseline_units = baseline / "courses" / COURSE_ID / "units"
    for unit_id in UNIT_IDS:
        unit = baseline_units / unit_id
        unit.mkdir(parents=True)
        _write_json(unit / "03-practice-flow.json", {"unit_id": unit_id, "version": "baseline"})
        _write_json(unit / "05-studykit.json", {"unit_id": unit_id, "version": "baseline"})
        (unit / "source-note.txt").write_text(f"baseline:{unit_id}\n", encoding="utf-8")
    _write_json(
        baseline / "run.json",
        {
            "build_id": baseline.name,
            "quality_mode": "strict",
            "delivery_policy": "publish",
            "parallel_units": "1",
        },
    )

    repair_plan = tmp_path / "repair-plan.json"
    _write_json(
        repair_plan,
        {
            "schema_version": "practice-only-repair-plan-v1",
            "course_id": COURSE_ID,
            "repair_unit_ids": repair_unit_ids,
        },
    )
    return {
        "repository": repository,
        "manifest": manifest,
        "baseline": baseline,
        "repair_plan": repair_plan,
        "output": tmp_path / "outputs",
    }


def _prepare(paths: dict[str, Path]) -> tuple[Path, dict[str, object]]:
    return prepare(
        catalog_manifest=paths["manifest"],
        baseline_build=paths["baseline"],
        repair_plan=paths["repair_plan"],
        repository_root=paths["repository"],
        output_base=paths["output"],
        coordinator_id="test-coordinator",
    )


def _write_master_plan(paths: dict[str, Path], *, repair_unit_ids: list[str]) -> None:
    _write_json(
        paths["repair_plan"],
        {
            "schema_version": "practice-only-repair-plan-v1",
            "courses": [
                {
                    "course_id": COURSE_ID,
                    "baseline_build_id": paths["baseline"].name,
                    "repair_unit_ids": repair_unit_ids,
                    "repair_stages": {unit_id: ["practice"] for unit_id in repair_unit_ids},
                }
            ],
        },
    )


def test_master_plan_records_repaired_and_reused_units_with_baseline_hashes(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, ["unit-03", "unit-01"])
    _write_master_plan(paths, repair_unit_ids=["unit-03", "unit-01"])

    build, record = _prepare(paths)

    assert record["schema_version"] == "practice-only-repair-v1"
    assert record["repair_unit_ids"] == ["unit-01", "unit-03"]
    assert record["reused_unit_ids"] == ["unit-02"]
    assert record["repair_plan_sha256"] == hashlib.sha256(paths["repair_plan"].read_bytes()).hexdigest()
    assert record["repair_plan_scope"] == "global-master"
    assert record["policy"]["repair_stages"] == ["practice"]

    unit_records = {item["unit_id"]: item for item in record["unit_records"]}
    assert unit_records["unit-01"]["status"] == "repair_pending"
    assert unit_records["unit-01"]["repair_stages"] == ["practice"]
    assert unit_records["unit-01"]["repair_checkpoint"] == "03-practice-flow.json"
    assert unit_records["unit-02"]["status"] == "reused"
    assert unit_records["unit-02"]["repair_checkpoint"] is None
    for unit_id in UNIT_IDS:
        baseline_unit = paths["baseline"] / "courses" / COURSE_ID / "units" / unit_id
        assert unit_records[unit_id]["baseline_tree_sha256"] == tree_digest(baseline_unit)
        assert unit_records[unit_id]["repair_baseline_tree_sha256"] == tree_digest(
            build / "courses" / COURSE_ID / "units" / unit_id / "repair-baseline"
        )
        assert unit_records[unit_id]["baseline_artifact_tree_sha256"] == unit_records[unit_id][
            "repair_parent_baseline_artifact_tree_sha256"
        ]

    assert json.loads((build / "repair-plan.json").read_text(encoding="utf-8")) == record


def test_per_unit_stage_preserves_stage_selection_and_baseline_snapshot(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, UNIT_IDS)
    _write_json(
        paths["repair_plan"],
        {
            "course_id": COURSE_ID,
            "repair_unit_ids": UNIT_IDS,
            "repair_stages": {
                "unit-01": ["practice"],
                "unit-02": ["structural"],
                "unit-03": ["evidence", "practice", "structural"],
            },
        },
    )

    build, _ = _prepare(paths)

    for candidate in UNIT_IDS:
        target = build / "courses" / COURSE_ID / "units" / candidate
        baseline = paths["baseline"] / "courses" / COURSE_ID / "units" / candidate
        assert (target / "repair-baseline").is_dir()
        assert (target / "repair-parent-baseline").is_dir()
        assert (target / "05-studykit.json").read_bytes() == (baseline / "05-studykit.json").read_bytes()
        assert (target / "repair-baseline" / "03-practice-flow.json").read_bytes() == (
            baseline / "03-practice-flow.json"
        ).read_bytes()
        assert (target / "repair-parent-baseline" / "03-practice-flow.json").read_bytes() == (
            baseline / "03-practice-flow.json"
        ).read_bytes()

    records = json.loads((build / "repair-plan.json").read_text(encoding="utf-8"))["unit_records"]
    selected = {item["unit_id"]: item for item in records}
    assert selected["unit-01"]["repair_stages"] == ["practice"]
    assert selected["unit-01"]["repair_checkpoint"] == "03-practice-flow.json"
    assert selected["unit-02"]["repair_stages"] == ["structural"]
    assert selected["unit-02"]["repair_checkpoint"] is None
    assert selected["unit-03"]["repair_stages"] == ["evidence", "practice", "structural"]
    assert selected["unit-03"]["repair_checkpoints"] == [
        "01-evidence-plan.json",
        "03-practice-flow.json",
        "05-studykit.candidate.json",
    ]
    assert selected["unit-03"]["repair_checkpoint"] == "03-practice-flow.json"


def test_fingerprint_changes_with_master_plan_and_is_stable_for_same_plan(tmp_path: Path) -> None:
    first_paths = _fixture(tmp_path / "first", ["unit-01"])
    first_build, first_record = _prepare(first_paths)
    same_build, same_record = _prepare(first_paths)

    second_paths = _fixture(tmp_path / "second", ["unit-02"])
    second_build, second_record = _prepare(second_paths)

    assert same_build == first_build
    assert same_record["build_id"] == first_record["build_id"]
    assert first_record["build_id"] != second_record["build_id"]
    assert first_build.name != second_build.name
    assert first_record["repair_plan_sha256"] != second_record["repair_plan_sha256"]
    assert first_record["build_id"] == first_build.name
    assert second_record["build_id"] == second_build.name


def test_resume_rejects_stale_direct_parent_snapshot(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, ["unit-01"])
    build, _ = _prepare(paths)
    stale_snapshot = (
        build
        / "courses"
        / COURSE_ID
        / "units"
        / "unit-01"
        / "repair-parent-baseline"
        / "source-note.txt"
    )
    stale_snapshot.write_text("from-a-different-parent\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the declared direct parent"):
        _prepare(paths)


def test_new_build_does_not_inherit_parent_snapshot_as_its_direct_parent(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, ["unit-01"])
    inherited = (
        paths["baseline"]
        / "courses"
        / COURSE_ID
        / "units"
        / "unit-01"
        / "repair-parent-baseline"
    )
    inherited.mkdir()
    (inherited / "from-grandparent.txt").write_text("stale\n", encoding="utf-8")

    build, _ = _prepare(paths)
    source = paths["baseline"] / "courses" / COURSE_ID / "units" / "unit-01"
    direct_parent = (
        build
        / "courses"
        / COURSE_ID
        / "units"
        / "unit-01"
        / "repair-parent-baseline"
    )

    assert not (direct_parent / "from-grandparent.txt").exists()
    assert artifact_tree_digest(direct_parent) == artifact_tree_digest(source)
