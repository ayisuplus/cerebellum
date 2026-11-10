# Task 2 review package

Task brief: task-2-brief.md
Implementer report: task-2-implementer.md
Comparison: task-start snapshots to current working tree; no commits or staging.

warning: in the working copy of 'crates\cerebellum-app\src\local_model.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-2-baseline\\crates\\cerebellum-app\\src\\local_model.rs" "b/crates\\cerebellum-app\\src\\local_model.rs"
index e69de29..bd25a7d 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-2-baseline\\crates\\cerebellum-app\\src\\local_model.rs"
+++ "b/crates\\cerebellum-app\\src\\local_model.rs"
@@ -0,0 +1,450 @@
+use crate::config::LocalModelConfig;
+use crate::quality::{StructuredModelClient, StructuredRequest, StructuredResponse};
+use anyhow::{Context, Result, anyhow, bail};
+use async_trait::async_trait;
+use cerebellum_core::{ModelTokenUsage, canonical_json_hash};
+use serde::Deserialize;
+use serde_json::{Value, json};
+use std::time::{Duration, Instant};
+
+const MAX_RESPONSE_BYTES: usize = 1_048_576;
+
+pub struct OpenAiCompatibleStructuredClient {
+    config: LocalModelConfig,
+    client: reqwest::Client,
+    models_endpoint: String,
+    chat_endpoint: String,
+    identity_verified: tokio::sync::OnceCell<()>,
+}
+
+impl OpenAiCompatibleStructuredClient {
+    pub fn new(config: LocalModelConfig) -> Result<Self> {
+        let root = config.endpoint.trim_end_matches('/');
+        let versioned = if root.ends_with("/v1") {
+            root.to_owned()
+        } else {
+            format!("{root}/v1")
+        };
+        Ok(Self {
+            config,
+            client: reqwest::Client::builder()
+                .timeout(Duration::from_secs(45))
+                .redirect(reqwest::redirect::Policy::none())
+                .no_proxy()
+                .build()?,
+            models_endpoint: format!("{versioned}/models"),
+            chat_endpoint: format!("{versioned}/chat/completions"),
+            identity_verified: tokio::sync::OnceCell::new(),
+        })
+    }
+
+    async fn send_with_one_retry<F>(&self, build: F) -> Result<reqwest::Response>
+    where
+        F: Fn() -> reqwest::RequestBuilder,
+    {
+        let mut last_error = None;
+        for attempt in 0..2 {
+            match build().send().await {
+                Ok(response) if response.status().is_server_error() && attempt == 0 => {
+                    last_error = Some(anyhow!("local model HTTP status {}", response.status()));
+                }
+                Ok(response) => return Ok(response),
+                Err(error) if attempt == 0 => last_error = Some(anyhow!(error)),
+                Err(error) => return Err(error.into()),
+            }
+        }
+        Err(last_error.unwrap_or_else(|| anyhow!("local model request failed")))
+    }
+
+    async fn verify_identity(&self) -> Result<()> {
+        self.identity_verified
+            .get_or_try_init(|| async {
+                let response = self
+                    .send_with_one_retry(|| self.client.get(&self.models_endpoint))
+                    .await?;
+                if !response.status().is_success() {
+                    bail!("local model identity HTTP status {}", response.status());
+                }
+                let models: ModelsEnvelope = serde_json::from_slice(
+                    &read_bounded(response, "local model identity response").await?,
+                )
+                .context("local model identity response is not valid JSON")?;
+                if !models.data.iter().any(|model| model.id == self.config.model) {
+                    bail!("local model identity does not include configured model");
+                }
+                Ok(())
+            })
+            .await?;
+        Ok(())
+    }
+}
+
+async fn read_bounded(mut response: reqwest::Response, description: &str) -> Result<Vec<u8>> {
+    if response
+        .content_length()
+        .is_some_and(|length| length > MAX_RESPONSE_BYTES as u64)
+    {
+        bail!("{description} exceeds the one-megabyte limit");
+    }
+    let mut bytes = Vec::new();
+    while let Some(chunk) = response.chunk().await? {
+        if bytes.len().saturating_add(chunk.len()) > MAX_RESPONSE_BYTES {
+            bail!("{description} exceeds the one-megabyte limit");
+        }
+        bytes.extend_from_slice(&chunk);
+    }
+    Ok(bytes)
+}
+
+#[derive(Deserialize)]
+struct ModelsEnvelope {
+    data: Vec<ModelIdentity>,
+}
+
+#[derive(Deserialize)]
+struct ModelIdentity {
+    id: String,
+}
+
+#[derive(Deserialize)]
+struct CompletionEnvelope {
+    model: String,
+    choices: Vec<CompletionChoice>,
+    usage: CompletionUsage,
+}
+
+#[derive(Deserialize)]
+struct CompletionChoice {
+    finish_reason: Option<String>,
+    message: CompletionMessage,
+}
+
+#[derive(Deserialize)]
+struct CompletionMessage {
+    content: Option<String>,
+    #[serde(default)]
+    tool_calls: Vec<Value>,
+}
+
+#[derive(Deserialize)]
+struct CompletionUsage {
+    prompt_tokens: u64,
+    #[serde(default)]
+    prompt_cache_hit_tokens: Option<u64>,
+    #[serde(default)]
+    prompt_cache_miss_tokens: Option<u64>,
+    completion_tokens: u64,
+    total_tokens: u64,
+    #[serde(default)]
+    prompt_tokens_details: PromptTokensDetails,
+}
+
+#[derive(Default, Deserialize)]
+struct PromptTokensDetails {
+    #[serde(default)]
+    cached_tokens: Option<u64>,
+}
+
+#[async_trait]
+impl StructuredModelClient for OpenAiCompatibleStructuredClient {
+    async fn complete(&self, request: &StructuredRequest) -> Result<StructuredResponse> {
+        let response_schema = request
+            .payload
+            .get("output_schema")
+            .cloned()
+            .context("structured request lacks output_schema")?;
+        self.verify_identity().await?;
+        let schema_hash = canonical_json_hash(&response_schema);
+        let body = json!({
+            "model": self.config.model,
+            "temperature": 0,
+            "max_tokens": request.max_tokens,
+            "response_format": {
+                "type": "json_schema",
+                "json_schema": {
+                    "name": "cerebellum_structured_output",
+                    "strict": true,
+                    "schema": response_schema
+                }
+            },
+            "messages": [
+                {"role": "system", "content": request.system_prompt},
+                {"role": "user", "content": serde_json::to_string(&request.payload)?}
+            ]
+        });
+        let started = Instant::now();
+        let response = self
+            .send_with_one_retry(|| self.client.post(&self.chat_endpoint).json(&body))
+            .await?;
+        if !response.status().is_success() {
+            bail!("local model HTTP status {}", response.status());
+        }
+        let envelope: CompletionEnvelope = serde_json::from_slice(
+            &read_bounded(response, "local model response").await?,
+        )
+        .context("local model response is not valid JSON")?;
+        if envelope.model != self.config.model {
+            bail!("local model response identity does not match configured model");
+        }
+        let choice = envelope
+            .choices
+            .into_iter()
+            .next()
+            .context("local model response has no choices")?;
+        if choice.finish_reason.as_deref() == Some("length") {
+            bail!("local model JSON output was truncated");
+        }
+        if !choice.message.tool_calls.is_empty() {
+            bail!("local model response attempted a tool call");
+        }
+        let raw_content = choice
+            .message
+            .content
+            .filter(|content| !content.trim().is_empty())
+            .context("local model response is empty")?;
+        let value = serde_json::from_str(&raw_content).context("local model emitted invalid JSON")?;
+        let cache_hits = envelope
+            .usage
+            .prompt_cache_hit_tokens
+            .or(envelope.usage.prompt_tokens_details.cached_tokens)
+            .unwrap_or(0)
+            .min(envelope.usage.prompt_tokens);
+        let cache_misses = envelope
+            .usage
+            .prompt_cache_miss_tokens
+            .unwrap_or(envelope.usage.prompt_tokens - cache_hits);
+        let system_fingerprint = canonical_json_hash(&json!({
+            "model": self.config.model,
+            "artifact_sha256": self.config.artifact_sha256,
+            "runtime": self.config.runtime,
+            "runtime_version": self.config.runtime_version,
+            "system_prompt": request.system_prompt,
+            "schema_hash": schema_hash,
+        }));
+        let usage = ModelTokenUsage {
+            prompt_tokens: envelope.usage.prompt_tokens,
+            prompt_cache_hit_tokens: cache_hits,
+            prompt_cache_miss_tokens: cache_misses,
+            completion_tokens: envelope.usage.completion_tokens,
+            reasoning_tokens: 0,
+            total_tokens: envelope.usage.total_tokens,
+        };
+        tracing::info!(
+            provider = "local-openai-compatible",
+            model = %self.config.model,
+            system_fingerprint = %system_fingerprint,
+            payload_hash = %canonical_json_hash(&request.payload),
+            stage = ?request.stage,
+            prompt_tokens = usage.prompt_tokens,
+            completion_tokens = usage.completion_tokens,
+            total_tokens = usage.total_tokens,
+            latency_ms = started.elapsed().as_millis(),
+            "local structured model completion"
+        );
+        Ok(StructuredResponse {
+            model_id: envelope.model,
+            system_fingerprint,
+            value,
+            raw_content,
+            usage,
+        })
+    }
+}
+
+#[cfg(test)]
+mod tests {
+    use super::OpenAiCompatibleStructuredClient;
+    use crate::config::LocalModelConfig;
+    use crate::quality::{StructuredModelClient, StructuredRequest};
+    use axum::{
+        Json, Router,
+        extract::State,
+        http::StatusCode,
+        routing::{get, post},
+    };
+    use cerebellum_core::QualityModelStage;
+    use serde_json::{Value, json};
+    use std::sync::{
+        Arc, Mutex,
+        atomic::{AtomicUsize, Ordering},
+    };
+
+    #[derive(Clone)]
+    struct FakeState {
+        mode: &'static str,
+        models_calls: Arc<AtomicUsize>,
+        chat_calls: Arc<AtomicUsize>,
+        redirect_target_calls: Arc<AtomicUsize>,
+        bodies: Arc<Mutex<Vec<Value>>>,
+    }
+
+    async fn models(State(state): State<FakeState>) -> (StatusCode, Json<Value>) {
+        state.models_calls.fetch_add(1, Ordering::SeqCst);
+        if state.mode == "redirect" {
+            return (
+                StatusCode::FOUND,
+                Json(json!({"location":"/redirect-target"})),
+            );
+        }
+        let model = if state.mode == "wrong_model" {
+            "other-model"
+        } else {
+            "ornith-1.5-9b"
+        };
+        (StatusCode::OK, Json(json!({"data":[{"id":model}]})))
+    }
+
+    async fn chat(
+        State(state): State<FakeState>,
+        Json(body): Json<Value>,
+    ) -> (StatusCode, Json<Value>) {
+        let call = state.chat_calls.fetch_add(1, Ordering::SeqCst);
+        state.bodies.lock().unwrap().push(body);
+        if state.mode == "first_500" && call == 0 {
+            return (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({})));
+        }
+        let content = match state.mode {
+            "invalid_json" => "not json".to_owned(),
+            "tool_call" => json!({"ok":true}).to_string(),
+            "oversized" => "x".repeat(1_048_577),
+            _ => json!({"ok":true}).to_string(),
+        };
+        let tool_calls = if state.mode == "tool_call" {
+            json!([{"id":"call_1"}])
+        } else {
+            json!([])
+        };
+        (
+            StatusCode::OK,
+            Json(json!({
+                "model":"ornith-1.5-9b",
+                "choices":[{"finish_reason":"stop","message":{"content":content,"tool_calls":tool_calls}}],
+                "usage":{"prompt_tokens":10,"prompt_cache_hit_tokens":2,"completion_tokens":4,"total_tokens":14}
+            })),
+        )
+    }
+
+    async fn redirect_target(State(state): State<FakeState>) -> StatusCode {
+        state.redirect_target_calls.fetch_add(1, Ordering::SeqCst);
+        StatusCode::OK
+    }
+
+    async fn serve_fake_local_model(mode: &'static str) -> (LocalModelConfig, FakeState) {
+        let state = FakeState {
+            mode,
+            models_calls: Arc::new(AtomicUsize::new(0)),
+            chat_calls: Arc::new(AtomicUsize::new(0)),
+            redirect_target_calls: Arc::new(AtomicUsize::new(0)),
+            bodies: Arc::new(Mutex::new(Vec::new())),
+        };
+        let app = Router::new()
+            .route("/v1/models", get(models))
+            .route("/v1/chat/completions", post(chat))
+            .route("/redirect-target", get(redirect_target))
+            .with_state(state.clone());
+        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
+        let address = listener.local_addr().unwrap();
+        tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
+        (
+            LocalModelConfig {
+                endpoint: format!("http://{address}/v1"),
+                model: "ornith-1.5-9b".into(),
+                artifact_sha256:
+                    "894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da".into(),
+                runtime: "llama.cpp".into(),
+                runtime_version: "2.31.2".into(),
+                enforcement_required: true,
+            },
+            state,
+        )
+    }
+
+    fn request() -> StructuredRequest {
+        StructuredRequest {
+            stage: QualityModelStage::Flash,
+            system_prompt: "Return one safe JSON object.",
+            payload: json!({
+                "output_schema": {
+                    "type": "object",
+                    "additionalProperties": false,
+                    "required": ["ok"],
+                    "properties": {"ok": {"type": "boolean"}}
+                },
+                "subject": {"safe": true}
+            }),
+            max_tokens: 100,
+        }
+    }
+
+    #[tokio::test]
+    async fn sends_strict_schema_without_tools_keys_or_thinking_options() {
+        let (config, state) = serve_fake_local_model("success").await;
+        let client = OpenAiCompatibleStructuredClient::new(config).unwrap();
+        let response = client.complete(&request()).await.unwrap();
+        assert_eq!(response.model_id, "ornith-1.5-9b");
+        assert_eq!(response.usage.prompt_tokens, 10);
+        assert_eq!(response.usage.prompt_cache_hit_tokens, 2);
+        assert_eq!(response.usage.prompt_cache_miss_tokens, 8);
+        assert_eq!(response.usage.completion_tokens, 4);
+        assert_eq!(response.usage.total_tokens, 14);
+        assert_eq!(state.models_calls.load(Ordering::SeqCst), 1);
+        let bodies = state.bodies.lock().unwrap();
+        assert_eq!(bodies[0]["response_format"]["type"], "json_schema");
+        assert_eq!(bodies[0]["response_format"]["json_schema"]["strict"], true);
+        assert!(bodies[0].get("tools").is_none());
+        assert!(bodies[0].get("thinking").is_none());
+    }
+
+    #[tokio::test]
+    async fn retries_one_transport_or_server_failure_but_not_invalid_output() {
+        let (config, state) = serve_fake_local_model("first_500").await;
+        OpenAiCompatibleStructuredClient::new(config)
+            .unwrap()
+            .complete(&request())
+            .await
+            .unwrap();
+        assert_eq!(state.chat_calls.load(Ordering::SeqCst), 2);
+
+        for mode in ["invalid_json", "tool_call", "oversized"] {
+            let (config, state) = serve_fake_local_model(mode).await;
+            assert!(OpenAiCompatibleStructuredClient::new(config)
+                .unwrap()
+                .complete(&request())
+                .await
+                .is_err());
+            assert_eq!(state.chat_calls.load(Ordering::SeqCst), 1, "mode {mode}");
+        }
+    }
+
+    #[tokio::test]
+    async fn rejects_model_identity_mismatch_and_redirects() {
+        let (config, state) = serve_fake_local_model("wrong_model").await;
+        assert!(OpenAiCompatibleStructuredClient::new(config)
+            .unwrap()
+            .complete(&request())
+            .await
+            .is_err());
+        assert_eq!(state.chat_calls.load(Ordering::SeqCst), 0);
+
+        let (config, state) = serve_fake_local_model("redirect").await;
+        assert!(OpenAiCompatibleStructuredClient::new(config)
+            .unwrap()
+            .complete(&request())
+            .await
+            .is_err());
+        assert_eq!(state.redirect_target_calls.load(Ordering::SeqCst), 0);
+    }
+
+    #[tokio::test]
+    async fn rejects_missing_schema_before_identity_request() {
+        let (config, state) = serve_fake_local_model("success").await;
+        let mut missing_schema = request();
+        missing_schema.payload.as_object_mut().unwrap().remove("output_schema");
+        assert!(OpenAiCompatibleStructuredClient::new(config)
+            .unwrap()
+            .complete(&missing_schema)
+            .await
+            .is_err());
+        assert_eq!(state.models_calls.load(Ordering::SeqCst), 0);
+    }
+}
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\task-2-baseline\crates\cerebellum-app\src\lib.rs', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'crates\cerebellum-app\src\lib.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-2-baseline\\crates\\cerebellum-app\\src\\lib.rs" "b/crates\\cerebellum-app\\src\\lib.rs"
index d672af0..86ed2ce 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-2-baseline\\crates\\cerebellum-app\\src\\lib.rs"
+++ "b/crates\\cerebellum-app\\src\\lib.rs"
@@ -12,6 +12,7 @@ pub mod importer;
 pub mod knowledge;
 pub mod knowledge_store;
 pub mod learning;
+pub mod local_model;
 mod learning_store;
 pub mod mcp;
 pub mod meta_training;
