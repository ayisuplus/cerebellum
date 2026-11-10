"""Tests for ArtifactWriter — template path and LLM path."""
from unittest.mock import MagicMock

from evolver.artifact_writer import ArtifactWriter


def test_artifact_writer_template_path(tmp_path):
    """When no LLM is provided, ArtifactWriter falls back to Jinja template."""
    memories = [
        MagicMock(category="success", content="Step 1: do the thing\nStep 2: verify"),
        MagicMock(category="failure", content="Watch out for null inputs"),
        MagicMock(category="insight", content="Idempotency matters"),
    ]
    graph_nodes = [MagicMock(label="python", node_type="language")]

    writer = ArtifactWriter(jinja_env=None)
    md, py = writer.render(
        topic="test topic",
        name="test-topic",
        description="Auto-generated",
        memories=memories,
        graph_nodes=graph_nodes,
        executable=True,
        llm_content=None,
    )

    assert "test topic" in md.lower()
    assert "version: 1" in md
    assert "test-topic" in md
    # executable=True and template path produces a .py
    assert py is not None
    assert "test-topic" in py


def test_artifact_writer_llm_path(tmp_path):
    """When LLM content is provided, frontmatter is prepended and py is thin wrapper."""
    memories = [
        MagicMock(category="success", content="Some content"),
    ]
    graph_nodes = [MagicMock(label="test", node_type="concept")]

    writer = ArtifactWriter()
    md, py = writer.render(
        topic="llm-skill",
        name="llm-skill",
        description="LLM generated skill",
        memories=memories,
        graph_nodes=graph_nodes,
        executable=True,
        llm_content="## Steps\n1. Do stuff\n2. Verify",
    )

    assert "---" in md
    assert "llm-skill" in md
    assert "Steps" in md
    # LLM path produces thin .py wrapper
    assert py is not None
    assert "NotImplementedError" in py


def test_artifact_writer_no_executable(tmp_path):
    """When executable=False, no .py content is returned."""
    memories = [MagicMock(category="success", content="Step 1")]
    graph_nodes = []

    writer = ArtifactWriter()
    md, py = writer.render(
        topic="simple",
        name="simple",
        description="Simple skill",
        memories=memories,
        graph_nodes=graph_nodes,
        executable=False,
        llm_content="Some content",
    )

    assert md is not None
    assert py is None


def test_artifact_writer_write(tmp_path):
    """ArtifactWriter.write creates .md and .py files on disk."""
    writer = ArtifactWriter()
    md_path, py_path = writer.write(
        name="test-skill",
        md_content="# Test Skill\n\nContent here",
        py_content='"""test-skill"""',
        output_dir=str(tmp_path / "output"),
    )

    assert md_path.endswith("test-skill.md")
    assert py_path is not None and py_path.endswith("test-skill.py")
    assert (tmp_path / "output" / "test-skill.md").exists()
    assert (tmp_path / "output" / "test-skill.py").exists()
