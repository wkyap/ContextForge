"""Embedding service — generate vector embeddings via LiteLLM."""

from __future__ import annotations

import logging

import litellm

from contextforge.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings using the configured model via LiteLLM."""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.embedding_model
        self._dim = settings.embedding_dim

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        response = await litellm.aembedding(model=self._model, input=[text])
        embedding: list[float] = response.data[0]["embedding"]
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single call."""
        if not texts:
            return []
        response = await litellm.aembedding(model=self._model, input=texts)
        return [item["embedding"] for item in response.data]
