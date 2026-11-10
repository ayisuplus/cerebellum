"""Tests for ANNIndex — both HNSW (if available) and brute-force paths."""

import numpy as np
from evolver.ann_index import ANNIndex


def _make_vectors(n: int, dim: int = 384) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.random((n, dim)).astype(np.float32)


class TestANNIndexBruteForce:
    """Brute-force path (use_hnsw=False explicitly)."""

    def test_add_and_search(self):
        idx = ANNIndex(dim=384, use_hnsw=False)
        ids = [1, 2, 3]
        vectors = _make_vectors(3)
        idx.add(ids, vectors)
        idx.build()

        results = idx.search(vectors[0], top_k=2)
        assert len(results) == 2
        # Closest should be id=1 (distance ~0)
        assert results[0][0] == 1
        assert results[0][1] < 0.01

    def test_empty_index(self):
        idx = ANNIndex(dim=384, use_hnsw=False)
        results = idx.search(np.zeros(384), top_k=5)
        assert results == []

    def test_search_returns_correct_ids(self):
        idx = ANNIndex(dim=8, use_hnsw=False)
        ids = [10, 20, 30, 40]
        vectors = np.array([
            [1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 0],
        ], dtype=np.float32)
        idx.add(ids, vectors)
        idx.build()

        results = idx.search(np.array([1, 0, 0, 0, 0, 0, 0, 0]), top_k=2)
        assert results[0][0] == 10

    def test_remove_ids(self):
        idx = ANNIndex(dim=8, use_hnsw=False)
        idx.add([1, 2, 3], np.array([[1, 0], [0, 1], [0, 0]], dtype=np.float32))
        idx.build()
        idx.remove({2})
        assert idx.size == 2
        assert 2 not in idx._ids

    def test_remove_all_ids(self):
        idx = ANNIndex(dim=8, use_hnsw=False)
        idx.add([1, 2], np.array([[1, 0], [0, 1]], dtype=np.float32))
        idx.build()
        idx.remove({1, 2})
        assert idx.size == 0
        assert idx._vectors is None

    def test_clear(self):
        idx = ANNIndex(dim=8, use_hnsw=False)
        idx.add([1, 2], np.array([[1, 0], [0, 1]], dtype=np.float32))
        idx.build()
        idx.clear()
        assert idx.size == 0
        assert idx._vectors is None


class TestANNIndexAutoDetect:
    """Auto-detect path — runs hnswlib if available, else brute-force."""

    def test_size_property(self):
        idx = ANNIndex(dim=384)
        assert idx.size == 0
        idx.add([1, 2], _make_vectors(2))
        assert idx.size == 2

    def test_lazy_build_on_search(self):
        idx = ANNIndex(dim=384)
        idx.add([1], _make_vectors(1))
        # build not called yet
        assert idx._dirty is True
        # search triggers build
        results = idx.search(np.zeros(384), top_k=1)
        assert len(results) == 1
        assert idx._dirty is False


class TestANNIndexAddSingle:
    """Edge cases for .add()."""

    def test_single_vector_as_1d(self):
        idx = ANNIndex(dim=8, use_hnsw=False)
        vec = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        idx.add([1], vec)  # 1D gets reshaped
        idx.build()
        results = idx.search(vec, top_k=1)
        assert results[0][0] == 1

    def test_progressive_adds(self):
        idx = ANNIndex(dim=8, use_hnsw=False)
        idx.add([1], np.array([[1, 0, 0, 0, 0, 0, 0, 0]], dtype=np.float32))
        idx.add([2], np.array([[0, 1, 0, 0, 0, 0, 0, 0]], dtype=np.float32))
        idx.build()
        assert idx.size == 2

    def test_build_with_no_ids(self):
        idx = ANNIndex(dim=8, use_hnsw=False)
        idx.build()  # Should not raise
        assert idx.size == 0
