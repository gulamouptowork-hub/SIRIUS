from __future__ import annotations

import json

from sirius.agents.base import Agent, AgentContext
from sirius.llm.base import ToolSpec
from sirius.web.search import fetch_url, web_search


class ResearchAgent(Agent):
    """Owns web access: search the internet and read pages."""

    name = "research"

    def system_hint(self) -> str:
        return (
            "Web: for questions about current events, prices, news, or anything that may "
            "have changed recently, use web_search before answering and cite the sources. "
            "Use fetch_url to read a specific page the user mentions or a promising result."
        )

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "web_search",
                "Search the web (DuckDuckGo). Returns titles, URLs, and snippets.",
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            ToolSpec(
                "fetch_url",
                "Fetch a web page and return its readable text content.",
                {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            ),
        ]

    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str:
        if tool_name == "web_search":
            results = web_search(args["query"], max_results=args.get("max_results", 5))
            return json.dumps(results, ensure_ascii=False) if results else "No results found."
        if tool_name == "fetch_url":
            return fetch_url(args["url"])
        raise ValueError(f"Unknown tool: {tool_name}")
