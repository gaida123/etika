"""No-network checks for the Gemini embedding boundary."""

import pytest

from app.knowledge.embeddings import EmbeddingUnavailable, GeminiEmbeddingService


def test_embedding_service_rejects_wrong_dimension_before_tidy_storage() -> None:
    service = GeminiEmbeddingService(model="test-model", dimensions=3)

    assert service._validate_vector([0.0, 1.0, -1.0]) == [0.0, 1.0, -1.0]
    with pytest.raises(EmbeddingUnavailable, match="dimension"):
        service._validate_vector([0.0, 1.0])


def test_embedding_service_rejects_non_finite_vector() -> None:
    service = GeminiEmbeddingService(model="test-model", dimensions=2)

    with pytest.raises(EmbeddingUnavailable, match="non-finite"):
        service._validate_vector([0.0, float("inf")])
