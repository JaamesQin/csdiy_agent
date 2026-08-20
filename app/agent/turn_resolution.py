"""Resolve untrusted semantic candidates into validated per-turn course context."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agent.context_token import ConversationState
from app.agent.contracts import CourseContext, ModelTurnUnderstanding
from app.catalog.contracts import CourseCard
from app.catalog.studykits import StudyKitStore
from app.course_navigation.service import CourseNavigationService


@dataclass(frozen=True, slots=True)
class ResolvedTurnContext:
    course_card: CourseCard | None
    selected_catalog_id: str | None
    studykit_context: CourseContext | None
    profile_course_context: CourseContext | None


class TurnResolver:
    """Apply explicit-evidence and monotonic-specificity rules once for all capabilities."""

    def __init__(
        self,
        store: StudyKitStore,
        course_navigation: CourseNavigationService,
    ) -> None:
        self.store = store
        self.course_navigation = course_navigation

    def resolve(
        self,
        *,
        latest: str,
        understanding: ModelTurnUnderstanding | None,
        previous_state: ConversationState | None,
        displayed_catalog_ids: list[str],
        selected_catalog_id: str | None,
        profile_course_context: CourseContext | None,
    ) -> ResolvedTurnContext:
        resolved_card: CourseCard | None = None
        if (
            understanding is not None
            and understanding.course is not None
            and understanding.course_mode != "recommendation"
        ):
            reference = understanding.course
            referenced_id: str | None = None
            if reference.ordinal is not None:
                index = reference.ordinal - 1
                if 0 <= index < len(displayed_catalog_ids):
                    referenced_id = displayed_catalog_ids[index]
            elif (
                understanding.course_mode == "selection"
                and displayed_catalog_ids
                and not reference.candidate_id
                and not reference.raw
            ):
                referenced_id = displayed_catalog_ids[0]
            resolved_card = self.course_navigation.resolve_card(
                referenced_id,
                reference.candidate_id,
                reference.raw,
            )
            if resolved_card is not None:
                selected_catalog_id = resolved_card.catalog_id
        if (
            resolved_card is None
            and selected_catalog_id
            and understanding is not None
            and understanding.unit is not None
        ):
            resolved_card = self.course_navigation.get_card(selected_catalog_id)

        studykit_context: CourseContext | None = None
        resolved_profile_context: CourseContext | None = None
        if (
            resolved_card is not None
            and resolved_card.manifest_course_id
            and resolved_card.course_version
        ):
            unit_id: str | None = None
            if understanding is not None and understanding.unit is not None:
                unit_ref = understanding.unit
                unit_id = unit_ref.candidate_id
                if unit_id is None and unit_ref.ordinal is not None:
                    ready_units = self.store.list_ready(
                        course_id=resolved_card.manifest_course_id,
                        course_version=resolved_card.course_version,
                    )
                    index = unit_ref.ordinal - 1
                    unit_id = (
                        ready_units[index].unit_id
                        if 0 <= index < len(ready_units)
                        else f"lecture-{unit_ref.ordinal:02d}"
                    )
            previous_course = previous_state.course if previous_state else None
            same_verified_course = bool(
                previous_course is not None
                and previous_course.course_id == resolved_card.manifest_course_id
                and previous_course.course_version == resolved_card.course_version
            )
            if (
                unit_id is None
                and same_verified_course
                and not requests_unit_listing(latest)
                and not has_explicit_unit_reference(latest)
            ):
                unit_id = previous_course.unit_id
            studykit_context = CourseContext(
                course_id=resolved_card.manifest_course_id,
                course_version=resolved_card.course_version,
                unit_id=unit_id,
                title=resolved_card.title,
            )
            resolved_profile_context = self.store.resolve_context(
                course_id=resolved_card.manifest_course_id,
                course_version=resolved_card.course_version,
                unit_id=unit_id,
            )
            if resolved_profile_context is None and unit_id is not None:
                resolved_profile_context = self.store.resolve_context(
                    course_id=resolved_card.manifest_course_id,
                    course_version=resolved_card.course_version,
                    unit_id=None,
                )
        if studykit_context is None and understanding is not None:
            candidates = [
                value
                for value in (
                    understanding.course.candidate_id if understanding.course else None,
                    understanding.course.raw if understanding.course else None,
                    understanding.unit.candidate_id if understanding.unit else None,
                    understanding.unit.raw if understanding.unit else None,
                )
                if value
            ]
            if candidates:
                studykit_context = self.store.match_context(candidates)
        if studykit_context is None and previous_state is not None and previous_state.course:
            inherited_unit = previous_state.course.unit_id
            if understanding is not None and understanding.unit is not None:
                inherited_unit = understanding.unit.candidate_id
                if inherited_unit is None and understanding.unit.ordinal is not None:
                    inherited_unit = f"lecture-{understanding.unit.ordinal:02d}"
            studykit_context = self.store.resolve_context(
                course_id=previous_state.course.course_id,
                course_version=previous_state.course.course_version,
                unit_id=inherited_unit,
            )
        if studykit_context is None:
            studykit_context = self.store.match_context([latest]) or profile_course_context
        if resolved_profile_context is None and studykit_context is not None:
            resolved_profile_context = self.store.resolve_context(
                course_id=studykit_context.course_id,
                course_version=studykit_context.course_version,
                unit_id=studykit_context.unit_id,
            )
        return ResolvedTurnContext(
            course_card=resolved_card,
            selected_catalog_id=selected_catalog_id,
            studykit_context=studykit_context,
            profile_course_context=resolved_profile_context,
        )


def requests_unit_listing(text: str) -> bool:
    return bool(
        re.search(
            r"(?:列出|显示|查看|浏览|有哪些|所有|全部|可用).{0,10}(?:讲次|讲|lectures?)"
            r"|(?:讲次|lectures?).{0,10}(?:列表|有哪些|所有|全部|可用)",
            text,
            re.IGNORECASE,
        )
    )


def has_explicit_unit_reference(text: str) -> bool:
    return bool(
        re.search(
            r"(?:lecture\s*[- ]?0?[0-9]{1,3}"
            r"|第\s*[零〇一二两三四五六七八九十百千0-9]{1,8}\s*讲)",
            text,
            re.IGNORECASE,
        )
    )
