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
from collections import defaultdict
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
SEQUENCE_MARKERS = ("/", "&", "a&b", "a/b", "sequence", "系列", "i&ii")


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
            return f"{prefix}-{slugify(title)}"
    if code:
        return slugify(code)
    base = re.sub(r"\.en(?=\.md$)", "", source_path, flags=re.I)
    base = str(PurePosixPath(base).with_suffix(""))
    return slugify(title) if title else slugify(base)


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
    code_records = course_code_records(identity_header)
    codes = [str(record["code"]) for record in code_records]
    page_institution = institution_for(identity_header, codes[0] if codes else None)
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
        target_type = "course_sequence" if len(codes) > 1 or any(marker in title.lower() for marker in SEQUENCE_MARKERS) else "course"
        is_course_target = True
        reason_parts = ["The page is under a learning subject category and contains course-like instructional content."]
        if codes:
            reason_parts.append(f"The title/path provides course identifier(s): {', '.join(codes)}.")
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
    target_records: list[dict[str, str | None]] = []
    if is_course_target:
        if code_records:
            for record in code_records:
                code = str(record["code"])
                institution = institution_for_code(identity_header, record)
                canonical_code = canonical_course_number(institution, code)
                target_records.append(
                    {
                        "canonical_course_id": course_id_for(title, str(relative_path), canonical_code, institution),
                        "course_number": canonical_code,
                        "institution": institution,
                    }
                )
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
    commit = git_value(root, ["rev-parse", "HEAD"], "unknown") or "unknown"
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
        "selected_offering",
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


def render_progress(registry: dict[str, Any]) -> str:
    source = registry["source_catalog"]
    leaves = registry["nav_leaves"]
    targets = registry["course_targets"]
    counts = {"all_nav_leaves": len(leaves), "course_target_count": len(targets)}
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
        f"- Course-target denominator: **{counts['course_target_count']}**",
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


def discover(upstream_root: Path, output: Path, progress_output: Path, resume: bool = False) -> dict[str, Any]:
    root = upstream_root.resolve()
    mkdocs_path = root / "mkdocs.yml"
    if not mkdocs_path.is_file():
        raise FileNotFoundError(f"missing mkdocs.yml under {root}")
    previous: dict[str, Any] | None = None
    if resume and output.is_file():
        previous = yaml.safe_load(output.read_text(encoding="utf-8")) or {}
    mkdocs = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8")) or {}
    commit = git_value(root, ["rev-parse", "HEAD"], "unknown") or "unknown"
    old_leaves = {item.get("leaf_key"): item for item in (previous or {}).get("nav_leaves", [])}
    old_targets = {item.get("canonical_course_id"): item for item in (previous or {}).get("course_targets", [])}
    leaves = []
    for nav_leaf in walk_nav(mkdocs.get("nav", [])):
        leaf = classify_leaf(nav_leaf, root, commit)
        leaves.append(merge_progress(leaf, old_leaves.get(leaf["leaf_key"])))
    leaves.sort(key=lambda item: item["leaf_key"])
    source = snapshot_info(root, previous)
    source.update(
        {
            "markdown_nav_leaf_count": len(leaves),
            "course_leaf_count": sum(1 for leaf in leaves if leaf["is_course_target"]),
        }
    )
    registry = {
        "registry_version": REGISTRY_VERSION,
        "generated_by": "scripts/discover_csdiy_courses.py",
        "source_catalog": source,
        "classification": {
            "target_type_values": ["course", "course_sequence", "book", "roadmap", "tool", "other"],
            "review_policy": "ambiguous leaves remain in nav_leaves and are not silently excluded",
            "independent_audit_status": (previous or {}).get("classification", {}).get("independent_audit_status", "pending"),
        },
        "nav_leaves": leaves,
        "course_targets": build_course_targets(leaves, old_targets),
    }
    registry["summary"] = {
        "nav_leaf_count": len(leaves),
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
    print(json.dumps(registry["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
