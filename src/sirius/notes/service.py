from __future__ import annotations

from sqlalchemy import or_, select

from sirius.db.database import Database
from sirius.db.models import Note, Notebook


class NoteService:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ── notebooks ────────────────────────────────────────────

    def create_notebook(self, user_id: str, name: str) -> Notebook:
        with self._db.session() as session:
            existing = session.scalar(
                select(Notebook).where(Notebook.user_id == user_id, Notebook.name == name)
            )
            if existing:
                return existing
            notebook = Notebook(user_id=user_id, name=name)
            session.add(notebook)
            session.flush()
            return notebook

    def list_notebooks(self, user_id: str) -> list[Notebook]:
        with self._db.session() as session:
            stmt = select(Notebook).where(Notebook.user_id == user_id).order_by(Notebook.name)
            return list(session.scalars(stmt))

    # ── notes ────────────────────────────────────────────────

    def create(
        self,
        user_id: str,
        title: str,
        content: str,
        notebook: str | None = None,
        tags: list[str] | None = None,
    ) -> Note:
        notebook_id = self.create_notebook(user_id, notebook).id if notebook else None
        note = Note(
            user_id=user_id,
            title=title,
            content=content,
            notebook_id=notebook_id,
            tags=",".join(tags or []),
        )
        with self._db.session() as session:
            session.add(note)
            session.flush()
        return note

    def update(self, note_id: str, title: str | None = None, content: str | None = None) -> Note:
        with self._db.session() as session:
            note = session.get(Note, note_id)
            if note is None:
                raise KeyError(f"Note {note_id} not found")
            if title is not None:
                note.title = title
            if content is not None:
                note.content = content
            return note

    def delete(self, note_id: str) -> bool:
        with self._db.session() as session:
            note = session.get(Note, note_id)
            if note is None:
                return False
            session.delete(note)
            return True

    def get(self, note_id: str) -> Note | None:
        with self._db.session() as session:
            return session.get(Note, note_id)

    def search(self, user_id: str, query: str, limit: int = 10) -> list[Note]:
        pattern = f"%{query}%"
        with self._db.session() as session:
            stmt = (
                select(Note)
                .where(
                    Note.user_id == user_id,
                    or_(
                        Note.title.ilike(pattern),
                        Note.content.ilike(pattern),
                        Note.tags.ilike(pattern),
                    ),
                )
                .order_by(Note.updated_at.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt))

    def list_all(self, user_id: str, notebook: str | None = None) -> list[Note]:
        with self._db.session() as session:
            stmt = select(Note).where(Note.user_id == user_id)
            if notebook:
                nb = session.scalar(
                    select(Notebook).where(
                        Notebook.user_id == user_id, Notebook.name == notebook
                    )
                )
                stmt = stmt.where(Note.notebook_id == (nb.id if nb else "__none__"))
            stmt = stmt.order_by(Note.updated_at.desc())
            return list(session.scalars(stmt))
