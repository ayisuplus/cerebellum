use crate::Registry;
use crate::config::{AutoDlConfig, AutoDlGpuSpecConfig};
use crate::meta_training::{META_TRAINING_COOLDOWN_DAYS, MIN_META_DECISIONS, MIN_META_REPLAYS};
use anyhow::{Context, Result, anyhow, bail};
use async_trait::async_trait;
use cerebellum_core::{
    ArtifactVersionRef, CancelTrainingRunRequest, CreateTrainingRunRequest, DatasetSnapshotRecord,
    ExpertAdapterOperationRequest, ExpertAdapterRef, ExpertAdapterStatus, ExpertAdapterVersion,
    GpuLease, GpuLeaseStatus, MetaModelBundle, MetaModelMetrics, MetaModelStatus,
    RoutedAdapterBundleManifest, SCHEMA_VERSION, StartTrainingRunRequest, TrainingRun,
    TrainingRunDetail, TrainingRunEvent, TrainingRunStatus, validate_create_training_run,
    validate_expert_adapter_version, validate_expert_dataset_view, validate_routed_adapter_bundle,
};
use chrono::{DateTime, Duration, Utc};
use reqwest::Method;
use rusqlite::{OptionalExtension, params};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::Read;
use std::sync::Arc;
use uuid::Uuid;

pub const WORKER_BOOTSTRAP_TTL_SECONDS: i64 = 600;
pub const WORKER_SESSION_TTL_SECONDS: i64 = 900;
/// How long a rotated-out worker token remains valid so in-flight requests
/// (long uploads, completion) that captured it before the last heartbeat
/// rotation do not fail. Bounded well under the session TTL.
const REPLACED_TOKEN_GRACE_SECONDS: i64 = 60;
pub const WORKER_HEARTBEAT_TIMEOUT_SECONDS: i64 = 600;
pub const MAX_TRAINING_ARTIFACT_BYTES: u64 = 512 * 1024 * 1024;

#[derive(Debug, Clone, Copy)]
struct TrainingReadinessThresholds {
    decisions: u64,
    replays: u64,
}

#[derive(Debug, Clone)]
pub struct ProvisionRequest {
    pub run_id: Uuid,
    pub application_uuid: String,
    pub application_version: String,
    pub gpu_spec: AutoDlGpuSpecConfig,
    pub start_command: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ProvisionOutcome {
    Created { instance_id: String },
    WaitingCapacity { reason: String },
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProviderInstanceSnapshot {
    pub instance_id: String,
    pub status: String,
    pub hourly_price_cny: f64,
    pub gpu_name: String,
    pub chip_vendor: String,
}

#[async_trait]
pub trait GpuProvider: Send + Sync {
    fn name(&self) -> &'static str;
    async fn create_instance(&self, request: &ProvisionRequest) -> Result<ProvisionOutcome>;
    async fn instance_snapshot(&self, instance_id: &str) -> Result<ProviderInstanceSnapshot>;
    async fn instance_status(&self, instance_id: &str) -> Result<String>;
    async fn power_off(&self, instance_id: &str) -> Result<()>;
    async fn release(&self, instance_id: &str) -> Result<()>;
}

#[derive(Clone)]
pub struct AutoDlAppProvider {
    client: reqwest::Client,
    base_url: String,
    token: String,
}

impl AutoDlAppProvider {
    pub fn new(config: &AutoDlConfig) -> Result<Self> {
        Ok(Self {
            client: reqwest::Client::builder()
                .connect_timeout(std::time::Duration::from_secs(15))
                .timeout(std::time::Duration::from_secs(60))
                .build()?,
            base_url: config.api_base_url.trim_end_matches('/').into(),
            token: config.api_token.clone(),
        })
    }

    async fn call(&self, method: Method, path: &str, body: Value) -> Result<Value> {
        let response = self
            .client
            .request(method, format!("{}{}", self.base_url, path))
            // AutoDL's application API expects the developer token directly,
            // not a Bearer prefix.
            .header("Authorization", &self.token)
            .json(&body)
            .send()
            .await
            .context("AutoDL API request failed")?;
        let status = response.status();
        let bytes = response.bytes().await.context("read AutoDL API response")?;
        let envelope: Value =
            serde_json::from_slice(&bytes).context("AutoDL API returned a non-JSON response")?;
        let code = envelope
            .get("code")
            .and_then(Value::as_str)
            .unwrap_or("Unknown");
        if !status.is_success() || code != "Success" {
            let message = envelope
                .get("msg")
                .and_then(Value::as_str)
                .unwrap_or("request rejected");
            let request_id = envelope
                .get("request_id")
                .and_then(Value::as_str)
                .unwrap_or("unknown");
            bail!("AutoDL API {code}: {message} (request {request_id})");
        }
        Ok(envelope.get("data").cloned().unwrap_or(Value::Null))
    }
}

#[async_trait]
impl GpuProvider for AutoDlAppProvider {
    fn name(&self) -> &'static str {
        "autodl-app"
    }

    async fn create_instance(&self, request: &ProvisionRequest) -> Result<ProvisionOutcome> {
        let body = json!({
            "data_center_list":request.gpu_spec.data_centers,
            "req_gpu_amount":1,
            "expand_system_disk_by_gb":0,
            "gpu_spec_uuid":request.gpu_spec.id,
            "application_uuid":request.application_uuid,
            "application_version":request.application_version,
            "instance_name":format!("cerebellum-{}", request.run_id.simple()),
            "start_command":request.start_command
        });
        match self
            .call(
                Method::POST,
                "/api/v1/adl_dev/dev/instance/pro/create",
                body,
            )
            .await
        {
            Ok(Value::String(instance_id)) if !instance_id.trim().is_empty() => {
                Ok(ProvisionOutcome::Created { instance_id })
            }
            Ok(_) => bail!("AutoDL create response lacks an instance id"),
            Err(error) if is_capacity_error(&error.to_string()) => {
                Ok(ProvisionOutcome::WaitingCapacity {
                    reason: sanitize_provider_error(&error.to_string()),
                })
            }
            Err(error) => Err(error),
        }
    }

    async fn instance_snapshot(&self, instance_id: &str) -> Result<ProviderInstanceSnapshot> {
        let data = self
            .call(
                Method::GET,
                "/api/v1/adl_dev/dev/instance/pro/snapshot",
                json!({"instance_uuid":instance_id}),
            )
            .await?;
        let raw_price = data
            .get("payg_price")
            .and_then(Value::as_f64)
            .ok_or_else(|| anyhow!("AutoDL snapshot lacks payg_price"))?;
        // AutoDL prices use thousandths of CNY (e.g. 1970 = CNY 1.970).
        let hourly_price_cny = raw_price / 1_000.0;
        if !hourly_price_cny.is_finite() || hourly_price_cny <= 0.0 {
            bail!("AutoDL returned an invalid hourly price");
        }
        Ok(ProviderInstanceSnapshot {
            instance_id: instance_id.into(),
            status: data
                .pointer("/usage_info/valid")
                .and_then(Value::as_bool)
                .map(|valid| if valid { "running" } else { "initializing" })
                .unwrap_or("unknown")
                .into(),
            hourly_price_cny,
            gpu_name: data
                .get("snapshot_gpu_alias_name")
                .and_then(Value::as_str)
                .unwrap_or("unknown")
                .into(),
            chip_vendor: data
                .get("chip_corp")
                .and_then(Value::as_str)
                .unwrap_or("unknown")
                .into(),
        })
    }

    async fn instance_status(&self, instance_id: &str) -> Result<String> {
        self.call(
            Method::GET,
            "/api/v1/adl_dev/dev/instance/pro/status",
            json!({"instance_uuid":instance_id}),
        )
        .await?
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| anyhow!("AutoDL status response is not a string"))
    }

    async fn power_off(&self, instance_id: &str) -> Result<()> {
        self.call(
            Method::POST,
            "/api/v1/adl_dev/dev/instance/pro/power_off",
            json!({"instance_uuid":instance_id}),
        )
        .await?;
        Ok(())
    }

    async fn release(&self, instance_id: &str) -> Result<()> {
        self.call(
            Method::POST,
            "/api/v1/adl_dev/dev/instance/pro/release",
            json!({"instance_uuid":instance_id}),
        )
        .await?;
        Ok(())
    }
}

/// Zero-spend loopback provider for operator-approved on-machine training
/// (e.g. a workstation GPU). Selected by `CEREBELLUM_TRAINING_PROVIDER=local`.
/// Instance operations are no-ops; `create_instance` writes the worker start
/// command into the data directory so the operator can execute it locally.
pub struct LocalGpuProvider {
    start_command_path: std::path::PathBuf,
    configured_gateway: String,
    loopback_gateway: String,
}

impl LocalGpuProvider {
    pub const NAME: &'static str = "local-5090";

    pub fn new(
        data_dir: &std::path::Path,
        configured_gateway: &str,
        bind: std::net::SocketAddr,
    ) -> Self {
        Self {
            start_command_path: data_dir.join("worker-start-command.txt"),
            configured_gateway: configured_gateway.into(),
            loopback_gateway: format!("http://{bind}"),
        }
    }
}

#[async_trait]
impl GpuProvider for LocalGpuProvider {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    async fn create_instance(&self, request: &ProvisionRequest) -> Result<ProvisionOutcome> {
        // The provisioned command embeds the configured (production) gateway;
        // for local execution the worker must reach this loopback daemon.
        let command = request.start_command.replace(
            &shell_quote(&self.configured_gateway),
            &shell_quote(&self.loopback_gateway),
        );
        std::fs::write(&self.start_command_path, format!("{command}\n"))?;
        tracing::info!(
            run_id = %request.run_id,
            path = %self.start_command_path.display(),
            "local training provider wrote the worker start command"
        );
        Ok(ProvisionOutcome::Created {
            instance_id: format!("{}-0", Self::NAME),
        })
    }

    async fn instance_snapshot(&self, instance_id: &str) -> Result<ProviderInstanceSnapshot> {
        Ok(ProviderInstanceSnapshot {
            instance_id: instance_id.into(),
            status: "running".into(),
            hourly_price_cny: 0.0,
            gpu_name: "RTX 5090".into(),
            chip_vendor: "nvidia".into(),
        })
    }

    async fn instance_status(&self, _instance_id: &str) -> Result<String> {
        Ok("running".into())
    }

    async fn power_off(&self, _instance_id: &str) -> Result<()> {
        Ok(())
    }

    async fn release(&self, _instance_id: &str) -> Result<()> {
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkerBootstrapRequest {
    pub run_id: Uuid,
    pub bootstrap_code: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkerBootstrapResponse {
    pub run_id: Uuid,
    pub snapshot_id: Uuid,
    pub provider_instance_id: String,
    pub worker_token: String,
    pub expires_at: DateTime<Utc>,
    pub bundle_hash: String,
    pub manifest_hash: String,
    pub snapshot_manifest_hash: String,
    pub base_model: cerebellum_core::BaseModelPin,
    pub qlora: cerebellum_core::QloraConfig,
    pub expert_plan: Option<cerebellum_core::ExpertTrainingPlan>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkerHeartbeatRequest {
    pub progress: String,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkerHeartbeatResponse {
    pub worker_token: String,
    pub expires_at: DateTime<Utc>,
    pub cancel_requested: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkerCompleteRequest {
    pub model_id: String,
    pub model_version: String,
    pub artifact_hash: String,
    pub metrics: MetaModelMetrics,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkerFailRequest {
    pub error: String,
}

#[derive(Debug, Clone)]
pub struct WorkerAuthorization {
    pub run_id: Uuid,
    pub provider_instance_id: String,
}

impl Registry {
    pub fn create_training_run(
        &self,
        request: &CreateTrainingRunRequest,
        config: &AutoDlConfig,
        now: DateTime<Utc>,
    ) -> Result<TrainingRun> {
        validate_create_training_run(request)?;
        let snapshot = self.require_usable_snapshot(request.snapshot_id)?;
        if self.quality_model_configured()? {
            let report_id = snapshot
                .snapshot
                .quality_report_id
                .context("quality enforcement requires a reviewed DatasetSnapshot")?;
            let report_hash = snapshot
                .snapshot
                .quality_report_hash
                .as_deref()
                .context("quality enforcement requires a DatasetSnapshot report hash")?;
            let report = self
                .get_dataset_quality_report(snapshot.snapshot.build_id)?
                .context("DatasetSnapshot quality report is missing")?;
            if !report.gate_passed
                || report.report_id != report_id
                || report.report_hash != report_hash
            {
                bail!("DatasetSnapshot quality report is invalid or did not pass");
            }
        }
        if !config
            .base_models
            .iter()
            .any(|model| model == &request.base_model)
        {
            bail!("base model is not on the pinned deployment allowlist");
        }
        let spec = config
            .gpu_allowlist
            .iter()
            .find(|spec| spec.id == request.gpu_spec)
            .ok_or_else(|| anyhow!("GPU spec is not on the ordered deployment allowlist"))?;
        if !spec.cuda || spec.memory_gb < 24 {
            bail!("training requires an approved CUDA GPU with at least 24GB");
        }
        let (training_bundle_hash, training_manifest_hash) = if let Some(plan) =
            &request.expert_plan
        {
            let view = self
                .get_expert_dataset_view(plan.expert_view_id)?
                .ok_or_else(|| anyhow!("expert dataset view was not found"))?;
            validate_expert_dataset_view(&view)?;
            if view.build_id != snapshot.snapshot.build_id
                || snapshot.snapshot.expert_view_id != Some(view.view_id)
                || snapshot.snapshot.expert_manifest_hash.as_deref()
                    != Some(view.manifest_hash.as_str())
                || snapshot.snapshot.expert_taxonomy_hash.as_deref()
                    != Some(view.taxonomy_hash.as_str())
            {
                bail!("expert dataset view is not bound to the frozen snapshot");
            }
            if plan.router_top_k != view.taxonomy.router_top_k
                || plan.fallback_expert_id != view.taxonomy.fallback_expert_id
            {
                bail!("training plan does not match the frozen expert taxonomy");
            }
            let eligible_experts = view
                .taxonomy
                .experts
                .iter()
                .filter(|expert| !expert.is_fallback)
                .map(|expert| expert.id.as_str())
                .collect::<std::collections::HashSet<_>>();
            if plan
                .expert_ids
                .iter()
                .any(|expert| !eligible_experts.contains(expert.as_str()))
            {
                bail!("training plan references an unknown or fallback expert");
            }
            if plan.train_router
                && view.readiness.router_train_records < view.readiness.minimum_router_records
            {
                bail!("expert router dataset does not meet the frozen readiness threshold");
            }
            for expert_id in &plan.expert_ids {
                let stats = view
                    .readiness
                    .per_expert
                    .get(expert_id)
                    .ok_or_else(|| anyhow!("expert readiness statistics are missing"))?;
                if stats.records.train < view.readiness.minimum_train_records_per_expert
                    || stats.evaluation_replay_records < view.readiness.minimum_replays_per_expert
                {
                    bail!("expert {expert_id} does not meet the frozen readiness threshold");
                }
            }
            (Some(view.bundle_hash), Some(view.manifest_hash))
        } else {
            (None, None)
        };
        let run = TrainingRun {
            schema_version: SCHEMA_VERSION.into(),
            run_id: Uuid::new_v4(),
            snapshot_id: snapshot.snapshot.snapshot_id,
            snapshot_bundle_hash: snapshot.snapshot.bundle_hash,
            snapshot_manifest_hash: snapshot.snapshot.manifest_hash,
            training_bundle_hash,
            training_manifest_hash,
            expert_plan: request.expert_plan.clone(),
            base_model: request.base_model.clone(),
            qlora: request.qlora.clone(),
            provider: config.provider_name.clone(),
            application_uuid: config.application_uuid.clone(),
            application_version: config.application_version.clone(),
            requested_gpu_spec: spec.id.clone(),
            selected_gpu_spec: None,
            administrator: request.administrator.trim().into(),
            reason: request.reason.trim().into(),
            budget: request.budget.clone(),
            status: TrainingRunStatus::Requested,
            provider_instance_id: None,
            hourly_price_cny: None,
            estimated_cost_cny: 0.0,
            artifact_hash: None,
            model_id: None,
            model_version: None,
            error: None,
            created_at: now,
            started_at: None,
            completed_at: None,
            updated_at: now,
        };
        self.insert_training_run(&run)?;
        self.append_training_event(
            run.run_id,
            "requested",
            json!({
                "administrator":run.administrator,
                "reason":run.reason,
                "gpu_spec":run.requested_gpu_spec,
                "max_hourly_cny":run.budget.max_hourly_cny,
                "max_total_cny":run.budget.max_total_cny,
                "max_wall_seconds":run.budget.max_wall_seconds,
                "architecture":if run.expert_plan.is_some() {"routed_lora"} else {"dense_lora"},
                "expert_plan":&run.expert_plan
            }),
            now,
        )?;
        Ok(run)
    }

    pub async fn start_training_run(
        &self,
        id: Uuid,
        request: &StartTrainingRunRequest,
        config: &AutoDlConfig,
        provider: &dyn GpuProvider,
        now: DateTime<Utc>,
    ) -> Result<TrainingRun> {
        self.start_training_run_with_thresholds(
            id,
            request,
            config,
            provider,
            now,
            TrainingReadinessThresholds {
                decisions: MIN_META_DECISIONS as u64,
                replays: MIN_META_REPLAYS as u64,
            },
        )
        .await
    }

    async fn start_training_run_with_thresholds(
        &self,
        id: Uuid,
        request: &StartTrainingRunRequest,
        config: &AutoDlConfig,
        provider: &dyn GpuProvider,
        now: DateTime<Utc>,
        thresholds: TrainingReadinessThresholds,
    ) -> Result<TrainingRun> {
        let mut run = self
            .get_training_run(id)?
            .ok_or_else(|| anyhow!("training run not found"))?;
        if !matches!(
            run.status,
            TrainingRunStatus::Requested | TrainingRunStatus::WaitingCapacity
        ) {
            bail!("only requested or waiting-capacity runs can be started");
        }
        verify_start_confirmation(&run, request)?;
        let snapshot = self.require_usable_snapshot(run.snapshot_id)?;
        self.validate_training_run_inputs(&run, &snapshot)?;
        if snapshot.snapshot.decision_count < thresholds.decisions
            || snapshot.snapshot.replay_eval_count < thresholds.replays
        {
            bail!(
                "training requires at least {} decisions and {} replay evaluations",
                thresholds.decisions,
                thresholds.replays
            );
        }
        if self.training_started_since(now - Duration::days(META_TRAINING_COOLDOWN_DAYS), id)? {
            bail!("training may be started at most once per week");
        }
        let spec = config
            .gpu_allowlist
            .iter()
            .find(|spec| spec.id == run.requested_gpu_spec)
            .cloned()
            .ok_or_else(|| anyhow!("requested GPU spec is no longer approved"))?;
        if provider.name() != run.provider {
            bail!("configured GPU provider does not match the immutable run");
        }

        self.append_training_event(
            run.run_id,
            "start_confirmed",
            json!({
                "administrator":request.administrator,
                "reason":request.reason,
                "gpu_spec":request.confirm_gpu_spec,
                "max_hourly_cny":request.confirm_max_hourly_cny,
                "max_total_cny":request.confirm_max_total_cny,
                "max_wall_seconds":request.confirm_max_wall_seconds
            }),
            now,
        )?;

        run = self.transition_training_run(run, TrainingRunStatus::Provisioning, None, now)?;
        let bootstrap_code = new_secret();
        self.store_worker_bootstrap(run.run_id, &bootstrap_code, None, now)?;
        let provision = ProvisionRequest {
            run_id: run.run_id,
            application_uuid: run.application_uuid.clone(),
            application_version: run.application_version.clone(),
            gpu_spec: spec.clone(),
            start_command: worker_start_command(config, run.run_id, &bootstrap_code),
        };
        let outcome = match provider.create_instance(&provision).await {
            Ok(value) => value,
            Err(error) => {
                return self.fail_training_run(
                    run,
                    &format!(
                        "provider create failed: {}",
                        sanitize_provider_error(&error.to_string())
                    ),
                    now,
                );
            }
        };
        let instance_id = match outcome {
            ProvisionOutcome::WaitingCapacity { reason } => {
                return self.transition_training_run(
                    run,
                    TrainingRunStatus::WaitingCapacity,
                    Some(reason),
                    now,
                );
            }
            ProvisionOutcome::Created { instance_id } => instance_id,
        };
        let mut lease = GpuLease {
            run_id: run.run_id,
            provider: run.provider.clone(),
            provider_instance_id: instance_id.clone(),
            gpu_spec: spec.id.clone(),
            gpu_memory_gb: spec.memory_gb,
            hourly_price_cny: 0.0,
            status: GpuLeaseStatus::Provisioning,
            last_provider_status: "created".into(),
            last_heartbeat_at: None,
            release_requested_at: None,
            released_at: None,
            created_at: now,
            updated_at: now,
        };
        if let Err(error) = self.save_gpu_lease(&lease) {
            let _ = cleanup_provider_instance(provider, &instance_id).await;
            return Err(error.context("persist provider instance lease"));
        }
        run.provider_instance_id = Some(instance_id.clone());
        run.selected_gpu_spec = Some(spec.id.clone());
        run.started_at = Some(now);
        self.persist_training_run(&run)?;
        if let Err(error) = self.bind_worker_bootstrap(run.run_id, &instance_id) {
            let run = self.fail_training_run(run, &error.to_string(), now)?;
            let _ = self.release_training_gpu(run.run_id, provider, now).await;
            return Ok(run);
        }
        let snapshot = match provider.instance_snapshot(&instance_id).await {
            Ok(snapshot) => snapshot,
            Err(error) => {
                let run = self.fail_training_run(
                    run,
                    &format!(
                        "provider price check failed: {}",
                        sanitize_provider_error(&error.to_string())
                    ),
                    now,
                )?;
                let _ = self.release_training_gpu(run.run_id, provider, now).await;
                return Ok(run);
            }
        };
        let projected =
            snapshot.hourly_price_cny * f64::from(run.budget.max_wall_seconds) / 3_600.0;
        if !snapshot.chip_vendor.eq_ignore_ascii_case("nvidia")
            || snapshot.hourly_price_cny > run.budget.max_hourly_cny
            || projected > run.budget.max_total_cny
        {
            let run = self.fail_training_run(
                run,
                &format!(
                    "provider instance violates GPU or budget gate (hourly {:.3}, projected {:.3})",
                    snapshot.hourly_price_cny, projected
                ),
                now,
            )?;
            let _ = self.release_training_gpu(run.run_id, provider, now).await;
            return Ok(run);
        }
        lease.hourly_price_cny = snapshot.hourly_price_cny;
        lease.status = GpuLeaseStatus::WaitingWorker;
        lease.last_provider_status = snapshot.status;
        lease.updated_at = now;
        self.save_gpu_lease(&lease)?;
        run.hourly_price_cny = Some(snapshot.hourly_price_cny);
        run = self.transition_training_run(run, TrainingRunStatus::WaitingWorker, None, now)?;
        Ok(run)
    }

    pub fn get_training_run(&self, id: Uuid) -> Result<Option<TrainingRun>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT run_json FROM training_runs WHERE id=?1",
            params![id.to_string()],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn list_training_runs(&self) -> Result<Vec<TrainingRun>> {
        let conn = self.lock_conn();
        let mut statement =
            conn.prepare("SELECT run_json FROM training_runs ORDER BY created_at DESC,id")?;
        statement
            .query_map([], |row| row.get::<_, String>(0))?
            .map(|row| Ok(serde_json::from_str(&row?)?))
            .collect()
    }

    pub fn get_training_run_detail(&self, id: Uuid) -> Result<Option<TrainingRunDetail>> {
        let Some(run) = self.get_training_run(id)? else {
            return Ok(None);
        };
        let conn = self.lock_conn();
        let lease = conn
            .query_row(
                "SELECT lease_json FROM gpu_leases WHERE run_id=?1",
                params![id.to_string()],
                |row| row.get::<_, String>(0),
            )
            .optional()?
            .map(|value| serde_json::from_str(&value))
            .transpose()?;
        let mut statement = conn.prepare(
            "SELECT id,kind,payload_json,created_at FROM training_run_events
             WHERE run_id=?1 ORDER BY id",
        )?;
        let events = statement
            .query_map(params![id.to_string()], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                ))
            })?
            .map(|row| {
                let (sequence, kind, payload, created_at) = row?;
                Ok(TrainingRunEvent {
                    sequence,
                    run_id: id,
                    kind,
                    payload: serde_json::from_str(&payload)?,
                    created_at: parse_time(&created_at)?,
                })
            })
            .collect::<Result<Vec<_>>>()?;
        Ok(Some(TrainingRunDetail { run, lease, events }))
    }

    pub async fn cancel_training_run(
        &self,
        id: Uuid,
        request: &CancelTrainingRunRequest,
        provider: Option<&dyn GpuProvider>,
        now: DateTime<Utc>,
    ) -> Result<TrainingRun> {
        if request.administrator.trim().is_empty() || request.reason.trim().is_empty() {
            bail!("cancellation administrator and reason are required");
        }
        let run = self
            .get_training_run(id)?
            .ok_or_else(|| anyhow!("training run not found"))?;
        if run.status.is_terminal() {
            return Ok(run);
        }
        let run = self.transition_training_run(
            run,
            TrainingRunStatus::Cancelled,
            Some(format!(
                "{}: {}",
                request.administrator.trim(),
                request.reason.trim()
            )),
            now,
        )?;
        if let Some(provider) = provider {
            let _ = self.release_training_gpu(id, provider, now).await;
        }
        Ok(run)
    }

    pub fn exchange_worker_bootstrap(
        &self,
        request: &WorkerBootstrapRequest,
        now: DateTime<Utc>,
    ) -> Result<WorkerBootstrapResponse> {
        let code_hash = secret_hash(&request.bootstrap_code);
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let row: Option<(String, Option<String>, Option<String>)> = transaction
            .query_row(
                "SELECT expires_at,exchanged_at,provider_instance_id
                 FROM training_worker_bootstraps
                 WHERE run_id=?1 AND code_hash=?2",
                params![request.run_id.to_string(), code_hash],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()?;
        let (expires_at, exchanged_at, provider_instance_id) =
            row.ok_or_else(|| anyhow!("invalid bootstrap code"))?;
        if exchanged_at.is_some() || parse_time(&expires_at)? <= now {
            bail!("bootstrap code has expired or was already exchanged");
        }
        let provider_instance_id = provider_instance_id
            .ok_or_else(|| anyhow!("bootstrap is not bound to a provider instance"))?;
        let run_json: String = transaction.query_row(
            "SELECT run_json FROM training_runs WHERE id=?1",
            params![request.run_id.to_string()],
            |row| row.get(0),
        )?;
        let run: TrainingRun = serde_json::from_str(&run_json)?;
        if run.status != TrainingRunStatus::WaitingWorker
            || run.provider_instance_id.as_deref() != Some(provider_instance_id.as_str())
        {
            bail!("training run is not accepting a worker");
        }
        let worker_token = new_secret();
        let token_hash = secret_hash(&worker_token);
        let expires_at = now + Duration::seconds(WORKER_SESSION_TTL_SECONDS);
        transaction.execute(
            "UPDATE training_worker_bootstraps SET exchanged_at=?3
             WHERE run_id=?1 AND code_hash=?2 AND exchanged_at IS NULL",
            params![request.run_id.to_string(), code_hash, now.to_rfc3339()],
        )?;
        transaction.execute(
            "INSERT INTO training_worker_sessions(
               token_hash,run_id,provider_instance_id,expires_at,replaced_at,created_at
             ) VALUES(?1,?2,?3,?4,NULL,?5)",
            params![
                token_hash,
                request.run_id.to_string(),
                provider_instance_id,
                expires_at.to_rfc3339(),
                now.to_rfc3339()
            ],
        )?;
        transaction.commit()?;
        drop(conn);
        self.touch_gpu_heartbeat(request.run_id, now, GpuLeaseStatus::Running)?;
        self.transition_training_run(run.clone(), TrainingRunStatus::Running, None, now)?;
        Ok(WorkerBootstrapResponse {
            run_id: run.run_id,
            snapshot_id: run.snapshot_id,
            provider_instance_id,
            worker_token,
            expires_at,
            bundle_hash: run.training_bundle_hash.unwrap_or(run.snapshot_bundle_hash),
            manifest_hash: run
                .training_manifest_hash
                .unwrap_or_else(|| run.snapshot_manifest_hash.clone()),
            snapshot_manifest_hash: run.snapshot_manifest_hash,
            base_model: run.base_model,
            qlora: run.qlora,
            expert_plan: run.expert_plan,
        })
    }

    pub fn authorize_worker_token(
        &self,
        token: &str,
        expected_run: Uuid,
        now: DateTime<Utc>,
    ) -> Result<WorkerAuthorization> {
        let conn = self.lock_conn();
        let row: Option<(String, String, String, Option<String>)> = conn
            .query_row(
                "SELECT run_id,provider_instance_id,expires_at,replaced_at
                 FROM training_worker_sessions WHERE token_hash=?1",
                params![secret_hash(token)],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .optional()?;
        let (run_id, provider_instance_id, expires_at, replaced_at) =
            row.ok_or_else(|| anyhow!("invalid worker token"))?;
        let run_id = Uuid::parse_str(&run_id)?;
        // A token stays valid for a short grace window after rotation: the
        // 30s heartbeat rotates continuously while long requests (e.g. a
        // 512 MiB artifact upload) still carry the previous token. Without
        // the grace an in-flight request 403s and the worker's except-path
        // could fail a run that actually finished.
        let replaced_ok = match &replaced_at {
            None => true,
            Some(replaced) => {
                parse_time(replaced)? + Duration::seconds(REPLACED_TOKEN_GRACE_SECONDS) > now
            }
        };
        if run_id != expected_run || !replaced_ok || parse_time(&expires_at)? <= now {
            bail!("worker token is expired, replaced, or scoped to another run");
        }
        let run_json: String = conn.query_row(
            "SELECT run_json FROM training_runs WHERE id=?1",
            params![run_id.to_string()],
            |row| row.get(0),
        )?;
        let run: TrainingRun = serde_json::from_str(&run_json)?;
        if run.status.is_terminal()
            || run.provider_instance_id.as_deref() != Some(provider_instance_id.as_str())
        {
            bail!("worker token belongs to a terminated or mismatched run");
        }
        Ok(WorkerAuthorization {
            run_id,
            provider_instance_id,
        })
    }

    pub fn rotate_worker_heartbeat(
        &self,
        run_id: Uuid,
        token: &str,
        heartbeat: &WorkerHeartbeatRequest,
        now: DateTime<Utc>,
    ) -> Result<WorkerHeartbeatResponse> {
        let authorization = self.authorize_worker_token(token, run_id, now)?;
        if heartbeat.progress.trim().is_empty() || heartbeat.progress.len() > 128 {
            bail!("worker heartbeat progress is invalid");
        }
        let next_token = new_secret();
        let expires_at = now + Duration::seconds(WORKER_SESSION_TTL_SECONDS);
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let changed = transaction.execute(
            "UPDATE training_worker_sessions SET replaced_at=?2
             WHERE token_hash=?1 AND replaced_at IS NULL AND expires_at>?2",
            params![secret_hash(token), now.to_rfc3339()],
        )?;
        if changed != 1 {
            bail!("worker token was already rotated");
        }
        transaction.execute(
            "INSERT INTO training_worker_sessions(
               token_hash,run_id,provider_instance_id,expires_at,replaced_at,created_at
             ) VALUES(?1,?2,?3,?4,NULL,?5)",
            params![
                secret_hash(&next_token),
                run_id.to_string(),
                authorization.provider_instance_id,
                expires_at.to_rfc3339(),
                now.to_rfc3339()
            ],
        )?;
        transaction.commit()?;
        drop(conn);
        self.touch_gpu_heartbeat(run_id, now, GpuLeaseStatus::Running)?;
        if heartbeat.progress == "uploading"
            && let Some(run) = self.get_training_run(run_id)?
            && run.status == TrainingRunStatus::Running
        {
            self.transition_training_run(run, TrainingRunStatus::Uploading, None, now)?;
        }
        self.append_training_event(
            run_id,
            "heartbeat",
            json!({
                "progress":heartbeat.progress,
                "message":heartbeat.message.as_deref().map(|value| value.chars().take(500).collect::<String>())
            }),
            now,
        )?;
        Ok(WorkerHeartbeatResponse {
            worker_token: next_token,
            expires_at,
            cancel_requested: false,
        })
    }

    pub fn save_training_artifact(
        &self,
        run_id: Uuid,
        kind: &str,
        object_hash: &str,
        byte_length: u64,
        metadata: &Value,
        now: DateTime<Utc>,
    ) -> Result<()> {
        if !matches!(kind, "adapter" | "logs" | "metrics") {
            bail!("unsupported training artifact kind");
        }
        let run = self
            .get_training_run(run_id)?
            .ok_or_else(|| anyhow!("training run not found"))?;
        if !matches!(
            run.status,
            TrainingRunStatus::Running | TrainingRunStatus::Uploading
        ) {
            bail!("training run is not accepting artifacts");
        }
        if kind == "adapter" && byte_length > MAX_TRAINING_ARTIFACT_BYTES {
            bail!("adapter exceeds the 512 MiB limit");
        }
        self.verify_object_hash(object_hash)
            .context("training artifact is absent from CAS or failed integrity verification")?;
        let conn = self.lock_conn();
        let existing: Option<(String, i64, String)> = conn
            .query_row(
                "SELECT object_hash,byte_length,metadata_json FROM training_artifacts
                 WHERE run_id=?1 AND kind=?2",
                params![run_id.to_string(), kind],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()?;
        let metadata_json = serde_json::to_string(metadata)?;
        if let Some((existing_hash, existing_length, existing_metadata)) = existing {
            if existing_hash == object_hash
                && existing_length == byte_length as i64
                && existing_metadata == metadata_json
            {
                drop(conn);
                if run.status == TrainingRunStatus::Running {
                    self.transition_training_run(
                        run,
                        TrainingRunStatus::Uploading,
                        Some(format!("worker resumed uploading {kind}")),
                        now,
                    )?;
                }
                return Ok(());
            }
            bail!("training artifact kinds are immutable after first upload");
        }
        conn.execute(
            "INSERT INTO training_artifacts(
               run_id,kind,object_hash,byte_length,metadata_json,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6)",
            params![
                run_id.to_string(),
                kind,
                object_hash,
                byte_length as i64,
                metadata_json,
                now.to_rfc3339()
            ],
        )?;
        drop(conn);
        if run.status == TrainingRunStatus::Running {
            self.transition_training_run(
                run,
                TrainingRunStatus::Uploading,
                Some(format!("worker started uploading {kind}")),
                now,
            )?;
        }
        Ok(())
    }

    pub fn complete_training_run_from_worker(
        &self,
        run_id: Uuid,
        request: &WorkerCompleteRequest,
        now: DateTime<Utc>,
    ) -> Result<(TrainingRun, MetaModelBundle)> {
        let mut run = self
            .get_training_run(run_id)?
            .ok_or_else(|| anyhow!("training run not found"))?;
        if run.status != TrainingRunStatus::Uploading {
            bail!("training run is not accepting completion");
        }
        if request.model_id.trim().is_empty() || request.model_version.trim().is_empty() {
            bail!("model id and version are required");
        }
        let conn = self.lock_conn();
        let artifact: Option<(String, i64)> = conn
            .query_row(
                "SELECT object_hash,byte_length FROM training_artifacts
                 WHERE run_id=?1 AND kind='adapter'",
                params![run_id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        drop(conn);
        let (artifact_hash, _) = artifact.ok_or_else(|| anyhow!("adapter upload is incomplete"))?;
        if artifact_hash != request.artifact_hash {
            bail!("completion artifact hash differs from the uploaded adapter");
        }
        let routed = if run.expert_plan.is_some() {
            let routed = self.validate_routed_training_artifact(&run, &artifact_hash)?;
            self.append_training_event(
                run.run_id,
                "routed_bundle_verified",
                json!({
                    "expert_view_id":routed.expert_view_id,
                    "taxonomy_hash":routed.taxonomy_hash,
                    "router_hash":routed.router.as_ref().map(|router| router.sha256.as_str()),
                    "expert_count":routed.experts.len()
                }),
                now,
            )?;
            Some(routed)
        } else {
            None
        };
        let bundle = MetaModelBundle {
            schema_version: SCHEMA_VERSION.into(),
            model_id: request.model_id.clone(),
            version: request.model_version.clone(),
            artifact_hash: artifact_hash.clone(),
            base_model: format!("{}@{}", run.base_model.model_id, run.base_model.revision),
            training_candidate_id: run.snapshot_id,
            trainer: format!("remote:{}", run.provider),
            metrics: request.metrics.clone(),
            status: MetaModelStatus::Candidate,
            previous_active: None,
            canary_started_at: None,
            canary_decisions: 0,
            created_at: now,
            updated_at: now,
        };
        if let Some(routed) = &routed {
            self.register_expert_adapter_candidates(
                &run,
                &request.model_version,
                &artifact_hash,
                routed,
                now,
            )?;
        } else {
            self.register_meta_model_from_stored_artifact(&bundle)?;
        }
        run.artifact_hash = Some(artifact_hash);
        run.model_id = Some(bundle.model_id.clone());
        run.model_version = Some(bundle.version.clone());
        run.completed_at = Some(now);
        run = self.transition_training_run(run, TrainingRunStatus::Completed, None, now)?;
        Ok((run, bundle))
    }

    fn validate_routed_training_artifact(
        &self,
        run: &TrainingRun,
        artifact_hash: &str,
    ) -> Result<RoutedAdapterBundleManifest> {
        let plan = run
            .expert_plan
            .as_ref()
            .ok_or_else(|| anyhow!("routed artifact has no immutable training plan"))?;
        let file = File::open(self.object_path(artifact_hash)?)?;
        let mut archive = tar::Archive::new(file);
        let mut entries = HashMap::<String, (String, u64)>::new();
        let mut manifest_bytes = None;
        for item in archive.entries()? {
            let mut item = item?;
            if !item.header().entry_type().is_file() {
                bail!("routed adapter Bundle may contain only regular files");
            }
            let path = item.path()?.to_string_lossy().replace('\\', "/");
            if path.starts_with('/')
                || path.split('/').any(|part| part.is_empty() || part == "..")
                || entries.contains_key(&path)
            {
                bail!("routed adapter Bundle contains an unsafe or duplicate path");
            }
            let declared_size = item.header().size()?;
            let mut digest = Sha256::new();
            let mut bytes = Vec::new();
            let mut buffer = [0_u8; 64 * 1024];
            let mut actual_size = 0_u64;
            loop {
                let count = item.read(&mut buffer)?;
                if count == 0 {
                    break;
                }
                actual_size += count as u64;
                digest.update(&buffer[..count]);
                if path == "cerebellum-routed-adapter-manifest.json" {
                    if actual_size > 1024 * 1024 {
                        bail!("routed adapter Manifest exceeds 1 MiB");
                    }
                    bytes.extend_from_slice(&buffer[..count]);
                }
            }
            if actual_size != declared_size {
                bail!("routed adapter member length differs from its header");
            }
            entries.insert(
                path.clone(),
                (format!("{:x}", digest.finalize()), actual_size),
            );
            if path == "cerebellum-routed-adapter-manifest.json" {
                manifest_bytes = Some(bytes);
            }
        }
        let manifest: RoutedAdapterBundleManifest = serde_json::from_slice(
            &manifest_bytes.ok_or_else(|| anyhow!("routed adapter Manifest is missing"))?,
        )?;
        validate_routed_adapter_bundle(&manifest)?;
        if manifest.base_model != run.base_model
            || manifest.snapshot_id != run.snapshot_id
            || manifest.expert_view_id != plan.expert_view_id
            || manifest.router_top_k != plan.router_top_k
            || manifest.fallback_expert_id != plan.fallback_expert_id
            || run.training_manifest_hash.as_deref().is_none()
        {
            bail!("routed adapter Manifest differs from the immutable TrainingRun");
        }
        if manifest.router.is_some() != plan.train_router {
            bail!("routed adapter Bundle router presence differs from the training plan");
        }
        let view = self
            .get_expert_dataset_view(plan.expert_view_id)?
            .ok_or_else(|| anyhow!("routed adapter expert view no longer exists"))?;
        if manifest.taxonomy_hash != view.taxonomy_hash
            || run.training_manifest_hash.as_deref() != Some(view.manifest_hash.as_str())
        {
            bail!("routed adapter taxonomy differs from the frozen expert view");
        }
        let expected_ids = plan
            .train_shared
            .then_some(plan.fallback_expert_id.as_str())
            .into_iter()
            .chain(plan.expert_ids.iter().map(String::as_str))
            .collect::<HashSet<_>>();
        let actual_ids = manifest
            .experts
            .iter()
            .map(|artifact| artifact.expert_id.as_str())
            .collect::<HashSet<_>>();
        if expected_ids != actual_ids {
            bail!("routed adapter Bundle does not contain the planned expert set");
        }
        let referenced = manifest
            .router
            .iter()
            .chain(manifest.experts.iter())
            .map(|artifact| artifact.path.as_str())
            .collect::<HashSet<_>>();
        let archive_payloads = entries
            .keys()
            .map(String::as_str)
            .filter(|path| *path != "cerebellum-routed-adapter-manifest.json")
            .collect::<HashSet<_>>();
        if referenced != archive_payloads {
            bail!("routed adapter Bundle contains missing or unreferenced payloads");
        }
        for artifact in manifest.router.iter().chain(manifest.experts.iter()) {
            let (hash, length) = entries
                .get(&artifact.path)
                .ok_or_else(|| anyhow!("routed adapter payload is missing"))?;
            if hash != &artifact.sha256 || *length != artifact.byte_length {
                bail!("routed adapter payload failed hash or length verification");
            }
        }
        Ok(manifest)
    }

    fn register_expert_adapter_candidates(
        &self,
        run: &TrainingRun,
        version: &str,
        bundle_hash: &str,
        manifest: &RoutedAdapterBundleManifest,
        now: DateTime<Utc>,
    ) -> Result<Vec<ExpertAdapterVersion>> {
        let adapters = manifest
            .router
            .iter()
            .chain(manifest.experts.iter())
            .map(|artifact| ExpertAdapterVersion {
                schema_version: SCHEMA_VERSION.into(),
                adapter_id: deterministic_adapter_id(run.run_id, &artifact.expert_id, version),
                expert_id: artifact.expert_id.clone(),
                version: version.into(),
                bundle_hash: bundle_hash.into(),
                artifact_path: artifact.path.clone(),
                artifact_hash: artifact.sha256.clone(),
                byte_length: artifact.byte_length,
                training_records: artifact.training_records,
                base_model: run.base_model.clone(),
                training_run_id: run.run_id,
                snapshot_id: run.snapshot_id,
                expert_view_id: manifest.expert_view_id,
                taxonomy_hash: manifest.taxonomy_hash.clone(),
                status: ExpertAdapterStatus::Candidate,
                metrics: None,
                previous_active: None,
                created_at: now,
                updated_at: now,
            })
            .collect::<Vec<_>>();
        for adapter in &adapters {
            validate_expert_adapter_version(adapter)?;
        }
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let mut stored = Vec::with_capacity(adapters.len());
        for adapter in &adapters {
            let changed = transaction.execute(
                "INSERT OR IGNORE INTO expert_adapter_versions(
                   adapter_id,expert_id,version,status,training_run_id,bundle_hash,
                   artifact_hash,adapter_json,updated_at
                 ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9)",
                params![
                    adapter.adapter_id.to_string(),
                    adapter.expert_id,
                    adapter.version,
                    expert_adapter_status_name(adapter.status),
                    adapter.training_run_id.to_string(),
                    adapter.bundle_hash,
                    adapter.artifact_hash,
                    serde_json::to_string(adapter)?,
                    adapter.updated_at.to_rfc3339()
                ],
            )?;
            if changed == 1 {
                stored.push(adapter.clone());
                continue;
            }
            let existing: String = transaction.query_row(
                "SELECT adapter_json FROM expert_adapter_versions
                 WHERE expert_id=?1 AND version=?2",
                params![adapter.expert_id, adapter.version],
                |row| row.get(0),
            )?;
            let existing: ExpertAdapterVersion = serde_json::from_str(&existing)?;
            if existing.adapter_id != adapter.adapter_id
                || existing.training_run_id != adapter.training_run_id
                || existing.bundle_hash != adapter.bundle_hash
                || existing.artifact_path != adapter.artifact_path
                || existing.artifact_hash != adapter.artifact_hash
                || existing.byte_length != adapter.byte_length
                || existing.training_records != adapter.training_records
                || existing.base_model != adapter.base_model
                || existing.snapshot_id != adapter.snapshot_id
                || existing.expert_view_id != adapter.expert_view_id
                || existing.taxonomy_hash != adapter.taxonomy_hash
                || existing.status != ExpertAdapterStatus::Candidate
            {
                bail!("expert adapter version already exists with different immutable content");
            }
            stored.push(existing);
        }
        transaction.commit()?;
        Ok(stored)
    }

    pub fn list_expert_adapters(
        &self,
        expert_id: Option<&str>,
    ) -> Result<Vec<ExpertAdapterVersion>> {
        let conn = self.lock_conn();
        let values = if let Some(expert_id) = expert_id {
            let mut statement = conn.prepare(
                "SELECT adapter_json FROM expert_adapter_versions
                 WHERE expert_id=?1 ORDER BY updated_at DESC,adapter_id",
            )?;
            statement
                .query_map(params![expert_id], |row| row.get::<_, String>(0))?
                .collect::<rusqlite::Result<Vec<_>>>()?
        } else {
            let mut statement = conn.prepare(
                "SELECT adapter_json FROM expert_adapter_versions
                 ORDER BY expert_id,updated_at DESC,adapter_id",
            )?;
            statement
                .query_map([], |row| row.get::<_, String>(0))?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };
        values
            .into_iter()
            .map(|value| serde_json::from_str(&value).map_err(Into::into))
            .collect()
    }

    pub fn get_expert_adapter(
        &self,
        expert_id: &str,
        version: &str,
    ) -> Result<Option<ExpertAdapterVersion>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT adapter_json FROM expert_adapter_versions
             WHERE expert_id=?1 AND version=?2",
            params![expert_id, version],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn active_expert_adapter(&self, expert_id: &str) -> Result<Option<ExpertAdapterVersion>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT adapter_json FROM expert_adapter_versions
             WHERE expert_id=?1 AND status='active'
             ORDER BY updated_at DESC,adapter_id LIMIT 1",
            params![expert_id],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn active_expert_adapter_refs(&self, taxonomy_hash: &str) -> Result<Vec<ExpertAdapterRef>> {
        let active = self
            .list_expert_adapters(None)?
            .into_iter()
            .filter(|adapter| {
                adapter.status == ExpertAdapterStatus::Active
                    && adapter.taxonomy_hash == taxonomy_hash
            })
            .collect::<Vec<_>>();
        let base_model = active
            .iter()
            .find(|adapter| adapter.expert_id == "router")
            .or_else(|| active.iter().find(|adapter| adapter.expert_id == "shared"))
            .or_else(|| active.first())
            .map(|adapter| adapter.base_model.clone());
        Ok(active
            .into_iter()
            .filter(|adapter| {
                base_model
                    .as_ref()
                    .is_some_and(|base| adapter.base_model == *base)
            })
            .map(expert_adapter_ref)
            .collect())
    }

    /// Record one routing decision that hit the deterministic 10% canary
    /// partition for a canary-status adapter (server-side release-gate input).
    pub fn record_expert_canary_decision(
        &self,
        adapter_id: Uuid,
        decision_id: Uuid,
        selected_expert: &str,
        dense_fallback: bool,
        unsafe_input: bool,
    ) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO expert_canary_decisions(
               id,adapter_id,decision_id,selected_expert,dense_fallback,unsafe_input,created_at
             ) VALUES (?1,?2,?3,?4,?5,?6,?7)",
            params![
                Uuid::new_v4().to_string(),
                adapter_id.to_string(),
                decision_id.to_string(),
                selected_expert,
                dense_fallback as i64,
                unsafe_input as i64,
                Utc::now().to_rfc3339()
            ],
        )?;
        Ok(())
    }

    /// Server-computed canary accounting: decision count and the span from
    /// the adapter's canary transition to its latest recorded decision.
    fn expert_canary_accounting(&self, adapter: &ExpertAdapterVersion) -> Result<(u64, u64)> {
        let conn = self.lock_conn();
        let decisions: u64 = conn.query_row(
            "SELECT COUNT(*) FROM expert_canary_decisions WHERE adapter_id=?1",
            params![adapter.adapter_id.to_string()],
            |row| row.get(0),
        )?;
        let canary_start: Option<String> = conn
            .query_row(
                "SELECT created_at FROM learning_audit
                 WHERE subject_type='expert_adapter' AND subject_id=?1 AND action='canary'
                 ORDER BY created_at DESC LIMIT 1",
                params![format!("{}@{}", adapter.expert_id, adapter.version)],
                |row| row.get(0),
            )
            .optional()?;
        let latest_decision: Option<String> = conn.query_row(
            "SELECT MAX(created_at) FROM expert_canary_decisions WHERE adapter_id=?1",
            params![adapter.adapter_id.to_string()],
            |row| row.get(0),
        )?;
        let duration = match (canary_start, latest_decision) {
            (Some(start), Some(latest)) => {
                let start = DateTime::parse_from_rfc3339(&start)?;
                let latest = DateTime::parse_from_rfc3339(&latest)?;
                (latest - start).num_seconds().max(0) as u64
            }
            _ => 0,
        };
        Ok((decisions, duration))
    }

    /// Persist an immutable adapter evaluation report and its per-record
    /// results object after checking the report against the stored adapter
    /// identity. Reports are evidence: insertion is the only mutation.
    pub fn record_expert_adapter_eval_report(
        &self,
        report: &cerebellum_core::ExpertAdapterEvalReport,
        results: &[u8],
    ) -> Result<()> {
        cerebellum_core::validate_expert_adapter_eval_report(report)?;
        let adapter = self
            .get_expert_adapter(&report.expert_id, &report.version)?
            .ok_or_else(|| anyhow!("expert adapter version not found"))?;
        if adapter.adapter_id != report.adapter_id
            || adapter.base_model != report.base_model
            || adapter.snapshot_id != report.snapshot_id
            || adapter.expert_view_id != report.expert_view_id
            || adapter.taxonomy_hash != report.taxonomy_hash
        {
            bail!("evaluation report identity does not match the stored adapter");
        }
        let results_hash = format!("{:x}", Sha256::digest(results));
        if results_hash != report.results_object_hash {
            bail!("evaluation results object hash mismatch");
        }
        self.put_object(results)?;
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        transaction.execute(
            "INSERT INTO expert_adapter_eval_reports(
               id,adapter_id,expert_id,version,results_hash,report_json,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7)",
            params![
                report.report_id.to_string(),
                report.adapter_id.to_string(),
                report.expert_id,
                report.version,
                results_hash,
                serde_json::to_string(report)?,
                report.created_at.to_rfc3339()
            ],
        )?;
        Self::audit_conn(
            &transaction,
            "expert_adapter",
            &format!("{}@{}", report.expert_id, report.version),
            "eval_report",
            "adapter-eval",
            &report.report_id.to_string(),
            report.created_at,
        )?;
        transaction.commit()?;
        Ok(())
    }

    pub fn get_expert_adapter_eval_report(
        &self,
        id: Uuid,
    ) -> Result<Option<cerebellum_core::ExpertAdapterEvalReport>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT report_json FROM expert_adapter_eval_reports WHERE id=?1",
            params![id.to_string()],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn list_expert_adapter_eval_reports(
        &self,
        expert_id: &str,
        version: &str,
    ) -> Result<Vec<cerebellum_core::ExpertAdapterEvalReport>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT report_json FROM expert_adapter_eval_reports
             WHERE expert_id=?1 AND version=?2 ORDER BY created_at DESC,id",
        )?;
        let values = statement
            .query_map(params![expert_id, version], |row| row.get::<_, String>(0))?
            .collect::<rusqlite::Result<Vec<_>>>()?;
        values
            .into_iter()
            .map(|value| serde_json::from_str(&value).map_err(Into::into))
            .collect()
    }

    /// Gate an expert adapter lifecycle transition. `canary_decisions` and
    /// `canary_duration_seconds` are always recomputed from the server-side
    /// routing record; every other gate metric comes from a recorded dual-arm
    /// evaluation report referenced by `eval_report_id` (see docs/security.md).
    pub fn operate_expert_adapter(
        &self,
        expert_id: &str,
        version: &str,
        action: &str,
        request: &ExpertAdapterOperationRequest,
        now: DateTime<Utc>,
    ) -> Result<ExpertAdapterVersion> {
        if request.actor.trim().is_empty() || request.reason.trim().is_empty() {
            bail!("expert adapter operation requires actor and reason");
        }
        let mut adapter = self
            .get_expert_adapter(expert_id, version)?
            .ok_or_else(|| anyhow!("expert adapter version not found"))?;
        let previous_active = if action == "activate" {
            self.active_expert_adapter(expert_id)?
                .filter(|current| current.adapter_id != adapter.adapter_id)
        } else {
            None
        };
        if action == "activate"
            && self.list_expert_adapters(None)?.into_iter().any(|active| {
                active.status == ExpertAdapterStatus::Active
                    && active.expert_id != adapter.expert_id
                    && active.taxonomy_hash == adapter.taxonomy_hash
                    && active.base_model != adapter.base_model
            })
        {
            bail!("active experts in one taxonomy must share the same frozen base model");
        }
        let rollback_target = if action == "rollback" {
            adapter
                .previous_active
                .as_ref()
                .map(|previous| self.get_expert_adapter(&previous.id, &previous.version))
                .transpose()?
                .flatten()
        } else {
            None
        };
        let next_status = match (adapter.status, action) {
            (ExpertAdapterStatus::Candidate, "shadow") => ExpertAdapterStatus::Shadow,
            (ExpertAdapterStatus::Shadow, "canary") => ExpertAdapterStatus::Canary,
            (ExpertAdapterStatus::Canary, "activate") => ExpertAdapterStatus::Active,
            (
                ExpertAdapterStatus::Candidate
                | ExpertAdapterStatus::Shadow
                | ExpertAdapterStatus::Canary,
                "reject",
            ) => ExpertAdapterStatus::Rejected,
            (ExpertAdapterStatus::Active, "rollback") => ExpertAdapterStatus::RolledBack,
            _ => bail!("expert adapter status transition is not allowed"),
        };
        let mut evidence_note = String::new();
        if matches!(action, "canary" | "activate") {
            if request.metrics.is_some() {
                bail!("metrics must come from a recorded evaluation report");
            }
            let report_id = request.eval_report_id.ok_or_else(|| {
                anyhow!("canary and activation require a recorded evaluation report")
            })?;
            let report = self
                .get_expert_adapter_eval_report(report_id)?
                .ok_or_else(|| anyhow!("evaluation report not found"))?;
            if report.adapter_id != adapter.adapter_id
                || report.base_model != adapter.base_model
                || report.snapshot_id != adapter.snapshot_id
                || report.expert_view_id != adapter.expert_view_id
                || report.taxonomy_hash != adapter.taxonomy_hash
            {
                bail!("evaluation report identity does not match this adapter");
            }
            let mut metrics = report.metrics.clone();
            // Server-verifiable dimensions always win over the recorded
            // report: canary decision count and duration are computed from
            // the recorded routing stream, never from the evidence file.
            let (server_decisions, server_duration) = self.expert_canary_accounting(&adapter)?;
            metrics.canary_decisions = server_decisions;
            metrics.canary_duration_seconds = server_duration;
            let passed = if action == "canary" {
                metrics.passes_canary_gate()
            } else {
                metrics.passes_release_gate()
            };
            if !passed {
                bail!("expert adapter objective {action} gate failed");
            }
            adapter.metrics = Some(metrics);
            evidence_note = format!(" [eval_report={report_id}]");
        } else if let Some(metrics) = &request.metrics {
            adapter.metrics = Some(metrics.clone());
        }
        adapter.status = next_status;
        adapter.updated_at = now;
        if let Some(previous) = &previous_active {
            adapter.previous_active = Some(ArtifactVersionRef {
                id: previous.expert_id.clone(),
                version: previous.version.clone(),
            });
        }
        validate_expert_adapter_version(&adapter)?;
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        if let Some(mut previous) = previous_active {
            previous.status = ExpertAdapterStatus::Superseded;
            previous.updated_at = now;
            persist_expert_adapter(&transaction, &previous)?;
        }
        if let Some(mut target) = rollback_target {
            if target.status != ExpertAdapterStatus::Superseded {
                bail!("rollback target is not a superseded expert adapter");
            }
            target.status = ExpertAdapterStatus::Active;
            target.updated_at = now;
            persist_expert_adapter(&transaction, &target)?;
        }
        persist_expert_adapter(&transaction, &adapter)?;
        Self::audit_conn(
            &transaction,
            "expert_adapter",
            &format!("{}@{}", adapter.expert_id, adapter.version),
            action,
            request.actor.trim(),
            &format!("{}{evidence_note}", request.reason.trim()),
            now,
        )?;
        transaction.commit()?;
        Ok(adapter)
    }

    pub fn fail_training_run_from_worker(
        &self,
        run_id: Uuid,
        request: &WorkerFailRequest,
        now: DateTime<Utc>,
    ) -> Result<TrainingRun> {
        let run = self
            .get_training_run(run_id)?
            .ok_or_else(|| anyhow!("training run not found"))?;
        self.fail_training_run(
            run,
            &format!(
                "worker failed: {}",
                request.error.chars().take(2_000).collect::<String>()
            ),
            now,
        )
    }

    pub async fn release_training_gpu(
        &self,
        run_id: Uuid,
        provider: &dyn GpuProvider,
        now: DateTime<Utc>,
    ) -> Result<()> {
        let Some(mut lease) = self.get_gpu_lease(run_id)? else {
            return Ok(());
        };
        if lease.status == GpuLeaseStatus::Released {
            return Ok(());
        }
        if lease.provider != provider.name() {
            bail!("GPU lease provider does not match configured provider");
        }
        lease.status = GpuLeaseStatus::ReleaseRequested;
        lease.release_requested_at.get_or_insert(now);
        lease.updated_at = now;
        self.save_gpu_lease(&lease)?;
        self.append_training_event(
            run_id,
            "release_requested",
            json!({"provider_instance_id":lease.provider_instance_id}),
            now,
        )?;
        let power_off = provider.power_off(&lease.provider_instance_id).await;
        let release = provider.release(&lease.provider_instance_id).await;
        match (power_off, release) {
            (_, Ok(())) => {
                lease.status = GpuLeaseStatus::Released;
                lease.released_at = Some(Utc::now());
                lease.updated_at = Utc::now();
                self.save_gpu_lease(&lease)?;
                self.append_training_event(
                    run_id,
                    "released",
                    json!({"provider_instance_id":lease.provider_instance_id}),
                    lease.updated_at,
                )?;
                Ok(())
            }
            (power_off, Err(release_error)) => {
                lease.status = GpuLeaseStatus::ReleaseFailed;
                lease.updated_at = Utc::now();
                self.save_gpu_lease(&lease)?;
                bail!(
                    "provider release failed after power-off result {:?}: {}",
                    power_off
                        .err()
                        .map(|error| sanitize_provider_error(&error.to_string())),
                    sanitize_provider_error(&release_error.to_string())
                )
            }
        }
    }

    pub fn record_training_admin_action(
        &self,
        run_id: Uuid,
        action: &str,
        actor: &str,
        reason: &str,
        now: DateTime<Utc>,
    ) -> Result<()> {
        if actor.trim().is_empty() || reason.trim().is_empty() {
            bail!("training admin action requires actor and reason");
        }
        self.append_training_event(
            run_id,
            action,
            json!({"actor":actor.trim(),"reason":reason.trim()}),
            now,
        )
    }

    pub fn training_token_gc(&self, now: DateTime<Utc>) -> Result<usize> {
        let conn = self.lock_conn();
        let sessions = conn.execute(
            "DELETE FROM training_worker_sessions
             WHERE expires_at<?1 OR (replaced_at IS NOT NULL AND replaced_at<?2)",
            params![now.to_rfc3339(), (now - Duration::days(1)).to_rfc3339()],
        )?;
        let bootstraps = conn.execute(
            "DELETE FROM training_worker_bootstraps
             WHERE expires_at<?1 AND (
               exchanged_at IS NOT NULL OR EXISTS(
                 SELECT 1 FROM training_runs r WHERE r.id=run_id
                 AND r.status IN ('completed','failed','cancelled','timed_out')
               )
             )",
            params![now.to_rfc3339()],
        )?;
        Ok(sessions + bootstraps)
    }

    pub async fn reconcile_training_runs(
        &self,
        provider: &dyn GpuProvider,
        now: DateTime<Utc>,
    ) -> Result<usize> {
        let runs = self.list_training_runs()?;
        let mut acted = 0;
        for mut run in runs {
            let Some(mut lease) = self.get_gpu_lease(run.run_id)? else {
                continue;
            };
            if lease.provider != provider.name() {
                continue;
            }
            if run.status.is_terminal() {
                if lease.status != GpuLeaseStatus::Released {
                    let _ = self.release_training_gpu(run.run_id, provider, now).await;
                    acted += 1;
                }
                continue;
            }
            if run.status == TrainingRunStatus::Provisioning
                && lease.hourly_price_cny <= 0.0
                && let Ok(snapshot) = provider
                    .instance_snapshot(&lease.provider_instance_id)
                    .await
            {
                let projected =
                    snapshot.hourly_price_cny * f64::from(run.budget.max_wall_seconds) / 3_600.0;
                if !snapshot.chip_vendor.eq_ignore_ascii_case("nvidia")
                    || snapshot.hourly_price_cny > run.budget.max_hourly_cny
                    || projected > run.budget.max_total_cny
                {
                    run = self.transition_training_run(
                        run,
                        TrainingRunStatus::Failed,
                        Some("recovered provider instance failed GPU or budget gate".into()),
                        now,
                    )?;
                    let _ = self.release_training_gpu(run.run_id, provider, now).await;
                    acted += 1;
                    continue;
                }
                self.bind_worker_bootstrap(run.run_id, &lease.provider_instance_id)?;
                lease.hourly_price_cny = snapshot.hourly_price_cny;
                lease.last_provider_status = snapshot.status;
                lease.status = GpuLeaseStatus::WaitingWorker;
                lease.updated_at = now;
                self.save_gpu_lease(&lease)?;
                run.hourly_price_cny = Some(snapshot.hourly_price_cny);
                run = self.transition_training_run(
                    run,
                    TrainingRunStatus::WaitingWorker,
                    Some("recovered provisioning after control-plane restart".into()),
                    now,
                )?;
                acted += 1;
            }
            if let Ok(status) = provider.instance_status(&lease.provider_instance_id).await {
                lease.last_provider_status = status.clone();
                lease.updated_at = now;
                self.save_gpu_lease(&lease)?;
                if ["stopped", "shutdown", "off", "released"]
                    .iter()
                    .any(|value| status.eq_ignore_ascii_case(value))
                {
                    run = self.transition_training_run(
                        run,
                        TrainingRunStatus::Failed,
                        Some(format!(
                            "provider instance entered terminal status {status}"
                        )),
                        now,
                    )?;
                    let _ = self.release_training_gpu(run.run_id, provider, now).await;
                    acted += 1;
                    continue;
                }
            }
            let started_at = run.started_at.unwrap_or(run.created_at);
            let elapsed_seconds = (now - started_at).num_seconds().max(0) as u32;
            run.estimated_cost_cny = lease.hourly_price_cny * f64::from(elapsed_seconds) / 3_600.0;
            let heartbeat_stale = matches!(
                run.status,
                TrainingRunStatus::WaitingWorker
                    | TrainingRunStatus::Running
                    | TrainingRunStatus::Uploading
            ) && lease.last_heartbeat_at.unwrap_or(started_at)
                + Duration::seconds(WORKER_HEARTBEAT_TIMEOUT_SECONDS)
                <= now;
            let timed_out = elapsed_seconds >= run.budget.max_wall_seconds
                || run.estimated_cost_cny >= run.budget.max_total_cny
                || heartbeat_stale;
            if timed_out {
                run = self.transition_training_run(
                    run,
                    TrainingRunStatus::TimedOut,
                    Some("wall-clock, cost, or heartbeat watchdog expired".into()),
                    now,
                )?;
                let _ = self.release_training_gpu(run.run_id, provider, now).await;
                acted += 1;
            } else {
                self.persist_training_run(&run)?;
            }
        }
        Ok(acted)
    }

    fn require_usable_snapshot(&self, id: Uuid) -> Result<DatasetSnapshotRecord> {
        let snapshot = self
            .get_dataset_snapshot(id)?
            .ok_or_else(|| anyhow!("dataset snapshot not found"))?;
        if snapshot.revocation.is_some() {
            bail!("dataset snapshot is revoked");
        }
        if !snapshot.snapshot.eligibility.passed
            || snapshot.snapshot.eligibility.contains_raw_documents
        {
            bail!("dataset snapshot failed training eligibility gates");
        }
        Ok(snapshot)
    }

    fn validate_training_run_inputs(
        &self,
        run: &TrainingRun,
        snapshot: &DatasetSnapshotRecord,
    ) -> Result<()> {
        if run.snapshot_bundle_hash != snapshot.snapshot.bundle_hash
            || run.snapshot_manifest_hash != snapshot.snapshot.manifest_hash
        {
            bail!("TrainingRun no longer matches its immutable DatasetSnapshot");
        }
        self.verify_object_hash(&run.snapshot_bundle_hash)
            .context("dataset Bundle failed CAS integrity verification")?;
        self.verify_object_hash(&run.snapshot_manifest_hash)
            .context("dataset Manifest failed CAS integrity verification")?;
        if let Some(plan) = &run.expert_plan {
            let view = self
                .get_expert_dataset_view(plan.expert_view_id)?
                .ok_or_else(|| anyhow!("expert dataset view was not found"))?;
            validate_expert_dataset_view(&view)?;
            if view.build_id != snapshot.snapshot.build_id
                || snapshot.snapshot.expert_view_id != Some(view.view_id)
                || run.training_bundle_hash.as_deref() != Some(view.bundle_hash.as_str())
                || run.training_manifest_hash.as_deref() != Some(view.manifest_hash.as_str())
                || snapshot.snapshot.expert_taxonomy_hash.as_deref()
                    != Some(view.taxonomy_hash.as_str())
            {
                bail!("routed TrainingRun no longer matches its frozen expert view");
            }
            self.verify_object_hash(&view.bundle_hash)
                .context("expert training Bundle failed CAS integrity verification")?;
            self.verify_object_hash(&view.manifest_hash)
                .context("expert dataset Manifest failed CAS integrity verification")?;
        } else if run.training_bundle_hash.is_some() || run.training_manifest_hash.is_some() {
            bail!("dense TrainingRun unexpectedly references an expert dataset");
        }
        Ok(())
    }

    fn training_started_since(&self, since: DateTime<Utc>, excluding: Uuid) -> Result<bool> {
        let conn = self.lock_conn();
        let count: i64 = conn.query_row(
            "SELECT COUNT(*) FROM training_runs
             WHERE id<>?1 AND started_at IS NOT NULL AND started_at>=?2",
            params![excluding.to_string(), since.to_rfc3339()],
            |row| row.get(0),
        )?;
        Ok(count != 0)
    }

    fn insert_training_run(&self, run: &TrainingRun) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO training_runs(
               id,snapshot_id,status,run_json,created_at,started_at,updated_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7)",
            params![
                run.run_id.to_string(),
                run.snapshot_id.to_string(),
                training_status_name(run.status),
                serde_json::to_string(run)?,
                run.created_at.to_rfc3339(),
                run.started_at.map(|value| value.to_rfc3339()),
                run.updated_at.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    fn persist_training_run(&self, run: &TrainingRun) -> Result<()> {
        let conn = self.lock_conn();
        let changed = conn.execute(
            "UPDATE training_runs SET status=?2,run_json=?3,started_at=?4,updated_at=?5
             WHERE id=?1",
            params![
                run.run_id.to_string(),
                training_status_name(run.status),
                serde_json::to_string(run)?,
                run.started_at.map(|value| value.to_rfc3339()),
                run.updated_at.to_rfc3339()
            ],
        )?;
        if changed != 1 {
            bail!("training run not found");
        }
        Ok(())
    }

    fn transition_training_run(
        &self,
        mut run: TrainingRun,
        status: TrainingRunStatus,
        detail: Option<String>,
        now: DateTime<Utc>,
    ) -> Result<TrainingRun> {
        if !run.status.can_transition_to(status) {
            bail!(
                "invalid training transition {:?} -> {:?}",
                run.status,
                status
            );
        }
        let previous = run.status;
        run.status = status;
        run.updated_at = now;
        if status.is_terminal() {
            run.completed_at.get_or_insert(now);
        }
        if matches!(
            status,
            TrainingRunStatus::Failed | TrainingRunStatus::TimedOut
        ) {
            run.error = detail.clone();
        }
        self.persist_training_run(&run)?;
        self.append_training_event(
            run.run_id,
            "state_transition",
            json!({
                "from":training_status_name(previous),
                "to":training_status_name(status),
                "detail":detail
            }),
            now,
        )?;
        Ok(run)
    }

    fn fail_training_run(
        &self,
        run: TrainingRun,
        error: &str,
        now: DateTime<Utc>,
    ) -> Result<TrainingRun> {
        self.transition_training_run(
            run,
            TrainingRunStatus::Failed,
            Some(error.chars().take(2_000).collect()),
            now,
        )
    }

    fn append_training_event(
        &self,
        run_id: Uuid,
        kind: &str,
        payload: Value,
        now: DateTime<Utc>,
    ) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO training_run_events(run_id,kind,payload_json,created_at)
             VALUES(?1,?2,?3,?4)",
            params![
                run_id.to_string(),
                kind,
                serde_json::to_string(&payload)?,
                now.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    fn save_gpu_lease(&self, lease: &GpuLease) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO gpu_leases(
               run_id,provider_instance_id,status,lease_json,updated_at
             ) VALUES(?1,?2,?3,?4,?5)
             ON CONFLICT(run_id) DO UPDATE SET
               provider_instance_id=excluded.provider_instance_id,
               status=excluded.status,lease_json=excluded.lease_json,
               updated_at=excluded.updated_at",
            params![
                lease.run_id.to_string(),
                lease.provider_instance_id,
                lease_status_name(lease.status),
                serde_json::to_string(lease)?,
                lease.updated_at.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    fn get_gpu_lease(&self, run_id: Uuid) -> Result<Option<GpuLease>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT lease_json FROM gpu_leases WHERE run_id=?1",
            params![run_id.to_string()],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    fn touch_gpu_heartbeat(
        &self,
        run_id: Uuid,
        now: DateTime<Utc>,
        status: GpuLeaseStatus,
    ) -> Result<()> {
        let mut lease = self
            .get_gpu_lease(run_id)?
            .ok_or_else(|| anyhow!("GPU lease not found"))?;
        lease.last_heartbeat_at = Some(now);
        lease.status = status;
        lease.updated_at = now;
        self.save_gpu_lease(&lease)
    }

    fn store_worker_bootstrap(
        &self,
        run_id: Uuid,
        code: &str,
        provider_instance_id: Option<&str>,
        now: DateTime<Utc>,
    ) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO training_worker_bootstraps(
               run_id,code_hash,provider_instance_id,expires_at,exchanged_at,created_at
             ) VALUES(?1,?2,?3,?4,NULL,?5)
             ON CONFLICT(run_id) DO UPDATE SET
               code_hash=excluded.code_hash,provider_instance_id=excluded.provider_instance_id,
               expires_at=excluded.expires_at,exchanged_at=NULL,created_at=excluded.created_at",
            params![
                run_id.to_string(),
                secret_hash(code),
                provider_instance_id,
                (now + Duration::seconds(WORKER_BOOTSTRAP_TTL_SECONDS)).to_rfc3339(),
                now.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    fn bind_worker_bootstrap(&self, run_id: Uuid, instance_id: &str) -> Result<()> {
        let conn = self.lock_conn();
        let changed = conn.execute(
            "UPDATE training_worker_bootstraps SET provider_instance_id=?2
             WHERE run_id=?1 AND exchanged_at IS NULL",
            params![run_id.to_string(), instance_id],
        )?;
        if changed != 1 {
            bail!("worker bootstrap could not be bound to provider instance");
        }
        Ok(())
    }
}

pub fn configured_provider(config: &AutoDlConfig) -> Result<Arc<dyn GpuProvider>> {
    Ok(Arc::new(AutoDlAppProvider::new(config)?))
}

pub async fn run_reconciler(registry: Arc<Registry>, provider: Arc<dyn GpuProvider>) {
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(30));
    loop {
        interval.tick().await;
        let outcome = {
            let registry = registry.clone();
            let provider = provider.clone();
            // Same executor boundary as the learning scheduler: the tick's
            // synchronous lease scans run on a blocking thread.
            tokio::task::spawn_blocking(move || {
                tokio::runtime::Handle::current().block_on(async move {
                    registry
                        .reconcile_training_runs(provider.as_ref(), Utc::now())
                        .await
                })
            })
            .await
        };
        match outcome {
            Ok(Err(error)) => tracing::error!(error=%error, "failed to reconcile GPU leases"),
            Err(error) => tracing::error!(error=%error, "GPU reconciler task failed"),
            Ok(Ok(_)) => {}
        }
    }
}

fn verify_start_confirmation(run: &TrainingRun, request: &StartTrainingRunRequest) -> Result<()> {
    if request.administrator.trim().is_empty()
        || request.reason.trim().is_empty()
        || request.confirm_gpu_spec != run.requested_gpu_spec
        || (request.confirm_max_hourly_cny - run.budget.max_hourly_cny).abs() > 1e-9
        || (request.confirm_max_total_cny - run.budget.max_total_cny).abs() > 1e-9
        || request.confirm_max_wall_seconds != run.budget.max_wall_seconds
    {
        bail!("start confirmation does not exactly match the immutable run budget and GPU spec");
    }
    Ok(())
}

fn worker_start_command(config: &AutoDlConfig, run_id: Uuid, bootstrap_code: &str) -> String {
    format!(
        "python -m cerebellum_meta_training.remote_worker --gateway {} --run-id {} --bootstrap-code {}",
        shell_quote(&config.worker_gateway_url),
        shell_quote(&run_id.to_string()),
        shell_quote(bootstrap_code)
    )
}

fn shell_quote(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\"'\"'"))
}

fn new_secret() -> String {
    format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple())
}

fn secret_hash(secret: &str) -> String {
    format!("{:x}", Sha256::digest(secret.as_bytes()))
}

fn parse_time(value: &str) -> Result<DateTime<Utc>> {
    Ok(DateTime::parse_from_rfc3339(value)?.with_timezone(&Utc))
}

fn expert_adapter_ref(adapter: ExpertAdapterVersion) -> ExpertAdapterRef {
    ExpertAdapterRef {
        expert_id: adapter.expert_id,
        version: adapter.version,
        base_model: adapter.base_model,
        taxonomy_hash: adapter.taxonomy_hash,
        bundle_hash: adapter.bundle_hash,
        artifact_path: adapter.artifact_path,
        artifact_hash: adapter.artifact_hash,
    }
}

fn deterministic_adapter_id(run_id: Uuid, expert_id: &str, version: &str) -> Uuid {
    let digest = Sha256::digest(format!("{run_id}\0{expert_id}\0{version}").as_bytes());
    let mut bytes = [0_u8; 16];
    bytes.copy_from_slice(&digest[..16]);
    bytes[6] = (bytes[6] & 0x0f) | 0x50;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    Uuid::from_bytes(bytes)
}

fn persist_expert_adapter(
    transaction: &rusqlite::Transaction<'_>,
    adapter: &ExpertAdapterVersion,
) -> Result<()> {
    validate_expert_adapter_version(adapter)?;
    let changed = transaction.execute(
        "UPDATE expert_adapter_versions
         SET status=?2,adapter_json=?3,updated_at=?4 WHERE adapter_id=?1",
        params![
            adapter.adapter_id.to_string(),
            expert_adapter_status_name(adapter.status),
            serde_json::to_string(adapter)?,
            adapter.updated_at.to_rfc3339()
        ],
    )?;
    if changed != 1 {
        bail!("expert adapter version not found");
    }
    Ok(())
}

fn expert_adapter_status_name(status: ExpertAdapterStatus) -> &'static str {
    match status {
        ExpertAdapterStatus::Candidate => "candidate",
        ExpertAdapterStatus::Shadow => "shadow",
        ExpertAdapterStatus::Canary => "canary",
        ExpertAdapterStatus::Active => "active",
        ExpertAdapterStatus::Superseded => "superseded",
        ExpertAdapterStatus::Rejected => "rejected",
        ExpertAdapterStatus::RolledBack => "rolled_back",
    }
}

fn training_status_name(status: TrainingRunStatus) -> &'static str {
    match status {
        TrainingRunStatus::Requested => "requested",
        TrainingRunStatus::Provisioning => "provisioning",
        TrainingRunStatus::WaitingCapacity => "waiting_capacity",
        TrainingRunStatus::WaitingWorker => "waiting_worker",
        TrainingRunStatus::Running => "running",
        TrainingRunStatus::Uploading => "uploading",
        TrainingRunStatus::Completed => "completed",
        TrainingRunStatus::Failed => "failed",
        TrainingRunStatus::Cancelled => "cancelled",
        TrainingRunStatus::TimedOut => "timed_out",
    }
}

fn lease_status_name(status: GpuLeaseStatus) -> &'static str {
    match status {
        GpuLeaseStatus::Provisioning => "provisioning",
        GpuLeaseStatus::WaitingWorker => "waiting_worker",
        GpuLeaseStatus::Running => "running",
        GpuLeaseStatus::ReleaseRequested => "release_requested",
        GpuLeaseStatus::Released => "released",
        GpuLeaseStatus::ReleaseFailed => "release_failed",
    }
}

fn is_capacity_error(message: &str) -> bool {
    let lower = message.to_ascii_lowercase();
    [
        "capacity",
        "no stock",
        "out of stock",
        "insufficient resource",
        "库存",
        "无可用",
        "资源不足",
    ]
    .iter()
    .any(|needle| lower.contains(needle))
}

fn sanitize_provider_error(message: &str) -> String {
    message.chars().take(1_000).collect()
}

async fn cleanup_provider_instance(provider: &dyn GpuProvider, instance_id: &str) -> Result<()> {
    let _ = provider.power_off(instance_id).await;
    provider.release(instance_id).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dataset_factory::META_DATASET_KIND;
    use axum::{
        Json, Router,
        extract::State,
        http::HeaderMap,
        routing::{get, post},
    };
    use cerebellum_core::{
        BaseModelPin, DatasetEligibilityReport, DatasetSnapshot, DatasetSplitStats,
        ExpertAdapterArtifact, ExpertAdapterMetrics, ExpertAdapterOperationRequest,
        ExpertDatasetStats, ExpertTrainingPlan, QloraConfig, RoutedAdapterBundleManifest,
        TrainingArchitecture, TrainingBudget,
    };
    use serde_json::Value;
    use std::sync::{
        Mutex,
        atomic::{AtomicUsize, Ordering},
    };
    use tempfile::tempdir;

    #[derive(Clone, Default)]
    struct FakeAutoDlState {
        calls: Arc<Mutex<Vec<String>>>,
    }

    async fn fake_create(
        State(state): State<FakeAutoDlState>,
        headers: HeaderMap,
        Json(body): Json<Value>,
    ) -> Json<Value> {
        assert_eq!(headers.get("authorization").unwrap(), "developer-token");
        assert_eq!(body["application_version"], "v1");
        state.calls.lock().unwrap().push("create".into());
        Json(json!({"code":"Success","data":"pro-fake","msg":"","request_id":"r1"}))
    }

    async fn fake_snapshot(
        State(state): State<FakeAutoDlState>,
        Json(body): Json<Value>,
    ) -> Json<Value> {
        assert_eq!(body["instance_uuid"], "pro-fake");
        state.calls.lock().unwrap().push("snapshot".into());
        Json(json!({
            "code":"Success",
            "data":{
                "payg_price":1970,
                "snapshot_gpu_alias_name":"NVIDIA RTX 4090",
                "chip_corp":"nvidia",
                "usage_info":{"valid":true},
                "root_password":"must-not-be-retained"
            },
            "msg":"",
            "request_id":"r2"
        }))
    }

    async fn fake_status(
        State(state): State<FakeAutoDlState>,
        Json(_): Json<Value>,
    ) -> Json<Value> {
        state.calls.lock().unwrap().push("status".into());
        Json(json!({"code":"Success","data":"running","msg":"","request_id":"r3"}))
    }

    async fn fake_power_off(
        State(state): State<FakeAutoDlState>,
        Json(_): Json<Value>,
    ) -> Json<Value> {
        state.calls.lock().unwrap().push("power_off".into());
        Json(json!({"code":"Success","data":null,"msg":"","request_id":"r4"}))
    }

    async fn fake_release(
        State(state): State<FakeAutoDlState>,
        Json(_): Json<Value>,
    ) -> Json<Value> {
        state.calls.lock().unwrap().push("release".into());
        Json(json!({"code":"Success","data":null,"msg":"","request_id":"r5"}))
    }

    struct FakeProvider {
        creates: AtomicUsize,
        releases: AtomicUsize,
        price: f64,
        last_command: Mutex<Option<String>>,
    }

    #[async_trait]
    impl GpuProvider for FakeProvider {
        fn name(&self) -> &'static str {
            "autodl-app"
        }

        async fn create_instance(&self, request: &ProvisionRequest) -> Result<ProvisionOutcome> {
            self.creates.fetch_add(1, Ordering::SeqCst);
            *self.last_command.lock().unwrap() = Some(request.start_command.clone());
            Ok(ProvisionOutcome::Created {
                instance_id: "pro-test".into(),
            })
        }

        async fn instance_snapshot(&self, instance_id: &str) -> Result<ProviderInstanceSnapshot> {
            Ok(ProviderInstanceSnapshot {
                instance_id: instance_id.into(),
                status: "running".into(),
                hourly_price_cny: self.price,
                gpu_name: "NVIDIA test".into(),
                chip_vendor: "nvidia".into(),
            })
        }

        async fn instance_status(&self, _: &str) -> Result<String> {
            Ok("running".into())
        }

        async fn power_off(&self, _: &str) -> Result<()> {
            Ok(())
        }

        async fn release(&self, _: &str) -> Result<()> {
            self.releases.fetch_add(1, Ordering::SeqCst);
            Ok(())
        }
    }

    fn config() -> AutoDlConfig {
        AutoDlConfig {
            api_base_url: "https://example.invalid".into(),
            api_token: "secret".into(),
            application_uuid: "app-test".into(),
            application_version: "v1".into(),
            worker_gateway_url: "https://worker.example.invalid".into(),
            provider_name: "autodl-app".into(),
            gpu_allowlist: vec![AutoDlGpuSpecConfig {
                id: "v-48g".into(),
                display_name: "4090 48G".into(),
                memory_gb: 48,
                cuda: true,
                data_centers: vec!["westDC3".into()],
            }],
            base_models: vec![BaseModelPin {
                model_id: "example/model".into(),
                revision: "abc123".into(),
                sha256: "a".repeat(64),
            }],
        }
    }

    fn seed_snapshot(registry: &Registry) -> Uuid {
        let snapshot = DatasetSnapshot {
            schema_version: SCHEMA_VERSION.into(),
            snapshot_id: Uuid::new_v4(),
            kind: META_DATASET_KIND.into(),
            build_id: Uuid::new_v4(),
            bundle_hash: registry.put_object(b"bundle").unwrap(),
            manifest_hash: registry.put_object(b"manifest").unwrap(),
            decision_count: 1,
            replay_eval_count: 0,
            split_stats: DatasetSplitStats {
                train: 1,
                validation: 0,
                holdout: 0,
            },
            eligibility: DatasetEligibilityReport {
                passed: true,
                policy_version: "test".into(),
                contains_raw_documents: false,
                eligible_records: 1,
                rejected_license_records: 0,
                rejected_safety_records: 0,
                reasons: vec![],
            },
            expert_view_id: None,
            expert_manifest_hash: None,
            expert_taxonomy_hash: None,
            quality_report_id: None,
            quality_report_hash: None,
            created_by: "test".into(),
            reason: "test".into(),
            legacy_candidate_id: None,
            created_at: Utc::now(),
        };
        let conn = registry.lock_conn();
        conn.execute(
            "INSERT INTO dataset_snapshots(id,kind,build_id,bundle_hash,manifest_hash,snapshot_json,created_at)
             VALUES(?1,?2,?3,?4,?5,?6,?7)",
            params![
                snapshot.snapshot_id.to_string(),
                snapshot.kind,
                snapshot.build_id.to_string(),
                snapshot.bundle_hash,
                snapshot.manifest_hash,
                serde_json::to_string(&snapshot).unwrap(),
                snapshot.created_at.to_rfc3339()
            ],
        )
        .unwrap();
        snapshot.snapshot_id
    }

    fn create_request(snapshot_id: Uuid) -> CreateTrainingRunRequest {
        CreateTrainingRunRequest {
            snapshot_id,
            base_model: config().base_models[0].clone(),
            qlora: QloraConfig::default(),
            expert_plan: None,
            gpu_spec: "v-48g".into(),
            administrator: "admin".into(),
            reason: "manual test".into(),
            budget: TrainingBudget {
                max_hourly_cny: 2.0,
                max_total_cny: 4.0,
                max_wall_seconds: 3_600,
            },
        }
    }

    fn routed_manifest(run: &TrainingRun) -> RoutedAdapterBundleManifest {
        RoutedAdapterBundleManifest {
            schema_version: SCHEMA_VERSION.into(),
            kind: "routed_lora_bundle_v1".into(),
            base_model: run.base_model.clone(),
            snapshot_id: run.snapshot_id,
            expert_view_id: Uuid::new_v4(),
            taxonomy_hash: "c".repeat(64),
            router_top_k: 1,
            fallback_expert_id: "shared".into(),
            router: Some(ExpertAdapterArtifact {
                expert_id: "router".into(),
                path: "adapters/router.zip".into(),
                sha256: "d".repeat(64),
                byte_length: 10,
                training_records: 5_000,
            }),
            experts: vec![
                ExpertAdapterArtifact {
                    expert_id: "retrieval".into(),
                    path: "adapters/retrieval.zip".into(),
                    sha256: "e".repeat(64),
                    byte_length: 11,
                    training_records: 1_200,
                },
                ExpertAdapterArtifact {
                    expert_id: "shared".into(),
                    path: "adapters/shared.zip".into(),
                    sha256: "f".repeat(64),
                    byte_length: 12,
                    training_records: 6_000,
                },
            ],
        }
    }

    fn passing_expert_metrics() -> ExpertAdapterMetrics {
        ExpertAdapterMetrics {
            evaluation_count: 200,
            canary_decisions: 1_000,
            canary_duration_seconds: 86_400,
            old_task_retention: 0.99,
            task_success_delta: 0.02,
            negative_transfer_rate_delta: -0.01,
            routing_accuracy_delta: 0.01,
            policy_violations: 0,
            injection_regression: false,
        }
    }

    /// A gate-passing evaluation report pinned to the adapter's identity
    /// (canary dimensions are zero: they are server-recomputed at the gate).
    fn passing_eval_report(
        adapter: &ExpertAdapterVersion,
    ) -> (cerebellum_core::ExpertAdapterEvalReport, Vec<u8>) {
        let results = b"{\"set\":\"role\",\"record_hash\":\"h\",\"base_success\":true,\"adapted_success\":true,\"violation\":false}\n".to_vec();
        let report = cerebellum_core::ExpertAdapterEvalReport {
            schema_version: SCHEMA_VERSION.into(),
            kind: "expert_adapter_eval_report_v1".into(),
            report_id: Uuid::new_v4(),
            adapter_id: adapter.adapter_id,
            expert_id: adapter.expert_id.clone(),
            version: adapter.version.clone(),
            base_model: adapter.base_model.clone(),
            snapshot_id: adapter.snapshot_id,
            expert_view_id: adapter.expert_view_id,
            taxonomy_hash: adapter.taxonomy_hash.clone(),
            base_gguf_sha256: "a".repeat(64),
            adapted_gguf_sha256: "b".repeat(64),
            llama_server_sha256: "c".repeat(64),
            set_summaries: ["role", "routing", "negative_transfer", "retention"]
                .into_iter()
                .map(|name| cerebellum_core::EvalSetSummary {
                    set_name: name.into(),
                    record_count: 50,
                    records_sha256: "d".repeat(64),
                })
                .collect(),
            metrics: ExpertAdapterMetrics {
                canary_decisions: 0,
                canary_duration_seconds: 0,
                ..passing_expert_metrics()
            },
            task_success_delta_ci95_low: 0.01,
            routing_accuracy_delta_ci95_low: 0.005,
            injection_probe_base_violations: 0,
            injection_probe_adapted_violations: 0,
            results_object_hash: format!("{:x}", Sha256::digest(&results)),
            metacognition: None,
            harness_version: "adapter-eval/1".into(),
            llama_cpp_version: "test-double".into(),
            started_at: Utc::now(),
            finished_at: Utc::now(),
            created_at: Utc::now(),
        };
        (report, results)
    }

    fn record_passing_eval_report(registry: &Registry, adapter: &ExpertAdapterVersion) -> Uuid {
        let (report, results) = passing_eval_report(adapter);
        let report_id = report.report_id;
        registry
            .record_expert_adapter_eval_report(&report, &results)
            .unwrap();
        report_id
    }

    fn annotation_request() -> ExpertAdapterOperationRequest {
        ExpertAdapterOperationRequest {
            actor: "admin".into(),
            reason: "objective replay passed".into(),
            metrics: None,
            eval_report_id: None,
        }
    }

    fn gate_request(
        registry: &Registry,
        expert_id: &str,
        version: &str,
    ) -> ExpertAdapterOperationRequest {
        let adapter = registry
            .get_expert_adapter(expert_id, version)
            .unwrap()
            .unwrap();
        let report_id = record_passing_eval_report(registry, &adapter);
        ExpertAdapterOperationRequest {
            eval_report_id: Some(report_id),
            ..annotation_request()
        }
    }

    fn seed_canary_accounting(registry: &Registry, adapter_id: Uuid, canary_start: DateTime<Utc>) {
        let conn = registry.lock_conn();
        for index in 0..1_000_i64 {
            let created = canary_start + chrono::Duration::seconds(86_400 + index);
            conn.execute(
                "INSERT INTO expert_canary_decisions(
                   id,adapter_id,decision_id,selected_expert,dense_fallback,unsafe_input,created_at
                 ) VALUES (?1,?2,?3,'router',0,0,?4)",
                params![
                    Uuid::new_v4().to_string(),
                    adapter_id.to_string(),
                    Uuid::new_v4().to_string(),
                    created.to_rfc3339()
                ],
            )
            .unwrap();
        }
    }

    #[test]
    fn expert_adapters_have_independent_gates_versions_and_rollback() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), Utc::now())
            .unwrap();
        let manifest = routed_manifest(&run);
        registry
            .register_expert_adapter_candidates(
                &run,
                "1.0.0",
                &"a".repeat(64),
                &manifest,
                Utc::now(),
            )
            .unwrap();
        registry
            .register_expert_adapter_candidates(
                &run,
                "1.0.0",
                &"a".repeat(64),
                &manifest,
                Utc::now(),
            )
            .unwrap();
        assert_eq!(registry.list_expert_adapters(None).unwrap().len(), 3);
        registry
            .operate_expert_adapter(
                "router",
                "1.0.0",
                "shadow",
                &annotation_request(),
                Utc::now(),
            )
            .unwrap();
        let request_100 = gate_request(&registry, "router", "1.0.0");
        let canary_start = Utc::now() - chrono::Duration::hours(25);
        registry
            .operate_expert_adapter("router", "1.0.0", "canary", &request_100, canary_start)
            .unwrap();
        seed_canary_accounting(
            &registry,
            deterministic_adapter_id(run.run_id, "router", "1.0.0"),
            canary_start,
        );
        registry
            .operate_expert_adapter("router", "1.0.0", "activate", &request_100, Utc::now())
            .unwrap();
        assert_eq!(
            registry
                .get_expert_adapter("retrieval", "1.0.0")
                .unwrap()
                .unwrap()
                .status,
            ExpertAdapterStatus::Candidate
        );

        registry
            .register_expert_adapter_candidates(
                &run,
                "1.1.0",
                &"b".repeat(64),
                &manifest,
                Utc::now(),
            )
            .unwrap();
        registry
            .operate_expert_adapter(
                "router",
                "1.1.0",
                "shadow",
                &annotation_request(),
                Utc::now(),
            )
            .unwrap();
        let request_110 = gate_request(&registry, "router", "1.1.0");
        let canary_start = Utc::now() - chrono::Duration::hours(25);
        registry
            .operate_expert_adapter("router", "1.1.0", "canary", &request_110, canary_start)
            .unwrap();
        seed_canary_accounting(
            &registry,
            deterministic_adapter_id(run.run_id, "router", "1.1.0"),
            canary_start,
        );
        registry
            .operate_expert_adapter("router", "1.1.0", "activate", &request_110, Utc::now())
            .unwrap();
        assert_eq!(
            registry
                .get_expert_adapter("router", "1.0.0")
                .unwrap()
                .unwrap()
                .status,
            ExpertAdapterStatus::Superseded
        );
        registry
            .operate_expert_adapter(
                "router",
                "1.1.0",
                "rollback",
                &annotation_request(),
                Utc::now(),
            )
            .unwrap();
        assert_eq!(
            registry
                .active_expert_adapter("router")
                .unwrap()
                .unwrap()
                .version,
            "1.0.0"
        );

        registry
            .operate_expert_adapter(
                "retrieval",
                "1.0.0",
                "shadow",
                &annotation_request(),
                Utc::now(),
            )
            .unwrap();
        // A recorded report with a negative-transfer regression fails the gate.
        let retrieval = registry
            .get_expert_adapter("retrieval", "1.0.0")
            .unwrap()
            .unwrap();
        let (mut report, results) = passing_eval_report(&retrieval);
        report.metrics.negative_transfer_rate_delta = 0.01;
        registry
            .record_expert_adapter_eval_report(&report, &results)
            .unwrap();
        let unsafe_request = ExpertAdapterOperationRequest {
            eval_report_id: Some(report.report_id),
            ..annotation_request()
        };
        assert!(
            registry
                .operate_expert_adapter("retrieval", "1.0.0", "canary", &unsafe_request, Utc::now())
                .is_err()
        );
    }

    #[test]
    fn operate_requires_a_recorded_matching_eval_report() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), Utc::now())
            .unwrap();
        let manifest = routed_manifest(&run);
        registry
            .register_expert_adapter_candidates(
                &run,
                "1.0.0",
                &"a".repeat(64),
                &manifest,
                Utc::now(),
            )
            .unwrap();
        registry
            .operate_expert_adapter(
                "router",
                "1.0.0",
                "shadow",
                &annotation_request(),
                Utc::now(),
            )
            .unwrap();

        // No report reference at all.
        assert!(
            registry
                .operate_expert_adapter(
                    "router",
                    "1.0.0",
                    "canary",
                    &annotation_request(),
                    Utc::now()
                )
                .is_err(),
            "canary without eval_report_id must be rejected"
        );
        // Request-body metrics are refused even alongside a valid report.
        let request = gate_request(&registry, "router", "1.0.0");
        let with_metrics = ExpertAdapterOperationRequest {
            metrics: Some(passing_expert_metrics()),
            ..request.clone()
        };
        assert!(
            registry
                .operate_expert_adapter("router", "1.0.0", "canary", &with_metrics, Utc::now())
                .is_err(),
            "request-body metrics must be rejected"
        );
        // An unknown report id.
        let unknown = ExpertAdapterOperationRequest {
            eval_report_id: Some(Uuid::new_v4()),
            ..annotation_request()
        };
        assert!(
            registry
                .operate_expert_adapter("router", "1.0.0", "canary", &unknown, Utc::now())
                .is_err(),
            "unknown evaluation report must be rejected"
        );
        // A report recorded for another adapter version (here also under a
        // different taxonomy hash) must not gate this adapter.
        let mut other_manifest = manifest.clone();
        other_manifest.taxonomy_hash = "f".repeat(64);
        registry
            .register_expert_adapter_candidates(
                &run,
                "1.1.0",
                &"b".repeat(64),
                &other_manifest,
                Utc::now(),
            )
            .unwrap();
        assert!(
            registry
                .operate_expert_adapter("router", "1.1.0", "canary", &request, Utc::now())
                .is_err(),
            "another adapter/taxonomy's report must be rejected"
        );
        // The matching report gates the transition.
        registry
            .operate_expert_adapter("router", "1.0.0", "canary", &request, Utc::now())
            .unwrap();
        // The release gate still needs the server-side canary record: a real
        // report cannot substitute for it.
        assert!(
            registry
                .operate_expert_adapter("router", "1.0.0", "activate", &request, Utc::now())
                .is_err(),
            "activation without server canary records must fail"
        );
    }

    #[test]
    fn server_canary_records_satisfy_release_gate_despite_evidence_zeros() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), Utc::now())
            .unwrap();
        let manifest = routed_manifest(&run);
        registry
            .register_expert_adapter_candidates(
                &run,
                "1.0.0",
                &"a".repeat(64),
                &manifest,
                Utc::now(),
            )
            .unwrap();
        registry
            .operate_expert_adapter(
                "router",
                "1.0.0",
                "shadow",
                &annotation_request(),
                Utc::now(),
            )
            .unwrap();
        let request = gate_request(&registry, "router", "1.0.0");
        let canary_start = Utc::now() - chrono::Duration::hours(25);
        registry
            .operate_expert_adapter("router", "1.0.0", "canary", &request, canary_start)
            .unwrap();
        seed_canary_accounting(
            &registry,
            deterministic_adapter_id(run.run_id, "router", "1.0.0"),
            canary_start,
        );

        // The evidence file's canary dimensions are zero by contract; the
        // server-side routing record fills them in at the gate.
        registry
            .operate_expert_adapter("router", "1.0.0", "activate", &request, Utc::now())
            .unwrap();
        let adapter = registry
            .get_expert_adapter("router", "1.0.0")
            .unwrap()
            .unwrap();
        assert_eq!(adapter.status, ExpertAdapterStatus::Active);
        let metrics = adapter.metrics.unwrap();
        assert_eq!(metrics.canary_decisions, 1_000);
        assert!(metrics.canary_duration_seconds >= 86_400);
    }

    #[test]
    fn routed_completion_verifies_inner_artifacts_and_registers_candidates() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let now = Utc::now();
        let build = registry
            .build_dataset_draft(META_DATASET_KIND, now)
            .unwrap();
        let mut view = registry
            .get_expert_dataset_view(build.expert_view_id.unwrap())
            .unwrap()
            .unwrap();
        view.assignment_count = 1;
        view.readiness.router_train_records = view.readiness.minimum_router_records;
        for stats in view.readiness.per_expert.values_mut() {
            *stats = ExpertDatasetStats {
                records: DatasetSplitStats {
                    train: 1_000,
                    validation: 0,
                    holdout: 200,
                },
                decision_records: 1_000,
                replay_records: 200,
                evaluation_replay_records: 200,
            };
        }
        view.readiness.ready = true;
        view.readiness.reasons.clear();
        validate_expert_dataset_view(&view).unwrap();
        registry
            .lock_conn()
            .execute(
                "UPDATE expert_dataset_views SET view_json=?2 WHERE id=?1",
                params![
                    view.view_id.to_string(),
                    serde_json::to_string(&view).unwrap()
                ],
            )
            .unwrap();
        let snapshot = registry
            .freeze_dataset_snapshot(
                &cerebellum_core::CreateDatasetSnapshotRequest {
                    kind: META_DATASET_KIND.into(),
                    build_id: Some(build.build_id),
                    created_by: "test".into(),
                    reason: "routed completion fixture".into(),
                },
                now,
            )
            .unwrap();
        let mut request = create_request(snapshot.snapshot.snapshot_id);
        request.expert_plan = Some(ExpertTrainingPlan {
            architecture: TrainingArchitecture::RoutedLora,
            expert_view_id: view.view_id,
            train_router: true,
            train_shared: true,
            expert_ids: vec!["retrieval".into()],
            router_top_k: 1,
            fallback_expert_id: "shared".into(),
        });
        let mut partial_request = request.clone();
        if let Some(plan) = partial_request.expert_plan.as_mut() {
            plan.train_router = false;
            plan.train_shared = false;
        }
        let partial = registry
            .create_training_run(&partial_request, &config(), now)
            .unwrap();
        assert!(!partial.expert_plan.unwrap().train_router);
        let mut run = registry
            .create_training_run(&request, &config(), now)
            .unwrap();
        let router = b"router-adapter".to_vec();
        let retrieval = b"retrieval-adapter".to_vec();
        let shared = b"shared-adapter".to_vec();
        let manifest = RoutedAdapterBundleManifest {
            schema_version: SCHEMA_VERSION.into(),
            kind: "routed_lora_bundle_v1".into(),
            base_model: run.base_model.clone(),
            snapshot_id: run.snapshot_id,
            expert_view_id: view.view_id,
            taxonomy_hash: view.taxonomy_hash.clone(),
            router_top_k: 1,
            fallback_expert_id: "shared".into(),
            router: Some(ExpertAdapterArtifact {
                expert_id: "router".into(),
                path: "adapters/router.zip".into(),
                sha256: format!("{:x}", Sha256::digest(&router)),
                byte_length: router.len() as u64,
                training_records: 5_000,
            }),
            experts: vec![
                ExpertAdapterArtifact {
                    expert_id: "retrieval".into(),
                    path: "adapters/retrieval.zip".into(),
                    sha256: format!("{:x}", Sha256::digest(&retrieval)),
                    byte_length: retrieval.len() as u64,
                    training_records: 1_200,
                },
                ExpertAdapterArtifact {
                    expert_id: "shared".into(),
                    path: "adapters/shared.zip".into(),
                    sha256: format!("{:x}", Sha256::digest(&shared)),
                    byte_length: shared.len() as u64,
                    training_records: 6_000,
                },
            ],
        };
        let manifest_bytes = serde_json::to_vec(&manifest).unwrap();
        let mut archive = tar::Builder::new(Vec::new());
        for (path, value) in [
            ("adapters/retrieval.zip", retrieval),
            ("adapters/router.zip", router),
            ("adapters/shared.zip", shared),
            ("cerebellum-routed-adapter-manifest.json", manifest_bytes),
        ] {
            let mut header = tar::Header::new_gnu();
            header.set_size(value.len() as u64);
            header.set_mode(0o644);
            header.set_mtime(0);
            header.set_cksum();
            archive
                .append_data(&mut header, path, std::io::Cursor::new(value))
                .unwrap();
        }
        archive.finish().unwrap();
        let artifact = archive.into_inner().unwrap();
        let artifact_hash = registry.put_object(&artifact).unwrap();
        run = registry
            .transition_training_run(run, TrainingRunStatus::Provisioning, None, now)
            .unwrap();
        run = registry
            .transition_training_run(run, TrainingRunStatus::WaitingWorker, None, now)
            .unwrap();
        run = registry
            .transition_training_run(run, TrainingRunStatus::Running, None, now)
            .unwrap();
        registry
            .save_training_artifact(
                run.run_id,
                "adapter",
                &artifact_hash,
                artifact.len() as u64,
                &json!({}),
                now,
            )
            .unwrap();
        let (completed, _) = registry
            .complete_training_run_from_worker(
                run.run_id,
                &WorkerCompleteRequest {
                    model_id: "meta-controller".into(),
                    model_version: "2.0.0".into(),
                    artifact_hash,
                    metrics: MetaModelMetrics::default(),
                },
                now,
            )
            .unwrap();
        assert_eq!(completed.status, TrainingRunStatus::Completed);
        let candidates = registry.list_expert_adapters(None).unwrap();
        assert_eq!(candidates.len(), 3);
        assert!(
            candidates
                .iter()
                .all(|adapter| adapter.status == ExpertAdapterStatus::Candidate)
        );
    }

    #[tokio::test]
    async fn creating_a_run_never_calls_the_gpu_provider() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let provider = FakeProvider {
            creates: AtomicUsize::new(0),
            releases: AtomicUsize::new(0),
            price: 1.0,
            last_command: Mutex::new(None),
        };
        registry
            .create_training_run(&create_request(snapshot_id), &config(), Utc::now())
            .unwrap();
        assert_eq!(provider.creates.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn explicit_start_provisions_and_over_budget_releases() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), Utc::now())
            .unwrap();
        let confirmation = StartTrainingRunRequest {
            administrator: "admin".into(),
            reason: "confirmed".into(),
            confirm_gpu_spec: "v-48g".into(),
            confirm_max_hourly_cny: 2.0,
            confirm_max_total_cny: 4.0,
            confirm_max_wall_seconds: 3_600,
        };
        let provider = FakeProvider {
            creates: AtomicUsize::new(0),
            releases: AtomicUsize::new(0),
            price: 3.0,
            last_command: Mutex::new(None),
        };
        let result = registry
            .start_training_run_with_thresholds(
                run.run_id,
                &confirmation,
                &config(),
                &provider,
                Utc::now(),
                TrainingReadinessThresholds {
                    decisions: 1,
                    replays: 0,
                },
            )
            .await
            .unwrap();
        assert_eq!(result.status, TrainingRunStatus::Failed);
        assert_eq!(provider.creates.load(Ordering::SeqCst), 1);
        assert_eq!(provider.releases.load(Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn bootstrap_is_one_use_and_heartbeat_rotates_the_scoped_token() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), Utc::now())
            .unwrap();
        let confirmation = StartTrainingRunRequest {
            administrator: "admin".into(),
            reason: "confirmed".into(),
            confirm_gpu_spec: "v-48g".into(),
            confirm_max_hourly_cny: 2.0,
            confirm_max_total_cny: 4.0,
            confirm_max_wall_seconds: 3_600,
        };
        let provider = FakeProvider {
            creates: AtomicUsize::new(0),
            releases: AtomicUsize::new(0),
            price: 1.0,
            last_command: Mutex::new(None),
        };
        let started = registry
            .start_training_run_with_thresholds(
                run.run_id,
                &confirmation,
                &config(),
                &provider,
                Utc::now(),
                TrainingReadinessThresholds {
                    decisions: 1,
                    replays: 0,
                },
            )
            .await
            .unwrap();
        assert_eq!(started.status, TrainingRunStatus::WaitingWorker);
        let command = provider.last_command.lock().unwrap().clone().unwrap();
        let bootstrap_code = command
            .split_whitespace()
            .last()
            .unwrap()
            .trim_matches('\'')
            .to_owned();
        let exchange_request = WorkerBootstrapRequest {
            run_id: run.run_id,
            bootstrap_code,
        };
        let session = registry
            .exchange_worker_bootstrap(&exchange_request, Utc::now())
            .unwrap();
        assert!(
            registry
                .exchange_worker_bootstrap(&exchange_request, Utc::now())
                .is_err()
        );
        let next = registry
            .rotate_worker_heartbeat(
                run.run_id,
                &session.worker_token,
                &WorkerHeartbeatRequest {
                    progress: "training".into(),
                    message: None,
                },
                Utc::now(),
            )
            .unwrap();
        // Within the grace window the rotated-out token still authorizes, so
        // an in-flight upload/complete started before the rotation succeeds.
        assert!(
            registry
                .authorize_worker_token(&session.worker_token, run.run_id, Utc::now())
                .is_ok()
        );
        // Past the grace window it is rejected.
        assert!(
            registry
                .authorize_worker_token(
                    &session.worker_token,
                    run.run_id,
                    Utc::now() + Duration::seconds(REPLACED_TOKEN_GRACE_SECONDS + 1),
                )
                .is_err()
        );
        // A rotated-out token cannot rotate again.
        assert!(
            registry
                .rotate_worker_heartbeat(
                    run.run_id,
                    &session.worker_token,
                    &WorkerHeartbeatRequest {
                        progress: "training".into(),
                        message: None,
                    },
                    Utc::now(),
                )
                .is_err()
        );
        assert!(
            registry
                .authorize_worker_token(&next.worker_token, run.run_id, Utc::now())
                .is_ok()
        );
        let artifact_hash = registry.put_object(b"fake-adapter").unwrap();
        registry
            .save_training_artifact(
                run.run_id,
                "adapter",
                &artifact_hash,
                12,
                &json!({"test":true}),
                Utc::now(),
            )
            .unwrap();
        let (completed, model) = registry
            .complete_training_run_from_worker(
                run.run_id,
                &WorkerCompleteRequest {
                    model_id: "meta-controller".into(),
                    model_version: "0.1.0".into(),
                    artifact_hash,
                    metrics: MetaModelMetrics::default(),
                },
                Utc::now(),
            )
            .unwrap();
        assert_eq!(completed.status, TrainingRunStatus::Completed);
        assert_eq!(model.status, MetaModelStatus::Candidate);
        assert!(registry.active_meta_model().unwrap().is_none());
        registry
            .release_training_gpu(run.run_id, &provider, Utc::now())
            .await
            .unwrap();
        assert_eq!(provider.releases.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn seven_daily_drafts_never_touch_a_gpu_provider() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let provider = FakeProvider {
            creates: AtomicUsize::new(0),
            releases: AtomicUsize::new(0),
            price: 1.0,
            last_command: Mutex::new(None),
        };
        let start = Utc::now();
        for day in 0..7 {
            registry
                .build_dataset_draft(META_DATASET_KIND, start + Duration::days(day))
                .unwrap();
        }
        assert_eq!(provider.creates.load(Ordering::SeqCst), 0);
        assert_eq!(
            registry
                .list_dataset_builds(META_DATASET_KIND, 30)
                .unwrap()
                .len(),
            7
        );
    }

    #[tokio::test]
    async fn autodl_contract_uses_direct_token_pinned_app_and_milli_cny_price() {
        let fake_state = FakeAutoDlState::default();
        let app = Router::new()
            .route("/api/v1/adl_dev/dev/instance/pro/create", post(fake_create))
            .route(
                "/api/v1/adl_dev/dev/instance/pro/snapshot",
                get(fake_snapshot),
            )
            .route("/api/v1/adl_dev/dev/instance/pro/status", get(fake_status))
            .route(
                "/api/v1/adl_dev/dev/instance/pro/power_off",
                post(fake_power_off),
            )
            .route(
                "/api/v1/adl_dev/dev/instance/pro/release",
                post(fake_release),
            )
            .with_state(fake_state.clone());
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
        let mut provider_config = config();
        provider_config.api_base_url = format!("http://{address}");
        provider_config.api_token = "developer-token".into();
        let provider = AutoDlAppProvider::new(&provider_config).unwrap();
        let request = ProvisionRequest {
            run_id: Uuid::new_v4(),
            application_uuid: "app-test".into(),
            application_version: "v1".into(),
            gpu_spec: provider_config.gpu_allowlist[0].clone(),
            start_command: "python worker.py --bootstrap-code one-use".into(),
        };
        assert_eq!(
            provider.create_instance(&request).await.unwrap(),
            ProvisionOutcome::Created {
                instance_id: "pro-fake".into()
            }
        );
        let snapshot = provider.instance_snapshot("pro-fake").await.unwrap();
        assert!((snapshot.hourly_price_cny - 1.97).abs() < 1e-9);
        assert_eq!(
            provider.instance_status("pro-fake").await.unwrap(),
            "running"
        );
        provider.power_off("pro-fake").await.unwrap();
        provider.release("pro-fake").await.unwrap();
        assert_eq!(
            *fake_state.calls.lock().unwrap(),
            vec!["create", "snapshot", "status", "power_off", "release"]
        );
    }

    fn confirmation() -> StartTrainingRunRequest {
        StartTrainingRunRequest {
            administrator: "admin".into(),
            reason: "confirmed".into(),
            confirm_gpu_spec: "v-48g".into(),
            confirm_max_hourly_cny: 2.0,
            confirm_max_total_cny: 4.0,
            confirm_max_wall_seconds: 3_600,
        }
    }

    fn cancel_request() -> CancelTrainingRunRequest {
        CancelTrainingRunRequest {
            administrator: "admin".into(),
            reason: "operator cancel".into(),
        }
    }

    fn fake_provider(price: f64) -> FakeProvider {
        FakeProvider {
            creates: AtomicUsize::new(0),
            releases: AtomicUsize::new(0),
            price,
            last_command: Mutex::new(None),
        }
    }

    struct ReconcileProvider {
        status: Mutex<String>,
        releases: AtomicUsize,
        price: f64,
    }

    #[async_trait]
    impl GpuProvider for ReconcileProvider {
        fn name(&self) -> &'static str {
            "autodl-app"
        }

        async fn create_instance(&self, _: &ProvisionRequest) -> Result<ProvisionOutcome> {
            Ok(ProvisionOutcome::Created {
                instance_id: "pro-reconcile".into(),
            })
        }

        async fn instance_snapshot(&self, instance_id: &str) -> Result<ProviderInstanceSnapshot> {
            Ok(ProviderInstanceSnapshot {
                instance_id: instance_id.into(),
                status: "running".into(),
                hourly_price_cny: self.price,
                gpu_name: "NVIDIA test".into(),
                chip_vendor: "nvidia".into(),
            })
        }

        async fn instance_status(&self, _: &str) -> Result<String> {
            Ok(self.status.lock().unwrap().clone())
        }

        async fn power_off(&self, _: &str) -> Result<()> {
            Ok(())
        }

        async fn release(&self, _: &str) -> Result<()> {
            self.releases.fetch_add(1, Ordering::SeqCst);
            Ok(())
        }
    }

    #[tokio::test]
    async fn get_list_and_detail_round_trip_a_started_run() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();
        let first = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        let second = registry
            .create_training_run(
                &create_request(snapshot_id),
                &config(),
                now + Duration::seconds(1),
            )
            .unwrap();

        assert!(registry.get_training_run(Uuid::new_v4()).unwrap().is_none());
        let fetched = registry.get_training_run(first.run_id).unwrap().unwrap();
        assert_eq!(fetched.snapshot_id, snapshot_id);
        assert_eq!(fetched.status, TrainingRunStatus::Requested);
        let runs = registry.list_training_runs().unwrap();
        assert_eq!(runs.len(), 2);
        assert_eq!(runs[0].run_id, second.run_id);
        assert_eq!(runs[1].run_id, first.run_id);

        // before start: no lease and a single "requested" event
        let detail = registry
            .get_training_run_detail(first.run_id)
            .unwrap()
            .unwrap();
        assert!(detail.lease.is_none());
        assert_eq!(detail.events.len(), 1);
        assert_eq!(detail.events[0].kind, "requested");
        assert!(
            registry
                .get_training_run_detail(Uuid::new_v4())
                .unwrap()
                .is_none()
        );

        let provider = fake_provider(1.0);
        let started = registry
            .start_training_run_with_thresholds(
                first.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                TrainingReadinessThresholds {
                    decisions: 1,
                    replays: 0,
                },
            )
            .await
            .unwrap();
        assert_eq!(started.status, TrainingRunStatus::WaitingWorker);
        let detail = registry
            .get_training_run_detail(first.run_id)
            .unwrap()
            .unwrap();
        let lease = detail.lease.expect("lease exists after start");
        assert_eq!(lease.provider_instance_id, "pro-test");
        assert_eq!(lease.status, GpuLeaseStatus::WaitingWorker);
        let kinds: Vec<&str> = detail
            .events
            .iter()
            .map(|event| event.kind.as_str())
            .collect();
        assert_eq!(
            kinds,
            [
                "requested",
                "start_confirmed",
                "state_transition",
                "state_transition"
            ]
        );
        let sequences: Vec<i64> = detail.events.iter().map(|event| event.sequence).collect();
        assert!(sequences.windows(2).all(|pair| pair[0] < pair[1]));
    }

    #[test]
    fn create_rejects_revoked_snapshot_unpinned_base_model_and_unapproved_gpu() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();

        let error = registry
            .create_training_run(&create_request(Uuid::new_v4()), &config(), now)
            .unwrap_err();
        assert_eq!(error.to_string(), "dataset snapshot not found");

        let mut unpinned = create_request(snapshot_id);
        unpinned.base_model.model_id = "example/other".into();
        let error = registry
            .create_training_run(&unpinned, &config(), now)
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "base model is not on the pinned deployment allowlist"
        );

        let mut wrong_gpu = create_request(snapshot_id);
        wrong_gpu.gpu_spec = "rtx-a6000".into();
        let error = registry
            .create_training_run(&wrong_gpu, &config(), now)
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "GPU spec is not on the ordered deployment allowlist"
        );

        let mut weak_config = config();
        weak_config.gpu_allowlist = vec![AutoDlGpuSpecConfig {
            id: "tiny".into(),
            display_name: "tiny".into(),
            memory_gb: 16,
            cuda: true,
            data_centers: vec![],
        }];
        let mut weak = create_request(snapshot_id);
        weak.gpu_spec = "tiny".into();
        let error = registry
            .create_training_run(&weak, &weak_config, now)
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "training requires an approved CUDA GPU with at least 24GB"
        );

        // a revoked snapshot can never be trained on again
        registry
            .revoke_dataset_snapshot(
                snapshot_id,
                &cerebellum_core::RevokeDatasetSnapshotRequest {
                    actor: "admin".into(),
                    reason: "bad source".into(),
                },
                now,
            )
            .unwrap();
        let error = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap_err();
        assert_eq!(error.to_string(), "dataset snapshot is revoked");
    }

    #[tokio::test]
    async fn start_gates_reject_budget_mismatch_insufficient_evidence_and_cooldown() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        let provider = fake_provider(1.0);
        let thresholds = TrainingReadinessThresholds {
            decisions: 1,
            replays: 0,
        };

        // the confirmation must restate the immutable budget and GPU spec exactly
        let mut mismatched = confirmation();
        mismatched.confirm_max_total_cny = 999.0;
        let error = registry
            .start_training_run_with_thresholds(
                run.run_id,
                &mismatched,
                &config(),
                &provider,
                now,
                thresholds,
            )
            .await
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "start confirmation does not exactly match the immutable run budget and GPU spec"
        );
        let mut wrong_gpu = confirmation();
        wrong_gpu.confirm_gpu_spec = "other".into();
        assert!(
            registry
                .start_training_run_with_thresholds(
                    run.run_id,
                    &wrong_gpu,
                    &config(),
                    &provider,
                    now,
                    thresholds,
                )
                .await
                .is_err()
        );
        let mut blank = confirmation();
        blank.administrator = " ".into();
        assert!(
            registry
                .start_training_run_with_thresholds(
                    run.run_id,
                    &blank,
                    &config(),
                    &provider,
                    now,
                    thresholds,
                )
                .await
                .is_err()
        );
        assert_eq!(provider.creates.load(Ordering::SeqCst), 0);

        // the production entrypoint enforces the 5,000/1,000 evidence minimums
        let error = registry
            .start_training_run(run.run_id, &confirmation(), &config(), &provider, now)
            .await
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "training requires at least 5000 decisions and 1000 replay evaluations"
        );
        assert_eq!(provider.creates.load(Ordering::SeqCst), 0);
        assert_eq!(
            registry
                .get_training_run(run.run_id)
                .unwrap()
                .unwrap()
                .status,
            TrainingRunStatus::Requested
        );

        // a successful start enforces the weekly cooldown for the next run
        let started = registry
            .start_training_run_with_thresholds(
                run.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                thresholds,
            )
            .await
            .unwrap();
        assert_eq!(started.status, TrainingRunStatus::WaitingWorker);
        let second = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        let error = registry
            .start_training_run_with_thresholds(
                second.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                thresholds,
            )
            .await
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "training may be started at most once per week"
        );

        // a cancelled run can never be started
        let third = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        registry
            .cancel_training_run(third.run_id, &cancel_request(), None, now)
            .await
            .unwrap();
        let error = registry
            .start_training_run_with_thresholds(
                third.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                thresholds,
            )
            .await
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "only requested or waiting-capacity runs can be started"
        );
    }

    #[tokio::test]
    async fn cancel_requires_actor_reason_transitions_once_and_releases_gpu() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();

        let mut blank_admin = cancel_request();
        blank_admin.administrator = " ".into();
        assert!(
            registry
                .cancel_training_run(run.run_id, &blank_admin, None, now)
                .await
                .is_err()
        );
        let mut blank_reason = cancel_request();
        blank_reason.reason = String::new();
        assert!(
            registry
                .cancel_training_run(run.run_id, &blank_reason, None, now)
                .await
                .is_err()
        );
        let error = registry
            .cancel_training_run(Uuid::new_v4(), &cancel_request(), None, now)
            .await
            .unwrap_err();
        assert_eq!(error.to_string(), "training run not found");

        // a requested run cancels without any GPU provider involvement
        let cancelled = registry
            .cancel_training_run(run.run_id, &cancel_request(), None, now)
            .await
            .unwrap();
        assert_eq!(cancelled.status, TrainingRunStatus::Cancelled);
        assert!(cancelled.completed_at.is_some());
        // cancelling a terminal run is a no-op, not a new transition
        let again = registry
            .cancel_training_run(run.run_id, &cancel_request(), None, now)
            .await
            .unwrap();
        assert_eq!(again.status, TrainingRunStatus::Cancelled);
        let detail = registry
            .get_training_run_detail(run.run_id)
            .unwrap()
            .unwrap();
        assert_eq!(
            detail
                .events
                .iter()
                .filter(|event| event.kind == "state_transition")
                .count(),
            1
        );

        // a started run releases its GPU lease when cancelled
        let provider = fake_provider(1.0);
        let running = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        registry
            .start_training_run_with_thresholds(
                running.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                TrainingReadinessThresholds {
                    decisions: 1,
                    replays: 0,
                },
            )
            .await
            .unwrap();
        let cancelled = registry
            .cancel_training_run(running.run_id, &cancel_request(), Some(&provider), now)
            .await
            .unwrap();
        assert_eq!(cancelled.status, TrainingRunStatus::Cancelled);
        assert_eq!(provider.releases.load(Ordering::SeqCst), 1);
        let detail = registry
            .get_training_run_detail(running.run_id)
            .unwrap()
            .unwrap();
        assert_eq!(detail.lease.unwrap().status, GpuLeaseStatus::Released);
        assert!(detail.events.iter().any(|event| event.kind == "released"));
    }

    #[tokio::test]
    async fn worker_failure_marks_run_failed_and_truncates_the_error() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();

        let error = registry
            .fail_training_run_from_worker(
                Uuid::new_v4(),
                &WorkerFailRequest {
                    error: "boom".into(),
                },
                now,
            )
            .unwrap_err();
        assert_eq!(error.to_string(), "training run not found");

        let failed = registry
            .fail_training_run_from_worker(
                run.run_id,
                &WorkerFailRequest {
                    error: "x".repeat(3_000),
                },
                now,
            )
            .unwrap();
        assert_eq!(failed.status, TrainingRunStatus::Failed);
        let message = failed.error.expect("failure records the worker error");
        assert!(message.starts_with("worker failed: "));
        assert_eq!(message.chars().count(), 2_000);

        // Failed -> Failed is an idempotent self-transition
        let refailed = registry
            .fail_training_run_from_worker(
                run.run_id,
                &WorkerFailRequest {
                    error: "again".into(),
                },
                now,
            )
            .unwrap();
        assert_eq!(refailed.status, TrainingRunStatus::Failed);

        // a cancelled run rejects a worker failure transition
        let cancelled = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        registry
            .cancel_training_run(cancelled.run_id, &cancel_request(), None, now)
            .await
            .unwrap();
        let error = registry
            .fail_training_run_from_worker(
                cancelled.run_id,
                &WorkerFailRequest {
                    error: "too late".into(),
                },
                now,
            )
            .unwrap_err();
        assert!(error.to_string().contains("invalid training transition"));
    }

    #[tokio::test]
    async fn reconcile_recovers_provisioning_releases_terminal_and_skips_leaseless_runs() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();
        let provider = ReconcileProvider {
            status: Mutex::new("running".into()),
            releases: AtomicUsize::new(0),
            price: 1.0,
        };

        // a run stuck mid-provisioning after a control-plane restart
        let recovering = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        registry
            .start_training_run_with_thresholds(
                recovering.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                TrainingReadinessThresholds {
                    decisions: 1,
                    replays: 0,
                },
            )
            .await
            .unwrap();
        let mut run = registry
            .get_training_run(recovering.run_id)
            .unwrap()
            .unwrap();
        run.status = TrainingRunStatus::Provisioning;
        {
            let conn = registry.lock_conn();
            conn.execute(
                "UPDATE training_runs SET status='provisioning',run_json=?2 WHERE id=?1",
                params![
                    recovering.run_id.to_string(),
                    serde_json::to_string(&run).unwrap()
                ],
            )
            .unwrap();
        }
        let mut lease = registry.get_gpu_lease(recovering.run_id).unwrap().unwrap();
        lease.hourly_price_cny = 0.0;
        lease.status = GpuLeaseStatus::Provisioning;
        registry.save_gpu_lease(&lease).unwrap();

        // a terminal run whose lease was never released
        let orphan = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        registry
            .cancel_training_run(orphan.run_id, &cancel_request(), None, now)
            .await
            .unwrap();
        registry
            .save_gpu_lease(&GpuLease {
                run_id: orphan.run_id,
                provider: "autodl-app".into(),
                provider_instance_id: "pro-orphan".into(),
                gpu_spec: "v-48g".into(),
                gpu_memory_gb: 48,
                hourly_price_cny: 1.0,
                status: GpuLeaseStatus::WaitingWorker,
                last_provider_status: "running".into(),
                last_heartbeat_at: None,
                release_requested_at: None,
                released_at: None,
                created_at: now,
                updated_at: now,
            })
            .unwrap();

        // a never-started run has no lease and is skipped
        registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();

        let acted = registry
            .reconcile_training_runs(&provider, now)
            .await
            .unwrap();
        assert_eq!(acted, 2);
        assert_eq!(provider.releases.load(Ordering::SeqCst), 1);

        let recovered = registry
            .get_training_run(recovering.run_id)
            .unwrap()
            .unwrap();
        assert_eq!(recovered.status, TrainingRunStatus::WaitingWorker);
        let lease = registry.get_gpu_lease(recovering.run_id).unwrap().unwrap();
        assert_eq!(lease.status, GpuLeaseStatus::WaitingWorker);
        assert!((lease.hourly_price_cny - 1.0).abs() < 1e-9);
        let orphan_lease = registry.get_gpu_lease(orphan.run_id).unwrap().unwrap();
        assert_eq!(orphan_lease.status, GpuLeaseStatus::Released);
    }

    #[tokio::test]
    async fn reconcile_times_out_a_stale_worker_heartbeat_exactly_once() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();
        let provider = ReconcileProvider {
            status: Mutex::new("running".into()),
            releases: AtomicUsize::new(0),
            price: 1.0,
        };
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        registry
            .start_training_run_with_thresholds(
                run.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                TrainingReadinessThresholds {
                    decisions: 1,
                    replays: 0,
                },
            )
            .await
            .unwrap();

        // no heartbeat ever arrives; the watchdog fires past the timeout
        let later = now + Duration::seconds(WORKER_HEARTBEAT_TIMEOUT_SECONDS + 60);
        let acted = registry
            .reconcile_training_runs(&provider, later)
            .await
            .unwrap();
        assert_eq!(acted, 1);
        let timed_out = registry.get_training_run(run.run_id).unwrap().unwrap();
        assert_eq!(timed_out.status, TrainingRunStatus::TimedOut);
        assert!(timed_out.error.unwrap().contains("watchdog"));
        assert_eq!(provider.releases.load(Ordering::SeqCst), 1);

        // the terminal run with a released lease is not acted on again
        let acted = registry
            .reconcile_training_runs(&provider, later + Duration::seconds(60))
            .await
            .unwrap();
        assert_eq!(acted, 0);
        assert_eq!(provider.releases.load(Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn reconcile_fails_the_run_when_the_provider_instance_stops() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let snapshot_id = seed_snapshot(&registry);
        let now = Utc::now();
        let provider = ReconcileProvider {
            status: Mutex::new("stopped".into()),
            releases: AtomicUsize::new(0),
            price: 1.0,
        };
        let run = registry
            .create_training_run(&create_request(snapshot_id), &config(), now)
            .unwrap();
        registry
            .start_training_run_with_thresholds(
                run.run_id,
                &confirmation(),
                &config(),
                &provider,
                now,
                TrainingReadinessThresholds {
                    decisions: 1,
                    replays: 0,
                },
            )
            .await
            .unwrap();

        let acted = registry
            .reconcile_training_runs(&provider, now)
            .await
            .unwrap();
        assert_eq!(acted, 1);
        let failed = registry.get_training_run(run.run_id).unwrap().unwrap();
        assert_eq!(failed.status, TrainingRunStatus::Failed);
        assert!(
            failed
                .error
                .unwrap()
                .contains("provider instance entered terminal status stopped")
        );
        assert_eq!(provider.releases.load(Ordering::SeqCst), 1);
        assert_eq!(
            registry.get_gpu_lease(run.run_id).unwrap().unwrap().status,
            GpuLeaseStatus::Released
        );
    }
}
