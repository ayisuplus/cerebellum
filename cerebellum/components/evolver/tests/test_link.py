# tests/test_link.py
import numpy as np
from unittest.mock import MagicMock
from evolver.link import LinkEngine
from evolver.models import Link, GraphNode, Memory, RecallResult


def make_link_engine():
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_memory = MagicMock()
    mock_graph = MagicMock()

    mock_embedding.embed_single.return_value = np.random.rand(384).tolist()
    mock_embedding.bytes_to_vector.return_value = [0.0] * 384
    mock_embedding.dim = 384

    engine = LinkEngine(mock_storage, mock_embedding, mock_memory, mock_graph)
    return engine, mock_storage, mock_embedding, mock_memory, mock_graph


def test_auto_link_creates_similarity_links():
    engine, storage, emb, memory, graph = make_link_engine()
    shared_vec = [0.5] * 384
    # Mock bytes_to_vector to return the SAME vector as embed_single
    # so cosine similarity = 1.0 (well above threshold 0.6)
    emb.embed_single.return_value = shared_vec
    emb.bytes_to_vector.return_value = shared_vec
    memory.ann_ready = False  # force sampled brute-force path

    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=2, content="similar topic", category="success",
               embedding=b"\x00" * 12),
        Memory(id=3, content="another topic", category="failure",
               embedding=b"\x00" * 12),
    ]

    engine.auto_link_memory(memory_id=1, content="test content about git")

    storage.insert_links_batch.assert_called_once()
    # Batch should contain at least 2 bidirectional links
    batch_args = storage.insert_links_batch.call_args[0][0]
    assert len(batch_args) >= 2


def test_auto_link_creates_entity_links():
    engine, storage, emb, memory, graph = make_link_engine()
    memory._storage.get_all_memories_with_embeddings.return_value = []
    graph._extract_entities.return_value = ["git"]
    storage.get_nodes_by_labels.return_value = [
        GraphNode(id=10, label="git", node_type="tool"),
    ]

    engine.auto_link_memory(memory_id=1, content="fix git merge conflict")

    entity_calls = [c for c in storage.insert_link.call_args_list
                    if c[0][4] == "auto_entity"]
    assert len(entity_calls) >= 1


def test_auto_link_batch():
    engine, storage, emb, memory, graph = make_link_engine()
    memory._storage.get_all_memories_with_embeddings.return_value = []
    graph.query.return_value = []

    engine.auto_link_batch(
        memory_ids=[1, 2, 3],
        contents=["content a", "content b", "content c"],
    )

    assert emb.embed_single.call_count == 3


def test_backlinks():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_backlinks.return_value = [
        Link(id=1, source_type="memory", source_id=2,
             target_type="memory", target_id=5,
             link_type="auto_similar", weight=0.8),
    ]

    result = engine.backlinks("memory", 5)
    assert len(result) == 1
    assert result[0].source_id == 2
    storage.get_backlinks.assert_called_once_with("memory", 5)


def test_outgoing():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="graph_node", target_id=10,
             link_type="auto_entity", weight=0.9),
    ]

    result = engine.outgoing("memory", 1)
    assert len(result) == 1
    storage.get_outgoing.assert_called_once_with("memory", 1)


def test_linked_memories():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="memory", target_id=2,
             link_type="auto_similar", weight=0.8),
        Link(id=2, source_type="memory", source_id=1,
             target_type="memory", target_id=3,
             link_type="auto_similar", weight=0.7),
    ]
    storage.get_memories_by_ids.return_value = [
        Memory(id=2, content="related content", category="success"),
        Memory(id=3, content="another related", category="failure"),
    ]

    results = engine.linked_memories(memory_id=1, top_k=10)
    assert len(results) == 2
    assert isinstance(results[0], RecallResult)


def test_linked_graph_nodes():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="graph_node", target_id=10,
             link_type="auto_entity", weight=0.9),
    ]
    from evolver.models import GraphNode
    storage.get_graph_node.return_value = GraphNode(
        id=10, label="git", node_type="tool",
    )

    nodes = engine.linked_graph_nodes(memory_id=1)
    assert len(nodes) == 1
    assert nodes[0].label == "git"


def test_compute_link_score_no_links():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = []

    score = engine.compute_link_score(memory_id=1, query_related_ids=[2, 3])
    assert score == 0.0


def test_compute_link_score_with_overlap():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="memory", target_id=2,
             link_type="auto_similar", weight=0.8),
        Link(id=2, source_type="memory", source_id=1,
             target_type="memory", target_id=3,
             link_type="auto_similar", weight=0.6),
    ]

    score = engine.compute_link_score(memory_id=1, query_related_ids=[2])
    assert score > 0.0
    assert score <= 1.0


def test_decay_links():
    engine, storage, emb, memory, graph = make_link_engine()
    engine.decay_links(factor=0.9, min_weight=0.01)
    storage.decay_links.assert_called_once_with(factor=0.9, min_weight=0.01)
