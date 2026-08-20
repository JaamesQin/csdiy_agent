from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.approve_studykit_archive import apply_approval, evaluate_archive


ROOT = Path(__file__).resolve().parents[2]
REAL_ARCHIVE = ROOT / "data" / "archive" / "studykits.sqlite3"
REGISTRY_AUDIT = ROOT / "evaluations" / "csdiy-catalog-registry-audit.json"
CS186_REPAIR_AUDIT = (
    ROOT / "evaluations" / "ucb-cs186-archive-identity-repair-audit-20260817.json"
)
LEGACY_APPROVALS = frozenset(
    {"mit-6.7960-fall-2024", "mit-6.s081-fall-2021"}
)


def test_real_archive_approval_gate_fails_closed_on_partial_legacy_and_identity_drift() -> None:
    result = evaluate_archive(REAL_ARCHIVE, REGISTRY_AUDIT)

    eligible = {
        item["course_id"] for item in result["builds"] if item["eligible"]
    }
    assert eligible == {
        "cambridge-semantics-of-programming-languages-2025-26",
        "mit-6-042j-spring-2024",
        "ucb-cs168-spring-2026",
        "ucb-cs188-spring-2026",
        "ucb-cs61a-summer-2026",
        "ucb-cs61c-spring-2026",
    }
    assert result["eligible_build_count"] == 6
    assert result["eligible_document_count"] == 153
    assert result["excluded_build_count"] == 6
    assert result["excluded_document_count"] == 133

    excluded = {
        item["course_id"]: item["reasons"]
        for item in result["builds"]
        if not item["eligible"]
    }
    assert "build_status_partial" in excluded["cmu-15.213-summer-2026"]
    assert "build_status_partial" in excluded["mit-6-031-spring-2022"]
    assert "build_status_partial" in excluded["ucb-cs61b-spring-2024"]
    assert "current_portable_schema_required" in excluded["mit-6.7960-fall-2024"]
    assert "current_portable_schema_required" in excluded["mit-6.s081-fall-2021"]
    assert "missing_independent_registry_audit" in excluded["ucb-cs186-spring-2026"]


def test_owner_legacy_approval_and_cs186_repair_release_220_documents() -> None:
    result = evaluate_archive(
        REAL_ARCHIVE,
        REGISTRY_AUDIT,
        supplemental_audits=(CS186_REPAIR_AUDIT,),
        owner_approved_legacy_courses=LEGACY_APPROVALS,
    )

    assert result["eligible_build_count"] == 9
    assert result["eligible_document_count"] == 220
    assert result["excluded_build_count"] == 3
    assert result["excluded_document_count"] == 66
    builds = {item["course_id"]: item for item in result["builds"]}
    assert builds["ucb-cs186-spring-2026"]["eligible"] is True
    assert builds["ucb-cs186-spring-2026"]["reasons"] == []
    for course_id in LEGACY_APPROVALS:
        assert builds[course_id]["eligible"] is True
        assert builds[course_id]["approval_basis"] == "owner-approved-reviewed-legacy"
        assert builds[course_id]["waived_reasons"]


def test_apply_approval_updates_only_eligible_builds_and_documents(tmp_path: Path) -> None:
    database = tmp_path / "archive.sqlite3"
    backup = tmp_path / "archive.before-approval.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE studykit_builds (
                build_id TEXT PRIMARY KEY,
                review_status TEXT NOT NULL
            );
            CREATE TABLE studykit_documents (
                unit_id TEXT PRIMARY KEY,
                build_id TEXT NOT NULL,
                review_status TEXT NOT NULL
            );
            INSERT INTO studykit_builds VALUES
                ('eligible-build', 'validated_draft'),
                ('excluded-build', 'validated_draft');
            INSERT INTO studykit_documents VALUES
                ('eligible-01', 'eligible-build', 'validated_draft'),
                ('eligible-02', 'eligible-build', 'validated_draft'),
                ('excluded-01', 'excluded-build', 'validated_draft');
            """
        )

    evaluation = {
        "eligible_document_count": 2,
        "builds": [
            {
                "build_id": "eligible-build",
                "eligible": True,
                "current_build_review_status": "validated_draft",
                "approved_document_count": 0,
            },
            {
                "build_id": "excluded-build",
                "eligible": False,
                "current_build_review_status": "validated_draft",
                "approved_document_count": 0,
            },
        ],
    }
    apply_approval(database, evaluation, backup=backup)

    assert backup.is_file()
    with sqlite3.connect(database) as connection:
        builds = dict(connection.execute("SELECT build_id, review_status FROM studykit_builds"))
        documents = dict(
            connection.execute("SELECT unit_id, review_status FROM studykit_documents")
        )
    assert builds == {
        "eligible-build": "approved",
        "excluded-build": "validated_draft",
    }
    assert documents == {
        "eligible-01": "approved",
        "eligible-02": "approved",
        "excluded-01": "validated_draft",
    }
