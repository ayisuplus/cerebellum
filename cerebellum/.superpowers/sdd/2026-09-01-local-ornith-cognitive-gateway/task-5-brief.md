### Task 5: Atomically switch application wiring and remove active DeepSeek paths

**Files:**
- Modify: `crates/cerebellum-app/src/config.rs:35-260, 391-860`
- Modify: `crates/cerebellum-app/src/quality.rs:1-1478, 2530-2620, 3235-3305`
- Modify: `crates/cerebellum-app/src/knowledge.rs:1-198, 368-451, 655-930`
- Modify: `crates/cerebellum-app/src/scheduler.rs:1-370`
- Modify: `crates/cerebellum-app/src/api.rs:24-105, 313-340, 1194-1220, 3957-4015, 4335-4425`

**Interfaces:**
- `AppConfig` produces one `local_model: Option<LocalModelConfig>`.
- `AppState` produces one `structured_model: Option<Arc<dyn StructuredModelClient>>` shared by router and scheduler.
- `scheduler::run_loop(registry, github_token, structured_model)` consumes no provider-specific configuration.
- `quality::assess_subject(registry, client, target)` consumes no paid-provider configuration.
- Knowledge consolidation consumes either the shared structured client or deterministic extraction; the duplicate direct HTTP path is removed.

- [ ] **Step 1: Add failing application-wiring assertions**

Update the `AppConfig` test fixtures and add:

```rust
#[test]
fn legacy_deepseek_environment_does_not_enable_a_model() {
    let env = EnvGuard::cleared();
    env.set("DEEPSEEK_API_KEY", &"k".repeat(32));
    env.set("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com");
    let config = AppConfig::load(tempdir().unwrap().path().join("data"), loopback()).unwrap();
    assert!(config.local_model.is_none());
}
```

Update `api::tests::state()` to expect a deterministic router and `structured_model=None` when `local_model=None`. Add a constructor test with a valid local config and fake loopback endpoint that asserts `router.name()=="local-openai-compatible"` and `structured_model.is_some()` without making an HTTP call during the synchronous constructor.

- [ ] **Step 2: Run focused compilation to expose all old wiring**

Run:

```powershell
cargo test -p cerebellum-app config::tests::legacy_deepseek_environment_does_not_enable_a_model -- --nocapture
cargo check -p cerebellum-app --all-targets
```

Expected: failures name old `quality_model`, router model, knowledge-model, and `DeepSeekClient` fields/callers.

- [ ] **Step 3: Collapse `AppConfig` to one local model**

Remove these active fields and loaders:

```text
router_backend
model_endpoint
model_name
model_api_key
knowledge_model_endpoint
knowledge_model_name
knowledge_model_api_key
quality_model
QualityModelConfig
load_quality_model_config
```

Add `pub local_model: Option<LocalModelConfig>` and call `load_local_model_config()` from `AppConfig::load`. Remove DeepSeek/API-key/pricing/external-provider variables from production reads. Keep their names only in the test environment clearing list and historical tests.

- [ ] **Step 4: Construct and share one local client in `AppState`**

Replace `quality_model` with `structured_model`. Build it once:

```rust
let structured_model: Option<Arc<dyn StructuredModelClient>> = config
    .local_model
    .clone()
    .map(OpenAiCompatibleStructuredClient::new)
    .transpose()?
    .map(|client| Arc::new(client) as Arc<dyn StructuredModelClient>);
let router: Arc<dyn RouterModel> = match structured_model.clone() {
    Some(client) => Arc::new(OpenAiCompatibleRouter::new(registry.clone(), client)),
    None => Arc::new(DeterministicRouter),
};
```

Remove startup pricing-policy persistence. Set quality enforcement from `config.local_model.enforcement_required`. Pass `structured_model.clone()` to the scheduler.

- [ ] **Step 5: Delete the active DeepSeek client and make quality configuration local**

Delete `DeepSeekClient`, `DeepSeekEnvelope`, choices/messages/usage types, provider thinking options, bearer auth, and provider-specific HTTP errors from `quality.rs`; their replacement is `local_model.rs`.

Delete the `fake_deepseek` server fixture and the two DeepSeek HTTP-client tests
from `quality.rs`; Task 2's local-client tests retain the retry, strict output,
redirect, tool-call, response-size, and token-parsing coverage.

Remove `QualityModelConfig` from `assess_subject`/`assess_subject_inner`. For this task, retain the existing deterministic eligibility, export scanner, external-permission check, echo scanner, calibration, approval, and promotion behavior; Task 6 changes only the local external-permission interpretation.

Change `quality_status` to take `Option<&LocalModelConfig>`, report
`provider=LOCAL_MODEL_PROVIDER`, put the same configured `model` into the
storage-compatible `flash_model` and `pro_model` fields, and include only
`version.provider == LOCAL_MODEL_PROVIDER` in `active_model_versions`.
The separate model-version list endpoint continues to expose historical rows.

- [ ] **Step 6: Remove the duplicate knowledge HTTP client**

Delete `KnowledgeModelConfig`, `consolidate_document_with_model_fallback`, `extract_with_model`, and their reqwest/API-key imports/tests. Rename the structured payload key from `schema` to `output_schema` so the shared client can send it as strict JSON Schema. Keep `consolidate_document` as the deterministic fallback.

- [ ] **Step 7: Simplify scheduler signatures and errors**

Use these final signatures:

```rust
pub async fn run_loop(
    registry: Arc<Registry>,
    github_token: Option<String>,
    structured_model: Option<Arc<dyn StructuredModelClient>>,
)

async fn run_once_with_model(
    registry: &Registry,
    worker: &str,
    github_token: Option<&str>,
    structured_model: Option<&dyn StructuredModelClient>,
) -> Result<Option<(Uuid, String)>>
```

For `knowledge_consolidate_v1`, use structured consolidation when the client exists and deterministic consolidation otherwise. For quality, synthesis, and calibration jobs, report `"local structured model is unavailable"`; never name or invoke DeepSeek.

- [ ] **Step 8: Update API conditions and user-facing errors**

Replace `state.config.quality_model.is_some()` with `state.structured_model.is_some()`. Update status to use `state.config.local_model.as_ref()`. Change backfill errors to `"local quality model is disabled"`. Do not yet remove the record-level external-processing comparisons; Task 6 owns that trust-boundary change.

- [ ] **Step 9: Compile and run all affected Rust modules**

Run:

```powershell
cargo test -p cerebellum-app config::tests -- --nocapture
cargo test -p cerebellum-app local_model::tests -- --nocapture
cargo test -p cerebellum-app router::tests -- --nocapture
cargo test -p cerebellum-app knowledge::tests -- --nocapture
cargo test -p cerebellum-app quality::tests -- --nocapture
cargo test -p cerebellum-app scheduler::tests -- --nocapture
cargo test -p cerebellum-app api::tests -- --nocapture
```

Expected: every command passes and no test server contacts a non-loopback address.

- [ ] **Step 10: Prove no active hosted-provider request path remains**

Run:

```powershell
rg -n "DeepSeekClient|api\.deepseek\.com|DEEPSEEK_API_KEY|DEEPSEEK_API_BASE_URL|bearer_auth" crates/cerebellum-app/src
```

Expected: no production match. Historical test-environment names may remain only inside `#[cfg(test)]` blocks.

- [ ] **Step 11: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/config.rs crates/cerebellum-app/src/quality.rs crates/cerebellum-app/src/knowledge.rs crates/cerebellum-app/src/scheduler.rs crates/cerebellum-app/src/api.rs
```

Expected: no whitespace errors. Do not stage the already-dirty target files.

---

