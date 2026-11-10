# Progressive Memory Stack for Evolver

**Date:** 2026-05-22
**Status:** Approved
**Scope:** 6 improvements inspired by mempalace architecture

---

## Problem

Evolver loads all memories into context with no layered loading, no dedup, no compression. As memory count grows, token cost per query becomes unsustainable.

## Solution

Implement a 4-layer progressive memory stack plus supporting infrastructure, in two phases.

---

## Phase 1: Core Impact

### 1. Progressive Context Loading

New file: `evolver/stack.py`

```
L0 Identity   (~100 tokens)   — agent config/personality, always loaded
L1 Essential  (~500-800)       — Top-N by importance, truncated to 200 chars/item
L2 On-Demand  (~200-500)       — category/tags filtered retrieval
L3 Deep       (unlimited)      — full recall() with RRF + reranker
```

**Wake-up cost: ~600-900 tokens (L0+L1). 95%+ context free.**

API:
```python
class MemoryStack:
    def __init__(self, storage, embedding, identity_path: str = None): ...

    def wake_up(self, category: str = None) -> str:
        """L0 + L1. ~600-900 tokens. Inject into system prompt."""

    def recall_light(self, query: str, category: str = None, top_k: int = 10) -> str:
        """L2 on-demand retrieval, truncated snippets."""

    def recall_deep(self, query: str, top_k: int = 5) -> list[RecallResult]:
        """L3 full recall(), returns original RecallResult."""
```

Implementation:
- `wake_up()` calls `storage.get_all_memories_with_embeddings()`, sorts by importance, takes Top-15
- Each memory truncated to 200 chars, grouped by category
- L0 reads from `~/.evolver/identity.txt` or config (new file, optional)
- Reuses existing `MemoryEngine` storage/embedding instances
- Constants: `MAX_DRAWERS=15`, `MAX_CHARS=3200`, `MAX_SCAN=2000`

### 2. Near-duplicate Detection

New file: `evolver/dedup.py`

Algorithm (from mempalace `dedup.py`):
1. Get all memories with embeddings
2. Group by category
3. Greedy: sort by content length descending, keep longest
4. For each candidate, query kept set for nearest neighbor
5. Cosine distance < threshold (default 0.15) → mark as duplicate, delete

API:
```python
class Deduplicator:
    def __init__(self, storage, embedding, threshold: float = 0.15): ...

    def dedup(self, category: str = None, dry_run: bool = True) -> tuple[int, int]:
        """Returns (kept, deleted). dry_run=True stats only."""

    def is_duplicate(self, content: str, embedding_bytes: bytes,
                     category: str = None) -> bool:
        """Single check for real-time dedup during store()."""
```

Integration:
- `MemoryEngine.store()`: call `is_duplicate()` before insert
- CLI `evolver dedup`: batch cleanup of historical data
- Coexists with existing `content_hash` (hash fast path + cosine fallback)

### 3. Content Compression

Snippet truncation + importance gating.

Strategy:
- `truncate(content, max_chars=200)` — truncate at sentence/newline boundary, add `...`
- L1 Essential: each ≤200 chars, total ≤3200 chars
- L2 On-Demand: each ≤300 chars
- L3 Deep: no truncation (full content)

New field on RecallResult:
```python
@dataclass
class RecallResult:
    content: str          # full content
    snippet: str = ""     # truncated version, always populated by MemoryStack
    ...
```

Implementation: `snippet` generated at MemoryStack layer. When MemoryStack creates RecallResult, `snippet` is always set (truncated copy of `content`). Direct `recall()` callers get `snippet=""` by default.

---

## Phase 2: Infrastructure

### 4. Input Normalization

New file: `evolver/normalize.py`

From mempalace `normalize.py`:
```python
def strip_noise(text: str) -> str:
    """Remove <system-reminder>, <command-message> tags,
    hook output lines, collapsed-lines markers."""

def normalize_input(text: str, source: str = "auto") -> str:
    """Entry point. source: auto, chat_export, raw"""
```

Integration: `MemoryEngine.store()` calls `normalize_input()` before `_extract_tags()` and embedding.

### 5. Closet-style Secondary Index

New file: `evolver/closet.py`

Format: `topic|entities|→memory_ids`
Each closet ≤1500 chars.

Entity extraction: reuse `_extract_tags()` from MemoryEngine. Topics from content keywords. Entities from capitalized words filtered against stoplist.

Usage: fast keyword lookup, skip vector search. When BM25 hits a closet, directly resolve memory_ids.

Integration:
- `MemoryEngine.store()` auto-generates closet entries after insert
- `recall()` adds closet fast path before full vector search

### 6. Backend Abstraction

From mempalace `backends/base.py`.

New ABC alongside existing `BaseStorage`:
```python
class StorageBackend(ABC):
    name: ClassVar[str]

    @abstractmethod
    def get_collection(self, ...) -> BaseCollection: ...

    def health(self) -> HealthStatus: ...
    def close(self) -> None: ...
```

Incremental: does not break existing `BaseStorage`. New ABC coexists.

---

## Files Changed

### New files
- `evolver/stack.py` — MemoryStack (L0/L1/L2/L3)
- `evolver/dedup.py` — Deduplicator
- `evolver/normalize.py` — strip_noise, normalize_input
- `evolver/closet.py` — closet index

### Modified files
- `evolver/memory.py` — integrate dedup in store(), normalize in store(), closet generation
- `evolver/models.py` — add `snippet` field to RecallResult (optional)
- `evolver/cli.py` — add `evolver dedup` command

### Unchanged
- `evolver/storage.py` — MySQL backend, no changes
- `evolver/storage_base.py` — BaseStorage ABC, no breaking changes
- `evolver/storage_sqlite.py` — SQLite backend, no changes
- `evolver/ann_index.py` — ANN index, no changes
- `evolver/embedding.py` — embedding client, no changes

---

## Testing

- Unit tests for `MemoryStack.wake_up()`, `recall_light()`, `recall_deep()`
- Unit tests for `Deduplicator.dedup()`, `is_duplicate()`
- Unit tests for `strip_noise()`, `normalize_input()`
- Integration test: store → dedup → stack.wake_up() roundtrip
- Existing 171 tests must pass unchanged

---

## Non-goals

- No ChromaDB migration (keep SQLite/MySQL)
- No LLM-based summarization (pure algorithmic)
- No changes to embedding model or ANN index
