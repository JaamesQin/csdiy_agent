from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from app.profile.contracts import FactStatus, LearnerProfile
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService
from tests.agent.helpers import FakeStructuredModel


async def test_explicit_profile_facts_persist_and_are_isolated(tmp_path) -> None:
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    service = ProfileService(repository)

    result = await service.observe(
        user_id="user-a",
        text="我想学系统方向，每周 6 小时，而且有 Python 基础，但没有 Java 基础。",
        current=LearnerProfile(user_id="user-a", persisted=True),
    )

    assert {fact.field_name for fact in result.profile.facts} == {
        "learning_directions",
        "weekly_minutes",
        "background",
    }
    assert result.profile.confirmed("weekly_minutes")[0].value == 360
    assert [fact.value for fact in result.profile.confirmed("background")] == ["Python"]
    assert repository.get_profile("user-b").facts == []

    systematic = await service.observe(
        user_id="user-c",
        text="我想系统学习深度学习，重点是理解训练和 Transformer，讲解时先给例子。",
        current=LearnerProfile(user_id="user-c", persisted=True),
    )
    assert [
        fact.value for fact in systematic.profile.confirmed("learning_directions")
    ] == ["ml_ai"]
    assert systematic.profile.confirmed("preferred_explanation_style")[0].value == "example_first"

    model = FakeStructuredModel(
        {
            "candidates": [
                {
                    "field_name": "learning_directions",
                    "value": "深度学习",
                    "status": "confirmed",
                    "confidence": 0.95,
                    "evidence_quote": "我想系统学习深度学习",
                    "course_id": None,
                    "course_version": None,
                    "unit_id": None,
                },
                {
                    "field_name": "background",
                    "value": ["Python基础", "线性代数基础"],
                    "status": "confirmed",
                    "confidence": 0.95,
                    "evidence_quote": "我有 Python 和线性代数基础",
                    "course_id": None,
                    "course_version": None,
                    "unit_id": None,
                },
                {
                    "field_name": "preferred_explanation_style",
                    "value": "先给例子再解释概念",
                    "status": "confirmed",
                    "confidence": 0.95,
                    "evidence_quote": "先给例子再解释概念",
                    "course_id": None,
                    "course_version": None,
                    "unit_id": None,
                },
            ]
        }
    )
    normalized_service = ProfileService(
        SQLiteProfileRepository(tmp_path / "normalized.sqlite3"), model=model
    )
    normalized = await normalized_service.observe(
        user_id="user-d",
        text=(
            "我想系统学习深度学习。我有 Python 和线性代数基础，"
            "讲解时先给例子再解释概念。"
        ),
        current=LearnerProfile(user_id="user-d", persisted=True),
    )
    assert [
        fact.value for fact in normalized.profile.confirmed("learning_directions")
    ] == ["ml_ai"]
    assert [fact.value for fact in normalized.profile.confirmed("background")] == [
        "Python",
        "线性代数",
    ]
    assert [
        fact.value
        for fact in normalized.profile.confirmed("preferred_explanation_style")
    ] == ["example_first"]


async def test_no_user_keeps_profile_transient(tmp_path) -> None:
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    service = ProfileService(repository)

    result = await service.observe(
        user_id=None,
        text="我想学算法方向，每周 90 分钟。",
        current=LearnerProfile(),
    )

    assert result.profile.persisted is False
    assert result.profile.confirmed("weekly_minutes")[0].value == 90
    assert not (tmp_path / "profiles.sqlite3").exists()


async def test_model_inference_requires_confirmation_and_expires(tmp_path) -> None:
    model = FakeStructuredModel(
        {
            "candidates": [
                {
                    "field_name": "learning_directions",
                    "value": "ml_ai",
                    "status": "inferred",
                    "confidence": 0.91,
                    "evidence_quote": None,
                    "course_id": None,
                    "course_version": None,
                    "unit_id": None,
                }
            ]
        }
    )
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    service = ProfileService(repository, model=model)

    result = await service.observe(
        user_id="user-a",
        text="我在考虑机器学习，但还不确定方向。",
        current=LearnerProfile(user_id="user-a", persisted=True),
    )

    inferred = result.profile.inferred()
    assert inferred
    assert inferred[-1].confidence == 0.79
    assert inferred[-1].expires_at is not None
    assert service.handle_management(
        user_id="user-a",
        text="确认记录这些画像",
        profile=result.profile,
    )[1].inferred() == []

    repository.add_fact(
        user_id="user-a",
        field_name="goals",
        value="expired",
        status=FactStatus.INFERRED,
        confidence=0.5,
        evidence_excerpt=None,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert all(fact.value != "expired" for fact in repository.get_profile("user-a").facts)


async def test_correction_and_deletion_are_real_database_changes(tmp_path) -> None:
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    service = ProfileService(repository)
    current = LearnerProfile(user_id="user-a", persisted=True)
    first = await service.observe(
        user_id="user-a", text="我想学系统方向，我每周 2 小时。", current=current
    )
    second = await service.observe(
        user_id="user-a", text="把每周时间改为 5 小时。", current=first.profile
    )

    assert [fact.value for fact in second.profile.confirmed("weekly_minutes")] == [300]
    corrected_direction = await service.observe(
        user_id="user-a",
        text="学习方向不是系统，改为算法。",
        current=second.profile,
    )
    assert [
        fact.value
        for fact in corrected_direction.profile.confirmed("learning_directions")
    ] == ["algorithms"]
    answer, deleted = service.handle_management(
        user_id="user-a",
        text="删除我的学习时间",
        profile=corrected_direction.profile,
    )
    assert "已删除" in answer
    assert deleted.confirmed("weekly_minutes") == []
    service.handle_management(
        user_id="user-a", text="删除我的画像", profile=deleted
    )
    assert repository.get_profile("user-a").facts == []


async def test_profile_evidence_never_contains_fenced_code(tmp_path) -> None:
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    service = ProfileService(repository)

    result = await service.observe(
        user_id="user-a",
        text="我有 Python 基础。\n```python\nsecret = 'do-not-store'\n```",
        current=LearnerProfile(user_id="user-a", persisted=True),
    )

    assert result.added
    assert all("do-not-store" not in (fact.evidence_excerpt or "") for fact in result.added)


async def test_model_cannot_mark_unquoted_claim_as_confirmed(tmp_path) -> None:
    model = FakeStructuredModel(
        {
            "candidates": [
                {
                    "field_name": "background",
                    "value": "Rust",
                    "status": "confirmed",
                    "confidence": 0.99,
                    "evidence_quote": "我熟悉 Rust",
                    "course_id": None,
                    "course_version": None,
                    "unit_id": None,
                }
            ]
        }
    )
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    service = ProfileService(repository, model=model)

    result = await service.observe(
        user_id="user-a",
        text="我想学习系统方向，但还没决定语言。",
        current=LearnerProfile(user_id="user-a", persisted=True),
    )

    rust = next(fact for fact in result.profile.facts if fact.value == "Rust")
    assert rust.status is FactStatus.INFERRED
    assert rust.confidence == 0.7


async def test_declined_field_is_removed_and_not_reobserved(tmp_path) -> None:
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    service = ProfileService(repository)
    first = await service.observe(
        user_id="user-a",
        text="我每周 3 小时。",
        current=LearnerProfile(user_id="user-a", persisted=True),
    )
    _, declined = service.handle_management(
        user_id="user-a",
        text="不要记录我的学习时间",
        profile=first.profile,
    )
    second = await service.observe(
        user_id="user-a",
        text="我每周 5 小时。",
        current=declined,
    )

    assert second.profile.confirmed("weekly_minutes") == []
    assert any(fact.status is FactStatus.DECLINED for fact in second.profile.facts)


def test_profile_repository_serializes_concurrent_writes(tmp_path) -> None:
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")

    def write(index: int) -> None:
        repository.add_fact(
            user_id="concurrent-user",
            field_name="goals",
            value=f"goal-{index}",
            status=FactStatus.CONFIRMED,
            confidence=1.0,
            evidence_excerpt=f"goal-{index}",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write, range(20)))

    assert len(repository.get_profile("concurrent-user").facts) == 20


def test_expired_inferred_fact_cannot_be_confirmed(tmp_path) -> None:
    repository = SQLiteProfileRepository(tmp_path / "profiles.sqlite3")
    repository.add_fact(
        user_id="user-a",
        field_name="goals",
        value="expired goal",
        status=FactStatus.INFERRED,
        confidence=0.6,
        evidence_excerpt="maybe",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    assert repository.confirm_inferred("user-a") == 0
    assert repository.get_profile("user-a").facts == []


async def test_profile_uses_one_model_call_and_reports_usage(tmp_path) -> None:
    extractor = FakeStructuredModel(
        {
            "candidates": [
                {
                    "field_name": "background",
                    "value": "Rust",
                    "status": "confirmed",
                    "confidence": 0.95,
                    "evidence_quote": "我熟悉 Rust",
                    "course_id": None,
                    "course_version": None,
                    "unit_id": None,
                }
            ]
        }
    )
    service = ProfileService(
        SQLiteProfileRepository(tmp_path / "profiles.sqlite3"),
        model=extractor,
    )

    result = await service.observe(
        user_id=None,
        text="我熟悉 Rust，并有项目经验。",
        current=LearnerProfile(),
    )

    assert result.usage["total_tokens"] == 15
    assert len(extractor.calls) == 1
