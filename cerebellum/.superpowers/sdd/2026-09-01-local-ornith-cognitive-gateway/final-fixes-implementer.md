# Final fixes implementer report

## Status

**BLOCKED** — the code, deployment, documentation, and automated gates pass,
but the required refreshed LM Studio evidence is only 14/16 because an
unrelated local Python process continuously saturated the RTX 5090. The model
was unloaded after every attempt and remains unloaded.

## Implemented review fixes

- Compose now passes only the seven active local gateway variables. It defaults
  disabled while retaining the approved endpoint, model, artifact SHA, runtime,
  runtime version, and enforcement values. The environment example says to
  enable only when the daemon and runtime share one loopback namespace.
- `docker-compose.deepseek.yml` is a retired empty `services: {}` override with
  no secret and no service mutation. The existing loopback-only Rust endpoint
  validation was not changed. `docs/deployment-v2.md` already stated the same
  namespace restriction and therefore needed no edit.
- The admin label is `LOCAL ORNITH QUALITY GATE`; its quality status text now
  reports local zero-cost semantics without a DeepSeek or daily-CNY claim.
- Knowledge consolidation copies classification and external-processing
  provenance from the referenced `SourcePolicy` and fails closed when the
  policy is missing.
- KnowledgeCard quality loading resolves every evidence document with a
  `documents.source_policy_id -> source_policies` JOIN on the already-held
  SQLite connection. It selects `Private > Internal > Public` and
  `Denied > Redacted` without recursively locking the Registry.
- README, security documentation, and the quality source comment now state
  that clean scanner-safe authenticated-local content may use literal
  loopback; secret, PII, injection, invalid, timeout, and low-confidence paths
  fall back, while licence, safety, and quality gates retain training authority.
- Probe schema version is 3. Each response requires non-negative integral usage,
  rejects cached prompt tokens above prompt tokens, rejects inconsistent cache
  and total counts, maps cache hit/miss like the Rust client, defaults missing
  reasoning tokens to zero, records per-result token fields and aggregate token
  totals, and sets `usageValid=false` on every catch path. Its exit gate is
  `accepted == total && schemaValid == total && usageValid == total`; `exact`
  remains reported but non-gating.

## TDD evidence

Before production changes:

- `cleaned_authenticated_local_content_uses_model_but_secret_content_falls_back`
  failed with actual `Public`, expected `Private`.
- `knowledge_card_quality_subject_uses_most_restrictive_evidence_provenance`
  failed with actual `Public`, expected `Private`.

After the minimal fixes, both focused tests passed. The complete affected suites
also passed: knowledge 4, quality 13, router 8, API 36, and dataset factory 9.

## Deployment and static gates

- PowerShell 5.1 parser AST: pass.
- `docker compose ... config` for the base file: pass.
- `docker compose ... -f docker-compose.deepseek.yml config`: pass; the empty
  retired override does not change the service.
- `cargo fmt --all -- --check`: pass.
- `cargo clippy -p cerebellum-app --all-targets -- -D warnings`: pass.
- Active deploy/admin scan: no DeepSeek, legacy knowledge/quality model,
  pricing, training-opt-out, or hosted credential configuration remains.
- Active Rust/docs scan: only `config.rs` `#[cfg(test)]` legacy environment
  clearing and compatibility-test strings remain; no active hosted request.
- No modified deployment, admin, active documentation, probe, knowledge, or
  quality file contains `262144`/`262,144` as a default.
- Final `git diff --check` plus report/probe trailing-whitespace checks: pass.

## Full project gate

`powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1` exited 0:

- cerebellum-app: 262 passed, 0 failed, 2 ignored;
- cerebellum-core: 17 passed, 0 failed;
- Evolver: 746 passed, 7 skipped;
- monorepo validation, all worker suites, and the benchmark generator passed.

## Probe evidence and blocker

Required new evidence path:

`E:/projects/持续学习引擎/.coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-usage-probe.json`

Current failed-evidence SHA-256:

`873A0CC623F6EF587629860290B7442791819E1A15EC94E6D99B5136EED66952`

The schema-v3 fixed 16-call run recorded:

- total 16;
- accepted 14;
- schemaValid 14;
- usageValid 14;
- validJson 14;
- exact 10 (non-gating);
- promptTokens 3818;
- promptCacheHitTokens 0;
- promptCacheMissTokens 3818;
- completionTokens 5692;
- reasoningTokens 4838;
- totalTokens 9510;
- mean/median/max accepted latency 18519/18999/37258 ms;
- GPU: NVIDIA GeForce RTX 5090, 32607 MiB total.

The two failures were `bugfix-zh`, at 45015 ms and 45009 ms, both
`The request was aborted: The operation has timed out.` The preserved prior
16/16 evidence ran the same cases at about 23146/23154 ms. During the failed
run GPU utilization rose to 100%; after LM Studio unloaded, external process
PID 77456 (`python.exe`, started 2026-09-01 14:04:33) remained at 98-100% SM,
using 21964/32607 MiB. Six consecutive five-second samples and a five-minute
follow-up window stayed saturated. No user process was terminated and the
45-second fixed timeout was not weakened.

An earlier attempt reached all model calls but PowerShell 5.1 rejected
`Measure-Object -Property` on ordered-dictionary keys during summary creation.
It produced no evidence file and unloaded the model. A local minimal
reproduction confirmed the runtime behavior; aggregation was changed to
`ForEach-Object { $_.<token> } | Measure-Object -Sum`, then the AST passed.

Preserved immutable evidence hashes remain unchanged:

- `lm-studio-probe.json`:
  `7E9C34D1916CD3B4B74E2B4137439AD2707685D85BA0F829BCE8312BD10BDA77`;
- `lm-studio-ornith-json-schema-probe.json`:
  `A76B7DDBDE3B1452BCD4B2DF13753AC6C41AC988BD9E3EDED178020660D0CF89`.

Final `lms ps`: no models loaded. No files were staged, committed, reset,
stashed, or cleaned.
