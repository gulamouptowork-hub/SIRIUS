from __future__ import annotations

from datetime import datetime

import httpx
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger

from sirius.config import get_settings

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Process-wide scheduler with a persistent SQL job store (jobs survive restarts)."""
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=settings.database_url)},
            timezone=settings.timezone,
        )
    return _scheduler


def start_scheduler() -> BackgroundScheduler:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started (timezone={})", get_settings().timezone)
    return scheduler


def send_telegram_reminder(chat_id: int, text: str) -> None:
    """Module-level so the persistent job store can serialize a reference to it."""
    token = get_settings().telegram_bot_token
    if not token:
        logger.warning("Reminder due but TELEGRAM_BOT_TOKEN is not set: {}", text)
        return
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": f"⏰ Reminder: {text}"},
        timeout=30,
    )


def parse_recurrence(recurrence: str) -> CronTrigger:
    """Parse a simple recurrence string into a CronTrigger.

    Supported forms:
      "daily 09:00"
      "weekly:mon 09:00"   (mon|tue|wed|thu|fri|sat|sun)
      "monthly:15 09:00"   (day of month)
      or a raw 5-field cron expression, e.g. "0 9 * * 1"
    """
    parts = recurrence.strip().lower().split()
    if len(parts) == 5:
        return CronTrigger.from_crontab(recurrence)
    if len(parts) != 2:
        raise ValueError(f"Unsupported recurrence: {recurrence!r}")
    freq, time_part = parts
    hour, minute = (int(x) for x in time_part.split(":"))
    if freq == "daily":
        return CronTrigger(hour=hour, minute=minute)
    if freq.startswith("weekly:"):
        return CronTrigger(day_of_week=freq.split(":", 1)[1], hour=hour, minute=minute)
    if freq.startswith("monthly:"):
        return CronTrigger(day=int(freq.split(":", 1)[1]), hour=hour, minute=minute)
    raise ValueError(f"Unsupported recurrence: {recurrence!r}")


def schedule_reminder(
    task_id: str, chat_id: int, text: str, due_at: datetime | None, recurrence: str = ""
) -> None:
    scheduler = get_scheduler()
    job_id = f"task:{task_id}"
    if recurrence:
        trigger = parse_recurrence(recurrence)
    elif due_at is not None:
        trigger = DateTrigger(run_date=due_at)
    else:
        return
    scheduler.add_job(
        send_telegram_reminder,
        trigger=trigger,
        args=[chat_id, text],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Scheduled reminder {} ({})", job_id, recurrence or due_at)


def cancel_reminder(task_id: str) -> None:
    scheduler = get_scheduler()
    job = scheduler.get_job(f"task:{task_id}")
    if job:
        job.remove()
