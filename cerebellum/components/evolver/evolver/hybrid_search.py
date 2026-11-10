from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from evolver.models import RecallResult
from evolver.retrieval import DEFAULT_RRF_K

if TYPE_CHECKING:
    from evolver.memory import MemoryEngine

logger = logging.getLogger(__name__)


class SearchMode(Enum):
    HYBRID = "hybrid"
    MEMORIES = "memories"
    RAG = "rag"


class HybridSearch:
    """Unified search interface combining memory recall with RAG retrieval.

    Modes:
    - hybrid: Merge memory recall + RAG results, deduplicate, re-rank.
    - memories: Search only the memory engine (existing recall path).
    - rag: Search only the RAG source (external knowledge/documents).
    """

    # RRF constant shared with retrieval's multi-signal fusion.
    RRF_K = DEFAULT_RRF_K
    # search_facts provides no relevance score; this is a display placeholder
    # only — fusion ordering comes from source rank, never from this value.
    FACT_FALLBACK_SCORE = 0.7

    def __init__(self, memory_engine, rag_source=None):
        self._memory = memory_engine
        self._rag_source = rag_source

    def search(self, query: str, mode: str = "hybrid", top_k: int = 5,
               **kwargs) -> list[RecallResult]:
        mode = SearchMode(mode)

        if mode == SearchMode.MEMORIES:
            return self._memory_recall(query, top_k, **kwargs)
        elif mode == SearchMode.RAG:
            return self._rag_recall(query, top_k, **kwargs)
        elif mode == SearchMode.HYBRID:
            return self._hybrid_recall(query, top_k, **kwargs)
        else:
            raise ValueError(f"Unknown search mode: {mode}")

    def _memory_recall(self, query: str, top_k: int, **kwargs) -> list[RecallResult]:
        return self._memory.recall(query, top_k=top_k, **kwargs)

    def _rag_recall(self, query: str, top_k: int, **kwargs) -> list[RecallResult]:
        if self._rag_source is None:
            logger.warning("RAG source not configured, returning empty results")
            return []
        if hasattr(self._rag_source, "recall"):
            raw = self._rag_source.recall(query, top_k=top_k, **kwargs)
            return [
                RecallResult(
                    content=r.content,
                    score=r.score,
                    source="rag",
                    category=r.category,
                    related_nodes=r.related_nodes,
                    lifecycle=getattr(r, "lifecycle", "seed"),
                    snippet=getattr(r, "snippet", ""),
                )
                for r in raw
            ]
        if hasattr(self._rag_source, "search_facts"):
            facts = self._rag_source.search_facts(query, limit=top_k)
            return [
                RecallResult(
                    content=f.fact if hasattr(f, "fact") else str(f),
                    score=self.FACT_FALLBACK_SCORE,
                    source="rag",
                    category="fact",
                    related_nodes=[],
                    snippet="",
                )
                for f in facts
            ]
        return []

    def _hybrid_recall(self, query: str, top_k: int, **kwargs) -> list[RecallResult]:
        mem_results = self._memory_recall(query, top_k=top_k * 2, **kwargs)
        rag_results = self._rag_recall(query, top_k=top_k * 2, **kwargs)

        # Reciprocal Rank Fusion with the same constant and formula as
        # retrieval's multi-signal RRF: rank-based, so the two sources'
        # incompatible score scales (memory post-rerank ~0.35-0.65 vs RAG
        # fallback placeholder) need no per-source normalization, and a
        # duplicate found by both channels is corroborated (contributions
        # add) instead of capped. Per channel, ties keep the source's
        # returned order (stable sort).
        channels = [
            sorted(results, key=lambda r: r.score, reverse=True)
            for results in (mem_results, rag_results)
        ]

        fused: dict[str, dict] = {}
        for ranked in channels:
            for rank, r in enumerate(ranked, start=1):
                key = r.content.strip().lower()
                entry = fused.setdefault(
                    key, {"best": r, "score": 0.0, "sources": set()}
                )
                entry["score"] += 1.0 / (self.RRF_K + rank)
                entry["sources"].add(r.source)

        # Same normalization as retrieval: theoretical max = rank 1 in every
        # active channel, i.e. active_channels / (RRF_K + 1).
        active = sum(1 for ranked in channels if ranked)
        norm = active / (self.RRF_K + 1) if active else 1.0
        merged = [
            RecallResult(
                content=entry["best"].content,
                score=entry["score"] / norm,
                source="hybrid" if len(entry["sources"]) > 1 else entry["best"].source,
                category=entry["best"].category,
                related_nodes=entry["best"].related_nodes,
                lifecycle=getattr(entry["best"], "lifecycle", "seed"),
                snippet=entry["best"].snippet or "",
            )
            for entry in fused.values()
        ]
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[:top_k]