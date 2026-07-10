from __future__ import annotations

from sirius.llm.base import ChatTurn, ToolSpec
from sirius.llm.openai_compat import OpenAICompatProvider


def make_provider() -> OpenAICompatProvider:
    return OpenAICompatProvider("http://fake", None, "test-model", 128)


def test_tool_loop_message_format(monkeypatch):
    provider = make_provider()
    seen_payloads: list[list[dict]] = []
    replies = iter(
        [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "get_time", "arguments": '{"zone": "utc"}'},
                    }
                ],
            },
            {"role": "assistant", "content": "It is 12:00."},
        ]
    )
    monkeypatch.setattr(
        provider,
        "_chat",
        lambda messages, tools=None: (seen_payloads.append(list(messages)), next(replies))[1],
    )

    calls: list[tuple[str, dict]] = []

    def executor(name: str, args: dict) -> str:
        calls.append((name, args))
        return "12:00"

    tool = ToolSpec("get_time", "Get the time", {"type": "object", "properties": {}})
    reply = provider.run_with_tools("sys", [ChatTurn("user", "time?")], [tool], executor)

    assert reply == "It is 12:00."
    assert calls == [("get_time", {"zone": "utc"})]  # JSON-string arguments parsed
    final_messages = seen_payloads[-1]
    assert final_messages[0] == {"role": "system", "content": "sys"}
    assert final_messages[-2]["role"] == "assistant"
    assert final_messages[-2]["tool_calls"]  # assistant tool_calls echoed back
    assert final_messages[-1] == {"role": "tool", "tool_call_id": "call_1", "content": "12:00"}


def test_tool_errors_returned_to_model(monkeypatch):
    provider = make_provider()
    replies = iter(
        [
            {
                "role": "assistant",
                "tool_calls": [{"id": "c1", "function": {"name": "boom", "arguments": "{}"}}],
            },
            {"role": "assistant", "content": "Recovered."},
        ]
    )
    messages_log: list[list[dict]] = []
    monkeypatch.setattr(
        provider,
        "_chat",
        lambda messages, tools=None: (messages_log.append(list(messages)), next(replies))[1],
    )

    def executor(name: str, args: dict) -> str:
        raise RuntimeError("kaboom")

    tool = ToolSpec("boom", "explodes", {"type": "object", "properties": {}})
    reply = provider.run_with_tools("sys", [ChatTurn("user", "go")], [tool], executor)

    assert reply == "Recovered."
    assert "kaboom" in messages_log[-1][-1]["content"]
