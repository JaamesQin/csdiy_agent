"""Source-partitioned output validation and transparent degradation."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.contracts import AnswerClaim, ProvenanceKind


@dataclass(frozen=True, slots=True)
class ProvenanceResult:
    claims: list[AnswerClaim]
    dropped_course_material: bool
    notices: list[str]


def enforce_provenance(
    claims: list[AnswerClaim],
    *,
    allowed_citation_ids: set[str] | None = None,
    allowed_catalog_ids: set[str] | None = None,
    allowed_diagnostic_ids: set[str] | None = None,
) -> ProvenanceResult:
    """Validate IDs per partition, dropping course material as one atomic section."""

    allowed_citations = allowed_citation_ids or set()
    allowed_catalog = allowed_catalog_ids or set()
    allowed_diagnostics = allowed_diagnostic_ids or set()
    course_claims = [
        claim for claim in claims if claim.provenance is ProvenanceKind.COURSE_MATERIAL
    ]
    course_valid = all(
        claim.supported and set(claim.citation_ids) <= allowed_citations
        for claim in course_claims
    )
    kept: list[AnswerClaim] = []
    notices: list[str] = []
    if course_claims and not course_valid:
        notices.append("课程资料部分因证据不足或引用无效而未显示。")
    for claim in claims:
        if claim.provenance is ProvenanceKind.COURSE_MATERIAL:
            if course_valid:
                kept.append(claim)
        elif claim.provenance is ProvenanceKind.CATALOG_METADATA:
            if claim.supported and set(claim.catalog_ids) <= allowed_catalog:
                kept.append(claim)
        elif claim.provenance is ProvenanceKind.STATIC_ANALYSIS:
            if claim.supported and set(claim.diagnostic_ids) <= allowed_diagnostics:
                kept.append(claim)
        elif claim.supported:
            kept.append(claim)
    return ProvenanceResult(
        claims=kept,
        dropped_course_material=bool(course_claims and not course_valid),
        notices=notices,
    )


def render_claims(result: ProvenanceResult) -> str:
    grouped: dict[ProvenanceKind, list[str]] = {}
    for claim in result.claims:
        grouped.setdefault(claim.provenance, []).append(claim.text)
    labels = {
        ProvenanceKind.COURSE_MATERIAL: "课程资料依据",
        ProvenanceKind.CATALOG_METADATA: "课程目录信息",
        ProvenanceKind.STATIC_ANALYSIS: "静态分析",
        ProvenanceKind.GENERAL_KNOWLEDGE: "通用知识（不代表当前课程材料）",
    }
    sections: list[str] = []
    for provenance in ProvenanceKind:
        content = grouped.get(provenance)
        if content:
            sections.append(f"### {labels[provenance]}\n" + "\n\n".join(content))
    if result.notices:
        sections.append("\n".join(result.notices))
    return "\n\n".join(sections)
