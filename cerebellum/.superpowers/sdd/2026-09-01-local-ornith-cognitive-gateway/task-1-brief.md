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

