"""Tests for embedding providers."""

import os

import pytest
import numpy as np

from evolver.embedding_providers import (
    EmbeddingProvider,
    FastEmbedProvider,
    VoyageProvider,
    OpenAIProvider,
    create_provider,
)


class TestEmbeddingProviderInterface:
    """Verify the ABC contract."""

    def test_abc_cannot_instantiate(self):
        """EmbeddingProvider is abstract."""
        with pytest.raises(TypeError):
            EmbeddingProvider()


class TestFastEmbedProvider:
    """Tests for local fastembed provider."""

    def test_dimension(self):
        provider = FastEmbedProvider()
        assert provider.dimension == 384

    def test_embed_single_shape(self):
        provider = FastEmbedProvider()
        vec = provider.embed_single("hello world")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (384,)
        assert vec.dtype == np.float32

    def test_embed_batch(self):
        provider = FastEmbedProvider()
        texts = ["hello world", "test sentence"]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 2
        for v in vecs:
            assert v.shape == (384,)
            assert v.dtype == np.float32


class TestVoyageProvider:
    """Tests for Voyage AI provider (requires VOYAGE_API_KEY)."""

    @pytest.fixture
    def api_key(self):
        key = os.environ.get("VOYAGE_API_KEY")
        if not key:
            pytest.skip("VOYAGE_API_KEY not set")
        return key

    def test_dimension(self, api_key):
        provider = VoyageProvider(api_key=api_key)
        assert provider.dimension == 1024

    def test_embed_single(self, api_key):
        provider = VoyageProvider(api_key=api_key)
        vec = provider.embed_single("hello world")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (1024,)
        assert vec.dtype == np.float32

    def test_embed_batch(self, api_key):
        provider = VoyageProvider(api_key=api_key)
        texts = ["hello", "world"]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 2
        for v in vecs:
            assert v.shape == (1024,)


class TestOpenAIProvider:
    """Tests for OpenAI provider (requires OPENAI_API_KEY)."""

    @pytest.fixture
    def api_key(self):
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            pytest.skip("OPENAI_API_KEY not set")
        return key

    def test_dimension(self, api_key):
        provider = OpenAIProvider(api_key=api_key)
        assert provider.dimension == 1536

    def test_embed_single(self, api_key):
        provider = OpenAIProvider(api_key=api_key)
        vec = provider.embed_single("hello world")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (1536,)


class TestCreateProvider:
    """Tests for the factory function."""

    def test_fastembed_default(self):
        provider = create_provider("fastembed")
        assert isinstance(provider, FastEmbedProvider)
        assert provider.dimension == 384

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            create_provider("nonexistent")
