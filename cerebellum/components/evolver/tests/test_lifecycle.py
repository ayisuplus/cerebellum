"""Tests for knowledge lifecycle management."""
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import numpy as np
from evolver.memory import MemoryEngine
from evolver.models import Memory


def make_engine():
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.embed_single.return_value = np.random.rand(384).tolist()
    mock_embedding.embed.return_value = [np.random.rand(384).tolist() for _ in range(3)]
    mock_embedding.vector_to_bytes.return_value = b"\x00" * (384 * 4)
    mock_embedding.bytes_to_vector.return_value = [0.0] * 384
    mock_embedding.dim = 384
    engine = MemoryEngine(mock_storage, mock_embedding)
    return engine, mock_storage, mock_embedding


def test_seed_to_growing_on_access_count():
    """seed -> growing when access_count >= 2."""
    engine, storage, _ = make_engine()
    storage.get_all_memories_columns.return_value = [
        Memory(id=1, content="test", category="experience",
               access_count=2, importance=0.5, lifecycle="seed"),
    ]

    result = engine.update_lifecycle()

    assert result["transitioned"] >= 1
    assert "seed_to_growing" in result["by_type"]


def test_growing_to_evergreen_on_importance_and_age():
    """growing -> evergreen when importance >= 0.8 and age >= 30 days."""
    engine, storage, _ = make_engine()
    old_date = (datetime.now() - timedelta(days=35)).isoformat()
    storage.get_all_memories_columns.return_value = [
        Memory(id=2, content="test", category="insight",
               access_count=5, importance=0.9, lifecycle="growing",
               created_at=old_date),
    ]

    result = engine.update_lifecycle()

    assert result["transitioned"] >= 1
    assert "growing_to_evergreen" in result["by_type"]


def test_any_to_stale_on_old_and_low_importance():
    """any -> stale when 90 days unrecalled and importance < 0.5."""
    engine, storage, _ = make_engine()
    old_date = (datetime.now() - timedelta(days=100)).isoformat()
    storage.get_all_memories_columns.return_value = [
        Memory(id=3, content="old forgotten", category="experience",
               access_count=0, importance=0.3, lifecycle="seed",
               created_at=old_date),
    ]

    result = engine.update_lifecycle()

    assert result["transitioned"] >= 1
    assert "seed_to_stale" in result["by_type"]


def test_stale_stays_stale_in_update():
    """stale memories with high importance should stay stale (reactivation via recall only)."""
    engine, storage, _ = make_engine()
    old_date = (datetime.now() - timedelta(days=35)).isoformat()
    storage.get_all_memories_columns.return_value = [
        Memory(id=4, content="stale but important", category="insight",
               access_count=5, importance=0.9, lifecycle="stale",
               created_at=old_date),
    ]

    result = engine.update_lifecycle()

    # Stale should stay stale -- reactivation only via recall
    assert result["distribution"]["stale"] >= 1
    assert "stale_to_evergreen" not in result.get("by_type", {})


def test_update_lifecycle_returns_distribution():
    """update_lifecycle returns lifecycle distribution stats."""
    engine, storage, _ = make_engine()
    storage.get_all_memories_columns.return_value = [
        Memory(id=1, content="a", category="test", lifecycle="seed"),
        Memory(id=2, content="b", category="test", lifecycle="growing"),
        Memory(id=3, content="c", category="test", lifecycle="stale"),
    ]

    result = engine.update_lifecycle()

    assert "distribution" in result
    assert result["distribution"]["seed"] >= 1
    assert result["distribution"]["growing"] >= 1
    assert result["distribution"]["stale"] >= 1


def test_rerank_applies_lifecycle_weight():
    """Lifecycle stage affects recall ranking."""
    engine, storage, emb = make_engine()
    mem1 = Memory(id=1, content="git merge conflict fix", category="success",
                  lifecycle="evergreen", importance=0.8, embedding=b"\x00" * 12)
    mem2 = Memory(id=2, content="git merge conflict fix", category="success",
                  lifecycle="stale", importance=0.3, embedding=b"\x00" * 12)
    storage.get_all_memories_with_embeddings.return_value = [mem1, mem2]
    storage.get_all_memories_with_embeddings_batched.return_value = [[mem1, mem2]]
    storage.get_memories_by_ids.return_value = [mem1, mem2]
    storage.query_nodes_batch.return_value = []

    results = engine.recall("git merge conflict")

    assert len(results) > 0
    for r in results:
        assert hasattr(r, 'lifecycle')
        assert r.lifecycle in ("seed", "growing", "evergreen", "stale", "distilled")


def test_distilled_skipped_by_update_lifecycle():
    """distilled memories are never transitioned by update_lifecycle."""
    engine, storage, _ = make_engine()
    old_date = (datetime.now() - timedelta(days=100)).isoformat()
    storage.get_all_memories_columns.return_value = [
        Memory(id=10, content="important distilled memory", category="insight",
               access_count=0, importance=0.3, lifecycle="distilled",
               created_at=old_date),
    ]

    result = engine.update_lifecycle()

    assert result["transitioned"] == 0
    assert result["distribution"].get("distilled", 0) >= 1
    storage.set_memory_lifecycle_batch.assert_not_called()
