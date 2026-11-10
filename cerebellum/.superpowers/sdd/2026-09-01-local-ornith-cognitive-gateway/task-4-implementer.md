# Task 4 implementer checkpoint

Status: DONE_DEFERRED_GREEN

## Scope

- Modified only `crates/cerebellum-app/src/router.rs`.
- Preserved its pre-existing user changes (baseline SHA-256: `1F6631AA44A134076CA8450691CA022CD5AD81420330570F8FB39DF60DA7C331`).
- Final SHA-256: `ACF567A0E4C33BE22B0083EDBB29069B58855645B8891479D655AC747C39134E`.

## RED evidence

Added `router::tests::local_router_uses_candidate_bounded_schema` with a fake `StructuredModelClient`. It captures the real `StructuredRequest`, returns a bounded selection and zero-cost default usage with a 64-character fingerprint.

`cargo test -p cerebellum-app router::tests::local_router_uses_candidate_bounded_schema -- --nocapture` failed as expected before implementation:

```
error[E0061]: this function takes 4 arguments but 2 arguments were supplied
... router.rs ... OpenAiCompatibleRouter::new(registry, client)
```

## Minimal change

- Replaced direct reqwest routing state and request construction with `Arc<Registry>`, `Arc<dyn StructuredModelClient>`, and `complete_budgeted`.
- Sends a strict request payload whose output schema limits `workflow_id` to supplied candidate IDs; confidence is `0..1`; reasons have bounded count and strings.
- Retains the local confidence threshold, candidate-ID lookup, and now validates reasons fail-closed. Router identity is `local-openai-compatible`.
- Kept `RouterModel`, `rank_with_fallback`, BM25, and deterministic fallback unchanged.

## GREEN deferral and risk

After the required constructor change, the only compile failure is the known Task 5 call site:

```
error[E0061]: this function takes 2 arguments but 4 arguments were supplied
... crates/cerebellum-app/src/api.rs:64
```

Task 4 is explicitly forbidden from changing `api.rs` or adding a compatibility constructor, so router-suite GREEN is deferred until Task 5 performs the shared-client API wiring. The controller must rerun:

```
cargo test -p cerebellum-app router::tests -- --nocapture
```

`git diff --check -- crates/cerebellum-app/src/router.rs` passed (only Git's pre-existing LF-to-CRLF warning was emitted).
