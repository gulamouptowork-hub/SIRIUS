from __future__ import annotations

import uuid
from pathlib import Path

from loguru import logger

from sirius.config import Settings
from sirius.memory.store import VectorStore


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    """Simple character-based chunking with overlap; good enough for personal KB."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


class KnowledgeBase:
    """Searchable knowledge base built from notes, PDFs, articles, and conversations."""

    def __init__(self, settings: Settings, embedding_function=None) -> None:
        self._vectors = VectorStore(
            settings.chroma_dir, "knowledge", embedding_function=embedding_function
        )

    def ingest_text(self, user_id: str, source: str, text: str) -> int:
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            self._vectors.add(
                f"{uuid.uuid4().hex}",
                chunk,
                {"user_id": user_id, "source": source, "chunk": i},
            )
        logger.info("Ingested {} chunks from {}", len(chunks), source)
        return len(chunks)

    def ingest_pdf(self, user_id: str, path: Path | str, source: str | None = None) -> int:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return self.ingest_text(user_id, source or Path(path).name, text)

    def search(self, user_id: str, query: str, limit: int = 5) -> list[dict]:
        return self._vectors.query(query, limit=limit, where={"user_id": user_id})
