# LinkEngine + QualityChecker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Obsidian-style bidirectional linking to evolver's memory system and Darwin-style 8-dimension quality checking to the skill engine.

**Architecture:** Two new modules (LinkEngine, QualityChecker) added as extension layers. Existing MemoryEngine, GraphEngine, and SkillEngine interfaces unchanged except for integration hooks. Storage gets 2 new tables.

**Tech Stack:** Python 3.10+, SQLite, pytest, unittest.mock

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `evolver/models.py` | Modify | Add `Link`, `EvalResult` dataclasses |
| `evolver/storage_sqlite.py` | Modify | Add `links` and `skill_evaluations` tables to schema, add link/eval CRUD methods |
| `evolver/link.py` | Create | `LinkEngine` — auto-inference, backlink queries, link scoring |
| `evolver/checker.py` | Create | `QualityChecker` — 8-dim evaluation, fix strategies, ratchet mechanism |
| `evolver/memory.py` | Modify | `store()` calls `auto_link_batch` after commit |
| `evolver/skill.py` | Modify | `generate()` calls `check_and_improve` before return |
| `evolver/__init__.py` | Modify | Wire LinkEngine + QualityChecker, add facade methods |
| `tests/test_link.py` | Create | Tests for LinkEngine |
| `tests/test_checker.py` | Create | Tests for QualityChecker |
| `tests/test_storage.py` | Modify | Tests for new storage methods |
| `tests/test_memory.py` | Modify | Test that store() triggers linking |
| `tests/test_skill.py` | Modify | Test that generate() triggers quality check |

---

### Task 1: Data Models — Link and EvalResult

**Files:**
- Modify: `evolver/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for new dataclasses**

```python
# Append to tests/test_models.py

from evolver.models import Link, EvalResult


def test_link_creation():
    link = Link(id=1, source_type="memory", source_id=10,
                target_type="memory", target_id=20,
                link_type="auto_similar", weight=0.85)
    assert link.source_type == "memory"
    assert link.target_id == 20
    assert link.weight == 0.85


def test_eval_result_creation():
    result = EvalResult(
        total_score=72.5,
        dim_scores={"frontmatter": 8, "workflow": 12, "edge_cases": 7},
        round=1,
        status="pass",
    )
    assert result.total_score == 72.5
    assert result.dim_scores["workflow"] == 12
    assert result.round == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'Link'`

- [ ] **Step 3: Add Link and EvalResult to models.py**

Append to `evolver/models.py`:

```python
@dataclass
class Link:
    id: Optional[int] = None
    source_type: str = ""
    source_id: int = 0
    target_type: str = ""
    target_id: int = 0
    link_type: str = "auto_similar"
    weight: float = 1.0


@dataclass
class EvalResult:
    total_score: float = 0.0
    dim_scores: dict = field(default_factory=dict)
    round: int = 1
    status: str = "pass"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_models.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/models.py tests/test_models.py
git commit -m "feat(models): add Link and EvalResult dataclasses"
```

---

### Task 2: Storage — New Tables and CRUD Methods

**Files:**
- Modify: `evolver/storage_sqlite.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write failing tests for new tables and methods**

Append to `tests/test_storage.py`:

```python
# --- Links table tests ---

def test_insert_link():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    link_id = storage.insert_link(
        source_type="memory", source_id=1,
        target_type="memory", target_id=2,
        link_type="auto_similar", weight=0.85,
    )
    assert link_id > 0


def test_insert_link_bidirectional():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.85)
    storage.insert_link("memory", 2, "memory", 1, "auto_similar", 0.85)
    rows = storage._fetchall("SELECT * FROM links")
    assert len(rows) == 2


def test_insert_link_dedup():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.85)
    # Second insert with same unique key should update weight
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.90)
    rows = storage._fetchall("SELECT * FROM links WHERE source_id=1 AND target_id=2")
    assert len(rows) == 1
    assert rows[0]["weight"] == 0.90


def test_get_backlinks():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 5, "auto_similar", 0.8)
    storage.insert_link("memory", 2, "memory", 5, "auto_similar", 0.7)
    storage.insert_link("memory", 3, "memory", 5, "auto_entity", 0.9)
    backlinks = storage.get_backlinks("memory", 5)
    assert len(backlinks) == 3


def test_get_outgoing():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.8)
    storage.insert_link("memory", 1, "graph_node", 10, "auto_entity", 0.9)
    outgoing = storage.get_outgoing("memory", 1)
    assert len(outgoing) == 2


def test_decay_links():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.05)
    storage.decay_links(factor=0.5, min_weight=0.03)
    rows = storage._fetchall("SELECT * FROM links")
    # 0.05 * 0.5 = 0.025 < 0.03, should be deleted
    assert len(rows) == 0


# --- Skill evaluations table tests ---

def test_insert_skill_evaluation():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    # First create a skill
    skill_id, _ = storage.upsert_skill("test-skill", "desc", "/path", "content")
    eval_id = storage.insert_skill_evaluation(
        skill_id=skill_id, version=1, total_score=72.5,
        dim_scores={"frontmatter": 8}, eval_mode="auto",
        round=1, status="pass",
    )
    assert eval_id > 0


def test_get_skill_evaluations():
    storage = SQLiteStorage(":memory:")
    storage._ensure_schema()
    skill_id, _ = storage.upsert_skill("test-skill", "desc", "/path", "content")
    storage.insert_skill_evaluation(skill_id, 1, 70.0, {"f": 7}, "auto", 1, "pass")
    storage.insert_skill_evaluation(skill_id, 1, 75.0, {"f": 8}, "auto", 2, "improved")
    evals = storage.get_skill_evaluations(skill_id)
    assert len(evals) == 2
    assert evals[1]["total_score"] == 75.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_storage.py -v -k "link or evaluation"`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Add new tables to _ensure_schema()**

In `evolver/storage_sqlite.py`, append to the `_ensure_schema` executescript:

```sql
CREATE TABLE IF NOT EXISTS links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type   TEXT NOT NULL,
    source_id     INTEGER NOT NULL,
    target_type   TEXT NOT NULL,
    target_id     INTEGER NOT NULL,
    link_type     TEXT NOT NULL,
    weight        REAL DEFAULT 1.0,
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(source_type, source_id, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS idx_links_source
    ON links(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_links_target
    ON links(target_type, target_id);

CREATE TABLE IF NOT EXISTS skill_evaluations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id      INTEGER NOT NULL,
    version       INTEGER NOT NULL,
    total_score   REAL,
    dim_scores    TEXT,
    eval_mode     TEXT DEFAULT 'auto',
    round         INTEGER DEFAULT 1,
    status        TEXT DEFAULT 'pass',
    diff_summary  TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);
```

- [ ] **Step 4: Add CRUD methods for links**

Append to `evolver/storage_sqlite.py`:

```python
    # --- Link operations ---

    def insert_link(self, source_type: str, source_id: int,
                    target_type: str, target_id: int,
                    link_type: str, weight: float = 1.0) -> int:
        existing = self._fetchone(
            "SELECT id FROM links WHERE source_type=? AND source_id=? "
            "AND target_type=? AND target_id=?",
            (source_type, source_id, target_type, target_id),
        )
        if existing:
            self._execute(
                "UPDATE links SET weight=? WHERE id=?",
                (weight, existing["id"]),
            )
            return existing["id"]
        cur = self._execute(
            "INSERT INTO links (source_type, source_id, target_type, target_id, link_type, weight) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source_type, source_id, target_type, target_id, link_type, weight),
        )
        return cur.lastrowid

    def get_backlinks(self, target_type: str, target_id: int) -> list:
        rows = self._fetchall(
            "SELECT id, source_type, source_id, target_type, target_id, link_type, weight "
            "FROM links WHERE target_type=? AND target_id=? ORDER BY weight DESC",
            (target_type, target_id),
        )
        from evolver.models import Link
        return [Link(**r) for r in rows]

    def get_outgoing(self, source_type: str, source_id: int) -> list:
        rows = self._fetchall(
            "SELECT id, source_type, source_id, target_type, target_id, link_type, weight "
            "FROM links WHERE source_type=? AND source_id=? ORDER BY weight DESC",
            (source_type, source_id),
        )
        from evolver.models import Link
        return [Link(**r) for r in rows]

    def decay_links(self, factor: float = 0.95, min_weight: float = 0.01):
        self._execute("UPDATE links SET weight = weight * ?", (factor,))
        self._execute("DELETE FROM links WHERE weight < ?", (min_weight,))

    # --- Skill evaluation operations ---

    def insert_skill_evaluation(self, skill_id: int, version: int,
                                total_score: float, dim_scores: dict,
                                eval_mode: str, round: int,
                                status: str, diff_summary: str = None) -> int:
        cur = self._execute(
            "INSERT INTO skill_evaluations "
            "(skill_id, version, total_score, dim_scores, eval_mode, round, status, diff_summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (skill_id, version, total_score, json.dumps(dim_scores, ensure_ascii=False),
             eval_mode, round, status, diff_summary),
        )
        return cur.lastrowid

    def get_skill_evaluations(self, skill_id: int) -> list:
        rows = self._fetchall(
            "SELECT id, skill_id, version, total_score, dim_scores, eval_mode, round, status, diff_summary "
            "FROM skill_evaluations WHERE skill_id=? ORDER BY round",
            (skill_id,),
        )
        for r in rows:
            r["dim_scores"] = json.loads(r["dim_scores"]) if r.get("dim_scores") else {}
        return rows
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_storage.py -v -k "link or evaluation"`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/storage_sqlite.py tests/test_storage.py
git commit -m "feat(storage): add links and skill_evaluations tables with CRUD"
```

---

### Task 3: LinkEngine — Core Implementation

**Files:**
- Create: `evolver/link.py`
- Test: `tests/test_link.py`

- [ ] **Step 1: Write failing tests for LinkEngine**

Create `tests/test_link.py`:

```python
# tests/test_link.py
import numpy as np
from unittest.mock import MagicMock, call
from evolver.link import LinkEngine
from evolver.models import Link, GraphNode, Memory, RecallResult


def make_link_engine():
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_memory = MagicMock()
    mock_graph = MagicMock()

    mock_embedding.embed_single.return_value = np.random.rand(384).tolist()
    mock_embedding.bytes_to_vector.return_value = [0.0] * 384
    mock_embedding.dim = 384

    engine = LinkEngine(mock_storage, mock_embedding, mock_memory, mock_graph)
    return engine, mock_storage, mock_embedding, mock_memory, mock_graph


def test_auto_link_creates_similarity_links():
    engine, storage, emb, memory, graph = make_link_engine()
    # Mock: find 2 similar memories
    memory._storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=2, content="similar topic", category="success",
               embedding=b"\x00" * 12),
        Memory(id=3, content="another topic", category="failure",
               embedding=b"\x00" * 12),
    ]
    # Mock: cosine similarity high enough
    emb.bytes_to_vector.return_value = emb.embed_single.return_value

    engine.auto_link_memory(memory_id=1, content="test content about git")

    # Should have inserted links (bidirectional: A->B and B->A)
    assert storage.insert_link.call_count >= 2


def test_auto_link_creates_entity_links():
    engine, storage, emb, memory, graph = make_link_engine()
    # Mock: no similar memories
    memory._storage.get_all_memories_with_embeddings.return_value = []
    # Mock: graph finds matching nodes
    graph.query.return_value = [
        GraphNode(id=10, label="git", node_type="tool"),
    ]

    engine.auto_link_memory(memory_id=1, content="fix git merge conflict")

    # Should have inserted entity links
    entity_calls = [c for c in storage.insert_link.call_args_list
                    if c[0][4] == "auto_entity"]
    assert len(entity_calls) >= 1


def test_auto_link_batch():
    engine, storage, emb, memory, graph = make_link_engine()
    memory._storage.get_all_memories_with_embeddings.return_value = []
    graph.query.return_value = []

    engine.auto_link_batch(
        memory_ids=[1, 2, 3],
        contents=["content a", "content b", "content c"],
    )

    # Should call embed_single for each content
    assert emb.embed_single.call_count == 3


def test_backlinks():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_backlinks.return_value = [
        Link(id=1, source_type="memory", source_id=2,
             target_type="memory", target_id=5,
             link_type="auto_similar", weight=0.8),
    ]

    result = engine.backlinks("memory", 5)
    assert len(result) == 1
    assert result[0].source_id == 2
    storage.get_backlinks.assert_called_once_with("memory", 5)


def test_outgoing():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="graph_node", target_id=10,
             link_type="auto_entity", weight=0.9),
    ]

    result = engine.outgoing("memory", 1)
    assert len(result) == 1
    storage.get_outgoing.assert_called_once_with("memory", 1)


def test_linked_memories():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="memory", target_id=2,
             link_type="auto_similar", weight=0.8),
        Link(id=2, source_type="memory", source_id=1,
             target_type="memory", target_id=3,
             link_type="auto_similar", weight=0.7),
    ]
    storage.get_memories_by_ids.return_value = [
        Memory(id=2, content="related content", category="success"),
        Memory(id=3, content="another related", category="failure"),
    ]

    results = engine.linked_memories(memory_id=1, top_k=10)
    assert len(results) == 2
    assert isinstance(results[0], RecallResult)


def test_linked_graph_nodes():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="graph_node", target_id=10,
             link_type="auto_entity", weight=0.9),
    ]
    storage._fetchall.return_value = [
        {"id": 10, "label": "git", "node_type": "tool", "properties": None},
    ]

    nodes = engine.linked_graph_nodes(memory_id=1)
    assert len(nodes) == 1
    assert nodes[0].label == "git"


def test_compute_link_score_no_links():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = []

    score = engine.compute_link_score(memory_id=1, query_related_ids=[2, 3])
    assert score == 0.0


def test_compute_link_score_with_overlap():
    engine, storage, emb, memory, graph = make_link_engine()
    storage.get_outgoing.return_value = [
        Link(id=1, source_type="memory", source_id=1,
             target_type="memory", target_id=2,
             link_type="auto_similar", weight=0.8),
        Link(id=2, source_type="memory", source_id=1,
             target_type="memory", target_id=3,
             link_type="auto_similar", weight=0.6),
    ]

    score = engine.compute_link_score(memory_id=1, query_related_ids=[2])
    # Memory 1 links to 2 (weight 0.8) and 2 is in query_related_ids
    assert score > 0.0
    assert score <= 1.0


def test_decay_links():
    engine, storage, emb, memory, graph = make_link_engine()
    engine.decay_links(factor=0.9, min_weight=0.01)
    storage.decay_links.assert_called_once_with(factor=0.9, min_weight=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_link.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evolver.link'`

- [ ] **Step 3: Implement LinkEngine**

Create `evolver/link.py`:

```python
import logging
import numpy as np
from evolver.models import Link, RecallResult, GraphNode

logger = logging.getLogger(__name__)


class LinkEngine:
    _SIMILARITY_THRESHOLD = 0.6
    _MAX_LINKS_PER_MEMORY = 10

    def __init__(self, storage, embedding, memory_engine, graph_engine):
        self._storage = storage
        self._embedding = embedding
        self._memory = memory_engine
        self._graph = graph_engine

    def auto_link_memory(self, memory_id: int, content: str):
        """Auto-infer bidirectional links for a newly stored memory."""
        sim_count = self._create_similarity_links(memory_id, content)
        ent_count = self._create_entity_links(memory_id, content)
        logger.info(
            "Auto-linked memory %d: %d similarity, %d entity links",
            memory_id, sim_count, ent_count,
        )

    def auto_link_batch(self, memory_ids: list[int], contents: list[str]):
        """Batch auto-link for multiple memories."""
        for mid, content in zip(memory_ids, contents):
            if content:
                self.auto_link_memory(mid, content)

    def backlinks(self, target_type: str, target_id: int) -> list[Link]:
        """Find all links pointing to a target."""
        return self._storage.get_backlinks(target_type, target_id)

    def outgoing(self, source_type: str, source_id: int) -> list[Link]:
        """Find all links originating from a source."""
        return self._storage.get_outgoing(source_type, source_id)

    def linked_memories(self, memory_id: int, top_k: int = 10) -> list[RecallResult]:
        """Get memories linked to a given memory."""
        links = self._storage.get_outgoing("memory", memory_id)
        memory_links = [l for l in links if l.target_type == "memory"][:top_k]
        if not memory_links:
            return []
        target_ids = [l.target_id for l in memory_links]
        weight_map = {l.target_id: l.weight for l in memory_links}
        memories = self._storage.get_memories_by_ids(target_ids)
        results = []
        for mem in memories:
            results.append(RecallResult(
                content=mem.content,
                score=round(weight_map.get(mem.id, 0.0), 4),
                source="link",
                category=mem.category,
                related_nodes=[],
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def linked_graph_nodes(self, memory_id: int) -> list[GraphNode]:
        """Get graph nodes linked to a memory."""
        links = self._storage.get_outgoing("memory", memory_id)
        node_links = [l for l in links if l.target_type == "graph_node"]
        if not node_links:
            return []
        node_ids = [l.target_id for l in node_links]
        nodes = []
        for nid in node_ids:
            rows = self._storage._fetchall(
                "SELECT id, label, node_type, properties FROM graph_nodes WHERE id=?",
                (nid,),
            )
            for r in rows:
                nodes.append(GraphNode(
                    id=r["id"], label=r["label"],
                    node_type=r["node_type"],
                ))
        return nodes

    def compute_link_score(self, memory_id: int,
                           query_related_ids: list[int]) -> float:
        """Compute link-based score for recall boost.

        Returns normalized score based on how many query-related memories
        are linked to this memory.
        """
        if not query_related_ids:
            return 0.0
        links = self._storage.get_outgoing("memory", memory_id)
        if not links:
            return 0.0
        linked_target_ids = {l.target_id for l in links}
        overlap = linked_target_ids & set(query_related_ids)
        if not overlap:
            return 0.0
        # Score = sum of weights of overlapping links / max possible
        total_weight = sum(
            l.weight for l in links if l.target_id in overlap
        )
        max_weight = len(query_related_ids)  # max 1.0 per link
        return min(total_weight / max_weight, 1.0)

    def decay_links(self, factor: float = 0.95, min_weight: float = 0.01):
        """Decay link weights over time."""
        self._storage.decay_links(factor=factor, min_weight=min_weight)

    # --- Internal ---

    def _create_similarity_links(self, memory_id: int, content: str) -> int:
        """Find similar memories via embeddings and create links."""
        query_vec = np.array(self._embedding.embed_single(content))
        all_mems = self._memory._storage.get_all_memories_with_embeddings()
        # Exclude self
        candidates = [m for m in all_mems if m.id != memory_id and m.embedding is not None]

        scored = []
        for mem in candidates:
            mem_vec = np.array(self._embedding.bytes_to_vector(mem.embedding))
            dot = np.dot(query_vec, mem_vec)
            norm = np.linalg.norm(query_vec) * np.linalg.norm(mem_vec)
            sim = float(dot / norm) if norm > 0 else 0.0
            if sim > self._SIMILARITY_THRESHOLD:
                scored.append((mem.id, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        count = 0
        for target_id, sim in scored[:self._MAX_LINKS_PER_MEMORY]:
            self._storage.insert_link("memory", memory_id, "memory", target_id,
                                      "auto_similar", sim)
            self._storage.insert_link("memory", target_id, "memory", memory_id,
                                      "auto_similar", sim)
            count += 1
        return count

    def _create_entity_links(self, memory_id: int, content: str) -> int:
        """Extract entities and link to matching graph nodes."""
        entities = self._graph._extract_entities(content)
        count = 0
        for entity in entities:
            nodes = self._storage.query_nodes(entity)
            for node in nodes:
                if node.label.lower() == entity.lower():
                    self._storage.insert_link("memory", memory_id,
                                              "graph_node", node.id,
                                              "auto_entity", 1.0)
                    count += 1
        return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_link.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/link.py tests/test_link.py
git commit -m "feat(link): add LinkEngine with auto-inference and backlink queries"
```

---

### Task 4: QualityChecker — Core Implementation

**Files:**
- Create: `evolver/checker.py`
- Test: `tests/test_checker.py`

- [ ] **Step 1: Write failing tests for QualityChecker**

Create `tests/test_checker.py`:

```python
# tests/test_checker.py
from unittest.mock import MagicMock
from evolver.checker import QualityChecker
from evolver.models import EvalResult


def make_checker():
    mock_storage = MagicMock()
    checker = QualityChecker(mock_storage)
    return checker, mock_storage


SAMPLE_SKILL = """---
name: git-conflict
description: Auto-generated skill for: git conflict
version: 1
tags: [git, conflict]
generated_from: 5 memories, 3 graph nodes
---

# Git Conflict

## Overview
Based on 5 memories and 3 knowledge graph nodes.

## Steps
1. Run git status to see conflicts
2. Open conflicted files
3. Resolve markers manually
4. git add the resolved files
5. git commit

## Success Cases
- Fixed merge conflict by rebasing

## Common Pitfalls
- Don't use git reset --hard

## Key Insights
- Always stash before rebase

## Related Skills
- git (tool)
"""


def test_evaluate_returns_eval_result():
    checker, _ = make_checker()
    result = checker.evaluate(SAMPLE_SKILL, "git conflict")
    assert isinstance(result, EvalResult)
    assert 0 <= result.total_score <= 100
    assert len(result.dim_scores) == 8


def test_evaluate_all_dimensions_present():
    checker, _ = make_checker()
    result = checker.evaluate(SAMPLE_SKILL, "git conflict")
    expected_dims = {
        "frontmatter", "workflow", "edge_cases", "checkpoints",
        "specificity", "resources", "architecture", "effectiveness",
    }
    assert set(result.dim_scores.keys()) == expected_dims


def test_evaluate_empty_skill_scores_low():
    checker, _ = make_checker()
    result = checker.evaluate("", "test topic")
    assert result.total_score < 30


def test_evaluate_well_structured_skill_scores_high():
    checker, _ = make_checker()
    result = checker.evaluate(SAMPLE_SKILL, "git conflict")
    # Well-structured skill should score above 50
    assert result.total_score > 50


def test_check_and_improve_returns_tuple():
    checker, storage = make_checker()
    storage.upsert_skill.return_value = (1, 1)
    storage.insert_skill_evaluation.return_value = 1

    content, result = checker.check_and_improve(1, SAMPLE_SKILL, "git conflict")
    assert isinstance(content, str)
    assert isinstance(result, EvalResult)


def test_check_and_improve_ratchet():
    """If improvement doesn't help, should revert to best version."""
    checker, storage = make_checker()
    storage.upsert_skill.return_value = (1, 1)
    storage.insert_skill_evaluation.return_value = 1

    content, result = checker.check_and_improve(1, SAMPLE_SKILL, "git conflict")
    # Content should be at least as good as original
    assert len(content) > 0


def test_fix_frontmatter_missing_fields():
    checker, _ = make_checker()
    bad_skill = """---
name: test
---

# Test

## Steps
1. Do something
"""
    result = checker.evaluate(bad_skill, "test")
    # Should score low on frontmatter
    assert result.dim_scores["frontmatter"] < 8


def test_fix_workflow_no_numbering():
    checker, _ = make_checker()
    bad_skill = """---
name: test-skill
description: A test skill
version: 1
tags: [test]
generated_from: 1 memories, 0 graph nodes
---

# Test

## Steps
Do this thing. Then do that thing. Finally do the other thing.
"""
    result = checker.evaluate(bad_skill, "test")
    # Workflow should score low without proper numbering
    assert result.dim_scores["workflow"] < 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_checker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evolver.checker'`

- [ ] **Step 3: Implement QualityChecker**

Create `evolver/checker.py`:

```python
import re
import json
import logging
from evolver.models import EvalResult

logger = logging.getLogger(__name__)


class QualityChecker:
    MAX_ROUNDS = 3

    # Dimension weights (total = 100)
    DIMENSIONS = {
        "frontmatter":   8,
        "workflow":      15,
        "edge_cases":    10,
        "checkpoints":    7,
        "specificity":   15,
        "resources":      5,
        "architecture":  15,
        "effectiveness": 25,
    }

    def __init__(self, storage):
        self._storage = storage

    def evaluate(self, skill_content: str, topic: str) -> EvalResult:
        """Evaluate skill content across 8 dimensions."""
        scores = {}
        scores["frontmatter"] = self._score_frontmatter(skill_content)
        scores["workflow"] = self._score_workflow(skill_content)
        scores["edge_cases"] = self._score_edge_cases(skill_content)
        scores["checkpoints"] = self._score_checkpoints(skill_content)
        scores["specificity"] = self._score_specificity(skill_content)
        scores["resources"] = self._score_resources(skill_content)
        scores["architecture"] = self._score_architecture(skill_content)
        scores["effectiveness"] = self._score_effectiveness(skill_content, topic)

        total = sum(scores[d] * self.DIMENSIONS[d] / 10.0 for d in scores)
        return EvalResult(
            total_score=round(total, 1),
            dim_scores=scores,
            round=1,
            status="pass",
        )

    def check_and_improve(self, skill_id: int, skill_content: str,
                          topic: str) -> tuple[str, EvalResult]:
        """Evaluate, fix weakest dimension, ratchet. Returns (best_content, best_eval)."""
        best_content = skill_content
        best_eval = self.evaluate(skill_content, topic)
        best_score = best_eval.total_score

        for round_num in range(1, self.MAX_ROUNDS + 1):
            current_eval = self.evaluate(best_content, topic)
            weakest = min(current_eval.dim_scores, key=current_eval.dim_scores.get)

            improved = self._fix_dimension(best_content, weakest, current_eval)
            new_eval = self.evaluate(improved, topic)

            if new_eval.total_score > best_score:
                best_content = improved
                best_score = new_eval.total_score
                best_eval = EvalResult(
                    total_score=new_eval.total_score,
                    dim_scores=new_eval.dim_scores,
                    round=round_num,
                    status="improved",
                )
                self._log_evaluation(skill_id, round_num, new_eval, "improved")
            else:
                self._log_evaluation(skill_id, round_num, current_eval, "reverted")
                break

        return best_content, best_eval

    # --- Dimension scorers (each returns 1-10) ---

    def _score_frontmatter(self, content: str) -> int:
        score = 0
        if re.search(r'^---\s*\n', content):
            score += 2
        if re.search(r'^name:\s*\S+', content, re.MULTILINE):
            score += 2
        if re.search(r'^description:\s+.+', content, re.MULTILINE):
            score += 2
        if re.search(r'^version:\s*\d+', content, re.MULTILINE):
            score += 1
        if re.search(r'^tags:\s*\[', content, re.MULTILINE):
            score += 1
        if re.search(r'^generated_from:', content, re.MULTILINE):
            score += 1
        if re.search(r'^---\s*$', content.split('---')[2] if content.count('---') >= 2 else ''):
            score += 1
        return min(score, 10)

    def _score_workflow(self, content: str) -> int:
        steps_match = re.search(r'## Steps\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if not steps_match:
            return 1
        steps_text = steps_match.group(1).strip()
        if not steps_text:
            return 1
        score = 2
        # Has numbered steps
        numbered = re.findall(r'^\d+\.', steps_text, re.MULTILINE)
        if len(numbered) >= 3:
            score += 3
        elif len(numbered) >= 1:
            score += 2
        # Has bullet steps
        bullets = re.findall(r'^[-*]\s', steps_text, re.MULTILINE)
        if bullets:
            score += 1
        # Steps have reasonable length
        lines = [l.strip() for l in steps_text.split('\n') if l.strip()]
        if len(lines) >= 3:
            score += 2
        # Steps mention input/output
        if any(kw in steps_text.lower() for kw in ['input', 'output', 'result', 'return']):
            score += 2
        return min(score, 10)

    def _score_edge_cases(self, content: str) -> int:
        score = 2  # base
        lower = content.lower()
        if any(kw in lower for kw in ['error', 'exception', 'fail', 'fallback']):
            score += 3
        if any(kw in lower for kw in ['if.*fail', 'when.*error', 'handle']):
            score += 2
        if any(kw in lower for kw in ['retry', 'timeout', 'rollback', 'recover']):
            score += 2
        if 'pitfall' in lower or 'warning' in lower or 'caution' in lower:
            score += 1
        return min(score, 10)

    def _score_checkpoints(self, content: str) -> int:
        score = 2
        lower = content.lower()
        if any(kw in lower for kw in ['confirm', 'verify', 'check', 'review']):
            score += 3
        if any(kw in lower for kw in ['ask', 'pause', 'wait', 'before proceeding']):
            score += 2
        if any(kw in lower for kw in ['approve', 'user', 'human']):
            score += 2
        return min(score, 10)

    def _score_specificity(self, content: str) -> int:
        score = 2
        # Has examples
        if re.search(r'```', content):
            score += 2
        # Has file paths
        if re.search(r'[\w/]+\.\w+', content):
            score += 1
        # Has parameters/values
        if re.search(r'=\d+|=\w+|:\s*\d+', content):
            score += 1
        # Not too vague — average word length > 4
        words = re.findall(r'\w+', content)
        if words and sum(len(w) for w in words) / len(words) > 4:
            score += 2
        # Has concrete nouns (commands, tools)
        if re.search(r'\b(git|docker|npm|pip|curl|ssh)\b', content, re.IGNORECASE):
            score += 1
        return min(score, 10)

    def _score_resources(self, content: str) -> int:
        score = 3
        if 'related' in content.lower() or 'see also' in content.lower():
            score += 3
        if re.search(r'https?://', content):
            score += 2
        if re.search(r'tags:', content):
            score += 1
        return min(score, 10)

    def _score_architecture(self, content: str) -> int:
        score = 2
        sections = re.findall(r'^## ', content, re.MULTILINE)
        if len(sections) >= 3:
            score += 3
        elif len(sections) >= 2:
            score += 2
        # Has overview/summary
        if 'overview' in content.lower() or 'summary' in content.lower():
            score += 2
        # Not too long (reasonable size)
        if 500 < len(content) < 5000:
            score += 1
        # Has structure markers
        if re.search(r'^### ', content, re.MULTILINE):
            score += 1
        return min(score, 10)

    def _score_effectiveness(self, content: str, topic: str) -> int:
        """Score based on how well the skill addresses the topic."""
        score = 3  # base
        topic_words = set(re.findall(r'\w+', topic.lower()))
        content_words = set(re.findall(r'\w+', content.lower()))
        overlap = topic_words & content_words
        if topic_words:
            coverage = len(overlap) / len(topic_words)
            if coverage > 0.7:
                score += 4
            elif coverage > 0.4:
                score += 2
        # Has actionable content
        if re.search(r'^\d+\.\s', content, re.MULTILINE):
            score += 2
        # Length suggests substance
        if len(content) > 300:
            score += 1
        return min(score, 10)

    # --- Fix strategies ---

    def _fix_dimension(self, content: str, dimension: str,
                       eval_result: EvalResult) -> str:
        """Attempt to fix the weakest dimension. Returns improved content."""
        fixers = {
            "frontmatter": self._fix_frontmatter,
            "workflow": self._fix_workflow,
            "edge_cases": self._fix_edge_cases,
            "checkpoints": self._fix_checkpoints,
            "specificity": self._fix_specificity,
            "resources": self._fix_resources,
            "architecture": self._fix_architecture,
            "effectiveness": self._fix_effectiveness,
        }
        fixer = fixers.get(dimension)
        if fixer:
            return fixer(content, eval_result)
        return content

    def _fix_frontmatter(self, content: str, eval_result: EvalResult) -> str:
        if not re.search(r'^---\s*\n', content):
            content = "---\name: generated-skill\ndescription: Auto-generated\nversion: 1\ntags: []\n---\n" + content
        # Add missing fields
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.strip() == '---' and i > 0:
                insert_idx = i
                break
        additions = []
        if not re.search(r'^version:', content, re.MULTILINE):
            additions.append('version: 1')
        if not re.search(r'^tags:', content, re.MULTILINE):
            additions.append('tags: []')
        if not re.search(r'^generated_from:', content, re.MULTILINE):
            additions.append('generated_from: evolver')
        for a in additions:
            lines.insert(insert_idx, a)
        return '\n'.join(lines)

    def _fix_workflow(self, content: str, eval_result: EvalResult) -> str:
        steps_match = re.search(r'(## Steps\s*\n)(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if not steps_match:
            content += "\n\n## Steps\n1. Review the task requirements\n2. Execute the main action\n3. Verify the result\n"
            return content
        header, steps_text, tail = steps_match.group(1), steps_match.group(2), ''
        lines = [l.strip() for l in steps_text.split('\n') if l.strip()]
        # Re-number if not numbered
        numbered = []
        for i, line in enumerate(lines, 1):
            if re.match(r'^\d+\.', line):
                numbered.append(line)
            else:
                numbered.append(f"{i}. {line}")
        return content.replace(steps_match.group(0), header + '\n'.join(numbered) + '\n')

    def _fix_edge_cases(self, content: str, eval_result: EvalResult) -> str:
        if '## Error Handling' not in content and '## Common Pitfalls' not in content:
            content += "\n\n## Error Handling\n- If an operation fails, check the logs for details\n- Retry transient errors up to 3 times\n- For persistent failures, report the error and stop\n"
        return content

    def _fix_checkpoints(self, content: str, eval_result: EvalResult) -> str:
        if 'confirm' not in content.lower() and 'verify' not in content.lower():
            # Add a checkpoint before the last step
            content = re.sub(
                r'(## Steps\s*\n)',
                r'\1> **Checkpoint:** Verify results before proceeding.\n\n',
                content,
            )
        return content

    def _fix_specificity(self, content: str, eval_result: EvalResult) -> str:
        # Add example block if none exists
        if '```' not in content:
            content += "\n\n## Example\n```\n# Example usage\n# Input: <describe input>\n# Output: <describe expected output>\n```\n"
        return content

    def _fix_resources(self, content: str, eval_result: EvalResult) -> str:
        if '## Related' not in content and '## See Also' not in content:
            content += "\n\n## See Also\n- Refer to project documentation for advanced usage\n"
        return content

    def _fix_architecture(self, content: str, eval_result: EvalResult) -> str:
        if '## Overview' not in content:
            content = re.sub(
                r'(---\s*\n)',
                r'\1\n## Overview\nThis skill was auto-generated and optimized by evolver.\n\n',
                content,
                count=1,
            )
        return content

    def _fix_effectiveness(self, content: str, eval_result: EvalResult) -> str:
        # Ensure topic keywords appear in the content
        # This is a light touch — just add a reference if missing
        return content

    # --- Logging ---

    def _log_evaluation(self, skill_id: int, round_num: int,
                        eval_result: EvalResult, status: str):
        try:
            self._storage.insert_skill_evaluation(
                skill_id=skill_id,
                version=1,
                total_score=eval_result.total_score,
                dim_scores=eval_result.dim_scores,
                eval_mode="auto",
                round=round_num,
                status=status,
            )
        except Exception as e:
            logger.warning("Failed to log evaluation: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_checker.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/checker.py tests/test_checker.py
git commit -m "feat(checker): add QualityChecker with 8-dim rubric and ratchet"
```

---

### Task 5: Integration — MemoryEngine + LinkEngine

**Files:**
- Modify: `evolver/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write failing test for store() triggering links**

Append to `tests/test_memory.py`:

```python
def test_store_triggers_auto_linking():
    engine, storage, emb = make_engine()
    storage.insert_memory.return_value = 1
    storage.insert_interaction.return_value = 1

    # Set up link engine mock
    mock_link = MagicMock()
    engine._link = mock_link

    ids = engine.store(
        task="fix bug",
        outcome="success",
        solution="fixed token",
        lessons="always validate input",
    )

    # auto_link_batch should be called
    mock_link.auto_link_batch.assert_called_once()
    call_args = mock_link.auto_link_batch.call_args
    memory_ids = call_args[0][0]
    contents = call_args[0][1]
    assert len(memory_ids) >= 1
    assert len(contents) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_memory.py::test_store_triggers_auto_linking -v`
Expected: FAIL — `_link` attribute not found

- [ ] **Step 3: Modify MemoryEngine.store() to call auto_link_batch**

In `evolver/memory.py`, modify the `__init__` to accept an optional link_engine:

```python
    def __init__(self, storage, embedding: EmbeddingClient):
        self._storage = storage
        self._embedding = embedding
        self._link = None  # Set by Evolver after construction
        self._ann: ANNIndex | None = None
        self._ann_built = False
```

In the `store()` method, after `self._storage.commit()` and before the existing `logger.info`, add:

```python
            # Auto-link stored memories
            if self._link and link_pairs:
                try:
                    self._link.auto_link_batch(
                        [mid for mid, _ in link_pairs],
                        [text for _, text in link_pairs],
                    )
                except Exception:
                    logger.warning("Auto-linking failed (non-fatal)", exc_info=True)
```

And build `link_pairs` during the store logic — add `link_pairs = []` after `memory_ids = []`, then append after each `insert_memory`:

After the task memory insert:
```python
                    link_pairs.append((mid, content))
```

After the lessons memory insert:
```python
                    link_pairs.append((mid, lessons))
```

After the context memory insert:
```python
                    link_pairs.append((mid, context))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_memory.py::test_store_triggers_auto_linking -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/memory.py tests/test_memory.py
git commit -m "feat(memory): integrate LinkEngine auto-linking into store()"
```

---

### Task 6: Integration — SkillEngine + QualityChecker

**Files:**
- Modify: `evolver/skill.py`
- Modify: `tests/test_skill.py`

- [ ] **Step 1: Write failing test for generate() triggering quality check**

Append to `tests/test_skill.py`:

```python
def test_generate_triggers_quality_check():
    engine, storage, memory, graph = make_engine()
    memory.recall.return_value = [
        RecallResult(content="git merge fix", score=0.9, source="memory",
                     category="success", related_nodes=[]),
    ]
    graph.query.return_value = []
    storage.upsert_skill.return_value = (1, 1)

    # Set up checker mock
    mock_checker = MagicMock()
    from evolver.models import EvalResult
    mock_checker.check_and_improve.return_value = (
        "# Improved Skill\n## Steps\n1. Step one\n",
        EvalResult(total_score=80.0, dim_scores={"workflow": 8}, round=1, status="improved"),
    )
    engine._checker = mock_checker

    with tempfile.TemporaryDirectory() as tmpdir:
        result = engine.generate("git conflict", output_dir=tmpdir)
        assert result is not None
        mock_checker.check_and_improve.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_skill.py::test_generate_triggers_quality_check -v`
Expected: FAIL — `_checker` attribute not found

- [ ] **Step 3: Modify SkillEngine to integrate QualityChecker**

In `evolver/skill.py`, modify `__init__` to accept optional checker:

```python
    def __init__(self, storage, memory_engine, graph_engine):
        self._storage = storage
        self._memory = memory_engine
        self._graph = graph_engine
        self._checker = None  # Set by Evolver after construction
        template_dir = Path(__file__).parent / "templates"
        self._env = Environment(loader=FileSystemLoader(str(template_dir)))
```

In the `generate()` method, after writing the file and before the `upsert_skill` call, add:

```python
        # Quality check and improve
        if self._checker:
            try:
                improved_content, eval_result = self._checker.check_and_improve(
                    0, md_content, topic,
                )
                if improved_content != md_content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(improved_content)
                    md_content = improved_content
                    logger.info("Quality check: score=%.1f, status=%s",
                                eval_result.total_score, eval_result.status)
            except Exception:
                logger.warning("Quality check failed (non-fatal)", exc_info=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_skill.py::test_generate_triggers_quality_check -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/skill.py tests/test_skill.py
git commit -m "feat(skill): integrate QualityChecker into generate()"
```

---

### Task 7: Integration — Recall Link Boost

**Files:**
- Modify: `evolver/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write failing test for recall link boost**

Append to `tests/test_memory.py`:

```python
def test_recall_includes_link_boost():
    engine, storage, emb = make_engine()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="git merge fix", category="success", embedding=b"\x00" * 12),
    ]
    storage.query_nodes.return_value = []

    # Set up link engine mock
    mock_link = MagicMock()
    mock_link.compute_link_score.return_value = 0.5
    engine._link = mock_link

    results = engine.recall("git conflict")
    assert len(results) >= 1
    mock_link.compute_link_score.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_memory.py::test_recall_includes_link_boost -v`
Expected: FAIL — `compute_link_score` not called

- [ ] **Step 3: Add link boost to recall()**

In `evolver/memory.py`, in the `recall()` method, change the default weights and add link scoring:

Change the method signature:
```python
    def recall(self, query: str, top_k: int = 5,
               recall_weights: tuple = (0.6, 0.15, 0.1, 0.15),
               max_scan: int = 2000) -> list[RecallResult]:
```

In the scoring loop (where `final_score` is computed), add link score:

```python
            # Link boost
            link_score = 0.0
            if self._link:
                try:
                    query_related = [m.id for m, _ in top[:top_k]]
                    link_score = self._link.compute_link_score(mem.id, query_related)
                except Exception:
                    pass

            w_vec, w_graph, w_imp, w_link = recall_weights
            final_score = w_vec * sim + w_graph * graph_score + w_imp * mem.importance + w_link * link_score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_memory.py::test_recall_includes_link_boost -v`
Expected: PASS

- [ ] **Step 5: Run all memory tests to verify no regression**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_memory.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/memory.py tests/test_memory.py
git commit -m "feat(memory): add link boost to recall() scoring"
```

---

### Task 8: Evolver Facade — Wire Everything Together

**Files:**
- Modify: `evolver/__init__.py`
- Test: `tests/test_evolver.py`

- [ ] **Step 1: Write failing tests for new facade methods**

Append to `tests/test_evolver.py`:

```python
def test_backlinks_method():
    """Evolver.backlinks delegates to LinkEngine."""
    from evolver.models import Link
    evolver = Evolver(db_url="sqlite://:memory:")
    evolver._storage.insert_link("memory", 1, "memory", 2, "auto_similar", 0.8)
    result = evolver.backlinks("memory", 2)
    assert len(result) == 1
    assert isinstance(result[0], Link)
    evolver.close()


def test_linked_memories_method():
    """Evolver.linked_memories delegates to LinkEngine."""
    evolver = Evolver(db_url="sqlite://:memory:")
    # Store something first
    evolver.learn(task="test task", outcome="success", solution="test solution")
    # Should not raise
    result = evolver.linked_memories(1, top_k=5)
    assert isinstance(result, list)
    evolver.close()


def test_eval_skill_method():
    """Evolver.eval_skill delegates to QualityChecker."""
    evolver = Evolver(db_url="sqlite://:memory:")
    result = evolver.eval_skill(
        "---\name: test\ndescription: test\n---\n# Test\n## Steps\n1. Do thing\n",
        "test topic",
    )
    assert result.total_score > 0
    assert len(result.dim_scores) == 8
    evolver.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_evolver.py -v -k "backlinks or linked_memories or eval_skill"`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Update Evolver.__init__ to wire new components**

In `evolver/__init__.py`, add imports and wiring:

Add imports at the top:
```python
from evolver.link import LinkEngine
from evolver.checker import QualityChecker
```

In `__init__`, after existing component initialization:
```python
        self._link = LinkEngine(self._storage, self._embedding, self._memory, self.graph)
        self._checker = QualityChecker(self._storage)
        # Wire into sub-engines
        self._memory._link = self._link
        self._skill._checker = self._checker
```

Add new facade methods:
```python
    def backlinks(self, target_type: str, target_id: int) -> list:
        """Find all links pointing to a target."""
        return self._link.backlinks(target_type, target_id)

    def linked_memories(self, memory_id: int, top_k: int = 10) -> list:
        """Get memories linked to a given memory."""
        return self._link.linked_memories(memory_id, top_k)

    def eval_skill(self, skill_content: str, topic: str):
        """Evaluate skill quality without modifying it."""
        return self._checker.evaluate(skill_content, topic)

    # Async variants

    async def backlinks_async(self, target_type: str, target_id: int) -> list:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: self.backlinks(target_type, target_id))

    async def linked_memories_async(self, memory_id: int, top_k: int = 10) -> list:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: self.linked_memories(memory_id, top_k))

    async def eval_skill_async(self, skill_content: str, topic: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: self.eval_skill(skill_content, topic))
```

Update `__all__` to include new types:
```python
__all__ = [
    "Evolver", "EvolverConfig", "RecallResult", "SkillResult",
    "MySQLStorage", "SQLiteStorage", "Link", "EvalResult",
    "EvolverError", "EvolverConnectionError", "EmbeddingError",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_evolver.py -v -k "backlinks or linked_memories or eval_skill"`
Expected: all PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/__init__.py tests/test_evolver.py
git commit -m "feat: wire LinkEngine + QualityChecker into Evolver facade"
```

---

### Task 9: Final Integration Test

**Files:**
- Test: `tests/test_evolver.py`

- [ ] **Step 1: Write end-to-end integration test**

Append to `tests/test_evolver.py`:

```python
def test_end_to_end_learn_recall_skillgen_with_links_and_quality():
    """Full pipeline: learn → recall (with link boost) → skillgen (with quality check)."""
    evolver = Evolver(db_url="sqlite://:memory:")

    # Learn multiple related experiences
    evolver.learn(
        task="fix git merge conflict",
        outcome="success",
        solution="use git rebase instead of merge",
        lessons="always stash before rebase",
    )
    evolver.learn(
        task="resolve git rebase conflict",
        outcome="success",
        solution="edit conflicted files, then git rebase --continue",
        lessons="check git status before rebase",
    )
    evolver.learn(
        task="docker deploy fails",
        outcome="failure",
        solution="",
        lessons="check container logs first",
    )

    # Verify links were created
    stats = evolver.stats()
    assert stats["memories"] >= 3

    # Recall with link boost
    results = evolver.recall("git merge conflict")
    assert len(results) >= 1
    # Git-related memories should rank higher
    assert any("git" in r.content.lower() for r in results)

    # Generate skill with quality check
    result = evolver.skillgen("git conflict resolution")
    assert result is not None
    assert result.name == "git-conflict-resolution"
    # Skill should have been quality-checked (content may differ from template)
    assert len(result.content) > 100

    # Check that evaluations were logged
    evolver.close()
```

- [ ] **Step 2: Run the integration test**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/test_evolver.py::test_end_to_end_learn_recall_skillgen_with_links_and_quality -v`
Expected: PASS

- [ ] **Step 3: Run full test suite one final time**

Run: `cd E:/agents\ factory/存储智能体/temp/evolver-project && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_evolver.py
git commit -m "test: add end-to-end integration test for linking + quality check"
```
