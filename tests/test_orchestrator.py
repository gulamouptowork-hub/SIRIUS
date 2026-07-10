from __future__ import annotations

import pytest

from sirius.agents.orchestrator import Orchestrator
from sirius.agents.task_agent import TaskAgent
from sirius.llm.base import ChatTurn, LLMProvider, ToolSpec
from sirius.memory.manager import MemoryManager
from sirius.tasks.service import TaskService


class ScriptedProvider(LLMProvider):
    """Fake LLM: calls a scripted list of tools, then answers."""

    def __init__(self, tool_calls: list[tuple[str, dict]], final: str) -> None:
        self._tool_calls = tool_calls
        self._final = final
        self.seen_system = ""
        self.seen_history: list[ChatTurn] = []

    def complete(self, system, history):
        return self._final

    def run_with_tools(self, system, history, tools, executor, max_rounds=8):
        self.seen_system = system
        self.seen_history = list(history)
        for name, args in self._tool_calls:
            executor(name, args)
        return self._final


@pytest.fixture
def memory(settings, db, embedding_function):
    return MemoryManager(settings, db, embedding_function=embedding_function)


def test_tool_routing_and_history_persistence(settings, db, memory):
    tasks = TaskService(db)
    provider = ScriptedProvider([("create_task", {"title": "buy milk"})], "Done, task created!")

    orchestrator = Orchestrator(settings, db, provider, memory)
    orchestrator.register(TaskAgent(tasks))

    reply = orchestrator.handle("u1", "add buy milk to my tasks")
    assert reply == "Done, task created!"
    assert [t.title for t in tasks.list_pending("u1")] == ["buy milk"]

    # history persisted and replayed on the next turn
    orchestrator.handle("u1", "thanks")
    assert any(t.content == "add buy milk to my tasks" for t in provider.seen_history)
    assert any(t.role == "assistant" for t in provider.seen_history)


def test_memory_context_injected_into_system_prompt(settings, db, memory):
    memory.remember("u1", "I prefer Python over Java")
    provider = ScriptedProvider([], "ok")
    orchestrator = Orchestrator(settings, db, provider, memory)
    orchestrator.handle("u1", "what language should I use for scripting Python or Java?")
    assert "Python over Java" in provider.seen_system


def test_duplicate_tool_names_rejected(settings, db, memory):
    provider = ScriptedProvider([], "ok")
    orchestrator = Orchestrator(settings, db, provider, memory)

    class DummyAgent(TaskAgent):
        name = "dummy"

        def tools(self):
            return [ToolSpec("create_task", "dup", {"type": "object", "properties": {}})]

    orchestrator.register(TaskAgent(TaskService(db)))
    with pytest.raises(ValueError):
        orchestrator.register(DummyAgent(TaskService(db)))
