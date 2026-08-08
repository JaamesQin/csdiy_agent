"""Static-first code tutoring with validated StudyKit citations."""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from pydantic import ValidationError

from app.agent.contracts import CourseContext
from app.agent.model_support import normalized_usage
from app.catalog.studykits import StudyKitStore
from app.code_tutor.contracts import (
    CodeTutorContext,
    StaticDiagnostic,
    TutorCitation,
    TutorDraft,
    TutorResult,
)
from app.generation.model import ModelError, StructuredModel
from app.profile.contracts import FactStatus, LearnerProfile

ACADEMIC_CONTEXT = re.compile(r"作业|课程项目|assignment|homework|lab\b", re.IGNORECASE)
FULL_SOLUTION = re.compile(
    r"完整答案|全部代码|直接写|直接给.*答案|可提交|帮我做完|full solution|solve it for me",
    re.IGNORECASE,
)


class CodeTutorService:
    def __init__(
        self,
        store: StudyKitStore,
        model: StructuredModel | None = None,
    ) -> None:
        self.store = store
        self.model = model

    async def tutor_code(
        self,
        *,
        user_id: str | None,
        conversation_id: str | None,
        course_context: CourseContext | None,
        code: str,
        language: str | None,
        error_text: str | None,
        question: str,
        profile: LearnerProfile,
    ) -> TutorResult:
        del user_id, conversation_id  # Reserved for future CodeArtifact persistence.
        if not code.strip():
            return TutorResult(
                answer="请粘贴最小相关代码，并用 Markdown 代码围栏标出；若有报错，也请附上完整 traceback。",
                next_checks=["保留能复现问题的最小输入、期望行为和实际行为。"],
                next_attempt="提供最小代码、输入、期望行为和实际行为。",
                ran_code=False,
                safety_notes=["未收到可静态分析的代码，未运行任何内容。"],
                usage=normalized_usage(),
            )

        diagnostics = self._static_diagnostics(code, language)
        if ACADEMIC_CONTEXT.search(question) and FULL_SOLUTION.search(question):
            return TutorResult(
                answer=(
                    "我不能代写可直接提交的完整作业答案。可以基于你的当前尝试帮助定位一个问题，"
                    "并给出最小测试和下一层提示。"
                ),
                diagnostics=diagnostics,
                next_checks=[
                    "说明当前实现在哪个输入上失败。",
                    "先写一个只覆盖该失败行为的最小测试。",
                ],
                next_attempt="提交你当前失败的最小实现和一个失败测试，我会从第一层提示开始。",
                ran_code=False,
                safety_notes=["学术诚信模式：未生成完整解答。", "代码仅做静态分析，未运行。"],
                usage=normalized_usage(),
            )

        context = self._build_context(
            course_context=course_context,
            code=code,
            language=language,
            error_text=error_text,
            question=question,
            profile=profile,
        )
        deterministic_checks = self._deterministic_checks(diagnostics, error_text)
        fallback_hypotheses = [item.message for item in diagnostics]
        draft: TutorDraft | None = None
        usage = normalized_usage()

        if self.model is not None:
            try:
                response = await self.model.generate_json(
                    system_prompt=(
                        "你是 CoursePilot Code Coach。只做静态分析，不得声称运行了代码。"
                        "按观察、诊断假设、验证步骤和下一次尝试提供分层提示。"
                        "只能引用 allowed_citations 中的 citation_id，不得输出完整作业解答。"
                        "只输出 JSON object。"
                    ),
                    user_prompt=json.dumps(
                        {
                            "context": context.model_dump(),
                            "static_diagnostics": [item.model_dump() for item in diagnostics],
                            "output_contract": {
                                "observation": "string",
                                "diagnostic_hypotheses": ["string"],
                                "next_checks": ["string"],
                                "next_attempt": "string",
                                "citation_ids": ["allowed id only"],
                                "safety_notes": ["string"],
                            },
                        },
                        ensure_ascii=False,
                    ),
                    thinking_enabled=False,
                    max_tokens=4096,
                    timeout_seconds=60,
                )
                usage = normalized_usage(response.usage)
                draft = self._parse_model_draft(response.output)
            except (ModelError, ValidationError, ValueError):
                draft = None

        allowed = {citation.citation_id: citation for citation in context.allowed_citations}
        citations = (
            [allowed[item] for item in draft.citation_ids if item in allowed]
            if draft is not None
            else context.allowed_citations[:2]
        )
        if draft is None:
            answer = (
                "已完成静态检查。优先处理下面的确定性诊断，再用最小输入验证行为；"
                "当前未配置或未成功调用辅导模型，因此没有补充语义推断。"
            )
            hypotheses = fallback_hypotheses or [
                "语法可以被 Python AST 解析；仍需结合输入、期望行为和错误输出缩小问题范围。"
            ]
            next_checks = deterministic_checks
            next_attempt = "按验证步骤缩小到第一个与期望不一致的中间状态。"
            safety_notes = ["代码仅做静态分析，未运行。"]
        else:
            answer = draft.observation
            hypotheses = draft.diagnostic_hypotheses or fallback_hypotheses
            next_checks = self._dedupe([*deterministic_checks, *draft.next_checks])
            next_attempt = draft.next_attempt
            safety_notes = self._dedupe([*draft.safety_notes, "代码仅做静态分析，未运行。"])

        return TutorResult(
            answer=answer,
            citations=citations,
            diagnostics=diagnostics,
            diagnostic_hypotheses=hypotheses,
            next_checks=next_checks,
            next_attempt=next_attempt,
            ran_code=False,
            safety_notes=safety_notes,
            usage=usage,
        )

    @staticmethod
    def _parse_model_draft(output: dict[str, Any]) -> TutorDraft:
        """Accept harmless provider formatting drift without widening the contract.

        Some OpenAI-compatible models add explanatory top-level fields or wrap the
        requested object in ``result``/``answer``. We retain only the six
        learner-facing fields and let Pydantic reject missing or mistyped content.
        """

        candidate: Any = output
        for wrapper in ("result", "answer"):
            wrapped = candidate.get(wrapper) if isinstance(candidate, dict) else None
            if isinstance(wrapped, dict):
                candidate = wrapped
                break
        if not isinstance(candidate, dict):
            raise ValueError("code tutor output must be an object")

        allowed = {
            "observation",
            "diagnostic_hypotheses",
            "next_checks",
            "next_attempt",
            "citation_ids",
            "safety_notes",
        }
        normalized = {key: value for key, value in candidate.items() if key in allowed}
        for key in (
            "diagnostic_hypotheses",
            "next_checks",
            "citation_ids",
            "safety_notes",
        ):
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = [value]
        return TutorDraft.model_validate(normalized)

    def _build_context(
        self,
        *,
        course_context: CourseContext | None,
        code: str,
        language: str | None,
        error_text: str | None,
        question: str,
        profile: LearnerProfile,
    ) -> CodeTutorContext:
        document: dict[str, Any] | None = None
        if course_context is not None and course_context.unit_id is not None:
            document = self.store.get_ready(
                course_context.course_id,
                course_context.course_version,
                course_context.unit_id,
            )

        objectives: list[str] = []
        concepts: list[dict[str, object]] = []
        practice: dict[str, object] | None = None
        allowed: list[TutorCitation] = []
        if document is not None:
            objectives = [
                str(item["objective"])
                for item in document.get("learning_objectives", [])[:3]
            ]
            selected = self._select_concepts(document, f"{question}\n{code}\n{error_text or ''}")
            for concept_index, concept in enumerate(selected, start=1):
                public_concept = {
                    key: concept[key]
                    for key in ("id", "term_en", "term_zh", "explanation")
                    if key in concept
                }
                concepts.append(public_concept)
                for page_index, citation in enumerate(concept.get("citations", []), start=1):
                    citation_id = f"concept-{concept_index}-page-{page_index}"
                    allowed.append(
                        TutorCitation(
                            citation_id=citation_id,
                            source_id=str(citation["source_id"]),
                            page=int(citation["page"]),
                            label=f"{document['title']}，第 {citation['page']} 页",
                        )
                    )
            raw_practice = next(
                (
                    item
                    for item in document.get("practice", [])
                    if item.get("setup_code") or item.get("practice_type") == "code_reading"
                ),
                None,
            )
            if raw_practice is not None:
                practice = {
                    key: raw_practice[key]
                    for key in ("id", "question", "hint", "deliverable", "setup", "setup_code")
                    if key in raw_practice
                }

        learner_constraints: dict[str, object] = {}
        for fact in profile.facts:
            if fact.status is not FactStatus.CONFIRMED:
                continue
            if fact.field_name in {
                "background",
                "weekly_minutes",
                "preferred_explanation_style",
            }:
                learner_constraints.setdefault(fact.field_name, [])
                values = learner_constraints[fact.field_name]
                if isinstance(values, list):
                    values.append(fact.value)

        return CodeTutorContext(
            course_context=course_context,
            language=language,
            code=code,
            error_text=error_text,
            question=question,
            learning_objectives=objectives,
            concepts=concepts,
            practice=practice,
            allowed_citations=allowed,
            learner_constraints=learner_constraints,
        )

    @staticmethod
    def _select_concepts(document: dict[str, Any], text: str) -> list[dict[str, Any]]:
        lowered = text.lower()
        aliases = {
            "backward": "backpropagation",
            ".backward": "backpropagation",
            "grad": "gradient",
            "attention": "attention",
            "softmax": "softmax",
            "shape": "tensor",
        }
        expanded = lowered + " " + " ".join(
            target for source, target in aliases.items() if source in lowered
        )
        scored: list[tuple[int, dict[str, Any]]] = []
        for concept in document.get("core_concepts", []):
            terms = [
                str(concept.get("term_en", "")).lower(),
                str(concept.get("term_zh", "")).lower(),
                str(concept.get("id", "")).lower().replace("concept-", "").replace("-", " "),
            ]
            score = sum(1 for term in terms if term and term in expanded)
            if score:
                scored.append((score, concept))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [concept for _, concept in scored[:2]]

    @staticmethod
    def _static_diagnostics(code: str, language: str | None) -> list[StaticDiagnostic]:
        normalized_language = (language or "python").lower()
        if normalized_language not in {"py", "python", "python3"}:
            return [
                StaticDiagnostic(
                    code="static_language_only",
                    message=f"{language or '未知语言'} 未进入确定性语法解析，仅能提供模型静态建议。",
                )
            ]
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return [
                StaticDiagnostic(
                    code="python_syntax_error",
                    message=exc.msg,
                    line=exc.lineno,
                    column=exc.offset,
                )
            ]

        diagnostics: list[StaticDiagnostic] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = [*node.args.defaults, *[item for item in node.args.kw_defaults if item]]
                if any(isinstance(item, (ast.List, ast.Dict, ast.Set)) for item in defaults):
                    diagnostics.append(
                        StaticDiagnostic(
                            code="mutable_default",
                            message="函数使用了可变默认参数，多个调用可能共享同一对象。",
                            line=node.lineno,
                            column=node.col_offset + 1,
                        )
                    )
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                diagnostics.append(
                    StaticDiagnostic(
                        code="bare_except",
                        message="裸 except 会吞掉与预期无关的异常，建议缩小异常类型。",
                        line=node.lineno,
                        column=node.col_offset + 1,
                    )
                )
            if isinstance(node, ast.Compare) and any(
                isinstance(operator, (ast.Eq, ast.NotEq)) for operator in node.ops
            ) and any(isinstance(item, ast.Constant) and item.value is None for item in [node.left, *node.comparators]):
                diagnostics.append(
                    StaticDiagnostic(
                        code="none_identity",
                        message="与 None 比较应优先使用 is / is not。",
                        line=node.lineno,
                        column=node.col_offset + 1,
                    )
                )
        return diagnostics

    @staticmethod
    def _deterministic_checks(
        diagnostics: list[StaticDiagnostic], error_text: str | None
    ) -> list[str]:
        checks: list[str] = []
        syntax = next((item for item in diagnostics if item.code == "python_syntax_error"), None)
        if syntax:
            checks.append(f"先修复第 {syntax.line or '?'} 行附近的语法错误，再重新做静态检查。")
        else:
            checks.append("构造一个最小输入，分别写下期望输出与实际输出。")
            checks.append("在关键边界打印或断言类型、shape 和索引范围。")
        if error_text:
            checks.append("从 traceback 最后一行开始定位异常类型，再回看首个属于用户代码的栈帧。")
        return checks

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in items if item.strip()))


def render_tutor_result(result: TutorResult) -> str:
    lines = ["### 观察", result.answer]
    if result.diagnostics:
        lines.extend(["", "### 确定性静态诊断"])
        for item in result.diagnostics:
            location = f"（第 {item.line} 行" if item.line is not None else ""
            if location and item.column is not None:
                location += f"，第 {item.column} 列"
            if location:
                location += "）"
            lines.append(f"- {item.message}{location}")
    lines.extend(["", "### 诊断假设"])
    hypotheses = result.diagnostic_hypotheses
    lines.extend(
        f"- {item}" for item in hypotheses or ["目前没有足够信息形成具体假设。"]
    )
    lines.extend(["", "### 验证步骤"])
    lines.extend(f"- {item}" for item in result.next_checks)
    if result.next_attempt:
        lines.extend(["", "### 下一次尝试", result.next_attempt])
    if result.citations:
        lines.extend(["", "### 资料依据"])
        lines.extend(f"- {item.label}" for item in result.citations)
    lines.extend(["", "### 限制"])
    lines.extend(f"- {item}" for item in result.safety_notes)
    lines.append(f"- ran_code={str(result.ran_code).lower()}")
    return "\n".join(lines).strip()
