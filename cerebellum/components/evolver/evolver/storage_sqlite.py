import logging
import sqlite3
import threading
import time
from evolver.storage_base import BaseStorage
from evolver.exceptions import StorageError

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2


class SQLiteStorage(BaseStorage):
    """SQLite-backed storage for evolver. Drop-in replacement for MySQLStorage."""

    def __init__(self, db_path: str = "evolver.db"):
        self._db_path = db_path
        self._conn = None
        self._transaction_conn = None
        self._lock = threading.RLock()
        self._connect()
        logger.info("SQLiteStorage initialized (db=%s)", db_path)

    def _placeholder(self) -> str:
        return "?"

    _LOCK_RETRY_ATTEMPTS = 3
    _LOCK_RETRY_BASE_SECONDS = 0.05

    def _run_with_lock_retry(self, op):
        """Run `op()` retrying transient 'database is locked' contention.

        busy_timeout=5000 absorbs most writer contention; this bounded
        exponential backoff (3 attempts) covers the residual busy races.
        Single statements are atomic, so retrying is always safe.
        """
        delay = self._LOCK_RETRY_BASE_SECONDS
        for attempt in range(1, self._LOCK_RETRY_ATTEMPTS + 1):
            try:
                return op()
            except sqlite3.OperationalError as e:
                if "locked" not in str(e).lower() or attempt == self._LOCK_RETRY_ATTEMPTS:
                    raise
                logger.warning(
                    "SQLite lock contention (attempt %d/%d); retrying in %.2fs",
                    attempt, self._LOCK_RETRY_ATTEMPTS, delay,
                )
                time.sleep(delay)
                delay *= 2


    def _date_sub_days(self, days: int) -> str:
        return f"datetime('now', '-{days} days')"

    def enqueue_vector_sync(self, memory_id: int, operation: str):
        """Atomically coalesce the latest vector mutation for a memory."""
        if operation not in {"upsert", "delete"}:
            raise ValueError(f"Unsupported vector sync operation: {operation}")
        self._execute(
            """
            INSERT INTO vector_sync_outbox (memory_id, operation)
            VALUES (?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                operation = excluded.operation,
                attempts = 0,
                last_error = NULL,
                created_at = datetime('now')
            """,
            (memory_id, operation),
        )

    def _connect(self):
        try:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._ensure_schema()
            self._migrate_schema()
        except Exception as e:
            raise StorageError(f"Failed to connect to SQLite: {e}") from e

    def _ensure_schema(self):
        """Create tables if they don't exist, migrate if needed."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                content     TEXT NOT NULL,
                category    TEXT,
                tags        TEXT,
                embedding   BLOB,
                source      TEXT,
                importance  REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                content_hash TEXT,
                lifecycle   TEXT DEFAULT 'seed',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now')),
                last_accessed_at TEXT,
                embedder   TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_memories_hash
                ON memories(content_hash);
        """)
        # Idempotent migration for existing DBs: add the decay-clock column
        # and backfill from updated_at (the previous clock source).
        memory_columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(memories)")
        }
        if "last_accessed_at" not in memory_columns:
            self._conn.execute(
                "ALTER TABLE memories ADD COLUMN last_accessed_at TEXT"
            )
            self._conn.execute(
                "UPDATE memories SET last_accessed_at = updated_at "
                "WHERE last_accessed_at IS NULL"
            )
        if "embedder" not in memory_columns:
            self._conn.execute("ALTER TABLE memories ADD COLUMN embedder TEXT")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                label       TEXT NOT NULL,
                node_type   TEXT,
                properties  TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(label, node_type)
            );
            CREATE INDEX IF NOT EXISTS idx_graph_nodes_label
                ON graph_nodes(label);

            CREATE TABLE IF NOT EXISTS graph_edges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id   INTEGER NOT NULL,
                target_id   INTEGER NOT NULL,
                relation    TEXT NOT NULL,
                weight      REAL DEFAULT 1.0,
                properties  TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (source_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                UNIQUE(source_id, target_id, relation)
            );

            CREATE TABLE IF NOT EXISTS skills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                description TEXT,
                file_path   TEXT,
                content     TEXT,
                version     INTEGER DEFAULT 1,
                status      TEXT DEFAULT 'draft',
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS interactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task        TEXT NOT NULL,
                outcome     TEXT,
                context     TEXT,
                solution    TEXT,
                lessons     TEXT,
                memory_ids  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS evolution_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                details     TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS links (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type   TEXT NOT NULL,
                source_id     INTEGER NOT NULL,
                target_type   TEXT NOT NULL,
                target_id     INTEGER NOT NULL,
                link_type     TEXT NOT NULL,
                weight        REAL DEFAULT 1.0,
                created_at    TEXT DEFAULT (datetime('now')),
                UNIQUE(source_type, source_id, target_type, target_id)
            );
            CREATE INDEX IF NOT EXISTS idx_links_source
                ON links(source_type, source_id);
            CREATE INDEX IF NOT EXISTS idx_links_target
                ON links(target_type, target_id);

            CREATE TABLE IF NOT EXISTS skill_evaluations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id      INTEGER NOT NULL,
                version       INTEGER NOT NULL,
                total_score   REAL,
                dim_scores    TEXT,
                eval_mode     TEXT DEFAULT 'auto',
                round         INTEGER DEFAULT 1,
                status        TEXT DEFAULT 'pass',
                diff_summary  TEXT,
                created_at    TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (skill_id) REFERENCES skills(id)
            );

            CREATE TABLE IF NOT EXISTS facts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fact        TEXT NOT NULL,
                tags        TEXT DEFAULT '[]',
                time        TEXT,
                session_id  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_facts_time ON facts(time);
            CREATE INDEX IF NOT EXISTS idx_facts_session ON facts(session_id);

            CREATE TABLE IF NOT EXISTS distill_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                level       TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                output      TEXT,
                token_count INTEGER,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_distill_lookup
                ON distill_runs(level, created_at);

            CREATE TABLE IF NOT EXISTS vector_sync_outbox (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id   INTEGER NOT NULL UNIQUE,
                operation   TEXT NOT NULL CHECK(operation IN ('upsert', 'delete')),
                attempts    INTEGER NOT NULL DEFAULT 0,
                last_error  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_vector_sync_pending
                ON vector_sync_outbox(id, attempts);
        """)
        # FTS5 (may not be available in all SQLite builds)
        try:
            self._conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
                    fact, content=facts, content_rowid=id, tokenize='unicode61'
                );
                CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
                    INSERT INTO facts_fts(rowid, fact) VALUES (new.id, new.fact);
                END;
                CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
                    INSERT INTO facts_fts(facts_fts, rowid, fact) VALUES ('delete', old.id, old.fact);
                END;
            """)
            self._has_fts = True
        except Exception:
            self._has_fts = False
            logger.info("FTS5 not available, full-text search disabled")

    def _get_schema_version(self):
        """Get current schema version from metadata table."""
        try:
            result = self._fetchone(
                "SELECT version FROM schema_version WHERE id = 1"
            )
            return result["version"] if result else 1
        except Exception:
            return 1

    def _set_schema_version(self, version):
        """Set schema version in metadata table."""
        self._execute(
            "INSERT OR REPLACE INTO schema_version (id, version) VALUES (1, ?)",
            (version,)
        )

    def _migrate_schema(self):
        """Run pending schema migrations."""
        current = self._get_schema_version()
        if current >= SCHEMA_VERSION:
            return

        self._execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL
            )
        """)

        migrations = [
            "ALTER TABLE memories ADD COLUMN content_hash TEXT",
            "ALTER TABLE memories ADD COLUMN lifecycle TEXT DEFAULT 'seed'",
        ]

        for i, sql in enumerate(migrations[current - 1:], start=current):
            try:
                self._execute(sql)
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    raise StorageError(f"Migration {i} failed: {e}")
        self._set_schema_version(SCHEMA_VERSION)

    def _get_conn(self):
        if self._transaction_conn is not None:
            return self._transaction_conn
        return self._conn

    def begin(self):
        # Hold the connection lock for the complete transaction.  RLock keeps
        # same-thread _execute calls re-entrant while other worker threads wait
        # instead of accidentally joining the active transaction.
        self._lock.acquire()
        try:
            if self._transaction_conn is not None:
                raise StorageError("Transaction already in progress")
            self._transaction_conn = self._conn
            self._transaction_conn.execute("BEGIN")
            logger.debug("Transaction started")
        except Exception:
            self._transaction_conn = None
            self._lock.release()
            raise

    def commit(self):
        if self._transaction_conn is None:
            raise StorageError("No active transaction to commit")
        try:
            self._transaction_conn.commit()
            logger.debug("Transaction committed")
        finally:
            self._transaction_conn = None
            self._lock.release()

    def rollback(self):
        if self._transaction_conn is None:
            raise StorageError("No active transaction to roll back")
        try:
            self._transaction_conn.rollback()
            logger.debug("Transaction rolled back")
        finally:
            self._transaction_conn = None
            self._lock.release()

    def _execute(self, sql: str, params=None):
        with self._lock:
            conn = self._get_conn()
            try:
                def op():
                    if params:
                        cur = conn.execute(sql, params)
                    else:
                        cur = conn.execute(sql)
                    if self._transaction_conn is None:
                        conn.commit()
                    return cur
                return self._run_with_lock_retry(op)
            except Exception as e:
                raise StorageError(f"Database operation failed: {e}") from e

    def _executemany(self, sql: str, seq_of_params):
        with self._lock:
            conn = self._get_conn()
            try:
                def op():
                    cur = conn.executemany(sql, seq_of_params)
                    if self._transaction_conn is None:
                        conn.commit()
                    return cur
                return self._run_with_lock_retry(op)
            except Exception as e:
                raise StorageError(f"Database operation failed: {e}") from e

    def _fetchall(self, sql: str, params=None) -> list:
        cur = self._execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def _fetchone(self, sql: str, params=None) -> dict | None:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def close(self):
        with self._lock:
            if self._transaction_conn:
                try:
                    self._transaction_conn.rollback()
                except Exception:
                    pass
                self._transaction_conn = None
            if self._conn:
                self._conn.close()
                self._conn = None
        logger.info("SQLiteStorage closed")
