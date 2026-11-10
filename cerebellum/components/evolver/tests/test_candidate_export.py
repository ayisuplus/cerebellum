import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from evolver.candidate_export import (
    SCHEMA_VERSION,
    build_candidate_export,
    write_candidate_export,
)


def memory(mid, content, category="success"):
    return SimpleNamespace(
        id=mid,
        content=content,
        category=category,
        tags=["coding"],
        source="session:test",
        importance=0.8,
        access_count=2,
        lifecycle="growing",
        created_at="2026-08-22T00:00:00Z",
    )


def test_candidate_export_is_stable_and_storage_independent(tmp_path):
    storage = MagicMock()
    storage.get_all_memories_columns.return_value = [
        memory(1, "Run the focused parser test first."),
        memory(2, "Avoid broad rewrites.", "failure"),
    ]

    result = build_candidate_export(storage, producer="evolver/test", limit=10)

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["producer"] == "evolver/test"
    assert len(result["candidates"]) == 2
    candidate = result["candidates"][0]
    assert candidate["candidate_id"] == "memory:1"
    assert candidate["content_hash"] == hashlib.sha256(
        candidate["content"].encode("utf-8")
    ).hexdigest()
    assert "embedding" not in candidate

    path = write_candidate_export(result, tmp_path / "nested" / "candidates.json")
    assert json.loads(path.read_text(encoding="utf-8"))["candidates"] == result["candidates"]


def test_candidate_export_filters_and_limits():
    storage = MagicMock()
    storage.get_all_memories_columns.return_value = [
        memory(1, "one", "success"),
        memory(2, "two", "failure"),
        memory(3, "three", "success"),
    ]
    result = build_candidate_export(
        storage, producer="test", categories=["success"], limit=1
    )
    assert [item["content"] for item in result["candidates"]] == ["one"]


def test_candidate_export_rejects_invalid_limit():
    with pytest.raises(ValueError, match="limit"):
        build_candidate_export(MagicMock(), producer="test", limit=0)
