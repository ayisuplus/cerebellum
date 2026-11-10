"""Tests for SkillGenerator."""
import os
import tempfile
from unittest.mock import MagicMock
from evolver.skill_generator import SkillGenerator
from evolver.models import SkillResult


def make_generator():
    mock_engine = MagicMock()
    mock_storage = MagicMock()
    gen = SkillGenerator(mock_engine, mock_storage)
    return gen, mock_engine, mock_storage


def test_generate_delegates_to_skill_engine():
    gen, engine, _ = make_generator()
    engine.generate.return_value = SkillResult(
        name="test-skill", path="/tmp/test-skill.md",
        content="# Test", version=1,
    )

    result = gen.generate("test topic", output_dir="/tmp/skills", lang="en")

    engine.generate.assert_called_once_with("test topic", output_dir="/tmp/skills", lang="en")
    assert result is not None
    assert result.name == "test-skill"


def test_generate_returns_none_when_engine_returns_none():
    gen, engine, _ = make_generator()
    engine.generate.return_value = None

    result = gen.generate("unknown topic")
    assert result is None


def test_export_writes_skill_file():
    gen, engine, storage = make_generator()
    storage.get_skill_by_name.return_value = {
        "name": "git-workflow",
        "content": "---\nname: git-workflow\n---\n# Git Workflow\n\n## Steps\n1. Commit",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        result = gen.export("git-workflow", output_dir=tmpdir)
        assert result is not None
        assert os.path.exists(result)
        with open(result) as f:
            content = f.read()
        assert "Git Workflow" in content


def test_export_returns_none_when_skill_not_found():
    gen, engine, storage = make_generator()
    storage.get_skill_by_name.return_value = None

    result = gen.export("nonexistent-skill")
    assert result is None


def test_export_returns_none_when_content_empty():
    gen, engine, storage = make_generator()
    storage.get_skill_by_name.return_value = {"name": "empty", "content": ""}

    result = gen.export("empty")
    assert result is None


def test_export_creates_output_dir():
    gen, engine, storage = make_generator()
    storage.get_skill_by_name.return_value = {
        "name": "test-skill",
        "content": "# Test skill",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        nested = os.path.join(tmpdir, "nested", "dir")
        result = gen.export("test-skill", output_dir=nested)
        assert result is not None
        assert os.path.exists(result)
