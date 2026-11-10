import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from evolver.models import Memory
from evolver.temporal_memory import TemporalMemory, TemporalEntry


class TestTemporalEntry:
    def test_create_entry(self):
        entry = TemporalEntry(
            memory_id=1,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.01,
        )
        assert entry.memory_id == 1
        assert entry.decay_rate == 0.01

    def test_is_expired_new_entry(self):
        entry = TemporalEntry(
            memory_id=1,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.01,
        )
        assert entry.is_expired() is False

    def test_is_expired_old_entry_high_decay(self):
        old = datetime.now(timezone.utc) - timedelta(days=200)
        entry = TemporalEntry(
            memory_id=1,
            created_at=old,
            last_accessed=old,
            decay_rate=0.05,
        )
        assert entry.is_expired() is True

    def test_is_expired_old_entry_low_decay(self):
        old = datetime.now(timezone.utc) - timedelta(days=30)
        entry = TemporalEntry(
            memory_id=1,
            created_at=old,
            last_accessed=old,
            decay_rate=0.001,
        )
        assert entry.is_expired() is False

    def test_update_access_refreshes_timestamp(self):
        old_access = datetime.now(timezone.utc) - timedelta(days=10)
        entry = TemporalEntry(
            memory_id=1,
            created_at=datetime.now(timezone.utc),
            last_accessed=old_access,
            decay_rate=0.01,
        )
        entry.update_access()
        assert entry.last_accessed > old_access

    def test_effective_importance_decays(self):
        old = datetime.now(timezone.utc) - timedelta(days=100)
        entry = TemporalEntry(
            memory_id=1,
            created_at=old,
            last_accessed=old,
            decay_rate=0.01,
            base_importance=0.8,
        )
        eff = entry.effective_importance()
        assert eff < 0.8

    def test_effective_importance_recent_is_full(self):
        entry = TemporalEntry(
            memory_id=1,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.01,
            base_importance=0.8,
        )
        eff = entry.effective_importance()
        assert abs(eff - 0.8) < 0.01

    def test_default_decay_rate(self):
        entry = TemporalEntry(memory_id=1)
        assert entry.decay_rate == 0.01


class TestTemporalMemory:
    def test_register_and_get(self):
        tm = TemporalMemory()
        now = datetime.now(timezone.utc)
        tm.register(memory_id=1, decay_rate=0.01)
        entry = tm.get(1)
        assert entry is not None
        assert entry.memory_id == 1

    def test_get_nonexistent(self):
        tm = TemporalMemory()
        assert tm.get(999) is None

    def test_touch_updates_access(self):
        tm = TemporalMemory()
        tm.register(memory_id=1)
        import time
        time.sleep(0.01)
        tm.touch(1)
        entry = tm.get(1)
        assert entry.last_accessed > entry.created_at

    def test_remove_expired_removes_old(self):
        tm = TemporalMemory()
        old = datetime.now(timezone.utc) - timedelta(days=200)
        tm.register(memory_id=1, created_at=old, last_accessed=old, decay_rate=0.05)
        tm.register(memory_id=2, created_at=datetime.now(timezone.utc), decay_rate=0.001)
        removed = tm.remove_expired()
        assert removed == 1
        assert tm.get(1) is None
        assert tm.get(2) is not None

    def test_remove_expired_none_when_all_fresh(self):
        tm = TemporalMemory()
        tm.register(memory_id=1)
        tm.register(memory_id=2)
        removed = tm.remove_expired()
        assert removed == 0

    def test_apply_decay_to_storage(self):
        tm = TemporalMemory()
        mock_storage = MagicMock()
        old = datetime.now(timezone.utc) - timedelta(days=100)
        tm.register(memory_id=1, created_at=old, last_accessed=old,
                     decay_rate=0.02, base_importance=0.9)
        tm.apply_decay(mock_storage)
        mock_storage.update_memory_importance.assert_called_once()
        args = mock_storage.update_memory_importance.call_args[0]
        assert args[0] == 1
        assert args[1] < 0.9

    def test_get_stats(self):
        tm = TemporalMemory()
        old = datetime.now(timezone.utc) - timedelta(days=200)
        tm.register(memory_id=1, created_at=old, last_accessed=old, decay_rate=0.05)
        tm.register(memory_id=2, decay_rate=0.001)
        stats = tm.get_stats()
        assert stats["total"] == 2
        assert stats["expired"] >= 1

    def test_sync_from_memories(self):
        tm = TemporalMemory()
        mock_storage = MagicMock()
        now = datetime.now(timezone.utc)
        memories = [
            Memory(id=1, content="test", category="success", importance=0.8,
                   created_at=now.isoformat(), lifecycle="seed"),
            Memory(id=2, content="test2", category="insight", importance=0.5,
                   created_at=now.isoformat(), lifecycle="growing"),
        ]
        mock_storage.get_all_memories_columns.return_value = memories
        tm.sync_from_memories(mock_storage)
        assert tm.get(1) is not None
        assert tm.get(2) is None
        assert tm.get(1).base_importance == 0.8

    def test_decay_rate_by_lifecycle(self):
        tm = TemporalMemory()
        now = datetime.now(timezone.utc)
        tm.register(memory_id=1, decay_rate=None, lifecycle="seed")
        tm.register(memory_id=2, decay_rate=None, lifecycle="evergreen")
        e1 = tm.get(1)
        e2 = tm.get(2)
        assert e1.decay_rate > e2.decay_rate
