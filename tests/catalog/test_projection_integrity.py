from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.audit_csdiy_registry import atomic_write_yaml, build_audit, find_manifest_for_target
from scripts.discover_csdiy_courses import render_progress, render_selected_status


@pytest.fixture
def projection_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    """A small, self-contained catalog with two canonical course targets."""

    registry_path = tmp_path / "data" / "catalog" / "registry.yaml"
    registry_path.parent.mkdir(parents=True)
    targets = [
        {
            "canonical_course_id": "ucb-cs61b",
            "state": "classified",
            "next_action": "research_offering",
            "priority": {"major_direction": "data_structures_algorithms"},
            "coverage": {"unit_count": 0, "validated_unit_count": 0, "audit_passed_unit_count": 0, "chunk_count": 0},
            "audit": {"last_successful_checkpoint": "classification"},
            "progress": {"state": "classified"},
            "selected_offering": {"course_id": "ucb-cs61b-spring-2024", "course_version": "spring-2024"},
        },
        {
            "canonical_course_id": "mit-6-042j",
            "state": "classified",
            "next_action": "research_offering",
            "priority": {"major_direction": "discrete_mathematics_probability"},
            "coverage": {"unit_count": 0, "validated_unit_count": 0, "audit_passed_unit_count": 0, "chunk_count": 0},
            "audit": {"last_successful_checkpoint": "classification"},
            "progress": {"state": "classified"},
            "selected_offering": {"course_id": "mit-6-042j-spring-2024", "course_version": "spring-2024"},
        },
    ]
    registry: dict[str, object] = {
        "source_catalog": {
            "pinned_commit": "fixture",
            "repository_url": "fixture",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "mkdocs_sha256": "fixture",
            "docs_tree_fingerprint": "fixture",
        },
        "nav_leaves": [
            {"leaf_key": "course-1", "is_course_target": True},
            {"leaf_key": "course-2", "is_course_target": True},
            {"leaf_key": "tool-1", "is_course_target": False},
        ],
        "course_targets": targets,
        "summary": {"nav_leaf_count": 3, "course_target_count": 2},
        "classification": {"independent_audit_status": "pending"},
        "global_gate": "partial",
    }
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return registry_path, registry


def test_registry_progress_and_status_use_the_same_canonical_target_denominator(
    projection_fixture: tuple[Path, dict[str, object]],
) -> None:
    _, registry = projection_fixture

    expected = len(registry["course_targets"])
    progress = render_progress(registry)
    status = render_selected_status(registry)

    assert registry["summary"]["course_target_count"] == expected
    assert f"Course-target denominator: **{expected}**" in progress
    assert "Markdown nav leaves: **3**" in status
    assert "Course nav leaves: **2**" in status
    assert "Excluded nav leaves: **1**" in status
    assert f"Canonical course-target denominator: **{expected}**" in status
    assert progress.count("| `") >= expected
    assert len({target["canonical_course_id"] for target in registry["course_targets"]}) == expected


def test_audit_detects_a_stale_complete_target(projection_fixture: tuple[Path, dict[str, object]]) -> None:
    registry_path, registry = projection_fixture
    target = registry["course_targets"][0]
    target.update({"state": "complete", "manifest_path": "data/manifests/ucb-cs61b.yaml"})
    manifest_dir = registry_path.parents[1] / "manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "ucb-cs61b.yaml").write_text(
        yaml.safe_dump(
            {
                "course_id": "ucb-cs61b-spring-2024",
                "primary_course_number": "CS61B",
                "units": [{"unit_id": "lecture-01", "sources": [{"local_path": "missing.pdf"}]}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    _, audit = build_audit(registry_path, registry_path.parents[2])

    assert audit["false_complete_targets"] == ["ucb-cs61b"]
    report = next(item for item in audit["target_reports"] if item["canonical_course_id"] == "ucb-cs61b")
    assert report["state"] != "complete"


def test_audit_reports_orphan_manifests_and_builds(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"course_targets": [{"canonical_course_id": "known-course", "course_numbers": ["CS1"]}], "nav_leaves": []}),
        encoding="utf-8",
    )
    manifests = tmp_path / "data" / "manifests"
    manifests.mkdir(parents=True)
    (manifests / "orphan.yaml").write_text(yaml.safe_dump({"course_id": "orphan-course", "units": []}), encoding="utf-8")
    orphan_build = tmp_path / "outputs" / "ghost-course" / "build-v1"
    orphan_build.mkdir(parents=True)

    _, audit = build_audit(registry_path, tmp_path)

    assert audit["orphan_manifests"] == ["data/manifests/orphan.yaml"]
    assert audit["orphan_builds"] == ["outputs/ghost-course/build-v1"]


def test_selected_manifest_path_wins_over_lexical_semester_order(tmp_path: Path) -> None:
    manifests = [
        (tmp_path / "data" / "manifests" / "ucb-cs61a-spring-2026.yaml", {"course_id": "ucb-cs61a-spring-2026", "primary_course_number": "CS 61A"}),
        (tmp_path / "data" / "manifests" / "ucb-cs61a-summer-2026.yaml", {"course_id": "ucb-cs61a-summer-2026", "primary_course_number": "CS 61A"}),
    ]
    target = {
        "canonical_course_id": "ucb-cs61a",
        "course_numbers": ["CS 61A"],
        "manifest_path": "data/manifests/ucb-cs61a-summer-2026.yaml",
    }

    selected = find_manifest_for_target(target, manifests)

    assert selected is not None
    assert selected[0].as_posix().endswith("data/manifests/ucb-cs61a-summer-2026.yaml")


def test_atomic_registry_projection_replaces_and_recovers_after_failed_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text("version: old\n", encoding="utf-8")
    atomic_write_yaml(path, {"version": "new"})
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {"version": "new"}
    assert not path.with_name(f".{path.name}.tmp").exists()

    path.write_text("version: stable\n", encoding="utf-8")
    original_replace = Path.replace

    def fail_replace(self: Path, target: Path) -> Path:
        if self.name == f".{path.name}.tmp":
            raise OSError("simulated projection replacement failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="projection replacement failure"):
        atomic_write_yaml(path, {"version": "must-not-commit"})
    assert path.read_text(encoding="utf-8") == "version: stable\n"

    monkeypatch.setattr(Path, "replace", original_replace)
    atomic_write_yaml(path, {"version": "recovered"})
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {"version": "recovered"}
