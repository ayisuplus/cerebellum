from collections import defaultdict
from evolver.utils import tokenize


# Stoplist for entity extraction (capitalized words that aren't entities)
_STOPLIST = frozenset({
    "The", "This", "That", "These", "Those", "When", "Where", "What",
    "Why", "Who", "Which", "How", "After", "Before", "Then", "Now",
    "And", "But", "Or", "Yet", "So", "If", "Else", "Yes", "No",
})


class ClosetIndex:
    """Topic->entity->memory_id fast lookup index.

    Provides keyword-based memory lookup without vector search.
    Format: topic|entities|->memory_ids (in-memory implementation).
    """

    def __init__(self):
        # keyword -> set of memory_ids
        self._index: dict[str, set[int]] = defaultdict(set)
        # memory_id -> set of keywords (for removal)
        self._reverse: dict[int, set[str]] = defaultdict(set)

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content for indexing."""
        return tokenize(content, min_len=3, stopwords=_STOPLIST,
                       english_pattern=r'[a-zA-Z][a-zA-Z0-9_]{2,}')

    def add(self, memory_id: int, content: str, category: str = ""):
        """Add a memory to the closet index.

        Args:
            memory_id: Memory ID.
            content: Memory content text.
            category: Memory category (used as keyword).
        """
        keywords = self._extract_keywords(content)
        if category:
            keywords.append(category.lower())

        for kw in keywords:
            self._index[kw].add(memory_id)
            self._reverse[memory_id].add(kw)

    def remove(self, memory_id: int):
        """Remove a memory from the closet index."""
        keywords = self._reverse.pop(memory_id, set())
        for kw in keywords:
            self._index[kw].discard(memory_id)
            if not self._index[kw]:
                del self._index[kw]

    def query(self, text: str) -> list[int]:
        """Query for memory IDs matching any keyword in text.

        Args:
            text: Query text.

        Returns:
            List of memory IDs, sorted by relevance (most keyword matches first).
        """
        if not text:
            return []

        query_keywords = self._extract_keywords(text)
        if not query_keywords:
            return []

        # Count keyword matches per memory_id
        scores: dict[int, int] = defaultdict(int)
        for kw in query_keywords:
            for mid in self._index.get(kw, []):
                scores[mid] += 1

        # Sort by score descending
        return [mid for mid, _ in sorted(scores.items(), key=lambda x: -x[1])]
