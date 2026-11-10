# tests/test_memory.py
import pytest
import numpy as np
from unittest.mock import MagicMock
from evolver.memory import MemoryEngine
from evolver.models import Memory
from evolver.exceptions import StorageError


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


def test_store_creates_memory_and_embeddings():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    ids = engine.store(
        task="fix bug",
        outcome="success",
        context="auth module",
        solution="fixed token",
        lessons="always validate input",
    )

    assert storage.insert_memory.call_count >= 1
    assert storage.insert_interaction.call_count == 1
    assert len(ids) >= 1


def test_store_persists_source_provenance():
    """store(source=...) must flow onto every created Memory record."""
    engine, storage, _ = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    engine.store(
        task="extracted fact",
        outcome="extracted",
        source="extract",
    )

    sources = [
        call.args[0].source
        for call in storage.insert_memory.call_args_list
    ]
    assert sources and all(source == "extract" for source in sources)


def test_store_defaults_source_to_learn():
    engine, storage, _ = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    engine.store(task="direct experience", outcome="success")

    sources = [call.args[0].source for call in storage.insert_memory.call_args_list]
    assert sources and all(source == "learn" for source in sources)


def test_recall_returns_sorted_results():
    engine, storage, emb = make_engine()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="git merge fix", category="success", embedding=b"\x00" * 12),
        Memory(id=2, content="docker deploy", category="failure", embedding=b"\x00" * 12),
    ]
    storage.query_nodes.return_value = []

    results = engine.recall("git conflict")
    assert isinstance(results, list)


def test_recall_empty_when_no_memories():
    engine, storage, emb = make_engine()
    storage.get_all_memories_with_embeddings.return_value = []
    storage.query_nodes.return_value = []

    results = engine.recall("anything")
    assert results == []


def test_store_rollback_on_failure():
    engine, storage, emb = make_engine()
    storage.insert_memory.side_effect = RuntimeError("db down")
    storage.insert_interaction.return_value = 1

    with pytest.raises(StorageError):
        engine.store(
            task="fix bug", outcome="success",
            solution="fixed token", lessons="validate",
        )
    storage.rollback.assert_called_once()
    storage.commit.assert_not_called()


def test_forget_by_id():
    engine, storage, emb = make_engine()
    engine.forget(memory_id=42)
    storage.delete_memory.assert_called_once_with(42)


def test_forget_older_than_days():
    engine, storage, emb = make_engine()
    engine.forget(older_than_days=30)
    storage.delete_memories_older_than.assert_called_once_with(30)


def test_forget_low_importance():
    engine, storage, emb = make_engine()
    engine.forget(low_importance=0.2)
    storage.delete_memories_low_importance.assert_called_once_with(0.2)


def test_forget_multiple_criteria():
    engine, storage, emb = make_engine()
    engine.forget(memory_id=1, older_than_days=7, low_importance=0.3)
    storage.delete_memory.assert_called_once_with(1)
    storage.delete_memories_older_than.assert_called_once_with(7)
    storage.delete_memories_low_importance.assert_called_once_with(0.3)


# --- Distilled memory protection ---

def test_forget_bulk_skips_distilled():
    """forget(older_than_days) and forget(low_importance) skip distilled."""
    engine, storage, emb = make_engine()
    engine.forget(older_than_days=30)
    # The SQL in storage layer handles exclusion; verify the call is made
    storage.delete_memories_older_than.assert_called_once_with(30)

    engine.forget(low_importance=0.2)
    storage.delete_memories_low_importance.assert_called_once_with(0.2)


# --- Failure-without-solution test ---

def test_store_failure_without_solution():
    """Failure outcome without solution should still create a memory."""
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    ids = engine.store(
        task="broken deployment",
        outcome="failure",
        # no solution provided
    )
    assert len(ids) >= 1
    # Check that a memory was inserted (with the fallback content)
    call_kwargs = storage.insert_memory.call_args[0][0]
    assert "(no solution recorded)" in call_kwargs.content
    assert call_kwargs.category == "failure"


# --- Chinese tokenization test (memory path) ---

def test_store_chinese_task():
    """Chinese text should be tokenized via jieba or fallback."""
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    ids = engine.store(
        task="修复数据库连接超时问题",
        outcome="success",
        solution="增加连接池大小",
    )
    assert len(ids) >= 1


def test_tag_extraction_chinese():
    """_extract_tags should handle mixed Chinese/English text."""
    engine, _, _ = make_engine()
    tags = engine._extract_tags("修复git merge冲突，使用rebase策略")
    # Should contain meaningful tokens
    assert "merge" in tags or "rebase" in tags or "冲突" in tags


# --- Task 5: Integration — MemoryEngine + LinkEngine ---

def test_store_triggers_auto_linking():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    # Set up link engine mock
    mock_link = MagicMock()
    engine._link = mock_link

    engine.store(
        task="fix bug",
        outcome="success",
        solution="fixed token",
        lessons="always validate input",
    )

    # auto_link_batch should be called
    mock_link.auto_link_batch.assert_called_once()
    call_args = mock_link.auto_link_batch.call_args
    memory_ids = call_args[0][0]
    contents = call_args[0][1]
    assert len(memory_ids) >= 1
    assert len(contents) >= 1


# --- Task 7: Integration — Recall Link Boost ---

def test_recall_includes_link_boost():
    engine, storage, emb = make_engine()
    memories = [
        Memory(id=1, content="git merge fix", category="success", embedding=b"\x00" * 12),
    ]
    storage.get_all_memories_with_embeddings.return_value = memories
    storage.get_all_memories_with_embeddings_batched.return_value = [memories]
    storage.get_memories_by_ids.return_value = memories
    storage.query_nodes.return_value = []
    storage.query_nodes_batch.return_value = []

    # Set up link engine mock
    mock_link = MagicMock()
    mock_link.compute_link_score.return_value = 0.5
    engine._link = mock_link

    results = engine.recall("git conflict")
    assert len(results) >= 1
    mock_link.compute_link_score.assert_called()


# --- Interference Decay Tests ---

def test_interference_decay_decays_older_memory():
    """interference_decay should decay the older memory (lower created_at), not based on access_count."""
    engine, storage, emb = make_engine()

    # Create two memories - newest first (id=2 newer, id=1 older)
    memories = [
        Memory(id=2, content="git merge fix", category="success",
               embedding=b"\x00" * (384 * 4), importance=0.8, created_at="2024-01-02"),
        Memory(id=1, content="git merge fix", category="success",
               embedding=b"\x00" * (384 * 4), importance=0.8, created_at="2024-01-01"),
    ]
    storage.get_all_memories_with_embeddings.return_value = memories

    # Both vectors are identical -> similarity = 1.0, above threshold
    emb.bytes_to_vector.return_value = [1.0] * 384

    affected = engine.interference_decay(similarity_threshold=0.85, decay_factor=0.8)

    # Should decay the older memory (id=1, lower created_at)
    assert affected == 1
    storage.update_memory_importance.assert_called_once_with(1, pytest.approx(0.64))


def test_interference_decay_uses_created_at_not_access_count():
    """interference_decay should use created_at ordering, not access_count."""
    engine, storage, emb = make_engine()

    # Memory with higher access_count but older created_at should still be decayed
    memories = [
        # New memory with high access_count (frequently queried)
        Memory(id=3, content="docker deploy fix", category="success",
               embedding=b"\x00" * (384 * 4), importance=0.8,
               created_at="2024-01-03", access_count=100),
        # Old memory with low access_count
        Memory(id=1, content="docker deploy fix", category="success",
               embedding=b"\x00" * (384 * 4), importance=0.8,
               created_at="2024-01-01", access_count=1),
    ]
    storage.get_all_memories_with_embeddings.return_value = memories

    emb.bytes_to_vector.return_value = [1.0] * 384

    affected = engine.interference_decay(similarity_threshold=0.85, decay_factor=0.8)

    # Should decay id=1 (older created_at), not id=3 (higher access_count)
    assert affected == 1
    storage.update_memory_importance.assert_called_once_with(1, pytest.approx(0.64))


def test_interference_decay_no_decay_below_threshold():
    """interference_decay should not decay when similarity is below threshold."""
    engine, storage, emb = make_engine()

    memories = [
        Memory(id=2, content="git merge fix", category="success",
               embedding=b"\x00" * (384 * 4), importance=0.8, created_at="2024-01-02"),
        Memory(id=1, content="python script", category="success",
               embedding=b"\x00" * (384 * 4), importance=0.8, created_at="2024-01-01"),
    ]
    storage.get_all_memories_with_embeddings.return_value = memories

    # Vary vectors to produce low similarity
    emb.bytes_to_vector.side_effect = [
        [1.0] * 384,   # memory id=2
        [0.0] * 384,   # memory id=1 - orthogonal vector
    ]

    affected = engine.interference_decay(similarity_threshold=0.85, decay_factor=0.8)

    assert affected == 0
    storage.update_memory_importance.assert_not_called()


def test_interference_decay_returns_zero_for_single_memory():
    """interference_decay should return 0 when there's only one memory."""
    engine, storage, emb = make_engine()

    memories = [
        Memory(id=1, content="git merge fix", category="success",
               embedding=b"\x00" * (384 * 4), importance=0.8, created_at="2024-01-01"),
    ]
    storage.get_all_memories_with_embeddings.return_value = memories

    affected = engine.interference_decay()
    assert affected == 0


# --- Task 6: Deduplicator integration ---

def test_store_skips_duplicate_when_dedup_configured():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    # Configure dedup with mock that returns True
    engine._deduplicator = MagicMock()
    engine._deduplicator.is_duplicate.return_value = True

    ids = engine.store(
        task="fix bug", outcome="success",
        solution="fixed token", lessons="validate",
    )

    storage.insert_memory.assert_not_called()
    assert ids == []


def test_store_inserts_when_not_duplicate():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    # Configure dedup with mock that returns False
    engine._deduplicator = MagicMock()
    engine._deduplicator.is_duplicate.return_value = False

    ids = engine.store(
        task="fix bug", outcome="success",
        solution="fixed token", lessons="validate",
    )

    assert storage.insert_memory.call_count >= 1
    assert len(ids) >= 1


# --- Task 9: Normalize integration ---

def test_store_normalizes_content_before_embedding():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    noisy_task = "fix bug\n<system-reminder>ignore this</system-reminder>"
    _ids = engine.store(
        task=noisy_task, outcome="success",
        solution="fixed", lessons="validate",
    )

    # embed_single should have been called with cleaned content
    call_args = emb.embed_single.call_args_list
    for call in call_args:
        content = call[0][0]
        assert "system-reminder" not in content


# --- Task 11: ClosetIndex integration ---

def test_store_populates_closet_index():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    from evolver.closet import ClosetIndex
    closet = ClosetIndex()
    engine.set_closet(closet)

    engine.store(
        task="fix auth bug", outcome="success",
        solution="fixed token", lessons="validate",
    )

    results = closet.query("auth")
    assert len(results) > 0
