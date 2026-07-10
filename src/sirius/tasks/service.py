from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from sirius.db.database import Database
from sirius.db.models import Task, utcnow

PRIORITIES = ("high", "medium", "low")


class TaskService:
    """CRUD + queries for tasks. Reminder scheduling is injected so the service
    stays testable without a running scheduler or Telegram token."""

    def __init__(self, db: Database, schedule_fn=None, cancel_fn=None) -> None:
        self._db = db
        self._schedule = schedule_fn
        self._cancel = cancel_fn

    def create(
        self,
        user_id: str,
        title: str,
        due_at: datetime | None = None,
        priority: str = "medium",
        recurrence: str = "",
        telegram_chat_id: int | None = None,
    ) -> Task:
        if priority not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        task = Task(
            user_id=user_id,
            title=title,
            due_at=due_at,
            priority=priority,
            recurrence=recurrence,
            telegram_chat_id=telegram_chat_id,
        )
        with self._db.session() as session:
            session.add(task)
            session.flush()
        if self._schedule and telegram_chat_id and (due_at or recurrence):
            self._schedule(task.id, telegram_chat_id, title, due_at, recurrence)
        return task

    def complete(self, task_id: str) -> Task:
        return self._set_status(task_id, "done")

    def cancel(self, task_id: str) -> Task:
        return self._set_status(task_id, "cancelled")

    def _set_status(self, task_id: str, status: str) -> Task:
        with self._db.session() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise KeyError(f"Task {task_id} not found")
            task.status = status
            if status == "done":
                task.completed_at = utcnow()
        if self._cancel:
            self._cancel(task_id)
        return task

    def get(self, task_id: str) -> Task | None:
        with self._db.session() as session:
            return session.get(Task, task_id)

    def list_pending(self, user_id: str) -> list[Task]:
        return self._query(user_id, status="pending")

    def list_today(self, user_id: str) -> list[Task]:
        now = datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return [
            t
            for t in self._query(user_id, status="pending")
            if t.due_at is not None and start <= _aware(t.due_at) <= end
        ]

    def list_overdue(self, user_id: str) -> list[Task]:
        now = datetime.now(UTC)
        return [
            t
            for t in self._query(user_id, status="pending")
            if t.due_at is not None and _aware(t.due_at) < now
        ]

    def _query(self, user_id: str, status: str | None = None) -> list[Task]:
        with self._db.session() as session:
            stmt = select(Task).where(Task.user_id == user_id)
            if status:
                stmt = stmt.where(Task.status == status)
            stmt = stmt.order_by(Task.due_at.asc().nulls_last(), Task.created_at.asc())
            return list(session.scalars(stmt))


def _aware(dt: datetime) -> datetime:
    # SQLite drops tzinfo; stored values are UTC by construction.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
