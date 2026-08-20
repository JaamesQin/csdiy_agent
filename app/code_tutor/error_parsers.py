"""Static parsers for user-supplied compiler and toolchain diagnostics."""

from __future__ import annotations

import re

from app.code_tutor.contracts import CodeArtifact, StaticDiagnostic


_LOCATION_PATTERNS = (
    ("clang_gcc", re.compile(r"^(?P<file>[^:\n]+):(?P<line>\d+):(?P<column>\d+):\s*(?:fatal\s+)?(?:error|warning):\s*(?P<message>.+)$", re.M)),
    ("rustc", re.compile(r"^\s*-->\s*(?P<file>[^:\n]+):(?P<line>\d+):(?P<column>\d+)", re.M)),
    ("go", re.compile(r"^(?P<file>[^:\n]+\.go):(?P<line>\d+):(?P<column>\d+):\s*(?P<message>.+)$", re.M)),
    ("java", re.compile(r"^(?P<file>[^:\n]+\.java):(?P<line>\d+):\s*(?:error|warning):\s*(?P<message>.+)$", re.M)),
    ("latex", re.compile(r"^l\.(?P<line>\d+)\s*(?P<message>.*)$", re.M)),
)
_CUDA = re.compile(r"(?P<message>(?:CUDA|nvcc).{0,200}(?:error|failed).*)", re.I)


def parse_toolchain_errors(
    error_text: str | None,
    *,
    artifact: CodeArtifact,
) -> list[StaticDiagnostic]:
    if not error_text:
        return []
    diagnostics: list[StaticDiagnostic] = []
    for parser_id, pattern in _LOCATION_PATTERNS:
        for match in pattern.finditer(error_text):
            line = int(match.group("line"))
            if line < 1 or (artifact.line_count and line > artifact.line_count):
                continue
            message = match.groupdict().get("message") or f"{parser_id} 报告了此位置。"
            diagnostics.append(
                StaticDiagnostic(
                    code=f"toolchain_{parser_id}",
                    message=message.strip()[:500],
                    line=line,
                    column=(
                        int(match.group("column"))
                        if match.groupdict().get("column")
                        else None
                    ),
                    end_line=line,
                    artifact_id=artifact.artifact_id,
                )
            )
            if len(diagnostics) >= 5:
                return diagnostics
    if not diagnostics and (match := _CUDA.search(error_text)):
        diagnostics.append(
            StaticDiagnostic(
                code="toolchain_cuda",
                message=match.group("message")[:500],
                artifact_id=artifact.artifact_id,
            )
        )
    return diagnostics
