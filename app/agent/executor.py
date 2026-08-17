"""Dependency-aware execution for bounded online task plans."""

from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable

from app.agent.contracts import (
    CapabilityId,
    PlannedTask,
    TaskExecutionResult,
    TaskPlan,
    TaskStatus,
)

TaskHandler = Callable[[PlannedTask], Awaitable[TaskExecutionResult]]


class TaskExecutor:
    def __init__(self, handlers: dict[CapabilityId, TaskHandler]) -> None:
        self._handlers = handlers.copy()

    async def execute(self, plan: TaskPlan) -> list[TaskExecutionResult]:
        results: dict[str, TaskExecutionResult] = {}
        for task in plan.ordered_tasks():
            failed_dependencies = [
                dependency
                for dependency in task.depends_on
                if results[dependency].status is not TaskStatus.COMPLETED
            ]
            if failed_dependencies:
                results[task.task_id] = TaskExecutionResult(
                    task_id=task.task_id,
                    capability_id=task.capability_id,
                    status=TaskStatus.BLOCKED,
                    missing_context=[f"dependency:{item}" for item in failed_dependencies],
                )
                continue
            if task.required_context:
                results[task.task_id] = TaskExecutionResult(
                    task_id=task.task_id,
                    capability_id=task.capability_id,
                    status=TaskStatus.BLOCKED,
                    missing_context=task.required_context,
                )
                continue
            handler = self._handlers.get(task.capability_id)
            if handler is None:
                results[task.task_id] = TaskExecutionResult(
                    task_id=task.task_id,
                    capability_id=task.capability_id,
                    status=TaskStatus.FAILED,
                    answer="该任务能力当前不可用。",
                )
                continue
            try:
                result = await handler(task)
                if result.task_id != task.task_id or result.capability_id != task.capability_id:
                    raise ValueError("task handler returned a mismatched identity")
            except (OSError, sqlite3.Error, RuntimeError, ValueError):
                result = TaskExecutionResult(
                    task_id=task.task_id,
                    capability_id=task.capability_id,
                    status=TaskStatus.FAILED,
                    answer="该任务执行失败；其他独立任务仍会继续。",
                )
            results[task.task_id] = result
        return [results[task.task_id] for task in plan.ordered_tasks()]


def render_execution(results: list[TaskExecutionResult], plan: TaskPlan) -> str:
    completed = [result.answer for result in results if result.answer]
    missing = list(
        dict.fromkeys(
            item
            for result in results
            if result.status is TaskStatus.BLOCKED
            for item in result.missing_context
            if not item.startswith("dependency:")
        )
    )
    sections = [answer for answer in completed if answer]
    if missing:
        questions = plan.clarifying_questions[:1]
        sections.append(
            questions[0]
            if questions
            else f"要继续剩余任务，请补充：{'、'.join(missing)}。"
        )
    return "\n\n---\n\n".join(sections)
