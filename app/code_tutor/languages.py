"""CSDIY-oriented language names, aliases, and static parser strategies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    language_id: str
    display_name: str
    aliases: tuple[str, ...]
    parser_key: str | None
    analysis_mode: str
    group: str

    @property
    def has_deterministic_parser(self) -> bool:
        return self.analysis_mode in {"python_ast", "tree_sitter"}


LANGUAGE_SPECS: tuple[LanguageSpec, ...] = (
    LanguageSpec("python", "Python", ("python", "py", "python3"), None, "python_ast", "通用编程"),
    LanguageSpec("c", "C", ("c", "h", "c99", "c11", "c17", "c23"), "c", "tree_sitter", "通用编程"),
    LanguageSpec(
        "cpp",
        "C++",
        ("cpp", "c++", "cc", "cxx", "hpp", "hxx", "c++17", "c++20", "c++23"),
        "cpp",
        "tree_sitter",
        "通用编程",
    ),
    LanguageSpec("java", "Java", ("java",), "java", "tree_sitter", "通用编程"),
    LanguageSpec(
        "javascript",
        "JavaScript",
        ("javascript", "js", "node", "nodejs"),
        "javascript",
        "tree_sitter",
        "通用编程",
    ),
    LanguageSpec(
        "typescript",
        "TypeScript",
        ("typescript", "ts"),
        "typescript",
        "tree_sitter",
        "通用编程",
    ),
    LanguageSpec("go", "Go", ("go", "golang"), "go", "tree_sitter", "通用编程"),
    LanguageSpec("rust", "Rust", ("rust", "rs"), "rust", "tree_sitter", "通用编程"),
    LanguageSpec("csharp", "C#", ("csharp", "c#", "cs"), "csharp", "tree_sitter", "通用编程"),
    LanguageSpec("ruby", "Ruby", ("ruby", "rb"), "ruby", "tree_sitter", "通用编程"),
    LanguageSpec("php", "PHP", ("php",), "php", "tree_sitter", "通用编程"),
    LanguageSpec("lua", "Lua", ("lua",), "lua", "tree_sitter", "通用编程"),
    LanguageSpec("cuda", "CUDA", ("cuda", "cu"), "cuda", "tree_sitter", "GPU 与 ML 系统"),
    LanguageSpec("ispc", "ISPC", ("ispc",), "ispc", "tree_sitter", "GPU 与 ML 系统"),
    LanguageSpec(
        "triton",
        "Triton",
        ("triton", "triton-lang"),
        None,
        "python_ast",
        "GPU 与 ML 系统",
    ),
    LanguageSpec("ptx", "PTX", ("ptx",), "asm", "tree_sitter", "GPU 与 ML 系统"),
    LanguageSpec("ocaml", "OCaml / ML", ("ocaml", "ml"), "ocaml", "tree_sitter", "函数式编程"),
    LanguageSpec("scheme", "Scheme", ("scheme",), "scheme", "tree_sitter", "函数式编程"),
    LanguageSpec("racket", "Racket", ("racket",), "racket", "tree_sitter", "函数式编程"),
    LanguageSpec("haskell", "Haskell", ("haskell", "hs"), "haskell", "tree_sitter", "函数式编程"),
    LanguageSpec("scala", "Scala", ("scala",), "scala", "tree_sitter", "函数式编程"),
    LanguageSpec("julia", "Julia", ("julia", "jl"), "julia", "tree_sitter", "科学计算与数据"),
    LanguageSpec("matlab", "MATLAB", ("matlab", "octave"), "matlab", "tree_sitter", "科学计算与数据"),
    LanguageSpec("sql", "SQL", ("sql",), "sql", "tree_sitter", "科学计算与数据"),
    LanguageSpec("html", "HTML", ("html", "htm"), "html", "tree_sitter", "Web 与脚本"),
    LanguageSpec("css", "CSS", ("css",), "css", "tree_sitter", "Web 与脚本"),
    LanguageSpec(
        "shell",
        "Shell / Bash",
        ("shell", "sh", "bash", "zsh"),
        "bash",
        "tree_sitter",
        "Web 与脚本",
    ),
    LanguageSpec(
        "powershell",
        "PowerShell",
        ("powershell", "pwsh", "ps1"),
        "powershell",
        "tree_sitter",
        "Web 与脚本",
    ),
    LanguageSpec("latex", "LaTeX", ("latex", "tex"), "latex", "tree_sitter", "文档与硬件"),
    LanguageSpec("verilog", "Verilog", ("verilog", "v"), "verilog", "tree_sitter", "文档与硬件"),
    LanguageSpec(
        "systemverilog",
        "SystemVerilog",
        ("systemverilog", "sv"),
        "verilog",
        "tree_sitter",
        "文档与硬件",
    ),
    LanguageSpec(
        "assembly",
        "Assembly（x86 / MIPS / RISC-V / LC-3）",
        ("asm", "assembly", "x86", "x86asm", "mips", "riscv", "risc-v", "lc3", "lc-3"),
        "asm",
        "tree_sitter",
        "文档与硬件",
    ),
    LanguageSpec("bcl", "BCL", ("bcl",), None, "model_only", "课程专用 DSL"),
    LanguageSpec("tirx", "TIRx", ("tirx",), None, "model_only", "课程专用 DSL"),
    LanguageSpec("lean", "Lean", ("lean", "lean4"), None, "model_only", "课程专用 DSL"),
    LanguageSpec("fstar", "F*", ("fstar", "f*"), None, "model_only", "课程专用 DSL"),
)


_LANGUAGES_BY_ID = {item.language_id: item for item in LANGUAGE_SPECS}
_ALIASES = {
    alias.casefold(): item
    for item in LANGUAGE_SPECS
    for alias in (item.language_id, *item.aliases)
}


def normalize_language_label(label: str | None) -> str | None:
    if label is None:
        return None
    normalized = label.strip().casefold()
    if not normalized:
        return None
    if normalized.startswith("{.") and normalized.endswith("}"):
        normalized = normalized[2:-1]
    normalized = normalized.split(maxsplit=1)[0]
    if normalized.startswith("language-"):
        normalized = normalized.removeprefix("language-")
    return normalized[:64] or None


def resolve_language(label: str | None) -> LanguageSpec | None:
    normalized = normalize_language_label(label)
    return _ALIASES.get(normalized) if normalized is not None else None


def get_language(language_id: str) -> LanguageSpec:
    return _LANGUAGES_BY_ID[language_id]


def grouped_languages(*, deterministic_only: bool = False) -> list[tuple[str, list[LanguageSpec]]]:
    grouped: dict[str, list[LanguageSpec]] = {}
    for item in LANGUAGE_SPECS:
        if deterministic_only and not item.has_deterministic_parser:
            continue
        grouped.setdefault(item.group, []).append(item)
    return list(grouped.items())


def tree_sitter_parser_keys() -> list[str]:
    return sorted(
        {
            item.parser_key
            for item in LANGUAGE_SPECS
            if item.analysis_mode == "tree_sitter" and item.parser_key is not None
        }
    )
