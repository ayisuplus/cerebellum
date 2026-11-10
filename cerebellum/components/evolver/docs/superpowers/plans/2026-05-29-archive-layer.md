# 数据归档层(Archive Layer)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Evolver 增加一个独立、可选、懒连接的 MySQL 数据归档层(`ArchiveStore`),与经验层(SQLite)完全并行、互不依赖。

**Architecture:** 新增独立类 `ArchiveStore`(不继承 `BaseStorage`),复用 `storage.py` 的 `_parse_mysql_url` 与 `Connection`,内嵌精简连接池,懒连接 + 自建带 ngram FULLTEXT 的 `archive` 单表。`Evolver` 通过可选 `data_url` 参数挂载,暴露 `archive` / `search_archive` / `get_archive` 三个 facade 方法。

**Tech Stack:** Python 3.10+、pymysql、MySQL 5.7.6+(ngram parser)、pytest + unittest.mock。

**Spec:** `docs/superpowers/specs/2026-05-29-archive-layer-design.md`

---

## 文件结构

- **创建** `evolver/archive_store.py` — `ArchiveStore` 类:懒连接、精简池、自建表、archive/search/get/close。
- **创建** `tests/test_archive.py` — `ArchiveStore` 单元测试(mock pymysql)。
- **修改** `evolver/config.py` — `EvolverConfig` 增加 `data_url` 字段 + `from_env` 读 `EVOLVER_DATA_URL`。
- **修改** `evolver/__init__.py` — 构造函数新增 `data_url` 参数、装配 `self._archive`、三个 facade 方法、`close`/`close_async` 收尾、`__all__` 导出。
- **修改** `tests/test_evolver.py` — facade 集成测试增补。

---

## Task 1: `ArchiveStore` 骨架 — 构造零 I/O + 懒连接

**Files:**
- Create: `evolver/archive_store.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_archive.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from evolver.archive_store import ArchiveStore


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_archive.py::test_construct_no_io -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evolver.archive_store'`

- [ ] **Step 3: 写最小实现**

Create `evolver/archive_store.py`:

```python
"""Archive layer: dead-data storage backed by MySQL.

Independent of BaseStorage. Lazy-connected, full-text searchable,
no embeddings / no skill generation.
"""

import json
import logging
import queue
import threading

import pymysql
from pymysql.cursors import DictCursor

from evolver.storage import _parse_mysql_url, Connection
from evolver.exceptions import EvolverConnectionError, StorageError

logger = logging.getLogger(__name__)


class ArchiveStore:
    """Dead-data archive layer. MySQL backend, lazy connect, full-text search."""

    def __init__(self, mysql_url: str, pool_size: int = 2):
        self._url = mysql_url
        self._params = _parse_mysql_url(mysql_url)
        self._pool_size = max(1, pool_size)
        self._pool = None            # built on first use
        self._schema_ready = False
        self._lock = threading.Lock()
        logger.info("ArchiveStore initialized (lazy, pool_size=%d)", self._pool_size)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_archive.py::test_construct_no_io -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/archive_store.py tests/test_archive.py
git commit -m "feat: add ArchiveStore skeleton with zero-IO constructor"
```

---

## Task 2: 懒连接 + 自建表(双重检查锁)

**Files:**
- Modify: `evolver/archive_store.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_archive.py`:

```python
def test_lazy_connect_builds_pool_and_schema(mock_conn):
    conn, cursor = mock_conn
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        store._ensure_connected()
        # pool built
        assert store._pool is not None
        assert store._schema_ready is True
        # CREATE TABLE executed
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
        store._ensure_connected()  # second call must be a no-op
        assert mock_pymysql.connect.call_count == calls_after_first
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_archive.py::test_lazy_connect_builds_pool_and_schema tests/test_archive.py::test_ensure_connected_idempotent -v`
Expected: FAIL — `AttributeError: 'ArchiveStore' object has no attribute '_ensure_connected'`

- [ ] **Step 3: 写最小实现**

Add the `CREATE_TABLE_SQL` constant after the imports in `evolver/archive_store.py`:

```python
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
```

Add these methods inside `ArchiveStore`:

```python
    def _create_connection(self):
        try:
            raw = pymysql.connect(**self._params)
            return Connection(raw)
        except Exception as e:
            raise EvolverConnectionError(
                f"Failed to connect to archive MySQL: {e}. "
                "Check data_url and ensure MySQL is running."
            ) from e

    def _ensure_connected(self):
        """Build the pool and create the table once (double-checked lock)."""
        if self._pool is not None:
            return
        with self._lock:
            if self._pool is not None:
                return
            pool = queue.Queue(maxsize=self._pool_size)
            for _ in range(self._pool_size):
                pool.put(self._create_connection())
            # Create schema using one connection
            conn = pool.get()
            try:
                with conn.conn.cursor() as cur:
                    cur.execute(CREATE_TABLE_SQL)
                conn.conn.commit()
                self._schema_ready = True
            finally:
                pool.put(conn)
            self._pool = pool
            logger.info("ArchiveStore connected (pool=%d, schema ready)", self._pool_size)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_archive.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
git add evolver/archive_store.py tests/test_archive.py
git commit -m "feat: ArchiveStore lazy connect + ngram archive table"
```

---

## Task 3: `archive()` 写入

**Files:**
- Modify: `evolver/archive_store.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_archive.py`:

```python
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
        assert json.loads(params[3]) == ["x"]   # tags position
        assert json.loads(params[5]) == {"k": "v"}  # meta position


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
        assert params[3] is None   # tags NULL
        assert params[5] is None   # meta NULL
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_archive.py::test_archive_returns_id -v`
Expected: FAIL — `AttributeError: 'ArchiveStore' object has no attribute 'archive'`

- [ ] **Step 3: 写最小实现**

Add a private connection helper and the `archive` method inside `ArchiveStore`. Note the INSERT column order so test param indices match: `content(0), kind(1), ref(2), tags(3), source(4), meta(5)`.

```python
    def _get_conn(self):
        return self._pool.get()

    def _return_conn(self, conn):
        self._pool.put(conn)

    def archive(self, content: str, kind: str,
                tags: list = None, source: str = None,
                ref: str = None, meta: dict = None) -> int:
        """Insert one archive record. Triggers lazy connect on first call."""
        self._ensure_connected()
        tags_json = json.dumps(tags, ensure_ascii=False) if tags is not None else None
        meta_json = json.dumps(meta, ensure_ascii=False) if meta is not None else None
        conn = self._get_conn()
        try:
            with conn.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO archive (content, kind, ref, tags, source, meta) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (content, kind, ref, tags_json, source, meta_json),
                )
                conn.conn.commit()
                return cur.lastrowid
        except Exception as e:
            raise StorageError(f"Archive insert failed: {e}") from e
        finally:
            self._return_conn(conn)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_archive.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 提交**

```bash
git add evolver/archive_store.py tests/test_archive.py
git commit -m "feat: ArchiveStore.archive() insert with JSON tags/meta"
```

---

## Task 4: `get_archive()` 取一条

**Files:**
- Modify: `evolver/archive_store.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_archive.py`:

```python
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
        assert row["tags"] == ["t1"]      # decoded
        assert row["meta"] == {"m": 1}    # decoded


def test_get_archive_not_found(mock_conn):
    conn, cursor = mock_conn
    cursor.fetchone.return_value = None
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        mock_pymysql.connect.return_value = conn
        store = ArchiveStore("mysql://root:root@localhost:3306/data", pool_size=1)
        assert store.get_archive(999) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_archive.py::test_get_archive_found -v`
Expected: FAIL — `AttributeError: ... no attribute 'get_archive'`

- [ ] **Step 3: 写最小实现**

Add a row decoder + `get_archive` inside `ArchiveStore`:

```python
    @staticmethod
    def _decode_row(row: dict) -> dict:
        """Decode JSON columns in place. tags -> list/None, meta -> dict/None."""
        if row is None:
            return None
        row["tags"] = json.loads(row["tags"]) if row.get("tags") else None
        row["meta"] = json.loads(row["meta"]) if row.get("meta") else None
        return row

    def get_archive(self, archive_id: int) -> dict | None:
        """Fetch one archive record by id, or None."""
        self._ensure_connected()
        conn = self._get_conn()
        try:
            with conn.conn.cursor() as cur:
                cur.execute(
                    "SELECT id, content, kind, ref, tags, source, meta, created_at "
                    "FROM archive WHERE id = %s",
                    (archive_id,),
                )
                row = cur.fetchone()
                return self._decode_row(row)
        except Exception as e:
            raise StorageError(f"Archive get failed: {e}") from e
        finally:
            self._return_conn(conn)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_archive.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 提交**

```bash
git add evolver/archive_store.py tests/test_archive.py
git commit -m "feat: ArchiveStore.get_archive() with JSON decode"
```

---

## Task 5: `search_archive()` 全文检索 + LIKE 兜底

**Files:**
- Modify: `evolver/archive_store.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_archive.py`:

```python
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
        # First non-DDL execute (the MATCH query) raises; LIKE must follow.
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
        assert calls["n"] == 1                       # MATCH was attempted
        assert rows[0]["content"] == "like result"   # LIKE fallback returned data
        all_sql = " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)
        assert "LIKE" in all_sql
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_archive.py::test_search_archive_fulltext -v`
Expected: FAIL — `AttributeError: ... no attribute 'search_archive'`

- [ ] **Step 3: 写最小实现**

Add `search_archive` inside `ArchiveStore`. The MATCH query runs in its own try; on any exception it falls back to LIKE on a fresh cursor:

```python
    def search_archive(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search via MATCH...AGAINST; fall back to LIKE on error."""
        self._ensure_connected()
        conn = self._get_conn()
        try:
            cols = "id, content, kind, ref, tags, source, meta, created_at"
            try:
                with conn.conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {cols} FROM archive "
                        "WHERE MATCH(content) AGAINST (%s IN NATURAL LANGUAGE MODE) "
                        "LIMIT %s",
                        (query, limit),
                    )
                    rows = cur.fetchall()
            except Exception:
                logger.info("Archive fulltext search failed, falling back to LIKE")
                with conn.conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {cols} FROM archive "
                        "WHERE content LIKE %s ORDER BY created_at DESC LIMIT %s",
                        (f"%{query}%", limit),
                    )
                    rows = cur.fetchall()
            return [self._decode_row(r) for r in rows]
        finally:
            self._return_conn(conn)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_archive.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: 提交**

```bash
git add evolver/archive_store.py tests/test_archive.py
git commit -m "feat: ArchiveStore.search_archive() with LIKE fallback"
```

---

## Task 6: `close()` 收尾(未连接 no-op)

**Files:**
- Modify: `evolver/archive_store.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_archive.py`:

```python
def test_close_when_never_connected():
    with patch("evolver.archive_store.pymysql") as mock_pymysql:
        store = ArchiveStore("mysql://root:root@localhost:3306/data")
        store.close()  # must not raise
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_archive.py::test_close_after_connect -v`
Expected: FAIL — `AttributeError: ... no attribute 'close'`

- [ ] **Step 3: 写最小实现**

Add `close` inside `ArchiveStore`:

```python
    def close(self):
        """Close all pooled connections. No-op if never connected."""
        with self._lock:
            if self._pool is None:
                return
            while True:
                try:
                    conn = self._pool.get_nowait()
                except queue.Empty:
                    break
                try:
                    conn.conn.close()
                except Exception:
                    pass
            self._pool = None
            self._schema_ready = False
        logger.info("ArchiveStore closed")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_archive.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: 提交**

```bash
git add evolver/archive_store.py tests/test_archive.py
git commit -m "feat: ArchiveStore.close() idempotent cleanup"
```

---

## Task 7: `EvolverConfig` 增加 `data_url`

**Files:**
- Modify: `evolver/config.py:57-93` (EvolverConfig 字段 + __post_init__ 区域)
- Modify: `evolver/config.py:95-144` (from_env)
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_config.py`:

```python
import os
from unittest.mock import patch
from evolver.config import EvolverConfig


def test_config_data_url_default_none():
    cfg = EvolverConfig(mysql_url="sqlite:///x.db")
    assert cfg.data_url is None


def test_config_from_env_reads_data_url():
    env = {
        "EVOLVER_DB_URL": "sqlite:///x.db",
        "EVOLVER_DATA_URL": "mysql://root:root@localhost:3306/data",
    }
    with patch.dict(os.environ, env, clear=True):
        cfg = EvolverConfig.from_env()
        assert cfg.data_url == "mysql://root:root@localhost:3306/data"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_config.py::test_config_data_url_default_none -v`
Expected: FAIL — `AttributeError: 'EvolverConfig' object has no attribute 'data_url'`

- [ ] **Step 3: 写最小实现**

In `evolver/config.py`, add the field to `EvolverConfig` (place it right after the `mysql_url: str` line at the top of the class body):

```python
    mysql_url: str
    data_url: str | None = None
```

In `from_env`, add this line inside the `return cls(` call (e.g. right after `mysql_url=url,`):

```python
            data_url=os.environ.get("EVOLVER_DATA_URL"),
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/config.py tests/test_config.py
git commit -m "feat: EvolverConfig.data_url + EVOLVER_DATA_URL env"
```

---

## Task 8: Evolver 装配 `self._archive`(可选 + 校验)

**Files:**
- Modify: `evolver/__init__.py:60-80` (构造函数签名)
- Modify: `evolver/__init__.py:85-115` (config 构造,传入 data_url)
- Modify: `evolver/__init__.py:~196` (storage 初始化后装配 archive)
- Test: `tests/test_evolver.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_evolver.py`:

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_evolver.py::test_evolver_archive_disabled_by_default -v`
Expected: FAIL — `AttributeError: 'Evolver' object has no attribute '_archive'`

- [ ] **Step 3: 写最小实现**

In `evolver/__init__.py`, add `data_url` to the constructor signature (right after `db_url: str = None,`):

```python
    def __init__(self, mysql_url: str = None, db_url: str = None,
                 data_url: str = None,
```

Pass it into the `EvolverConfig(` construction (add after `mysql_url=url,`):

```python
            data_url=data_url,
```

After the experience-layer storage is initialized (i.e. after the `self._storage = ...` if/elif/else block around line 132), add the archive wiring:

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

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_evolver.py::test_evolver_archive_disabled_by_default tests/test_evolver.py::test_evolver_invalid_data_url_scheme tests/test_evolver.py::test_evolver_archive_constructed_lazily -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
git add evolver/__init__.py tests/test_evolver.py
git commit -m "feat: wire optional lazy ArchiveStore into Evolver"
```

---

## Task 9: Evolver facade 方法 + close 收尾

**Files:**
- Modify: `evolver/__init__.py` (add three methods near `add_fact`/`search_facts`, ~line 422-428)
- Modify: `evolver/__init__.py:452-465` (close)
- Modify: `evolver/__init__.py:541-552` (close_async)
- Test: `tests/test_evolver.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_evolver.py`:

```python
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
```

Ensure the test file imports `EvolverError`. If not present, add at the top of `tests/test_evolver.py`:

```python
from evolver.exceptions import EvolverError
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_evolver.py::test_archive_methods_raise_when_not_configured -v`
Expected: FAIL — `AttributeError: 'Evolver' object has no attribute 'archive'`

- [ ] **Step 3: 写最小实现**

In `evolver/__init__.py`, ensure `EvolverError` is imported (it already is, via the exceptions import line). Add the three methods right after the existing `add_fact` method:

```python
    def archive(self, content: str, kind: str, tags: list = None,
                source: str = None, ref: str = None, meta: dict = None) -> int:
        """Store a dead-data record in the archive layer (MySQL)."""
        if self._archive is None:
            raise EvolverError("Archive layer not configured. Pass data_url= to enable it.")
        return self._archive.archive(content, kind, tags=tags,
                                     source=source, ref=ref, meta=meta)

    def search_archive(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search the archive layer."""
        if self._archive is None:
            raise EvolverError("Archive layer not configured. Pass data_url= to enable it.")
        return self._archive.search_archive(query, limit=limit)

    def get_archive(self, archive_id: int) -> dict | None:
        """Fetch one archive record by id."""
        if self._archive is None:
            raise EvolverError("Archive layer not configured. Pass data_url= to enable it.")
        return self._archive.get_archive(archive_id)
```

In `close()`, add the archive close right after `self._storage.close()`:

```python
        self._storage.close()
        if self._archive is not None:
            self._archive.close()
```

In `close_async()`, add the same right after `self._storage.close()`:

```python
        self._storage.close()
        if self._archive is not None:
            self._archive.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_evolver.py -v`
Expected: PASS (all)

- [ ] **Step 5: 提交**

```bash
git add evolver/__init__.py tests/test_evolver.py
git commit -m "feat: Evolver archive/search_archive/get_archive facade + close"
```

---

## Task 10: 可选真实 MySQL 集成测试(默认跳过)

**Files:**
- Modify: `tests/test_archive.py`

- [ ] **Step 1: 写带跳过守卫的集成测试**

Append to `tests/test_archive.py`:

```python
import os


@pytest.mark.skipif(
    not os.environ.get("EVOLVER_TEST_MYSQL"),
    reason="set EVOLVER_TEST_MYSQL=mysql://user:pass@host:port/db to run",
)
def test_real_mysql_roundtrip():
    url = os.environ["EVOLVER_TEST_MYSQL"]
    store = ArchiveStore(url, pool_size=1)
    try:
        new_id = store.archive("集成测试 中文 fulltext payload",
                               kind="record", tags=["zh"], source="it",
                               meta={"mime": "text/plain"})
        assert new_id > 0
        got = store.get_archive(new_id)
        assert got["content"].startswith("集成测试")
        assert got["tags"] == ["zh"]
        results = store.search_archive("fulltext", limit=10)
        assert any(r["id"] == new_id for r in results)
        # Chinese search exercises ngram parser (or LIKE fallback)
        zh = store.search_archive("中文", limit=10)
        assert any(r["id"] == new_id for r in zh)
    finally:
        store.close()
```

- [ ] **Step 2: 运行测试确认跳过(无 MySQL 环境时)**

Run: `pytest tests/test_archive.py::test_real_mysql_roundtrip -v`
Expected: SKIPPED (reason shown) — unless `EVOLVER_TEST_MYSQL` is set

- [ ] **Step 3: 提交**

```bash
git add tests/test_archive.py
git commit -m "test: optional real-MySQL archive integration test (skipped by default)"
```

---

## Task 11: 全量回归 + 文档同步

**Files:**
- Modify: `CLAUDE.md`(在 Storage 段补充 archive 层说明)

- [ ] **Step 1: 跑全量测试套件**

Run: `pytest -q`
Expected: 全绿(新增 archive/config/evolver 测试通过,既有测试不回归;真实 MySQL 测试 SKIPPED)

- [ ] **Step 2: 在 `CLAUDE.md` 的 `## Storage` 段后补充一段**

Add after the existing Storage section:

```markdown
## Archive Layer (data tier)

Optional MySQL-backed dead-data store, independent of the experience tier.
Enable by passing `data_url="mysql://..."` to `Evolver(...)`. Lazy-connected:
no connection until the first `archive()` call.

- `archive(content, kind, tags=, source=, ref=, meta=)` — store a record, returns id.
- `search_archive(query, limit=)` — full-text (ngram) search, LIKE fallback.
- `get_archive(id)` — fetch one record.

Images/large files are stored by reference (`ref` = path/URL), not as BLOBs.
No embeddings, no skill generation, no cross-tier links.
```

- [ ] **Step 3: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: document optional archive data tier in CLAUDE.md"
```

---

## 自审结论

- **Spec 覆盖:** 架构(Task 8/9)、schema+ngram(Task 2)、ArchiveStore API(Task 3/4/5/6)、Evolver 接线(Task 7/8/9)、测试策略含真实 MySQL 跳过(Task 1-6/10)、文档(Task 11)。全部有对应任务。
- **占位符:** 无 TBD/TODO,每个代码步骤均给出完整代码与可运行命令。
- **类型/签名一致性:** `archive(content, kind, tags, source, ref, meta)` 在 ArchiveStore 与 Evolver facade 一致;INSERT 列序 `content,kind,ref,tags,source,meta` 与 Task 3 测试的 params 下标一致;`_decode_row` 在 get/search 复用;`_ensure_connected`/`_get_conn`/`_return_conn`/`close` 命名贯穿一致。
