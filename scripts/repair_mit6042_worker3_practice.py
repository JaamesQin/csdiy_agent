#!/usr/bin/env python3
"""Repair worker-3 practice metadata and generic tail items offline."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("outputs/mit-6-042j-spring-2024/d446518d10d36f7ef5d7a1ba91c4dab3f383ab767b22568371fe18b44d67ac9b/courses/mit-6-042j-spring-2024/units")
UNITS = {
    "lecture-03": (
        "将同一锦标赛改为 4 名选手，明确给出 P→Q、Q→R、R→S、S→P、P→R、Q→S 的胜负；按枢轴 P 分组并写出一条相邻胜者顺序。",
        "对 3 名选手 P,Q,R 给出 P→Q、Q→R、R→P；枚举所有 6 个排列，判断是否存在 beats ordering，并说明强归纳结论的适用边界。",
    ),
    "lecture-07": (
        "对 T(1)=1、T(n)=2T(n/2)+n（n 为 2 的幂）计算 T(2),T(4),T(8)，再把加项改为 n²，比较两棵递归树的每层成本。",
        "对 T(1)=1、T(2)=3 的递推 T(n)=2T(n/2)+n，检查最小非平凡规模 n=2，并说明递归树叶层是否需要继续展开。",
    ),
    "lecture-11": (
        "对 V={A,B,C,D}、E={AB,BC,CD} 的路径图，添加边 AD 后重新计算度数、判断是否二分并给出最少颜色；所有结论都要引用具体边。",
        "对三角形 V={A,B,C}、E={AB,BC,CA}，列出所有可能的 2-着色尝试并指出冲突边，再给出 3-着色。",
    ),
    "lecture-15": (
        "在 {1,2,3,4,5,6} 上定义 xRy 当且仅当 3|(x−y)，列出 [1]、[2]、[3] 三个等价类，并检查 1R4、2R5。",
        "在偏序集合 {1,2,4,8} 上按整除关系列出所有相邻覆盖关系，找出最小和最大元素，并检查 2 与 8 的可比性。",
    ),
    "lecture-19": (
        "两所学院的录取数据为学院 A: 男 6/10、女 7/20；学院 B: 男 2/20、女 1/5。分别算分层率和合并率，判断是否出现 Simpson 方向反转。",
        "袋中有 2 红 3 蓝，不放回抽两次；计算 P(第一红)、P(第二红)、P(第二红|第一红)，并用乘法规则核对联合概率。",
    ),
    "lecture-23": (
        "6 个独立元件各以 0.15 失效。用 union bound 给出至少一次失效的上界，并用 1−0.85⁶ 计算精确值；说明上界为何不需要独立性。",
        "令 X 为 4 次伯努利试验中的成功数，p=0.25。用指标变量求 E[X]，再把第 1 次成功概率改为 0.5，重算期望。",
    ),
}


def atomic(path: Path, value: object) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


for unit, replacements in UNITS.items():
    path = ROOT / unit / "03-practice-flow.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    source_id = f"mit-6-042j-spring-2024-{unit}-material"
    for idx, item in enumerate(data.get("practice", [])):
        pages = item.get("source_pages") or []
        if not item.get("citations"):
            item["citations"] = [
                {"source_id": source_id, "anchor": {"type": "page", "value": int(page)}}
                for page in pages
            ]
        if idx >= 3:
            item["question"] = replacements[idx - 3]
            item["expected_evidence"] = [
                "题目给定的具体对象、数值、状态和约束被逐项复述并使用。",
                "中间步骤和最终结果可由读者独立核验。",
                "改变条件后的结论明确指出保持、变化或前提失效。",
            ]
            item["evaluation"] = {
                "criteria": [
                    "输入和边界条件完整，不能靠补造未给定对象作答。",
                    "计算/证明步骤与 source_id@page 支持的概念一致。",
                    "最终结果和变体比较具有可观察的判定标准。",
                ],
                "self_check": "逐项检查题设、运算、边界、结论与页级引用。",
            }
            item["content_grounding"] = {
                "setting_is_fully_specified": True,
                "transfer_task": True,
                "lecture_example_replay": False,
            }
    data["version"] = "0.2.1"
    data["repair_revision"] = "citation-and-generic-shell-repair-20260812"
    atomic(path, data)
    print(unit, len(data.get("practice", [])))
