"""Regression tests for temporal sync fixes and hash-embedding tiling fix."""
import math
from datetime import datetime, timezone, timedelta

import pytest

from evolver.embedding import EmbeddingClient
from evolver.models import Memory
from evolver.storage_sqlite import SQLiteStorage
from evolver.temporal_memory import TemporalMemory


class _FakeDatetime(datetime):
    """Controllable clock patched over evolver.temporal_memory.datetime."""
    _now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._now.replace(tzinfo=None)
        return cls._now.astimezone(tz)


def _set_clock(monkeypatch, moment):
    _FakeDatetime._now = moment
    monkeypatch.setattr("evolver.temporal_memory.datetime", _FakeDatetime)


class _FakeStorage:
    """Minimal storage double returning a configurable memory list."""

    def __init__(self, memories):
        self._memories = memories

    def get_all_memories_columns(self, columns=None):
        return list(self._memories)


def _mem(mid, created, category="success", importance=0.8, lifecycle="seed"):
    return Memory(id=mid, content=f"m{mid}", category=category,
                  importance=importance, created_at=created.isoformat(),
                  lifecycle=lifecycle)


class TestSyncPreservesDecay:
    def test_resync_preserves_decay_progress(self, monkeypatch):
        """Old behavior: sync_from_memories called register() without
        last_accessed, resetting the decay clock to now on every re-sync
        (Evolver syncs on each init), so effective importance bounced
        back to base_importance after a restart. Across two syncs with
        time advanced, effective importance must strictly decrease."""
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        created = t0 - timedelta(days=10)
        storage = _FakeStorage([_mem(1, created)])
        tm = TemporalMemory()

        _set_clock(monkeypatch, t0)
        tm.sync_from_memories(storage)
        eff1 = tm.get(1).effective_importance()

        _set_clock(monkeypatch, t0 + timedelta(days=5))
        tm.sync_from_memories(storage)
        eff2 = tm.get(1).effective_importance()

        assert tm.get(1).last_accessed == created
        assert eff1 < 0.8
        assert eff2 < eff1

    def test_sync_removes_entries_deleted_from_storage(self, monkeypatch):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _set_clock(monkeypatch, t0)
        created = t0 - timedelta(days=1)
        storage = _FakeStorage([_mem(1, created), _mem(2, created)])
        tm = TemporalMemory()
        tm.sync_from_memories(storage)
        assert tm.get(1) is not None
        assert tm.get(2) is not None

        # Memory 2 is deleted from storage; re-sync must prune it.
        storage._memories = [_mem(1, created)]
        tm.sync_from_memories(storage)
        assert tm.get(1) is not None
        assert tm.get(2) is None

    def test_sync_keeps_non_episodic_ids_untracked_but_not_pruned(self, monkeypatch):
        """Non success/failure memories are never tracked; their ids still
        count as existing so a hypothetical tracked entry is not pruned
        merely because its category left the episodic set is out of scope —
        but a tracked id still present in storage must survive."""
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _set_clock(monkeypatch, t0)
        created = t0 - timedelta(days=1)
        tm = TemporalMemory()
        tm.register(memory_id=7, created_at=created, last_accessed=created)
        storage = _FakeStorage([_mem(7, created, category="insight")])
        tm.sync_from_memories(storage)
        assert tm.get(7) is not None  # id still exists in storage

    def test_remove_expired_prunes(self, monkeypatch):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _set_clock(monkeypatch, t0)
        tm = TemporalMemory()
        old = t0 - timedelta(days=200)
        tm.register(memory_id=1, created_at=old, last_accessed=old,
                    decay_rate=0.05, base_importance=1.0)
        tm.register(memory_id=2, created_at=t0, last_accessed=t0,
                    decay_rate=0.001, base_importance=1.0)
        removed = tm.remove_expired()
        assert removed == 1
        assert tm.get(1) is None
        assert tm.get(2) is not None


class TestApplyDecayBatching:
    def test_batches_into_single_executemany_when_supported(self, monkeypatch):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _set_clock(monkeypatch, t0)
        old = t0 - timedelta(days=100)

        calls = []

        class BatchStorage:
            def _placeholder(self):
                return "?"

            def _executemany(self, sql, seq):
                calls.append((sql, list(seq)))

        tm = TemporalMemory()
        tm.register(memory_id=1, created_at=old, last_accessed=old,
                    decay_rate=0.02, base_importance=0.9)
        tm.register(memory_id=2, created_at=old, last_accessed=old,
                    decay_rate=0.02, base_importance=0.7)
        tm.apply_decay(BatchStorage())

        assert len(calls) == 1
        sql, rows = calls[0]
        assert "UPDATE memories SET importance" in sql
        assert sorted(mid for _, mid in rows) == [1, 2]
        assert all(0 < imp < 1 for imp, _ in rows)


class TestHashEmbedding:
    def test_deterministic(self):
        client = EmbeddingClient(fallback=True, dim=384)
        v1 = client.embed_single("determinism check")
        v2 = client.embed_single("determinism check")
        assert v1 == v2

    def test_dimension_and_unit_norm(self):
        client = EmbeddingClient(fallback=True, dim=384)
        v = client.embed_single("shape check")
        assert len(v) == 384
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6
        assert all(math.isfinite(x) for x in v)

    def test_different_inputs_differ_in_more_than_16_positions(self):
        client = EmbeddingClient(fallback=True, dim=384)
        v1 = client.embed_single("alpha input text")
        v2 = client.embed_single("beta input text")
        differing = sum(1 for a, b in zip(v1, v2) if a != b)
        assert differing > 16

    def test_no_period_16_tiling(self):
        """Old behavior: start=(i*4)%64 over a single 64-byte digest made
        vec[i] == vec[i-16] for all i >= 16 (a 16-float block repeated).
        Per-block re-hashing must yield more than 16 distinct values."""
        client = EmbeddingClient(fallback=True, dim=384)
        v = client.embed_single("tiling regression probe")
        assert len(set(v)) > 16
        repeats = sum(1 for i in range(16, len(v)) if v[i] == v[i - 16])
        assert repeats == 0


class TestDecayClockPersistence:
    """last_accessed_at is the decay clock; only decay checkpoints write it."""

    def test_decay_checkpoint_survives_restart(self, tmp_path):
        storage = SQLiteStorage(str(tmp_path / "decay.db"))
        mid = storage.insert_memory(
            Memory(content="aged", category="success", importance=1.0)
        )
        storage._execute(
            "UPDATE memories SET last_accessed_at = datetime('now', '-10 days') "
            "WHERE id = ?",
            (mid,),
        )
        tm = TemporalMemory()
        tm.sync_from_memories(storage)
        entry = tm.get(mid)
        age_days = (
            datetime.now(timezone.utc) - entry.last_accessed
        ).total_seconds() / 86400
        assert age_days > 9.9

        tm.apply_decay(storage)
        row = storage._fetchone(
            "SELECT importance, last_accessed_at FROM memories WHERE id = ?", (mid,)
        )
        decayed = row["importance"]
        # seed lifecycle -> rate 0.02; importance checkpointed to decayed value.
        assert decayed == pytest.approx(math.exp(-0.02 * age_days), abs=0.01)
        assert row["last_accessed_at"] is not None

        # Restart: re-sync loads the decayed value as base with the checkpoint
        # as clock — accumulated decay progress is not erased.
        tm2 = TemporalMemory()
        tm2.sync_from_memories(storage)
        entry2 = tm2.get(mid)
        assert entry2.base_importance == pytest.approx(decayed)
        age2 = (
            datetime.now(timezone.utc) - entry2.last_accessed
        ).total_seconds() / 86400
        assert age2 < 0.5
        storage.close()

    def test_content_and_tag_writes_do_not_reset_decay_clock(self, tmp_path):
        storage = SQLiteStorage(str(tmp_path / "decay2.db"))
        mid = storage.insert_memory(
            Memory(content="aged", category="success", importance=1.0)
        )
        storage._execute(
            "UPDATE memories SET last_accessed_at = datetime('now', '-10 days') "
            "WHERE id = ?",
            (mid,),
        )
        # Old behavior: these bumped updated_at, and sync read updated_at as
        # last_accessed — every unrelated write erased accumulated decay time.
        storage.update_memory_content(mid, "rewritten")
        storage.update_memory_tags(mid, ["x"])

        tm = TemporalMemory()
        tm.sync_from_memories(storage)
        age_days = (
            datetime.now(timezone.utc) - tm.get(mid).last_accessed
        ).total_seconds() / 86400
        assert age_days > 9.9, "unrelated writes must not erase decay time"
        storage.close()

    def test_existing_db_backfills_last_accessed(self, tmp_path):
        import sqlite3

        db = str(tmp_path / "old.db")
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT,
                tags TEXT,
                embedding BLOB,
                source TEXT,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                content_hash TEXT,
                lifecycle TEXT DEFAULT 'seed',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version INTEGER NOT NULL);
            INSERT INTO schema_version (id, version) VALUES (1, 2);
            INSERT INTO memories (content, category, importance, created_at, updated_at)
            VALUES ('old row', 'success', 0.9, '2020-01-01 00:00:00', '2021-01-01 00:00:00');
        """)
        conn.close()

        storage = SQLiteStorage(db)  # must add + backfill the column
        row = storage._fetchone(
            "SELECT last_accessed_at FROM memories WHERE content = 'old row'", []
        )
        assert row["last_accessed_at"] == "2021-01-01 00:00:00"
        storage.close()
