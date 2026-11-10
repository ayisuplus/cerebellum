from unittest.mock import MagicMock, patch
import json
import pytest
from evolver.memory_graph import MemoryGraph, MemoryNode, DocNode, VisEdge
from evolver.models import Memory, GraphNode, Link


def make_mock_storage():
    storage = MagicMock()
    return storage


def sample_memories():
    return [
        Memory(
            id=1,
            content="First memory content for testing",
            category="test",
            importance=0.8,
            lifecycle="seed",
            content_hash="hash1",
            created_at="2024-01-01 00:00:00",
        ),
        Memory(
            id=2,
            content="Second memory content for testing",
            category="test",
            importance=0.6,
            lifecycle="growing",
            content_hash="hash2",
            created_at="2024-01-02 00:00:00",
        ),
        Memory(
            id=3,
            content="First memory content for testing updated",
            category="test",
            importance=0.9,
            lifecycle="evergreen",
            content_hash="hash1",
            created_at="2024-01-03 00:00:00",
        ),
    ]


def sample_graph_nodes():
    return [
        GraphNode(id=10, label="Unique Node", node_type="concept", properties={"key": "val"}),
        GraphNode(id=11, label="First memory content for testing", node_type="entity", properties=None),
    ]


def sample_graph_edges():
    return [
        {"source_id": 10, "target_id": 1, "relation": "about", "weight": 0.5},
        {"source_id": 1, "target_id": 2, "relation": "related", "weight": 0.3},
    ]


def sample_links():
    return [
        Link(id=1, source_type="memory", source_id=1, target_type="memory", target_id=2, link_type="auto_similar", weight=0.7),
        Link(id=2, source_type="memory", source_id=2, target_type="memory", target_id=3, link_type="manual", weight=0.9),
    ]


def test_memory_node_dataclass():
    node = MemoryNode(id=1, label="test", node_type="memory", importance=0.5)
    assert node.id == 1
    assert node.label == "test"
    assert node.node_type == "memory"
    assert node.importance == 0.5
    assert node.x == 0
    assert node.y == 0
    assert node.properties is None
    assert node.category is None
    assert node.lifecycle is None


def test_doc_node_dataclass():
    node = DocNode(id=1, label="doc", node_type="document")
    assert node.id == 1
    assert node.label == "doc"
    assert node.node_type == "document"
    assert node.x == 0
    assert node.y == 0
    assert node.properties is None


def test_vis_edge_dataclass():
    edge = VisEdge(source=1, target=2, edge_type="similarity")
    assert edge.source == 1
    assert edge.target == 2
    assert edge.edge_type == "similarity"
    assert edge.weight == 1.0


def test_build_empty_storage():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = []
    storage.query_nodes.return_value = []
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    result = mg.build()

    assert result == {"nodes": [], "edges": []}


def test_build_memories_to_memory_nodes():
    storage = make_mock_storage()
    memories = sample_memories()
    storage.get_all_memories_with_embeddings.return_value = memories
    storage.query_nodes.return_value = []
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    result = mg.build()

    assert len(result["nodes"]) == 3
    memory_nodes = [n for n in result["nodes"] if n.node_type == "memory"]
    assert len(memory_nodes) == 3
    assert memory_nodes[0].id == 1
    assert memory_nodes[0].label == "First memory content for testing"
    assert memory_nodes[0].importance == 0.8
    assert memory_nodes[0].category == "test"
    assert memory_nodes[0].lifecycle == "seed"


def test_build_graph_nodes_to_doc_nodes():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = []
    storage.query_nodes.return_value = sample_graph_nodes()
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    result = mg.build()

    assert len(result["nodes"]) == 2
    doc_nodes = [n for n in result["nodes"] if n.node_type == "document"]
    assert len(doc_nodes) == 2
    assert doc_nodes[0].id == 10
    assert doc_nodes[0].label == "Unique Node"
    assert doc_nodes[0].properties == {"key": "val"}


def test_build_dedup_graph_node_matching_memory():
    storage = make_mock_storage()
    memories = sample_memories()
    graph_nodes = sample_graph_nodes()
    storage.get_all_memories_with_embeddings.return_value = memories
    storage.query_nodes.return_value = graph_nodes
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    result = mg.build()

    doc_nodes = [n for n in result["nodes"] if n.node_type == "document"]
    assert len(doc_nodes) == 1
    assert doc_nodes[0].label == "Unique Node"


def test_build_graph_edges_to_vis_edges():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = []
    storage.query_nodes.return_value = []

    def fetchall_side_effect(sql, params=None):
        if "graph_edges" in sql:
            return sample_graph_edges()
        elif "links" in sql:
            return []
        return []

    storage._fetchall.side_effect = fetchall_side_effect

    mg = MemoryGraph(storage)
    result = mg.build()

    assert len(result["edges"]) == 2
    assert all(e.edge_type == "reference" for e in result["edges"])


def test_build_similarity_edges_from_links():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = []
    storage.query_nodes.return_value = []

    def fetchall_side_effect(sql, params=None):
        if "graph_edges" in sql:
            return []
        elif "links" in sql:
            return [
                {"source_type": "memory", "source_id": 1, "target_type": "memory", "target_id": 2, "link_type": "auto_similar", "weight": 0.7},
            ]
        return []

    storage._fetchall.side_effect = fetchall_side_effect

    mg = MemoryGraph(storage)
    result = mg.build()

    similarity_edges = [e for e in result["edges"] if e.edge_type == "similarity"]
    assert len(similarity_edges) == 1
    assert similarity_edges[0].source == 1
    assert similarity_edges[0].target == 2
    assert similarity_edges[0].weight == 0.7


def test_build_version_chain():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = sample_memories()
    storage.query_nodes.return_value = []
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    result = mg.build()

    version_edges = [e for e in result["edges"] if e.edge_type == "version_chain"]
    assert len(version_edges) == 1
    assert version_edges[0].source == 1
    assert version_edges[0].target == 3


def test_build_edge_dedup():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = []
    storage.query_nodes.return_value = []

    def fetchall_side_effect(sql, params=None):
        if "graph_edges" in sql:
            return [
                {"source_id": 1, "target_id": 2, "relation": "about", "weight": 0.5},
                {"source_id": 1, "target_id": 2, "relation": "about", "weight": 0.8},
            ]
        elif "links" in sql:
            return []
        return []

    storage._fetchall.side_effect = fetchall_side_effect

    mg = MemoryGraph(storage)
    result = mg.build()

    assert len(result["edges"]) == 1
    assert result["edges"][0].weight == 0.8


def test_layout_returns_coords():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="Test", category="c", importance=0.5, lifecycle="seed"),
        Memory(id=2, content="Test2", category="c", importance=0.5, lifecycle="seed"),
    ]
    storage.query_nodes.return_value = []
    storage._fetchall.return_value = [
        {"source_id": 1, "target_id": 2, "relation": "about", "weight": 1.0},
    ]

    mg = MemoryGraph(storage)
    result = mg.layout(iterations=10, width=800, height=600)

    assert len(result["nodes"]) == 2
    for node in result["nodes"]:
        assert 30 <= node.x <= 770
        assert 30 <= node.y <= 570


def test_layout_empty():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = []
    storage.query_nodes.return_value = []
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    result = mg.layout()

    assert result == {"nodes": [], "edges": []}


def test_to_json_format():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="Test", category="c", importance=0.5, lifecycle="seed"),
    ]
    storage.query_nodes.return_value = []
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    json_str = mg.to_json(iterations=5, width=400, height=300)

    data = json.loads(json_str)
    assert "nodes" in data
    assert "edges" in data
    assert "meta" in data
    assert data["meta"]["node_count"] == 1
    assert data["meta"]["edge_count"] == 0
    assert data["meta"]["layout_iterations"] == 5


def test_to_dict_format():
    storage = make_mock_storage()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="Test", category="c", importance=0.5, lifecycle="seed"),
    ]
    storage.query_nodes.return_value = []
    storage._fetchall.return_value = []

    mg = MemoryGraph(storage)
    result = mg.to_dict(iterations=5, width=400, height=300)

    assert isinstance(result, dict)
    assert "nodes" in result
    assert "edges" in result
    assert "meta" in result


def test_layout_boundary_constraints():
    storage = make_mock_storage()
    nodes = []
    for i in range(10):
        nodes.append(Memory(id=i, content=f"Node {i}", category="c", importance=0.5, lifecycle="seed"))
    storage.get_all_memories_with_embeddings.return_value = nodes
    storage.query_nodes.return_value = []
    edges = []
    for i in range(9):
        edges.append({"source_id": i, "target_id": i + 1, "relation": "about", "weight": 1.0})
    storage._fetchall.return_value = edges

    mg = MemoryGraph(storage)
    result = mg.layout(iterations=100, width=200, height=200)

    for node in result["nodes"]:
        assert 30 <= node.x <= 170
        assert 30 <= node.y <= 170
