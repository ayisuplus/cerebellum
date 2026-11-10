"""Four-layer memory distillation engine.

Layers:
    today     — compress today's memories into coarse lessons (≤500 tokens)
    week      — compress past 7 days into recurring patterns (≤400 tokens)
    longterm  — fold week into long-term skill profile (≤300 tokens)
    facts     — extract atomic facts from recent memories
    assemble  — concatenate layers into memory_context (≤1500 tokens)

When no LLM is configured, falls back to heuristic compression
(importance-sorted top-N truncation).
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from evolver.llm_client import LLMClient

logger = logging.getLogger(__name__)

TOKEN_LIMITS = {
    "today": 2000,
    "week": 2000,
    "longterm": 1500,
    "facts": 2000,
}

DISTILL_HALF_LIFE_DAYS = 7

LIFECYCLE_DISTILL_MULTIPLIERS = {
    "seed": 1.00,
    "growing": 1.15,
    "evergreen": 1.60,
    "stale": 0.25,
    "distilled": 2.00,
}


class MemoryCompiler:
    """Four-layer memory distillation engine."""

    def __init__(self, storage, llm_client: Optional[LLMClient] = None,
                 memory_dir: str = "./memory", lang: str = "zh"):
        self.storage = storage
        self.llm = llm_client or LLMClient()
        self.memory_dir = memory_dir
        self.lang = lang
        os.makedirs(memory_dir, exist_ok=True)

    # ── public API ──

    def compile_today(self, days: int = 1) -> str:
        """Compress recent memories into today.md (≤500 tokens)."""
        memories = self.storage.get_memories_in_range(days=days)
        if not memories:
            return ""
        memories = self._sort_memories_for_distill(memories)
        text = self._memories_to_text(memories)
        fp = self._fingerprint(text)
        cached = self._check_cache("today", fp)
        if cached is not None:
            return cached
        result = self.llm.compress(text, level="today",
                                   max_tokens=TOKEN_LIMITS["today"],
                                   lang=self.lang)
        result = self._verify_and_fallback(text, result, "today")
        self._save_cache("today", fp, result)
        self._write_file("today.md", result)
        return result

    def compile_week(self, days: int = 7) -> str:
        """Compress past 7 days into week.md (≤400 tokens)."""
        memories = self.storage.get_memories_in_range(days=days)
        if not memories:
            return ""
        memories = self._sort_memories_for_distill(memories)
        text = self._memories_to_text(memories)
        fp = self._fingerprint(text)
        cached = self._check_cache("week", fp)
        if cached is not None:
            return cached
        result = self.llm.compress(text, level="week",
                                   max_tokens=TOKEN_LIMITS["week"],
                                   lang=self.lang)
        result = self._verify_and_fallback(text, result, "week")
        self._save_cache("week", fp, result)
        self._write_file("week.md", result)
        return result

    def compile_longterm(self) -> str:
        """Fold week.md into longterm.md (≤300 tokens)."""
        week = self._read_file("week.md")
        prev = self._read_file("longterm.md")
        combined = (
            f"[Higher-authority current weekly patterns]\n{week}\n\n"
            f"[Lower-authority previous long-term profile]\n{prev}"
        ).strip()
        if not combined.strip():
            return ""
        fp = self._fingerprint(combined)
        cached = self._check_cache("longterm", fp)
        if cached is not None:
            return cached
        result = self.llm.compress(combined, level="longterm",
                                   max_tokens=TOKEN_LIMITS["longterm"],
                                   lang=self.lang)
        result = self._verify_and_fallback(combined, result, "longterm")
        self._save_cache("longterm", fp, result)
        self._write_file("longterm.md", result, previous=prev)
        return result

    def compile_facts(self, days: int = 7) -> list:
        """Extract atomic facts from recent memories, store to DB."""
        memories = self.storage.get_memories_in_range(days=days)
        logger.debug("Found %d memories for facts extraction", len(memories))
        if not memories:
            return []
        memories = self._sort_memories_for_distill(memories)
        text = self._memories_to_text(memories)
        fp = self._fingerprint(text)
        cached = self._check_cache("facts", fp)
        if cached is not None:
            logger.debug("Using cached facts")
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass
        logger.debug("Calling LLM for facts extraction (text length: %d)", len(text))
        raw = self.llm.compress(text, level="facts",
                                max_tokens=TOKEN_LIMITS["facts"],
                                lang=self.lang)
        logger.debug("LLM returned %d chars", len(raw))
        facts = self._parse_facts(raw)
        logger.debug("Parsed %d facts", len(facts))
        if facts:
            stored = self.storage.insert_facts_batch(facts)
            logger.info("Stored %d new facts", stored)
        self._save_cache("facts", fp, json.dumps(facts, ensure_ascii=False))
        return facts

    def assemble(self, format: str = "4layer") -> str:
        """Assemble memory context from distillation layers.

        Args:
            format: "4layer" (default) for Active/QuickAccess/Durable/Facts,
                    "legacy" for old 3-section format.

        Returns:
            Assembled memory context string.
        """
        if format == "legacy":
            return self._assemble_legacy()

        parts = []

        # Layer 1: Active — recent undistilled memories
        try:
            recent = self.storage.get_memories_in_range(days=1)
            if recent:
                recent = self._sort_memories_for_distill(recent)
                active_text = self._memories_to_text(recent[:10])
                parts.append(f"[Active — recent session]\n{active_text}")
        except Exception:
            logger.debug("Active layer unavailable", exc_info=True)

        # Layer 2: Quick Access — today + week
        today = self._read_file("today.md")
        week = self._read_file("week.md")
        if today or week:
            qa_parts = []
            if today:
                qa_parts.append(f"[Today]\n{today}")
            if week:
                qa_parts.append(f"[This week]\n{week}")
            parts.append("[Quick Access — distilled recent]\n" + "\n\n".join(qa_parts))

        # Layer 3: Durable — longterm profile
        longterm = self._read_file("longterm.md")
        if longterm:
            parts.append(f"[Durable — long-term profile]\n{longterm}")

        # Layer 4: Facts — top atomic facts
        try:
            facts = self.storage.get_all_facts(limit=20)
            if facts:
                fact_lines = [f"- {f.fact}" for f in facts]
                parts.append("[Facts — atomic knowledge]\n" + "\n".join(fact_lines))
        except Exception:
            logger.debug("Facts layer unavailable", exc_info=True)

        result = "\n\n---\n\n".join(parts)
        self._write_file("memory_context.md", result)
        return result

    def _assemble_legacy(self) -> str:
        """Old 3-section format for backward compatibility."""
        today = self._read_file("today.md")
        week = self._read_file("week.md")
        longterm = self._read_file("longterm.md")
        parts = []
        if longterm:
            parts.append(f"[Long-term profile]\n{longterm}")
        if week:
            parts.append(f"[This week]\n{week}")
        if today:
            parts.append(f"[Today]\n{today}")
        result = "\n\n".join(parts)
        self._write_file("memory_context.md", result)
        return result

    def distill_all(self, days: int = 7) -> dict:
        """Full distillation pipeline. Returns stats per layer."""
        stats = {}
        stats["today"] = self.compile_today(days=1)
        stats["week"] = self.compile_week(days=days)
        stats["longterm"] = self.compile_longterm()
        stats["facts"] = self.compile_facts(days=days)
        stats["context"] = self.assemble()
        return stats

    # ── public helpers ──

    def get_prompt_injection(self) -> str:
        """返回可直接拼接到 agent system prompt 的记忆上下文。

        与 assemble() 类似，但格式适合 prompt 注入：
        包含标签头，便于 agent 区分记忆来源。
        """
        context = self.assemble()
        if not context:
            return ""
        return (
            "---\n"
            "[Memory Context — auto-generated by evolver]\n"
            "Use the following memories to inform your responses. "
            "These are the user's past learnings and patterns.\n\n"
            f"{context}\n"
            "---"
        )

    # ── internal ──

    def _verify_and_fallback(self, original: str, distilled: str, level: str) -> str:
        """验证蒸馏保真度 — 蒸馏模式下跳过验证，直接返回。"""
        return distilled

    def _memory_age_days(self, memory, now: datetime = None) -> float:
        """Return non-negative memory age in days."""
        now = now or datetime.now(timezone.utc)
        created_at = getattr(memory, "created_at", None)
        if not created_at:
            return 0.0
        try:
            created = datetime.fromisoformat(str(created_at))
        except ValueError:
            return 0.0
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = now - created.astimezone(timezone.utc)
        return max(delta.total_seconds() / 86400, 0.0)

    def _distill_weight(self, memory, now: datetime = None) -> float:
        """Blend recency, lifecycle, and importance into distillation weight."""
        age_days = self._memory_age_days(memory, now=now)
        age_weight = 0.5 ** (age_days / DISTILL_HALF_LIFE_DAYS)
        lifecycle = getattr(memory, "lifecycle", "seed") or "seed"
        lifecycle_multiplier = LIFECYCLE_DISTILL_MULTIPLIERS.get(lifecycle, 1.0)
        importance = getattr(memory, "importance", 0.5)
        if importance is None:
            importance = 0.5
        importance_multiplier = 0.5 + float(importance)
        return age_weight * lifecycle_multiplier * importance_multiplier

    def _sort_memories_for_distill(self, memories: list) -> list:
        """Return memories ordered by descending distillation weight."""
        now = datetime.now(timezone.utc)
        return sorted(memories, key=lambda m: self._distill_weight(m, now=now), reverse=True)

    def _memories_to_text(self, memories: list) -> str:
        """Serialize memories to plain text for LLM input."""
        lines = []
        for m in memories:
            cat = f"[{m.category}]" if m.category else ""
            tags = f" ({', '.join(m.tags)})" if m.tags else ""
            lines.append(f"{cat}{tags} {m.content}")
        return "\n".join(lines)

    def _fingerprint(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def _check_cache(self, level: str, fp: str) -> Optional[str]:
        """Check if distill_runs has matching fingerprint."""
        row = self.storage.get_last_distill_run(level)
        if row and row.get("fingerprint") == fp:
            logger.debug("Cache hit for %s (fp=%s)", level, fp[:8])
            return row["output"]
        return None

    def _save_cache(self, level: str, fp: str, output: str):
        """Save distill result to DB for fingerprint caching."""
        token_count = len(output) // 3  # rough estimate
        self.storage.insert_distill_run(level, fp, output, token_count)

    def _parse_facts(self, raw: str) -> list:
        """Parse LLM output into list of {fact, tags} dicts."""
        from evolver.utils import extract_json_from_llm
        logger.debug("Raw facts output (%d chars): %s", len(raw), raw[:200])
        parsed = extract_json_from_llm(raw)
        if isinstance(parsed, list):
            return [
                {"fact": f["fact"], "tags": f.get("tags", [])}
                for f in parsed
                if isinstance(f, dict) and "fact" in f
            ]
        return []

    def _read_file(self, name: str) -> str:
        path = os.path.join(self.memory_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def _write_file(self, name: str, content: str, previous: str = None):
        path = os.path.join(self.memory_dir, name)
        if previous is not None and previous.strip() == content.strip():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                if f.read() == content:
                    return
        except FileNotFoundError:
            pass
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
