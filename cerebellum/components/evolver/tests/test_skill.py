import os
import tempfile
from unittest.mock import MagicMock
from evolver.skill import SkillEngine
from evolver.models import RecallResult, SkillResult


def make_engine():
    mock_storage = MagicMock()
    mock_memory = MagicMock()
    mock_graph = MagicMock()
    engine = SkillEngine(mock_storage, mock_memory, mock_graph)
    return engine, mock_storage, mock_memory, mock_graph


def test_generate_skill_md():
    engine, storage, memory, graph = make_engine()
    memory.recall.return_value = [
        RecallResult(content="git merge fix", score=0.9, source="memory",
                     category="success", related_nodes=[]),
        RecallResult(content="always rebase first", score=0.8, source="memory",
                     category="insight", related_nodes=[]),
    ]
    graph.query.return_value = []
    storage.upsert_skill.return_value = (1, 2)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = engine.generate("git conflict", output_dir=tmpdir)
        assert result is not None
        assert isinstance(result, SkillResult)
        assert result.name == "git-conflict"
        assert os.path.exists(result.path)
        with open(result.path) as f:
            content = f.read()
        assert "# Git Conflict" in content


def test_generate_returns_none_when_no_content():
    engine, storage, memory, graph = make_engine()
    memory.recall.return_value = []
    graph.query.return_value = []

    result = engine.generate("nonexistent topic")
    assert result is None


def test_skill_name_slugification():
    engine, _, _, _ = make_engine()
    assert engine._slugify("Git 冲突处理") == "git-冲突处理"
    assert engine._slugify("hello world") == "hello-world"
    assert engine._slugify("  spaces  ") == "spaces"


def test_generate_triggers_quality_check():
    engine, storage, memory, graph = make_engine()
    memory.recall.return_value = [
        RecallResult(content="git merge fix", score=0.9, source="memory",
                     category="success", related_nodes=[]),
    ]
    graph.query.return_value = []
    storage.upsert_skill.return_value = (1, 1)

    # Set up checker mock
    mock_checker = MagicMock()
    from evolver.models import EvalResult
    mock_checker.check_and_improve.return_value = (
        "# Improved Skill\n## Steps\n1. Step one\n",
        EvalResult(total_score=80.0, dim_scores={"workflow": 8}, round=1, status="improved"),
    )
    engine._checker = mock_checker

    with tempfile.TemporaryDirectory() as tmpdir:
        result = engine.generate("git conflict", output_dir=tmpdir)
        assert result is not None
        mock_checker.check_and_improve.assert_called_once()
