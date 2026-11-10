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
$env:EVOLVER_DB_URL
```

| Operation | Primary storage | File output |
|---|---|---|
| `learn` | database `memories`, `interactions`, `event_log`, derived graph rows | none |
| `add-fact` | database `facts` | none |
| `distill` | database `distill_runs`, sometimes `facts` | `memory/today.md`, `memory/week.md`, `memory/longterm.md`, `memory/memory_context.md` |
| `forget` | deletes database memory rows by id/filter | none |

## Steps

### Learn — store a reusable lesson

Map all content into `--task`. The whole experience — what happened, how it was solved, the takeaway — goes in one field. `--outcome` defaults to `success`.

```bash
evolver --fallback learn --db-url $env:EVOLVER_DB_URL \
  --task "what happened, how it was solved, and the takeaway" \
  --outcome success
```

### Recall — search stored experiences

```bash
evolver --fallback recall --db-url $env:EVOLVER_DB_URL \
  --query "search terms" --top-k 5
```

Use `recall-light` for fast snippet lookup:

```bash
evolver --fallback recall-light --db-url $env:EVOLVER_DB_URL \
  --query "search terms" --top-k 10
```

### Facts — list or search atomic facts

```bash
evolver --fallback facts --db-url $env:EVOLVER_DB_URL \
  --query "search terms"
```

### Distill — time-weighted memory compression

```bash
evolver --fallback distill --db-url $env:EVOLVER_DB_URL \
  --level all --days 7
```

Levels: `today`, `week`, `longterm`, `facts`, `all`.

### Forget — remove targeted memories

```bash
evolver --fallback forget --db-url $env:EVOLVER_DB_URL \
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
