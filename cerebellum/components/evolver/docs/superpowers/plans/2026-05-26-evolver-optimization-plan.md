# Evolver v2.3.0 全面优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize evolver for performance, architecture, and production readiness across 3 phases.

**Architecture:** Incremental refactoring in 3 phases: (1) Performance - lazy imports, batch embedding, deduplicate utilities; (2) Architecture - split memory.py, clean storage_base.py, fix encapsulation; (3) Production - LLM retry, connection pool, schema migration.

**Tech Stack:** Python 3.11+, Click CLI, SQLite/MySQL, FlagEmbedding, numpy, Jinja2

---

## Phase 1: 性能优化

### Task 1.1: 提取公共工具函数到 utils.py

**Files:**
- Modify: `evolver/utils.py`
- Test: `tests/test_utils.py`

- [ ] **Step 1: Write the failing test for cosine_similarity**

```python
# tests/test_utils.py — add to existing file
def test_cosine_similarity_identical():
    from evolver.utils import cosine_similarity
    vec = [1.0, 0.0, 0.0]
    assert cosine_similarity(vec, vec) == pytest.approx(1.0)

def test_cosine_similarity_orthogonal():
    from evolver.utils import cosine_similarity
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(0.0)

def test_cosine_similarity_zero_vector():
    from evolver.utils import cosine_similarity
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

def test_extract_json_from_llm_direct():
    from evolver.utils import extract_json_from_llm
    result = extract_json_from_llm('{"key": "value"}')
    assert result == {"key": "value"}

def test_extract_json_from_llm_code_fence():
    from evolver.utils import extract_json_from_llm
    text = 'Here is the result:\n```json\n{"key": "value"}\n```'
    result = extract_json_from_llm(text)
    assert result == {"key": "value"}

def test_extract_json_from_llm_no_json():
    from evolver.utils import extract_json_from_llm
    result = extract_json_from_llm("No JSON here")
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_utils.py::test_cosine_similarity_identical -v`
Expected: FAIL with "cannot import name 'cosine_similarity'"

- [ ] **Step 3: Implement cosine_similarity and extract_json_from_llm**

```python
# evolver/utils.py — append to existing file
import json
import re

import numpy as np


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def extract_json_from_llm(text):
    """Extract JSON from LLM output text.

    Tries: direct parse, ```json code fence, regex extraction.
    Returns parsed dict/list or None.
    """
    if not text:
        return None
    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    # 2. Try ```json code fence
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass
    # 3. Try regex extraction of { ... } or [ ... ]
    for pattern in [r'\{[^{}]*\}', r'\[[^\[\]]*\]']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                continue
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_utils.py::test_cosine_similarity_identical tests/test_utils.py::test_cosine_similarity_orthogonal tests/test_utils.py::test_cosine_similarity_zero_vector tests/test_utils.py::test_extract_json_from_llm_direct tests/test_utils.py::test_extract_json_from_llm_code_fence tests/test_utils.py::test_extract_json_from_llm_no_json -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/utils.py tests/test_utils.py
git commit -m "feat(utils): add cosine_similarity and extract_json_from_llm"
```

---

### Task 1.2: 替换 memory.py 中的余弦相似度

**Files:**
- Modify: `evolver/memory.py:892-897`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py — add test
def test_memory_cosine_similarity_uses_utils():
    """Verify memory module uses shared cosine_similarity."""
    from evolver.memory import MemoryEngine
    import inspect
    source = inspect.getsource(MemoryEngine)
    # Should NOT contain local _cosine_similarity definition
    assert "_cosine_similarity" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py::test_memory_cosine_similarity_uses_utils -v`
Expected: FAIL (because _cosine_similarity still exists in memory.py)

- [ ] **Step 3: Replace _cosine_similarity in memory.py**

In `evolver/memory.py`:
1. Remove the `_cosine_similarity` method (lines ~892-897)
2. Add import at top: `from evolver.utils import cosine_similarity`
3. Replace all calls to `self._cosine_similarity(a, b)` with `cosine_similarity(a, b)`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory.py::test_memory_cosine_similarity_uses_utils -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/memory.py tests/test_memory.py
git commit -m "refactor(memory): use shared cosine_similarity from utils"
```

---

### Task 1.3: 替换 dedup.py 中的余弦距离

**Files:**
- Modify: `evolver/dedup.py:25-31`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dedup.py — add test
def test_dedup_uses_shared_cosine():
    """Verify dedup module uses shared cosine_similarity."""
    from evolver.dedup import Deduplicator
    import inspect
    source = inspect.getsource(Deduplicator)
    assert "_cosine_distance" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dedup.py::test_dedup_uses_shared_cosine -v`
Expected: FAIL

- [ ] **Step 3: Replace _cosine_distance in dedup.py**

In `evolver/dedup.py`:
1. Remove the `_cosine_distance` method
2. Add import: `from evolver.utils import cosine_similarity`
3. Replace calls: `1.0 - cosine_similarity(a, b)` (distance = 1 - similarity)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dedup.py::test_dedup_uses_shared_cosine -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/dedup.py tests/test_dedup.py
git commit -m "refactor(dedup): use shared cosine_similarity from utils"
```

---

### Task 1.4: 替换 skill_library.py 中的余弦相似度和tokenize

**Files:**
- Modify: `evolver/skill_library.py:113-149`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_skill_docs.py — add test
def test_skill_library_uses_shared_utils():
    """Verify skill_library uses shared utilities."""
    from evolver.skill_library import SkillLibrary
    import inspect
    source = inspect.getsource(SkillLibrary)
    assert "_cosine_similarity" not in source
    assert "_extract_keywords" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_docs.py::test_skill_library_uses_shared_utils -v`
Expected: FAIL

- [ ] **Step 3: Replace methods in skill_library.py**

In `evolver/skill_library.py`:
1. Remove `_cosine_similarity` method (lines ~137-149)
2. Remove `_extract_keywords` method (lines ~113-135)
3. Add imports: `from evolver.utils import cosine_similarity, tokenize`
4. Replace similarity calls with `cosine_similarity(a, b)`
5. Replace keyword extraction with `tokenize(text)`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill_docs.py::test_skill_library_uses_shared_utils -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/skill_library.py tests/test_skill_docs.py
git commit -m "refactor(skill_library): use shared cosine_similarity and tokenize"
```

---

### Task 1.5: 替换 graph.py/extraction.py/compiler.py 中的 JSON 提取

**Files:**
- Modify: `evolver/graph.py:183-206`
- Modify: `evolver/extraction.py:155-179`
- Modify: `evolver/compiler.py:258-279`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph.py — add test
def test_graph_uses_shared_json_extraction():
    """Verify graph module uses shared extract_json_from_llm."""
    from evolver.graph import GraphEngine
    import inspect
    source = inspect.getsource(GraphEngine)
    assert "_parse_json" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph.py::test_graph_uses_shared_json_extraction -v`
Expected: FAIL

- [ ] **Step 3: Replace _parse_json in graph.py**

In `evolver/graph.py`:
1. Remove `_parse_json` method
2. Add import: `from evolver.utils import extract_json_from_llm`
3. Replace calls with `extract_json_from_llm(text)`

- [ ] **Step 4: Replace _parse_json in extraction.py**

In `evolver/extraction.py`:
1. Remove `_parse_json` method
2. Add import: `from evolver.utils import extract_json_from_llm`
3. Replace calls with `extract_json_from_llm(text)`

- [ ] **Step 5: Replace _parse_facts in compiler.py**

In `evolver/compiler.py`:
1. Remove `_parse_facts` method
2. Add import: `from evolver.utils import extract_json_from_llm`
3. Replace calls with `extract_json_from_llm(text)`

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_graph.py::test_graph_uses_shared_json_extraction -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add evolver/graph.py evolver/extraction.py evolver/compiler.py tests/test_graph.py
git commit -m "refactor: use shared extract_json_from_llm from utils"
```

---

### Task 1.6: 批量 embedding 优化

**Files:**
- Modify: `evolver/memory.py:140-160`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py — add test
def test_store_uses_batch_embedding():
    """Verify store() uses embed_batch instead of embed_single."""
    from evolver.memory import MemoryEngine
    import inspect
    source = inspect.getsource(MemoryEngine.store)
    # Should use embed_batch, not multiple embed_single calls
    assert "embed_batch" in source
    assert source.count("embed_single") <= 1  # At most 1 fallback
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py::test_store_uses_batch_embedding -v`
Expected: FAIL

- [ ] **Step 3: Modify store() to use batch embedding**

In `evolver/memory.py`, modify the `store()` method:

```python
def store(self, task, outcome, context="", solution="", lessons="",
          source="cli", tags=None):
    """Store a learning interaction with batch embedding."""
    # ... existing validation ...

    # Batch embed all non-empty texts
    texts_to_embed = []
    text_map = {}  # index -> field name
    if task:
        text_map[len(texts_to_embed)] = "task"
        texts_to_embed.append(task)
    if lessons:
        text_map[len(texts_to_embed)] = "lessons"
        texts_to_embed.append(lessons)
    if context:
        text_map[len(texts_to_embed)] = "context"
        texts_to_embed.append(context)
    if solution:
        text_map[len(texts_to_embed)] = "solution"
        texts_to_embed.append(solution)

    # Single batch embedding call
    if texts_to_embed:
        vecs = self._embedding.embed_batch(texts_to_embed)
    else:
        vecs = []

    # Map vectors back to fields
    task_vec = vecs[text_map.inv["task"]] if "task" in text_map.values() else None
    # ... similar for lessons_vec, context_vec, solution_vec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory.py::test_store_uses_batch_embedding -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/memory.py tests/test_memory.py
git commit -m "perf(memory): batch embedding in store() for 3x speedup"
```

---

### Task 1.7: 延迟导入 __init__.py

**Files:**
- Modify: `evolver/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evolver.py — add test
def test_lazy_import_does_not_load_optional_deps():
    """Verify import evolver does not load optional dependencies."""
    import subprocess
    result = subprocess.run(
        ["python", "-c", "import time; t=time.time(); import evolver; print(time.time()-t)"],
        capture_output=True, text=True, timeout=10
    )
    # Should import in <1 second (no heavy deps loaded)
    assert float(result.stdout.strip()) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evolver.py::test_lazy_import_does_not_load_optional_deps -v`
Expected: FAIL (import takes >1s)

- [ ] **Step 3: Implement lazy imports in __init__.py**

In `evolver/__init__.py`:
1. Remove all top-level imports of sub-modules except `Evolver` class
2. Keep only: `__version__`, `__all__`, and the `Evolver` class definition
3. Add lazy loading at the end of the file:

```python
# evolver/__init__.py — at end of file
_LAZY_IMPORTS = {
    "EvolverConfig": "evolver.config",
    "RerankerConfig": "evolver.config",
    "LifecycleRule": "evolver.config",
    "DEFAULT_LIFECYCLE_RULES": "evolver.config",
    "RecallResult": "evolver.models",
    "SkillResult": "evolver.models",
    "Link": "evolver.models",
    "EvalResult": "evolver.models",
    "Fact": "evolver.models",
    "Memory": "evolver.models",
    "BaseStorage": "evolver.storage_base",
    "SQLiteStorage": "evolver.storage_sqlite",
    "LLMClient": "evolver.llm_client",
    "MemoryCompiler": "evolver.compiler",
    "EvolverError": "evolver.exceptions",
    "EvolverConnectionError": "evolver.exceptions",
    "EmbeddingError": "evolver.exceptions",
}

def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module = __import__(_LAZY_IMPORTS[name], fromlist=[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return list(globals().keys()) + list(_LAZY_IMPORTS.keys())
```

4. Move `MySQLStorage` import to be lazy (it requires pymysql)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evolver.py::test_lazy_import_does_not_load_optional_deps -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/__init__.py tests/test_evolver.py
git commit -m "perf: lazy imports in __init__.py for faster startup"
```

---

### Task 1.8: Phase 1 验证

**Files:**
- None (verification only)

- [ ] **Step 1: Verify import time improvement**

Run: `python -c "import time; t=time.time(); import evolver; print(f'Import time: {time.time()-t:.2f}s')"`
Expected: <1 second

- [ ] **Step 2: Verify batch embedding works**

Run: `pytest tests/test_memory.py -v -k "store"`
Expected: All store tests PASS

- [ ] **Step 3: Verify no duplicate implementations**

Run: `grep -r "_cosine_similarity\|_cosine_distance" evolver/ --include="*.py" | grep -v utils.py`
Expected: No matches

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit Phase 1 completion**

```bash
git add -A
git commit -m "chore: Phase 1 performance optimization complete"
```

---

## Phase 2: 架构重构

### Task 2.1: 拆分 memory.py 为 memory.py + retrieval.py

**Files:**
- Create: `evolver/retrieval.py`
- Modify: `evolver/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py — add test
def test_retrieval_module_exists():
    """Verify retrieval module exists and has expected functions."""
    from evolver import retrieval
    assert hasattr(retrieval, 'recall')
    assert hasattr(retrieval, 'recall_light')
    assert hasattr(retrieval, 'recall_deep')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py::test_retrieval_module_exists -v`
Expected: FAIL with "No module named 'evolver.retrieval'"

- [ ] **Step 3: Create retrieval.py with extracted functions**

Create `evolver/retrieval.py` with the following methods extracted from memory.py:
- `recall()` — main recall entry point
- `recall_light()` — L2 lightweight recall
- `recall_deep()` — L3 deep recall
- `_recall_semantic()` — semantic vector recall
- `_recall_graph()` — knowledge graph recall
- `_recall_links()` — link boost recall
- `_recall_bm25()` — BM25 keyword recall
- `_rrf_fusion()` — reciprocal rank fusion
- `_weighted_fusion()` — weighted fusion
- `_rerank()` — second-stage reranking
- `_bm25_score()` — BM25 scoring

```python
# evolver/retrieval.py
"""Multi-signal retrieval pipeline for evolver memories."""

from __future__ import annotations
import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evolver.memory import MemoryEngine

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """Handles multi-signal memory retrieval."""

    def __init__(self, memory_engine: MemoryEngine):
        self._engine = memory_engine

    def recall(self, query, top_k=5, recall_weights=(0.6, 0.15, 0.1, 0.15),
               method="rrf"):
        """Main recall entry point with 4-channel fusion."""
        # ... extracted from memory.py ...
        pass

    def recall_light(self, query, category=None, top_k=10):
        """L2 lightweight recall with truncated snippets."""
        # ... extracted from memory.py ...
        pass

    def recall_deep(self, query, top_k=5):
        """L3 deep recall with all fusion signals."""
        # ... extracted from memory.py ...
        pass

    # ... private methods ...
```

- [ ] **Step 4: Update memory.py to use RetrievalEngine**

In `evolver/memory.py`:
1. Remove all recall-related methods
2. Add import: `from evolver.retrieval import RetrievalEngine`
3. In `MemoryEngine.__init__`, create: `self._retrieval = RetrievalEngine(self)`
4. Delegate recall calls: `def recall(self, *args, **kwargs): return self._retrieval.recall(*args, **kwargs)`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_memory.py::test_retrieval_module_exists -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add evolver/retrieval.py evolver/memory.py tests/test_memory.py
git commit -m "refactor: split memory.py into memory.py + retrieval.py"
```

---

### Task 2.2: 清理 storage_base.py SELECT 重复

**Files:**
- Modify: `evolver/storage_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage.py — add test
def test_storage_uses_memory_columns_constant():
    """Verify storage_base uses _MEMORY_COLUMNS constant."""
    from evolver.storage_base import BaseStorage
    import inspect
    source = inspect.getsource(BaseStorage)
    assert "_MEMORY_COLUMNS" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_storage_uses_memory_columns_constant -v`
Expected: FAIL

- [ ] **Step 3: Add _MEMORY_COLUMNS constant and replace SELECT statements**

In `evolver/storage_base.py`:
1. Add constant at top of class:
```python
_MEMORY_COLUMNS = (
    "id, content, category, tags, embedding, source, importance, "
    "access_count, content_hash, lifecycle, created_at, updated_at"
)
```
2. Replace all 8 occurrences of the SELECT column list with `f"SELECT {_MEMORY_COLUMNS} FROM memories"`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py::test_storage_uses_memory_columns_constant -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/storage_base.py tests/test_storage.py
git commit -m "refactor(storage): deduplicate SELECT columns with _MEMORY_COLUMNS"
```

---

### Task 2.3: 修复 LinkEngine 封装

**Files:**
- Modify: `evolver/memory.py`
- Modify: `evolver/link.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_link.py — add test
def test_link_engine_uses_public_search():
    """Verify LinkEngine uses memory.search_similar, not _ann directly."""
    from evolver.link import LinkEngine
    import inspect
    source = inspect.getsource(LinkEngine)
    assert "_ann" not in source
    assert "search_similar" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_link.py::test_link_engine_uses_public_search -v`
Expected: FAIL

- [ ] **Step 3: Add search_similar to MemoryEngine**

In `evolver/memory.py`:
```python
def search_similar(self, query_vec, top_k=10, threshold=0.0):
    """Public similarity search interface."""
    if not self._ann_built:
        self.build_index()
    return self._ann.search(query_vec, top_k, threshold)
```

- [ ] **Step 4: Update LinkEngine to use search_similar**

In `evolver/link.py`:
Replace: `similar = self._memory._ann.search(vec, 20, 0.0)`
With: `similar = self._memory.search_similar(vec, top_k=20)`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_link.py::test_link_engine_uses_public_search -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/memory.py evolver/link.py tests/test_link.py
git commit -m "refactor: add search_similar() public API, fix LinkEngine encapsulation"
```

---

### Task 2.4: 修复 learn_extracted() 事务安全

**Files:**
- Modify: `evolver/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evolver.py — add test
def test_learn_extracted_uses_memory_store():
    """Verify learn_extracted uses MemoryEngine.store for transaction safety."""
    from evolver import Evolver
    import inspect
    source = inspect.getsource(Evolver.learn_extracted)
    # Should call self._memory.store, not self._storage.insert_memory directly
    assert "self._memory.store" in source
    assert "self._storage.insert_memory" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evolver.py::test_learn_extracted_uses_memory_store -v`
Expected: FAIL

- [ ] **Step 3: Refactor learn_extracted to use MemoryEngine.store**

In `evolver/__init__.py`, modify `learn_extracted()`:
```python
def learn_extracted(self, text, source="extract"):
    """Learn by extracting atomic facts via LLM."""
    import re
    facts = self._extractor.extract(text)
    if not facts:
        return []

    existing_hashes = self._storage.get_all_content_hashes()
    results = []

    for fact in facts:
        fact_text = fact.get("text", "")
        if not fact_text or len(fact_text) < 5:
            continue

        normalized = re.sub(r'\s+', ' ', fact_text.strip().lower())
        fact_hash = hashlib.md5(normalized.encode()).hexdigest()

        if fact_hash in existing_hashes:
            results.append({"action": "skip", "fact": fact_text[:50]})
            continue

        # Use MemoryEngine.store for transaction safety
        tags = fact.get("tags", [])
        ids = self._memory.store(
            task=fact_text,
            outcome="extracted",
            source=source,
            tags=tags,
        )
        existing_hashes.add(fact_hash)
        results.append({"action": "add", "fact": fact_text[:50], "id": ids[0] if ids else None})

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evolver.py::test_learn_extracted_uses_memory_store -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/__init__.py tests/test_evolver.py
git commit -m "fix: learn_extracted uses MemoryEngine.store for transaction safety"
```

---

### Task 2.5: Phase 2 验证

**Files:**
- None (verification only)

- [ ] **Step 1: Verify memory.py line count**

Run: `wc -l evolver/memory.py`
Expected: <500 lines

- [ ] **Step 2: Verify retrieval.py exists**

Run: `wc -l evolver/retrieval.py`
Expected: >0 lines

- [ ] **Step 3: Verify no private attribute access**

Run: `grep -r "\._ann\b" evolver/link.py`
Expected: No matches

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit Phase 2 completion**

```bash
git add -A
git commit -m "chore: Phase 2 architecture refactoring complete"
```

---

## Phase 3: 生产就绪

### Task 3.1: 添加 LLM 重试机制

**Files:**
- Modify: `evolver/llm_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_client.py — add test
def test_retry_decorator_retries_on_429():
    """Verify retry decorator retries on 429 errors."""
    from evolver.llm_client import retry
    from unittest.mock import MagicMock

    call_count = 0

    @retry(max_retries=2, backoff=0.01, retry_on=(429,))
    def mock_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            error = Exception("rate limited")
            error.code = 429
            raise error
        return "success"

    result = mock_func()
    assert result == "success"
    assert call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py::test_retry_decorator_retries_on_429 -v`
Expected: FAIL with "cannot import name 'retry'"

- [ ] **Step 3: Implement retry decorator**

In `evolver/llm_client.py`:
```python
import time
from functools import wraps


def retry(max_retries=3, backoff=1.0, retry_on=(429, 503)):
    """Decorator for retrying failed function calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    error_code = getattr(e, 'code', None)
                    if error_code in retry_on:
                        wait = backoff * (2 ** attempt)
                        logger.warning(
                            "Retry %d/%d after %.1fs (code=%s)",
                            attempt + 1, max_retries, wait, error_code
                        )
                        time.sleep(wait)
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator
```

- [ ] **Step 4: Apply @retry to LLM calling methods**

Apply `@retry(max_retries=3, backoff=1.0, retry_on=(429, 503))` to:
- `_call_openai()`
- `_call_anthropic()`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_llm_client.py::test_retry_decorator_retries_on_429 -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add evolver/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): add retry decorator with exponential backoff"
```

---

### Task 3.2: 改进 MySQL 连接池

**Files:**
- Modify: `evolver/storage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage.py — add test
def test_mysql_connection_expiry():
    """Verify MySQL connections expire after MAX_CONNECTION_AGE."""
    from evolver.storage import Connection
    import time
    conn = Connection(None, time.time() - 7200)  # 2 hours ago
    assert conn.is_expired is True
    conn = Connection(None, time.time())  # just created
    assert conn.is_expired is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_mysql_connection_expiry -v`
Expected: FAIL with "cannot import name 'Connection'"

- [ ] **Step 3: Add Connection class and pool improvements**

In `evolver/storage.py`:
```python
import time

MAX_CONNECTION_AGE = 3600  # 1 hour


class Connection:
    """Wrapper for database connections with lifecycle tracking."""

    def __init__(self, conn, created_at=None):
        self.conn = conn
        self.created_at = created_at or time.time()

    @property
    def is_expired(self):
        return time.time() - self.created_at > MAX_CONNECTION_AGE


class MySQLStorage(BaseStorage):
    def __init__(self, url):
        # ... existing init ...
        self._total_created = 0
        self._active_count = 0

    def _get_connection(self):
        with self._lock:
            while not self._pool.empty():
                conn = self._pool.get_nowait()
                if conn.is_expired:
                    self._close_connection(conn)
                    continue
                self._active_count += 1
                return conn
            self._total_created += 1
            self._active_count += 1
            return self._create_connection()

    def _return_connection(self, conn):
        with self._lock:
            self._active_count -= 1
            if not conn.is_expired:
                self._pool.put_nowait(conn)
            else:
                self._close_connection(conn)

    def stats(self):
        return {
            "pool_size": self._pool.qsize(),
            "active": self._active_count,
            "total_created": self._total_created,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py::test_mysql_connection_expiry -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/storage.py tests/test_storage.py
git commit -m "feat(storage): add connection lifecycle management to MySQL pool"
```

---

### Task 3.3: 添加 Schema 版本跟踪

**Files:**
- Modify: `evolver/storage_sqlite.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage.py — add test
def test_sqlite_schema_version_tracking():
    """Verify SQLite storage tracks schema version."""
    from evolver.storage_sqlite import SQLiteStorage
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    try:
        storage = SQLiteStorage(db_path)
        version = storage._get_schema_version()
        assert isinstance(version, int)
        storage.close()
    finally:
        os.unlink(db_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_sqlite_schema_version_tracking -v`
Expected: FAIL with "no attribute '_get_schema_version'"

- [ ] **Step 3: Add schema version tracking**

In `evolver/storage_sqlite.py`:
```python
SCHEMA_VERSION = 2  # Increment when schema changes


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path):
        # ... existing init ...
        self._ensure_schema()
        self._migrate_schema()

    def _get_schema_version(self):
        """Get current schema version from metadata table."""
        try:
            result = self._fetchone(
                "SELECT version FROM schema_version WHERE id = 1"
            )
            return result[0] if result else 1
        except Exception:
            return 1

    def _set_schema_version(self, version):
        """Set schema version in metadata table."""
        self._execute(
            "INSERT OR REPLACE INTO schema_version (id, version) VALUES (1, ?)",
            (version,)
        )

    def _migrate_schema(self):
        """Run pending schema migrations."""
        current = self._get_schema_version()
        if current >= SCHEMA_VERSION:
            return

        # Create schema_version table if not exists
        self._execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL
            )
        """)

        migrations = [
            # version 1 -> 2: Add confidence column (example)
            # "ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 1.0",
        ]

        for i, sql in enumerate(migrations[current - 1:], start=current):
            try:
                self._execute(sql)
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    raise StorageError(f"Migration {i} failed: {e}")
            self._set_schema_version(i + 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py::test_sqlite_schema_version_tracking -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/storage_sqlite.py tests/test_storage.py
git commit -m "feat(storage): add schema version tracking for safe migrations"
```

---

### Task 3.4: 改进错误处理

**Files:**
- Modify: `evolver/__init__.py`
- Modify: `evolver/memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evolver.py — add test
def test_auto_distill_narrow_exception():
    """Verify auto_distill uses narrow exception handling."""
    from evolver import Evolver
    import inspect
    source = inspect.getsource(Evolver._auto_distill)
    # Should not have bare "except Exception:" that swallows everything
    assert "except Exception:" not in source
    assert "except (OSError" in source or "except ValueError" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evolver.py::test_auto_distill_narrow_exception -v`
Expected: FAIL

- [ ] **Step 3: Narrow exception handling in auto_distill**

In `evolver/__init__.py`, modify `_auto_distill()`:
```python
def _auto_distill(self):
    """Trigger background distillation if last run is stale."""
    if self._distill_pending:
        return
    hours = self.config.auto_distill_hours
    if hours <= 0:
        return
    try:
        last = self._storage.get_last_distill_run("today")
        if last:
            from datetime import datetime, timezone
            created = last.get("created_at", "")
            if created:
                try:
                    last_dt = datetime.fromisoformat(str(created))
                except ValueError:
                    return
                if last_dt.tzinfo is not None:
                    last_dt = last_dt.astimezone(timezone.utc).replace(tzinfo=None)
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if (now - last_dt).total_seconds() < hours * 3600:
                    return
        logger.info("Auto-distill triggered (last run stale or missing)")
        self._distill_pending = True
        self._distill_future = self._executor.submit(self._distill_safe)
    except (OSError, ValueError) as e:
        logger.warning("Auto-distill check failed: %s", e)
    except Exception:
        logger.exception("Unexpected error in auto-distill")
        raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evolver.py::test_auto_distill_narrow_exception -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evolver/__init__.py tests/test_evolver.py
git commit -m "fix: narrow exception handling in auto_distill"
```

---

### Task 3.5: Phase 3 验证

**Files:**
- None (verification only)

- [ ] **Step 1: Verify retry decorator exists**

Run: `grep -n "def retry" evolver/llm_client.py`
Expected: Line number found

- [ ] **Step 2: Verify Connection class exists**

Run: `grep -n "class Connection" evolver/storage.py`
Expected: Line number found

- [ ] **Step 3: Verify schema version tracking**

Run: `grep -n "_get_schema_version" evolver/storage_sqlite.py`
Expected: Line number found

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit Phase 3 completion**

```bash
git add -A
git commit -m "chore: Phase 3 production readiness complete"
```

---

## Final Verification

- [ ] **Run complete test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Verify no regressions**

Run: `pytest tests/ -x` (stop on first failure)
Expected: No failures

- [ ] **Check code quality**

Run: `ruff check evolver/`
Expected: No errors

- [ ] **Final commit**

```bash
git add -A
git commit -m "chore: evolver v2.3.0 optimization complete"
```
