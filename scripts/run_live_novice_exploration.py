#!/usr/bin/env python3
"""Explore CoursePilot as a novice with the real configured DeepSeek model.

The scenarios use only synthetic learner data. Full replies are written to an
explicit local report for human review; credentials and provider prompts are
never included.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent.context_token import ContextTokenSigner
from app.agent.events import AgentEvent
from app.agent.orchestrator import CoursePilotAgent
from app.agent.planning import TaskPlanner
from app.agent.router import IntentRouter
from app.catalog.courses import ReviewedCourseCatalogStore
from app.catalog.studykits import build_default_studykit_store
from app.code_tutor.service import CodeTutorService
from app.course_navigation.service import CourseNavigationService
from app.generation.model import DeepSeekModel
from app.learning.service import StudyKitLookupService
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService
from app.protocol.schemas import ChatMessage


SCENARIOS: dict[str, list[str]] = {
    "onboarding": [
        "你好",
        "/help",
        "我第一次用，也不知道该选哪个功能，你建议我先做什么？",
    ],
    "code_inline_cpp": [
        "/help code",
        "这段代码有什么问题：“include<stdio.h> int main(){int a,b; cin>>a>>b;cout<<a+b; return 0;}",
    ],
    "code_plain_python": [
        "/help code",
        "帮我看看这段程序哪里错了 def add(a,b) return a+b print(add(1,2))",
    ],
    "code_generate_cpp_example": [
        "/help code",
        "教我怎么写面向对象编程中的虚函数",
        "给我一段完整的cpp示例代码",
    ],
    "course_followup": [
        "/help course",
        "我只会一点Python，最近想学计算机系统，有没有适合我的课？",
        "这几门我应该先学哪一门？",
        "那就学你说的第一门，先带我开始。",
    ],
    "material_followup": [
        "/help material",
        "我想看看 MIT 6.7960 第二讲。",
        "这节最重要的东西是什么？",
        "第九百九十九页讲了什么？",
    ],
    "practice_without_ids": [
        "/help practice",
        "给我一道 MIT 6.7960 第二讲的题。",
        "我觉得应该先算梯度，然后用梯度更新参数。",
        "我还是不太懂，再给点提示。",
    ],
    "profile_vague": [
        "/help profile",
        "我平时挺忙，周末有空，想学系统和人工智能，会一点python。",
        "你记住了什么？",
    ],
    "course_typo": [
        "/help course",
        "我想学 cs6lc。",
        "就是伯克利那个讲计算机组成的课。",
    ],
    "multi_intent": [
        "/help",
        "我会Python，想学系统，还想请你看看这个：int main(){std::cout << 1; return 0;}",
    ],
    "underspecified": [
        "/help",
        "这题怎么做？",
        "就是刚才那题呀。",
    ],
    "code_language_contrast": [
        "/help code",
        "我会Python，但下面是C++程序，帮我看看 int main(){std::cout << 1; return 0;}",
        "换一个，这次是Python：def add(a,b) return a+b",
    ],
    "practice_answer_contrast": [
        "/help practice",
        "给我一道 MIT 6.7960 第二讲的题。",
        "我的答案是：batch等于1就用一个样本，等于N就用全部样本，小批量介于两者之间。",
        "再提示一点。",
    ],
    "course_selection_contrast": [
        "/help course",
        "推荐几门适合Python初学者的系统课程。",
        "我选第一门。",
        "我说的是你刚才列表里的第一门。",
        "那我明确选 CSAPP，应该从哪里开始？",
    ],
    "material_natural_contrast": [
        "/help material",
        "查看 MIT 6.7960 第二讲的 StudyKit。",
        "这讲最重要的内容是什么？",
        "反向传播到底是什么意思？",
    ],
    "profile_paraphrase_contrast": [
        "/help profile",
        "我只会一点python，系统和AI都挺感兴趣，时间不固定。",
        "查看我的学习画像。",
        "其实AI先不学了，先学系统。",
        "现在记住了什么？",
    ],
    "studykit_novice": [
        "/help studykit",
        "我想从操作系统第一讲开始。",
        "先给我讲讲这一讲。",
    ],
    "concept_novice": [
        "/help concept",
        "解释一下反向传播。",
        "能用生活中的例子再说一遍吗？",
    ],
    "concept_grounded": [
        "解释 MIT 6.7960 第二讲的反向传播",
    ],
    "feedback_novice": [
        "/help feedback",
        "我刚做完上一道题，帮我看看。",
        "我需要给你哪些东西？",
    ],
    "code_expected_result": [
        "/help code",
        "这个程序不对，输入1和2应该输出3，代码是 include<stdio.h> int main(){int a,b; cin>>a>>b; cout<<a+b; return 0;}",
    ],
    "profile_correction_delete": [
        "/help profile",
        "我会python，想学AI。",
        "其实不是AI，是系统。",
        "把我的编程基础忘掉。",
        "你现在还记得我什么？",
    ],
    "course_colloquial": [
        "/help course",
        "伯克利那个61c适合我吗？",
        "如果适合就直接带我从第一讲开始。",
    ],
    "course_correction_direct": [
        "不是 CS61A，我想了解 CS61C",
    ],
    "studykit_natural_direct": [
        "我想看看 MIT 6.7960 第二讲。",
    ],
}


class RecordingModel:
    def __init__(self, delegate: DeepSeekModel) -> None:
        self.delegate = delegate
        self.calls: list[dict[str, Any]] = []

    async def generate_json(self, **kwargs: Any):
        try:
            response = await self.delegate.generate_json(**kwargs)
        except Exception as exc:
            self.calls.append({"ok": False, "error_type": type(exc).__name__})
            raise
        self.calls.append(
            {
                "ok": True,
                "model": response.model,
                "request_id": response.request_id,
                "usage": response.usage,
                "structured_output": response.output,
            }
        )
        return response


class EventRecorder:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        self.events.append(event)


@dataclass
class NoviceConversation:
    agent: CoursePilotAgent
    user_id: str
    model: RecordingModel
    events: EventRecorder
    messages: list[ChatMessage] = field(default_factory=list)
    context: str | None = None

    async def send(self, text: str) -> dict[str, Any]:
        model_before = len(self.model.calls)
        event_before = len(self.events.events)
        self.messages.append(ChatMessage(role="user", content=text))
        reply = await self.agent.handle(
            messages=self.messages,
            user_id=self.user_id,
            coursepilot_context=self.context,
        )
        self.context = reply.coursepilot_context
        self.messages.append(ChatMessage(role="assistant", content=reply.answer))
        return {
            "user": text,
            "assistant": reply.answer,
            "provider_calls": len(self.model.calls) - model_before,
            "events": [
                {
                    "kind": event.kind,
                    "capability": event.capability_id.value if event.capability_id else None,
                    "status": event.status.value if event.status else None,
                }
                for event in self.events.events[event_before:]
            ],
            "context_returned": reply.coursepilot_context is not None,
        }


async def run(selected: set[str]) -> dict[str, Any]:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is required")
    unknown = selected - set(SCENARIOS)
    if unknown:
        raise ValueError(f"unknown scenarios: {', '.join(sorted(unknown))}")

    model = RecordingModel(DeepSeekModel.from_env())
    store = build_default_studykit_store()
    catalog = ReviewedCourseCatalogStore(store)
    events = EventRecorder()
    scenario_reports: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="coursepilot-novice-") as directory:
        profiles = ProfileService(
            SQLiteProfileRepository(Path(directory) / "profiles.sqlite3"), model=model
        )
        agent = CoursePilotAgent(
            store=store,
            router=IntentRouter(store, model=model),
            profiles=profiles,
            code_tutor=CodeTutorService(store, model=model),
            course_navigation=CourseNavigationService(catalog),
            studykit_learning=StudyKitLookupService(store, model=model, catalog=catalog),
            planner=TaskPlanner(model=model, robust_input_enabled=True),
            context_signer=ContextTokenSigner(
                hashlib.sha256(b"coursepilot-live-novice-exploration").digest()
            ),
            event_sink=events,
        )
        names = list(SCENARIOS) if not selected else [name for name in SCENARIOS if name in selected]
        for name in names:
            conversation = NoviceConversation(
                agent=agent,
                user_id=f"legacy:novice-{name}",
                model=model,
                events=events,
            )
            turns: list[dict[str, Any]] = []
            for text in SCENARIOS[name]:
                try:
                    turns.append(await conversation.send(text))
                except Exception as exc:
                    turns.append(
                        {
                            "user": text,
                            "assistant": None,
                            "error_type": type(exc).__name__,
                        }
                    )
            scenario_reports.append({"name": name, "turns": turns})

    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for call in model.calls:
        for key in usage:
            usage[key] += int(call.get("usage", {}).get(key, 0))
    return {
        "provider": {
            "calls": len(model.calls),
            "successful_calls": sum(bool(call.get("ok")) for call in model.calls),
            "usage": usage,
            "calls_detail": model.calls,
        },
        "scenarios": scenario_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("/tmp/coursepilot-live-novice-exploration.json"),
    )
    args = parser.parse_args()
    try:
        report = asyncio.run(run(set(args.scenario)))
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__}))
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "report": str(args.report),
                "scenario_count": len(report["scenarios"]),
                "provider": {
                    key: value
                    for key, value in report["provider"].items()
                    if key != "calls_detail"
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
