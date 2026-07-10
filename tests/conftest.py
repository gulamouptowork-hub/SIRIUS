from __future__ import annotations

import pytest
from chromadb.api.types import EmbeddingFunction

from sirius.config import Settings
from sirius.db.database import Database


class FakeEmbeddingFunction(EmbeddingFunction):
    """Deterministic tiny embeddings so tests never download the ONNX model."""

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 (chroma API name)
        return [self._embed(text) for text in input]

    @staticmethod
    def _embed(text: str) -> list[float]:
        vector = [0.0] * 64
        for token in text.lower().split():
            vector[hash(token) % 64] += 1.0
        return vector

    @staticmethod
    def name() -> str:
        return "fake"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        encryption_key=None,
        _env_file=None,
    )


@pytest.fixture
def db(settings) -> Database:
    settings.ensure_dirs()
    database = Database(settings.database_url)
    database.create_all()
    return database


@pytest.fixture
def embedding_function() -> FakeEmbeddingFunction:
    return FakeEmbeddingFunction()
