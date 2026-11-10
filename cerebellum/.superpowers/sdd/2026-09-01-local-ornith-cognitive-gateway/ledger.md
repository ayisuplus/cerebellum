# SDD ledger — plan: docs/superpowers/plans/2026-09-01-local-ornith-cognitive-gateway.md

## Execution rulings

- Work in the current checkout. The approved source of truth includes extensive uncommitted user changes, so a clean worktree would silently omit them.
- Never reset, stash, stage, or commit. The plan explicitly defers commits; every review uses a task-start file snapshot instead of a commit range.
- Run only the task-scoped tests during Tasks 3–5. Do not start the daemon or scheduler until the atomic switchover is complete.
- Use the smallest existing abstraction: one `StructuredModelClient`, no new dependency, factory, or cognitive-engine layer.

## Preflight consistency

| Scope | Result | Ruling |
|---|---|---|
| Task 1 | clean | Establishes `LocalModelConfig` and `AppConfig.local_model`. |
| Task 2 | clean | Consumes Task 1 config and implements the existing structured-client contract. |
| Task 3 | clean | Preserves historical rows while making new local usage zero-cost. |
| Task 4 | clean | Reuses the shared structured-client interface and deterministic fallback. |
| Task 5 | clean | Atomic wiring/removal step; no daemon start before completion. |
| Task 6 | clean | Local processing does not bypass existing scanners or deterministic gates. |
| Task 7 | clean | Documents and probes the completed contract; the 262k context defect is not made a default. |
| Tasks 1 ↔ 5 | ordered | Task 1 adds local config; Task 5 removes the hosted provider fields after consumers switch. |
| Tasks 2 ↔ 5 | ordered | Task 2 creates the client; Task 5 shares one instance across active call paths. |
| Tasks 2 ↔ 7 | ordered | Task 7 probes the strict schema and identity contract implemented by Task 2. |
| Tasks 3 ↔ 5 | atomic | No application start between accounting changes and hosted-client removal. |
| Tasks 3 ↔ 7 | ordered | Task 7 verifies/document zero-cost evidence after accounting is wired. |
| Tasks 4 ↔ 5 | ordered | Router API lands before construction and scheduler wiring change. |
| Tasks 4 ↔ 6 | ordered | Privacy behavior is verified only after the shared router path exists. |
| Tasks 5 ↔ 6 | ordered | Local permission semantics are changed after all active paths are local. |
| Tasks 5 ↔ 7 | ordered | Documentation describes only the final active topology. |
| Tasks 6 ↔ 7 | ordered | Security documentation follows the verified fail-closed behavior. |

## Task log

### Task 1 — local-model configuration boundary

- State: complete.
- Repository HEAD: `339c42f2d12000ea58c4c27af0c93bb47c69ff7e` (reference only; no commits will be made).
- Baseline `config.rs`: `53E642D79D7FC4B9508EC0EC16534316478B3F75742510AF2324B1874F73564F`.
- Baseline `api.rs`: `A6301D53F6DEF9657E51DAF9A2578AFD753FE7C2FBC42C25739E259F1D65ED41`.
- Baseline verification: `cargo test -p cerebellum-app config::tests -- --nocapture` → 19 passed, 0 failed.
- Implementation verification: focused local-model config tests → 2 passed; config suite → 21 passed; scoped `git diff --check` passed.
- Review loop: initial review rejected broad IPv4 `127/8`; TDD fix now compares exactly with `Ipv4Addr::LOCALHOST` and rejects `127.0.0.2`.
- Final review: Spec compliance PASS; Code quality APPROVED.

### Task 2 — strict local OpenAI-compatible client

- State: complete.
- Baseline `lib.rs`: `F426C8416B5112F71B0635A292F8C33E707FAD742ED9513F660452DB800104C4`.
- Baseline `local_model.rs`: absent (represented by an empty snapshot file).
- Baseline verification: `cargo test -p cerebellum-app router::tests -- --nocapture` → 6 passed, 0 failed.
- Implementation verification: local-model tests → 4 passed; strict clippy passed; scoped `git diff --check` passed.
- Final review: Spec compliance PASS; Code quality APPROVED; no P0–P2 findings.

### Task 3 — local zero-cost usage and historical compatibility

- State: complete.
- Atomic-switchover rule active: no daemon or scheduler start through Task 5.
- Baseline `quality.rs`: `CC32F239D3AC29A9335B5404B3DC4BBE65E02C799FBFD2D925171B3E5854F72D`.
- Baseline verification: `cargo test -p cerebellum-app quality::tests -- --nocapture` → 12 passed, 0 failed.
- Implementation verification: quality suite → 13 passed; scoped `git diff --check` passed.
- Final review: Spec compliance PASS; Code quality APPROVED; historical provider pricing and JSON preservation confirmed.

### Task 4 — shared structured router

- State: complete with deferred GREEN.
- Atomic-switchover rule remains active: no daemon or scheduler start.
- Baseline `router.rs`: `1F6631AA44A134076CA8450691CA022CD5AD81420330570F8FB39DF60DA7C331`.
- Baseline verification: `cargo test -p cerebellum-app router::tests -- --nocapture` → 6 passed, 0 failed.
- Implementation checkpoint: scoped `git diff --check` passed; crate compile is intentionally blocked only by the old `api.rs` four-argument constructor owned by Task 5.
- Review: Spec compliance PASS; Code quality APPROVED conditional on Task 5 wiring and post-wiring router-suite GREEN.

### Task 5 — atomic application switchover

- State: complete.
- Ruling: Task 5 must clear the known Task 4 `api.rs` constructor failure before any service start; all affected module tests are the atomic GREEN checkpoint.
- Baseline `config.rs`: `468133AFC33E1A165DEFAA8F108C030C1770D3D0A9F14E865ACCAE8BFC75303A`.
- Baseline `quality.rs`: `8FA08F1A8421BDD42C66C7538B55E12D1E80CA876E293202AAFEA3996D1F0A6D`.
- Baseline `knowledge.rs`: `F7765DA8E104BF92089D8AB6A8ADE7E633B82AFF3234FA0865741AF51ABCCE9F`.
- Baseline `scheduler.rs`: `24813D5F90A1D7251B3CCF0456E82F06893655F9F349CFA8082786B47F688F6F`.
- Baseline `api.rs`: `6B28AE1966E2D2410BEA74B469143008BE0339178913685C1942A245026A12F3`.
- Baseline `cargo check -p cerebellum-app --all-targets`: failed only at `api.rs:64` old four-argument router constructor (expected Task 4→5 boundary).
- Implementation verification: config 15/15, local client 4/4, router 7/7, knowledge 3/3, quality 11/11, scheduler 6/6, API 36/36; `cargo check --all-targets` and scoped `git diff --check` passed.
- Hosted-path audit: no active hosted cognitive-model path remains; legacy DeepSeek strings survive only in test clearing/history, and unrelated collector/MCP bearer auth is unchanged.
- Final review: Spec compliance PASS; Code quality APPROVED; no P0–P2 findings.

### Task 6 — loopback-local privacy semantics

- State: complete.
- Atomic Tasks 3–5 window is closed after full GREEN; service remains stopped until Task 7 runtime probe.
- Baseline `quality.rs`: `75C5E499653A8F64CFDB6BC973AD10AA348ED33567ACE6029DEA0191F85F8E96`.
- Baseline `knowledge.rs`: `8694B40AC846F4082136AD59C701C042B60DAF18A21CCE61022CB755C285E0D2`.
- Baseline `router.rs`: `ACF567A0E4C33BE22B0083EDBB29069B58855645B8891479D655AC747C39134E`.
- Baseline `api.rs`: `E62F43FD254BE4352B5812DD22C81EA0B2501623BCAE64F0F1D57D819B414D94`.
- Baseline `dataset_factory.rs`: `E1D53AF0406EEAB24A056DD8E05BB9708BFA0DD81030AA503B1B345D1E740281`.
- Baseline behavior: all affected suites passed at the Task 5 atomic checkpoint.
- Implementation verification: quality 12/12, knowledge 4/4, router 8/8, API 36/36, dataset factory 9/9; scoped `git diff --check` passed.
- Integration ruling: updated only the `#[cfg(test)]` dataset fixture provider/model identity after local-only active-version filtering exposed the stale DeepSeek fixture; production selection is unchanged.
- Final review: Spec compliance PASS; Code quality APPROVED; all deterministic/scanner/licence/approval gates preserved.

### Task 7 — documentation and fixed local GPU evidence

- State: implementation in progress.
- User authorization: local LM Studio/RTX 5090 model load, 16-call probe, evidence write, and unload were explicitly approved earlier.
- Baseline `README.md`: `72E6558CA0A4F72A4546990FA47DE84FB2679C8F1A89E8F674F8E473360B1F4B`.
- Baseline `docs/security.md`: `9330980E2FD125815EB60FA04268D9E88E84B6DB8523B29F712A5783DC4F0537`.
- Baseline `docs/protocol.md`: `82E3CCBFA5B5EC614A65ECE55925B2EA22B083E131CEFF3E7A90D82A228CA493`.
- Baseline `docs/deployment-v2.md`: `74612883D273CC762266920F4A4BCF3EED3C053FAE4BC98219C3DAA34C2FEC34`.
- Baseline `docs/deepseek-quality-v3.3.md`: `66B22965A73F68E7DA2DEE0E55EDD4551A2378E1ED43DCE945FF834AE09F2FA3`.
- Baseline `docs/local-ornith-quality-v3.4.md`: absent (empty snapshot).
- Baseline `probe.ps1`: `964BDC294CBC77EE6A2B1DFB5B7542C80548697B2A07BE7C484FD3C742D2252A`.
- Baseline strict-schema evidence file: absent (empty snapshot); prior `lm-studio-probe.json` remains immutable.
- Tool availability: `lms.exe` and `nvidia-smi.exe` found locally.

### Final cross-task correction

- State: implementation in progress after final review requested changes.
- Final-review findings: container deployment still carried retired DeepSeek variables; smoke evidence omitted token usage; authenticated-local provenance was hard-coded as public/redacted; README/security/comment text still described the pre-Task-6 fallback rule.
- Ruling: fix these as one bounded integration correction. Preserve both existing probe evidence files and generate `lm-studio-ornith-json-schema-usage-probe.json` as the new immutable usage-complete artifact.
- User authorization for the repeat local GPU probe remains in force; always unload the model after the attempt.
