"""Deterministic, non-executing syntax analysis for supported tutor languages."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from app.code_tutor.contracts import StaticDiagnostic
from app.code_tutor.languages import (
    LanguageSpec,
    normalize_language_label,
    resolve_language,
)

MAX_SYNTAX_DIAGNOSTICS = 5


@dataclass(frozen=True, slots=True)
class StaticAnalysis:
    language: LanguageSpec | None
    submitted_language: str | None
    diagnostics: list[StaticDiagnostic]
    deterministic_parser_used: bool

    @property
    def normalized_language(self) -> str | None:
        if self.language is not None:
            return self.language.language_id
        return self.submitted_language

    @property
    def display_name(self) -> str:
        if self.language is not None:
            return self.language.display_name
        return self.submitted_language or "未知语言"


def analyze_static_code(code: str, language: str | None) -> StaticAnalysis:
    submitted = normalize_language_label(language)
    spec = resolve_language(language)
    if submitted is None:
        return StaticAnalysis(
            language=None,
            submitted_language=None,
            diagnostics=[
                StaticDiagnostic(
                    code="language_required",
                    message=(
                        "未标明代码语言，无法安全选择语法解析器；请在 Markdown 代码围栏中"
                        "写明语言，例如 ```cpp、```cuda 或 ```latex。"
                    ),
                )
            ],
            deterministic_parser_used=False,
        )
    if spec is None:
        return StaticAnalysis(
            language=None,
            submitted_language=submitted,
            diagnostics=[
                StaticDiagnostic(
                    code="static_parser_unavailable",
                    message=f"未找到 {submitted} 的确定性语法解析器，仅能提供模型静态建议。",
                )
            ],
            deterministic_parser_used=False,
        )
    if spec.analysis_mode == "model_only":
        return StaticAnalysis(
            language=spec,
            submitted_language=submitted,
            diagnostics=[
                StaticDiagnostic(
                    code="static_parser_unavailable",
                    message=f"{spec.display_name} 暂无可靠的确定性语法解析器，仅能提供模型静态建议。",
                )
            ],
            deterministic_parser_used=False,
        )
    if spec.analysis_mode == "python_ast":
        return StaticAnalysis(
            language=spec,
            submitted_language=submitted,
            diagnostics=_python_diagnostics(code, spec),
            deterministic_parser_used=True,
        )
    diagnostics, parser_used = _tree_sitter_diagnostics(code, spec)
    return StaticAnalysis(
        language=spec,
        submitted_language=submitted,
        diagnostics=diagnostics,
        deterministic_parser_used=parser_used,
    )


def _python_diagnostics(code: str, spec: LanguageSpec) -> list[StaticDiagnostic]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [
            StaticDiagnostic(
                code="python_syntax_error" if spec.language_id == "python" else "syntax_error",
                message=exc.msg,
                line=exc.lineno,
                column=exc.offset,
            )
        ]

    diagnostics: list[StaticDiagnostic] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defaults = [
                *node.args.defaults,
                *[item for item in node.args.kw_defaults if item],
            ]
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
        if (
            isinstance(node, ast.Compare)
            and any(isinstance(operator, (ast.Eq, ast.NotEq)) for operator in node.ops)
            and any(
                isinstance(item, ast.Constant) and item.value is None
                for item in [node.left, *node.comparators]
            )
        ):
            diagnostics.append(
                StaticDiagnostic(
                    code="none_identity",
                    message="与 None 比较应优先使用 is / is not。",
                    line=node.lineno,
                    column=node.col_offset + 1,
                )
            )
    return diagnostics


def _tree_sitter_diagnostics(
    code: str, spec: LanguageSpec
) -> tuple[list[StaticDiagnostic], bool]:
    try:
        from tree_sitter_language_pack import get_parser

        parser = get_parser(spec.parser_key or spec.language_id)
        tree = parser.parse(code.encode("utf-8"))
    except (ImportError, KeyError, OSError, RuntimeError, ValueError):
        return (
            [
                StaticDiagnostic(
                    code="static_parser_unavailable",
                    message=f"{spec.display_name} 语法解析器当前不可用，仅能提供模型静态建议。",
                )
            ],
            False,
        )

    issues: list[Any] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.is_error or node.is_missing:
            issues.append(node)
        if node.has_error:
            stack.extend(reversed(node.children))

    unique: dict[tuple[int, int, bool], Any] = {}
    for node in issues:
        point = node.start_point
        unique.setdefault((point.row, point.column, bool(node.is_missing)), node)
    ordered = sorted(
        unique.values(),
        key=lambda item: (item.start_point.row, item.start_point.column, not item.is_missing),
    )[:MAX_SYNTAX_DIAGNOSTICS]

    diagnostics: list[StaticDiagnostic] = []
    for node in ordered:
        point = node.start_point
        detail = (
            f"缺少必要的 {node.type} 语法结构。"
            if node.is_missing
            else "解析器在此处发现不完整或无效的语法结构。"
        )
        diagnostics.append(
            StaticDiagnostic(
                code="syntax_error",
                message=f"{spec.display_name} {detail}",
                line=point.row + 1,
                column=_character_column(code, point.row, point.column),
            )
        )
    return diagnostics, True


def _character_column(code: str, row: int, byte_column: int) -> int:
    lines = code.splitlines()
    if row >= len(lines):
        return byte_column + 1
    prefix = lines[row].encode("utf-8")[:byte_column]
    return len(prefix.decode("utf-8", errors="ignore")) + 1
