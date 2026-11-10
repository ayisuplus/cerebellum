import pytest
import threading
from unittest.mock import MagicMock, patch
from evolver.storage import MySQLStorage
from evolver.storage_sqlite import SQLiteStorage
from evolver.models import Memory, GraphNode, GraphEdge
from evolver.exceptions import EvolverConnectionError


@pytest.fixture
def mock_conn():
    """Mock MySQL connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_storage_connect():
    with patch("evolver.storage.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = MagicMock()
        storage = MySQLStorage("mysql://root:root@localhost:3306/test", pool_size=1)
        storage.connect()
        mock_pymysql.connect.assert_called_once()


def test_storage_connect_failure():
    with patch("evolver.storage.pymysql") as mock_pymysql:
        mock_pymysql.connect.side_effect = Exception("Connection refused")
        storage = MySQLStorage("mysql://root:root@localhost:3306/test", pool_size=1)
        with pytest.raises(EvolverConnectionError):
            storage.connect()


def test_insert_memory(mock_conn):
    conn, cursor = mock_conn
    cursor.lastrowid = 42
    with patch("evolver.storage.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        storage = MySQLStorage("mysql://root:root@localhost:3306/test")
        storage.connect()
        mem = Memory(content="test", category="success", embedding=b"\x00" * 12)
        mid = storage.insert_memory(mem)
        assert mid == 42
        cursor.execute.assert_called()


def test_get_memories_by_ids(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchall.return_value = [
        {"id": 1, "content": "hello", "category": "success", "tags": "[]",
         "embedding": None, "source": None, "importance": 0.5, "access_count": 0}
    ]
    with patch("evolver.storage.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        storage = MySQLStorage("mysql://root:root@localhost:3306/test")
        storage.connect()
        memories = storage.get_memories_by_ids([1])
        assert len(memories) == 1
        assert memories[0].content == "hello"


def test_mysql_commit_returns_transaction_connection_to_pool(mock_conn):
    conn, _cursor = mock_conn
    with patch("evolver.storage.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        storage = MySQLStorage(
            "mysql://root:root@localhost:3306/test", pool_size=1
        )
        storage.connect()

        storage.begin()
        assert storage._pool.qsize() == 0
        storage.commit()

        assert storage._pool.qsize() == 1


def test_sqlite_transaction_blocks_other_threads_until_commit():
    storage = SQLiteStorage(":memory:")
    first_started = threading.Event()
    release_first = threading.Event()
    second_done = threading.Event()
    errors = []

    def first_writer():
        try:
            storage.begin()
            storage.insert_memory(Memory(content="first", category="insight"))
            first_started.set()
            release_first.wait(timeout=2)
            storage.commit()
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    def second_writer():
        try:
            first_started.wait(timeout=2)
            storage.insert_memory(Memory(content="second", category="insight"))
            second_done.set()
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    first = threading.Thread(target=first_writer)
    second = threading.Thread(target=second_writer)
    first.start()
    second.start()

    assert first_started.wait(timeout=2)
    assert not second_done.wait(timeout=0.05)
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert errors == []
    assert second_done.is_set()
    assert storage.stats()["memories"] == 2


def test_insert_node(mock_conn):
    conn, cursor = mock_conn
    cursor.lastrowid = 1
    cursor.fetchone.return_value = None  # no existing node
    with patch("evolver.storage.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        storage = MySQLStorage("mysql://root:root@localhost:3306/test")
        storage.connect()
        node = GraphNode(label="git", node_type="tool")
        nid = storage.upsert_node(node)
        assert nid == 1


def test_insert_edge(mock_conn):
    conn, cursor = mock_conn
    cursor.lastrowid = 1
    cursor.fetchone.return_value = None  # no existing edge
    with patch("evolver.storage.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        storage = MySQLStorage("mysql://root:root@localhost:3306/test")
        storage.connect()
        edge = GraphEdge(source_id=1, target_id=2, relation="uses")
        eid = storage.upsert_edge(edge)
        assert eid == 1


# --- SQLite direct integration tests (no mocking) ---

def test_sqlite_decay_edges():
    from evolver.storage_sqlite import SQLiteStorage
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()

    # Insert two edges with known weights
    n1 = storage.upsert_node(GraphNode(label="a", node_type="concept"))
    n2 = storage.upsert_node(GraphNode(label="b", node_type="concept"))
    n3 = storage.upsert_node(GraphNode(label="c", node_type="concept"))
    storage.upsert_edge(GraphEdge(source_id=n1, target_id=n2, relation="related_to", weight=1.0))
    storage.upsert_edge(GraphEdge(source_id=n1, target_id=n3, relation="related_to", weight=0.05))

    storage.decay_edges(factor=0.5, min_weight=0.1)

    count = storage.count_edges()
    # Edge with weight 0.05 decayed to 0.025, below 0.1 threshold → deleted
    assert count == 1, "Only one edge should remain after decay"

    storage.close()

def test_sqlite_no_edges_decay():
    """decay_edges with no edges should not raise."""
    from evolver.storage_sqlite import SQLiteStorage
    storage = SQLiteStorage(":memory:")
    storage.decay_edges()  # no edges — should not raise
    storage.close()


# --- Links table tests ---

def test_insert_link():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    link_id = storage.insert_link(
        source_type="memory", source_id=1,
        target_type="memory", target_id=2,
        link_type="auto_similar", weight=0.85,
    )
    assert link_id > 0


def test_insert_link_bidirectional():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.85)
    storage.insert_link("memory", 2, "memory", 1, "auto_similar", 0.85)
    rows = storage._fetchall("SELECT * FROM links")
    assert len(rows) == 2


def test_insert_link_dedup():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.85)
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.90)
    rows = storage._fetchall("SELECT * FROM links WHERE source_id=1 AND target_id=2")
    assert len(rows) == 1
    assert rows[0]["weight"] == 0.90


def test_get_backlinks():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 5, "auto_similar", 0.8)
    storage.insert_link("memory", 2, "memory", 5, "auto_similar", 0.7)
    storage.insert_link("memory", 3, "memory", 5, "auto_entity", 0.9)
    backlinks = storage.get_backlinks("memory", 5)
    assert len(backlinks) == 3


def test_get_outgoing():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.8)
    storage.insert_link("memory", 1, "graph_node", 10, "auto_entity", 0.9)
    outgoing = storage.get_outgoing("memory", 1)
    assert len(outgoing) == 2


def test_decay_links():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.05)
    storage.decay_links(factor=0.5, min_weight=0.03)
    rows = storage._fetchall("SELECT * FROM links")
    assert len(rows) == 0


# --- Skill evaluations table tests ---

def test_insert_skill_evaluation():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    skill_id, _ = storage.upsert_skill("test-skill", "desc", "/path", "content")
    eval_id = storage.insert_skill_evaluation(
        skill_id=skill_id, version=1, total_score=72.5,
        dim_scores={"frontmatter": 8}, eval_mode="auto",
        round=1, status="pass",
    )
    assert eval_id > 0


def test_get_skill_evaluations():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    skill_id, _ = storage.upsert_skill("test-skill", "desc", "/path", "content")
    storage.insert_skill_evaluation(skill_id, 1, 70.0, {"f": 7}, "auto", 1, "pass")
    storage.insert_skill_evaluation(skill_id, 1, 75.0, {"f": 8}, "auto", 2, "improved")
    evals = storage.get_skill_evaluations(skill_id)
    assert len(evals) == 2
    assert evals[1]["total_score"] == 75.0


# --- Lifecycle CRUD tests ---

@pytest.fixture
def sqlite_storage():
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    storage = SQLiteStorage(path)
    yield storage
    storage.close()
    os.unlink(path)


def test_insert_memory_with_lifecycle(sqlite_storage):
    """Verify lifecycle is persisted on insert."""
    storage = sqlite_storage
    mem = Memory(content="test with lifecycle", category="test", lifecycle="growing")
    mid = storage.insert_memory(mem)
    # Read back directly
    row = storage._fetchone(
        "SELECT id, content, category, tags, embedding, source, importance, access_count, content_hash, lifecycle, created_at FROM memories WHERE id = ?",
        (mid,)
    )
    m = storage._row_to_memory(row)
    assert m.lifecycle == "growing"


def test_get_memories_in_range_includes_lifecycle(sqlite_storage):
    """Verify lifecycle is returned in range queries."""
    storage = sqlite_storage
    mem = Memory(content="range test lifecycle", category="test", lifecycle="evergreen")
    storage.insert_memory(mem)
    results = storage.get_memories_in_range(days=1)
    assert any(m.lifecycle == "evergreen" for m in results)


def test_find_memory_by_hash(sqlite_storage):
    """Single-hash lookup returns the matching memory."""
    storage = sqlite_storage
    mem = Memory(content="hash lookup", category="test", content_hash="deadbeef")
    storage.insert_memory(mem)
    found = storage.find_memory_by_hash("deadbeef")
    assert found is not None
    assert found.content == "hash lookup"
    assert storage.find_memory_by_hash("nonexistent") is None


def test_find_memories_by_hashes_batch(sqlite_storage):
    """Batch lookup returns dict keyed by hash."""
    storage = sqlite_storage
    storage.insert_memory(Memory(content="a", category="test", content_hash="h1"))
    storage.insert_memory(Memory(content="b", category="test", content_hash="h2"))
    result = storage.find_memories_by_hashes(["h1", "h2", "missing"])
    assert set(result.keys()) == {"h1", "h2"}
    assert result["h1"].content == "a"


def test_get_all_content_hashes(sqlite_storage):
    """Cheap hash-only fetch skips NULL hashes."""
    storage = sqlite_storage
    storage.insert_memory(Memory(content="x", category="test", content_hash="hh1"))
    storage.insert_memory(Memory(content="y", category="test"))  # no hash
    storage.insert_memory(Memory(content="z", category="test", content_hash="hh2"))
    hashes = storage.get_all_content_hashes()
    assert hashes == {"hh1", "hh2"}


def test_delete_older_than_skips_distilled(sqlite_storage):
    """delete_memories_older_than does not remove distilled memories."""
    storage = sqlite_storage
    import datetime
    old = (datetime.datetime.now() - datetime.timedelta(days=100)).isoformat()
    storage.insert_memory(Memory(content="regular old", category="test",
                                  created_at=old, lifecycle="seed"))
    storage.insert_memory(Memory(content="distilled old", category="test",
                                  created_at=old, lifecycle="distilled"))

    deleted = storage.delete_memories_older_than(30)

    remaining = storage.get_all_memories_columns(["id", "content", "lifecycle"])
    contents = [m.content for m in remaining]
    assert "regular old" not in contents
    assert "distilled old" in contents


def test_delete_low_importance_skips_distilled(sqlite_storage):
    """delete_memories_low_importance does not remove distilled memories."""
    storage = sqlite_storage
    storage.insert_memory(Memory(content="low imp", category="test",
                                  importance=0.1, lifecycle="seed"))
    storage.insert_memory(Memory(content="low imp distilled", category="test",
                                  importance=0.1, lifecycle="distilled"))

    deleted = storage.delete_memories_low_importance(0.3)

    remaining = storage.get_all_memories_columns(["id", "content", "lifecycle"])
    contents = [m.content for m in remaining]
    assert "low imp" not in contents
    assert "low imp distilled" in contents
