---
name: evolver-query
description: Use when an agent needs to read archived raw data from Evolver's MySQL data tier by keyword or id; trigger on /evolver-query, 查一下归档, get archive record, search archived logs, or when previously stored verbatim records, payloads, transcripts, or image references must be retrieved.
---

# Evolver Query — Read Archived Data (MySQL)

Retrieve raw data from Evolver's **data tier** (MySQL). Two ways to fetch:

- **Full-text search** — find records whose `content` matches a query (Chinese-friendly ngram index, with a LIKE fallback when full-text matches nothing).
- **By id** — fetch one exact record.

This reads the archive only. It does **not** recall experiences — semantic recall of reusable lessons is a separate experience-tier operation. Use this when you want verbatim archived material (the logs/records/image references that `evolver-store` put away).

## When to use

| Goal | Skill |
|---|---|
| Find an archived log/record/transcript by keyword | **evolver-query** (this) |
| Fetch one archived record by its id | **evolver-query** (this) |
| Write data into the archive | evolver-store |
| Recall a reusable lesson/insight by meaning | (experience tier — not this) |

## Configuration

The archive tier is optional and **lazy-connected** — it connects on first query. Configure via:

- `--data-url mysql://user:pass@host:3306/dbname`, or
- the `EVOLVER_DATA_URL` environment variable.

If unconfigured, the command errors with guidance to set `--data-url` / `EVOLVER_DATA_URL`.

## Storage Map

| Operation | Reads | Notes |
|---|---|---|
| `query-archive --query` | MySQL `archive` table (full-text) | falls back to LIKE if full-text matches nothing |
| `query-archive --id`    | MySQL `archive` table (primary key) | returns one record or "not found" |

This is a read-only operation; it produces no files or DB writes.

## Steps

1. Full-text search by keyword:
   ```bash
   evolver query-archive \
     --data-url mysql://user:pass@localhost:3306/evolver_archive \
     --query "deployment rollback" \
     --limit 20
   ```
   Results list each record's id, kind, tags, ref (if any), and a content snippet.

2. Fetch one record by id (e.g. an id returned earlier by `evolver-store`):
   ```bash
   evolver query-archive \
     --data-url mysql://user:pass@localhost:3306/evolver_archive \
     --id 42
   ```

3. For machine-readable output (full content, all fields), use JSON:
   ```bash
   evolver query-archive \
     --data-url mysql://user:pass@localhost:3306/evolver_archive \
     --query "payload" --format json
   ```

4. Report what was found: ids, kinds, and the relevant snippet(s). For an image record, surface the `ref` path/URL so the user can open the actual file.

Flags:
- `--query`: full-text search string. Either `--query` or `--id` is required.
- `--id`: fetch a single record by primary key.
- `--limit`: max results for search (default 20).
- `--format`: `text` (default, snippets) or `json` (full records, fields decoded).

## Examples

**Example 1 — keyword search**
Input: Find the archived logs about a failed migration.
```bash
evolver query-archive --data-url mysql://user:pass@localhost:3306/evolver_archive \
  --query "migration failed" --limit 10
```

**Example 2 — fetch one record verbatim**
Input: Pull archive record 17 in full.
```bash
evolver query-archive --data-url mysql://user:pass@localhost:3306/evolver_archive \
  --id 17 --format json
```

## Checkpoints

- Read-only — safe to run freely. No writes, no files.
- Either `--query` or `--id` must be provided; running with neither prints a usage hint.
- For images/large files the archive stores only a `ref` — to view the actual content, follow the returned path/URL.
- Use `--format json` when you need the full content or want to parse fields; the text format truncates content to a snippet.

## Error Handling

- "Archive layer not configured. Pass data_url= to enable it." → supply `--data-url` or set `EVOLVER_DATA_URL`.
- "No archive records found." → broaden keywords or verify the id; full-text already falls back to a LIKE scan when it matches nothing, so an empty result means there's genuinely no match.
- Connection errors mention checking the URL and that MySQL is running — verify host/credentials and reachability.

## Related

- `evolver-store` — write data into the archive (the counterpart to this read path).
- `evolver-summary` / `evolver-learn` — the experience tier, for reusable lessons recalled by meaning.
