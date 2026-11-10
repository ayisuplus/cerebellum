# Cerebellum

Cerebellum is an auditable, self-evolving learning control plane and hard-gate
sidecar for coding agents. The main model can remain frozen while experiences,
feedback, memories, Skills, Workflows, datasets and a future small controller
evolve. A model may recommend a workflow, but only deterministic gates can
authorize a brokered high-risk action.

It is designed to sit between an agent (the "brain") and mutation-capable
tools:

```text
GitHub / agent trajectories -> immutable experience + feedback ledger
        -> deterministic learning decisions -> Evolver consolidation
        -> Skill / Workflow / anti-skill proposals -> paired evaluation
        -> reproducible training candidate -> human model approval

Registry -> Router -> Workflow DAG -> Hard gates -> action-bound permit

GitHub / HN / RSS / search -> bounded acquisition -> immutable documents
        -> evidence-backed KnowledgeCards -> FTS5 + hybrid retrieval -> MCP

Learning traces -> daily Dataset Draft -> immutable Snapshot -> manual start
        -> MoE-ready expert views -> temporary AutoDL QLoRA worker
        -> Router + independent expert candidates -> shadow/canary/rollback

Eligible records -> deterministic privacy/license gate -> DeepSeek Flash review
        -> Pro arbitration/audit -> bounded synthetic candidates -> verified Draft
```

The current MVP includes:

- SQLite WAL Registry plus SHA-256 content-addressed object storage.
- Versioned Skill, Workflow, Gate, Trace, CandidateExport and PairedEval
  contracts with generated JSON Schemas.
- `bugfix`, `feature`, `code-review`, and `pre-merge` workflows.
- Deterministic BM25 routing with fail-safe fallback from local model servers.
- Built-in evidence, test, file, Git, diff, permission and approval gates.
- HMAC-signed, short-lived, action-bound and optionally single-use permits.
- Authenticated loopback HTTP API and a stdio MCP adapter.
- Quarantined Skill Wiki and pinned-commit GitHub collection.
- Paired baseline/treatment execution in digest-pinned, network-disabled Docker
  sandboxes with bounded resources and output.
- Evidence refresh, promotion thresholds and guarded training export.
- Immutable `ExperienceEnvelope`, `FeedbackSignal`, `LearningDecision`,
  consolidation and training-candidate contracts.
- Objective-first feedback aggregation, deterministic learning priority,
  anti-skill retention and context retrieval.
- Bounded CurriculumPlanner, signed GitHub webhooks and fixed-commit automatic
  collection with global daily 20/50/500 limits.
- Durable SQLite jobs with leases, retries, dead letters, result hashes and a
  database-independent Evolver worker.
- Dataset-manifest generation and audited human model approve/reject/rollback;
  this milestone cannot launch training.
- A pinned Microsoft SkillOpt reference worker, a deterministic 60-task Python
  benchmark, restricted Skill edit patches, objective validation/holdout gates
  and human-only SkillVersion adoption.
- Versioned TopicWatch and SourcePolicy control, resumable GitHub/HN/RSS
  connectors, conditional requests, source-rate budgets and acquisition plans.
- An isolated failure-driven web acquisition worker with direct HTTP,
  Crawl4AI, Firecrawl, LinkMapper, Scrapling and local-only OpenCLI adapters.
- Immutable evidence-backed KnowledgeCards with revision history, conflict and
  retraction states, 30-day raw retention, FTS5 retrieval and a rebuildable
  compact embedding index.
- A fail-closed 1--3B QLoRA worker contract plus shadow, deterministic 10%
  canary, 24-hour/1,000-decision activation gates and immediate rollback.
- A daily 03:00 Asia/Shanghai dataset factory with deterministic `JSONL.zst`
  shards, immutable snapshots, manual budget confirmation, a pinned AutoDL
  application provider, scoped rotating worker tokens and a built-in `/admin`
  console. Creating data or a TrainingRun never allocates a GPU.
- Request-level Top-1 Routed LoRA over a frozen base model: deterministic
  expert assignment, shared/router/domain/routing-negative shards, independent
  Router/Shared/Expert versions, objective release gates and dense fallback.
- DeepSeek Flash/Pro semantic quality gates with explicit external-processing
  permission, local redaction attestations, fingerprint approval, atomic daily
  CNY budgeting, non-recursive synthetic lineage and Pro-audited Draft promotion.

## Repository layout

Cerebellum is a single versioned repository. The runtime boundaries remain
explicit so that proposal engines and imported knowledge cannot bypass the
deterministic control plane:

- `crates/`: authoritative Rust registry, router, workflow engine and hard gates.
- `components/evolver/`: Python memory, retrieval, consolidation and candidate
  proposal engine.
- `knowledge/skill-wiki/`: quarantined Wiki pages and derived training JSONL.
- `workers/`: stateless reference workers for optimization, acquisition and
  meta-training.
- `schemas/`, `docs/`, `deploy/` and `scripts/`: shared contracts, operations
  and repository-wide quality gates.

See [docs/monorepo.md](docs/monorepo.md) for the ownership rules, data flow and
the full architecture diagram. Import provenance is recorded in
[IMPORT_MANIFEST.json](IMPORT_MANIFEST.json).

## Quick start

```powershell
cargo build --release

# Create Registry and import the legacy Wiki as quarantined data.
target\release\cerebellum.exe --data-dir .cerebellum init `
  --wiki knowledge\skill-wiki\skill-wiki

# Start the authenticated loopback sidecar.
target\release\cerebellumd.exe --data-dir .cerebellum `
  --bind 127.0.0.1:3927
```

The first start creates `.cerebellum/auth.token` and
`.cerebellum/signing.key`. Keep both private. Send the token as
`Authorization: Bearer <token>`.

Configure an MCP client to launch:

```powershell
target\release\cerebellum.exe --data-dir .cerebellum mcp `
  --server-url http://127.0.0.1:3927
```

The canonical protocol is documented in [docs/protocol.md](docs/protocol.md)
and the trust boundary in [docs/security.md](docs/security.md). Linux/mTLS
server deployment is documented in [docs/deployment-v2.md](docs/deployment-v2.md).
The v2.1 Skill evolution experiment is documented in
[docs/skillopt-v2.1.md](docs/skillopt-v2.1.md).
The realtime acquisition and meta-learning loop is documented in
[docs/realtime-knowledge-v3.md](docs/realtime-knowledge-v3.md).
The decoupled dataset factory and on-demand AutoDL lifecycle are documented in
[docs/dataset-factory-v3.1.md](docs/dataset-factory-v3.1.md).
The MoE-ready dataset and request-routed LoRA lifecycle are documented in
[docs/routed-lora-moe-v3.2.md](docs/routed-lora-moe-v3.2.md).
The DeepSeek quality and synthesis lifecycle is documented in
[docs/deepseek-quality-v3.3.md](docs/deepseek-quality-v3.3.md).

## Dataset factory and on-demand training

With `CEREBELLUM_LEARNING_SCHEDULER=true`, the server enqueues exactly one
`dataset_draft_build_v1` per Shanghai calendar day after 03:00. Draft builds
have no minimum-size threshold and never create a GPU instance. An administrator
freezes a Build into a Snapshot, creates a budgeted TrainingRun, then separately
confirms `:start`. The formal start gate requires 5,000 eligible deduplicated
decisions, 1,000 safe independent replays, an unretracted Snapshot, a pinned
base model, an allowlisted NVIDIA CUDA GPU with at least 24 GB, and exact hourly,
total and wall-clock budgets.

Every Build also emits an immutable expert view. Routed training is opt-in and
adds a 5,000-record Top-1 router view plus four domain views and a shared
fallback. Each selected domain expert requires 1,000 train records and 200
replays. Dense LoRA remains available and is the fail-safe runtime baseline.

The central deployment is CPU-only. AutoDL is disabled unless every provider,
application-version, GPU, base-model and HTTPS worker-gateway setting is
explicit. The generated AutoDL command receives only a one-use bootstrap code;
it receives neither the Registry token nor the AutoDL developer token. Open the
single-user console through the mTLS gateway at `/admin`.

## Realtime knowledge loop

Set `CEREBELLUM_LEARNING_SCHEDULER=true`, create a `SourcePolicy`, then create
a `TopicWatch` referring to that policy. HN is polled at no less than 30
seconds; GitHub and RSS/Atom at no less than 120 seconds; broad Tavily and
Firecrawl discovery at no less than 30 minutes. A connector can also be synced
immediately with `POST /v1/connectors/{policy_id}:sync`.

Knowledge remains usable without a model. SQLite FTS5 and the local
`feature-hash-v1` index are deterministic; rebuild the latter with:

```powershell
cerebellum --data-dir .cerebellum rebuild-knowledge-index
```

An optional OpenAI-compatible extractor is enabled only when both
`CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT` and
`CEREBELLUM_KNOWLEDGE_MODEL_NAME` are present. Invalid JSON, timeout, low
confidence, prompt injection, PII, secrets, and authenticated-local documents
all fall back to deterministic consolidation.

## SkillOpt reference experiment

The v2.1 loop optimizes `evolver-verify` without training or publishing a
model. Rust remains authoritative: it replays candidate patches, recomputes
objective gates and requires a named human approval. Generate the family-level
30/15/15 benchmark with:

```powershell
python benchmarks/verify/generate.py `
  --image ghcr.io/OWNER/cerebellum-python311-pytest@sha256:DIGEST `
  --output benchmarks/verify/generated
```

Then use `optimize-skill`, `optimization-status`, and
`review-optimization`. Docker Desktop with Linux containers and all four
OpenAI-compatible environment variables are required for a real run; the
service provides no model defaults.

## Continual-learning dry run

The acceptance fixture generates 100 coding trajectories, objective test
feedback, classifications, memory/anti-skill proposals and a reproducible but
insufficient-evidence training candidate. It never starts a trainer:

```powershell
cerebellum --data-dir .cerebellum simulate-learning --count 100
cerebellum --data-dir .cerebellum learning-status
```

## Local model routing

The service works without a model using `deterministic-bm25`. To route through
a Rust-native `mistral.rs` server or a `llama.cpp` server, configure its
OpenAI-compatible endpoint:

```powershell
$env:CEREBELLUM_ROUTER_BACKEND = "mistralrs"
$env:CEREBELLUM_MODEL_ENDPOINT = "http://127.0.0.1:1234"
$env:CEREBELLUM_MODEL_NAME = "local-router"
target\release\cerebellumd.exe --data-dir .cerebellum
```

Invalid JSON, invented workflow IDs, confidence below `0.25`, timeouts, and
backend failures fall back to deterministic routing. Model output never
changes or bypasses a gate definition.

## Import boundaries

Legacy Wiki import:

```powershell
cerebellum import-wiki knowledge\skill-wiki\skill-wiki --limit 100
```

Pinned GitHub import:

```powershell
cerebellum collect-github https://github.com/OWNER/REPO FULL_40_CHAR_COMMIT_SHA
```

Evolver export and import:

```powershell
python -m pip install -e .\components\evolver
evolver export-candidates --output candidates.json --limit 1000
cerebellum import-evolver candidates.json
```

All three paths produce quarantined inputs. Unknown licenses remain
`NOASSERTION` and are never training eligible.

## Evaluation and training

Run a paired evaluation from an operator-reviewed plan, optionally recording
the result directly in the Registry:

```powershell
# Register the Skill, then replace the placeholder image and runner arguments.
cerebellum run-paired-eval examples\paired-sandbox-plan.json --record
```

Both arms must use the same digest-pinned image, repository snapshot, timeout,
environment and budget. Docker runs without network access, Linux capabilities,
or writable host paths other than a copied evaluation workspace. Third-party
Skill text is never executed directly on the host. The referenced Skill version
must already exist in the Registry, but it may remain quarantined while evidence
is collected.

Existing evaluation results can also be recorded using the generated
`paired-eval` schema, then used to refresh a Skill's evidence card:

```powershell
cerebellum record-eval examples\paired-eval.json
cerebellum refresh-evidence SKILL_ID VERSION
cerebellum training-status
cerebellum export-training training.jsonl
```

`experimental` requires at least 10 independent tasks and 30 paired runs with
non-negative uplift. `trusted` requires 50 independent tasks and a positive
95% bootstrap lower bound. Normal training export remains blocked until 5,000
completed routing decisions and 1,000 paired evaluations exist.

## Development

```powershell
.\scripts\test-all.ps1
```

The command runs the Rust workspace, JavaScript syntax check, Python workers,
Evolver suite and knowledge-corpus validation. Individual commands remain
documented in [docs/monorepo.md](docs/monorepo.md).
Measure and enforce per-area test coverage (Rust via `llvm-tools-preview`
source instrumentation, Python via `pytest-cov`; every area must stay at or
above 80%, overall reported last):

```powershell
.\scripts\coverage.ps1
```

Cerebellum-authored code is dual-licensed under MIT or Apache-2.0. Imported
assets retain their recorded provenance and license status; `NOASSERTION`
material remains quarantined and is not training eligible.
