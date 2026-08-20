from __future__ import annotations

import json
from pathlib import Path

from scripts.update_csdiy_hybrid_progress import render


def test_hybrid_progress_uses_root_course_summary_counts(tmp_path: Path) -> None:
    output = tmp_path / "outputs" / "mit-6-042j-spring-2024" / "build-1"
    output.mkdir(parents=True)
    (output / "course-summary.json").write_text(
        json.dumps(
            {
                "requested_unit_count": 24,
                "completed_unit_count": 23,
                "validated_unit_count": 24,
                "audited_unit_count": 23,
                "failed_unit_count": 1,
                "pending_unit_count": 0,
                "status": "partial",
            }
        ),
        encoding="utf-8",
    )
    registry = {
        "course_targets": [
            {
                "canonical_course_id": "mit-6-042j",
                "coverage": {
                    "build_id": "build-1",
                    "output_index": "outputs/mit-6-042j-spring-2024/build-1",
                    "unit_count": 99,
                    "validated_unit_count": 99,
                    "audit_passed_unit_count": 99,
                },
            }
        ]
    }

    rendered = render(tmp_path, registry, generated_at="fixture")

    assert "MIT 6.042J | 23 / 24 | 95.8% | 23 | 24 | 1 | 0 | `partial`" in rendered
    assert "Course-target" not in rendered


def test_hybrid_progress_does_not_guess_missing_root_summary(tmp_path: Path) -> None:
    rendered = render(tmp_path, {"course_targets": []}, generated_at="fixture")

    assert "`not_reconciled`" in rendered
    assert "**当前合计** | **0 / 0**" in rendered


def test_hybrid_progress_distinguishes_deferred_practice_from_future_quality_gate(
    tmp_path: Path,
) -> None:
    rendered = render(tmp_path, {"course_targets": []}, generated_at="fixture")

    assert "已存在的 practice 语义问题本轮只登记为延期问题" in rendered
    assert "新生成或修复的单元仍须逐题满足 StudyKit practice 契约" in rendered
    assert "真实 source_id@page 锚点" in rendered
