# Task 3 implementer checkpoint

## RED

Added the local zero-cost ledger and historical endpoint JSON tests before production changes.

`cargo test -p cerebellum-app quality::tests::local_usage_records_tokens_with_zero_cost -- --nocapture`
initially failed to compile because `LOCAL_MODEL_PROVIDER` did not yet exist. This is the missing public local-provider contract; the pre-existing reservation path also still required DeepSeek pricing.

## GREEN

The same focused test passed after the minimal implementation. The scoped lifecycle check also passed:

`cargo test -p cerebellum-app quality::tests -- --nocapture`

Result: 13 passed, 0 failed.

## Change summary

- New local usage reservations store `local-openai-compatible` with zero reserved/spent cost while retaining token accounting.
- Historical non-local settlement and ledger conversion still load that provider's stored pricing.
- New endpoint records, quality status usage, and dataset audit usage use the local provider; existing rows are not changed.
- Active quality policy/prompt/synthetic versions now identify the local Ornith mode.

## Historical compatibility evidence

`registering_local_identity_does_not_rewrite_historical_deepseek_rows` passed. It inserts a serialized DeepSeek endpoint row, registers a local identity, and asserts the original `version_json` bytes are unchanged.

## Checkpoint

`git diff --check -- crates/cerebellum-app/src/quality.rs` completed with no whitespace errors (Git emitted only the pre-existing LF-to-CRLF warning).

SHA-256: `8FA08F1A8421BDD42C66C7538B55E12D1E80CA876E293202AAFEA3996D1F0A6D`

## Remaining risk

Tasks 3–5 remain an uncommitted switchover. The temporary DeepSeek client/configuration stays in place for Task 5; no daemon, scheduler, or application was started.
