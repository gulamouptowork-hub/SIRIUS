from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sirius.llm.base import ToolSpec


@dataclass
class AgentContext:
    """Per-request context passed to every tool execution."""

    user_id: str
    telegram_chat_id: int | None = None


class Agent(ABC):
    """A specialized capability of Sirius. Each agent contributes tools to the
    orchestrator and a short hint to the system prompt. Agents are replaceable:
    register/unregister them on the orchestrator without touching other code."""

    name: str = "agent"

    @abstractmethod
    def tools(self) -> list[ToolSpec]: ...

    @abstractmethod
    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str: ...

    def system_hint(self) -> str:
        """Optional extra guidance appended to the system prompt."""
        return ""
