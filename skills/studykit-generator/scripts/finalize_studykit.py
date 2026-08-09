#!/usr/bin/env python3
"""Validate a StudyKit candidate and render deterministic YAML and Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _citation(value: dict[str, Any]) -> str:
    anchor = value["anchor"]
    return f"{value['source_id']}@{anchor['type']}:{anchor['value']}"


def _render(studykit: dict[str, Any]) -> str:
    lines = [f"# {studykit['title']}", ""]
    lines.append(f"> 课程：{studykit.get('course_id') or '未知'} · 版本：{studykit.get('course_version') or '未知'} · 单元：{studykit['unit_id']}")
    lines.extend(["", "## 学习目标", ""])
    lines.extend(f"- {item['objective']}" for item in studykit["learning_objectives"])
    lines.extend(["", "## 前置知识", ""])
    lines.extend(f"- {item['topic']}：{item['required_level']}" for item in studykit["prerequisites"])
    lines.extend(["", "## 核心概念", ""])
    for concept in studykit["core_concepts"]:
        refs = ", ".join(_citation(item) for item in concept["citations"])
        lines.extend([f"### {concept['term']}", "", concept["explanation"], "", f"来源：{refs}", ""])
        formula = concept.get("formula")
        if formula:
            if formula["status"] == "resolved" and formula.get("latex"):
                lines.extend([f"公式：$${formula['latex']}$$", ""])
            elif formula.get("image"):
                lines.extend([f"公式图像：{formula['image']}（识别未解决）", ""])
    lines.extend(["## 学习顺序", ""])
    lines.extend(f"{item['step']}. {item['activity']}（{item['duration_minutes']} 分钟）" for item in studykit["learning_sequence"])
    lines.extend(["", "## 练习", ""])
    for item in studykit["practice"]:
        refs = ", ".join(_citation(value) for value in item["citations"])
        lines.extend([f"### {item['id']} · {item['level']}", "", item["question"], "", f"提示：{item['hint']}", "", f"提交：{item['deliverable']}", "", f"来源：{refs}", ""])
    if studykit["limitations"]:
        lines.extend(["## 限制", ""])
        lines.extend(f"- {item}" for item in studykit["limitations"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--studykit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = args.output_dir / "validation.json"
    validation = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_artifacts.py"), "--chunks", str(args.chunks), "--studykit", str(args.studykit), "--report", str(report)],
        text=True, capture_output=True, check=False,
    )
    if validation.returncode:
        print(validation.stdout, end="", file=sys.stderr)
        return validation.returncode
    studykit = json.loads(args.studykit.read_text(encoding="utf-8"))
    canonical = args.output_dir / "05-studykit.json"
    canonical.write_text(json.dumps(studykit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        import yaml
    except ImportError:
        print("PyYAML is required to render studykit.yaml", file=sys.stderr)
        return 2
    (args.output_dir / "studykit.yaml").write_text(yaml.safe_dump(studykit, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (args.output_dir / "studykit.md").write_text(_render(studykit), encoding="utf-8")
    print(json.dumps({"status": "succeeded", "output_dir": str(args.output_dir.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
