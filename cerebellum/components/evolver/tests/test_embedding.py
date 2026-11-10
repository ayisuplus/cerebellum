import math

import numpy as np
from unittest.mock import patch, MagicMock
from evolver.embedding import EmbeddingClient


def test_embed_single_returns_vector():
    with patch("evolver.embedding.TextEmbedding") as MockModel:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = iter([np.array([0.1, 0.2, 0.3])])
        MockModel.return_value = mock_instance

        client = EmbeddingClient(model_name="test-model", dim=3)
        result = client.embed_single("hello world")
        assert len(result) == 3
        assert all(isinstance(v, float) for v in result)


def test_embed_batch_returns_list_of_vectors():
    with patch("evolver.embedding.TextEmbedding") as MockModel:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = iter([
            np.array([0.1, 0.2, 0.3]),
            np.array([0.4, 0.5, 0.6]),
        ])
        MockModel.return_value = mock_instance

        client = EmbeddingClient(model_name="test-model", dim=3)
        result = client.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 3


def test_embed_empty_list():
    with patch("evolver.embedding.TextEmbedding") as MockModel:
        MockModel.return_value = MagicMock()
        client = EmbeddingClient(model_name="test-model", dim=3)
        result = client.embed([])
        assert result == []


def test_vector_to_bytes_roundtrip():
    with patch("evolver.embedding.TextEmbedding") as MockModel:
        MockModel.return_value = MagicMock()
        client = EmbeddingClient(model_name="test-model", dim=3)
        vec = [0.1, 0.2, 0.3]
        raw = client.vector_to_bytes(vec)
        assert isinstance(raw, bytes)
        recovered = client.bytes_to_vector(raw)
        assert len(recovered) == 3
        for a, b in zip(vec, recovered):
            assert abs(a - b) < 1e-5


# ── fallback (hash-based) embedding tests ──


def test_fallback_embed_no_nan():
    """Hash-based fallback must never produce NaN or Inf."""
    client = EmbeddingClient(fallback=True, dim=384)
    for text in ["hello", "world", "test", "中文测试", ""]:
        vec = client.embed_single(text)
        assert len(vec) == 384
        for v in vec:
            assert isinstance(v, float)
            assert math.isfinite(v), f"Non-finite value {v} for text={text!r}"


def test_fallback_embed_normalized():
    """Hash-based fallback should produce unit vectors."""
    client = EmbeddingClient(fallback=True, dim=384)
    vec = client.embed_single("normalization test")
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-6, f"Norm is {norm}, expected 1.0"


def test_fallback_embed_different_strings():
    """Different strings should produce different embeddings."""
    client = EmbeddingClient(fallback=True, dim=384)
    v1 = client.embed_single("hello world")
    v2 = client.embed_single("goodbye universe")
    # Should not be identical
    assert v1 != v2
    # Cosine similarity should not be 1.0 (not identical)
    dot = sum(a * b for a, b in zip(v1, v2))
    assert dot < 0.999, f"Vectors too similar: dot={dot}"


def test_fallback_embed_deterministic():
    """Same input should always produce the same vector."""
    client = EmbeddingClient(fallback=True, dim=384)
    v1 = client.embed_single("deterministic")
    v2 = client.embed_single("deterministic")
    assert v1 == v2


def test_fallback_embed_batch():
    """Batch embedding with fallback should work."""
    client = EmbeddingClient(fallback=True, dim=128)
    results = client.embed(["a", "b", "c"])
    assert len(results) == 3
    for r in results:
        assert len(r) == 128
        assert all(math.isfinite(v) for v in r)


def test_fallback_embed_empty():
    """Empty list should return empty list even in fallback mode."""
    client = EmbeddingClient(fallback=True, dim=384)
    assert client.embed([]) == []
