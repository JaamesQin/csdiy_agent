from __future__ import annotations

from app.generation.generator import _practice_with_feedback_contract


def test_page_only_generator_emits_exact_online_feedback_citations() -> None:
    practice = {
        "id": "p1",
        "source_pages": [2, 7],
    }

    result = _practice_with_feedback_contract(
        practice,
        ({"source_id": "lecture-slides"},),
    )

    assert result["feedback_mode"] == "course_grounded"
    assert result["citations"] == [
        {
            "source_id": "lecture-slides",
            "anchor": {"type": "page", "value": 2},
        },
        {
            "source_id": "lecture-slides",
            "anchor": {"type": "page", "value": 7},
        },
    ]
