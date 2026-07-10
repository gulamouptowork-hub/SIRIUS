from __future__ import annotations

import pytest

from sirius.llm.base import ChatTurn, LLMProvider
from sirius.llm.router import CHAT, CODE, RESEARCH, RouterProvider, classify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # code (pt + en)
        ("me ajuda a debugar esse código Python", CODE),
        ("write a function that parses JSON", CODE),
        ("got a TypeError traceback in my script", CODE),
        ("refatora essa classe pra mim", CODE),
        # research (pt + en)
        ("explica como funciona a fotossíntese", RESEARCH),
        ("what is the difference between TCP and UDP?", RESEARCH),
        ("faz um quiz de SQL pra eu estudar", CODE),  # code keyword wins for code topics
        ("me faz um resumo desse assunto", RESEARCH),
        # chat (default)
        ("bom dia! como você está?", CHAT),
        ("remind me tomorrow at 9 to call mom", CHAT),
        ("adiciona leite na minha lista de compras", CHAT),
    ],
)
def test_classify(text, expected):
    assert classify(text) == expected


class NamedProvider(LLMProvider):
    def __init__(self, name: str) -> None:
        self.name = name

    def complete(self, system, history):
        return self.name

    def run_with_tools(self, system, history, tools, executor, max_rounds=8):
        return self.name


def make_router() -> RouterProvider:
    return RouterProvider(
        {
            CODE: NamedProvider("qwen"),
            RESEARCH: NamedProvider("deepseek"),
            CHAT: NamedProvider("mistral"),
        }
    )


def test_router_delegates_by_last_user_message():
    router = make_router()
    assert router.complete("s", [ChatTurn("user", "conserta esse bug no código")]) == "qwen"
    assert router.complete("s", [ChatTurn("user", "explica por que o céu é azul")]) == "deepseek"
    assert router.complete("s", [ChatTurn("user", "oi, tudo bem?")]) == "mistral"


def test_router_uses_latest_user_turn_not_history():
    router = make_router()
    history = [
        ChatTurn("user", "debug this python error"),
        ChatTurn("assistant", "done!"),
        ChatTurn("user", "obrigado! e bom dia pra você"),
    ]
    assert router.run_with_tools("s", history, [], lambda n, a: "") == "mistral"


def test_router_requires_all_routes():
    with pytest.raises(ValueError):
        RouterProvider({CODE: NamedProvider("qwen")})
