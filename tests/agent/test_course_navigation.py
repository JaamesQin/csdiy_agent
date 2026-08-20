from __future__ import annotations

from datetime import UTC, datetime
import json

from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.knowledge import ReviewedCourseKnowledgeStore
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.course_navigation.service import CourseNavigationService
from app.profile.contracts import FactStatus, LearnerProfile, ProfileFact
from tests.agent.helpers import FakeStructuredModel


def _service() -> CourseNavigationService:
    store = ReviewedFileStudyKitStore()
    return CourseNavigationService(ReviewedCourseCatalogStore(store))


async def test_navigation_asks_only_for_direction_when_recommendation_is_underspecified() -> None:
    answer = await _service().navigate(text="推荐一门课程", profile=LearnerProfile())

    assert "希望学习哪个方向" in answer
    assert "已有基础" not in answer
    assert "每周" not in answer


async def test_navigation_uses_only_confirmed_profile_direction() -> None:
    now = datetime.now(UTC)
    profile = LearnerProfile(
        facts=[
            ProfileFact(
                id="confirmed",
                field_name="learning_directions",
                value="systems",
                status=FactStatus.CONFIRMED,
                confidence=1,
                created_at=now,
            ),
            ProfileFact(
                id="inferred",
                field_name="learning_directions",
                value="ml_ai",
                status=FactStatus.INFERRED,
                confidence=0.7,
                created_at=now,
            ),
        ]
    )

    answer = await _service().navigate(text="推荐一门课程", profile=profile)

    assert "未个性化排序" in answer
    assert any(term in answer for term in ("Operating", "System", "操作系统", "CSAPP"))
    assert "在线 StudyKit" in answer


async def test_navigation_exact_match_exposes_only_trusted_links() -> None:
    answer = await _service().navigate(text="查看 MIT 6.7960", profile=LearnerProfile())

    assert "## 匹配到的课程" in answer
    assert "官方课程页" in answer
    assert "ocw.mit.edu" in answer
    assert "CSDIY 导航页" in answer
    assert "candidate_offerings" not in answer


async def test_navigation_list_is_capped_at_five() -> None:
    answer = await _service().navigate(text="有哪些课程", profile=LearnerProfile())

    assert "## 课程目录候选" in answer
    assert "6. **" not in answer


async def test_navigation_prefers_corrected_course_and_hides_internal_statuses() -> None:
    answer = await _service().navigate(
        text="不是 CS61A，我想了解 CS61C", profile=LearnerProfile()
    )

    assert "按你的纠正匹配到的课程" in answer
    assert "CS61C" in answer
    assert "CS61A" not in answer
    assert "independently_audited" not in answer
    assert "目录状态：已独立审核" in answer


def test_navigation_compacts_long_ready_unit_ranges() -> None:
    units = CourseNavigationService._compact_units(
        [f"lecture-{index:02d}" for index in range(1, 27)]
    )

    assert units == "共 26 讲：lecture-01–lecture-26"


async def test_navigation_accepts_a_validated_model_course_candidate() -> None:
    service = _service()
    card = service.resolve_card("CS61C")

    assert card is not None
    result = await service.navigate_result(
        text="cs6lc",
        profile=LearnerProfile(),
        candidate_id=card.catalog_id,
    )

    assert result.catalog_ids == (card.catalog_id,)
    assert "CS61C" in result.answer


async def test_personalized_navigation_uses_negative_background_and_all_courses() -> None:
    store = ReviewedFileStudyKitStore()
    catalog = ReviewedCourseCatalogStore(store)
    knowledge = ReviewedCourseKnowledgeStore(catalog)
    model = FakeStructuredModel(
        {
            "mode": "recommend",
            "overview": "你应先建立编程基础，再进入系统核心课程。",
            "now_catalog_ids": ["ucb-cs61a"],
            "later_catalog_ids": ["ucb-cs61c", "mit-6-s081"],
            "ran_code": False,
        }
    )
    service = CourseNavigationService(catalog, model=model, knowledge=knowledge)
    now = datetime.now(UTC)
    profile = LearnerProfile(
        facts=[
            ProfileFact(
                id="direction",
                field_name="learning_directions",
                value="systems",
                status=FactStatus.CONFIRMED,
                confidence=1,
                created_at=now,
            ),
            ProfileFact(
                id="background",
                field_name="background",
                value="没有Python",
                status=FactStatus.CONFIRMED,
                confidence=1,
                created_at=now,
            ),
        ]
    )

    result = await service.navigate_result(text="给我推荐课程", profile=profile)

    prompt = json.loads(model.calls[0]["user_prompt"])
    assert prompt["confirmed_profile"]["background"] == ["没有Python"]
    assert len(prompt["course_index"]["courses"]) == 119
    assert model.calls[0]["thinking_enabled"] is False
    assert model.calls[0]["max_tokens"] == 4096
    assert "## 现在开始" in result.answer
    assert "CS61A" in result.answer
    assert "## 长期目标" in result.answer
    assert "CS61C" in result.answer
    assert "6.S081" in result.answer
    assert "未记录精确先修要求" in result.answer


async def test_invalid_personalized_id_falls_back_without_claiming_personalization() -> None:
    store = ReviewedFileStudyKitStore()
    catalog = ReviewedCourseCatalogStore(store)
    model = FakeStructuredModel(
        {
            "mode": "recommend",
            "overview": "错误结果",
            "now_catalog_ids": ["invented-course"],
            "later_catalog_ids": [],
            "ran_code": False,
        }
    )
    service = CourseNavigationService(
        catalog,
        model=model,
        knowledge=ReviewedCourseKnowledgeStore(catalog),
    )

    answer = await service.navigate(text="推荐系统课程", profile=LearnerProfile())

    assert "未个性化排序" in answer
    assert "invented-course" not in answer
