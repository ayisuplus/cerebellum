"""G3: embedder identity tags, sqlite hardening (busy_timeout + lock retry)."""
import sqlite3
import threading

import pytest
from unittest.mock import MagicMock

from evolver.embedding import EmbeddingClient
from evolver.models import Memory
from evolver.storage_sqlite import SQLiteStorage
from evolver.utils import embedder_tags_compatible


def test_fallback_identity_is_versioned_and_distinct():
    client = EmbeddingClient(fallback=True)
    assert client.identity == "hash-fallback:v2"

    # A model-backed client identifies as backend:model (no model load needed).
    model_client = object.__new__(EmbeddingClient)
    model_client._fallback = False
    model_client._backend = "fastembed"
    model_client._provider_name = "fastembed"
    model_client.model_name = "BAAI/bge-small-en-v1.5"
    assert model_client.identity == "fastembed:BAAI/bge-small-en-v1.5"
    assert model_client.identity != client.identity


def test_embedder_tags_compatible_truth_table():
    # Untagged legacy rows compare with everything.
    assert embedder_tags_compatible(None, None)
    assert embedder_tags_compatible(None, "fastembed:m")
    assert embedder_tags_compatible("hash-fallback:v2", None)
    # Equal tags compare; different non-null tags never do.
    assert embedder_tags_compatible("fastembed:m", "fastembed:m")
    assert not embedder_tags_compatible("hash-fallback:v2", "fastembed:m")


def test_sqlite_embedder_column_roundtrip_and_busy_timeout(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "tags.db"))
    try:
        columns = {row["name"] for row in storage._fetchall("PRAGMA table_info(memories)")}
        assert "embedder" in columns
        assert storage._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000

        mid = storage.insert_memory(Memory(
            content="tagged", category="success", embedding=b"\x00" * 8,
            embedder="fastembed:test-model",
        ))
        row = storage._fetchone("SELECT embedder FROM memories WHERE id = ?", (mid,))
        assert row["embedder"] == "fastembed:test-model"
        loaded = [m for m in storage.get_all_memories_with_embeddings() if m.id == mid][0]
        assert loaded.embedder == "fastembed:test-model"

        storage.update_memory_embedding(mid, b"\x01" * 8, embedder="hash-fallback:v2")
        row = storage._fetchone("SELECT embedder FROM memories WHERE id = ?", (mid,))
        assert row["embedder"] == "hash-fallback:v2"
        # Without a tag argument the stored tag is preserved.
        storage.update_memory_embedding(mid, b"\x02" * 8)
        row = storage._fetchone("SELECT embedder FROM memories WHERE id = ?", (mid,))
        assert row["embedder"] == "hash-fallback:v2"
    finally:
        storage.close()


def test_sqlite_existing_db_gains_embedder_column(tmp_path):
    # Simulate a pre-tag database: create one without the column, then open.
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE memories (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "content TEXT NOT NULL, category TEXT, tags TEXT, embedding BLOB, "
        "source TEXT, importance REAL DEFAULT 0.5, access_count INTEGER DEFAULT 0, "
        "content_hash TEXT, lifecycle TEXT DEFAULT 'seed', "
        "created_at TEXT DEFAULT (datetime('now')), "
        "updated_at TEXT DEFAULT (datetime('now')), last_accessed_at TEXT)"
    )
    conn.commit()
    conn.close()

    storage = SQLiteStorage(str(db))
    try:
        columns = {row["name"] for row in storage._fetchall("PRAGMA table_info(memories)")}
        assert "embedder" in columns
    finally:
        storage.close()


def test_lock_retry_recovers_from_transient_busy(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "retry.db"))
    try:
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        assert storage._run_with_lock_retry(flaky) == "ok"
        assert attempts["n"] == 3

        # Non-lock operational errors are not retried.
        def broken():
            attempts["n"] = 0
            raise sqlite3.OperationalError("no such table")

        with pytest.raises(sqlite3.OperationalError):
            storage._run_with_lock_retry(broken)
        assert attempts["n"] == 0

        # Persistent lock contention exhausts the bounded attempts.
        def always_locked():
            attempts["n"] += 1
            raise sqlite3.OperationalError("database is locked")

        attempts["n"] = 0
        with pytest.raises(sqlite3.OperationalError):
            storage._run_with_lock_retry(always_locked)
        assert attempts["n"] == SQLiteStorage._LOCK_RETRY_ATTEMPTS
    finally:
        storage.close()


def test_lock_retry_sleeps_are_bounded(tmp_path, monkeypatch):
    storage = SQLiteStorage(str(tmp_path / "bounded.db"))
    try:
        sleeps = []
        monkeypatch.setattr("evolver.storage_sqlite.time.sleep", sleeps.append)
        attempts = {"n": 0}

        def always_locked():
            attempts["n"] += 1
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError):
            storage._run_with_lock_retry(always_locked)
        # Exponential backoff between the attempts (attempts - 1 sleeps).
        assert len(sleeps) == SQLiteStorage._LOCK_RETRY_ATTEMPTS - 1
        assert sleeps == sorted(sleeps)
    finally:
        storage.close()
