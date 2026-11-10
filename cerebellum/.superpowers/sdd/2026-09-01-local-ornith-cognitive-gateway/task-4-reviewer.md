# Task 4 independent review

## Verdict

- Spec compliance: **PASS**.
- Code quality: **APPROVED (conditional on Task 5 completing the planned API wiring)**.

The current crate-level compilation failure at `crates/cerebellum-app/src/api.rs:64` is the ruled, out-of-scope four-argument constructor call. Task 5 owns its replacement with the shared client; Task 4 must neither edit `api.rs` nor add a compatibility constructor. It is therefore not a Task 4 defect.

## Evidence reviewed

- `OpenAiCompatibleRouter` holds exactly `Arc<Registry>` and `Arc<dyn StructuredModelClient>` and is constructed as `new(registry, client)` (`crates/cerebellum-app/src/router.rs:105-113`).
- Routing goes through `complete_budgeted` at `QualityModelStage::Flash` (`router.rs:139-161`), preserving the usage/registry path.
- The payload contains only the planned schema, task, context, capabilities, and candidates; it omits `repository_path` and other `DecisionRequest` fields (`router.rs:146-152`).
- The dynamic top-level schema is strict: candidate IDs form `workflow_id.enum`; confidence is `0..1`; reasons are arrays of at most four nonempty strings of at most 200 characters; all three fields are required and additional properties are disallowed (`router.rs:128-138`).
- Response parsing rejects absent/wrong-typed candidate, confidence, and reasons values; candidate IDs must match supplied workflows; confidence additionally retains the pre-existing `0.25..=1.0` acceptance threshold; reasons reject excess, non-string, empty, and oversize values (`router.rs:162-194`).
- Any structured-client/model error propagates from `rank`, so the unchanged `rank_with_fallback` takes the deterministic BM25 path (`router.rs:202-230`). The fallback test remains present (`router.rs:372-385`).
- The router no longer imports or uses `reqwest`, endpoints, API keys, bearer auth, or direct HTTP. The delta is limited to `router.rs` and its scoped test.
- The new fake client captures the real structured request and returns a 64-character fingerprint with zeroed, internally consistent `ModelTokenUsage` (`router.rs:302-325`); the test verifies a candidate-bounded schema and `Flash` stage (`router.rs:387-416`).

## Findings

No P0-P2 findings. No tests were run, per the review assignment; Task 5 must rerun the Task 4 router test suite after its compile wiring change.
