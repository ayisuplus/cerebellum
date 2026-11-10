"""Regression tests for reranker fusion formula, time-keyword tokenization,
brute-force truncation warning, weighted cosine clamp, and hybrid fusion
scale normalization."""

import logging
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from evolver.config import RerankerConfig
from evolver.hybrid_search import HybridSearch
from evolver.models import Memory, RecallResult
from evolver.retrieval import RetrievalEngine


def _whitespace_tags(text):
    return [
        token.strip(".,:;!?\n").lower()
        for token in text.split()
        if token.strip(".,:;!?\n")
    ]


def make_engine_mock():
    engine = MagicMock()
    engine._RECALL_CANDIDATE_MULTIPLIER = 2
    engine._recall_bm25_weight = 0.15
    engine._reranker = RerankerConfig()
    engine._link = None
    engine._ann = None
    engine._extract_tags.side_effect = _whitespace_tags
    return engine


# --- Finding 1: reranker relevance must dominate metadata constants ---

def test_rerank_relevance_dominates_metadata():
    """A highly relevant but metadata-hostile item must outrank a slightly
    less relevant item with every metadata boost (evergreen/recent/success).

    Old additive formula ranked the decorated item first (0.567 vs 0.451);
    the multiplicative formula ranks the relevant one first.
    """
    retrieval = RetrievalEngine(make_engine_mock())
    now = datetime.now(timezone.utc)
    relevant = RecallResult(
        content="alpha beta gamma",  # 16 chars, jaccard 0.5 vs query
        score=0.06, source="memory", category="failure",
        lifecycle="stale", created_at=(now - timedelta(days=365)).isoformat(),
    )
    decorated = RecallResult(
        content="alpha beta delta",  # 16 chars, jaccard 0.5 vs query
        score=0.05, source="memory", category="success",
        lifecycle="evergreen", created_at=now.isoformat(),
    )
    fusion_norm = 4.0 / 61.0  # RRF theoretical max with 4 active channels

    out = retrieval._rerank(
        "now alpha beta", [decorated, relevant],
        query_vec=[1.0], fusion_norm=fusion_norm,
    )

    assert out[0].content == "alpha beta gamma"
    # Pinned formula values (see _rerank docstring):
    # relevant:  fused = 0.06*61/4 = 0.915, jaccard = 0.5
    #   relevance = 0.4*0.915 + 0.2*0.5 = 0.466
    #   lenp = 1/(1+ln(1.16)); mult = (1+.1*(2*lenp-1)) * 0.99 * ~1.0 * 0.95
    # decorated: fused = 0.05*61/4 = 0.7625
    #   relevance = 0.4*0.7625 + 0.1 = 0.405
    #   mult = (1+.1*(2*lenp-1)) * 1.01 * 1.02 * 1.03
    assert out[0].score == pytest.approx(0.4708, abs=1e-4)
    assert out[1].score == pytest.approx(0.4616, abs=1e-4)


def test_rerank_clamps_weighted_fusion_above_one():
    """Weighted fusion scores can exceed 1.0 (weights sum > 1); the reranker
    clamps the fusion channel to [0, 1] when clamp_fusion is set."""
    retrieval = RetrievalEngine(make_engine_mock())
    result = RecallResult(
        content="alpha beta", score=1.15, source="memory", category="note",
    )

    out = retrieval._rerank(
        "alpha beta", [result], query_vec=[1.0],
        fusion_norm=1.0, clamp_fusion=True,
    )

    # fused clamped to 1.0; jaccard = 1.0 -> relevance = 0.4 + 0.2 = 0.6
    # lenp = 1/(1+ln(1.1)); mult = 1 + 0.1*(2*lenp - 1); others neutral
    lenp = 1.0 / (1.0 + math.log(1.1))
    expected = round(0.6 * (1.0 + 0.1 * (2.0 * lenp - 1.0)), 4)
    assert out[0].score == pytest.approx(expected, abs=1e-4)


# --- Finding 3: time keywords match tokens, not substrings ---

@pytest.mark.parametrize("query", [
    "do you know about snow",  # 'now' only inside know/snow
    "i knew it already",       # 'new' only inside knew
])
def test_substring_time_keywords_do_not_trigger_recency(query):
    retrieval = RetrievalEngine(make_engine_mock())
    now = datetime.now(timezone.utc)
    recent = RecallResult(
        content="alpha beta", score=0.5, source="memory",
        category="note", created_at=now.isoformat(),
    )
    old = RecallResult(
        content="alpha beta", score=0.5, source="memory",
        category="note", created_at=(now - timedelta(days=365)).isoformat(),
    )

    out = retrieval._rerank(query, [old, recent], query_vec=[1.0])

    # No time keyword token -> no recency differentiation at all.
    assert out[0].score == out[1].score


def test_real_time_keyword_still_triggers_recency():
    retrieval = RetrievalEngine(make_engine_mock())
    now = datetime.now(timezone.utc)
    recent = RecallResult(
        content="alpha beta", score=0.5, source="memory",
        category="note", created_at=now.isoformat(),
    )
    old = RecallResult(
        content="alpha beta", score=0.5, source="memory",
        category="note", created_at=(now - timedelta(days=365)).isoformat(),
    )

    out = retrieval._rerank("what is new in snow", [old, recent], query_vec=[1.0])

    assert out[0].score > out[1].score
    assert out[0].created_at == recent.created_at


# --- Finding 2: brute-force truncation is observable ---

def make_brute_force_engine(memories, batches):
    engine = make_engine_mock()
    engine._ensure_vector_store_synced.return_value = False
    engine._embedding.embed_single.return_value = [1.0, 0.0, 0.0]
    engine._embedding.bytes_to_vector.return_value = [1.0, 0.0, 0.0]
    by_id = {m.id: m for m in memories}
    engine._storage.get_memories_by_ids.side_effect = lambda ids: [
        by_id[i] for i in ids if i in by_id
    ]
    engine._storage.get_all_memories_with_embeddings_batched.side_effect = (
        lambda batch_size: iter(batches)
    )
    engine._storage.search_memories_lexical.return_value = []
    engine._storage.query_nodes_batch.return_value = []
    return engine


def test_brute_force_truncation_warns(caplog):
    memories = [
        Memory(id=i, content=f"mem number {i}", category="note", embedding=b"\x00")
        for i in range(1, 13)
    ]
    engine = make_brute_force_engine(memories, [memories[:10], memories[10:]])
    retrieval = RetrievalEngine(engine)

    with caplog.at_level(logging.WARNING, logger="evolver.retrieval"):
        retrieval.recall("mem", top_k=2, max_scan=10)

    truncated = [r for r in caplog.records if "truncated" in r.message]
    assert len(truncated) == 1
    assert "max_scan=10" in truncated[0].message


def test_brute_force_untruncated_scan_does_not_warn(caplog):
    memories = [
        Memory(id=i, content=f"mem number {i}", category="note", embedding=b"\x00")
        for i in range(1, 9)
    ]
    engine = make_brute_force_engine(memories, [memories])
    retrieval = RetrievalEngine(engine)

    with caplog.at_level(logging.WARNING, logger="evolver.retrieval"):
        retrieval.recall("mem", top_k=2, max_scan=10)

    assert not any("truncated" in r.message for r in caplog.records)


# --- Finding 5: weighted fusion clamps negative cosine ---

def test_weighted_fusion_clamps_negative_cosine():
    engine = make_engine_mock()
    engine._recall_bm25_weight = 0.0
    retrieval = RetrievalEngine(engine)
    neg = Memory(id=1, content="neg", category="note", importance=0.0)
    pos = Memory(id=2, content="pos", category="note", importance=0.0)

    results = retrieval._weighted_fusion(
        {1, 2}, {1: neg, 2: pos},
        semantic_ranked=[(2, 0.5), (1, -0.5)],
        graph_ranked=[], link_ranked=[], bm25_ranked=[],
        top_k=2, recall_weights=(1.0, 0.0, 0.0, 0.0),
    )

    assert results[0].score == 0.5
    # Raw cosine -0.5 used to subtract under its weight; now clamped to 0.
    assert results[1].score == 0.0


# --- Finding 6: hybrid fusion is RRF (rank-based corroboration) ---

def test_hybrid_rrf_corroborates_cross_source_duplicates():
    engine = MagicMock()
    hybrid = HybridSearch(engine, rag_source=engine)
    engine.recall.return_value = [
        RecallResult(content="shared", score=0.65, source="memory", category="success"),
        RecallResult(content="mem only", score=0.35, source="memory", category="success"),
    ]
    hybrid._rag_recall = MagicMock(return_value=[
        RecallResult(content="shared", score=0.7, source="rag", category="fact"),
        RecallResult(content="rag only", score=0.7, source="rag", category="fact"),
    ])

    results = hybrid.search("q", mode="hybrid", top_k=5)

    by_content = {r.content: r for r in results}
    # Duplicate content merged exactly once.
    assert len(by_content) == 3
    # Rank 1 in both channels -> corroborated maximum 1.0 (old min-max + MAX
    # capped it at the memory weight 0.6).
    assert by_content["shared"].score == pytest.approx(1.0, abs=1e-9)
    assert by_content["shared"].source == "hybrid"
    assert results[0].content == "shared"
    # Single-channel rank 2 = (1/(60+2)) / (2/(60+1)).
    expected = (1.0 / 62) / (2.0 / 61)
    assert by_content["mem only"].score == pytest.approx(expected, abs=1e-9)
    assert by_content["rag only"].score == pytest.approx(expected, abs=1e-9)


def test_hybrid_rrf_rank_dominates_source_score_scale():
    engine = MagicMock()
    hybrid = HybridSearch(engine, rag_source=engine)
    # "both" is memory rank 2 and rag rank 1; "mem top" is memory rank 1 with
    # a far higher source score. RRF corroboration puts "both" first.
    engine.recall.return_value = [
        RecallResult(content="mem top", score=0.9, source="memory", category="success"),
        RecallResult(content="both", score=0.4, source="memory", category="success"),
    ]
    hybrid._rag_recall = MagicMock(return_value=[
        RecallResult(content="both", score=0.01, source="rag", category="fact"),
    ])

    results = hybrid.search("q", mode="hybrid", top_k=5)

    assert results[0].content == "both"
    assert results[0].source == "hybrid"
    expected = (1.0 / 62 + 1.0 / 61) / (2.0 / 61)
    assert results[0].score == pytest.approx(expected, abs=1e-9)


def test_hybrid_rrf_single_channel_normalizes_to_one():
    engine = MagicMock()
    hybrid = HybridSearch(engine, rag_source=engine)
    engine.recall.return_value = [
        RecallResult(content="only mem", score=0.42, source="memory", category="success"),
    ]
    hybrid._rag_recall = MagicMock(return_value=[])

    results = hybrid.search("q", mode="hybrid", top_k=5)

    # Sole active channel: rank-1 item normalizes to 1.0, source preserved.
    assert results[0].score == pytest.approx(1.0, abs=1e-9)
    assert results[0].source == "memory"
