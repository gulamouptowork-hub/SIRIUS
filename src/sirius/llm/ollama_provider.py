from __future__ import annotations

import json

import httpx
from loguru import logger

from sirius.config import Settings
from sirius.llm.base import ChatTurn, LLMProvider, ToolExecutor, ToolSpec, execute_safely


class OllamaProvider(LLMProvider):
    """Free, local models via Ollama's /api/chat endpoint (supports tool calling)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._client = httpx.Client(timeout=settings.llm_timeout_seconds)

    def _chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload: dict = {"model": self._model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        response = self._client.post(f"{self._base_url}/api/chat", json=payload)
        response.raise_for_status()
        return response.json()["message"]

    @staticmethod
    def _turns(system: str, history: list[ChatTurn]) -> list[dict]:
        messages = [{"role": "system", "content": system}]
        messages.extend({"role": t.role, "content": t.content} for t in history)
        return messages

    def complete(self, system: str, history: list[ChatTurn]) -> str:
        return self._chat(self._turns(system, history)).get("content", "").strip()

    def run_with_tools(
        self,
        system: str,
        history: list[ChatTurn],
        tools: list[ToolSpec],
        executor: ToolExecutor,
        max_rounds: int = 8,
    ) -> str:
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]
        messages = self._turns(system, history)

        for _ in range(max_rounds):
            message = self._chat(messages, tools=tool_defs)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return message.get("content", "").strip()

            messages.append(message)
            for call in tool_calls:
                fn = call["function"]
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args)
                logger.debug("tool call: {} {}", fn["name"], args)
                result, _ = execute_safely(executor, fn["name"], args)
                messages.append({"role": "tool", "content": result})

        return "I ran out of tool-use rounds before finishing. Please try a simpler request."
