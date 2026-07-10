from __future__ import annotations

from loguru import logger

from sirius.config import Settings
from sirius.llm.base import ChatTurn, LLMProvider, ToolExecutor, ToolSpec, execute_safely


class AnthropicProvider(LLMProvider):
    """Claude via the official Anthropic SDK. Adaptive thinking, streaming, manual tool loop."""

    def __init__(self, settings: Settings) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
        self._model = settings.anthropic_model
        self._max_tokens = settings.llm_max_tokens

    def _stream_message(self, **kwargs):
        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            thinking={"type": "adaptive"},
            **kwargs,
        ) as stream:
            return stream.get_final_message()

    @staticmethod
    def _turns(history: list[ChatTurn]) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in history]

    @staticmethod
    def _text_of(message) -> str:
        return "".join(b.text for b in message.content if b.type == "text").strip()

    def complete(self, system: str, history: list[ChatTurn]) -> str:
        message = self._stream_message(system=system, messages=self._turns(history))
        if message.stop_reason == "refusal":
            return "I can't help with that request."
        return self._text_of(message)

    def run_with_tools(
        self,
        system: str,
        history: list[ChatTurn],
        tools: list[ToolSpec],
        executor: ToolExecutor,
        max_rounds: int = 8,
    ) -> str:
        tool_defs = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        messages = self._turns(history)

        for _ in range(max_rounds):
            message = self._stream_message(system=system, messages=messages, tools=tool_defs)

            if message.stop_reason == "refusal":
                return "I can't help with that request."
            if message.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": message.content})
                continue
            if message.stop_reason != "tool_use":
                return self._text_of(message)

            messages.append({"role": "assistant", "content": message.content})
            results = []
            for block in message.content:
                if block.type != "tool_use":
                    continue
                logger.debug("tool call: {} {}", block.name, block.input)
                result, is_error = execute_safely(executor, block.name, dict(block.input))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error,
                    }
                )
            messages.append({"role": "user", "content": results})

        return "I ran out of tool-use rounds before finishing. Please try a simpler request."
