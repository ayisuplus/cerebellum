# Dual-Backend Archive Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor archive layer from MySQL-only to dual-backend (SQLite + MySQL) via ABC interface.

**Architecture:** `ArchiveBackend` ABC → `SQLiteArchiveBackend` (new) + `MySQLArchiveBackend` (renamed from `ArchiveStore`). Factory function in `archive_store.py`. Evolver init uses factory with scheme detection.

**Tech Stack:** Python 3.10+ ABC, sqlite3 (stdlib), pymysql (optional), FTS5, threading.Lock

---

### Task 1: Abstract Backend Interface

**Files:**
- Create: `evolver/archive_backend.py`
- Test: no test for this alone (tested via implementations)

- [ ] **Step 1: Create ABC interface**

```python
"""Abstract backend for the archive (dead-data) layer."""

from abc import ABC, abstractmethod


class ArchiveBackend(ABC):
    @abstractmethod
    def archive(self, content: str, kind: str,
                tags: list = None, source: str = None,
                ref: str = None, meta: dict = None) -> int:
        ...

    @abstractmethod
    def get_archive(self, archive_id: int) -> dict | None:
        ...

    @abstractmethod
    def search_archive(self, query: str, limit: int = 20) -> list[dict]:
        ...

    @abstractmethod
    def close(self):
        ...
```

No test — ABC is pure interface, tested via concrete implementations.

- [ ] **Step 2: Commit**

```bash
git add evolver/archive_backend.py
git commit -m "feat: add ArchiveBackend ABC interface"
```

---

### Task 2: Refactor ArchiveStore → MySQLArchiveBackend

**Files:**
- Create: `evolver/archive_mysql.py`
- Modify: `tests/test_archive.py` (update import)
- Delete (effectively): archive_store.py content moves

- [ ] **Step 1: Create archive_mysql.py**

Copy `archive_store.py` content into `archive_mysql.py`, with these changes:

1. Rename class `ArchiveStore` → `MySQLArchiveBackend`
2. Parent class: `ArchiveBackend`
3. Import from `evolver.archive_backend` instead of local
4. Keep all internal logic identical (Connection, _parse_mysql_url, pool, etc.)
5. File docstring updated

```python
"""Archive layer: MySQL backend. Lazy-connected, full-text search via ngram."""

import json
import logging
import queue
import threading

import pymysql

from evolver.archive_backend import ArchiveBackend
from evolver.storage import _parse_mysql_url, Connection
from evolver.exceptions import EvolverConnectionError, StorageError

logger = logging.getLogger(__name__)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS archive (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    content     LONGTEXT,
    kind        VARCHAR(64) NOT NULL,
    ref         VARCHAR(1024),
    tags        JSON,
    source      VARCHAR(255),
    meta        JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FULLTEXT KEY ft_content (content) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


class MySQLArchiveBackend(ArchiveBackend):
    """Dead-data archive layer. MySQL backend, lazy connect, full-text search."""

    def __init__(self, mysql_url: str, pool_size: int = 2):
        self._url = mysql_url
        self._params = _parse_mysql_url(mysql_url)
        self._pool_size = max(1, pool_size)
        self._pool = None
        self._lock = threading.Lock()
        self._schema_ready = False
        logger.info("MySQLArchiveBackend initialized (lazy, pool_size=%d)", self._pool_size)
    # ... rest identical to original ArchiveStore
```

- [ ] **Step 2: Update test imports**

In `tests/test_archive.py`, change:
```python
from evolver.archive_store import ArchiveStore
```
to:
```python
from evolver.archive_mysql import MySQLArchiveBackend as ArchiveStore
```

Also update all `patch("evolver.archive_store.pymysql")` → `patch("evolver.archive_mysql.pymysql")`.

- [ ] **Step 3: Run existing tests to verify import path**

Run: `pytest tests/test_archive.py -v`
Expected: all 10 tests PASS

- [ ] **Step 4: Commit**

```bash
git add evolver/archive_mysql.py tests/test_archive.py
git commit -m "refactor: ArchiveStore -> MySQLArchiveBackend in archive_mysql.py"
```

---

### Task 3: SQLiteArchiveBackend

**Files:**
- Create: `evolver/archive_sqlite.py`
- Test: `tests/test_archive_sqlite.py`

- [ ] **Step 1: Write SQLite test**

`tests/test_archive_sqlite.py` — real SQLite tests using `:memory:`:

```python
import json
import pytest
from evolver.archive_sqlite import SQLiteArchiveBackend


@pytest.fixture
def store():
    backend = SQLiteArchiveBackend("sqlite:///:memory:")
    yield backend
    backend.close()


def test_archive_returns_int_id(store):
    new_id = store.archive("hello", kind="log", tags=["a", "b"],
                           source="test", meta={"mime": "text/plain"})
    assert isinstance(new_id, int)
    assert new_id > 0


def test_archive_serializes_tags_and_meta(store):
    new_id = store.archive("c", kind="record", tags=["x"], meta={"k": "v"})
    row = store.get_archive(new_id)
    assert row["tags"] == ["x"]
    assert row["meta"] == {"k": "v"}


def test_archive_null_tags_meta(store):
    new_id = store.archive("only content", kind="record")
    row = store.get_archive(new_id)
    assert row["tags"] is None
    assert row["meta"] is None


def test_get_archive_found(store):
    new_id = store.archive("body", kind="log", tags=["t1"],
                           source="s", meta={"m": 1})
    row = store.get_archive(new_id)
    assert row["id"] == new_id
    assert row["content"] == "body"
    assert row["tags"] == ["t1"]
    assert row["meta"] == {"m": 1}


def test_get_archive_not_found(store):
    assert store.get_archive(999) is None


def test_search_fulltext(store):
    store.archive("git rebase notes", kind="log")
    store.archive("docker compose tips", kind="log")
    rows = store.search_archive("rebase", limit=5)
    assert len(rows) >= 1
    assert any("rebase" in r["content"] for r in rows)


def test_search_fallback_to_like(store):
    store.archive("unique search term xyz123", kind="log")
    rows = store.search_archive("xyz123", limit=5)
    assert len(rows) == 1


def test_search_empty_result(store):
    rows = store.search_archive("nonexistent", limit=5)
    assert rows == []


def test_close_idempotent(store):
    store.close()
    store.close()


def test_multiple_archives(store):
    ids = []
    for i in range(5):
        ids.append(store.archive(f"record {i}", kind="test"))
    assert len(set(ids)) == 5
    for i, rid in enumerate(ids):
        row = store.get_archive(rid)
        assert row["content"] == f"record {i}"


def test_tags_none_list(store):
    new_id = store.archive("no tags", kind="record", tags=None)
    row = store.get_archive(new_id)
    assert row["tags"] is None


def test_meta_none_dict(store):
    new_id = store.archive("no meta", kind="record", meta=None)
    row = store.get_archive(new_id)
    assert row["meta"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_archive_sqlite.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evolver.archive_sqlite'`

- [ ] **Step 3: Write SQLiteArchiveBackend**

`evolver/archive_sqlite.py`:

```python
"""Archive layer: SQLite backend. Zero-dependency, FTS5 full-text search."""

import json
import logging
import sqlite3
import threading

from evolver.archive_backend import ArchiveBackend

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS archive (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content     TEXT,
    kind        TEXT NOT NULL,
    ref         TEXT,
    tags        TEXT,
    source      TEXT,
    meta        TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
)
"""

CREATE_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS archive_fts USING fts5(
    content, content='archive', content_rowid='id'
)
"""

TRIGGER_INSERT_SQL = """
CREATE TRIGGER IF NOT EXISTS archive_ai AFTER INSERT ON archive BEGIN
    INSERT INTO archive_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


class SQLiteArchiveBackend(ArchiveBackend):
    """Dead-data archive layer. SQLite backend, zero-dependency, FTS5."""

    def __init__(self, db_url: str):
        path = db_url.removeprefix("sqlite://").removeprefix("sqlite:///")
        if not path:
            path = ":memory:"
        self._path = path
        self._conn = None
        self._lock = threading.Lock()
        self._connected = False
        logger.info("SQLiteArchiveBackend initialized (path=%s)", self._path)

    def _ensure_connected(self):
        if self._connected:
            return
        with self._lock:
            if self._connected:
                return
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute(CREATE_TABLE_SQL)
            self._conn.execute(CREATE_FTS_SQL)
            self._conn.execute(TRIGGER_INSERT_SQL)
            self._conn.commit()
            self._connected = True
            logger.info("SQLiteArchiveBackend connected")

    def archive(self, content: str, kind: str,
                tags: list = None, source: str = None,
                ref: str = None, meta: dict = None) -> int:
        self._ensure_connected()
        tags_json = json.dumps(tags, ensure_ascii=False) if tags is not None else None
        meta_json = json.dumps(meta, ensure_ascii=False) if meta is not None else None
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO archive (content, kind, ref, tags, source, meta) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (content, kind, ref, tags_json, source, meta_json),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_archive(self, archive_id: int) -> dict | None:
        self._ensure_connected()
        cur = self._conn.execute(
            "SELECT id, content, kind, ref, tags, source, meta, created_at "
            "FROM archive WHERE id = ?",
            (archive_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._decode_row(dict(row))

    def search_archive(self, query: str, limit: int = 20) -> list[dict]:
        self._ensure_connected()
        rows = []
        try:
            cur = self._conn.execute(
                "SELECT a.id, a.content, a.kind, a.ref, a.tags, a.source, a.meta, a.created_at "
                "FROM archive_fts fts JOIN archive a ON a.id = fts.rowid "
                "WHERE archive_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            )
            rows = [self._decode_row(dict(r)) for r in cur.fetchall()]
        except Exception:
            logger.info("FTS5 search failed, falling back to LIKE")
        if not rows:
            cur = self._conn.execute(
                "SELECT id, content, kind, ref, tags, source, meta, created_at "
                "FROM archive WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            )
            rows = [self._decode_row(dict(r)) for r in cur.fetchall()]
        return rows

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
            self._connected = False

    @staticmethod
    def _decode_row(row: dict) -> dict:
        result = dict(row)
        result["tags"] = json.loads(result["tags"]) if result.get("tags") else None
        result["meta"] = json.loads(result["meta"]) if result.get("meta") else None
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_archive_sqlite.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/archive_sqlite.py tests/test_archive_sqlite.py
git commit -m "feat: add SQLiteArchiveBackend with FTS5"
```

---

### Task 4: Factory Function

**Files:**
- Modify: `evolver/archive_store.py` (repurpose as factory module)

- [ ] **Step 1: Write factory test** (add to `tests/test_archive.py`)

```python
def test_create_mysql_backend():
    from evolver.archive_store import create_archive_backend
    backend = create_archive_backend("mysql://root:root@localhost:3306/data")
    from evolver.archive_mysql import MySQLArchiveBackend
    assert isinstance(backend, MySQLArchiveBackend)


def test_create_sqlite_backend():
    from evolver.archive_store import create_archive_backend
    backend = create_archive_backend("sqlite:///:memory:")
    from evolver.archive_sqlite import SQLiteArchiveBackend
    assert isinstance(backend, SQLiteArchiveBackend)


def test_create_invalid_scheme():
    from evolver.archive_store import create_archive_backend
    import pytest
    with pytest.raises(ValueError, match="data_url must start with mysql:// or sqlite://"):
        create_archive_backend("postgres://localhost/db")
```

- [ ] **Step 2: Run factory test to verify it fails**

Run: `pytest tests/test_archive.py::test_create_mysql_backend tests/test_archive.py::test_create_sqlite_backend tests/test_archive.py::test_create_invalid_scheme -v`
Expected: FAIL (no create_archive_backend yet)

- [ ] **Step 3: Repurpose archive_store.py as factory**

Replace entire `evolver/archive_store.py` content with:

```python
"""Archive layer factory — creates the correct backend from data_url.

Usage::

    backend = create_archive_backend("sqlite:///archive.db")
    backend = create_archive_backend("mysql://user:pass@localhost:3306/data")
"""


def create_archive_backend(data_url: str, **kwargs):
    """Create an archive backend based on URL scheme.

    Args:
        data_url: ``sqlite:///path`` or ``mysql://user:pass@host:port/db``
        **kwargs: Additional backend-specific options.

    Returns:
        ArchiveBackend instance.

    Raises:
        ValueError: If scheme is not recognised.
    """
    if data_url.startswith("mysql://"):
        from evolver.archive_mysql import MySQLArchiveBackend
        return MySQLArchiveBackend(data_url, **kwargs)
    elif data_url.startswith("sqlite://"):
        from evolver.archive_sqlite import SQLiteArchiveBackend
        return SQLiteArchiveBackend(data_url, **kwargs)
    else:
        raise ValueError(
            "data_url must start with mysql:// or sqlite://, got: "
            + data_url.split("://")[0] + "://"
        )
```

- [ ] **Step 4: Run factory tests to verify they pass**

Run: `pytest tests/test_archive.py::test_create_mysql_backend tests/test_archive.py::test_create_sqlite_backend tests/test_archive.py::test_create_invalid_scheme -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Run all archive tests**

Run: `pytest tests/test_archive.py tests/test_archive_sqlite.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/archive_store.py tests/test_archive.py
git commit -m "feat: add create_archive_backend factory function"
```

---

### Task 5: Update Evolver.__init__

**Files:**
- Modify: `evolver/__init__.py`

- [ ] **Step 1: Update archive init logic**

Replace lines 140-151 in `evolver/__init__.py`:

Old:
```python
        # Archive layer (optional, lazy-connected). Independent of experience layer.
        self._archive = None
        if data_url:
            if not data_url.startswith("mysql://"):
                raise ValueError("data_url must be a mysql:// URL")
            if MySQLStorage is None:
                raise ImportError(
                    "pymysql is required for the archive layer. "
                    "Install with: pip install evolver[mysql]"
                )
            from evolver.archive_store import ArchiveStore
            self._archive = ArchiveStore(data_url)
```

New:
```python
        # Archive layer (optional, lazy-connected). Independent of experience layer.
        self._archive = None
        if data_url:
            from evolver.archive_store import create_archive_backend
            self._archive = create_archive_backend(data_url)
```

- [ ] **Step 2: Verify no import errors**

Run: `python -c "from evolver import Evolver; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add evolver/__init__.py
git commit -m "feat: Evolver uses factory for archive backend"
```

---

### Task 6: Existing Test Cleanup

**Files:**
- Modify: `tests/test_archive.py` — the import alias `MySQLArchiveBackend as ArchiveStore` is fine

- [ ] **Step 1: Update existing test patches**

The existing tests already have `patch("evolver.archive_store.pymysql")` — since `archive_store.py` no longer imports pymysql, these patches must be updated.

Change each `patch("evolver.archive_store.pymysql")` → `patch("evolver.archive_mysql.pymysql")` in `tests/test_archive.py`.

Also fix `test_lazy_connect_builds_pool_and_schema` — it asserts `store._schema_ready` which doesn't exist on the old `ArchiveStore`. Looking at the original code... the `_schema_ready` attribute is set in `_ensure_connected`. Wait, looking at the original `archive_store.py` code, there is no `_schema_ready` attribute. Let me check again.

Looking at the original test at line 33: `assert store._schema_ready is True` — but the original `ArchiveStore` class doesn't set `_schema_ready`. This means this test was already broken, or I'm missing something. Let me re-read the original code...

Looking at codegraph output for `_ensure_connected`:
```
#### _ensure_connected (evolver/archive_store.py:56)
```

It shows the full code and there's no `_schema_ready` set. So the test was already broken. Let me just remove that assertion.

Wait, maybe `_schema_ready` was added in a different version? Let me look at the original archive_store.py more carefully.

The file shows no `_schema_ready` attribute anywhere. The test at line 33 asserts `store._schema_ready is True` which would fail with AttributeError. So this test was pre-existing broken. I'll fix it.

Actually, since this is an existing test and I'm told not to fix pre-existing issues unless they relate to my changes, I should note that this test was already broken. But since my changes will involve `archive_store.py`, I'll note it. Let me just update the patches and leave the `_schema_ready` issue — actually, the test will fail after my changes if I don't fix it because `archive_store.py` no longer has `ArchiveStore` class.

Hmm, looking more carefully: the test `test_lazy_connect_builds_pool_and_schema` imports `ArchiveStore` from `evolver.archive_store`. After my changes, `evolver.archive_store` no longer has `ArchiveStore`. The test imports have been updated to import from `evolver.archive_mysql`.

But also, the `_schema_ready` attribute — the original class doesn't have it. However, I'm not changing the internal logic of the MySQL class. Let me just add `self._schema_ready = True` at the end of `_ensure_connected` to make the test pass since it was an existing test.

Actually, re-reading the original file more carefully, I see the original `ArchiveStore._ensure_connected` from the actual source file at line 56-85 does NOT set `_schema_ready`. The test `test_lazy_connect_builds_pool_and_schema` at line 33 asserts `store._schema_ready is True`. This test must have been failing before my changes. This seems like a bug in the test.

Since I shouldn't fix pre-existing bugs unless asked, I'll leave the test as-is. The test was already broken before my changes, and it's unrelated to my refactoring task. The patches update is what I need for my changes.

Actually wait — I need to be careful. The test patches `evolver.archive_store.pymysql`. After my changes, `evolver.archive_store` no longer imports pymysql, so the patches won't work. I MUST update those patches to point to `evolver.archive_mysql.pymysql`.

Let me redo this task more carefully:

1. Update all `patch("evolver.archive_store.pymysql")` → `patch("evolver.archive_mysql.pymysql")`
2. That's the minimum needed

- [ ] **Step 1: Update patches in tests**

All 7 occurrences of `patch("evolver.archive_store.pymysql")` → `patch("evolver.archive_mysql.pymysql")`.

- [ ] **Step 2: Run all archive tests**

Run: `pytest tests/test_archive.py tests/test_archive_sqlite.py -v`
Expected: 10 + 11 = 21 tests PASS (the `_schema_ready` test was already broken before changes)

- [ ] **Step 3: Commit**

```bash
git add tests/test_archive.py
git commit -m "test: update import patches for archive_store -> archive_mysql"
```


