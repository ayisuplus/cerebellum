# Realtime technical knowledge and meta-learning v3

V3 adds a second continual-learning loop without replacing the Skill,
Workflow, Gate, SkillOpt, or Evolver subsystems.

```text
TopicWatch + SourcePolicy
  -> incremental discovery -> failure-driven acquisition -> DocumentEnvelope
  -> deterministic/weak-model consolidation -> KnowledgeCard revisions
  -> FTS5 + compact local-vector reranking -> HTTP/MCP retrieval

MetaDecisionTrace + objective replay
  -> licensed manifest -> isolated QLoRA adapter
  -> shadow -> deterministic 10% canary -> activate or rollback
```

## Source setup

`SourcePolicy` is the durable authorization boundary. It fixes source kind,
base URL, allowed domains, public/API/authenticated-local mode, robots policy,
depth, per-run pages, per-minute rate, raw retention, license, and model-term
eligibility. `TopicWatch` supplies bilingual keywords/entities, source IDs,
refresh interval, and daily budgets.

Built-in incremental discovery supports Hacker News updates/items, GitHub
events, and RSS/Atom with ETag and Last-Modified cursors. A signed WebSub
notification can trigger the same bounded RSS sync without storing its body.
Tavily and Firecrawl search are optional managed/provider calls. HN is clamped
to 30 seconds, GitHub/RSS to 120 seconds, and broad search to 1,800 seconds.

The SQLite queue stores leases, delayed retry time, attempts, and dead-letter
state. Discovery children are canonicalized, allowlist-filtered, deduplicated,
budgeted, and bounded before they become acquisition jobs.

## Acquisition ladder

The worker escalates only after `partial_content`, `js_shell`, or
`parse_failed`:

1. Direct platform/RSS/HTTP response.
2. Crawl4AI.
3. Firecrawl independent API.
4. Built-in sitemap/canonical/link mapping.
5. Scrapling browser mode for authorized public pages.
6. Local OpenCLI bridge for an explicitly authenticated-local source.

`429`, timeout, and `5xx` persist their attempt and retry later with the same
identity. `401` reaches OpenCLI only when policy already permits local auth.
Robots denial, CAPTCHA, explicit challenge, policy denial, 404, and 410 stop.
The implementation never rotates identity or solves a challenge.

The default worker image includes the standard-library path and HTTP service
adapters. Browser extras remain disabled until their pinned packages and
runtime are deliberately installed. Exact upstream versions, commits, source
archive hashes, licenses, and integration modes live in
`workers/web-acquisition/providers.lock.json`. AnythingSearch and the unknown
legacy Scraping repository remain unimplemented provider slots.

## Knowledge semantics

A DocumentEnvelope points to SHA-256 CAS objects and records extraction,
rights, provenance, timestamps, and safety flags. Raw content expires after 30
days by default. KnowledgeCard stores atomic claims and evidence relationships
as immutable revisions with these states:

- `unverified`: only one independent support path or insufficient evidence;
- `corroborated`: support from at least two independent source domains;
- `contested`: active opposing evidence exists;
- `superseded`: retained historical conclusion replaced by a newer one;
- `retracted`: all active evidence was withdrawn or explicit retraction exists.

Retrieval uses FTS5 as the permanent baseline, with topic/time/status filters
and a rebuildable 64-dimensional feature-hash reranker. Results always expose
status, observation time, confidence, and evidence URL. Run
`cerebellum rebuild-knowledge-index` after changing local embedding logic.

The optional OpenAI-compatible extractor must return JSON matching a closed
schema. Its self-confidence is capped at 0.6, and it cannot set source,
license, safety, or status fields. Invalid JSON, low confidence, timeout, and
service failure use deterministic extraction. Sensitive and local-auth content
is never sent to that model.

## Retention and withdrawal

Daily `retention_gc_v1` removes expired raw objects only when no live document
references them. A source withdrawal through
`POST /v1/source-policies/{id}:tombstone` additionally disables collection,
tombstones all active documents, deletes unreferenced raw and cleaned CAS
objects, removes evidence excerpts from returned history, creates recalculated
card revisions, and writes an actor/reason audit record. Content hashes and
tombstone metadata remain for integrity and deletion provenance.

## Meta-learning lifecycle

The trainable 1--3B controller targets relevance, noise filtering,
deduplication, retrieval ranking, claim relationship, acquisition escalation,
curriculum priority, and expected information gain. The main model remains
frozen, and deterministic policy remains authoritative.

Candidate preparation requires 5,000 deduplicated licensed traces, 1,000
independent safe replay evaluations, and a seven-day cooldown. Splits group by
source domain and topic family while preserving event time; failed, ignored,
bad-retrieval, and negative-transfer outcomes are retained. The manifest
asserts that no raw documents are present.

The GPU worker is disabled unless base model, model version, licensed-only
policy, and a real 24 GiB CUDA device are explicit. It trains a 4-bit NF4 LoRA
adapter and returns a deterministic immutable ZIP. Training loss is diagnostic
only and cannot pass activation gates.

Rust permits `candidate -> shadow -> canary -> active`. A lease-verified
training result enters shadow automatically; objective shadow evaluation then
enters canary only with zero policy violations, no injection regression, old-task retention
at least 98%, relative NDCG@10 gain at least 3%, no core topic regression over
2%, no fact-precision loss, and cost regression at most 10%. Exactly 10% of
decision IDs are assigned by stable SHA-256 partitioning. Activation requires
at least 24 hours and 1,000 assigned decisions. Any policy violation or failed
metric rolls back; named manual rollback remains available.

## What can run without Docker or models

SQLite WAL/CAS, HN/GitHub/RSS discovery, direct HTTP acquisition, deterministic
consolidation, retention, FTS5/hybrid retrieval, MCP, decision logging,
candidate preparation, and every hard policy work without Docker, a browser,
GPU, or hosted model. Browser provider smoke tests, real QLoRA, a 24-hour soak,
and the release 100,000-card latency benchmark are environment acceptance
tests, not startup requirements.
