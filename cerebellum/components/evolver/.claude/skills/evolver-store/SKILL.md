---
name: evolver-store
description: Use when an agent needs to archive raw logs, transcripts, records, payloads, or image/file references into Evolver's MySQL data tier for verbatim long-term retention; trigger on /evolver-store, archive this, 存档, stash this payload, or when content should be fetched later by id or keyword rather than semantic recall.
---

# Evolver Store — Archive Raw Data (MySQL)

Archive raw, verbatim data into Evolver's **data tier** (MySQL). This tier is for "dead data": logs, transcripts, structured records, payloads, and image references that should be retained and fetched back verbatim — but do **not** need semantic recall or skill synthesis.

This is deliberately separate from the experience tier. Experiences (in `evolver-learn`) are living memory that gets recalled by meaning and distilled into skills. The archive is sealed storage you query by keyword or id.

## When to use vs. evolver-learn

Ask one question: **will a future agent want to recall this by meaning, or fetch it verbatim?**

| Content | Tier | Skill |
|---|---|---|
| A reusable lesson, fix, or insight | experience (SQLite) | evolver-learn |
| A raw log dump, transcript, record, payload | data (MySQL) | **evolver-store** (this) |
| An image / large file | data (MySQL), by reference | **evolver-store** (this) |

If in doubt and the material is bulky or you'll want it word-for-word later, store it here.

## Configuration

The archive tier is optional and **lazy-connected** — it only connects to MySQL on the first archive call. It must be configured via one of:

- `--data-url mysql://user:pass@host:3306/dbname` on the command, or
- the `EVOLVER_DATA_URL` environment variable.

Only `mysql://` URLs are accepted. If it isn't configured, the command errors with guidance to set `--data-url` / `EVOLVER_DATA_URL`. The `archive` table (with a Chinese-friendly ngram full-text index) is created automatically on first use.

## Storage Map

| Operation | Primary storage | Notes |
|---|---|---|
| `archive` | MySQL `archive` table | text in `content`; images/large files by `ref` (path or URL) |

## Steps

1. Decide the `kind` — a free-form category you choose: `record`, `log`, `image`, `transcript`, etc. It is required and lets you filter later.

2. Store a text record:
   ```bash
   evolver archive \
     --data-url mysql://user:pass@localhost:3306/evolver_archive \
     --content "raw log or record text" \
     --kind log \
     --tags prod --tags deploy \
     --source ci-pipeline
   ```

3. Store an image or large file **by reference** (the file stays on disk / object storage; only the pointer + metadata are archived):
   ```bash
   evolver archive \
     --data-url mysql://user:pass@localhost:3306/evolver_archive \
     --kind image \
     --ref /data/screenshots/run-42.png \
     --tags qa \
     --meta "{\"mime\": \"image/png\", \"width\": 1920}"
   ```

4. Report the receipt: the CLI prints the new record id and the archive database. Surface the id so it can be fetched later with `evolver-query`.

Field reference:
- `--content`: the text body (optional for pure-image records).
- `--kind` (required): your category label.
- `--tags`: repeatable label flags.
- `--source`: where it came from.
- `--ref`: path or URL for an image/large file — the archive stores the reference, never the bytes.
- `--meta`: extra metadata as a JSON string (e.g. mime type, dimensions, original timestamp).

## Checkpoints

- This is a WRITE to a sealed data store. Confirm the archive database (`--data-url` / `EVOLVER_DATA_URL`) before running.
- Images and large files go in by **reference** (`--ref`), not as blobs — keep the actual file in storage and archive only the pointer + metadata.
- `--meta` must be a valid JSON string; invalid JSON is rejected before any connection is made.
- Don't archive secrets or credentials in `content`/`meta`.
- Note the returned id in your reply so the record can be retrieved later.

## Error Handling

- "Archive layer not configured. Pass data_url= to enable it." → supply `--data-url` or set `EVOLVER_DATA_URL`.
- "data_url must be a mysql:// URL" → the archive tier only accepts MySQL URLs.
- "--meta must be a valid JSON string" → fix the JSON (mind shell quoting of inner quotes).
- Connection errors mention checking the URL and that MySQL is running — verify host/credentials and that the server is reachable.

## Related

- `evolver-query` — read archived data back (full-text search or by id).
- `evolver-learn` — store reusable *experiences* instead (semantic, recalled, distilled into skills).
