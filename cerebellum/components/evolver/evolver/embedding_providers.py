"""Embedding provider abstraction layer.

Supports multiple embedding backends:
- FastEmbedProvider: local fastembed models (default)
- VoyageProvider: Voyage AI API (voyage-3, 1024 dim)
- OpenAIProvider: OpenAI API (text-embedding-3-small, 1536 dim)
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Embedding model provider interface."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension."""
        ...

    @abstractmethod
    def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a batch of text strings."""
        ...


class VoyageProvider(EmbeddingProvider):
    """Voyage AI embedding provider (voyage-3, 1024 dim by default)."""

    def __init__(self, api_key: str, model: str = "voyage-3"):
        self._model = model
        self._dim = 1024  # voyage-3 default
        try:
            import voyageai
        except ImportError:
            raise ImportError(
                "voyageai is required for Voyage embeddings. "
                "Install with: pip install voyageai"
            )
        self._client = voyageai.Client(api_key=api_key)

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_single(self, text: str) -> np.ndarray:
        result = self._client.embed([text], model=self._model)
        return np.array(result.embeddings[0], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        result = self._client.embed(texts, model=self._model)
        return [np.array(e, dtype=np.float32) for e in result.embeddings]


class OpenAIProvider(EmbeddingProvider):
    """OpenAI embedding provider (text-embedding-3-small, 1536 dim)."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self._model = model
        self._dim = 1536  # text-embedding-3-small default
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai is required for OpenAI embeddings. "
                "Install with: pip install openai"
            )
        self._client = openai.OpenAI(api_key=api_key)

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_single(self, text: str) -> np.ndarray:
        result = self._client.embeddings.create(input=[text], model=self._model)
        return np.array(result.data[0].embedding, dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        result = self._client.embeddings.create(input=texts, model=self._model)
        return [np.array(d.embedding, dtype=np.float32) for d in result.data]


class FastEmbedProvider(EmbeddingProvider):
    """Local fastembed provider (default: BAAI/bge-small-en-v1.5, 384 dim)."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", dim: int = 384):
        self._model = model
        self._dim = dim
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise ImportError(
                "fastembed is required for local embeddings. "
                "Install with: pip install fastembed"
            )
        self._embedder = TextEmbedding(model_name=model)

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_single(self, text: str) -> np.ndarray:
        results = list(self._embedder.embed([text]))
        return np.array(results[0], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        results = list(self._embedder.embed(texts))
        return [np.array(r, dtype=np.float32) for r in results]


class FlagEmbeddingProvider(EmbeddingProvider):
    """FlagEmbedding provider using BGEM3FlagModel for dense/sparse/colbert embeddings.

    Supports BGE-M3 and similar models with:
    - Dense retrieval (single vector per text)
    - Sparse retrieval (lexical weights like BM25)
    - ColBERT multi-vector retrieval
    """

    def __init__(self, model: str = "BAAI/bge-m3", dim: int = 1024, use_fp16: bool = True):
        self._model_path = model
        self._dim = dim
        self._use_fp16 = use_fp16
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError:
            raise ImportError(
                "FlagEmbedding is required for this provider. "
                "Install with: pip install FlagEmbedding"
            )
        self._embedder = BGEM3FlagModel(model, use_fp16=use_fp16)

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_single(self, text: str) -> np.ndarray:
        result = self._embedder.encode([text], return_dense=True, return_sparse=False, return_colbert_vecs=False)
        return np.array(result['dense_vecs'][0], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        result = self._embedder.encode(texts, return_dense=True, return_sparse=False, return_colbert_vecs=False)
        return [np.array(v, dtype=np.float32) for v in result['dense_vecs']]


def create_provider(provider: str = "flagembedding",
                    api_key: Optional[str] = None,
                    model: Optional[str] = None,
                    dim: Optional[int] = None) -> EmbeddingProvider:
    """Factory function to create an embedding provider.

    Args:
        provider: "flagembedding", "fastembed", "voyage", or "openai"
        api_key: API key (required for voyage/openai)
        model: Model name or path (provider-specific default if omitted)
        dim: Vector dimension (auto-detected if omitted)

    Returns:
        EmbeddingProvider instance
    """
    if provider == "flagembedding":
        return FlagEmbeddingProvider(
            model=model or "BAAI/bge-m3",
            dim=dim or 1024,
            use_fp16=True
        )
    elif provider == "voyage":
        return VoyageProvider(api_key=api_key or "", model=model or "voyage-3")
    elif provider == "openai":
        return OpenAIProvider(api_key=api_key or "", model=model or "text-embedding-3-small")
    elif provider == "fastembed":
        return FastEmbedProvider(model=model or "BAAI/bge-small-en-v1.5", dim=dim or 384)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
