#!/usr/bin/env python3
"""Render the tracked six-course progress projection from local checkpoints.

This command is offline and read-only with respect to raw materials and
StudyKit content.  It reads the catalog registry's selected build IDs and the
root ``course-summary.json`` files, so the human-readable table cannot retain
hand-edited unit counts after a root reconcile.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


COURSES = (
    ("MIT 6.042J", "mit-6-042j"),
    ("UCB CS168", "ucb-cs168"),
    ("UCB CS186", "ucb-cs186"),
    ("UCB CS188", "ucb-cs188"),
    ("UCB CS61A", "ucb-cs61a"),
    ("UCB CS61C", "ucb-cs61c"),
)


def _summary(repository_root: Path, target: dict[str, Any]) -> dict[str, Any]:
    coverage = target.get("coverage") or {}
    build_id = coverage.get("build_id")
    output_index = coverage.get("output_index")
    summary_path = repository_root / str(output_index or "") / "course-summary.json"
    summary: dict[str, Any] = {}
    if summary_path.is_file():
        value = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            summary = value
    requested = int(summary.get("requested_unit_count", coverage.get("unit_count", 0)) or 0)
    completed = int(summary.get("completed_unit_count", 0) or 0)
    validated = int(summary.get("validated_unit_count", coverage.get("validated_unit_count", 0)) or 0)
    audited = int(summary.get("audited_unit_count", coverage.get("audit_passed_unit_count", 0)) or 0)
    failed = int(summary.get("failed_unit_count", 0) or 0)
    pending = int(summary.get("pending_unit_count", 0) or 0)
    return {
        "build_id": build_id,
        "output_index": output_index,
        "requested": requested,
        "completed": completed,
        "validated": validated,
        "audited": audited,
        "failed": failed,
        "pending": pending,
        "status": summary.get("status") or "not_reconciled",
    }


def render(repository_root: Path, registry: dict[str, Any], *, generated_at: str | None = None) -> str:
    targets = {target.get("canonical_course_id"): target for target in registry.get("course_targets", [])}
    rows = [(label, course_id, _summary(repository_root, targets.get(course_id, {}))) for label, course_id in COURSES]
    totals = {key: sum(row[2][key] for row in rows) for key in ("requested", "completed", "validated", "audited", "failed", "pending")}
    timestamp = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "# 六门课程批次进度",
        "",
        f"更新时间：`{timestamp}`",
        "",
        "本表由 `scripts/update_csdiy_hybrid_progress.py` 从 registry 当前选定的 fingerprinted build 及其 `course-summary.json` 生成。`完成` 是 root reconciler 的完成单元数；portable validation 单独列出，不能替代独立审计或 finalization。",
        "",
        "> **Agent 数量硬门槛：** 本批次调度上限为 **16/16**：1 个 global coordinator；每个 build 最多 4 个 unit worker。agent 数量不参与课程进度计算。",
        "",
        "## 完成总览",
        "",
        "| 课程 build | 完成 / 总单元 | 完成度 | audited | portable validated | failed | pending | root status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for label, _, row in rows:
        percent = f"{100 * row['completed'] / row['requested']:.1f}%" if row["requested"] else "0.0%"
        lines.append(f"| {label} | {row['completed']} / {row['requested']} | {percent} | {row['audited']} | {row['validated']} | {row['failed']} | {row['pending']} | `{row['status']}` |")
    percent = f"{100 * totals['completed'] / totals['requested']:.1f}%" if totals["requested"] else "0.0%"
    lines.append(f"| **当前合计** | **{totals['completed']} / {totals['requested']}** | **{percent}** | **{totals['audited']}** | **{totals['validated']}** | **{totals['failed']}** | **{totals['pending']}** | — |")
    lines += [
        "",
        "## 口径与来源",
        "",
        "- 课程分母来自 pinned catalog registry；本表不会删除 failed、blocked 或 pending 单元。",
        "- 每一行的数字来自 registry `coverage.build_id` 指向的 root `course-summary.json`；缺少该文件时显示 0 并标记 `not_reconciled`，不会猜测旧 build 数字。",
        "- 新输入或版本必须生成新 fingerprinted build；旧 build 保留为历史证据，不原地覆盖。",
        "- 已存在的 practice 语义问题本轮只登记为延期问题，不在本轮返工或数字投影中处理；这不表示问题已通过，也不表示可以忽略。",
        "- 新生成或修复的单元仍须逐题满足 StudyKit practice 契约：题目必须具体、可作答、真正考查本单元材料，而不是只复述标题；每题须有真实 source_id@page 锚点，并由独立审计检查练习与内容的语义对应关系。",
        "- root、registry 与本表的更新命令：",
        "",
        "```bash",
        ".venv/bin/python scripts/audit_csdiy_registry.py --registry data/catalog/csdiy-course-registry.yaml --repository-root . --report evaluations/csdiy-catalog-registry-audit.json --update",
        ".venv/bin/python scripts/update_csdiy_hybrid_progress.py --repository-root . --registry data/catalog/csdiy-course-registry.yaml --output docs/csdiy-hybrid-batch-progress.md",
        "```",
        "",
        "全局机器可读状态以 [`data/catalog/csdiy-course-registry.yaml`](../data/catalog/csdiy-course-registry.yaml) 和 [`evaluations/csdiy-catalog-registry-audit.json`](../evaluations/csdiy-catalog-registry-audit.json) 为准；本表是六课 root 数字的人类可读投影。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--registry", type=Path, default=Path("data/catalog/csdiy-course-registry.yaml"))
    parser.add_argument("--output", type=Path, default=Path("docs/csdiy-hybrid-batch-progress.md"))
    args = parser.parse_args()
    root = args.repository_root.resolve()
    registry = yaml.safe_load(args.registry.read_text(encoding="utf-8")) or {}
    rendered = render(root, registry)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "status": "updated"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
