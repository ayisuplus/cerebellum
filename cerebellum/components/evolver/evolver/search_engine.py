"""Unified search engine dispatching across vector, hybrid, memory, and auto strategies."""

from __future__ import annotations

import re
import time
from typing import Any

from evolver.models import RecallResult


class SearchEngine:
    """Route queries to the right backend (vector / hybrid / memory / auto)."""

    _TIME_KEYWORDS_EN = (
        "latest",
        "today",
        "yesterday",
        "this week",
        "recent",
        "new",
    )
    _TIME_KEYWORDS_ZH = ("最近", "刚刚", "今天", "昨天")

    _FACT_KEYWORDS_EN = (
        "what is",
        "how to",
        "difference between",
        "why",
        "meaning of",
    )
    _FACT_KEYWORDS_ZH = ("什么是", "为什么", "如何", "怎样")

    def __init__(
        self,
        memory_engine: Any,
        hybrid_search: Any,
        retrieval_engine: Any,
        vector_store: Any,
        storage: Any,
    ) -> None:
        self._memory_engine = memory_engine
        self._hybrid_search = hybrid_search
        self._retrieval_engine = retrieval_engine
        self._vector_store = vector_store
        self._storage = storage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search(
        self, query: str, strategy: str = "hybrid", top_k: int = 5
    ) -> list[RecallResult]:
        if strategy == "auto":
            routed = self._route(query)
            if routed == "memory" and self._is_time_sensitive(query.lower(), query):
                return self._retrieval_engine.recall_by_time(query, top_k=top_k)
            return self._dispatch(routed, query, top_k)

        if strategy in ("vector", "hybrid", "memory"):
            return self._dispatch(strategy, query, top_k)

        raise ValueError(f"Unknown search strategy: {strategy!r}")

    def search_with_meta(
        self, query: str, strategy: str = "hybrid", top_k: int = 5
    ) -> dict:
        start = time.perf_counter()
        strategy_used = self._route(query) if strategy == "auto" else strategy
        results = self._dispatch(strategy_used, query, top_k)
        timing_ms = (time.perf_counter() - start) * 1000.0
        return {
            "results": results,
            "strategy_used": strategy_used,
            "timing_ms": timing_ms,
        }

    def list_strategies(self) -> list[dict]:
        return [
            {"name": "vector", "description": "Vector similarity search via vector_store."},
            {"name": "hybrid", "description": "Hybrid search combining vector + keyword signals."},
            {"name": "memory", "description": "Memory recall via retrieval_engine (semantic + temporal)."},
            {"name": "auto", "description": "Route the query to the best strategy automatically."},
        ]

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------
    def _route(self, query: str) -> str:
        q = (query or "").strip()
        lower = q.lower()

        if self._is_time_sensitive(lower, q):
            return "memory"
        if self._is_simple_keyword(q):
            return "vector"
        if self._is_fact_query(lower, q):
            return "memory"
        return "hybrid"

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    def _dispatch(self, strategy: str, query: str, top_k: int) -> list[RecallResult]:
        if strategy == "vector":
            return self._vector_search(query, top_k)
        if strategy == "hybrid":
            return self._hybrid_search.search(query, top_k=top_k)
        if strategy == "memory":
            return self._retrieval_engine.recall(query, top_k=top_k)
        raise ValueError(f"Unknown search strategy: {strategy!r}")

    def _vector_search(self, query: str, top_k: int) -> list[RecallResult]:
        embedding = self._memory_engine.embed_single(query)
        hits = self._vector_store.search(embedding, top_k)
        results: list[RecallResult] = []
        for hit in hits:
            doc_id, score = hit[0], hit[1]
            results.append(
                RecallResult(
                    content=f"id:{doc_id}",
                    score=float(score),
                    source="vector",
                    category="general",
                )
            )
        return results

    # ------------------------------------------------------------------
    # Routing helpers
    # ------------------------------------------------------------------
    def _is_time_sensitive(self, lower: str, original: str) -> bool:
        for kw in self._TIME_KEYWORDS_EN:
            if kw in lower:
                return True
        for kw in self._TIME_KEYWORDS_ZH:
            if kw in original:
                return True
        return False

    def _is_simple_keyword(self, query: str) -> bool:
        # 1-2 tokens → simple keyword. Use whitespace for English/ASCII;
        # for Chinese, each character counts as a token.
        stripped = query.strip()
        if not stripped:
            return False
        if self._has_chinese(stripped):
            return 1 <= len(stripped) <= 2
        tokens = stripped.split()
        return 1 <= len(tokens) <= 2

    def _is_fact_query(self, lower: str, original: str) -> bool:
        for kw in self._FACT_KEYWORDS_EN:
            if kw in lower:
                return True
        for kw in self._FACT_KEYWORDS_ZH:
            if kw in original:
                return True
        return False

    @staticmethod
    def _has_chinese(text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", text))
