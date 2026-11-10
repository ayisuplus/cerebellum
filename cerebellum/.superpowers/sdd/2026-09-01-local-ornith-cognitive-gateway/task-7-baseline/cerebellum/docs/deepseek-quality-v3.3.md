# v3.3 DeepSeek intelligent data-quality and synthesis factory

## Trust boundary

DeepSeek is a semantic reviewer and bounded data generator. It is not the
license authority, secret scanner, objective verifier, or release authority.
The effective training predicate is always:

```text
deterministic_training_eligible && quality_clear
```

Historical records default to `private` plus `denied`. A record is exported
only when it explicitly declares `external_processing=redacted`, passes the
local secret/PII/prompt-injection scan, and receives an immutable
`RedactionAttestation`. Authenticated OpenCLI content, cookies, login state,
whole private repositories, and raw private trajectories are never eligible.

Private redacted records additionally require both
`CEREBELLUM_PRIVATE_REDACTED_EXTERNAL_PROCESSING=1` and the administrator's
account-level opt-out attestation. No request can contain tools or an external
URL. HTTP redirects are disabled. Reasoning content is discarded before the
response reaches the Registry.

## Review lifecycle

Flash reviews every newly eligible record. Confidence below `0.85`, a non-pass
verdict, an objective disagreement, or the deterministic 5% sample schedules a
Pro review. Privacy leakage or prompt injection forces quarantine. A Flash/Pro
disagreement is not silently resolved in favor of Flash.

Every exact `(model, system_fingerprint, prompt, schema)` version is recorded.
The first fingerprint is unusable until a named administrator approves it.
Later fingerprints enter calibration/shadow state and cannot satisfy
`quality_clear` while pending. Thus model drift pauses new Draft promotion but
does not affect the previous Draft, deterministic knowledge retrieval, or hard
workflow gates.

The client requests JSON Object mode and then applies local strict deserialization,
enum, length, score, usage, and hash validation. Empty, truncated, invalid, or
tool-calling output is rejected. Neither final JSON nor a model recommendation
can turn a deterministic denial into an eligible record.

## Budget ledger

Every call first reserves a conservative cache-miss/input and maximum-output
cost in one SQLite transaction. Usage settlement records Flash/Pro calls,
cache-hit/miss tokens, output/reasoning tokens, micro-USD, and a conservative
`8.0 CNY/USD` conversion. New reservations stop at 10 CNY per Shanghai day.
The versioned official price confirmation expires after 30 days, which fails
closed until an operator confirms current prices again.

The API key is read from `DEEPSEEK_API_KEY_FILE` first. In deployment, mount a
read-only Docker secret at `/run/secrets/deepseek_api_key`; never add the key to
the Compose environment, Registry, CAS, command line, traces, or admin page.

## Synthetic records

Only a quality-cleared original decision or replay can be a generation parent.
Generation depth is exactly one, so synthetic records cannot recursively create
more records. The candidate records the parent hash, transformation, model and
fingerprint, prompt hash, token/cost usage, evidence references, and immutable
content hash.

Every generated candidate receives a Pro review. Executable-test, gate-replay,
and paired-replay candidates still require the corresponding objective verifier
before automatic `verified` status. Semantic candidates remain quarantined until
a human approves them. Human approval itself requires an active passing Pro
assessment.

Dataset construction applies the 20% cap per task and split. Excess candidates
remain in the candidate ledger and are not deleted.

## Build and training gates

With quality enforcement configured, building creates an immutable candidate
Build but does not update `DatasetDraft`. The Build includes only records that
already have an effective active assessment. A Pro audit deterministically
samples `min(total, min(500, max(50, ceil(5%))))` records. The Draft pointer
moves only if coverage is 100%, unresolved arbitration and deterministic
violations are zero, generated ratio is at most 20%, severe misses are zero,
and non-safety disagreement is at most 2%.

A failed report is immutable. Repairing data produces a new Build. Existing
Snapshots remain readable after enabling v3.3, but a new TrainingRun requires a
Snapshot bound to a passing report ID and hash.

## Minimal enablement

1. Mount the DeepSeek key as a Docker secret.
2. Confirm current official pricing and set `DEEPSEEK_PRICING_CONFIRMED_AT` to
   an RFC3339 timestamp.
3. Confirm the provider account's model-improvement setting and input rights.
4. Enable the quality model and scheduler.
5. Submit or backfill only explicitly redacted records.
6. Review the first Flash and Pro fingerprints in `/admin`.

Use the opt-in Compose override so deployments with quality disabled do not
require a placeholder secret:

```bash
docker compose -f deploy/docker-compose.yml \
  -f deploy/docker-compose.deepseek.yml up -d
```

If DeepSeek, its budget, or model calibration is unavailable, new review jobs
remain pending/retryable. The previous Draft stays available and no unreviewed
record is admitted as a fallback.
