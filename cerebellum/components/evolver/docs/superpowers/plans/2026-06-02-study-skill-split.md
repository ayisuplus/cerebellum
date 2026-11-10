# Study And Skill Channel Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `evolver-learn`/`evolver-summary` with `evolver-study`/`evolver-skill` as active agent skills, enforce four-channel boundaries via tests.

**Architecture:** TDD on `tests/test_skill_docs.py` first (contract tests change names and tier assertions), then create `evolver-study` and `evolver-skill` SKILL.md, delete old ones. CLI commands unchanged.

**Tech Stack:** Python, pytest, Markdown SKILL.md frontmatter.

---

## File Structure

- Delete: `.claude/skills/evolver-learn/SKILL.md`
- Delete: `.claude/skills/evolver-summary/SKILL.md`
- Create: `.claude/skills/evolver-study/SKILL.md`
- Create: `.claude/skills/evolver-skill/SKILL.md`
- Modify: `tests/test_skill_docs.py`
- Keep: `.claude/skills/evolver-store/SKILL.md` (unchanged)
- Keep: `.claude/skills/evolver-query/SKILL.md` (unchanged)

## Task 1: Update Contract Tests To New Channel Names

**Files:**
- Modify: `tests/test_skill_docs.py`

- [ ] **Step 1: Write failing tests for new skill names**

Replace the entire `tests/test_skill_docs.py` with:

```python
"""Contract tests for project-level agent skills."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _frontmatter_keys(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    keys = []
    for line in lines[1:end]:
        if ":" in line:
            keys.append(line.split(":", 1)[0])
    return keys


def _skill_text(name: str) -> str:
    return (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def _frontmatter_description(name: str) -> str:
    lines = _skill_text(name).splitlines()
    end = lines.index("---", 1)
    for line in lines[1:end]:
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"{name} has no description frontmatter")


ACTIVE_SKILLS = ["evolver-study", "evolver-skill", "evolver-store", "evolver-query"]
OLD_SKILLS = ["evolver-learn", "evolver-summary", "evolver-memory", "evolver-skillcraft"]


def test_agent_facing_evolver_skills_are_four_storage_channels():
    skill_dir = ROOT / ".claude" / "skills"

    for name in ACTIVE_SKILLS:
        assert (skill_dir / name / "SKILL.md").exists()

    for name in OLD_SKILLS:
        assert not (skill_dir / name / "SKILL.md").exists()

    assert not (skill_dir / "evolver-engine.md").exists()


def test_agent_facing_evolver_skills_use_minimal_frontmatter():
    for name in ACTIVE_SKILLS:
        keys = _frontmatter_keys(ROOT / ".claude" / "skills" / name / "SKILL.md")

        assert keys == ["name", "description"]


def test_project_skill_descriptions_are_trigger_focused_and_compact():
    for name in ACTIVE_SKILLS:
        description = _frontmatter_description(name)

        assert description.startswith("Use when")
        assert len(description) <= 500
        assert "This is the" not in description
        assert "Do not under-trigger" not in description


def test_four_skills_keep_experience_and_data_tiers_separate():
    study = _skill_text("evolver-study")
    skill = _skill_text("evolver-skill")
    store = _skill_text("evolver-store")
    query = _skill_text("evolver-query")

    assert "SQLite experience tier" in study
    assert "SQLite experience tier" in skill
    assert "MySQL data tier" in store
    assert "MySQL data tier" in query
    assert "dead data" in store
    assert "verbatim" in query


def test_study_skill_documents_time_weighted_distillation():
    study = _skill_text("evolver-study")

    assert "time-weighted" in study
    assert "evergreen" in study
    assert "importance" in study
    assert "old memories become quieter" in study


def test_skill_skill_documents_quality_gate():
    skill = _skill_text("evolver-skill")

    assert "skillgen" in skill
    assert "evaluate" in skill
    assert "quality" in skill.lower()


def test_study_owns_recall_and_distill():
    study = _skill_text("evolver-study")

    assert "recall" in study
    assert "distill" in study
    assert "facts" in study


def test_skill_does_not_own_recall():
    skill = _skill_text("evolver-skill")

    lower = skill.lower()
    assert "recall" not in lower.split("##")[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_docs.py -v
```

Expected: FAIL because `evolver-study` and `evolver-skill` directories do not exist yet.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_skill_docs.py
git commit -m "test: add study/skill channel contract tests"
```

## Task 2: Create Evolver Study Skill

**Files:**
- Create: `.claude/skills/evolver-study/SKILL.md`

- [ ] **Step 1: Write evolver-study SKILL.md**

```markdown
---
name: evolver-study
description: Use when an agent needs to learn from interactions, recall stored experiences, inspect facts, distill time-weighted memory context, or manage the SQLite experience tier lifecycle; trigger on /evolver-study, learn this, recall, distill memory, memory context, 记住这个经验, or when the agent needs semantic living memory.
---

# Evolver Study — Experience Lifecycle (SQLite)

Study is the complete experience lifecycle in Evolver's **SQLite experience tier**. It owns learning, recall, facts, time-weighted distillation, memory context, and targeted forgetting. Experiences are living memory: embedded, recalled semantically, and distilled over time.

Distillation is time-weighted: old memories become quieter; `evergreen` lifecycle and high `importance` memories resist decay.

## When to use vs. other skills

| Situation | Skill |
|---|---|
| Learn from interaction, store reusable lesson | **evolver-study** |
| Recall experiences by meaning | **evolver-study** |
| Distill recent memory into digest files | **evolver-study** |
| Generate/evaluate/repair a skill document from stored experiences | evolver-skill |
| Archive raw logs, records, payloads, image references (MySQL) | evolver-store |
| Query archived raw data by keyword or id (MySQL) | evolver-query |

## Storage Map

Default project database:

```bash
sqlite:///E:/projects/evolver-project/evolver.db
```

| Operation | Primary storage | File output |
|---|---|---|
| `learn` | database `memories`, `interactions`, `event_log`, derived graph rows | none |
| `add-fact` | database `facts` | none |
| `distill` | database `distill_runs`, sometimes `facts` | `memory/today.md`, `memory/week.md`, `memory/longterm.md`, `memory/memory_context.md` |
| `forget` | deletes database memory rows by id/filter | none |

## Steps

### Learn — store a reusable lesson

```bash
evolver --fallback learn --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --task "task description" \
  --outcome success \
  --solution "what worked" \
  --lessons "reusable takeaway"
```

### Recall — search stored experiences

```bash
evolver --fallback recall --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --query "search terms" --top-k 5
```

Use `recall-light` for fast snippet lookup:

```bash
evolver --fallback recall-light --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --query "search terms" --top-k 10
```

### Facts — list or search atomic facts

```bash
evolver --fallback facts --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --query "search terms"
```

### Distill — time-weighted memory compression

```bash
evolver --fallback distill --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --level all --days 7
```

Levels: `today`, `week`, `longterm`, `facts`, `all`.

### Forget — remove targeted memories

```bash
evolver --fallback forget --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --id <memory_id>
```

Inspect matching memories first before deleting.

## Checkpoints

- Write operations print a storage receipt with database path and affected tables.
- `distill` is time-weighted: old memories fade; evergreen and high-importance resist decay.
- After `learn`, optionally run `distill` to consolidate.
- Do not store secrets or tokens in lesson text.

## Error Handling

- If embeddings fail, retry with `--fallback`.
- If recall returns nothing, try broader keywords or `facts`.
- If distillation file is missing, run `distill` then check `memory/` directory.

## Related

- `evolver-skill` — generate reusable skill documents from stored experiences.
- `evolver-store` / `evolver-query` — MySQL dead-data archive (separate from living memory).
```

- [ ] **Step 2: Run tests to check study-related assertions pass**

Run:

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_docs.py -v
```

Expected: `test_agent_facing_evolver_skills_are_four_storage_channels` still FAILS because `evolver-skill` missing, but study-related checks should pass.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/evolver-study/SKILL.md
git commit -m "feat: add evolver-study skill"
```

## Task 3: Create Evolver Skill Skill

**Files:**
- Create: `.claude/skills/evolver-skill/SKILL.md`

- [ ] **Step 1: Write evolver-skill SKILL.md**

```markdown
---
name: evolver-skill
description: Use when an agent needs to generate, evaluate, or repair reusable skill documents from stored Evolver experiences; trigger on /evolver-skill, generate a skill, evaluate this skill, 提炼成skill, or when accumulated experience should become an operational workflow document.
---

# Evolver Skill — Skill Generation And Evaluation

Turn stored experiences from Evolver's **SQLite experience tier** into reusable operational skill documents. This skill owns `skillgen`, `evaluate`, and generated skill quality control.

## When to use vs. other skills

| Situation | Skill |
|---|---|
| Generate a reusable skill from accumulated experience | **evolver-skill** |
| Evaluate or repair an existing generated skill | **evolver-skill** |
| Learn from interaction, recall, distill memory | evolver-study |
| Archive raw data (MySQL) | evolver-store |
| Query archived raw data (MySQL) | evolver-query |

## Storage Map

Default project database:

```bash
sqlite:///E:/projects/evolver-project/evolver.db
```

| Output | Meaning |
|---|---|
| database `skills` | registered skill metadata and content |
| database `skill_evaluations` | quality scores when evaluation runs |
| database `event_log` | `skillgen` event |
| `skills/<name>.md` | generated Markdown skill |
| `evolver-skills/index.json` | skill library index |

## Steps

### Generate — synthesize a topic into a skill

```bash
evolver --fallback skillgen --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --topic "git rebase conflict resolution" \
  --output-dir ./skills
```

Focused topics produce sharper skills. If "No relevant memories found", store more with `evolver-study` first.

### Evaluate — score a generated skill

```bash
evolver evaluate --db-url sqlite:///E:/projects/evolver-project/evolver.db \
  --file ./skills/<name>.md --topic "skill topic"
```

## Quality Gate

Accept a generated skill only when:

| Check | Requirement |
|---|---|
| Boundary | One cohesive intention, not one CLI command per skill |
| Description | Trigger conditions, not a workflow summary |
| Procedure | Concrete steps with commands or deterministic actions |
| Provenance | Explains which memories/topic produced it |
| Validation | `evolver evaluate` score is acceptable |

Reject or revise skills that look like memory dumps. A usable skill needs triggers, workflow, inputs/outputs, checkpoints, error handling.

## Error Handling

- "No relevant memories found for this topic": store experiences with `evolver-study`, then retry.
- If embedding/model access fails, retry with `--fallback`.
- If a generated skill duplicates an existing library skill, evolve the existing one.

## Related

- `evolver-study` — learn, recall, distill the experiences this skill synthesizes from.
- `evolver-store` / `evolver-query` — MySQL dead-data archive (not involved in skill generation).
```

- [ ] **Step 2: Run tests to check skill-related assertions pass**

Run:

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_docs.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/evolver-skill/SKILL.md
git commit -m "feat: add evolver-skill skill"
```

## Task 4: Delete Old Skills

**Files:**
- Delete: `.claude/skills/evolver-learn/SKILL.md`
- Delete: `.claude/skills/evolver-summary/SKILL.md`

- [ ] **Step 1: Delete old skill directories**

```bash
rm -r .claude/skills/evolver-learn
rm -r .claude/skills/evolver-summary
```

- [ ] **Step 2: Run full test suite**

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_docs.py -v
```

Expected: All 8 tests PASS. `test_agent_facing_evolver_skills_are_four_storage_channels` now passes because old skills are gone.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/evolver-learn .claude/skills/evolver-summary
git commit -m "feat: remove old evolver-learn and evolver-summary skills"
```

## Task 5: Final Verification

**Files:**
- Verify only; no code changes expected.

- [ ] **Step 1: Run skill-doc tests**

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_docs.py -v
```

Expected: 8 passed.

- [ ] **Step 2: Inspect final diff**

```bash
git diff --stat main..HEAD
```

Expected: Only `.claude/skills/evolver-study/SKILL.md`, `.claude/skills/evolver-skill/SKILL.md`, `.claude/skills/evolver-learn/SKILL.md` (deleted), `.claude/skills/evolver-summary/SKILL.md` (deleted), `tests/test_skill_docs.py`.

- [ ] **Step 3: Commit only if files changed**

If no files changed since Task 4 commit, do not create an empty commit.
