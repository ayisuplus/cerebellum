import logging
import os
import struct
from typing import Optional

from evolver.exceptions import EmbeddingError

TextEmbedding = None
SentenceTransformer = None


def _import_fastembed():
    """Lazy import of fastembed.TextEmbedding. Returns the class or None."""
    global TextEmbedding
    if TextEmbedding is not None:
        return TextEmbedding
    try:
        from fastembed import TextEmbedding as _TextEmbedding
        TextEmbedding = _TextEmbedding
        return _TextEmbedding
    except ImportError:
        return None


def _import_sentence_transformers():
    """Lazy import of sentence_transformers.SentenceTransformer. Returns the class or None."""
    global SentenceTransformer
    if SentenceTransformer is not None:
        return SentenceTransformer
    try:
        from sentence_transformers import SentenceTransformer as _SentenceTransformer
        SentenceTransformer = _SentenceTransformer
        return _SentenceTransformer
    except ImportError:
        return None

logger = logging.getLogger(__name__)

# Known model dimensions for validation
_MODEL_DIMS = {
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-small-en": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-m3": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "intfloat/multilingual-e5-small": 384,
    "intfloat/multilingual-e5-base": 768,
    "intfloat/multilingual-e5-large": 1024,
}


class EmbeddingClient:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", dim: int = 384,
                 fallback: bool = False,
                 provider: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.model_name = model_name
        self.dim = dim
        self._fallback = fallback
        self._model = None
        self._backend = None  # "fastembed", "sentence_transformers", or "provider"
        self._provider = None  # EmbeddingProvider instance

        # Offline mode is an explicit caller choice and must take precedence
        # over the configured provider (including the default provider).
        if fallback:
            self._provider_name = "hash-fallback"
            logger.warning("Embedding fallback mode: using hash-based vectors (no semantic search)")
            return

        # If provider is specified, use the new provider abstraction
        if provider and provider != "fastembed":
            from evolver.embedding_providers import create_provider
            self._provider = create_provider(
                provider=provider,
                api_key=api_key,
                model=model_name,
                dim=dim,
            )
            self.dim = self._provider.dimension
            self._backend = "provider"
            self._provider_name = provider
            logger.info("Using embedding provider '%s' (dim=%d)", provider, self.dim)
            return

        # Legacy path: fastembed / sentence_transformers / fallback
        self._provider_name = "fastembed"

        # Detect local path
        is_local = os.path.isdir(model_name) or os.path.exists(model_name)

        if is_local:
            # Use sentence-transformers for local models
            _SentenceTransformer = _import_sentence_transformers()
            if _SentenceTransformer is None:
                raise EmbeddingError(
                    "sentence-transformers is required for local models. "
                    "Install with: pip install sentence-transformers"
                )
            try:
                self._model = _SentenceTransformer(model_name)
                self._backend = "sentence_transformers"
                actual_dim = self._model.get_sentence_embedding_dimension()
                if actual_dim != dim:
                    raise EmbeddingError(
                        f"Dimension mismatch: model '{model_name}' produces {actual_dim}-d "
                        f"vectors, but config specifies dim={dim}. "
                        f"Use embedding_dim={actual_dim} or omit it to use the default."
                    )
                logger.info("Loaded local model '%s' via sentence-transformers (dim=%d)", model_name, dim)
            except Exception as e:
                raise EmbeddingError(
                    f"Failed to load local model '{model_name}': {e}"
                ) from e
        else:
            # Use fastembed for remote models
            _TextEmbedding = _import_fastembed()
            if _TextEmbedding is None:
                raise RuntimeError(
                    "fastembed is not installed. Install with: pip install fastembed"
                )
            # Validate dimension against known models
            expected_dim = _MODEL_DIMS.get(model_name)
            if expected_dim is not None and expected_dim != dim:
                raise EmbeddingError(
                    f"Dimension mismatch: model '{model_name}' produces {expected_dim}-d "
                    f"vectors, but config specifies dim={dim}. "
                    f"Use embedding_dim={expected_dim} or omit it to use the default."
                )
            if expected_dim is None:
                logger.warning(
                    "Unknown model '%s' — cannot validate dim=%d. "
                    "Proceeding, but mismatched dims will cause runtime errors.",
                    model_name, dim,
                )
            try:
                self._model = _TextEmbedding(model_name=model_name)
                self._backend = "fastembed"
                logger.info("Loaded embedding model '%s' (dim=%d)", model_name, dim)
            except Exception as e:
                raise EmbeddingError(
                    f"Failed to load embedding model '{model_name}': {e}. "
                    "Check network connection for first-run download."
                ) from e

    def _hash_embed(self, text: str) -> list[float]:
        """Hash-based fallback embedding for offline mode.

        Re-hashes per 16-float block: for each block index, computes
        SHA-512(text + str(block_index)) and unpacks the 64-byte digest
        as 16 consecutive 4-byte uint32 windows. Each uint32 is mapped
        to [-1, 1] and the full vector is normalized to a unit vector.
        Per-block re-hashing keeps every dimension distinct (a single
        digest only yields 16 unique values).

        NOTE: hash-fallback vectors are non-semantic and support EXACT
        duplicate detection only (identical text -> identical vector;
        similar text -> unrelated vectors). Rows written by this path are
        tagged embedder="hash-fallback:v2" (see EmbeddingClient.identity),
        so retrieval and dedup never cross-compare them with model
        embeddings; bump the version if the hashing scheme changes again.
        """
        import hashlib
        block_floats = 16  # 64-byte SHA-512 digest / 4-byte uint32
        vec = []
        for block_index in range((self.dim + block_floats - 1) // block_floats):
            digest = hashlib.sha512(
                text.encode("utf-8") + str(block_index).encode("ascii")
            ).digest()
            for j in range(block_floats):
                if len(vec) >= self.dim:
                    break
                chunk = digest[j * 4:j * 4 + 4]
                # Unsigned 32-bit int — guaranteed finite (never NaN / Inf)
                val = struct.unpack("I", chunk)[0]
                vec.append((val / 4294967295.0) * 2.0 - 1.0)
        # Normalize to unit vector
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @property
    def identity(self) -> str:
        """Stable embedder identity tag stamped on stored embedding rows.

        Vectors from different identities are incomparable; retrieval,
        dedup and linking never cross-compare rows whose non-null tags
        differ. The hash fallback carries its own versioned tag.
        """
        if self._fallback:
            return "hash-fallback:v2"
        if self._backend == "provider":
            return f"provider:{self._provider_name}:{self.model_name}"
        return f"{self._backend or 'fastembed'}:{self.model_name}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._fallback:
            return [self._hash_embed(t) for t in texts]
        try:
            if self._backend == "provider":
                # Use the new provider abstraction
                vecs = self._provider.embed_batch(texts)
                return [v.tolist() for v in vecs]
            elif self._backend == "sentence_transformers":
                embeddings = self._model.encode(texts, show_progress_bar=False)
                return [e.tolist() for e in embeddings]
            else:
                embeddings = list(self._model.embed(texts))
                return [e.tolist() for e in embeddings]
        except Exception as e:
            raise EmbeddingError(f"Embedding generation failed: {e}") from e

    def embed_single(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def vector_to_bytes(self, vec: list[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    def bytes_to_vector(self, raw: bytes) -> list[float]:
        count = len(raw) // 4
        return list(struct.unpack(f"{count}f", raw))
