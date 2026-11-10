# Task 3 Independent Review

Scope reviewed: frozen Task 3 brief, Global Constraints, implementer report, review-package delta, and read-only `quality.rs` call/transaction context. No tests were run.

## Spec compliance: PASS

- `LOCAL_MODEL_PROVIDER` and the three active Ornith version strings match the plan (`quality.rs:30-39`).
- New reservations are local with `reserved_microusd = 0`, retain the transaction and request-ID idempotency path, and settle local calls with zero cost while recording stage/token totals (`quality.rs:1934-2073`).
- Settlement reads the reservation provider first; non-local reservations query and validate that stored provider's pricing before cost calculation (`quality.rs:1985-2039`). Local ledger reads do not require pricing and report `estimated_cny = 0.0` (`quality.rs:2076-2130`).
- New model-version creation and active lookup use the local provider, leaving existing version rows untouched; the regression test verifies historical DeepSeek `version_json` bytes remain unchanged (`quality.rs:1079-1146`, `quality.rs:2302-2388`).
- No schema migration or public API shape change appears in the supplied delta. Persisted `Flash`/`Pro` values and the temporary DeepSeek client remain untouched, as required for this checkpoint.

## Code quality: APPROVED

No P0-P2 actionable issues found. The implementation is a minimal, transaction-preserving change. The implementer-reported scoped lifecycle check passed: 13 passed, 0 failed.
