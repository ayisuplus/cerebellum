# Task 7 implementer report

Task 7's documentation, strict-schema probe, successful GPU evidence and
cleanup are complete. The former formatting blocker was resolved in the
authorized follow-up described at the end of this report; all requested fresh
gates now pass.

## Changes

- Updated `README.md`, `docs/security.md`, `docs/protocol.md`, and
  `docs/deployment-v2.md` for the single pinned loopback Ornith model, the exact
  seven environment variables, strict JSON Schema, zero monetary model cost,
  deterministic authority and no hosted fallback.
- Added `docs/local-ornith-quality-v3.4.md` with screening/challenge semantics,
  calibration and human approval, deterministic gates and the explicit no
  weight-update boundary.
- Marked `docs/deepseek-quality-v3.3.md` historical and linked to v3.4 without
  removing its historical protocol.
- Updated `probe.ps1` with mandatory artifact/runtime pins, candidate-derived
  strict schema, exact property/type/boundary validation, `schemaValid`,
  accepted-plus-schema exit gating, GPU snapshots and Windows PowerShell 5.1
  compatible SHA-256/UTF-8 handling. The request timeout is 45 seconds, matching
  the implemented local client; the observed maximum call was 23,154 ms.
- Created `lm-studio-ornith-json-schema-probe.json` mechanically from the fixed
  16-call run. The previous `lm-studio-probe.json` was not modified.

## Pre-fix gate history

This section records the state before the authorized formatting follow-up. It
is retained as debugging history and is not the final gate status.

- `cargo fmt --all -- --check`: **FAIL**, exit 1. Rustfmt reported differences
  in `config.rs`, `lib.rs`, `local_model.rs`, `quality.rs`, and `router.rs`.
  Task 7 did not modify any Rust file and did not run formatting that would
  rewrite this pre-existing user work.
- `cargo clippy -p cerebellum-app --all-targets -- -D warnings`: **PASS**, exit
  0.
- `cargo test -p cerebellum-app --all-targets`: **PASS**, 261 passed, 0 failed,
  2 ignored; the remaining binary/example targets contained 0 tests and passed.
- Active-path scan for `DeepSeekClient`, `api.deepseek.com`,
  `DEEPSEEK_API_KEY`, and `CEREBELLUM_KNOWLEDGE_MODEL_API_KEY`: no runtime
  request/key path or active-document configuration. The only matches are the
  `#[cfg(test)]` environment clearing list and
  `legacy_deepseek_environment_does_not_enable_a_model` fixture in `config.rs`.

## LM Studio and GPU evidence

- LM Studio server was already running on port 1234; it was not started.
- Load command: `lms load ornith-1.5-9b --identifier ornith-1.5-9b --gpu max
  --context-length 4096 --parallel 1 --yes`.
- The load succeeded. The CLI also printed a non-fatal sandbox warning that it
  could not write `cli-pref.json`; this did not affect the command's exit code
  or model residency.
- `/v1/models` contained the exact ID `ornith-1.5-9b`.
- `lms ps` showed model `ornith-1.5-9b`, parallel 1, and actual context
  **262144**, despite requesting 4096. This remains the known LM Studio defect
  and is not documented as a default.
- Initial GPU snapshot before the first load: RTX 5090, 17,749 / 32,607 MiB,
  4% utilization. First loaded snapshot: 30,777 / 32,607 MiB.
- Successful evidence GPU snapshots: before calls 31,127 / 32,607 MiB at 0%;
  after calls 31,253 / 32,607 MiB at 76%.
- Final `lms unload ornith-1.5-9b`: **PASS**. `lms ps` reports no models loaded.
  Post-unload GPU: 15,719 / 32,607 MiB at 4%.

## Probe result

- Final command exit: **0**.
- `total=16`, `accepted=16`, `schemaValid=16`, `validJson=16`.
- Semantic baseline only: `exact=12`; it is not an exit gate.
- `reasoningFieldPresent=16`; no thinking option was requested and no reasoning
  content is persisted.
- Mean/median/max latency: 5,032 / 3,244 / 23,154 ms.
- Artifact pin:
  `894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da`.
- Runtime pin: `llama.cpp-win-x86_64-nvidia-cuda12-avx2` 2.31.2.
- Evidence SHA-256:
  `A76B7DDBDE3B1452BCD4B2DF13753AC6C41AC988BD9E3EDED178020660D0CF89`.
- Old evidence SHA-256 before and after:
  `7E9C34D1916CD3B4B74E2B4137439AD2707685D85BA0F829BCE8312BD10BDA77`.
- Final evidence sensitive/path scan: no drive path, home path, API key,
  password, secret, token or bearer value.

### Probe debugging record

1. The first attempt failed before HTTP because Windows PowerShell 5.1 lacks
   `SHA256.HashData`. The script now uses `SHA256.Create().ComputeHash()` and
   `BitConverter`; the input hash remained
   `7f5a04078e7ead6f137a622f46ae00e545b2b0670dc7fbda296df41e6bee7427`.
2. The second attempt failed before HTTP because Windows PowerShell 5.1 decoded
   the BOM-less UTF-8 input as ANSI. Explicit `-Encoding UTF8` parsed all eight
   cases without changing `probe-inputs.json`.
3. The first real 16-call run returned 14/16: both `bugfix-zh` calls timed out
   at 10,026 and 10,008 ms under `TimeoutSec 10`; the other 14 were schema
   valid. Aligning the probe with the client's 45-second timeout produced the
   final 16/16/16 result. The model was unloaded after every failed attempt.

## Pre-fix full-gate history

- `powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1`: **FAIL**,
  exit 1. It stopped at line 31 after the same `cargo fmt` differences and did
  not execute later suites. This failure was resolved by the authorized
  formatting follow-up below.
- `git diff --check`: **PASS**, exit 0; Git emitted existing LF-to-CRLF notices
  but no whitespace error.
- Final `git status --short` and `git diff --stat` retain the large pre-existing
  dirty tree. No reset, stash, stage or commit was performed.
- Final active source scan again found only the test-only legacy environment
  cleanup/disable fixture; there is no active provider request/key path.
- Final probe PowerShell AST parse: **PASS**.
- Final model residency check: **PASS**, no models loaded.

## Scope and remaining risks

The implementation scope contains these eight Task 7 artifact/document paths:

- `README.md`
- `docs/security.md`
- `docs/protocol.md`
- `docs/deployment-v2.md`
- `docs/local-ornith-quality-v3.4.md`
- `docs/deepseek-quality-v3.3.md`
- `../.coordination/work/lm-studio-ornith-compatibility/probe.ps1`
- `../.coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json`

The authorized follow-up additionally changed only rustfmt output in five Rust
files: `config.rs`, `lib.rs`, `local_model.rs`, `quality.rs`, and `router.rs`.
This report is the required implementation evidence. `probe-inputs.json`,
`defect.md`, and the old failed evidence remain unchanged. Existing README
coverage text and protocol learned-context text were preserved.

Remaining risks:

- LM Studio still ignores the requested 4096 context and allocates 262144,
  leaving very low GPU headroom during this probe.
- Semantic exactness is 12/16. The compatibility contract intentionally gates
  strict shape and accepted candidate identity, not semantic accuracy; exactness
  must not be described as 16/16.

## Authorized formatting follow-up

The primary agent reproduced the former blocker and authorized only the exact
pure-format hunks printed by `cargo fmt --all -- --check` in these five Task
1--5 files:

- `crates/cerebellum-app/src/config.rs`
- `crates/cerebellum-app/src/lib.rs`
- `crates/cerebellum-app/src/local_model.rs`
- `crates/cerebellum-app/src/quality.rs`
- `crates/cerebellum-app/src/router.rs`

Those hunks were applied manually with `apply_patch`. No write-mode `cargo
fmt`, bulk formatter, model load, stage, commit, reset or stash was used. The
changes are only rustfmt line wrapping and import/module ordering; no behavior
was changed.

Fresh post-fix gates:

- `cargo fmt --all -- --check`: **PASS**, exit 0.
- `cargo clippy -p cerebellum-app --all-targets -- -D warnings`: **PASS**, exit
  0.
- `cargo test -p cerebellum-app --all-targets`: **PASS**, 261 passed, 0 failed,
  2 ignored; binary/example targets also passed.
- `powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1`: **PASS**,
  exit 0. This included the Rust workspace (261 app tests plus 17 core tests),
  schema/corpus and monorepo validation, 746 Evolver/Python tests with 7
  skipped, worker suites, 209 tests plus 21 subtests, and benchmark generator
  tests.
- `git diff --check`: **PASS**, exit 0. Existing LF-to-CRLF notices remain
  informational and no whitespace error was reported.
- Active source scan remains limited to the `#[cfg(test)]` legacy environment
  clearing/disable fixture; there is no active DeepSeek request or key path.
- Successful probe evidence SHA-256 remains
  `A76B7DDBDE3B1452BCD4B2DF13753AC6C41AC988BD9E3EDED178020660D0CF89`;
  old evidence remains
  `7E9C34D1916CD3B4B74E2B4137439AD2707685D85BA0F829BCE8312BD10BDA77`.
- `lms ps` still reports no loaded models. No GPU action occurred during this
  follow-up.

## Authoritative final status

**FIXED_DONE** — the strict-schema probe and evidence pass, the model is
unloaded, and every requested fresh formatting, lint, app-test, full-project and
diff-check gate passes. Earlier FAIL entries above are pre-fix history only.
