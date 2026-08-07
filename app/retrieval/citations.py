"""Validate StudyKit page citations against parsed SourceChunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CitationIssue:
    location: str
    source_id: str
    page: int
    reason: str


def _expand_pages(value: str) -> list[int]:
    match = re.fullmatch(r"(\d+)(?:[–-](\d+))?", value.strip())
    if not match:
        raise ValueError(f"unsupported page range: {value}")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if end < start:
        raise ValueError(f"descending page range: {value}")
    return list(range(start, end + 1))


def iter_studykit_citations(studykit: dict[str, Any]) -> Iterable[tuple[str, str, int]]:
    default_source = studykit["scope"]["included_sources"][0]["source_id"]
    for index, concept in enumerate(studykit.get("core_concepts", [])):
        for citation in concept.get("citations", []):
            yield (
                f"core_concepts[{index}]",
                citation["source_id"],
                int(citation["page"]),
            )
    for index, practice in enumerate(studykit.get("practice", [])):
        for page in practice.get("source_pages", []):
            yield f"practice[{index}]", default_source, int(page)
    for index, misconception in enumerate(
        studykit.get("common_misconceptions", [])
    ):
        for support in misconception.get("support", []):
            yield (
                f"common_misconceptions[{index}]",
                default_source,
                int(support["page"]),
            )
    for index, citation in enumerate(studykit.get("citations", [])):
        for page in _expand_pages(citation["pages"]):
            yield f"citations[{index}]", citation["source_id"], page


def validate_citations(
    studykit: dict[str, Any], chunks: Iterable[dict[str, Any]]
) -> list[CitationIssue]:
    page_index = {
        (chunk["source_id"], int(chunk["anchor"]["value"])): chunk
        for chunk in chunks
        if chunk["anchor"]["type"] == "page"
    }
    issues: list[CitationIssue] = []
    for location, source_id, page in iter_studykit_citations(studykit):
        chunk = page_index.get((source_id, page))
        if chunk is None:
            issues.append(CitationIssue(location, source_id, page, "page_not_parsed"))
        elif not chunk["content"].strip():
            issues.append(CitationIssue(location, source_id, page, "empty_page_text"))
    return issues
