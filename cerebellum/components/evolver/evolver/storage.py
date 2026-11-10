import logging
import queue
import threading
import time
from urllib.parse import urlparse, parse_qs, unquote

import pymysql
from pymysql.cursors import DictCursor
from evolver.storage_base import BaseStorage
from evolver.exceptions import EvolverConnectionError, StorageError

logger = logging.getLogger(__name__)

MAX_CONNECTION_AGE = 3600  # 1 hour


class Connection:
    """Wrapper for database connections with lifecycle tracking."""

    def __init__(self, conn, created_at=None):
        self.conn = conn
        self.created_at = created_at or time.time()

    @property
    def is_expired(self):
        return time.time() - self.created_at > MAX_CONNECTION_AGE


def _parse_mysql_url(url: str) -> dict:
    """Parse ``mysql://user:password@host:port/db?params`` into connection kwargs.

    Supports:
    - IPv4 and IPv6 hosts (``[::1]``)
    - URL-encoded special characters in user/password (``%40`` → ``@``)
    - Optional password, optional port (defaults to 3306)
    - Extra query parameters (charset, timeouts)
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("mysql", "mysql+pymysql", "mysql+aiomysql"):
        raise ValueError(f"Invalid MySQL URL scheme '{parsed.scheme}', expected 'mysql': {url}")

    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    user = unquote(parsed.username) if parsed.username else "root"
    password = unquote(parsed.password) if parsed.password else ""
    database = parsed.path.lstrip("/") if parsed.path else ""

    if not database:
        raise ValueError(f"Missing database name in MySQL URL: {url}")

    params: dict = {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": database,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
    }

    if parsed.query:
        qs = parse_qs(parsed.query)
        for key in ("charset", "connect_timeout", "read_timeout", "write_timeout"):
            if key in qs:
                params[key] = qs[key][0]

    return params


class MySQLStorage(BaseStorage):
    def __init__(self, mysql_url: str, pool_size: int = 3):
        self._url = mysql_url
        self._params = _parse_mysql_url(mysql_url)
        self._pool_size = max(1, pool_size)
        self._pool = queue.Queue(maxsize=self._pool_size)
        self._pool_lock = threading.Lock()
        self._created_count = 0
        self._total_created = 0
        self._active_count = 0
        self._transaction_conn = None  # active transaction connection
        self._transaction_owner = None
        self._transaction_lock = threading.RLock()
        logger.info("MySQLStorage initialized (pool_size=%d)", self._pool_size)

    def _placeholder(self) -> str:
        return "%s"

    def _date_sub_days(self, days: int) -> str:
        return "DATE_SUB(NOW(), INTERVAL %s DAY)"

    def enqueue_vector_sync(self, memory_id: int, operation: str):
        """Atomically coalesce the latest vector mutation for a memory."""
        if operation not in {"upsert", "delete"}:
            raise ValueError(f"Unsupported vector sync operation: {operation}")
        self._execute(
            """
            INSERT INTO vector_sync_outbox (memory_id, operation)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                operation = VALUES(operation),
                attempts = 0,
                last_error = NULL,
                created_at = CURRENT_TIMESTAMP
            """,
            (memory_id, operation),
        )

    def _create_connection(self):
        """Create a new MySQL connection wrapped with lifecycle tracking."""
        try:
            raw_conn = pymysql.connect(**self._params)
            logger.debug("Created new MySQL connection")
            return Connection(raw_conn)
        except Exception as e:
            raise EvolverConnectionError(
                f"Failed to connect to MySQL: {e}. Check connection string and ensure MySQL is running."
            ) from e

    def _get_conn(self):
        """Get a connection: returns the active transaction conn, or one from the pool."""
        if (self._transaction_conn is not None
                and self._transaction_owner == threading.get_ident()):
            return self._transaction_conn

        # Try pool first
        try:
            conn = self._pool.get_nowait()
        except queue.Empty:
            # Pool empty — create new if under capacity
            with self._pool_lock:
                if self._created_count < self._pool_size:
                    self._created_count += 1
                    self._total_created += 1
                    self._active_count += 1
                    return self._create_connection()
            # At capacity — block until one is returned
            logger.debug("Connection pool exhausted, waiting...")
            conn = self._pool.get()

        # Skip expired connections
        if conn.is_expired:
            self._close_connection(conn)
            return self._get_conn()

        # Verify the connection is alive
        try:
            conn.conn.ping(reconnect=True)
            self._active_count += 1
            return conn
        except Exception:
            # Broken connection — close it and create a replacement
            self._close_connection(conn)
            self._active_count += 1
            return self._create_connection()

    def _return_conn(self, conn):
        """Return a connection to the pool (unless it's the transaction conn)."""
        if conn is self._transaction_conn:
            return
        self._active_count -= 1
        if conn.is_expired:
            self._close_connection(conn)
            return
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            with self._pool_lock:
                # Re-check: another thread may have drained from the pool
                try:
                    self._pool.put_nowait(conn)
                except queue.Full:
                    self._close_connection(conn)

    def _close_connection(self, conn):
        """Close a connection and decrement counters."""
        try:
            conn.conn.close()
        except Exception:
            pass
        with self._pool_lock:
            self._created_count -= 1

    def connect(self):
        """Pre-warm the connection pool. Raises if zero connections could be created."""
        failures = 0
        with self._pool_lock:
            for _ in range(self._pool_size - self._created_count):
                try:
                    self._pool.put(self._create_connection())
                    self._created_count += 1
                    self._total_created += 1
                except EvolverConnectionError:
                    failures += 1
                    if self._created_count == 0:
                        continue
                    break
        if self._created_count == 0:
            raise EvolverConnectionError(
                "Failed to create any connections. Check MySQL URL and ensure MySQL is running."
            )
        logger.info("Connection pool warmed (%d connections)", self._created_count)

    def begin(self):
        """Start a transaction. All subsequent operations use the same connection."""
        if (self._transaction_conn is not None
                and self._transaction_owner == threading.get_ident()):
            raise StorageError("Transaction already in progress")
        self._transaction_lock.acquire()
        conn = None
        try:
            if self._transaction_conn is not None:
                raise StorageError("Transaction already in progress")
            conn = self._get_conn()
            self._transaction_conn = conn
            self._transaction_owner = threading.get_ident()
            conn.conn.begin()
            logger.debug("Transaction started")
        except Exception:
            if self._transaction_conn is conn:
                self._transaction_conn = None
                self._transaction_owner = None
            if conn is not None:
                self._return_conn(conn)
            self._transaction_lock.release()
            raise

    def commit(self):
        """Commit the active transaction and release the connection."""
        if self._transaction_conn is None:
            raise StorageError("No active transaction to commit")
        if self._transaction_owner != threading.get_ident():
            raise StorageError("Transaction must be committed by its owner thread")
        conn = self._transaction_conn
        try:
            conn.conn.commit()
            logger.debug("Transaction committed")
        finally:
            self._transaction_conn = None
            self._transaction_owner = None
            self._return_conn(conn)
            self._transaction_lock.release()

    def rollback(self):
        """Roll back the active transaction and release the connection."""
        if self._transaction_conn is None:
            raise StorageError("No active transaction to roll back")
        if self._transaction_owner != threading.get_ident():
            raise StorageError("Transaction must be rolled back by its owner thread")
        conn = self._transaction_conn
        try:
            conn.conn.rollback()
            logger.debug("Transaction rolled back")
        finally:
            self._transaction_conn = None
            self._transaction_owner = None
            self._return_conn(conn)
            self._transaction_lock.release()

    def _execute(self, sql: str, params=None):
        conn = self._get_conn()
        try:
            with conn.conn.cursor() as cur:
                cur.execute(sql, params)
                # Only auto-commit when NOT inside a transaction
                if self._transaction_conn is None:
                    conn.conn.commit()
                return cur
        except Exception as e:
            raise StorageError(f"Database operation failed: {e}") from e
        finally:
            self._return_conn(conn)

    def _executemany(self, sql: str, seq_of_params):
        seq = list(seq_of_params)
        if not seq:
            return None
        conn = self._get_conn()
        try:
            with conn.conn.cursor() as cur:
                cur.executemany(sql, seq)
                if self._transaction_conn is None:
                    conn.conn.commit()
                return cur
        except Exception as e:
            raise StorageError(f"Database operation failed: {e}") from e
        finally:
            self._return_conn(conn)

    def _fetchall(self, sql: str, params=None) -> list:
        cur = self._execute(sql, params)
        return cur.fetchall()

    def _fetchone(self, sql: str, params=None) -> dict | None:
        cur = self._execute(sql, params)
        return cur.fetchone()

    def stats(self):
        return {
            "pool_size": self._pool.qsize(),
            "active": self._active_count,
            "total_created": self._total_created,
        }

    def close(self):
        if self._transaction_conn:
            try:
                self._transaction_conn.conn.rollback()
            except Exception:
                pass
            try:
                self._transaction_conn.conn.close()
            except Exception:
                pass
            self._transaction_conn = None
        while True:
            try:
                conn = self._pool.get_nowait()
                try:
                    conn.conn.close()
                except Exception:
                    pass
            except queue.Empty:
                break
        with self._pool_lock:
            self._created_count = 0
        logger.info("MySQLStorage closed")
