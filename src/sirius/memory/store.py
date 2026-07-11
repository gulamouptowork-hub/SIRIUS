from __future__ import annotations

from pathlib import Path


class VectorStore:
    """Thin wrapper around a persistent ChromaDB collection.

    Embeddings default to Chroma's built-in local model (all-MiniLM-L6-v2 via ONNX) —
    free and offline. Pass `embedding_function` to override (e.g. a stub in tests).
    """

    def __init__(
        self,
        persist_dir: Path,
        collection: str,
        embedding_function=None,
    ) -> None:
        import chromadb  # lazy: heavy import, keeps non-memory code paths light

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        kwargs = {"embedding_function": embedding_function} if embedding_function else {}
        self._collection = self._client.get_or_create_collection(collection, **kwargs)

    def count(self) -> int:
        """Number of indexed documents; raises if the store is broken."""
        return self._collection.count()

    def add(self, doc_id: str, text: str, metadata: dict) -> None:
        self._collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])

    def delete(self, doc_id: str) -> None:
        self._collection.delete(ids=[doc_id])

    def query(self, text: str, limit: int = 5, where: dict | None = None) -> list[dict]:
        result = self._collection.query(
            query_texts=[text], n_results=limit, where=where or None
        )
        hits = []
        for i, doc_id in enumerate(result["ids"][0]):
            hits.append(
                {
                    "id": doc_id,
                    "text": result["documents"][0][i],
                    "metadata": result["metadatas"][0][i],
                    "distance": result["distances"][0][i] if result.get("distances") else None,
                }
            )
        return hits
