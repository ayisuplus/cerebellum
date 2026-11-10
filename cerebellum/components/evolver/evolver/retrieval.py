"""Multi-signal retrieval pipeline for evolver memories."""

from __future__ import annotations
import logging
import math
import re
from typing import TYPE_CHECKING

import numpy as np

from evolver.models import Memory, RecallResult
from evolver.config import DEFAULT_MAX_SCAN
from evolver.stopwords import STOPWORDS
from evolver.stack import truncate_content
from evolver.utils import cosine_similarity, embedder_identity_of, embedder_tags_compatible

if TYPE_CHECKING:
    from evolver.memory import MemoryEngine

# Reciprocal Rank Fusion constant shared by the multi-signal recall pipeline
# and HybridSearch's memory/RAG fusion.
DEFAULT_RRF_K = 60

logger = logging.getLogger(__name__)
# Time-sensitive query detection: single Latin words are token-matched so
# 'now' doesn't match 'know'/'snow' and 'new' doesn't match 'knew';
# multi-word phrases and CJK keywords (no token boundaries) stay
# substring-matched.
_TIME_WORDS = frozenset({
    "today", "recent", "latest", "new", "current", "now", "yesterday",
})
_TIME_PHRASES = ("this week", "this month", "刚刚", "最近", "今天", "昨天")


class RetrievalEngine:
    """Handles multi-signal memory retrieval."""

    def __init__(self, memory_engine: MemoryEngine):
        self._engine = memory_engine

    def recall(self, query: str, top_k: int = 5,
               recall_weights: tuple = (0.6, 0.15, 0.1, 0.15),
               max_scan: int = DEFAULT_MAX_SCAN,
               method: str = "rrf",
               rrf_k: int = DEFAULT_RRF_K) -> list[RecallResult]:
        """Recall relevant memories via multi-signal retrieval.

        Two fusion methods:
        - "rrf": Reciprocal Rank Fusion (default) — rank-based, no weight tuning needed
        - "weighted": Weighted score sum — legacy, requires tuned weights

        Uses VectorStore (Qdrant/InMemory) when available, falls back to ANN index,
        then brute-force scan.
        """
        e = self._engine
        query_vec = np.array(e._embedding.embed_single(query))
        candidate_mult = e._RECALL_CANDIDATE_MULTIPLIER
        pool_size = top_k * candidate_mult

        # --- Channel 1: Semantic vector similarity ---
        semantic_ranked: list[tuple[int, float]] = []  # (memory_id, score)

        # Priority: VectorStore > ANN > brute-force
        vector_store_used = False
        if e._ensure_vector_store_synced():
            try:
                if e._vector_store.count() > 0:
                    # Use VectorStore (Qdrant or InMemory)
                    vs_results = e._vector_store.search(query_vec, top_k=pool_size)
                    semantic_ranked = [(mid, score) for mid, score in vs_results]
                    vector_store_used = True
                    logger.debug("VectorStore recall found %d candidates", len(semantic_ranked))
            except Exception:
                logger.warning(
                    "VectorStore query failed; using local retrieval fallback",
                    exc_info=True,
                )

        if not vector_store_used:
            # Fallback: ANN index or brute-force
            e._ensure_ann()
            if e._ann is not None and e._ann.size > 0:
                ann_results = e._ann.search(query_vec, top_k=pool_size)
                for mid, dist in ann_results:
                    semantic_ranked.append((mid, 1.0 - dist))
                logger.debug("ANN recall found %d candidates", len(semantic_ranked))
            else:
                if max_scan > 0:
                    all_memories = []
                    for batch in e._storage.get_all_memories_with_embeddings_batched(
                        batch_size=min(max_scan, 500),
                    ):
                        all_memories.extend(batch)
                        if len(all_memories) > max_scan:
                            break
                    memories_pool = all_memories[:max_scan]
                    if len(all_memories) > max_scan:
                        # Blind spot: brute-force caps at the newest max_scan
                        # rows while ANN only auto-builds at _ANN_THRESHOLD —
                        # memories in between are silently unreachable.
                        logger.warning(
                            "Brute-force recall scan truncated at max_scan=%d with no "
                            "ANN/VectorStore active; memories beyond the newest %d are "
                            "unreachable for this recall",
                            max_scan, max_scan,
                        )
                else:
                    memories_pool = e._storage.get_all_memories_with_embeddings()

                current_identity = embedder_identity_of(e._embedding)
                for mem in memories_pool:
                    if mem.embedding is None:
                        continue
                    # Rows embedded by a different embedder (e.g. hash fallback
                    # vs model) are incomparable; untagged legacy rows compare.
                    if not embedder_tags_compatible(mem.embedder, current_identity):
                        continue
                    mem_vec = np.array(e._embedding.bytes_to_vector(mem.embedding))
                    sim = cosine_similarity(query_vec, mem_vec)
                    semantic_ranked.append((mem.id, sim))
                semantic_ranked.sort(key=lambda x: x[1], reverse=True)
                semantic_ranked = semantic_ranked[:pool_size]

        semantic_ids = {mid for mid, _ in semantic_ranked}
        semantic_memories = e._storage.get_memories_by_ids(list(semantic_ids))
        # Indexed channels (VectorStore/ANN) cannot filter by embedder tag at
        # query time; drop cross-embedder candidates here instead.
        compatible_ids = {
            m.id for m in semantic_memories
            if embedder_tags_compatible(m.embedder, embedder_identity_of(e._embedding))
        }
        semantic_ranked = [
            (mid, score) for mid, score in semantic_ranked if mid in compatible_ids
        ]
        semantic_ids = {mid for mid, _ in semantic_ranked}
        semantic_memories = [m for m in semantic_memories if m.id in compatible_ids]

        # --- Channel 2: Independent lexical candidate generation ---
        query_tokens = e._extract_tags(query)
        graph_nodes = e._storage.query_nodes_batch(query_tokens) if query_tokens else []
        lexical_terms = list(query_tokens)
        lexical_terms.extend(node.label for node in graph_nodes if node.label)
        lexical_memories = e._storage.search_memories_lexical(
            lexical_terms,
            limit=max_scan,
        )
        bm25_ranked = self._bm25_score(query, lexical_memories)[:pool_size]

        # --- Channel 3: Graph candidates, independent of semantic Top-K ---
        channel_memories: dict[int, Memory] = {
            mem.id: mem
            for mem in [*semantic_memories, *lexical_memories]
            if mem.id is not None
        }
        graph_idf = self._compute_graph_idf(
            graph_nodes, list(channel_memories.values())
        )

        graph_ranked: list[tuple[int, float]] = []
        if graph_nodes:
            graph_scores: dict[int, float] = {}
            for mid, mem in channel_memories.items():
                score = 0.0
                content_lower = mem.content.lower()
                for node in graph_nodes:
                    node_label_lower = node.label.lower()
                    if node_label_lower in content_lower:
                        tf = content_lower.count(node_label_lower)
                        idf = graph_idf.get(node_label_lower, 1.0)
                        score += tf * idf
                if score > 0:
                    graph_scores[mid] = score
            graph_ranked = sorted(
                graph_scores.items(), key=lambda x: x[1], reverse=True
            )[:pool_size]

        candidate_ids = (
            semantic_ids
            | {mid for mid, _ in bm25_ranked}
            | {mid for mid, _ in graph_ranked}
        )
        memories_map = {
            mid: mem for mid, mem in channel_memories.items() if mid in candidate_ids
        }
        missing_ids = candidate_ids - set(memories_map)
        if missing_ids:
            memories_map.update({
                mem.id: mem
                for mem in e._storage.get_memories_by_ids(list(missing_ids))
                if mem.id is not None
            })

        # --- Channel 4: Link boost over the union of independent channels ---
        link_ranked: list[tuple[int, float]] = []
        if e._link:
            try:
                link_scores: dict[int, float] = {}
                query_related = list(candidate_ids)
                for mid in candidate_ids:
                    link_scores[mid] = e._link.compute_link_score(mid, query_related)
                link_ranked = sorted(link_scores.items(), key=lambda x: x[1], reverse=True)
                link_ranked = [(mid, s) for mid, s in link_ranked if s > 0]
            except Exception:
                logger.warning("Link scoring failed", exc_info=True)

        if method == "rrf":
            results = self._rrf_fusion(
                candidate_ids, memories_map,
                semantic_ranked, graph_ranked, link_ranked, bm25_ranked,
                top_k, rrf_k,
            )
            # RRF normalization base: theoretical max = rank 1 in every
            # active channel, i.e. active_channels / (rrf_k + 1).
            active_channels = sum(
                1 for channel in (semantic_ranked, graph_ranked, link_ranked, bm25_ranked)
                if channel
            )
            fusion_norm = active_channels / (rrf_k + 1) if active_channels else 1.0
            clamp_fusion = False
        else:
            results = self._weighted_fusion(
                candidate_ids, memories_map,
                semantic_ranked, graph_ranked, link_ranked, bm25_ranked,
                top_k, recall_weights,
            )
            # Weighted fusion weights can sum above 1.0; clamp instead of
            # dividing by a theoretical max that real candidates never reach.
            fusion_norm = 1.0
            clamp_fusion = True

        # --- Reranker: second-stage refinement ---
        results = self._rerank(query, results, query_vec,
                               fusion_norm=fusion_norm, clamp_fusion=clamp_fusion)

        content_to_id: dict[str, int] = {}
        for mid, m in memories_map.items():
            if m.content in content_to_id:
                logger.warning("Duplicate content detected for memory ids %d and %d; "
                               "access_count may be misattributed",
                               content_to_id[m.content], mid)
            content_to_id[m.content] = mid
        for r in results:
            mid = content_to_id.get(r.content)
            if mid is not None:
                e._storage.update_access_count(mid)

        e._storage.log_event("recall", {"query": query, "results": len(results), "method": method})
        logger.info("Recall returned %d results (method=%s)", len(results), method)
        return results

    def _rrf_fusion(self, candidate_ids, memories_map,
                    semantic_ranked, graph_ranked, link_ranked, bm25_ranked,
                    top_k, rrf_k) -> list[RecallResult]:
        """Reciprocal Rank Fusion: rank-based, no weight tuning."""
        # Build rank maps (mid -> rank position)
        sem_ranks = {mid: r for r, (mid, _) in enumerate(semantic_ranked, start=1)}
        graph_ranks = {mid: r for r, (mid, _) in enumerate(graph_ranked, start=1)}
        link_ranks = {mid: r for r, (mid, _) in enumerate(link_ranked, start=1)}
        bm25_ranks = {mid: r for r, (mid, _) in enumerate(bm25_ranked, start=1)}

        all_mids = set(sem_ranks) | set(graph_ranks) | set(link_ranks) | set(bm25_ranks)
        scored: list[tuple[float, int]] = []
        for mid in all_mids:
            rrf_score = 0.0
            if mid in sem_ranks:
                rrf_score += 1.0 / (rrf_k + sem_ranks[mid])
            if mid in graph_ranks:
                rrf_score += 1.0 / (rrf_k + graph_ranks[mid])
            if mid in link_ranks:
                rrf_score += 1.0 / (rrf_k + link_ranks[mid])
            if mid in bm25_ranks:
                rrf_score += 1.0 / (rrf_k + bm25_ranks[mid])
            scored.append((rrf_score, mid))

        scored.sort(reverse=True)

        results = []
        for score, mid in scored[:top_k]:
            mem = memories_map.get(mid)
            if not mem:
                continue
            related = self._get_related_nodes(mem, graph_ranked, memories_map)
            results.append(RecallResult(
                content=mem.content,
                score=round(score, 4),
                source="memory",
                category=mem.category,
                related_nodes=related,
                lifecycle=getattr(mem, 'lifecycle', 'seed'),
                created_at=mem.created_at,
                snippet=truncate_content(mem.content.strip().replace("\n", " "), 200),
            ))
        return results

    def _weighted_fusion(self, candidate_ids, memories_map,
                         semantic_ranked, graph_ranked, link_ranked, bm25_ranked,
                         top_k, recall_weights) -> list[RecallResult]:
        """Legacy weighted sum fusion."""
        sem_scores = {mid: s for mid, s in semantic_ranked}
        graph_scores = {mid: s for mid, s in graph_ranked}
        link_scores = {mid: s for mid, s in link_ranked}
        bm25_scores = {mid: s for mid, s in bm25_ranked}

        # Normalize scores to [0, 1]; raw cosine similarity can go negative
        # (subtracting under its weight), so clamp it explicitly.
        max_graph = max((s for _, s in graph_ranked), default=1.0) or 1.0
        max_link = max((s for _, s in link_ranked), default=1.0) or 1.0
        max_bm25 = max((s for _, s in bm25_ranked), default=1.0) or 1.0

        w_vec, w_graph, w_imp, w_link = recall_weights
        w_bm25 = self._engine._recall_bm25_weight
        scored: list[tuple[float, int]] = []
        for mid in candidate_ids:
            mem = memories_map.get(mid)
            if not mem:
                continue
            s_sem = min(1.0, max(0.0, sem_scores.get(mid, 0.0)))
            s_graph = graph_scores.get(mid, 0.0) / max_graph
            s_link = link_scores.get(mid, 0.0) / max_link
            s_bm25 = bm25_scores.get(mid, 0.0) / max_bm25
            final = (w_vec * s_sem + w_graph * s_graph + w_imp * mem.importance +
                     w_link * s_link + w_bm25 * s_bm25)
            scored.append((final, mid))

        scored.sort(reverse=True)

        results = []
        for score, mid in scored[:top_k]:
            mem = memories_map[mid]
            related = self._get_related_nodes(mem, graph_ranked, memories_map)
            results.append(RecallResult(
                content=mem.content,
                score=round(score, 4),
                source="memory",
                category=mem.category,
                related_nodes=related,
                lifecycle=getattr(mem, 'lifecycle', 'seed'),
                created_at=mem.created_at,
                snippet=truncate_content(mem.content.strip().replace("\n", " "), 200),
            ))
        return results

    def _rerank(self, query: str, results: list[RecallResult],
                query_vec: np.ndarray,
                fusion_norm: float = 1.0,
                clamp_fusion: bool = False) -> list[RecallResult]:
        """Second-stage reranker for precision refinement.

        Scoring formula (deterministic, relevance-dominated)::

            fused     = r.score / fusion_norm, clamped to [0, 1] when
                        clamp_fusion is set (weighted method, whose weights
                        can sum above 1); for RRF, fusion_norm is the
                        theoretical max over the active channels.
            relevance = cfg.fusion_score * fused + cfg.jaccard * jaccard
            rerank    = relevance * product(1 + cfg.w_i * (factor_i - 1))

        Metadata signals (length, category, recency, lifecycle) enter as
        bounded 1.0-centered multipliers instead of additive constants, so a
        metadata-neutral memory keeps its relevance score unchanged and the
        metadata factors can no longer dwarf the fusion channel. Config
        weights keep their relative influence: fusion : jaccard stays
        cfg.fusion_score : cfg.jaccard, and each metadata weight scales its
        factor's deviation from neutral (1.0).

        Signals:
        1. Normalized fusion score (semantic/graph/link/bm25 channels)
        2. Content overlap (token Jaccard)
        3. Content length multiplier (prefers concise results)
        4. Category multiplier
        5. Temporal grounding multiplier (recency for time-sensitive queries)
        6. Lifecycle multiplier

        Args:
            query: Original query string.
            results: First-stage results to rerank.
            query_vec: Query embedding vector.
            fusion_norm: Maximum achievable fusion score, used to normalize
                r.score to [0, 1].
            clamp_fusion: Clamp the normalized fusion score to [0, 1]
                (weighted fusion can exceed 1.0).

        Returns:
            Reranked results sorted by new scores.
        """
        if not results:
            return results

        query_tokens = set(self._engine._extract_tags(query))

        # Time sensitivity is query-invariant: compute once. Single Latin
        # keywords are token-matched; phrases and CJK keywords use substring.
        query_lower = query.lower()
        query_word_tokens = set(re.findall(r"[a-z0-9]+", query_lower))
        is_time_sensitive = (
            not query_word_tokens.isdisjoint(_TIME_WORDS)
            or any(phrase in query_lower for phrase in _TIME_PHRASES)
        )

        cfg = self._engine._reranker
        reranked: list[tuple[float, RecallResult]] = []

        for r in results:
            # Signal 1: Semantic similarity (already in r.score)
            mem_tokens = set(self._engine._extract_tags(r.content))

            # Signal 2: Token overlap (Jaccard similarity)
            if query_tokens and mem_tokens:
                intersection = query_tokens & mem_tokens
                union = query_tokens | mem_tokens
                jaccard = len(intersection) / len(union) if union else 0.0
            else:
                jaccard = 0.0

            # Signal 3: Content length penalty (prefer concise results)
            content_len = len(r.content)
            len_penalty = 1.0 / (1.0 + math.log(1 + content_len / 100))

            # Signal 4: Category relevance
            category_boost = 1.0
            if r.category in ("success", "insight"):
                category_boost = 1.1
            elif r.category == "failure":
                category_boost = 0.9

            # Signal 5: Temporal grounding (recency boost)
            recency_boost = 1.0
            if is_time_sensitive and r.created_at:
                try:
                    from datetime import datetime, timezone

                    created = datetime.fromisoformat(
                        str(r.created_at).replace("Z", "+00:00")
                    )
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    age_days = max(
                        0.0,
                        (datetime.now(timezone.utc) - created).total_seconds() / 86400.0,
                    )
                    # Smoothly decays from +20% now to effectively neutral.
                    recency_boost = 1.0 + 0.2 * math.exp(-age_days / 30.0)
                except (TypeError, ValueError, OverflowError):
                    logger.debug("Invalid memory created_at: %r", r.created_at)

            # Signal 6: Lifecycle weight
            lifecycle_weights = {
                "seed": 1.0,
                "growing": 1.1,
                "evergreen": 1.3,
                "stale": 0.5,
            }
            lifecycle_boost = lifecycle_weights.get(getattr(r, 'lifecycle', 'seed'), 1.0)

            # Combined reranker score: relevance base times bounded
            # 1.0-centered metadata multipliers (see docstring).
            fused = r.score / fusion_norm if fusion_norm > 0 else 0.0
            if clamp_fusion:
                fused = min(1.0, max(0.0, fused))
            else:
                fused = max(0.0, fused)
            relevance = cfg.fusion_score * fused + cfg.jaccard * jaccard
            multiplier = 1.0
            multiplier *= 1.0 + cfg.len_penalty * (2.0 * len_penalty - 1.0)
            multiplier *= 1.0 + cfg.category * (category_boost - 1.0)
            multiplier *= 1.0 + cfg.recency * (recency_boost - 1.0)
            multiplier *= 1.0 + cfg.lifecycle * (lifecycle_boost - 1.0)
            rerank_score = relevance * multiplier

            reranked.append((rerank_score, r))

        # Sort by reranker score
        reranked.sort(key=lambda x: x[0], reverse=True)

        # Update scores
        results = []
        for score, r in reranked:
            results.append(RecallResult(
                content=r.content,
                score=round(score, 4),
                source=r.source,
                category=r.category,
                related_nodes=r.related_nodes,
                lifecycle=getattr(r, 'lifecycle', 'seed'),
                created_at=r.created_at,
                snippet=r.snippet or truncate_content(r.content.strip().replace("\n", " "), 200),
            ))

        return results

    def _get_related_nodes(self, mem, graph_ranked, memories_map):
        """Extract related graph nodes for a memory."""
        # Re-query graph nodes from memory content tags
        tags = self._engine._extract_tags(mem.content)
        nodes = self._engine._storage.query_nodes_batch(tags) if tags else []
        return [{"label": n.label, "type": n.node_type} for n in nodes
                if n.label.lower() in mem.content.lower()]

    def _compute_graph_idf(self, graph_nodes, memories) -> dict[str, float]:
        """Compute IDF weights for graph node labels across memory corpus.

        Uses a single-pass inverted index (token -> document set) so that
        the common single-word label path is O(tokens + labels) rather than
        O(labels x documents). Multi-word labels fall back to substring scan.
        """
        if not graph_nodes or not memories:
            return {}
        n_docs = len(memories)

        # Single-pass: tokenize each doc once, build inverted index
        token_to_docs: dict[str, set] = {}
        for idx, mem in enumerate(memories):
            tokens = set(re.findall(r'\w+', mem.content.lower()))
            for token in tokens:
                token_to_docs.setdefault(token, set()).add(idx)

        idf: dict[str, float] = {}
        for node in graph_nodes:
            label = node.label.lower()
            # Fast path: single word -> O(1) lookup in inverted index
            if ' ' not in label:
                doc_count = len(token_to_docs.get(label, set()))
            else:
                # Multi-word label -> fall back to substring scan (rare)
                doc_count = sum(1 for mem in memories if label in mem.content.lower())
            idf[label] = math.log((n_docs + 1) / (doc_count + 1)) + 1.0
        return idf

    def recall_by_time(self, query: str, days: int = 7, top_k: int = 5) -> list[RecallResult]:
        """Recall memories filtered by time range.

        Combines semantic search with temporal filtering for time-sensitive queries.

        Args:
            query: Search query.
            days: Only include memories from the last N days.
            top_k: Maximum results.

        Returns:
            List of RecallResult from the specified time range.
        """
        e = self._engine
        # Get recent memories
        recent_memories = e.get_recent_memories(days, limit=200)
        if not recent_memories:
            return []

        # Score only recent memories
        query_vec = np.array(e._embedding.embed_single(query))
        scored: list[tuple[float, Memory]] = []

        for mem in recent_memories:
            if mem.embedding is None:
                continue
            mem_vec = np.array(e._embedding.bytes_to_vector(mem.embedding))
            sim = cosine_similarity(query_vec, mem_vec)
            scored.append((sim, mem))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, mem in scored[:top_k]:
            tags = e._extract_tags(mem.content)
            nodes = e._storage.query_nodes_batch(tags) if tags else []
            related = [{"label": n.label, "type": n.node_type} for n in nodes
                       if n.label.lower() in mem.content.lower()]
            results.append(RecallResult(
                content=mem.content,
                score=round(score, 4),
                source="memory",
                category=mem.category,
                related_nodes=related,
                created_at=mem.created_at,
                snippet=truncate_content(mem.content.strip().replace("\n", " "), 200),
            ))

        return results

    def _bm25_score(self, query: str, memories: list[Memory],
                    k1: float = 1.5, b: float = 0.75) -> list[tuple[int, float]]:
        """BM25 keyword retrieval scoring.

        Args:
            query: Search query.
            memories: List of Memory objects to score.
            k1: Term frequency saturation parameter.
            b: Length normalization parameter.

        Returns:
            List of (memory_id, bm25_score) tuples, sorted by score descending.
        """
        if not memories:
            return []

        # Tokenize query
        query_tokens = self._engine._extract_tags(query)
        if not query_tokens:
            return []

        # Build inverted index: token -> {doc_idx: tf}
        inverted_index: dict[str, dict[int, int]] = {}
        doc_lens: list[int] = []

        for idx, mem in enumerate(memories):
            tokens = self._engine._extract_tags(mem.content)
            doc_lens.append(len(tokens))
            for token in tokens:
                postings = inverted_index.setdefault(token, {})
                postings[idx] = postings.get(idx, 0) + 1

        # BM25 length normalization must use the same token unit as doc_len.
        n_docs = len(memories)
        avg_doc_len = sum(doc_lens) / n_docs if n_docs > 0 else 1.0
        avg_doc_len = avg_doc_len or 1.0

        # Score each document
        scored: list[tuple[int, float]] = []
        for idx, mem in enumerate(memories):
            score = 0.0
            doc_len = doc_lens[idx]

            for token in query_tokens:
                if token not in inverted_index:
                    continue

                # TF (term frequency)
                tf = inverted_index[token].get(idx, 0)
                if tf == 0:
                    continue

                # IDF (inverse document frequency)
                doc_freq = len(inverted_index[token])
                idf = math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)

                # BM25 formula
                tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
                score += idf * tf_norm

            if score > 0:
                scored.append((mem.id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
