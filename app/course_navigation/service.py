"""Learner-facing navigation over the validated CSDIY catalog."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from dataclasses import dataclass

from app.catalog.contracts import CourseCard
from app.catalog.courses import CatalogDataError, CourseCatalogStore
from app.profile.contracts import FactStatus, LearnerProfile


_DIRECTION_TERMS: dict[str, tuple[str, ...]] = {
    "systems": ("系统", "操作系统", "体系结构", "网络", "编译", "数据库", "并行", "分布式"),
    "ml_ai": ("机器学习", "深度学习", "人工智能", "ai", "ml", "视觉", "自然语言", "强化学习"),
    "algorithms": ("算法", "数据结构", "竞赛"),
    "security": ("安全", "密码学", "security"),
    "web_frontend": ("前端", "frontend", "react", "ui"),
    "web_backend": ("后端", "backend", "web 开发"),
    "theory": ("理论", "形式化", "计算理论"),
}

_AUTHORING_LABELS = {
    "classified": "仅目录收录",
    "researching_offering": "课程版本调研中",
    "offering_selected": "已选择课程版本",
    "sources_inventoried": "已建立材料清单",
    "downloaded": "材料已下载",
    "prepared": "材料已准备",
    "chunked": "材料已切分",
    "authoring": "StudyKit 编写中",
    "audited": "离线审核中",
    "validated": "离线产物已验证",
    "complete": "离线课程包已完成",
    "blocked_no_public_evidence": "缺少公开材料",
    "blocked_access": "材料访问受限",
    "failed_recoverable": "离线处理待修复",
    "discovered": "目录发现",
}

_REVIEW_LABELS = {
    "pass": "已审核",
    "approved": "已审核",
    "independently_audited": "已独立审核",
    "pending": "待独立审核",
    "pending_independent_audit": "待独立审核",
}


@dataclass(frozen=True, slots=True)
class NavigationResult:
    answer: str
    catalog_ids: tuple[str, ...] = ()


class CourseNavigationService:
    def __init__(self, catalog: CourseCatalogStore) -> None:
        self.catalog = catalog

    def navigate(self, *, text: str, profile: LearnerProfile) -> str:
        return self.navigate_result(text=text, profile=profile).answer

    def navigate_result(
        self,
        *,
        text: str,
        profile: LearnerProfile,
        candidate_id: str | None = None,
    ) -> NavigationResult:
        try:
            if candidate_id:
                candidate = self.catalog.get(candidate_id)
                if candidate is not None:
                    return NavigationResult(
                        self._render([candidate], heading="按你的描述匹配到的课程"),
                        (candidate.catalog_id,),
                    )
            if "不是" in text:
                correction_tail = re.split(r"(?:而是|改为|改成|，|,|；|;)", text)[-1]
                corrected = self.catalog.match_explicit(correction_tail)
                if corrected:
                    return NavigationResult(
                        self._render(corrected, heading="按你的纠正匹配到的课程"),
                        tuple(item.catalog_id for item in corrected),
                    )
            explicit = self.catalog.match_explicit(text)
            if explicit:
                return NavigationResult(
                    self._render(explicit, heading="匹配到的课程"),
                    tuple(item.catalog_id for item in explicit),
                )

            directions = self._directions(text, profile)
            is_list = bool(re.search(r"有哪些课程|课程列表|列出.{0,4}课程|查看.{0,4}课程", text, re.I))
            if not directions and not is_list:
                return NavigationResult(
                    "你希望学习哪个方向？例如系统、算法、机器学习、安全、Web 或理论。"
                    "我会从现有课程表中推荐候选，并分别标明目录状态、离线制作状态和在线 StudyKit 状态。"
                )
            limit = 5 if is_list else 3
            search_text = "" if is_list and not directions else text
            matches = self.catalog.search(search_text, directions=directions, limit=limit)
        except CatalogDataError:
            return NavigationResult(
                "课程目录当前校验失败，因此本轮没有生成课程推荐，也不会让模型补全目录事实。"
            )
        if not matches:
            return NavigationResult(
                "现有课程表中没有找到可信匹配。请换一个方向、学校名或课程号重试。"
            )
        heading = "课程目录候选" if is_list else "课程推荐"
        return NavigationResult(
            self._render(matches, heading=heading),
            tuple(item.catalog_id for item in matches),
        )

    def get_card(self, catalog_id: str) -> CourseCard | None:
        try:
            return self.catalog.get(catalog_id)
        except CatalogDataError:
            return None

    def resolve_card(self, *queries: str | None) -> CourseCard | None:
        """Resolve one model-proposed identity only when the catalog result is unique."""

        try:
            for query in queries:
                if not query:
                    continue
                direct = self.catalog.get(query)
                if direct is not None:
                    return direct
                normalized_query = re.sub(r"[^a-z0-9]+", "", query.casefold())
                identity_matches = [
                    card
                    for card in self.catalog.list_courses()
                    if card.manifest_course_id
                    and (
                        re.sub(r"[^a-z0-9]+", "", card.manifest_course_id.casefold())
                        == normalized_query
                        or (
                            len(normalized_query) >= 5
                            and re.sub(
                                r"[^a-z0-9]+", "", card.manifest_course_id.casefold()
                            ).startswith(normalized_query)
                        )
                    )
                ]
                if len(identity_matches) == 1:
                    return identity_matches[0]
                matches = self.catalog.match_explicit(query, limit=2)
                if len(matches) == 1:
                    return matches[0]
                course_tokens = re.findall(r"[a-z]*\d+[a-z]+|\d+[a-z]+", query.casefold())
                if course_tokens:
                    token = course_tokens[-1]
                    suffix_matches = [
                        card
                        for card in self.catalog.list_courses()
                        if any(
                            re.sub(r"[^a-z0-9]+", "", number.casefold()).endswith(token)
                            for number in card.course_numbers
                        )
                    ]
                    if len(suffix_matches) == 1:
                        return suffix_matches[0]
                if len(normalized_query) >= 4:
                    fuzzy = []
                    for card in self.catalog.list_courses():
                        scores = [
                            SequenceMatcher(
                                None,
                                normalized_query,
                                re.sub(r"[^a-z0-9]+", "", number.casefold()),
                            ).ratio()
                            for number in card.course_numbers
                        ]
                        if scores and max(scores) >= 0.8:
                            fuzzy.append(card)
                    if len(fuzzy) == 1:
                        return fuzzy[0]
        except CatalogDataError:
            return None
        return None

    @staticmethod
    def _directions(text: str, profile: LearnerProfile) -> tuple[str, ...]:
        lowered = text.casefold()
        explicit = [
            direction
            for direction, markers in _DIRECTION_TERMS.items()
            if any(marker.casefold() in lowered for marker in markers)
        ]
        if explicit:
            return tuple(dict.fromkeys(explicit))
        confirmed = [
            str(fact.value)
            for fact in profile.facts
            if fact.field_name == "learning_directions"
            and fact.status is FactStatus.CONFIRMED
            and isinstance(fact.value, str)
            and fact.value in _DIRECTION_TERMS
        ]
        return tuple(dict.fromkeys(confirmed))

    @staticmethod
    def _render(cards: list[CourseCard], *, heading: str) -> str:
        lines = [f"## {heading}", ""]
        for index, card in enumerate(cards, start=1):
            number = " / ".join(card.course_numbers)
            identity = f"（{number}）" if number and number.casefold() not in card.title.casefold() else ""
            lines.append(f"{index}. **{card.title}**{identity}")
            if card.institution:
                lines.append(f"   - 学校：{card.institution}")
            if card.categories:
                lines.append(f"   - 方向：{' / '.join(card.categories)}")
            review = _REVIEW_LABELS.get(
                card.catalog_review_status,
                "待独立审核" if "pending" in card.catalog_review_status else "已审核",
            )
            lines.append(f"   - 目录状态：{review}")
            lines.append(
                f"   - 离线制作：{_AUTHORING_LABELS.get(card.authoring_status, card.authoring_status)}"
            )
            if card.online_studykits:
                units = CourseNavigationService._compact_units(
                    [item.unit_id for item in card.online_studykits]
                )
                lines.append(f"   - 在线 StudyKit：可用（{units}）")
            else:
                lines.append("   - 在线 StudyKit：尚不可用")
            if card.official_url:
                lines.append(f"   - [官方课程页]({card.official_url})")
            lines.append(f"   - [CSDIY 导航页]({card.navigation_url})")
            lines.append("")
        lines.append(
            "说明：课程表收录或离线产物完成不等于在线 StudyKit 已可用；"
            "只有明确标为“在线 StudyKit：可用”的讲次才能进入材料问答和练习。"
        )
        return "\n".join(lines)

    @staticmethod
    def _compact_units(unit_ids: list[str]) -> str:
        if not unit_ids:
            return ""
        parsed = [re.fullmatch(r"(.+?)(\d+)", item) for item in unit_ids]
        if all(match is not None for match in parsed):
            prefixes = {match.group(1) for match in parsed if match is not None}
            numbers = [int(match.group(2)) for match in parsed if match is not None]
            if len(prefixes) == 1 and numbers == list(range(numbers[0], numbers[0] + len(numbers))):
                return f"共 {len(unit_ids)} 讲：{unit_ids[0]}–{unit_ids[-1]}"
        if len(unit_ids) > 8:
            return "、".join(unit_ids[:5]) + f" 等，共 {len(unit_ids)} 讲"
        return "、".join(unit_ids)
