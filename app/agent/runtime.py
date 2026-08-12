"""Construction of the default online Agent runtime."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.agent.model_support import load_optional_model
from app.agent.orchestrator import CoursePilotAgent
from app.agent.router import IntentRouter
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.code_tutor.service import CodeTutorService
from app.course_navigation.service import CourseNavigationService
from app.learning.service import StudyKitLookupService
from app.profile.service import ProfileService, get_profile_service


@lru_cache(maxsize=8)
def _build_coursepilot_agent(profiles: ProfileService) -> CoursePilotAgent:
    model = load_optional_model()
    store = ReviewedFileStudyKitStore()
    catalog = ReviewedCourseCatalogStore(store)
    if profiles.model is None:
        profiles.model = model
    return CoursePilotAgent(
        store=store,
        router=IntentRouter(store, model=model),
        profiles=profiles,
        code_tutor=CodeTutorService(store, model=model),
        course_navigation=CourseNavigationService(catalog),
        studykit_learning=StudyKitLookupService(store, model=model, catalog=catalog),
    )


def get_coursepilot_agent(
    profiles: ProfileService = Depends(get_profile_service),
) -> CoursePilotAgent:
    """Build the online agent around the request's injectable profile service."""

    return _build_coursepilot_agent(profiles)
