from __future__ import annotations

import json
from datetime import datetime

from sirius.agents.base import Agent, AgentContext
from sirius.db.models import Task
from sirius.llm.base import ToolSpec
from sirius.tasks.service import TaskService


def _task_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "recurrence": task.recurrence,
    }


class TaskAgent(Agent):
    """Owns tasks, reminders, and scheduling."""

    name = "tasks"

    def __init__(self, tasks: TaskService) -> None:
        self._tasks = tasks

    def system_hint(self) -> str:
        return (
            "Tasks: convert natural-language times ('tomorrow at 9') into ISO-8601 datetimes "
            "with timezone offset using the current time given above. For repeating tasks use "
            "recurrence strings: 'daily HH:MM', 'weekly:mon HH:MM', 'monthly:15 HH:MM'."
        )

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "create_task",
                "Create a task or reminder. Provide due_at as ISO-8601 with offset "
                "(e.g. 2026-07-11T09:00:00+08:00) when the user gives a time.",
                {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "due_at": {"type": "string", "description": "ISO-8601 datetime."},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                        "recurrence": {
                            "type": "string",
                            "description": (
                                "'daily HH:MM', 'weekly:mon HH:MM', 'monthly:15 HH:MM' or ''."
                            ),
                        },
                    },
                    "required": ["title"],
                },
            ),
            ToolSpec(
                "list_tasks",
                "List the user's tasks. scope: 'today', 'overdue', or 'pending' (all open).",
                {
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string", "enum": ["today", "overdue", "pending"]}
                    },
                },
            ),
            ToolSpec(
                "complete_task",
                "Mark a task as done (find its id via list_tasks).",
                {
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"],
                },
            ),
            ToolSpec(
                "cancel_task",
                "Cancel a task (find its id via list_tasks).",
                {
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"],
                },
            ),
        ]

    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str:
        if tool_name == "create_task":
            due_at = datetime.fromisoformat(args["due_at"]) if args.get("due_at") else None
            task = self._tasks.create(
                ctx.user_id,
                args["title"],
                due_at=due_at,
                priority=args.get("priority", "medium"),
                recurrence=args.get("recurrence", ""),
                telegram_chat_id=ctx.telegram_chat_id,
            )
            scheduled = ctx.telegram_chat_id and (due_at or task.recurrence)
            return f"Task created (id={task.id})." + (
                " Reminder scheduled." if scheduled else ""
            )
        if tool_name == "list_tasks":
            scope = args.get("scope", "pending")
            tasks = {
                "today": self._tasks.list_today,
                "overdue": self._tasks.list_overdue,
                "pending": self._tasks.list_pending,
            }[scope](ctx.user_id)
            return json.dumps([_task_dict(t) for t in tasks]) if tasks else "No tasks."
        if tool_name == "complete_task":
            self._tasks.complete(args["task_id"])
            return "Task completed."
        if tool_name == "cancel_task":
            self._tasks.cancel(args["task_id"])
            return "Task cancelled."
        raise ValueError(f"Unknown tool: {tool_name}")
