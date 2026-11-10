import logging
import numpy as np
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import hnswlib
    _HAS_HNSWLIB = True
except ImportError:
    _HAS_HNSWLIB = False


class ANNIndex:
    """Approximate nearest neighbor index for memory embeddings.

    Uses hnswlib if available (fast, scales to millions), Otherwise falls back
    to brute-force numpy cosine search (fine for <50k vectors). Supports
    persistence to disk so the index survives process restarts.
    """

    def __init__(self, dim: int = 1024, use_hnsw: Optional[bool] = None):
        self._dim = dim
        self._ids: list[int] = []
        self._vectors: Optional[np.ndarray] = None  # (N, dim) float32
        self._dirty = True
        # Set by load() when only ids were restored (hnsw snapshots carry no
        # raw vector buffer); cleared by a full re-add via add().
        self._loaded_without_vectors = False
        # Ids logically removed while _loaded_without_vectors (search filters).
        self._deleted: set[int] = set()

        # Auto-detect: use hnswlib if available and caller didn't say no
        if use_hnsw is None:
            self._use_hnsw = _HAS_HNSWLIB
        else:
            self._use_hnsw = use_hnsw and _HAS_HNSWLIB

        self._hnsw_index = None
        self._hnsw_inited = False
        if self._use_hnsw:
            self._init_hnsw()

    def _init_hnsw(self):
        self._hnsw_index = hnswlib.Index(space="cosine", dim=self._dim)
        # Will be populated on first build
        self._hnsw_inited = False

    def add(self, ids: list[int], vectors: np.ndarray):
        """Add vectors with associated IDs. Call build() after all adds."""
        if self._loaded_without_vectors:
            # A full re-add supersedes the id-only state restored by load();
            # drop the loaded hnsw index whose labels no longer align.
            self._ids = []
            self._vectors = None
            self._deleted = set()
            self._loaded_without_vectors = False
            if self._use_hnsw:
                self._init_hnsw()
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        self._ids.extend(ids)
        if self._vectors is None:
            self._vectors = vectors.astype(np.float32)
        else:
            self._vectors = np.vstack([self._vectors, vectors.astype(np.float32)])
        self._dirty = True

    def add_one(self, memory_id: int, vector: np.ndarray):
        """Add a single vector. If index is already built, adds incrementally (no rebuild)."""
        if self._loaded_without_vectors:
            # No vector buffer to stage into; record the id and let the
            # caller's full re-add (add()) rebuild from source data.
            self._ids.append(memory_id)
            self._dirty = True
            return
        vec = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        # Add to internal buffer
        self._ids.append(memory_id)
        if self._vectors is None:
            self._vectors = vec
        else:
            self._vectors = np.vstack([self._vectors, vec])
        # If hnswlib index is already built, add directly (immediately searchable)
        if self._use_hnsw and self._hnsw_inited and self._hnsw_index is not None:
            if self._dirty:
                # Buffer diverged from the built index (e.g. after remove());
                # rebuild so the incremental add lands on a consistent index.
                self.build()
            else:
                new_idx = np.array([len(self._ids) - 1], dtype=np.int64)
                self._hnsw_index.add_items(vec, new_idx)
        else:
            self._dirty = True

    def build(self):
        """Build/rebuild the index. Must be called after add() and before search()."""
        if self._loaded_without_vectors:
            # Cannot rebuild without vectors; the owning MemoryEngine rebuilds
            # via add() with the full DB vector set instead.
            logger.debug("build() skipped: index loaded without vectors")
            return
        if not self._ids:
            return
        if self._use_hnsw and self._hnsw_index is not None:
            if self._hnsw_inited:
                # hnswlib raises RuntimeError on re-init of a live Index;
                # rebuild into a fresh object instead.
                self._init_hnsw()
            n = len(self._ids)
            max_elements = max(n, 1000)
            self._hnsw_index.init_index(
                max_elements=max_elements,
                ef_construction=200,
                M=16,
            )
            self._hnsw_index.add_items(
                self._vectors, np.arange(n, dtype=np.int64)
            )
            self._hnsw_index.set_ef(50)
            self._hnsw_inited = True
            logger.debug("HNSW index built with %d vectors", n)
        else:
            logger.debug("Brute-force index ready with %d vectors", len(self._ids))
        self._dirty = False

    def save(self, path: str):
        """Persist index to disk. hnswlib uses .bin; brute-force uses .npz.

        Writes go through a temp file + os.replace so concurrent readers
        never observe a torn snapshot.
        """
        if not self._ids:
            return
        if self._loaded_without_vectors:
            # No vector buffer to persist; keep the on-disk index untouched
            # and refresh only the ids sidecar.
            self.save_ids_sidecar(path)
            return
        self._dirty and self.build()
        dir_ = os.path.dirname(path) or "."
        os.makedirs(dir_, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=dir_
        )
        try:
            if self._use_hnsw and self._hnsw_inited:
                os.close(fd)
                self._hnsw_index.save_index(tmp)
            else:
                # File object, not a path: np.savez* would otherwise append
                # ".npz" and load(path) would never find the snapshot.
                with os.fdopen(fd, "wb") as fh:
                    np.savez_compressed(
                        fh,
                        ids=np.array(self._ids, dtype=np.int64),
                        vectors=self._vectors,
                    )
                    fh.flush()
                    os.fsync(fh.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        if self._use_hnsw and self._hnsw_inited:
            logger.info("HNSW index saved to %s (%d vectors)", path, len(self._ids))
        else:
            logger.info("Brute-force index saved to %s (%d vectors)", path, len(self._ids))

    def load(self, path: str) -> bool:
        """Load index from disk. Returns True if loaded, False if file missing or incompatible."""
        if not os.path.exists(path):
            return False
        self.clear()
        if self._use_hnsw:
            try:
                self._hnsw_index.load_index(path)
                # hnswlib doesn't expose element count directly; infer from file
                # After load, we need ids list — read from companion .ids.npy if available
                ids_path = path.rsplit(".", 1)[0] + ".ids.npy"
                if os.path.exists(ids_path):
                    self._ids = np.load(ids_path, allow_pickle=True).tolist()
                else:
                    # Fall back: rebuild ids from stored metadata in a sidecar file
                    meta_path = path.rsplit(".", 1)[0] + ".meta.npz"
                    if os.path.exists(meta_path):
                        meta = np.load(meta_path)
                        self._ids = meta["ids"].tolist()
                        dim = meta.get("dim", self._dim)
                        if dim != self._dim:
                            logger.warning(
                                "Loaded index dim=%d but client expects %d; will rebuild on mismatch",
                                dim, self._dim,
                            )
                            # Re-init HNSW to match expected dim before returning False
                            self._init_hnsw()
                            return False
                self._hnsw_inited = True
                # Index is consistent with _ids; don't trigger a rebuild from
                # the (empty after load) vector buffer on the next add_one.
                self._dirty = False
                self._loaded_without_vectors = True
                logger.info("HNSW index loaded from %s", path)
                return True
            except Exception as e:
                logger.warning("Failed to load HNSW index from %s: %s — will rebuild", path, e)
                self._init_hnsw()
                return False
        else:
            try:
                npz = np.load(path, allow_pickle=True)
                self._ids = npz["ids"].tolist()
                self._vectors = npz["vectors"].astype(np.float32)
                self._dirty = False
                logger.info("Brute-force index loaded from %s (%d vectors)", path, len(self._ids))
                return True
            except Exception as e:
                logger.warning("Failed to load index from %s: %s", path, e)
                return False

    def ensure_capacity(self):
        """Grow a loaded hnswlib index so incremental add_one() calls fit.

        load_index() restores the persisted max_elements (saved as
        max(n, 1000)), which leaves zero headroom once n >= 1000.
        """
        if not (self._use_hnsw and self._hnsw_inited and self._hnsw_index is not None):
            return
        n = len(self._ids)
        self._hnsw_index.resize_index(max(n * 2, n + 1000))

    def save_ids_sidecar(self, base_path: str):
        """Save ids array alongside the main index file."""
        dir_ = os.path.dirname(base_path)
        if dir_:
            os.makedirs(dir_, exist_ok=True)
        # Save as both .ids.npy (simple) and .meta.npz (with extra info)
        ids_arr = np.array(self._ids, dtype=np.int64)
        np.save(base_path.rsplit(".", 1)[0] + ".ids.npy", ids_arr)
        np.savez_compressed(
            base_path.rsplit(".", 1)[0] + ".meta.npz",
            ids=ids_arr,
            dim=self._dim,
        )

    def search(self, query: np.ndarray, top_k: int = 5) -> list[tuple[int, float]]:
        """Search for nearest neighbors. Returns list of (memory_id, distance).

        Distance is cosine distance (0 = identical, 2 = opposite).
        """
        if not self._ids:
            return []
        if self._dirty:
            self.build()

        if query.ndim == 1:
            query = query.reshape(1, -1)
        query = query.astype(np.float32)

        if self._use_hnsw and self._hnsw_inited:
            # knn_query raises when k exceeds the live (non-deleted) count.
            k = min(top_k, len(self._ids) - len(self._deleted))
            if k <= 0:
                return []
            labels, distances = self._hnsw_index.knn_query(query, k=k)
            results = []
            for idx, dist in zip(labels[0], distances[0]):
                if idx < 0:  # hnswlib pads with -1 when too few live elements
                    continue
                if self._ids[idx] in self._deleted:
                    continue
                results.append((self._ids[idx], float(dist)))
            return results
        else:
            return self._brute_force_search(query[0], top_k)

    def _brute_force_search(self, query: np.ndarray, top_k: int) -> list[tuple[int, float]]:
        """Brute-force cosine similarity search."""
        if self._vectors is None:
            return []
        # Normalize
        query_norm = query / (np.linalg.norm(query) + 1e-10)
        vecs = self._vectors
        vecs_norm = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10)
        similarities = vecs_norm @ query_norm
        # Convert to distance (1 - sim) for consistency with hnswlib
        distances = 1.0 - similarities

        k = min(top_k, len(self._ids))
        if k == 0:
            return []
        # argpartition kth is 0-based; when k == len, use k-1
        top_indices = np.argpartition(distances, k - 1)[:k]
        top_indices = top_indices[np.argsort(distances[top_indices])]

        results = []
        for idx in top_indices:
            if self._ids[idx] in self._deleted:
                continue
            results.append((self._ids[idx], float(distances[idx])))
        return results

    def remove(self, ids_to_remove: set[int]):
        """Remove vectors by ID. Requires rebuild."""
        if not ids_to_remove:
            return
        if self._loaded_without_vectors:
            # No vector buffer to mask; mark deleted inside hnsw (labels stay
            # aligned with _ids) and track the ids for search filtering.
            for pos, mid in enumerate(self._ids):
                if mid in ids_to_remove:
                    self._deleted.add(mid)
                    if self._use_hnsw and self._hnsw_inited and self._hnsw_index is not None:
                        try:
                            self._hnsw_index.mark_deleted(pos)
                        except Exception:
                            logger.debug("hnsw mark_deleted failed for %s", mid, exc_info=True)
            return
        keep_mask = np.array([i not in ids_to_remove for i in self._ids])
        if not keep_mask.any():
            self._ids = []
            self._vectors = None
            self._dirty = True
            return
        self._ids = [id_ for id_, keep in zip(self._ids, keep_mask) if keep]
        self._vectors = self._vectors[keep_mask]
        self._dirty = True

    @property
    def size(self) -> int:
        return len(self._ids) - len(self._deleted)

    def clear(self):
        self._ids = []
        self._vectors = None
        self._dirty = True
        self._loaded_without_vectors = False
        self._deleted = set()
        self._hnsw_inited = False
        if self._use_hnsw:
            self._init_hnsw()
