"""Deterministic extraction and management of a minimal learner profile."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.profile.repository import SQLiteProfileRepository
from app.storage.database import get_database

FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
WEEKLY_TIME = re.compile(
    r"每(?:周|星期)[^。；，,]{0,20}?(\d+(?:\.\d+)?)\s*(小时|分钟)",
    re.IGNORECASE,
)
BACKGROUND = re.compile(
    r"(?:有|具备|熟悉|学过)\s*([A-Za-z][A-Za-z0-9+#.]{0,30})\s*(?:基础|经验)?",
    re.IGNORECASE,
)
DIRECTIONS = {
    "系统": "systems",
    "算法": "algorithms",
    "机器学习": "ml_ai",
    "深度学习": "ml_ai",
    "安全": "security",
    "前端": "frontend",
    "后端": "backend",
}


@dataclass(frozen=True)
class ProfileHandlingResult:
    answer: str | None = None
    added_fields: tuple[str, ...] = ()


class ProfileService:
    def __init__(self, repository: SQLiteProfileRepository) -> None:
        self.repository = repository

    def handle(self, *, user_id: str | None, text: str) -> ProfileHandlingResult:
        if user_id is None:
            return ProfileHandlingResult()

        lowered = text.lower()
        if any(word in lowered for word in ("删除", "清空", "忘记")) and any(
            word in lowered for word in ("画像", "记录", "关于我")
        ):
            count = self.repository.delete_all(user_id)
            return ProfileHandlingResult(answer=f"已删除你的学习画像（{count} 条事实）。")

        if any(word in lowered for word in ("查看", "显示", "知道", "记得")) and any(
            word in lowered for word in ("画像", "关于我", "我的学习")
        ):
            return ProfileHandlingResult(answer=self.render(self.repository.get_profile(user_id)))

        prose = FENCED_CODE.sub("", text)
        facts = self._extract(prose)
        for field_name, value, excerpt in facts:
            self.repository.set_fact(
                user_id=user_id,
                field_name=field_name,
                value=value,
                evidence_excerpt=excerpt,
            )
        return ProfileHandlingResult(
            added_fields=tuple(dict.fromkeys(item[0] for item in facts))
        )

    @staticmethod
    def render(profile: dict[str, list[object]]) -> str:
        if not profile:
            return "当前没有已保存的学习画像。你可以告诉我学习方向、每周时间或已有基础。"
        labels = {
            "learning_direction": "学习方向",
            "weekly_minutes": "每周学习时间（分钟）",
            "background": "已有基础",
        }
        lines = ["你的已确认学习画像："]
        for field_name in ("learning_direction", "weekly_minutes", "background"):
            values = profile.get(field_name)
            if values:
                lines.append(f"- {labels[field_name]}：{', '.join(map(str, values))}")
        lines.append("你可以随时发送“删除我的画像”清除这些信息。")
        return "\n".join(lines)

    @staticmethod
    def _extract(text: str) -> list[tuple[str, object, str]]:
        facts: list[tuple[str, object, str]] = []
        time_match = WEEKLY_TIME.search(text)
        if time_match:
            amount = float(time_match.group(1))
            minutes = int(amount * 60) if time_match.group(2) == "小时" else int(amount)
            facts.append(("weekly_minutes", minutes, time_match.group(0)))

        if any(signal in text for signal in ("想学", "学习方向", "准备学", "正在学")):
            for label, value in DIRECTIONS.items():
                if label in text:
                    facts.append(("learning_direction", value, label))
                    break

        background_match = BACKGROUND.search(text)
        if background_match:
            facts.append(
                ("background", background_match.group(1), background_match.group(0))
            )
        return facts


@lru_cache(maxsize=1)
def get_profile_service() -> ProfileService:
    return ProfileService(SQLiteProfileRepository(get_database()))
