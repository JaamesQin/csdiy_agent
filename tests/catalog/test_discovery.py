from __future__ import annotations

from pathlib import Path

import yaml

from scripts.discover_csdiy_courses import discover, render_progress


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "csdiy_catalog"


def test_discovery_walks_nav_and_deduplicates_translations(tmp_path: Path) -> None:
    output = tmp_path / "registry.yaml"
    progress = tmp_path / "progress.md"

    registry = discover(FIXTURE_ROOT, output, progress)

    assert registry["source_catalog"]["markdown_nav_leaf_count"] == 5
    assert len(registry["nav_leaves"]) == 5
    assert len(registry["course_targets"]) == 1
    target = registry["course_targets"][0]
    assert target["canonical_course_id"] == "ucb-cs61b"
    assert len(target["guide_page_provenance"]) == 2
    assert target["candidate_offerings"][0]["probe_status"] == "not_run"

    by_title = {leaf["nav_title"]: leaf for leaf in registry["nav_leaves"]}
    assert by_title["Git"]["target_type"] == "tool"
    assert by_title["A learning roadmap"]["target_type"] == "roadmap"
    assert by_title["Git"]["is_course_target"] is False
    assert "tool" in by_title["Git"]["classification_reason"]


def test_resume_preserves_progress_fields(tmp_path: Path) -> None:
    output = tmp_path / "registry.yaml"
    progress = tmp_path / "progress.md"
    first = discover(FIXTURE_ROOT, output, progress)
    first["course_targets"][0]["state"] = "prepared"
    first["course_targets"][0]["manifest_path"] = "data/manifests/ucb-cs61b.yaml"
    output.write_text(yaml.safe_dump(first, allow_unicode=True, sort_keys=False), encoding="utf-8")

    resumed = discover(FIXTURE_ROOT, output, progress, resume=True)

    assert resumed["course_targets"][0]["state"] == "prepared"
    assert resumed["course_targets"][0]["manifest_path"] == "data/manifests/ucb-cs61b.yaml"


def test_progress_is_explicit_about_the_denominator(tmp_path: Path) -> None:
    registry = discover(FIXTURE_ROOT, tmp_path / "registry.yaml", tmp_path / "progress.md")

    rendered = render_progress(registry)

    assert "Course-target denominator: **1**" in rendered
    assert "Every Markdown nav leaf is retained" in rendered
