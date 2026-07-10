from __future__ import annotations

from sqlalchemy import func, select

from sirius.db.database import Database
from sirius.db.models import StudySession


class StudyService:
    """Tracks study sessions so Sirius can recognize recurring topics and
    tailor tutoring over time. Quiz/flashcard/plan generation is done by the
    LLM itself, guided by this history."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def log_session(self, user_id: str, topic: str, minutes: int, notes: str = "") -> StudySession:
        session_row = StudySession(
            user_id=user_id, topic=topic.strip().lower(), minutes=minutes, notes=notes
        )
        with self._db.session() as session:
            session.add(session_row)
            session.flush()
        return session_row

    def progress(self, user_id: str) -> list[dict]:
        """Per-topic totals, most-studied first."""
        with self._db.session() as session:
            stmt = (
                select(
                    StudySession.topic,
                    func.count(StudySession.id),
                    func.sum(StudySession.minutes),
                )
                .where(StudySession.user_id == user_id)
                .group_by(StudySession.topic)
                .order_by(func.sum(StudySession.minutes).desc())
            )
            return [
                {"topic": topic, "sessions": count, "total_minutes": int(total or 0)}
                for topic, count, total in session.execute(stmt)
            ]

    def recent(self, user_id: str, limit: int = 10) -> list[StudySession]:
        with self._db.session() as session:
            stmt = (
                select(StudySession)
                .where(StudySession.user_id == user_id)
                .order_by(StudySession.created_at.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt))
