"""Regression tests for ANN-assisted dedup: dedup() must actually use the
ANN callback, is_duplicate's ANN path must filter by category, and both
paths must agree on verdicts."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from evolver.dedup import Deduplicator
from evolver.models import Memory
from evolver.utils import cosine_similarity

DIM = 16


class FakeANN:
    """Exact brute-force ANN double over a fixed id -> vector map."""

    def __init__(self, id_to_vec):
        self._vecs = dict(id_to_vec)
        self.calls = 0

    @property
    def size(self):
        return len(self._vecs)

    def search(self, vec, top_k=10):
        self.calls += 1
        scored = [
            (mid, 1.0 - cosine_similarity(vec, v))
            for mid, v in self._vecs.items()
        ]
        scored.sort(key=lambda x: x[1])
        return scored[:top_k]


def build_corpus():
    """Seeded random corpus: 6 orthogonal bases each with one near-duplicate
    (3 pairs per category), plus one identical-vector cross-category twin
    pair that must NOT dedup (categories are isolated)."""
    rng = np.random.default_rng(7)
    memories, vecs = [], {}
    mid = 1
    base_idx = 0
    for cat in ("success", "failure"):
        for _ in range(3):
            base = np.zeros(DIM)
            base[base_idx] = 1.0
            base_idx += 1
            vecs[f"vec{mid}"] = base
            memories.append(Memory(
                id=mid, content=f"base memory {mid} with extra length",
                category=cat, embedding=f"vec{mid}".encode(),
            ))
            mid += 1
            dup = base + rng.normal(0.0, 0.01, DIM)
            dup = dup / np.linalg.norm(dup)
            vecs[f"vec{mid}"] = dup
            memories.append(Memory(
                id=mid, content=f"dup of {mid}",
                category=cat, embedding=f"vec{mid}".encode(),
            ))
            mid += 1
    twin = np.zeros(DIM)
    twin[6] = 1.0
    vecs["vec-twin-a"] = twin
    memories.append(Memory(
        id=mid, content="cross category twin",
        category="success", embedding=b"vec-twin-a",
    ))
    mid += 1
    vecs["vec-twin-b"] = twin
    memories.append(Memory(
        id=mid, content="cross category twin",
        category="failure", embedding=b"vec-twin-b",
    ))
    return memories, vecs


def make_storage_embedding(memories, vecs):
    storage = MagicMock()
    by_id = {m.id: m for m in memories}
    storage.get_all_memories_with_embeddings.side_effect = (
        lambda category=None: [
            m for m in memories if category is None or m.category == category
        ]
    )
    storage.get_all_memories_with_embeddings_batched.side_effect = (
        lambda batch_size=500, category=None: iter(
            [storage.get_all_memories_with_embeddings(category=category)]
        )
    )
    storage.get_memories_by_ids.side_effect = lambda ids: [
        by_id[i] for i in ids if i in by_id
    ]
    embedding = MagicMock()
    embedding.dim = DIM
    embedding.bytes_to_vector.side_effect = lambda b: vecs[b.decode()]
    return storage, embedding


def test_dedup_uses_ann_and_matches_linear():
    memories, vecs = build_corpus()

    storage, embedding = make_storage_embedding(memories, vecs)
    ann = FakeANN({m.id: vecs[m.embedding.decode()] for m in memories})
    dedup_ann = Deduplicator(storage, embedding, threshold=0.15,
                             get_ann=lambda: ann)
    kept_ann, deleted_ann = dedup_ann.dedup(dry_run=True)
    # The ANN callback was actually consulted (old code never called it).
    assert ann.calls > 0

    storage2, embedding2 = make_storage_embedding(memories, vecs)
    dedup_lin = Deduplicator(storage2, embedding2, threshold=0.15)
    kept_lin, deleted_lin = dedup_lin.dedup(dry_run=True)

    assert (kept_ann, deleted_ann) == (kept_lin, deleted_lin)
    # 6 near-dup pairs collapse; the cross-category twins both survive.
    assert (kept_ann, deleted_ann) == (8, 6)


def test_dedup_ann_live_run_deletes_same_as_linear():
    memories, vecs = build_corpus()
    storage, embedding = make_storage_embedding(memories, vecs)
    ann = FakeANN({m.id: vecs[m.embedding.decode()] for m in memories})
    dedup = Deduplicator(storage, embedding, threshold=0.15,
                         get_ann=lambda: ann)

    kept, deleted = dedup.dedup(dry_run=False)

    assert (kept, deleted) == (8, 6)
    assert storage.delete_memory.call_count == 6


def test_dedup_falls_back_to_linear_when_ann_empty():
    memories, vecs = build_corpus()
    storage, embedding = make_storage_embedding(memories, vecs)
    ann = FakeANN({})  # size 0 -> unavailable
    dedup = Deduplicator(storage, embedding, threshold=0.15,
                         get_ann=lambda: ann)

    kept, deleted = dedup.dedup(dry_run=True)

    assert ann.calls == 0
    assert (kept, deleted) == (8, 6)


def test_is_duplicate_ann_filters_by_category():
    """Same input must give the same verdict whether or not the ANN is
    available; the ANN path used to ignore `category` entirely."""
    base = np.zeros(DIM)
    base[0] = 1.0
    existing = [
        Memory(id=1, content="existing failure note",
               category="failure", embedding=b"v1"),
        Memory(id=2, content="unrelated success note",
               category="success", embedding=b"v2"),
    ]
    other = np.zeros(DIM)
    other[1] = 1.0
    vecs = {"v1": base, "v2": other, "new": base.copy()}

    storage, embedding = make_storage_embedding(existing, vecs)
    ann = FakeANN({1: base, 2: other})
    dedup_ann = Deduplicator(storage, embedding, threshold=0.15,
                             get_ann=lambda: ann)

    storage2, embedding2 = make_storage_embedding(existing, vecs)
    dedup_lin = Deduplicator(storage2, embedding2, threshold=0.15)

    # Identical vector exists but only in a different category.
    assert dedup_ann.is_duplicate("new note", b"new", category="success") is False
    assert dedup_lin.is_duplicate("new note", b"new", category="success") is False
    # Without the category filter both paths detect the duplicate.
    assert dedup_ann.is_duplicate("new note", b"new", category=None) is True
    assert dedup_lin.is_duplicate("new note", b"new", category=None) is True
    # Matching category also detects it on both paths.
    assert dedup_ann.is_duplicate("new note", b"new", category="failure") is True
    assert dedup_lin.is_duplicate("new note", b"new", category="failure") is True


def test_is_duplicate_ann_and_linear_agree_on_non_duplicate():
    base = np.zeros(DIM)
    base[0] = 1.0
    existing = [
        Memory(id=1, content="existing note",
               category="success", embedding=b"v1"),
    ]
    far = np.zeros(DIM)
    far[1] = 1.0
    vecs = {"v1": base, "new": far}

    storage, embedding = make_storage_embedding(existing, vecs)
    ann = FakeANN({1: base})
    dedup_ann = Deduplicator(storage, embedding, threshold=0.15,
                             get_ann=lambda: ann)
    storage2, embedding2 = make_storage_embedding(existing, vecs)
    dedup_lin = Deduplicator(storage2, embedding2, threshold=0.15)

    assert dedup_ann.is_duplicate("novel note", b"new") is False
    assert dedup_lin.is_duplicate("novel note", b"new") is False
