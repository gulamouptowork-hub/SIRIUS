from __future__ import annotations

import json
import time

import httpx
from loguru import logger

from sirius.llm.base import ChatTurn, LLMProvider, ToolExecutor, ToolSpec, execute_safely


class OpenAICompatProvider(LLMProvider):
    """Any OpenAI-compatible /chat/completions endpoint with function calling.

    Used for NVIDIA NIM (integrate.api.nvidia.com), and works unchanged for
    Groq, Together, OpenRouter, LM Studio, etc. — just point base_url at them.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        max_tokens: int,
        timeout: float = 300.0,
        extra_body: dict | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )
        self._model = model
        self._max_tokens = max_tokens
        self._extra_body = extra_body or {}

    def _chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            **self._extra_body,
        }
        if tools:
            payload["tools"] = tools
        # Free hosted tiers throttle under load — retry 429/5xx with backoff.
        for attempt in range(4):
            response = self._client.post("/chat/completions", json=payload)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                delay = 5 * 2**attempt
                logger.warning(
                    "LLM endpoint returned {}, retrying in {}s", response.status_code, delay
                )
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]
        raise RuntimeError("unreachable")

    @staticmethod
    def _turns(system: str, history: list[ChatTurn]) -> list[dict]:
        messages = [{"role": "system", "content": system}]
        messages.extend({"role": t.role, "content": t.content} for t in history)
        return messages

    def complete(self, system: str, history: list[ChatTurn]) -> str:
        return (self._chat(self._turns(system, history)).get("content") or "").strip()

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
                return (message.get("content") or "").strip()

            # Some OpenAI-compatible backends reject null content on the echo.
            messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                fn = call["function"]
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args) if args.strip() else {}
                logger.debug("tool call: {} {}", fn["name"], args)
                result, _ = execute_safely(executor, fn["name"], args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", fn["name"]),
                        "content": result,
                    }
                )

        return "I ran out of tool-use rounds before finishing. Please try a simpler request."
