from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sirius.tasks.scheduler import parse_recurrence
from sirius.tasks.service import TaskService


@pytest.fixture
def tasks(db) -> TaskService:
    return TaskService(db)


def test_create_and_complete(tasks):
    task = tasks.create("u1", "write report", priority="high")
    assert task.status == "pending"
    done = tasks.complete(task.id)
    assert done.status == "done"
    assert done.completed_at is not None


def test_invalid_priority_rejected(tasks):
    with pytest.raises(ValueError):
        tasks.create("u1", "bad", priority="urgent")


def test_today_and_overdue(tasks):
    now = datetime.now(UTC)
    tasks.create("u1", "due today", due_at=now + timedelta(minutes=5))
    tasks.create("u1", "overdue", due_at=now - timedelta(days=1))
    tasks.create("u1", "someday")

    assert [t.title for t in tasks.list_today("u1")] == ["due today"]
    assert [t.title for t in tasks.list_overdue("u1")] == ["overdue"]
    assert len(tasks.list_pending("u1")) == 3


def test_cancel(tasks):
    task = tasks.create("u1", "meh")
    assert tasks.cancel(task.id).status == "cancelled"
    assert tasks.list_pending("u1") == []


def test_schedule_hook_called(db):
    calls = []
    service = TaskService(db, schedule_fn=lambda *a: calls.append(a))
    due = datetime.now(UTC) + timedelta(hours=1)
    task = service.create("u1", "ping me", due_at=due, telegram_chat_id=42)
    assert calls == [(task.id, 42, "ping me", due, "")]


def test_recurrence_parser():
    daily = parse_recurrence("daily 09:30")
    assert "hour='9'" in str(daily) and "minute='30'" in str(daily)
    weekly = parse_recurrence("weekly:mon 08:00")
    assert "day_of_week='mon'" in str(weekly)
    monthly = parse_recurrence("monthly:15 07:45")
    assert "day='15'" in str(monthly)
    cron = parse_recurrence("0 9 * * 1")
    assert "day_of_week='mon'" in str(cron) or "day_of_week='1'" in str(cron)


def test_recurrence_parser_rejects_garbage():
    with pytest.raises(ValueError):
        parse_recurrence("whenever")
