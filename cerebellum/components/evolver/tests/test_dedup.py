import numpy as np
import pytest
from unittest.mock import MagicMock

from evolver.ann_index import ANNIndex, _HAS_HNSWLIB
from evolver.dedup import Deduplicator
from evolver.models import Memory

DIM = 384
THRESHOLD = 0.15


def _unit(index: int) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    vec[index] = 1.0
    return vec


def _blend(a: np.ndarray, b: np.ndarray, weight_a: float) -> np.ndarray:
    """Unit vector with cosine similarity `weight_a` to `a` (a, b orthonormal)."""
    vec = weight_a * a + np.sqrt(1.0 - weight_a**2) * b
    return (vec / np.linalg.norm(vec)).astype(np.float32)


# Embedding byte payloads are opaque keys; each maps to a distinct vector.
VEC_NEAR = b"\x01" * 12  # cosine 0.90 to VEC_A  -> distance 0.10 < threshold
VEC_FAR = b"\x02" * 12  # cosine 0.80 to VEC_A  -> distance 0.20 > threshold
VEC_OTHER = b"\x03" * 12  # orthogonal to VEC_A -> distance 1.0
VEC_A = b"\x04" * 12
# Probe payloads for is_duplicate; deliberately never stored as memories.
VEC_PROBE_NEAR = b"\x05" * 12  # cosine 0.88 to VEC_A -> duplicate
VEC_PROBE_FAR = b"\x06" * 12  # >= 0.20 from every stored vector -> unique

_VECTORS = {
    VEC_A: _unit(0),
    VEC_NEAR: _blend(_unit(0), _unit(1), 0.90),
    VEC_FAR: _blend(_unit(0), _unit(3), 0.80),
    VEC_OTHER: _unit(2),
    VEC_PROBE_NEAR: _blend(_unit(0), _unit(1), 0.88),
    VEC_PROBE_FAR: _blend(_unit(0), _unit(2), 0.80),
}


def make_dedup(threshold: float = THRESHOLD, ann=None):
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.dim = DIM
    mock_embedding.bytes_to_vector.side_effect = lambda data: _VECTORS[data].tolist()
    mock_embedding.identity = "fastembed:test-model"
    get_ann = (lambda: ann) if ann is not None else None
    dedup = Deduplicator(mock_storage, mock_embedding, threshold=threshold, get_ann=get_ann)
    # dedup() fetches via the batched API; mirror whatever the unbatched mock
    # returns (honoring its side_effect, e.g. category filtering).
    mock_storage.get_all_memories_with_embeddings_batched.side_effect = (
        lambda batch_size=500, category=None: iter(
            [mock_storage.get_all_memories_with_embeddings(category=category)]
        )
    )
    return dedup, mock_storage


def build_ann(memories, use_hnsw=False):
    ann = ANNIndex(dim=DIM, use_hnsw=use_hnsw)
    ids = [mem.id for mem in memories]
    vectors = np.stack([_VECTORS[mem.embedding] for mem in memories])
    ann.add(ids, vectors)
    ann.build()
    return ann


def behavior_memories():
    """m2 sits below the threshold from m1 (duplicate), m3 above it (kept),
    m4 is orthogonal (kept), m5 duplicates m1 but in another category (kept)."""
    return [
        Memory(id=1, content="A" * 40, category="success", embedding=VEC_A),
        Memory(id=2, content="B" * 20, category="success", embedding=VEC_NEAR),
        Memory(id=3, content="C" * 20, category="success", embedding=VEC_FAR),
        Memory(id=4, content="D" * 20, category="success", embedding=VEC_OTHER),
        Memory(id=5, content="E" * 20, category="failure", embedding=VEC_A),
    ]


def assert_behavioral_verdict(dedup, storage):
    kept, deleted = dedup.dedup(dry_run=False)
    assert (kept, deleted) == (4, 1)
    # The longest same-category version is kept; only the near duplicate of
    # memory 1 is deleted. Threshold-above and foreign-category items survive.
    storage.delete_memory.assert_called_once_with(2)


def test_dedup_linear_keeps_and_deletes_by_threshold():
    dedup, storage = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = behavior_memories()
    assert_behavioral_verdict(dedup, storage)


def test_dedup_dry_run_deletes_nothing():
    dedup, storage = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = behavior_memories()
    kept, deleted = dedup.dedup(dry_run=True)
    assert (kept, deleted) == (4, 1)
    storage.delete_memory.assert_not_called()
    storage.log_event.assert_not_called()


def test_dedup_ann_path_matches_linear_verdict():
    memories = behavior_memories()
    ann = build_ann(memories)
    dedup, storage = make_dedup(ann=ann)
    storage.get_all_memories_with_embeddings.return_value = memories
    assert_behavioral_verdict(dedup, storage)


@pytest.mark.skipif(not _HAS_HNSWLIB, reason="hnswlib not installed")
def test_dedup_ann_hnsw_path_matches_linear_verdict():
    memories = behavior_memories()
    ann = build_ann(memories, use_hnsw=True)
    dedup, storage = make_dedup(ann=ann)
    storage.get_all_memories_with_embeddings.return_value = memories
    assert_behavioral_verdict(dedup, storage)


def test_is_duplicate_ann_path_respects_threshold_and_category():
    memories = behavior_memories()
    ann = build_ann(memories)
    dedup, storage = make_dedup(ann=ann)
    storage.get_memories_by_ids.side_effect = lambda ids: [
        mem for mem in memories if mem.id in set(ids)
    ]
    # Near the anchor vector -> duplicate of memory 1.
    assert dedup.is_duplicate("near", VEC_PROBE_NEAR, category="success") is True
    # Above the threshold from every stored vector -> not a duplicate.
    assert dedup.is_duplicate("far", VEC_PROBE_FAR, category="success") is False
    # Identical vector but a category with no matching memory -> not a duplicate.
    assert dedup.is_duplicate("other category", VEC_A, category="error") is False


def test_is_duplicate_returns_false_for_unique():
    dedup, storage = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = []
    assert dedup.is_duplicate("unique content", VEC_PROBE_NEAR) is False


def test_is_duplicate_linear_path_matches_ann_verdicts():
    dedup, storage = make_dedup()
    # The mock must honor the category filter like the real SQL storage does.
    storage.get_all_memories_with_embeddings.side_effect = lambda category=None: [
        mem for mem in behavior_memories() if category is None or mem.category == category
    ]
    assert dedup.is_duplicate("near", VEC_PROBE_NEAR, category="success") is True
    assert dedup.is_duplicate("far", VEC_PROBE_FAR, category="success") is False
    assert dedup.is_duplicate("other category", VEC_A, category="error") is False


def test_dedup_empty_storage():
    dedup, storage = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = []
    kept, deleted = dedup.dedup(dry_run=True)
    assert kept == 0
    assert deleted == 0


def test_dedup_never_cross_compares_embedder_tags():
    dedup, storage = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="A" * 40, category="success", embedding=VEC_A,
               embedder="fastembed:test-model"),
        Memory(id=2, content="B" * 20, category="success", embedding=VEC_A,
               embedder="hash-fallback:v2"),
        Memory(id=3, content="C" * 20, category="success", embedding=VEC_A,
               embedder="fastembed:test-model"),
        Memory(id=4, content="D" * 20, category="success", embedding=VEC_A),
    ]
    kept, deleted = dedup.dedup(dry_run=False)
    # m3 collapses into m1 (same tag); m4 (untagged legacy) also collapses.
    # m2 survives: identical vector but a different embedder — incomparable.
    assert (kept, deleted) == (2, 2)
    deleted_ids = {call.args[0] for call in storage.delete_memory.call_args_list}
    assert deleted_ids == {3, 4}


def test_is_duplicate_skips_cross_embedder_rows():
    dedup, storage = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="x", category="success", embedding=VEC_PROBE_NEAR,
               embedder="hash-fallback:v2"),
    ]
    # Query embedded by "fastembed:test-model" vs a hash-fallback row: no match.
    assert dedup.is_duplicate("q", VEC_PROBE_NEAR, category="success") is False
    # Same embedder tag: the near vector is a duplicate.
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="x", category="success", embedding=VEC_PROBE_NEAR,
               embedder="fastembed:test-model"),
    ]
    assert dedup.is_duplicate("q", VEC_PROBE_NEAR, category="success") is True
