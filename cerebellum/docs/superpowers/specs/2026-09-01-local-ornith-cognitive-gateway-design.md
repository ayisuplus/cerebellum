# Local Ornith Cognitive Model Gateway Design

- **Date:** 2026-09-01
- **Status:** Approved design
- **Scope:** First implementation package only

## Purpose

Replace the DeepSeek runtime dependency with the locally hosted
Ornith-1.5-9B-GGUF model while preserving Cerebellum's deterministic and human
authority boundaries.

This package establishes one local model service for routing, structured
knowledge extraction, semantic quality review, and synthetic-data generation.
It does not yet connect completed work to an experience-learning loop, generate
a self-directed curriculum, or update model weights.

## Context

Cerebellum already contains the durable control-plane mechanisms needed around
a model: deterministic gates, structured requests, quality assessments,
calibration, shadow review, approval records, knowledge storage, and audit
records. DeepSeek is currently a provider-specific implementation behind some
of those mechanisms. The shortest safe change is to reuse those mechanisms and
replace only the provider boundary.

The current LM Studio compatibility probe also found a concrete protocol
mismatch: Cerebellum sends `response_format.type=json_object`, while the tested
LM Studio runtime accepts `json_schema` or `text`. All structured local-model
requests therefore use strict JSON Schema.

The approved local artifact is:

- Model: Ornith-1.5-9B-GGUF Q4_K_M
- Artifact SHA-256:
  `894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da`
- Artifact size: 5,780,090,816 bytes
- Storage: one hard-linked payload shared by Ollama and LM Studio

## Authority Model

Ornith may propose, solve, criticize, distill, and select curriculum material.
It may participate in every semantic stage, but it cannot certify its own
output as trusted.

Authority remains split as follows:

```text
Ornith
  -> routing / generation / reflection / semantic review / distillation

Cerebellum
  -> storage / retrieval / scheduling / deduplication / state / datasets

Deterministic gates and humans
  -> tests / builds / policy / licence / privacy / promotion / rollback
```

Objective validation may promote a candidate. A result supported only by the
model's own judgment remains quarantined. Secrets, unlicensed material, or a
self-generated sample without an objective verifier cannot become trusted
knowledge. Model output cannot override a Rust denial.

## Components and Interfaces

### Existing interface

Keep the existing `StructuredModelClient`, `StructuredRequest`, and
`StructuredResponse` boundary. Do not introduce a new cognitive-engine layer,
factory, or role framework.

Logical roles are represented by the existing request stage, prompt version,
subject kind, and schema. A new `ModelRole` abstraction is unnecessary for this
package.

### Local structured client

Replace `DeepSeekClient` with one generic
`OpenAiCompatibleStructuredClient`. It calls the local
`/v1/chat/completions` endpoint and sends a strict `json_schema` response
format. Knowledge extraction, quality review, and synthesis reuse this client.

The existing router may retain its router-specific request construction, but
it must use the same local model configuration and the same strict-schema
contract. This avoids a broad router rewrite while ensuring that one physical
Ornith model performs every semantic role.

### Configuration

Use one `LocalModelConfig` source for all model-backed stages:

- literal loopback endpoint;
- API model name;
- expected GGUF SHA-256;
- runtime name and version;
- request timeout and existing prompt/schema versions.

Do not retain DeepSeek domain, API-key, pricing, or deployment configuration.
Do not add provider discovery or automatic external fallback.

The client derives a stable audit fingerprint from the expected model name,
GGUF SHA-256, runtime identity, prompt version, and schema version. A local
server's optional `system_fingerprint` is supplementary and is not the source
of truth. The configured model name must agree with the local `/v1/models`
identity before learning or quality output can be accepted.

The application does not hash the 5.78 GB artifact for every request. The
verified import hash is pinned in configuration and audit records; a separate
operator action is responsible for changing the artifact or runtime.

## Request and Data Flow

```text
typed request
  -> existing privacy and input scans
  -> role-specific prompt plus JSON Schema
  -> local Ornith endpoint
  -> strict response parsing and schema validation
  -> deterministic task-specific gates
  -> audit record
  -> accepted, quarantined, rejected, or deterministic fallback
```

Routing uses a schema whose values are limited to the supplied candidate set.
Knowledge, quality, and synthesis retain their existing task-specific schemas
and validation. A successful model response is evidence, not approval.

## Local Processing and Security

Only literal `127.0.0.1` and `::1` endpoints are accepted. Hostnames, public
addresses, proxies, and HTTP redirects are rejected so that a nominally local
configuration cannot silently transfer data elsewhere.

Loopback inference does not require the external-processing permission. It
still passes through the existing credential, PII, prompt-injection, and
licensing checks and records the input hash and redaction attestation. The
change does not weaken those checks or create a raw-credential path.

## Failure Behaviour

- A transport failure, timeout, or server 5xx is retried at most once.
- Schema, model-identity, privacy, licensing, or prompt-injection failures are
  not retried.
- There is no DeepSeek or other hosted-model fallback.
- Router failure uses the existing deterministic routing fallback.
- Knowledge extraction, reflection, quality review, or synthesis failure does
  not block returning an otherwise valid task result, but it cannot create or
  promote knowledge.
- Failed objective verification may be stored as a failure episode, but it
  cannot enter the trusted knowledge set.
- If the audit write fails, the result cannot be marked accepted.
- Application-side request and response budgets remain bounded regardless of
  the context size advertised by the runtime.

LM Studio 1.3.3 with the tested llama.cpp runtime ignored the requested 4,096
context and reported 262,144, consuming substantially more VRAM. Until that
runtime defect is resolved or explicitly accepted, the package must not
silently make that LM Studio configuration the default service. LM Studio can
still be used for the approved compatibility smoke test.

## Historical Data and Compatibility

No destructive database migration is needed:

- existing DeepSeek assessments and provider/model strings remain unchanged;
- generic quality, calibration, shadow, approval, and usage tables remain;
- new records use the local provider identity and combined Ornith fingerprint;
- new monetary cost is zero while token counts and latency remain audited;
- `Flash` and `Pro` database enum values remain for compatibility and are
  interpreted for new local work as initial screening and challenge review;
- historical scores are not recalculated or relabelled;
- old DeepSeek environment variables are no longer read, and no compatibility
  adapter or secret migration is added.

## Verification

### Automated checks

- Accept literal IPv4 and IPv6 loopback endpoints; reject hostnames, public
  addresses, and redirects.
- Assert strict `json_schema` request construction and response validation.
- Assert one retry for transport/5xx and no retry for schema, security, or
  identity failures.
- Assert deterministic router fallback when the model is unavailable.
- Assert that failed knowledge and quality calls cannot promote results.
- Assert that the combined fingerprint is stable and changes when the artifact
  hash or runtime version changes.
- Assert local quality records have zero monetary cost but retain tokens,
  latency, stage, and model identity.
- Run against a fixture containing historical DeepSeek rows and prove those
  rows are unchanged.
- Prove no executable DeepSeek request path or API-key requirement remains.
- Pass the existing Cerebellum checks relevant to the touched Rust package and
  the full project gate if the narrow checks pass.

### Local GPU smoke test

Use the existing fixed 16-case probe with the approved Ornith Q4_K_M artifact.
Acceptance requires:

- 16/16 HTTP-success responses;
- 16/16 responses parsed against their strict JSON Schema;
- no public-network model request;
- recorded runtime identity, artifact SHA-256, token counts, latency, and GPU
  use.

Semantic agreement is recorded as a baseline rather than used as a gateway
acceptance threshold. Prompt tuning and routing-quality optimization are not
part of this provider-boundary package.

## Non-goals

This package does not:

- connect completed runs to `WorkEpisode` ingestion;
- implement the self-generated curriculum loop;
- fine-tune or otherwise update model weights;
- add a second judge model;
- delete or rewrite historical DeepSeek rows or migration names;
- refactor unrelated quality, knowledge, routing, or training code;
- activate a production service or allocate the GPU without separate approval.

## Completion Boundary

The package is complete when the same pinned local Ornith service can satisfy
all existing structured model-call roles through the OpenAI-compatible
contract, failure cannot produce trusted knowledge, historical data remains
intact, the scoped automated checks pass, and the fixed local compatibility
probe produces the required evidence.

The next separately approved package will connect real completed work to an
auditable experience and knowledge loop. The self-generated curriculum loop
comes after that real-work loop is measurable.
