import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from evolver.models import Memory, RecallResult
from evolver.hybrid_search import HybridSearch


def make_memory_engine():
    mock = MagicMock()
    mock._embedding = MagicMock()
    mock._embedding.embed_single.return_value = np.random.rand(384).tolist()
    mock._embedding.dim = 384
    mock._embedding.bytes_to_vector.return_value = [0.1] * 384
    mock._extract_tags.return_value = ["test"]
    mock._recall_bm25_weight = 0.15
    mock._reranker = MagicMock()
    mock._storage = MagicMock()
    return mock


class TestHybridSearchMode:
    def test_hybrid_mode_returns_both(self):
        engine = make_memory_engine()
        hybrid = HybridSearch(engine, rag_source=engine)

        mem_results = [
            RecallResult(content="memory result", score=0.9, source="memory", category="success"),
        ]
        rag_results = [
            RecallResult(content="rag result", score=0.8, source="rag", category="knowledge"),
        ]
        engine.recall.return_value = mem_results
        hybrid._rag_recall = MagicMock(return_value=rag_results)

        results = hybrid.search("test query", mode="hybrid", top_k=5)
        assert len(results) >= 1

    def test_memories_mode_uses_only_memory(self):
        engine = make_memory_engine()
        hybrid = HybridSearch(engine, rag_source=engine)

        mem_results = [
            RecallResult(content="mem only", score=0.9, source="memory", category="success"),
        ]
        engine.recall.return_value = mem_results

        results = hybrid.search("test query", mode="memories", top_k=5)
        assert all(r.source == "memory" for r in results)
        assert len(results) >= 1

    def test_rag_mode_uses_only_rag(self):
        engine = make_memory_engine()
        hybrid = HybridSearch(engine, rag_source=engine)

        rag_results = [
            RecallResult(content="rag content", score=0.85, source="rag", category="knowledge"),
        ]
        hybrid._rag_recall = MagicMock(return_value=rag_results)

        results = hybrid.search("test query", mode="rag", top_k=5)
        assert all(r.source == "rag" for r in results)

    def test_invalid_mode_raises(self):
        engine = make_memory_engine()
        hybrid = HybridSearch(engine, rag_source=engine)
        with pytest.raises(ValueError):
            hybrid.search("test", mode="invalid")

    def test_hybrid_deduplicates(self):
        engine = make_memory_engine()
        hybrid = HybridSearch(engine, rag_source=engine)

        same_content = "shared content"
        mem_results = [
            RecallResult(content=same_content, score=0.9, source="memory", category="success"),
        ]
        rag_results = [
            RecallResult(content=same_content, score=0.85, source="rag", category="knowledge"),
        ]
        engine.recall.return_value = mem_results
        hybrid._rag_recall = MagicMock(return_value=rag_results)

        results = hybrid.search("test", mode="hybrid", top_k=5)
        contents = [r.content for r in results]
        assert contents.count(same_content) <= 1

    def test_hybrid_merges_scores(self):
        engine = make_memory_engine()
        hybrid = HybridSearch(engine, rag_source=engine)

        mem_results = [
            RecallResult(content="mem-A", score=0.8, source="memory", category="success"),
        ]
        rag_results = [
            RecallResult(content="rag-A", score=0.7, source="rag", category="knowledge"),
        ]
        engine.recall.return_value = mem_results
        hybrid._rag_recall = MagicMock(return_value=rag_results)

        results = hybrid.search("test", mode="hybrid", top_k=5)
        assert len(results) == 2

    def test_rag_search_facts_fallback_uses_named_placeholder_score(self):
        from types import SimpleNamespace

        class FactSource:
            def search_facts(self, query, limit=5):
                return [SimpleNamespace(fact="fact one"), SimpleNamespace(fact="fact two")]

        engine = make_memory_engine()
        hybrid = HybridSearch(engine, rag_source=FactSource())
        results = hybrid.search("test", mode="rag", top_k=5)
        assert [r.score for r in results] == [HybridSearch.FACT_FALLBACK_SCORE] * 2
        assert all(r.source == "rag" for r in results)