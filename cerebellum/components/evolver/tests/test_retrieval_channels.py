"""Algorithm tests for independent retrieval channels and RRF fusion."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from evolver.config import RerankerConfig
from evolver.models import GraphNode, Memory
from evolver.retrieval import RetrievalEngine
from evolver.storage_sqlite import SQLiteStorage


def make_retrieval(memories, lexical_memories, graph_nodes=None):
    engine = MagicMock()
    engine._RECALL_CANDIDATE_MULTIPLIER = 2
    engine._recall_bm25_weight = 0.15
    engine._reranker = RerankerConfig()
    engine._link = None
    engine._ann = None
    engine._vector_store.count.return_value = 1
    engine._vector_store.search.return_value = [(1, 0.99)]
    engine._ensure_vector_store_synced.return_value = True
    engine._embedding.embed_single.return_value = [1.0, 0.0, 0.0]
    engine._extract_tags.side_effect = lambda text: [
        token.strip(".,:;!?\n").lower()
        for token in text.split()
        if token.strip(".,:;!?\n")
    ]

    by_id = {memory.id: memory for memory in memories}
    engine._storage.get_memories_by_ids.side_effect = lambda ids: [
        by_id[memory_id] for memory_id in ids if memory_id in by_id
    ]
    engine._storage.search_memories_lexical.return_value = lexical_memories
    engine._storage.query_nodes_batch.return_value = graph_nodes or []
    return RetrievalEngine(engine), engine


def test_lexical_hit_can_enter_results_outside_vector_top_k():
    semantic = Memory(
        id=1, content="semantic but unrelated", category="insight"
    )
    lexical = Memory(
        id=2, content="needle exact recovery procedure", category="success"
    )
    retrieval, engine = make_retrieval(
        [semantic, lexical], lexical_memories=[lexical]
    )

    results = retrieval.recall("needle", top_k=2)

    assert {result.content for result in results} == {
        semantic.content,
        lexical.content,
    }
    engine._storage.search_memories_lexical.assert_called_once()


def test_graph_hit_can_enter_results_outside_vector_top_k():
    semantic = Memory(id=1, content="semantic candidate", category="insight")
    graph_hit = Memory(
        id=3, content="cache tuning playbook", category="success"
    )
    graph_node = GraphNode(id=7, label="cache", node_type="concept")
    retrieval, _engine = make_retrieval(
        [semantic, graph_hit],
        lexical_memories=[graph_hit],
        graph_nodes=[graph_node],
    )

    results = retrieval.recall("performance", top_k=2)

    assert graph_hit.content in {result.content for result in results}


def test_rrf_rank_positions_start_at_one():
    memory = Memory(id=1, content="one result", category="insight")
    retrieval, _engine = make_retrieval([memory], lexical_memories=[])

    results = retrieval._rrf_fusion(
        {1},
        {1: memory},
        semantic_ranked=[(1, 0.9)],
        graph_ranked=[],
        link_ranked=[],
        bm25_ranked=[],
        top_k=1,
        rrf_k=60,
    )

    assert results[0].score == round(1.0 / 61.0, 4)


def test_bm25_length_normalization_uses_token_counts():
    short = Memory(id=1, content="needle compact", category="insight")
    long = Memory(
        id=2,
        content="needle " + "padding " * 50,
        category="insight",
    )
    retrieval, _engine = make_retrieval([short, long], lexical_memories=[])

    ranked = retrieval._bm25_score("needle", [long, short])

    assert [memory_id for memory_id, _score in ranked] == [1, 2]


def test_time_sensitive_rerank_prefers_recent_memory():
    retrieval, _engine = make_retrieval([], lexical_memories=[])
    now = datetime.now(timezone.utc)
    recent = retrieval._rrf_fusion(
        {1},
        {1: Memory(
            id=1,
            content="latest deployment status",
            category="insight",
            created_at=now.isoformat(),
        )},
        [(1, 1.0)], [], [], [], 1, 60,
    )[0]
    old = retrieval._rrf_fusion(
        {2},
        {2: Memory(
            id=2,
            content="latest deployment status",
            category="insight",
            created_at=(now - timedelta(days=365)).isoformat(),
        )},
        [(2, 1.0)], [], [], [], 1, 60,
    )[0]

    reranked = retrieval._rerank(
        "latest deployment status",
        [old, recent],
        query_vec=[1.0, 0.0, 0.0],
    )

    assert reranked[0].created_at == recent.created_at


def test_sqlite_lexical_candidates_do_not_load_embeddings():
    storage = SQLiteStorage(":memory:")
    storage.insert_memory(Memory(
        content="needle recovery procedure",
        category="success",
        importance=0.8,
    ))
    storage.insert_memory(Memory(
        content="unrelated deployment notes",
        category="insight",
    ))

    results = storage.search_memories_lexical(["needle"], limit=10)

    assert len(results) == 1
    assert results[0].content == "needle recovery procedure"
    assert results[0].embedding is None
