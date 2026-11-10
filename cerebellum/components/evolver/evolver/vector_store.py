"""Vector store abstraction layer.

Supports multiple vector backends:
- InMemoryVectorStore: in-memory hnswlib (default, dev)
- QdrantVectorStore: Qdrant vector database (production)
"""

import logging
import heapq
import threading
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Vector storage interface for embeddings."""

    @abstractmethod
    def upsert(self, id: int, vector: np.ndarray, metadata: dict = None):
        """Insert or update a vector with optional metadata."""
        ...

    def upsert_many(self, items: list[tuple[int, np.ndarray, dict]]):
        """Insert or update multiple vectors.

        Backends can override this to use a native batch API.  The default
        implementation preserves compatibility with third-party stores.
        """
        for vector_id, vector, metadata in items:
            self.upsert(vector_id, vector, metadata)

    @abstractmethod
    def search(self, vector: np.ndarray, top_k: int = 10,
               filter_metadata: dict = None) -> List[Tuple[int, float]]:
        """Search for similar vectors. Returns list of (id, score)."""
        ...

    @abstractmethod
    def delete(self, id: int):
        """Delete a vector by ID."""
        ...

    def delete_many(self, ids: list[int]):
        """Delete multiple vectors."""
        for vector_id in ids:
            self.delete(vector_id)

    @abstractmethod
    def count(self) -> int:
        """Return the number of vectors stored."""
        ...

    @abstractmethod
    def list_ids(self) -> set[int]:
        """Return all vector IDs for consistency reconciliation."""
        ...


class QdrantVectorStore(VectorStore):
    """Qdrant vector database backend (production)."""

    def __init__(self, url: str = "http://localhost:6333",
                 collection: str = "evolver_memory",
                 dimension: int = 1024,
                 api_key: Optional[str] = None):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import VectorParams, Distance
        except ImportError:
            raise ImportError(
                "qdrant-client is required for Qdrant vector store. "
                "Install with: pip install qdrant-client"
            )

        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection = collection
        self._dim = dimension

        # Create collection if it doesn't exist
        if not self._client.collection_exists(collection):
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE)
            )
            logger.info("Created Qdrant collection '%s' (dim=%d)", collection, dimension)

    def upsert(self, id: int, vector: np.ndarray, metadata: dict = None):
        from qdrant_client.models import PointStruct
        self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=id, vector=vector.tolist(), payload=metadata or {})]
        )

    def upsert_many(self, items: list[tuple[int, np.ndarray, dict]]):
        if not items:
            return
        from qdrant_client.models import PointStruct
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=vector_id,
                    vector=np.asarray(vector, dtype=np.float32).reshape(-1).tolist(),
                    payload=metadata or {},
                )
                for vector_id, vector, metadata in items
            ],
        )

    def search(self, vector: np.ndarray, top_k: int = 10,
               filter_metadata: dict = None) -> List[Tuple[int, float]]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_filter = None
        if filter_metadata:
            query_filter = Filter(must=[
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_metadata.items()
            ])

        results = self._client.search(
            collection_name=self._collection,
            query_vector=vector.tolist(),
            limit=top_k,
            query_filter=query_filter
        )
        return [(r.id, r.score) for r in results]

    def delete(self, id: int):
        self._client.delete(
            collection_name=self._collection,
            points_selector=[id]
        )

    def delete_many(self, ids: list[int]):
        if not ids:
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=ids,
        )

    def count(self) -> int:
        return self._client.get_collection(self._collection).points_count

    def list_ids(self) -> set[int]:
        ids: set[int] = set()
        offset = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self._collection,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            ids.update(int(record.id) for record in records)
            if offset is None:
                return ids


class InMemoryVectorStore(VectorStore):
    """In-memory vector store (development, fallback)."""

    def __init__(self, dimension: int = 384):
        self._dim = dimension
        self._vectors = {}  # id -> (vector, metadata)
        self._lock = threading.RLock()

    def upsert(self, id: int, vector: np.ndarray, metadata: dict = None):
        normalized = np.asarray(vector, dtype=np.float32).reshape(-1)
        if normalized.size != self._dim:
            raise ValueError(
                f"Vector dimension mismatch: expected {self._dim}, got {normalized.size}"
            )
        with self._lock:
            self._vectors[id] = (normalized.copy(), dict(metadata or {}))

    def search(self, vector: np.ndarray, top_k: int = 10,
               filter_metadata: dict = None) -> List[Tuple[int, float]]:
        if top_k <= 0:
            return []
        query = np.asarray(vector, dtype=np.float32).reshape(-1)
        if query.size != self._dim:
            raise ValueError(
                f"Query dimension mismatch: expected {self._dim}, got {query.size}"
            )
        query_norm = np.linalg.norm(query)
        results = []
        with self._lock:
            for vid, (vec, meta) in self._vectors.items():
                # Apply metadata filter
                if filter_metadata:
                    if not all(meta.get(k) == v for k, v in filter_metadata.items()):
                        continue

                # Cosine similarity
                norm_b = np.linalg.norm(vec)
                if query_norm == 0 or norm_b == 0:
                    sim = 0.0
                else:
                    sim = float(np.dot(query, vec) / (query_norm * norm_b))
                results.append((vid, sim))

        return heapq.nlargest(top_k, results, key=lambda item: item[1])

    def delete(self, id: int):
        with self._lock:
            self._vectors.pop(id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._vectors)

    def list_ids(self) -> set[int]:
        with self._lock:
            return set(self._vectors)


def create_vector_store(store_type: str = "memory",
                        url: Optional[str] = None,
                        collection: str = "evolver_memory",
                        dimension: int = 1024,
                        api_key: Optional[str] = None) -> VectorStore:
    """Factory function to create a vector store.

    Args:
        store_type: "memory" or "qdrant"
        url: Qdrant server URL (required for qdrant)
        collection: Collection name
        dimension: Vector dimension
        api_key: Qdrant API key (optional)

    Returns:
        VectorStore instance
    """
    if store_type == "qdrant":
        return QdrantVectorStore(
            url=url or "http://localhost:6333",
            collection=collection,
            dimension=dimension,
            api_key=api_key,
        )
    elif store_type == "memory":
        return InMemoryVectorStore(dimension=dimension)
    else:
        raise ValueError(f"Unknown vector store type: {store_type}")
