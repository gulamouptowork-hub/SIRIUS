from __future__ import annotations

from sirius.knowledge.service import KnowledgeBase, chunk_text


def test_chunking_overlap():
    text = "a" * 3000
    chunks = chunk_text(text, chunk_size=1200, overlap=150)
    assert len(chunks) == 3
    assert sum(len(c) for c in chunks) >= 3000  # overlap duplicates content


def test_chunking_empty():
    assert chunk_text("   ") == []


def test_ingest_and_search(settings, embedding_function):
    kb = KnowledgeBase(settings, embedding_function=embedding_function)
    kb.ingest_text("u1", "notes.md", "FastAPI is a modern Python web framework.")
    hits = kb.search("u1", "Python web framework FastAPI")
    assert hits
    assert hits[0]["metadata"]["source"] == "notes.md"
