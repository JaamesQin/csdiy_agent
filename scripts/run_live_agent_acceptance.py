#!/usr/bin/env python3
"""Manual provider-backed acceptance checks for the online Agent.

This script is intentionally excluded from the offline pytest suite. It uses
synthetic learner text, persists nothing, prints no model prose, and never
prints credentials or hidden authoring fields.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent.contracts import CapabilityId, CourseContext
from app.agent.planning import TaskPlanner
from app.code_tutor.service import CodeTutorService, render_tutor_result
from app.generation.model import DeepSeekModel
from app.learning.service import StudyKitLookupService
from app.profile.contracts import FactStatus, LearnerProfile
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService
from app.protocol.schemas import ChatMessage


Check = Callable[[], Awaitable[dict[str, Any]]]


class SyntheticStudyKitStore:
    """Minimal non-persistent store containing only invented acceptance data."""

    document = {
        "course_id": "synthetic-course",
        "course_version": "v1",
        "unit_id": "unit-01",
        "title": "Synthetic Unit",
        "scope": {
            "included_sources": [
                {"source_id": "synthetic-handout", "official_url": "https://example.invalid"}
            ]
        },
        "learning_objectives": [{"objective": "Distinguish invented Quorix phases."}],
        "core_concepts": [
            {
                "id": "concept-quorix-checkpoint",
                "term_en": "Quorix checkpoint",
                "term_zh": "Quorix 检查点",
                "explanation": (
                    "在这个虚构协议中，capture 阶段只记录候选状态；"
                    "commit 阶段验证标记后才公开该状态。"
                ),
                "citations": [{"source_id": "synthetic-handout", "page": 7}],
            }
        ],
        "practice": [
            {
                "id": "synthetic-practice-01",
                "level": "基础",
                "practice_type": "concept",
                "question": "为什么 capture 之后还不能公开状态？",
                "hint": "区分记录候选与验证公开两个动作。",
                "deliverable": "用两句话说明两个阶段。",
                "expected_evidence": ["capture 只记录候选", "commit 才公开"],
                "evaluation": {"full_credit": "区分两个阶段"},
                "citations": [{"source_id": "synthetic-handout", "page": 7}],
            }
        ],
        "outline": [],
        "common_misconceptions": [],
    }

    def get_ready(self, course_id: str, course_version: str, unit_id: str) -> dict[str, Any] | None:
        if (course_id, course_version, unit_id) == (
            "synthetic-course",
            "v1",
            "unit-01",
        ):
            return self.document
        return None


async def main(only: set[str] | None = None) -> int:
    model = DeepSeekModel.from_env()
    store = SyntheticStudyKitStore()
    results: list[dict[str, Any]] = []

    async def planning_check() -> dict[str, Any]:
        outcome = await TaskPlanner(model).plan(
            [
                ChatMessage(role="user", content="我在看 MIT 6.7960 第 2 讲。"),
                ChatMessage(role="assistant", content="你想继续做什么？"),
                ChatMessage(
                    role="user",
                    content=(
                        "我学过反向传播，但理解好像报错了。请先解释它和梯度下降的区别，"
                        "然后给我一道入门练习。"
                    ),
                ),
            ]
        )
        capabilities = {task.capability_id for task in outcome.plan.tasks}
        passed = {
            CapabilityId.CONCEPT_EXPLANATION,
            CapabilityId.PRACTICE_SELECTION,
        } <= capabilities and outcome.reason.startswith("model_planner")
        return {
            "name": "full_history_multi_intent_plan",
            "passed": passed,
            "task_count": len(outcome.plan.tasks),
            "capabilities": sorted(item.value for item in capabilities),
            "planner_reason": outcome.reason,
            "usage": outcome.usage,
        }

    async def profile_check() -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="coursepilot-live-profile-") as directory:
            profiles = ProfileService(
                SQLiteProfileRepository(Path(directory) / "profiles.sqlite3"),
                model=model,
                support_reviewer=model,
            )
            observation = await profiles.observe(
                user_id=None,
                text=(
                    "我不是要学系统方向，真正目标是算法。"
                    "我没有 Java 基础，只有 Python 基础。"
                ),
                current=LearnerProfile(),
            )
        confirmed = {
            (fact.field_name, str(fact.value))
            for fact in observation.profile.facts
            if fact.status is FactStatus.CONFIRMED
        }
        passed = (
            ("learning_directions", "algorithms") in confirmed
            and ("learning_directions", "systems") not in confirmed
            and ("background", "Java") not in confirmed
        )
        return {
            "name": "profile_negation_semantic_review",
            "passed": passed,
            "confirmed_fields": sorted(field for field, _ in confirmed),
            "usage": observation.usage,
        }

    context = CourseContext(
        course_id="synthetic-course",
        course_version="v1",
        unit_id="unit-01",
    )
    learning = StudyKitLookupService(
        store,
        model=model,
        claim_reviewer=model,
    )

    async def material_check() -> dict[str, Any]:
        reply = await learning.material_question(
            messages=[
                ChatMessage(
                    role="user",
                    content="虚构的 Quorix 协议中，capture 与 commit 分别负责什么？",
                )
            ],
            course_context=context,
        )
        forbidden = ("expected_evidence", "evaluation", "rubric", "评分标准")
        passed = (
            "### 依据" in reply.answer
            and "第 " in reply.answer
            and not any(item.casefold() in reply.answer.casefold() for item in forbidden)
        )
        return {
            "name": "material_generation_and_support_audit",
            "passed": passed,
            "has_citation_section": "### 依据" in reply.answer,
            "usage": reply.usage,
        }

    async def general_check() -> dict[str, Any]:
        reply = await learning.concept_explanation(
            messages=[ChatMessage(role="user", content="什么是 amortized analysis？")],
            course_context=None,
        )
        passed = (
            "通用知识（不代表当前课程材料）" in reply.answer
            and "当前已审核材料不足" in reply.answer
        )
        return {
            "name": "explicit_general_knowledge_partition",
            "passed": passed,
            "usage": reply.usage,
        }

    async def practice_check() -> dict[str, Any]:
        reply = await learning.practice_feedback(
            messages=[
                ChatMessage(
                    role="user",
                    content=(
                        "点评 synthetic-practice-01。我的答案是 capture 记录候选状态，"
                        "commit 验证标记后才公开状态。"
                    ),
                )
            ],
            course_context=context,
        )
        forbidden = (
            "expected_evidence",
            "evaluation",
            "rubric",
            "full_credit",
            "评分标准",
        )
        passed = (
            "ran_code=true" not in reply.answer
            and not any(item.casefold() in reply.answer.casefold() for item in forbidden)
            and "完整标准答案" not in reply.answer
        )
        return {
            "name": "practice_feedback_no_hidden_control_leak",
            "passed": passed,
            "usage": reply.usage,
        }

    async def code_check() -> dict[str, Any]:
        result = await CodeTutorService(store, model=model).tutor_code(
            user_id=None,
            conversation_id=None,
            course_context=None,
            code="def collect(items=[]):\n    items.append(1)\n    return items\n",
            language="python",
            error_text=None,
            question="为什么多次调用 collect 后结果会累积？只给诊断和验证步骤。",
            profile=LearnerProfile(),
        )
        rendered = render_tutor_result(result)
        passed = (
            result.ran_code is False
            and result.artifact is not None
            and bool(result.bound_hypotheses)
            and all(
                item.artifact_id == result.artifact.artifact_id
                and 1 <= item.start_line <= item.end_line <= result.artifact.line_count
                for item in result.bound_hypotheses
            )
            and "ran_code=false" in rendered
        )
        return {
            "name": "static_code_artifact_binding",
            "passed": passed,
            "diagnostic_codes": [item.code for item in result.diagnostics],
            "hypothesis_count": len(result.bound_hypotheses),
            "usage": result.usage,
        }

    checks: dict[str, Check] = {
        "planning": planning_check,
        "profile": profile_check,
        "material": material_check,
        "general": general_check,
        "practice": practice_check,
        "code": code_check,
    }
    selected = [
        check for name, check in checks.items() if only is None or name in only
    ]
    for check in selected:
        try:
            results.append(await check())
        except Exception as exc:  # noqa: BLE001 - sanitized manual acceptance boundary
            results.append(
                {
                    "name": check.__name__,
                    "passed": False,
                    "error_type": type(exc).__name__,
                }
            )

    total_usage = sum(
        int(result.get("usage", {}).get("total_tokens", 0))
        for result in results
        if isinstance(result.get("usage"), dict)
    )
    summary = {
        "provider_model": model.model,
        "passed": sum(result["passed"] is True for result in results),
        "total": len(results),
        "total_reported_tokens": total_usage,
        "checks": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        action="append",
        choices=["planning", "profile", "material", "general", "practice", "code"],
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(set(arguments.only) if arguments.only else None)))
