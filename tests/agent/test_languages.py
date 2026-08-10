from __future__ import annotations

import pytest
import tree_sitter_language_pack

from app.code_tutor.languages import resolve_language, tree_sitter_parser_keys
from app.code_tutor.static_analysis import analyze_static_code


@pytest.mark.parametrize(
    ("alias", "language_id"),
    [
        ("python3", "python"),
        ("c++", "cpp"),
        ("cu", "cuda"),
        ("ispc", "ispc"),
        ("triton-lang", "triton"),
        ("tex", "latex"),
        ("ml", "ocaml"),
        ("risc-v", "assembly"),
        ("sv", "systemverilog"),
        ("pwsh", "powershell"),
        ("f*", "fstar"),
    ],
)
def test_language_aliases_are_normalized(alias: str, language_id: str) -> None:
    language = resolve_language(alias)

    assert language is not None
    assert language.language_id == language_id


def test_every_guaranteed_tree_sitter_parser_is_bundled() -> None:
    for parser_key in tree_sitter_parser_keys():
        assert tree_sitter_language_pack.get_parser(parser_key) is not None


@pytest.mark.parametrize(
    ("language", "code"),
    [
        ("python", "def f(x):\n    return x"),
        ("c", "int main(void) { return 0; }"),
        ("cpp", "template <typename T> T id(T x) { return x; }"),
        ("cuda", "__global__ void kernel(float *x) { x[threadIdx.x] = 0.0f; }"),
        ("ispc", "export void f(uniform int n) { foreach (i = 0 ... n) {} }"),
        ("triton", "import triton\n@triton.jit\ndef kernel(x):\n    return"),
        ("latex", "\\documentclass{article}\n\\begin{document}\nHi\n\\end{document}"),
    ],
)
def test_representative_supported_syntax_parses(language: str, code: str) -> None:
    result = analyze_static_code(code, language)

    assert result.deterministic_parser_used is True
    assert result.diagnostics == []


@pytest.mark.parametrize(
    ("language", "code"),
    [
        ("python", "def f(:\n    pass"),
        ("c", "int main( { return 0; }"),
        ("cpp", "template <class T void f() {}"),
        ("cuda", "__global__ void kernel( {"),
        ("ispc", "export void f(uniform int x {"),
        ("triton", "@triton.jit\ndef kernel(:\n    pass"),
        ("latex", "\\begin{document}\n{missing\n\\end{document}"),
    ],
)
def test_representative_syntax_errors_have_locations(language: str, code: str) -> None:
    result = analyze_static_code(code, language)

    assert result.deterministic_parser_used is True
    assert result.diagnostics
    assert result.diagnostics[0].code in {"python_syntax_error", "syntax_error"}
    assert result.diagnostics[0].line is not None
    assert result.diagnostics[0].column is not None


def test_course_specific_dsl_is_explicit_model_only() -> None:
    result = analyze_static_code("kernel foo", "tirx")

    assert result.language is not None
    assert result.language.language_id == "tirx"
    assert result.deterministic_parser_used is False
    assert result.diagnostics[0].code == "static_parser_unavailable"


def test_parser_failure_degrades_without_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_: str) -> object:
        raise RuntimeError("parser unavailable")

    monkeypatch.setattr(tree_sitter_language_pack, "get_parser", fail)

    result = analyze_static_code("int main(void) { return 0; }", "c")

    assert result.deterministic_parser_used is False
    assert result.diagnostics[0].code == "static_parser_unavailable"
