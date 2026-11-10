import logging
import os
import threading
import time
import numpy as np
from evolver.models import Memory, RecallResult
from evolver.embedding import EmbeddingClient
from evolver.ann_index import ANNIndex
from evolver.exceptions import StorageError
from evolver.stopwords import STOPWORDS
from evolver.normalize import normalize_input
from evolver.config import RerankerConfig
from evolver.utils import embedder_identity_of
from evolver.config import DEFAULT_LIFECYCLE_RULES, DEFAULT_MAX_SCAN
from evolver.retrieval import RetrievalEngine

logger = logging.getLogger(__name__)


class MemoryEngine:
    _MIN_CONTEXT_LENGTH = 20
    _RECALL_CANDIDATE_MULTIPLIER = 2
    _MAX_TAGS = 20
    # ANN auto-build threshold; shares DEFAULT_MAX_SCAN with retrieval's
    # brute-force scan cap so memories beyond the newest max_scan rows stay
    # reachable (no 2000-5000 blind zone).
    _ANN_THRESHOLD = DEFAULT_MAX_SCAN
    _VECTOR_SYNC_RETRY_SECONDS = 30.0

    def __init__(self, storage, embedding: EmbeddingClient, ann_index_path: str = "evolver.ann",
                 recall_bm25_weight: float = 0.15, reranker_config: RerankerConfig = None,
                 lifecycle_rules: list = None, vector_store=None):
        self._storage = storage
        self._embedding = embedding
        self._link = None  # Set by Evolver after construction
        self._ann: ANNIndex | None = None
        self._ann_built = False
        self._ann_index_path = ann_index_path
        self._recall_bm25_weight = recall_bm25_weight
        self._reranker = reranker_config or RerankerConfig()
        self._lifecycle_rules = sorted(
            lifecycle_rules or DEFAULT_LIFECYCLE_RULES,
            key=lambda r: r.priority, reverse=True,
        )
        self._deduplicator = None  # Set by set_deduplicator()
        self._closet = None  # Set by set_closet()
        self._vector_store = vector_store  # VectorStore (Qdrant, InMemory, etc.)
        self._vector_store_synced = False
        self._vector_store_last_sync_attempt = 0.0
        self._vector_sync_lock = threading.RLock()
        self._retrieval = RetrievalEngine(self)

    def set_deduplicator(self, deduplicator):
        """Configure near-duplicate detection for store()."""
        self._deduplicator = deduplicator

    def set_closet(self, closet):
        """Configure closet index for store()."""
        self._closet = closet

    @staticmethod
    def _vector_metadata(mem: Memory) -> dict:
        """Build the filterable payload stored alongside a memory vector."""
        return {
            "category": mem.category,
            "source": mem.source,
            "lifecycle": mem.lifecycle,
            "tags": list(mem.tags or []),
        }

    def _drain_vector_sync_outbox(self, limit: int = 100) -> dict:
        """Apply committed vector mutations without failing the DB write path."""
        if self._vector_store is None:
            return {"processed": 0, "failed": 0}

        processed = 0
        failed = 0
        with self._vector_sync_lock:
            try:
                events = self._storage.get_pending_vector_sync(limit=limit)
            except Exception:
                logger.warning("Unable to read vector sync outbox", exc_info=True)
                return {"processed": 0, "failed": 1}

            for event in events:
                event_id = event["id"]
                memory_id = int(event["memory_id"])
                try:
                    if event["operation"] == "upsert":
                        mem = self._storage.get_memory_by_id(memory_id)
                        if mem is None or mem.embedding is None:
                            self._vector_store.delete(memory_id)
                        else:
                            vector = np.asarray(
                                self._embedding.bytes_to_vector(mem.embedding),
                                dtype=np.float32,
                            )
                            self._vector_store.upsert(
                                memory_id, vector, self._vector_metadata(mem)
                            )
                    else:
                        self._vector_store.delete(memory_id)
                    self._storage.mark_vector_sync_done(event_id)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    try:
                        self._storage.mark_vector_sync_failed(event_id, str(exc))
                    except Exception:
                        logger.warning(
                            "Unable to record vector sync failure for event %s",
                            event_id,
                            exc_info=True,
                        )
                    logger.warning(
                        "Vector sync failed for memory %s; durable retry retained",
                        memory_id,
                        exc_info=True,
                    )
        return {"processed": processed, "failed": failed}

    def sync_vector_store(self, batch_size: int = 500, prune: bool = True) -> dict:
        """Reconcile VectorStore from the database source of truth.

        This is safe to run repeatedly.  It repairs missed inserts and updates,
        removes orphaned vectors, and drains any durable outbox mutations that
        raced with the full scan.
        """
        if self._vector_store is None:
            return {"upserted": 0, "deleted": 0, "processed": 0, "failed": 0}
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        upserted = 0
        deleted = 0
        db_ids: set[int] = set()
        with self._vector_sync_lock:
            for memories in self._storage.get_all_memories_with_embeddings_batched(
                batch_size=batch_size
            ):
                items = []
                for mem in memories:
                    if mem.id is None or mem.embedding is None:
                        continue
                    memory_id = int(mem.id)
                    db_ids.add(memory_id)
                    vector = np.asarray(
                        self._embedding.bytes_to_vector(mem.embedding),
                        dtype=np.float32,
                    )
                    items.append((memory_id, vector, self._vector_metadata(mem)))
                self._vector_store.upsert_many(items)
                upserted += len(items)

            if prune:
                stale_ids = sorted(self._vector_store.list_ids() - db_ids)
                self._vector_store.delete_many(stale_ids)
                deleted = len(stale_ids)

            outbox = self._drain_vector_sync_outbox(limit=max(batch_size, 100))
            self._vector_store_synced = outbox["failed"] == 0

        logger.info(
            "VectorStore reconciled (upserted=%d, deleted=%d, pending_failures=%d)",
            upserted,
            deleted,
            outbox["failed"],
        )
        return {"upserted": upserted, "deleted": deleted, **outbox}

    def _ensure_vector_store_synced(self) -> bool:
        """Lazily backfill a VectorStore and rate-limit retries during outages."""
        if self._vector_store is None:
            return False
        if self._vector_store_synced:
            outbox = self._drain_vector_sync_outbox()
            return outbox["failed"] == 0

        now = time.monotonic()
        if now - self._vector_store_last_sync_attempt < self._VECTOR_SYNC_RETRY_SECONDS:
            return False
        self._vector_store_last_sync_attempt = now
        try:
            result = self.sync_vector_store()
            return result["failed"] == 0
        except Exception:
            logger.warning(
                "VectorStore reconciliation failed; using local retrieval fallback",
                exc_info=True,
            )
            return False

    def store(self, task: str, outcome: str, context: str = "",
              solution: str = "", lessons: str = "",
              source: str = "learn") -> list[int]:
        """Store a learning experience atomically.

        All memory inserts, the interaction record, and the event log are
        wrapped in a single transaction — partial failure rolls everything back.

        ``source`` is persisted on each created Memory for provenance
        (``learn`` for direct experience, e.g. ``extract`` for LLM-extracted
        facts).
        """
        memory_ids = []
        link_pairs = []
        ann_pairs = []  # (memory_id, vector) — avoid re-querying DB later
        transaction_started = False
        try:
            # Normalize inputs — strip system tags, hook output, UI chrome
            if task:
                task = normalize_input(task)
            if solution:
                solution = normalize_input(solution)
            if context:
                context = normalize_input(context)
            if lessons:
                lessons = normalize_input(lessons)

            # Build list of texts to embed in one batch
            texts_to_embed = []
            text_indices = {}  # maps index to name

            if task:
                if solution:
                    content = f"Task: {task}\nSolution: {solution}"
                else:
                    content = f"Task: {task}\n(no solution recorded)"
                text_indices[len(texts_to_embed)] = "task"
                texts_to_embed.append(content)

            if lessons:
                text_indices[len(texts_to_embed)] = "lessons"
                texts_to_embed.append(lessons)

            if context and len(context) > self._MIN_CONTEXT_LENGTH:
                text_indices[len(texts_to_embed)] = "context"
                texts_to_embed.append(context)

            # Single batch embedding call
            if texts_to_embed:
                vecs = self._embedding.embed(texts_to_embed)
            else:
                vecs = []

            # Map vectors back by name
            task_vec = None
            lessons_vec = None
            context_vec = None
            for idx, name in text_indices.items():
                if name == "task":
                    task_vec = vecs[idx]
                elif name == "lessons":
                    lessons_vec = vecs[idx]
                elif name == "context":
                    context_vec = vecs[idx]

            # Remote/CPU embedding and duplicate lookup deliberately happen
            # before BEGIN so a slow provider does not hold a write lock.
            task_embedding_bytes = None
            if task:
                task_embedding_bytes = self._embedding.vector_to_bytes(task_vec)
                if self._deduplicator and self._deduplicator.is_duplicate(
                    content, task_embedding_bytes
                ):
                    logger.info("Skipping duplicate memory: %s...", content[:50])
                    return []

            self._storage.begin()
            transaction_started = True

            # Create experience memory from task (+ solution if available)
            if task:
                mem = Memory(
                    content=content,
                    category="success" if outcome == "success" else "failure",
                    tags=self._extract_tags(task),
                    embedding=task_embedding_bytes,
                    embedder=embedder_identity_of(self._embedding),
                    source=source,
                )
                mid = self._storage.insert_memory(mem)
                memory_ids.append(mid)
                link_pairs.append((mid, content, mem.category))
                ann_pairs.append((mid, task_vec))

            # Create insight memory from lessons
            if lessons_vec is not None:
                mem = Memory(
                    content=lessons,
                    category="insight",
                    tags=self._extract_tags(lessons),
                    embedding=self._embedding.vector_to_bytes(lessons_vec),
                    embedder=embedder_identity_of(self._embedding),
                    source=source,
                )
                mid = self._storage.insert_memory(mem)
                memory_ids.append(mid)
                link_pairs.append((mid, lessons, "insight"))
                ann_pairs.append((mid, lessons_vec))

            # Create context memory if significant
            if context_vec is not None:
                mem = Memory(
                    content=context,
                    category="pattern",
                    tags=self._extract_tags(context),
                    embedding=self._embedding.vector_to_bytes(context_vec),
                    embedder=embedder_identity_of(self._embedding),
                    source=source,
                )
                mid = self._storage.insert_memory(mem)
                memory_ids.append(mid)
                link_pairs.append((mid, context, "pattern"))
                ann_pairs.append((mid, context_vec))

            # Store interaction record
            self._storage.insert_interaction(
                task=task, outcome=outcome, context=context,
                solution=solution, lessons=lessons, memory_ids=memory_ids,
            )

            self._storage.log_event("learn", {"memory_ids": memory_ids, "outcome": outcome})
            self._storage.commit()
            transaction_started = False
            # The database commit is authoritative.  External vector failures
            # remain in the durable outbox and never roll back learned memory.
            self._drain_vector_sync_outbox()
            # Auto-link stored memories
            if self._link and link_pairs:
                try:
                    self._link.auto_link_batch(
                        [mid for mid, _, _ in link_pairs],
                        [text for _, text, _ in link_pairs],
                    )
                except (TypeError, AttributeError):
                    # Programming error in the linking path — still non-fatal
                    # for store(), but loud enough to catch in logs.
                    logger.error("Auto-linking hit a programming error (non-fatal)", exc_info=True)
                except Exception:
                    logger.warning("Auto-linking failed (non-fatal)", exc_info=True)
            # Incrementally add new vectors to existing ANN index
            if self._ann_built and self._ann is not None:
                try:
                    for mid, vec in ann_pairs:
                        self._ann.add_one(mid, vec)
                    logger.debug(
                        "ANN index incrementally updated with %d new vectors",
                        len(ann_pairs),
                    )
                except Exception:
                    self._invalidate_ann()
                    logger.warning("ANN incremental update failed; rebuild required", exc_info=True)
            else:
                self._ann_built = False
            # Populate closet index
            if self._closet and link_pairs:
                try:
                    for mid, text, cat in link_pairs:
                        self._closet.add(memory_id=mid, content=text, category=cat)
                except Exception:
                    logger.warning("Closet index update failed (non-fatal)", exc_info=True)
            logger.info("Stored %d memories (outcome=%s)", len(memory_ids), outcome)
        except Exception:
            if transaction_started:
                try:
                    self._storage.rollback()
                except Exception:
                    logger.warning("Failed to roll back memory transaction", exc_info=True)
            logger.exception("Failed to store memories")
            raise StorageError("Failed to store memories")
        return memory_ids

    def build_index(self, persist: bool = True):
        """Build/rebuild the ANN index from all stored embeddings.

        Call this after bulk inserts or on first recall. Automatically used
        when the index exceeds _ANN_THRESHOLD vectors.

        Args:
            persist: If True (default), save the built index to disk at
                ann_index_path so it survives process restarts.
        """
        memories = self._storage.get_all_memories_with_embeddings()
        if not memories:
            logger.info("No memories with embeddings to index")
            return

        ids = []
        vectors = []
        for mem in memories:
            if mem.embedding is None:
                continue
            ids.append(mem.id)
            vectors.append(self._embedding.bytes_to_vector(mem.embedding))

        if not vectors:
            return

        self._ann = ANNIndex(dim=self._embedding.dim)
        self._ann.add(ids, np.array(vectors, dtype=np.float32))
        self._ann.build()
        self._ann_built = True
        logger.info("ANN index built with %d vectors", len(ids))
        if persist and self._ann_index_path:
            base = self._ann_index_path
            self._ann.save(base)
            self._ann.save_ids_sidecar(base)

    def _invalidate_ann(self):
        """Drop the in-memory ANN and any persisted snapshot (now stale).

        Keeping either around lets _ensure_ann() resurrect an index whose
        contents no longer match the database (e.g. after forget()).
        """
        self._ann_built = False
        self._ann = None
        if self._ann_index_path:
            base = self._ann_index_path.rsplit(".", 1)[0]
            for path in (self._ann_index_path, base + ".ids.npy", base + ".meta.npz"):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    logger.warning("Failed to remove stale ANN snapshot %s", path, exc_info=True)

    @property
    def ann_ready(self):
        """Whether the ANN index is loaded and searchable."""
        return self._ann is not None and self._ann_built

    def search_similar(self, query_vec, top_k=10, threshold=0.0):
        """Public similarity search interface.

        Returns list of (memory_id, cosine_distance). `threshold` is a
        minimum cosine similarity; results below it are filtered out here
        (ANNIndex.search itself takes no threshold).
        """
        if not self._ann_built:
            self.build_index()
        if self._ann is None:
            # Empty store — build_index() found nothing to index.
            return []
        results = self._ann.search(query_vec, top_k)
        if threshold > 0.0:
            results = [(mid, dist) for mid, dist in results if 1.0 - dist >= threshold]
        return results

    def _ensure_ann(self):
        """Lazily build or load the ANN index."""
        if self._ann_built and self._ann is not None:
            return
        # Try loading from disk first
        if self._ann_index_path and self._ann is None:
            self._ann = ANNIndex(dim=self._embedding.dim)
        if self._ann is not None and self._ann.load(self._ann_index_path):
            if self._ann._loaded_without_vectors:
                # hnsw snapshots persist ids only; rebuild the vector buffer
                # from the DB so remove()/build() stay consistent.
                memories = self._storage.get_all_memories_with_embeddings() or []
                ids, vectors = [], []
                for mem in memories:
                    if mem.embedding is None:
                        continue
                    ids.append(mem.id)
                    vectors.append(self._embedding.bytes_to_vector(mem.embedding))
                if ids:
                    self._ann.add(ids, np.array(vectors, dtype=np.float32))
                    self._ann.build()
                else:
                    # Snapshot is stale (DB has nothing to index); drop it.
                    self._invalidate_ann()
                    return
            # load_index() restores the persisted max_elements with no
            # headroom; grow it so incremental add_one() calls fit.
            self._ann.ensure_capacity()
            self._ann_built = True
            logger.info("ANN index loaded from disk (%d vectors)", self._ann.size)
            return
        # Load failed — clear stale ANNIndex so we don't retry on every recall
        self._ann = None
        # Fall back: build from DB
        try:
            stats = self._storage.stats()
            count = stats.get("memories", 0) if isinstance(stats, dict) else 0
        except Exception:
            logger.warning("Failed to get storage stats for ANN threshold check", exc_info=True)
            count = 0
        if count >= self._ANN_THRESHOLD:
            self.build_index()

    def recall(self, query: str, top_k: int = 5,
               recall_weights: tuple = (0.6, 0.15, 0.1, 0.15),
               method: str = "rrf",
               **kwargs) -> list[RecallResult]:
        """Delegate to RetrievalEngine."""
        return self._retrieval.recall(query, top_k, recall_weights, method=method, **kwargs)







    def get_recent_memories(self, days: int = 7, limit: int = 50) -> list[Memory]:
        """Get recent memories for temporal grounding.

        Args:
            days: Number of days to look back.
            limit: Maximum number of memories to return.

        Returns:
            List of recent Memory objects, newest first.
        """
        return self._storage.get_memories_created_after(days, limit)

    def recall_by_time(self, query: str, days: int = 7, top_k: int = 5) -> list[RecallResult]:
        """Delegate to RetrievalEngine."""
        return self._retrieval.recall_by_time(query, days, top_k)

    def forget(self, memory_id: int = None, older_than_days: int = None,
               low_importance: float = None):
        """Forget memories by one or more criteria.

        Args:
            memory_id: Delete a specific memory by ID.
            older_than_days: Delete memories older than N days.
            low_importance: Delete memories with importance below this threshold.
                Range 0.0–1.0, default importance is 0.5.
        """
        self._storage.begin()
        try:
            if memory_id:
                self._storage.delete_memory(memory_id)
            if older_than_days:
                self._storage.delete_memories_older_than(older_than_days)
            if low_importance is not None:
                self._storage.delete_memories_low_importance(low_importance)
            self._storage.log_event("forget", {
                "memory_id": memory_id, "older_than_days": older_than_days,
                "low_importance": low_importance,
            })
            self._storage.commit()
        except Exception:
            self._storage.rollback()
            raise

        self._drain_vector_sync_outbox()
        self._invalidate_ann()

    def reconsolidate(self, memory_id: int, correction: str) -> bool:
        """修正记忆内容，重新计算 embedding 和 tags。

        人脑每次 recall 都在重写记忆。当用户反馈某条记忆过时或错误时，
        调用此方法修正内容，而非删除后重新存储。

        Args:
            memory_id: 要修正的记忆 ID。
            correction: 修正后的记忆内容。

        Returns:
            True if the memory was found and updated, False otherwise.
        """
        mem = self._storage.get_memory_by_id(memory_id)
        if not mem:
            logger.warning("reconsolidate: memory %d not found", memory_id)
            return False

        vec = self._embedding.embed_single(correction)
        new_tags = self._extract_tags(correction)
        embedding_bytes = self._embedding.vector_to_bytes(vec)

        self._storage.begin()
        try:
            self._storage.update_memory_content(memory_id, correction)
            self._storage.update_memory_tags(memory_id, new_tags)
            self._storage.update_memory_embedding(
                memory_id, embedding_bytes, embedder=embedder_identity_of(self._embedding)
            )

            # Reconsolidation signals belief revision — reset lifecycle to seed
            if mem.importance < 0.5:
                self._storage.set_memory_lifecycle(memory_id, "seed")

            self._storage.log_event("reconsolidate", {
                "memory_id": memory_id,
                "old_content": mem.content[:100],
                "new_content": correction[:100],
            })
            self._storage.commit()
        except Exception:
            self._storage.rollback()
            raise

        self._drain_vector_sync_outbox()

        if self._ann_built and self._ann is not None:
            try:
                self._ann.remove({memory_id})
                self._ann.add_one(memory_id, vec)
            except Exception:
                self._invalidate_ann()
                logger.warning(
                    "ANN update during reconsolidate failed; rebuild required",
                    exc_info=True,
                )

        logger.info("Reconsolidated memory %d", memory_id)
        return True

    def suggest(self, context: str, top_k: int = 3,
                min_score: float = 0.3) -> list[RecallResult]:
        """主动记忆：给当前上下文，搜索可能相关的历史教训。

        与 recall() 不同，suggest() 只返回高相关度的结果，
        用于在用户未提问时主动提醒。importance 已通过 recall 权重参与打分。

        Args:
            context: 当前上下文（如当前任务描述、正在编辑的文件等）。
            top_k: 最多返回几条建议。
            min_score: 最低 score 阈值。

        Returns:
            过滤后的 RecallResult 列表。
        """
        candidates = self.recall(context, top_k=top_k * 3)
        results = [r for r in candidates if r.score >= min_score][:top_k]
        return results

    def interference_decay(self, similarity_threshold: float = 0.85,
                           decay_factor: float = 0.8) -> int:
        """干扰模型遗忘：高相似度旧记忆的 importance 衰减。

        人脑遗忘不是因为"不重要"或"太久远"，而是因为相似的新记忆干扰了旧记忆。
        当新旧记忆语义高度相似时，旧记忆的 effective importance 衰减。

        When ANN index is built, uses O(n log n) candidate search instead of
        O(n²) full pairwise matrix.

        Args:
            similarity_threshold: 相似度阈值，超过此值触发衰减。
            decay_factor: 衰减因子，如 0.8 表示 importance 降到 80%。

        Returns:
            受影响的记忆数。
        """
        memories = self._storage.get_all_memories_with_embeddings()
        if len(memories) < 2:
            return 0

        # Build aligned (memory, vector, index) triples.
        # memories ordered by created_at DESC (newest first):
        #   lower index = newer memory, higher index = older memory
        pairs = []
        for mem in memories:
            if mem.embedding is None:
                continue
            vec = np.array(self._embedding.bytes_to_vector(mem.embedding), dtype=np.float32)
            pairs.append((mem, vec))

        if len(pairs) < 2:
            return 0

        # created_at has second precision and the storage ORDER BY has no id
        # tiebreaker (the query is shared); enforce a deterministic
        # newest-first order here so "older" (higher index) is well-defined.
        pairs.sort(key=lambda p: (str(p[0].created_at or ""), p[0].id or 0), reverse=True)

        affected = set()

        # Path 1: ANN candidate search — O(n log n)
        if self._ann_built and self._ann is not None and self._ann.size > 0:
            # Build id→(index, mem) lookup for O(1) position check
            id_to_idx: dict[int, tuple[int, object]] = {}
            for idx, (m, _) in enumerate(pairs):
                id_to_idx[m.id] = (idx, m)

            for i, (mem, vec) in enumerate(pairs):
                candidates = self._ann.search(vec, top_k=20)
                for cand_id, dist in candidates:
                    if cand_id not in id_to_idx:
                        continue
                    sim = 1.0 - dist
                    if sim >= similarity_threshold:
                        j, other_mem = id_to_idx[cand_id]
                        if j > i:
                            new_imp = max(0.1, other_mem.importance * decay_factor)
                            if new_imp < other_mem.importance:
                                self._storage.update_memory_importance(other_mem.id, new_imp)
                                affected.add(other_mem.id)
        else:
            # Path 2: Full pairwise scan — O(n²) time, but the similarity
            # matrix is computed in row blocks so memory stays bounded
            # (a full n×n float32 matrix needs ~10GB at 50k memories).
            vec_matrix = np.stack([v for _, v in pairs])
            norms = np.linalg.norm(vec_matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            normalized = vec_matrix / norms

            n = len(pairs)
            chunk = 1024
            for start in range(0, n, chunk):
                end = min(start + chunk, n)
                sim_block = np.dot(normalized[start:end], normalized.T)
                for i in range(start, end):
                    row = sim_block[i - start]
                    for j in range(i + 1, n):
                        if row[j] >= similarity_threshold:
                            older_mem = pairs[j][0]
                            new_imp = max(0.1, older_mem.importance * decay_factor)
                            if new_imp < older_mem.importance:
                                self._storage.update_memory_importance(older_mem.id, new_imp)
                                affected.add(older_mem.id)

        if affected:
            self._storage.log_event("interference_decay", {
                "affected_count": len(affected),
                "threshold": similarity_threshold,
                "decay_factor": decay_factor,
            })
            logger.info("Interference decay affected %d memories", len(affected))
        return len(affected)

    def update_lifecycle(self) -> dict:
        """Scan all memories, auto-migrate lifecycle stages.

        Rules:
        - seed -> growing: access_count >= 2
        - growing -> evergreen: importance >= 0.8 and age >= 30 days
        - growing -> seed: importance dropped below 0.3
        - evergreen -> growing: importance eroded below 0.5
        - any -> stale: 90 days unrecalled and importance < 0.5
        - stale stays stale until reactivated by recall()

        Returns: {transitioned: int, by_type: {from_to: count}, distribution: {stage: count}}
        """
        from datetime import datetime, timezone

        self._storage.begin()
        try:
            memories = self._storage.get_all_memories_columns([
                "id", "lifecycle", "created_at", "importance", "access_count"
            ])
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            transitions: dict[str, int] = {}
            distribution = {"seed": 0, "growing": 0, "evergreen": 0, "stale": 0}
            pending: list[tuple[str, int]] = []

            for m in memories:
                current = m.lifecycle or "seed"
                if current == "distilled":
                    distribution["distilled"] = distribution.get("distilled", 0) + 1
                    continue
                new_lifecycle = current

                age_days = 0
                if m.created_at:
                    try:
                        created = datetime.fromisoformat(str(m.created_at))
                        if created.tzinfo is not None:
                            created = created.astimezone(timezone.utc).replace(tzinfo=None)
                        age_days = (now - created).days
                    except (ValueError, TypeError):
                        pass

                # Data-driven transition rules (sorted by priority desc)
                importance = m.importance or 0
                access_count = m.access_count or 0
                for rule in self._lifecycle_rules:
                    if rule.from_stage is not None and current != rule.from_stage:
                        continue
                    if not (rule.min_age_days <= age_days <= rule.max_age_days):
                        continue
                    if not (rule.min_importance <= importance <= rule.max_importance):
                        continue
                    if not (rule.min_access_count <= access_count <= rule.max_access_count):
                        continue
                    new_lifecycle = rule.to_stage
                    break

                if new_lifecycle != current:
                    key = f"{current}_to_{new_lifecycle}"
                    transitions[key] = transitions.get(key, 0) + 1
                    pending.append((new_lifecycle, m.id))

                distribution[new_lifecycle] = distribution.get(new_lifecycle, 0) + 1

            if pending:
                self._storage.set_memory_lifecycle_batch(pending)

            self._storage.commit()
            return {
                "transitioned": len(pending),
                "by_type": transitions,
                "distribution": distribution,
            }
        except Exception:
            self._storage.rollback()
            raise

    def _extract_tags(self, text: str) -> list[str]:
        """Keyword extraction via shared tokenizer."""
        from evolver.utils import tokenize
        return tokenize(text, min_len=2, stopwords=STOPWORDS,
                       max_items=self._MAX_TAGS,
                       english_pattern=r'[a-zA-Z][a-zA-Z0-9_]{1,}')

