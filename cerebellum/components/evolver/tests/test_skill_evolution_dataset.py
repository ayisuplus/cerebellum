"""Tests for offline skill evolution dataset building."""
import json
from types import SimpleNamespace

import pytest

from evolver.models import RecallResult
from evolver.skill_evolution import (
    DatasetError,
    build_dataset,
    build_memory_dataset,
    load_manual_dataset,
    load_skill_artifact,
    split_examples,
)


VALID_SKILL = """---
name: git-review
description: Use when reviewing git changes.
---

# Git Review

## Steps
1. Inspect the diff.
"""


def _write_valid_skill(tmp_path):
    skill_path = tmp_path / "git-review.md"
    skill_path.write_text(VALID_SKILL, encoding="utf-8")
    return load_skill_artifact(skill_path)


def test_load_manual_dataset_splits_valid_jsonl(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    rows = [
        {"task_input": "review diff 1", "expected_behavior": "find risky change 1"},
        {"task_input": "review diff 2", "expected_behavior": "find risky change 2"},
        {"task_input": "review diff 3", "expected_behavior": "find risky change 3"},
        {"task_input": "review diff 4", "expected_behavior": "find risky change 4"},
        {"task_input": "review diff 5", "expected_behavior": "find risky change 5"},
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    dataset = load_manual_dataset(dataset_path)

    assert len(dataset.train) == 3
    assert len(dataset.val) == 1
    assert len(dataset.holdout) == 1
    assert dataset.train[0].source == "manual"


def test_load_manual_dataset_rejects_missing_required_field(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        json.dumps({"task_input": "review diff"}),
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="expected_behavior"):
        load_manual_dataset(dataset_path)


def test_load_manual_dataset_rejects_invalid_json(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(DatasetError, match="Invalid JSON"):
        load_manual_dataset(dataset_path)


def test_split_examples_requires_three_examples():
    with pytest.raises(DatasetError, match="at least 3"):
        split_examples([])


def test_build_memory_dataset_from_recall_results():
    evo = SimpleNamespace()
    evo.recall = lambda query, top_k=20: [
        RecallResult(content="Always inspect auth middleware", score=0.9, source="memory", category="success"),
        RecallResult(content="Check expired token failures", score=0.8, source="memory", category="failure"),
        RecallResult(content="Report security risk first", score=0.7, source="memory", category="insight"),
    ]

    dataset = build_memory_dataset(evo, "git review")

    assert len(dataset.train) == 1
    assert len(dataset.val) == 1
    assert len(dataset.holdout) == 1
    assert dataset.train[0].source == "memory"
    assert "lesson" in dataset.train[0].expected_behavior.lower()


def test_build_memory_dataset_rejects_too_few_memories():
    evo = SimpleNamespace()
    evo.recall = lambda query, top_k=20: [
        RecallResult(content="Only one memory", score=0.9, source="memory", category="success"),
    ]

    with pytest.raises(DatasetError, match="at least 3"):
        build_memory_dataset(evo, "git review")


def test_build_dataset_uses_manual_source(tmp_path):
    artifact = _write_valid_skill(tmp_path)
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        "\n".join([
            json.dumps({"task_input": "one", "expected_behavior": "first"}),
            json.dumps({"task_input": "two", "expected_behavior": "second"}),
            json.dumps({"task_input": "three", "expected_behavior": "third"}),
        ]),
        encoding="utf-8",
    )
    config = SimpleNamespace(dataset_source="manual", dataset_path=dataset_path)

    dataset = build_dataset(config, artifact)

    assert len(dataset.all_examples) == 3
