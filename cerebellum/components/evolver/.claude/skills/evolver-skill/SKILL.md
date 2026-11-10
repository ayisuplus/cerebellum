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
$env:EVOLVER_DB_URL
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
evolver --fallback skillgen --db-url $env:EVOLVER_DB_URL \
  --topic "git rebase conflict resolution" \
  --output-dir ./skills
```

Focused topics produce sharper skills. If "No relevant memories found", store more with `evolver-study` first.

### Evaluate — score a generated skill

```bash
evolver evaluate --db-url $env:EVOLVER_DB_URL \
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
