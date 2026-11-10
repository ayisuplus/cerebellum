# Task 5 Implementer Report

Status: DONE

## Scope and assumptions

- Modified source files only: `config.rs`, `quality.rs`, `knowledge.rs`, `scheduler.rs`, and `api.rs` under `crates/cerebellum-app/src`.
- Did not modify `router.rs`, add dependencies, add a factory/compatibility constructor, stage, commit, reset, stash, or start the daemon/scheduler/application.
- Preserved Task 6 ownership of external-processing semantics. The record/source permission comparisons remain in `quality.rs`, `knowledge.rs`, and `api.rs`.
- The working tree and all five target files were already dirty. Scoped `git diff --stat` therefore includes pre-existing user changes and is not an implementation-only size measurement.

## Baseline hashes

| File | Before SHA-256 | After SHA-256 |
|---|---|---|
| `config.rs` | `468133AFC33E1A165DEFAA8F108C030C1770D3D0A9F14E865ACCAE8BFC75303A` | `D984D74A903F906BDE26CF0FD03B5ED34551CDF5D89ED8AFC00C466E04734021` |
| `quality.rs` | `8FA08F1A8421BDD42C66C7538B55E12D1E80CA876E293202AAFEA3996D1F0A6D` | `75C5E499653A8F64CFDB6BC973AD10AA348ED33567ACE6029DEA0191F85F8E96` |
| `knowledge.rs` | `F7765DA8E104BF92089D8AB6A8ADE7E633B82AFF3234FA0865741AF51ABCCE9F` | `8694B40AC846F4082136AD59C701C042B60DAF18A21CCE61022CB755C285E0D2` |
| `scheduler.rs` | `24813D5F90A1D7251B3CCF0456E82F06893655F9F349CFA8082786B47F688F6F` | `6C78DFEBF43B0310722C60090EB4EA4E70C9F7590A4727A7966A836537643AE7` |
| `api.rs` | `6B28AE1966E2D2410BEA74B469143008BE0339178913685C1942A245026A12F3` | `E62F43FD254BE4352B5812DD22C81EA0B2501623BCAE64F0F1D57D819B414D94` |

## TDD RED

Added first:

- `config::tests::legacy_deepseek_environment_does_not_enable_a_model`
- `api::tests::local_model_is_shared_by_router_and_scheduler_without_constructor_http`
- `api::tests::state()` assertions for deterministic routing and `structured_model == None` when `local_model == None`

Observed RED:

1. `cargo test -p cerebellum-app config::tests::legacy_deepseek_environment_does_not_enable_a_model -- --nocapture` exited 1.
2. `cargo check -p cerebellum-app --all-targets` exited 1.

Expected failures:

- `api.rs:64`: Task 4 changed `OpenAiCompatibleRouter::new` from the legacy four hosted-provider arguments to `(Arc<Registry>, Arc<dyn StructuredModelClient>)`.
- Two test compile errors: `AppState.structured_model` did not exist.

No production implementation was added before these failures were observed.

## GREEN implementation

- `config.rs`: removed active router/model/knowledge/quality hosted fields, `QualityModelConfig`, and `load_quality_model_config`; retained one `local_model` loader. Legacy DeepSeek environment names remain only in the `#[cfg(test)]` clearing list and boundary test.
- `api.rs`: constructs one `OpenAiCompatibleStructuredClient`, shares the same trait object with `OpenAiCompatibleRouter` and the scheduler, uses deterministic routing when disabled, derives enforcement/status/backfill conditions from the local model, and removed startup pricing persistence.
- `quality.rs`: deleted `DeepSeekClient`, hosted envelopes/messages/usage parsing, bearer-auth HTTP code, fake DeepSeek server, and its two client tests. `assess_subject` no longer accepts provider configuration. Status uses `LocalModelConfig`, local provider identity, the same model for storage-compatible Flash/Pro fields, and filters active versions by local provider. A `#[cfg(test)]` historical provider constant remains because the out-of-scope `dataset_factory.rs` historical fixture references it.
- `knowledge.rs`: deleted `KnowledgeModelConfig`, duplicate direct reqwest client, hosted fallback, and its HTTP test. Structured extraction now uses `output_schema`; deterministic fallback remains.
- `scheduler.rs`: reduced the loop/one-shot execution path to one optional shared structured client, chooses structured or deterministic knowledge consolidation, and uses `local structured model is unavailable` errors.
- `api.rs` record-level external-permission comparisons and the equivalent quality/knowledge checks remain unchanged for Task 6.

## Fresh verification

Final fresh run after all edits:

| Command | Result |
|---|---|
| `cargo test -p cerebellum-app config::tests -- --nocapture` | PASS, 15/15 |
| `cargo test -p cerebellum-app local_model::tests -- --nocapture` | PASS, 4/4 |
| `cargo test -p cerebellum-app router::tests -- --nocapture` | PASS, 7/7 |
| `cargo test -p cerebellum-app knowledge::tests -- --nocapture` | PASS, 3/3 |
| `cargo test -p cerebellum-app quality::tests -- --nocapture` | PASS, 11/11 |
| `cargo test -p cerebellum-app scheduler::tests -- --nocapture` | PASS, 6/6 |
| `cargo test -p cerebellum-app api::tests -- --nocapture` | PASS, 36/36 |
| `cargo check --all-targets` | PASS, exit 0 |
| Task 4 deferred GREEN: `cargo test -p cerebellum-app router::tests -- --nocapture` | PASS, 7/7 |
| scoped `git diff --check` for the five target files | PASS, exit 0 |

The first aggregate API test run failed because the new helper asserted the obsolete display name `deterministic`; the real existing `DeterministicRouter::name()` is `deterministic-bm25`. Correcting that test expectation made the API suite pass 36/36; no production behavior changed for this correction.

## Hosted-path deletion proof

Command:

```text
rg -n "DeepSeekClient|api\.deepseek\.com|DEEPSEEK_API_KEY|DEEPSEEK_API_BASE_URL|bearer_auth" \
  crates/cerebellum-app/src/config.rs crates/cerebellum-app/src/quality.rs \
  crates/cerebellum-app/src/knowledge.rs crates/cerebellum-app/src/scheduler.rs \
  crates/cerebellum-app/src/api.rs
```

Remaining matches are all in `config.rs` after its line 309 `#[cfg(test)]` boundary:

- lines 334-336: historical environment clearing names
- lines 464-465: the legacy-environment regression test

There is no production match in the five Task 5 files. The plan's repository-wide broad `bearer_auth` scan also finds pre-existing non-model authentication in `collector.rs` and `mcp.rs`; those are unrelated acquisition/MCP token paths outside Task 5 and were not changed.

Explicit removed-symbol scan for `QualityModelConfig`, `load_quality_model_config`, `DeepSeekClient`, `KnowledgeModelConfig`, `consolidate_document_with_model_fallback`, and `extract_with_model` across the five files returned no matches.

## Risks and deferred work

- No daemon/scheduler/application runtime was started, per the Tasks 3-5 atomic-window constraint. Verification is compile/unit-test based only.
- Task 6 must still change the local interpretation of external-processing permission. This task deliberately retained every current comparison.
- Historical DeepSeek rows/tests remain. Production cannot load hosted credentials or issue the removed model HTTP requests.
- Line-ending warnings state Git may convert LF to CRLF on a future Git write; scoped `git diff --check` is clean.
- Because the five files contained substantial pre-existing user edits, no staging or commit was attempted.
