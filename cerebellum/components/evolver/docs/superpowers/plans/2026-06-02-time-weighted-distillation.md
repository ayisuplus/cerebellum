# Time-Weighted Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic time-weighted ordering to memory distillation so old memories fade while important evergreen memories resist decay.

**Architecture:** Keep `MemoryCompiler` as the only implementation target. Add pure helper methods for weight calculation and weighted sorting, then route `today`, `week`, `facts`, and active context input through those helpers. No database schema or public API changes.

**Tech Stack:** Python, pytest, existing `Memory` dataclass, existing `MemoryCompiler` and `tests/test_compiler.py`.

---

## File Structure

- Modify: `evolver/compiler.py`
  - Add constants for half-life and lifecycle multipliers.
  - Add pure helpers `_memory_age_days()`, `_distill_weight()`, and `_sort_memories_for_distill()`.
  - Use weighted ordering in `compile_today()`, `compile_week()`, `compile_facts()`, and `assemble()` Active layer.
  - Adjust `compile_longterm()` input labels so previous long-term profile is lower-authority than current week.
- Modify: `tests/test_compiler.py`
  - Add tests for time decay, lifecycle/importance anti-decay, fallback behavior, weighted LLM input order, facts input order, and cache preservation.

## Task 1: Add Distillation Weight Helpers

**Files:**
- Modify: `tests/test_compiler.py`
- Modify: `evolver/compiler.py`

- [ ] **Step 1: Write failing tests for weight calculation**

Add these imports near the top of `tests/test_compiler.py`:

```python
from datetime import datetime, timedelta, timezone
```

Add these tests after `test_fingerprint_deterministic()`:

```python
def test_distill_weight_decays_with_age():
    compiler, _, _ = make_compiler()
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    newer = Memory(
        content="new",
        category="test",
        importance=0.5,
        lifecycle="seed",
        created_at=now.isoformat(),
    )
    older = Memory(
        content="old",
        category="test",
        importance=0.5,
        lifecycle="seed",
        created_at=(now - timedelta(days=7)).isoformat(),
    )

    assert compiler._distill_weight(newer, now=now) > compiler._distill_weight(older, now=now)
    assert compiler._distill_weight(older, now=now) == 0.5


def test_distill_weight_evergreen_importance_resists_decay():
    compiler, _, _ = make_compiler()
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    evergreen_old = Memory(
        content="evergreen",
        category="test",
        importance=1.0,
        lifecycle="evergreen",
        created_at=(now - timedelta(days=7)).isoformat(),
    )
    stale_new = Memory(
        content="stale",
        category="test",
        importance=0.1,
        lifecycle="stale",
        created_at=now.isoformat(),
    )

    assert compiler._distill_weight(evergreen_old, now=now) > compiler._distill_weight(stale_new, now=now)


def test_distill_weight_fallbacks_for_missing_fields():
    compiler, _, _ = make_compiler()
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    memory = Memory(
        content="fallback",
        category="test",
        importance=None,
        lifecycle="unknown",
        created_at="not-a-date",
    )

    assert compiler._distill_weight(memory, now=now) == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_compiler.py::test_distill_weight_decays_with_age tests/test_compiler.py::test_distill_weight_evergreen_importance_resists_decay tests/test_compiler.py::test_distill_weight_fallbacks_for_missing_fields -v
```

Expected: FAIL because `MemoryCompiler` has no `_distill_weight` method.

- [ ] **Step 3: Add minimal helper implementation**

Modify imports and constants in `evolver/compiler.py`:

```python
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional
```

Add below `TOKEN_LIMITS`:

```python
DISTILL_HALF_LIFE_DAYS = 7

LIFECYCLE_DISTILL_MULTIPLIERS = {
    "seed": 1.00,
    "growing": 1.15,
    "evergreen": 1.60,
    "stale": 0.25,
}
```

Add these methods before `_memories_to_text()`:

```python
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
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run:

```bash
python -m pytest tests/test_compiler.py::test_distill_weight_decays_with_age tests/test_compiler.py::test_distill_weight_evergreen_importance_resists_decay tests/test_compiler.py::test_distill_weight_fallbacks_for_missing_fields -v
```

Expected: PASS, 3 tests passed.

- [ ] **Step 5: Commit Task 1**

```bash
git add evolver/compiler.py tests/test_compiler.py
git commit -m "feat: add distillation memory weighting"
```

## Task 2: Apply Weighted Ordering To Distillation Inputs

**Files:**
- Modify: `tests/test_compiler.py`
- Modify: `evolver/compiler.py`

- [ ] **Step 1: Write failing tests for weighted input order**

Add these tests after `test_compile_week()`:

```python
def test_compile_week_sends_memories_in_weighted_order(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    now = datetime.now(timezone.utc)
    storage.get_memories_in_range.return_value = [
        Memory(
            content="stale new low value",
            category="test",
            importance=0.1,
            lifecycle="stale",
            created_at=now.isoformat(),
        ),
        Memory(
            content="evergreen older high value",
            category="test",
            importance=1.0,
            lifecycle="evergreen",
            created_at=(now - timedelta(days=7)).isoformat(),
        ),
    ]
    storage.get_last_distill_run.return_value = None

    compiler.compile_week(days=7)

    input_text = llm.compress.call_args[0][0]
    assert input_text.index("evergreen older high value") < input_text.index("stale new low value")


def test_compile_facts_sends_memories_in_weighted_order(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    now = datetime.now(timezone.utc)
    storage.get_memories_in_range.return_value = [
        Memory(
            content="low weight fact source",
            category="test",
            importance=0.1,
            lifecycle="stale",
            created_at=now.isoformat(),
        ),
        Memory(
            content="high weight fact source",
            category="test",
            importance=1.0,
            lifecycle="evergreen",
            created_at=(now - timedelta(days=7)).isoformat(),
        ),
    ]
    storage.get_last_distill_run.return_value = None
    llm.compress.return_value = "[]"

    compiler.compile_facts(days=7)

    input_text = llm.compress.call_args[0][0]
    assert input_text.index("high weight fact source") < input_text.index("low weight fact source")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_compiler.py::test_compile_week_sends_memories_in_weighted_order tests/test_compiler.py::test_compile_facts_sends_memories_in_weighted_order -v
```

Expected: FAIL because current compiler preserves storage order.

- [ ] **Step 3: Add weighted sorting helper and apply it**

Add this method after `_distill_weight()` in `evolver/compiler.py`:

```python
    def _sort_memories_for_distill(self, memories: list) -> list:
        """Return memories ordered by descending distillation weight."""
        now = datetime.now(timezone.utc)
        return sorted(memories, key=lambda m: self._distill_weight(m, now=now), reverse=True)
```

Modify `compile_today()`, `compile_week()`, and `compile_facts()` so each sorts before serializing:

```python
        memories = self._sort_memories_for_distill(memories)
        text = self._memories_to_text(memories)
```

The resulting shape in each method should be:

```python
        memories = self.storage.get_memories_in_range(days=days)
        if not memories:
            return ""
        memories = self._sort_memories_for_distill(memories)
        text = self._memories_to_text(memories)
```

For `compile_facts()`, preserve the existing empty return list:

```python
        memories = self.storage.get_memories_in_range(days=days)
        logger.debug("Found %d memories for facts extraction", len(memories))
        if not memories:
            return []
        memories = self._sort_memories_for_distill(memories)
        text = self._memories_to_text(memories)
```

- [ ] **Step 4: Run weighted-order tests to verify they pass**

Run:

```bash
python -m pytest tests/test_compiler.py::test_compile_week_sends_memories_in_weighted_order tests/test_compiler.py::test_compile_facts_sends_memories_in_weighted_order -v
```

Expected: PASS, 2 tests passed.

- [ ] **Step 5: Run compiler tests for regression check**

Run:

```bash
python -m pytest tests/test_compiler.py -v
```

Expected: PASS for all tests in `tests/test_compiler.py`.

- [ ] **Step 6: Commit Task 2**

```bash
git add evolver/compiler.py tests/test_compiler.py
git commit -m "feat: apply weighted order to distillation inputs"
```

## Task 3: Make Long-Term And Active Context Respect Weighting Semantics

**Files:**
- Modify: `tests/test_compiler.py`
- Modify: `evolver/compiler.py`

- [ ] **Step 1: Write failing tests for long-term labels and active ordering**

Add these tests after `test_compile_longterm_reads_files()`:

```python
def test_compile_longterm_marks_previous_profile_lower_authority(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    with open(os.path.join(d, "week.md"), "w") as f:
        f.write("new weekly pattern")
    with open(os.path.join(d, "longterm.md"), "w") as f:
        f.write("old profile")
    storage.get_last_distill_run.return_value = None

    compiler.compile_longterm()

    input_text = llm.compress.call_args[0][0]
    assert "[Lower-authority previous long-term profile]" in input_text
    assert "[Higher-authority current weekly patterns]" in input_text
    assert input_text.index("Higher-authority") < input_text.index("Lower-authority")


def test_assemble_active_layer_uses_weighted_order(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, _ = make_compiler(tmp_path=d)
    now = datetime.now(timezone.utc)
    storage.get_memories_in_range.return_value = [
        Memory(
            content="low active",
            category="test",
            importance=0.1,
            lifecycle="stale",
            created_at=now.isoformat(),
        ),
        Memory(
            content="high active",
            category="test",
            importance=1.0,
            lifecycle="evergreen",
            created_at=(now - timedelta(days=7)).isoformat(),
        ),
    ]
    storage.get_all_facts.return_value = []

    result = compiler.assemble()

    assert result.index("high active") < result.index("low active")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_compiler.py::test_compile_longterm_marks_previous_profile_lower_authority tests/test_compiler.py::test_assemble_active_layer_uses_weighted_order -v
```

Expected: FAIL because labels and active ordering are not implemented yet.

- [ ] **Step 3: Update long-term combined input labels**

Replace `compile_longterm()` combined text in `evolver/compiler.py`:

```python
        combined = (
            f"[Higher-authority current weekly patterns]\n{week}\n\n"
            f"[Lower-authority previous long-term profile]\n{prev}"
        ).strip()
```

- [ ] **Step 4: Apply weighted ordering to Active layer**

Replace the Active layer block in `assemble()` with:

```python
        try:
            recent = self.storage.get_memories_in_range(days=1)
            if recent:
                recent = self._sort_memories_for_distill(recent)
                active_text = self._memories_to_text(recent[:10])
                parts.append(f"[Active — recent session]\n{active_text}")
        except Exception:
            logger.debug("Active layer unavailable", exc_info=True)
```

This intentionally changes `days=0` to `days=1` because `days=0` can mean `created_at >= now`, which often returns no active memories.

- [ ] **Step 5: Run Task 3 tests to verify they pass**

Run:

```bash
python -m pytest tests/test_compiler.py::test_compile_longterm_marks_previous_profile_lower_authority tests/test_compiler.py::test_assemble_active_layer_uses_weighted_order -v
```

Expected: PASS, 2 tests passed.

- [ ] **Step 6: Run full relevant test suite**

Run:

```bash
python -m pytest tests/test_compiler.py tests/test_evolver.py::test_wake_up_returns_layered_context -v
```

Expected: PASS for compiler tests and wake-up regression test.

- [ ] **Step 7: Commit Task 3**

```bash
git add evolver/compiler.py tests/test_compiler.py
git commit -m "feat: weight active and long-term distillation context"
```

## Task 4: Final Verification

**Files:**
- Verify only; no code changes expected.

- [ ] **Step 1: Run full compiler tests**

Run:

```bash
python -m pytest tests/test_compiler.py -v
```

Expected: PASS for all compiler tests.

- [ ] **Step 2: Run broader memory-related tests**

Run:

```bash
python -m pytest tests/test_compiler.py tests/test_stack.py tests/test_evolver.py -v
```

Expected: PASS. If unrelated failures appear from existing dirty worktree changes, capture exact failures and do not hide them.

- [ ] **Step 3: Inspect final diff**

Run:

```bash
git diff -- evolver/compiler.py tests/test_compiler.py
```

Expected: Diff only contains weighted distillation helper/tests and planned call-site changes.

- [ ] **Step 4: Commit final verification note only if files changed**

If no files changed since Task 3 commit, do not create an empty commit. If a small fix was needed during verification, commit it:

```bash
git add evolver/compiler.py tests/test_compiler.py
git commit -m "fix: stabilize weighted distillation tests"
```

## Self-Review

- Spec coverage: Tasks cover helper, weighted ordering, lifecycle and importance anti-decay, no DB migration, public API unchanged, and tests.
- Placeholder scan: No unfinished placeholder instructions.
- Type consistency: Plan uses existing `Memory.created_at`, `Memory.importance`, `Memory.lifecycle`, and `MemoryCompiler` private-helper style.
