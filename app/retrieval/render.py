"""Render internal StudyKit YAML as user-facing Markdown."""

from __future__ import annotations

from typing import Any

from app.retrieval.practice import render_practice_prompt


def render_studykit_markdown(studykit: dict[str, Any]) -> str:
    lines = [
        f"# {studykit['title']}",
        "",
        f"> 版本：{studykit['course_version'] or '未知'} · 状态：{studykit['status']}",
        "",
        "## 学习目标",
        "",
    ]
    for item in studykit["learning_objectives"]:
        lines.append(f"- {item['objective']}")

    lines.extend(["", "## 前置知识", ""])
    for item in studykit["prerequisites"]["items"]:
        lines.append(f"- {item['topic']}：{item['required_level']}")

    lines.extend(["", "## 学习提纲", ""])
    for item in studykit["outline"]:
        lines.append(
            f"{item['order']}. **{item['topic']}**（第 {item['pages']} 页）：{item['purpose']}"
        )

    lines.extend(["", "## 核心概念", ""])
    for concept in studykit["core_concepts"]:
        pages = "、".join(str(item["page"]) for item in concept["citations"])
        lines.extend(
            [
                f"### {concept['term_zh']}（{concept['term_en']}）",
                "",
                concept["explanation"],
                "",
                f"来源：讲义第 {pages} 页。",
                "",
            ]
        )

    lines.extend(["## 学习顺序", ""])
    for item in studykit["learning_sequence"]:
        lines.append(f"{item['step']}. {item['activity']}（约 {item['duration_minutes']} 分钟）")
        if item.get("concept_explanation"):
            lines.append(f"   - {item['concept_explanation']}")

    lines.extend(["", "## 练习", ""])
    for problem in studykit["practice"]:
        lines.extend([render_practice_prompt(studykit, problem["id"]), ""])

    lines.extend(["## 使用限制", ""])
    for limitation in studykit["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines).rstrip() + "\n"
