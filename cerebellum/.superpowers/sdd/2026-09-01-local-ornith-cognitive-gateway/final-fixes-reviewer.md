# Final fixes static review

**Static spec: PASS**

**Static quality: APPROVED**

**Runtime evidence: BLOCKED**

The four findings in `final-reviewer.md` are closed at the code, deployment and
documentation layers. No new P0-P2 static finding was found. Package completion is
still blocked because the reviewed third candidate evidence is a failed 14/16 run, not
the required refreshed 16/16/16/16 evidence.

## Static finding closure

1. **Deployment/provider boundary — closed.**
   - `deploy/docker-compose.yml:13-19` passes exactly the enabled flag, endpoint,
     model, artifact SHA-256, runtime, runtime version and quality-enforcement
     variables. It no longer passes legacy knowledge/quality provider variables,
     DeepSeek URL/key/model, pricing or opt-out configuration.
   - `deploy/.env.example:10-18` exposes the same seven variables, defaults the gateway
     off and states the shared-loopback-namespace precondition.
   - `deploy/docker-compose.deepseek.yml:1-3` is a retired empty compatibility override:
     it defines no secret and cannot mutate the service. The literal-loopback Rust
     validation was not weakened.
   - `admin/index.html:73-76` and `admin/app.js:37-38` identify the local Ornith gate and
     local zero-cost semantics; the hosted daily-CNY wording is gone.

2. **Knowledge and quality provenance — closed.**
   - `crates/cerebellum-app/src/knowledge.rs:340-342` resolves the document's referenced
     `SourcePolicy` before recording a trace and fails closed if it is missing;
     `crates/cerebellum-app/src/knowledge.rs:384-392` preserves the source
     classification and external-processing permission.
   - `crates/cerebellum-app/src/quality.rs:1949-1951` acquires the Registry SQLite lock
     once. The KnowledgeCard branch performs direct JOIN queries through that already
     held connection at `crates/cerebellum-app/src/quality.rs:2031-2055`, so it does not
     recursively lock the Registry. A missing evidence document or source policy makes
     `query_row` fail closed.
   - The reducer implements `Private > Internal > Public` and
     `Denied > Redacted` across every evidence document. The regression covers all
     classification levels and both permission levels and asserts `Private`/`Denied`.

3. **Probe usage contract — closed statically.**
   - `E:/projects/持续学习引擎/.coordination/work/lm-studio-ornith-compatibility/probe.ps1:50-117`
     requires the three core usage fields, accepts only finite non-negative integral
     values convertible to `uint64`, resolves cache hits from the direct field before
     nested `cached_tokens`, derives a missing cache miss, rejects cache inconsistency,
     and requires `total = prompt + completion`.
   - For accepted inputs, prompt/cache/completion/total mapping agrees with the Rust
     `CompletionUsage -> ModelTokenUsage` mapping. The probe safely rejects inconsistent
     cache input that Rust would clamp or later reject. Probe `reasoningTokens` is
     supplementary provider evidence; the current local Rust mapping deliberately
     records that ledger field as zero, so the two reasoning fields must not be claimed
     to be identical.
   - `probe.ps1:229-260` aggregates only `usageValid` results using the PowerShell 5.1
     compatible `ForEach-Object { ... } | Measure-Object -Sum` form. Every catch result
     has null token fields and `usageValid=false`; `probe.ps1:263-266` writes the
     artifact and exits non-zero unless accepted, schema-valid and usage-valid counts
     all equal total. Semantic `exact` remains reported and non-gating.

4. **Documentation drift — closed.**
   - `README.md:174-178`, `docs/security.md:55-69` and the source comment at
     `crates/cerebellum-app/src/quality.rs:2062-2064` now agree: clean scanner-safe
     authenticated-local content may use literal loopback, unsafe/invalid/timeout/
     low-confidence paths fall back, and licence/safety/quality gates retain training
     authority.

## Static findings

### P0

None.

### P1

None.

### P2

None.

## Runtime evidence blocker

The reviewed candidate
`E:/projects/持续学习引擎/.coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-usage-probe.json`
with SHA-256
`873A0CC623F6EF587629860290B7442791819E1A15EC94E6D99B5136EED66952`
reports `total=16`, `accepted=14`, `schemaValid=14`, `usageValid=14` and
`validJson=14`. Both `bugfix-zh` calls timed out at the fixed 45-second boundary while
an unrelated Python process saturated the GPU. This honestly captured failed artifact
must not be treated as final acceptance evidence.

Runtime evidence remains **BLOCKED** until a fresh idle-GPU run using the unchanged
probe and pins produces a new immutable artifact with at least:

- `total=16`;
- `accepted=16`;
- `schemaValid=16`;
- `usageValid=16`;
- `validJson=16`;
- recorded runtime/artifact/GPU/latency/token evidence;
- a published new SHA-256; and
- no loaded model after the run.

`exact` remains a non-gating semantic baseline.

## Preserved evidence

Read-only SHA-256 verification confirms that the two pre-existing evidence files were
not changed:

- `lm-studio-probe.json`:
  `7E9C34D1916CD3B4B74E2B4137439AD2707685D85BA0F829BCE8312BD10BDA77`;
- `lm-studio-ornith-json-schema-probe.json`:
  `A76B7DDBDE3B1452BCD4B2DF13753AC6C41AC988BD9E3EDED178020660D0CF89`.

## Review basis

This reviewer performed only static/read-only inspection of the repair package and
current relevant files. No test, probe or model was run. The implementer's reported
green automated gates support the static approval but do not override the failed
candidate evidence. No staging, commit, reset or cleanup is requested or authorized in
the dirty normal-`main` checkout.
