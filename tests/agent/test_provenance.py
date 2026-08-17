from __future__ import annotations

from app.agent.contracts import AnswerClaim, ProvenanceKind
from app.agent.provenance import enforce_provenance, render_claims


def test_invalid_course_claim_drops_course_partition_but_keeps_general_knowledge() -> None:
    result = enforce_provenance(
        [
            AnswerClaim(
                text="合法课程结论",
                provenance=ProvenanceKind.COURSE_MATERIAL,
                citation_ids=["chunk-1"],
            ),
            AnswerClaim(
                text="伪造课程结论",
                provenance=ProvenanceKind.COURSE_MATERIAL,
                citation_ids=["invented"],
            ),
            AnswerClaim(
                text="一个独立生成的通用解释。",
                provenance=ProvenanceKind.GENERAL_KNOWLEDGE,
            ),
        ],
        allowed_citation_ids={"chunk-1"},
    )

    rendered = render_claims(result)
    assert result.dropped_course_material is True
    assert "合法课程结论" not in rendered
    assert "伪造课程结论" not in rendered
    assert "通用知识（不代表当前课程材料）" in rendered
