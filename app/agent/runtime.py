"""Construction of the default online Agent runtime."""

from __future__ import annotations

from functools import lru_cache

from app.agent.model_support import load_optional_model
from app.agent.orchestrator import CoursePilotAgent
from app.agent.router import IntentRouter
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.code_tutor.service import CodeTutorService
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService


@lru_cache(maxsize=1)
def get_coursepilot_agent() -> CoursePilotAgent:
    model = load_optional_model()
    store = ReviewedFileStudyKitStore()
    profiles = ProfileService(SQLiteProfileRepository(), model=model)
    return CoursePilotAgent(
        store=store,
        router=IntentRouter(store, model=model),
        profiles=profiles,
        code_tutor=CodeTutorService(store, model=model),
    )
