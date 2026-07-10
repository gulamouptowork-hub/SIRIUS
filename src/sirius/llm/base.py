from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ToolSpec:
    """Provider-agnostic tool definition (Anthropic-style JSON schema)."""

    name: str
    description: str
    input_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass
class ChatTurn:
    role: str  # "user" | "assistant"
    content: str


ToolExecutor = Callable[[str, dict], str]
"""(tool_name, tool_input) -> result string. Raise for hard failures."""


class LLMProvider(ABC):
    """Each provider runs its own native tool loop so message formats never leak out."""

    @abstractmethod
    def complete(self, system: str, history: list[ChatTurn]) -> str:
        """Plain completion without tools."""

    @abstractmethod
    def run_with_tools(
        self,
        system: str,
        history: list[ChatTurn],
        tools: list[ToolSpec],
        executor: ToolExecutor,
        max_rounds: int = 8,
    ) -> str:
        """Agentic loop: call tools via `executor` until the model produces a final answer."""


def execute_safely(executor: ToolExecutor, name: str, args: dict) -> tuple[str, bool]:
    """Run a tool call; return (result_text, is_error). Shared by all providers."""
    try:
        return executor(name, args), False
    except Exception as exc:  # tool errors go back to the model, not up the stack
        return f"Error: {exc}", True
