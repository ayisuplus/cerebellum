"""Base storage with shared business logic for MySQL and SQLite backends."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from evolver.models import (
    Memory, GraphNode, GraphEdge, Link, Fact,
)

logger = logging.getLogger(__name__)


class BaseStorage(ABC):
    """Abstract base storage. Subclasses provide connection management and SQL dialect."""

    _MEMORY_COLUMNS = (
        "id, content, category, tags, embedding, source, importance, "
        "access_count, content_hash, lifecycle, created_at, updated_at, embedder"
    )
    _MEMORY_SEARCH_COLUMNS = (
        "id, content, category, tags, NULL AS embedding, source, importance, "
        "access_count, content_hash, lifecycle, created_at, updated_at"
    )

    # --- Abstract interface (subclasses MUST implement) ---

    @abstractmethod
    def _placeholder(self) -> str:
        """Return SQL placeholder ('?' for SQLite, '%s' for MySQL)."""

    @abstractmethod
    def _date_sub_days(self, days: int) -> str:
        """Return SQL expression for 'now minus N days'."""

    @abstractmethod
    def _execute(self, sql: str, params=None):
        """Execute SQL and return cursor."""

    def _executemany(self, sql: str, seq_of_params):
        """Execute SQL with many param sets. Default: loop _execute."""
        for params in seq_of_params:
            self._execute(sql, params)

    @abstractmethod
    def _fetchall(self, sql: str, params=None) -> list:
        """Execute and return all rows as list[dict]."""

    @abstractmethod
    def _fetchone(self, sql: str, params=None) -> dict | None:
        """Execute and return one row as dict or None."""

    @abstractmethod
    def begin(self):
        """Start a transaction."""

    @abstractmethod
    def commit(self):
        """Commit the active transaction."""

    @abstractmethod
    def rollback(self):
        """Roll back the active transaction."""

    @abstractmethod
    def close(self):
        """Release all resources."""

    # --- Shared business logic ---

    def insert_memory(self, mem: Memory) -> int:
        p = self._placeholder()
        sql = f"""
            INSERT INTO memories (
                content, category, tags, embedding, source, importance,
                content_hash, lifecycle, created_at, embedder
            )
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, COALESCE({p}, CURRENT_TIMESTAMP), {p})
        """
        cur = self._execute(sql, (
            mem.content, mem.category,
            json.dumps(mem.tags) if mem.tags else None,
            mem.embedding, mem.source, mem.importance,
            mem.content_hash, mem.lifecycle, mem.created_at, mem.embedder,
        ))
        memory_id = cur.lastrowid
        if mem.embedding is not None:
            self.enqueue_vector_sync(memory_id, "upsert")
        return memory_id

    # --- Durable vector-index synchronization outbox ---

    def enqueue_vector_sync(self, memory_id: int, operation: str):
        """Coalesce a vector-index mutation into the durable outbox.

        Callers normally invoke this inside the same transaction as the
        memory mutation.  One row per memory ID makes the latest operation
        authoritative and keeps repeated updates bounded.
        """
        if operation not in {"upsert", "delete"}:
            raise ValueError(f"Unsupported vector sync operation: {operation}")
        p = self._placeholder()
        self._execute(
            f"DELETE FROM vector_sync_outbox WHERE memory_id = {p}",
            (memory_id,),
        )
        self._execute(
            "INSERT INTO vector_sync_outbox "
            f"(memory_id, operation) VALUES ({p}, {p})",
            (memory_id, operation),
        )

    def get_pending_vector_sync(self, limit: int = 100) -> list[dict]:
        """Return pending vector mutations in commit order."""
        p = self._placeholder()
        return self._fetchall(
            "SELECT id, memory_id, operation, attempts, last_error, created_at "
            f"FROM vector_sync_outbox ORDER BY id LIMIT {p}",
            (limit,),
        )

    def mark_vector_sync_done(self, event_id: int):
        p = self._placeholder()
        self._execute(
            f"DELETE FROM vector_sync_outbox WHERE id = {p}",
            (event_id,),
        )

    def mark_vector_sync_failed(self, event_id: int, error: str):
        p = self._placeholder()
        self._execute(
            "UPDATE vector_sync_outbox "
            f"SET attempts = attempts + 1, last_error = {p} WHERE id = {p}",
            (error[:1000], event_id),
        )

    def find_memory_by_hash(self, content_hash: str) -> Optional['Memory']:
        p = self._placeholder()
        row = self._fetchone(
            f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE content_hash = {p} LIMIT 1",
            (content_hash,),
        )
        if not row:
            return None
        return self._row_to_memory(row)

    def find_memories_by_hashes(self, hashes: list[str]) -> dict[str, 'Memory']:
        """Return {hash: Memory} for all matching hashes (single IN query)."""
        if not hashes:
            return {}
        p = self._placeholder()
        placeholders = ",".join([p] * len(hashes))
        rows = self._fetchall(
            f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE content_hash IN ({placeholders})",
            list(hashes),
        )
        result: dict[str, 'Memory'] = {}
        for r in rows:
            mem = self._row_to_memory(r)
            if mem.content_hash:
                result[mem.content_hash] = mem
        return result

    def get_all_content_hashes(self) -> set[str]:
        """Cheap hash-only fetch for dedup lookups (no embedding BLOB load)."""
        rows = self._fetchall(
            "SELECT content_hash FROM memories WHERE content_hash IS NOT NULL"
        )
        return {r["content_hash"] for r in rows if r.get("content_hash")}

    def get_all_memories_with_embeddings(self, max_scan: int = 0, category: str = None) -> list:
        p = self._placeholder()
        where = ["embedding IS NOT NULL"]
        params = []
        if category:
            where.append(f"category = {p}")
            params.append(category)
        sql = (
            f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE " + " AND ".join(where) +
            " ORDER BY created_at DESC"
        )
        if max_scan > 0:
            sql += f" LIMIT {p}"
            params.append(max_scan)
        rows = self._fetchall(sql, params)
        return [self._row_to_memory(r) for r in rows]

    def get_all_memories_columns(self, columns: list[str] | None = None) -> list:
        """Get all memories with only specified columns (no embedding BLOB).

        Args:
            columns: list of column names, defaults to id, content, category, tags,
                     source, importance, access_count, content_hash, lifecycle, created_at.
        """
        if columns is None:
            columns = ["id", "content", "category", "tags", "source",
                       "importance", "access_count", "content_hash", "lifecycle", "created_at"]
        sql = f"SELECT {', '.join(columns)} FROM memories ORDER BY created_at DESC"
        rows = self._fetchall(sql, [])
        return [self._row_to_memory(r) for r in rows]

    def get_all_memories_with_embeddings_batched(self, batch_size: int = 500, category: str = None):
        p = self._placeholder()
        offset = 0
        while True:
            where = ["embedding IS NOT NULL"]
            params = []
            if category:
                where.append(f"category = {p}")
                params.append(category)
            sql = (
                f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE " + " AND ".join(where) +
                f" ORDER BY created_at DESC LIMIT {p} OFFSET {p}"
            )
            params.extend([batch_size, offset])
            rows = self._fetchall(sql, params)
            if not rows:
                break
            yield [self._row_to_memory(r) for r in rows]
            offset += batch_size

    def get_memories_by_ids(self, ids: list) -> list:
        if not ids:
            return []
        p = self._placeholder()
        placeholders = ",".join([p] * len(ids))
        rows = self._fetchall(
            f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE id IN ({placeholders})", ids
        )
        return [self._row_to_memory(r) for r in rows]

    def search_memories_lexical(self, terms: list[str], limit: int = 2000) -> list:
        """Generate lexical candidates independently of the vector index.

        This portable implementation uses parameterized LIKE predicates for
        SQLite and MySQL.  It intentionally omits embedding BLOBs; BM25 and
        graph channels only need memory metadata and content.
        """
        normalized_terms = []
        seen = set()
        for term in terms:
            value = str(term).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized_terms.append(value)
            if len(normalized_terms) >= 20:
                break
        if not normalized_terms:
            return []

        p = self._placeholder()
        predicates = []
        params = []
        for term in normalized_terms:
            predicates.append(f"(content LIKE {p} OR tags LIKE {p})")
            wildcard = f"%{term}%"
            params.extend([wildcard, wildcard])

        sql = (
            f"SELECT {self._MEMORY_SEARCH_COLUMNS} FROM memories WHERE "
            + " OR ".join(predicates)
            + " ORDER BY importance DESC, created_at DESC"
        )
        if limit > 0:
            sql += f" LIMIT {p}"
            params.append(limit)
        rows = self._fetchall(sql, params)
        return [self._row_to_memory(row) for row in rows]

    def get_memories_created_after(self, days: int, limit: int = 50) -> list:
        """Get memories created within the last N days.

        Args:
            days: Number of days to look back.
            limit: Maximum number of memories to return.

        Returns:
            List of Memory objects, newest first.
        """
        p = self._placeholder()
        date_expr = self._date_sub_days(days)
        params = []
        if p in date_expr:
            params.append(days)
        params.append(limit)
        rows = self._fetchall(
            f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE created_at >= {date_expr} ORDER BY created_at DESC LIMIT {p}",
            params
        )
        return [self._row_to_memory(r) for r in rows]

    def update_access_count(self, memory_id: int):
        p = self._placeholder()
        self._execute(
            f"UPDATE memories SET access_count = access_count + 1 WHERE id = {p}", (memory_id,)
        )

    def update_memory_content(self, memory_id: int, new_content: str):
        p = self._placeholder()
        self._execute(
            f"UPDATE memories SET content = {p}, updated_at = CURRENT_TIMESTAMP WHERE id = {p}",
            (new_content, memory_id),
        )

    def update_memory_importance(self, memory_id: int, new_importance: float):
        p = self._placeholder()
        # Importance changes checkpoint the decay clock (the new value becomes
        # the base for further decay); unrelated columns stay untouched so
        # decay time is never erased by other writes.
        self._execute(
            f"UPDATE memories SET importance = {p}, last_accessed_at = CURRENT_TIMESTAMP WHERE id = {p}",
            (new_importance, memory_id),
        )

    def update_memory_tags(self, memory_id: int, new_tags: list):
        p = self._placeholder()
        self._execute(
            f"UPDATE memories SET tags = {p}, updated_at = CURRENT_TIMESTAMP WHERE id = {p}",
            (json.dumps(new_tags, ensure_ascii=False), memory_id),
        )

    def update_memory_embedding(self, memory_id: int, embedding_bytes: bytes,
                                embedder: str = None):
        p = self._placeholder()
        self._execute(
            f"UPDATE memories SET embedding = {p}, embedder = COALESCE({p}, embedder) WHERE id = {p}",
            (embedding_bytes, embedder, memory_id),
        )
        self.enqueue_vector_sync(memory_id, "upsert")

    def set_memory_lifecycle(self, memory_id: int, lifecycle: str):
        p = self._placeholder()
        self._execute(
            f"UPDATE memories SET lifecycle = {p} WHERE id = {p}",
            (lifecycle, memory_id),
        )

    def set_memory_lifecycle_batch(self, pending: list[tuple[str, int]]):
        """Batch update lifecycle stages using executemany.

        Args:
            pending: list of (lifecycle, memory_id) tuples.
        """
        if not pending:
            return
        p = self._placeholder()
        self._executemany(
            f"UPDATE memories SET lifecycle = {p} WHERE id = {p}",
            [(lifecycle, mid) for lifecycle, mid in pending],
        )

    def get_memory_by_id(self, memory_id: int):
        p = self._placeholder()
        row = self._fetchone(
            f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE id = {p}", (memory_id,)
        )
        return self._row_to_memory(row) if row else None

    def delete_memory(self, memory_id: int):
        p = self._placeholder()
        self.enqueue_vector_sync(memory_id, "delete")
        self._execute(f"DELETE FROM memories WHERE id = {p}", (memory_id,))

    def delete_memories_older_than(self, days: int):
        p = self._placeholder()
        date_expr = self._date_sub_days(days)
        params = ["distilled"]
        if p in date_expr:
            params.append(days)
        rows = self._fetchall(
            f"SELECT id FROM memories WHERE lifecycle != {p} AND created_at < {date_expr}",
            params,
        )
        for row in rows:
            self.enqueue_vector_sync(row["id"], "delete")
        result = self._execute(
            f"DELETE FROM memories WHERE lifecycle != {p} AND created_at < {date_expr}", params
        )
        return result.rowcount

    def delete_memories_low_importance(self, threshold: float):
        p = self._placeholder()
        params = ("distilled", threshold)
        rows = self._fetchall(
            f"SELECT id FROM memories WHERE lifecycle != {p} AND importance < {p}",
            params,
        )
        for row in rows:
            self.enqueue_vector_sync(row["id"], "delete")
        result = self._execute(
            f"DELETE FROM memories WHERE lifecycle != {p} AND importance < {p}",
            params,
        )
        return result.rowcount

    def delete_memories_by_lifecycle(self, lifecycle: str) -> int:
        """Batch delete memories by lifecycle (atomic, single SQL statement).

        Args:
            lifecycle: lifecycle stage such as 'stale', 'seed', etc.

        Returns:
            Number of memories deleted.
        """
        p = self._placeholder()
        rows = self._fetchall(
            f"SELECT id FROM memories WHERE lifecycle = {p}", (lifecycle,)
        )
        for row in rows:
            self.enqueue_vector_sync(row["id"], "delete")
        result = self._execute(
            f"DELETE FROM memories WHERE lifecycle = {p}", (lifecycle,)
        )
        return result.rowcount

    def _row_to_memory(self, r: dict) -> Memory:
        tags_raw = r.get("tags")
        tags = json.loads(tags_raw) if tags_raw else []
        return Memory(
            id=r.get("id"),
            content=r.get("content", ""),
            category=r.get("category", ""),
            tags=tags,
            embedding=r.get("embedding"),
            source=r.get("source"),
            importance=r.get("importance", 0.5),
            access_count=r.get("access_count", 0),
            content_hash=r.get("content_hash"),
            lifecycle=r.get("lifecycle", "seed"),
            created_at=r.get("created_at"),
            last_accessed_at=r.get("last_accessed_at"),
            embedder=r.get("embedder"),
        )

    # --- Graph operations ---

    def upsert_node(self, node: GraphNode) -> int:
        p = self._placeholder()
        existing = self._fetchone(
            f"SELECT id FROM graph_nodes WHERE label = {p} AND node_type = {p}",
            (node.label, node.node_type),
        )
        if existing:
            return existing["id"]
        cur = self._execute(
            f"INSERT INTO graph_nodes (label, node_type, properties) VALUES ({p}, {p}, {p})",
            (node.label, node.node_type, json.dumps(node.properties) if node.properties else None),
        )
        return cur.lastrowid

    def upsert_edge(self, edge: GraphEdge) -> int:
        p = self._placeholder()
        existing = self._fetchone(
            f"SELECT id FROM graph_edges WHERE source_id = {p} AND target_id = {p} AND relation = {p}",
            (edge.source_id, edge.target_id, edge.relation),
        )
        if existing:
            self._execute(
                f"UPDATE graph_edges SET weight = weight + {p} WHERE id = {p}",
                (edge.weight, existing["id"]),
            )
            return existing["id"]
        cur = self._execute(
            f"INSERT INTO graph_edges (source_id, target_id, relation, weight, properties) "
            f"VALUES ({p}, {p}, {p}, {p}, {p})",
            (edge.source_id, edge.target_id, edge.relation, edge.weight,
             json.dumps(edge.properties) if edge.properties else None),
        )
        return cur.lastrowid

    def get_graph_node(self, node_id: int) -> GraphNode | None:
        p = self._placeholder()
        row = self._fetchone(
            f"SELECT id, label, node_type, properties FROM graph_nodes WHERE id = {p}",
            (node_id,),
        )
        if not row:
            return None
        return GraphNode(
            id=row["id"], label=row["label"], node_type=row["node_type"],
            properties=json.loads(row["properties"]) if row.get("properties") else None,
        )

    def query_nodes(self, label: str, relation: str = None) -> list:
        p = self._placeholder()
        if relation:
            rows = self._fetchall(
                "SELECT DISTINCT n.id, n.label, n.node_type, n.properties "
                "FROM graph_nodes n "
                "JOIN graph_edges e ON (n.id = e.source_id OR n.id = e.target_id) "
                f"WHERE (n.label LIKE {p}) AND e.relation = {p}",
                (f"%{label}%", relation),
            )
        else:
            rows = self._fetchall(
                f"SELECT id, label, node_type, properties FROM graph_nodes WHERE label LIKE {p}",
                (f"%{label}%",),
            )
        return [GraphNode(id=r["id"], label=r["label"], node_type=r["node_type"],
                          properties=json.loads(r["properties"]) if r.get("properties") else None)
                for r in rows]

    def query_nodes_batch(self, tokens: list[str]) -> list:
        """Batch LIKE search for multiple tokens in a single query."""
        if not tokens:
            return []
        p = self._placeholder()
        conditions = " OR ".join([f"label LIKE {p}"] * len(tokens))
        params = [f"%{t}%" for t in tokens]
        rows = self._fetchall(
            f"SELECT id, label, node_type, properties FROM graph_nodes WHERE {conditions}",
            params,
        )
        return [GraphNode(id=r["id"], label=r["label"], node_type=r["node_type"],
                          properties=json.loads(r["properties"]) if r.get("properties") else None)
                for r in rows]

    def get_nodes_by_labels(self, labels: list[str]) -> list:
        """Batch lookup nodes by exact label match."""
        if not labels:
            return []
        p = self._placeholder()
        placeholders = ",".join([p] * len(labels))
        rows = self._fetchall(
            f"SELECT id, label, node_type, properties FROM graph_nodes WHERE label IN ({placeholders})",
            labels,
        )
        return [GraphNode(id=r["id"], label=r["label"], node_type=r["node_type"],
                          properties=json.loads(r["properties"]) if r.get("properties") else None)
                for r in rows]

    def get_neighbors(self, node_id: int, hops: int = 1, visited: set = None) -> list:
        if hops < 1:
            return []
        if visited is None:
            visited = set()
        if node_id in visited:
            return []
        visited.add(node_id)
        p = self._placeholder()
        rows = self._fetchall(
            "SELECT DISTINCT n.id, n.label, n.node_type, n.properties "
            "FROM graph_nodes n "
            "JOIN graph_edges e ON (n.id = e.source_id OR n.id = e.target_id) "
            f"WHERE (e.source_id = {p} OR e.target_id = {p}) AND n.id != {p}",
            (node_id, node_id, node_id),
        )
        neighbors = []
        for r in rows:
            nid = r["id"]
            if nid in visited:
                continue
            visited.add(nid)
            neighbors.append(GraphNode(
                id=nid, label=r["label"], node_type=r["node_type"],
                properties=json.loads(r["properties"]) if r.get("properties") else None,
            ))
        if hops > 1:
            for n in list(neighbors):
                deeper = self.get_neighbors(n.id, hops - 1, visited)
                neighbors.extend(deeper)
        return neighbors

    def count_nodes(self) -> int:
        row = self._fetchone("SELECT COUNT(*) as cnt FROM graph_nodes")
        return row["cnt"] if row else 0

    def count_edges(self) -> int:
        row = self._fetchone("SELECT COUNT(*) as cnt FROM graph_edges")
        return row["cnt"] if row else 0

    # --- Interaction operations ---

    def insert_interaction(self, task: str, outcome: str, context: str,
                           solution: str, lessons: str, memory_ids: list) -> int:
        p = self._placeholder()
        cur = self._execute(
            f"INSERT INTO interactions (task, outcome, context, solution, lessons, memory_ids) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
            (task, outcome, context, solution, lessons, json.dumps(memory_ids)),
        )
        return cur.lastrowid

    # --- Evolution log ---

    def log_event(self, event_type: str, details: dict):
        p = self._placeholder()
        self._execute(
            f"INSERT INTO evolution_log (event_type, details) VALUES ({p}, {p})",
            (event_type, json.dumps(details, ensure_ascii=False)),
        )

    # --- Skill operations ---

    def upsert_skill(self, name: str, description: str, file_path: str,
                     content: str, version: int = 1) -> tuple[int, int]:
        p = self._placeholder()
        existing = self._fetchone(f"SELECT id, version FROM skills WHERE name = {p}", (name,))
        if existing:
            new_ver = existing["version"] + 1
            self._execute(
                f"UPDATE skills SET description={p}, file_path={p}, content={p}, version={p} WHERE id={p}",
                (description, file_path, content, new_ver, existing["id"]),
            )
            return (existing["id"], new_ver)
        cur = self._execute(
            f"INSERT INTO skills (name, description, file_path, content, version) VALUES ({p},{p},{p},{p},{p})",
            (name, description, file_path, content, version),
        )
        return (cur.lastrowid, version)

    # --- Stats ---

    def list_skills(self) -> list:
        """List all stored skills."""
        rows = self._fetchall(
            "SELECT id, name, description, file_path, content, version, status, created_at "
            "FROM skills ORDER BY created_at DESC"
        )
        return rows

    def get_skill_by_name(self, name: str) -> dict | None:
        """Get a skill by name."""
        p = self._placeholder()
        return self._fetchone(
            f"SELECT id, name, description, file_path, content, version, status, created_at "
            f"FROM skills WHERE name = {p}", (name,)
        )

    def stats(self) -> dict:
        mem = self._fetchone("SELECT COUNT(*) as cnt FROM memories")
        sk = self._fetchone("SELECT COUNT(*) as cnt FROM skills")
        inter = self._fetchone("SELECT COUNT(*) as cnt FROM interactions")
        result = {
            "memories": mem["cnt"] if mem else 0,
            "nodes": self.count_nodes(),
            "edges": self.count_edges(),
            "skills": sk["cnt"] if sk else 0,
            "interactions": inter["cnt"] if inter else 0,
        }
        # Lifecycle distribution snapshot
        try:
            rows = self._fetchall(
                "SELECT lifecycle, COUNT(*) as cnt FROM memories GROUP BY lifecycle"
            )
            if rows:
                result["lifecycle_distribution"] = {r["lifecycle"]: r["cnt"] for r in rows}
        except Exception:
            result["lifecycle_distribution"] = {}
            logger.warning("Failed to query lifecycle distribution", exc_info=True)
        return result

    def decay_edges(self, factor: float = 0.9, min_weight: float = 0.01):
        p = self._placeholder()
        self._execute(f"UPDATE graph_edges SET weight = weight * {p}", (factor,))
        self._execute(f"DELETE FROM graph_edges WHERE weight < {p}", (min_weight,))

    # --- Link operations ---

    def insert_link(self, source_type: str, source_id: int,
                    target_type: str, target_id: int,
                    link_type: str, weight: float = 1.0) -> int:
        p = self._placeholder()
        existing = self._fetchone(
            f"SELECT id FROM links WHERE source_type={p} AND source_id={p} "
            f"AND target_type={p} AND target_id={p}",
            (source_type, source_id, target_type, target_id),
        )
        if existing:
            self._execute(
                f"UPDATE links SET weight={p} WHERE id={p}",
                (weight, existing["id"]),
            )
            return existing["id"]
        cur = self._execute(
            f"INSERT INTO links (source_type, source_id, target_type, target_id, link_type, weight) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
            (source_type, source_id, target_type, target_id, link_type, weight),
        )
        return cur.lastrowid

    def insert_links_batch(self, links: list[tuple]) -> int:
        """Batch insert/upsert links, deduplicating against existing pairs.

        Args:
            links: List of (source_type, source_id, target_type, target_id,
                   link_type, weight) tuples.

        Returns:
            Number of new links inserted (updates not counted).
        """
        if not links:
            return 0

        # Fetch all existing pairs in one query to dedup
        # Build WHERE clause with OR chains for the common case
        p = self._placeholder()
        existing_keys: set[tuple] = set()
        # Query in batches of 500 to avoid giant SQL
        for batch_start in range(0, len(links), 500):
            batch = links[batch_start:batch_start + 500]
            conditions = []
            params = []
            for src_type, src_id, tgt_type, tgt_id, *_ in batch:
                conditions.append(
                    f"(source_type={p} AND source_id={p} AND target_type={p} AND target_id={p})"
                )
                params.extend([src_type, src_id, tgt_type, tgt_id])
            if conditions:
                rows = self._fetchall(
                    f"SELECT source_type, source_id, target_type, target_id FROM links "
                    f"WHERE {' OR '.join(conditions)}",
                    params,
                )
                for row in rows:
                    existing_keys.add((
                        row["source_type"], row["source_id"],
                        row["target_type"], row["target_id"],
                    ))

        # Split into inserts (new) and updates (existing weight change)
        to_insert = []
        to_update = []
        for src_type, src_id, tgt_type, tgt_id, link_type, weight in links:
            key = (src_type, src_id, tgt_type, tgt_id)
            if key in existing_keys:
                to_update.append((weight, src_type, src_id, tgt_type, tgt_id))
            else:
                to_insert.append((src_type, src_id, tgt_type, tgt_id, link_type, weight))

        count = 0
        if to_insert:
            p = self._placeholder()
            placeholders = ", ".join("(" + ", ".join(p for _ in range(6)) + ")" for _ in to_insert)
            flat = []
            for src_type, src_id, tgt_type, tgt_id, link_type, weight in to_insert:
                flat.extend([src_type, src_id, tgt_type, tgt_id, link_type, weight])
            self._execute(
                f"INSERT INTO links (source_type, source_id, target_type, target_id, link_type, weight) "
                f"VALUES {placeholders}",
                flat,
            )
            count = len(to_insert)

        if to_update:
            p = self._placeholder()
            for weight, src_type, src_id, tgt_type, tgt_id in to_update:
                self._execute(
                    f"UPDATE links SET weight={p} "
                    f"WHERE source_type={p} AND source_id={p} AND target_type={p} AND target_id={p}",
                    (weight, src_type, src_id, tgt_type, tgt_id),
                )

        return count

    def get_backlinks(self, target_type: str, target_id: int) -> list:
        p = self._placeholder()
        rows = self._fetchall(
            f"SELECT id, source_type, source_id, target_type, target_id, link_type, weight "
            f"FROM links WHERE target_type={p} AND target_id={p} ORDER BY weight DESC",
            (target_type, target_id),
        )
        return [Link(**r) for r in rows]

    def get_outgoing(self, source_type: str, source_id: int) -> list:
        p = self._placeholder()
        rows = self._fetchall(
            f"SELECT id, source_type, source_id, target_type, target_id, link_type, weight "
            f"FROM links WHERE source_type={p} AND source_id={p} ORDER BY weight DESC",
            (source_type, source_id),
        )
        return [Link(**r) for r in rows]

    def decay_links(self, factor: float = 0.95, min_weight: float = 0.01):
        p = self._placeholder()
        self._execute(f"UPDATE links SET weight = weight * {p}", (factor,))
        self._execute(f"DELETE FROM links WHERE weight < {p}", (min_weight,))

    # --- Skill evaluation operations ---

    def insert_skill_evaluation(self, skill_id: int, version: int,
                                total_score: float, dim_scores: dict,
                                eval_mode: str, round: int,
                                status: str, diff_summary: str = None) -> int:
        p = self._placeholder()
        cur = self._execute(
            "INSERT INTO skill_evaluations "
            "(skill_id, version, total_score, dim_scores, eval_mode, round, status, diff_summary) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})",
            (skill_id, version, total_score, json.dumps(dim_scores, ensure_ascii=False),
             eval_mode, round, status, diff_summary),
        )
        return cur.lastrowid

    def get_skill_evaluations(self, skill_id: int) -> list:
        p = self._placeholder()
        rows = self._fetchall(
            f"SELECT id, skill_id, version, total_score, dim_scores, eval_mode, round, status, diff_summary "
            f"FROM skill_evaluations WHERE skill_id={p} ORDER BY round",
            (skill_id,),
        )
        for r in rows:
            r["dim_scores"] = json.loads(r["dim_scores"]) if r.get("dim_scores") else {}
        return rows

    # --- Facts operations ---

    def insert_fact(self, fact: str, tags: list = None,
                    time: str = None, session_id: str = None) -> int:
        p = self._placeholder()
        cur = self._execute(
            f"INSERT INTO facts (fact, tags, time, session_id) VALUES ({p}, {p}, {p}, {p})",
            (fact, json.dumps(tags or []), time, session_id),
        )
        return cur.lastrowid

    def insert_facts_batch(self, facts: list) -> int:
        """Batch insert facts. Each item: {fact, tags?, time?, session_id?}."""
        count = 0
        for f in facts:
            self.insert_fact(
                fact=f["fact"], tags=f.get("tags"),
                time=f.get("time"), session_id=f.get("session_id"),
            )
            count += 1
        return count

    def get_all_facts(self, limit: int = 100) -> list:
        rows = self._fetchall(
            f"SELECT id, fact, tags, time, session_id, created_at FROM facts ORDER BY created_at DESC LIMIT {self._placeholder()}",
            (limit,),
        )
        return [self._row_to_fact(r) for r in rows]

    def search_facts_fts(self, query: str, limit: int = 10) -> list:
        """Full-text search on facts (FTS5). Falls back to LIKE if FTS unavailable."""
        p = self._placeholder()
        try:
            rows = self._fetchall(
                f"SELECT f.id, f.fact, f.tags, f.time, f.session_id, f.created_at "
                f"FROM facts_fts fts JOIN facts f ON f.id = fts.rowid "
                f"WHERE facts_fts MATCH {p} ORDER BY rank LIMIT {p}",
                (query, limit),
            )
        except Exception:
            rows = self._fetchall(
                f"SELECT id, fact, tags, time, session_id, created_at FROM facts "
                f"WHERE fact LIKE {p} ORDER BY created_at DESC LIMIT {p}",
                (f"%{query}%", limit),
            )
        return [self._row_to_fact(r) for r in rows]

    def delete_fact(self, fact_id: int):
        p = self._placeholder()
        self._execute(f"DELETE FROM facts WHERE id = {p}", (fact_id,))

    def _row_to_fact(self, r: dict) -> Fact:
        tags = json.loads(r["tags"]) if r.get("tags") else []
        return Fact(
            id=r["id"], fact=r["fact"], tags=tags,
            time=r.get("time"), session_id=r.get("session_id"),
        )

    # --- Distill runs operations ---

    def insert_distill_run(self, level: str, fingerprint: str,
                           output: str, token_count: int = 0) -> int:
        p = self._placeholder()
        cur = self._execute(
            f"INSERT INTO distill_runs (level, fingerprint, output, token_count) VALUES ({p}, {p}, {p}, {p})",
            (level, fingerprint, output, token_count),
        )
        return cur.lastrowid

    def get_last_distill_run(self, level: str) -> dict | None:
        p = self._placeholder()
        return self._fetchone(
            f"SELECT id, level, fingerprint, output, token_count, created_at "
            f"FROM distill_runs WHERE level={p} ORDER BY created_at DESC LIMIT 1",
            (level,),
        )

    def get_memories_in_range(self, days: int = 1, category: str = None) -> list:
        """Get memories created within the last N days."""
        p = self._placeholder()
        date_expr = self._date_sub_days(days)
        where = [f"created_at >= {date_expr}"]
        params = []
        if p in date_expr:
            params.append(days)
        if category:
            where.append(f"category = {p}")
            params.append(category)
        sql = (
            f"SELECT {self._MEMORY_COLUMNS} FROM memories WHERE " + " AND ".join(where) +
            " ORDER BY importance DESC, created_at DESC"
        )
        rows = self._fetchall(sql, params)
        return [self._row_to_memory(r) for r in rows]
