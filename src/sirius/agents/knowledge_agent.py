from __future__ import annotations

import json

from sirius.agents.base import Agent, AgentContext
from sirius.knowledge.service import KnowledgeBase
from sirius.llm.base import ToolSpec


class KnowledgeAgent(Agent):
    """Owns the searchable knowledge base (PDFs, articles, ingested documents)."""

    name = "knowledge"

    def __init__(self, kb: KnowledgeBase) -> None:
        self._kb = kb

    def system_hint(self) -> str:
        return (
            "Knowledge base: when the user asks about their documents or previously "
            "ingested material, search_knowledge first and cite the source names."
        )

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "search_knowledge",
                "Semantic search over the user's ingested documents (PDFs, articles, notes).",
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
        ]

    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str:
        if tool_name == "search_knowledge":
            hits = self._kb.search(ctx.user_id, args["query"], limit=args.get("limit", 5))
            if not hits:
                return "Knowledge base has no matching content."
            return json.dumps(
                [{"source": h["metadata"].get("source"), "text": h["text"]} for h in hits]
            )
        raise ValueError(f"Unknown tool: {tool_name}")
