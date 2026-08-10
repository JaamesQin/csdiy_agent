from __future__ import annotations

from evaluations.studykit_benchmark.benchmark import anonymous_id, decide_default, normalize_artifact, validate_score
from evaluations.studykit_benchmark.validate_aligned_timing import validate_timing
from evaluations.studykit_benchmark.normalize_v2_metadata import normalize_metrics, normalize_review


def _records(fast_score=90, standard_score=92, fast_time=60, standard_time=100):
    rows = []
    for lecture in ("lecture-02", "lecture-03", "lecture-04", "lecture-08"):
        rows.extend([
            {"lecture_id": lecture, "mode": "fast", "structure_valid": True, "score": fast_score, "critical": 0, "duration_seconds": fast_time, "unresolved_formula": 0, "citation_support_errors": 0},
            {"lecture_id": lecture, "mode": "standard", "structure_valid": True, "score": standard_score, "critical": 0, "duration_seconds": standard_time},
        ])
    return rows


def test_normalization_handles_alternate_fields() -> None:
    normalized = normalize_artifact({"concepts": [{"explanation": "x", "source_refs": [{"anchor": {"type": "page", "value": 2}}], "formula": {"expression": "x"}}]}, pdf_sha256="a" * 64, lecture_id="lecture-02")
    assert normalized["claims"][0]["text"] == "x"
    assert normalized["formulas"][0]["latex"] == "x"


def test_legacy_deepseek_citations_and_embedded_formulas_are_preserved() -> None:
    data = {
        "scope": {"included_sources": [{"source_id": "slides"}]},
        "core_concepts": [{
            "explanation": "Update $x_{k+1}=x_k-\\eta g$.",
            "citations": [{"source_id": "slides", "page": 8}],
        }],
        "practice": [{
            "question": "Explain $QK^T$.", "deliverable": "text", "expected_evidence": ["shape"],
            "source_pages": [29, 34],
        }],
        "citations": [{"source_id": "slides", "pages": "10–12"}],
    }
    normalized = normalize_artifact(data, pdf_sha256="a" * 64, lecture_id="lecture-02")
    assert {item["page"] for item in normalized["anchors"]} == {8, 10, 11, 12, 29, 34}
    claim = normalized["claims"][0]
    assert claim["anchors"][0]["page"] == 8
    assert any(item["latex"] == "x_{k+1}=x_k-\\eta g" and item["anchors"][0]["page"] == 8 for item in normalized["formulas"])
    assert normalized["practice"][0]["anchors"][0]["page"] == 29


def test_normalization_reads_external_metrics() -> None:
    normalized = normalize_artifact({}, pdf_sha256="a" * 64, lecture_id="lecture-02", external_metrics={"stage_duration_seconds": {"total": 12.5}, "input_tokens": 7, "output_tokens": 3})
    assert normalized["duration_seconds"] == 12.5
    assert normalized["tokens"] == {"input": 7, "output": 3}


def test_anonymous_id_is_reproducible_and_label_free() -> None:
    assert anonymous_id("a", "lecture-02", b"{}", "salt") == anonymous_id("a", "lecture-02", b"{}", "salt")
    assert anonymous_id("a", "lecture-02", b'{"duration":1}', "salt") != anonymous_id("a", "lecture-02", b'{"duration":2}', "salt")


def test_critical_overrides_score() -> None:
    score = {"categories": {"source_and_formula": 50, "core_coverage": 15, "pedagogy": 20, "practice": 10, "consistency_usability": 5}, "total": 100, "errors": {"critical": 1}, "eligible": True}
    assert "Critical" in " ".join(validate_score(score))


def test_default_decision_rules() -> None:
    assert decide_default(_records())["default_quality_mode"] == "fast"
    assert decide_default(_records(fast_score=80))["default_quality_mode"] == "standard"
    rows = _records()
    rows[0]["critical"] = 1
    assert decide_default(rows)["default_quality_mode"] == "standard"
    rows = _records()
    for row in rows:
        if row["lecture_id"] == "lecture-03":
            row["unresolved_formula"] = 1
    assert decide_default(rows)["default_quality_mode"] == "fast"
    next(row for row in rows if row["lecture_id"] == "lecture-03" and row["mode"] == "fast")["unresolved_formula"] = 2
    assert decide_default(rows)["default_quality_mode"] == "standard"
    rows = _records()
    rows[0]["duration_seconds"] = 0
    result = decide_default(rows)
    assert result["default_quality_mode"] == "standard"
    assert "timing evidence is incomplete" in result["reasons"]


def test_aligned_timing_rejects_overlapping_modes() -> None:
    summary = {
        "setup": {"started_at": "2026-01-01T00:00:00Z", "completed_at": "2026-01-01T00:00:10Z", "total_duration_seconds": 10},
        "modes": {},
    }
    for index, mode in enumerate(("fast", "standard", "strict")):
        summary["modes"][mode] = {
            "started_at": f"2026-01-01T00:00:{10 + index:02d}Z",
            "completed_at": f"2026-01-01T00:00:{20 + index:02d}Z",
            "total_duration_seconds": 10,
            "stage_durations_seconds": {"work": 10},
            "reviewed_page_count": 1,
        }
    issues = validate_timing(summary)
    assert any("overlaps" in issue for issue in issues)


def test_worker_metadata_normalizes_legacy_keys() -> None:
    review = normalize_review({"mode": "strict", "vision_review": {"pages": [3, 1, 3]}, "formula_review": {"pages": [3]}, "independent_audit": {"completed": True}}, "strict")
    assert review["selected_pages"] == [1, 3]
    assert review["actual_reviewed_pages"] == [1, 3]
    assert review["required_final_formula_pages"] == [3]
    assert review["independent_audit"] is True
    metrics = normalize_metrics({"repairs": 1}, review, "strict")
    assert metrics["reviewed_page_count"] == 2
    assert len(metrics["repairs"]) == 1
