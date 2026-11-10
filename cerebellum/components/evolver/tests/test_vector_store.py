"""Tests for vector store implementations."""

import pytest
import numpy as np

from evolver.vector_store import (
    VectorStore,
    InMemoryVectorStore,
    create_vector_store,
)


class TestVectorStoreInterface:
    """Verify the ABC contract."""

    def test_abc_cannot_instantiate(self):
        """VectorStore is abstract."""
        with pytest.raises(TypeError):
            VectorStore()


class TestInMemoryVectorStore:
    """Tests for in-memory vector store."""

    def test_upsert_and_count(self):
        store = InMemoryVectorStore(dimension=384)
        assert store.count() == 0

        vec = np.random.randn(384).astype(np.float32)
        store.upsert(id=1, vector=vec, metadata={"category": "test"})
        assert store.count() == 1

    def test_search_returns_top_k(self):
        store = InMemoryVectorStore(dimension=384)

        # Insert 5 vectors
        for i in range(5):
            vec = np.random.randn(384).astype(np.float32)
            store.upsert(id=i, vector=vec)

        # Search with random query
        query = np.random.randn(384).astype(np.float32)
        results = store.search(query, top_k=3)

        assert len(results) == 3
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
        # Results should be sorted by score (descending)
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_with_metadata_filter(self):
        store = InMemoryVectorStore(dimension=384)

        vec1 = np.random.randn(384).astype(np.float32)
        vec2 = np.random.randn(384).astype(np.float32)
        store.upsert(id=1, vector=vec1, metadata={"category": "success"})
        store.upsert(id=2, vector=vec2, metadata={"category": "failure"})

        query = np.random.randn(384).astype(np.float32)

        # Filter by category
        results = store.search(query, top_k=10, filter_metadata={"category": "success"})
        assert len(results) == 1
        assert results[0][0] == 1

    def test_delete(self):
        store = InMemoryVectorStore(dimension=384)
        vec = np.random.randn(384).astype(np.float32)
        store.upsert(id=1, vector=vec)
        assert store.count() == 1

        store.delete(id=1)
        assert store.count() == 0

    def test_update_existing(self):
        store = InMemoryVectorStore(dimension=384)

        vec1 = np.random.randn(384).astype(np.float32)
        vec2 = np.random.randn(384).astype(np.float32)

        store.upsert(id=1, vector=vec1, metadata={"version": 1})
        store.upsert(id=1, vector=vec2, metadata={"version": 2})

        assert store.count() == 1  # should update, not create new


class TestCreateProvider:
    """Tests for the factory function."""

    def test_memory_default(self):
        store = create_vector_store("memory", dimension=384)
        assert isinstance(store, InMemoryVectorStore)
        assert store.count() == 0

    def test_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown vector store type"):
            create_vector_store("nonexistent")
