
from __future__ import annotations

import os
import logging
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evolver.memory import MemoryEngine

logger = logging.getLogger(__name__)

DEFAULT_IDENTITY = "## L0 -- IDENTITY\nNo identity configured. Create ~/.evolver/identity.txt"


def truncate_content(text: str, max_chars: int = 200) -> str:
    """Truncate text at sentence or newline boundary, adding '...' if truncated.

    Args:
        text: Input text.
        max_chars: Maximum characters before truncation.

    Returns:
        Original text if short enough, or truncated version ending with '...'.
    """
    if not text or len(text) <= max_chars:
        return text

    # Try to find a sentence boundary (. followed by space or end)
    truncated = text[:max_chars]
    for sep in (". ", ".\n", "\n", "! ", "? "):
        last = truncated.rfind(sep)
        if last > max_chars // 2:  # at least half the budget
            return truncated[: last + len(sep)].rstrip() + "..."

    # No good boundary -- hard cut
    return truncated.rstrip() + "..."


class MemoryStack:
    """4-layer progressive memory stack.

    L0 Identity   (~100 tokens)  -- always loaded
    L1 Essential  (~500-800)      -- top-N by importance, truncated
    L2 On-Demand  (~200-500)      -- category/tags filtered
    L3 Deep       (unlimited)     -- full recall()
    """

    MAX_DRAWERS = 15
    MAX_CHARS = 3200
    MAX_SCAN = 2000

    def __init__(self, engine: MemoryEngine, identity_path: str = None):
        self._engine = engine
        self._identity_path = identity_path or os.path.expanduser("~/.evolver/identity.txt")

    def _render_identity(self) -> str:
        """L0: Read identity file or return default."""
        if os.path.exists(self._identity_path):
            with open(self._identity_path, "r") as f:
                return f.read().strip()
        return DEFAULT_IDENTITY

    def wake_up(self, category: str = None) -> str:
        """L0 + L1 wake-up text. ~600-900 tokens.

        Args:
            category: Optional category filter for L1.

        Returns:
            Formatted string with identity and top memories.
        """
        parts = []
        # L0: Identity
        parts.append(self._render_identity())
        parts.append("")
        # L1: Essential Story
        parts.append(self._generate_l1(category))
        return "\n".join(parts)

    def _generate_l1(self, category: str = None) -> str:
        """Generate L1 from top memories by importance."""
        storage = self._engine._storage
        memories = storage.get_all_memories_with_embeddings(
            max_scan=self.MAX_SCAN, category=category
        )
        if not memories:
            return "## L1 -- No memories yet."

        # Score by importance, take top N
        scored = [(m.importance, m) for m in memories]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: self.MAX_DRAWERS]

        # Group by category
        by_category = defaultdict(list)
        for imp, mem in top:
            by_category[mem.category].append((imp, mem))

        lines = ["## L1 -- ESSENTIAL STORY"]
        total_len = 0

        for cat, entries in sorted(by_category.items()):
            cat_line = f"\n[{cat}]"
            lines.append(cat_line)
            total_len += len(cat_line)

            for _imp, mem in entries:
                snippet = truncate_content(mem.content.strip().replace("\n", " "), max_chars=200)
                entry_line = f"  - {snippet}"
                if total_len + len(entry_line) > self.MAX_CHARS:
                    lines.append("  ... (more in L3 search)")
                    return "\n".join(lines)
                lines.append(entry_line)
                total_len += len(entry_line)

        return "\n".join(lines)

    def recall_light(self, query: str, category: str = None, top_k: int = 10) -> str:
        """L2: On-demand retrieval with truncated snippets."""
        results = self._engine.recall(query, top_k=top_k)
        if category:
            results = [r for r in results if r.category == category]
        if not results:
            return "No memories found."
        lines = [f"## L2 -- ON-DEMAND ({len(results)} results)"]
        for r in results:
            snippet = truncate_content(r.content.strip().replace("\n", " "), max_chars=300)
            entry = f"  [{r.category}] {snippet} (score={r.score:.2f})"
            lines.append(entry)
        return "\n".join(lines)

    def recall_deep(self, query: str, top_k: int = 5):
        """L3: Full recall with all fusion signals."""
        return self._engine.recall(query, top_k=top_k)
