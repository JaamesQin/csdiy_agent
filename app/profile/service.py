"""Active, evidence-aware learner profile observation and management."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Iterable

from pydantic import ValidationError

from app.agent.contracts import CourseContext, ProfileOperation
from app.agent.model_support import normalized_usage
from app.generation.model import ModelError, StructuredModel
from app.profile.contracts import (
    FactStatus,
    LearnerProfile,
    ObservationResult,
    ProfileCandidate,
    ProfileFact,
    ProfileFieldName,
    ProfileObservation,
)
from app.profile.repository import SQLiteProfileRepository
from app.storage.database import get_database

INFERENCE_TTL_DAYS = 7
PROFILE_SIGNAL = re.compile(
    r"每周|每星期|小时|分钟|想学|准备学|学习方向|目标|基础|学过|熟悉|掌握|"
    r"偏好|喜欢.*讲|先讲例子|系统方向|机器学习|深度学习|算法|安全|前端|后端",
    re.IGNORECASE,
)


class ProfileAction(str, Enum):
    NONE = "none"
    VIEW = "view"
    CONFIRM = "confirm"
    DELETE_ALL = "delete_all"
    DELETE_FIELD = "delete_field"
    DECLINE_FIELD = "decline_field"


class ProfileService:
    def __init__(
        self,
        repository: SQLiteProfileRepository,
        model: StructuredModel | None = None,
    ) -> None:
        self.repository = repository
        self.model = model

    def load(self, user_id: str | None) -> LearnerProfile:
        if not user_id:
            return LearnerProfile(user_id=None, persisted=False)
        return self.repository.get_profile(user_id)

    def transient_from_messages(self, messages: Iterable[str]) -> LearnerProfile:
        facts: list[ProfileFact] = []
        for message in messages:
            for candidate in self._deterministic_candidates(self._prose_only(message)):
                if candidate.status is FactStatus.CONFIRMED:
                    facts = self._merge_transient(facts, self._candidate_to_fact(candidate, None))
        return LearnerProfile(user_id=None, facts=facts, persisted=False)

    def management_action(
        self, text: str
    ) -> tuple[ProfileAction, ProfileFieldName | None]:
        lowered = text.lower()
        profile_word = any(word in lowered for word in ("画像", "记住", "记录", "了解我"))
        if any(word in lowered for word in ("删除", "清空", "忘记")):
            field = self._field_from_text(lowered)
            if field is not None:
                return ProfileAction.DELETE_FIELD, field
            if profile_word or "所有" in lowered or "全部" in lowered:
                return ProfileAction.DELETE_ALL, None
        if any(word in lowered for word in ("不要记录", "别记录", "不想保存")):
            return ProfileAction.DECLINE_FIELD, self._field_from_text(lowered)
        if any(word in lowered for word in ("确认记录", "确认这些", "是的，记录", "可以记录")):
            return ProfileAction.CONFIRM, None
        if profile_word and any(word in lowered for word in ("查看", "显示", "是什么", "知道", "记得")):
            return ProfileAction.VIEW, None
        if lowered.strip() in {"我的画像", "查看画像", "学习画像"}:
            return ProfileAction.VIEW, None
        return ProfileAction.NONE, None

    def handle_management(
        self,
        *,
        user_id: str | None,
        text: str,
        profile: LearnerProfile,
    ) -> tuple[str, LearnerProfile]:
        action, field = self.management_action(text)
        if action is ProfileAction.VIEW or action is ProfileAction.NONE:
            return self.render(profile), profile
        if not user_id:
            return "当前请求没有 `user` 标识，因此没有持久画像可修改。", profile
        if action is ProfileAction.CONFIRM:
            count = self.repository.confirm_inferred(user_id)
            updated = self.repository.get_profile(user_id)
            return f"已确认 {count} 条画像候选。\n\n{self.render(updated)}", updated
        if action is ProfileAction.DELETE_ALL:
            count = self.repository.delete_all(user_id)
            updated = self.repository.get_profile(user_id)
            return f"已删除全部画像数据（{count} 条）。", updated
        if field is None:
            return "请说明要删除或拒绝记录的画像字段。", profile
        count = self.repository.delete_field(user_id, field)
        if action is ProfileAction.DECLINE_FIELD:
            self.repository.add_fact(
                user_id=user_id,
                field_name=field,
                value=None,
                status=FactStatus.DECLINED,
                confidence=1.0,
                evidence_excerpt=self._prose_only(text)[:200],
                replace=True,
            )
            updated = self.repository.get_profile(user_id)
            return f"已删除并标记不再主动记录“{self._label(field)}”（原有 {count} 条）。", updated
        updated = self.repository.get_profile(user_id)
        return f"已删除“{self._label(field)}”相关画像（{count} 条）。", updated

    async def observe(
        self,
        *,
        user_id: str | None,
        text: str,
        current: LearnerProfile,
        course_context: CourseContext | None = None,
    ) -> ObservationResult:
        prose = self._prose_only(text)
        candidates = self._deterministic_candidates(prose)
        usage = normalized_usage()

        if course_context is not None and self._mentions_course(text):
            candidates.extend(
                [
                    ProfileCandidate(
                        field_name="active_course",
                        value=course_context.course_id,
                        status=FactStatus.CONFIRMED,
                        confidence=1.0,
                        evidence_quote=prose[:200],
                        course_id=course_context.course_id,
                        course_version=course_context.course_version,
                    )
                ]
            )
            if course_context.unit_id:
                candidates.append(
                    ProfileCandidate(
                        field_name="active_unit",
                        value=course_context.unit_id,
                        status=FactStatus.CONFIRMED,
                        confidence=1.0,
                        evidence_quote=prose[:200],
                        course_id=course_context.course_id,
                        course_version=course_context.course_version,
                        unit_id=course_context.unit_id,
                    )
                )

        if prose and PROFILE_SIGNAL.search(prose) and self.model is not None:
            try:
                response = await self.model.generate_json(
                    system_prompt=(
                        "你是 CoursePilot 画像观察器。只抽取课程学习相关信息。"
                        "明确事实必须逐字提供 evidence_quote；不能从代码推断能力。"
                        "不确定推断使用 inferred。只输出 JSON object。"
                    ),
                    user_prompt=json.dumps(
                        {
                            "allowed_fields": [
                                "learning_directions",
                                "goals",
                                "background",
                                "weekly_minutes",
                                "preferred_explanation_style",
                                "active_course",
                                "active_unit",
                            ],
                            "statuses": ["confirmed", "inferred", "declined"],
                            "text": prose[:4000],
                            "output_contract": {
                                "candidates": [
                                    {
                                        "field_name": "one allowed field",
                                        "value": "string, integer, or list",
                                        "status": "confirmed, inferred, or declined",
                                        "confidence": 0.0,
                                        "evidence_quote": "exact substring or null",
                                        "course_id": None,
                                        "course_version": None,
                                        "unit_id": None,
                                    }
                                ]
                            },
                        },
                        ensure_ascii=False,
                    ),
                    thinking_enabled=False,
                    max_tokens=2048,
                    timeout_seconds=30,
                )
                observation = ProfileObservation.model_validate(response.output)
                candidates.extend(observation.candidates)
                usage = normalized_usage(response.usage)
            except (ModelError, ValidationError, ValueError):
                pass

        candidates = self._normalize_candidates(candidates, prose, current)
        added: list[ProfileFact] = []
        persistence_error = False
        if user_id:
            try:
                for candidate in candidates:
                    expires_at = (
                        datetime.now(UTC) + timedelta(days=INFERENCE_TTL_DAYS)
                        if candidate.status is FactStatus.INFERRED
                        else None
                    )
                    replace = candidate.field_name in {
                        "weekly_minutes",
                        "preferred_explanation_style",
                        "active_course",
                        "active_unit",
                    }
                    if candidate.field_name == "learning_directions" and "不是" in prose:
                        replace = True
                    added.append(
                        self.repository.add_fact(
                            user_id=user_id,
                            field_name=candidate.field_name,
                            value=candidate.value,
                            status=candidate.status,
                            confidence=candidate.confidence,
                            evidence_excerpt=candidate.evidence_quote,
                            course_id=candidate.course_id,
                            course_version=candidate.course_version,
                            unit_id=candidate.unit_id,
                            expires_at=expires_at,
                            replace=replace,
                        )
                    )
                profile = self.repository.get_profile(user_id)
            except (OSError, sqlite3.Error, RuntimeError):
                persistence_error = True
                profile = current.model_copy(deep=True)
                for candidate in candidates:
                    fact = self._candidate_to_fact(candidate, None)
                    profile.facts = self._merge_transient(profile.facts, fact)
                    added.append(fact)
                profile.persisted = False
        else:
            profile = current.model_copy(deep=True)
            for candidate in candidates:
                fact = self._candidate_to_fact(candidate, None)
                profile.facts = self._merge_transient(profile.facts, fact)
                added.append(fact)

        return ObservationResult(
            profile=profile,
            added=added,
            notice=self._notice(added, persisted=bool(user_id) and not persistence_error),
            usage=usage,
            persistence_error=persistence_error,
        )

    def apply_operations(
        self,
        *,
        user_id: str | None,
        text: str,
        current: LearnerProfile,
        operations: list[ProfileOperation],
        course_context: CourseContext | None = None,
    ) -> ObservationResult:
        """Apply model-understood profile mutations after local grounding checks."""

        profile = current.model_copy(deep=True)
        added: list[ProfileFact] = []
        notices: list[str] = []
        persistence_error = False
        for operation in operations:
            quote = (operation.evidence_quote or "").strip()
            if not quote or quote not in text:
                continue
            field = operation.field_name
            if operation.action == "delete":
                if user_id:
                    try:
                        count = self.repository.delete_field(user_id, field)
                        profile = self.repository.get_profile(user_id)
                    except (OSError, sqlite3.Error, RuntimeError):
                        persistence_error = True
                        count = 0
                else:
                    before = len(profile.facts)
                    profile.facts = [fact for fact in profile.facts if fact.field_name != field]
                    count = before - len(profile.facts)
                notices.append(f"已删除{self._label(field)}（{count} 条）")
                continue

            value = operation.value
            candidate_course = course_context
            if field in {"active_course", "active_unit"}:
                if candidate_course is None:
                    continue
                value = (
                    candidate_course.course_id
                    if field == "active_course"
                    else candidate_course.unit_id
                )
                if value is None:
                    continue
            candidate = ProfileCandidate(
                field_name=field,
                value=value,
                status=(
                    FactStatus.INFERRED
                    if operation.action == "infer"
                    else FactStatus.CONFIRMED
                ),
                confidence=0.7 if operation.action == "infer" else 1.0,
                evidence_quote=quote,
                course_id=candidate_course.course_id if candidate_course else None,
                course_version=candidate_course.course_version if candidate_course else None,
                unit_id=(
                    candidate_course.unit_id
                    if candidate_course and field == "active_unit"
                    else None
                ),
            )
            normalized = self._normalize_candidates([candidate], text, profile)
            if not normalized:
                continue
            candidate = normalized[0]
            replace = operation.action == "replace" or field in {
                "weekly_minutes",
                "preferred_explanation_style",
                "active_course",
                "active_unit",
            }
            if user_id:
                try:
                    fact = self.repository.add_fact(
                        user_id=user_id,
                        field_name=candidate.field_name,
                        value=candidate.value,
                        status=candidate.status,
                        confidence=candidate.confidence,
                        evidence_excerpt=candidate.evidence_quote,
                        course_id=candidate.course_id,
                        course_version=candidate.course_version,
                        unit_id=candidate.unit_id,
                        expires_at=(
                            datetime.now(UTC) + timedelta(days=INFERENCE_TTL_DAYS)
                            if candidate.status is FactStatus.INFERRED
                            else None
                        ),
                        replace=replace,
                    )
                    profile = self.repository.get_profile(user_id)
                except (OSError, sqlite3.Error, RuntimeError):
                    persistence_error = True
                    fact = self._candidate_to_fact(candidate, None)
                    profile.facts = self._merge_transient(profile.facts, fact)
            else:
                fact = self._candidate_to_fact(candidate, None)
                if replace:
                    profile.facts = [
                        item for item in profile.facts if item.field_name != field
                    ]
                profile.facts = self._merge_transient(profile.facts, fact)
            added.append(fact)

        if user_id and not persistence_error:
            profile = self.repository.get_profile(user_id)
        notice = self._notice(added, persisted=bool(user_id) and not persistence_error)
        if notices:
            suffix = "；".join(notices) + "。"
            notice = f"{notice}；{suffix}" if notice else suffix
        return ObservationResult(
            profile=profile,
            added=added,
            notice=notice,
            usage=normalized_usage(),
            persistence_error=persistence_error,
        )

    def render(self, profile: LearnerProfile) -> str:
        confirmed = [fact for fact in profile.facts if fact.status is FactStatus.CONFIRMED]
        inferred = profile.inferred()
        if not confirmed and not inferred:
            persistence = "提供 `user` 标识后可以跨会话保存。" if not profile.persisted else ""
            return (
                "当前没有足够的学习画像。请告诉我你想学习的 CS 方向、已有基础，"
                f"以及每周可投入的时间。{persistence}"
            )
        lines = ["### 当前学习画像"]
        grouped: dict[str, list[ProfileFact]] = {}
        for fact in confirmed:
            grouped.setdefault(fact.field_name, []).append(fact)
        for field_name, facts in grouped.items():
            values = "、".join(
                self._display_value(fact.value, fact.field_name) for fact in facts
            )
            latest = max(facts, key=lambda fact: fact.created_at)
            evidence = next(
                (fact.evidence_excerpt for fact in reversed(facts) if fact.evidence_excerpt),
                None,
            )
            metadata = (
                f"状态 confirmed，置信度 {latest.confidence:.2f}，"
                f"更新于 {latest.created_at.date().isoformat()}"
            )
            if evidence:
                metadata += f"，依据：{evidence}"
            suffix = f"（{metadata}）"
            lines.append(f"- {self._label(field_name)}：{values}{suffix}")
        if inferred:
            lines.append("\n待你确认的候选：")
            for fact in inferred:
                lines.append(
                    f"- {self._label(fact.field_name)}：{self._display_value(fact.value, fact.field_name)}"
                    f"（状态 inferred，置信度 {fact.confidence:.2f}，"
                    f"更新于 {fact.created_at.date().isoformat()}）"
                )
        lines.append("\n你可以直接说“把每周时间改为 5 小时”或“删除我的画像”。")
        if not profile.persisted:
            lines.append("当前画像只存在于本轮消息中，尚未持久保存。")
        return "\n".join(lines)

    @staticmethod
    def _prose_only(text: str) -> str:
        without_fences = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)

        def looks_like_code(candidate: str) -> bool:
            return sum(
                (
                    ";" in candidate,
                    "{" in candidate or "}" in candidate,
                    bool(re.search(r"#?\s*include\s*<[^>]+>", candidate, re.I)),
                    bool(re.search(r"\b(?:def|class|int|void|fn)\s+\w+\s*\(", candidate)),
                )
            ) >= 2

        def remove_code_quote(match: re.Match[str]) -> str:
            return " " if looks_like_code(match.group(1)) else match.group(0)

        without_quotes = re.sub(
            r"[“\"「『](.*?)[”\"」』]",
            remove_code_quote,
            without_fences,
            flags=re.DOTALL,
        )
        code_tail = re.search(
            r"(?:这段|以下|下面的?).{0,8}代码.{0,16}?[：:]",
            without_quotes,
            re.IGNORECASE,
        )
        if code_tail and looks_like_code(without_quotes[code_tail.end() :].strip("“”\"'")):
            without_quotes = without_quotes[: code_tail.start()]
        without_traceback = re.split(
            r"Traceback \(most recent call last\):", without_quotes, maxsplit=1
        )[0]
        return re.sub(r"\s+", " ", without_traceback).strip()[:4000]

    def _deterministic_candidates(self, prose: str) -> list[ProfileCandidate]:
        candidates: list[ProfileCandidate] = []
        time_match = re.search(
            r"每(?:周|星期)[^。；，,]{0,20}?(\d+(?:\.\d+)?)\s*(小时|分钟)", prose
        )
        if time_match:
            amount = float(time_match.group(1))
            minutes = round(amount * 60) if time_match.group(2) == "小时" else round(amount)
            if 0 < minutes <= 7 * 24 * 60:
                candidates.append(
                    ProfileCandidate(
                        field_name="weekly_minutes",
                        value=minutes,
                        status=FactStatus.CONFIRMED,
                        confidence=1.0,
                        evidence_quote=time_match.group(0),
                    )
                )

        learning_intent = re.search(
            r"想学|想.{0,12}(?:学习|掌握)|准备学|系统学习|学习方向|目标|重点是|方向是|转向|"
            r"方向.*改(?:为|成)|不是.*(?:系统|算法|机器学习|深度学习|安全)",
            prose,
        )
        direction_patterns = (
            (r"系统方向|计算机系统|操作系统|体系结构|系统课程", "systems"),
            (r"机器学习|深度学习|人工智能|transformer", "ml_ai"),
            (r"算法", "algorithms"),
            (r"安全", "security"),
            (r"前端", "web_frontend"),
            (r"后端", "web_backend"),
            (r"理论计算机|计算理论", "theory"),
        )
        if learning_intent:
            for pattern, normalized in direction_patterns:
                if re.search(pattern, prose, re.IGNORECASE):
                    candidates.append(
                        ProfileCandidate(
                            field_name="learning_directions",
                            value=normalized,
                            status=FactStatus.CONFIRMED,
                            confidence=1.0,
                            evidence_quote=prose[:200],
                        )
                    )

        for skill in ("Python", "C++", "Java", "Git", "线性代数", "微积分", "PyTorch"):
            match = re.search(
                rf"(?<![不没])(?:有|会|学过|熟悉|掌握)[^。；，,]{{0,18}}?{re.escape(skill)}(?:[^。；，,]{{0,8}}?(?:基础|经验))?",
                prose,
                re.IGNORECASE,
            )
            if match:
                candidates.append(
                    ProfileCandidate(
                        field_name="background",
                        value=skill,
                        status=FactStatus.CONFIRMED,
                        confidence=1.0,
                        evidence_quote=match.group(0),
                    )
                )

        goal_match = re.search(
            r"(?:(?:我的)?目标(?:是|：|:)|重点是)([^。；]{2,160})", prose
        )
        if goal_match:
            candidates.append(
                ProfileCandidate(
                    field_name="goals",
                    value=goal_match.group(1).strip(),
                    status=FactStatus.CONFIRMED,
                    confidence=1.0,
                    evidence_quote=goal_match.group(0),
                )
            )

        style_map = {
            "先讲例子": "example_first",
            "先给例子": "example_first",
            "例子优先": "example_first",
            "循序渐进": "step_by_step",
            "一步一步": "step_by_step",
            "简洁": "concise",
            "先讲概念": "concept_first",
        }
        for phrase, style in style_map.items():
            if phrase in prose:
                candidates.append(
                    ProfileCandidate(
                        field_name="preferred_explanation_style",
                        value=style,
                        status=FactStatus.CONFIRMED,
                        confidence=1.0,
                        evidence_quote=phrase,
                    )
                )
                break
        return candidates

    def _normalize_candidates(
        self,
        candidates: list[ProfileCandidate],
        prose: str,
        current: LearnerProfile,
    ) -> list[ProfileCandidate]:
        declined = {
            fact.field_name for fact in current.facts if fact.status is FactStatus.DECLINED
        }
        normalized: list[ProfileCandidate] = []
        seen: set[tuple[str, str, str]] = set()
        expanded_candidates: list[ProfileCandidate] = []
        for candidate in candidates:
            values = (
                candidate.value
                if isinstance(candidate.value, list)
                and candidate.field_name
                in {"learning_directions", "goals", "background"}
                else [candidate.value]
            )
            for value in values:
                item = candidate.model_copy(deep=True)
                item.value = self._canonical_value(item.field_name, value)
                if (
                    item.field_name == "learning_directions"
                    and item.value
                    not in {
                        "systems",
                        "ml_ai",
                        "algorithms",
                        "security",
                        "web_frontend",
                        "web_backend",
                        "theory",
                    }
                ):
                    continue
                if item.value not in {None, ""}:
                    expanded_candidates.append(item)

        for candidate in expanded_candidates:
            if candidate.field_name in declined:
                continue
            item = candidate.model_copy(deep=True)
            if item.status is FactStatus.CONFIRMED:
                quote = (item.evidence_quote or "").strip()
                if not quote or quote not in prose:
                    item.status = FactStatus.INFERRED
                    item.confidence = min(item.confidence, 0.7)
                    item.evidence_quote = None
                else:
                    item.confidence = 1.0
                    item.evidence_quote = quote[:200]
            elif item.status is FactStatus.INFERRED:
                item.confidence = min(item.confidence, 0.79)
                item.evidence_quote = (item.evidence_quote or "")[:200] or None
            elif item.status is FactStatus.DECLINED:
                quote = (item.evidence_quote or "").strip()
                if (
                    not quote
                    or quote not in prose
                    or not re.search(r"不要记录|别记录|不想保存", quote)
                ):
                    continue
                item.value = None
                item.confidence = 1.0
                item.evidence_quote = quote[:200]
            if item.field_name == "weekly_minutes":
                if not isinstance(item.value, int) or not 0 < item.value <= 10080:
                    continue
            serialized = json.dumps(item.value, ensure_ascii=False, sort_keys=True)
            if len(serialized) > 1000:
                continue
            key = (item.field_name, serialized, item.status.value)
            if key in seen:
                continue
            if item.field_name == "goals" and item.status is FactStatus.CONFIRMED:
                same_evidence_goal = next(
                    (
                        existing
                        for existing in normalized
                        if existing.field_name == "goals"
                        and existing.status is FactStatus.CONFIRMED
                        and existing.evidence_quote
                        and item.evidence_quote
                        and (
                            existing.evidence_quote in item.evidence_quote
                            or item.evidence_quote in existing.evidence_quote
                        )
                    ),
                    None,
                )
                if same_evidence_goal is not None:
                    continue
            seen.add(key)
            normalized.append(item)
        if "不是" in prose:
            directions = [
                item for item in normalized if item.field_name == "learning_directions"
            ]
            if directions:
                normalized = [
                    item
                    for item in normalized
                    if item.field_name != "learning_directions"
                ]
                normalized.append(directions[-1])
        return normalized

    @staticmethod
    def _canonical_value(field_name: str, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        lowered = cleaned.lower()
        if field_name == "learning_directions":
            if re.search(r"机器学习|深度学习|人工智能|transformer|\bai\b|\bml\b", lowered):
                return "ml_ai"
            if cleaned == "系统" or re.search(
                r"系统方向|计算机系统|操作系统|体系结构|systems?", lowered
            ):
                return "systems"
            if "算法" in lowered or "algorithm" in lowered:
                return "algorithms"
            if "安全" in lowered or "security" in lowered:
                return "security"
            if "前端" in lowered or "frontend" in lowered:
                return "web_frontend"
            if "后端" in lowered or "backend" in lowered:
                return "web_backend"
            if "理论" in lowered or "theory" in lowered:
                return "theory"
        if field_name == "preferred_explanation_style":
            if re.search(r"例子|示例|example", lowered):
                return "example_first"
            if re.search(r"一步一步|循序渐进|step", lowered):
                return "step_by_step"
            if re.search(r"简洁|concise", lowered):
                return "concise"
            if re.search(r"概念优先|先讲概念|concept", lowered):
                return "concept_first"
        if field_name == "background":
            cleaned = re.sub(r"(?:基础|经验|入门)$", "", cleaned).strip()
            aliases = {
                "python": "Python",
                "python3": "Python",
                "c++": "C++",
                "cpp": "C++",
                "java": "Java",
                "javascript": "JavaScript",
                "typescript": "TypeScript",
                "rust": "Rust",
                "golang": "Go",
                "go": "Go",
                "git": "Git",
                "pytorch": "PyTorch",
            }
            return aliases.get(cleaned.casefold(), cleaned)
        return cleaned

    @staticmethod
    def _candidate_to_fact(candidate: ProfileCandidate, user_id: str | None) -> ProfileFact:
        now = datetime.now(UTC)
        return ProfileFact(
            id=uuid.uuid4().hex,
            user_id=user_id,
            field_name=candidate.field_name,
            value=candidate.value,
            status=candidate.status,
            confidence=candidate.confidence,
            evidence_excerpt=candidate.evidence_quote,
            course_id=candidate.course_id,
            course_version=candidate.course_version,
            unit_id=candidate.unit_id,
            created_at=now,
            expires_at=(
                now + timedelta(days=INFERENCE_TTL_DAYS)
                if candidate.status is FactStatus.INFERRED
                else None
            ),
        )

    @staticmethod
    def _merge_transient(facts: list[ProfileFact], new_fact: ProfileFact) -> list[ProfileFact]:
        if new_fact.field_name in {
            "weekly_minutes",
            "preferred_explanation_style",
            "active_course",
            "active_unit",
        }:
            facts = [fact for fact in facts if fact.field_name != new_fact.field_name]
        if any(
            fact.field_name == new_fact.field_name
            and fact.value == new_fact.value
            and fact.status == new_fact.status
            for fact in facts
        ):
            return facts
        return [*facts, new_fact]

    def _notice(self, facts: list[ProfileFact], *, persisted: bool) -> str | None:
        if not facts:
            return None
        confirmed = [fact for fact in facts if fact.status is FactStatus.CONFIRMED]
        inferred = [fact for fact in facts if fact.status is FactStatus.INFERRED]
        parts: list[str] = []
        if confirmed:
            summary = "、".join(
                f"{self._label(fact.field_name)}={self._display_value(fact.value, fact.field_name)}"
                for fact in confirmed[:4]
            )
            prefix = "已记录" if persisted else "本轮已识别（未持久保存）"
            parts.append(f"{prefix}：{summary}")
        if inferred:
            summary = "、".join(
                f"{self._label(fact.field_name)}={self._display_value(fact.value, fact.field_name)}"
                for fact in inferred[:3]
            )
            parts.append(f"待确认：{summary}")
        return "；".join(parts) + "。"

    @staticmethod
    def _field_from_text(text: str) -> ProfileFieldName | None:
        mappings: list[tuple[tuple[str, ...], ProfileFieldName]] = [
            (("时间", "每周", "每星期"), "weekly_minutes"),
            (("方向",), "learning_directions"),
            (("目标",), "goals"),
            (("基础", "背景"), "background"),
            (("偏好", "讲解方式"), "preferred_explanation_style"),
            (("课程",), "active_course"),
            (("讲次", "lecture"), "active_unit"),
        ]
        return next((field for words, field in mappings if any(word in text for word in words)), None)

    @staticmethod
    def _label(field_name: str) -> str:
        return {
            "learning_directions": "学习方向",
            "goals": "学习目标",
            "background": "已有基础",
            "weekly_minutes": "每周时间",
            "preferred_explanation_style": "讲解偏好",
            "active_course": "当前课程",
            "active_unit": "当前讲次",
        }.get(field_name, field_name)

    @staticmethod
    def _display_value(value: object, field_name: str | None = None) -> str:
        if isinstance(value, int):
            hours, minutes = divmod(value, 60)
            if hours and minutes:
                return f"{hours} 小时 {minutes} 分钟（{value} 分钟）"
            return f"{hours} 小时（{value} 分钟）" if hours else f"{minutes} 分钟"
        if isinstance(value, list):
            return "、".join(str(item) for item in value)
        if field_name == "learning_directions":
            return {
                "systems": "系统（systems）",
                "ml_ai": "人工智能/机器学习（ml_ai）",
                "algorithms": "算法（algorithms）",
                "security": "安全（security）",
                "web_frontend": "Web 前端",
                "web_backend": "Web 后端",
                "theory": "理论计算机科学",
            }.get(str(value), str(value))
        if field_name == "preferred_explanation_style":
            return {
                "example_first": "示例优先",
                "step_by_step": "循序渐进",
                "concise": "简洁",
                "concept_first": "概念优先",
            }.get(str(value), str(value))
        return str(value)

    @staticmethod
    def _mentions_course(text: str) -> bool:
        lowered = text.lower()
        return bool(re.search(r"6\.7960|lecture\s*[- ]?\d+|第\s*\d+\s*讲", lowered))


@lru_cache(maxsize=1)
def get_profile_service() -> ProfileService:
    return ProfileService(SQLiteProfileRepository(get_database()))
