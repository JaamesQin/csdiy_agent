from __future__ import annotations

from app.retrieval.parser import infer_heading, normalize_pdf_text


def test_normalize_pdf_text_removes_hidden_formula_noise() -> None:
    text = """
    Computation Graphs
    <latexit
    sha1_base64="abc"
    Useful explanation.
    """

    normalized, warnings = normalize_pdf_text(text)

    assert normalized == "Computation Graphs\nUseful explanation."
    assert "removed_hidden_formula_noise_lines:2" in warnings


def test_normalize_pdf_text_deduplicates_page_local_accessibility_text() -> None:
    normalized, warnings = normalize_pdf_text(
        "Title\nRepeated description\nRepeated description"
    )

    assert normalized == "Title\nRepeated description"
    assert "removed_duplicate_lines:1" in warnings


def test_infer_heading_uses_first_plausible_line() -> None:
    assert infer_heading("26\nComputation Graphs\nMore") == "Computation Graphs"
