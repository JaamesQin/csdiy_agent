from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.agent.contracts import CourseContext
from app.catalog.archive import StudyKitArchive
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.studykits import (
    ArchivedStudyKitStore,
    CompositeStudyKitStore,
    ReviewedFileStudyKitStore,
    StudyKitArchiveError,
)
from app.course_navigation.service import CourseNavigationService
from app.learning.service import StudyKitLookupService
from app.profile.contracts import LearnerProfile
from app.protocol.schemas import ChatMessage
from scripts.archive_studykit_builds import archive_builds


ROOT = Path(__file__).resolve().parents[2]
REAL_ARCHIVE = ROOT / "data" / "archive" / "studykits.sqlite3"
V01_IDENTITY = ("mit-6.7960-fall-2024", "fall-2024", "lecture-01")
V02_IDENTITY = (
    "cambridge-semantics-of-programming-languages-2025-26",
    "2025-26",
    "lecture-01",
)
V02_SECOND_IDENTITY = (
    "cambridge-semantics-of-programming-languages-2025-26",
    "2025-26",
    "lecture-02",
)


def _messages(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


def _copy_approved_documents(
    path: Path,
    *identities: tuple[str, str, str],
) -> Path:
    source = sqlite3.connect(f"file:{REAL_ARCHIVE}?mode=ro&immutable=1", uri=True)
    target = sqlite3.connect(path)
    try:
        for table in ("studykit_builds", "studykit_documents", "studykit_artifacts"):
            sql = source.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()[0]
            target.execute(sql)
        target.execute("PRAGMA user_version = 1")

        build_ids: set[str] = set()
        for course_id, course_version, unit_id in identities:
            document = source.execute(
                """
                SELECT * FROM studykit_documents
                WHERE course_id=? AND course_version=? AND unit_id=?
                """,
                (course_id, course_version, unit_id),
            ).fetchone()
            assert document is not None
            document_columns = [
                row[1] for row in source.execute("PRAGMA table_info(studykit_documents)")
            ]
            document_values = dict(zip(document_columns, document, strict=True))
            document_values["review_status"] = "approved"
            placeholders = ",".join("?" for _ in document_columns)
            target.execute(
                f"INSERT INTO studykit_documents ({','.join(document_columns)}) VALUES ({placeholders})",
                [document_values[column] for column in document_columns],
            )
            build_ids.add(str(document_values["build_id"]))

        build_columns = [row[1] for row in source.execute("PRAGMA table_info(studykit_builds)")]
        for build_id in build_ids:
            build = source.execute(
                "SELECT * FROM studykit_builds WHERE build_id=?", (build_id,)
            ).fetchone()
            assert build is not None
            build_values = dict(zip(build_columns, build, strict=True))
            build_values["review_status"] = "approved"
            build_values["unit_count"] = sum(
                identity[0] == build_values["course_id"]
                and identity[1] == build_values["course_version"]
                for identity in identities
            )
            placeholders = ",".join("?" for _ in build_columns)
            target.execute(
                f"INSERT INTO studykit_builds ({','.join(build_columns)}) VALUES ({placeholders})",
                [build_values[column] for column in build_columns],
            )
        target.commit()
    finally:
        source.close()
        target.close()
    return path


def test_real_archive_exposes_only_approved_documents() -> None:
    store = ArchivedStudyKitStore(REAL_ARCHIVE)

    ready = store.list_ready()

    assert len(ready) == 220
    assert {item.course_id for item in ready} == {
        "cambridge-semantics-of-programming-languages-2025-26",
        "mit-6-042j-spring-2024",
        "mit-6.7960-fall-2024",
        "mit-6.s081-fall-2021",
        "ucb-cs168-spring-2026",
        "ucb-cs186-spring-2026",
        "ucb-cs188-spring-2026",
        "ucb-cs61a-summer-2026",
        "ucb-cs61c-spring-2026",
    }
    assert store.resolve_context(
        course_id="ucb-cs186-spring-2026", unit_id="note-03"
    ) == CourseContext(
        course_id="ucb-cs186-spring-2026",
        course_version="spring-2026",
        unit_id="note-03",
        title="磁盘、文件与记录布局",
    )


def test_approved_archive_supports_both_portable_schema_families(tmp_path: Path) -> None:
    archive = _copy_approved_documents(tmp_path / "approved.sqlite3", V01_IDENTITY, V02_IDENTITY)
    store = ArchivedStudyKitStore(archive)

    ready = store.list_ready()

    assert [(item.course_id, item.unit_id) for item in ready] == [
        (V02_IDENTITY[0], "lecture-01"),
        (V01_IDENTITY[0], "lecture-01"),
    ]
    assert store.match_context(["查看 Cambridge semantics 第 1 讲"]) == CourseContext(
        course_id=V02_IDENTITY[0],
        course_version=V02_IDENTITY[1],
        unit_id="lecture-01",
        title="导论：语义与转换系统",
    )


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        (
            "UPDATE studykit_documents SET document_sha256=?",
            "document hash mismatch",
        ),
        (
            "UPDATE studykit_documents SET unit_id='lecture-99'",
            "identity mismatch",
        ),
    ],
)
def test_approved_archive_fails_closed_on_document_corruption(
    tmp_path: Path,
    statement: str,
    expected: str,
) -> None:
    archive = _copy_approved_documents(tmp_path / "corrupt.sqlite3", V01_IDENTITY)
    with sqlite3.connect(archive) as connection:
        parameters = ("0" * 64,) if "?" in statement else ()
        connection.execute(statement, parameters)

    with pytest.raises(StudyKitArchiveError, match=expected):
        ArchivedStudyKitStore(archive).list_ready()


def test_approved_archive_fails_closed_on_unknown_schema(tmp_path: Path) -> None:
    archive = _copy_approved_documents(tmp_path / "unknown.sqlite3", V01_IDENTITY)
    with sqlite3.connect(archive) as connection:
        connection.execute("UPDATE studykit_builds SET schema_id='unknown-v9'")
        connection.execute("UPDATE studykit_documents SET schema_id='unknown-v9'")

    with pytest.raises(StudyKitArchiveError, match="unsupported approved StudyKit schema"):
        ArchivedStudyKitStore(archive).list_ready()


def test_archive_fails_closed_on_incompatible_tables(tmp_path: Path) -> None:
    archive = tmp_path / "incompatible.sqlite3"
    with sqlite3.connect(archive) as connection:
        connection.execute("PRAGMA user_version = 1")
        connection.execute("CREATE TABLE studykit_builds (build_id TEXT PRIMARY KEY)")

    with pytest.raises(StudyKitArchiveError, match="table is incompatible"):
        ArchivedStudyKitStore(archive).list_ready()


def test_composite_store_prefers_approved_archive_and_keeps_golden_fallback(
    tmp_path: Path,
) -> None:
    approved = _copy_approved_documents(tmp_path / "approved.sqlite3", V01_IDENTITY)
    primary = ArchivedStudyKitStore(approved)
    fallback = ReviewedFileStudyKitStore()
    store = CompositeStudyKitStore(primary, fallback)

    archived = store.get_ready(*V01_IDENTITY)
    golden = store.get_ready("mit-6.7960-fall-2024", "fall-2024", "lecture-02")

    assert archived is not None and archived["title"] == "Lecture 1：深度学习导论"
    assert golden is not None and golden["review"]["human_review_status"] == "approved"
    missing_primary = CompositeStudyKitStore(
        ArchivedStudyKitStore(tmp_path / "missing.sqlite3"),
        fallback,
    )
    assert [item.unit_id for item in missing_primary.list_ready()] == [
        "lecture-02",
        "lecture-08",
    ]


async def test_six_learning_capabilities_accept_archive_portable_documents(
    tmp_path: Path,
) -> None:
    archive = _copy_approved_documents(tmp_path / "approved.sqlite3", V01_IDENTITY, V02_IDENTITY)
    store = CompositeStudyKitStore(ArchivedStudyKitStore(archive), ReviewedFileStudyKitStore())
    catalog = ReviewedCourseCatalogStore(store)
    learning = StudyKitLookupService(store, catalog=catalog)
    navigation = CourseNavigationService(catalog)
    context_v01 = CourseContext(
        course_id=V01_IDENTITY[0], course_version=V01_IDENTITY[1], unit_id=V01_IDENTITY[2]
    )
    context_v02 = CourseContext(
        course_id=V02_IDENTITY[0], course_version=V02_IDENTITY[1], unit_id=V02_IDENTITY[2]
    )

    navigation_answer = await navigation.navigate(
        text="查看 MIT 6.7960", profile=LearnerProfile()
    )
    lookup = await learning.lookup(messages=_messages("查看 StudyKit"), course_context=context_v01)
    material = await learning.material_question(
        messages=_messages("材料里的程序语言语义是什么？"), course_context=context_v02
    )
    concept = await learning.concept_explanation(
        messages=_messages("解释程序语言语义"), course_context=context_v02
    )
    practice = await learning.practice_selection(
        messages=_messages("给我一道概念练习"), course_context=context_v02
    )
    feedback = await learning.practice_feedback(
        messages=_messages("点评 P-01。我的答案是 syntax 描述程序形状，semantics 描述行为。"),
        course_context=context_v02,
    )

    assert "在线 StudyKit：可用（lecture-01、lecture-02、lecture-08）" in navigation_answer
    assert "ex-1" in lookup.answer
    assert "第 3 页" in material.answer
    assert "**定义**" in concept.answer and "第 3 页" in concept.answer
    assert "P-01" in practice.answer and "expected_evidence" not in practice.answer
    assert "本题反馈暂时降级" in feedback.answer and "第 3 页" in feedback.answer
    assert "expected_evidence" not in feedback.answer and "full_credit" not in feedback.answer


def test_page_reference_does_not_become_unit_for_archive_context(tmp_path: Path) -> None:
    archive = _copy_approved_documents(
        tmp_path / "approved.sqlite3", V02_IDENTITY, V02_SECOND_IDENTITY
    )
    store = ArchivedStudyKitStore(archive)

    context = store.match_context(["Cambridge semantics 的讲义第 3 页说了什么？"])

    assert context is not None
    assert context.course_id == V02_IDENTITY[0]
    assert context.unit_id is None


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _legacy_build(root: Path, build_id: str, course_id: str, unit_id: str) -> Path:
    build = root / build_id
    _write_json(build / "result.json", {"status": "succeeded", "build_id": build_id})
    _write_json(build / "run.json", {"quality_mode": "standard", "delivery_policy": "draft"})
    unit = build / "courses" / course_id / "units" / unit_id
    _write_json(
        unit / "05-studykit.json",
        {
            "course_id": course_id,
            "course_version": "fall-2026",
            "unit_id": unit_id,
            "title": "Test unit",
            "status": "draft",
        },
    )
    _write_json(unit / "validation.json", {"valid": True})
    _write_json(unit / "review-validation.json", {"status": "passed"})
    (unit / "studykit.md").write_text("# Test\n", encoding="utf-8")
    return build


def test_archive_round_trip_and_ready_boundary(tmp_path: Path) -> None:
    build_id = "a" * 64
    build = _legacy_build(tmp_path, build_id, "test-course-fall-2026", "lecture-01")
    database = tmp_path / "studykits.sqlite3"

    report = archive_builds(database, [(build, True)])
    archive = StudyKitArchive(database)

    assert report["build_count"] == 1
    assert report["document_count"] == 1
    assert archive.verify_integrity() == []
    assert archive.get_document(
        "test-course-fall-2026", "fall-2026", "lecture-01"
    ) is None
    document = archive.get_document(
        "test-course-fall-2026", "fall-2026", "lecture-01", ready_only=False
    )
    assert document is not None
    assert document["unit_id"] == "lecture-01"


def test_reimport_replaces_same_identity_and_prunes_unselected(tmp_path: Path) -> None:
    first = _legacy_build(tmp_path, "a" * 64, "course-a", "lecture-01")
    other = _legacy_build(tmp_path, "b" * 64, "course-b", "lecture-01")
    database = tmp_path / "studykits.sqlite3"
    archive_builds(database, [(first, True), (other, True)])

    replacement = _legacy_build(tmp_path, "c" * 64, "course-a", "lecture-02")
    archive_builds(database, [(replacement, True)])

    builds = StudyKitArchive(database).list_builds()
    assert [(item.build_id, item.course_id, item.unit_count) for item in builds] == [
        ("c" * 64, "course-a", 1)
    ]


def test_approved_import_requires_document_level_human_approval(tmp_path: Path) -> None:
    build = _legacy_build(tmp_path, "d" * 64, "course-a", "lecture-01")
    with pytest.raises(ValueError, match="human_review_status=approved"):
        archive_builds(
            tmp_path / "studykits.sqlite3",
            [(build, True)],
            review_status="approved",
        )
