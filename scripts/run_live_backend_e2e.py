#!/usr/bin/env python3
"""Credentialed backend E2E checks using the real configured DeepSeek provider.

This is intentionally not a pytest module.  It uses synthetic learner messages,
an isolated profile database, real reviewed stores, and the complete Agent
orchestration path.  It prints no credentials, prompts, learner code, or model prose.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent.context_token import ContextTokenSigner
from app.agent.events import AgentEvent
from app.agent.orchestrator import CoursePilotAgent
from app.agent.planning import TaskPlanner
from app.agent.router import IntentRouter
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.knowledge import ReviewedCourseKnowledgeStore
from app.catalog.studykits import build_default_studykit_store
from app.code_tutor.service import CodeTutorService
from app.course_navigation.service import CourseNavigationService
from app.generation.model import DeepSeekModel, ModelError
from app.general_assistance.service import GeneralAssistanceService
from app.learning.service import StudyKitLookupService
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService
from app.protocol.schemas import ChatMessage


class RecordingStructuredModel:
    """Record sanitized provider metadata while delegating every call to DeepSeek."""

    def __init__(self, delegate: DeepSeekModel) -> None:
        self.delegate = delegate
        self.calls: list[dict[str, Any]] = []

    async def generate_json(self, **kwargs: Any):
        started = time.monotonic()
        try:
            response = await self.delegate.generate_json(**kwargs)
        except Exception as exc:
            self.calls.append(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                }
            )
            raise
        self.calls.append(
            {
                "ok": True,
                "model": response.model,
                "request_id": response.request_id,
                "usage": response.usage,
                "structured_output": response.output,
                "transport_attempts": response.transport_attempts,
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
        )
        return response


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        self.events.append(event)

    def completed_capabilities_since(self, index: int) -> list[str]:
        return [
            event.capability_id.value
            for event in self.events[index:]
            if event.kind == "task_result"
            and event.capability_id is not None
            and event.status is not None
            and event.status.value == "completed"
        ]


@dataclass
class ConversationRunner:
    agent: CoursePilotAgent
    user_id: str | None
    messages: list[ChatMessage] = field(default_factory=list)
    context: str | None = None

    async def turn(self, text: str) -> str:
        self.messages.append(ChatMessage(role="user", content=text))
        reply = await self.agent.handle(
            messages=self.messages,
            user_id=self.user_id,
            coursepilot_context=self.context,
        )
        self.context = reply.coursepilot_context
        self.messages.append(ChatMessage(role="assistant", content=reply.answer))
        return reply.answer


Check = Callable[[], Awaitable[dict[str, Any]]]


def _result(name: str, passed: bool, **metadata: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, **metadata}


async def _preflight(model: RecordingStructuredModel) -> dict[str, Any]:
    before = len(model.calls)
    response = await model.generate_json(
        system_prompt="Return one JSON object only. This is a provider connectivity check.",
        user_prompt='Return exactly {"status":"ok"}.',
        thinking_enabled=False,
        max_tokens=64,
        timeout_seconds=20,
    )
    return _result(
        "provider_preflight",
        response.output.get("status") == "ok",
        provider_calls=len(model.calls) - before,
        model=response.model,
        usage=response.usage,
    )


async def run(suite: str, selected: set[str], repeat: int) -> dict[str, Any]:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is required for live backend E2E")
    model = RecordingStructuredModel(DeepSeekModel.from_env())
    results: list[dict[str, Any]] = []
    results.append(await _preflight(model))

    with tempfile.TemporaryDirectory(prefix="coursepilot-live-backend-") as directory:
        store = build_default_studykit_store()
        catalog = ReviewedCourseCatalogStore(store)
        course_knowledge = ReviewedCourseKnowledgeStore(catalog)
        profiles = ProfileService(
            SQLiteProfileRepository(Path(directory) / "profiles.sqlite3"), model=model
        )
        events = RecordingEventSink()
        agent = CoursePilotAgent(
            store=store,
            router=IntentRouter(store, model=model),
            profiles=profiles,
            code_tutor=CodeTutorService(store, model=model),
            course_navigation=CourseNavigationService(
                catalog, model=model, knowledge=course_knowledge
            ),
            studykit_learning=StudyKitLookupService(store, model=model, catalog=catalog),
            general_assistance=GeneralAssistanceService(
                model=model, course_knowledge=course_knowledge
            ),
            planner=TaskPlanner(model=model, robust_input_enabled=True),
            context_signer=ContextTokenSigner(
                hashlib.sha256(b"coursepilot-live-backend-e2e").digest()
            ),
            event_sink=events,
        )

        async def inline_cpp() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-code-inline")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn(
                "这段代码有什么问题：“include<stdio.h> "
                "int main(){int a,b; cin>>a>>b;cout<<a+b; return 0;}"
            )
            required = ("C++", "ran_code=false")
            diagnostics = ("include", "iostream", "cin", "cout")
            passed = (
                all(item in answer for item in required)
                and sum(item in answer for item in diagnostics) >= 3
                and "未收到可静态分析的代码" not in answer
                and "Markdown 代码围栏" not in answer
                and events.completed_capabilities_since(event_before) == ["code_tutoring"]
            )
            return _result(
                "code_inline_cpp",
                passed,
                provider_calls=len(model.calls) - before,
                static_diagnostic_markers=sum(item in answer for item in diagnostics),
            )

        async def flattened_fence() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-code-flat")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn(
                "请静态分析 ```cpp   include<stdio.h> int main(){std::cout << 1; return 0;}   ```"
            )
            return _result(
                "code_flattened_fence",
                "ran_code=false" in answer
                and "未收到可静态分析的代码" not in answer
                and events.completed_capabilities_since(event_before) == ["code_tutoring"],
                provider_calls=len(model.calls) - before,
            )

        async def profile_course() -> dict[str, Any]:
            user_id = "legacy:live-profile-course"
            runner = ConversationRunner(agent, user_id)
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("我有python基础，给我推荐一些系统方向课程")
            backgrounds = [
                fact.value for fact in profiles.load(user_id).confirmed("background")
            ]
            return _result(
                "profile_course_multi_intent",
                len(backgrounds) == 1
                and "python" in backgrounds[0].lower()
                and any(
                    marker in answer
                    for marker in ("现在开始", "长期目标", "未个性化排序")
                )
                and "Python、python" not in answer
                and "independently_audited" not in answer
                and events.completed_capabilities_since(event_before)
                == ["profile_analysis", "course_navigation"],
                provider_calls=len(model.calls) - before,
                background_count=len(backgrounds),
                capabilities=events.completed_capabilities_since(event_before),
            )

        async def negative_background_course_path() -> dict[str, Any]:
            user_id = "legacy:live-negative-background-course"
            runner = ConversationRunner(agent, user_id)
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn(
                "我想要学习系统方向，但是我没有 Python 基础，也没有编程基础。给我推荐一些课程。"
            )
            backgrounds = [
                str(fact.value)
                for fact in profiles.load(user_id).confirmed("background")
            ]
            completed = events.completed_capabilities_since(event_before)
            navigation_output = next(
                (
                    call.get("structured_output", {})
                    for call in reversed(model.calls[before:])
                    if isinstance(call.get("structured_output"), dict)
                    and "now_catalog_ids" in call["structured_output"]
                ),
                {},
            )
            now_ids = navigation_output.get("now_catalog_ids", [])
            later_ids = navigation_output.get("later_catalog_ids", [])
            index_by_id = {
                item.catalog_id: item for item in course_knowledge.list_index()
            }
            now_has_foundation = any(
                catalog_id in index_by_id
                and index_by_id[catalog_id].major_direction == "programming_foundations"
                for catalog_id in now_ids
            )
            system_directions = {
                "systems",
                "operating_systems",
                "architecture",
                "networks",
                "distributed_systems",
                "databases",
                "compilers",
                "parallel_computing",
            }
            later_has_system_goal = any(
                catalog_id in index_by_id
                and (
                    index_by_id[catalog_id].major_direction in system_directions
                    or bool(
                        set(index_by_id[catalog_id].secondary_directions)
                        & system_directions
                    )
                )
                for catalog_id in later_ids
            )
            return _result(
                "negative_background_course_path",
                completed == ["profile_analysis", "course_navigation"]
                and len(backgrounds) >= 1
                and "## 现在开始" in answer
                and "## 长期目标" in answer
                and now_has_foundation
                and later_has_system_goal
                and "未记录精确先修要求" in answer
                and "未个性化排序" not in answer,
                provider_calls=len(model.calls) - before,
                background_count=len(backgrounds),
                capabilities=completed,
                now_catalog_ids=now_ids,
                later_catalog_ids=later_ids,
                now_has_foundation=now_has_foundation,
                later_has_system_goal=later_has_system_goal,
                has_now_heading="## 现在开始" in answer,
                has_later_heading="## 长期目标" in answer,
                has_unknown_prerequisite_notice="未记录精确先修要求" in answer,
                used_unpersonalized_fallback="未个性化排序" in answer,
                navigation_output_keys=sorted(navigation_output),
                navigation_mode=navigation_output.get("mode"),
                navigation_ran_code=navigation_output.get("ran_code"),
                navigation_overview_type=type(navigation_output.get("overview")).__name__,
            )

        async def chinese_unit_lookup() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-studykit")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("查看 MIT 6.7960 第二讲的 StudyKit")
            capabilities = events.completed_capabilities_since(event_before)
            return _result(
                "studykit_chinese_unit",
                "lecture-02" in answer
                and "当前可用 StudyKit" not in answer
                and capabilities == ["studykit_lookup"],
                provider_calls=len(model.calls) - before,
                capabilities=capabilities,
            )

        async def material_grounding() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-material")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("MIT 6.7960 第二讲的材料里，反向传播是什么？")
            return _result(
                "material_grounded_answer",
                "### 依据" in answer
                and "反向传播" in answer
                and events.completed_capabilities_since(event_before) == ["material_question"],
                provider_calls=len(model.calls) - before,
            )

        async def practice_continuity() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-practice")
            before = len(model.calls)
            event_before = len(events.events)
            first = await runner.turn("给我一道 MIT 6.7960 第二讲的练习")
            second = await runner.turn("我的答案是第二次梯度会累加，我会把 w.grad 设为 None。")
            passed = (
                "ex-1" in first
                and "practice ID" not in second.splitlines()[0]
                and "ran_code=false" not in second
                and "请在反馈请求中附上" not in second
                and runner.context is not None
                and events.completed_capabilities_since(event_before)
                == ["practice_selection", "practice_feedback"]
            )
            return _result(
                "practice_context_feedback",
                passed,
                provider_calls=len(model.calls) - before,
                context_returned=runner.context is not None,
                selected_expected_practice="ex-1" in first,
                feedback_requested_id="请在反馈请求中附上" in second,
                feedback_misrouted_to_code="ran_code=false" in second,
            )

        async def help_short_circuit() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-help")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("你目前能帮我做什么？")
            return _result(
                "help_short_circuit",
                "CoursePilot 当前功能" in answer
                and len(model.calls) == before
                and len(events.events) == event_before,
                provider_calls=len(model.calls) - before,
            )

        async def course_correction() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-course-correction")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("不是 CS61A，我想了解 CS61C")
            completed = events.completed_capabilities_since(event_before)
            return _result(
                "course_correction",
                "CS61C" in answer
                and "**CS61A" not in answer
                and "course_navigation" in completed,
                provider_calls=len(model.calls) - before,
                capabilities=completed,
            )

        async def chinese_page_boundary() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-page-boundary")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("MIT 6.7960 第二讲的材料里，第九百九十九页说了什么？")
            return _result(
                "material_chinese_page_boundary",
                "第 999 页" in answer
                and "没有足够依据" in answer
                and events.completed_capabilities_since(event_before) == ["material_question"],
                provider_calls=len(model.calls) - before,
            )

        async def concept_grounding() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-concept")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("解释 MIT 6.7960 第二讲的反向传播")
            completed = events.completed_capabilities_since(event_before)
            grounded_shape = (
                ("**定义**" in answer and completed == ["concept_explanation"])
                or ("### 依据" in answer and completed == ["material_question"])
            )
            return _result(
                "concept_grounded_answer",
                grounded_shape
                and "反向传播" in answer
                and "通用知识（不代表当前课程材料）" not in answer,
                provider_calls=len(model.calls) - before,
                capabilities=completed,
            )

        async def multi_intent() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-multi-intent")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn(
                "我会 Python，推荐系统课程，再分析这段 C++ 代码："
                "include<stdio.h> int main(){std::cout << 1; return 0;}"
            )
            completed = events.completed_capabilities_since(event_before)
            return _result(
                "profile_course_code_multi_intent",
                completed == ["profile_analysis", "course_navigation", "code_tutoring"]
                and any(
                    marker in answer
                    for marker in ("现在开始", "长期目标", "未个性化排序")
                )
                and "ran_code=false" in answer,
                provider_calls=len(model.calls) - before,
                capabilities=completed,
            )

        async def tampered_context() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-tampered-context")
            await runner.turn("给我一道 MIT 6.7960 第二讲的练习")
            assert runner.context is not None
            original = runner.context
            tampered = original[:-1] + ("A" if original[-1] != "A" else "B")
            before = len(model.calls)
            event_before = len(events.events)
            reply = await agent.handle(
                messages=[ChatMessage(role="user", content="我的答案是 capture 后立即公开状态。")],
                user_id="legacy:live-tampered-context",
                coursepilot_context=tampered,
            )
            return _result(
                "tampered_context_rejected",
                "请先指定" in reply.answer
                or "practice ID" in reply.answer
                or "当前没有" in reply.answer,
                provider_calls=len(model.calls) - before,
                capabilities=events.completed_capabilities_since(event_before),
            )

        async def novice_onboarding() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-onboarding")
            before = len(model.calls)
            answer = await runner.turn("我第一次用，也不知道该选哪个功能，你建议我先做什么？")
            return _result(
                "novice_onboarding",
                "第一次使用" in answer
                and "学习画像是可选" in answer
                and "告诉我想学的方向" in answer,
                provider_calls=len(model.calls) - before,
            )

        async def unformatted_python() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-python-inline")
            before = len(model.calls)
            answer = await runner.turn(
                "帮我看看这段程序哪里错了 def add(a,b) return a+b print(add(1,2))"
            )
            return _result(
                "code_unformatted_python",
                "ran_code=false" in answer
                and "expected ':'" in answer
                and "未收到可静态分析的代码" not in answer
                and "Markdown 代码围栏" not in answer,
                provider_calls=len(model.calls) - before,
            )

        async def code_switch() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-code-switch")
            before = len(model.calls)
            await runner.turn("帮我看 C++：int main(){std::cout << 1; return 0;}")
            answer = await runner.turn("换一个，这次是 Python：def add(a,b) return a+b")
            return _result(
                "code_current_turn_replaces_previous",
                "ran_code=false" in answer
                and "expected ':'" in answer
                and "混用" not in answer
                and "std::cout" not in answer,
                provider_calls=len(model.calls) - before,
            )

        async def course_ordinal() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-course-ordinal")
            before = len(model.calls)
            first = await runner.turn("推荐几门适合 Python 初学者的系统课程。")
            second = await runner.turn("我选第一门。")
            return _result(
                "course_recent_ordinal",
                "2. **" in first
                and "1. **" in second
                and "2. **" not in second
                and "当前可用 StudyKit" not in second,
                provider_calls=len(model.calls) - before,
            )

        async def natural_studykit() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-natural-studykit")
            before = len(model.calls)
            answer = await runner.turn("我想看看 MIT 6.7960 第二讲。")
            return _result(
                "studykit_natural_language",
                "lecture-02" in answer
                and "请说明你想了解的概念" not in answer
                and "当前可用 StudyKit" not in answer,
                provider_calls=len(model.calls) - before,
            )

        async def material_summary_followup() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-material-summary")
            before = len(model.calls)
            await runner.turn("查看 MIT 6.7960 第二讲的 StudyKit。")
            answer = await runner.turn("这讲最重要的内容是什么？")
            return _result(
                "material_unit_summary_followup",
                "本讲重点" in answer
                and "已审核 StudyKit" in answer
                and "算法、数据结构、编程语言和计算理论" not in answer,
                provider_calls=len(model.calls) - before,
            )

        async def practice_natural_hint() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-practice-natural")
            before = len(model.calls)
            selected = await runner.turn("给我一道 MIT 6.7960 第二讲的题。")
            feedback = await runner.turn("我觉得应该先算梯度，然后用梯度更新参数。")
            hint = await runner.turn("我还是不太懂，再给点提示。")
            return _result(
                "practice_natural_answer_and_hint",
                "practice" in selected
                and "请说明你想了解的概念" not in feedback
                and "请在反馈请求中附上" not in feedback
                and "空答案" not in hint
                and "请说明你想了解的概念" not in hint,
                provider_calls=len(model.calls) - before,
            )

        async def profile_correction_delete() -> dict[str, Any]:
            user_id = "legacy:live-profile-correction-delete"
            runner = ConversationRunner(agent, user_id)
            before = len(model.calls)
            await runner.turn("我会 Python，想学 AI。")
            await runner.turn("其实不是 AI，是系统。")
            answer = await runner.turn("把我的编程基础忘掉。")
            stored = profiles.load(user_id)
            directions = [
                fact.value for fact in stored.confirmed("learning_directions")
            ]
            return _result(
                "profile_natural_correction_and_delete",
                directions == ["systems"]
                and stored.confirmed("background") == []
                and "Python" not in answer,
                provider_calls=len(model.calls) - before,
                directions=directions,
            )

        async def course_typo() -> dict[str, Any]:
            user_id = "legacy:live-course-typo"
            runner = ConversationRunner(agent, user_id)
            before = len(model.calls)
            answer = await runner.turn("我想学 cs6lc。")
            stored = profiles.load(user_id)
            active = [fact.value for fact in stored.confirmed("active_course")]
            return _result(
                "course_typo_resolves_without_invalid_profile",
                "CS61C" in answer and "cs6lc" not in active,
                provider_calls=len(model.calls) - before,
                active_course=active,
            )

        async def concept_followup() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-concept-followup")
            before = len(model.calls)
            await runner.turn("解释一下反向传播。")
            answer = await runner.turn("能用生活中的例子再说一遍吗？")
            return _result(
                "concept_natural_followup",
                "请说明你想了解的概念" not in answer
                and "反向传播" in answer,
                provider_calls=len(model.calls) - before,
            )

        async def unscoped_lookup_bounded() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-bounded-lookup")
            before = len(model.calls)
            answer = await runner.turn("查看当前可用的 StudyKit。")
            return _result(
                "studykit_unscoped_output_bounded",
                answer.count("\n-") <= 3
                and "避免一次返回全部学习包" in answer,
                provider_calls=len(model.calls) - before,
                bullet_count=answer.count("\n-"),
            )

        async def operating_system_first() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-os-first")
            before = len(model.calls)
            first = await runner.turn("我想从操作系统第一讲开始。")
            second = await runner.turn("先给我讲讲这一讲。")
            return _result(
                "operating_system_first_unit_continuity",
                first.count("\n-") < 25
                and "当前可用 StudyKit" not in first
                and "请说明你想了解的概念" not in second,
                provider_calls=len(model.calls) - before,
            )

        async def feedback_missing_context() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-feedback-missing")
            before = len(model.calls)
            answer = await runner.turn("我刚做完上一道题，帮我看看。")
            return _result(
                "feedback_missing_context_is_specific",
                ("practice ID" in answer or "题面" in answer)
                and "当前答案" in answer
                and "请说明你想了解的概念" not in answer,
                provider_calls=len(model.calls) - before,
            )

        async def general_learning_fallback() -> dict[str, Any]:
            runner = ConversationRunner(agent, "legacy:live-general-assistance")
            before = len(model.calls)
            event_before = len(events.events)
            answer = await runner.turn("我最近同时学很多内容，有点乱，应该怎么调整？")
            completed = events.completed_capabilities_since(event_before)
            return _result(
                "general_learning_fallback",
                completed == ["general_assistance"]
                and "通用学习回答当前暂时不可用" not in answer
                and "ran_code=true" not in answer
                and "### 依据" not in answer,
                provider_calls=len(model.calls) - before,
                capabilities=completed,
            )

        checks: dict[str, Check] = {
            "code_inline_cpp": inline_cpp,
            "code_flattened_fence": flattened_fence,
            "profile_course_multi_intent": profile_course,
            "negative_background_course_path": negative_background_course_path,
            "studykit_chinese_unit": chinese_unit_lookup,
            "material_grounded_answer": material_grounding,
            "practice_context_feedback": practice_continuity,
            "help_short_circuit": help_short_circuit,
            "course_correction": course_correction,
            "material_chinese_page_boundary": chinese_page_boundary,
            "concept_grounded_answer": concept_grounding,
            "profile_course_code_multi_intent": multi_intent,
            "tampered_context_rejected": tampered_context,
            "novice_onboarding": novice_onboarding,
            "code_unformatted_python": unformatted_python,
            "code_current_turn_replaces_previous": code_switch,
            "course_recent_ordinal": course_ordinal,
            "studykit_natural_language": natural_studykit,
            "material_unit_summary_followup": material_summary_followup,
            "practice_natural_answer_and_hint": practice_natural_hint,
            "profile_natural_correction_and_delete": profile_correction_delete,
            "course_typo_resolves_without_invalid_profile": course_typo,
            "concept_natural_followup": concept_followup,
            "studykit_unscoped_output_bounded": unscoped_lookup_bounded,
            "operating_system_first_unit_continuity": operating_system_first,
            "feedback_missing_context_is_specific": feedback_missing_context,
            "general_learning_fallback": general_learning_fallback,
        }
        smoke = {"code_inline_cpp", "profile_course_multi_intent", "studykit_chinese_unit"}
        names = list(checks) if suite == "full" else [name for name in checks if name in smoke]
        if selected:
            unknown = selected - set(checks)
            if unknown:
                raise ValueError(f"unknown scenarios: {', '.join(sorted(unknown))}")
            names = [name for name in names if name in selected]
        for _ in range(repeat):
            for name in names:
                try:
                    results.append(await checks[name]())
                except Exception as exc:
                    results.append(_result(name, False, error_type=type(exc).__name__))

    call_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for call in model.calls:
        for key in call_usage:
            call_usage[key] += int(call.get("usage", {}).get(key, 0))
    return {
        "suite": suite,
        "passed": all(item["passed"] for item in results),
        "checks": results,
        "provider": {
            "calls": len(model.calls),
            "successful_calls": sum(bool(item.get("ok")) for item in model.calls),
            "error_types": [
                item["error_type"] for item in model.calls if not item.get("ok")
            ],
            "transport_attempts": [
                item.get("transport_attempts", 0)
                for item in model.calls
                if item.get("ok")
            ],
            "calls_detail": model.calls,
            "usage": call_usage,
            "latency_ms": [item["latency_ms"] for item in model.calls],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("smoke", "full"), default="full")
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.repeat < 1 or args.repeat > 10:
        parser.error("--repeat must be between 1 and 10")
    try:
        report = asyncio.run(run(args.suite, set(args.scenario), args.repeat))
    except (ModelError, RuntimeError, ValueError) as exc:
        print(json.dumps({"passed": False, "error_type": type(exc).__name__}))
        return 1
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized + "\n", encoding="utf-8")
    public_report = json.loads(serialized)
    public_report.get("provider", {}).pop("calls_detail", None)
    print(json.dumps(public_report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
