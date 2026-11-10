# v3.4 local Ornith quality and synthesis

## Runtime boundary

Cerebellum uses one optional local OpenAI-compatible model for workflow
routing, weak KnowledgeCard extraction, data-quality review and bounded
synthetic-candidate generation. The approved pins are:

```text
CEREBELLUM_LOCAL_MODEL_ENABLED=1
CEREBELLUM_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:1234/v1
CEREBELLUM_LOCAL_MODEL_NAME=ornith-1.5-9b
CEREBELLUM_LOCAL_MODEL_SHA256=894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da
CEREBELLUM_LOCAL_MODEL_RUNTIME=llama.cpp-win-x86_64-nvidia-cuda12-avx2
CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION=2.31.2
CEREBELLUM_QUALITY_ENFORCEMENT=1
```

The endpoint accepts only literal IPv4 or IPv6 loopback HTTP roots, optionally
ending in `/v1`. Requests have no API key, proxy, redirect, tools, thinking
option, public address or hosted fallback. `/v1/models` must expose the exact
configured model identity before completion requests are accepted.

Every call uses `response_format.type=json_schema` with `strict=true` and a
request-specific bounded schema. The client rejects missing or invalid JSON,
tool calls, truncation, oversized responses and identity mismatch. It retries
only transport or HTTP 5xx failure, once.

## Quality lifecycle

`Flash` and `Pro` remain the persisted stage names for compatibility. They are
not different providers or models:

- `Flash` is the first screening pass for each deterministically eligible
  record.
- `Pro` is a challenge/arbitration pass for low-confidence, disagreeing,
  sampled or synthetic records and for Build audits.

Both stages use the same pinned Ornith model. Local calls settle at zero
monetary cost while retaining stage, model identity, fingerprint, prompt/cache/
completion token counts and the existing audit evidence. Each completed local
structured call records `latency_ms` in the structured-call trace. The fixed
smoke probe separately persists per-call latency and its mean/median/maximum
summary in the probe JSON evidence. These use the existing trace and probe
artifacts; no database column or migration is added. Historical hosted usage
and assessments are not rewritten.

The fingerprint binds model name, GGUF SHA-256, runtime name/version, system
prompt and response-schema hash. A first fingerprint requires named human
approval. Drift enters calibration/shadow state and cannot satisfy
`quality_clear` until its fixture, safety, quality and shadow evidence passes
and an administrator approves it.

## Deterministic authority

Loopback inference is a processing location, not an authority. Licence,
credential, PII, prompt-injection, private-output echo, deterministic
eligibility, objective verification, dataset audit, human approval, activation
and rollback gates remain authoritative and fail closed. Model output may veto
or quarantine but cannot turn a deterministic denial into an eligible record.
Routing failures fall back to deterministic BM25.

Synthetic generation is depth one, lineage-bound and non-recursive. Executable
or replayable candidates still require objective verification; semantic
candidates require human approval and an active passing challenge assessment.
A Build advances the Draft immediately; the Pro-stage sample report is
enforced later as a hard gate at snapshot freeze.

This lifecycle does not update Ornith weights. Dataset creation, adapter
training, model promotion and activation remain separate, explicitly approved
workflows with their existing evaluation and rollback gates.
