import logging
import numpy as np
from collections import defaultdict

from evolver.utils import cosine_similarity, embedder_identity_of, embedder_tags_compatible

logger = logging.getLogger(__name__)


class Deduplicator:
    """Near-duplicate detection using cosine distance.

    Groups memories by category, keeps longest version when
    cosine distance < threshold.

    When an ANN index is available (via get_ann callback), both dedup() and
    is_duplicate() use it to shortlist candidates (exact cosine distance
    still decides every verdict); otherwise they fall back to an O(n)
    linear scan. The ANN path is approximate: a fixed-size shortlist can
    miss a kept same-category neighbor when foreign categories crowd it
    out, so a verdict may differ from the linear path on adversarial
    distributions. The linear path is the exact reference.
    """

    def __init__(self, storage, embedding, threshold: float = 0.15,
                 get_ann=None):
        self._storage = storage
        self._embedding = embedding
        self._threshold = threshold
        self._get_ann = get_ann  # callable that returns ANNIndex | None

    def _dedup_ann(self, memories, ann, dry_run):
        """ANN-assisted dedup: ANN shortlists candidates, cosine verifies.

        Same grouping and longest-first order as _dedup_linear, but the
        per-item scan is replaced by a fixed top_k=10 ANN shortlist. When
        the shortlist contains no kept id (deleted or foreign-category
        entries crowded it out), one wider re-query runs before giving
        up. This path is approximate: verdicts may differ from the exact
        linear path.
        """
        groups = defaultdict(list)
        for mem in memories:
            groups[mem.category].append(mem)

        total_kept = 0
        total_deleted = 0

        for cat, cat_memories in groups.items():
            cat_memories.sort(key=lambda m: len(m.content), reverse=True)
            kept_vectors = []

            for mem in cat_memories:
                if mem.embedding is None:
                    continue
                vec = np.array(self._embedding.bytes_to_vector(mem.embedding), dtype=np.float32)
                is_dup = False
                if kept_vectors:
                    candidate_ids = {mid for mid, _ in ann.search(vec, top_k=10)}
                    kept_ids = {kept_mem.id for kept_mem, _ in kept_vectors}
                    relevant = candidate_ids & kept_ids
                    if not relevant and ann.size > 10:
                        # Shortlist crowded out by deleted/foreign-category
                        # entries; one wider re-query before giving up.
                        wider = {mid for mid, _ in ann.search(vec, top_k=min(ann.size, 50))}
                        relevant = wider & kept_ids
                    for kept_mem, kept_vec in kept_vectors:
                        if kept_mem.id not in relevant:
                            continue
                        if not embedder_tags_compatible(mem.embedder, kept_mem.embedder):
                            continue
                        dist = 1.0 - cosine_similarity(vec, kept_vec)
                        if dist < self._threshold:
                            is_dup = True
                            break
                if is_dup:
                    total_deleted += 1
                    if not dry_run:
                        self._storage.delete_memory(mem.id)
                        logger.debug("Deleted duplicate memory %d (cat=%s)", mem.id, cat)
                else:
                    kept_vectors.append((mem, vec))
                    total_kept += 1

        return total_kept, total_deleted

    def _dedup_linear(self, memories, dry_run):
        """Linear scan dedup (fallback when ANN unavailable).

        Exact reference implementation. Each candidate is compared against
        every kept vector in one batched dot product (numerics match
        utils.cosine_similarity: float64, zero norm -> similarity 0).
        """
        groups = defaultdict(list)
        for mem in memories:
            groups[mem.category].append(mem)

        total_kept = 0
        total_deleted = 0

        for cat, cat_memories in groups.items():
            cat_memories.sort(key=lambda m: len(m.content), reverse=True)
            kept_buf = np.empty(
                (len(cat_memories), self._embedding.dim), dtype=np.float64
            )
            n_kept = 0
            kept_tags = []

            for mem in cat_memories:
                if mem.embedding is None:
                    continue
                vec = np.array(
                    self._embedding.bytes_to_vector(mem.embedding), dtype=np.float64
                )
                is_dup = False
                if n_kept:
                    buf = kept_buf[:n_kept]
                    denom = np.linalg.norm(buf, axis=1) * np.linalg.norm(vec)
                    sims = np.divide(
                        buf @ vec, denom,
                        out=np.zeros(n_kept, dtype=np.float64),
                        where=denom != 0,
                    )
                    # Cross-embedder pairs never compare; untagged legacy
                    # rows compare with everything.
                    compat = np.array(
                        [embedder_tags_compatible(mem.embedder, tag) for tag in kept_tags],
                        dtype=bool,
                    )
                    is_dup = bool(np.any((1.0 - sims < self._threshold) & compat))
                if is_dup:
                    total_deleted += 1
                    if not dry_run:
                        self._storage.delete_memory(mem.id)
                        logger.debug("Deleted duplicate memory %d (cat=%s)", mem.id, cat)
                else:
                    kept_buf[n_kept] = vec
                    n_kept += 1
                    total_kept += 1
                    kept_tags.append(mem.embedder)

        return total_kept, total_deleted

    def dedup(self, category: str = None, dry_run: bool = True) -> tuple[int, int]:
        """Find and optionally remove near-duplicate memories.

        Fetch is batched (1000 rows per round-trip) so large stores do not
        materialize one giant SQL result; grouping still spans all batches.
        """
        memories = []
        for batch in self._storage.get_all_memories_with_embeddings_batched(
            batch_size=1000, category=category
        ):
            memories.extend(batch)
        if not memories:
            return 0, 0

        ann = self._get_ann() if self._get_ann else None
        if ann is not None and ann.size > 0:
            total_kept, total_deleted = self._dedup_ann(memories, ann, dry_run)
        else:
            total_kept, total_deleted = self._dedup_linear(memories, dry_run)

        if not dry_run and total_deleted > 0:
            self._storage.log_event("dedup", {
                "kept": total_kept, "deleted": total_deleted, "category": category,
            })
            logger.info("Dedup: kept=%d, deleted=%d", total_kept, total_deleted)

        return total_kept, total_deleted

    def is_duplicate(self, content: str, embedding_bytes: bytes,
                     category: str = None) -> bool:
        """Check if content is a near-duplicate of existing memories.

        Uses ANN index for candidate search when available (O(log n)),
        falls back to linear scan (O(n)).
        """
        new_vec = np.array(self._embedding.bytes_to_vector(embedding_bytes), dtype=np.float32)

        # Path 1: ANN candidate search — fast O(log n)
        ann = self._get_ann() if self._get_ann else None
        if ann is not None and ann.size > 0:
            candidates = ann.search(new_vec, top_k=10)
            if candidates:
                candidate_ids = [mid for mid, _ in candidates]
                candidate_mems = self._storage.get_memories_by_ids(candidate_ids)
                for mem in candidate_mems:
                    if mem.embedding is None:
                        continue
                    # Match the linear path: restrict to the requested category.
                    if category is not None and mem.category != category:
                        continue
                    if not embedder_tags_compatible(mem.embedder, embedder_identity_of(self._embedding)):
                        continue
                    mem_vec = np.array(self._embedding.bytes_to_vector(mem.embedding), dtype=np.float32)
                    dist = 1.0 - cosine_similarity(new_vec, mem_vec)
                    if dist < self._threshold:
                        logger.debug("Duplicate detected (ANN): dist=%.4f vs memory %d", dist, mem.id)
                        return True
                return False

        # Path 2: Linear scan fallback
        memories = self._storage.get_all_memories_with_embeddings(category=category)
        for mem in memories:
            if mem.embedding is None:
                continue
            if not embedder_tags_compatible(mem.embedder, embedder_identity_of(self._embedding)):
                continue
            mem_vec = np.array(self._embedding.bytes_to_vector(mem.embedding), dtype=np.float32)
            dist = 1.0 - cosine_similarity(new_vec, mem_vec)
            if dist < self._threshold:
                logger.debug("Duplicate detected (linear): dist=%.4f vs memory %d", dist, mem.id)
                return True
        return False
