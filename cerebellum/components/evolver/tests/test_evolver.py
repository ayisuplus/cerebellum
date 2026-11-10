# tests/test_evolver.py
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from evolver import Evolver
from evolver.exceptions import EvolverError


def test_evolver_init():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        assert e is not None


def test_evolver_init_missing_url():
    with pytest.raises((ValueError, TypeError)):
        Evolver(mysql_url="")


def test_evolver_learn():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        emb = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = emb
        emb.embed_single.return_value = [0.1] * 384
        emb.vector_to_bytes.return_value = b"\x00" * 12
        storage.insert_memory.return_value = 1
        storage.insert_interaction.return_value = 1

        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        ids = e.learn(
            task="test task",
            outcome="success",
            solution="test solution",
        )
        assert len(ids) >= 1


def test_evolver_stats():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = MagicMock()
        storage.stats.return_value = {
            "memories": 5, "nodes": 3, "edges": 2,
            "skills": 1, "interactions": 4,
        }

        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        s = e.stats()
        assert s["memories"] == 5
        assert s["nodes"] == 3


def test_evolver_sqlite_init():
    """Test SQLite backend auto-detection."""
    with patch("evolver.EmbeddingClient") as MockEmb:
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="sqlite:///:memory:")
        assert e is not None
        e.close()


def test_evolver_db_url_param():
    """Test db_url parameter works same as mysql_url."""
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="mysql://root:root@localhost:3306/test")
        assert e is not None


def test_evolver_build_index():
    """Test build_index delegates to memory engine."""
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="mysql://root:root@localhost:3306/test")
        e._memory = MagicMock()
        e.build_index()
        e._memory.build_index.assert_called_once()


def test_evolver_sync_vector_store():
    """Test VectorStore reconciliation delegates to the memory engine."""
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="mysql://root:root@localhost:3306/test")
        e._memory = MagicMock()
        e._memory.sync_vector_store.return_value = {
            "upserted": 3, "deleted": 1, "processed": 2, "failed": 0,
        }

        result = e.sync_vector_store(batch_size=250, prune=False)

        assert result["upserted"] == 3
        e._memory.sync_vector_store.assert_called_once_with(
            batch_size=250, prune=False
        )


# --- Async method tests ---

@pytest.mark.asyncio
async def test_learn_async():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        emb = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = emb
        emb.embed_single.return_value = [0.1] * 384
        emb.vector_to_bytes.return_value = b"\x00" * 12
        storage.insert_memory.return_value = 1
        storage.insert_interaction.return_value = 1

        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        ids = await e.learn_async(task="async task", outcome="success", solution="async sol")
        assert len(ids) >= 1
        e.close()


@pytest.mark.asyncio
async def test_recall_async():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        emb = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = emb
        storage.get_all_memories_with_embeddings.return_value = []
        storage.query_nodes.return_value = []

        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        results = await e.recall_async("test query")
        assert isinstance(results, list)
        e.close()


@pytest.mark.asyncio
async def test_stats_async():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = MagicMock()
        storage.stats.return_value = {"memories": 3, "nodes": 1, "edges": 1,
                                       "skills": 0, "interactions": 2}

        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        s = await e.stats_async()
        assert s["memories"] == 3
        e.close()


@pytest.mark.asyncio
async def test_close_async():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="mysql://root:root@localhost:3306/test")
        await e.close_async()
        # Should not raise


def test_close_idempotent():
    """close() can be called multiple times without error."""
    with patch("evolver.SQLiteStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="sqlite:///test.db")
        e.close()
        e.close()  # idempotent - no error
        # storage.close should be called once
        assert storage.close.call_count == 1


@pytest.mark.asyncio
async def test_close_async_idempotent():
    """close_async() can be called multiple times without error."""
    with patch("evolver.SQLiteStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="sqlite:///test.db")
        await e.close_async()
        await e.close_async()  # idempotent - no error
        # storage.close should be called once
        assert storage.close.call_count == 1


# --- Context manager test ---

def test_context_manager():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = MagicMock()

        with Evolver(mysql_url="mysql://root:root@localhost:3306/test") as e:
            assert e is not None
        # close should have been called on exit
        storage.close.assert_called_once()


def test_context_manager_closes_on_error():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        storage = MagicMock()
        MockStorage.return_value = storage
        MockEmb.return_value = MagicMock()

        with pytest.raises(RuntimeError):
            with Evolver(mysql_url="mysql://root:root@localhost:3306/test") as e:
                assert e is not None
                raise RuntimeError("boom")
        # close should still have been called
        storage.close.assert_called_once()


# --- Facade method tests ---

def test_forget_delegates_to_memory():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="mysql://root:root@localhost:3306/test")
        e._memory = MagicMock()
        e.forget(memory_id=1, older_than_days=7, low_importance=0.3)
        e._memory.forget.assert_called_once_with(memory_id=1, older_than_days=7, low_importance=0.3)
        e.close()


def test_forget_empty_call():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="mysql://root:root@localhost:3306/test")
        e._memory = MagicMock()
        e.forget()  # No args — should not raise
        e._memory.forget.assert_called_once_with(memory_id=None, older_than_days=None, low_importance=None)
        e.close()


def test_skillgen_delegates():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(db_url="mysql://root:root@localhost:3306/test")
        e._skill = MagicMock()
        e._skill.generate.return_value = MagicMock()
        e._skill_library = MagicMock()
        e._skill_library.get_skill.return_value = None
        result = e.skillgen("test topic")
        e._skill.generate.assert_called_once_with("test topic", output_dir="./skills", lang="zh")
        assert result is not None
        e.close()


# --- Task 8: LinkEngine + QualityChecker facade methods ---


def test_backlinks_method():
    """Evolver.backlinks delegates to LinkEngine."""
    from evolver.models import Link
    with patch("evolver.EmbeddingClient") as MockEmb:
        MockEmb.return_value = MagicMock()
        evolver = Evolver(db_url="sqlite://:memory:")
        evolver._storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.8)
        result = evolver.backlinks("memory", 2)
        assert len(result) == 1
        assert isinstance(result[0], Link)
        evolver.close()


def test_linked_memories_method():
    """Evolver.linked_memories delegates to LinkEngine."""
    with patch("evolver.EmbeddingClient") as MockEmb:
        emb = MagicMock()
        MockEmb.return_value = emb
        emb.embed_single.return_value = [0.1] * 384
        emb.vector_to_bytes.return_value = b"\x00" * 12
        evolver = Evolver(db_url="sqlite://:memory:")
        evolver.learn(task="test task", outcome="success", solution="test solution")
        result = evolver.linked_memories(1, top_k=5)
        assert isinstance(result, list)
        evolver.close()


def test_eval_skill_method():
    """Evolver.eval_skill delegates to QualityChecker."""
    with patch("evolver.EmbeddingClient") as MockEmb:
        MockEmb.return_value = MagicMock()
        evolver = Evolver(db_url="sqlite://:memory:")
        result = evolver.eval_skill(
            "---\nname: test\ndescription: test\n---\n# Test\n## Steps\n1. Do thing\n",
            "test topic",
        )
        assert result.total_score > 0
        assert len(result.dim_scores) == 8
        evolver.close()


# --- Task 9: End-to-end integration test ---


@patch("evolver.EmbeddingClient")
def test_end_to_end_learn_recall_skillgen_with_links_and_quality(mock_emb_cls):
    """Full pipeline: learn -> recall (with link boost) -> skillgen (with quality check)."""
    import numpy as np
    mock_emb = MagicMock()
    mock_emb.embed_single.return_value = np.random.rand(384).tolist()
    mock_emb.embed.return_value = [np.random.rand(384).tolist() for _ in range(3)]
    mock_emb.vector_to_bytes.return_value = b"\x00" * (384 * 4)
    mock_emb.bytes_to_vector.return_value = [0.0] * 384
    mock_emb.dim = 384
    mock_emb_cls.return_value = mock_emb

    evolver = Evolver(db_url="sqlite://:memory:")

    # Learn multiple related experiences
    evolver.learn(
        task="fix git merge conflict",
        outcome="success",
        solution="use git rebase instead of merge",
        lessons="always stash before rebase",
    )
    evolver.learn(
        task="resolve git rebase conflict",
        outcome="success",
        solution="edit conflicted files, then git rebase --continue",
        lessons="check git status before rebase",
    )
    evolver.learn(
        task="docker deploy fails",
        outcome="failure",
        solution="",
        lessons="check container logs first",
    )

    # Verify memories were stored
    stats = evolver.stats()
    assert stats["memories"] >= 3

    # Recall with link boost
    results = evolver.recall("git merge conflict")
    assert len(results) >= 1
    # Git-related memories should rank higher
    assert any("git" in r.content.lower() for r in results)

    # Generate skill with quality check
    with tempfile.TemporaryDirectory() as tmpdir:
        result = evolver.skillgen("git conflict resolution", output_dir=tmpdir)
        assert result is not None
        assert result.name == "git-conflict-resolution"
        assert len(result.content) > 100

    evolver.close()


# --- Auto-distill tests ---

def _make_evolver_with_mock(db_url="sqlite://:memory:", **kwargs):
    """Helper: create Evolver with properly mocked embedding."""
    import numpy as np
    with patch("evolver.EmbeddingClient") as MockEmb:
        emb = MagicMock()
        emb.embed_single.return_value = np.random.rand(384).tolist()
        emb.vector_to_bytes.return_value = b"\x00" * (384 * 4)
        emb.dim = 384
        MockEmb.return_value = emb
        e = Evolver(db_url=db_url, **kwargs)
        return e


def test_auto_distill_triggered_when_stale():
    """Auto-distill fires when last run is older than threshold."""
    from datetime import datetime, timedelta, timezone
    e = _make_evolver_with_mock(auto_distill_hours=1)
    e._compiler = MagicMock()
    # Simulate stale distill run (2 hours ago, in UTC to match SQLite datetime('now'))
    e._storage.insert_distill_run("today", "abc123", "old output", 100)
    stale_time = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    p = e._storage._placeholder()
    e._storage._execute(
        f"UPDATE distill_runs SET created_at = {p} WHERE level = {p}",
        (stale_time, "today"),
    )
    e.learn(task="test", outcome="success")
    e._compiler.distill_all.assert_called_once()
    e.close()


def test_auto_distill_skipped_when_fresh():
    """Auto-distill skipped when last run is recent."""
    e = _make_evolver_with_mock(auto_distill_hours=24)
    e._compiler = MagicMock()
    e._storage.insert_distill_run("today", "abc123", "fresh output", 100)
    e.learn(task="test", outcome="success")
    e._compiler.distill_all.assert_not_called()
    e.close()


def test_auto_distill_disabled():
    """Auto-distill disabled when auto_distill_hours=0."""
    e = _make_evolver_with_mock(auto_distill_hours=0)
    e._compiler = MagicMock()
    e.learn(task="test", outcome="success")
    e._compiler.distill_all.assert_not_called()
    e.close()


def test_auto_distill_triggered_when_no_history():
    """Auto-distill fires when no distill history exists."""
    e = _make_evolver_with_mock(auto_distill_hours=24)
    e._compiler = MagicMock()
    e.learn(task="test", outcome="success")
    e._compiler.distill_all.assert_called_once()
    e.close()


def test_evolver_dedup_closet_stack_wired():
    """v0.10 features (Deduplicator/ClosetIndex/MemoryStack) are wired by default."""
    e = Evolver(db_url="sqlite:///:memory:", fallback_embeddings=True,
                auto_distill_hours=0)
    try:
        assert e._deduplicator is not None
        assert e._closet is not None
        assert e._stack is not None
        assert e._memory._deduplicator is e._deduplicator
        assert e._memory._closet is e._closet
    finally:
        e.close()


def test_evolver_dedup_blocks_duplicate_learn():
    """Duplicate learn() is rejected by inline Deduplicator."""
    e = Evolver(db_url="sqlite:///:memory:", fallback_embeddings=True,
                auto_distill_hours=0, dedup_threshold=0.5)
    try:
        first = e.learn(task="git rebase", outcome="success",
                        solution="use --interactive")
        second = e.learn(task="git rebase", outcome="success",
                         solution="use --interactive")
        assert len(first) >= 1
        assert second == []  # blocked as duplicate
    finally:
        e.close()


def test_evolver_closet_query_after_learn():
    """ClosetIndex finds memory IDs by keyword after learn()."""
    e = Evolver(db_url="sqlite:///:memory:", fallback_embeddings=True,
                auto_distill_hours=0)
    try:
        e.learn(task="docker compose up", outcome="success")
        hits = e.closet_query("docker")
        assert len(hits) >= 1
    finally:
        e.close()


def test_evolver_can_disable_dedup_and_closet():
    """Flags turn v0.10 features off."""
    e = Evolver(db_url="sqlite:///:memory:", fallback_embeddings=True,
                auto_distill_hours=0, enable_dedup=False, enable_closet=False)
    try:
        assert e._deduplicator is None
        assert e._closet is None
        assert e._memory._deduplicator is None
        assert e._memory._closet is None
    finally:
        e.close()


def test_recall_fills_snippet():
    """recall() populates RecallResult.snippet (was empty in v1.0.0)."""
    e = Evolver(db_url="sqlite:///:memory:", fallback_embeddings=True,
                auto_distill_hours=0)
    try:
        e.learn(task="some long task description for testing snippet population",
                outcome="success",
                solution="solution body that should appear in snippet")
        results = e.recall("snippet population")
        assert results
        assert all(r.snippet for r in results)
    finally:
        e.close()


def test_wake_up_returns_layered_context():
    """wake_up() returns L0 identity + L1 essential story."""
    e = Evolver(db_url="sqlite:///:memory:", fallback_embeddings=True,
                auto_distill_hours=0)
    try:
        e.learn(task="learning Python", outcome="success",
                solution="use venv")
        text = e.wake_up()
        assert "L0" in text
        assert "L1" in text
    finally:
        e.close()


# --- Task 8: Archive layer assembly ---


def test_evolver_archive_disabled_by_default():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        assert e._archive is None


def test_evolver_invalid_data_url_scheme():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        with pytest.raises(ValueError):
            Evolver(mysql_url="mysql://root:root@localhost:3306/test",
                    data_url="sqlite:///nope.db")


def test_evolver_archive_constructed_lazily():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb, \
         patch("evolver.archive_store.ArchiveStore") as MockArchive:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        MockArchive.return_value = MagicMock()
        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test",
                    data_url="mysql://root:root@localhost:3306/data")
        assert e._archive is not None
        MockArchive.assert_called_once_with("mysql://root:root@localhost:3306/data")


# --- Task 9: Archive facade methods ---


def test_archive_methods_raise_when_not_configured():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test")
        with pytest.raises(EvolverError, match="data_url"):
            e.archive("c", kind="log")
        with pytest.raises(EvolverError, match="data_url"):
            e.search_archive("q")
        with pytest.raises(EvolverError, match="data_url"):
            e.get_archive(1)


def test_archive_methods_delegate_to_store():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb, \
         patch("evolver.archive_store.ArchiveStore") as MockArchive:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        store = MagicMock()
        store.archive.return_value = 11
        store.get_archive.return_value = {"id": 11}
        store.search_archive.return_value = [{"id": 11}]
        MockArchive.return_value = store
        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test",
                    data_url="mysql://root:root@localhost:3306/data")
        assert e.archive("c", kind="log", tags=["t"]) == 11
        assert e.get_archive(11) == {"id": 11}
        assert e.search_archive("q")[0]["id"] == 11
        store.archive.assert_called_once()


def test_close_also_closes_archive():
    with patch("evolver.MySQLStorage") as MockStorage, \
         patch("evolver.EmbeddingClient") as MockEmb, \
         patch("evolver.archive_store.ArchiveStore") as MockArchive:
        MockStorage.return_value = MagicMock()
        MockEmb.return_value = MagicMock()
        store = MagicMock()
        MockArchive.return_value = store
        e = Evolver(mysql_url="mysql://root:root@localhost:3306/test",
                    data_url="mysql://root:root@localhost:3306/data")
        e.close()
        store.close.assert_called_once()
