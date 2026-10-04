"""Gemini embeddings with strict model/dimension validation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

from google.genai import errors, types

from app.core.llm import LLMNotConfiguredError, get_client
from app.core.settings import get_settings


class EmbeddingUnavailable(RuntimeError):
    """A provider could not produce an embedding without exposing provider details."""


class EmbeddingProvider(Protocol):
    """Small injectable interface for query and backfill embedding calls."""

    @property
    def model(self) -> str: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]: ...


class GeminiEmbeddingService:
    """Embed text through the configured Gemini embedding model.

    The response is checked before it is allowed near TiDB: mixing dimensions or
    accepting NaN values would make the vector column impossible to query safely.
    """

    def __init__(self, *, model: str | None = None, dimensions: int | None = None) -> None:
        settings = get_settings()
        self._model = model or settings.gemini_embedding_model
        self._dimensions = dimensions or settings.gemini_embedding_dimensions
        if not self._model.strip():
            raise ValueError("gemini embedding model must not be empty")
        if self._dimensions <= 0:
            raise ValueError("gemini embedding dimensions must be positive")

    @property
    def model(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [item.strip() for item in texts]
        if not cleaned or any(not item for item in cleaned):
            raise ValueError("embedding input must contain non-empty text")
        try:
            response = get_client().models.embed_content(
                model=self._model,
                contents=cleaned,
                config=types.EmbedContentConfig(output_dimensionality=self._dimensions),
            )
        except LLMNotConfiguredError as exc:
            raise EmbeddingUnavailable("Gemini embeddings are not configured") from exc
        except errors.APIError as exc:
            raise EmbeddingUnavailable(f"Gemini embeddings unavailable ({exc.code})") from exc
        except Exception as exc:
            raise EmbeddingUnavailable("Gemini embeddings request failed") from exc

        embeddings = response.embeddings or []
        if len(embeddings) != len(cleaned):
            raise EmbeddingUnavailable("Gemini returned an unexpected embedding count")
        return [self._validate_vector(item.values) for item in embeddings]

    def _validate_vector(self, values: object) -> list[float]:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
            raise EmbeddingUnavailable("Gemini returned an invalid embedding")
        vector = [float(value) for value in values]
        if len(vector) != self._dimensions:
            raise EmbeddingUnavailable(
                f"Gemini embedding dimension {len(vector)} does not match configured {self._dimensions}"
            )
        if not all(math.isfinite(value) for value in vector):
            raise EmbeddingUnavailable("Gemini returned a non-finite embedding")
        return vector
