# Task 1 review package

Task brief: task-1-brief.md
Implementer report: task-1-implementer.md
Comparison: task-start snapshots to current working tree; no commits or staging.

warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\task-1-baseline\crates\cerebellum-app\src\config.rs', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'crates\cerebellum-app\src\config.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-1-baseline\\crates\\cerebellum-app\\src\\config.rs" "b/crates\\cerebellum-app\\src\\config.rs"
index c819afa..6c9f5a4 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-1-baseline\\crates\\cerebellum-app\\src\\config.rs"
+++ "b/crates\\cerebellum-app\\src\\config.rs"
@@ -43,6 +43,16 @@ pub struct QualityModelConfig {
     pub pricing: ProviderPricingPolicy,
 }
 
+#[derive(Debug, Clone, PartialEq, Eq)]
+pub struct LocalModelConfig {
+    pub endpoint: String,
+    pub model: String,
+    pub artifact_sha256: String,
+    pub runtime: String,
+    pub runtime_version: String,
+    pub enforcement_required: bool,
+}
+
 impl fmt::Debug for QualityModelConfig {
     fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
         formatter
@@ -91,6 +101,7 @@ pub struct AppConfig {
     pub knowledge_model_name: Option<String>,
     pub knowledge_model_api_key: Option<String>,
     pub quality_model: Option<QualityModelConfig>,
+    pub local_model: Option<LocalModelConfig>,
     pub learning_scheduler_enabled: bool,
     pub github_webhook_secret: Option<Vec<u8>>,
     pub websub_secret: Option<Vec<u8>>,
@@ -146,6 +157,7 @@ impl AppConfig {
         }
         let knowledge_model_api_key = nonempty_env("CEREBELLUM_KNOWLEDGE_MODEL_API_KEY");
         let quality_model = load_quality_model_config()?;
+        let local_model = load_local_model_config()?;
         let autodl = load_autodl_config()?;
         let admin_origin = std::env::var("CEREBELLUM_ADMIN_ORIGIN")
             .unwrap_or_else(|_| "https://localhost:8443".into());
@@ -168,6 +180,7 @@ impl AppConfig {
             knowledge_model_name,
             knowledge_model_api_key,
             quality_model,
+            local_model,
             learning_scheduler_enabled: env_flag("CEREBELLUM_LEARNING_SCHEDULER", false),
             github_webhook_secret: nonempty_env("CEREBELLUM_GITHUB_WEBHOOK_SECRET")
                 .map(String::into_bytes),
@@ -198,6 +211,50 @@ impl AppConfig {
     }
 }
 
+fn load_local_model_config() -> Result<Option<LocalModelConfig>> {
+    if !env_flag("CEREBELLUM_LOCAL_MODEL_ENABLED", false) {
+        return Ok(None);
+    }
+    let endpoint = nonempty_env("CEREBELLUM_LOCAL_MODEL_ENDPOINT")
+        .context("CEREBELLUM_LOCAL_MODEL_ENDPOINT is required")?;
+    let parsed = url::Url::parse(&endpoint)
+        .context("CEREBELLUM_LOCAL_MODEL_ENDPOINT must be an absolute URL")?;
+    let literal_loopback = match parsed.host() {
+        Some(url::Host::Ipv4(address)) => address == std::net::Ipv4Addr::LOCALHOST,
+        Some(url::Host::Ipv6(address)) => address.is_loopback(),
+        _ => false,
+    };
+    if parsed.scheme() != "http"
+        || !literal_loopback
+        || parsed.username() != ""
+        || parsed.password().is_some()
+        || parsed.query().is_some()
+        || parsed.fragment().is_some()
+        || !matches!(parsed.path(), "/" | "/v1")
+    {
+        bail!("local model endpoint must be a literal loopback HTTP root or /v1 URL");
+    }
+    let artifact_sha256 = nonempty_env("CEREBELLUM_LOCAL_MODEL_SHA256")
+        .context("CEREBELLUM_LOCAL_MODEL_SHA256 is required")?
+        .to_ascii_lowercase();
+    if artifact_sha256.len() != 64
+        || !artifact_sha256.bytes().all(|byte| byte.is_ascii_hexdigit())
+    {
+        bail!("CEREBELLUM_LOCAL_MODEL_SHA256 must be a SHA-256 hex digest");
+    }
+    Ok(Some(LocalModelConfig {
+        endpoint: endpoint.trim_end_matches('/').into(),
+        model: nonempty_env("CEREBELLUM_LOCAL_MODEL_NAME")
+            .context("CEREBELLUM_LOCAL_MODEL_NAME is required")?,
+        artifact_sha256,
+        runtime: nonempty_env("CEREBELLUM_LOCAL_MODEL_RUNTIME")
+            .context("CEREBELLUM_LOCAL_MODEL_RUNTIME is required")?,
+        runtime_version: nonempty_env("CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION")
+            .context("CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION is required")?,
+        enforcement_required: env_flag("CEREBELLUM_QUALITY_ENFORCEMENT", true),
+    }))
+}
+
 fn load_quality_model_config() -> Result<Option<QualityModelConfig>> {
     if !env_flag("CEREBELLUM_QUALITY_MODEL_ENABLED", false) {
         return Ok(None);
@@ -407,6 +464,12 @@ mod tests {
         "CEREBELLUM_KNOWLEDGE_MODEL_API_KEY",
         "CEREBELLUM_QUALITY_MODEL_ENABLED",
         "CEREBELLUM_QUALITY_ENFORCEMENT",
+        "CEREBELLUM_LOCAL_MODEL_ENABLED",
+        "CEREBELLUM_LOCAL_MODEL_ENDPOINT",
+        "CEREBELLUM_LOCAL_MODEL_NAME",
+        "CEREBELLUM_LOCAL_MODEL_SHA256",
+        "CEREBELLUM_LOCAL_MODEL_RUNTIME",
+        "CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION",
         "DEEPSEEK_API_BASE_URL",
         "DEEPSEEK_API_KEY",
         "DEEPSEEK_API_KEY_FILE",
@@ -509,6 +572,54 @@ mod tests {
         env.set("DEEPSEEK_PRICING_CONFIRMED_AT", &Utc::now().to_rfc3339());
     }
 
+    const ORNITH_SHA256: &str =
+        "894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da";
+
+    fn set_valid_local_model_env(env: &EnvGuard) {
+        env.set("CEREBELLUM_LOCAL_MODEL_ENABLED", "true");
+        env.set("CEREBELLUM_LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:1234/v1");
+        env.set("CEREBELLUM_LOCAL_MODEL_NAME", "ornith-1.5-9b");
+        env.set("CEREBELLUM_LOCAL_MODEL_SHA256", ORNITH_SHA256);
+        env.set(
+            "CEREBELLUM_LOCAL_MODEL_RUNTIME",
+            "llama.cpp-win-x86_64-nvidia-cuda12-avx2",
+        );
+        env.set("CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION", "2.31.2");
+    }
+
+    #[test]
+    fn local_model_is_disabled_by_default_and_requires_complete_pins() {
+        let env = EnvGuard::cleared();
+        assert!(load_local_model_config().unwrap().is_none());
+        env.set("CEREBELLUM_LOCAL_MODEL_ENABLED", "true");
+        let error = load_local_model_config().unwrap_err();
+        assert!(format!("{error:#}").contains("CEREBELLUM_LOCAL_MODEL_ENDPOINT"));
+        set_valid_local_model_env(&env);
+        let config = load_local_model_config().unwrap().unwrap();
+        assert_eq!(config.model, "ornith-1.5-9b");
+        assert_eq!(config.artifact_sha256, ORNITH_SHA256);
+    }
+
+    #[test]
+    fn local_model_rejects_non_literal_or_non_loopback_endpoints() {
+        let env = EnvGuard::cleared();
+        set_valid_local_model_env(&env);
+        for endpoint in [
+            "http://localhost:1234/v1",
+            "http://127.0.0.2:1234/v1",
+            "http://192.168.1.10:1234/v1",
+            "https://127.0.0.1:1234/v1",
+            "http://user:pass@127.0.0.1:1234/v1",
+            "http://127.0.0.1:1234/v1?redirect=https://example.com",
+            "http://127.0.0.1:1234/other",
+        ] {
+            env.set("CEREBELLUM_LOCAL_MODEL_ENDPOINT", endpoint);
+            assert!(load_local_model_config().is_err(), "accepted {endpoint}");
+        }
+        env.set("CEREBELLUM_LOCAL_MODEL_ENDPOINT", "http://[::1]:1234/v1");
+        assert!(load_local_model_config().is_ok());
+    }
+
     fn set_valid_autodl_env(env: &EnvGuard) {
         env.set("CEREBELLUM_AUTODL_ENABLED", "true");
         env.set("AUTODL_API_TOKEN", "autodl-token");
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\task-1-baseline\crates\cerebellum-app\src\api.rs', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'crates\cerebellum-app\src\api.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-1-baseline\\crates\\cerebellum-app\\src\\api.rs" "b/crates\\cerebellum-app\\src\\api.rs"
index 8eae483..f0b861b 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-1-baseline\\crates\\cerebellum-app\\src\\api.rs"
+++ "b/crates\\cerebellum-app\\src\\api.rs"
@@ -1206,6 +1206,7 @@ mod tests {
             knowledge_model_name: None,
             knowledge_model_api_key: None,
             quality_model: None,
+            local_model: None,
             learning_scheduler_enabled: false,
             github_webhook_secret: None,
             websub_secret: None,
@@ -1647,6 +1648,7 @@ mod tests {
             knowledge_model_name: None,
             knowledge_model_api_key: None,
             quality_model: None,
+            local_model: None,
             learning_scheduler_enabled: false,
             github_webhook_secret: Some(secret.clone()),
             websub_secret: None,
@@ -1715,6 +1717,7 @@ mod tests {
             knowledge_model_name: None,
             knowledge_model_api_key: None,
             quality_model: None,
+            local_model: None,
             learning_scheduler_enabled: false,
             github_webhook_secret: None,
             websub_secret: Some(secret.clone()),
