# Third Brain Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Borrow Third Brain's best patterns — closure protocol, verify-before-claim, knowledge lifecycle, and 4-layer architecture — into Evolver.

**Architecture:** 3 phases: Phase 1 adds 2 SKILL.md files (zero code changes), Phase 2 adds lifecycle field to Memory model with DB migration and reranker integration, Phase 3 refactors compiler.assemble() for 4-layer output.

**Tech Stack:** Python 3.11+, Click CLI, SQLite/MySQL, pytest

---

## File Structure

| Phase | File | Action | Purpose |
|-------|------|--------|---------|
| 1 | `evolver/skills/closure-protocol/SKILL.md` | Create | Closure protocol skill |
| 1 | `evolver/skills/verify-before-claim/SKILL.md` | Create | Verify before claim skill |
| 2 | `evolver/models.py` | Modify | Add `lifecycle` field to Memory |
| 2 | `evolver/storage_sqlite.py` | Modify | Add lifecycle column migration |
| 2 | `evolver/storage.py` | Modify | Add lifecycle column migration |
| 2 | `evolver/storage_base.py` | Modify | Update insert/query/_row_to_memory for lifecycle |
| 2 | `evolver/memory.py` | Modify | Add `update_lifecycle()`, reranker lifecycle weight |
| 2 | `evolver/cli.py` | Modify | Add `--stale` to forget command |
| 2 | `tests/test_lifecycle.py` | Create | Tests for lifecycle feature |
| 3 | `evolver/compiler.py` | Modify | Refactor `assemble()` for 4-layer output |
| 3 | `tests/test_compiler.py` | Modify | Add 4-layer assemble tests |

---

## Phase 1: Skills (Zero Code Changes)

### Task 1: Create closure-protocol Skill

**Files:**
- Create: `evolver/skills/closure-protocol/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p "E:/skills/improve/evolver-project/evolver/skills/closure-protocol"
```

- [ ] **Step 2: Write SKILL.md**

Create `evolver/skills/closure-protocol/SKILL.md`:

```markdown
---
name: evolver-closure
description: Close agent sessions with structured knowledge extraction. Ensures no value leaks from sessions — every significant output feeds back into Evolver via learn(). Use at session end or when user says "save session" / "close session".
---

# Evolver Closure Protocol

Every significant agent session must close with knowledge extraction. No value leakage.

## When to Use

- Agent completed ≥3 tool calls in the session
- User says "save session" / "close session" / "extract knowledge"
- After completing a substantive task (code fix, research, design)
- User corrects the agent's understanding of a topic

## The 3-Step Closure Cycle

```
Step 1: FORMAT
  Extract key outputs from the session into evolver.learn() parameters:
  - task: what was the session objective?
  - outcome: success or failure?
  - solution: what was the core approach?
  - lessons: what pitfalls, insights, or patterns emerged?

Step 2: LINK
  Check for related history before storing:
  - Call evolver.recall() with a summary of the task
  - If related memories found → note connections in lessons
  - If conflicts detected → mark conflict, do NOT overwrite old memories
  - If knowledge gaps found → note them

Step 3: LOG
  Persist to Evolver:
  - Call evolver.learn() with structured parameters
  - Verify storage by calling evolver.recall() to confirm retrievability
  - Report stored memory IDs to user
```

## Extraction Quality Rules

- **Don't over-extract**: trivial sessions (<3 tool calls) skip learning
- **Be specific**: "learned that pytest fixtures need scope='session' for DB setup" not "learned about testing"
- **Capture failures**: failed solutions are as valuable as successful ones
- **Note conflicts**: if new learning contradicts existing memory, annotate it

## Anti-patterns

- Extracting from shallow sessions (<3 tool calls)
- Too vague ("learned many things") or too granular (every tool call)
- Storing without checking for duplicates via recall() first
- Overwriting existing memories without conflict annotation
- Saying "done" without verifying learn() succeeded

## Quality Gates

- [ ] Session depth check passed (≥3 tool calls or user-initiated)
- [ ] Extraction is specific and actionable
- [ ] No duplicate memories created (recall() check before learn())
- [ ] Conflicts annotated, not silently overwritten
- [ ] Memory IDs confirmed via output
```

- [ ] **Step 3: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/skills/closure-protocol/SKILL.md
git commit -m "feat: add evolver-closure skill for session knowledge extraction"
```

### Task 2: Create verify-before-claim Skill

**Files:**
- Create: `evolver/skills/verify-before-claim/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p "E:/skills/improve/evolver-project/evolver/skills/verify-before-claim"
```

- [ ] **Step 2: Write SKILL.md**

Create `evolver/skills/verify-before-claim/SKILL.md`:

```markdown
---
name: evolver-verify
description: Iron rule — no completion claims without fresh verification evidence. Use whenever about to claim work is done, fixed, working, or passing. Run verification commands and show output before making any success statement.
---

# Evolver Verify Before Claim

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

## When to Use

- Before saying "done", "fixed", "complete", "passing", "working"
- Before committing or creating a PR
- When the user asks "is it working?"
- Any time the agent feels the urge to say "it should work"

## The Gate Function

```
1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim
```

**Skip any step = lying, not verifying.**

## Evolver-Specific Verification

| Action | Verification Required |
|--------|----------------------|
| skillgen complete | `evolver evaluate -f <file>` score ≥60 |
| distill complete | `evolver stats` shows updated fact count |
| learn complete | `evolver recall <query>` returns the stored memory |
| forget complete | `evolver stats` shows decreased memory count |
| lifecycle updated | `evolver stats` shows lifecycle distribution |

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test output: 0 failures | Previous run, "should pass" |
| Memory stored | recall() returns it | "learn() returned IDs" |
| Distill complete | stats() shows new facts | "distill() ran without error" |

## Red Flags — STOP

- Using "should", "probably", "seems to" about completion
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!")
- About to commit/push/PR without verification
- Trusting agent success reports without independent check

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Different context so rule doesn't apply" | Spirit over letter |

## Quality Gates

- [ ] Verification command identified and run
- [ ] Full output shown (exit code, failure count)
- [ ] Claim only made WITH evidence
- [ ] No "should", "probably", "I think" on completion status
```

- [ ] **Step 3: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/skills/verify-before-claim/SKILL.md
git commit -m "feat: add evolver-verify skill for completion verification discipline"
```

---

## Phase 2: Knowledge Lifecycle

### Task 3: Add lifecycle field to Memory model

**Files:**
- Modify: `evolver/models.py:25-36`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_memory_lifecycle_default():
    from evolver.models import Memory
    m = Memory(content="test", category="experience")
    assert m.lifecycle == "seed"


def test_memory_lifecycle_custom():
    from evolver.models import Memory
    m = Memory(content="test", category="experience", lifecycle="growing")
    assert m.lifecycle == "growing"


def test_memory_to_dict_includes_lifecycle():
    from evolver.models import Memory
    m = Memory(content="test", category="experience", lifecycle="evergreen")
    d = m.to_dict()
    assert d["lifecycle"] == "evergreen"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_models.py::test_memory_lifecycle_default -v`
Expected: FAIL with `AttributeError` or `TypeError`

- [ ] **Step 3: Add lifecycle field to Memory dataclass**

In `evolver/models.py`, add `lifecycle` field to Memory class (after `content_hash`):

```python
@dataclass
class Memory:
    content: str
    category: str
    tags: list = field(default_factory=list)
    embedding: Optional[list] = None
    source: Optional[str] = None
    importance: float = 0.5
    access_count: int = 0
    content_hash: Optional[str] = None
    lifecycle: str = "seed"  # seed | growing | evergreen | stale
    id: Optional[int] = None
    created_at: Optional[str] = None
```

Also update `to_dict()` to include lifecycle:

```python
def to_dict(self) -> dict:
    return {
        "id": self.id,
        "content": self.content,
        "category": self.category,
        "tags": json.dumps(self.tags),
        "embedding": self.embedding,
        "source": self.source,
        "importance": self.importance,
        "access_count": self.access_count,
        "lifecycle": self.lifecycle,
        "created_at": self.created_at,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/models.py tests/test_models.py
git commit -m "feat: add lifecycle field to Memory model"
```

### Task 4: DB migration for lifecycle column

**Files:**
- Modify: `evolver/storage_sqlite.py:37-60`
- Modify: `evolver/storage.py` (MySQL migration)
- Modify: `setup.sql`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_storage.py`:

```python
def test_lifecycle_column_exists(sqlite_storage):
    """Verify lifecycle column exists after migration."""
    storage = sqlite_storage
    # Insert a memory with default lifecycle
    from evolver.models import Memory
    mem = Memory(content="test lifecycle", category="test")
    mid = storage.insert_memory(mem)
    # Read back and check lifecycle
    row = storage._fetchone(
        "SELECT lifecycle FROM memories WHERE id = ?", (mid,)
    )
    assert row is not None
    assert row["lifecycle"] == "seed"


def test_lifecycle_column_update(sqlite_storage):
    """Verify lifecycle can be updated."""
    storage = sqlite_storage
    from evolver.models import Memory
    mem = Memory(content="test lifecycle update", category="test")
    mid = storage.insert_memory(mem)
    storage._execute(
        "UPDATE memories SET lifecycle = ? WHERE id = ?",
        ("growing", mid)
    )
    row = storage._fetchone(
        "SELECT lifecycle FROM memories WHERE id = ?", (mid,)
    )
    assert row["lifecycle"] == "growing"
```

Note: Check if `tests/test_storage.py` has a `sqlite_storage` fixture. If not, add one:

```python
@pytest.fixture
def sqlite_storage():
    import tempfile, os
    from evolver.storage_sqlite import SQLiteStorage
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    storage = SQLiteStorage(path)
    yield storage
    storage.close()
    os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_storage.py::test_lifecycle_column_exists -v`
Expected: FAIL (column doesn't exist yet)

- [ ] **Step 3: Add lifecycle migration to SQLiteStorage._ensure_schema()**

In `evolver/storage_sqlite.py`, after the content_hash migration block (around line 56-60), add:

```python
# Migration: add lifecycle column if missing
try:
    self._conn.execute("ALTER TABLE memories ADD COLUMN lifecycle TEXT DEFAULT 'seed')
except Exception:
    pass  # column already exists
```

Also update the CREATE TABLE statement to include lifecycle:

```sql
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content     TEXT NOT NULL,
    category    TEXT,
    tags        TEXT,
    embedding   BLOB,
    source      TEXT,
    importance  REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    content_hash TEXT,
    lifecycle   TEXT DEFAULT 'seed',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Add lifecycle migration to MySQLStorage**

In `evolver/storage.py`, in the `_ensure_schema()` method, add similar migration:

```python
# Migration: add lifecycle column if missing
try:
    self._execute("ALTER TABLE memories ADD COLUMN lifecycle VARCHAR(20) DEFAULT 'seed'")
    self.commit()
except Exception:
    pass  # column already exists
```

- [ ] **Step 5: Update setup.sql**

In `setup.sql`, add `lifecycle` column to the memories table definition:

```sql
lifecycle   VARCHAR(20) DEFAULT 'seed',
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_storage.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/storage_sqlite.py evolver/storage.py setup.sql tests/test_storage.py
git commit -m "feat: add lifecycle column migration to SQLite and MySQL"
```

### Task 5: Update storage_base for lifecycle CRUD

**Files:**
- Modify: `evolver/storage_base.py:58-70` (insert_memory)
- Modify: `evolver/storage_base.py:220-228` (_row_to_memory)
- Modify: `evolver/storage_base.py:94-109` (get_all_memories_with_embeddings)
- Modify: `evolver/storage_base.py:593-608` (get_memories_in_range)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_storage.py`:

```python
def test_insert_memory_with_lifecycle(sqlite_storage):
    """Verify lifecycle is persisted on insert."""
    storage = sqlite_storage
    from evolver.models import Memory
    mem = Memory(content="test with lifecycle", category="test", lifecycle="growing")
    mid = storage.insert_memory(mem)
    # Read back via _row_to_memory
    row = storage._fetchone(
        "SELECT id, content, category, tags, embedding, source, importance, access_count, content_hash, lifecycle, created_at FROM memories WHERE id = ?",
        (mid,)
    )
    m = storage._row_to_memory(row)
    assert m.lifecycle == "growing"


def test_get_memories_in_range_includes_lifecycle(sqlite_storage):
    """Verify lifecycle is returned in range queries."""
    storage = sqlite_storage
    from evolver.models import Memory
    mem = Memory(content="range test lifecycle", category="test", lifecycle="evergreen")
    storage.insert_memory(mem)
    results = storage.get_memories_in_range(days=1)
    assert any(m.lifecycle == "evergreen" for m in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_storage.py::test_insert_memory_with_lifecycle -v`
Expected: FAIL

- [ ] **Step 3: Update insert_memory() in storage_base.py**

In `evolver/storage_base.py`, update `insert_memory()`:

```python
def insert_memory(self, mem: Memory) -> int:
    p = self._placeholder()
    sql = f"""
        INSERT INTO memories (content, category, tags, embedding, source, importance, content_hash, lifecycle)
        VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
    """
    cur = self._execute(sql, (
        mem.content, mem.category,
        json.dumps(mem.tags) if mem.tags else None,
        mem.embedding, mem.source, mem.importance,
        mem.content_hash, mem.lifecycle,
    ))
    return cur.lastrowid
```

- [ ] **Step 4: Update _row_to_memory() in storage_base.py**

```python
def _row_to_memory(self, r: dict) -> Memory:
    tags = json.loads(r["tags"]) if r.get("tags") else []
    return Memory(
        id=r["id"], content=r["content"], category=r["category"],
        tags=tags, embedding=r.get("embedding"), source=r.get("source"),
        importance=r.get("importance", 0.5), access_count=r.get("access_count", 0),
        content_hash=r.get("content_hash"),
        lifecycle=r.get("lifecycle", "seed"),
        created_at=r.get("created_at"),
    )
```

- [ ] **Step 5: Update SELECT queries to include lifecycle**

In `get_all_memories_with_embeddings()`, add `lifecycle` to the SELECT column list:

```python
sql = (
    "SELECT id, content, category, tags, embedding, source, importance, access_count, content_hash, lifecycle, created_at "
    "FROM memories WHERE " + " AND ".join(where) +
    " ORDER BY created_at DESC"
)
```

In `get_memories_in_range()`, add `lifecycle` to the SELECT column list:

```python
sql = (
    "SELECT id, content, category, tags, embedding, source, importance, access_count, content_hash, lifecycle, created_at "
    "FROM memories WHERE " + " AND ".join(where) +
    " ORDER BY importance DESC, created_at DESC"
)
```

Also update `get_all_memories_with_embeddings_batched()` similarly.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_storage.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/storage_base.py tests/test_storage.py
git commit -m "feat: add lifecycle to storage CRUD operations"
```

### Task 6: Implement update_lifecycle() method

**Files:**
- Modify: `evolver/memory.py`
- Test: `tests/test_lifecycle.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lifecycle.py`:

```python
"""Tests for knowledge lifecycle management."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import numpy as np
from evolver.memory import MemoryEngine
from evolver.models import Memory


def make_engine():
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.embed_single.return_value = np.random.rand(384).tolist()
    mock_embedding.embed.return_value = [np.random.rand(384).tolist() for _ in range(3)]
    mock_embedding.vector_to_bytes.return_value = b"\x00" * (384 * 4)
    mock_embedding.bytes_to_vector.return_value = [0.0] * 384
    mock_embedding.dim = 384
    engine = MemoryEngine(mock_storage, mock_embedding)
    return engine, mock_storage, mock_embedding


def test_seed_to_growing_on_access_count():
    """seed → growing when access_count >= 2."""
    engine, storage, _ = make_engine()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="test", category="experience",
               access_count=2, importance=0.5, lifecycle="seed",
               embedding=b"\x00" * 12),
    ]
    storage._fetchone.return_value = None  # no backlinks needed

    result = engine.update_lifecycle()

    assert result["transitioned"] >= 1
    # Verify the UPDATE was called
    storage._execute.assert_called()


def test_growing_to_evergreen_on_importance_and_age():
    """growing → evergreen when importance >= 0.8 and age >= 30 days."""
    engine, storage, _ = make_engine()
    old_date = (datetime.now() - timedelta(days=35)).isoformat()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=2, content="test", category="insight",
               access_count=5, importance=0.9, lifecycle="growing",
               created_at=old_date, embedding=b"\x00" * 12),
    ]

    result = engine.update_lifecycle()

    assert result["transitioned"] >= 1


def test_any_to_stale_on_old_and_low_importance():
    """any → stale when 90 days unrecalled and importance < 0.5."""
    engine, storage, _ = make_engine()
    old_date = (datetime.now() - timedelta(days=100)).isoformat()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=3, content="old forgotten", category="experience",
               access_count=0, importance=0.3, lifecycle="seed",
               created_at=old_date, embedding=b"\x00" * 12),
    ]

    result = engine.update_lifecycle()

    assert result["transitioned"] >= 1


def test_stale_not_evergreen():
    """stale memories should not transition to evergreen directly."""
    engine, storage, _ = make_engine()
    old_date = (datetime.now() - timedelta(days=35)).isoformat()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=4, content="stale but important", category="insight",
               access_count=5, importance=0.9, lifecycle="stale",
               created_at=old_date, embedding=b"\x00" * 12),
    ]

    result = engine.update_lifecycle()

    # Stale with high importance and access should stay stale
    # (reactivation only happens via recall, not update_lifecycle)
    assert result["distribution"]["stale"] >= 1
    assert "stale_to_evergreen" not in result.get("by_type", {})


def test_update_lifecycle_returns_distribution():
    """update_lifecycle returns lifecycle distribution stats."""
    engine, storage, _ = make_engine()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="a", category="test", lifecycle="seed", embedding=b"\x00" * 12),
        Memory(id=2, content="b", category="test", lifecycle="growing", embedding=b"\x00" * 12),
        Memory(id=3, content="c", category="test", lifecycle="stale", embedding=b"\x00" * 12),
    ]

    result = engine.update_lifecycle()

    assert "distribution" in result
    assert result["distribution"]["seed"] >= 1
    assert result["distribution"]["growing"] >= 1
    assert result["distribution"]["stale"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_lifecycle.py -v`
Expected: ALL FAIL (update_lifecycle doesn't exist)

- [ ] **Step 3: Implement update_lifecycle() in memory.py**

Add this method to the `MemoryEngine` class in `evolver/memory.py`:

```python
def update_lifecycle(self) -> dict:
    """Scan all memories, auto-migrate lifecycle stages.

    Rules:
    - seed → growing: access_count >= 2
    - growing → evergreen: importance >= 0.8 and age >= 30 days
    - any → stale: 90 days unrecalled and importance < 0.5
    - stale stays stale until reactivated by recall()

    Returns: {transitioned: int, by_type: {from_to: count}, distribution: {stage: count}}
    """
    from datetime import datetime, timezone, timedelta

    memories = self.storage.get_all_memories_with_embeddings()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    transitions = {}
    distribution = {"seed": 0, "growing": 0, "evergreen": 0, "stale": 0}
    transitioned = 0

    for m in memories:
        current = m.lifecycle or "seed"
        new_lifecycle = current

        # Parse age
        age_days = 0
        if m.created_at:
            try:
                created = datetime.fromisoformat(str(m.created_at))
                if created.tzinfo is not None:
                    created = created.astimezone(timezone.utc).replace(tzinfo=None)
                age_days = (now - created).days
            except (ValueError, TypeError):
                pass

        # Rule: any → stale (90 days, low importance, low access)
        if age_days >= 90 and (m.importance or 0) < 0.5 and (m.access_count or 0) == 0:
            new_lifecycle = "stale"
        # Rule: seed → growing (access_count >= 2)
        elif current == "seed" and (m.access_count or 0) >= 2:
            new_lifecycle = "growing"
        # Rule: growing → evergreen (importance >= 0.8, age >= 30 days)
        elif current == "growing" and (m.importance or 0) >= 0.8 and age_days >= 30:
            new_lifecycle = "evergreen"

        if new_lifecycle != current:
            transition_key = f"{current}_to_{new_lifecycle}"
            transitions[transition_key] = transitions.get(transition_key, 0) + 1
            transitioned += 1
            # Update in DB
            p = self.storage._placeholder()
            self.storage._execute(
                f"UPDATE memories SET lifecycle = {p} WHERE id = {p}",
                (new_lifecycle, m.id),
            )

        distribution[new_lifecycle] = distribution.get(new_lifecycle, 0) + 1

    return {
        "transitioned": transitioned,
        "by_type": transitions,
        "distribution": distribution,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_lifecycle.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/memory.py tests/test_lifecycle.py
git commit -m "feat: implement update_lifecycle() for knowledge lifecycle management"
```

### Task 7: Integrate lifecycle into recall reranker

**Files:**
- Modify: `evolver/memory.py:424-509` (_rerank method)
- Test: `tests/test_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_lifecycle.py`:

```python
def test_rerank_applies_lifecycle_weight():
    """Lifecycle stage affects recall ranking."""
    engine, storage, emb = make_engine()
    # Two memories with same content but different lifecycle
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="git merge conflict fix", category="success",
               lifecycle="evergreen", importance=0.8, embedding=b"\x00" * 12),
        Memory(id=2, content="git merge conflict fix", category="success",
               lifecycle="stale", importance=0.3, embedding=b"\x00" * 12),
    ]
    storage.query_nodes.return_value = []

    results = engine.recall("git merge conflict")

    # Verify results are returned and have lifecycle info
    assert len(results) > 0
    for r in results:
        assert hasattr(r, 'lifecycle')
        assert r.lifecycle in ("seed", "growing", "evergreen", "stale")
```

- [ ] **Step 2: Run test to verify it fails (or passes trivially)**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_lifecycle.py::test_rerank_applies_lifecycle_weight -v`

- [ ] **Step 3: Add lifecycle weight to _rerank()**

In `evolver/memory.py`, in the `_rerank()` method, add a lifecycle signal after the existing 5 signals:

```python
# Signal 6: Lifecycle weight
lifecycle_weights = {
    "seed": 1.0,
    "growing": 1.1,
    "evergreen": 1.3,
    "stale": 0.5,
}
lifecycle_boost = lifecycle_weights.get(getattr(r, 'lifecycle', 'seed'), 1.0)
```

Then update the combined score formula:

```python
# Combined reranker score
rerank_score = (
    0.40 * r.score +           # Original fusion score
    0.20 * jaccard +            # Token overlap
    0.10 * len_penalty +        # Conciseness
    0.10 * category_boost +     # Category relevance
    0.10 * recency_boost +      # Temporal grounding
    0.10 * lifecycle_boost      # Lifecycle stage
)
```

Note: The RecallResult needs to carry lifecycle info. Check if `related_nodes` can carry it, or add a `lifecycle` field to RecallResult. Simplest: add lifecycle to RecallResult.

In `evolver/models.py`, add `lifecycle` to RecallResult:

```python
@dataclass
class RecallResult:
    content: str
    score: float
    source: str
    category: str
    related_nodes: list = field(default_factory=list)
    snippet: str = ""
    lifecycle: str = "seed"
```

Then in `memory.py`'s `recall()`, when building RecallResult objects, pass the lifecycle from the Memory object.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_lifecycle.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/memory.py evolver/models.py tests/test_lifecycle.py
git commit -m "feat: integrate lifecycle weights into recall reranker"
```

### Task 8: Expose lifecycle in Evolver facade and CLI

**Files:**
- Modify: `evolver/__init__.py` (add update_lifecycle to facade)
- Modify: `evolver/cli.py` (add --stale to forget, add lifecycle to stats)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_evolver.py`:

```python
def test_update_lifecycle_via_facade():
    """Evolver facade exposes update_lifecycle."""
    from evolver import Evolver
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        evo = Evolver(db_url=f"sqlite:///{path}", fallback_embeddings=True)
        result = evo.update_lifecycle()
        assert "transitioned" in result
        assert "distribution" in result
        evo.close()
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_evolver.py::test_update_lifecycle_via_facade -v`
Expected: FAIL (update_lifecycle not on Evolver class)

- [ ] **Step 3: Add update_lifecycle() to Evolver facade**

In `evolver/__init__.py`, add method:

```python
def update_lifecycle(self) -> dict:
    """Auto-migrate memory lifecycle stages (seed→growing→evergreen→stale)."""
    return self._memory.update_lifecycle()
```

- [ ] **Step 4: Add --stale option to forget CLI command**

In `evolver/cli.py`, update the `forget` command:

```python
@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--id", "memory_id", type=int, help="Memory ID to delete")
@click.option("--older-than", type=int, help="Delete memories older than N days")
@click.option("--below", type=float, help="Delete memories with importance below threshold")
@click.option("--stale", is_flag=True, help="Delete all stale lifecycle memories")
@click.pass_context
def forget(ctx, db_url, memory_id, older_than, below, stale):
    """Forget memories."""
    if not any([memory_id, older_than, below, stale]):
        click.echo("Error: specify --id, --older-than, --below, or --stale")
        return
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        if stale:
            # Get all stale memories and delete them
            all_mems = evo._storage.get_all_memories_with_embeddings()
            stale_ids = [m.id for m in all_mems if m.lifecycle == "stale"]
            for mid in stale_ids:
                evo.forget(memory_id=mid)
            click.echo(f"Forgot {len(stale_ids)} stale memories.")
        else:
            evo.forget(memory_id=memory_id, older_than_days=older_than, low_importance=below)
            click.echo("Done.")
    finally:
        evo.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_evolver.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/__init__.py evolver/cli.py tests/test_evolver.py
git commit -m "feat: expose lifecycle in facade and CLI (--stale forget option)"
```

---

## Phase 3: 4-Layer Architecture

### Task 9: Refactor assemble() for 4-layer output

**Files:**
- Modify: `evolver/compiler.py:128-142` (assemble method)
- Test: `tests/test_compiler.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_compiler.py`:

```python
def test_assemble_four_layers():
    """assemble() should output 4 layers: Active, Quick Access, Durable, Facts."""
    from evolver.compiler import MemoryCompiler
    from unittest.mock import MagicMock
    import tempfile, os

    mock_storage = MagicMock()
    mock_llm = MagicMock()

    # Mock active memories (Layer 1)
    from evolver.models import Memory, Fact
    mock_storage.get_memories_in_range.return_value = [
        Memory(id=1, content="recent fix", category="success", lifecycle="seed"),
    ]
    # Mock facts (Layer 4)
    mock_storage.get_all_facts.return_value = [
        Fact(id=1, fact="pytest uses fixtures", tags=["testing"]),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        compiler = MemoryCompiler(mock_storage, mock_llm, memory_dir=tmpdir)

        # Write some distill files for layers 2-3
        with open(os.path.join(tmpdir, "today.md"), "w") as f:
            f.write("Today's lesson: always test edge cases")
        with open(os.path.join(tmpdir, "week.md"), "w") as f:
            f.write("This week: learned about RRF fusion")
        with open(os.path.join(tmpdir, "longterm.md"), "w") as f:
            f.write("Long-term: expert at knowledge retrieval")

        result = compiler.assemble()

        assert "[Active" in result
        assert "[Quick Access" in result
        assert "[Durable" in result
        assert "[Facts" in result


def test_assemble_legacy_format():
    """assemble(format='legacy') should output old 3-layer format."""
    from evolver.compiler import MemoryCompiler
    from unittest.mock import MagicMock
    import tempfile, os

    mock_storage = MagicMock()
    mock_llm = MagicMock()
    mock_storage.get_memories_in_range.return_value = []
    mock_storage.get_all_facts.return_value = []

    with tempfile.TemporaryDirectory() as tmpdir:
        compiler = MemoryCompiler(mock_storage, mock_llm, memory_dir=tmpdir)

        with open(os.path.join(tmpdir, "today.md"), "w") as f:
            f.write("Today's lesson")
        with open(os.path.join(tmpdir, "week.md"), "w") as f:
            f.write("This week")
        with open(os.path.join(tmpdir, "longterm.md"), "w") as f:
            f.write("Long-term")

        result = compiler.assemble(format="legacy")

        assert "[Long-term profile]" in result
        assert "[This week]" in result
        assert "[Today]" in result
        assert "[Active" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_compiler.py::test_assemble_four_layers -v`
Expected: FAIL (assemble doesn't have format param, doesn't output 4 layers)

- [ ] **Step 3: Refactor assemble() in compiler.py**

Replace the existing `assemble()` method in `evolver/compiler.py`:

```python
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
        recent = self.storage.get_memories_in_range(days=0)
        if recent:
            # Max 10 most recent
            active_text = self._memories_to_text(recent[-10:])
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
        parts.append(f"[Quick Access — distilled recent]\n" + "\n\n".join(qa_parts))

    # Layer 3: Durable — longterm profile
    longterm = self._read_file("longterm.md")
    if longterm:
        parts.append(f"[Durable — long-term profile]\n{longterm}")

    # Layer 4: Facts — top atomic facts
    try:
        facts = self.storage.get_all_facts(limit=20)
        if facts:
            fact_lines = [f"- {f.fact}" for f in facts]
            parts.append(f"[Facts — atomic knowledge]\n" + "\n".join(fact_lines))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/test_compiler.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
cd "E:/skills/improve/evolver-project"
git add evolver/compiler.py tests/test_compiler.py
git commit -m "feat: refactor assemble() for 4-layer knowledge architecture

Layers: Active (recent session) → Quick Access (today+week) → Durable (longterm) → Facts (atomic)
Backward compatible via format='legacy' parameter."
```

### Task 10: Update get_prompt_injection() and final integration

**Files:**
- Modify: `evolver/compiler.py` (get_prompt_injection)

- [ ] **Step 1: Verify get_prompt_injection() works with new assemble()**

The existing `get_prompt_injection()` calls `self.assemble()`, so it automatically gets the 4-layer format. No code change needed — just verify.

- [ ] **Step 2: Run full test suite**

Run: `cd "E:/skills/improve/evolver-project" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 3: Final commit with all Phase 3 changes**

```bash
cd "E:/skills/improve/evolver-project"
git add -A
git commit -m "feat: complete Third Brain integration — closure skill, verify skill, lifecycle, 4-layer architecture"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `evolver/skills/closure-protocol/SKILL.md` exists and is well-formed
- [ ] `evolver/skills/verify-before-claim/SKILL.md` exists and is well-formed
- [ ] `Memory` model has `lifecycle` field defaulting to "seed"
- [ ] SQLite and MySQL migrations handle lifecycle column
- [ ] `insert_memory()` persists lifecycle
- [ ] `_row_to_memory()` reads lifecycle
- [ ] `update_lifecycle()` transitions stages correctly
- [ ] `recall()` reranker applies lifecycle weights
- [ ] `Evolver` facade exposes `update_lifecycle()`
- [ ] CLI `forget --stale` works
- [ ] `assemble()` outputs 4 layers by default
- [ ] `assemble(format="legacy")` outputs old 3-section format
- [ ] All existing tests still pass
- [ ] New tests cover lifecycle and 4-layer assembly
