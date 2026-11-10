# tests/test_models.py
from evolver.models import RecallResult, SkillResult, Memory, GraphNode, GraphEdge, Link, EvalResult


def test_recall_result_fields():
    r = RecallResult(
        content="test content",
        score=0.85,
        source="memory",
        category="success",
        related_nodes=[{"label": "git", "type": "tool"}],
    )
    assert r.content == "test content"
    assert r.score == 0.85
    assert r.source == "memory"
    assert r.category == "success"
    assert len(r.related_nodes) == 1


def test_skill_result_fields():
    s = SkillResult(
        name="git-conflict",
        path="/skills/git-conflict.md",
        content="# Git Conflict",
        version=1,
    )
    assert s.name == "git-conflict"
    assert s.version == 1


def test_memory_defaults():
    m = Memory(content="hello", category="insight")
    assert m.content == "hello"
    assert m.importance == 0.5
    assert m.access_count == 0
    assert m.embedding is None


def test_graph_node_creation():
    n = GraphNode(label="git", node_type="tool")
    assert n.label == "git"
    assert n.node_type == "tool"
    assert n.properties is None


def test_graph_edge_creation():
    e = GraphEdge(source_id=1, target_id=2, relation="uses")
    assert e.source_id == 1
    assert e.weight == 1.0


def test_link_creation():
    link = Link(id=1, source_type="memory", source_id=10,
                target_type="memory", target_id=20,
                link_type="auto_similar", weight=0.85)
    assert link.source_type == "memory"
    assert link.target_id == 20
    assert link.weight == 0.85


def test_eval_result_creation():
    result = EvalResult(
        total_score=72.5,
        dim_scores={"frontmatter": 8, "workflow": 12, "edge_cases": 7},
        round=1,
        status="pass",
    )
    assert result.total_score == 72.5
    assert result.dim_scores["workflow"] == 12
    assert result.round == 1


def test_recall_result_has_snippet():
    r = RecallResult(content="full text", score=0.9, source="memory", category="success")
    assert r.snippet == ""
    r2 = RecallResult(content="full text", score=0.9, source="memory", category="success", snippet="full...")
    assert r2.snippet == "full..."


def test_memory_lifecycle_default():
    from evolver.models import Memory
    m = Memory(content="test", category="experience")
    assert m.lifecycle == "seed"


def test_memory_lifecycle_custom():
    from evolver.models import Memory
    m = Memory(content="test", category="experience", lifecycle="growing")
    assert m.lifecycle == "growing"


def test_memory_to_dict_includes_lifecycle():
    from evolver.models import Memory
    m = Memory(content="test", category="experience", lifecycle="evergreen")
    d = m.to_dict()
    assert d["lifecycle"] == "evergreen"
