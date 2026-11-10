# Local Ornith Cognitive Gateway — final cross-task review

**Overall spec: FAIL**

**Overall quality: CHANGES_REQUESTED**

The core Rust integration is coherent, but the package is not complete against the
approved design. Three cross-task defects remain: the supported container deployment
cannot receive the local-model configuration and still carries active DeepSeek
configuration, the immutable smoke evidence omits required token-usage evidence, and
knowledge/quality provenance is misclassified after authenticated-local inference was
enabled.

## Findings

### P0

No P0 findings.

### P1

1. **The Compose deployment cannot enable the gateway and still provisions the retired hosted provider.**
   - **Files:** `deploy/docker-compose.yml:13-25`, `deploy/.env.example:10-26`,
     `deploy/docker-compose.deepseek.yml:1-8`, `docs/deployment-v2.md:49-66`,
     `admin/index.html:73-76`.
   - **Evidence:** the documented `CEREBELLUM_LOCAL_MODEL_ENABLED`, endpoint, model,
     artifact and runtime pins are absent from the Compose service's explicit
     `environment` map. `--env-file` supplies Compose substitutions; it does not inject
     unreferenced variables into this service. The same active deployment surface still
     exposes the legacy knowledge-model variables, DeepSeek URL/key file, model names,
     budget/pricing variables, secret mount and UI label. This conflicts with the
     design's explicit removal requirement at
     `docs/superpowers/specs/2026-09-01-local-ornith-cognitive-gateway-design.md:90-99`.
   - **Impact:** the documented container path silently leaves the single local client
     disabled, while operators are still prompted to configure a hosted credential.
     Although current Rust cognitive code no longer consumes those legacy variables,
     the deployment contract is both unusable for the new gateway and misleading about
     the active provider boundary.
   - **Minimal fix:** replace the legacy cognitive-provider entries in the Compose and
     environment example with the exact seven local gateway variables; retire the
     DeepSeek override/secret mount from the active deployment; rename the admin label.
     Keep the existing requirement that the daemon and model runtime share a loopback
     network namespace—do not weaken endpoint validation to make container networking
     easier.

2. **The compatibility probe and immutable evidence omit the required token usage.**
   - **Files:**
     `E:/projects/持续学习引擎/.coordination/work/lm-studio-ornith-compatibility/probe.ps1:107-122`,
     `E:/projects/持续学习引擎/.coordination/work/lm-studio-ornith-compatibility/probe.ps1:145-169`,
     `E:/projects/持续学习引擎/.coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json:1`.
   - **Evidence:** the probe reads selection output and `reasoning_content`, but never
     reads `response.usage`; neither each result nor the summary contains prompt,
     cache-hit/cache-miss, completion or total tokens. The design requires recorded
     token counts alongside runtime identity, artifact hash, latency and GPU use at
     `docs/superpowers/specs/2026-09-01-local-ornith-cognitive-gateway-design.md:196-205`.
   - **Impact:** the 16/16 compatibility gate cannot substantiate the runtime usage
     contract or reconcile the zero-cost ledger's token accounting. The supplied
     artifact is valid evidence for HTTP/JSON/schema compatibility, but not the complete
     smoke evidence required by the spec.
   - **Minimal fix:** record per-response OpenAI usage fields, including cached-token
     detail when present, normalize/validate them using the same invariants as the Rust
     client, and add aggregate token totals. Re-run the fixed probe into a **new**
     immutable evidence file and publish its new SHA-256; preserve both existing
     evidence files and hashes.

3. **Authenticated-local source policy is replaced by false public/redacted provenance.**
   - **Files:** `crates/cerebellum-app/src/knowledge.rs:332-389`,
     `crates/cerebellum-app/src/knowledge.rs:755-801`,
     `crates/cerebellum-app/src/quality.rs:1914-1925`,
     `crates/cerebellum-app/src/knowledge_store.rs:146-151`,
     `crates/cerebellum-app/src/dataset_factory.rs:1094-1118`.
   - **Evidence:** Task 6 intentionally allows clean `AuthenticatedLocal` content with
     `Private` classification and `Denied` external processing to use the loopback
     model, as the regression test shows. Nevertheless, the resulting meta trace is
     hard-coded to `Public`/`Redacted`, and loading the resulting KnowledgeCard as a
     quality subject repeats the same hard-coded values under a comment that is now
     factually false. `Registry::get_source_policy` is already available, while dataset
     selection later trusts the stored trace after its licence/safety/quality gates.
   - **Impact:** the deterministic eligibility and safety gates are not bypassed, but
     the auditable ledger can misstate the sensitivity and processing permission of
     private evidence. A source policy that separately permits training can therefore
     yield training evidence with incorrect provenance, undermining the package's
     security and rollback audit contract.
   - **Minimal fix:** resolve `document.source_policy_id` when recording the trace and
     copy its `data_classification` and `external_processing` fields. When building a
     KnowledgeCard quality subject, derive a conservative value from its evidence source
     policies (most restrictive if several sources contribute) instead of hard-coding
     public/redacted. Extend the authenticated-local regression to assert the persisted
     trace and quality-subject provenance.

### P2

1. **User-facing security documentation still says authenticated-local content always falls back.**
   - **Files:** `README.md:174-177`, `docs/security.md:55-67`,
     `crates/cerebellum-app/src/quality.rs:1921-1923`.
   - **Impact:** operators and reviewers are given two contradictory trust-boundary
     descriptions, and the source comment contributed directly to the provenance defect
     above.
   - **Minimal fix:** state that safe, cleaned authenticated-local content may use the
     literal-loopback client, while prompt injection, PII, secrets, invalid output,
     timeout and low confidence still force deterministic fallback. Keep training
     eligibility explicitly separate and under licence/safety/quality gates.

## Cross-task conclusions

- `LocalModelConfig` is loaded once and one shared
  `OpenAiCompatibleStructuredClient` is constructed in `AppState`; the same client flows
  through the router and scheduler into knowledge, quality/challenge and synthesis.
  Synchronous construction performs no HTTP.
- The client is fail-closed at literal loopback HTTP, with no credentials, proxy,
  redirects, public fallback, tools or thinking parameters. Identity preflight, exact
  response-model checks, one retry for transport/5xx only, bounded bodies, strict
  task-level schema validation and derived audit fingerprints are mutually consistent.
- Local calls retain token accounting with zero monetary cost. Historical provider
  versions/pricing remain readable, while the active version set is local-only; legacy
  Flash/Pro storage names map to the one configured model rather than introducing a
  second runtime client.
- Local inference does not bypass deterministic eligibility, licence, scanner,
  output-echo, approval, dataset, activation or rollback gates. The provenance defect
  above is an audit-integrity failure, not a demonstrated gate bypass.
- The active Rust cognitive path contains no hosted-provider request. DeepSeek
  environment strings in `config.rs` are test-only legacy-disable coverage; the active
  deployment remnants are covered by P1 finding 1. Historical API rows remain readable.
- The current evidence correctly reports `total=16`, `accepted=16`,
  `schemaValid=16`, `validJson=16`, and `exact=12`. Documentation does not inflate this
  to semantic 16/16, does not set 262144 as an application default, and does not claim
  that this provider-boundary package updates model weights.
- The runtime implementation reuses the existing shared client/usage/quality boundary;
  no additional P0-P2 Ponytail/YAGNI abstraction finding was found.

## Verification basis

This reviewer performed static, read-only inspection and did not run tests, probes or
models. The controller's fresh verification reports `scripts/test-all.ps1` exit 0;
Rust app 261 passed/0 failed/2 ignored, core 17 passed; Python/Evolver 746 passed/7
skipped; worker and benchmark gates passed; `lms ps` showed no loaded model; and
`git diff --check` exited 0. The reviewed evidence hashes match:

- new evidence:
  `A76B7DDBDE3B1452BCD4B2DF13753AC6C41AC988BD9E3EDED178020660D0CF89`;
- preserved older evidence:
  `7E9C34D1916CD3B4B74E2B4137439AD2707685D85BA0F829BCE8312BD10BDA77`.

Those green gates do not close the three P1 contract defects above.

## Remaining known risks

- **262144 context:** the runtime can expose this model limit, but the application must
  continue using its bounded request defaults; the observed high-context setting is not
  an application default or a memory-safety guarantee.
- **Exact 12/16:** schema/transport compatibility is 16/16, while semantic agreement is
  only 12/16. This is an explicitly non-blocking baseline for this package, not evidence
  of perfect routing quality.
- **Uncommitted mixed tree:** the checkout is normal `main`, ahead of its remote and very
  dirty with mixed user work. Nothing should be staged or committed automatically.

After the findings are fixed and the scoped gates/evidence are refreshed, present the
user with integration choices for the existing checkout; do not auto-stage, auto-commit,
reset or clean the tree.
