from __future__ import annotations

from app.code_tutor.contracts import CodeArtifact
from app.code_tutor.error_parsers import parse_toolchain_errors


def test_toolchain_location_is_bound_to_artifact_and_real_line_range() -> None:
    artifact = CodeArtifact.create("int main() {\n  return missing;\n}\n", language="cpp")
    diagnostics = parse_toolchain_errors(
        "main.cpp:2:10: error: use of undeclared identifier 'missing'",
        artifact=artifact,
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].artifact_id == artifact.artifact_id
    assert diagnostics[0].line == diagnostics[0].end_line == 2


def test_toolchain_location_outside_artifact_is_rejected() -> None:
    artifact = CodeArtifact.create("package main\n", language="go")

    assert (
        parse_toolchain_errors(
            "main.go:99:2: undefined: missing",
            artifact=artifact,
        )
        == []
    )
