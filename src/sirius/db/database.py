from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


class Database:
    """Owns the engine and session factory. One instance per process."""

    def __init__(self, database_url: str) -> None:
        self.engine = make_engine(database_url)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        # Import models so they are registered on Base before create_all.
        from sirius.db import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def ping(self) -> None:
        """Raise if the database is unreachable (used by health checks)."""
        with self.session() as session:
            session.execute(text("SELECT 1"))

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
