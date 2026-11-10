"""G1: ANN auto-build threshold shares the recall scan cap (blind-zone fix)."""
import inspect

import numpy as np
import pytest
from unittest.mock import MagicMock

from evolver.config import DEFAULT_MAX_SCAN
from evolver.memory import MemoryEngine
from evolver.models import Memory
from evolver.retrieval import RetrievalEngine


def test_ann_threshold_shares_recall_scan_constant():
    # One source of truth: the ANN auto-build threshold and the brute-force
    # recall scan cap are the same constant, so the 2000-5000 blind zone
    # (memories too old for the scan, too few for the ANN build) cannot reopen.
    assert MemoryEngine._ANN_THRESHOLD == DEFAULT_MAX_SCAN
    signature = inspect.signature(RetrievalEngine.recall)
    assert signature.parameters["max_scan"].default == DEFAULT_MAX_SCAN


def _engine(storage, embedding, tmp_path):
    return MemoryEngine(storage, embedding, ann_index_path=str(tmp_path / "test.ann"))


def _seeded_storage(count: int):
    storage = MagicMock()
    storage.stats.return_value = {"memories": count}
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="alpha", category="success", embedding=b"\x01" * 16),
        Memory(id=2, content="beta", category="success", embedding=b"\x02" * 16),
    ]
    return storage


def _embedding():
    embedding = MagicMock()
    embedding.dim = 4
    vectors = {
        b"\x01" * 16: [1.0, 0.0, 0.0, 0.0],
        b"\x02" * 16: [0.0, 1.0, 0.0, 0.0],
    }
    embedding.bytes_to_vector.side_effect = lambda data: vectors[data]
    return embedding


def test_ann_auto_builds_once_store_reaches_threshold(tmp_path):
    # At >= DEFAULT_MAX_SCAN memories the ANN index builds eagerly, so recall
    # can reach memories beyond the newest max_scan brute-force window.
    storage = _seeded_storage(DEFAULT_MAX_SCAN + 500)
    engine = _engine(storage, _embedding(), tmp_path)
    engine._ensure_ann()
    assert engine.ann_ready
    storage.get_all_memories_with_embeddings.assert_called()


def test_ann_not_built_below_threshold(tmp_path):
    storage = _seeded_storage(DEFAULT_MAX_SCAN - 1)
    engine = _engine(storage, _embedding(), tmp_path)
    engine._ensure_ann()
    assert not engine.ann_ready
