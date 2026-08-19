"""Non-sensitive execution events for tests and operational counters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.agent.contracts import CapabilityId, TaskStatus


@dataclass(frozen=True, slots=True)
class AgentEvent:
    kind: str
    capability_id: CapabilityId | None = None
    task_id: str | None = None
    status: TaskStatus | None = None
    reason: str | None = None
    task_count: int | None = None


class AgentEventSink(Protocol):
    def emit(self, event: AgentEvent) -> None: ...


class NullAgentEventSink:
    def emit(self, event: AgentEvent) -> None:
        del event
