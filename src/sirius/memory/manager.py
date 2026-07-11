from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select

from sirius.config import Settings
from sirius.db.database import Database
from sirius.db.models import MemoryRecord, MemoryVersion
from sirius.logging_setup import audit
from sirius.memory.store import VectorStore
from sirius.utils.crypto import ContentCipher

PERMANENT = "permanent"
TEMPORARY = "temporary"


class MemoryManager:
    """Long-term memory: SQL is the source of truth, Chroma powers semantic recall.

    Design decisions:
    - Sensitive memories are Fernet-encrypted at rest and NOT added to the vector
      index (indexing them would store plaintext embeddings/documents). They are
      retrievable by listing/tags only.
    - Every update writes a MemoryVersion row (versioning + rollback).
    - All mutations go to the audit log.
    """

    def __init__(
        self,
        settings: Settings,
        db: Database,
        embedding_function=None,
    ) -> None:
        self._db = db
        self._cipher = ContentCipher(settings.encryption_key)
        self._backup_dir = settings.backup_dir
        self._vectors = VectorStore(
            settings.chroma_dir, "memories", embedding_function=embedding_function
        )

    def heartbeat(self) -> int:
        """Vector-store health probe: returns indexed memory count or raises."""
        return self._vectors.count()

    # ── write ────────────────────────────────────────────────

    def remember(
        self,
        user_id: str,
        content: str,
        kind: str = PERMANENT,
        tags: list[str] | None = None,
        sensitive: bool = False,
    ) -> MemoryRecord:
        if kind not in (PERMANENT, TEMPORARY):
            raise ValueError(f"kind must be '{PERMANENT}' or '{TEMPORARY}'")
        record = MemoryRecord(
            user_id=user_id,
            kind=kind,
            content=self._cipher.encrypt(content) if sensitive else content,
            tags=",".join(tags or []),
            sensitive=sensitive,
        )
        with self._db.session() as session:
            session.add(record)
            session.flush()
            if not sensitive:
                self._vectors.add(
                    record.id, content, {"user_id": user_id, "kind": kind, "tags": record.tags}
                )
        audit("memory.remember", memory_id=record.id, user_id=user_id, kind=kind)
        return record

    def update(self, memory_id: str, new_content: str) -> MemoryRecord:
        with self._db.session() as session:
            record = session.get(MemoryRecord, memory_id)
            if record is None:
                raise KeyError(f"Memory {memory_id} not found")
            session.add(
                MemoryVersion(memory_id=record.id, version=record.version, content=record.content)
            )
            record.version += 1
            record.content = (
                self._cipher.encrypt(new_content) if record.sensitive else new_content
            )
            if not record.sensitive:
                self._vectors.add(
                    record.id,
                    new_content,
                    {"user_id": record.user_id, "kind": record.kind, "tags": record.tags},
                )
        audit("memory.update", memory_id=memory_id, version=record.version)
        return record

    def forget(self, memory_id: str) -> bool:
        with self._db.session() as session:
            record = session.get(MemoryRecord, memory_id)
            if record is None:
                return False
            session.delete(record)
        self._vectors.delete(memory_id)
        audit("memory.forget", memory_id=memory_id)
        return True

    # ── read ─────────────────────────────────────────────────

    def get(self, memory_id: str) -> dict | None:
        with self._db.session() as session:
            record = session.get(MemoryRecord, memory_id)
            return self._to_dict(record) if record else None

    def list_all(self, user_id: str, kind: str | None = None) -> list[dict]:
        with self._db.session() as session:
            stmt = select(MemoryRecord).where(MemoryRecord.user_id == user_id)
            if kind:
                stmt = stmt.where(MemoryRecord.kind == kind)
            stmt = stmt.order_by(MemoryRecord.created_at.desc())
            return [self._to_dict(r) for r in session.scalars(stmt)]

    def search(self, user_id: str, query: str, limit: int = 5) -> list[dict]:
        """Semantic search over non-sensitive memories."""
        hits = self._vectors.query(query, limit=limit, where={"user_id": user_id})
        results = []
        for hit in hits:
            record = self.get(hit["id"])
            if record:
                record["distance"] = hit["distance"]
                results.append(record)
        return results

    def recall_context(self, user_id: str, query: str, limit: int = 5) -> str:
        """Relevant memories formatted for injection into the system prompt."""
        memories = self.search(user_id, query, limit=limit)
        if not memories:
            return ""
        lines = [f"- [{m['kind']}] {m['content']}" for m in memories]
        return "\n".join(lines)

    # ── export / backup / restore ────────────────────────────

    def export_all(self, user_id: str) -> list[dict]:
        audit("memory.export", user_id=user_id)
        return self.list_all(user_id)

    def backup(self, user_id: str) -> str:
        data = self.export_all(user_id)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = self._backup_dir / f"memories_{user_id}_{stamp}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        audit("memory.backup", user_id=user_id, path=str(path))
        return str(path)

    def restore(self, user_id: str, memories: list[dict]) -> int:
        count = 0
        for item in memories:
            self.remember(
                user_id,
                item["content"],
                kind=item.get("kind", PERMANENT),
                tags=[t for t in item.get("tags", "").split(",") if t],
                sensitive=bool(item.get("sensitive", False)),
            )
            count += 1
        audit("memory.restore", user_id=user_id, count=count)
        return count

    # ── helpers ──────────────────────────────────────────────

    def _to_dict(self, record: MemoryRecord) -> dict:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "kind": record.kind,
            "content": self._cipher.decrypt(record.content),
            "tags": record.tags,
            "sensitive": record.sensitive,
            "version": record.version,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
