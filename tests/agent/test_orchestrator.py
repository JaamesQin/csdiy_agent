from __future__ import annotations

import pytest

from app.agent.orchestrator import CoursePilotAgent
from app.agent.router import IntentRouter
from app.catalog.studykits import ReviewedFileStudyKitStore
from app.code_tutor.service import CodeTutorService
from app.profile.repository import SQLiteProfileRepository
from app.profile.service import ProfileService
from app.protocol.schemas import ChatMessage


def _agent(tmp_path) -> CoursePilotAgent:
    store = ReviewedFileStudyKitStore()
    profiles = ProfileService(SQLiteProfileRepository(tmp_path / "profiles.sqlite3"))
    return CoursePilotAgent(
        store=store,
        router=IntentRouter(store),
        profiles=profiles,
        code_tutor=CodeTutorService(store),
    )


async def test_profile_persists_across_new_message_history(tmp_path) -> None:
    agent = _agent(tmp_path)
    await agent.handle(
        messages=[ChatMessage(role="user", content="我想学系统方向，每周 6 小时。")],
        user_id="stable-user",
    )

    reply = await agent.handle(
        messages=[ChatMessage(role="user", content="查看我的画像")],
        user_id="stable-user",
    )

    assert "systems" in reply.answer
    assert "6 小时" in reply.answer


async def test_code_turn_can_update_profile_sidecar(tmp_path) -> None:
    agent = _agent(tmp_path)
    reply = await agent.handle(
        messages=[
            ChatMessage(
                role="user",
                content="我有 Python 基础，请帮我调试：\n```python\ndef f(x)\n return x\n```",
            )
        ],
        user_id="stable-user",
    )

    assert "ran_code=false" in reply.answer
    assert "画像更新" in reply.answer
    profile = agent.profiles.load("stable-user")
    assert profile.confirmed("background")[0].value == "Python"


async def test_chat_cannot_run_admin_generator(tmp_path) -> None:
    agent = _agent(tmp_path)

    reply = await agent.handle(
        messages=[ChatMessage(role="user", content="运行生成器后台生成")],
        user_id=None,
    )

    assert "不能触发" in reply.answer


async def test_help_lists_only_available_capabilities_and_skips_observation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = _agent(tmp_path)

    async def fail_observation(**_: object) -> object:
        raise AssertionError("help must not observe or persist profile facts")

    monkeypatch.setattr(agent.profiles, "observe", fail_observation)

    reply = await agent.handle(
        messages=[ChatMessage(role="user", content="你目前有哪些功能")],
        user_id="stable-user",
    )

    assert "1. **学习画像**" in reply.answer
    assert "2. **多语言静态代码辅导**" in reply.answer
    assert "3. **" not in reply.answer
    assert "/help code" in reply.answer


async def test_specific_code_help_lists_languages(tmp_path) -> None:
    agent = _agent(tmp_path)

    reply = await agent.handle(
        messages=[ChatMessage(role="user", content="代码辅导支持什么语言")],
        user_id=None,
    )

    assert "## 多语言静态代码辅导" in reply.answer
    assert "C++" in reply.answer
    assert "CUDA" in reply.answer
    assert "ISPC" in reply.answer
    assert "LaTeX" in reply.answer
    assert "ran_code 始终为 false" in reply.answer


async def test_unavailable_capability_help_reports_status(tmp_path) -> None:
    agent = _agent(tmp_path)

    reply = await agent.handle(
        messages=[ChatMessage(role="user", content="课程导航是什么")],
        user_id=None,
    )

    assert "## 课程导航" in reply.answer
    assert "尚未接入在线能力" in reply.answer


async def test_database_failure_degrades_to_transient_profile(tmp_path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("block", encoding="utf-8")
    store = ReviewedFileStudyKitStore()
    profiles = ProfileService(SQLiteProfileRepository(blocker / "profiles.sqlite3"))
    agent = CoursePilotAgent(
        store=store,
        router=IntentRouter(store),
        profiles=profiles,
        code_tutor=CodeTutorService(store),
    )

    reply = await agent.handle(
        messages=[ChatMessage(role="user", content="我想学算法，每周 2 小时。")],
        user_id="stable-user",
    )

    assert "2 小时" in reply.answer
    assert "没有持久保存" in reply.answer
