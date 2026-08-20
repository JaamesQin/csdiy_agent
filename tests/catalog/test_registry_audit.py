from __future__ import annotations

import yaml

from scripts.audit_csdiy_registry import (
    build_audit,
    build_projection_issues,
    independent_audit_evidence,
    output_records,
    reconcile_target,
)


def _unit(unit_id: str) -> dict[str, object]:
    return {
        "unit_id": unit_id,
        "final_exists": True,
        "validation_exists": True,
        "status": "draft",
        "validation_status": "succeeded",
    }


def _independent_audit(*, auditor: str = "reviewer-1", author: str = "author-1", source: str = "independent-audit.json", result: str = "pass") -> dict[str, object]:
    return {
        "status": "succeeded" if result == "pass" else "failed",
        "source": source,
        "auditor": auditor,
        "result": result,
        "author": author,
        "actual_reviewed_pages": [1],
        "issues": [],
    }


def test_reconcile_prefers_build_with_more_valid_units_over_lexical_path() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 2, "valid_chunk_count": 2, "source_page_count": 2},
        {"unit_id": "lecture-02", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 2, "valid_chunk_count": 2, "source_page_count": 2},
    ]
    output_records = [
        {"build_id": "f62-old-v0.1", "result_status": "partial", "index_exists": False, "unit_records": [_unit("lecture-01")]},
        {"build_id": "b6-new-v0.2", "result_status": "partial", "index_exists": False, "unit_records": [_unit("lecture-01"), _unit("lecture-02")]},
    ]

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, output_records)

    assert report["build_id"] == "b6-new-v0.2"
    assert report["validated_unit_count"] == 2
    assert report["state"] == "authoring"


def test_reconcile_output_index_matches_selected_build() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    older = {
        "build_id": "older-build",
        "path": "outputs/demo/older-build",
        "result_status": "partial",
        "index_exists": True,
        "unit_records": [_unit("lecture-01")],
    }
    selected = {
        "build_id": "selected-build",
        "path": "outputs/demo/selected-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()}],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [older, selected])

    assert report["build_id"] == "selected-build"
    assert report["output_index"] == "outputs/demo/selected-build"


def test_reconcile_separates_schema_validation_from_independent_audit() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "review-gated-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "pending"}],
    }

    pending = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert pending["validated_unit_count"] == 1
    assert pending["audit_passed_unit_count"] == 0
    assert pending["state"] == "authoring"

    output["unit_records"][0].update({"audit_status": "succeeded", "audit_evidence": _independent_audit()})
    audited = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert audited["audit_passed_unit_count"] == 1
    assert audited["state"] == "complete"


def test_failed_review_validation_cannot_be_overridden_by_audit_pass() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "review-failed-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{
            **_unit("lecture-01"),
            "review_status": "failed",
            "audit_status": "succeeded",
            "audit_evidence": _independent_audit(),
        }],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert report["audit_passed_unit_count"] == 0
    assert any(issue["code"] == "review_validation_not_passed" for issue in report["issues"])
    assert report["state"] == "authoring"


def test_author_self_audit_cannot_close_independent_gate() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "self-audit-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{
            **_unit("lecture-01"),
            "audit_status": "succeeded",
            "audit_evidence": _independent_audit(auditor="author-1", author="author-1", source="04-quality-audit.json"),
        }],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert report["audit_passed_unit_count"] == 0
    assert report["state"] == "authoring"
    assert any(issue["code"] == "independent_audit_author_match" for issue in report["issues"])
    assert "lecture-01" in report["next_action"]


def test_partial_units_report_the_unit_missing_independent_audit() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
        {"unit_id": "lecture-02", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "partial-audit-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [
            {**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()},
            _unit("lecture-02"),
        ],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert report["audit_passed_unit_count"] == 1
    assert report["audited_units"] == ["lecture-01"]
    assert any(issue["unit_id"] == "lecture-02" and issue["code"] == "independent_audit_missing" for issue in report["issues"])
    assert "lecture-02" in report["next_action"]


def test_all_requested_units_with_distinct_passing_audits_complete() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
        {"unit_id": "lecture-02", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "complete-audit-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [
            {**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit(auditor="reviewer-1")},
            {**_unit("lecture-02"), "audit_status": "succeeded", "audit_evidence": _independent_audit(auditor="reviewer-2")},
        ],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert report["audited_units"] == ["lecture-01", "lecture-02"]
    assert report["audit_passed_unit_count"] == 2
    assert report["state"] == "complete"


def test_explicit_practice_quality_gate_blocks_false_complete() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "quality-gated-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{
            **_unit("lecture-01"),
            "audit_status": "succeeded",
            "audit_evidence": _independent_audit(),
        }],
    }

    report = reconcile_target(
        {
            "canonical_course_id": "demo-course",
            "practice_quality_review": {
                "status": "needs_repair",
                "source": "calibration-review",
                "next_action": "rebuild_content_grounded_practice",
            },
        },
        manifest_records,
        [output],
    )

    assert report["state"] == "authoring"
    assert report["next_action"] == "rebuild_content_grounded_practice"
    assert any(issue["code"] == "practice_quality_review_not_passed" for issue in report["issues"])


def test_pending_visual_review_blocks_false_complete() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "visual-gated-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()}],
    }

    report = reconcile_target(
        {
            "canonical_course_id": "demo-course",
            "coverage": {"visual_review_status": "risk_pages_passed_final_citation_review_pending"},
        },
        manifest_records,
        [output],
    )

    assert report["state"] == "authoring"
    assert any(issue["code"] == "visual_review_not_complete" for issue in report["issues"])


def test_no_parser_risk_visual_status_allows_complete() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "visual-empty-risk-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()}],
    }

    report = reconcile_target(
        {
            "canonical_course_id": "demo-course",
            "coverage": {"visual_review_status": "no_parser_risk_pages"},
        },
        manifest_records,
        [output],
    )

    assert report["state"] == "complete"


def test_pending_classification_review_blocks_false_complete() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    output = {
        "build_id": "classification-gated-build",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()}],
    }

    report = reconcile_target(
        {"canonical_course_id": "demo-course", "audit": {"classification": "pending_independent_audit"}},
        manifest_records,
        [output],
    )

    assert report["state"] == "authoring"
    assert any(issue["code"] == "classification_review_not_complete" for issue in report["issues"])


def test_registry_audit_prefers_post_repair_audit_sidecar(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.json").write_text(
        '{"auditor_id":"old-reviewer","author_id":"author-1","result":"block","actual_reviewed_pages":[1],"audited_at":"2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    (unit / "independent-audit.post-repair.json").write_text(
        '{"auditor_id":"new-reviewer","author_id":"author-1","result":"pass","actual_reviewed_pages":[1],"audited_at":"2026-01-02T00:00:00+00:00"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-repair.json"


def test_registry_audit_post_final_reaudit_supersedes_older_post_final_block(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-final.json").write_text(
        '{"auditor_id":"old-reviewer","author_id":"author-1","result":"block","actual_reviewed_pages":[1],"audited_at":"2026-01-02T00:00:00+00:00"}',
        encoding="utf-8",
    )
    (unit / "independent-audit.post-final.reaudit.json").write_text(
        '{"auditor_id":"new-reviewer","author_id":"author-1","result":"pass_with_warnings","actual_reviewed_pages":[1],"audited_at":"2026-01-03T00:00:00+00:00"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-final.reaudit.json"


def test_registry_audit_recognizes_qualified_repair_sidecar(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-repair.reaudit.json").write_text(
        '{"auditor_id":"old-reviewer","author_id":"author-1","result":"block","actual_reviewed_pages":[1],"audited_at":"2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    (unit / "independent-audit.post-second-repair.xhigh.json").write_text(
        '{"auditor_id":"new-reviewer","author_id":"author-1","result":"pass","actual_reviewed_pages":[1],"audited_at":"2026-01-02T00:00:00+00:00"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-second-repair.xhigh.json"


def test_registry_audit_prefers_post_checkpoint_audit_sidecar(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-repair.json").write_text(
        '{"auditor_id":"old-reviewer","author_id":"author-1","result":"pass","actual_reviewed_pages":[1],"audited_at":"2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    (unit / "independent-audit.post-checkpoint.json").write_text(
        '{"auditor_id":"new-reviewer","author_id":"author-1","result":"block","actual_reviewed_pages":[1],"audited_at":"2026-01-02T00:00:00+00:00"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "failed"
    assert evidence["source"] == "independent-audit.post-checkpoint.json"


def test_registry_audit_prefers_newer_untimestamped_post_final_over_date_only_block(
    tmp_path,
) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.json").write_text(
        '{"auditor_id":"old-reviewer","author_id":"author-1","result":"block","actual_reviewed_pages":[1],"audited_at":"2026-08-12"}',
        encoding="utf-8",
    )
    (unit / "independent-audit.post-final.json").write_text(
        '{"auditor_id":"new-reviewer","author_id":"author-1","result":"pass_with_warnings","actual_reviewed_pages":[1]}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-final.json"


def test_registry_audit_accepts_explicit_nonblocking_warning_result(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-finalization.json").write_text(
        '{"auditor_id":"reviewer-current","author_id":"author-1","result":"pass_with_warnings","actual_reviewed_pages":[1]}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-finalization.json"


def test_registry_audit_accepts_post_final_warning_alias(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-final.json").write_text(
        '{"reviewer":"reviewer-current","author_id":"author-1","result":"passed_with_limitations","actual_reviewed_pages":[1]}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["source"] == "independent-audit.post-final.json"
    assert evidence["result"] == "pass_with_limitations"


def test_registry_audit_accepts_heading_anchors_without_page_numbers(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "review-plan.json").write_text(
        '{"actual_reviewed_pages": [], "actual_reviewed_anchors": ["Lecture 2#binary-search"], "anchor_type": "heading"}',
        encoding="utf-8",
    )
    (unit / "independent-audit.post-final.json").write_text(
        '{"auditor_id":"reviewer-current","author_id":"author-1","result":"pass","actual_reviewed_pages":[],"anchor_type":"heading"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["actual_reviewed_pages"] == []
    assert evidence["actual_reviewed_anchors"] == ["Lecture 2#binary-search"]


def test_registry_audit_accepts_implicit_markdown_heading_anchors(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-final.json").write_text(
        '{"auditor_id":"reviewer-current","author_id":"author-1","result":"pass","actual_reviewed_pages":[],"actual_reviewed_anchors":["## SIMD","### Registers"]}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"


def test_registry_audit_does_not_let_warning_alias_hide_compatibility_blocker(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-final.json").write_text(
        '{"reviewer":"reviewer-current","author_id":"author-1","result":"passed_with_warnings","actual_reviewed_pages":[1],"blockers":["COMPAT-001"]}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "failed"
    assert evidence["source"] == "independent-audit.post-final.json"
    assert any(issue["code"] == "independent_audit_blocker_present" for issue in evidence["issues"])


def test_registry_audit_does_not_let_metrics_mask_explicit_audit_block(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.json").write_text(
        '{"auditor_id":"reviewer-current","author_id":"author-1","result":"block","actual_reviewed_pages":[1],"blockers":["source-grounding blocker"],"audited_at":"2026-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    (unit / "metrics.json").write_text(
        '{"author_id":"author-1","independent_audit":true,"independent_auditor":"reviewer-metadata","independent_audit_result":"pass","independent_audit_time":"2026-01-02T00:00:00+00:00"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "failed"
    assert evidence["source"] == "independent-audit.json"


def test_registry_audit_ignores_preserved_historical_block_in_current_pass(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.json").write_text(
        '{"auditor_id":"reviewer-current","author_id":"author-1","result":"pass","actual_reviewed_pages":[1],"preserved_prior_evidence":{"initial_independent_audit":{"result":"block","blockers":["old issue"]}}}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "succeeded"
    assert evidence["result"] == "pass"


def test_registry_audit_reports_root_projection_drift(tmp_path) -> None:
    build_root = tmp_path / "build"
    build_root.mkdir()
    (build_root / "STUDYKIT_INDEX.md").write_text(
        "- Completed: **2/2**\n",
        encoding="utf-8",
    )
    batch_summary = {
        "requested_units": ["lecture-01", "lecture-02"],
        "succeeded_units": ["lecture-01"],
        "validated_units": ["lecture-01", "lecture-02"],
        "audited_units": ["lecture-01"],
        "failed_units": ["lecture-02"],
        "pending_units": [],
        "status": "partial",
    }
    course_summary = {
        "requested_unit_count": 2,
        "completed_unit_count": 2,
        "validated_unit_count": 2,
        "audited_unit_count": 1,
        "failed_unit_count": 1,
        "pending_unit_count": 0,
        "status": "partial",
    }
    result = {
        "completed_units": ["lecture-01"],
        "validated_units": ["lecture-01", "lecture-02"],
        "audited_units": ["lecture-01"],
        "failed_units": ["lecture-02"],
        "pending_units": [],
        "status": "partial",
    }
    handoff = {
        "requested_units": ["lecture-01", "lecture-02"],
        "completed_units": ["lecture-01"],
        "validated_units": ["lecture-01", "lecture-02"],
        "audited_units": ["lecture-01"],
        "failed_units": ["lecture-02"],
        "pending_units": [],
        "mergeable": False,
    }
    units = [
        {**_unit("lecture-01"), "audit_status": "succeeded"},
        {**_unit("lecture-02"), "audit_status": "failed"},
    ]

    issues = build_projection_issues(
        build_root,
        batch_summary=batch_summary,
        course_summary=course_summary,
        result=result,
        coordinator_handoff=handoff,
        unit_records=units,
    )

    assert any(
        issue["code"] == "build_projection_drift"
        and issue["file"] == "course-summary.json"
        and issue["field"] == "completed_unit_count"
        for issue in issues
    )
    assert any(
        issue["code"] == "build_projection_drift"
        and issue["file"] == "STUDYKIT_INDEX.md"
        for issue in issues
    )


def test_output_records_resolve_legacy_unit_alias_once(tmp_path) -> None:
    course_id = "ucb-cs186-spring-2026"
    build_root = tmp_path / "outputs" / course_id / "build-1"
    unit_root = build_root / "courses" / course_id / "units"
    unit_root.joinpath("lecture-01").mkdir(parents=True)
    unit_root.joinpath("note-02").mkdir(parents=True)
    (build_root / "manifest.yaml").write_text(
        yaml.safe_dump(
            {"course_id": course_id, "units": [{"unit_id": "note-01"}, {"unit_id": "note-02"}]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (build_root / "run.json").write_text("{}", encoding="utf-8")
    for unit_dir in (unit_root / "lecture-01", unit_root / "note-02"):
        (unit_dir / "05-studykit.json").write_text('{"status":"draft"}', encoding="utf-8")
        (unit_dir / "validation.json").write_text('{"status":"succeeded"}', encoding="utf-8")
        (unit_dir / "review-validation.json").write_text('{"status":"succeeded"}', encoding="utf-8")
        (unit_dir / "independent-audit.json").write_text(
            '{"auditor_id":"reviewer-1","author_id":"author-1","result":"pass","actual_reviewed_pages":[1]}',
            encoding="utf-8",
        )

    records = output_records({"course_id": course_id}, tmp_path)
    units = records[0]["unit_records"]

    assert [unit["unit_id"] for unit in units] == ["note-01", "note-02"]
    assert units[0]["unit_directory"] == "lecture-01"
    assert all(unit["audit_status"] == "succeeded" for unit in units)


def test_extra_residual_unit_directory_does_not_create_false_incomplete_state() -> None:
    manifest_records = [
        {
            "unit_id": "lecture-01",
            "source_count": 1,
            "raw_exists": True,
            "raw_sha256_matches": True,
            "chunks_exists": True,
            "chunk_count": 1,
            "valid_chunk_count": 1,
            "source_page_count": 1,
        }
    ]
    output = {
        "build_id": "complete-with-residue",
        "result_status": "succeeded",
        "index_exists": True,
        "projection_issues": [
            {
                "code": "build_projection_extra_unit_records",
                "blocking": False,
                "extra_unit_ids": ["stale-unit"],
            }
        ],
        "unit_records": [
            {
                **_unit("lecture-01"),
                "audit_status": "succeeded",
                "audit_evidence": _independent_audit(),
            }
        ],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert report["state"] == "complete"
    assert any(issue["code"] == "build_projection_extra_unit_records" for issue in report["issues"])


def test_registry_audit_rejects_missing_reviewer_or_pages(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-final.json").write_text(
        '{"author_id":"author-1","result":"pass"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "failed"
    assert any(issue["code"] == "independent_audit_auditor_missing" for issue in evidence["issues"])
    assert any(issue["code"] == "independent_audit_actual_reviewed_pages_missing" for issue in evidence["issues"])


def test_registry_audit_recognizes_alternate_offering_manifests(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    manifest_dir = tmp_path / "data" / "manifests"
    manifest_dir.mkdir(parents=True)
    base_manifest = {
        "primary_course_number": "CS61A",
        "units": [],
    }
    (manifest_dir / "ucb-cs61a-spring-2026.yaml").write_text(
        yaml.safe_dump({**base_manifest, "course_id": "ucb-cs61a-spring-2026"}),
        encoding="utf-8",
    )
    (manifest_dir / "ucb-cs61a-summer-2026.yaml").write_text(
        yaml.safe_dump({**base_manifest, "course_id": "ucb-cs61a-summer-2026"}),
        encoding="utf-8",
    )
    registry_path.write_text(
        yaml.safe_dump(
            {
                "course_targets": [{"canonical_course_id": "ucb-cs61a", "course_numbers": ["CS61A"]}],
                "nav_leaves": [],
            }
        ),
        encoding="utf-8",
    )

    _, audit = build_audit(registry_path, tmp_path)

    assert audit["orphan_manifests"] == []


def test_reconcile_prefers_active_hybrid_build_over_historical_standard_build() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    historical = {
        "build_id": "historical-standard",
        "coordinator_id": "standard-v021-coordinator-demo",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "succeeded"}],
    }
    active = {
        "build_id": "active-hybrid",
        "coordinator_id": "hybrid-fast-demo",
        "result_status": "partial",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "pending"}],
    }

    report = reconcile_target(
        {"canonical_course_id": "demo-course", "active_build_id": "active-hybrid"},
        manifest_records,
        [historical, active],
    )

    assert report["build_id"] == "active-hybrid"
    assert report["audit_passed_unit_count"] == 0


def test_reconcile_prefers_succeeded_build_without_explicit_active_marker() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    historical = {
        "build_id": "historical-standard",
        "coordinator_id": "standard-v021-coordinator-demo",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()}],
    }
    stale_hybrid = {
        "build_id": "stale-hybrid",
        "coordinator_id": "hybrid-fast-demo",
        "result_status": "partial",
        "index_exists": True,
        "unit_records": [{**_unit("lecture-01"), "audit_status": "pending"}],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [historical, stale_hybrid])

    assert report["build_id"] == "historical-standard"
    assert report["audit_passed_unit_count"] == 1


def test_registry_audit_second_repair_checkpoint_supersedes_first_repair_pass(tmp_path) -> None:
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "independent-audit.post-repair.json").write_text(
        '{"auditor_id":"reviewer-1","author_id":"author-1","result":"pass",'
        '"actual_reviewed_pages":[1],"audited_at":"2026-08-11T00:00:00+00:00"}',
        encoding="utf-8",
    )
    (unit / "independent-audit.post-repair-2.reaudit.json").write_text(
        '{"auditor_id":"reviewer-2","author_id":"author-1","result":"block",'
        '"actual_reviewed_pages":[1],"audited_at":"2026-08-12T00:00:00+00:00"}',
        encoding="utf-8",
    )

    evidence = independent_audit_evidence(unit)

    assert evidence["status"] == "failed"
    assert evidence["source"] == "independent-audit.post-repair-2.reaudit.json"


def test_reconcile_active_second_repair_partial_line_remains_authoritative() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
        {"unit_id": "lecture-02", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    historical = {
        "build_id": "historical-complete",
        "result_status": "succeeded",
        "index_exists": True,
        "unit_records": [
            {**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()},
            {**_unit("lecture-02"), "audit_status": "succeeded", "audit_evidence": _independent_audit(auditor="reviewer-2")},
        ],
    }
    active_second_repair = {
        "build_id": "repair-2-active",
        "result_status": "partial",
        "index_exists": True,
        "unit_records": [
            {**_unit("lecture-01"), "audit_status": "succeeded", "audit_evidence": _independent_audit()},
            {**_unit("lecture-02"), "audit_status": "pending"},
        ],
    }

    report = reconcile_target(
        {"canonical_course_id": "demo-course", "active_build_id": "repair-2-active"},
        manifest_records,
        [historical, active_second_repair],
    )

    assert report["build_id"] == "repair-2-active"
    assert report["state"] == "authoring"
    assert report["missing_audit_units"] == ["lecture-02"]


def test_reviewed_root_compatibility_does_not_require_generated_projections(tmp_path) -> None:
    course_id = "demo-course"
    build_root = tmp_path / "data" / "reviewed" / course_id / "reviewed-v1"
    unit_root = build_root / "units" / "lecture-01"
    unit_root.mkdir(parents=True)
    (build_root / "REVIEW.md").write_text("# Reviewed package\n", encoding="utf-8")
    (build_root / "result.json").write_text('{"status":"succeeded"}', encoding="utf-8")
    (unit_root / "05-studykit.json").write_text('{"status":"draft"}', encoding="utf-8")
    (unit_root / "validation.json").write_text('{"status":"succeeded"}', encoding="utf-8")
    (unit_root / "independent-audit.json").write_text(
        '{"auditor_id":"reviewer-1","author_id":"author-1","result":"pass",'
        '"actual_reviewed_pages":[1]}',
        encoding="utf-8",
    )

    records = output_records({"course_id": course_id}, tmp_path)

    assert records[0]["package_kind"] == "reviewed"
    assert records[0]["index_exists"] is True
    assert records[0]["projection_issues"] == []


def test_checkpoint_integrity_blocks_root_false_complete_when_unit_checkpoint_is_missing() -> None:
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 1, "source_page_count": 1},
    ]
    projection_issues = [
        {
            "code": "build_projection_unit_denominator_drift",
            "blocking": True,
            "missing_unit_ids": ["lecture-01"],
        }
    ]
    output = {
        "build_id": "checkpoint-corrupt",
        "result_status": "succeeded",
        "index_exists": True,
        "projection_issues": projection_issues,
        "unit_records": [],
    }

    report = reconcile_target({"canonical_course_id": "demo-course"}, manifest_records, [output])

    assert report["state"] == "authoring"
    assert report["audit_passed_unit_count"] == 0
    assert any(issue["code"] == "build_projection_unit_denominator_drift" for issue in report["issues"])
