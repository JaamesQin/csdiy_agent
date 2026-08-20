from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.discover_csdiy_courses import (
    build_course_targets,
    canonical_identity_key,
    catalog_identity_overrides,
    course_id_for,
    discover,
    infer_direction,
    infer_direction_details,
    merge_progress,
    render_progress,
    render_selected_status,
    sequence_evidence,
    snapshot_commit,
)


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
    assert "Course nav leaves: **2**" in rendered
    assert "Every Markdown nav leaf is retained" in rendered


def test_resume_projects_canonical_target_state_to_nav_leaf(tmp_path: Path) -> None:
    output = tmp_path / "registry.yaml"
    progress = tmp_path / "progress.md"
    first = discover(FIXTURE_ROOT, output, progress)
    first["course_targets"][0]["state"] = "sources_inventoried"
    first["course_targets"][0]["audit"]["last_successful_checkpoint"] = "source_inventory"
    output.write_text(yaml.safe_dump(first, allow_unicode=True, sort_keys=False), encoding="utf-8")

    resumed = discover(FIXTURE_ROOT, output, progress, resume=True)

    course_leaves = [leaf for leaf in resumed["nav_leaves"] if leaf["is_course_target"]]
    assert course_leaves
    for leaf in course_leaves:
        assert leaf["progress"]["state"] == "sources_inventoried"
        assert leaf["progress"]["course_target_states"] == ["sources_inventoried"]


def test_selected_status_reports_validated_unit_count(tmp_path: Path) -> None:
    registry = discover(FIXTURE_ROOT, tmp_path / "registry.yaml", tmp_path / "progress.md")
    target = registry["course_targets"][0]
    target["coverage"].update({"unit_count": 2, "validated_unit_count": 1, "chunk_count": 20, "build_id": "build-v2"})
    target["audit"]["last_successful_checkpoint"] = "registry_reconciliation"

    rendered = render_selected_status(registry)

    assert "1/2 units validated; 0/2 audited; registry_reconciliation" in rendered


def test_selected_status_includes_any_target_with_a_selected_offering(tmp_path: Path) -> None:
    registry = discover(FIXTURE_ROOT, tmp_path / "registry.yaml", tmp_path / "progress.md")
    target = registry["course_targets"][0]
    target["canonical_course_id"] = "newly-selected-course"
    target["selected_offering"] = {"course_id": "newly-selected-course-spring-2026", "course_version": "spring-2026"}

    rendered = render_selected_status(registry)

    assert "`newly-selected-course`" in rendered
    assert "[review](newly-selected-course-spring-2026-source-review.md)" in rendered


def test_snapshot_directory_name_is_authoritative_without_nested_git(tmp_path: Path) -> None:
    snapshot = tmp_path / "81d874ee0fb37b2289839847026ba7651f3725d5"

    assert snapshot_commit(snapshot) == "81d874ee0fb37b2289839847026ba7651f3725d5"


def test_resume_preserves_researched_offering_candidates(tmp_path: Path) -> None:
    new = {"candidate_offerings": [{"url": "https://guide.example/term", "probe_status": "not_run"}]}
    old = {
        "candidate_offerings": [{"url": "https://guide.example/term", "probe_status": "verified_public"}],
        "selected_offering": {"course_version": "spring-2024"},
        "state": "offering_selected",
    }

    resumed = merge_progress(new, old)

    assert resumed["candidate_offerings"][0]["probe_status"] == "verified_public"
    assert resumed["selected_offering"]["course_version"] == "spring-2024"
    assert resumed["state"] == "offering_selected"


def test_nav_category_precedes_conflicting_course_title() -> None:
    title = "CS 168: Introduction to the Internet: Architecture and Protocols"

    assert infer_direction(["计算机网络"], title) == "networks"
    direction, evidence, secondary = infer_direction_details(["计算机网络"], title)
    assert direction == "networks"
    assert evidence
    assert "architecture" in secondary


def test_neural_network_title_does_not_create_networks_secondary_direction() -> None:
    direction, _evidence, secondary = infer_direction_details(
        ["数学进阶"],
        "The Information Theory, Pattern Recognition, and Neural Networks",
    )

    assert direction == "discrete_mathematics_probability"
    assert "machine_learning" in secondary
    assert "networks" not in secondary


def test_substantive_numerical_analysis_title_overrides_broad_math_bucket() -> None:
    direction, evidence, secondary = infer_direction_details(
        ["数学进阶"],
        "MIT18.330: Introduction to numerical analysis",
    )

    assert direction == "numerical_scientific_computing"
    assert any("numerical-analysis" in item for item in evidence)
    assert secondary == []


def test_large_language_model_category_is_artificial_intelligence() -> None:
    assert infer_direction(["深度生成模型", "大语言模型"], "CMU 11-667") == "artificial_intelligence"


def test_punctuation_and_legacy_prefix_aliases_share_one_identity_key() -> None:
    assert canonical_identity_key("Massachusetts Institute of Technology", "6.7960") == canonical_identity_key(
        "Massachusetts Institute of Technology", "6-7960"
    )
    assert canonical_identity_key("Carnegie Mellon University", "CS15213") == canonical_identity_key(
        "Carnegie Mellon University", "15-213"
    )


def test_non_latin_no_number_pages_use_source_stem_for_canonical_identity() -> None:
    assert course_id_for("PKU 编译原理实践", "docs/编译原理/PKU-Compilers.md", None, "Peking University") == "pku-pku-compilers"
    assert course_id_for("北京大学 软件分析技术", "docs/编程语言设计与分析/PKU-SoftwareAnalysis.md", None, "Peking University") == "pku-pku-softwareanalysis"
    assert course_id_for("智能计算系统", "docs/机器学习系统/AICS.md", None, None) == "aics"


def test_topic_ampersand_is_not_a_course_sequence() -> None:
    assert sequence_evidence("CS571 Building UI (React & React Native)", "docs/Web开发/CS571.md", "", ["CS571"]) is None
    assert sequence_evidence(
        "MIT 6.046: Design and Analysis of Algorithms",
        "docs/数据结构与算法/6.046.md",
        "Prerequisite: 6.006/CS61B/CS106B/CS106X or equivalent",
        ["6.046"],
    ) is None


def test_known_sequence_and_crosslisted_overrides_preserve_identity_evidence() -> None:
    sequence = catalog_identity_overrides("Coursera: Algorithms I & II", "docs/数据结构与算法/Algo.md", "Coursera: Algorithms I & II", [])
    crosslisted = catalog_identity_overrides("UMich EECS 498-007 / 598-005", "docs/深度学习/EECS498-007.md", "UMich EECS 498-007 / 598-005", [])
    assert [item["code"] for item in sequence] == ["Algorithms-I", "Algorithms-II"]
    assert [item["code"] for item in crosslisted] == ["EECS498-007", "EECS598-005"]


def test_cambridge_semantics_override_preserves_provider_identity() -> None:
    records = catalog_identity_overrides(
        "Cambridge: Semantics of Programming Languages",
        "docs/编程语言设计与分析/Cambridge-Semantics.md",
        "Cambridge: Semantics of Programming Languages University of Cambridge",
        [],
    )
    assert records[0]["institution"] == "University of Cambridge"
    assert course_id_for(
        "Cambridge: Semantics of Programming Languages",
        "docs/编程语言设计与分析/Cambridge-Semantics.md",
        records[0]["code"],
        records[0]["institution"],
    ) == "cambridge-semantics-of-programming-languages"


@pytest.mark.parametrize(
    ("target_id", "category", "title", "secondary"),
    [
        (
            "ucb-cs168",
            "计算机网络",
            "UCB CS168: Introduction to the Internet: Architecture and Protocols",
            "architecture",
        ),
        (
            "ucb-cs161",
            "计算机系统安全",
            "UCB CS161: Computer Security Architecture",
            "architecture",
        ),
    ],
)
def test_course_target_priority_preserves_nav_evidence_over_title_keywords(
    target_id: str, category: str, title: str, secondary: str
) -> None:
    leaf = {
        "course_target_ids": [target_id],
        "course_target_records": [{"canonical_course_id": target_id, "institution": "University of California, Berkeley", "course_number": target_id.rsplit("-", 1)[-1]}],
        "course_family_id": f"page-{target_id}",
        "course_title": title,
        "nav_title": title,
        "nav_category": [category],
        "aliases": [title],
        "language": "en",
        "leaf_key": f"{category}::{title}",
        "source_markdown_path": f"docs/courses/{target_id}.md",
        "public_page_url": "https://csdiy.wiki/courses/example",
        "page_sha256": "fixture",
        "candidate_offerings": [],
    }

    target = build_course_targets([leaf], {})[0]
    priority = target["priority"]

    assert priority["major_direction"] == {
        "计算机网络": "networks",
        "计算机系统安全": "security",
    }[category]
    assert secondary in priority["secondary_directions"]
    assert any("category evidence takes precedence" in item for item in priority["direction_evidence"])


def test_resume_replaces_stale_generated_direction_but_keeps_research_fields() -> None:
    resumed = merge_progress(
        {"priority": {"major_direction": "networks", "direction_evidence": ["category"], "secondary_directions": ["architecture"]}},
        {"priority": {"major_direction": "architecture", "public_source_readiness": 3}, "state": "classified"},
    )

    assert resumed["priority"]["major_direction"] == "networks"
    assert resumed["priority"]["secondary_directions"] == ["architecture"]
    assert resumed["priority"]["public_source_readiness"] == 3


def test_new_priority_records_keep_unresearched_signals_explicit() -> None:
    target = build_course_targets(
        [
            {
                "course_target_ids": ["example-course"],
                "course_target_records": [{"canonical_course_id": "example-course"}],
                "course_family_id": "example-family",
                "course_title": "Example Course",
                "nav_title": "Example Course",
                "nav_category": ["编程入门"],
                "aliases": [],
                "language": "en",
                "leaf_key": "example",
                "source_markdown_path": "docs/example.md",
                "public_page_url": "https://csdiy.wiki/example",
                "page_sha256": "fixture",
                "candidate_offerings": [],
            }
        ],
        {},
    )[0]["priority"]

    assert target["notes_kind"] == "unknown"
    assert target["notes_completeness"] == "unknown"
    assert target["notes_public_status"] == "not_researched"
    assert target["notes_license_status"] == "not_researched"
    assert target["notes_public_readiness"] == 0
    assert target["ai_relevance"] is None
    assert target["non_cs_accessibility"] is None
