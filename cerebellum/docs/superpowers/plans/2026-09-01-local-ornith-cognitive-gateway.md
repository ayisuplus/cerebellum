# Local Ornith Cognitive Model Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all active DeepSeek and duplicated model-call paths with one pinned, loopback-only Ornith OpenAI-compatible client while preserving deterministic gates, historical records, and auditable zero-cost usage.

**Architecture:** Reuse the existing `StructuredModelClient` contract. Add one concrete local OpenAI-compatible implementation, make the router, knowledge extraction, quality review, calibration, and synthesis share it, and leave `Flash`/`Pro` as storage-compatible screening stages. Keep model output advisory: existing Rust validation, calibration, approval, dataset, and rollback gates remain authoritative.

**Tech Stack:** Rust 2024, Tokio, reqwest, Axum test servers, serde/serde_json, SQLite/rusqlite, PowerShell, LM Studio llama.cpp runtime, Ornith-1.5-9B Q4_K_M GGUF.

**Spec:** `docs/superpowers/specs/2026-09-01-local-ornith-cognitive-gateway-design.md`

## Global Constraints

- The only active codebase is `cerebellum/`; do not touch the two archived predecessor projects.
- Do not add a dependency or a new cognitive-engine/factory/role abstraction.
- Reuse `StructuredModelClient`, `StructuredRequest`, `StructuredResponse`, deterministic router fallback, quality tables, calibration, shadow review, and approval workflows.
- Accept only literal `http://127.0.0.1[:port]` and `http://[::1][:port]` model roots, optionally ending in `/v1`; reject hostnames, credentials, query strings, fragments, public addresses, and redirects.
- Use one API model name and the pinned GGUF SHA-256 `894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da` for the approved smoke test.
- All structured requests use `response_format.type=json_schema` with `strict=true`; no tools, provider thinking option, API key, proxy, external fallback, or hosted request is permitted.
- Derive the stored fingerprint from model name, GGUF SHA-256, runtime name/version, system prompt, and response-schema hash.
- Retry only transport failures and HTTP 5xx, at most once. Do not retry 4xx, schema, identity, security, truncation, or tool-call failures.
- New local usage has zero monetary cost but records stage, token counts, latency/evidence where the existing record supports it, and model identity. Historical DeepSeek rows remain byte-for-byte unchanged.
- External-processing permission is not an authority for loopback inference. Deterministic eligibility, licence, credential, PII, prompt-injection, output-echo, approval, and rollback checks remain fail-closed.
- Do not add a database migration and do not rename the persisted `Flash`/`Pro` enum values.
- LM Studio's observed 262,144-context load is a known defect. Do not make that runtime configuration an implicit default.
- The current target files already contain user changes. Capture pre-task hashes and never reset, stash, or overwrite them. Task commits are deferred because staging a touched file would also commit pre-existing user work; use verification checkpoints until the user explicitly chooses a commit strategy.
- Tasks 3 through 5 form one uncommitted switchover. Do not start `cerebellumd` or its scheduler between them; only the named local tests may run until Task 5 removes the hosted client.

## File Map

- Create `crates/cerebellum-app/src/local_model.rs`: loopback OpenAI-compatible structured client, identity preflight, strict-schema request, response parsing, retry policy, and fingerprint derivation.
- Modify `crates/cerebellum-app/src/config.rs`: `LocalModelConfig` and environment validation; remove active router/knowledge/DeepSeek configuration during switchover.
- Modify `crates/cerebellum-app/src/lib.rs`: export the new local-model module.
- Modify `crates/cerebellum-app/src/quality.rs`: remove `DeepSeekClient`, use local provider identity and zero-cost accounting, preserve history/calibration/approval, and keep scanners authoritative.
- Modify `crates/cerebellum-app/src/router.rs`: express routing as a `StructuredRequest` through the shared client and existing deterministic fallback.
- Modify `crates/cerebellum-app/src/knowledge.rs`: remove the duplicate direct HTTP client and use either the shared structured client or deterministic extraction.
- Modify `crates/cerebellum-app/src/scheduler.rs`: carry one optional structured client instead of separate knowledge and quality clients/configs.
- Modify `crates/cerebellum-app/src/api.rs`: construct one local client, share it with router and scheduler, and update local-processing enqueue conditions/messages.
- Modify `crates/cerebellum-app/src/dataset_factory.rs`: update the provider-specific quality-gate comment only; do not change dataset authority.
- Modify `README.md`, `docs/security.md`, `docs/protocol.md`, and `docs/deployment-v2.md`: document the active local runtime and environment contract.
- Create `docs/local-ornith-quality-v3.4.md`: active local quality/synthesis lifecycle; retain `docs/deepseek-quality-v3.3.md` as historical documentation.
- Modify `../.coordination/work/lm-studio-ornith-compatibility/probe.ps1`: strict-schema compatibility probe and non-semantic acceptance gate.
- Create `../.coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json`: new immutable probe evidence; do not overwrite the prior failed probe.

---

### Task 1: Add the pinned local-model configuration boundary

**Files:**
- Modify: `crates/cerebellum-app/src/config.rs:35-63, 201-281, 391-860`
- Modify: `crates/cerebellum-app/src/api.rs:1194-1220, 1634-1730` (test `AppConfig` literals only)

**Interfaces:**
- Produces: `pub struct LocalModelConfig { endpoint, model, artifact_sha256, runtime, runtime_version, enforcement_required }`.
- Produces: `fn load_local_model_config() -> anyhow::Result<Option<LocalModelConfig>>` and `AppConfig.local_model`.
- Consumes later: `OpenAiCompatibleStructuredClient::new(LocalModelConfig)`.

- [ ] **Step 1: Capture the dirty-file baseline before editing**

Run:

```powershell
git status --short
Get-FileHash crates/cerebellum-app/src/config.rs -Algorithm SHA256
git diff -- crates/cerebellum-app/src/config.rs
```

Expected: `config.rs` is already modified. Preserve the displayed content; do not restore it.

- [ ] **Step 2: Replace the provider-config tests with failing local boundary tests**

Add these environment names to `CONFIG_ENV_VARS` and add the helper/tests below. Keep DeepSeek names in the clearing list until Task 5 so inherited process state cannot leak into tests.

```rust
const ORNITH_SHA256: &str =
    "894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da";

fn set_valid_local_model_env(env: &EnvGuard) {
    env.set("CEREBELLUM_LOCAL_MODEL_ENABLED", "true");
    env.set("CEREBELLUM_LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:1234/v1");
    env.set("CEREBELLUM_LOCAL_MODEL_NAME", "ornith-1.5-9b");
    env.set("CEREBELLUM_LOCAL_MODEL_SHA256", ORNITH_SHA256);
    env.set("CEREBELLUM_LOCAL_MODEL_RUNTIME", "llama.cpp-win-x86_64-nvidia-cuda12-avx2");
    env.set("CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION", "2.31.2");
}

#[test]
fn local_model_is_disabled_by_default_and_requires_complete_pins() {
    let env = EnvGuard::cleared();
    assert!(load_local_model_config().unwrap().is_none());
    env.set("CEREBELLUM_LOCAL_MODEL_ENABLED", "true");
    let error = load_local_model_config().unwrap_err();
    assert!(format!("{error:#}").contains("CEREBELLUM_LOCAL_MODEL_ENDPOINT"));
    set_valid_local_model_env(&env);
    let config = load_local_model_config().unwrap().unwrap();
    assert_eq!(config.model, "ornith-1.5-9b");
    assert_eq!(config.artifact_sha256, ORNITH_SHA256);
}

#[test]
fn local_model_rejects_non_literal_or_non_loopback_endpoints() {
    let env = EnvGuard::cleared();
    set_valid_local_model_env(&env);
    for endpoint in [
        "http://localhost:1234/v1",
        "http://192.168.1.10:1234/v1",
        "https://127.0.0.1:1234/v1",
        "http://user:pass@127.0.0.1:1234/v1",
        "http://127.0.0.1:1234/v1?redirect=https://example.com",
        "http://127.0.0.1:1234/other",
    ] {
        env.set("CEREBELLUM_LOCAL_MODEL_ENDPOINT", endpoint);
        assert!(load_local_model_config().is_err(), "accepted {endpoint}");
    }
    env.set("CEREBELLUM_LOCAL_MODEL_ENDPOINT", "http://[::1]:1234/v1");
    assert!(load_local_model_config().is_ok());
}
```

- [ ] **Step 3: Run the tests and verify they fail for the missing type/loader**

Run:

```powershell
cargo test -p cerebellum-app config::tests::local_model -- --nocapture
```

Expected: compilation fails because `load_local_model_config` and `LocalModelConfig` do not exist.

- [ ] **Step 4: Implement the minimal configuration loader**

Add this type near `QualityModelConfig`; the old type is removed only during the atomic switchover in Task 5.

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LocalModelConfig {
    pub endpoint: String,
    pub model: String,
    pub artifact_sha256: String,
    pub runtime: String,
    pub runtime_version: String,
    pub enforcement_required: bool,
}
```

Implement `load_local_model_config` with these exact decisions:

```rust
fn load_local_model_config() -> Result<Option<LocalModelConfig>> {
    if !env_flag("CEREBELLUM_LOCAL_MODEL_ENABLED", false) {
        return Ok(None);
    }
    let endpoint = nonempty_env("CEREBELLUM_LOCAL_MODEL_ENDPOINT")
        .context("CEREBELLUM_LOCAL_MODEL_ENDPOINT is required")?;
    let parsed = url::Url::parse(&endpoint)
        .context("CEREBELLUM_LOCAL_MODEL_ENDPOINT must be an absolute URL")?;
    let literal_loopback = match parsed.host() {
        Some(url::Host::Ipv4(address)) => address.is_loopback(),
        Some(url::Host::Ipv6(address)) => address.is_loopback(),
        _ => false,
    };
    if parsed.scheme() != "http"
        || !literal_loopback
        || parsed.username() != ""
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
        || !matches!(parsed.path(), "/" | "/v1")
    {
        bail!("local model endpoint must be a literal loopback HTTP root or /v1 URL");
    }
    let artifact_sha256 = nonempty_env("CEREBELLUM_LOCAL_MODEL_SHA256")
        .context("CEREBELLUM_LOCAL_MODEL_SHA256 is required")?
        .to_ascii_lowercase();
    if artifact_sha256.len() != 64
        || !artifact_sha256.bytes().all(|byte| byte.is_ascii_hexdigit())
    {
        bail!("CEREBELLUM_LOCAL_MODEL_SHA256 must be a SHA-256 hex digest");
    }
    Ok(Some(LocalModelConfig {
        endpoint: endpoint.trim_end_matches('/').into(),
        model: nonempty_env("CEREBELLUM_LOCAL_MODEL_NAME")
            .context("CEREBELLUM_LOCAL_MODEL_NAME is required")?,
        artifact_sha256,
        runtime: nonempty_env("CEREBELLUM_LOCAL_MODEL_RUNTIME")
            .context("CEREBELLUM_LOCAL_MODEL_RUNTIME is required")?,
        runtime_version: nonempty_env("CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION")
            .context("CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION is required")?,
        enforcement_required: env_flag("CEREBELLUM_QUALITY_ENFORCEMENT", true),
    }))
}
```

Add `pub local_model: Option<LocalModelConfig>` to `AppConfig`, call the loader
once in `AppConfig::load`, and store the result. Add `local_model: None` to every
direct `AppConfig` test literal in `api.rs`. Keep the old model fields until the
atomic Task 5 switchover so this task compiles independently.

- [ ] **Step 5: Run the focused configuration tests**

Run:

```powershell
cargo test -p cerebellum-app config::tests::local_model -- --nocapture
cargo test -p cerebellum-app config::tests -- --nocapture
```

Expected: both commands pass.

- [ ] **Step 6: Record a verification checkpoint without staging user work**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/config.rs crates/cerebellum-app/src/api.rs
Get-FileHash crates/cerebellum-app/src/config.rs -Algorithm SHA256
```

Expected: no whitespace errors. Do not commit these already-dirty files.

---

### Task 2: Implement the strict local OpenAI-compatible client

**Files:**
- Create: `crates/cerebellum-app/src/local_model.rs`
- Modify: `crates/cerebellum-app/src/lib.rs:1-30`

**Interfaces:**
- Consumes: `LocalModelConfig`, `StructuredModelClient`, `StructuredRequest`, `StructuredResponse`.
- Produces: `pub struct OpenAiCompatibleStructuredClient`.
- Produces: `pub fn new(config: LocalModelConfig) -> Result<OpenAiCompatibleStructuredClient>`.
- Produces: `StructuredModelClient::complete`, including `/v1/models` identity preflight and derived fingerprint.

- [ ] **Step 1: Write failing fake-server tests in the new module**

The test server must expose `/v1/models` and `/v1/chat/completions`. Capture request bodies and return `model="ornith-1.5-9b"`, one JSON-string content choice, and OpenAI usage. Add these tests:

```rust
#[tokio::test]
async fn sends_strict_schema_without_tools_keys_or_thinking_options() {
    let (config, state) = serve_fake_local_model("success").await;
    let client = OpenAiCompatibleStructuredClient::new(config).unwrap();
    let response = client.complete(&request()).await.unwrap();
    assert_eq!(response.model_id, "ornith-1.5-9b");
    assert_eq!(response.usage.prompt_tokens, 10);
    assert_eq!(response.usage.prompt_cache_hit_tokens, 2);
    assert_eq!(response.usage.prompt_cache_miss_tokens, 8);
    assert_eq!(response.usage.completion_tokens, 4);
    assert_eq!(response.usage.total_tokens, 14);
    assert_eq!(state.models_calls.load(Ordering::SeqCst), 1);
    let bodies = state.bodies.lock().unwrap();
    assert_eq!(bodies[0]["response_format"]["type"], "json_schema");
    assert_eq!(bodies[0]["response_format"]["json_schema"]["strict"], true);
    assert!(bodies[0].get("tools").is_none());
    assert!(bodies[0].get("thinking").is_none());
}

#[tokio::test]
async fn retries_one_transport_or_server_failure_but_not_invalid_output() {
    let (config, state) = serve_fake_local_model("first_500").await;
    OpenAiCompatibleStructuredClient::new(config)
        .unwrap()
        .complete(&request())
        .await
        .unwrap();
    assert_eq!(state.chat_calls.load(Ordering::SeqCst), 2);

    for mode in ["invalid_json", "tool_call", "oversized"] {
        let (config, state) = serve_fake_local_model(mode).await;
        assert!(OpenAiCompatibleStructuredClient::new(config)
            .unwrap()
            .complete(&request())
            .await
            .is_err());
        assert_eq!(state.chat_calls.load(Ordering::SeqCst), 1, "mode {mode}");
    }
}

#[tokio::test]
async fn rejects_model_identity_mismatch_and_redirects() {
    let (config, state) = serve_fake_local_model("wrong_model").await;
    assert!(OpenAiCompatibleStructuredClient::new(config)
        .unwrap()
        .complete(&request())
        .await
        .is_err());
    assert_eq!(state.chat_calls.load(Ordering::SeqCst), 0);

    let (config, state) = serve_fake_local_model("redirect").await;
    assert!(OpenAiCompatibleStructuredClient::new(config)
        .unwrap()
        .complete(&request())
        .await
        .is_err());
    assert_eq!(state.redirect_target_calls.load(Ordering::SeqCst), 0);
}
```

The test request must carry the schema in the already-existing payload instead of adding a new request abstraction:

```rust
fn request() -> StructuredRequest {
    StructuredRequest {
        stage: QualityModelStage::Flash,
        system_prompt: "Return one safe JSON object.",
        payload: json!({
            "output_schema": {
                "type": "object",
                "additionalProperties": false,
                "required": ["ok"],
                "properties": {"ok": {"type": "boolean"}}
            },
            "subject": {"safe": true}
        }),
        max_tokens: 100,
    }
}
```

- [ ] **Step 2: Register the module and verify the tests fail**

Add `pub mod local_model;` to `lib.rs`, create the empty module, then run:

```powershell
cargo test -p cerebellum-app local_model::tests -- --nocapture
```

Expected: compilation fails because the client and fake-server helpers are not implemented.

- [ ] **Step 3: Implement identity preflight and the no-proxy HTTP client**

Use the already-installed reqwest/Tokio features:

```rust
pub struct OpenAiCompatibleStructuredClient {
    config: LocalModelConfig,
    client: reqwest::Client,
    models_endpoint: String,
    chat_endpoint: String,
    identity_verified: tokio::sync::OnceCell<()>,
}

impl OpenAiCompatibleStructuredClient {
    pub fn new(config: LocalModelConfig) -> Result<Self> {
        let root = config.endpoint.trim_end_matches('/');
        let versioned = if root.ends_with("/v1") {
            root.to_owned()
        } else {
            format!("{root}/v1")
        };
        Ok(Self {
            config,
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(45))
                .redirect(reqwest::redirect::Policy::none())
                .no_proxy()
                .build()?,
            models_endpoint: format!("{versioned}/models"),
            chat_endpoint: format!("{versioned}/chat/completions"),
            identity_verified: tokio::sync::OnceCell::new(),
        })
    }
}
```

Implement one private `send_with_one_retry` helper that rebuilds a request, retries only `send()` errors and 5xx once, and returns every 4xx/3xx immediately. Use it for the identity GET and chat POST. `identity_verified.get_or_try_init` must set the cell only after `/v1/models` contains an exact `data[].id == config.model`; subsequent responses must also report the exact configured `model`.

- [ ] **Step 4: Implement strict-schema request and bounded response parsing**

Read the schema from `request.payload["output_schema"]`; fail before HTTP when it is absent. Build this body:

```rust
let body = json!({
    "model": self.config.model,
    "temperature": 0,
    "max_tokens": request.max_tokens,
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "cerebellum_structured_output",
            "strict": true,
            "schema": response_schema
        }
    },
    "messages": [
        {"role": "system", "content": request.system_prompt},
        {"role": "user", "content": serde_json::to_string(&request.payload)?}
    ]
});
```

Retain the existing one-megabyte streaming limit. Reject missing/empty content, `finish_reason="length"`, tool calls, invalid JSON, and model mismatch without retry. Parse OpenAI-compatible usage as follows:

```rust
let cache_hits = usage
    .prompt_cache_hit_tokens
    .or(usage.prompt_tokens_details.cached_tokens)
    .unwrap_or(0)
    .min(usage.prompt_tokens);
let cache_misses = usage
    .prompt_cache_miss_tokens
    .unwrap_or(usage.prompt_tokens - cache_hits);
```

Compute `schema_hash=canonical_json_hash(&response_schema)` before moving the
schema into the request body. Derive the response fingerprint rather than
trusting the optional server field:

```rust
let system_fingerprint = canonical_json_hash(&json!({
    "model": self.config.model,
    "artifact_sha256": self.config.artifact_sha256,
    "runtime": self.config.runtime,
    "runtime_version": self.config.runtime_version,
    "system_prompt": request.system_prompt,
    "schema_hash": schema_hash,
}));
```

Measure the successful call with `std::time::Instant` and emit a structured
trace containing only `provider`, `model`, `system_fingerprint`,
`payload_hash=canonical_json_hash(&request.payload)`, `stage`, token totals,
and `latency_ms`. Never log prompt or response content. The immutable GPU probe
in Task 7 persists latency evidence; the runtime trace supplies per-call audit
without a database migration.

- [ ] **Step 5: Run the client tests and lint the new module**

Run:

```powershell
cargo test -p cerebellum-app local_model::tests -- --nocapture
cargo clippy -p cerebellum-app --lib -- -D warnings
```

Expected: both pass; the invalid-output test records exactly one chat request.

- [ ] **Step 6: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/local_model.rs crates/cerebellum-app/src/lib.rs
```

Expected: no whitespace errors. Do not stage `lib.rs`, which already contains user work.

---

### Task 3: Convert usage and model-version records to local zero-cost semantics

**Files:**
- Modify: `crates/cerebellum-app/src/quality.rs:25-45, 1044-1080, 1701-2057, 2226-2315, 3235-3305, 3690-3740`

**Interfaces:**
- Produces: `pub const LOCAL_MODEL_PROVIDER: &str = "local-openai-compatible"`.
- Keeps: `Registry::reserve_model_usage`, `settle_model_usage`, `model_usage_ledger`, quality/version/calibration tables and public API shapes.
- Historical compatibility: non-local ledger rows still use their stored provider pricing; local rows never require a pricing policy.

- [ ] **Step 1: Replace the daily-budget test with failing zero-cost/history tests**

Remove `concurrent_budget_reservations_stop_at_the_daily_ceiling`; that policy belongs to the removed paid provider. Add:

```rust
#[test]
fn local_usage_records_tokens_with_zero_cost() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let now = Utc::now();
    let request_id = Uuid::new_v4();
    assert_eq!(registry.reserve_model_usage(
        request_id,
        QualityModelStage::Flash,
        1_000,
        200,
        now,
    ).unwrap(), 0);
    let usage = ModelTokenUsage {
        prompt_tokens: 10,
        prompt_cache_hit_tokens: 2,
        prompt_cache_miss_tokens: 8,
        completion_tokens: 4,
        reasoning_tokens: 0,
        total_tokens: 14,
    };
    assert_eq!(registry.settle_model_usage(request_id, Some(&usage), now).unwrap(), 0);
    let ledger = registry.model_usage_ledger(LOCAL_MODEL_PROVIDER, now).unwrap().unwrap();
    assert_eq!(ledger.spent_microusd, 0);
    assert_eq!(ledger.estimated_cny, 0.0);
    assert_eq!(ledger.usage, usage);
}

#[test]
fn registering_local_identity_does_not_rewrite_historical_deepseek_rows() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let historical = ModelEndpointVersion {
        schema_version: SCHEMA_VERSION.into(),
        endpoint_version_id: Uuid::new_v4(),
        provider: "deepseek".into(),
        model_id: "deepseek-v4-flash".into(),
        system_fingerprint: "historical-fingerprint".into(),
        prompt_version: "deepseek-quality-rubric-v1".into(),
        schema_hash: "a".repeat(64),
        status: ModelEndpointStatus::PendingApproval,
        metrics: ModelCalibrationMetrics::default(),
        approved_by: None,
        approval_reason: None,
        first_seen_at: Utc::now(),
        updated_at: Utc::now(),
    };
    let historical_json = serde_json::to_string(&historical).unwrap();
    registry.conn.lock().unwrap().execute(
        "INSERT INTO quality_model_versions(
           id,provider,model_id,system_fingerprint,prompt_version,status,version_json,updated_at
         ) VALUES(?1,?2,?3,?4,?5,'pending_approval',?6,?7)",
        params![
            historical.endpoint_version_id.to_string(),
            historical.provider,
            historical.model_id,
            historical.system_fingerprint,
            historical.prompt_version,
            historical_json,
            historical.updated_at.to_rfc3339(),
        ],
    ).unwrap();
    let before: String = registry.conn.lock().unwrap().query_row(
        "SELECT version_json FROM quality_model_versions WHERE id=?1",
        params![historical.endpoint_version_id.to_string()],
        |row| row.get(0),
    ).unwrap();
    registry.ensure_model_endpoint_version(
        "ornith-1.5-9b",
        &"b".repeat(64),
        &"c".repeat(64),
        Utc::now(),
    ).unwrap();
    let after: String = registry.conn.lock().unwrap().query_row(
        "SELECT version_json FROM quality_model_versions WHERE id=?1",
        params![historical.endpoint_version_id.to_string()],
        |row| row.get(0),
    ).unwrap();
    assert_eq!(before, after);
}
```

- [ ] **Step 2: Run the focused tests and verify the local ledger test fails**

Run:

```powershell
cargo test -p cerebellum-app quality::tests::local_usage_records_tokens_with_zero_cost -- --nocapture
```

Expected: failure because reservation still requires DeepSeek pricing.

- [ ] **Step 3: Implement local zero-cost reservations without a schema migration**

Rename active constants:

```rust
pub const QUALITY_POLICY_VERSION: &str = "ornith-local-quality-v1";
pub const QUALITY_PROMPT_VERSION: &str = "ornith-local-quality-rubric-v1";
pub const SYNTHETIC_PROMPT_VERSION: &str = "ornith-local-synthetic-v1";
pub const LOCAL_MODEL_PROVIDER: &str = "local-openai-compatible";
```

Change `reserve_model_usage` to insert `provider=LOCAL_MODEL_PROVIDER` with
`reserved_microusd=0`; remove paid-price lookup and ceiling enforcement from
this method. Keep the existing transaction and idempotent request-ID behavior.
Do not start the application until Task 5 has removed the temporary DeepSeek
client that still exists in the source tree at this checkpoint.

Change `settle_model_usage` to query the reservation before selecting pricing:

```rust
let spent = if provider == LOCAL_MODEL_PROVIDER {
    0
} else {
    let pricing = self.current_provider_pricing(&provider)?;
    usage.map_or(reserved, |usage| {
        estimate_microusd(
            &pricing,
            stage,
            usage.prompt_cache_hit_tokens,
            usage.prompt_cache_miss_tokens,
            usage.completion_tokens,
        )
    })
};
```

Change `model_usage_ledger` so local `estimated_cny` is `0.0`; only load pricing for a non-local provider. This preserves readable historical DeepSeek ledgers and unsettled reservations.

- [ ] **Step 4: Store new endpoint versions under the local provider only**

Replace `DEEPSEEK_PROVIDER` with `LOCAL_MODEL_PROVIDER` in:

- `ensure_model_endpoint_version`;
- `active_model_endpoint`;
- `quality_status` usage/provider values;
- `audit_dataset_quality` usage lookup.

Do not update existing rows. The unique lookup includes provider, so the same model/fingerprint under the new provider creates a distinct record.

- [ ] **Step 5: Run quality lifecycle tests**

Run:

```powershell
cargo test -p cerebellum-app quality::tests -- --nocapture
```

Expected: all quality tests pass, including zero-cost usage and unchanged historical JSON.

- [ ] **Step 6: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/quality.rs
Get-FileHash crates/cerebellum-app/src/quality.rs -Algorithm SHA256
```

Expected: no whitespace errors. Do not stage the already-dirty file.

---

### Task 4: Route decisions through the shared structured client

**Files:**
- Modify: `crates/cerebellum-app/src/router.rs:1-230, 293-455`

**Interfaces:**
- Consumes: `Arc<Registry>`, `Arc<dyn StructuredModelClient>`, `complete_budgeted`.
- Produces: `OpenAiCompatibleRouter::new(registry, client)`.
- Keeps: `RouterModel`, `rank_with_fallback`, and deterministic BM25 behavior.

- [ ] **Step 1: Add a failing structured-router test**

Use a fake `StructuredModelClient` that captures its request and returns a valid selection:

```rust
#[tokio::test]
async fn local_router_uses_candidate_bounded_schema() {
    let directory = tempdir().unwrap();
    let registry = Arc::new(Registry::open(directory.path()).unwrap());
    let captured = Arc::new(Mutex::new(None));
    let client = Arc::new(FakeStructuredRouter { captured: captured.clone() });
    let router = OpenAiCompatibleRouter::new(registry, client);
    let request = DecisionRequest {
        task: "review this pull request".into(),
        repository_path: None,
        capabilities: vec![],
        context: Value::Null,
    };
    let ranked = router.rank(&request, &builtins::workflows()).await.unwrap();
    assert_eq!(ranked[0].workflow_id, "code-review");
    let request = captured.lock().unwrap().clone().unwrap();
    let allowed = request.payload
        .pointer("/output_schema/properties/workflow_id/enum")
        .unwrap()
        .as_array()
        .unwrap();
    assert!(allowed.iter().any(|id| id == "code-review"));
}
```

The fake response must include internally consistent zero-cost usage and a 64-character derived-style fingerprint.

- [ ] **Step 2: Run the test and verify it fails against the direct HTTP router**

Run:

```powershell
cargo test -p cerebellum-app router::tests::local_router_uses_candidate_bounded_schema -- --nocapture
```

Expected: compilation fails because the constructor still takes endpoint/model/key/backend strings.

- [ ] **Step 3: Replace direct reqwest routing with `StructuredRequest`**

Make the router hold only:

```rust
pub struct OpenAiCompatibleRouter {
    registry: Arc<Registry>,
    client: Arc<dyn StructuredModelClient>,
}

impl OpenAiCompatibleRouter {
    pub fn new(registry: Arc<Registry>, client: Arc<dyn StructuredModelClient>) -> Self {
        Self { registry, client }
    }
}
```

Build a dynamic strict schema with `workflow_id.enum` equal to the supplied IDs, `confidence` bounded to `0..1`, `reasons` bounded to short strings, all three fields required, and `additionalProperties=false`. Put it under `payload.output_schema`, then call:

```rust
let response = complete_budgeted(
    &self.registry,
    self.client.as_ref(),
    &StructuredRequest {
        stage: QualityModelStage::Flash,
        system_prompt: ROUTER_SYSTEM_PROMPT,
        payload: json!({
            "output_schema": schema,
            "task": request.task,
            "context": request.context,
            "capabilities": request.capabilities,
            "candidates": candidates,
        }),
        max_tokens: 512,
    },
    Utc::now(),
).await?;
```

Parse `response.value` and retain existing local checks for confidence and invented IDs. Return `"local-openai-compatible"` from `name()`.

- [ ] **Step 4: Verify strict routing and deterministic failure fallback**

Run:

```powershell
cargo test -p cerebellum-app router::tests -- --nocapture
```

Expected: structured router test passes, and `model_failure_falls_back_without_losing_a_decision` still selects `code-review` through `deterministic-bm25`.

- [ ] **Step 5: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/router.rs
```

Expected: no whitespace errors; do not stage the already-dirty file.

---

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

### Task 6: Apply the loopback-local privacy interpretation without weakening scanners

**Files:**
- Modify: `crates/cerebellum-app/src/quality.rs:276-310, 2059-2162, 2576-2620, 3120-3235`
- Modify: `crates/cerebellum-app/src/knowledge.rs:67-127, 655-930`
- Modify: `crates/cerebellum-app/src/router.rs:102-230, 293-370`
- Modify: `crates/cerebellum-app/src/api.rs:3957-4015`
- Modify: `crates/cerebellum-app/src/dataset_factory.rs:380`

**Interfaces:**
- Keeps: `ExternalProcessingPermission` in stored records as provenance.
- Changes: local inference eligibility no longer requires `ExternalProcessingPermission::Redacted` and no longer rejects `AuthenticatedLocal` solely for access mode.
- Keeps: deterministic eligibility, document secret/PII/injection flags, `validate_export_payload`, redaction attestation, private-echo scanning, licensing, quality-clear, and human approval.
- Adds: router input scanning before the shared client sees task/context/capabilities; a rejected router input uses the existing deterministic fallback.

- [ ] **Step 1: Write failing quality tests for local-only permission semantics**

Split the old `denied_or_deterministically_ineligible_records_never_call_the_model` expectation into:

```rust
#[tokio::test]
async fn eligible_local_record_can_be_reviewed_when_external_transfer_is_denied() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let calls = Arc::new(AtomicUsize::new(0));
    let model = FakeModel { calls: calls.clone() };
    let item = trace(ExternalProcessingPermission::Denied, true);
    registry.record_meta_decision(&item).unwrap();
    assess_subject(
        &registry,
        &model,
        QualityAssessmentTarget {
            subject_kind: QualitySubjectKind::MetaDecision,
            subject_id: &item.decision_id.to_string(),
            stage: QualityModelStage::Flash,
            parent_assessment_id: None,
            now: Utc::now(),
        },
    ).await.unwrap();
    assert_eq!(calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn local_permission_bypass_does_not_bypass_deterministic_or_secret_gates() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let calls = Arc::new(AtomicUsize::new(0));
    let model = FakeModel { calls: calls.clone() };
    let mut item = trace(ExternalProcessingPermission::Denied, false);
    registry.record_meta_decision(&item).unwrap();
    assert!(assess_subject(&registry, &model, target(&item)).await.is_err());
    item.decision_id = Uuid::new_v4();
    item.training_eligible = true;
    item.input = json!({"api_key": "sk-abcdefghijklmnop1234"});
    registry.record_meta_decision(&item).unwrap();
    assert!(assess_subject(&registry, &model, target(&item)).await.is_err());
    assert_eq!(calls.load(Ordering::SeqCst), 0);
}
```

Add a router test whose task contains `api_key=sk-abcdefghijklmnop1234`.
The fake structured client call count must stay zero, and `rank_with_fallback`
must return a deterministic result with `fallback_used=true`.

- [ ] **Step 2: Add a failing knowledge test for cleaned authenticated-local content**

Create an authenticated-local source with `external_processing=Denied`, a document with all three detection flags false, and a fake structured model. Assert structured extraction is attempted. Then set `secret_detected=true` on a second document and assert deterministic fallback with no additional model call.

- [ ] **Step 3: Run the new tests and verify current permission checks reject them**

Run:

```powershell
cargo test -p cerebellum-app eligible_local_record_can_be_reviewed -- --nocapture
cargo test -p cerebellum-app cleaned_authenticated_local -- --nocapture
```

Expected: the safe local cases fail before calling the model.

- [ ] **Step 4: Remove only external-transfer blockers from local paths**

In `assess_subject_inner`, remove:

```rust
if subject.permission != ExternalProcessingPermission::Redacted {
    bail!("external processing permission is denied");
}
```

Do not remove `deterministic_eligible`, `validate_export_payload`, redaction attestation, echo, secret, PII, injection, endpoint approval, or quality-clear checks.

In `consolidate_document_with_structured_model_fallback`, remove only `AuthenticatedLocal` and `source.external_processing` from the early fallback condition. Keep document injection/PII/secret flags.

In API enqueue and `enqueue_quality_backfill`, remove only the `external_processing == Redacted` predicates. Keep training eligibility, safety, policy, and prompt-injection predicates.

Make `validate_export_payload` `pub(crate)` without changing its scanner logic.
Before building the router request, call it on exactly:

```rust
json!({
    "task": request.task,
    "context": request.context,
    "capabilities": request.capabilities,
})
```

Discard the returned serialization; this is a local trust-boundary check. An
error naturally reaches `rank_with_fallback`, which selects the deterministic
router. Do not scan the generated JSON Schema or workflow manifests as user
data.

- [ ] **Step 5: Update stale provider-authority comments**

Change the KnowledgeCard source comment to state that cards may derive from cleaned local or public content, while training eligibility remains deterministic and quality-gated. Change the dataset-factory comment from “DeepSeek quality gate” to “active structured quality gate”. Do not alter dataset selection logic.

- [ ] **Step 6: Run privacy, knowledge, API, and dataset tests**

Run:

```powershell
cargo test -p cerebellum-app quality::tests -- --nocapture
cargo test -p cerebellum-app knowledge::tests -- --nocapture
cargo test -p cerebellum-app router::tests -- --nocapture
cargo test -p cerebellum-app api::tests -- --nocapture
cargo test -p cerebellum-app dataset_factory::tests -- --nocapture
```

Expected: safe loopback-local records can reach the model; ineligible, secret, PII, injection, and private-echo cases never become trusted knowledge.

- [ ] **Step 7: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/quality.rs crates/cerebellum-app/src/knowledge.rs crates/cerebellum-app/src/router.rs crates/cerebellum-app/src/api.rs crates/cerebellum-app/src/dataset_factory.rs
```

Expected: no whitespace errors.

---

### Task 7: Update active documentation and produce the fixed local GPU evidence

**Files:**
- Modify: `README.md:1-210`
- Modify: `docs/security.md:56-76, 128-145`
- Modify: `docs/protocol.md:125-175`
- Modify: `docs/deployment-v2.md:45-65`
- Create: `docs/local-ornith-quality-v3.4.md`
- Modify: `docs/deepseek-quality-v3.3.md:1-8`
- Modify: `../.coordination/work/lm-studio-ornith-compatibility/probe.ps1`
- Create: `../.coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json`

**Interfaces:**
- Documents final environment variables and trust boundary.
- Probe accepts artifact/runtime identity parameters and emits strict-schema, latency, semantic-baseline, and GPU evidence.
- Previous `lm-studio-probe.json` remains immutable.

- [ ] **Step 1: Update the probe contract before allocating the GPU**

Add mandatory parameters:

```powershell
[Parameter(Mandatory = $true)][string]$ArtifactSha256,
[Parameter(Mandatory = $true)][string]$RuntimeName,
[Parameter(Mandatory = $true)][string]$RuntimeVersion,
```

Build a dynamic schema using the candidate IDs:

```powershell
$schema = [ordered]@{
    type = 'object'
    additionalProperties = $false
    required = @('workflow_id', 'confidence', 'reasons')
    properties = [ordered]@{
        workflow_id = @{ type = 'string'; enum = $candidateIds }
        confidence = @{ type = 'number'; minimum = 0; maximum = 1 }
        reasons = @{ type = 'array'; maxItems = 8; items = @{ type = 'string'; maxLength = 240 } }
    }
}
$body.response_format = @{
    type = 'json_schema'
    json_schema = @{ name = 'cerebellum_router'; strict = $true; schema = $schema }
}
```

Validate that the parsed object has exactly the required properties, a legal ID, bounded confidence, and an array of strings. Add `schemaValid` per result and summary. Keep `exact` as a reported semantic baseline, but change the exit gate to:

```powershell
if ($summary.accepted -ne $summary.total -or $summary.schemaValid -ne $summary.total) { exit 1 }
```

Add artifact SHA, runtime name/version, and `nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits` snapshots to the summary. Do not include paths outside the approved model artifact or any secret.

- [ ] **Step 2: Update active documentation**

Document these exact variables:

```text
CEREBELLUM_LOCAL_MODEL_ENABLED=1
CEREBELLUM_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:1234/v1
CEREBELLUM_LOCAL_MODEL_NAME=ornith-1.5-9b
CEREBELLUM_LOCAL_MODEL_SHA256=894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da
CEREBELLUM_LOCAL_MODEL_RUNTIME=llama.cpp-win-x86_64-nvidia-cuda12-avx2
CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION=2.31.2
CEREBELLUM_QUALITY_ENFORCEMENT=1
```

`docs/local-ornith-quality-v3.4.md` must describe one local model, strict schema, local zero cost, screening/challenge semantics, calibration/approval, deterministic authority, and no weight update. Mark `docs/deepseek-quality-v3.3.md` as historical and link to the new active document; do not erase its historical protocol description.

- [ ] **Step 3: Run formatting, focused tests, and source scans before GPU use**

Run:

```powershell
cargo fmt --all -- --check
cargo clippy -p cerebellum-app --all-targets -- -D warnings
cargo test -p cerebellum-app --all-targets
rg -n "DeepSeekClient|api\.deepseek\.com|DEEPSEEK_API_KEY|CEREBELLUM_KNOWLEDGE_MODEL_API_KEY" crates/cerebellum-app/src README.md docs/security.md docs/protocol.md docs/deployment-v2.md
```

Expected: Rust checks pass and the scan finds no active provider request/key configuration. Historical documentation and test fixtures are outside this active-path assertion.

- [ ] **Step 4: Load the already-approved Ornith model in LM Studio and confirm identity**

The user has already approved this local RTX 5090 probe and the existing hard-linked artifact. Run:

```powershell
lms ls
lms server status
lms load ornith-1.5-9b --identifier ornith-1.5-9b --gpu max --context-length 4096 --parallel 1 --yes
Invoke-RestMethod http://127.0.0.1:1234/v1/models | ConvertTo-Json -Depth 6
nvidia-smi
```

Expected: the server is running and model ID `ornith-1.5-9b` is listed. If
`lms server status` reports stopped, run `lms server start` once before loading.
Record the actual context echoed by LM Studio; if it remains 262,144, retain
the known-defect warning and continue only because the approved RTX 5090 probe
fits.

- [ ] **Step 5: Run the immutable 16-call strict-schema probe**

Run from the workspace root:

```powershell
powershell -ExecutionPolicy Bypass -File .coordination/work/lm-studio-ornith-compatibility/probe.ps1 `
  -Endpoint http://127.0.0.1:1234/v1/chat/completions `
  -Model ornith-1.5-9b `
  -Backend lm-studio-llama.cpp `
  -ArtifactSha256 894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da `
  -RuntimeName llama.cpp-win-x86_64-nvidia-cuda12-avx2 `
  -RuntimeVersion 2.31.2 `
  -Runs 2 `
  -OutputPath .coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json
```

Expected: `total=16`, `accepted=16`, `schemaValid=16`, exit code zero. `exact` is reported but is not the package gate.

- [ ] **Step 6: Unload the model and hash the evidence**

Run:

```powershell
lms unload ornith-1.5-9b
nvidia-smi
Get-FileHash .coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json -Algorithm SHA256
```

Expected: Ornith is unloaded, GPU memory returns near baseline, and the evidence receives a stable SHA-256. Do not overwrite the previous failed probe.

- [ ] **Step 7: Run the full project gate**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1
```

Expected: all Rust, JavaScript, monorepo, Python, worker, and benchmark checks pass. If an unrelated pre-existing dirty-tree failure appears, preserve its exact command/output and do not claim package completion until the scoped Rust checks and ownership of the unrelated failure are clear.

- [ ] **Step 8: Final scope and history verification**

Run:

```powershell
git status --short
git diff --check
git diff --stat
rg -n "DeepSeekClient|api\.deepseek\.com|DEEPSEEK_API_KEY" crates/cerebellum-app/src
```

Expected: only approved paths changed, no whitespace errors, no active DeepSeek request/key path, and all pre-existing unrelated user changes remain present.

- [ ] **Step 9: Present the combined diff before any implementation commit**

Because `config.rs`, `quality.rs`, `router.rs`, `knowledge.rs`, `scheduler.rs`, `api.rs`, and documentation were already dirty before this package, do not run `git add` or `git commit`. Present:

```powershell
git diff -- crates/cerebellum-app/src/local_model.rs crates/cerebellum-app/src/config.rs crates/cerebellum-app/src/quality.rs crates/cerebellum-app/src/router.rs crates/cerebellum-app/src/knowledge.rs crates/cerebellum-app/src/scheduler.rs crates/cerebellum-app/src/api.rs crates/cerebellum-app/src/dataset_factory.rs README.md docs/security.md docs/protocol.md docs/deployment-v2.md docs/local-ornith-quality-v3.4.md docs/deepseek-quality-v3.3.md
```

Expected: user chooses whether to incorporate pre-existing changes into a commit, split them manually, or leave the verified implementation uncommitted.
