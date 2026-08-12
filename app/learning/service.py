"""Evidence-bounded online learning capabilities backed by ready StudyKits."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.agent.contracts import CourseContext
from app.agent.model_support import normalized_usage
from app.catalog.courses import CatalogDataError, CourseCatalogStore
from app.catalog.studykits import StudyKitStore
from app.generation.model import ModelError, StructuredModel
from app.learning.contracts import (
    LearningReply,
    MaterialAnswerDraft,
    PracticeFeedbackDraft,
)
from app.protocol.schemas import ChatMessage
from app.retrieval.practice import render_practice_prompt


_FULL_SOLUTION = re.compile(
    r"完整答案|标准答案|全部解答|直接给.*答案|可提交|帮我做完|full solution|solve it for me",
    re.IGNORECASE,
)
_PAGE_REFERENCE = re.compile(r"(?:第\s*(\d{1,4})\s*页|page\s*(\d{1,4}))", re.IGNORECASE)
_HIDDEN_OUTPUT = re.compile(
    r"expected_evidence|full_credit|partial_credit|evaluation|rubric|评分标准|预期证据|"
    r"累计正确率|总体掌握度|\b\d+\s*/\s*\d+\b|得分[:：]",
    re.IGNORECASE,
)
_QUERY_STOPWORDS = {
    "什么",
    "为什么",
    "如何",
    "怎么",
    "解释",
    "一下",
    "讲义",
    "材料",
    "里面",
    "这个",
    "课程",
    "概念",
    "请问",
    "说了",
}


@dataclass(frozen=True, slots=True)
class _EvidenceItem:
    citation_id: str
    kind: str
    text: str
    source_id: str
    pages: tuple[int, ...]
    search_terms: tuple[str, ...]


class StudyKitLookupService:
    """Read-only StudyKit learning features with no answer persistence."""

    def __init__(
        self,
        store: StudyKitStore,
        model: StructuredModel | None = None,
        catalog: CourseCatalogStore | None = None,
    ) -> None:
        self.store = store
        self.model = model
        self.catalog = catalog

    async def lookup(
        self,
        *,
        messages: list[ChatMessage],
        course_context: CourseContext | None,
    ) -> LearningReply:
        if course_context is None:
            catalog_status = self._catalog_status(messages)
            if catalog_status is not None:
                return self._reply(catalog_status)
            ready = self.store.list_ready()
            if not ready:
                return self._reply("当前没有可在线读取的已审核 StudyKit。")
            lines = ["## 当前可用 StudyKit", ""]
            for item in ready:
                lines.append(
                    f"- `{item.course_id}` / `{item.course_version}` / `{item.unit_id}`：{item.title}"
                )
            lines.extend(["", "请指定课程和讲次，例如“查看 MIT 6.7960 第 2 讲的 StudyKit”。"])
            return self._reply("\n".join(lines))
        if course_context.unit_id is None:
            return self._reply(self._render_available_units(course_context))
        document = self._get_document(course_context)
        if document is None:
            return self._reply(self._unavailable_context(course_context))
        return self._reply(self._render_lookup(document))

    async def material_question(
        self,
        *,
        messages: list[ChatMessage],
        course_context: CourseContext | None,
    ) -> LearningReply:
        document, unavailable = self._require_document(course_context, messages)
        if document is None:
            return self._reply(unavailable)
        question = _latest_user_text(messages)
        candidates = self._select_evidence(document, question)
        page = self._requested_page(question)
        if not candidates:
            if page is not None:
                return self._reply(
                    f"当前已审核 StudyKit 没有足够依据说明第 {page} 页的具体内容。"
                    "SourceChunk 检索尚未上线，因此我不会猜测该页原文；请回看官方材料，"
                    "或改问 StudyKit 已覆盖的核心概念。"
                )
            return self._reply(
                "当前 StudyKit 中没有找到与这个问题直接对应且带页码的已审核内容。"
                "SourceChunk 检索尚未上线，因此我不会用通用知识补成课程事实。"
            )

        usage = normalized_usage()
        if self.model is not None:
            try:
                response = await self.model.generate_json(
                    system_prompt=(
                        "你是 CoursePilot 材料问答器。只能使用 evidence 中的文字，"
                        "不得补充外部课程事实。每个结论必须由 citation_ids 支持；"
                        "不得引用未提供的 ID。只输出 JSON object。"
                    ),
                    user_prompt=json.dumps(
                        {
                            "question": question[:4000],
                            "evidence": [
                                {
                                    "citation_id": item.citation_id,
                                    "kind": item.kind,
                                    "text": item.text,
                                    "source_id": item.source_id,
                                    "pages": list(item.pages),
                                }
                                for item in candidates
                            ],
                            "output_contract": {
                                "answer": "answer using only evidence",
                                "citation_ids": ["one or more allowed ids"],
                            },
                        },
                        ensure_ascii=False,
                    ),
                    thinking_enabled=False,
                    max_tokens=2048,
                    timeout_seconds=30,
                )
                usage = normalized_usage(response.usage)
                draft = MaterialAnswerDraft.model_validate(_unwrap(response.output))
                allowed = {item.citation_id: item for item in candidates}
                if (
                    any(citation_id not in allowed for citation_id in draft.citation_ids)
                    or _HIDDEN_OUTPUT.search(draft.answer)
                ):
                    raise ValueError("material answer violated its evidence contract")
                cited = [allowed[citation_id] for citation_id in dict.fromkeys(draft.citation_ids)]
                return LearningReply(
                    answer=self._render_material_answer(draft.answer, cited),
                    usage=usage,
                )
            except (ModelError, ValidationError, ValueError):
                pass
        return LearningReply(
            answer=self._render_material_fallback(candidates),
            usage=usage,
        )

    async def concept_explanation(
        self,
        *,
        messages: list[ChatMessage],
        course_context: CourseContext | None,
    ) -> LearningReply:
        document, unavailable = self._require_document(course_context, messages)
        if document is None:
            return self._reply(unavailable)
        question = _latest_user_text(messages)
        concepts = [item for item in document.get("core_concepts", []) if isinstance(item, dict)]
        ranked = sorted(
            (
                (self._concept_score(item, question), index, item)
                for index, item in enumerate(concepts)
            ),
            key=lambda entry: (-entry[0], entry[1]),
        )
        if not ranked or ranked[0][0] <= 0:
            available = "、".join(str(item.get("term_zh") or item.get("term_en")) for item in concepts[:8])
            return self._reply(
                "当前 StudyKit 没有覆盖你询问的概念，不能把通用解释冒充为课程内容。"
                f"本讲可解释的核心概念包括：{available}。"
            )
        concept = ranked[0][2]
        citations = [
            item
            for item in concept.get("citations", [])
            if isinstance(item, dict)
            and isinstance(item.get("page"), int)
            and item.get("source_id")
        ]
        if not citations:
            return self._reply("这个概念在当前 StudyKit 中没有可核查页码，因此暂不提供课程化解释。")
        return self._reply(self._render_concept(document, concept, citations))

    async def practice_selection(
        self,
        *,
        messages: list[ChatMessage],
        course_context: CourseContext | None,
    ) -> LearningReply:
        document, unavailable = self._require_document(course_context, messages)
        if document is None:
            return self._reply(unavailable)
        practices = [item for item in document.get("practice", []) if isinstance(item, dict)]
        latest = _latest_user_text(messages)
        explicit = next(
            (item for item in practices if str(item.get("id", "")) in latest),
            None,
        )
        if explicit is not None:
            selected = explicit
        else:
            requested = self._requested_practice_type(latest)
            displayed = {
                str(item.get("id"))
                for item in practices
                if any(str(item.get("id", "")) in message.content for message in messages)
            }
            candidates = [item for item in practices if str(item.get("id")) not in displayed]
            if requested:
                candidates = [item for item in candidates if self._practice_matches(item, requested)]
            if not candidates:
                if requested:
                    return self._reply(
                        f"本讲没有尚未展示的“{requested}”练习。可以指定已有 practice ID 重新查看。"
                    )
                return self._reply("本讲练习已在当前对话中展示完毕；请指定 practice ID 重新查看。")
            selected = candidates[0]
        practice_id = str(selected["id"])
        prompt = render_practice_prompt(document, practice_id, include_hint=False)
        return self._reply(
            f"{prompt}\n\n作答后请明确写出 `practice ID: {practice_id}` 并附上你的当前答案。"
            "反馈只针对这一次回答，不累计得分或掌握度。"
        )

    async def practice_feedback(
        self,
        *,
        messages: list[ChatMessage],
        course_context: CourseContext | None,
    ) -> LearningReply:
        document, unavailable = self._require_document(course_context, messages)
        if document is None:
            return self._reply(unavailable)
        latest = _latest_user_text(messages)
        practices = [item for item in document.get("practice", []) if isinstance(item, dict)]
        problem = next(
            (item for item in practices if str(item.get("id", "")) in latest),
            None,
        )
        if problem is None:
            return self._reply(
                "请在反馈请求中附上本讲的 practice ID 和你的当前答案，例如："
                "`practice ID: practice-concept-01`。"
            )
        practice_id = str(problem["id"])
        answer_text = self._extract_answer(latest, practice_id)
        if len(answer_text) < 4:
            return self._reply(f"请补充你对 `{practice_id}` 的当前答案；我不会根据空答案推断掌握度。")
        if _FULL_SOLUTION.search(latest):
            return self._reply(
                "我不能提供完整标准答案或可直接提交的作业答案。你可以贴出当前尝试，"
                "我会指出一个关键遗漏，"
                "并给出下一层提示和相关讲义页码。"
            )
        source_pages = sorted(
            {
                int(page)
                for page in problem.get("source_pages", [])
                if isinstance(page, int) and page > 0
            }
        )
        if not source_pages:
            return self._reply("这道练习没有可核查的来源页码，因此暂不进行语义反馈。")

        usage = normalized_usage()
        if self.model is not None:
            try:
                response = await self.model.generate_json(
                    system_prompt=(
                        "你是 CoursePilot 练习反馈器。只评价 current_answer，不累计分数或掌握度。"
                        "指出已经正确的点、一个最重要的错误或遗漏、下一层提示；不要给完整标准答案。"
                        "expected_evidence 和 evaluation 仅用于内部比较，绝不能复述、列出或提及这些字段。"
                        "source_pages 只能选 allowed_source_pages。只输出 JSON object。"
                    ),
                    user_prompt=json.dumps(
                        {
                            "practice": {
                                "id": practice_id,
                                "question": problem.get("question"),
                                "deliverable": problem.get("deliverable"),
                                "expected_evidence": problem.get("expected_evidence", []),
                                "evaluation": problem.get("evaluation", {}),
                            },
                            "current_answer": answer_text[:6000],
                            "allowed_source_pages": source_pages,
                            "output_contract": {
                                "correct_points": ["at most four points from this answer"],
                                "correction": "one important error or omission, or null",
                                "next_hint": "a hint, not the full answer",
                                "source_pages": ["allowed integer pages only"],
                            },
                        },
                        ensure_ascii=False,
                    ),
                    thinking_enabled=False,
                    max_tokens=2048,
                    timeout_seconds=30,
                )
                usage = normalized_usage(response.usage)
                draft = PracticeFeedbackDraft.model_validate(_unwrap(response.output))
                if (
                    not draft.correct_points
                    and not draft.correction
                    or any(page not in source_pages for page in draft.source_pages)
                ):
                    raise ValueError("practice feedback violated its contract")
                rendered = self._render_feedback(draft)
                if _HIDDEN_OUTPUT.search(rendered):
                    raise ValueError("practice feedback exposed hidden controls")
                return LearningReply(answer=rendered, usage=usage)
            except (ModelError, ValidationError, ValueError):
                pass
        return LearningReply(
            answer=self._render_feedback_fallback(problem, source_pages),
            usage=usage,
        )

    def _require_document(
        self,
        course_context: CourseContext | None,
        messages: list[ChatMessage],
    ) -> tuple[dict[str, Any] | None, str]:
        if course_context is None:
            catalog_status = self._catalog_status(messages)
            if catalog_status is not None:
                return None, catalog_status
            return None, (
                "请先指定课程、版本和讲次。当前在线材料能力只会读取已审核 StudyKit，"
                "不会根据名称猜测课程身份。"
            )
        if course_context.unit_id is None:
            return None, self._render_available_units(course_context)
        document = self._get_document(course_context)
        if document is None:
            return None, self._unavailable_context(course_context)
        return document, ""

    def _catalog_status(self, messages: list[ChatMessage]) -> str | None:
        if self.catalog is None:
            return None
        try:
            matches = self.catalog.match_explicit(_latest_user_text(messages), limit=1)
        except CatalogDataError:
            return "课程目录当前校验失败，因此没有使用目录记录补全 StudyKit 身份。"
        if not matches:
            return None
        card = matches[0]
        if card.online_studykits:
            units = "、".join(f"`{item.unit_id}`" for item in card.online_studykits)
            return (
                f"已在目录中匹配到 **{card.title}**，当前在线 StudyKit 讲次为 {units}。"
                "请使用课程号并明确选择一个讲次。"
            )
        return (
            f"已在课程表中匹配到 **{card.title}**，离线制作状态为 `{card.authoring_status}`，"
            "但当前没有经过 StudyKitStore 门禁的在线讲次。目录收录或离线产物完成"
            "不等于在线内容已经可用。"
        )

    def _get_document(self, context: CourseContext) -> dict[str, Any] | None:
        if context.unit_id is None:
            return None
        return self.store.get_ready(context.course_id, context.course_version, context.unit_id)

    def _render_available_units(self, context: CourseContext) -> str:
        ready = self.store.list_ready(
            course_id=context.course_id,
            course_version=context.course_version,
        )
        if not ready:
            return self._unavailable_context(context)
        lines = [
            f"`{context.course_id}` / `{context.course_version}` 当前可在线读取的讲次：",
            *[f"- `{item.unit_id}`：{item.title}" for item in ready],
            "请明确选择一个讲次。",
        ]
        return "\n".join(lines)

    @staticmethod
    def _unavailable_context(context: CourseContext) -> str:
        unit = f" / `{context.unit_id}`" if context.unit_id else ""
        return (
            f"`{context.course_id}` / `{context.course_version}`{unit} 没有可在线读取的已审核 StudyKit。"
            "目录收录或离线产物完成不等于在线内容已经可用。"
        )

    @staticmethod
    def _render_lookup(document: dict[str, Any]) -> str:
        lines = [
            f"## {document['title']}",
            "",
            f"- 身份：`{document['course_id']}` / `{document['course_version']}` / `{document['unit_id']}`",
        ]
        estimated = document.get("estimated_study_time_minutes")
        if isinstance(estimated, int):
            lines.append(f"- 建议学习时间：约 {estimated} 分钟")
        summary = document.get("scope", {}).get("summary")
        if summary:
            lines.extend(["", str(summary)])
        lines.extend(["", "### 学习目标"])
        lines.extend(
            f"- {item['objective']}"
            for item in document.get("learning_objectives", [])
            if isinstance(item, dict) and item.get("objective")
        )
        lines.extend(["", "### 核心概念"])
        lines.extend(
            f"- {item.get('term_zh')}（{item.get('term_en')}）"
            for item in document.get("core_concepts", [])
            if isinstance(item, dict) and item.get("term_zh") and item.get("term_en")
        )
        lines.extend(["", "### 练习"])
        lines.extend(
            f"- `{item.get('id')}`（{item.get('level')}）"
            for item in document.get("practice", [])
            if isinstance(item, dict) and item.get("id")
        )
        source = next(
            (
                item
                for item in document.get("scope", {}).get("included_sources", [])
                if isinstance(item, dict) and item.get("official_url")
            ),
            None,
        )
        if source:
            lines.extend(["", f"[官方课程材料]({source['official_url']})"])
        return "\n".join(lines)

    def _select_evidence(self, document: dict[str, Any], question: str) -> list[_EvidenceItem]:
        items = self._evidence_items(document)
        requested_page = self._requested_page(question)
        if requested_page is not None:
            return [item for item in items if requested_page in item.pages][:4]
        ranked = sorted(
            ((self._evidence_score(item, question), index, item) for index, item in enumerate(items)),
            key=lambda entry: (-entry[0], entry[1]),
        )
        return [item for score, _, item in ranked if score > 0][:4]

    @staticmethod
    def _requested_page(question: str) -> int | None:
        match = _PAGE_REFERENCE.search(question)
        return int(match.group(1) or match.group(2)) if match else None

    @staticmethod
    def _evidence_items(document: dict[str, Any]) -> list[_EvidenceItem]:
        default_source = next(
            (
                str(item.get("source_id"))
                for item in document.get("scope", {}).get("included_sources", [])
                if isinstance(item, dict) and item.get("source_id")
            ),
            "unknown-source",
        )
        items: list[_EvidenceItem] = []
        for index, concept in enumerate(document.get("core_concepts", []), start=1):
            if not isinstance(concept, dict):
                continue
            citations = [item for item in concept.get("citations", []) if isinstance(item, dict)]
            pages = tuple(
                sorted({int(item["page"]) for item in citations if isinstance(item.get("page"), int)})
            )
            if not pages:
                continue
            source_id = str(citations[0].get("source_id") or default_source)
            parts = [str(concept.get("explanation") or "")]
            if concept.get("intuition"):
                parts.append(f"直觉：{concept['intuition']}")
            if concept.get("formula"):
                parts.append(f"公式：{concept['formula']}")
            terms = tuple(
                str(value)
                for value in (concept.get("term_en"), concept.get("term_zh"), concept.get("id"))
                if value
            )
            items.append(
                _EvidenceItem(
                    citation_id=f"concept-{index}",
                    kind="core_concept",
                    text=" ".join(part for part in parts if part),
                    source_id=source_id,
                    pages=pages,
                    search_terms=terms,
                )
            )
        for index, outline in enumerate(document.get("outline", []), start=1):
            if not isinstance(outline, dict):
                continue
            pages = tuple(_expand_pages(str(outline.get("pages", ""))))
            if not pages or not outline.get("topic") or not outline.get("purpose"):
                continue
            items.append(
                _EvidenceItem(
                    citation_id=f"outline-{index}",
                    kind="outline",
                    text=f"{outline['topic']}：{outline['purpose']}",
                    source_id=default_source,
                    pages=pages,
                    search_terms=(str(outline["topic"]),),
                )
            )
        for index, misconception in enumerate(document.get("common_misconceptions", []), start=1):
            if not isinstance(misconception, dict):
                continue
            support = [item for item in misconception.get("support", []) if isinstance(item, dict)]
            pages = tuple(
                sorted({int(item["page"]) for item in support if isinstance(item.get("page"), int)})
            )
            if not pages or not misconception.get("correction"):
                continue
            text = f"常见误区：{misconception.get('misconception', '')} 修正：{misconception['correction']}"
            items.append(
                _EvidenceItem(
                    citation_id=f"misconception-{index}",
                    kind="misconception",
                    text=text,
                    source_id=default_source,
                    pages=pages,
                    search_terms=(str(misconception.get("misconception") or ""),),
                )
            )
        return items

    @staticmethod
    def _evidence_score(item: _EvidenceItem, question: str) -> int:
        lowered = question.casefold()
        score = sum(20 for term in item.search_terms if term and term.casefold() in lowered)
        haystack = f"{' '.join(item.search_terms)} {item.text}".casefold()
        score += sum(1 for token in _query_tokens(question) if token in haystack)
        return score

    @staticmethod
    def _concept_score(concept: dict[str, Any], question: str) -> int:
        item = _EvidenceItem(
            citation_id="concept",
            kind="concept",
            text=" ".join(
                str(concept.get(key) or "") for key in ("explanation", "intuition", "formula")
            ),
            source_id="",
            pages=(),
            search_terms=tuple(
                str(concept.get(key) or "") for key in ("term_en", "term_zh", "id")
            ),
        )
        return StudyKitLookupService._evidence_score(item, question)

    @staticmethod
    def _render_concept(
        document: dict[str, Any],
        concept: dict[str, Any],
        citations: list[dict[str, Any]],
    ) -> str:
        lines = [
            f"## {concept.get('term_zh')}（{concept.get('term_en')}）",
            "",
            f"**定义**：{concept.get('explanation')}",
        ]
        if concept.get("intuition"):
            lines.extend(["", f"**直觉**：{concept['intuition']}"])
        if concept.get("formula"):
            lines.extend(["", f"**公式**：`{concept['formula']}`"])
        if concept.get("teaching_note"):
            lines.extend(["", f"**说明**：{concept['teaching_note']}"])
        terms = [
            str(concept.get("term_zh") or "").casefold(),
            str(concept.get("term_en") or "").casefold(),
        ]
        misconceptions = [
            item
            for item in document.get("common_misconceptions", [])
            if isinstance(item, dict)
            and any(
                term and term in f"{item.get('misconception', '')} {item.get('correction', '')}".casefold()
                for term in terms
            )
            and item.get("support")
        ]
        if misconceptions:
            lines.extend(["", "### 常见误区"])
            for item in misconceptions[:2]:
                lines.append(f"- {item.get('misconception')} → {item.get('correction')}")
        labels = sorted(
            {(str(item["source_id"]), int(item["page"])) for item in citations},
            key=lambda value: (value[0], value[1]),
        )
        lines.extend(["", "### 来源"])
        lines.extend(f"- `{source_id}`，第 {page} 页" for source_id, page in labels)
        return "\n".join(lines)

    @staticmethod
    def _render_material_answer(answer: str, cited: list[_EvidenceItem]) -> str:
        lines = [answer.strip(), "", "### 依据"]
        lines.extend(
            f"- `{item.source_id}`，第 {_format_pages(item.pages)} 页（{item.kind}）"
            for item in cited
        )
        return "\n".join(lines)

    @staticmethod
    def _render_material_fallback(candidates: list[_EvidenceItem]) -> str:
        lines = [
            "当前未配置或未成功调用语义问答模型。下面只返回 StudyKit 中最相关的已审核内容，不补充外部事实：",
            "",
        ]
        for item in candidates[:3]:
            lines.append(f"- {item.text}（`{item.source_id}`，第 {_format_pages(item.pages)} 页）")
        return "\n".join(lines)

    @staticmethod
    def _requested_practice_type(text: str) -> str | None:
        lowered = text.casefold()
        mappings = (
            (("调试", "debug"), "调试"),
            (("代码阅读", "code reading"), "代码阅读"),
            (("推导", "derivation", "计算题"), "推导"),
            (("迁移", "transfer"), "迁移"),
            (("实现", "implementation"), "实现"),
            (("概念", "concept"), "概念"),
        )
        return next((label for markers, label in mappings if any(marker in lowered for marker in markers)), None)

    @staticmethod
    def _practice_matches(problem: dict[str, Any], requested: str) -> bool:
        level = str(problem.get("level", "")).casefold()
        practice_id = str(problem.get("id", "")).casefold()
        expected = {
            "调试": ("debug",),
            "代码阅读": ("code_reading", "code-reading"),
            "推导": ("derivation",),
            "迁移": ("transfer",),
            "实现": ("implementation",),
            "概念": ("concept",),
        }[requested]
        return any(value == level or value in practice_id for value in expected)

    @staticmethod
    def _extract_answer(text: str, practice_id: str) -> str:
        cleaned = text.replace(practice_id, " ")
        cleaned = re.sub(
            r"(?:mit\s*)?6[.-]7960(?:-fall-2024)?|fall-2024|"
            r"lecture\s*[- ]?\d+|第\s*\d+\s*讲",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"practice\s*id\s*[:：]?|练习(?:反馈|答案)?|请?(?:点评|批改|反馈)|我的答案(?:是)?[:：]?",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _render_feedback(draft: PracticeFeedbackDraft) -> str:
        lines = ["### 本题点评"]
        if draft.correct_points:
            lines.extend(["", "**这次回答中正确的部分**"])
            lines.extend(f"- {item}" for item in draft.correct_points)
        if draft.correction:
            lines.extend(["", f"**最重要的修正**：{draft.correction}"])
        lines.extend(
            [
                "",
                f"**下一层提示**：{draft.next_hint}",
                "",
                f"**讲义依据**：第 {_format_pages(tuple(sorted(set(draft.source_pages))))} 页",
                "",
                "本反馈只针对当前答案，不保存答题记录，也不统计分数或整体掌握度。",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _render_feedback_fallback(problem: dict[str, Any], source_pages: list[int]) -> str:
        return "\n".join(
            [
                "### 本题反馈暂时降级",
                "",
                "当前未配置或未成功调用语义反馈模型，因此我不会对这次答案做不可靠判分。",
                "",
                f"**原题提示**：{problem.get('hint')}",
                f"**相关讲义页码**：第 {_format_pages(tuple(source_pages))} 页",
                f"**请补充**：{problem.get('deliverable')}",
                "",
                "补充后请继续携带同一个 practice ID；反馈仍只针对当前回答。",
            ]
        )

    @staticmethod
    def _reply(answer: str) -> LearningReply:
        return LearningReply(answer=answer, usage=normalized_usage())


def _latest_user_text(messages: list[ChatMessage]) -> str:
    return next(message.content for message in reversed(messages) if message.role == "user")


def _unwrap(output: dict[str, Any]) -> dict[str, Any]:
    candidate: Any = output
    for wrapper in ("result", "answer"):
        wrapped = candidate.get(wrapper) if isinstance(candidate, dict) else None
        if isinstance(wrapped, dict):
            candidate = wrapped
            break
    if not isinstance(candidate, dict):
        raise ValueError("model output must be an object")
    return candidate


def _expand_pages(value: str) -> list[int]:
    match = re.fullmatch(r"\s*(\d{1,4})(?:\s*[–-]\s*(\d{1,4}))?\s*", value)
    if not match:
        return []
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start < 1 or end < start or end - start > 500:
        return []
    return list(range(start, end + 1))


def _format_pages(pages: tuple[int, ...]) -> str:
    return "、".join(str(page) for page in pages)


def _query_tokens(text: str) -> set[str]:
    lowered = text.casefold()
    tokens = {token for token in re.findall(r"[a-z][a-z0-9_.-]{2,}", lowered)}
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    for size in (2, 3, 4):
        for index in range(max(0, len(chinese) - size + 1)):
            token = chinese[index : index + size]
            if token not in _QUERY_STOPWORDS and not any(stop in token for stop in _QUERY_STOPWORDS):
                tokens.add(token)
    return tokens
