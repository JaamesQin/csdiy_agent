from __future__ import annotations

import copy
from pathlib import Path

import yaml

from scripts.audit_csdiy_registry import reconcile_target
from scripts.discover_csdiy_courses import discover, merge_progress


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "csdiy_catalog"


def _target(tmp_path: Path) -> dict[str, object]:
    # Build from the checked-in fixture through the same public discovery path
    # used by the offline worker; no network or provider is involved.
    discovered = discover(FIXTURE_ROOT, tmp_path / "registry.yaml", tmp_path / "progress.md")
    return discovered["course_targets"][0]


def _resume_target(target: dict[str, object], old: dict[str, object]) -> dict[str, object]:
    refreshed = copy.deepcopy(target)
    refreshed["state"] = "classified"
    refreshed["progress"] = {"state": "classified", "last_successful_checkpoint": "classification"}
    return merge_progress(refreshed, old)


def test_offline_worker_advances_research_and_inventory_states_without_losing_checkpoints(tmp_path: Path) -> None:
    target = _target(tmp_path)
    assert target["state"] == "classified"
    offering = {
        "course_id": "ucb-cs61b-spring-2024",
        "course_version": "spring-2024",
        "term": "Spring",
        "year": 2024,
        "official_url": "https://example.test/cs61b",
    }
    manifest = "data/manifests/ucb-cs61b-spring-2024.yaml"
    build = "outputs/ucb-cs61b-spring-2024/build-v2"

    researching = _resume_target(
        target,
        {
            "state": "researching_offering",
            "progress": {"state": "researching_offering", "last_successful_checkpoint": "offering_research"},
            "candidate_offerings": [{"url": "https://example.test/cs61b", "probe_status": "verified_public"}],
            "next_action": "select_offering",
        },
    )
    assert researching["state"] == "researching_offering"
    assert researching["candidate_offerings"][0]["probe_status"] == "verified_public"

    selected = _resume_target(
        researching,
        {
            "state": "offering_selected",
            "progress": {"state": "offering_selected", "last_successful_checkpoint": "offering_selection"},
            "selected_offering": offering,
            "next_action": "inventory_sources",
        },
    )
    assert selected["state"] == "offering_selected"
    assert selected["selected_offering"] == offering

    inventoried = _resume_target(
        selected,
        {
            "state": "sources_inventoried",
            "progress": {"state": "sources_inventoried", "last_successful_checkpoint": "source_inventory"},
            "selected_offering": offering,
            "source_inventory": {"unit_count": 2, "source_gaps": ["lecture-02 slides"]},
            "manifest_path": manifest,
            "active_build_id": "build-v2",
            "build": {"build_id": "build-v2", "path": build},
            "coverage": {"manifest_path": manifest, "build_id": "build-v2", "output_index": f"{build}/STUDYKIT_INDEX.md"},
            "next_action": "repair_missing_raw_sources",
        },
    )
    assert inventoried["state"] == "sources_inventoried"
    assert inventoried["selected_offering"] == offering
    assert inventoried["manifest_path"] == manifest
    assert inventoried["active_build_id"] == "build-v2"
    assert inventoried["build"] == {"build_id": "build-v2", "path": build}
    assert inventoried["coverage"]["output_index"] == f"{build}/STUDYKIT_INDEX.md"


def test_discovery_resume_is_idempotent_and_preserves_selected_manifest_and_build_metadata(tmp_path: Path) -> None:
    output = tmp_path / "registry.yaml"
    progress = tmp_path / "progress.md"
    first = discover(FIXTURE_ROOT, output, progress)
    target = first["course_targets"][0]
    target.update(
        {
            "state": "sources_inventoried",
            "selected_offering": {"course_id": "ucb-cs61b-spring-2024", "course_version": "spring-2024"},
            "manifest_path": "data/manifests/ucb-cs61b-spring-2024.yaml",
            "active_build_id": "build-v2",
            "build": {"build_id": "build-v2", "path": "outputs/ucb-cs61b-spring-2024/build-v2"},
            "coverage": {"manifest_path": "data/manifests/ucb-cs61b-spring-2024.yaml", "build_id": "build-v2"},
        }
    )
    output.write_text(yaml.safe_dump(first, allow_unicode=True, sort_keys=False), encoding="utf-8")

    resumed = discover(FIXTURE_ROOT, output, progress, resume=True)
    output.write_text(yaml.safe_dump(resumed, allow_unicode=True, sort_keys=False), encoding="utf-8")
    resumed_again = discover(FIXTURE_ROOT, output, progress, resume=True)

    assert resumed_again == resumed
    resumed_target = resumed_again["course_targets"][0]
    assert resumed_target["state"] == "sources_inventoried"
    assert resumed_target["selected_offering"]["course_id"] == "ucb-cs61b-spring-2024"
    assert resumed_target["manifest_path"] == "data/manifests/ucb-cs61b-spring-2024.yaml"
    assert resumed_target["active_build_id"] == "build-v2"
    assert resumed_target["build"]["path"] == "outputs/ucb-cs61b-spring-2024/build-v2"


def _manifest_record(*, raw: bool, chunks: bool) -> dict[str, object]:
    return {
        "unit_id": "lecture-01",
        "source_count": 1,
        "raw_exists": raw,
        "raw_sha256_matches": raw,
        "chunks_exists": chunks,
        "chunk_count": 1 if chunks else 0,
        "valid_chunk_count": 1 if chunks else 0,
        "source_page_count": 1 if chunks else None,
    }


def test_local_reconciliation_transitions_sources_inventoried_prepared_and_chunked() -> None:
    target = {
        "canonical_course_id": "demo-course",
        "state": "offering_selected",
        "selected_offering": {"course_id": "demo-course-spring-2026", "course_version": "spring-2026"},
        "manifest_path": "data/manifests/demo-course.yaml",
    }

    inventoried = reconcile_target(target, [_manifest_record(raw=False, chunks=False)], [])
    assert inventoried["state"] == "sources_inventoried"
    assert inventoried["manifest_path"] == target["manifest_path"]

    prepared = reconcile_target(target, [_manifest_record(raw=True, chunks=False)], [])
    assert prepared["state"] == "prepared"

    chunked = reconcile_target(target, [_manifest_record(raw=True, chunks=True)], [])
    assert chunked["state"] == "chunked"
    assert chunked["unit_count"] == 1
    assert chunked["chunk_count"] == 1


def test_reconciliation_keeps_selected_build_metadata_when_build_checkpoint_exists() -> None:
    target = {
        "canonical_course_id": "demo-course",
        "state": "sources_inventoried",
        "selected_offering": {"course_id": "demo-course-spring-2026"},
        "manifest_path": "data/manifests/demo-course.yaml",
        "active_build_id": "selected-build",
    }
    output = {
        "build_id": "selected-build",
        "path": "outputs/demo-course/selected-build",
        "result_status": "partial",
        "index_exists": False,
        "unit_records": [],
    }

    report = reconcile_target(target, [_manifest_record(raw=True, chunks=True)], [output])

    assert report["state"] == "authoring"
    assert report["build_id"] == "selected-build"
    assert report["manifest_path"] == "data/manifests/demo-course.yaml"
    assert target["selected_offering"] == {"course_id": "demo-course-spring-2026"}
