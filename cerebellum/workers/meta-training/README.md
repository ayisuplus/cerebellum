# Cerebellum AutoDL Training Worker

The v3.1 worker runs as a pinned **private AutoDL application**, using native
Python. It is not a long-running Docker service and never receives the root
`CEREBELLUM_AUTH_TOKEN`, the AutoDL developer token, a general CAS credential,
or a Hugging Face token.

The AutoDL start command contains only a ten-minute, one-use bootstrap code
bound to a `TrainingRun`. The code is exchanged for a 15-minute scoped token;
every 30-second heartbeat rotates that token. Its routes can only:

- download the current Run's immutable Bundle, with Range resume;
- send the current Run's heartbeat;
- stream the current Run's adapter, metrics, and redacted log artifacts;
- complete or fail the current Run.

The worker verifies the Bundle, Manifest, every `JSONL.zst` shard, the pinned
base-model id/revision/tree hash, CUDA, and at least 24 GiB VRAM. It uploads all
outputs before reporting completion. Rust registers a `candidate` model only;
the worker cannot publish it. Its `finally` block invokes
`/usr/bin/shutdown now`; the control plane also powers off and releases the
AutoDL instance and retries during reconciliation.

For a Run with `expert_plan.architecture=routed_lora`, the same Bundle includes
an expert Manifest. The worker verifies assignment/readiness and all
Shared/Router/routing-negative/domain shards, trains a Top-1 router plus the
shared fallback and selected domain adapters, and uploads one deterministic tar
with per-adapter SHA-256 values. `train_router`, `train_shared`, and
`expert_ids` can select a single adapter for a later low-cost refresh. Rust
re-verifies the tar and registers each adapter as an independent candidate.
Dense LoRA remains the default-compatible path when `expert_plan` is absent.

Private application settings (values are examples, not defaults):

```text
META_BASE_MODEL_ID=org/public-1b-model
META_BASE_MODEL_REVISION=<full immutable revision>
META_BASE_MODEL_SHA256=<deterministic tree hash>
META_BASE_MODEL_PATH=/root/autodl-tmp/base-model  # optional preloaded copy
META_MODEL_ID=cerebellum-meta-controller
META_MODEL_VERSION=0.1.0
META_TRAINER_ENABLED=1
META_DATA_LICENSE_POLICY=licensed-only
```

Do not configure `HF_TOKEN`, `AUTODL_API_TOKEN`, or
`CEREBELLUM_AUTH_TOKEN` in the application. If no preloaded path is supplied,
the model must be publicly downloadable at the pinned revision.
Generate the configured tree hash inside the finalized private application with
`cerebellum-model-tree-hash /absolute/model/path`.

The generated launch command is:

```bash
python -m cerebellum_meta_training.remote_worker \
  --gateway https://worker.example.com:8445 \
  --run-id <uuid> --bootstrap-code <one-use-code>
```

The former `worker.py` queue consumer is retained for protocol compatibility
tests, but v3.1 never schedules `meta_train_v1` and the central deployment no
longer contains a GPU worker service.

Run contract tests without a GPU:

```bash
python -m unittest discover -s tests -v
```
