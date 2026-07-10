from __future__ import annotations

import json

from sirius.agents.base import Agent, AgentContext
from sirius.llm.base import ToolSpec
from sirius.memory.manager import MemoryManager


class MemoryAgent(Agent):
    """Owns long-term memory: remember, forget, update, search, export."""

    name = "memory"

    def __init__(self, memory: MemoryManager) -> None:
        self._memory = memory

    def system_hint(self) -> str:
        return (
            "Memory: when the user shares a lasting fact (preference, goal, skill, plan) "
            "or says 'remember this', store it with remember_memory (kind='permanent'). "
            "Use kind='temporary' for short-lived items (shopping lists, one-off reminders). "
            "When they correct you, update the relevant memory. Never invent memories."
        )

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "remember_memory",
                "Store a fact about the user. Use kind='permanent' for lasting facts "
                "(preferences, goals, profile) and kind='temporary' for short-lived items.",
                {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The fact to remember."},
                        "kind": {"type": "string", "enum": ["permanent", "temporary"]},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "sensitive": {
                            "type": "boolean",
                            "description": "True for private data; stored encrypted.",
                        },
                    },
                    "required": ["content"],
                },
            ),
            ToolSpec(
                "search_memories",
                "Semantic search over stored memories. Use before answering questions "
                "about the user's life, preferences, or past statements.",
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            ToolSpec(
                "update_memory",
                "Replace the content of an existing memory (find its id via search_memories).",
                {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"},
                        "new_content": {"type": "string"},
                    },
                    "required": ["memory_id", "new_content"],
                },
            ),
            ToolSpec(
                "forget_memory",
                "Delete a memory permanently (find its id via search_memories first).",
                {
                    "type": "object",
                    "properties": {"memory_id": {"type": "string"}},
                    "required": ["memory_id"],
                },
            ),
            ToolSpec(
                "list_memories",
                "List everything Sirius remembers about the user.",
                {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["permanent", "temporary"]}
                    },
                },
            ),
        ]

    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str:
        if tool_name == "remember_memory":
            record = self._memory.remember(
                ctx.user_id,
                args["content"],
                kind=args.get("kind", "permanent"),
                tags=args.get("tags"),
                sensitive=bool(args.get("sensitive", False)),
            )
            return f"Remembered (id={record.id}, kind={record.kind})."
        if tool_name == "search_memories":
            hits = self._memory.search(ctx.user_id, args["query"], limit=args.get("limit", 5))
            return json.dumps(hits, default=str) if hits else "No matching memories."
        if tool_name == "update_memory":
            self._memory.update(args["memory_id"], args["new_content"])
            return "Memory updated."
        if tool_name == "forget_memory":
            return "Forgotten." if self._memory.forget(args["memory_id"]) else "Memory not found."
        if tool_name == "list_memories":
            items = self._memory.list_all(ctx.user_id, kind=args.get("kind"))
            return json.dumps(items, default=str) if items else "No memories stored yet."
        raise ValueError(f"Unknown tool: {tool_name}")
