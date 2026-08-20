"""Construction of the default online Agent runtime."""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.agent.model_support import load_optional_model
from app.agent.context_token import ContextTokenSigner
from app.agent.session_state import SQLiteSessionStateStore
from app.agent.orchestrator import CoursePilotAgent
from app.agent.planning import TaskPlanner
from app.agent.router import IntentRouter
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.knowledge import ReviewedCourseKnowledgeStore
from app.catalog.studykits import ReviewedFileStudyKitStore, build_default_studykit_store
from app.code_tutor.service import CodeTutorService
from app.course_navigation.service import CourseNavigationService
from app.learning.service import StudyKitLookupService
from app.general_assistance.service import GeneralAssistanceService
from app.retrieval.source_chunks import SQLiteSourceChunkStore
from app.profile.service import ProfileService, get_profile_service
from app.config import (
    API_KEY,
    CONVERSATION_TTL_DAYS,
    PRACTICE_REWRITE_ENABLED,
    ROBUST_INPUT_ENABLED,
)


@lru_cache(maxsize=8)
def _build_coursepilot_agent(profiles: ProfileService) -> CoursePilotAgent:
    model = load_optional_model()
    store = (
        ReviewedFileStudyKitStore()
        if os.getenv("COURSEPILOT_TEST_MODE", "").strip().lower() == "true"
        else build_default_studykit_store()
    )
    catalog = ReviewedCourseCatalogStore(store)
    course_knowledge = ReviewedCourseKnowledgeStore(catalog)
    if profiles.model is None:
        profiles.model = model
    return CoursePilotAgent(
        store=store,
        router=IntentRouter(store, model=model),
        profiles=profiles,
        code_tutor=CodeTutorService(store, model=model),
        course_navigation=CourseNavigationService(
            catalog, model=model, knowledge=course_knowledge
        ),
        studykit_learning=StudyKitLookupService(
            store,
            model=model,
            catalog=catalog,
            source_chunks=SQLiteSourceChunkStore(
                Path(__file__).resolve().parents[2]
                / "data"
                / "archive"
                / "source_chunks.sqlite3"
            ),
            practice_rewrite_enabled=PRACTICE_REWRITE_ENABLED,
        ),
        general_assistance=GeneralAssistanceService(
            model=model, course_knowledge=course_knowledge
        ),
        planner=TaskPlanner(model=model, robust_input_enabled=ROBUST_INPUT_ENABLED),
        context_signer=ContextTokenSigner(
            hashlib.sha256(f"coursepilot-context-v1:{API_KEY}".encode()).digest()
        ),
        session_state_store=SQLiteSessionStateStore(
            profiles.repository.database,
            key_secret=hashlib.sha256(
                f"coursepilot-conversation-store-v1:{API_KEY}".encode()
            ).digest(),
            ttl_days=CONVERSATION_TTL_DAYS,
        ),
    )


def get_coursepilot_agent(
    profiles: ProfileService = Depends(get_profile_service),
) -> CoursePilotAgent:
    """Build the online agent around the request's injectable profile service."""

    return _build_coursepilot_agent(profiles)
