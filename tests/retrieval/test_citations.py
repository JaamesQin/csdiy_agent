from __future__ import annotations

from app.retrieval.citations import validate_citations


def test_missing_and_empty_pages_are_reported() -> None:
    studykit = {
        "scope": {"included_sources": [{"source_id": "slides"}]},
        "core_concepts": [
            {"citations": [{"source_id": "slides", "page": 2}]},
            {"citations": [{"source_id": "slides", "page": 3}]},
        ],
        "practice": [],
        "citations": [],
    }
    chunks = [
        {
            "source_id": "slides",
            "anchor": {"type": "page", "value": 2},
            "content": "",
        }
    ]

    issues = validate_citations(studykit, chunks)

    assert [issue.reason for issue in issues] == ["empty_page_text", "page_not_parsed"]
