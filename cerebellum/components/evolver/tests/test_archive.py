import json
import os
import pytest
from unittest.mock import MagicMock, patch
from evolver.archive_store import ArchiveStore
from evolver.exceptions import EvolverError


@pytest.fixture
def mock_conn():
    """Mock MySQL connection + cursor (context-manager style)."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_construct_no_io():
    """Constructing ArchiveStore must not open any connection."""
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        store = ArchiveStore("mysql://root:root@localhost:3306/data")
        assert store._pool is None
        mock_pymysql.connect.assert_not_called()


def test_lazy_connect_builds_pool_and_schema(mock_conn):
    conn, cursor = mock_conn
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        store._ensure_connected()
        assert store._pool is not None
        assert store._schema_ready is True
        executed = " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)
        assert "CREATE TABLE IF NOT EXISTS archive" in executed
        assert "WITH PARSER ngram" in executed


def test_ensure_connected_idempotent(mock_conn):
    conn, cursor = mock_conn
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        store._ensure_connected()
        calls_after_first = mock_pymysql.connect.call_count
        store._ensure_connected()
        assert mock_pymysql.connect.call_count == calls_after_first


# --- Task 3: archive() ---


def test_archive_returns_id(mock_conn):
    conn, cursor = mock_conn
    cursor.lastrowid = 7
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        new_id = store.archive("hello log", kind="log",
                               tags=["a", "b"], source="test",
                               ref=None, meta={"mime": "text/plain"})
        assert new_id == 7


def test_archive_serializes_tags_and_meta(mock_conn):
    conn, cursor = mock_conn
    cursor.lastrowid = 1
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        store.archive("c", kind="record", tags=["x"], meta={"k": "v"})
        insert_call = [c for c in cursor.execute.call_args_list
                       if "INSERT INTO archive" in str(c.args[0])][0]
        params = insert_call.args[1]
        assert json.loads(params[3]) == ["x"]
        assert json.loads(params[5]) == {"k": "v"}


def test_archive_null_tags_meta(mock_conn):
    conn, cursor = mock_conn
    cursor.lastrowid = 2
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        store.archive("only content", kind="record")
        insert_call = [c for c in cursor.execute.call_args_list
                       if "INSERT INTO archive" in str(c.args[0])][0]
        params = insert_call.args[1]
        assert params[3] is None
        assert params[5] is None


# --- Task 4: get_archive() ---


def test_get_archive_found(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchone.return_value = {
        "id": 3, "content": "body", "kind": "log", "ref": None,
        "tags": '["t1"]', "source": "s", "meta": '{"m": 1}',
        "created_at": "2026-05-29 00:00:00",
    }
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        row = store.get_archive(3)
        assert row["id"] == 3
        assert row["tags"] == ["t1"]
        assert row["meta"] == {"m": 1}


def test_get_archive_not_found(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchone.return_value = None
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        assert store.get_archive(999) is None


# --- Task 5: search_archive() ---


def test_search_archive_fulltext(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchall.return_value = [{
        "id": 1, "content": "git rebase notes", "kind": "log", "ref": None,
        "tags": None, "source": None, "meta": None,
        "created_at": "2026-05-29 00:00:00",
    }]
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        rows = store.search_archive("git", limit=5)
        assert len(rows) == 1
        assert rows[0]["content"] == "git rebase notes"
        first_sql = str(cursor.execute.call_args_list[-1].args[0])
        assert "MATCH" in first_sql and "AGAINST" in first_sql


def test_search_archive_falls_back_to_like(mock_conn):
    conn, cursor = mock_conn
    calls = {"n": 0}

    def execute_side_effect(sql, params=None):
        if "MATCH" in str(sql):
            calls["n"] += 1
            raise Exception("fulltext not supported")
        return None

    cursor.execute.side_effect = execute_side_effect
    cursor.fetchall.return_value = [{
        "id": 2, "content": "like result", "kind": "log", "ref": None,
        "tags": None, "source": None, "meta": None,
        "created_at": "2026-05-29 00:00:00",
    }]
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        rows = store.search_archive("like", limit=5)
        assert calls["n"] == 1
        assert rows[0]["content"] == "like result"
        all_sql = " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)
        assert "LIKE" in all_sql


# --- Task 6: close() ---


def test_close_when_never_connected():
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        store = ArchiveStore("mysql://root:root@localhost:3306/data")
        store.close()
        mock_pymysql.connect.assert_not_called()


def test_close_after_connect(mock_conn):
    conn, cursor = mock_conn
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        store._ensure_connected()
        store.close()
        conn.close.assert_called()
        assert store._pool is None


# --- Optional real MySQL integration test (skipped by default) ---


@pytest.mark.skipif(
    not os.environ.get("EVOLVER_TEST_MYSQL"),
    reason="set EVOLVER_TEST_MYSQL=mysql://user:pass@host:port/db to run",
)
def test_real_mysql_roundtrip():
    url = os.environ["EVOLVER_TEST_MYSQL"]
    store = ArchiveStore(url, pool_size=1)
    try:
        new_id = store.archive(
            "integration test Chinese fulltext payload",
            kind="record", tags=["zh"], source="it",
            meta={"mime": "text/plain"},
        )
        assert new_id > 0
        got = store.get_archive(new_id)
        assert got["content"].startswith("integration test")
        assert got["tags"] == ["zh"]
        results = store.search_archive("fulltext", limit=10)
        assert any(r["id"] == new_id for r in results)
        # Chinese search exercises ngram parser (or LIKE fallback)
        zh = store.search_archive("Chinese", limit=10)
        assert any(r["id"] == new_id for r in zh)
    finally:
        store.close()


# --- Task 5: error scenarios (dead-data layer MySQL-only) ---


def test_unsupported_scheme_raises_value_error():
    """Non-MySQL schemes must raise a clear ValueError when building ArchiveStore."""
    with pytest.raises(ValueError, match="Invalid MySQL URL scheme"):
        ArchiveStore("sqlite:///other.db")


def test_mysql_plus_pymysql_scheme_accepted():
    """mysql+pymysql:// scheme must be accepted (factory does not connect)."""
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        store = ArchiveStore("mysql+pymysql://u:p@host:3306/db", pool_size=1)
        assert store._pool is None
        assert store._url.startswith("mysql+pymysql://")
        mock_pymysql.connect.assert_not_called()


def test_mysql_plus_aiomysql_scheme_accepted():
    """mysql+aiomysql:// scheme must be accepted."""
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        store = ArchiveStore("mysql+aiomysql://u:p@host:3306/db", pool_size=1)
        assert store._pool is None
        mock_pymysql.connect.assert_not_called()


def test_archive_not_configured_raises_clear_error():
    """When archive layer is not configured, calls must raise a clear error."""
    from evolver import _archive_not_configured_msg, Evolver

    class _FakeEvolver:
        _archive = None
        archive = Evolver.archive
        search_archive = Evolver.search_archive
        get_archive = Evolver.get_archive

    fake = _FakeEvolver()
    with pytest.raises(EvolverError, match="EVOLVER_DATA_URL is not configured"):
        fake.archive("x", kind="log")
    with pytest.raises(EvolverError, match="EVOLVER_DATA_URL is not configured"):
        fake.search_archive("q")
    with pytest.raises(EvolverError, match="EVOLVER_DATA_URL is not configured"):
        fake.get_archive(1)


def test_error_message_includes_both_shells():
    """The 'not configured' message must include both Bash and PowerShell examples."""
    from evolver import _archive_not_configured_msg
    msg = _archive_not_configured_msg()
    assert "Bash" in msg and "export EVOLVER_DATA_URL" in msg
    assert "PowerShell" in msg and "$env:EVOLVER_DATA_URL" in msg
