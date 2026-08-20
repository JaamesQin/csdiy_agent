#!/usr/bin/env python3
"""Discover and classify every Markdown leaf in a pinned cs-self-learning nav.

This script is deliberately deterministic and offline.  It reads a checked-out
upstream snapshot, never follows URLs, and keeps classification/progress data
separate from later offering research and StudyKit authoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import quote, urljoin

import yaml


REPOSITORY_URL = "https://github.com/PKUFlyingPig/cs-self-learning"
SITE_URL = "https://csdiy.wiki/"
REGISTRY_VERSION = "0.1"
STATES = (
    "discovered",
    "classified",
    "researching_offering",
    "offering_selected",
    "sources_inventoried",
    "downloaded",
    "prepared",
    "chunked",
    "authoring",
    "audited",
    "validated",
    "complete",
    "blocked_no_public_evidence",
    "blocked_access",
    "failed_recoverable",
)

COURSE_PREFIXES = (
    "MIT|CMU|UCB|UC\\s*BERKELEY|STANFORD|HARVARD|CORNELL|DUKE|ASU|"
    "ETHZ|NJU|PKU|USTC|SJTU|KAIST|NTU|EECS|GAMES|STAT|STA|CSE|CS|"
    "EE|MATH|INFO|COMS"
)
EXPLICIT_INSTITUTION_PREFIXES = "MIT|CMU|UCB"
COURSE_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<code>(?:"
    rf"(?:{COURSE_PREFIXES})\s*[- ]?\s*\d+(?:[.-][A-Za-z]?\d+)?[A-Za-z]*(?:[-/]\d+)?"
    r"|(?:EECS|GAMES|STAT|STA|CSE|CS|EE|MATH|INFO|COMS)\s*[- ]?\s*\d+[A-Za-z]*(?:[-/]\d+)?"
    r"|\d+\.\d+[A-Za-z]*))"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)

INSTITUTION_ALIASES = {
    "mit": "Massachusetts Institute of Technology",
    "cmu": "Carnegie Mellon University",
    "ucb": "University of California, Berkeley",
    "berkeley": "University of California, Berkeley",
    "stanford": "Stanford University",
    "harvard": "Harvard University",
    "cornell": "Cornell University",
    "duke": "Duke University",
    "asu": "Arizona State University",
    "ethz": "ETH Zürich",
    "nju": "Nanjing University",
    "pku": "Peking University",
    "ustc": "University of Science and Technology of China",
    "sjtu": "Shanghai Jiao Tong University",
    "kaist": "KAIST",
    "ntu": "National Taiwan University",
    "caltech": "California Institute of Technology",
    "umich": "University of Michigan",
    "columbia": "Columbia University",
    "helsinki": "University of Helsinki",
    "princeton": "Princeton University",
}

INSTITUTION_SLUGS = {
    "Massachusetts Institute of Technology": "mit",
    "Carnegie Mellon University": "cmu",
    "University of California, Berkeley": "ucb",
    "Stanford University": "stanford",
    "Harvard University": "harvard",
    "Cornell University": "cornell",
    "Duke University": "duke",
    "Arizona State University": "asu",
    "ETH Zürich": "ethz",
    "Nanjing University": "nju",
    "Peking University": "pku",
    "University of Science and Technology of China": "ustc",
    "Shanghai Jiao Tong University": "sjtu",
    "KAIST": "kaist",
    "National Taiwan University": "ntu",
    "California Institute of Technology": "caltech",
    "University of Michigan": "umich",
    "Columbia University": "columbia",
    "University of Helsinki": "helsinki",
    "Princeton University": "princeton",
    "University of Cambridge": "cambridge",
}

TOOL_CATEGORIES = {"必学工具", "productivity toolkit", "useful tools"}
ROADMAP_MARKERS = ("roadmap", "路线图", "学习规划", "学习路线", "guideline")
BOOK_MARKERS = ("好书推荐", "book recommendation", "textbook", "top-down approach")
OTHER_MARKERS = (
    "前言",
    "foreword",
    "使用指南",
    "how to use",
    "后记",
    "postscript",
    "workflow",
    "翻墙",
    "gfw",
    "信息检索",
    "thesis",
)
COURSE_MARKERS = (
    "课程",
    "course",
    "lecture",
    "讲义",
    "syllabus",
    "schedule",
    "homework",
    "assignment",
    "course site",
    "课程主页",
)
SEQUENCE_MARKERS = ("sequence", "系列", "i&ii")

CURRENT_SEED_IDS = {"mit-6-7960", "mit-6-s081", "cmu-15-213", "ucb-cs61b"}
FOUNDATION_MARKERS = ("编程入门", "数据结构", "算法", "数学基础", "离散", "概率")
DIRECTION_RULES = (
    (("编程语言", "programming language", "haskell", "ocaml"), "programming_languages"),
    (("机器学习", "深度学习", "machine learning", "deep learning", "neural network", "神经网络"), "machine_learning"),
    (("编程入门", "programming", "python", "java", "c++", "rust", "haskell"), "programming_foundations"),
    (("数据结构", "算法", "algorithms", "data structures"), "data_structures_algorithms"),
    (("系统基础", "计算机系统", "systems"), "systems"),
    (("操作系统", "operating system"), "operating_systems"),
    (("体系结构", "architecture"), "architecture"),
    (("网络", "network"), "networks"),
    (("数据库", "database"), "databases"),
    (("编译", "compiler"), "compilers"),
    (("软件工程", "software engineering"), "software_engineering"),
    (("并行", "分布式", "distributed", "parallel"), "distributed_systems"),
    (("安全", "security", "密码学", "cryptography"), "security"),
    (("人工智能", "ai"), "artificial_intelligence"),
    (("图形", "视觉", "graphics", "vision"), "graphics_vision"),
    (("理论", "theory"), "theory"),
    (("数学", "概率", "离散", "calculus", "linear algebra", "statistics"), "discrete_mathematics_probability"),
    (("数值", "科学", "numerical", "scientific"), "numerical_scientific_computing"),
)
# Navigation categories and guide paths are stronger evidence than a generic
# word in a course title.  Keep this table explicit so title/category conflicts
# are reviewable and regression-testable (for example, CS168's "Architecture").
CATEGORY_DIRECTION_RULES = (
    (("计算机网络", "computer networks", "computer network", "networking"), "networks"),
    (("操作系统", "operating systems"), "operating_systems"),
    (("计算机系统安全", "computer systems security"), "security"),
    (("数据库系统", "database systems"), "databases"),
    (("数据结构与算法", "data structures and algorithms"), "data_structures_algorithms"),
    (("体系结构", "computer architecture"), "architecture"),
    (("编译原理", "compiler design", "compilers"), "compilers"),
    (("软件工程", "software engineering"), "software_engineering"),
    (("并行与分布式系统", "parallel and distributed systems"), "distributed_systems"),
    (("计算机图形学", "computer graphics"), "graphics_vision"),
    (("大语言模型", "large language model", "自然语言处理", "natural language processing", "nlp"), "artificial_intelligence"),
    (("人工智能", "artificial intelligence"), "artificial_intelligence"),
    (("深度学习", "机器学习系统", "机器学习进阶", "机器学习", "machine learning"), "machine_learning"),
    (("编程语言设计与分析", "programming languages"), "programming_languages"),
    (("编程入门", "programming foundations"), "programming_foundations"),
    (("数学基础", "数学进阶", "discrete mathematics"), "discrete_mathematics_probability"),
    (("计算机系统基础", "computer systems"), "systems"),
    (("理论", "theory"), "theory"),
    (("数据科学", "data science", "numerical computing"), "numerical_scientific_computing"),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[\u4e00-\u9fff]+", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown"


def normalize_code(value: str) -> str:
    value = re.sub(r"\s+", "", value).upper()
    return value


def canonical_course_number(institution: str | None, code: str) -> str:
    """Normalize known catalog aliases without erasing the original evidence."""

    if institution == "Carnegie Mellon University" and code.upper() == "CS15213":
        return "15-213"
    return code


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def git_value(root: Path, args: list[str], fallback: str | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return fallback
    return result.stdout.strip() or fallback


def snapshot_commit(root: Path) -> str:
    """Use an immutable snapshot directory name before probing parent Git.

    Catalog snapshots are intentionally copied into an ignored directory and
    need not carry their own `.git` metadata.  ``git -C`` would otherwise walk
    up into the CoursePilot checkout and incorrectly pin the application HEAD.
    """

    if re.fullmatch(r"[0-9a-fA-F]{40}", root.name):
        return root.name.lower()
    return git_value(root, ["rev-parse", "HEAD"], "unknown") or "unknown"


def walk_nav(value: Any, categories: tuple[str, ...] = ()) -> Iterable[dict[str, Any]]:
    """Yield nav leaves without relying on rendered HTML or table of contents."""

    if isinstance(value, list):
        for item in value:
            yield from walk_nav(item, categories)
        return
    if not isinstance(value, dict):
        return
    for title, child in value.items():
        title = str(title)
        if isinstance(child, str):
            if child.lower().split("#", 1)[0].endswith(".md"):
                yield {"title": title, "source_path": child, "category_path": list(categories)}
            continue
        yield from walk_nav(child, categories + (title,))


def sectioned_links(text: str) -> list[dict[str, str | None]]:
    links: list[dict[str, str | None]] = []
    heading: str | None = None
    markdown_re = re.compile(r"(?<!!)\[([^\]]+)\]\(([^\s)]+)(?:\s+[^)]*)?\)")
    html_re = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I)
    for line_number, line in enumerate(text.splitlines(), start=1):
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading_match:
            heading = heading_match.group(1).strip()
        for match in markdown_re.finditer(line):
            target = match.group(2).strip().strip("<>")
            if target.startswith("#"):
                continue
            links.append(
                {
                    "label": re.sub(r"\s+", " ", match.group(1).strip()),
                    "target": target,
                    "section_heading": heading,
                    "line": str(line_number),
                }
            )
        for match in html_re.finditer(line):
            target = match.group(1).strip()
            label = re.sub(r"<[^>]+>", "", match.group(2))
            links.append(
                {
                    "label": re.sub(r"\s+", " ", label).strip() or None,
                    "target": target,
                    "section_heading": heading,
                    "line": str(line_number),
                }
            )
    return links


def first_heading(text: str) -> str | None:
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def infer_language(source_path: str, text: str) -> str:
    if source_path.lower().endswith(".en.md"):
        return "en"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh-CN"
    return "en"


def institution_for(text: str, code: str | None = None) -> str | None:
    lowered = text.lower()
    checks = (
        ("mit", "Massachusetts Institute of Technology"),
        ("cmu", "Carnegie Mellon University"),
        ("ucb", "University of California, Berkeley"),
        ("berkeley", "University of California, Berkeley"),
        ("stanford", "Stanford University"),
        ("harvard", "Harvard University"),
        ("cornell", "Cornell University"),
        ("duke", "Duke University"),
        ("asu", "Arizona State University"),
        ("ethz", "ETH Zürich"),
        ("nju", "Nanjing University"),
        ("pku", "Peking University"),
        ("ustc", "University of Science and Technology of China"),
        ("sjtu", "Shanghai Jiao Tong University"),
        ("kaist", "KAIST"),
        ("ntu", "National Taiwan University"),
        ("caltech", "California Institute of Technology"),
        ("umich", "University of Michigan"),
        ("columbia", "Columbia University"),
        ("helsinki", "University of Helsinki"),
        ("princeton", "Princeton University"),
    )
    for marker, institution in checks:
        if marker in lowered:
            return institution
    if code:
        prefix = re.match(r"[A-Z]+", code.upper())
        if prefix and prefix.group(0) in {"MIT", "CMU", "UCB"}:
            return INSTITUTION_ALIASES.get(prefix.group(0).lower())
    return None


def course_code_records(identity_text: str) -> list[dict[str, str | None]]:
    records: list[dict[str, str | None]] = []
    for match in COURSE_CODE_RE.finditer(identity_text):
        raw = match.group("code")
        code = normalize_code(raw)
        explicit_institution = re.match(
            rf"(?:{EXPLICIT_INSTITUTION_PREFIXES})",
            code,
            flags=re.IGNORECASE,
        )
        if explicit_institution:
            code = re.sub(rf"^(?:{EXPLICIT_INSTITUTION_PREFIXES})", "", code, flags=re.IGNORECASE)
        context = identity_text[max(0, match.start() - 32) : match.end() + 16]
        variants = [code]
        sequence_match = re.fullmatch(r"(\d+[-.]\d+)/(\d+)", code)
        if sequence_match:
            prefix = sequence_match.group(1).rsplit("-", 1)[0]
            variants = [sequence_match.group(1), f"{prefix}-{sequence_match.group(2)}"]
        for variant in variants:
            record = {"code": variant, "raw": raw, "context": context}
            if not any(item["code"] == variant and item["context"] == context for item in records):
                records.append(record)
    # A/B and B/X course pages often encode the second official course as a
    # bare letter after the first identifier. Preserve it as an explicit
    # target candidate instead of silently collapsing the sequence.
    expanded: list[dict[str, str | None]] = list(records)
    for record in records:
        code = str(record["code"])
        pattern = re.escape(code[-1:])
        if re.search(rf"{pattern}\s*[&/]\s*([ABX])\b", identity_text, flags=re.IGNORECASE):
            suffix = re.search(rf"{pattern}\s*[&/]\s*([ABX])\b", identity_text, flags=re.IGNORECASE)
            if suffix:
                variant = code[:-1] + suffix.group(1).upper()
                if variant not in {str(item["code"]) for item in expanded}:
                    expanded.append({"code": variant, "raw": variant, "context": record["context"]})
    deduped: list[dict[str, str | None]] = []
    for record in expanded:
        if not any(item["code"] == record["code"] for item in deduped):
            deduped.append(record)
    return deduped


def catalog_identity_overrides(
    title: str,
    source_path: str,
    identity_text: str,
    records: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """Apply evidence-backed identity corrections for known catalog collisions.

    The generic code regex intentionally remains broad for discovery.  A small
    explicit layer is required for pages where a family stem, umbrella label,
    or malformed slash expression is not itself an official course identity.
    These cases are keyed by the pinned page title/path and retain the source
    text as the evidence for the correction.
    """

    lowered_title = title.lower()
    lowered_path = source_path.lower().replace("\\", "/")
    lowered_identity = identity_text.lower()

    def record(code: str) -> dict[str, str | None]:
        return {"code": code, "raw": code, "context": identity_text[:256]}

    if "cs50p" in lowered_title or "cs50p" in lowered_path:
        return [record("CS50P")]
    if (
        ("cs50" in lowered_path and ("artificial" in lowered_path or "人工智能" in lowered_path))
        or re.search(r"cs50\s*(?:ai|artificial intelligence)", lowered_title)
        or re.search(r"cs50.{0,20}\bai\b", lowered_title)
    ):
        return [record("CS50 AI")]
    if "cs50x" in lowered_title or "cs50x" in lowered_path:
        return [record("CS50X")]

    if "cs231n" in lowered_title or lowered_path.endswith("/cs231.md"):
        return [record("CS231N")]

    if "ee16a&b" in lowered_title or lowered_path.endswith("/ee16.md"):
        return [record("EE16A"), record("EE16B")]

    if lowered_path.endswith("/algo.md"):
        return [
            {**record("Algorithms-I"), "institution": "Princeton University"},
            {**record("Algorithms-II"), "institution": "Princeton University"},
        ]

    if lowered_path.endswith("/eecs498-007.md"):
        return [record("EECS498-007"), record("EECS598-005")]

    if lowered_path.endswith("/cs229m.md"):
        return [record("CS229M"), record("STATS214")]

    # The guide page explicitly identifies the provider as the University of
    # Cambridge.  Do not let the generic ``Cambridge`` title token fall
    # through to the first institution heuristic (which historically mapped
    # unnumbered pages to MIT).  This is a course identity correction, not a
    # source-offering claim; the selected term remains an offering-level
    # record.
    if lowered_path.endswith("/cambridge-semantics.md"):
        return [{**record("Semantics of Programming Languages"), "institution": "University of Cambridge"}]

    if (
        "18.01" in lowered_identity
        and "18.02" in lowered_identity
        and ("mitmaths" in lowered_path or "calculus" in lowered_title)
    ):
        return [record("18.01"), record("18.02")]

    return records


def institution_for_code(identity_text: str, record: dict[str, str | None]) -> str | None:
    context = str(record.get("context") or "")
    raw = str(record.get("raw") or record.get("code") or "")
    lowered_context = context.lower()
    code_position = lowered_context.rfind(raw.lower())
    nearby = (
        ("mit", "Massachusetts Institute of Technology"),
        ("cmu", "Carnegie Mellon University"),
        ("ucb", "University of California, Berkeley"),
        ("berkeley", "University of California, Berkeley"),
        ("stanford", "Stanford University"),
        ("harvard", "Harvard University"),
        ("cornell", "Cornell University"),
        ("duke", "Duke University"),
        ("asu", "Arizona State University"),
        ("ethz", "ETH Zürich"),
        ("nju", "Nanjing University"),
        ("pku", "Peking University"),
        ("ustc", "University of Science and Technology of China"),
        ("sjtu", "Shanghai Jiao Tong University"),
        ("kaist", "KAIST"),
        ("ntu", "National Taiwan University"),
        ("caltech", "California Institute of Technology"),
        ("umich", "University of Michigan"),
        ("columbia", "Columbia University"),
        ("helsinki", "University of Helsinki"),
    )
    matches = [(lowered_context.rfind(marker, 0, code_position), institution) for marker, institution in nearby]
    matches = [(position, institution) for position, institution in matches if position >= 0]
    if matches:
        return max(matches, key=lambda item: item[0])[1]
    return institution_for(identity_text, raw)


def course_id_for(title: str, source_path: str, code: str | None, institution: str | None) -> str:
    if institution and code:
        prefix = INSTITUTION_SLUGS.get(institution)
        if prefix:
            return f"{prefix}-{slugify(code)}"
    if institution and title:
        prefix = INSTITUTION_SLUGS.get(institution)
        if prefix:
            title_slug = slugify(title)
            if title_slug not in {"unknown", prefix}:
                return f"{prefix}-{title_slug}"
            source_stem = PurePosixPath(source_path).stem
            return f"{prefix}-{slugify(source_stem)}"
    if code:
        return slugify(code)
    base = re.sub(r"\.en(?=\.md$)", "", source_path, flags=re.I)
    base = str(PurePosixPath(base).with_suffix(""))
    title_slug = slugify(title) if title else "unknown"
    if title_slug != "unknown":
        return title_slug
    return slugify(PurePosixPath(base).stem)


def canonical_identity_key(institution: str | None, code: str) -> str:
    """Normalize punctuation and known institution aliases for one identity.

    A dot/hyphen variation or a legacy CMU prefix is evidence for one course,
    not a second course.  Cross-listed identities are preserved by explicit
    catalog overrides and are handled separately by ``is_crosslisted_alias``.
    """

    normalized = normalize_code(code)
    compact = re.sub(r"[^A-Z0-9]", "", normalized)
    if institution == "Carnegie Mellon University" and compact in {"CS15213", "15213"}:
        return "15-213"
    if institution == "Massachusetts Institute of Technology" and compact == "67960":
        return "6-7960"
    return compact


def is_crosslisted_alias(source_path: str, identity_text: str) -> bool:
    lowered_path = source_path.lower().replace("\\", "/")
    lowered = identity_text.lower()
    if lowered_path.endswith(("/eecs498-007.md", "/cs229m.md")):
        return True
    return bool(re.search(r"cross[- ]?listed|cross[- ]?listed|同一门|交叉列课", lowered))


def sequence_evidence(title: str, source_path: str, identity_text: str, codes: list[str]) -> str | None:
    title_path = f"{title} {source_path}".lower()
    lowered = f"{title_path} {identity_text}".lower()
    if any(marker in title_path for marker in SEQUENCE_MARKERS):
        return "title/path explicitly identifies a course sequence"
    if re.search(r"algorithms\s+i\s*&\s*ii|18\.01\s*/\s*18\.02|cs106b\s*/\s*cs106x|15[- ]418\s*/\s*stanford\s*cs149", title_path):
        return "guide explicitly names paired official course identities"
    if len(codes) > 1 and not is_crosslisted_alias(source_path, identity_text):
        return "distinct official course identities are explicitly listed"
    return None


def infer_direction_details(category_paths: Iterable[str], title: str, source_paths: Iterable[str] = ()) -> tuple[str, list[str], list[str]]:
    categories = [str(value) for value in category_paths]
    category_haystack = " ".join(categories).lower()
    title_haystack = " ".join([title, *source_paths]).lower()

    # Some titles carry a substantive direction that is more specific than a
    # broad navigation bucket.  Numerical analysis is the clearest example:
    # it may live under "advanced mathematics", but it is not a discrete-math
    # course.  Treat this as an explicit title/path override, not as a generic
    # keyword exception, so the evidence remains reviewable and deterministic.
    if re.search(r"(?:numerical\s+analysis|numerical\s+methods|scientific\s+comput(?:ing|ation)|数值分析|科学计算)", title_haystack):
        return (
            "numerical_scientific_computing",
            ["substantive title/path matched numerical-analysis or scientific-computing evidence"],
            [],
        )

    for markers, direction in CATEGORY_DIRECTION_RULES:
        if any(marker.lower() in category_haystack for marker in markers):
            evidence = [f"nav category/path matched {marker!r}; category evidence takes precedence over title keywords" for marker in markers if marker.lower() in category_haystack]
            secondary: list[str] = []
            for generic_markers, generic_direction in DIRECTION_RULES:
                if generic_direction != direction and any(marker.lower() in title_haystack for marker in generic_markers):
                    # "network" is a substring of "neural network".  The
                    # latter is machine-learning evidence and must not create
                    # a false computer-networks secondary direction.
                    if generic_direction == "networks" and re.search(r"(?:neural\s+networks?|神经网络)", title_haystack):
                        continue
                    if generic_direction not in secondary:
                        secondary.append(generic_direction)
            return direction, evidence, secondary

    haystack = " ".join([*categories, title, *source_paths]).lower()
    for markers, direction in DIRECTION_RULES:
        if any(marker.lower() in haystack for marker in markers):
            return direction, [f"title/path matched {marker!r}" for marker in markers if marker.lower() in haystack], []
    return "other_computing", ["no substantive direction marker matched; retained as other_computing"], []


def infer_direction(category_paths: Iterable[str], title: str, source_paths: Iterable[str] = ()) -> str:
    return infer_direction_details(category_paths, title, source_paths)[0]


def priority_fields(target_id: str, title: str, direction: str, category_paths: Iterable[str], family_count: int) -> dict[str, Any]:
    inferred_direction, direction_evidence, secondary_directions = infer_direction_details(category_paths, title)
    if direction != inferred_direction:
        direction = inferred_direction
    haystack = " ".join([title, *category_paths]).lower()
    introductory = 5 if any(marker in haystack for marker in ("101", "入门", "intro", "introduction", "cs50", "61a")) else 2
    downstream = 5 if direction in {"programming_foundations", "data_structures_algorithms", "systems", "discrete_mathematics_probability"} else 2
    existing_reuse = 5 if target_id in CURRENT_SEED_IDS else 0
    coverage_gain = 1 if direction in {"systems", "operating_systems", "data_structures_algorithms", "machine_learning"} else 4
    redundancy_penalty = 2 if family_count > 1 else 0
    cost = 4 if any(marker in haystack for marker in ("sequence", "i&ii", "specialization", "mooc")) else 2
    if target_id in CURRENT_SEED_IDS:
        cohort = "batch-0-current-work"
        reason = "已存在可复用的官方学期、manifest、分块或 reviewed/build checkpoint。"
    elif target_id == "ucb-cs61a":
        cohort = "batch-1-programming-onramp"
        reason = "编程基础与抽象入口，能补足 CS61B 前置并连接后续课程；需先验证完成学期和公开证据。"
    elif direction not in {"systems", "operating_systems", "data_structures_algorithms", "machine_learning"}:
        cohort = "breadth-before-depth"
        reason = f"代表当前四门课程尚未覆盖或覆盖较弱的方向：{direction}；优先寻找稳定官方公开材料。"
    else:
        cohort = "later-depth"
        reason = f"方向 {direction} 已有代表课程，待完成宽度覆盖后再增加近邻课程。"
    return {
        "major_direction": direction,
        "direction_evidence": direction_evidence,
        "secondary_directions": secondary_directions,
        "introductory_value": introductory,
        "learner_demand": 3 if introductory >= 5 or downstream >= 5 else 2,
        "downstream_prerequisite_value": downstream,
        "direction_coverage_gain": coverage_gain,
        "public_source_readiness": 0,
        "existing_work_reuse": existing_reuse,
        "redundancy_penalty": redundancy_penalty,
        "estimated_ingestion_cost": cost,
        # Keep every requested priority dimension explicit before offering
        # research. Unknown is not a negative score and must not be inferred
        # from personal preference or from a missing URL probe.
        "notes_completeness": "unknown",
        "notes_kind": "unknown",
        "notes_public_readiness": 0,
        "notes_public_status": "not_researched",
        "notes_license_status": "not_researched",
        "ai_relevance": None,
        "non_cs_accessibility": None,
        "priority_cohort": cohort,
        "priority_reason": reason,
        "priority_evidence": [
            "证据来自固定 guide nav category/title、课程编号、入门/前置关系或现有磁盘 checkpoint；未使用个人偏好或星标数。",
            "public_source_readiness 在 offering research 完成前保持 0，避免把未验证的公开可得性当作事实。",
            "notes、AI relevance 与 non-CS accessibility 在 offering research 前显式保持 unknown/not_researched；不得把缺少证据解释为低需求或低可访问性。",
        ],
    }


def candidate_offerings(links: list[dict[str, str | None]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    keywords = ("course", "课程", "schedule", "lecture", "讲", "syllabus", "notes", "video", "resource")
    for link in links:
        target = link.get("target") or ""
        label = link.get("label") or ""
        heading = link.get("section_heading") or ""
        haystack = f"{target} {label} {heading}".lower()
        if target.startswith(("http://", "https://")) and any(word in haystack for word in keywords):
            candidates.append(
                {
                    "url": target,
                    "label": label,
                    "section_heading": link.get("section_heading"),
                    "probe_status": "not_run",
                    "probe_result": None,
                    "rejection_reason": None,
                }
            )
    return candidates


def classify_leaf(leaf: dict[str, Any], root: Path, commit: str) -> dict[str, Any]:
    source_path = str(leaf["source_path"]).split("#", 1)[0].lstrip("./")
    if source_path.startswith("docs/"):
        relative_path = PurePosixPath(source_path)
    else:
        relative_path = PurePosixPath("docs") / source_path
    page_path = root / Path(*relative_path.parts)
    exists = page_path.is_file()
    text = read_text(page_path) if exists else ""
    title = str(leaf["title"])
    heading = first_heading(text)
    identity_header = " ".join(filter(None, (title, heading, str(relative_path))))
    identity_text = " ".join(filter(None, (identity_header, text[:1200])))
    links = sectioned_links(text)
    code_records = catalog_identity_overrides(
        title,
        str(relative_path),
        identity_text,
        course_code_records(identity_header),
    )
    raw_codes = [str(record["code"]) for record in code_records]
    page_institution = institution_for(identity_text, raw_codes[0] if raw_codes else None)
    canonical_records: list[dict[str, str | None]] = []
    seen_identity_keys: set[tuple[str | None, str]] = set()
    for record in code_records:
        code = str(record["code"])
        institution = record.get("institution") or institution_for_code(identity_text, record)
        canonical_code = canonical_course_number(institution, code)
        key = (institution, canonical_identity_key(institution, canonical_code))
        if key in seen_identity_keys:
            continue
        seen_identity_keys.add(key)
        canonical_records.append({**record, "code": canonical_code, "institution": institution})
    codes = [str(record["code"]) for record in canonical_records]
    if canonical_records:
        page_institution = next(
            (record.get("institution") for record in canonical_records if record.get("institution")),
            page_institution,
        )
    language = infer_language(str(relative_path), text)
    category_path = list(leaf.get("category_path", []))
    category_text = " / ".join(category_path)
    lowered = f"{title} {category_text} {relative_path}".lower()
    explicit_course = bool(codes) or any(marker.lower() in lowered for marker in COURSE_MARKERS)
    tool = any(marker.lower() in lowered for marker in TOOL_CATEGORIES) or "必学工具" in category_text
    roadmap = any(marker.lower() in lowered for marker in ROADMAP_MARKERS)
    book = any(marker.lower() in lowered for marker in BOOK_MARKERS)
    other = any(marker.lower() in lowered for marker in OTHER_MARKERS)
    course_like_category = bool(category_path) and not tool and not roadmap and not book and not other

    if not exists:
        target_type = "other"
        is_course_target = False
        reason = "The mkdocs nav leaf points to a missing Markdown file in the pinned snapshot."
        confidence = 1.0
        review_status = "needs_review"
    elif roadmap:
        target_type = "roadmap"
        is_course_target = False
        reason = "The title or path explicitly identifies a learning roadmap or study plan."
        confidence = 0.99
        review_status = "auto_classified"
    elif tool:
        target_type = "tool"
        is_course_target = False
        reason = "The nav category or title identifies a productivity/tooling page rather than a course."
        confidence = 0.99
        review_status = "auto_classified"
    elif book:
        target_type = "book"
        is_course_target = False
        reason = "The nav category or title identifies a book recommendation or textbook-only page."
        confidence = 0.95
        review_status = "auto_classified"
    elif other:
        target_type = "other"
        is_course_target = False
        reason = "The title identifies an introduction, workflow, postscript, or other non-course guide page."
        confidence = 0.95
        review_status = "auto_classified"
    elif explicit_course or course_like_category:
        sequence_reason = sequence_evidence(title, str(relative_path), identity_text, codes)
        target_type = "course_sequence" if sequence_reason and not is_crosslisted_alias(str(relative_path), identity_text) else "course"
        is_course_target = True
        reason_parts = ["The page is under a learning subject category and contains course-like instructional content."]
        if codes:
            reason_parts.append(f"The title/path provides course identifier(s): {', '.join(codes)}.")
        if target_type == "course_sequence" and sequence_reason:
            reason_parts.append(f"Sequence evidence: {sequence_reason}; distinct official identities are retained as separate targets.")
        elif is_crosslisted_alias(str(relative_path), identity_text) and len(codes) > 1:
            reason_parts.append("The page records one cross-listed course; source course numbers are preserved as aliases rather than split into separate targets.")
        if links:
            reason_parts.append(f"It contains {len(links)} labeled outbound resource link(s) for provenance review.")
        reason = " ".join(reason_parts)
        confidence = 0.96 if codes else 0.78
        review_status = "pending_independent_audit" if confidence < 0.9 else "auto_classified_pending_audit"
    else:
        target_type = "other"
        is_course_target = False
        reason = "The page does not provide enough deterministic course evidence; retained for explicit review."
        confidence = 0.45
        review_status = "needs_review"

    base_path = re.sub(r"\.en(?=\.md$)", "", str(relative_path), flags=re.I)
    family_id = f"page-{slugify(str(PurePosixPath(base_path).with_suffix('')))}"
    target_records: list[dict[str, Any]] = []
    if is_course_target:
        if canonical_records:
            records_for_targets = canonical_records[:1] if is_crosslisted_alias(str(relative_path), identity_text) else canonical_records
            cross_listed_codes = [str(record["code"]) for record in canonical_records[1:]] if is_crosslisted_alias(str(relative_path), identity_text) else []
            for record in records_for_targets:
                code = str(record["code"])
                institution = record.get("institution") or institution_for_code(identity_text, record)
                canonical_code = code
                target_record = {
                    "canonical_course_id": course_id_for(title, str(relative_path), canonical_code, institution),
                    "course_number": canonical_code,
                    "institution": institution,
                }
                if cross_listed_codes:
                    target_record["cross_listed_course_numbers"] = cross_listed_codes
                target_records.append(target_record)
        else:
            target_records.append(
                {
                    "canonical_course_id": course_id_for(title, str(relative_path), None, page_institution),
                    "course_number": None,
                    "institution": page_institution,
                }
            )
    target_ids = list(dict.fromkeys(str(record["canonical_course_id"]) for record in target_records))
    if len(target_ids) > 1:
        family_id = f"family-{slugify(title)}"

    page_url = urljoin(SITE_URL, quote(str(relative_path.with_suffix("")), safe="/-._~!$&'()*+,;=:@"))
    return {
        "leaf_key": f"{category_text}::{title}::{relative_path}",
        "nav_category": category_path,
        "nav_title": title,
        "source_markdown_path": str(relative_path),
        "public_page_url": page_url,
        "upstream_commit": commit,
        "page_sha256": sha256_file(page_path) if exists else None,
        "page_exists": exists,
        "page_heading": heading,
        "language": language,
        "outbound_links": links,
        "target_type": target_type,
        "is_course_target": is_course_target,
        "classification_reason": reason,
        "classification_confidence": confidence,
        "classification_review_status": review_status,
        "institution": page_institution,
        "course_numbers": codes,
        "course_title": heading or title,
        "aliases": sorted({value for value in (title, heading) if value}),
        "course_family_id": family_id,
        "course_target_ids": target_ids,
        "course_target_records": target_records,
        "candidate_offerings": candidate_offerings(links),
        "progress": {"state": "classified" if is_course_target else "discovered", "last_successful_checkpoint": "classification"},
    }


def docs_tree_fingerprint(root: Path) -> str:
    entries: list[str] = []
    for path in sorted((root / "docs").rglob("*.md")):
        relative = path.relative_to(root).as_posix()
        entries.append(f"{relative}\t{sha256_file(path)}")
    return sha256_bytes(("\n".join(entries) + "\n").encode())


def snapshot_info(root: Path, previous: dict[str, Any] | None) -> dict[str, Any]:
    commit = snapshot_commit(root)
    retrieved_at = None
    if previous:
        retrieved_at = previous.get("source_catalog", {}).get("retrieved_at")
    if not retrieved_at:
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    mkdocs = root / "mkdocs.yml"
    return {
        "repository_url": REPOSITORY_URL,
        "site_url": SITE_URL,
        "navigation_source": "mkdocs.yml",
        "upstream_root": str(root),
        "pinned_commit": commit,
        "retrieved_at": retrieved_at,
        "mkdocs_sha256": sha256_file(mkdocs),
        "docs_tree_fingerprint": docs_tree_fingerprint(root),
    }


def merge_progress(new: dict[str, Any], old: dict[str, Any] | None) -> dict[str, Any]:
    if not old:
        return new
    result = dict(new)
    for key in (
        "state",
        "progress",
        "candidate_offerings",
        "selected_offering",
        "active_build_id",
        "priority",
        "rejected_terms",
        "source_inventory",
        "manifest_path",
        "build",
        "issues",
        "coverage",
        "audit",
        "retry_count",
        "issue_code",
        "next_action",
    ):
        if key in old:
            result[key] = old[key]
    old_priority = old.get("priority") or {}
    new_priority = new.get("priority") or {}
    if old_priority or new_priority:
        merged_priority = dict(new_priority)
        merged_priority.update(old_priority)
        # Preserve researched readiness and checkpoint fields, but refresh all
        # deterministic classification-derived fields so a corrected category
        # rule also repairs an already-regenerated registry projection.
        for key in (
            "major_direction",
            "direction_evidence",
            "secondary_directions",
            "downstream_prerequisite_value",
            "direction_coverage_gain",
            "learner_demand",
            "priority_cohort",
            "priority_reason",
            "priority_evidence",
        ):
            if key in new_priority:
                merged_priority[key] = new_priority[key]
        result["priority"] = merged_priority
    if old.get("classification_review_status") == "independently_audited":
        result["classification_review_status"] = old["classification_review_status"]
    return result


def build_course_targets(leaves: list[dict[str, Any]], old_targets: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for leaf in leaves:
        for target_id in leaf.get("course_target_ids", []):
            grouped[target_id].append(leaf)

    targets: list[dict[str, Any]] = []
    for target_id in sorted(grouped):
        entries = grouped[target_id]
        first = entries[0]
        target_records = [
            record
            for entry in entries
            for record in entry.get("course_target_records", [])
            if record.get("canonical_course_id") == target_id
        ]
        aliases = sorted({alias for entry in entries for alias in entry.get("aliases", [])})
        candidate_map: dict[str, dict[str, Any]] = {}
        for entry in entries:
            for candidate in entry.get("candidate_offerings", []):
                candidate_map.setdefault(str(candidate["url"]), candidate)
        target = {
            "canonical_course_id": target_id,
            "course_family_id": first["course_family_id"],
            "institution": next((record.get("institution") for record in target_records if record.get("institution")), first.get("institution")),
            "course_numbers": sorted({str(record.get("course_number")) for record in target_records if record.get("course_number")}),
            "cross_listed_course_numbers": sorted({str(number) for record in target_records for number in (record.get("cross_listed_course_numbers") or [])}),
            "title": first.get("course_title") or first.get("nav_title"),
            "aliases": aliases,
            "language_variants": sorted({entry.get("language") for entry in entries if entry.get("language")}),
            "guide_page_provenance": [
                {
                    "leaf_key": entry["leaf_key"],
                    "source_markdown_path": entry["source_markdown_path"],
                    "public_page_url": entry["public_page_url"],
                    "page_sha256": entry["page_sha256"],
                }
                for entry in entries
            ],
            "candidate_offerings": [candidate_map[key] for key in sorted(candidate_map)],
            "priority": priority_fields(
                target_id,
                first.get("course_title") or first.get("nav_title") or target_id,
                infer_direction([str(path) for entry in entries for path in entry.get("nav_category", [])], first.get("course_title") or first.get("nav_title") or target_id),
                [str(path) for entry in entries for path in entry.get("nav_category", [])],
                len(entries),
            ),
            "selected_offering": None,
            "rejected_terms": [],
            "state": "classified",
            "coverage": {
                "raw_inventory_path": None,
                "manifest_path": None,
                "unit_count": 0,
                "source_gaps": [],
                "exclusion_count": 0,
                "chunk_count": 0,
                "page_count": 0,
                "warning_count": 0,
                "empty_count": 0,
                "build_id": None,
                "output_index": None,
            },
            "audit": {"classification": "pending_independent_audit", "last_successful_checkpoint": "classification"},
            "retry_count": 0,
            "issue_code": None,
            "next_action": "research_offering",
            "progress": {"state": "classified", "last_successful_checkpoint": "classification", "retry_count": 0},
        }
        targets.append(merge_progress(target, old_targets.get(target_id)))
    return targets


def sync_nav_leaf_progress(leaves: list[dict[str, Any]], targets: list[dict[str, Any]]) -> None:
    """Project canonical target state back onto each nav leaf.

    A resumed registry historically preserved the leaf's original
    ``classified`` progress forever, even after its canonical target had a
    selected offering or a reconciled build.  That was a projection bug, not
    a change to the target denominator.  Keep the canonical target as the
    authority and make split pages explicit when their targets differ.
    """

    target_by_id = {target.get("canonical_course_id"): target for target in targets}
    for leaf in leaves:
        target_ids = [target_id for target_id in leaf.get("course_target_ids", []) if target_id in target_by_id]
        if not target_ids:
            continue
        states = sorted({str(target_by_id[target_id].get("state") or "classified") for target_id in target_ids})
        progress = dict(leaf.get("progress") or {})
        progress["course_target_ids"] = target_ids
        progress["course_target_states"] = states
        if len(states) == 1:
            progress["state"] = states[0]
            checkpoints = {
                str(target_by_id[target_id].get("audit", {}).get("last_successful_checkpoint") or "")
                for target_id in target_ids
            }
            checkpoints.discard("")
            if len(checkpoints) == 1:
                progress["last_successful_checkpoint"] = next(iter(checkpoints))
        else:
            progress["state"] = "mixed"
            progress["last_successful_checkpoint"] = "canonical_target_projection"
        leaf["progress"] = progress


def render_progress(registry: dict[str, Any]) -> str:
    source = registry["source_catalog"]
    leaves = registry["nav_leaves"]
    targets = registry["course_targets"]
    counts = {
        "all_nav_leaves": len(leaves),
        "course_nav_leaf_count": sum(1 for leaf in leaves if leaf.get("is_course_target")),
        "course_target_count": len(targets),
    }
    for state in STATES:
        counts[state] = sum(1 for target in targets if target.get("state") == state)
    lines = [
        "# CSDIY catalog progress",
        "",
        "This file is generated by `scripts/discover_csdiy_courses.py`; it is a tracked reproducibility record, not a claim that course sources or StudyKits are complete.",
        "",
        f"- Pinned upstream commit: `{source['pinned_commit']}`",
        f"- Repository: {source['repository_url']}",
        f"- Retrieved at: `{source['retrieved_at']}`",
        f"- `mkdocs.yml` SHA-256: `{source['mkdocs_sha256']}`",
        f"- Docs-tree fingerprint: `{source['docs_tree_fingerprint']}`",
        f"- Markdown nav leaves: **{counts['all_nav_leaves']}**",
        f"- Course nav leaves: **{counts['course_nav_leaf_count']}** (pages classified as course material)",
        f"- Course-target denominator: **{counts['course_target_count']}** (canonical identities after sequence splitting and alias deduplication)",
        "",
        "## State counts",
        "",
        "| State | Targets |",
        "| --- | ---: |",
    ]
    for state in STATES:
        if counts[state]:
            lines.append(f"| `{state}` | {counts[state]} |")
    lines += ["", "## Course targets", "", "| Canonical ID | Institution | Title | State | Next action |", "| --- | --- | --- | --- | --- |"]
    for target in targets:
        lines.append(
            f"| `{target['canonical_course_id']}` | {target.get('institution') or 'unknown'} | "
            f"{target.get('title') or 'unknown'} | `{target.get('state')}` | {target.get('next_action') or '—'} |"
        )
    lines += ["", "## Classification caveat", "", "Every Markdown nav leaf is retained in the registry. Pages classified as tools, books, roadmaps, or other are excluded from the course denominator with an explicit reason; low-confidence pages remain marked for review rather than being silently dropped.", ""]
    return "\n".join(lines)


def render_selected_status(registry: dict[str, Any]) -> str:
    source = registry["source_catalog"]
    targets = registry["course_targets"]
    nav_leaf_count = len(registry["nav_leaves"])
    course_nav_leaf_count = sum(1 for leaf in registry["nav_leaves"] if leaf.get("is_course_target"))
    excluded_nav_leaf_count = nav_leaf_count - course_nav_leaf_count
    counts = Counter(target.get("state") for target in targets)
    directions = Counter((target.get("priority") or {}).get("major_direction", "other_computing") for target in targets)
    selected_ids = CURRENT_SEED_IDS | {"ucb-cs61a"} | {
        target.get("canonical_course_id")
        for target in targets
        if target.get("selected_offering")
    }
    lines = [
        "# CSDIY selected course status",
        "",
        "This file is generated from `data/catalog/csdiy-course-registry.yaml`; the registry is the source of truth. It records reproducible catalog progress, not authorization to publish materials into the online StudyKitStore.",
        "",
        f"- Pinned upstream commit: `{source['pinned_commit']}`",
        f"- Retrieval time: `{source['retrieved_at']}`",
        f"- Markdown nav leaves: **{nav_leaf_count}**",
        f"- Course nav leaves: **{course_nav_leaf_count}**",
        f"- Excluded nav leaves: **{excluded_nav_leaf_count}**",
        f"- Canonical course-target denominator: **{len(targets)}**",
        f"- Last registry reconciliation: `{registry.get('last_reconciled_at', 'not recorded')}`",
        "- Reconciliation command: `.venv/bin/python scripts/audit_csdiy_registry.py --registry data/catalog/csdiy-course-registry.yaml --repository-root . --report evaluations/csdiy-catalog-registry-audit.json --update`",
        "- Tracked records: registry, manifests, source reviews, evaluations, reviewed packages and this status projection. Ignored local checkpoints: `data/raw/`, `data/sources/`, `outputs/` and private data.",
        "",
        "## State counts",
        "",
        "| State | Targets |",
        "| --- | ---: |",
    ]
    for state, count in sorted(counts.items()):
        lines.append(f"| `{state}` | {count} |")
    lines += ["", "## Direction coverage", "", "| Direction | Targets |", "| --- | ---: |"]
    for direction, count in sorted(directions.items()):
        lines.append(f"| `{direction}` | {count} |")
    lines += ["", "## Selected courses and leading candidate", "", "| ID | Direction | State | Term/build | Units/chunks | Gaps/visual | Validation/review | Records | Next action |", "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |"]
    for target in targets:
        if target.get("canonical_course_id") not in selected_ids:
            continue
        coverage = target.get("coverage") or {}
        offering = target.get("selected_offering") or {}
        term = offering.get("term_version") or offering.get("course_version") or "not selected"
        checkpoint = target.get("audit", {}).get("last_successful_checkpoint") or target.get("state")
        validated = coverage.get("validated_unit_count", 0)
        audited = coverage.get("audit_passed_unit_count", 0)
        unit_count = coverage.get("unit_count", 0)
        review = f"{validated}/{unit_count} units validated; {audited}/{unit_count} audited; {checkpoint}"
        course_id = offering.get("course_id")
        manifest = coverage.get("manifest_path") or target.get("manifest_path")
        records = []
        if manifest:
            records.append(f"[manifest](../{manifest})")
        if course_id:
            records.extend((f"[review]({course_id}-source-review.md)", f"[parser](../evaluations/{course_id}-parser-results.md)"))
        if coverage.get("output_index"):
            records.append(f"[StudyKit index](../{coverage['output_index']})")
        gaps = len(coverage.get("source_gaps") or [])
        visual = coverage.get("visual_review_status") or target.get("audit", {}).get("visual_review_status") or "not recorded"
        lines.append(f"| `{target.get('canonical_course_id')}` | `{(target.get('priority') or {}).get('major_direction', 'other_computing')}` | `{target.get('state')}` | {term} / `{coverage.get('build_id') or '—'}` | {coverage.get('unit_count', 0)} / {coverage.get('chunk_count', 0)} | {gaps} / `{visual}` | `{review}` | {' · '.join(records) or '—'} | {target.get('next_action') or '—'} |")
    lines += ["", "## Priority rationale", "", "Execution order is breadth-first after the current work: finish the four seed courses, validate UCB CS61A as the programming on-ramp, then cover networks, databases, architecture, programming languages/compilers, security and foundational mathematics before adding near-duplicates.", "", "| Cohort | Meaning |", "| --- | --- |", "| `batch-0-current-work` | MIT 6.7960, MIT 6.S081, CMU 15.213 and UCB CS61B; reuse existing evidence and builds. |", "| `batch-1-programming-onramp` | UCB CS61A; candidate only until a completed official semester and public evidence are verified. |", "| `breadth-before-depth` | Representative courses in currently uncovered directions. |", "| `later-depth` | Additional courses after direction coverage improves. |", "", "## All course targets", "", "| Canonical ID | Direction | Cohort | State | Priority reason |", "| --- | --- | --- | --- | --- |"]
    for target in targets:
        priority = target.get("priority") or {}
        lines.append(f"| `{target.get('canonical_course_id')}` | `{priority.get('major_direction', 'other_computing')}` | `{priority.get('priority_cohort', 'unassigned')}` | `{target.get('state')}` | {priority.get('priority_reason', '—')} |")
    lines += ["", "## Classification and global gate", "", f"- Independent classification audit: `{registry.get('classification', {}).get('independent_audit_status', 'pending')}`.", f"- Current global gate: `{registry.get('global_gate', 'partial')}`; it cannot be `succeeded` while any real course target remains unresearched, incomplete, blocked or unaudited.", "- Source gaps, access failures, vintage mismatches, license limits and academic-integrity exclusions belong in the registry target, manifest and course review; they must not be silently removed from the denominator.", ""]
    return "\n".join(lines)


def discover(upstream_root: Path, output: Path, progress_output: Path, resume: bool = False) -> dict[str, Any]:
    root = upstream_root.resolve()
    mkdocs_path = root / "mkdocs.yml"
    if not mkdocs_path.is_file():
        raise FileNotFoundError(f"missing mkdocs.yml under {root}")
    previous: dict[str, Any] | None = None
    if resume and output.is_file():
        previous = yaml.safe_load(output.read_text(encoding="utf-8")) or {}
    mkdocs = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8")) or {}
    commit = snapshot_commit(root)
    old_leaves = {item.get("leaf_key"): item for item in (previous or {}).get("nav_leaves", [])}
    old_targets = {item.get("canonical_course_id"): item for item in (previous or {}).get("course_targets", [])}
    leaves = []
    for nav_leaf in walk_nav(mkdocs.get("nav", [])):
        leaf = classify_leaf(nav_leaf, root, commit)
        leaves.append(merge_progress(leaf, old_leaves.get(leaf["leaf_key"])))
    leaves.sort(key=lambda item: item["leaf_key"])
    targets = build_course_targets(leaves, old_targets)
    sync_nav_leaf_progress(leaves, targets)
    source = snapshot_info(root, previous)
    source.update(
        {
            "markdown_nav_leaf_count": len(leaves),
            "course_nav_leaf_count": sum(1 for leaf in leaves if leaf["is_course_target"]),
        }
    )
    registry = {
        "registry_version": REGISTRY_VERSION,
        "generated_by": "scripts/discover_csdiy_courses.py",
        "source_catalog": source,
        "last_reconciled_at": (previous or {}).get("last_reconciled_at"),
        "global_gate": (previous or {}).get("global_gate", "partial"),
        "classification": {
            "target_type_values": ["course", "course_sequence", "book", "roadmap", "tool", "other"],
            "review_policy": "ambiguous leaves remain in nav_leaves and are not silently excluded",
            "independent_audit_status": (previous or {}).get("classification", {}).get("independent_audit_status", "pending"),
        },
        "nav_leaves": leaves,
        "course_targets": targets,
    }
    registry["summary"] = {
        "nav_leaf_count": len(leaves),
        "course_nav_leaf_count": sum(1 for leaf in leaves if leaf["is_course_target"]),
        "course_target_count": len(registry["course_targets"]),
        "excluded_leaf_count": sum(1 for leaf in leaves if not leaf["is_course_target"]),
        "target_states": {state: sum(1 for target in registry["course_targets"] if target.get("state") == state) for state in STATES},
    }
    if not output.parent.exists():
        output.parent.mkdir(parents=True, exist_ok=True)
    if not progress_output.parent.exists():
        progress_output.parent.mkdir(parents=True, exist_ok=True)
    return registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress-output", type=Path, default=Path("docs/csdiy-catalog-progress.md"))
    parser.add_argument("--selected-status-output", type=Path, default=Path("docs/csdiy-selected-course-status.md"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = discover(args.upstream_root, args.output, args.progress_output, args.resume)
    rendered = yaml.safe_dump(registry, allow_unicode=True, sort_keys=False, default_flow_style=False)
    if not args.dry_run:
        tmp = args.output.with_name(f".{args.output.name}.tmp")
        tmp.write_text(rendered, encoding="utf-8")
        tmp.replace(args.output)
        progress = args.progress_output.with_name(f".{args.progress_output.name}.tmp")
        progress.write_text(render_progress(registry), encoding="utf-8")
        progress.replace(args.progress_output)
        selected = args.selected_status_output.with_name(f".{args.selected_status_output.name}.tmp")
        selected.write_text(render_selected_status(registry), encoding="utf-8")
        selected.replace(args.selected_status_output)
    print(json.dumps(registry["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
