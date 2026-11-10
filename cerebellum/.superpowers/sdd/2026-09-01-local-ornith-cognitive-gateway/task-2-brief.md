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

