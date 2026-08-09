#!/usr/bin/env python3
"""Normalize, anonymize, validate scores, and decide the default quality mode."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from statistics import mean
from typing import Any, Iterable


LECTURES = ("lecture-02", "lecture-03", "lecture-04", "lecture-08")
CATEGORIES = {
    "source_and_formula": 50,
    "core_coverage": 15,
    "pedagogy": 20,
    "practice": 10,
    "consistency_usability": 5,
}


def _walk(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _pages(value: Any) -> list[int]:
    if isinstance(value, int):
        return [value] if value > 0 else []
    if isinstance(value, list):
        return sorted({page for item in value for page in _pages(item)})
    if not isinstance(value, str):
        return []
    result: set[int] = set()
    for start, end in re.findall(r"(\d+)(?:\s*[-–—]\s*(\d+))?", value):
        first, last = int(start), int(end or start)
        if 0 < first <= last and last - first <= 500:
            result.update(range(first, last + 1))
    return sorted(result)


def _normalized_citations(value: Any, pdf_sha256: str, default_source_id: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        value = [value]
    result: list[dict[str, Any]] = []
    for citation in value:
        if not isinstance(citation, dict):
            continue
        source_id = citation.get("source_id") or default_source_id
        anchor = citation.get("anchor") or citation.get("source_anchor")
        pages: list[int] = []
        if isinstance(anchor, dict) and anchor.get("type") == "page":
            pages = _pages(anchor.get("value"))
        if not pages:
            pages = _pages(citation.get("page") or citation.get("pages") or citation.get("source_pages"))
        for page in pages:
            result.append({"pdf_sha256": pdf_sha256, "source_id": source_id, "page": page})
    return result


def _latex_spans(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    spans = re.findall(r"(?<!\\)\$\$?(.+?)(?<!\\)\$\$?", text, flags=re.DOTALL)
    return [re.sub(r"\s+", " ", span).strip() for span in spans if span.strip()]


def normalize_artifact(data: dict[str, Any], *, pdf_sha256: str, lecture_id: str, external_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Map Codex or DeepSeek-shaped artifacts to a common semantic object."""
    claims, formulas, objectives, practices, limitations, anchors = [], [], [], [], [], []
    included = data.get("scope", {}).get("included_sources", []) if isinstance(data.get("scope"), dict) else []
    default_source_id = included[0].get("source_id") if included and isinstance(included[0], dict) else None
    for node in _walk(data):
        node_citations = _normalized_citations(
            node.get("citations") or node.get("source_refs") or node,
            pdf_sha256,
            default_source_id,
        )
        if not node_citations and node.get("source_pages") is not None:
            node_citations = _normalized_citations(
                {"source_id": node.get("source_id") or default_source_id, "source_pages": node["source_pages"]},
                pdf_sha256,
                default_source_id,
            )
        anchors.extend(node_citations)
        formula = node.get("formula")
        if isinstance(formula, dict):
            formulas.append({
                "latex": formula.get("latex") or formula.get("expression"),
                "status": formula.get("status", "resolved"),
                "anchors": node_citations or _normalized_citations(formula.get("citation"), pdf_sha256, default_source_id),
                "origin": "structured",
            })
        if "objective" in node:
            objectives.append(str(node["objective"]))
        if "question" in node and ("deliverable" in node or "expected_evidence" in node):
            practice = {key: node.get(key) for key in ("question", "hint", "deliverable", "expected_evidence", "evaluation")}
            practice["anchors"] = node_citations
            practices.append(practice)
        if "explanation" in node and ("citations" in node or "source_refs" in node):
            claims.append({"text": node["explanation"], "anchors": node_citations})
        text_fields = [node.get(key) for key in ("explanation", "question", "objective", "summary")]
        for text_value in text_fields:
            for latex in _latex_spans(text_value):
                formulas.append({"latex": latex, "status": "text_embedded", "anchors": node_citations, "origin": "text"})
    raw_limits = data.get("limitations") or data.get("warnings") or []
    limitations.extend(str(item) for item in raw_limits)
    metrics = external_metrics or data.get("metrics", {})
    stage_durations = metrics.get("stage_duration_seconds", {}) if isinstance(metrics, dict) else {}
    unique_anchors = list({(item["pdf_sha256"], item.get("source_id"), item["page"]): item for item in anchors}.values())
    unique_formulas = list({
        (item.get("latex"), item.get("status"), tuple(anchor["page"] for anchor in item.get("anchors", []))): item
        for item in formulas if item.get("latex") or item.get("status") == "formula_unresolved"
    }.values())
    return {
        "lecture_id": lecture_id,
        "pdf_sha256": pdf_sha256,
        "claims": claims,
        "formulas": unique_formulas,
        "objectives": objectives,
        "practice": practices,
        "limitations": limitations,
        "anchors": sorted(unique_anchors, key=lambda item: (item["page"], item.get("source_id") or "")),
        "duration_seconds": metrics.get("duration_seconds") or metrics.get("total_duration_seconds") or stage_durations.get("total") or data.get("duration_seconds"),
        "reviewed_page_count": metrics.get("reviewed_page_count"),
        "semantic_passes": metrics.get("semantic_passes"),
        "tokens": metrics.get("tokens") or (
            {"input": metrics.get("input_tokens"), "output": metrics.get("output_tokens")}
            if metrics.get("input_tokens") is not None or metrics.get("output_tokens") is not None else data.get("token_usage")
        ),
    }


def anonymous_id(pdf_sha256: str, lecture_id: str, artifact_bytes: bytes, salt: str) -> str:
    digest = hashlib.sha256(salt.encode() + b"\0" + pdf_sha256.encode() + b"\0" + lecture_id.encode() + b"\0" + artifact_bytes).hexdigest()
    return f"sample-{digest[:16]}"


def validate_score(score: dict[str, Any]) -> list[str]:
    issues = []
    categories = score.get("categories", {})
    for name, maximum in CATEGORIES.items():
        value = categories.get(name)
        if not isinstance(value, (int, float)) or not 0 <= value <= maximum:
            issues.append(f"{name} must be within 0..{maximum}")
    calculated = sum(categories.get(name, 0) for name in CATEGORIES)
    if score.get("total") != calculated:
        issues.append(f"total must equal {calculated}")
    critical = int(score.get("errors", {}).get("critical", 0))
    if critical and score.get("eligible", True):
        issues.append("Critical errors must set eligible=false regardless of total")
    return issues


def decide_default(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the fixed fast-vs-standard non-inferiority rules."""
    by_mode = {mode: [r for r in records if r.get("mode") == mode] for mode in ("fast", "standard")}
    reasons: list[str] = []
    for mode in by_mode:
        missing = set(LECTURES) - {r.get("lecture_id") for r in by_mode[mode]}
        if missing:
            reasons.append(f"{mode} missing lectures: {sorted(missing)}")
    fast, standard = by_mode["fast"], by_mode["standard"]
    if any(not r.get("structure_valid", False) for r in fast):
        reasons.append("fast structure validation failed")
    if any(r.get("critical", 0) for r in fast):
        reasons.append("fast has Critical errors")
    for lecture in LECTURES:
        f = [r for r in fast if r.get("lecture_id") == lecture]
        s = [r for r in standard if r.get("lecture_id") == lecture]
        if f and s:
            if mean(x["score"] for x in f) < mean(x["score"] for x in s) - 5:
                reasons.append(f"fast is over 5 points lower on {lecture}")
            if sum(x.get("critical", 0) for x in f) > sum(x.get("critical", 0) for x in s):
                reasons.append(f"fast adds Critical errors on {lecture}")
    if fast and standard and mean(r["score"] for r in fast) < mean(r["score"] for r in standard) - 3:
        reasons.append("fast average is over 3 points lower")
    timing_complete = all(float(r.get("duration_seconds") or 0) > 0 for r in fast + standard)
    fast_time = sum(float(r.get("duration_seconds") or 0) for r in fast)
    standard_time = sum(float(r.get("duration_seconds") or 0) for r in standard)
    if not timing_complete:
        reasons.append("timing evidence is incomplete")
    elif not standard_time or fast_time > standard_time * 0.70:
        reasons.append("fast is not at least 30% faster")
    for lecture in LECTURES:
        f = [r for r in fast if r.get("lecture_id") == lecture]
        s = [r for r in standard if r.get("lecture_id") == lecture]
        if f and s:
            if mean(r.get("unresolved_formula", 0) for r in f) > mean(r.get("unresolved_formula", 0) for r in s):
                reasons.append(f"fast adds unresolved formulas on {lecture}")
            if mean(r.get("citation_support_errors", 0) for r in f) > mean(r.get("citation_support_errors", 0) for r in s):
                reasons.append(f"fast adds citation support errors on {lecture}")
    return {
        "decision_version": "default-mode-v1",
        "lectures": list(LECTURES),
        "default_quality_mode": "fast" if not reasons else "standard",
        "fast_passed_all_rules": not reasons,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    normalize = sub.add_parser("normalize")
    normalize.add_argument("--artifact", type=Path, required=True)
    normalize.add_argument("--pdf-sha256", required=True)
    normalize.add_argument("--lecture-id", choices=LECTURES, required=True)
    normalize.add_argument("--salt", required=True)
    normalize.add_argument("--metrics", type=Path)
    normalize.add_argument("--output", type=Path, required=True)
    normalize.add_argument("--blind-dir", type=Path)
    decide = sub.add_parser("decide")
    decide.add_argument("--records", type=Path, required=True)
    decide.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "normalize":
        raw = args.artifact.read_bytes()
        external_metrics = json.loads(args.metrics.read_text(encoding="utf-8")) if args.metrics else None
        data = normalize_artifact(json.loads(raw), pdf_sha256=args.pdf_sha256, lecture_id=args.lecture_id, external_metrics=external_metrics)
        normalized_bytes = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        data["anonymous_id"] = anonymous_id(args.pdf_sha256, args.lecture_id, normalized_bytes, args.salt)
        # The anonymous file intentionally contains no provider or quality-mode label.
        result = data
    else:
        records = json.loads(args.records.read_text(encoding="utf-8"))
        result = decide_default(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.command == "normalize" and args.blind_dir:
        args.blind_dir.mkdir(parents=True, exist_ok=True)
        blind_path = args.blind_dir / f"{result['anonymous_id']}.json"
        blind_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "succeeded", "output": str(args.output), "anonymous_id": result.get("anonymous_id")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
