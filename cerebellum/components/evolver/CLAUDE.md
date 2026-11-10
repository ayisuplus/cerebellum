# Evolver Project

Unified evolver database location: `E:\projects\evolver-project\evolver.db`

Control-plane skills: evolver-memory, evolver-skillcraft

## Entrypoints

- `/evolver-input -> evolver-memory`: store a durable lesson, then distill if consolidation is requested.
- `/evolver-recall -> evolver-memory`: query memories, facts, or memory summaries and report provenance.
- `/evolver-skill -> evolver-skillcraft`: generate, evaluate, or repair reusable skill documents.

The slash commands are thin wrappers. They do not define separate skill rules.

## Storage

All project-local Evolver commands should use this database unless the user gives another target:

```bash
sqlite:///E:/projects/evolver-project/evolver.db
```

Write-producing commands print a storage receipt:

- `learn`: database `memories`, `interactions`, `event_log`, derived graph rows.
- `add-fact`: database `facts`.
- `distill`: database `distill_runs` plus `memory/today.md`, `memory/week.md`, `memory/longterm.md`, `memory/memory_context.md`.
- `skillgen`: database `skills`, `event_log`, `skills/<name>.md`, and the `evolver-skills/` library.

## Archive Layer (data tier)

Optional MySQL-backed dead-data store, independent of the experience tier.
Enable by passing `data_url="mysql://..."` to `Evolver(...)`. Lazy-connected:
no connection until the first `archive()` call.

- `archive(content, kind, tags=, source=, ref=, meta=)` — store a record, returns id.
- `search_archive(query, limit=)` — full-text (ngram) search, LIKE fallback.
- `get_archive(id)` — fetch one record.

Images/large files are stored by reference (`ref` = path/URL), not as BLOBs.
No embeddings, no skill generation, no cross-tier links.

## Commands

```bash
evolver --fallback learn --db-url sqlite:///E:/projects/evolver-project/evolver.db --task "task" --outcome success --solution "solution" --lessons "lesson"
evolver --fallback distill --db-url sqlite:///E:/projects/evolver-project/evolver.db --level all --days 1
evolver --fallback recall --db-url sqlite:///E:/projects/evolver-project/evolver.db --query "query"
evolver --fallback facts --db-url sqlite:///E:/projects/evolver-project/evolver.db --query "query"
evolver --fallback skillgen --db-url sqlite:///E:/projects/evolver-project/evolver.db --topic "topic" --output-dir ./skills
evolver stats --db-url sqlite:///E:/projects/evolver-project/evolver.db
```
