# HTTP and MCP protocol

All `/v1` routes except signed GitHub/WebSub callbacks and the narrowly scoped
training-worker gateway require the bearer token created in the configured data
directory. Worker routes accept only one-use bootstrap or Run-bound rotating
tokens; they never accept that root token as worker authority. `/health` is
unauthenticated and reveals only service status, version and the Registry
snapshot hash.

## Continual-learning sequence

1. `POST /v1/experiences` records an immutable `ExperienceEnvelope v1` and
   immediately creates a low-confidence deterministic classification.
2. `POST /v1/experiences/{id}/feedback` appends a `FeedbackSignal v1` and
   creates a new `LearningDecision`; it never mutates the original envelope.
3. `POST /v1/context:retrieve` returns relevant episodic/fact/failure and
   anti-skill proposals. Anti-skills carry an explicit non-executable warning.
4. `GET /v1/learning/status` exposes counts, queue state, task success,
   forward transfer, retention, negative transfer, calibration error and gain
   per unit cost.
5. `GET|POST /v1/curricula` manages bounded GitHub exploration plans.
6. `GET /v1/training-candidates` returns reproducible dataset manifests. No
   endpoint starts a trainer.
7. `POST /v1/models/{model}@{version}:approve|:reject|:rollback` requires a
   non-empty human actor and reason and writes an audit event.

Objective test/build/gate feedback has trust weight `1.0`, human and delayed
outcomes `0.8`, and LLM critic feedback `0.25`. If objective feedback exists,
weaker feedback does not control correctness. Objective feedback also requires
a canonical evidence hash and a Sidecar HMAC attestation; an Agent holding only
the HTTP token cannot promote its own self-report to strong evidence. The baseline scheduling formula
is exactly `expected_gain * confidence * (1-risk) / (1+cost)`.

The trusted local tool broker can run `cerebellum attest-feedback INPUT
OUTPUT` using filesystem access to the Sidecar data directory. This command is
not exposed as HTTP or MCP and must not be delegated to the model.

Evolver workers use `POST /v1/learning/jobs:claim` with an allowed-kind list,
fetch immutable requests from `GET /v1/objects/{sha256}`, post
`ConsolidationResponse v1` to `/v1/consolidations`, then complete or fail the
lease. Lease expiry, retries and dead-letter state live in SQLite; workers do
not access its tables.

## Skill optimization sequence

1. `POST /v1/optimization-runs` validates a `CreateOptimizationRunRequest`,
   resolves the immutable baseline Skill and benchmark CAS objects, reserves a
   prerelease/stable version pair and atomically enqueues
   `skillopt_optimize_v1`.
2. `GET /v1/optimization-runs/{id}` and
   `GET /v1/optimization-runs/{id}/patches` expose run and immutable patch
   state.
3. The leased worker fetches only `GET /v1/objects/{sha256}`. It submits one
   immutable `SkillOptimizationResult v1` to
   `POST /v1/optimization-runs/{id}/result`; a different or expired lease
   owner is rejected.
4. Rust replays every restricted patch, verifies frontmatter protection,
   hashes and budgets, recomputes task means and validation gates, and
   recomputes the paired holdout bootstrap. Worker booleans are assertions,
   not trusted decisions.
5. A positive run enters `validated`. A named human may call
   `POST /v1/optimization-runs/{id}:approve|:reject` with a non-empty reason.
   Approval creates a new SkillVersion with lineage; it never updates the
   baseline row.

An optimization job cannot be completed before its result is accepted. Empty
failed-closed results remain auditable and become `rejected`. A result above
the 240 target-rollout, 24 optimizer-call, two-million-token or six-hour hard
budget is rejected by the control plane.

`POST /v1/github/webhooks` is outside bearer authentication because GitHub
cannot use the local token. It requires a valid `X-Hub-Signature-256`, a
watchlisted repository, and a full commit SHA. WebSub
`GET|POST /v1/websub/{policy_id}` is likewise isolated: verification must name
the exact enabled RSS/Atom policy URL, and notifications require the configured
HMAC-SHA256. Notification bodies are not trusted or stored; they only schedule
the normal bounded connector sync. The deployment exposes only these callback
routes on its separate TLS listener.

## Realtime acquisition and knowledge sequence

1. `GET|POST /v1/source-policies` registers a bounded source once. Public,
   API, and authenticated-local access are distinct policy modes.
2. `GET|POST /v1/topics` records a bilingual `TopicWatch` with source IDs,
   refresh interval, and daily discovery/fetch/browser budgets.
3. The scheduler or `POST /v1/connectors/{policy_id}:sync` creates an immutable
   `AcquisitionPlan` and a leased `source_discover_v1` job. Conditional ETag,
   Last-Modified, and source cursors survive process restarts.
4. The isolated web worker claims only `document_acquire_v1`, reserves each
   source request and browser escalation atomically, and submits one immutable
   `AcquisitionWorkerResult`. Retryable attempts are recorded before their
   delayed retry; terminal failures remain evidence.
   List-type discovery sources (Chinese hot boards `weibo`/`zhihu`/`douyin`/
   `bilibili`/`xhs`/`baidu`/`kuaishou`/`tieba` and the `openalex`/`arxiv`/
   `journal` paper collectors) are delegated by the same discovery executor to
   the isolated social acquisition worker under `social_acquisition_v1`. The
   claim protocol discriminates workers by job kind, so the two workers can
   never steal each other's jobs. The social worker submits a board-level
   snapshot Document plus item URLs; each item URL then flows through the
   ordinary `document_acquire_v1` path. Authenticated-local douyin/xhs
   providers are fail-closed: a missing policy mode or cookie file yields
   `policy_denied`/`auth_required`, never fabricated items.
5. Successful documents enter CAS and enqueue `knowledge_consolidate_v1`.
   Consolidation creates a new `KnowledgeCard` revision; it never overwrites
   history. Independent supporting domains corroborate a claim, opposing
   evidence makes it contested, and withdrawal creates a retracted revision.
6. `POST /v1/knowledge:retrieve` performs time/status/topic-filtered FTS5 plus
   rebuildable local-vector reranking. Every item returns state, observation
   time, confidence, and evidence URLs. `GET /v1/knowledge/cards/{id}` and
   `/history` return the latest card and all immutable revisions.
7. `POST /v1/source-policies/{id}:tombstone` requires `actor` and `reason`,
   disables the source, removes unreferenced raw/cleaned CAS content, redacts
   excerpts, recomputes cards, and appends an audit event.

Worker-only routes use the same bearer authentication but additionally verify
the active lease owner: `/v1/acquisition/results`,
`/v1/acquisition/browser-budget:reserve`, and
`/v1/acquisition/source-rate:reserve`. Workers cannot read SQLite.

## Meta-learning sequence

1. Each deterministic or weak-model learning decision is appended as a
   `MetaDecisionTrace`; objective replays are appended as
   `MetaReplayEvaluation`. IDs are immutable and training-eligible traces are
   rejected if they contain secrets or policy violations.
2. At 03:00 Asia/Shanghai the scheduler creates `DatasetBuild v1` regardless
   of size and advances `DatasetDraft` only after every deterministic
   `JSONL.zst` shard, Manifest and Bundle has entered CAS. It never schedules a
   trainer. Ordinary KnowledgeCards and network source text are absent.
   Two kinds are built daily under independent dedup keys: `meta-controller`
   (decision traces, replays, synthetic candidates) and `knowledge-web`
   (instruction records mapped from the latest revisions of training-eligible
   KnowledgeCards that additionally cleared the local Ornith quality gate;
   unassessed or ineligible cards never enter the Build). knowledge-web Builds
   carry no expert view and train through the dense TrainingRun path.
3. `POST /v1/dataset-snapshots` freezes a successful Build. A revocation is a
   separate immutable event. `POST /v1/training-runs` records configuration and
   budget without contacting a GPU provider. Only
   `POST /v1/training-runs/{id}:start` may provision AutoDL, after rechecking
   5,000/1,000 evidence thresholds and the seven-day frequency gate.
4. `POST /v1/meta-models/{model}@{version}:evaluate` records objective shadow
   metrics and automatically enters canary only when every activation gate
   passes. `:shadow` and `:canary` remain administrator recovery operations.
   Canary assignment is a stable SHA-256 partition at 10%.
5. `POST /v1/meta/canary-decisions` records outcomes. Any policy violation
   rolls back immediately. `:evaluate` activates only after at least 24 hours,
   1,000 canary decisions, all safety gates, 98% old-task retention, a relative
   3% NDCG@10 gain, bounded topic regression, non-decreasing fact precision,
   and bounded cost. `:rollback` remains available with an actor and reason.

Dataset and Run routes are:

- `GET /v1/datasets/{kind}/draft` and `POST /v1/datasets/{kind}:build`;
- `GET|POST /v1/dataset-snapshots`, `GET /{id}`, and `POST /{id}:revoke`;
- `GET|POST /v1/training-runs`, `GET /{id}`, and
  `POST /{id}:start|:cancel|:release`;
- `GET /v1/training-config` exposes only safe pinned choices, never secrets.

Quality and synthesis routes are:

- `GET /v1/quality/status` and `GET /v1/quality/assessments`;
- `GET /v1/quality/model-versions` and
  `POST /v1/quality/model-versions/{id}:approve|:reject`;
- `POST /v1/quality:backfill`;
- `GET /v1/dataset-builds/{id}/quality-report` and
  `POST /v1/dataset-builds/{id}:reaudit`;
- `GET /v1/synthetic-candidates` and
  `POST /v1/synthetic-candidates/{id}:approve|:reject`.

When quality enforcement is enabled, deterministic eligibility is evaluated
first and every included record must have an assessment from an active exact
model fingerprint. `Flash` and `Pro` remain storage-compatible stage names for
screening and challenge by the same pinned local model. Every request uses a
strict response schema. A Build is immutable and advances the Draft
immediately; its Pro sample report is enforced later as a hard gate at
snapshot freeze, before any snapshot may replace `DatasetDraft`. Assessments and
generated candidates never alter source licenses or deterministic safety facts.

Each Build also exposes a versioned expert view. The MoE control routes are:

- `GET /v1/expert-taxonomy`;
- `GET /v1/expert-dataset-views`, `GET /{id}` and `GET /{id}/assignments`;
- `POST /v1/experts:route` for deterministic Top-1 selection with active
  adapter references and shared/dense fallback markers;
- `GET /v1/expert-adapters` and `GET /{expert}@{version}`;
- `POST /v1/expert-adapters/{expert}@{version}:shadow|:canary|:activate|:reject|:rollback`.

`expert_plan` is absent for Dense LoRA. A Routed LoRA plan binds one frozen
expert view, `router_top_k=1`, the shared fallback identity and an explicit
adapter selection. `train_router`, `train_shared`, and `expert_ids` permit
single-expert refreshes; at least one must be selected. Candidate adapters are
independently gated and cannot be activated by the training Worker.

The deprecated `/v1/meta/training-candidates` remains read-only. Existing
candidate IDs/hashes are idempotently backfilled as Snapshots.
`/v1/meta/training:enqueue` accepts the old candidate ID but now requires all
new model/GPU/budget/operator fields and maps to create plus explicit start.
The scheduler never creates `meta_train_v1`.

The separate worker gateway exposes only:

- `POST /v1/training-worker/bootstrap` (one use, ten minutes);
- `GET /v1/training-worker/runs/{id}/bundle` (Range and SHA-256);
- heartbeat (rotates a 15-minute Run/instance-scoped token);
- streaming artifact `PUT` for adapter/logs/metrics;
- Run-bound `complete` and `fail`.

The adapter limit is 512 MiB and Base64 uploads are not used. Completion only
registers a model `candidate`; existing shadow, canary, activation, and rollback
gates remain authoritative.

## Execution sequence

1. `POST /v1/decisions` with `task`, optional `repository_path`,
   `capabilities`, and structured `context`. Workflow routing completes before
   the task text is used to retrieve up to five memory items and five current
   KnowledgeCards. The resulting `memory_context` and `knowledge_context` are
   persisted with the decision and returned by `cerebellum_plan`; they are
   non-executable evidence and are never sent to the workflow router.
2. Start exactly the selected workflow with `POST /v1/runs`.
3. Append observations to `POST /v1/runs/{id}/events`.
4. Submit evidence to each mandatory
   `POST /v1/runs/{id}/gates/{gate_id}:evaluate`.
5. Request a permit from `POST /v1/authorize` using the complete action JSON.
6. The tool broker calls `POST /v1/permits/verify` with the same action and
   `consume: true` immediately before execution.
7. Finish with `POST /v1/runs/{id}/complete`.

`GET /v1/runs/{id}/trace` returns the versioned, replayable run trace with
ordered events, latest gate evidence and optional completion record.

Automatic knowledge context includes only `unverified`, `corroborated`, and
`contested` cards. `superseded` and `retracted` cards are excluded. Agents must
verify unverified, contested, or stale evidence before using it.

Successful completion and authorization both fail while any mandatory gate is
missing or non-passing. Failed runs may be completed without passing gates so
that negative training evidence is retained.

Workflow state is reconstructed from immutable events. State-changing events
use `kind: node_started | node_completed | node_failed` and require
`payload.node_id`. A node may start only after each incoming edge is satisfied;
edge conditions are the closed set `always`, `on_success`, and `on_failure`.
A successful run must complete every node marked `required`. Other event kinds
remain append-only observations and do not change DAG state.

## Permit properties

A permit binds:

- a random permit ID and run ID;
- the exact workflow ID and version;
- a canonical SHA-256 hash of the complete action JSON;
- issue and expiry timestamps.

TTL is clamped to 1–300 seconds. HMAC verification uses constant-time signature
comparison. A consumed permit cannot be replayed.

## MCP tools

The stdio adapter exposes:

- `cerebellum_plan`
- `cerebellum_start_run`
- `cerebellum_record_event`
- `cerebellum_evaluate_gate`
- `cerebellum_authorize`
- `cerebellum_complete_run`
- `cerebellum_search_skills`
- `cerebellum_record_experience`
- `cerebellum_record_feedback`
- `cerebellum_retrieve_context`
- `cerebellum_learning_status`
- `cerebellum_route_expert`
- `cerebellum_search_knowledge`
- `cerebellum_recent_knowledge`
- `cerebellum_get_knowledge_card`

MCP is an adapter only; HTTP/JSON remains the stable protocol.

Generated request and artifact schemas are in [`schemas/`](../schemas/).
