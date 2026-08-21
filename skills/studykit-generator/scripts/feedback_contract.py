"""Shared deterministic checks for the online practice-feedback evidence contract."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def evaluate_feedback_contract(
    studykit: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    require_explicit: bool | None = None,
) -> dict[str, Any]:
    """Classify practices and report declarations that cannot work online."""

    if require_explicit is None:
        require_explicit = studykit.get("studykit_version") == "0.2.2"
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_anchor: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        source_id = chunk.get("source_id")
        anchor = chunk.get("anchor")
        if isinstance(chunk_id, str):
            by_id[chunk_id].append(chunk)
        if isinstance(source_id, str) and isinstance(anchor, dict):
            anchor_type = anchor.get("type")
            anchor_value = anchor.get("value")
            if isinstance(anchor_type, str) and isinstance(anchor_value, (str, int)):
                by_anchor[(source_id, anchor_type, str(anchor_value))].append(chunk)

    counts = {
        "course_grounded": 0,
        "general_only": 0,
        "unresolved": 0,
        "declaration_mismatch": 0,
    }
    issues: list[dict[str, str]] = []
    for index, practice in enumerate(studykit.get("practice", [])):
        if not isinstance(practice, dict):
            continue
        location = f"practice[{index}]"
        citations = _practice_citations(practice, studykit)
        declared = practice.get("feedback_mode")
        resolved = [
            _resolve_citation(citation, by_id, by_anchor, studykit)
            for citation in citations
        ]
        within_online_limit = len(citations) <= 16
        all_resolved = (
            bool(citations)
            and within_online_limit
            and all(chunk is not None for chunk in resolved)
        )

        if not within_online_limit:
            counts["unresolved"] += 1
            issues.append(
                _issue(
                    location,
                    "practice_evidence_limit_exceeded",
                    "course-grounded practice has more than 16 exact references",
                )
            )

        if declared not in {"course_grounded", "general_only"}:
            if require_explicit:
                counts["declaration_mismatch"] += 1
                issues.append(
                    _issue(location, "feedback_mode_missing", "v0.2.2 practice must declare feedback_mode")
                )
            declared = "course_grounded" if all_resolved else "general_only"

        counts[declared] += 1
        if declared == "general_only" and citations:
            counts["declaration_mismatch"] += 1
            issues.append(
                _issue(location, "general_only_has_citations", "general_only practice must have no citations")
            )
        if declared == "course_grounded" and not citations:
            counts["declaration_mismatch"] += 1
            issues.append(
                _issue(location, "course_grounded_without_citations", "course_grounded practice needs citations")
            )
        if citations and within_online_limit and not all_resolved:
            counts["unresolved"] += 1
            issues.append(
                _issue(location, "practice_evidence_unresolved", "practice citation does not resolve to one visible identity-matched chunk")
            )
    return {**counts, "issues": issues}


def _practice_citations(
    practice: dict[str, Any], studykit: dict[str, Any]
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for field in ("citations", "page_citations", "source_anchors", "anchors"):
        values = practice.get(field)
        if isinstance(values, list):
            citations.extend(value for value in values if isinstance(value, dict))
    source_id = _single_included_source_id(studykit)
    source_pages = practice.get("source_pages")
    if source_id is not None and isinstance(source_pages, list):
        citations.extend(
            {
                "source_id": source_id,
                "anchor": {"type": "page", "value": page},
            }
            for page in source_pages
            if isinstance(page, int) and page > 0
        )
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for citation in citations:
        chunk_id = citation.get("chunk_id")
        citation_source_id = citation.get("source_id")
        anchor = citation.get("anchor")
        if isinstance(chunk_id, str) and chunk_id:
            identity = ("chunk", chunk_id, "")
        elif isinstance(citation_source_id, str) and isinstance(anchor, dict):
            identity = (
                citation_source_id,
                str(anchor.get("type")),
                str(anchor.get("value")),
            )
        else:
            identity = ("invalid", str(len(result)), "")
        if identity not in seen:
            seen.add(identity)
            result.append(citation)
    return result


def _single_included_source_id(studykit: dict[str, Any]) -> str | None:
    scope = studykit.get("scope")
    sources = scope.get("included_sources") if isinstance(scope, dict) else None
    if not isinstance(sources, list):
        return None
    source_ids = {
        str(source["source_id"])
        for source in sources
        if isinstance(source, dict) and source.get("source_id")
    }
    return next(iter(source_ids)) if len(source_ids) == 1 else None


def _resolve_citation(
    citation: Any,
    by_id: dict[str, list[dict[str, Any]]],
    by_anchor: dict[tuple[str, str, str], list[dict[str, Any]]],
    studykit: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(citation, dict):
        return None
    chunk_id = citation.get("chunk_id")
    source_id = citation.get("source_id")
    anchor = citation.get("anchor")
    candidates: list[dict[str, Any]]
    if isinstance(chunk_id, str) and chunk_id:
        candidates = by_id.get(chunk_id, [])
    elif isinstance(source_id, str) and isinstance(anchor, dict):
        anchor_type = anchor.get("type")
        anchor_value = anchor.get("value")
        if not isinstance(anchor_type, str) or not isinstance(anchor_value, (str, int)):
            return None
        candidates = by_anchor.get((source_id, anchor_type, str(anchor_value)), [])
    else:
        return None
    if len(candidates) != 1:
        return None
    chunk = candidates[0]
    if chunk.get("scope") != "public" or _hidden(chunk):
        return None
    for field in ("course_id", "course_version", "unit_id"):
        expected = studykit.get(field)
        actual = chunk.get(field)
        if expected is not None and actual != expected:
            return None
    if isinstance(source_id, str) and chunk.get("source_id") != source_id:
        return None
    if isinstance(anchor, dict):
        chunk_anchor = chunk.get("anchor")
        if not isinstance(chunk_anchor, dict):
            return None
        if (
            chunk_anchor.get("type") != anchor.get("type")
            or str(chunk_anchor.get("value")) != str(anchor.get("value"))
        ):
            return None
    return chunk


def _hidden(chunk: dict[str, Any]) -> bool:
    return chunk.get("content_type") == "hidden_text" or any(
        "hidden" in str(warning).casefold()
        for warning in chunk.get("parse_warnings", [])
    )


def _issue(location: str, code: str, message: str) -> dict[str, str]:
    return {"location": location, "code": code, "message": message}
