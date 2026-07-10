from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet

from sirius.memory.manager import MemoryManager


@pytest.fixture
def memory(settings, db, embedding_function) -> MemoryManager:
    return MemoryManager(settings, db, embedding_function=embedding_function)


def test_remember_and_search(memory):
    memory.remember("u1", "I prefer Python over Java", tags=["preference"])
    memory.remember("u1", "My goal is to become a data analyst")

    results = memory.search("u1", "Python preference programming", limit=2)
    assert results
    assert any("Python" in r["content"] for r in results)


def test_search_is_scoped_per_user(memory):
    memory.remember("u1", "secret plan alpha")
    assert memory.search("u2", "secret plan alpha") == []


def test_update_creates_version(memory):
    record = memory.remember("u1", "I live in Taipei")
    updated = memory.update(record.id, "I live in Hualien")
    assert updated.version == 2
    fetched = memory.get(record.id)
    assert fetched["content"] == "I live in Hualien"


def test_forget(memory):
    record = memory.remember("u1", "temporary thought", kind="temporary")
    assert memory.forget(record.id) is True
    assert memory.get(record.id) is None
    assert memory.forget(record.id) is False


def test_temporary_vs_permanent_listing(memory):
    memory.remember("u1", "buy milk", kind="temporary")
    memory.remember("u1", "career goal: ML engineer", kind="permanent")
    assert len(memory.list_all("u1")) == 2
    assert len(memory.list_all("u1", kind="temporary")) == 1


def test_sensitive_memory_encrypted_and_not_indexed(settings, db, embedding_function):
    settings.encryption_key = Fernet.generate_key().decode()
    memory = MemoryManager(settings, db, embedding_function=embedding_function)

    record = memory.remember("u1", "my passport number is X123", sensitive=True)
    # encrypted at rest
    with db.session() as session:
        from sirius.db.models import MemoryRecord

        raw = session.get(MemoryRecord, record.id)
        assert "passport" not in raw.content
    # decrypted on read
    assert memory.get(record.id)["content"] == "my passport number is X123"
    # not semantically searchable
    assert all(r["id"] != record.id for r in memory.search("u1", "passport number"))


def test_export_backup_restore(memory, settings):
    memory.remember("u1", "fact one")
    memory.remember("u1", "fact two", kind="temporary")

    exported = memory.export_all("u1")
    assert len(exported) == 2

    path = memory.backup("u1")
    data = json.loads(open(path, encoding="utf-8").read())
    assert len(data) == 2

    restored = memory.restore("u2", data)
    assert restored == 2
    assert len(memory.list_all("u2")) == 2
