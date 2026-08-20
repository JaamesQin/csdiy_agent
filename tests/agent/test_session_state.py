from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.agent.context_token import ConversationState
from app.agent.contracts import StudyKitCourseIdentity
from app.agent.session_state import SQLiteSessionStateStore
from app.storage.database import SQLiteDatabase


def _state(unit: str = "lecture-02") -> ConversationState:
    return ConversationState(
        course=StudyKitCourseIdentity(
            course_id="mit-6.7960-fall-2024",
            course_version="fall-2024",
            unit_id=unit,
        ),
        displayed_practice_ids=["ex-1"],
        last_concept="梯度下降",
    )


def test_session_state_round_trips_without_raw_identifiers(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "coursepilot.sqlite3")
    store = SQLiteSessionStateStore(database, key_secret=b"s" * 32)

    assert store.save(
        "legacy:gateway-user", "clear-session-id", _state(), expected_revision=None
    )
    loaded = store.load("legacy:gateway-user", "clear-session-id")

    assert loaded is not None
    assert loaded.revision == 1
    assert loaded.state.course is not None
    assert loaded.state.course.unit_id == "lecture-02"
    raw = database.path.read_bytes()
    assert b"clear-session-id" not in raw
    assert b"legacy:gateway-user" not in raw


def test_session_state_isolated_and_compare_and_swap_protected(tmp_path) -> None:
    store = SQLiteSessionStateStore(
        SQLiteDatabase(tmp_path / "coursepilot.sqlite3"), key_secret=b"s" * 32
    )
    assert store.save("legacy:a", "same", _state(), expected_revision=None)
    assert store.load("legacy:b", "same") is None
    assert store.load("legacy:a", "different") is None

    assert store.save(
        "legacy:a", "same", _state("lecture-08"), expected_revision=1
    )
    assert not store.save(
        "legacy:a", "same", _state("lecture-03"), expected_revision=1
    )
    loaded = store.load("legacy:a", "same")
    assert loaded is not None
    assert loaded.revision == 2
    assert loaded.state.course is not None
    assert loaded.state.course.unit_id == "lecture-08"


def test_session_state_has_thirty_day_sliding_expiry(tmp_path) -> None:
    current = [datetime(2026, 8, 20, tzinfo=UTC)]
    store = SQLiteSessionStateStore(
        SQLiteDatabase(tmp_path / "coursepilot.sqlite3"),
        key_secret=b"s" * 32,
        ttl_days=30,
        clock=lambda: current[0],
    )
    assert store.save("legacy:a", "session", _state(), expected_revision=None)
    current[0] += timedelta(days=29)
    loaded = store.load("legacy:a", "session")
    assert loaded is not None
    assert store.save(
        "legacy:a",
        "session",
        loaded.state,
        expected_revision=loaded.revision,
    )
    current[0] += timedelta(days=29)
    assert store.load("legacy:a", "session") is not None
    current[0] += timedelta(days=2)
    assert store.load("legacy:a", "session") is None
