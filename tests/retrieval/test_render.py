from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from app.retrieval.practice import (
    render_current_answer_feedback,
    render_practice_prompt,
)
from app.retrieval.render import render_studykit_markdown
from app.retrieval.schema_validation import load_yaml

ROOT = Path(__file__).parents[2]
STUDYKIT = ROOT / "data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml"


def test_user_render_hides_internal_rubric() -> None:
    rendered = render_studykit_markdown(load_yaml(STUDYKIT))

    assert "# Lecture 2: How to Train a Neural Net" in rendered
    assert "full_credit" not in rendered
    assert "partial_credit" not in rendered
    assert "expected_evidence" not in rendered


def test_practice_hint_is_only_rendered_on_request() -> None:
    studykit = load_yaml(STUDYKIT)

    initial = render_practice_prompt(studykit, "practice-concept-01")
    hinted = render_practice_prompt(
        studykit, "practice-concept-01", include_hint=True
    )

    assert "提示：" not in initial
    assert "提示：" in hinted


def test_feedback_is_current_answer_only() -> None:
    feedback = render_current_answer_feedback(
        correct_points=["区分了梯度计算和参数更新"],
        correction="学习率用于参数更新阶段。",
        source_pages=[44, 8],
    )

    assert "答对的部分" in feedback
    assert "需要修正" in feedback
    assert "第 8、44 页" in feedback
    assert "正确率" not in feedback


def test_user_render_preserves_markdown_latex() -> None:
    studykit = deepcopy(load_yaml(STUDYKIT))
    studykit["core_concepts"][0]["explanation"] = (
        r"行内公式 $\theta_{k+1}=\theta_k-\eta\nabla J(\theta_k)$。"
    )
    studykit["practice"][0]["question"] = (
        r"计算 $\frac{\partial J}{\partial \theta}$。"
    )
    studykit["practice"][0]["deliverable"] = (
        "$$\\nabla_\\theta J=0$$"
    )

    rendered = render_studykit_markdown(studykit)

    assert r"$\theta_{k+1}=\theta_k-\eta\nabla J(\theta_k)$" in rendered
    assert r"$\frac{\partial J}{\partial \theta}$" in rendered
    assert "$$\\nabla_\\theta J=0$$" in rendered
