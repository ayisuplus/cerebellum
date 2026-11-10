"""Tests for offline skill evolution artifact loading."""
from pathlib import Path

import pytest

from evolver.skill_evolution import (
    SkillFormatError,
    SkillLoadError,
    load_skill_artifact,
)


VALID_SKILL = """---
name: git-review
description: Use when reviewing git changes.
---

# Git Review

## Steps
1. Inspect the diff.
2. Report risky changes.
"""


def test_load_skill_artifact_parses_frontmatter(tmp_path):
    skill_path = tmp_path / "git-review.md"
    skill_path.write_text(VALID_SKILL, encoding="utf-8")

    artifact = load_skill_artifact(skill_path)

    assert artifact.path == skill_path
    assert artifact.name == "git-review"
    assert artifact.description == "Use when reviewing git changes."
    assert "## Steps" in artifact.body
    assert artifact.size == len(VALID_SKILL)


def test_load_skill_artifact_rejects_missing_file(tmp_path):
    missing_path = tmp_path / "missing.md"

    with pytest.raises(SkillLoadError, match="does not exist"):
        load_skill_artifact(missing_path)


def test_load_skill_artifact_rejects_missing_name(tmp_path):
    skill_path = tmp_path / "bad.md"
    skill_path.write_text(
        """---
description: Use when reviewing git changes.
---

## Steps
1. Inspect the diff.
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillFormatError, match="name"):
        load_skill_artifact(skill_path)


def test_load_skill_artifact_rejects_missing_description(tmp_path):
    skill_path = tmp_path / "bad.md"
    skill_path.write_text(
        """---
name: git-review
---

## Steps
1. Inspect the diff.
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillFormatError, match="description"):
        load_skill_artifact(skill_path)


def test_load_skill_artifact_rejects_empty_body(tmp_path):
    skill_path = tmp_path / "bad.md"
    skill_path.write_text(
        """---
name: git-review
description: Use when reviewing git changes.
---
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillFormatError, match="body"):
        load_skill_artifact(skill_path)
