"""Integration tests for database-to-VectorStore consistency."""

import numpy as np

from evolver.memory import MemoryEngine
from evolver.models import Memory
from evolver.storage_sqlite import SQLiteStorage
from evolver.vector_store import InMemoryVectorStore


class FakeEmbedding:
    dim = 3

    def embed_single(self, text: str):
        if "corrected" in text:
            return [0.0, 1.0, 0.0]
        return [1.0, 0.0, 0.0]

    def embed(self, texts: list[str]):
        return [self.embed_single(text) for text in texts]

    @staticmethod
    def vector_to_bytes(vector):
        return np.asarray(vector, dtype=np.float32).tobytes()

    @staticmethod
    def bytes_to_vector(data: bytes):
        return np.frombuffer(data, dtype=np.float32).copy()


class FlakyVectorStore(InMemoryVectorStore):
    def __init__(self, dimension: int, failures: int = 1):
        super().__init__(dimension)
        self._failures = failures

    def upsert(self, id: int, vector: np.ndarray, metadata: dict = None):
        if self._failures:
            self._failures -= 1
            raise RuntimeError("vector backend unavailable")
        return super().upsert(id, vector, metadata)


def make_engine(vector_store=None):
    storage = SQLiteStorage(":memory:")
    embedding = FakeEmbedding()
    vectors = vector_store or InMemoryVectorStore(dimension=embedding.dim)
    return MemoryEngine(storage, embedding, vector_store=vectors), storage, vectors


def test_store_commits_database_and_drains_vector_outbox():
    engine, storage, vectors = make_engine()

    memory_ids = engine.store(
        task="fix authentication bug",
        outcome="success",
        solution="validate the token",
    )

    assert vectors.list_ids() == set(memory_ids)
    assert storage.get_pending_vector_sync() == []


def test_embedding_finishes_before_database_transaction_starts():
    storage = SQLiteStorage(":memory:")

    class ObservingEmbedding(FakeEmbedding):
        def embed(self, texts: list[str]):
            assert storage._transaction_conn is None
            return super().embed(texts)

    embedding = ObservingEmbedding()
    engine = MemoryEngine(
        storage,
        embedding,
        vector_store=InMemoryVectorStore(dimension=embedding.dim),
    )

    memory_ids = engine.store(
        task="slow embedding provider",
        outcome="success",
        solution="finish embedding before opening the write transaction",
    )

    assert len(memory_ids) == 1


def test_vector_failure_does_not_rollback_memory_and_is_retryable():
    vectors = FlakyVectorStore(dimension=3)
    engine, storage, _ = make_engine(vectors)

    memory_ids = engine.store(
        task="repair deployment",
        outcome="success",
        solution="retry with bounded backoff",
    )

    assert storage.get_memory_by_id(memory_ids[0]) is not None
    pending = storage.get_pending_vector_sync()
    assert len(pending) == 1
    assert pending[0]["attempts"] == 1

    result = engine.sync_vector_store()

    assert result["failed"] == 0
    assert vectors.list_ids() == set(memory_ids)
    assert storage.get_pending_vector_sync() == []


def test_full_sync_backfills_and_prunes_orphan_vectors():
    engine, storage, vectors = make_engine()
    embedding = FakeEmbedding()
    stored_id = storage.insert_memory(Memory(
        content="database source of truth",
        category="insight",
        embedding=embedding.vector_to_bytes([1.0, 0.0, 0.0]),
    ))
    vectors.upsert(999, np.array([0.0, 0.0, 1.0], dtype=np.float32))

    result = engine.sync_vector_store(prune=True)

    assert result["upserted"] == 1
    assert result["deleted"] == 1
    assert vectors.list_ids() == {stored_id}


def test_reconsolidate_and_forget_update_vector_store():
    engine, storage, vectors = make_engine()
    memory_id = engine.store(
        task="old guidance",
        outcome="success",
        solution="old solution",
    )[0]

    assert engine.reconsolidate(memory_id, "corrected guidance") is True
    nearest = vectors.search(np.array([0.0, 1.0, 0.0], dtype=np.float32), top_k=1)
    assert nearest[0][0] == memory_id

    engine.forget(memory_id=memory_id)

    assert storage.get_memory_by_id(memory_id) is None
    assert memory_id not in vectors.list_ids()
    assert storage.get_pending_vector_sync() == []


def test_outbox_entry_rolls_back_with_memory_transaction():
    storage = SQLiteStorage(":memory:")
    embedding = FakeEmbedding()

    storage.begin()
    storage.insert_memory(Memory(
        content="rolled back",
        category="insight",
        embedding=embedding.vector_to_bytes([1.0, 0.0, 0.0]),
    ))
    storage.rollback()

    assert storage.get_all_memories_with_embeddings() == []
    assert storage.get_pending_vector_sync() == []
