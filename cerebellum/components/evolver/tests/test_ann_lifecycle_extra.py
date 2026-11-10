# tests/test_ann_lifecycle_extra.py
"""Regression tests for ANN lifecycle bugs:

- MemoryEngine.search_similar() passed a 3rd arg to ANNIndex.search (TypeError,
  swallowed by store()'s broad auto-link catch -> similarity linking never ran).
- ANNIndex.build() crashed on rebuild (hnswlib Index cannot be re-initialized)
  and add_one() wrote into a stale index after remove().
- forget()/store() invalidation kept the stale ANN + persisted snapshot, so
  forgotten ids resurrected on the next recall; loaded hnsw indexes had zero
  capacity headroom, causing an invalidate->reload-stale loop.
- search_similar() on an empty store raised AttributeError.
- interference_decay() used a full n x n similarity matrix (now chunked).
"""
import hashlib
import os

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from evolver.ann_index import ANNIndex, _HAS_HNSWLIB
from evolver.link import LinkEngine
from evolver.memory import MemoryEngine
from evolver.models import Memory


class FakeEmbedding:
    """Deterministic, offline embedding client (dim configurable)."""

    def __init__(self, dim: int = 16):
        self.dim = dim
        self._map: dict[str, np.ndarray] = {}

    def set(self, text: str, vec) -> None:
        self._map[text] = np.asarray(vec, dtype=np.float32)

    def _vec_for(self, text: str) -> np.ndarray:
        if text not in self._map:
            seed = int.from_bytes(hashlib.md5(text.encode()).digest()[:4], "little")
            self._map[text] = np.random.default_rng(seed).random(self.dim).astype(np.float32)
        return self._map[text]

    def embed(self, texts):
        return [self._vec_for(t).tolist() for t in texts]

    def embed_single(self, text):
        return self._vec_for(text).tolist()

    def vector_to_bytes(self, vec) -> bytes:
        return np.asarray(vec, dtype=np.float32).tobytes()

    def bytes_to_vector(self, b: bytes):
        return np.frombuffer(b, dtype=np.float32).tolist()


def make_engine(tmp_path, dim: int = 16):
    storage = MagicMock()
    embedding = FakeEmbedding(dim=dim)
    engine = MemoryEngine(storage, embedding, ann_index_path=str(tmp_path / "test.ann"))
    return engine, storage, embedding


def make_memory(mid: int, embedding: FakeEmbedding, vec, created_at="2026-01-01T00:00:00"):
    return Memory(
        id=mid,
        content=f"memory {mid}",
        category="success",
        embedding=embedding.vector_to_bytes(vec),
        created_at=created_at,
    )


# --- search_similar on empty store -----------------------------------------


def test_search_similar_empty_store_returns_empty_list(tmp_path):
    engine, storage, emb = make_engine(tmp_path)
    storage.get_all_memories_with_embeddings.return_value = []

    # Previously raised AttributeError: NoneType has no attribute 'search'
    assert engine.search_similar(np.zeros(emb.dim, dtype=np.float32)) == []


# --- auto-link with a built ANN ---------------------------------------------


def test_auto_link_with_built_ann_produces_links(tmp_path, caplog):
    engine, storage, emb = make_engine(tmp_path)

    # One pre-existing memory already in the (built) ANN index.
    base_vec = np.full(emb.dim, 0.5, dtype=np.float32)
    storage.get_all_memories_with_embeddings.return_value = [
        make_memory(1, emb, base_vec),
    ]
    engine.build_index()
    assert engine.ann_ready

    # Wire a real LinkEngine; skip entity linking.
    graph = MagicMock()
    graph._extract_entities.return_value = []
    engine._link = LinkEngine(storage, emb, engine, graph)

    # New lessons text embeds to a near-identical vector (cosine sim ~1).
    lessons = "always validate input before writing"
    emb.set(lessons, base_vec + 0.001)
    storage.insert_memory.side_effect = [10, 11]
    storage.insert_links_batch.return_value = 2

    with caplog.at_level("WARNING", logger="evolver.memory"):
        ids = engine.store(
            task="fix bug",
            outcome="success",
            solution="added validation",
            lessons=lessons,
        )

    assert ids == [10, 11]
    # The TypeError from search_similar used to be swallowed here, so no
    # links were ever created once the ANN was built.
    assert storage.insert_links_batch.call_count >= 1
    batches = [call.args[0] for call in storage.insert_links_batch.call_args_list]
    flat = [link for batch in batches for link in batch]
    assert ("memory", 11, "memory", 1, "auto_similar", pytest.approx(1.0, abs=1e-3)) in flat or any(
        link[0] == "memory" and link[1] == 11 and link[2] == "memory" and link[3] == 1
        and link[4] == "auto_similar" and link[5] >= 0.6
        for link in flat
    )
    assert not [r for r in caplog.records if "Auto-linking" in r.getMessage()]


def test_auto_link_operational_error_stays_warning(tmp_path, caplog):
    """Non-programming auto-link failures keep the old warning-level behavior."""
    engine, storage, emb = make_engine(tmp_path)
    graph = MagicMock()
    link = MagicMock()
    link.auto_link_batch.side_effect = OSError("disk full")
    engine._link = link
    storage.insert_memory.side_effect = [10, 11]

    with caplog.at_level("WARNING", logger="evolver.memory"):
        engine.store(task="t", outcome="success", solution="s", lessons="l")

    warnings = [r for r in caplog.records if r.levelname == "WARNING"
                and "Auto-linking failed" in r.getMessage()]
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(warnings) == 1
    assert not errors


def test_auto_link_programming_error_logged_at_error(tmp_path, caplog):
    """TypeError/AttributeError in the link path must be loud (error level)."""
    engine, storage, emb = make_engine(tmp_path)
    link = MagicMock()
    link.auto_link_batch.side_effect = TypeError("boom")
    engine._link = link
    storage.insert_memory.side_effect = [10, 11]

    with caplog.at_level("WARNING", logger="evolver.memory"):
        engine.store(task="t", outcome="success", solution="s", lessons="l")

    errors = [r for r in caplog.records if r.levelname == "ERROR"
              and "Auto-linking" in r.getMessage()]
    assert len(errors) == 1


# --- ANNIndex rebuild / remove / add_one ------------------------------------


@pytest.mark.parametrize("use_hnsw", [
    False,
    pytest.param(True, marks=pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")),
])
def test_remove_then_search_rebuilds(use_hnsw):
    rng = np.random.default_rng(7)
    vecs = rng.random((4, 16)).astype(np.float32)
    idx = ANNIndex(dim=16, use_hnsw=use_hnsw)
    idx.add([1, 2, 3, 4], vecs)
    idx.build()

    idx.remove({2})
    # Old hnsw path crashed here with RuntimeError('The index is already initiated.')
    results = idx.search(vecs[1], top_k=4)

    assert idx.size == 3
    assert all(mid != 2 for mid, _ in results)
    # Every surviving vector still self-matches at ~zero distance.
    for mid, vec in zip([1, 3, 4], [vecs[0], vecs[2], vecs[3]]):
        top = idx.search(vec, top_k=1)
        assert top[0][0] == mid
        assert top[0][1] < 1e-3


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_add_one_after_remove_rebuilds_stale_hnsw():
    rng = np.random.default_rng(11)
    vecs = rng.random((3, 16)).astype(np.float32)
    idx = ANNIndex(dim=16)
    idx.add([1, 2, 3], vecs)
    idx.build()

    idx.remove({2})
    new_vec = rng.random(16).astype(np.float32)
    # Old code wrote into the stale hnsw index (checked _hnsw_inited, not _dirty).
    idx.add_one(4, new_vec)

    assert idx.size == 3
    for mid, vec in [(1, vecs[0]), (3, vecs[2]), (4, new_vec)]:
        top = idx.search(vec, top_k=1)
        assert top[0][0] == mid
        assert top[0][1] < 1e-3


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_second_build_recreates_hnsw_index():
    rng = np.random.default_rng(13)
    idx = ANNIndex(dim=16)
    idx.add([1, 2], rng.random((2, 16)).astype(np.float32))
    idx.build()
    first = idx._hnsw_index
    idx.build()  # old code: RuntimeError('The index is already initiated.')
    assert idx._hnsw_index is not first
    assert idx.search(rng.random(16).astype(np.float32), top_k=1)


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_ensure_capacity_after_load_allows_incremental_growth(tmp_path):
    rng = np.random.default_rng(17)
    path = str(tmp_path / "cap.ann")
    idx = ANNIndex(dim=16)
    idx.add([1, 2, 3], rng.random((3, 16)).astype(np.float32))
    idx.build()
    idx.save(path)
    idx.save_ids_sidecar(path)

    loaded = ANNIndex(dim=16)
    assert loaded.load(path)
    loaded.ensure_capacity()

    # Persisted max_elements was max(3, 1000) == 1000; growing to 1003 total
    # exceeds it, so this requires the resize done by ensure_capacity().
    for mid in range(100, 1100):
        loaded.add_one(mid, rng.random(16).astype(np.float32))
    assert loaded.size == 3 + 1000


def test_ensure_capacity_noop_on_brute_force():
    idx = ANNIndex(dim=8, use_hnsw=False)
    idx.add([1], np.ones((1, 8), dtype=np.float32))
    idx.build()
    idx.ensure_capacity()  # must not raise
    assert idx.size == 1


# --- forget() must not resurrect forgotten ids -------------------------------


def test_forget_invalidates_ann_and_snapshot(tmp_path):
    engine, storage, emb = make_engine(tmp_path)
    rng = np.random.default_rng(23)
    vecs = {mid: rng.random(emb.dim).astype(np.float32) for mid in (1, 2, 3)}
    storage.get_all_memories_with_embeddings.return_value = [
        make_memory(mid, emb, vecs[mid]) for mid in (1, 2, 3)
    ]
    engine.build_index()
    snapshot = tmp_path / "test.ann"
    assert engine.ann_ready and snapshot.exists()

    engine.forget(memory_id=2)

    assert engine._ann is None
    assert not engine._ann_built
    assert not snapshot.exists(), "stale persisted snapshot must be removed"

    # DB now reflects the deletion; force the rebuild path in _ensure_ann.
    storage.get_all_memories_with_embeddings.return_value = [
        make_memory(mid, emb, vecs[mid]) for mid in (1, 3)
    ]
    storage.stats.return_value = {"memories": engine._ANN_THRESHOLD}

    engine._ensure_ann()
    assert engine.ann_ready
    results = engine.search_similar(vecs[2], top_k=5)
    assert results, "rebuilt index should answer queries"
    assert all(mid != 2 for mid, _ in results), "forgotten id resurrected"


def test_store_ann_add_failure_drops_stale_ann(tmp_path):
    engine, storage, emb = make_engine(tmp_path)
    rng = np.random.default_rng(29)
    storage.get_all_memories_with_embeddings.return_value = [
        make_memory(1, emb, rng.random(emb.dim).astype(np.float32)),
    ]
    engine.build_index()
    assert engine.ann_ready
    (tmp_path / "test.ann").exists()

    # Make incremental add_one blow up (operational failure).
    engine._ann.add_one = MagicMock(side_effect=RuntimeError("capacity"))
    storage.insert_memory.side_effect = [10, 11]

    engine.store(task="t", outcome="success", solution="s", lessons="l")

    assert engine._ann is None
    assert not engine._ann_built


# --- interference_decay chunking ---------------------------------------------


def test_interference_decay_chunked_matches_brute_force_reference(tmp_path):
    dim = 16
    n = 1030  # > 1024-row chunk so chunking actually kicks in
    rng = np.random.default_rng(31)

    centers = rng.random((10, dim)).astype(np.float32)
    vecs = np.stack([
        centers[i % 10] + 0.02 * rng.random(dim).astype(np.float32)
        for i in range(n)
    ])

    engine, storage, emb = make_engine(tmp_path, dim=dim)
    # Same created_at for all: exercises the (created_at, id) tiebreak sort.
    mems = [make_memory(i + 1, emb, vecs[i]) for i in range(n)]
    storage.get_all_memories_with_embeddings.return_value = mems
    engine._ann_built = False  # force the pairwise path
    engine._ann = None

    threshold, factor = 0.9, 0.8
    affected = engine.interference_decay(similarity_threshold=threshold, decay_factor=factor)

    # Brute-force reference over the full (unchunked) similarity matrix,
    # with the same deterministic newest-first ordering.
    order = sorted(range(n), key=lambda i: ("2026-01-01T00:00:00", i + 1), reverse=True)
    mat = vecs[order]
    mat = mat / np.linalg.norm(mat, axis=1, keepdims=True)
    sim = mat @ mat.T
    expected_ids = set()
    for a in range(n):
        for b in range(a + 1, n):
            if sim[a, b] >= threshold:
                expected_ids.add(order[b] + 1)  # higher index = older memory

    updates = {call.args[0]: call.args[1]
               for call in storage.update_memory_importance.call_args_list}
    assert set(updates) == expected_ids
    assert affected == len(expected_ids)
    for mid, value in updates.items():
        assert value == pytest.approx(max(0.1, 0.5 * factor))

# --- load() without vectors: marked-state operations -------------------------


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_load_then_remove_uses_mark_deleted(tmp_path):
    rng = np.random.default_rng(31)
    vecs = rng.random((4, 16)).astype(np.float32)
    path = str(tmp_path / "rm.ann")
    idx = ANNIndex(dim=16)
    idx.add([1, 2, 3, 4], vecs)
    idx.build()
    idx.save(path)
    idx.save_ids_sidecar(path)

    loaded = ANNIndex(dim=16)
    assert loaded.load(path)
    assert loaded._loaded_without_vectors

    loaded.remove({2})  # old code: TypeError on _vectors[keep_mask]

    assert loaded.size == 3
    results = loaded.search(vecs[1], top_k=3)
    assert all(mid != 2 for mid, _ in results)
    top = loaded.search(vecs[2], top_k=1)
    assert top[0][0] == 3


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_load_then_add_one_and_build_stay_safe(tmp_path):
    rng = np.random.default_rng(37)
    vecs = rng.random((3, 16)).astype(np.float32)
    path = str(tmp_path / "add.ann")
    idx = ANNIndex(dim=16)
    idx.add([1, 2, 3], vecs)
    idx.build()
    idx.save(path)
    idx.save_ids_sidecar(path)

    loaded = ANNIndex(dim=16)
    assert loaded.load(path)
    loaded.add_one(4, rng.random(16).astype(np.float32))  # staged; buffer stays None
    assert loaded._vectors is None
    loaded.build()  # old code: crash on the missing vector buffer

    results = loaded.search(vecs[0], top_k=1)
    assert results and results[0][0] == 1
    # A full re-add clears the marker and restores a consistent index.
    loaded.add([1, 2, 3, 4], rng.random((4, 16)).astype(np.float32))
    loaded.build()
    assert not loaded._loaded_without_vectors
    assert loaded.size == 4


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_ensure_ann_rebuilds_vector_buffer_after_load(tmp_path):
    engine, storage, emb = make_engine(tmp_path)
    rng = np.random.default_rng(41)
    vecs = {mid: rng.random(emb.dim).astype(np.float32) for mid in (1, 2, 3)}
    storage.get_all_memories_with_embeddings.return_value = [
        make_memory(mid, emb, vecs[mid]) for mid in (1, 2, 3)
    ]
    engine.build_index()
    assert engine.ann_ready

    # Simulate a restart: drop in-memory state so _ensure_ann hits the disk load.
    engine._ann = None
    engine._ann_built = False
    engine._ensure_ann()

    assert engine.ann_ready
    assert not engine._ann._loaded_without_vectors
    assert engine._ann._vectors is not None
    engine._ann.remove({2})
    results = engine.search_similar(vecs[1], top_k=3)
    assert all(mid != 2 for mid, _ in results)


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_reconsolidate_after_snapshot_load_does_not_raise(tmp_path):
    engine, storage, emb = make_engine(tmp_path)
    rng = np.random.default_rng(43)
    vecs = {mid: rng.random(emb.dim).astype(np.float32) for mid in (1, 2)}
    mems = [make_memory(mid, emb, vecs[mid]) for mid in (1, 2)]
    storage.get_all_memories_with_embeddings.return_value = mems
    engine.build_index()

    engine._ann = None
    engine._ann_built = False
    engine._ensure_ann()
    assert engine.ann_ready

    storage.get_memory_by_id.return_value = mems[0]
    # Old chain: DB commit succeeded, then ann.remove() crashed to the caller.
    assert engine.reconsolidate(1, "corrected content") is True

    assert engine.ann_ready
    results = engine.search_similar(np.asarray(emb.embed_single("corrected content"), dtype=np.float32), top_k=2)
    assert results and results[0][0] == 1


def test_reconsolidate_ann_failure_invalidates_instead_of_raising(tmp_path):
    engine, storage, emb = make_engine(tmp_path)
    ones = np.ones(emb.dim, dtype=np.float32)
    storage.get_all_memories_with_embeddings.return_value = [make_memory(1, emb, ones)]
    engine.build_index()
    storage.get_memory_by_id.return_value = make_memory(1, emb, ones)
    engine._ann.remove = MagicMock(side_effect=RuntimeError("broken index"))

    assert engine.reconsolidate(1, "new content") is True
    assert engine._ann is None
    assert not engine._ann_built


# --- atomic snapshot writes ---------------------------------------------------


def test_brute_force_snapshot_roundtrips(tmp_path):
    rng = np.random.default_rng(47)
    vecs = rng.random((3, 8)).astype(np.float32)
    idx = ANNIndex(dim=8, use_hnsw=False)
    idx.add([1, 2, 3], vecs)
    path = str(tmp_path / "bf.ann")
    idx.save(path)

    # save() must write the exact path load() reads (np.savez* used to append
    # ".npz", so brute-force snapshots silently never loaded).
    assert (tmp_path / "bf.ann").exists()
    loaded = ANNIndex(dim=8, use_hnsw=False)
    assert loaded.load(path)
    assert not loaded._loaded_without_vectors
    top = loaded.search(vecs[1], top_k=1)
    assert top[0][0] == 2


def test_save_writes_via_temp_file_and_cleans_up_on_failure(tmp_path):
    idx = ANNIndex(dim=8, use_hnsw=False)
    idx.add([1], np.ones((1, 8), dtype=np.float32))
    path = str(tmp_path / "atomic.ann")

    replaced = []
    real_replace = os.replace

    def spy_replace(src, dst):
        replaced.append((src, dst))
        return real_replace(src, dst)

    with patch("evolver.ann_index.os.replace", side_effect=spy_replace):
        idx.save(path)

    assert len(replaced) == 1
    src, dst = replaced[0]
    assert src != dst and dst == path
    assert os.path.basename(src).startswith(".") and src.endswith(".tmp")
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")], \
        "temp file must be renamed away, not left behind"

    # A failed write leaves no torn target and no temp litter.
    with patch("evolver.ann_index.np.savez_compressed", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            idx.save(str(tmp_path / "atomic2.ann"))
    assert not (tmp_path / "atomic2.ann").exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]
