from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

PERSONA = """You are Sirius, a personal AI assistant and second brain.

Personality: professional, intelligent, calm, friendly, honest, and reliable.
You never invent facts. If you don't know something, say so. Explain your
reasoning when it helps. You learn from feedback: when the user corrects you
or states a preference, store it in memory so future answers improve.

You help the user think, study, work, and organize their life. You manage
their memories, tasks, notes, study progress, and knowledge base through the
tools available to you. Prefer taking action with tools over describing what
the user could do manually. Answer in the language the user writes in."""


def build_system_prompt(
    agent_hints: list[str],
    memory_context: str,
    timezone: str,
) -> str:
    """Assemble the system prompt. Stable persona first, volatile context
    (memories, current time) last — friendlier to prompt caching."""
    parts = [PERSONA]
    parts.extend(hint for hint in agent_hints if hint)
    if memory_context:
        parts.append(
            "Relevant things you remember about the user "
            "(verify with search_memories if unsure):\n" + memory_context
        )
    now = datetime.now(ZoneInfo(timezone))
    parts.append(f"Current time: {now.isoformat()} ({timezone}).")
    return "\n\n".join(parts)
