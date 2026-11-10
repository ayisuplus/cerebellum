"""LLM-based memory extraction — atomic facts from text.

Inspired by mem0's ADDITIVE_EXTRACTION_PROMPT but adapted for evolver's
learn() workflow. Extracts self-contained factual statements, deduplicates
against existing memories via hash, and updates stale facts.
"""

import hashlib
import logging
import re
from evolver.utils import extract_json_from_llm, nonempty_lines

logger = logging.getLogger(__name__)

EXTRACTION_PROMPTS = {
    "zh": (
        "你是一个精确的记忆提取器。从以下文本中提取所有值得记住的独立事实。\n\n"
        "规则：\n"
        "- 每条事实必须自包含（不依赖上下文就能理解）\n"
        "- 一条事实只记一件事（原子性）\n"
        "- 去掉无关的寒暄、过渡句、格式标记\n"
        "- 如果原文包含相对时间（如\"上周\"、\"昨天\"），转换为绝对日期\n"
        "- 如果原文包含更新/修正信息，标记为对已有事实的更新\n\n"
        "输出格式（纯JSON）：\n"
        '{{"facts": [{{"text": "事实内容", "tags": ["标签1", "标签2"]}}]}}\n\n'
        "如果没有值得提取的内容，返回 {{\"facts\": []}}"
    ),
    "en": (
        "You are a precise memory extractor. Extract all memorable independent facts.\n\n"
        "Rules:\n"
        "- Each fact must be self-contained (understandable without context)\n"
        "- One fact per entry (atomic)\n"
        "- Remove greetings, transitions, formatting artifacts\n"
        "- Convert relative time references to absolute dates\n"
        "- Mark updates/corrections to existing facts\n\n"
        "Output format (pure JSON):\n"
        '{{"facts": [{{"text": "fact content", "tags": ["tag1", "tag2"]}}]}}\n\n'
        "Return {{\"facts\": []}} if nothing worth extracting."
    ),
}

DEDUP_PROMPTS = {
    "zh": (
        "你是一个记忆去重器。判断以下新事实是否与已有记忆重复或冲突。\n\n"
        "已有记忆：\n{existing}\n\n"
        "新事实：\n{new_fact}\n\n"
        "输出JSON：\n"
        "- 如果是全新事实：{{\"action\": \"add\"}}\n"
        "- 如果与已有事实重复：{{\"action\": \"skip\"}}\n"
        "- 如果是已有事实的更新/修正：{{\"action\": \"update\", \"target_id\": {{id}}, \"reason\": \"更新原因\"}}"
    ),
    "en": (
        "You are a memory deduplicator. Determine if the new fact duplicates or conflicts.\n\n"
        "Existing memories:\n{existing}\n\n"
        "New fact:\n{new_fact}\n\n"
        "Output JSON:\n"
        "- If brand new: {{\"action\": \"add\"}}\n"
        "- If duplicate: {{\"action\": \"skip\"}}\n"
        "- If update/correction: {{\"action\": \"update\", \"target_id\": {{id}}, \"reason\": \"why\"}}"
    ),
}


class MemoryExtractor:
    """Extract atomic facts from text using LLM, with hash-based dedup."""

    def __init__(self, llm_client, lang: str = "zh"):
        self._llm = llm_client
        self._lang = lang

    def extract(self, text: str) -> list[dict]:
        """Extract atomic facts from text.

        Returns list of {"text": str, "tags": list[str]}.
        Falls back to line-based extraction if LLM unavailable.
        """
        if not text.strip():
            return []

        if not self._llm or not self._llm.available:
            return self._heuristic_extract(text)

        prompt = EXTRACTION_PROMPTS.get(self._lang, EXTRACTION_PROMPTS["en"])
        try:
            result = self._llm.call_llm(text, prompt, max_tokens=1000)
            result = self._llm.extract_final_answer(result)
            return self._parse_facts(result)
        except Exception as e:
            logger.warning("LLM extraction failed, falling back to heuristic: %s", e)
            return self._heuristic_extract(text)

    def should_update(self, new_fact: str, existing_facts: list[dict],
                      existing_hashes: set[str]) -> str | None:
        """Check if a new fact should be added, skipped, or used to update.

        Returns:
            "add" — new fact, not duplicate
            "skip" — duplicate
            "update:<id>" — update existing memory with this ID
            None — error
        """
        new_hash = self._fact_hash(new_fact)
        if new_hash in existing_hashes:
            return "skip"

        if not self._llm or not self._llm.available or not existing_facts:
            return "add"

        # Use LLM for semantic dedup against top similar existing facts
        existing_text = "\n".join(
            f"[{f['id']}] {f['text']}" for f in existing_facts[:10]
        )
        prompt = DEDUP_PROMPTS.get(self._lang, DEDUP_PROMPTS["en"]).format(
            existing=existing_text, new_fact=new_fact
        )
        try:
            result = self._llm.call_llm("", prompt, max_tokens=200)
            result = self._llm.extract_final_answer(result)
            parsed = extract_json_from_llm(result) or {}
            action = parsed.get("action", "add")
            if action == "skip":
                return "skip"
            elif action == "update" and "target_id" in parsed:
                return f"update:{parsed['target_id']}"
            return "add"
        except Exception:
            return "add"

    @staticmethod
    def _fact_hash(text: str) -> str:
        """MD5 hash of normalized text for fast dedup."""
        normalized = re.sub(r'\s+', ' ', text.strip().lower())
        return hashlib.md5(normalized.encode()).hexdigest()

    @staticmethod
    def _parse_json(text: str):
        """Backward-compatible JSON extraction helper.

        Keep the parsing behavior centralized in ``extract_json_from_llm`` so
        fenced JSON, arrays, and invalid model output are handled consistently.
        """
        return extract_json_from_llm(text) or {}

    def _heuristic_extract(self, text: str) -> list[dict]:
        """Fallback: split by lines, each non-empty line is a fact."""
        lines = nonempty_lines(text)
        facts = []
        for line in lines:
            line = line.strip()
            if len(line) > 10:  # skip very short lines
                facts.append({"text": line, "tags": []})
        return facts

    def _parse_facts(self, text: str) -> list[dict]:
        """Parse JSON facts from LLM output."""
        parsed = extract_json_from_llm(text) or {}
        if isinstance(parsed, dict) and "facts" in parsed:
            return parsed["facts"]
        if isinstance(parsed, list):
            return parsed
        return []
