"""Archive layer: dead-data storage backed by MySQL.

Independent of BaseStorage. Lazy-connected, full-text searchable,
no embeddings / no skill generation.
"""

import json
import logging
import queue
import threading

import pymysql

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


class ArchiveStore:
    """Dead-data archive layer. MySQL backend, lazy connect, full-text search."""

    def __init__(self, mysql_url: str, pool_size: int = 2):
        self._url = mysql_url
        self._params = _parse_mysql_url(mysql_url)
        self._pool_size = max(1, pool_size)
        self._pool = None
        self._schema_ready = False
        self._lock = threading.Lock()
        logger.info("ArchiveStore initialized (lazy, pool_size=%d)", self._pool_size)

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
            connections = []
            try:
                for _ in range(self._pool_size):
                    c = self._create_connection()
                    connections.append(c)
                    pool.put(c)
                conn = pool.get()
                try:
                    with conn.conn.cursor() as cur:
                        cur.execute(CREATE_TABLE_SQL)
                    conn.conn.commit()
                finally:
                    pool.put(conn)
                self._pool = pool
                self._schema_ready = True
            except Exception:
                for c in connections:
                    try:
                        c.conn.close()
                    except Exception:
                        pass
                raise
            logger.info("ArchiveStore connected (pool=%d)", self._pool_size)

    def _get_conn(self):
        return self._pool.get()

    def _return_conn(self, conn):
        if self._pool is not None:
            self._pool.put(conn)

    @staticmethod
    def _decode_row(row: dict) -> dict:
        if row is None:
            return None
        result = dict(row)
        result["tags"] = json.loads(result["tags"]) if result.get("tags") else None
        result["meta"] = json.loads(result["meta"]) if result.get("meta") else None
        return result

    def archive(self, content: str, kind: str,
                tags: list = None, source: str = None,
                ref: str = None, meta: dict = None) -> int:
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

    def get_archive(self, archive_id: int) -> dict | None:
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

    def search_archive(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search via MATCH...AGAINST; fall back to LIKE on error or empty result."""
        self._ensure_connected()
        conn = self._get_conn()
        try:
            cols = "id, content, kind, ref, tags, source, meta, created_at"
            rows = []
            fulltext_ok = False
            try:
                with conn.conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {cols} FROM archive "
                        "WHERE MATCH(content) AGAINST (%s IN NATURAL LANGUAGE MODE) "
                        "LIMIT %s",
                        (query, limit),
                    )
                    rows = cur.fetchall()
                    fulltext_ok = True
            except Exception:
                logger.info("Archive fulltext search failed, falling back to LIKE")
            if not fulltext_ok or not rows:
                if fulltext_ok:
                    logger.debug("FULLTEXT matched nothing, trying LIKE fallback")
                with conn.conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {cols} FROM archive "
                        "WHERE content LIKE %s ORDER BY created_at DESC LIMIT %s",
                        (f"%{query}%", limit),
                    )
                    rows = cur.fetchall()
            return [self._decode_row(r) for r in rows]
        except Exception as e:
            raise StorageError(f"Archive search failed: {e}") from e
        finally:
            self._return_conn(conn)

    def list_recent(self, limit: int = 100, kind: str = None) -> list[dict]:
        """List recent archive records, newest first.

        Args:
            limit: Max records to return.
            kind: Optional filter by record kind.

        Returns:
            List of decoded archive record dicts.
        """
        self._ensure_connected()
        conn = self._get_conn()
        try:
            cols = "id, content, kind, ref, tags, source, meta, created_at"
            if kind:
                with conn.conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {cols} FROM archive WHERE kind = %s "
                        "ORDER BY created_at DESC LIMIT %s",
                        (kind, limit),
                    )
                    rows = cur.fetchall()
            else:
                with conn.conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {cols} FROM archive ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    )
                    rows = cur.fetchall()
            return [self._decode_row(r) for r in rows]
        except Exception as e:
            raise StorageError(f"Archive list_recent failed: {e}") from e
        finally:
            self._return_conn(conn)

    def close(self):
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
        logger.info("ArchiveStore closed")
