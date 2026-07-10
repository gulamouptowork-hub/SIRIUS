from __future__ import annotations

import pytest

from sirius.notes.service import NoteService


@pytest.fixture
def notes(db) -> NoteService:
    return NoteService(db)


def test_create_and_search(notes):
    notes.create("u1", "SQL joins", "INNER vs LEFT JOIN explained", tags=["sql", "study"])
    notes.create("u1", "Groceries", "milk, eggs")

    hits = notes.search("u1", "join")
    assert len(hits) == 1
    assert hits[0].title == "SQL joins"
    assert notes.search("u1", "sql")  # tag match


def test_notebooks_dedupe_and_listing(notes):
    notes.create("u1", "a", "x", notebook="Study")
    notes.create("u1", "b", "y", notebook="Study")
    assert [nb.name for nb in notes.list_notebooks("u1")] == ["Study"]
    assert len(notes.list_all("u1", notebook="Study")) == 2


def test_update_and_delete(notes):
    note = notes.create("u1", "draft", "v1")
    notes.update(note.id, content="v2")
    assert notes.get(note.id).content == "v2"
    assert notes.delete(note.id) is True
    assert notes.get(note.id) is None
