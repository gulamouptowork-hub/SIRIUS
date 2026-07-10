from __future__ import annotations

from loguru import logger
from sqlalchemy import select

from sirius.agents.base import Agent, AgentContext
from sirius.config import Settings
from sirius.db.database import Database
from sirius.db.models import ChatMessage
from sirius.llm.base import ChatTurn, LLMProvider, ToolSpec
from sirius.memory.manager import MemoryManager
from sirius.prompts.system import build_system_prompt


class Orchestrator:
    """Routes every conversation through the LLM with the combined tool set of
    all registered agents. Handles memory recall, working memory (history),
    and persistence of the conversation."""

    def __init__(
        self,
        settings: Settings,
        db: Database,
        llm: LLMProvider,
        memory: MemoryManager,
    ) -> None:
        self._settings = settings
        self._db = db
        self._llm = llm
        self._memory = memory
        self._agents: dict[str, Agent] = {}
        self._tool_owner: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent
        for tool in agent.tools():
            if tool.name in self._tool_owner:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tool_owner[tool.name] = agent

    @property
    def tools(self) -> list[ToolSpec]:
        return [tool for agent in self._agents.values() for tool in agent.tools()]

    def handle(self, user_id: str, text: str, telegram_chat_id: int | None = None) -> str:
        ctx = AgentContext(user_id=user_id, telegram_chat_id=telegram_chat_id)
        memory_context = self._safe_recall(user_id, text)
        system = build_system_prompt(
            [agent.system_hint() for agent in self._agents.values()],
            memory_context,
            self._settings.timezone,
        )
        history = self._load_history(user_id)
        history.append(ChatTurn("user", text))

        def executor(tool_name: str, args: dict) -> str:
            agent = self._tool_owner.get(tool_name)
            if agent is None:
                raise ValueError(f"Unknown tool: {tool_name}")
            return agent.execute(tool_name, args, ctx)

        reply = self._llm.run_with_tools(
            system,
            history,
            self.tools,
            executor,
            max_rounds=self._settings.llm_max_tool_rounds,
        )
        self._save_turns(user_id, text, reply)
        return reply

    def _safe_recall(self, user_id: str, text: str) -> str:
        try:
            return self._memory.recall_context(user_id, text)
        except Exception as exc:  # recall must never block a conversation
            logger.warning("Memory recall failed: {}", exc)
            return ""

    def _load_history(self, user_id: str) -> list[ChatTurn]:
        limit = self._settings.history_turns
        with self._db.session() as session:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.user_id == user_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            rows = list(session.scalars(stmt))
        rows.reverse()
        return [ChatTurn(row.role, row.content) for row in rows]

    def _save_turns(self, user_id: str, user_text: str, assistant_text: str) -> None:
        with self._db.session() as session:
            session.add(ChatMessage(user_id=user_id, role="user", content=user_text))
            session.add(ChatMessage(user_id=user_id, role="assistant", content=assistant_text))
