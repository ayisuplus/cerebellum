"""Extra tests for the evolver facade (__init__.py) — lazy exports and facade methods."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import evolver
from evolver import Evolver
from evolver.exceptions import EvolverError


def _make_evolver(**kwargs):
    kwargs.setdefault("db_url", "sqlite://:memory:")
    kwargs.setdefault("fallback_embeddings", True)
    kwargs.setdefault("auto_distill_hours", 0)
    return Evolver(**kwargs)


@pytest.fixture
def ev(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    e = _make_evolver()
    yield e
    e.close()


# --- Storage backend selection ---

class TestStorageSelection:
    def test_mysql_url_without_pymysql_raises_import_error(self):
        with patch("evolver.MySQLStorage", None), \
             patch("evolver.EmbeddingClient", MagicMock()):
            with pytest.raises(ImportError, match="pymysql"):
                Evolver(db_url="mysql://u:p@localhost:3306/db")

    def test_plain_path_defaults_to_sqlite(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        e = _make_evolver(db_url=str(tmp_path / "plain.db"))
        try:
            from evolver.storage_sqlite import SQLiteStorage
            assert isinstance(e._storage, SQLiteStorage)
        finally:
            e.close()

    def test_archive_without_pymysql_raises_import_error(self):
        with patch("evolver.MySQLStorage", None), \
             patch("evolver.EmbeddingClient", MagicMock()):
            with pytest.raises(ImportError, match="pymysql"):
                Evolver(db_url="sqlite://:memory:",
                        data_url="mysql://u:p@localhost:3306/archive")


# --- Startup resilience ---

class TestStartupResilience:
    def test_temporal_sync_failure_is_logged_not_raised(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        temporal = MagicMock()
        temporal.sync_from_memories.side_effect = RuntimeError("corrupt")
        with patch("evolver.TemporalMemory", return_value=temporal), \
             patch("evolver.EmbeddingClient", MagicMock()):
            e = Evolver(db_url="sqlite://:memory:", fallback_embeddings=True)
            e.close()

    def test_closet_prepopulated_from_existing_memories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        storage = MagicMock()
        storage.get_all_memories_with_embeddings.return_value = [
            SimpleNamespace(id=7, content="docker compose restart", category="ops"),
        ]
        with patch("evolver.SQLiteStorage", return_value=storage), \
             patch("evolver.EmbeddingClient", MagicMock()):
            e = Evolver(db_url="sqlite://:memory:", fallback_embeddings=True)
            try:
                assert e.closet_query("docker") == [7]
            finally:
                e.close()

    def test_closet_populate_failure_is_logged_not_raised(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        storage = MagicMock()
        storage.get_all_memories_with_embeddings.side_effect = RuntimeError("bad db")
        with patch("evolver.SQLiteStorage", return_value=storage), \
             patch("evolver.EmbeddingClient", MagicMock()):
            e = Evolver(db_url="sqlite://:memory:", fallback_embeddings=True)
            e.close()


# --- learn_extracted ---

class TestLearnExtracted:
    def _wire(self, ev):
        ev._extractor = MagicMock()
        ev._memory = MagicMock()
        ev._memory.store.return_value = [42]
        ev.graph = MagicMock()

    def test_add_skip_and_dedup(self, ev):
        self._wire(ev)
        ev._extractor.extract.return_value = [
            {"text": "alpha fact about python packaging", "tags": ["py"]},
            {"text": "alpha fact about python packaging"},  # duplicate hash -> skip
            {"text": "abc"},  # too short -> dropped silently
        ]

        results = ev.learn_extracted("raw text", source="unit")

        actions = [r["action"] for r in results]
        assert actions == ["add", "skip"]
        assert results[0]["id"] == 42
        ev._memory.store.assert_called_once_with(
            task="alpha fact about python packaging",
            outcome="extracted",
            source="unit",
        )
        ev.graph.build_from_text.assert_called_once()

    def test_deduplicates_against_existing_storage_hashes(self, ev):
        import hashlib
        import re
        self._wire(ev)
        normalized = re.sub(r"\s+", " ", "known fact about caching".strip().lower())
        known_hash = hashlib.md5(normalized.encode()).hexdigest()
        with patch.object(ev._storage, "get_all_content_hashes",
                          return_value={known_hash}):
            ev._extractor.extract.return_value = [
                {"text": "known   fact   about caching"},  # whitespace-normalized dup
            ]
            results = ev.learn_extracted("t", source="s")
        assert [r["action"] for r in results] == ["skip"]
        ev._memory.store.assert_not_called()

    def test_no_facts_returns_empty(self, ev):
        ev._extractor = MagicMock()
        ev._extractor.extract.return_value = []
        assert ev.learn_extracted("nothing here") == []


# --- export_candidates / consolidate_experience ---

class TestCerebellumBoundary:
    def test_export_candidates_with_path(self, ev, tmp_path):
        ev.learn(task="exported memory task", outcome="success",
                 solution="a solution long enough for graph")
        out = tmp_path / "nested" / "candidates.json"

        export = ev.export_candidates(path=str(out), limit=10)

        assert export["schema_version"] == "cerebellum/v1"
        assert export["producer"].startswith("evolver/")
        assert len(export["candidates"]) == 1
        assert out.exists()

    def test_export_candidates_rejects_bad_limit(self, ev):
        with pytest.raises(ValueError, match="limit"):
            ev.export_candidates(limit=0)

    def test_consolidate_experience_stores_proposals(self, ev, tmp_path):
        experience_id = str(uuid.uuid4())
        request = {
            "schema_version": "cerebellum/v1",
            "request_id": str(uuid.uuid4()),
            "experience": {
                "experience_id": experience_id,
                "task": "fix the parser bug",
                "task_family": "parser",
                "outcome": {"success": True, "summary": "patched the lexer"},
            },
            "feedback": [],
            "decision": {
                "experience_id": experience_id,
                "actions": ["store", "propose_skill"],
            },
        }
        ev.learn = MagicMock(return_value=[1])
        out = tmp_path / "response.json"

        response = ev.consolidate_experience(request, path=str(out), store=True)

        assert response["schema_version"] == "cerebellum/v1"
        assert response["proposals"]
        assert ev.learn.call_count == len(response["proposals"])
        for call in ev.learn.call_args_list:
            assert call[1]["outcome"] == "success"
        assert out.exists()

    def test_consolidate_experience_store_false_learns_nothing(self, ev):
        experience_id = str(uuid.uuid4())
        request = {
            "schema_version": "cerebellum/v1",
            "request_id": str(uuid.uuid4()),
            "experience": {
                "experience_id": experience_id,
                "task": "investigate flaky test",
                "outcome": {"success": False, "summary": ""},
            },
            "feedback": [],
            "decision": {"experience_id": experience_id, "actions": ["store"]},
        }
        ev.learn = MagicMock()
        response = ev.consolidate_experience(request, store=False)
        assert response["proposals"]
        ev.learn.assert_not_called()

    def test_consolidate_experience_rejects_bad_schema(self, ev):
        with pytest.raises(ValueError, match="schema_version"):
            ev.consolidate_experience({"schema_version": "nope"}, store=False)


# --- distill / auto-distill ---

class TestDistill:
    def test_distill_levels_delegate(self, ev):
        ev._compiler = MagicMock()
        ev.distill("all", days=3)
        ev._compiler.distill_all.assert_called_once_with(days=3)
        ev.distill("today")
        ev._compiler.compile_today.assert_called_once_with(days=1)
        ev.distill("week", days=14)
        ev._compiler.compile_week.assert_called_once_with(days=14)
        ev.distill("longterm")
        ev._compiler.compile_longterm.assert_called_once_with()
        ev.distill("facts", days=2)
        ev._compiler.compile_facts.assert_called_once_with(days=2)

    def test_distill_unknown_level_raises(self, ev):
        ev._compiler = MagicMock()
        with pytest.raises(ValueError, match="Unknown distill level"):
            ev.distill("century")

    def test_distill_safe_logs_and_clears_pending(self, ev):
        ev._compiler = MagicMock()
        ev._compiler.distill_all.side_effect = RuntimeError("distill boom")
        ev._distill_pending = True
        ev._distill_safe()  # must not raise
        assert ev._distill_pending is False

    def test_auto_distill_tz_aware_fresh_run_skips(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        e = _make_evolver(auto_distill_hours=24)
        try:
            e._compiler = MagicMock()
            with patch.object(e._storage, "get_last_distill_run", return_value={
                "created_at": datetime.now(timezone.utc).isoformat(),  # tz-aware
            }):
                e._auto_distill()
            assert e._distill_pending is False
            e._compiler.distill_all.assert_not_called()
        finally:
            e.close()

    def test_auto_distill_invalid_timestamp_skips(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        e = _make_evolver(auto_distill_hours=24)
        try:
            e._compiler = MagicMock()
            with patch.object(e._storage, "get_last_distill_run", return_value={
                "created_at": "not-a-timestamp",
            }):
                e._auto_distill()
            assert e._distill_pending is False
        finally:
            e.close()

    def test_auto_distill_oserror_is_logged_not_raised(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        e = _make_evolver(auto_distill_hours=24)
        try:
            e._compiler = MagicMock()
            with patch.object(e._storage, "get_last_distill_run",
                              side_effect=OSError("io")):
                e._auto_distill()  # must not raise
            assert e._distill_pending is False
        finally:
            e.close()

    def test_auto_distill_unexpected_error_reraises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        e = _make_evolver(auto_distill_hours=24)
        try:
            e._compiler = MagicMock()
            with patch.object(e._storage, "get_last_distill_run",
                              side_effect=RuntimeError("unexpected")):
                with pytest.raises(RuntimeError, match="unexpected"):
                    e._auto_distill()
        finally:
            e.close()


# --- Simple delegating facade methods ---

class TestDelegatingMethods:
    def test_memory_context_search_facts_add_fact(self, ev):
        ev._compiler = MagicMock()
        ev._compiler.assemble.return_value = "assembled context"
        assert ev.memory_context() == "assembled context"

        ev.add_fact("the sky is blue", tags=["trivia"])
        results = ev.search_facts("sky")
        assert isinstance(results, list)

    def test_decay_links_and_edges(self, ev):
        ev._storage = MagicMock()
        ev.decay_links(factor=0.9, min_weight=0.02)
        ev._storage.decay_links.assert_called_once_with(factor=0.9, min_weight=0.02)
        ev.decay_edges()
        ev._storage.decay_edges.assert_called_once_with(factor=0.9, min_weight=0.01)

    def test_reconsolidate_and_suggest(self, ev):
        ev._memory = MagicMock()
        ev._memory.reconsolidate.return_value = True
        assert ev.reconsolidate(5, "correction") is True
        ev._memory.reconsolidate.assert_called_once_with(5, "correction")

        ev._memory.suggest.return_value = ["r1"]
        assert ev.suggest("ctx", top_k=2) == ["r1"]
        ev._memory.suggest.assert_called_once_with("ctx", top_k=2)

    def test_memory_graph_delegates(self, ev):
        ev._memory_graph = MagicMock()
        ev._memory_graph.to_dict.return_value = {"nodes": [], "edges": [], "meta": {}}
        result = ev.memory_graph(iterations=10, width=100.0, height=50.0)
        assert result["nodes"] == []
        ev._memory_graph.to_dict.assert_called_once_with(
            iterations=10, width=100.0, height=50.0)

    def test_ingest_delegates_to_ingest_directory(self, ev):
        with patch("evolver.ingest.ingest_directory") as mock_ingest:
            mock_ingest.return_value = "stats"
            result = ev.ingest("some/dir", recursive=False, source_prefix="docs")
        assert result == "stats"
        args, kwargs = mock_ingest.call_args
        assert args[0] is ev
        assert args[1] == "some/dir"
        assert kwargs["recursive"] is False
        assert kwargs["source_prefix"] == "docs"

    def test_interference_decay_and_update_lifecycle(self, ev):
        ev._memory = MagicMock()
        ev._memory.interference_decay.return_value = 3
        assert ev.interference_decay(0.9, 0.7) == 3
        ev._memory.interference_decay.assert_called_once_with(0.9, 0.7)

        ev._memory.update_lifecycle.return_value = {"promoted": 2}
        assert ev.update_lifecycle() == {"promoted": 2}

    def test_compose_skills_and_find_pairs(self, ev):
        ev._skill = MagicMock()
        ev._skill.compose.return_value = "composed"
        assert ev.compose_skills("a", "b", "topic") == "composed"
        ev._skill.compose.assert_called_once_with("a", "b", "topic")

        ev._skill.find_composable_pairs.return_value = [("a", "b")]
        assert ev.find_composable_pairs(min_shared_nodes=5) == [("a", "b")]
        ev._skill.find_composable_pairs.assert_called_once_with(5)

    def test_recall_light_and_deep(self, ev):
        ev._stack = MagicMock()
        ev._stack.recall_light.return_value = "light"
        assert ev.recall_light("q", category="c", top_k=3) == "light"
        ev._stack.recall_light.assert_called_once_with("q", category="c", top_k=3)

        ev._stack.recall_deep.return_value = ["deep"]
        assert ev.recall_deep("q", top_k=2) == ["deep"]
        ev._stack.recall_deep.assert_called_once_with("q", top_k=2)

    def test_closet_query_without_closet_returns_empty(self, ev):
        ev._closet = None
        assert ev.closet_query("anything") == []

    def test_profile_methods(self, ev):
        ev._profile = MagicMock()
        assert ev.build_profile() is ev._profile
        ev._profile.from_memories.assert_called_once_with(ev._storage)

        ev._profile.to_prompt.return_value = "prompt text"
        assert ev.profile_prompt() == "prompt text"

        assert ev.get_profile() is ev._profile

    def test_hybrid_search_delegates(self, ev):
        ev._hybrid = MagicMock()
        ev._hybrid.search.return_value = ["hit"]
        assert ev.hybrid_search("q", mode="rag", top_k=4, extra=1) == ["hit"]
        ev._hybrid.search.assert_called_once_with("q", mode="rag", top_k=4, extra=1)

    def test_temporal_methods(self, ev):
        ev._temporal = MagicMock()
        ev._temporal.get_stats.return_value = {"tracked": 4}
        assert ev.temporal_stats() == {"tracked": 4}

        ev.apply_temporal_decay()
        ev._temporal.apply_decay.assert_called_once_with(ev._storage)

        ev._temporal.remove_expired.return_value = 2
        assert ev.expire_stale_memories() == 2


# --- Lifecycle ---

class TestLifecycle:
    def test_close_tolerates_failing_distill_future(self, ev):
        future = MagicMock()
        future.result.side_effect = RuntimeError("distill failed")
        ev._distill_future = future
        ev.close()  # must not raise
        assert ev._distill_future is None

    async def test_async_context_manager(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        async with _make_evolver() as e:
            assert e is not None
        assert e._closed is True

    async def test_close_async_closes_archive(self, ev):
        archive = MagicMock()
        ev._archive = archive
        await ev.close_async()
        archive.close.assert_called_once()


# --- Lazy module exports ---

class TestPymysqlFallback:
    def test_module_survives_missing_pymysql(self, monkeypatch):
        """Lines 36-37, 42: without pymysql the module still imports."""
        import builtins
        import importlib

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pymysql":
                raise ImportError("No module named 'pymysql'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        try:
            importlib.reload(evolver)
            assert evolver.pymysql is None
            assert evolver.MySQLStorage is None
        finally:
            monkeypatch.undo()
            importlib.reload(evolver)


class TestLazyExports:
    @pytest.mark.parametrize("name", [
        "RecallResult", "SkillResult", "Link", "EvalResult", "Fact", "Memory",
        "BaseStorage", "RetrievalEngine", "ProfileTrait", "SearchMode",
        "TemporalEntry",
    ])
    def test_lazy_imports_resolve(self, name):
        assert getattr(evolver, name) is not None

    def test_unknown_attribute_raises_attribute_error(self):
        with pytest.raises(AttributeError, match="no attribute"):
            evolver.no_such_thing_anywhere

    def test_dir_includes_lazy_names(self):
        names = dir(evolver)
        for name in ("RecallResult", "RetrievalEngine", "TemporalEntry"):
            assert name in names
