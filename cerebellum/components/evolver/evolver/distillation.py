"""Distillation engine: bridge between archive dead-data tier and
experience tier. Extracts experiences from archived records via LLM,
builds knowledge graphs, and establishes cross-memory links."""

import asyncio
import logging
from typing import Optional

from evolver.models import Memory

logger = logging.getLogger(__name__)

DISTILL_PROMPTS = {
    "zh": (
        "你是一个经验提取器。从以下归档数据中提取值得记住的经验教训。\n\n"
        "规则：\n"
        "- 每条经验必须自包含、原子化\n"
        "- 提取核心教训、关键发现、可重复使用的解决方案\n"
        "- 去掉无关细节、日志噪音、格式标记\n"
        "- 如果内容包含问题-解决方案模式，明确提炼\n\n"
        "输出格式（纯JSON）：\n"
        '{"experiences": [{"content": "经验内容", "category": "类别", "tags": ["标签"]}]}\n\n'
        '如果没有值得提取的内容，返回 {"experiences": []}'
    ),
    "en": (
        "You are an experience extractor. Extract memorable lessons from the "
        "following archived data.\n\n"
        "Rules:\n"
        "- Each experience must be self-contained and atomic\n"
        "- Extract core lessons, key findings, reusable solutions\n"
        "- Remove irrelevant details, log noise, formatting artifacts\n"
        "- If content contains problem-solution patterns, extract them explicitly\n\n"
        "Output format (pure JSON):\n"
        '{"experiences": [{"content": "experience text", "category": "category", '
        '"tags": ["tag"]}]}\n\n'
        'Return {"experiences": []} if nothing worth extracting.'
    ),
}


class DistillationEngine:
    """Bridge between archive dead-data tier and experience tier.

    Pipeline:
        1. distill()      — pull archive records, LLM extract, store as memories
        2. build_graph()  — extract entities from memories, build graph nodes/edges
        3. build_links()  — similarity + entity links between memories

    Usage::

        engine = DistillationEngine(archive, storage, graph, link, llm=llm)
        result = engine.distill(kind="log", limit=50)
        engine.build_graph(result["memory_ids"], texts)
        engine.build_links(result["memory_ids"], texts)
    """

    def __init__(self, archive_store, storage, graph_engine, link_engine,
                 llm_client=None, lang="zh"):
        self._archive = archive_store
        self._storage = storage
        self._graph = graph_engine
        self._link = link_engine
        self._llm = llm_client
        self._lang = lang

    # ── public API ──

    def distill(self, kind=None, limit=100) -> dict:
        """Pull archive records, extract experiences via LLM, store as memories.

        Args:
            kind: Filter by archive record kind (None = all).
            limit: Max records to process.

        Returns:
            dict with processed, stored, skipped, memory_ids.
        """
        processed = 0
        stored = 0
        skipped = 0
        memory_ids = []

        records = self._fetch_archive_records(kind=kind, limit=limit)
        if not records:
            logger.info("No archive records to distill")
            return {"processed": 0, "stored": 0, "skipped": 0, "memory_ids": []}

        for record in records:
            processed += 1
            experience = self._extract_experience(record)
            if experience is None:
                skipped += 1
                continue

            mem_id = self._store_memory(experience, record)
            if mem_id is not None:
                memory_ids.append(mem_id)
                stored += 1
            else:
                skipped += 1

        logger.info(
            "Distillation: %d processed, %d stored, %d skipped",
            processed, stored, skipped,
        )
        return {
            "processed": processed,
            "stored": stored,
            "skipped": skipped,
            "memory_ids": memory_ids,
        }

    def build_graph(self, memory_ids, texts) -> dict:
        """Extract entities from memories and build knowledge graph nodes/edges.

        Each extracted entity is linked back to its source memory.

        Args:
            memory_ids: List of memory IDs.
            texts: Corresponding list of text contents (same order).

        Returns:
            dict with node_count and link_count.
        """
        node_count = 0
        link_count = 0

        for mid, text in zip(memory_ids, texts):
            if not text or not text.strip():
                continue
            node_ids = self._graph.build_from_text(text)
            if node_ids:
                node_count += len(node_ids)
                for nid in node_ids:
                    try:
                        self._storage.insert_link(
                            "memory", mid, "graph_node", nid,
                            "distill_entity", 1.0,
                        )
                        link_count += 1
                    except Exception as e:
                        logger.debug("Link insert failed (mem=%d, node=%d): %s",
                                     mid, nid, e)

        logger.info("Graph built: %d nodes, %d links to memories", node_count, link_count)
        return {"node_count": node_count, "link_count": link_count}

    def build_links(self, memory_ids, texts) -> dict:
        """Build similarity and entity links between distilled memories.

        Delegates to LinkEngine.auto_link_memory per memory.

        Args:
            memory_ids: List of memory IDs.
            texts: Corresponding list of text contents (same order).

        Returns:
            dict with total_linked count.
        """
        count = 0
        for mid, text in zip(memory_ids, texts):
            if not text or not text.strip():
                continue
            try:
                self._link.auto_link_memory(mid, text)
                count += 1
            except Exception as e:
                logger.debug("Auto-link failed for memory %d: %s", mid, e)

        logger.info("Links built for %d memories", count)
        return {"total_linked": count}

    # ── internal ──

    def _fetch_archive_records(self, kind=None, limit=100) -> list:
        """Fetch archive records for distillation."""
        if kind:
            return self._archive.search_archive(kind, limit=limit)
        return self._archive.list_recent(limit=limit)

    def _extract_experience(self, record: dict) -> Optional[dict]:
        """Extract structured experience from a single archive record via LLM.

        Returns {"content": str, "category": str, "tags": list} or None.
        """
        content = (record.get("content") or "").strip()
        if not content or len(content) < 20:
            return None

        if self._llm and self._llm.available:
            prompt = DISTILL_PROMPTS.get(self._lang, DISTILL_PROMPTS["en"])
            try:
                result = self._llm.call_llm(content, prompt, max_tokens=1000)
                result = self._llm.extract_final_answer(result)
                from evolver.utils import extract_json_from_llm
                parsed = extract_json_from_llm(result) or {}
                experiences = parsed.get("experiences", [])
                if experiences:
                    exp = experiences[0]
                    return {
                        "content": exp.get("content", content[:500]),
                        "category": exp.get("category",
                                            record.get("kind", "archive")),
                        "tags": exp.get("tags", record.get("tags", []) or []),
                    }
            except Exception as e:
                logger.debug("LLM distill failed for archive %s: %s",
                             record.get("id"), e)

        return {
            "content": content[:500],
            "category": record.get("kind", "archive"),
            "tags": record.get("tags", []) or [],
        }

    def _store_memory(self, experience: dict, record: dict) -> Optional[int]:
        """Store a distilled experience as a memory in the experience tier."""
        mem = Memory(
            content=experience["content"],
            category=experience.get("category", "archive"),
            tags=experience.get("tags", []),
            source=record.get("source", "distill"),
            lifecycle="distilled",
        )
        try:
            return self._storage.insert_memory(mem)
        except Exception as e:
            logger.warning("Failed to store distilled memory: %s", e)
            return None

    # ── async wrappers ──

    async def adistill(self, *args, **kwargs) -> dict:
        """Async version of distill — runs sync distill in a thread."""
        return await asyncio.to_thread(self.distill, *args, **kwargs)

    async def abuild_graph(self, *args, **kwargs) -> dict:
        """Async version of build_graph — runs sync build_graph in a thread."""
        return await asyncio.to_thread(self.build_graph, *args, **kwargs)

    async def abuild_links(self, *args, **kwargs) -> dict:
        """Async version of build_links — runs sync build_links in a thread."""
        return await asyncio.to_thread(self.build_links, *args, **kwargs)
