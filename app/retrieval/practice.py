"""Stateless practice presentation and feedback rendering."""

from __future__ import annotations

from typing import Any


def find_practice(studykit: dict[str, Any], practice_id: str) -> dict[str, Any]:
    for problem in studykit["practice"]:
        if problem["id"] == practice_id:
            return problem
    raise KeyError(f"unknown practice id: {practice_id}")


def render_practice_prompt(
    studykit: dict[str, Any], practice_id: str, *, include_hint: bool = False
) -> str:
    problem = find_practice(studykit, practice_id)
    parts = [f"### {problem['id']}", f"类型：{problem['level']}"]
    setup = problem.get("setup") or problem.get("setup_code")
    if isinstance(setup, list):
        parts.append("\n".join(f"- {item}" for item in setup))
    elif setup:
        fence = "python" if problem.get("setup_code") else "text"
        parts.append(f"```{fence}\n{str(setup).strip()}\n```")
    parts.extend([problem["question"], f"作答要求：{problem['deliverable']}"])
    if include_hint:
        parts.append(f"提示：{problem['hint']}")
    return "\n\n".join(parts)


def render_current_answer_feedback(
    *,
    correct_points: list[str],
    correction: str | None,
    source_pages: list[int],
) -> str:
    parts = ["### 本题点评"]
    if correct_points:
        parts.append("答对的部分：\n" + "\n".join(f"- {item}" for item in correct_points))
    if correction:
        parts.append(f"需要修正：{correction}")
    pages = "、".join(str(page) for page in sorted(set(source_pages)))
    parts.append(f"讲义依据：第 {pages} 页")
    return "\n\n".join(parts)
