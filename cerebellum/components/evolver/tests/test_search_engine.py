"""Tests for evolver.search_engine.SearchEngine."""

import time
from unittest.mock import MagicMock

import pytest

from evolver.models import RecallResult
from evolver.search_engine import SearchEngine


def make_dependencies():
    """Build a consistent set of mocked dependencies for SearchEngine."""
    memory_engine = MagicMock(name="memory_engine")
    hybrid_search = MagicMock(name="hybrid_search")
    retrieval_engine = MagicMock(name="retrieval_engine")
    vector_store = MagicMock(name="vector_store")
    storage = MagicMock(name="storage")

    # Default hybrid returns a single hybrid-style result
    hybrid_search.search.return_value = [
        RecallResult(content="hybrid hit", score=0.7, source="hybrid",
                     category="success"),
    ]
    # Default retrieval engine recall() returns a memory result
    retrieval_engine.recall.return_value = [
        RecallResult(content="memory hit", score=0.9, source="memory",
                     category="success"),
    ]
    retrieval_engine.recall_by_time.return_value = [
        RecallResult(content="recent hit", score=0.8, source="memory",
                     category="insight"),
    ]
    return memory_engine, hybrid_search, retrieval_engine, vector_store, storage


def make_engine(**overrides):
    """Build a SearchEngine with mocked dependencies (overridable)."""
    mem, hyb, ret, vs, st = make_dependencies()
    for k, v in overrides.items():
        # Allow passing pre-built mocks per slot
        if k == "memory_engine":
            mem = v
        elif k == "hybrid_search":
            hyb = v
        elif k == "retrieval_engine":
            ret = v
        elif k == "vector_store":
            vs = v
        elif k == "storage":
            st = v
    return SearchEngine(mem, hyb, ret, vs, st), mem, hyb, ret, vs, st


class TestVectorStrategy:
    def test_vector_strategy_returns_results(self):
        engine, _mem, _hyb, _ret, vs, _st = make_engine()
        vs.search.return_value = [(1, 0.95), (2, 0.80)]
        # Engine uses embed_single via memory_engine fallback; mock that
        engine._memory_engine.embed_single = MagicMock(return_value=[0.1] * 8)

        results = engine.search("hello world", strategy="vector", top_k=5)
        assert isinstance(results, list)
        assert all(isinstance(r, RecallResult) for r in results)
        assert len(results) == 2
        assert results[0].source == "vector"
        assert results[0].content in ("id:1", "id:2") or "id:" in results[0].content

    def test_vector_empty_returns_empty(self):
        engine, _mem, _hyb, _ret, vs, _st = make_engine()
        vs.search.return_value = []
        engine._memory_engine.embed_single = MagicMock(return_value=[0.0] * 8)

        results = engine.search("nothing matches", strategy="vector", top_k=5)
        assert results == []


class TestHybridStrategy:
    def test_hybrid_strategy_delegates(self):
        engine, _mem, hyb, _ret, _vs, _st = make_engine()
        results = engine.search("anything", strategy="hybrid", top_k=7)
        hyb.search.assert_called_once()
        # Forwarding of top_k to HybridSearch
        _args, kwargs = hyb.search.call_args
        assert kwargs.get("top_k") == 7
        assert len(results) == 1
        assert results[0].source == "hybrid"


class TestMemoryStrategy:
    def test_memory_strategy_delegates(self):
        engine, _mem, _hyb, ret, _vs, _st = make_engine()
        results = engine.search("git merge", strategy="memory", top_k=4)
        ret.recall.assert_called_once()
        assert len(results) == 1
        assert results[0].source == "memory"


class TestAutoRouting:
    def test_auto_strategy_time_sensitive_english(self):
        engine, _mem, _hyb, ret, _vs, _st = make_engine()
        engine.search("what did I do today", strategy="auto", top_k=5)
        # "today" triggers time-sensitive branch → memory
        ret.recall_by_time.assert_called_once()
        ret.recall.assert_not_called()

    def test_auto_strategy_time_sensitive_chinese(self):
        engine, _mem, _hyb, ret, _vs, _st = make_engine()
        engine.search("最近的项目", strategy="auto", top_k=5)
        ret.recall_by_time.assert_called_once()

    def test_auto_strategy_simple_keyword(self):
        engine, mem, _hyb, _ret, vs, _st = make_engine()
        vs.search.return_value = []
        mem.embed_single = MagicMock(return_value=[0.0] * 4)
        # 1-2 tokens, no time/fact words
        engine.search("python", strategy="auto", top_k=5)
        vs.search.assert_called_once()

    def test_auto_strategy_fact_query_english(self):
        engine, _mem, _hyb, ret, _vs, _st = make_engine()
        engine.search("how to fix merge conflict in git", strategy="auto", top_k=5)
        # fact query → memory
        ret.recall.assert_called_once()

    def test_auto_strategy_fact_query_chinese(self):
        engine, _mem, _hyb, ret, _vs, _st = make_engine()
        engine.search("什么是 evolver", strategy="auto", top_k=5)
        ret.recall.assert_called_once()

    def test_auto_strategy_default_hybrid(self):
        engine, _mem, hyb, _ret, _vs, _st = make_engine()
        engine.search("explain evolution pipeline architecture", strategy="auto", top_k=5)
        # Default → hybrid
        hyb.search.assert_called_once()


class TestMetaAndStrategies:
    def test_list_strategies(self):
        engine, *_ = make_engine()
        strategies = engine.list_strategies()
        assert isinstance(strategies, list)
        names = {s["name"] for s in strategies}
        assert {"vector", "hybrid", "memory", "auto"} <= names

    def test_search_with_meta(self):
        engine, _mem, hyb, _ret, _vs, _st = make_engine()
        meta = engine.search_with_meta("explain evolver", strategy="hybrid", top_k=3)
        assert "results" in meta
        assert "strategy_used" in meta
        assert "timing_ms" in meta
        assert meta["strategy_used"] == "hybrid"
        assert isinstance(meta["results"], list)
        assert isinstance(meta["timing_ms"], float)
        assert meta["timing_ms"] >= 0.0

    def test_search_with_meta_auto_reports_routed_strategy(self):
        engine, _mem, _hyb, _ret, _vs, _st = make_engine()
        # Trigger time-sensitive routing
        meta = engine.search_with_meta("yesterday's notes", strategy="auto", top_k=3)
        assert meta["strategy_used"] == "memory"

    def test_invalid_strategy_raises(self):
        engine, *_ = make_engine()
        with pytest.raises(ValueError):
            engine.search("q", strategy="not-a-real-strategy")


class TestRouteUnit:
    def test_route_time_sensitive(self):
        engine, *_ = make_engine()
        assert engine._route("latest findings on caching") == "memory"
        assert engine._route("this week summary") == "memory"
        assert engine._route("刚刚发生了什么") == "memory"

    def test_route_simple_keyword(self):
        engine, *_ = make_engine()
        assert engine._route("python") == "vector"
        assert engine._route("git merge") == "vector"

    def test_route_fact_query(self):
        engine, *_ = make_engine()
        assert engine._route("what is the difference between x and y") == "memory"
        assert engine._route("为什么需要 RRF") == "memory"

    def test_route_default(self):
        engine, *_ = make_engine()
        assert engine._route("explain the architecture of the pipeline") == "hybrid"
