# Evolver: Bidirectional Linking + Darwin Quality Check

**Date:** 2026-05-20
**Status:** Approved
**Approach:** Extension Layer (Approach A)

---

## Overview

Two additions to evolver-project:

1. **LinkEngine** — Obsidian-style bidirectional linking for memories and graph nodes, auto-inferred via vector similarity and entity extraction
2. **QualityChecker** — Darwin-inspired 8-dimension quality evaluation with auto-fix and ratchet mechanism for generated skills

---

## Data Model

### New Tables

```sql
CREATE TABLE IF NOT EXISTS links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type   TEXT NOT NULL,  -- 'memory' | 'graph_node'
    source_id     INTEGER NOT NULL,
    target_type   TEXT NOT NULL,  -- 'memory' | 'graph_node'
    target_id     INTEGER NOT NULL,
    link_type     TEXT NOT NULL,  -- 'auto_similar' | 'auto_entity' | 'explicit'
    weight        REAL DEFAULT 1.0,
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(source_type, source_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS skill_evaluations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id      INTEGER NOT NULL,
    version       INTEGER NOT NULL,
    total_score   REAL,
    dim_scores    TEXT,          -- JSON object
    eval_mode     TEXT DEFAULT 'auto',
    round         INTEGER DEFAULT 1,
    status        TEXT DEFAULT 'pass',  -- 'pass' | 'improved' | 'reverted'
    diff_summary  TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);
```

### Link Types

- `auto_similar`: vector cosine similarity between memories (threshold > 0.6)
- `auto_entity`: entity extracted from memory content matches a graph node
- `explicit`: reserved for future manual `[[wiki-link]]` support

### New Data Classes (models.py)

```python
@dataclass
class Link:
    id: int
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    link_type: str
    weight: float

@dataclass
class EvalResult:
    total_score: float
    dim_scores: dict[str, float]  # dimension_name -> score
    round: int
    status: str  # 'pass' | 'improved' | 'reverted'
```

---

## LinkEngine

**File:** `evolver/link.py`

### Public API

```python
class LinkEngine:
    def __init__(self, storage, embedding, memory_engine, graph_engine): ...

    # Auto-inference (called after memory store)
    def auto_link_memory(self, memory_id: int, content: str): ...
    def auto_link_batch(self, memory_ids: list[int], contents: list[str]): ...

    # Queries
    def backlinks(self, target_type: str, target_id: int) -> list[Link]: ...
    def outgoing(self, source_type: str, source_id: int) -> list[Link]: ...
    def linked_memories(self, memory_id: int, top_k: int = 10) -> list[RecallResult]: ...
    def linked_graph_nodes(self, memory_id: int) -> list[GraphNode]: ...

    # Link score for recall boost
    def compute_link_score(self, memory_id: int, query_related_ids: list[int]) -> float: ...

    # Maintenance
    def decay_links(self, factor: float = 0.95, min_weight: float = 0.01): ...
```

### Auto-Inference Logic

When `auto_link_memory(memory_id, content)` is called:

1. **Similarity links**: embed content, search top-10 similar memories by cosine similarity, create `auto_similar` links for those with similarity > 0.6, cap at 10 links per memory
2. **Entity links**: run `GraphEngine._extract_entities(content)`, for each entity find matching `graph_nodes` by label, create `auto_entity` links
3. All links are bidirectional: A→B and B→A are both stored

### Integration Point

`MemoryEngine.store()` builds `(memory_id, content)` pairs during insertion, then calls `auto_link_batch` after commit:

```python
# Inside store(), build link_pairs alongside memory_ids
link_pairs = []  # (memory_id, content_text)

if task:
    mid = self._storage.insert_memory(mem)
    memory_ids.append(mid)
    link_pairs.append((mid, content))  # "Task: ...\nSolution: ..."

if lessons:
    mid = self._storage.insert_memory(mem)
    memory_ids.append(mid)
    link_pairs.append((mid, lessons))

if context and len(context) > self._MIN_CONTEXT_LENGTH:
    mid = self._storage.insert_memory(mem)
    memory_ids.append(mid)
    link_pairs.append((mid, context))

# ... existing commit logic ...

# After commit, auto-link
if link_pairs:
    self._link.auto_link_batch(
        [mid for mid, _ in link_pairs],
        [text for _, text in link_pairs],
    )
```

---

## QualityChecker

**File:** `evolver/checker.py`

### 8-Dimension Rubric (adapted for evolver)

| # | Dimension | Weight | What It Checks |
|---|-----------|--------|----------------|
| 1 | Frontmatter | 8 | name, description, version, tags completeness |
| 2 | Workflow clarity | 15 | Steps ordered, executable, with I/O |
| 3 | Edge cases | 10 | Exception handling, fallback paths |
| 4 | Checkpoints | 7 | User confirmation at key decisions |
| 5 | Instruction specificity | 15 | Concrete params/examples, no vagueness |
| 6 | Resource integration | 5 | related_skills, tags, memory references valid |
| 7 | Architecture | 15 | Structure clear, no redundancy/gaps |
| 8 | Practical effectiveness | 25 | Test prompt output quality |

Scoring: each dimension 1-10, multiplied by weight. Total = sum / 10, max 100.

### Public API

```python
class QualityChecker:
    MAX_ROUNDS = 3

    def __init__(self, storage): ...

    def evaluate(self, skill_content: str, topic: str) -> EvalResult: ...
    def check_and_improve(self, skill_id: int, skill_content: str, topic: str) -> tuple[str, EvalResult]: ...
```

### Ratchet Mechanism

```
best_content = original_content
best_score = evaluate(original).total_score

for round in 1..MAX_ROUNDS:
    eval = evaluate(current_content, topic)
    weakest = min(eval.dim_scores, key=eval.dim_scores.get)

    improved = fix_dimension(current_content, weakest, eval)
    new_eval = evaluate(improved, topic)

    if new_eval.total_score > best_score:
        best_content = improved
        best_score = new_eval.total_score
        log(skill_id, round, new_eval, "improved")
    else:
        log(skill_id, round, eval, "reverted")
        break  # hit plateau

return best_content, final_eval
```

### fix_dimension Strategies

| Dimension | Fix Approach |
|-----------|-------------|
| Frontmatter | Fill missing fields, normalize description |
| Workflow | Add numbering, I/O descriptions |
| Edge cases | Add exception handling section |
| Checkpoints | Insert confirmation steps at decisions |
| Specificity | Replace vague text with concrete params/examples |
| Resources | Add related_skills, fix tags |
| Architecture | Reorder sections, remove redundancy |
| Effectiveness | Run test prompt, compare output quality |

### Integration Point

`SkillEngine.generate()` appends before returning:

```python
# After writing file, before return
improved_content, eval_result = self._checker.check_and_improve(skill_id, md_content, topic)
if improved_content != md_content:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(improved_content)
    md_content = improved_content
```

---

## Evolver Facade Changes

### New Methods

```python
class Evolver:
    def backlinks(self, target_type: str, target_id: int) -> list[Link]: ...
    def linked_memories(self, memory_id: int, top_k: int = 10) -> list[RecallResult]: ...
    def eval_skill(self, skill_content: str, topic: str) -> EvalResult: ...

    # Async variants
    async def backlinks_async(self, target_type: str, target_id: int) -> list[Link]: ...
    async def linked_memories_async(self, memory_id: int, top_k: int = 10) -> list[RecallResult]: ...
    async def eval_skill_async(self, skill_content: str, topic: str) -> EvalResult: ...
```

### recall() Weight Change

Default weights change from `(0.7, 0.2, 0.1)` to `(0.6, 0.15, 0.1, 0.15)`:
- 0.6: vector similarity
- 0.15: graph boost
- 0.1: importance
- 0.15: link boost (new)

---

## Complete Data Flow

```
learn(task, outcome, solution, lessons)
  ├─ MemoryEngine.store() → store memories
  │    └─ LinkEngine.auto_link_memory() → auto-create bidirectional links
  │         ├─ vector similarity → auto_similar links
  │         └─ entity extraction → auto_entity links
  └─ GraphEngine.build_from_text() → build graph nodes + edges

recall(query)
  ├─ vector similarity search
  ├─ graph boost
  ├─ link boost (new)
  └─ return sorted results

skillgen(topic)
  ├─ recall() → retrieve memories (with link boost)
  ├─ GraphEngine.query() → query graph
  ├─ render SKILL.md template
  ├─ QualityChecker.check_and_improve() (new)
  │    ├─ 8-dimension evaluation
  │    ├─ fix weakest dimension
  │    └─ ratchet: keep if improved, revert if not
  └─ return final SkillResult
```

---

## Files Changed

### Modified

| File | Change |
|------|--------|
| `evolver/__init__.py` | Add LinkEngine + QualityChecker init, 3 new public methods |
| `evolver/memory.py` | `store()` calls `auto_link_memory()` after commit |
| `evolver/skill.py` | `generate()` calls `check_and_improve()` before return |
| `evolver/storage_sqlite.py` | `_ensure_schema()` adds 2 new tables |
| `evolver/models.py` | Add Link, EvalResult dataclasses |

### New

| File | Content |
|------|---------|
| `evolver/link.py` | LinkEngine class |
| `evolver/checker.py` | QualityChecker class |
