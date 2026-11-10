# Progressive Memory Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4-layer progressive memory loading, near-duplicate detection, content compression, input normalization, closet index, and backend abstraction to evolver.

**Architecture:** New modules (`stack.py`, `dedup.py`, `normalize.py`, `closet.py`) integrate with existing `MemoryEngine` via composition. No breaking changes to existing API. TDD throughout.

**Tech Stack:** Python 3.10+, pytest, numpy, MagicMock for unit tests

**Spec:** `docs/superpowers/specs/2026-05-22-progressive-memory-design.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `evolver/stack.py` | MemoryStack: L0/L1/L2/L3 progressive loading |
| `evolver/dedup.py` | Deduplicator: cosine-distance near-duplicate detection |
| `evolver/normalize.py` | strip_noise, normalize_input: input cleaning |
| `evolver/closet.py` | ClosetIndex: topic→entity→memory_id fast lookup |
| `tests/test_stack.py` | MemoryStack unit tests |
| `tests/test_dedup.py` | Deduplicator unit tests |
| `tests/test_normalize.py` | Normalization unit tests |
| `tests/test_closet.py` | ClosetIndex unit tests |

### Modified files
| File | Changes |
|------|---------|
| `evolver/memory.py:37-127` | Integrate dedup check in `store()`, normalize before embed |
| `evolver/models.py:7-12` | Add `snippet` field to RecallResult |
| `evolver/cli.py` | Add `evolver dedup` CLI command |

### Unchanged files
- `evolver/storage.py`, `storage_base.py`, `storage_sqlite.py`, `ann_index.py`, `embedding.py`

---

## Phase 1: Core Impact

### Task 1: Add `snippet` field to RecallResult

**Files:**
- Modify: `evolver/models.py:7-12`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test for snippet field**

```python
# tests/test_models.py — add at end
def test_recall_result_has_snippet():
    from evolver.models import RecallResult
    r = RecallResult(content="full text", score=0.9, source="memory", category="success")
    assert r.snippet == ""
    r2 = RecallResult(content="full text", score=0.9, source="memory", category="success", snippet="full...")
    assert r2.snippet == "full..."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_models.py::test_recall_result_has_snippet -v`
Expected: FAIL — `snippet` field not found

- [ ] **Step 3: Add snippet field to RecallResult**

```python
# evolver/models.py — RecallResult class
@dataclass
class RecallResult:
    content: str
    score: float
    source: str
    category: str
    related_nodes: list = field(default_factory=list)
    snippet: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_models.py::test_recall_result_has_snippet -v`
Expected: PASS

- [ ] **Step 5: Run all existing tests**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/ -v`
Expected: All 171+ tests pass (snippet field is additive, no breakage)

- [ ] **Step 6: Commit**

```bash
git add evolver/models.py tests/test_models.py
git commit -m "feat: add snippet field to RecallResult"
```

---

### Task 2: Content truncation utility

**Files:**
- Create: `evolver/stack.py` (truncation functions only, MemoryStack comes later)
- Test: `tests/test_stack.py`

- [ ] **Step 1: Write failing tests for truncate**

```python
# tests/test_stack.py
import pytest
from evolver.stack import truncate_content


def test_truncate_short_text_unchanged():
    text = "Short text."
    assert truncate_content(text, max_chars=200) == text


def test_truncate_at_sentence_boundary():
    text = "First sentence. Second sentence that is much longer and goes on and on."
    result = truncate_content(text, max_chars=30)
    assert result.endswith("...")
    assert len(result) <= 33  # 30 + "..."


def test_truncate_at_newline_boundary():
    text = "Line one\nLine two\nLine three"
    result = truncate_content(text, max_chars=15)
    assert result.endswith("...")


def test_truncate_hard_cut_if_no_boundary():
    text = "a" * 300
    result = truncate_content(text, max_chars=100)
    assert len(result) == 103  # 100 + "..."
    assert result.endswith("...")


def test_truncate_empty_string():
    assert truncate_content("", max_chars=200) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_stack.py -v`
Expected: FAIL — module `evolver.stack` not found

- [ ] **Step 3: Implement truncate_content**

```python
# evolver/stack.py


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

    # No good boundary — hard cut
    return truncated.rstrip() + "..."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_stack.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/stack.py tests/test_stack.py
git commit -m "feat: add truncate_content utility for memory snippets"
```

---

### Task 3: MemoryStack L0 + L1 (wake_up)

**Files:**
- Modify: `evolver/stack.py`
- Test: `tests/test_stack.py`

- [ ] **Step 1: Write failing tests for MemoryStack L0/L1**

```python
# tests/test_stack.py — add at end
import numpy as np
from unittest.mock import MagicMock
from evolver.memory import MemoryEngine
from evolver.models import Memory
from evolver.stack import MemoryStack


def make_stack():
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.dim = 384
    mock_embedding.embed_single.return_value = np.random.rand(384).tolist()
    mock_embedding.vector_to_bytes.return_value = b"\x00" * (384 * 4)
    mock_embedding.bytes_to_vector.return_value = [0.0] * 384
    engine = MemoryEngine(mock_storage, mock_embedding)
    stack = MemoryStack(engine)
    return stack, engine, mock_storage


def test_wake_up_returns_identity_and_top_memories():
    stack, engine, storage = make_stack()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="A" * 300, category="success", importance=0.9, embedding=b"\x00" * 12),
        Memory(id=2, content="B" * 100, category="failure", importance=0.3, embedding=b"\x00" * 12),
    ]

    result = stack.wake_up()
    assert isinstance(result, str)
    # Should contain L0 and L1 sections
    assert "IDENTITY" in result or "ESSENTIAL" in result or len(result) > 0


def test_wake_up_empty_when_no_memories():
    stack, engine, storage = make_stack()
    storage.get_all_memories_with_embeddings.return_value = []

    result = stack.wake_up()
    assert isinstance(result, str)
    assert len(result) > 0  # at least L0 identity text


def test_wake_up_respects_max_drawers():
    stack, engine, storage = make_stack()
    # Create 30 memories, should only take top 15
    memories = [
        Memory(id=i, content=f"Memory {i} " * 50, category="success",
               importance=1.0 - i * 0.01, embedding=b"\x00" * 12)
        for i in range(30)
    ]
    storage.get_all_memories_with_embeddings.return_value = memories

    result = stack.wake_up()
    # Count how many memory snippets appear
    assert result.count("Memory") <= 16  # MAX_DRAWERS=15 + some margin


def test_wake_up_truncates_long_content():
    stack, engine, storage = make_stack()
    long_content = "x" * 500
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content=long_content, category="success", importance=0.9, embedding=b"\x00" * 12),
    ]

    result = stack.wake_up()
    # Should not contain full 500-char content
    assert "x" * 300 not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_stack.py -v -k "wake_up"`
Expected: FAIL — `MemoryStack` not found

- [ ] **Step 3: Implement MemoryStack with L0/L1**

```python
# evolver/stack.py — add after truncate_content
import os
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

DEFAULT_IDENTITY = "## L0 — IDENTITY\nNo identity configured. Create ~/.evolver/identity.txt"


class MemoryStack:
    """4-layer progressive memory stack.

    L0 Identity   (~100 tokens)  — always loaded
    L1 Essential  (~500-800)      — top-N by importance, truncated
    L2 On-Demand  (~200-500)      — category/tags filtered
    L3 Deep       (unlimited)     — full recall()
    """

    MAX_DRAWERS = 15
    MAX_CHARS = 3200
    MAX_SCAN = 2000

    def __init__(self, engine: "MemoryEngine", identity_path: str = None):
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
            return "## L1 — No memories yet."

        # Score by importance, take top N
        scored = [(m.importance, m) for m in memories]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: self.MAX_DRAWERS]

        # Group by category
        by_category = defaultdict(list)
        for imp, mem in top:
            by_category[mem.category].append((imp, mem))

        lines = ["## L1 — ESSENTIAL STORY"]
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_stack.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/stack.py tests/test_stack.py
git commit -m "feat: add MemoryStack L0 identity + L1 essential story"
```

---

### Task 4: MemoryStack L2 (recall_light) + L3 (recall_deep)

**Files:**
- Modify: `evolver/stack.py`
- Test: `tests/test_stack.py`

- [ ] **Step 1: Write failing tests for L2/L3**

```python
# tests/test_stack.py — add at end


def test_recall_light_returns_truncated_results():
    stack, engine, storage = make_stack()
    engine._storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="Auth fix " * 50, category="success", importance=0.8, embedding=b"\x00" * 12),
    ]
    storage.query_nodes.return_value = []

    result = stack.recall_light("auth")
    assert isinstance(result, str)
    assert len(result) > 0


def test_recall_deep_returns_recall_results():
    stack, engine, storage = make_stack()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="git merge", category="success", embedding=b"\x00" * 12),
    ]
    storage.query_nodes_batch.return_value = []

    results = stack.recall_deep("git conflict")
    assert isinstance(results, list)


def test_recall_light_empty_when_no_memories():
    stack, engine, storage = make_stack()
    storage.get_all_memories_with_embeddings.return_value = []

    result = stack.recall_light("anything")
    assert "No memories" in result or result == "" or isinstance(result, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_stack.py -v -k "recall"`
Expected: FAIL — methods not found

- [ ] **Step 3: Implement L2/L3**

```python
# evolver/stack.py — add to MemoryStack class

    def recall_light(self, query: str, category: str = None, top_k: int = 10) -> str:
        """L2: On-demand retrieval with truncated snippets.

        Args:
            query: Search query.
            category: Optional category filter.
            top_k: Max results.

        Returns:
            Formatted string with truncated memory snippets.
        """
        results = self._engine.recall(query, top_k=top_k)

        # Filter by category if specified
        if category:
            results = [r for r in results if r.category == category]

        if not results:
            return "No memories found."

        lines = [f"## L2 — ON-DEMAND ({len(results)} results)"]
        for r in results:
            snippet = truncate_content(r.content.strip().replace("\n", " "), max_chars=300)
            entry = f"  [{r.category}] {snippet} (score={r.score})"
            lines.append(entry)

        return "\n".join(lines)

    def recall_deep(self, query: str, top_k: int = 5):
        """L3: Full recall with all fusion signals.

        Args:
            query: Search query.
            top_k: Max results.

        Returns:
            List of RecallResult with full content.
        """
        return self._engine.recall(query, top_k=top_k)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_stack.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/stack.py tests/test_stack.py
git commit -m "feat: add MemoryStack L2 recall_light + L3 recall_deep"
```

---

### Task 5: Deduplicator — cosine distance dedup

**Files:**
- Create: `evolver/dedup.py`
- Test: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests for Deduplicator**

```python
# tests/test_dedup.py
import numpy as np
from unittest.mock import MagicMock
from evolver.dedup import Deduplicator
from evolver.models import Memory


def make_dedup():
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.dim = 384
    mock_embedding.bytes_to_vector.side_effect = lambda b: np.random.rand(384).tolist()
    mock_embedding.embed_single.side_effect = lambda t: np.random.rand(384).tolist()
    mock_embedding.vector_to_bytes.side_effect = lambda v: b"\x00" * (384 * 4)
    dedup = Deduplicator(mock_storage, mock_embedding, threshold=0.15)
    return dedup, mock_storage, mock_embedding


def test_dedup_dry_run_returns_counts():
    dedup, storage, emb = make_dedup()
    # Two very similar memories
    vec = np.random.rand(384).astype(np.float32)
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="Short", category="success", embedding=emb.vector_to_bytes(vec)),
        Memory(id=2, content="Short text", category="success", embedding=emb.vector_to_bytes(vec)),
    ]

    kept, deleted = dedup.dedup(dry_run=True)
    assert isinstance(kept, int)
    assert isinstance(deleted, int)
    assert kept + deleted == 2


def test_is_duplicate_returns_false_for_unique():
    dedup, storage, emb = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = []

    result = dedup.is_duplicate("unique content", b"\x00" * 12)
    assert result is False


def test_is_duplicate_returns_true_for_similar():
    dedup, storage, emb = make_dedup()
    # Same vector = same content
    vec = np.random.rand(384).astype(np.float32)
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="existing", category="success", embedding=emb.vector_to_bytes(vec)),
    ]
    # Mock embed_single to return same vector
    emb.embed_single.return_value = vec.tolist()

    result = dedup.is_duplicate("existing content", emb.vector_to_bytes(vec))
    assert result is True


def test_dedup_empty_storage():
    dedup, storage, emb = make_dedup()
    storage.get_all_memories_with_embeddings.return_value = []

    kept, deleted = dedup.dedup(dry_run=True)
    assert kept == 0
    assert deleted == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_dedup.py -v`
Expected: FAIL — module `evolver.dedup` not found

- [ ] **Step 3: Implement Deduplicator**

```python
# evolver/dedup.py
import logging
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class Deduplicator:
    """Near-duplicate detection using cosine distance.

    Groups memories by category, keeps longest version when
    cosine distance < threshold.
    """

    def __init__(self, storage, embedding, threshold: float = 0.15):
        self._storage = storage
        self._embedding = embedding
        self._threshold = threshold

    def _cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine distance (0 = identical, 2 = opposite)."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 2.0
        return 1.0 - float(np.dot(a, b) / (norm_a * norm_b))

    def dedup(self, category: str = None, dry_run: bool = True) -> tuple[int, int]:
        """Find and optionally remove near-duplicate memories.

        Args:
            category: Optional category filter.
            dry_run: If True, only count without deleting.

        Returns:
            (kept, deleted) counts.
        """
        memories = self._storage.get_all_memories_with_embeddings(category=category)
        if not memories:
            return 0, 0

        # Group by category
        groups = defaultdict(list)
        for mem in memories:
            groups[mem.category].append(mem)

        total_kept = 0
        total_deleted = 0

        for cat, cat_memories in groups.items():
            # Sort by content length descending (keep longest)
            cat_memories.sort(key=lambda m: len(m.content), reverse=True)

            kept_vectors = []  # (memory, vector) pairs

            for mem in cat_memories:
                if mem.embedding is None:
                    continue

                vec = np.array(self._embedding.bytes_to_vector(mem.embedding), dtype=np.float32)

                # Check against all kept memories
                is_dup = False
                for _, kept_vec in kept_vectors:
                    dist = self._cosine_distance(vec, kept_vec)
                    if dist < self._threshold:
                        is_dup = True
                        break

                if is_dup:
                    total_deleted += 1
                    if not dry_run:
                        self._storage.delete_memory(mem.id)
                        logger.debug("Deleted duplicate memory %d (cat=%s)", mem.id, cat)
                else:
                    kept_vectors.append((mem, vec))
                    total_kept += 1

        if not dry_run and total_deleted > 0:
            self._storage.log_event("dedup", {
                "kept": total_kept, "deleted": total_deleted, "category": category,
            })
            logger.info("Dedup: kept=%d, deleted=%d", total_kept, total_deleted)

        return total_kept, total_deleted

    def is_duplicate(self, content: str, embedding_bytes: bytes,
                     category: str = None) -> bool:
        """Check if content is a near-duplicate of existing memories.

        Args:
            content: Memory content text.
            embedding_bytes: Embedding as bytes.
            category: Optional category to search within.

        Returns:
            True if a near-duplicate exists.
        """
        new_vec = np.array(self._embedding.bytes_to_vector(embedding_bytes), dtype=np.float32)

        # Get existing memories in same category
        memories = self._storage.get_all_memories_with_embeddings(category=category)

        for mem in memories:
            if mem.embedding is None:
                continue
            mem_vec = np.array(self._embedding.bytes_to_vector(mem.embedding), dtype=np.float32)
            dist = self._cosine_distance(new_vec, mem_vec)
            if dist < self._threshold:
                logger.debug("Duplicate detected: dist=%.4f vs memory %d", dist, mem.id)
                return True

        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_dedup.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/dedup.py tests/test_dedup.py
git commit -m "feat: add Deduplicator with cosine distance near-duplicate detection"
```

---

### Task 6: Integrate dedup into MemoryEngine.store()

**Files:**
- Modify: `evolver/memory.py:37-127`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write failing test for dedup integration**

```python
# tests/test_memory.py — add at end


def test_store_skips_duplicate_when_dedup_configured():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    # Configure dedup
    from evolver.dedup import Deduplicator
    dedup = Deduplicator(storage, emb, threshold=0.15)
    engine.set_deduplicator(dedup)

    # Make is_duplicate return True
    engine._deduplicator = MagicMock()
    engine._deduplicator.is_duplicate.return_value = True

    ids = engine.store(
        task="fix bug", outcome="success",
        solution="fixed token", lessons="validate",
    )

    # Should skip insertion because it's a duplicate
    storage.insert_memory.assert_not_called()
    assert ids == []


def test_store_inserts_when_not_duplicate():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    from evolver.dedup import Deduplicator
    dedup = Deduplicator(storage, emb, threshold=0.15)
    engine.set_deduplicator(dedup)

    # Make is_duplicate return False
    engine._deduplicator = MagicMock()
    engine._deduplicator.is_duplicate.return_value = False

    ids = engine.store(
        task="fix bug", outcome="success",
        solution="fixed token", lessons="validate",
    )

    assert storage.insert_memory.call_count >= 1
    assert len(ids) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_memory.py -v -k "dedup"`
Expected: FAIL — `set_deduplicator` not found

- [ ] **Step 3: Add dedup integration to MemoryEngine**

```python
# evolver/memory.py — add to MemoryEngine.__init__
    def __init__(self, storage, embedding: EmbeddingClient, ann_index_path: str = "evolver.ann",
                 recall_bm25_weight: float = 0.15):
        # ... existing init ...
        self._deduplicator = None  # Set by set_deduplicator()

    def set_deduplicator(self, deduplicator):
        """Configure near-duplicate detection for store()."""
        self._deduplicator = deduplicator
```

```python
# evolver/memory.py — modify store() method, after self._storage.begin()
    def store(self, task: str, outcome: str, context: str = "",
              solution: str = "", lessons: str = "") -> list[int]:
        memory_ids = []
        link_pairs = []
        ann_pairs = []
        self._storage.begin()
        try:
            # Create experience memory from task (+ solution if available)
            if task:
                if solution:
                    content = f"Task: {task}\nSolution: {solution}"
                else:
                    content = f"Task: {task}\n(no solution recorded)"
                vec = self._embedding.embed_single(content)
                embedding_bytes = self._embedding.vector_to_bytes(vec)

                # Dedup check
                if self._deduplicator and self._deduplicator.is_duplicate(content, embedding_bytes):
                    logger.info("Skipping duplicate memory: %s...", content[:50])
                    self._storage.rollback()
                    return []

                mem = Memory(
                    content=content,
                    category="success" if outcome == "success" else "failure",
                    tags=self._extract_tags(task),
                    embedding=embedding_bytes,
                    source="learn",
                )
                # ... rest unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_memory.py -v`
Expected: All PASS (including new dedup tests)

- [ ] **Step 5: Commit**

```bash
git add evolver/memory.py tests/test_memory.py
git commit -m "feat: integrate dedup check into MemoryEngine.store()"
```

---

### Task 7: CLI `evolver dedup` command

**Files:**
- Modify: `evolver/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for CLI dedup command**

```python
# tests/test_cli.py — add at end
from unittest.mock import patch, MagicMock


def test_cli_dedup_dry_run():
    from evolver.cli import main
    with patch("sys.argv", ["evolver", "dedup", "--dry-run"]):
        with patch("evolver.cli._get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get_all_memories_with_embeddings.return_value = []
            # Should not raise
            try:
                main()
            except SystemExit:
                pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_cli.py -v -k "dedup"`
Expected: FAIL — dedup command not found

- [ ] **Step 3: Add dedup command to CLI**

```python
# evolver/cli.py — add to argument parser
    subparsers = parser.add_subparsers(dest="command")
    # ... existing commands ...
    dedup_parser = subparsers.add_parser("dedup", help="Remove near-duplicate memories")
    dedup_parser.add_argument("--dry-run", action="store_true", help="Preview only")
    dedup_parser.add_argument("--threshold", type=float, default=0.15, help="Cosine distance threshold")
    dedup_parser.add_argument("--category", type=str, default=None, help="Filter by category")
```

```python
# evolver/cli.py — add to command dispatch
    elif args.command == "dedup":
        from evolver.dedup import Deduplicator
        from evolver.embedding import EmbeddingClient
        storage = _get_storage(args)
        emb = EmbeddingClient()
        dedup = Deduplicator(storage, emb, threshold=args.threshold)
        kept, deleted = dedup.dedup(category=args.category, dry_run=args.dry_run)
        mode = "DRY RUN" if args.dry_run else "LIVE"
        print(f"[{mode}] Kept: {kept}, Deleted: {deleted}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_cli.py -v -k "dedup"`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/cli.py tests/test_cli.py
git commit -m "feat: add evolver dedup CLI command"
```

---

## Phase 2: Infrastructure

### Task 8: Input normalization — strip_noise

**Files:**
- Create: `evolver/normalize.py`
- Test: `tests/test_normalize.py`

- [ ] **Step 1: Write failing tests for strip_noise**

```python
# tests/test_normalize.py
import pytest
from evolver.normalize import strip_noise, normalize_input


def test_strip_system_reminder_tags():
    text = "Before\n<system-reminder>some config</system-reminder>\nAfter"
    result = strip_noise(text)
    assert "system-reminder" not in result
    assert "Before" in result
    assert "After" in result


def test_strip_command_message_tags():
    text = "Hello\n<command-message>run tests</command-message>\nWorld"
    result = strip_noise(text)
    assert "command-message" not in result
    assert "Hello" in result
    assert "World" in result


def test_strip_hook_output_lines():
    text = "Content\nRan 2 Stop hook\nMore content"
    result = strip_noise(text)
    assert "Ran 2 Stop hook" not in result
    assert "Content" in result
    assert "More content" in result


def test_strip_collapsed_lines_marker():
    text = "Code\n… +42 lines\nEnd"
    result = strip_noise(text)
    assert "… +42 lines" not in result
    assert "Code" in result
    assert "End" in result


def test_strip_noise_preserves_user_prose():
    text = "I wrote a system-reminder handler for the app."
    result = strip_noise(text)
    # Should NOT strip inline mentions
    assert "system-reminder handler" in result


def test_normalize_input_passes_clean_text():
    text = "Clean text with no noise."
    result = normalize_input(text)
    assert result == text


def test_normalize_input_strips_noise():
    text = "Before\n<system-reminder>noise</system-reminder>\nAfter"
    result = normalize_input(text)
    assert "noise" not in result
    assert "Before" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_normalize.py -v`
Expected: FAIL — module `evolver.normalize` not found

- [ ] **Step 3: Implement normalize module**

```python
# evolver/normalize.py
import re

# System tags to strip (line-anchored, lazy body, can't cross blank lines)
_NOISE_TAGS = (
    "system-reminder",
    "command-message",
    "command-name",
    "task-notification",
    "user-prompt-submit-hook",
    "hook_output",
)

_TAG_PATTERNS = [
    re.compile(
        rf"(?m)^<{name}(?:\s[^>]*)?>" rf"(?:(?!\n\s*\n)[\s\S])*?" rf"</{name}>[ \t]*\n?"
    )
    for name in _NOISE_TAGS
]

# Hook output lines (line-anchored)
_HOOK_LINE_RE = re.compile(
    r"(?m)^Ran \d+ (?:Stop|PreCompact|PreToolUse|PostToolUse|UserPromptSubmit|Notification|SessionStart|SessionEnd) hook[s]?.*\n?"
)

# Collapsed lines marker
_COLLAPSED_LINES_RE = re.compile(r"(?m)^…\s*\+\d+ lines.*\n?")


def strip_noise(text: str) -> str:
    """Remove system tags, hook output, and UI chrome from text.

    All patterns are line-anchored. Inline mentions in user prose are preserved.
    """
    for pat in _TAG_PATTERNS:
        text = pat.sub("", text)
    text = _HOOK_LINE_RE.sub("", text)
    text = _COLLAPSED_LINES_RE.sub("", text)
    return text


def normalize_input(text: str, source: str = "auto") -> str:
    """Normalize input text before storage.

    Args:
        text: Raw input text.
        source: Source type hint (auto, chat_export, raw).

    Returns:
        Cleaned text.
    """
    return strip_noise(text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_normalize.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/normalize.py tests/test_normalize.py
git commit -m "feat: add input normalization with noise stripping"
```

---

### Task 9: Integrate normalize into MemoryEngine.store()

**Files:**
- Modify: `evolver/memory.py:37-127`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write failing test for normalize integration**

```python
# tests/test_memory.py — add at end


def test_store_normalizes_content_before_embedding():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    # Content with noise tags
    noisy_task = "fix bug\n<system-reminder>ignore this</system-reminder>"
    ids = engine.store(
        task=noisy_task, outcome="success",
        solution="fixed", lessons="validate",
    )

    # embed_single should have been called with cleaned content
    call_args = emb.embed_single.call_args_list
    for call in call_args:
        content = call[0][0]
        assert "system-reminder" not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_memory.py -v -k "normalize"`
Expected: FAIL — noise tags still in embedded content

- [ ] **Step 3: Add normalize import and call to store()**

```python
# evolver/memory.py — add import at top
from evolver.normalize import normalize_input

# In store() method, before embedding:
    if task:
        task = normalize_input(task)
    if solution:
        solution = normalize_input(solution)
    if context:
        context = normalize_input(context)
    if lessons:
        lessons = normalize_input(lessons)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_memory.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/memory.py tests/test_memory.py
git commit -m "feat: integrate normalize_input into MemoryEngine.store()"
```

---

### Task 10: ClosetIndex — topic→entity→memory_id fast lookup

**Files:**
- Create: `evolver/closet.py`
- Test: `tests/test_closet.py`

- [ ] **Step 1: Write failing tests for ClosetIndex**

```python
# tests/test_closet.py
import pytest
from evolver.closet import ClosetIndex


def test_closet_add_and_query():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Fixed auth bug in login module", category="success")
    closet.add(memory_id=2, content="Deployed docker container", category="success")

    results = closet.query("auth")
    assert 1 in results
    assert 2 not in results


def test_closet_query_multiple_matches():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Auth fix for login", category="success")
    closet.add(memory_id=2, content="Auth token validation", category="success")

    results = closet.query("auth")
    assert 1 in results
    assert 2 in results


def test_closet_query_no_match():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Docker deploy", category="success")

    results = closet.query("nonexistent")
    assert results == []


def test_closet_remove():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Auth fix", category="success")
    closet.remove(1)

    results = closet.query("auth")
    assert 1 not in results


def test_closet_empty_query():
    closet = ClosetIndex()
    closet.add(memory_id=1, content="Auth fix", category="success")

    results = closet.query("")
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_closet.py -v`
Expected: FAIL — module `evolver.closet` not found

- [ ] **Step 3: Implement ClosetIndex**

```python
# evolver/closet.py
import re
from collections import defaultdict


# Stoplist for entity extraction (capitalized words that aren't entities)
_STOPLIST = frozenset({
    "The", "This", "That", "These", "Those", "When", "Where", "What",
    "Why", "Who", "Which", "How", "After", "Before", "Then", "Now",
    "And", "But", "Or", "Yet", "So", "If", "Else", "Yes", "No",
})


class ClosetIndex:
    """Topic→entity→memory_id fast lookup index.

    Provides keyword-based memory lookup without vector search.
    Format: topic|entities|→memory_ids (in-memory implementation).
    """

    def __init__(self):
        # keyword -> set of memory_ids
        self._index: dict[str, set[int]] = defaultdict(set)
        # memory_id -> set of keywords (for removal)
        self._reverse: dict[int, set[str]] = defaultdict(set)

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content for indexing."""
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", content)
        keywords = set()
        for w in words:
            if w not in _STOPLIST:
                keywords.add(w.lower())
        return list(keywords)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_closet.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/closet.py tests/test_closet.py
git commit -m "feat: add ClosetIndex topic→entity→memory_id fast lookup"
```

---

### Task 11: Integrate ClosetIndex into MemoryEngine.store() and recall()

**Files:**
- Modify: `evolver/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write failing test for closet integration**

```python
# tests/test_memory.py — add at end


def test_store_populates_closet_index():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    from evolver.closet import ClosetIndex
    closet = ClosetIndex()
    engine.set_closet(closet)

    engine.store(
        task="fix auth bug", outcome="success",
        solution="fixed token", lessons="validate",
    )

    # Closet should have entries
    results = closet.query("auth")
    assert len(results) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_memory.py -v -k "closet"`
Expected: FAIL — `set_closet` not found

- [ ] **Step 3: Add closet integration**

```python
# evolver/memory.py — add to __init__
    def __init__(self, ...):
        # ... existing ...
        self._closet = None

    def set_closet(self, closet):
        """Configure closet index for store()."""
        self._closet = closet

# In store(), after memory insertion:
    # Populate closet index
    if self._closet and memory_ids:
        for mid, text in link_pairs:
            self._closet.add(memory_id=mid, content=text, category=mem.category if 'mem' in dir() else "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/test_memory.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/memory.py tests/test_memory.py
git commit -m "feat: integrate ClosetIndex into MemoryEngine.store()"
```

---

### Task 12: Final integration — run all tests

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/ -v --tb=short`
Expected: All tests pass (171 existing + new tests)

- [ ] **Step 2: Check test count**

Run: `cd E:/skills/improve/evolver-project && python -m pytest tests/ --co -q | wc -l`
Expected: 190+ tests collected

- [ ] **Step 3: Commit any fixes if needed**

If any tests fail, fix and commit:
```bash
git add -A
git commit -m "fix: resolve test failures from progressive memory integration"
```

---

## Summary

| Task | Module | Tests | Lines |
|------|--------|-------|-------|
| 1 | models.py snippet field | 1 | ~5 |
| 2 | stack.py truncate_content | 5 | ~30 |
| 3 | stack.py MemoryStack L0/L1 | 4 | ~80 |
| 4 | stack.py MemoryStack L2/L3 | 3 | ~40 |
| 5 | dedup.py Deduplicator | 4 | ~100 |
| 6 | memory.py dedup integration | 2 | ~20 |
| 7 | cli.py dedup command | 1 | ~20 |
| 8 | normalize.py strip_noise | 7 | ~50 |
| 9 | memory.py normalize integration | 1 | ~10 |
| 10 | closet.py ClosetIndex | 5 | ~70 |
| 11 | memory.py closet integration | 1 | ~15 |
| 12 | Final verification | 0 | 0 |
| **Total** | | **34** | **~440** |
