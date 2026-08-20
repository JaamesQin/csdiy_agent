"""Static-first code tutoring with validated StudyKit citations."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.agent.contracts import CodeTutorMode, CourseContext
from app.agent.model_support import normalized_usage
from app.catalog.studykits import StudyKitStore
from app.code_tutor.contracts import (
    CodeArtifact,
    CodeTutorRequest,
    CodeTutorContext,
    TutorCitation,
    TutorDraft,
    TutorResult,
    TutorHypothesis,
    TutorCodeBlock,
)
from app.code_tutor.error_parsers import parse_toolchain_errors
from app.code_tutor.languages import resolve_language
from app.code_tutor.static_analysis import StaticAnalysis, analyze_static_code
from app.generation.model import ModelError, StructuredModel
from app.profile.contracts import FactStatus, LearnerProfile

ACADEMIC_CONTEXT = re.compile(r"作业|课程项目|assignment|homework|lab\b", re.IGNORECASE)
FULL_SOLUTION = re.compile(
    r"完整答案|完整(?:的)?(?:代码|实现|解答)|全部代码|直接写|直接给.*答案|"
    r"可提交|帮我做完|full solution|solve it for me",
    re.IGNORECASE,
)
CODE_REQUIRED_MODES = {
    CodeTutorMode.DIAGNOSE,
    CodeTutorMode.REVIEW,
    CodeTutorMode.REPAIR,
    CodeTutorMode.REFACTOR,
}
GENERATED_BLOCK_KIND = {
    CodeTutorMode.GENERATE_EXAMPLE: "example",
    CodeTutorMode.REPAIR: "repair",
    CodeTutorMode.REFACTOR: "refactor",
    CodeTutorMode.DESIGN_TESTS: "tests",
}


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
        request: CodeTutorRequest | None = None,
        filename: str | None = None,
        previous_artifact: CodeArtifact | None = None,
    ) -> TutorResult:
        del user_id, conversation_id  # Reserved for future CodeArtifact persistence.
        request = request or CodeTutorRequest(
            mode=CodeTutorMode.DIAGNOSE,
            target_language=language,
        )
        mode = request.mode
        target_language = request.target_language or language

        if ACADEMIC_CONTEXT.search(question) and FULL_SOLUTION.search(question):
            return TutorResult(
                mode=mode,
                answer=(
                    "我不能代写可直接提交的完整作业答案。可以基于你的当前尝试帮助定位一个问题，"
                    "提供分层提示、最小测试，或生成不对应作业答案的独立概念示例。"
                ),
                next_checks=[
                    "说明当前实现在哪个输入上失败。",
                    "先写一个只覆盖该失败行为的最小测试。",
                ],
                next_attempt="提交你当前失败的最小实现和一个失败测试，我会从第一层提示开始。",
                ran_code=False,
                safety_notes=["学术诚信模式：未生成完整解答。", "代码未运行。"],
                usage=normalized_usage(),
            )

        if not code.strip() and (
            mode in CODE_REQUIRED_MODES or request.references_existing_code
        ):
            return TutorResult(
                mode=mode,
                answer=(
                    "这个辅导操作需要看到当前代码，或它所指的最近代码。请直接粘贴最小相关代码；"
                    "普通文本或 Markdown 代码块都可以。"
                ),
                next_checks=["保留能复现问题的最小输入、期望行为和实际行为。"],
                next_attempt="提供当前代码，以及你希望执行的解释、诊断、修复、审阅、重构或测试目标。",
                ran_code=False,
                safety_notes=["未收到可静态分析的代码，未运行任何内容。"],
                usage=normalized_usage(),
            )

        if target_language is None:
            unlabeled_analysis = analyze_static_code(code, None) if code.strip() else None
            unlabeled_artifact = (
                CodeArtifact.create(
                    code,
                    language=None,
                    filename=filename,
                    previous=previous_artifact,
                )
                if code.strip()
                else None
            )
            unlabeled_diagnostics = [
                item.model_copy(
                    update={
                        "artifact_id": (
                            unlabeled_artifact.artifact_id
                            if unlabeled_artifact is not None
                            else None
                        )
                    }
                )
                for item in (
                    unlabeled_analysis.diagnostics
                    if unlabeled_analysis is not None
                    else []
                )
            ]
            return TutorResult(
                mode=mode,
                answer=(
                    "请说明希望使用的编程语言，例如 C++、Python、Rust 或 Java。"
                    "我不会在语言不明确时默认选择 Python。"
                ),
                next_checks=["补充目标语言；不需要使用特定 Markdown 格式。"],
                next_attempt="告诉我目标语言后，我会继续当前代码辅导任务。",
                diagnostics=unlabeled_diagnostics,
                ran_code=False,
                safety_notes=["语言尚未确认，未生成或运行代码。"],
                usage=normalized_usage(),
                artifact=unlabeled_artifact,
            )

        analysis = analyze_static_code(code, language or target_language)
        artifact = (
            CodeArtifact.create(
                code,
                language=analysis.normalized_language,
                filename=filename,
                previous=previous_artifact,
            )
            if code.strip()
            else None
        )
        diagnostics = [
            item.model_copy(
                update={
                    "artifact_id": artifact.artifact_id if artifact is not None else None,
                    "end_line": item.end_line or item.line,
                }
            )
            for item in (analysis.diagnostics if artifact is not None else [])
        ]
        if artifact is not None:
            diagnostics.extend(parse_toolchain_errors(error_text, artifact=artifact))

        context = self._build_context(
            course_context=course_context,
            code=code,
            analysis=analysis,
            error_text=error_text,
            question=question,
            profile=profile,
            request=request,
        )
        deterministic_checks = (
            self._deterministic_checks(analysis, error_text)
            if artifact is not None
            else ["使用目标语言的本地工具链自行编译或检查，并核对预期行为。"]
        )
        fallback_hypotheses = [item.message for item in diagnostics]
        draft: TutorDraft | None = None
        usage = normalized_usage()

        if self.model is not None:
            try:
                response = await self.model.generate_json(
                    system_prompt=(
                        "你是 CoursePilot Code Coach，支持生成示例、解释、诊断、审阅、修复、"
                        "重构和测试设计。只做静态推理，不得声称编译、运行或测试了代码。"
                        "必须按照 context.language 分析对应语言，不得把非 Python 代码当作 Python。"
                        "生成示例时默认给一个自包含、设计为最小可运行的例子；预期行为必须明确"
                        "标为预期而不是运行结果。只有用户明确要求额外源文件或测试块时才返回多个"
                        " code_blocks。修复、重构和测试设计应把代码放入 code_blocks。"
                        "按当前 mode 提供结论、必要解释、验证步骤和下一次尝试。"
                        "只能引用 allowed_citations 中的 citation_id，不得输出完整作业解答。"
                        "只输出 JSON object。"
                    ),
                    user_prompt=json.dumps(
                        {
                            "context": context.model_dump(),
                            "static_diagnostics": [item.model_dump() for item in diagnostics],
                            "output_contract": {
                                "observation": "string",
                                "code_blocks": [
                                    {
                                        "kind": "example | repair | refactor | tests",
                                        "language": "context.target_language",
                                        "filename": "basename or null",
                                        "code": "complete code",
                                        "explanation": "string",
                                        "expected_behavior": "expected, not observed, behavior",
                                    }
                                ],
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
                draft = self._validate_model_draft(draft, request)
            except (ModelError, ValidationError, ValueError):
                draft = None

        allowed = {citation.citation_id: citation for citation in context.allowed_citations}
        if draft is None:
            citations = context.allowed_citations[:2]
        else:
            # Tutor citations are a resource list, not prose claims. Invalid IDs
            # are removed here; claim partitions use enforce_provenance atomically.
            citations = [allowed[item] for item in draft.citation_ids if item in allowed]
        code_blocks: list[TutorCodeBlock] = [] if draft is None else draft.code_blocks
        generated_notes = self._generated_code_notes(code_blocks)
        if draft is None:
            if mode in {
                CodeTutorMode.GENERATE_EXAMPLE,
                CodeTutorMode.EXPLAIN,
                CodeTutorMode.REPAIR,
                CodeTutorMode.REFACTOR,
                CodeTutorMode.DESIGN_TESTS,
            }:
                answer = (
                    "代码辅导模型当前不可用，或返回的代码没有通过结构与静态语法校验，"
                    "因此本轮没有展示未经验证的生成内容。"
                )
            else:
                answer = (
                    "已完成静态检查。优先处理下面的确定性诊断，再用最小输入验证行为；"
                    "当前未配置或未成功调用辅导模型，因此没有补充语义推断。"
                )
            hypotheses = fallback_hypotheses or [
                (
                    f"{analysis.display_name} 解析器未定位到结构性语法错误；"
                    "这不等价于通过编译，仍需结合输入、期望行为和工具链错误输出缩小范围。"
                )
            ]
            next_checks = deterministic_checks
            next_attempt = "按验证步骤缩小到第一个与期望不一致的中间状态。"
            if artifact is None:
                hypotheses = []
                next_attempt = "保留目标语言和需求后稍后重试；本轮没有生成代码。"
            safety_notes = ["代码仅做静态分析，未运行。"]
        else:
            answer = draft.observation
            hypotheses = draft.diagnostic_hypotheses or fallback_hypotheses
            next_checks = self._dedupe([*deterministic_checks, *draft.next_checks])
            next_attempt = draft.next_attempt
            safety_notes = self._dedupe(
                [*draft.safety_notes, *generated_notes, "代码仅做静态分析，未运行。"]
            )

        return TutorResult(
            mode=mode,
            answer=answer,
            code_blocks=code_blocks,
            citations=citations,
            diagnostics=diagnostics,
            diagnostic_hypotheses=hypotheses,
            next_checks=next_checks,
            next_attempt=next_attempt,
            ran_code=False,
            safety_notes=safety_notes,
            usage=usage,
            artifact=artifact,
            bound_hypotheses=(
                self._bind_hypotheses(artifact, diagnostics, hypotheses, next_checks)
                if artifact is not None
                else []
            ),
        )

    @staticmethod
    def _bind_hypotheses(
        artifact: CodeArtifact,
        diagnostics: list,
        hypotheses: list[str],
        next_checks: list[str] | None = None,
    ) -> list[TutorHypothesis]:
        bound: list[TutorHypothesis] = []
        checks = next_checks or []
        for index, text in enumerate(hypotheses[:3]):
            diagnostic = diagnostics[index] if index < len(diagnostics) else None
            line = diagnostic.line if diagnostic is not None else None
            if line is None:
                line = 1 if artifact.line_count else 1
            line = max(1, min(line, max(artifact.line_count, 1)))
            end_line = (
                diagnostic.end_line
                if diagnostic is not None and diagnostic.end_line is not None
                else line
            )
            end_line = max(line, min(end_line, max(artifact.line_count, line)))
            support_id = diagnostic.code if diagnostic is not None else "model_hypothesis"
            bound.append(
                TutorHypothesis(
                    text=text,
                    artifact_id=artifact.artifact_id,
                    language=artifact.language,
                    start_line=line,
                    end_line=end_line,
                    support_id=support_id,
                    verification_step=(
                        checks[index]
                        if index < len(checks)
                        else "用最小输入验证该假设，并比较期望与实际中间状态。"
                    ),
                    pending_verification=diagnostic is None,
                )
            )
        return bound

    @staticmethod
    def _parse_model_draft(output: dict[str, Any]) -> TutorDraft:
        """Accept harmless provider formatting drift without widening the contract.

        Some OpenAI-compatible models add explanatory top-level fields or wrap the
        requested object in ``result``/``answer``. We retain only the seven
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
            "code_blocks",
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

    @staticmethod
    def _validate_model_draft(
        draft: TutorDraft, request: CodeTutorRequest
    ) -> TutorDraft:
        """Validate generated code without widening the one-call model budget."""

        target = resolve_language(request.target_language)
        normalized_blocks: list[TutorCodeBlock] = []
        for block in draft.code_blocks:
            spec = resolve_language(block.language)
            if spec is None:
                raise ValueError("generated code uses an unsupported language")
            if target is not None and spec.language_id != target.language_id:
                raise ValueError("generated code language does not match the request")
            if not block.explanation.strip() or not block.expected_behavior.strip():
                raise ValueError(
                    "generated code must explain its purpose and expected behavior"
                )
            if block.filename and not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", block.filename
            ):
                raise ValueError("generated code filename must be a safe basename")
            analysis = analyze_static_code(block.code, spec.language_id)
            if any(
                item.code in {"python_syntax_error", "syntax_error"}
                for item in analysis.diagnostics
            ):
                raise ValueError("generated code failed deterministic syntax validation")
            normalized_blocks.append(
                block.model_copy(update={"language": spec.language_id})
            )

        required_kind = GENERATED_BLOCK_KIND.get(request.mode)
        if required_kind is not None and not any(
            block.kind == required_kind for block in normalized_blocks
        ):
            raise ValueError("code tutor response omitted the required code block")
        return draft.model_copy(update={"code_blocks": normalized_blocks})

    @staticmethod
    def _generated_code_notes(blocks: list[TutorCodeBlock]) -> list[str]:
        notes: list[str] = []
        for block in blocks:
            analysis = analyze_static_code(block.code, block.language)
            if analysis.deterministic_parser_used:
                notes.append(
                    f"{analysis.display_name} 代码通过了确定性语法结构检查，但未编译或运行。"
                )
            else:
                notes.append(
                    f"{analysis.display_name} 暂无可用的确定性解析结果，本段仅为模型静态建议。"
                )
        return list(dict.fromkeys(notes))

    def _build_context(
        self,
        *,
        course_context: CourseContext | None,
        code: str,
        analysis: StaticAnalysis,
        error_text: str | None,
        question: str,
        profile: LearnerProfile,
        request: CodeTutorRequest,
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
            mode=request.mode,
            course_context=course_context,
            language=analysis.normalized_language,
            target_language=request.target_language or analysis.normalized_language,
            language_display_name=analysis.display_name,
            deterministic_parser_used=analysis.deterministic_parser_used,
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
        query_tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", lowered))
        scored: list[tuple[int, dict[str, Any]]] = []
        for concept in document.get("core_concepts", []):
            searchable = " ".join(
                str(concept.get(key, "")).lower()
                for key in ("id", "term_en", "term_zh", "explanation", "intuition")
            )
            concept_tokens = set(
                re.findall(r"[a-z][a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", searchable)
            )
            exact = sum(token in searchable for token in query_tokens)
            prefix = sum(
                1
                for query_token in query_tokens
                for concept_token in concept_tokens
                if min(len(query_token), len(concept_token)) >= 4
                and _common_prefix(query_token, concept_token) >= 4
            )
            score = exact * 3 + prefix
            if score:
                scored.append((score, concept))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [concept for _, concept in scored[:2]]

    @staticmethod
    def _deterministic_checks(
        analysis: StaticAnalysis, error_text: str | None
    ) -> list[str]:
        checks: list[str] = []
        diagnostics = analysis.diagnostics
        language_required = next(
            (item for item in diagnostics if item.code == "language_required"), None
        )
        parser_unavailable = next(
            (item for item in diagnostics if item.code == "static_parser_unavailable"),
            None,
        )
        syntax = next(
            (
                item
                for item in diagnostics
                if item.code in {"python_syntax_error", "syntax_error"}
            ),
            None,
        )
        if language_required:
            checks.append("给代码围栏补充准确的语言标签后重新提交。")
        elif parser_unavailable:
            checks.append("附上该语言编译器、解释器或课程工具链的原始错误输出。")
        if syntax:
            checks.append(
                f"先修复第 {syntax.line or '?'} 行附近的语法错误，再重新做静态检查。"
            )
        elif not language_required and not parser_unavailable:
            checks.append("构造一个最小输入，分别写下期望输出与实际输出。")
            checks.append("在关键边界打印或断言类型、shape 和索引范围。")
        if error_text:
            checks.append("从原始错误输出的首个根因位置开始，回看对应的用户代码行。")
        return checks

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in items if item.strip()))


def _common_prefix(left: str, right: str) -> int:
    count = 0
    for left_char, right_char in zip(left, right):
        if left_char != right_char:
            break
        count += 1
    return count


def render_tutor_result(result: TutorResult) -> str:
    block_headings = {
        CodeTutorMode.GENERATE_EXAMPLE: "### 代码示例",
        CodeTutorMode.REPAIR: "### 修复版本",
        CodeTutorMode.REFACTOR: "### 重构版本",
        CodeTutorMode.DESIGN_TESTS: "### 测试代码",
    }
    summary_headings = {
        CodeTutorMode.GENERATE_EXAMPLE: "### 说明",
        CodeTutorMode.EXPLAIN: "### 代码讲解",
        CodeTutorMode.REVIEW: "### 审阅结论",
        CodeTutorMode.REPAIR: "### 修复说明",
        CodeTutorMode.REFACTOR: "### 重构说明",
        CodeTutorMode.DESIGN_TESTS: "### 测试设计",
    }
    lines: list[str] = []
    block_heading = block_headings.get(result.mode)
    if block_heading and result.code_blocks:
        lines.append(block_heading)
        for block in result.code_blocks:
            if block.filename:
                lines.extend(["", f"**{block.filename}**"])
            lines.extend(["", _render_code_block(block)])
            if block.explanation:
                lines.extend(["", f"说明：{block.explanation}"])
        lines.extend(["", summary_headings[result.mode], result.answer])
        expected = [block for block in result.code_blocks if block.expected_behavior]
        if expected:
            lines.extend(["", "### 预期行为（未运行）"])
            for block in expected:
                label = f"{block.filename}：" if block.filename else ""
                lines.append(f"- {label}{block.expected_behavior}")
    else:
        lines.extend([summary_headings.get(result.mode, "### 观察"), result.answer])
    if result.diagnostics:
        deterministic = any(
            item.code not in {"language_required", "static_parser_unavailable"}
            for item in result.diagnostics
        )
        heading = "### 确定性静态诊断" if deterministic else "### 静态分析说明"
        lines.extend(["", heading])
        for item in result.diagnostics:
            location = f"（第 {item.line} 行" if item.line is not None else ""
            if location and item.column is not None:
                location += f"，第 {item.column} 列"
            if location:
                location += "）"
            lines.append(f"- {item.message}{location}")
    hypothesis_heading = {
        CodeTutorMode.DIAGNOSE: "### 诊断假设",
        CodeTutorMode.REVIEW: "### 审阅发现",
        CodeTutorMode.REPAIR: "### 修复依据",
        CodeTutorMode.REFACTOR: "### 改进依据",
    }.get(result.mode)
    if hypothesis_heading:
        lines.extend(["", hypothesis_heading])
        hypotheses = result.diagnostic_hypotheses
        lines.extend(
            f"- {item}" for item in hypotheses or ["目前没有足够信息形成具体假设。"]
        )
    if result.next_checks:
        checks_heading = (
            "### 验证步骤"
            if result.mode in {CodeTutorMode.DIAGNOSE, CodeTutorMode.REVIEW}
            else "### 自查步骤"
        )
        lines.extend(["", checks_heading])
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


def _render_code_block(block: TutorCodeBlock) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", block.code)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{block.language}\n{block.code}\n{fence}"
