from __future__ import annotations

import re

from loguru import logger

from sirius.llm.base import ChatTurn, LLMProvider, ToolExecutor, ToolSpec

# Routing map:
#
#   Usuário → Router ─┬─ código   → Qwen
#                     ├─ pesquisa → DeepSeek (thinking)
#                     └─ conversa → Mistral (fast path)
#
# Classification is a keyword/pattern heuristic (pt + en) on the latest user
# message: zero extra latency and zero extra API calls. Ambiguous messages fall
# through to the fast conversation model.

CODE = "code"
RESEARCH = "research"
CHAT = "chat"

_CODE_PATTERNS = re.compile(
    r"```"
    r"|\b(def|class|import|function|return|traceback|exception|stack ?trace)\b"
    r"|\b(python|javascript|typescript|java\b|sql|html|css|regex|json|yaml|bash|powershell)\b"
    r"|\b(c[óo]digo|programa[rç]|script|debug|debugar|refator\w*|compilar?|erro de|bug)\b"
    r"|\b(code|coding|program|refactor|compile|debugging|implement\w*|implementa\w*)\b"
    r"|\b(fun[çc][ãa]o|vari[áa]vel|classe|api\b|endpoint|framework|biblioteca|library)\b",
    re.IGNORECASE,
)

_RESEARCH_PATTERNS = re.compile(
    r"\b(pesquis\w*|research|analis\w*|analy[sz]\w*|compar\w*|investig\w*)\b"
    r"|\b(explica\w*|explain|por ?qu[eê]|why|como funciona|how does|o que [ée]|what is)\b"
    r"|\b(resum\w*|summar\w*|estud\w*|study|aprend\w*|learn|ensina\w*|teach)\b"
    r"|\b(diferen[çc]a|difference|vantagens|advantages|hist[óo]ria de|history of)\b"
    r"|\b(quiz|flashcard|prova|exam|exerc[íi]cio)\b",
    re.IGNORECASE,
)


def classify(text: str) -> str:
    """Pick a route for the latest user message. Code wins over research
    (questions about code should go to the code model)."""
    if _CODE_PATTERNS.search(text):
        return CODE
    if _RESEARCH_PATTERNS.search(text):
        return RESEARCH
    return CHAT


class RouterProvider(LLMProvider):
    """Routes each request to a specialized provider by task type."""

    def __init__(self, providers: dict[str, LLMProvider], default: str = CHAT) -> None:
        missing = {CODE, RESEARCH, CHAT} - providers.keys()
        if missing:
            raise ValueError(f"Router is missing providers for: {sorted(missing)}")
        self._providers = providers
        self._default = default

    def _pick(self, history: list[ChatTurn]) -> LLMProvider:
        last_user = next((t.content for t in reversed(history) if t.role == "user"), "")
        route = classify(last_user) if last_user else self._default
        logger.info("Router → {} ({} chars)", route, len(last_user))
        return self._providers[route]

    def complete(self, system: str, history: list[ChatTurn]) -> str:
        return self._pick(history).complete(system, history)

    def run_with_tools(
        self,
        system: str,
        history: list[ChatTurn],
        tools: list[ToolSpec],
        executor: ToolExecutor,
        max_rounds: int = 8,
    ) -> str:
        return self._pick(history).run_with_tools(
            system, history, tools, executor, max_rounds=max_rounds
        )
