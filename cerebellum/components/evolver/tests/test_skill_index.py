"""Tests for SkillIndex — add, find, upsert."""
import json
from pathlib import Path
from unittest.mock import MagicMock

from evolver.skill_library import SkillIndex


def test_skill_index_add_and_find(tmp_path):
    embedding = MagicMock()
    embedding.embed_single.return_value = [0.1, 0.2, 0.3]
    index = SkillIndex(library_path=str(tmp_path), embedding_client=embedding)

    meta = index.add_skill(
        name="git-workflow", description="Git workflow tips",
        content="# Git Workflow\n\n## Steps\n1. Commit often",
        topic="git workflow", version=1,
    )
    assert meta["name"] == "evolver-git-workflow"
    assert (tmp_path / "skills" / "evolver-git-workflow.md").exists()


def test_skill_index_upsert_new(tmp_path):
    embedding = MagicMock()
    embedding.embed_single.return_value = [0.1, 0.2, 0.3]
    index = SkillIndex(library_path=str(tmp_path), embedding_client=embedding)

    skill_id, version = index.upsert_skill(
        name="test-skill",
        description="Test skill",
        file_path="/tmp/test.md",
        content="# Test\nContent here",
    )
    assert version >= 1


def test_skill_index_list_empty(tmp_path):
    index = SkillIndex(library_path=str(tmp_path))
    assert index.list_skills() == []


def test_skill_index_get_skill_content(tmp_path):
    index = SkillIndex(library_path=str(tmp_path))
    index.add_skill(
        name="my-skill", description="desc",
        content="# My Skill\nContent", topic="my skill",
    )
    content = index.get_skill_content("evolver-my-skill")
    assert content is not None
    assert "My Skill" in content


def test_skill_index_search(tmp_path):
    index = SkillIndex(library_path=str(tmp_path))
    index.add_skill(
        name="python-tips", description="Python coding tips",
        content="# Python Tips", topic="python coding",
    )
    results = index.search_skills("python")
    assert len(results) >= 1
