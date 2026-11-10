# v3.1 dataset factory and on-demand AutoDL training

## Lifecycle separation

The implementation has three independent ledgers:

```text
eligible traces/replays -> daily Build -> mutable Draft pointer -> frozen Snapshot
Snapshot -> requested TrainingRun -> explicit :start -> temporary AutoDL instance
uploaded adapter -> model candidate -> shadow -> 10% canary -> active or rollback
```

A dataset operation cannot allocate compute. `create_training_run` also performs
only SQLite/CAS writes. The sole provisioning boundary is `:start`.

## Dataset artifacts

`DatasetBuild v1` records the source watermark, previous Build, deterministic
split statistics, policy version, rejection counts, shard hashes, Manifest hash,
Bundle hash and build time. Records are deduplicated by task/input or independent
replay identity and grouped by source domain plus topic family, preventing a
group from crossing train/validation/holdout.

Each non-empty `(split, record kind)` becomes a zstd-compressed JSONL shard.
The deterministic tar Bundle contains those shards and `dataset-manifest.json`.
It also contains an additive MoE-ready view: `expert-dataset-manifest.json`,
`expert-assignments.jsonl`, and shared/router/routing-negative/domain shards.
See [`routed-lora-moe-v3.2.md`](routed-lora-moe-v3.2.md). The original dense
view remains byte-verifiable and usable on its own.
The same ledger and policy produce the same Bundle even though a new Shanghai
calendar day creates a new immutable Build. A failed build never advances the
Draft pointer.

Only `training_eligible` safe decision traces and safety-passing replays are
included. Failure, ignore and negative-transfer labels remain valid examples.
Raw documents, ordinary KnowledgeCards, cookies, authenticated content and
unknown-license source text never enter the Bundle.

The retention pass keeps the latest 30 daily Builds, one Build from each of the
latest 12 weeks, every Draft target and every Snapshot target. Snapshot rows are
permanent; revocation appends an event. Build pruning never directly deletes CAS
objects—only a reference-aware CAS collector may do that.

## AutoDL control plane

`AutoDlAppProvider` implements the ordinary-account application endpoints from
the [official AutoDL application API](https://autodl.art/docs/app_api/): create,
snapshot/price, status, power-off and release. The application version cannot be
`latest`. GPU IDs are selected from deployment configuration and must declare
NVIDIA CUDA with at least 24 GB. Stock failure becomes `waiting_capacity`; the
controller never silently switches to an unapproved GPU.

AutoDL reports prices in thousandths of CNY; the provider converts them before
checking `max_hourly_cny` and projected wall-clock cost. Billing starts when an
instance is created, so a provisional `GpuLease` is persisted immediately and
is recoverable after a control-plane restart. The
[official billing rules](https://autodl.art/docs/app/) charge running time to
the second and stop compute billing at power-off, while disk can continue to
incur a daily fee until release; therefore every terminal path requests both
power-off and release.

## Worker protocol

The private AutoDL application runs native Python. Its start command contains a
Run ID, HTTPS gateway and random bootstrap code—no reusable credential. The
bootstrap row is bound to the Provider instance after creation, expires in ten
minutes and can be exchanged once. The resulting 15-minute token is scoped to
one Run/instance and is replaced on every 30-second heartbeat.

The worker resumes the Bundle with HTTP Range, verifies every hash and count,
checks the base-model id/revision/tree hash, trains from the immutable QLoRA
configuration, and streams adapter/log/metric files. It reports completion only
after the adapter is present and verified in central CAS. Its `finally` invokes
`/usr/bin/shutdown now`; Rust concurrently starts release and its reconciler
retries failures.

For a `routed_lora` Run the Worker additionally verifies the frozen expert
taxonomy and readiness, then trains Router, Shared and selected domain adapters
as separate artifacts. Rust verifies every inner artifact before registering
independently releasable candidates.

No Run completion publishes a model. It creates `MetaModelStatus::Candidate`;
the existing objective shadow replay, 10% canary, 24-hour/1,000-decision gate
and rollback policy remain unchanged.

## Operations

Copy `deploy/.env.example`, keep `CEREBELLUM_AUTODL_ENABLED=0`, and first build
the private application from `workers/meta-training`. Pin its exact application
version and deterministic base-model tree hash. Then configure the HTTPS worker
gateway, GPU allowlist and base-model allowlist before enabling the provider.

The admin console is available at `/admin` through the mTLS listener. It shows
acquisition and eligibility counts, Draft/Snapshot hashes and TrainingRuns. The
start confirmation repeats GPU, hourly limit, total limit and maximum duration.
For an opt-in real smoke test, use a separate low budget and a short synthetic
Snapshot; CI and normal development use the Fake AutoDL provider only.
[`scripts/autodl-smoke.ps1`](../scripts/autodl-smoke.ps1) requires both an
explicit switch and the phrase-valued `CEREBELLUM_REAL_AUTODL_SMOKE` guard
before it can call `:start`.
