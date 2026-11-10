# v3.2 request-routed LoRA experts

## Why this is MoE-ready instead of a native FFN MoE

Cerebellum uses request-level Top-1 routing over independent LoRA adapters on
one frozen 1--3B base model. The first taxonomy is:

- `retrieval`: relevance, noise filtering, deduplication and ranking;
- `evidence`: claim support, contradiction and provenance;
- `acquisition`: crawl escalation, curriculum priority and information gain;
- `skill_workflow`: Skill and Workflow routing/evolution;
- `shared`: cross-domain, ambiguous, negative-transfer and out-of-distribution
  fallback.

This preserves the useful sparse-compute property without introducing a custom
token-level FFN runtime or training a large collection of experts from scratch.
Initial training is not expected to be cheaper than one Dense LoRA run: it
trains a router, the shared fallback and selected experts. The cost advantage
appears later, when one expert can be rebuilt, evaluated, deployed or rolled
back independently.

Dense LoRA remains a permanent baseline and failure fallback. Deterministic
hard policy remains outside every model and adapter.

The frozen training base is pinned to `Qwen/Qwen2.5-1.5B` (Apache-2.0, strong
CJK, standard pretrained base, not a third-party continued-training artifact —
so engine contribution stays attributable). Ornith-1.5-9B remains only the
local structured-inference model and a comparison arm. Cerebellum's research
artifact is the closed-loop engine and its evidence chain, not a replica of any
weight file: base substitutability (Ornith/Qwen/OLMo) is exactly how that claim
is tested — the thesis holds if the engine can continuously improve a standard
clean base, while fine-tuning on someone else's continued-training artifact
makes uplift unattributable and proves nothing. Once an adapter activates, the
serving base must match the training base (switching the inference endpoint is
an operations step after the first adapter passes the promotion gate, out of
scope for this document). Training from scratch is rejected: flywheel output is
fine-tuning grade (meta gate at 5,000 decisions + 1,000 replay records,
`dataset_factory/meta_training.rs`), the compute budget is a single on-demand
24GB QLoRA GPU, and the repository contains no pretraining code path.

## Dataset construction

Every daily `DatasetBuild` now contains two compatible views in the same
deterministic tar Bundle:

1. the original dense `dataset-manifest.json` and split shards;
2. `expert-dataset-manifest.json`, `expert-assignments.jsonl` and purpose-bound
   shards under `experts/`.

An `ExpertAssignment` records the record hash, original split, selected expert,
secondary candidates, confidence and one of `assigned`, `ambiguous`,
`out_of_distribution` or `negative_transfer`. Assignment never changes a
record's source-domain/topic-family split. All records enter the shared view;
assigned records additionally enter exactly one domain view. Ambiguous, OOD
and negative-transfer records enter an explicit routing-negative view and do
not contaminate domain experts.

The router view contains positive routes plus an oversampled copy of routing
negatives. The split is still decided before expert assignment, so no expert
can leak a repository/topic family from train into validation or holdout.

Formal routed training requires at least 5,000 router train records and, for
every selected domain expert, 1,000 train records plus 200 replay records from
validation/holdout (training-split replay does not count). Drafts below those
limits remain valid data products but are marked
not ready. A frozen Snapshot binds the expert view, taxonomy hash, Manifest
hash and Bundle hash.

## Training and artifacts

`CreateTrainingRunRequest.expert_plan` opts into `routed_lora`. Rust checks the
plan against the frozen Snapshot and expert taxonomy before the Run exists and
again at `:start`. The AutoDL Worker verifies both Manifests, every compressed
and uncompressed shard hash, assignment hash/count, readiness thresholds and
the immutable base-model pin.

For an initial full Run the Worker trains adapters in this order:

```text
router -> shared fallback -> selected domain experts
```

`train_router`, `train_shared`, and `expert_ids` are independent. A later Run
may therefore train only `retrieval` (or another domain expert) while reusing
the active Router and Shared versions. At least one adapter must be selected.

It uploads one deterministic outer tar containing independent adapter archives
and `cerebellum-routed-adapter-manifest.json`. Rust streams the tar, rejects
links, devices, traversal, duplicate or unreferenced paths, verifies each inner
hash/length and checks the exact Run/Snapshot/view/taxonomy/expert set before
registering candidates.

No completion activates an adapter. Router, shared and domain adapters have
independent `candidate -> shadow -> canary -> active` state. Canary and
activation require objective metrics: no policy or injection regression, at
least 98% old-task retention, no task-success decline, no negative-transfer
increase and no routing-accuracy decline. Canary entry requires at least 200
independent evaluations; activation additionally requires a report covering
24 hours and 1,000 canary decisions. Activating a new version supersedes
only that expert's previous version; rollback restores it without changing the
other experts. Active adapters under one taxonomy must share the exact frozen
base-model pin; a mixed-base expert set is rejected.

## Runtime behavior

`POST /v1/experts:route` and the `cerebellum_route_expert` MCP tool return a
single expert, active adapter references and whether shared or dense fallback
was used. Secrets and prompt-injection markers route to the shared policy path.
If the mapped expert is unavailable, the active shared adapter is used. If no
safe active adapter exists, `dense_fallback=true` and the permanent
deterministic/dense controller remains authoritative.

The deterministic router is the runtime baseline in this milestone. An active
learned router is versioned and exposed in the decision, but it cannot override
the deterministic safety fallback or hard gates.

Promotion-gate metrics for `canary` and `activate` come from recorded
`run-adapter-eval` evidence: a local dual-arm llama.cpp evaluation of the
frozen base GGUF against the merged base+adapter GGUF over the frozen
Snapshot's validation/holdout shards plus pinned injection probes. The
request must name a stored report with matching adapter/base-model/snapshot/
view/taxonomy identity; the canary decision count and duration dimensions are
still recomputed from the server-side routing stream and are never taken from
the evidence file. Reports are listed at
`GET /v1/expert-adapter-eval-reports?expert_id=...&version=...`.

## Operator surfaces

HTTP:

- `GET /v1/expert-taxonomy`
- `GET /v1/expert-dataset-views`
- `GET /v1/expert-dataset-views/{id}`
- `GET /v1/expert-dataset-views/{id}/assignments`
- `POST /v1/experts:route`
- `GET /v1/expert-adapters?expert_id=...`
- `GET /v1/expert-adapters/{expert}@{version}`
- `POST /v1/expert-adapters/{expert}@{version}:shadow|:canary|:activate|:reject|:rollback`
- `GET /v1/expert-adapter-eval-reports?expert_id=...&version=...`

CLI:

- `list-expert-views`
- `route-expert REQUEST.json`
- `list-expert-adapters [--expert-id ID]`
- `review-expert-adapter ID VERSION ACTION --actor NAME --reason TEXT [--metrics FILE] [--eval-report-id UUID]`
- `run-adapter-eval PLAN.json [--record]`

The `/admin` console shows expert readiness, allows Dense versus Routed LoRA
selection before creating a Run, and lists independently versioned adapters.
