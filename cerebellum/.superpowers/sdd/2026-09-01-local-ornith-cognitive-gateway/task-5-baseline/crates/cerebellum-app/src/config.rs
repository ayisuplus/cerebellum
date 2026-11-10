use anyhow::{Context, Result, bail};
use cerebellum_core::{BaseModelPin, ProviderPricingPolicy, validate_provider_pricing_policy};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fmt;
use std::fs;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct AutoDlGpuSpecConfig {
    pub id: String,
    pub display_name: String,
    pub memory_gb: u32,
    pub cuda: bool,
    #[serde(default)]
    pub data_centers: Vec<String>,
}

#[derive(Clone)]
pub struct AutoDlConfig {
    pub api_base_url: String,
    pub api_token: String,
    pub application_uuid: String,
    pub application_version: String,
    pub worker_gateway_url: String,
    pub gpu_allowlist: Vec<AutoDlGpuSpecConfig>,
    pub base_models: Vec<BaseModelPin>,
}

#[derive(Clone)]
pub struct QualityModelConfig {
    pub endpoint: String,
    pub api_key: String,
    pub flash_model: String,
    pub pro_model: String,
    pub enforcement_required: bool,
    pub private_redacted_allowed: bool,
    pub provider_training_optout_attested: bool,
    pub pricing: ProviderPricingPolicy,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LocalModelConfig {
    pub endpoint: String,
    pub model: String,
    pub artifact_sha256: String,
    pub runtime: String,
    pub runtime_version: String,
    pub enforcement_required: bool,
}

impl fmt::Debug for QualityModelConfig {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("QualityModelConfig")
            .field("endpoint", &self.endpoint)
            .field("api_key", &"[REDACTED]")
            .field("flash_model", &self.flash_model)
            .field("pro_model", &self.pro_model)
            .field("enforcement_required", &self.enforcement_required)
            .field("private_redacted_allowed", &self.private_redacted_allowed)
            .field(
                "provider_training_optout_attested",
                &self.provider_training_optout_attested,
            )
            .field("pricing", &self.pricing)
            .finish()
    }
}

impl fmt::Debug for AutoDlConfig {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("AutoDlConfig")
            .field("api_base_url", &self.api_base_url)
            .field("api_token", &"[REDACTED]")
            .field("application_uuid", &self.application_uuid)
            .field("application_version", &self.application_version)
            .field("worker_gateway_url", &self.worker_gateway_url)
            .field("gpu_allowlist", &self.gpu_allowlist)
            .field("base_models", &self.base_models)
            .finish()
    }
}

#[derive(Debug, Clone)]
pub struct AppConfig {
    pub data_dir: PathBuf,
    pub bind: SocketAddr,
    pub auth_token: String,
    pub signing_secret: Vec<u8>,
    pub router_backend: String,
    pub model_endpoint: Option<String>,
    pub model_name: Option<String>,
    pub model_api_key: Option<String>,
    pub knowledge_model_endpoint: Option<String>,
    pub knowledge_model_name: Option<String>,
    pub knowledge_model_api_key: Option<String>,
    pub quality_model: Option<QualityModelConfig>,
    pub local_model: Option<LocalModelConfig>,
    pub learning_scheduler_enabled: bool,
    pub github_webhook_secret: Option<Vec<u8>>,
    pub websub_secret: Option<Vec<u8>>,
    pub trainer_enabled: bool,
    pub github_token: Option<String>,
    pub github_watchlist: Vec<String>,
    pub meta_trainer_enabled: bool,
    pub meta_base_model: Option<String>,
    pub meta_data_license_policy: Option<String>,
    pub meta_gpu_memory_gb: Option<u32>,
    pub autodl: Option<AutoDlConfig>,
    pub admin_origin: String,
}

impl AppConfig {
    pub fn load(data_dir: PathBuf, bind: SocketAddr) -> Result<Self> {
        if !bind.ip().is_loopback() {
            bail!("cerebellumd may only bind to a loopback address");
        }
        fs::create_dir_all(&data_dir)
            .with_context(|| format!("create data directory {}", data_dir.display()))?;

        let auth_token = match std::env::var("CEREBELLUM_AUTH_TOKEN") {
            Ok(value) if value.len() >= 32 => value,
            Ok(_) => bail!("CEREBELLUM_AUTH_TOKEN is too short"),
            Err(_) => load_or_create(&data_dir.join("auth.token"), "auth")?,
        };
        let signing_secret = load_or_create(&data_dir.join("signing.key"), "signing")?.into_bytes();
        let meta_base_model = std::env::var("CEREBELLUM_META_BASE_MODEL").ok();
        let meta_data_license_policy = std::env::var("CEREBELLUM_META_DATA_LICENSE_POLICY").ok();
        let meta_gpu_memory_gb = std::env::var("CEREBELLUM_META_GPU_MEMORY_GB")
            .ok()
            .map(|value| {
                value
                    .parse::<u32>()
                    .context("CEREBELLUM_META_GPU_MEMORY_GB must be an integer")
            })
            .transpose()?;
        let meta_trainer_enabled = env_flag("CEREBELLUM_META_TRAINER_ENABLED", false);
        if meta_trainer_enabled
            && (meta_base_model.as_deref().is_none_or(str::is_empty)
                || meta_data_license_policy.as_deref() != Some("licensed-only")
                || meta_gpu_memory_gb.is_none_or(|memory| memory < 24))
        {
            bail!(
                "meta training requires an explicit base model, licensed-only data policy, and at least 24GB declared GPU memory"
            );
        }
        let knowledge_model_endpoint = nonempty_env("CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT");
        let knowledge_model_name = nonempty_env("CEREBELLUM_KNOWLEDGE_MODEL_NAME");
        if knowledge_model_endpoint.is_some() != knowledge_model_name.is_some() {
            bail!("knowledge model endpoint and name must be configured together");
        }
        let knowledge_model_api_key = nonempty_env("CEREBELLUM_KNOWLEDGE_MODEL_API_KEY");
        let quality_model = load_quality_model_config()?;
        let local_model = load_local_model_config()?;
        let autodl = load_autodl_config()?;
        let admin_origin = std::env::var("CEREBELLUM_ADMIN_ORIGIN")
            .unwrap_or_else(|_| "https://localhost:8443".into());
        let parsed_admin_origin = url::Url::parse(&admin_origin)
            .context("CEREBELLUM_ADMIN_ORIGIN must be an absolute URL")?;
        if parsed_admin_origin.scheme() != "https" || parsed_admin_origin.host_str().is_none() {
            bail!("CEREBELLUM_ADMIN_ORIGIN must use HTTPS and include a host");
        }
        Ok(Self {
            data_dir,
            bind,
            auth_token,
            signing_secret,
            router_backend: std::env::var("CEREBELLUM_ROUTER_BACKEND")
                .unwrap_or_else(|_| "deterministic".into()),
            model_endpoint: std::env::var("CEREBELLUM_MODEL_ENDPOINT").ok(),
            model_name: std::env::var("CEREBELLUM_MODEL_NAME").ok(),
            model_api_key: std::env::var("CEREBELLUM_MODEL_API_KEY").ok(),
            knowledge_model_endpoint,
            knowledge_model_name,
            knowledge_model_api_key,
            quality_model,
            local_model,
            learning_scheduler_enabled: env_flag("CEREBELLUM_LEARNING_SCHEDULER", false),
            github_webhook_secret: nonempty_env("CEREBELLUM_GITHUB_WEBHOOK_SECRET")
                .map(String::into_bytes),
            websub_secret: nonempty_env("CEREBELLUM_WEBSUB_SECRET").map(String::into_bytes),
            // The first v2 milestone explicitly produces manifests only. This
            // flag is surfaced in status so an accidental environment setting
            // cannot silently launch Python/GPU work.
            trainer_enabled: false,
            github_token: std::env::var("GITHUB_TOKEN").ok(),
            github_watchlist: std::env::var("CEREBELLUM_GITHUB_WATCHLIST")
                .ok()
                .map(|value| {
                    value
                        .split(',')
                        .map(str::trim)
                        .filter(|item| !item.is_empty())
                        .map(str::to_owned)
                        .collect()
                })
                .unwrap_or_default(),
            meta_trainer_enabled,
            meta_base_model,
            meta_data_license_policy,
            meta_gpu_memory_gb,
            autodl,
            admin_origin: admin_origin.trim_end_matches('/').into(),
        })
    }
}

fn load_local_model_config() -> Result<Option<LocalModelConfig>> {
    if !env_flag("CEREBELLUM_LOCAL_MODEL_ENABLED", false) {
        return Ok(None);
    }
    let endpoint = nonempty_env("CEREBELLUM_LOCAL_MODEL_ENDPOINT")
        .context("CEREBELLUM_LOCAL_MODEL_ENDPOINT is required")?;
    let parsed = url::Url::parse(&endpoint)
        .context("CEREBELLUM_LOCAL_MODEL_ENDPOINT must be an absolute URL")?;
    let literal_loopback = match parsed.host() {
        Some(url::Host::Ipv4(address)) => address == std::net::Ipv4Addr::LOCALHOST,
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

fn load_quality_model_config() -> Result<Option<QualityModelConfig>> {
    if !env_flag("CEREBELLUM_QUALITY_MODEL_ENABLED", false) {
        return Ok(None);
    }
    let endpoint =
        nonempty_env("DEEPSEEK_API_BASE_URL").unwrap_or_else(|| "https://api.deepseek.com".into());
    let parsed = url::Url::parse(&endpoint).context("invalid DEEPSEEK_API_BASE_URL")?;
    if parsed.scheme() != "https"
        || parsed.host_str() != Some("api.deepseek.com")
        || !matches!(parsed.path(), "" | "/")
        || parsed.username() != ""
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
    {
        bail!("DeepSeek quality API must use the exact https://api.deepseek.com origin");
    }
    let api_key = if let Some(path) = nonempty_env("DEEPSEEK_API_KEY_FILE") {
        fs::read_to_string(&path)
            .with_context(|| format!("read DeepSeek API key file {path}"))?
            .trim()
            .to_owned()
    } else {
        nonempty_env("DEEPSEEK_API_KEY").context("DeepSeek API key is required")?
    };
    if api_key.len() < 20 {
        bail!("DeepSeek API key is too short");
    }
    let flash_model =
        nonempty_env("DEEPSEEK_FLASH_MODEL").unwrap_or_else(|| "deepseek-v4-flash".into());
    let pro_model = nonempty_env("DEEPSEEK_PRO_MODEL").unwrap_or_else(|| "deepseek-v4-pro".into());
    if flash_model != "deepseek-v4-flash" || pro_model != "deepseek-v4-pro" {
        bail!("quality model names must be deepseek-v4-flash and deepseek-v4-pro");
    }
    let private_redacted_allowed =
        env_flag("CEREBELLUM_PRIVATE_REDACTED_EXTERNAL_PROCESSING", false);
    let provider_training_optout_attested =
        env_flag("CEREBELLUM_DEEPSEEK_TRAINING_OPTOUT_ATTESTED", false);
    if private_redacted_allowed && !provider_training_optout_attested {
        bail!("private redacted export requires a DeepSeek training opt-out attestation");
    }
    let confirmed_at = nonempty_env("DEEPSEEK_PRICING_CONFIRMED_AT")
        .context("DEEPSEEK_PRICING_CONFIRMED_AT is required")?;
    let confirmed_at = DateTime::parse_from_rfc3339(&confirmed_at)
        .context("DEEPSEEK_PRICING_CONFIRMED_AT must be RFC3339")?
        .with_timezone(&Utc);
    let pricing = ProviderPricingPolicy {
        schema_version: cerebellum_core::SCHEMA_VERSION.into(),
        policy_id: format!("deepseek-v4-{}", confirmed_at.date_naive()),
        provider: "deepseek".into(),
        // 当前官方 V4 峰值价（api-docs.deepseek.com/quick_start/pricing，
        // 2026-08 核对）。峰值=计费上界：离峰时段会多计成本，属保守方向，
        // 账本绝不少计。USD/CNY 8.0 同样是上界。
        flash_input_cache_hit_usd_per_million: 0.014,
        flash_input_cache_miss_usd_per_million: 0.44,
        flash_output_usd_per_million: 1.32,
        pro_input_cache_hit_usd_per_million: 0.044,
        pro_input_cache_miss_usd_per_million: 1.32,
        pro_output_usd_per_million: 3.96,
        usd_to_cny_ceiling: 8.0,
        daily_max_cny: nonempty_env("DEEPSEEK_DAILY_MAX_CNY")
            .unwrap_or_else(|| "10.0".into())
            .parse()
            .context("DEEPSEEK_DAILY_MAX_CNY must be numeric")?,
        confirmed_at,
    };
    validate_provider_pricing_policy(&pricing)?;
    if Utc::now() - pricing.confirmed_at > chrono::Duration::days(30) {
        bail!("DeepSeek pricing confirmation is older than 30 days");
    }
    Ok(Some(QualityModelConfig {
        endpoint: endpoint.trim_end_matches('/').into(),
        api_key,
        flash_model,
        pro_model,
        enforcement_required: env_flag("CEREBELLUM_QUALITY_ENFORCEMENT", true),
        private_redacted_allowed,
        provider_training_optout_attested,
        pricing,
    }))
}

fn load_autodl_config() -> Result<Option<AutoDlConfig>> {
    if !env_flag("CEREBELLUM_AUTODL_ENABLED", false) {
        return Ok(None);
    }
    let api_base_url =
        nonempty_env("AUTODL_API_BASE_URL").unwrap_or_else(|| "https://www.autodl.art".into());
    let parsed_api = url::Url::parse(&api_base_url).context("invalid AUTODL_API_BASE_URL")?;
    if parsed_api.scheme() != "https" || parsed_api.host_str().is_none() {
        bail!("AUTODL_API_BASE_URL must use HTTPS and include a host");
    }
    let api_token = nonempty_env("AUTODL_API_TOKEN").context("AUTODL_API_TOKEN is required")?;
    let application_uuid =
        nonempty_env("AUTODL_APPLICATION_UUID").context("AUTODL_APPLICATION_UUID is required")?;
    let application_version = nonempty_env("AUTODL_APPLICATION_VERSION")
        .context("AUTODL_APPLICATION_VERSION is required")?;
    if application_version.eq_ignore_ascii_case("latest") {
        bail!("AUTODL_APPLICATION_VERSION must be pinned and cannot be latest");
    }
    let worker_gateway_url = nonempty_env("CEREBELLUM_TRAINING_WORKER_GATEWAY_URL")
        .context("CEREBELLUM_TRAINING_WORKER_GATEWAY_URL is required")?;
    let parsed_gateway =
        url::Url::parse(&worker_gateway_url).context("invalid training worker gateway URL")?;
    if parsed_gateway.scheme() != "https" || parsed_gateway.host_str().is_none() {
        bail!("training worker gateway must use HTTPS and include a host");
    }
    let gpu_allowlist: Vec<AutoDlGpuSpecConfig> = serde_json::from_str(
        &nonempty_env("AUTODL_GPU_ALLOWLIST_JSON")
            .context("AUTODL_GPU_ALLOWLIST_JSON is required")?,
    )
    .context("AUTODL_GPU_ALLOWLIST_JSON must be valid JSON")?;
    if gpu_allowlist.is_empty()
        || gpu_allowlist.iter().any(|spec| {
            spec.id.trim().is_empty()
                || spec.display_name.trim().is_empty()
                || !spec.cuda
                || spec.memory_gb < 24
        })
    {
        bail!("AutoDL GPU allowlist entries must be NVIDIA CUDA specs with at least 24GB");
    }
    let mut spec_ids = std::collections::HashSet::new();
    if gpu_allowlist
        .iter()
        .any(|spec| !spec_ids.insert(spec.id.clone()))
    {
        bail!("AUTODL_GPU_ALLOWLIST_JSON contains duplicate spec ids");
    }
    let base_models: Vec<BaseModelPin> = serde_json::from_str(
        &nonempty_env("CEREBELLUM_TRAINING_BASE_MODELS_JSON")
            .context("CEREBELLUM_TRAINING_BASE_MODELS_JSON is required")?,
    )
    .context("CEREBELLUM_TRAINING_BASE_MODELS_JSON must be valid JSON")?;
    if base_models.is_empty() {
        bail!("at least one pinned training base model is required");
    }
    for model in &base_models {
        cerebellum_core::validate_base_model_pin(model)?;
    }
    Ok(Some(AutoDlConfig {
        api_base_url: api_base_url.trim_end_matches('/').into(),
        api_token,
        application_uuid,
        application_version,
        worker_gateway_url: worker_gateway_url.trim_end_matches('/').into(),
        gpu_allowlist,
        base_models,
    }))
}

fn env_flag(name: &str, default: bool) -> bool {
    std::env::var(name)
        .ok()
        .and_then(|value| match value.to_ascii_lowercase().as_str() {
            "1" | "true" | "yes" | "on" => Some(true),
            "0" | "false" | "no" | "off" => Some(false),
            _ => None,
        })
        .unwrap_or(default)
}

fn nonempty_env(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|value| value.trim().to_owned())
        .filter(|value| !value.is_empty())
}

fn load_or_create(path: &Path, purpose: &str) -> Result<String> {
    if path.exists() {
        let value = fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
        let value = value.trim();
        if value.len() < 32 {
            bail!("{} is too short", path.display());
        }
        return Ok(value.to_owned());
    }
    let material = format!("{}:{}:{}", purpose, Uuid::new_v4(), Uuid::new_v4());
    let value = format!("{:x}", Sha256::digest(material.as_bytes()));
    fs::write(path, format!("{value}\n")).with_context(|| format!("write {}", path.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
    }
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::*;
    use cerebellum_core::SCHEMA_VERSION;
    use std::sync::{Mutex, MutexGuard};
    use tempfile::tempdir;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    const CONFIG_ENV_VARS: &[&str] = &[
        "CEREBELLUM_AUTH_TOKEN",
        "CEREBELLUM_ROUTER_BACKEND",
        "CEREBELLUM_MODEL_ENDPOINT",
        "CEREBELLUM_MODEL_NAME",
        "CEREBELLUM_MODEL_API_KEY",
        "CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT",
        "CEREBELLUM_KNOWLEDGE_MODEL_NAME",
        "CEREBELLUM_KNOWLEDGE_MODEL_API_KEY",
        "CEREBELLUM_QUALITY_MODEL_ENABLED",
        "CEREBELLUM_QUALITY_ENFORCEMENT",
        "CEREBELLUM_LOCAL_MODEL_ENABLED",
        "CEREBELLUM_LOCAL_MODEL_ENDPOINT",
        "CEREBELLUM_LOCAL_MODEL_NAME",
        "CEREBELLUM_LOCAL_MODEL_SHA256",
        "CEREBELLUM_LOCAL_MODEL_RUNTIME",
        "CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION",
        "DEEPSEEK_API_BASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_API_KEY_FILE",
        "DEEPSEEK_FLASH_MODEL",
        "DEEPSEEK_PRO_MODEL",
        "DEEPSEEK_PRICING_CONFIRMED_AT",
        "DEEPSEEK_DAILY_MAX_CNY",
        "CEREBELLUM_PRIVATE_REDACTED_EXTERNAL_PROCESSING",
        "CEREBELLUM_DEEPSEEK_TRAINING_OPTOUT_ATTESTED",
        "CEREBELLUM_LEARNING_SCHEDULER",
        "CEREBELLUM_GITHUB_WEBHOOK_SECRET",
        "CEREBELLUM_WEBSUB_SECRET",
        "GITHUB_TOKEN",
        "CEREBELLUM_GITHUB_WATCHLIST",
        "CEREBELLUM_META_TRAINER_ENABLED",
        "CEREBELLUM_META_BASE_MODEL",
        "CEREBELLUM_META_DATA_LICENSE_POLICY",
        "CEREBELLUM_META_GPU_MEMORY_GB",
        "CEREBELLUM_AUTODL_ENABLED",
        "AUTODL_API_BASE_URL",
        "AUTODL_API_TOKEN",
        "AUTODL_APPLICATION_UUID",
        "AUTODL_APPLICATION_VERSION",
        "AUTODL_GPU_ALLOWLIST_JSON",
        "CEREBELLUM_TRAINING_WORKER_GATEWAY_URL",
        "CEREBELLUM_TRAINING_BASE_MODELS_JSON",
        "CEREBELLUM_ADMIN_ORIGIN",
    ];

    /// Serializes environment mutation across tests and restores the process
    /// environment on drop so parallel tests never observe each other's vars.
    struct EnvGuard {
        saved: Vec<(&'static str, Option<String>)>,
        _lock: MutexGuard<'static, ()>,
    }

    impl EnvGuard {
        fn cleared() -> Self {
            let lock = ENV_LOCK.lock().unwrap_or_else(|error| error.into_inner());
            let saved = CONFIG_ENV_VARS
                .iter()
                .map(|name| (*name, std::env::var(name).ok()))
                .collect::<Vec<_>>();
            for name in CONFIG_ENV_VARS {
                unsafe { std::env::remove_var(name) };
            }
            Self { saved, _lock: lock }
        }

        fn set(&self, name: &str, value: &str) {
            assert!(CONFIG_ENV_VARS.contains(&name), "untracked env var {name}");
            unsafe { std::env::set_var(name, value) };
        }

        /// Removes every tracked var again without releasing the env lock.
        fn reset(&self) {
            for name in CONFIG_ENV_VARS {
                unsafe { std::env::remove_var(name) };
            }
        }
    }

    impl Drop for EnvGuard {
        fn drop(&mut self) {
            for (name, value) in &self.saved {
                unsafe {
                    match value {
                        Some(value) => std::env::set_var(name, value),
                        None => std::env::remove_var(name),
                    }
                }
            }
        }
    }

    fn loopback() -> SocketAddr {
        "127.0.0.1:9443".parse().unwrap()
    }

    fn pricing_policy() -> ProviderPricingPolicy {
        ProviderPricingPolicy {
            schema_version: SCHEMA_VERSION.into(),
            policy_id: "deepseek-v4-test".into(),
            provider: "deepseek".into(),
            flash_input_cache_hit_usd_per_million: 0.014,
            flash_input_cache_miss_usd_per_million: 0.44,
            flash_output_usd_per_million: 1.32,
            pro_input_cache_hit_usd_per_million: 0.044,
            pro_input_cache_miss_usd_per_million: 1.32,
            pro_output_usd_per_million: 3.96,
            usd_to_cny_ceiling: 8.0,
            daily_max_cny: 10.0,
            confirmed_at: Utc::now(),
        }
    }

    fn set_valid_quality_env(env: &EnvGuard) {
        env.set("CEREBELLUM_QUALITY_MODEL_ENABLED", "true");
        env.set("DEEPSEEK_API_KEY", &"k".repeat(32));
        env.set("DEEPSEEK_PRICING_CONFIRMED_AT", &Utc::now().to_rfc3339());
    }

    const ORNITH_SHA256: &str =
        "894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da";

    fn set_valid_local_model_env(env: &EnvGuard) {
        env.set("CEREBELLUM_LOCAL_MODEL_ENABLED", "true");
        env.set("CEREBELLUM_LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:1234/v1");
        env.set("CEREBELLUM_LOCAL_MODEL_NAME", "ornith-1.5-9b");
        env.set("CEREBELLUM_LOCAL_MODEL_SHA256", ORNITH_SHA256);
        env.set(
            "CEREBELLUM_LOCAL_MODEL_RUNTIME",
            "llama.cpp-win-x86_64-nvidia-cuda12-avx2",
        );
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
            "http://127.0.0.2:1234/v1",
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

    fn set_valid_autodl_env(env: &EnvGuard) {
        env.set("CEREBELLUM_AUTODL_ENABLED", "true");
        env.set("AUTODL_API_TOKEN", "autodl-token");
        env.set("AUTODL_APPLICATION_UUID", "app-uuid-1");
        env.set("AUTODL_APPLICATION_VERSION", "1.2.3");
        env.set(
            "CEREBELLUM_TRAINING_WORKER_GATEWAY_URL",
            "https://gateway.example.com",
        );
        env.set(
            "AUTODL_GPU_ALLOWLIST_JSON",
            r#"[{"id":"rtx4090","display_name":"RTX 4090","memory_gb":24,"cuda":true}]"#,
        );
        env.set(
            "CEREBELLUM_TRAINING_BASE_MODELS_JSON",
            &format!(
                r#"[{{"model_id":"qwen3-32b","revision":"v1","sha256":"{}"}}]"#,
                "a".repeat(64)
            ),
        );
    }

    #[test]
    fn defaults_generate_persistent_secrets_and_safe_values() {
        let _env = EnvGuard::cleared();
        let dir = tempdir().unwrap();
        let data_dir = dir.path().join("nested").join("data");
        let config = AppConfig::load(data_dir.clone(), loopback()).unwrap();
        assert!(data_dir.is_dir());
        assert_eq!(config.data_dir, data_dir);
        assert_eq!(config.bind, loopback());
        assert_eq!(config.auth_token.len(), 64);
        assert!(config.auth_token.chars().all(|ch| ch.is_ascii_hexdigit()));
        assert_eq!(config.signing_secret.len(), 64);
        assert_eq!(config.router_backend, "deterministic");
        assert_eq!(config.admin_origin, "https://localhost:8443");
        assert!(!config.learning_scheduler_enabled);
        assert!(!config.trainer_enabled);
        assert!(!config.meta_trainer_enabled);
        assert!(config.model_endpoint.is_none());
        assert!(config.quality_model.is_none());
        assert!(config.autodl.is_none());
        assert!(config.github_webhook_secret.is_none());
        assert!(config.websub_secret.is_none());
        assert!(config.github_watchlist.is_empty());
        // A second load reuses the persisted material instead of rotating it.
        let reloaded = AppConfig::load(config.data_dir.clone(), loopback()).unwrap();
        assert_eq!(reloaded.auth_token, config.auth_token);
        assert_eq!(reloaded.signing_secret, config.signing_secret);
        // auth and signing material are independent secrets.
        assert_ne!(
            config.auth_token.as_bytes(),
            config.signing_secret.as_slice()
        );
        // A fresh data dir generates fresh random material (>= 32 bytes).
        let other = tempdir().unwrap();
        let other_config = AppConfig::load(other.path().join("data"), loopback()).unwrap();
        assert_ne!(other_config.auth_token, config.auth_token);
    }

    #[test]
    fn auth_token_env_override_wins_and_short_values_fail() {
        let env = EnvGuard::cleared();
        let dir = tempdir().unwrap();
        env.set("CEREBELLUM_AUTH_TOKEN", &"t".repeat(32));
        let config = AppConfig::load(dir.path().join("data"), loopback()).unwrap();
        assert_eq!(config.auth_token, "t".repeat(32));
        assert!(!dir.path().join("data").join("auth.token").exists());

        env.reset();
        env.set("CEREBELLUM_AUTH_TOKEN", "short");
        let error = AppConfig::load(dir.path().join("other"), loopback()).unwrap_err();
        assert!(
            format!("{error:#}").contains("CEREBELLUM_AUTH_TOKEN is too short"),
            "unexpected error: {error:#}"
        );
    }

    #[test]
    fn load_or_create_round_trips_and_rejects_short_material() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("secret.key");
        let created = load_or_create(&path, "test").unwrap();
        assert!(created.len() >= 32);
        // File content carries a trailing newline that reloads must trim.
        assert_eq!(fs::read_to_string(&path).unwrap(), format!("{created}\n"));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(&path).unwrap().permissions().mode() & 0o777,
                0o600
            );
        }
        assert_eq!(load_or_create(&path, "test").unwrap(), created);

        let short = dir.path().join("short.key");
        fs::write(&short, "too-short\n").unwrap();
        let error = load_or_create(&short, "test").unwrap_err();
        assert!(
            format!("{error:#}").contains("too short"),
            "unexpected error: {error:#}"
        );
    }

    #[test]
    fn env_flag_parses_truthy_falsy_and_falls_back_on_invalid() {
        let env = EnvGuard::cleared();
        let name = "CEREBELLUM_LEARNING_SCHEDULER";
        assert!(!env_flag(name, false));
        assert!(env_flag(name, true));
        for value in ["1", "true", "yes", "on", "TRUE", "Yes", "ON"] {
            env.set(name, value);
            assert!(env_flag(name, false), "value {value} must be truthy");
        }
        for value in ["0", "false", "no", "off", "FALSE", "No", "OFF"] {
            env.set(name, value);
            assert!(!env_flag(name, true), "value {value} must be falsy");
        }
        for value in ["maybe", "2", ""] {
            env.set(name, value);
            assert!(env_flag(name, true), "invalid value {value} keeps default");
            assert!(
                !env_flag(name, false),
                "invalid value {value} keeps default"
            );
        }
    }

    #[test]
    fn nonempty_env_trims_and_drops_blank_values() {
        let env = EnvGuard::cleared();
        let name = "CEREBELLUM_GITHUB_WEBHOOK_SECRET";
        assert_eq!(nonempty_env(name), None);
        env.set(name, "");
        assert_eq!(nonempty_env(name), None);
        env.set(name, "   ");
        assert_eq!(nonempty_env(name), None);
        env.set(name, "  secret  ");
        assert_eq!(nonempty_env(name), Some("secret".into()));
    }

    #[test]
    fn bind_must_be_a_loopback_address() {
        let _env = EnvGuard::cleared();
        let dir = tempdir().unwrap();
        let error =
            AppConfig::load(dir.path().join("a"), "0.0.0.0:9443".parse().unwrap()).unwrap_err();
        assert!(
            format!("{error:#}").contains("loopback"),
            "unexpected error: {error:#}"
        );
        assert!(
            AppConfig::load(dir.path().join("b"), "203.0.113.10:9443".parse().unwrap()).is_err()
        );
        assert!(AppConfig::load(dir.path().join("c"), "[::1]:9443".parse().unwrap()).is_ok());
    }

    #[test]
    fn meta_trainer_is_fail_closed_until_fully_attested() {
        let env = EnvGuard::cleared();
        let dir = tempdir().unwrap();
        env.set("CEREBELLUM_META_TRAINER_ENABLED", "true");
        let error = AppConfig::load(dir.path().join("a"), loopback()).unwrap_err();
        assert!(
            format!("{error:#}").contains("meta training requires"),
            "unexpected error: {error:#}"
        );

        env.set("CEREBELLUM_META_BASE_MODEL", "qwen3-32b");
        env.set("CEREBELLUM_META_DATA_LICENSE_POLICY", "anything-goes");
        env.set("CEREBELLUM_META_GPU_MEMORY_GB", "80");
        assert!(AppConfig::load(dir.path().join("b"), loopback()).is_err());

        env.set("CEREBELLUM_META_DATA_LICENSE_POLICY", "licensed-only");
        env.set("CEREBELLUM_META_GPU_MEMORY_GB", "23");
        assert!(AppConfig::load(dir.path().join("c"), loopback()).is_err());

        env.set("CEREBELLUM_META_GPU_MEMORY_GB", "not-a-number");
        let error = AppConfig::load(dir.path().join("d"), loopback()).unwrap_err();
        assert!(
            format!("{error:#}").contains("CEREBELLUM_META_GPU_MEMORY_GB must be an integer"),
            "unexpected error: {error:#}"
        );

        env.set("CEREBELLUM_META_GPU_MEMORY_GB", "24");
        let config = AppConfig::load(dir.path().join("e"), loopback()).unwrap();
        assert!(config.meta_trainer_enabled);
        assert_eq!(config.meta_base_model.as_deref(), Some("qwen3-32b"));
        assert_eq!(config.meta_gpu_memory_gb, Some(24));
    }

    #[test]
    fn knowledge_model_endpoint_and_name_are_configured_together() {
        let env = EnvGuard::cleared();
        let dir = tempdir().unwrap();
        env.set(
            "CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT",
            "https://llm.example.com",
        );
        let error = AppConfig::load(dir.path().join("a"), loopback()).unwrap_err();
        assert!(
            format!("{error:#}").contains("must be configured together"),
            "unexpected error: {error:#}"
        );

        env.reset();
        env.set("CEREBELLUM_KNOWLEDGE_MODEL_NAME", "knowledge-v1");
        assert!(AppConfig::load(dir.path().join("b"), loopback()).is_err());

        env.set(
            "CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT",
            "https://llm.example.com",
        );
        env.set("CEREBELLUM_KNOWLEDGE_MODEL_API_KEY", "key");
        let config = AppConfig::load(dir.path().join("c"), loopback()).unwrap();
        assert_eq!(
            config.knowledge_model_endpoint.as_deref(),
            Some("https://llm.example.com")
        );
        assert_eq!(config.knowledge_model_name.as_deref(), Some("knowledge-v1"));
        assert_eq!(config.knowledge_model_api_key.as_deref(), Some("key"));
    }

    #[test]
    fn quality_model_is_disabled_by_default_and_fail_closed_when_enabled() {
        let env = EnvGuard::cleared();
        assert!(load_quality_model_config().unwrap().is_none());

        env.set("CEREBELLUM_QUALITY_MODEL_ENABLED", "true");
        let error = load_quality_model_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("DeepSeek API key is required"),
            "unexpected error: {error:#}"
        );

        env.set("DEEPSEEK_API_KEY", "short");
        let error = load_quality_model_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("too short"),
            "unexpected error: {error:#}"
        );
    }

    #[test]
    fn quality_model_requires_the_exact_deepseek_origin() {
        let env = EnvGuard::cleared();
        set_valid_quality_env(&env);
        for bad in [
            "http://api.deepseek.com",
            "https://api.deepseek.com.evil.example",
            "https://api.deepseek.com/v1",
            "https://user:pass@api.deepseek.com",
            "https://api.deepseek.com/?x=1",
        ] {
            env.set("DEEPSEEK_API_BASE_URL", bad);
            let error = load_quality_model_config().unwrap_err();
            assert!(
                format!("{error:#}").contains("exact https://api.deepseek.com origin"),
                "endpoint {bad} must be rejected: {error:#}"
            );
        }
        env.set("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com/");
        let config = load_quality_model_config().unwrap().unwrap();
        assert_eq!(config.endpoint, "https://api.deepseek.com");
    }

    #[test]
    fn quality_model_names_and_model_overrides_are_pinned() {
        let env = EnvGuard::cleared();
        set_valid_quality_env(&env);
        env.set("DEEPSEEK_FLASH_MODEL", "deepseek-v3-flash");
        assert!(load_quality_model_config().is_err());

        env.reset();
        set_valid_quality_env(&env);
        env.set("DEEPSEEK_PRO_MODEL", "gpt-4o");
        assert!(load_quality_model_config().is_err());
    }

    #[test]
    fn quality_model_pricing_policy_is_validated() {
        let env = EnvGuard::cleared();
        set_valid_quality_env(&env);
        // Confirmation timestamp is mandatory before pricing can be trusted.
        unsafe { std::env::remove_var("DEEPSEEK_PRICING_CONFIRMED_AT") };
        let error = load_quality_model_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("DEEPSEEK_PRICING_CONFIRMED_AT is required"),
            "unexpected error: {error:#}"
        );

        env.set("DEEPSEEK_PRICING_CONFIRMED_AT", "not-a-date");
        assert!(load_quality_model_config().is_err());

        env.set(
            "DEEPSEEK_PRICING_CONFIRMED_AT",
            &(Utc::now() - chrono::Duration::days(31)).to_rfc3339(),
        );
        let error = load_quality_model_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("older than 30 days"),
            "unexpected error: {error:#}"
        );

        env.set("DEEPSEEK_PRICING_CONFIRMED_AT", &Utc::now().to_rfc3339());
        env.set("DEEPSEEK_DAILY_MAX_CNY", "not-numeric");
        assert!(load_quality_model_config().is_err());

        // Above the policy ceiling the pricing policy validation fails closed.
        env.set("DEEPSEEK_DAILY_MAX_CNY", "10.01");
        assert!(load_quality_model_config().is_err());

        // Boundary value passes and yields the pinned policy.
        env.set("DEEPSEEK_DAILY_MAX_CNY", "10.0");
        let config = load_quality_model_config().unwrap().unwrap();
        assert_eq!(config.pricing.daily_max_cny, 10.0);
        assert!(config.enforcement_required);
    }

    #[test]
    fn quality_model_redacted_export_requires_training_optout_attestation() {
        let env = EnvGuard::cleared();
        set_valid_quality_env(&env);
        env.set("CEREBELLUM_PRIVATE_REDACTED_EXTERNAL_PROCESSING", "true");
        let error = load_quality_model_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("training opt-out attestation"),
            "unexpected error: {error:#}"
        );
        env.set("CEREBELLUM_DEEPSEEK_TRAINING_OPTOUT_ATTESTED", "yes");
        let config = load_quality_model_config().unwrap().unwrap();
        assert!(config.private_redacted_allowed);
        assert!(config.provider_training_optout_attested);
    }

    #[test]
    fn quality_model_reads_api_key_from_file_and_trims_it() {
        let env = EnvGuard::cleared();
        set_valid_quality_env(&env);
        let dir = tempdir().unwrap();
        let key_file = dir.path().join("deepseek.key");
        let file_key = "f".repeat(40);
        fs::write(&key_file, format!("  {file_key}  \n")).unwrap();
        env.set("DEEPSEEK_API_KEY_FILE", key_file.to_str().unwrap());
        let config = load_quality_model_config().unwrap().unwrap();
        // The key file wins over the environment variable and is trimmed.
        assert_eq!(config.api_key, file_key);
    }

    #[test]
    fn autodl_is_disabled_by_default_and_fail_closed_when_enabled() {
        let env = EnvGuard::cleared();
        assert!(load_autodl_config().unwrap().is_none());

        env.set("CEREBELLUM_AUTODL_ENABLED", "true");
        let error = load_autodl_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("AUTODL_API_TOKEN is required"),
            "unexpected error: {error:#}"
        );

        env.set("AUTODL_API_TOKEN", "token");
        let error = load_autodl_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("AUTODL_APPLICATION_UUID is required"),
            "unexpected error: {error:#}"
        );

        env.set("AUTODL_APPLICATION_UUID", "uuid");
        let error = load_autodl_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("AUTODL_APPLICATION_VERSION is required"),
            "unexpected error: {error:#}"
        );
    }

    #[test]
    fn autodl_requires_pinned_version_https_urls_and_valid_allowlist() {
        let env = EnvGuard::cleared();
        set_valid_autodl_env(&env);

        env.set("AUTODL_APPLICATION_VERSION", "LATEST");
        let error = load_autodl_config().unwrap_err();
        assert!(
            format!("{error:#}").contains("cannot be latest"),
            "unexpected error: {error:#}"
        );

        env.reset();
        set_valid_autodl_env(&env);
        env.set("AUTODL_API_BASE_URL", "http://www.autodl.art");
        assert!(load_autodl_config().is_err());

        env.reset();
        set_valid_autodl_env(&env);
        env.set(
            "CEREBELLUM_TRAINING_WORKER_GATEWAY_URL",
            "http://gateway.example.com",
        );
        assert!(load_autodl_config().is_err());

        for bad_allowlist in [
            "not-json",
            "[]",
            r#"[{"id":"a100","display_name":"A100","memory_gb":40,"cuda":false}]"#,
            r#"[{"id":"rtx3080","display_name":"RTX 3080","memory_gb":10,"cuda":true}]"#,
            r#"[{"id":"rtx4090","display_name":"RTX 4090","memory_gb":24,"cuda":true},{"id":"rtx4090","display_name":"dup","memory_gb":24,"cuda":true}]"#,
        ] {
            env.reset();
            set_valid_autodl_env(&env);
            env.set("AUTODL_GPU_ALLOWLIST_JSON", bad_allowlist);
            assert!(
                load_autodl_config().is_err(),
                "allowlist {bad_allowlist} must be rejected"
            );
        }

        env.reset();
        set_valid_autodl_env(&env);
        env.set("CEREBELLUM_TRAINING_BASE_MODELS_JSON", "[]");
        assert!(load_autodl_config().is_err());
        env.set(
            "CEREBELLUM_TRAINING_BASE_MODELS_JSON",
            r#"[{"model_id":"qwen3-32b","revision":"v1","sha256":"not-a-sha"}]"#,
        );
        assert!(load_autodl_config().is_err());

        env.reset();
        set_valid_autodl_env(&env);
        let config = load_autodl_config().unwrap().unwrap();
        assert_eq!(config.api_base_url, "https://www.autodl.art");
        assert_eq!(config.gpu_allowlist.len(), 1);
        assert_eq!(config.base_models.len(), 1);
    }

    #[test]
    fn admin_origin_must_be_absolute_https_and_is_trimmed() {
        let env = EnvGuard::cleared();
        let dir = tempdir().unwrap();
        env.set("CEREBELLUM_ADMIN_ORIGIN", "http://admin.example.com");
        assert!(AppConfig::load(dir.path().join("a"), loopback()).is_err());

        env.set("CEREBELLUM_ADMIN_ORIGIN", "not a url");
        assert!(AppConfig::load(dir.path().join("b"), loopback()).is_err());

        env.set("CEREBELLUM_ADMIN_ORIGIN", "https://admin.example.com/");
        let config = AppConfig::load(dir.path().join("c"), loopback()).unwrap();
        assert_eq!(config.admin_origin, "https://admin.example.com");
    }

    #[test]
    fn github_watchlist_and_secret_envs_are_parsed() {
        let env = EnvGuard::cleared();
        let dir = tempdir().unwrap();
        env.set(
            "CEREBELLUM_GITHUB_WATCHLIST",
            " openai/example , ,rust-lang/rust ",
        );
        env.set("CEREBELLUM_GITHUB_WEBHOOK_SECRET", "hook-secret");
        env.set("CEREBELLUM_WEBSUB_SECRET", "   ");
        env.set("GITHUB_TOKEN", "ghp_test");
        let config = AppConfig::load(dir.path().join("data"), loopback()).unwrap();
        assert_eq!(
            config.github_watchlist,
            vec!["openai/example".to_string(), "rust-lang/rust".to_string()]
        );
        assert_eq!(
            config.github_webhook_secret.as_deref(),
            Some(b"hook-secret".as_slice())
        );
        assert!(config.websub_secret.is_none());
        assert_eq!(config.github_token.as_deref(), Some("ghp_test"));
    }

    #[test]
    fn debug_impls_never_leak_secrets() {
        let quality = QualityModelConfig {
            endpoint: "https://api.deepseek.com".into(),
            api_key: "sk-super-secret-quality-key".into(),
            flash_model: "deepseek-v4-flash".into(),
            pro_model: "deepseek-v4-pro".into(),
            enforcement_required: true,
            private_redacted_allowed: false,
            provider_training_optout_attested: false,
            pricing: pricing_policy(),
        };
        let rendered = format!("{quality:?}");
        assert!(rendered.contains("[REDACTED]"));
        assert!(!rendered.contains("sk-super-secret-quality-key"));

        let autodl = AutoDlConfig {
            api_base_url: "https://www.autodl.art".into(),
            api_token: "autodl-super-secret-token".into(),
            application_uuid: "uuid".into(),
            application_version: "1.0.0".into(),
            worker_gateway_url: "https://gateway.example.com".into(),
            gpu_allowlist: vec![AutoDlGpuSpecConfig {
                id: "rtx4090".into(),
                display_name: "RTX 4090".into(),
                memory_gb: 24,
                cuda: true,
                data_centers: vec![],
            }],
            base_models: vec![BaseModelPin {
                model_id: "qwen3-32b".into(),
                revision: "v1".into(),
                sha256: "a".repeat(64),
            }],
        };
        let rendered = format!("{autodl:?}");
        assert!(rendered.contains("[REDACTED]"));
        assert!(!rendered.contains("autodl-super-secret-token"));
    }
}
