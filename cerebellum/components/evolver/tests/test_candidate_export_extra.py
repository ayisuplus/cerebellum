"""Extra tests for evolver.candidate_export — error/edge paths."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from evolver.candidate_export import (
    SCHEMA_VERSION,
    build_candidate_export,
    write_candidate_export,
)


def memory(mid, content, category="success", tags=("coding",)):
    return SimpleNamespace(
        id=mid,
        content=content,
        category=category,
        tags=list(tags) if tags is not None else None,
        source="session:test",
        importance=0.5,
        access_count=1,
        lifecycle="seed",
        created_at="2026-08-30T00:00:00Z",
    )


class TestBuildCandidateExportEdges:
    def test_category_filter_skips_non_matching_memory(self):
        """Line 31: category not in allowed set is skipped before content handling."""
        storage = MagicMock()
        storage.get_all_memories_columns.return_value = [
            memory(1, "rejected", category="failure"),
            memory(2, "kept", category="success"),
        ]
        result = build_candidate_export(
            storage, producer="test", categories=["success"], limit=10
        )
        assert [c["content"] for c in result["candidates"]] == ["kept"]

    def test_falsy_category_entries_are_ignored(self):
        """Empty strings in categories do not restrict the export."""
        storage = MagicMock()
        storage.get_all_memories_columns.return_value = [memory(1, "kept", "anything")]
        result = build_candidate_export(
            storage, producer="test", categories=["", None], limit=10
        )
        assert len(result["candidates"]) == 1

    def test_blank_and_none_content_skipped(self):
        """Line 34: whitespace-only or missing content never becomes a candidate."""
        storage = MagicMock()
        storage.get_all_memories_columns.return_value = [
            memory(1, "   "),
            memory(2, None),
            memory(3, "real content"),
        ]
        result = build_candidate_export(storage, producer="test", limit=10)
        assert [c["content"] for c in result["candidates"]] == ["real content"]

    def test_memory_without_id_falls_back_to_hash_prefix(self):
        storage = MagicMock()
        storage.get_all_memories_columns.return_value = [memory(None, "no id content")]
        result = build_candidate_export(storage, producer="test", limit=10)
        candidate = result["candidates"][0]
        assert candidate["candidate_id"].startswith("memory:")
        assert candidate["candidate_id"] == f"memory:{candidate['content_hash'][:16]}"

    def test_non_list_tags_become_empty_list(self):
        storage = MagicMock()
        storage.get_all_memories_columns.return_value = [
            memory(1, "tagged", tags=None),
        ]
        storage.get_all_memories_columns.return_value[0].tags = "not-a-list"
        result = build_candidate_export(storage, producer="test", limit=10)
        assert result["candidates"][0]["tags"] == []

    def test_exported_at_is_utc_z_suffix(self):
        storage = MagicMock()
        storage.get_all_memories_columns.return_value = []
        result = build_candidate_export(storage, producer="test", limit=1)
        assert result["schema_version"] == SCHEMA_VERSION
        assert result["exported_at"].endswith("Z")
        assert result["candidates"] == []


class TestWriteCandidateExportFailure:
    def test_failed_replace_cleans_up_temp_file(self, tmp_path):
        """Lines 76-81: an os.replace failure removes the temp file and re-raises."""
        target = tmp_path / "out" / "candidates.json"
        export = {"schema_version": SCHEMA_VERSION, "candidates": []}

        with patch("evolver.candidate_export.os.replace",
                   side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                write_candidate_export(export, target)

        assert not target.exists()
        leftovers = list(target.parent.glob(".candidates.json.*.tmp"))
        assert leftovers == []

    def test_failed_replace_survives_unlink_failure(self, tmp_path):
        """Lines 79-80: an OSError while unlinking the temp file is swallowed."""
        target = tmp_path / "candidates.json"
        export = {"schema_version": SCHEMA_VERSION, "candidates": []}

        with patch("evolver.candidate_export.os.replace",
                   side_effect=OSError("disk full")), \
             patch("evolver.candidate_export.os.unlink",
                   side_effect=OSError("cannot unlink")):
            with pytest.raises(OSError, match="disk full"):
                write_candidate_export(export, target)

    def test_round_trip_preserves_unicode(self, tmp_path):
        target = tmp_path / "candidates.json"
        export = {"schema_version": SCHEMA_VERSION,
                  "candidates": [{"content": "中文内容"}]}
        path = write_candidate_export(export, target)
        assert json.loads(path.read_text(encoding="utf-8")) == export
