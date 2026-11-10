# Third Brain Integration Design

**Date:** 2026-05-22
**Status:** Approved
**Scope:** Borrow 5 core patterns from Third Brain v5 Skills into Evolver

---

## Summary

Integrate Third Brain's best patterns into Evolver in 3 phases:
1. **Skills** — Closure Protocol + verify-before-claim (pure prompt layer, zero code changes)
2. **Knowledge Lifecycle** — seed→growing→evergreen→stale lifecycle on Memory model
3. **4-Layer Architecture** — Refactor compiler.assemble() to output Active/QuickAccess/Durable/Facts layers

## What We're NOT Doing

- Token cost tracking (deferred to future version)
- Full rewrite of the compiler pipeline (incremental refactor only)
- Multi-harness portability (Evolver stays Python-only)

---

## Phase 1: Evolver Skills

### 1.1 `evolver-closure` Skill

**File:** `evolver/skills/closure-protocol/SKILL.md`

**Purpose:** Ensure every significant agent session feeds knowledge back into Evolver. No value leakage.

**Trigger conditions:**
- Agent completed ≥3 tool calls in the session
- User says "save session" / "close session" / "extract knowledge"
- After completing a substantive task (code fix, research, design)

**3-Step Closure Cycle:**

```
Step 1: FORMAT
  - Extract key outputs from the session
  - Structure into evolver.learn() parameters:
    task: session objective
    outcome: success/failure
    solution: core solution approach
    lessons: pitfalls and insights

Step 2: LINK
  - Call evolver.recall() with task summary
  - If related memories found → note connections in lessons
  - If conflicts detected → mark conflict, do NOT overwrite old memories
  - Check for knowledge gaps (concepts mentioned but not stored)

Step 3: LOG
  - Call evolver.learn() with structured parameters
  - Output stored memory IDs
  - Trigger auto_distill if configured
```

**Anti-patterns:**
- Extracting from shallow sessions (<3 tool calls)
- Extracting too vaguely ("learned many things") or too granularly (every tool call)
- Storing without checking for duplicates first
- Overwriting existing memories without conflict annotation

**Quality gates:**
- [ ] Session depth check passed (≥3 tool calls or user-initiated)
- [ ] No duplicate memories created (recall() check before learn())
- [ ] Conflicts annotated, not silently overwritten
- [ ] Memory IDs confirmed via output

### 1.2 `evolver-verify` Skill

**File:** `evolver/skills/verify-before-claim/SKILL.md`

**Purpose:** No completion claims without fresh verification evidence. Prevents agent from saying "done" without proof.

**Trigger conditions:**
- Before saying "done", "fixed", "complete", "passing", "working"
- Before committing or creating a PR
- When the user asks "is it working?"
- Any time the agent feels the urge to say "it should work"

**Gate Function:**

```
1. IDENTIFY — What command proves this claim?
2. RUN — Execute the FULL command (fresh, complete)
3. READ — Full output, check exit code, count failures
4. VERIFY — Does output confirm the claim?
   - If NO → State actual status with evidence
   - If YES → State claim WITH evidence
5. ONLY THEN — Make the claim
```

**Evolver-specific verification:**

| Action | Verification required |
|--------|----------------------|
| skillgen complete | `evolver evaluate -f <file>` score ≥60 |
| distill complete | `evolver stats` shows updated fact count |
| learn complete | `evolver recall <query>` returns the stored memory |
| forget complete | `evolver stats` shows decreased memory count |

**Rationalization prevention:**

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Different context" | Spirit over letter |

**Quality gates:**
- [ ] Verification command identified and run
- [ ] Full output shown (exit code, failure count)
- [ ] Claim only made WITH evidence
- [ ] No "should", "probably", "I think" on completion status

---

## Phase 2: Knowledge Lifecycle

### 2.1 Memory Model Extension

Add `lifecycle` field to `Memory` dataclass:

```python
@dataclass
class Memory:
    # ... existing fields ...
    lifecycle: str = "seed"  # seed | growing | evergreen | stale
```

### 2.2 Lifecycle Stages

| Stage | Meaning | Entry condition | Recall impact |
|-------|---------|-----------------|---------------|
| `seed` | Just stored, unverified | Default for new learn() | Normal weight |
| `growing` | Recalled ≥2 times, or linked | access_count ≥2 or backlinks ≥1 | Weight ×1.1 |
| `evergreen` | Long-term stable, high importance | importance ≥0.8 and age ≥30 days | Weight ×1.3 |
| `stale` | Long-unused, possibly outdated | 90 days unrecalled and importance <0.5 | Weight ×0.5 |

### 2.3 Automatic Lifecycle Migration

New method on `MemoryEngine`:

```python
def update_lifecycle(self) -> dict:
    """Scan all memories, auto-migrate lifecycle stages.
    
    Rules:
    - seed → growing: access_count >= 2 or backlinks >= 1
    - growing → evergreen: importance >= 0.8 and age >= 30 days
    - any → stale: 90 days unrecalled and importance < 0.5
    - stale → seed: reactivated on recall (access_count resets)
    
    Returns: {transitioned: int, by_type: {from_to: count}}
    """
```

Called automatically during:
- `distill_all()` — as part of the distillation pipeline (batch, full scan)
- `recall()` — lightweight check: only reactivates stale memories that match the query (sync, inline before returning results)

### 2.4 DB Migration

**SQLite:**
```sql
ALTER TABLE memories ADD COLUMN lifecycle TEXT DEFAULT 'seed';
CREATE INDEX idx_lifecycle ON memories(lifecycle);
```

**MySQL:**
```sql
ALTER TABLE memories ADD COLUMN lifecycle VARCHAR(20) DEFAULT 'seed';
CREATE INDEX idx_lifecycle ON memories(lifecycle);
```

Migration runs automatically on `Evolver.__init__()` — detect column existence before altering.

### 2.5 Impact on Existing Features

- **recall()** — reranker applies lifecycle weight multiplier
- **distill()** — stale memories deprioritized, evergreen prioritized
- **stats()** — output lifecycle distribution: `{seed: 45, growing: 12, evergreen: 3, stale: 8}`
- **forget()** — new `--stale` CLI option: `evolver forget --stale` cleans all stale memories
- **interference_decay()** — stale memories get extra decay

---

## Phase 3: 4-Layer Architecture (Incremental Refactor)

### 3.1 Layer Mapping

| Third Brain Layer | Evolver Equivalent | Data Source |
|-------------------|-------------------|-------------|
| Active Execution Truth | Current session undistilled memories | `get_memories_in_range(days=0)` |
| Quick Access Memory | today + week distillation | Existing today.md + week.md |
| Durable Wiki | longterm distillation + generated skills | Existing longterm.md + skill files |
| Vector Store (Facts) | Atomic facts database | Existing facts table |

### 3.2 `assemble()` Refactor

Current: concatenates today + week + longterm → 3 sections
New: 4-section output with Active and Facts layers

```python
def assemble(self) -> str:
    """4-layer knowledge architecture assembly."""
    parts = []
    
    # Layer 1: Active — recent undistilled memories
    recent = self.storage.get_memories_in_range(days=0)
    if recent:
        active_text = self._memories_to_text(recent[-10:])  # max 10
        parts.append(f"[Active — recent session]\n{active_text}")
    
    # Layer 2: Quick Access — today + week
    today = self._read_file("today.md")
    week = self._read_file("week.md")
    if today or week:
        qa = "\n\n".join(filter(None, [
            f"[Today]\n{today}" if today else None,
            f"[This week]\n{week}" if week else None,
        ]))
        parts.append(f"[Quick Access — distilled recent]\n{qa}")
    
    # Layer 3: Durable — longterm profile
    longterm = self._read_file("longterm.md")
    if longterm:
        parts.append(f"[Durable — long-term profile]\n{longterm}")
    
    # Layer 4: Facts — top atomic facts
    facts = self.storage.get_all_facts(limit=20)
    if facts:
        fact_lines = [f"- {f.fact}" for f in facts]
        parts.append(f"[Facts — atomic knowledge]\n" + "\n".join(fact_lines))
    
    result = "\n\n---\n\n".join(parts)
    self._write_file("memory_context.md", result)
    return result
```

### 3.3 Backward Compatibility

- `compile_today/week/longterm/facts` — unchanged, continue independent operation
- `distill_all()` — unchanged
- `assemble()` — output format changes from 3 to 4 sections
- `memory_context()` — calls assemble(), auto-gets 4-layer format
- `get_prompt_injection()` — unchanged, wraps assemble() output

### 3.4 Size Control

- Active layer: max 10 most recent memories
- Quick Access: existing token limits (today=2000, week=2000)
- Durable: existing token limit (longterm=1500)
- Facts: max 20 most recent facts
- Total assembly: estimated ≤6000 tokens (within reasonable prompt budget)

### 3.5 Optional Format Parameter

For users who need the old format:

```python
def assemble(self, format: str = "4layer") -> str:
    """Assemble memory context.
    
    Args:
        format: "4layer" (default) or "legacy" (3-section)
    """
```

---

## Implementation Order

1. Phase 1 (Skills) — zero risk, immediate value
   - Write `evolver/skills/closure-protocol/SKILL.md`
   - Write `evolver/skills/verify-before-claim/SKILL.md`
2. Phase 2 (Lifecycle) — moderate risk, additive change
   - Add `lifecycle` field to Memory model
   - Add DB migration in `__init__`
   - Implement `update_lifecycle()`
   - Update recall reranker with lifecycle weights
   - Update CLI with `--stale` forget option
3. Phase 3 (4-Layer) — low risk, refactor assemble()
   - Rewrite `assemble()` with 4-layer output
   - Add `format` parameter for backward compat
   - Update `get_prompt_injection()` if needed

## Files Changed

| Phase | File | Change |
|-------|------|--------|
| 1 | `evolver/skills/closure-protocol/SKILL.md` | New file |
| 1 | `evolver/skills/verify-before-claim/SKILL.md` | New file |
| 2 | `evolver/models.py` | Add `lifecycle` field |
| 2 | `evolver/memory.py` | Add `update_lifecycle()` |
| 2 | `evolver/storage_base.py` | Add lifecycle column migration |
| 2 | `evolver/storage_sqlite.py` | SQLite migration |
| 2 | `evolver/storage.py` | MySQL migration |
| 2 | `evolver/cli.py` | Add `--stale` to forget command |
| 3 | `evolver/compiler.py` | Refactor `assemble()` |

## Testing

- Phase 1: Manual verification (invoke skills, check behavior)
- Phase 2: Unit tests for lifecycle migration, integration test for recall weights
- Phase 3: Unit test for assemble() output format, backward compat test
