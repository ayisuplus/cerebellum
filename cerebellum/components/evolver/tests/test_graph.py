# tests/test_graph.py
from unittest.mock import MagicMock
from evolver.graph import GraphEngine
from evolver.models import GraphNode


def make_engine():
    mock_storage = MagicMock()
    engine = GraphEngine(mock_storage)
    return engine, mock_storage


def test_add_node():
    engine, storage = make_engine()
    storage.upsert_node.return_value = 1
    nid = engine.add_node("git", node_type="tool")
    assert nid == 1
    storage.upsert_node.assert_called_once()


def test_add_edge():
    engine, storage = make_engine()
    storage.upsert_node.side_effect = [1, 2]
    storage.upsert_edge.return_value = 1
    eid = engine.add_edge("git", "merge", relation="uses")
    assert eid == 1
    assert storage.upsert_node.call_count == 2


def test_query():
    engine, storage = make_engine()
    storage.query_nodes.return_value = [
        GraphNode(id=1, label="git", node_type="tool"),
    ]
    nodes = engine.query("git", relation="uses")
    assert len(nodes) == 1
    assert nodes[0].label == "git"


def test_build_from_text():
    engine, storage = make_engine()
    storage.upsert_node.return_value = 1
    storage.upsert_edge.return_value = 1
    engine.build_from_text("修复git merge冲突，使用rebase策略")
    assert storage.upsert_node.call_count >= 1


# --- Entity extraction tests ---

def test_extract_entities_english():
    engine, _ = make_engine()
    tokens = engine._extract_entities("Fix git merge conflict with rebase strategy")
    assert "git" in tokens
    assert "merge" in tokens
    assert "rebase" in tokens
    # Stopwords should be filtered out
    assert "with" not in tokens


def test_extract_entities_chinese():
    engine, _ = make_engine()
    tokens = engine._extract_entities("修复数据库连接超时问题")
    # Should extract Chinese tokens of length >= 2
    assert len(tokens) >= 1


def test_extract_entities_mixed():
    engine, _ = make_engine()
    tokens = engine._extract_entities("在docker中部署nginx容器")
    assert "docker" in tokens or "nginx" in tokens


def test_infer_type_tool():
    engine, _ = make_engine()
    assert engine._infer_type("git") == "tool"
    assert engine._infer_type("docker") == "tool"
    assert engine._infer_type("unknown") == "concept"


def test_infer_type_technique():
    engine, _ = make_engine()
    assert engine._infer_type("merge") == "technique"
    assert engine._infer_type("deploy") == "technique"


def test_extract_entities_removes_short_tokens():
    engine, _ = make_engine()
    tokens = engine._extract_entities("a b c is the")
    assert all(len(t) >= 2 for t in tokens)
    assert "is" not in tokens
    assert "the" not in tokens


def test_extract_entities_camel_case():
    engine, _ = make_engine()
    tokens = engine._extract_entities("FixCamelCase bug in FastAPIApp")
    # camelCase splits should produce tokens
    assert any("fix" in t.lower() for t in tokens) or any("camel" in t.lower() for t in tokens)


# --- Edge decay tests ---

def test_decay_edges_default_params():
    engine, storage = make_engine()
    engine.decay_edges()
    storage.decay_edges.assert_called_once_with(factor=0.9, min_weight=0.01)


def test_decay_edges_custom_params():
    engine, storage = make_engine()
    engine.decay_edges(factor=0.5, min_weight=0.1)
    storage.decay_edges.assert_called_once_with(factor=0.5, min_weight=0.1)
