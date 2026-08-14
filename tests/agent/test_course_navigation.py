from __future__ import annotations

from datetime import UTC, datetime

from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.course_navigation.service import CourseNavigationService
from app.profile.contracts import FactStatus, LearnerProfile, ProfileFact


def _service() -> CourseNavigationService:
    store = ReviewedFileStudyKitStore()
    return CourseNavigationService(ReviewedCourseCatalogStore(store))


def test_navigation_asks_only_for_direction_when_recommendation_is_underspecified() -> None:
    answer = _service().navigate(text="推荐一门课程", profile=LearnerProfile())

    assert "希望学习哪个方向" in answer
    assert "已有基础" not in answer
    assert "每周" not in answer


def test_navigation_uses_only_confirmed_profile_direction() -> None:
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

    answer = _service().navigate(text="推荐一门课程", profile=profile)

    assert "## 课程推荐" in answer
    assert any(term in answer for term in ("Operating", "System", "操作系统", "CSAPP"))
    assert "在线 StudyKit" in answer


def test_navigation_exact_match_exposes_only_trusted_links() -> None:
    answer = _service().navigate(text="查看 MIT 6.7960", profile=LearnerProfile())

    assert "## 匹配到的课程" in answer
    assert "官方课程页" in answer
    assert "ocw.mit.edu" in answer
    assert "CSDIY 导航页" in answer
    assert "candidate_offerings" not in answer


def test_navigation_list_is_capped_at_five() -> None:
    answer = _service().navigate(text="有哪些课程", profile=LearnerProfile())

    assert "## 课程目录候选" in answer
    assert "6. **" not in answer
