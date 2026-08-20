"""Shared, deterministic understanding of learner-authored chat turns.

The helpers in this module only identify intent signals and ephemeral artifacts.
They do not establish course identity, persist learner content, or execute code.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.agent.contracts import CodeTutorMode, SemanticCodeArtifact, SemanticCodeRequest
from app.code_tutor.contracts import CodeTutorRequest
from app.code_tutor.languages import (
    LANGUAGE_SPECS,
    get_language,
    normalize_language_label,
    resolve_language,
)
from app.protocol.schemas import ChatMessage


OUTPUT_FENCE_LABELS = {"console", "error", "errors", "log", "output", "text", "traceback"}
FENCE_BLOCK = re.compile(r"```(?P<body>.*?)```", re.DOTALL)
CODE_REQUEST = re.compile(
    r"(?:代码(?:辅导|分析|审阅|检查|有什么问题|哪里有问题)|"
    r"(?:这段|以下|下面的?).{0,8}代码|帮我.{0,8}(?:调试|debug)|"
    r"静态分析|编译(?:错误|失败)|syntaxerror|traceback|"
    r"示例代码|代码示例|example\s+code|sample\s+code|"
    r"逐行解释.{0,8}代码|修(?:好|复|正).{0,8}代码|"
    r"重构.{0,8}代码|优化.{0,8}代码|单元测试|测试用例|边界用例)",
    re.IGNORECASE,
)
ASSISTANT_CODE_REFERENCE = re.compile(
    r"(?:上面|上一段|前面|刚才|这段|这个|该)(?:的)?(?:例子|示例|代码|程序)|"
    r"(?:above|previous|last)\s+(?:example|code|snippet)",
    re.IGNORECASE,
)

_MODE_PATTERNS: tuple[tuple[CodeTutorMode, re.Pattern[str]], ...] = (
    (
        CodeTutorMode.REFACTOR,
        re.compile(
            r"(?:重构|refactor).{0,12}(?:这段|上面|刚才|代码|程序|函数|类|示例)|"
            r"(?:这段|上面|刚才|代码|程序|函数|类|示例).{0,12}(?:重构|refactor)|"
            r"优化.{0,8}代码",
            re.I,
        ),
    ),
    (
        CodeTutorMode.REPAIR,
        re.compile(
            r"(?:修(?:好|复|正)|改正).{0,12}(?:这段|上面|刚才|代码|程序|函数|类|示例|错误|bug)|"
            r"(?:这段|上面|刚才|代码|程序|函数|类|示例|错误|bug).{0,12}(?:修(?:好|复|正)|改正)|"
            r"(?:fix|repair).{0,8}(?:this|the|above|previous)?\s*(?:code|example|function|class|bug)",
            re.I,
        ),
    ),
    (
        CodeTutorMode.DESIGN_TESTS,
        re.compile(
            r"单元测试|测试用例|边界用例|(?:代码|函数|方法|类).{0,12}测试|"
            r"测试.{0,12}(?:代码|函数|方法|类)|unit\s+tests?|test\s+cases?",
            re.I,
        ),
    ),
    (
        CodeTutorMode.REVIEW,
        re.compile(r"代码审阅|审查.{0,8}代码|代码质量|code\s+review|review\s+(?:this|the)?\s*code", re.I),
    ),
    (
        CodeTutorMode.EXPLAIN,
        re.compile(r"逐行解释|解释.{0,12}(?:这段|下面|以上|代码|程序)|walk\s+me\s+through", re.I),
    ),
    (
        CodeTutorMode.GENERATE_EXAMPLE,
        re.compile(
            r"示例代码|代码示例|示例程序|example\s+code|sample\s+code|"
            r"(?:给|写|生成|提供|展示).{0,24}(?:一段|一个|一份)?.{0,12}(?:代码|程序)(?!.*(?:练习|习题))|"
            r"(?:怎么|如何).{0,16}(?:写|实现).{0,20}(?:函数|类|程序|代码)",
            re.I,
        ),
    ),
    (
        CodeTutorMode.DIAGNOSE,
        re.compile(
            r"代码(?:辅导|分析|检查|有什么问题|哪里有问题)|调试|debug|"
            r"静态分析|编译(?:错误|失败)|syntaxerror|traceback|"
            r"(?:代码|程序).{0,8}(?:报错|哪里错)",
            re.I,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class ExtractedCode:
    content: str = ""
    language: str | None = None
    language_inferred: bool = False
    source: str | None = None

    @property
    def display_language(self) -> str | None:
        if self.language is None:
            return None
        spec = resolve_language(self.language)
        return spec.display_name if spec is not None else self.language


@dataclass(frozen=True, slots=True)
class TurnUnderstanding:
    """Shared deterministic interpretation passed into routing and extraction."""

    latest_user_text: str
    normalized_text: str
    code: ExtractedCode
    code_requested: bool


def normalize_for_matching(text: str) -> str:
    """Normalize matching-only text without changing learner-authored artifacts."""

    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.translate(
        str.maketrans({"：": ":", "，": ",", "；": ";", "（": "(", "）": ")"})
    )
    return re.sub(r"\s+", " ", normalized).strip()


def is_code_request(text: str) -> bool:
    normalized = normalize_for_matching(text)
    return bool(
        CODE_REQUEST.search(normalized)
        or infer_code_tutor_mode(text) is not None
        or FENCE_BLOCK.search(text)
    )


def infer_code_tutor_mode(text: str) -> CodeTutorMode | None:
    """Classify only high-confidence code-coaching operations."""

    normalized = normalize_for_matching(text)
    if re.search(r"(?:练习|习题)", normalized) and not re.search(
        r"示例代码|代码示例|example\s+code|sample\s+code|测试用例|单元测试",
        normalized,
        re.I,
    ):
        return None
    return next(
        (mode for mode, pattern in _MODE_PATTERNS if pattern.search(normalized)),
        None,
    )


def explicit_language_from_text(text: str) -> str | None:
    """Find an explicitly named supported language without treating prose as code."""

    normalized = normalize_for_matching(text)
    candidates: list[tuple[int, int, str]] = []
    aliases = sorted(
        (
            (alias.casefold(), spec.language_id)
            for spec in LANGUAGE_SPECS
            for alias in (spec.language_id, *spec.aliases)
            if len(alias) >= 2 or alias.casefold() == "c"
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for alias, language_id in aliases:
        match = re.search(
            rf"(?<![a-z0-9_]){re.escape(alias)}(?![a-z0-9_+#.-])",
            normalized,
            re.I,
        )
        if not match:
            continue
        if alias.isalpha() and len(alias) <= 2:
            if alias in {"cs", "ml"}:
                continue
            whole_message = normalized.strip(" .,:;!?/()[]{}") == alias
            contextual = bool(
                re.search(
                    rf"(?:用|使用|采用|改成|换成|in|using)\s*{re.escape(alias)}\b|"
                    rf"\b{re.escape(alias)}\s*(?:语言|代码|程序|示例|测试|"
                    rf"language|code|program|example|tests?)\b",
                    normalized,
                    re.I,
                )
            )
            if not whole_message and not contextual:
                continue
        candidates.append((match.start(), -len(alias), language_id))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def looks_like_code(text: str) -> bool:
    """Require multiple syntax signals so ordinary technical prose is not captured."""

    candidate = text.strip()
    if not candidate or len(candidate) > 20000:
        return False
    signals = (
        bool(re.search(r"[{}]", candidate)),
        ";" in candidate,
        bool(re.search(r"#?\s*include\s*<[^>]+>", candidate, re.I)),
        bool(re.search(r"\b(?:int|void)\s+main\s*\(", candidate)),
        bool(re.search(r"\b(?:cin|cout|cerr)\s*(?:>>|<<)", candidate)),
        bool(re.search(r"(?:^|\n)\s*(?:async\s+)?def\s+\w+\s*\(", candidate)),
        bool(re.search(r"(?:^|\n)\s*(?:from\s+\S+\s+)?import\s+\S+", candidate)),
        bool(re.search(r"\b(?:fn\s+main|public\s+static\s+void\s+main)\b", candidate)),
        bool(re.search(r"\b(?:SELECT|INSERT|UPDATE|DELETE)\b.+\b(?:FROM|INTO|SET)\b", candidate, re.I)),
        bool(re.search(r"(?:=>|::|&&|\|\||\+\+|--)", candidate)),
    )
    return sum(signals) >= 2


def _infer_language(code: str, surrounding_text: str) -> tuple[str | None, bool]:
    explicit = explicit_language_from_text(surrounding_text)
    if explicit is not None:
        return explicit, False

    votes: dict[str, int] = {}

    def vote(language: str, condition: bool) -> None:
        if condition:
            votes[language] = votes.get(language, 0) + 1

    vote("cpp", bool(re.search(r"\b(?:cin|cout|cerr)\s*(?:>>|<<)", code)))
    vote("cpp", "std::" in code)
    vote("cpp", bool(re.search(r"#?\s*include\s*<(?:iostream|vector|string|map|algorithm)>", code)))
    vote("cpp", bool(re.search(r"\bint\s+main\s*\(", code)) and ";" in code)
    vote("python", bool(re.search(r"(?:^|\n)\s*(?:async\s+)?def\s+\w+\s*\([^)]*\)\s*:", code)))
    vote("python", bool(re.search(r"(?:^|\n)\s*(?:from\s+\S+\s+)?import\s+\S+", code)))
    vote("rust", "fn main" in code)
    vote("rust", bool(re.search(r"\blet\s+(?:mut\s+)?\w+", code)))
    vote("java", "public static void main" in code)
    vote("java", "System.out." in code)
    vote("javascript", bool(re.search(r"\b(?:const|let|var)\s+\w+\s*=", code)))
    vote("javascript", "console.log" in code)

    ordered = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    if ordered and ordered[0][1] >= 2 and (len(ordered) == 1 or ordered[0][1] > ordered[1][1]):
        return ordered[0][0], True
    return None, False


def _parse_fence(body: str) -> tuple[str, str | None]:
    stripped = body.strip()
    if not stripped:
        return "", None
    first_line, newline, remainder = stripped.partition("\n")
    first_label = normalize_language_label(first_line)
    if newline and (resolve_language(first_label) is not None or first_label in OUTPUT_FENCE_LABELS):
        spec = resolve_language(first_label)
        return remainder.strip(), spec.language_id if spec is not None else first_label
    token, separator, remainder = stripped.partition(" ")
    token_label = normalize_language_label(token)
    if separator and (resolve_language(token_label) is not None or token_label in OUTPUT_FENCE_LABELS):
        spec = resolve_language(token_label)
        return remainder.strip(), spec.language_id if spec is not None else token_label
    return stripped, None


def _inline_candidates(text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for match in re.finditer(r"[“\"「『](.*?)[”\"」』]", text, re.DOTALL):
        candidates.append((match.group(1).strip(), "quoted"))
    if is_code_request(text):
        for separator in ("：", ":"):
            if separator in text:
                tail = text.rsplit(separator, 1)[1].strip().strip("“”\"'「」『』")
                candidates.append((tail, "inline"))
    return candidates


def extract_code(user_texts: list[str]) -> ExtractedCode:
    """Return the most recent learner-authored code artifact, if one is recognizable."""

    for text in reversed(user_texts):
        for match in reversed(list(FENCE_BLOCK.finditer(text))):
            code, label = _parse_fence(match.group("body"))
            if label in OUTPUT_FENCE_LABELS or not code:
                continue
            if label is not None:
                return ExtractedCode(code[:20000], label, False, "fence")
            language, inferred = _infer_language(code, text)
            return ExtractedCode(code[:20000], language, inferred, "fence")

        for candidate, source in reversed(_inline_candidates(text)):
            if looks_like_code(candidate):
                language, inferred = _infer_language(candidate, text)
                return ExtractedCode(candidate[:20000], language, inferred, source)

        stripped = text.strip()
        if looks_like_code(stripped):
            language, inferred = _infer_language(stripped, text)
            return ExtractedCode(stripped[:20000], language, inferred, "plain")
    return ExtractedCode()


def understand_user_texts(user_texts: list[str]) -> TurnUnderstanding:
    if not user_texts:
        raise ValueError("at least one user message is required")
    latest = user_texts[-1]
    return TurnUnderstanding(
        latest_user_text=latest,
        normalized_text=normalize_for_matching(latest),
        code=extract_code(user_texts),
        code_requested=is_code_request(latest),
    )


def build_code_tutor_request(
    text: str,
    code: ExtractedCode,
    semantic: SemanticCodeRequest | None = None,
) -> CodeTutorRequest:
    """Resolve mode and language using deterministic evidence before model advice."""

    mode = infer_code_tutor_mode(text)
    if mode is None and semantic is not None:
        mode = semantic.mode
    if mode is None:
        mode = CodeTutorMode.DIAGNOSE
    references_existing_code = bool(
        ASSISTANT_CODE_REFERENCE.search(normalize_for_matching(text))
    )

    explicit_language = explicit_language_from_text(text)
    if explicit_language is not None:
        return CodeTutorRequest(
            mode=mode,
            target_language=explicit_language,
            language_inferred=False,
            references_existing_code=references_existing_code,
        )
    if code.language is not None:
        return CodeTutorRequest(
            mode=mode,
            target_language=code.language,
            language_inferred=code.language_inferred,
            references_existing_code=references_existing_code,
        )
    if semantic is not None and semantic.target_language:
        spec = resolve_language(semantic.target_language)
        if spec is not None:
            return CodeTutorRequest(
                mode=mode,
                target_language=spec.language_id,
                language_inferred=True,
                references_existing_code=references_existing_code,
            )
    return CodeTutorRequest(
        mode=mode,
        references_existing_code=references_existing_code,
    )


def extract_referenced_assistant_code(
    messages: list[ChatMessage], latest_user_text: str
) -> ExtractedCode:
    """Recover an exact recent assistant code block only for an explicit reference."""

    if not ASSISTANT_CODE_REFERENCE.search(normalize_for_matching(latest_user_text)):
        return ExtractedCode()
    for message in reversed(messages[-12:-1]):
        if message.role != "assistant":
            continue
        for match in reversed(list(FENCE_BLOCK.finditer(message.content))):
            code, label = _parse_fence(match.group("body"))
            if not code or label in OUTPUT_FENCE_LABELS:
                continue
            spec = resolve_language(label) if label else None
            if spec is None:
                language, inferred = _infer_language(code, message.content)
            else:
                language, inferred = spec.language_id, False
            return ExtractedCode(
                content=code[:20000],
                language=language,
                language_inferred=inferred,
                source="assistant_reference",
            )
    return ExtractedCode()


def prose_without_code(text: str) -> str:
    """Remove recognizable code artifacts before profile or planner prose analysis."""

    cleaned = FENCE_BLOCK.sub(" ", text)

    def remove_quoted(match: re.Match[str]) -> str:
        return " " if looks_like_code(match.group(1)) else match.group(0)

    cleaned = re.sub(r"[“\"「『](.*?)[”\"」』]", remove_quoted, cleaned, flags=re.DOTALL)
    if is_code_request(cleaned):
        for separator in ("：", ":"):
            if separator not in cleaned:
                continue
            prefix, tail = cleaned.rsplit(separator, 1)
            candidate = tail.strip().strip("“”\"'「」『』")
            if looks_like_code(candidate):
                cleaned = prefix
                break
    cleaned = re.split(r"Traceback \(most recent call last\):", cleaned, maxsplit=1)[0]
    return re.sub(r"\s+", " ", cleaned).strip()


def language_assumption(extracted: ExtractedCode) -> str | None:
    if not extracted.language_inferred or extracted.language is None:
        return None
    try:
        display = get_language(extracted.language).display_name
    except KeyError:
        display = extracted.language
    if extracted.content:
        return f"理解：我按 {display} 代码进行静态分析；如果语言判断不对，请直接纠正我。"
    return f"理解：我按 {display} 处理这次代码辅导；如果语言判断不对，请直接纠正我。"


def validate_model_code(
    messages: list[ChatMessage], candidate: SemanticCodeArtifact | None
) -> ExtractedCode:
    """Bind model-extracted code to one learner-authored message.

    The model owns semantic segmentation, but it cannot introduce code that the
    learner did not send. Minor quote and whitespace differences are tolerated.
    """

    if candidate is None:
        return ExtractedCode()
    window = messages[-12:]
    if candidate.source_message_index >= len(window):
        return ExtractedCode()
    source = window[candidate.source_message_index]
    if source.role != "user":
        return ExtractedCode()
    content = candidate.content.strip()
    if not content:
        return ExtractedCode()
    if content not in source.content:
        compact_source = re.sub(r"[\s“”\"'「」『』`]+", "", source.content)
        compact_content = re.sub(r"[\s“”\"'「」『』`]+", "", content)
        if not compact_content or compact_content not in compact_source:
            return ExtractedCode()
    spec = resolve_language(candidate.language) if candidate.language else None
    language = spec.language_id if spec is not None else None
    inferred = False
    if language is None:
        language, inferred = _infer_language(content, content)
    return ExtractedCode(
        content=content[:20000],
        language=language,
        language_inferred=inferred,
        source="model_current_turn",
    )
