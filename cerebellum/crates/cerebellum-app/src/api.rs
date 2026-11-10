use anyhow::Result;
use axum::{
    Json, Router as AxumRouter,
    body::{Body, Bytes},
    extract::{Path, Query, Request, State},
    http::{HeaderMap, HeaderValue, StatusCode, header},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post, put},
};
use base64::Engine;
use cerebellum_core::*;
use chrono::{Duration, Utc};
use futures_util::StreamExt;
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{collections::HashMap, io::SeekFrom, sync::Arc};
use tokio::io::{AsyncReadExt, AsyncSeekExt, AsyncWriteExt};
use tokio::net::TcpListener;
use tokio_util::io::ReaderStream;
use tower_http::trace::TraceLayer;
use uuid::Uuid;

use crate::builtins;
use crate::config::AppConfig;
use crate::gates::evaluate_gate;
use crate::learning::{self, LearningController};
use crate::local_model::OpenAiCompatibleStructuredClient;
use crate::permit::PermitSigner;
use crate::quality::StructuredModelClient;
use crate::router::{DeterministicRouter, OpenAiCompatibleRouter, RouterModel, rank_with_fallback};
use crate::store::Registry;
use crate::training::{
    GpuProvider, WorkerBootstrapRequest, WorkerCompleteRequest, WorkerFailRequest,
    WorkerHeartbeatRequest,
};

pub struct AppState {
    pub registry: Arc<Registry>,
    pub config: AppConfig,
    pub router: Arc<dyn RouterModel>,
    pub signer: PermitSigner,
    pub gpu_provider: Option<Arc<dyn GpuProvider>>,
    pub structured_model: Option<Arc<dyn StructuredModelClient>>,
    pub admin_csrf: String,
}

impl AppState {
    pub fn new(config: AppConfig) -> Result<Arc<Self>> {
        let registry = Arc::new(Registry::open(&config.data_dir)?);
        builtins::seed(&registry)?;
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
        let signer = PermitSigner::new(config.signing_secret.clone())?;
        let gpu_provider = if config.training_provider_local {
            let autodl = config.autodl.as_ref().ok_or_else(|| {
                anyhow::anyhow!("local training provider requires the pinned training config")
            })?;
            if autodl.provider_name != crate::training::LocalGpuProvider::NAME {
                anyhow::bail!(
                    "CEREBELLUM_TRAINING_PROVIDER_NAME must equal the local provider name"
                );
            }
            Some(Arc::new(crate::training::LocalGpuProvider::new(
                &config.data_dir,
                &autodl.worker_gateway_url,
                config.bind,
            )) as Arc<dyn GpuProvider>)
        } else {
            config
                .autodl
                .as_ref()
                .map(crate::training::configured_provider)
                .transpose()?
        };
        registry.set_quality_enforcement(
            config
                .local_model
                .as_ref()
                .is_some_and(|model| model.enforcement_required),
            Utc::now(),
        )?;
        Ok(Arc::new(Self {
            registry,
            config,
            router,
            signer,
            gpu_provider,
            structured_model,
            admin_csrf: format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple()),
        }))
    }
}

pub fn app(state: Arc<AppState>) -> AxumRouter {
    let protected = AxumRouter::new()
        .route("/v1/decisions", post(decide))
        .route("/v1/runs", post(create_run))
        .route("/v1/runs/{id}/events", post(append_event))
        .route("/v1/runs/{id}/trace", get(get_trace))
        .route("/v1/runs/{id}/gates/{*gate_operation}", post(evaluate))
        .route("/v1/runs/{id}/complete", post(complete_run))
        .route("/v1/authorize", post(authorize))
        .route("/v1/permits/verify", post(verify_permit))
        .route("/v1/skills", get(list_skills))
        .route("/v1/workflows", get(list_workflows))
        .route("/v1/experiences", post(create_experience))
        .route(
            "/v1/experiences/{id}/feedback",
            post(add_experience_feedback),
        )
        .route("/v1/context:retrieve", post(retrieve_context))
        .route("/v1/learning/status", get(get_learning_status))
        .route("/v1/curricula", get(list_curricula).post(create_curriculum))
        .route("/v1/training-candidates", get(list_training_candidates))
        .route("/v1/optimization-runs", post(create_optimization_run))
        .route(
            "/v1/optimization-runs/{operation}",
            get(get_optimization_run).post(review_optimization),
        )
        .route(
            "/v1/optimization-runs/{id}/patches",
            get(list_optimization_patches),
        )
        .route(
            "/v1/optimization-runs/{id}/result",
            post(submit_optimization_result),
        )
        .route("/v1/models/{*model_operation}", post(review_model))
        .route("/v1/consolidations", post(import_consolidation))
        .route("/v1/topics", get(list_topics).post(create_topic))
        .route(
            "/v1/source-policies",
            get(list_source_policies).post(create_source_policy),
        )
        .route(
            "/v1/source-policies/{operation}",
            post(tombstone_source_policy),
        )
        .route("/v1/connectors/{operation}", post(sync_connector))
        .route("/v1/acquisition/status", get(get_acquisition_status))
        .route("/v1/acquisition/results", post(submit_acquisition_result))
        .route(
            "/v1/acquisition/results/{job_id}",
            get(get_acquisition_result),
        )
        .route(
            "/v1/acquisition/browser-budget:reserve",
            post(reserve_browser_budget),
        )
        .route(
            "/v1/acquisition/source-rate:reserve",
            post(reserve_source_rate),
        )
        .route("/v1/knowledge:retrieve", post(retrieve_knowledge))
        .route("/v1/knowledge/cards", get(list_knowledge_cards))
        .route("/v1/knowledge/cards/{id}", get(get_knowledge_card))
        .route("/v1/documents", get(list_documents))
        .route("/v1/events", get(list_events))
        .route("/v1/events/{id}", get(get_event))
        .route(
            "/v1/knowledge/cards/{id}/history",
            get(get_knowledge_card_history),
        )
        .route("/v1/learning/jobs", get(list_learning_jobs))
        .route("/v1/learning/jobs:claim", post(claim_learning_job))
        .route(
            "/v1/learning/jobs/{*job_operation}",
            post(finish_learning_job),
        )
        .route("/v1/meta/status", get(get_meta_status))
        .route("/v1/meta/decisions", post(record_meta_decision))
        .route("/v1/meta/replays", post(record_meta_replay))
        .route(
            "/v1/meta/training-candidates",
            get(list_meta_training_candidates),
        )
        .route("/v1/meta/training:enqueue", post(enqueue_meta_training))
        .route("/v1/datasets/{kind}/draft", get(get_dataset_draft))
        .route("/v1/datasets/{operation}", post(build_dataset_draft))
        .route(
            "/v1/dataset-builds/{id}/quality-report",
            get(get_dataset_quality_report),
        )
        .route(
            "/v1/dataset-builds/{operation}",
            post(reaudit_dataset_quality),
        )
        .route("/v1/quality/status", get(get_quality_status))
        .route("/v1/quality/assessments", get(list_quality_assessments))
        .route(
            "/v1/quality/model-versions",
            get(list_quality_model_versions),
        )
        .route(
            "/v1/quality/model-versions/{operation}",
            post(review_quality_model_version),
        )
        .route("/v1/quality:backfill", post(backfill_quality))
        .route("/v1/synthetic-candidates", get(list_synthetic_candidates))
        .route(
            "/v1/synthetic-candidates/{operation}",
            post(review_synthetic_candidate),
        )
        .route("/v1/expert-taxonomy", get(get_expert_taxonomy))
        .route("/v1/experts:route", post(route_expert_request))
        .route("/v1/expert-adapters", get(list_expert_adapters))
        .route(
            "/v1/expert-adapters/{operation}",
            get(get_expert_adapter).post(operate_expert_adapter),
        )
        .route(
            "/v1/expert-adapter-eval-reports",
            get(list_expert_adapter_eval_reports),
        )
        .route("/v1/expert-dataset-views", get(list_expert_dataset_views))
        .route(
            "/v1/expert-dataset-views/{id}",
            get(get_expert_dataset_view),
        )
        .route(
            "/v1/expert-dataset-views/{id}/assignments",
            get(list_expert_assignments),
        )
        .route(
            "/v1/dataset-snapshots",
            get(list_dataset_snapshots).post(create_dataset_snapshot),
        )
        .route(
            "/v1/dataset-snapshots/{operation}",
            get(get_dataset_snapshot).post(revoke_dataset_snapshot),
        )
        .route(
            "/v1/training-runs",
            get(list_training_runs).post(create_training_run_v31),
        )
        .route("/v1/training-config", get(get_training_config))
        .route(
            "/v1/training-runs/{operation}",
            get(get_training_run).post(operate_training_run),
        )
        .route(
            "/v1/meta-training/results",
            post(submit_meta_training_result),
        )
        .route(
            "/v1/meta-training/results/{job_id}",
            get(get_meta_training_result),
        )
        .route(
            "/v1/meta-models",
            get(list_meta_models).post(register_meta_model),
        )
        .route("/v1/meta-models/{operation}", post(operate_meta_model))
        .route(
            "/v1/meta/canary-decisions",
            post(record_meta_canary_decision),
        )
        .route("/v1/objects/{hash}", get(get_object))
        .route("/admin", get(admin_index))
        .route("/admin/app.js", get(admin_javascript))
        .route("/admin/style.css", get(admin_stylesheet))
        .layer(middleware::from_fn_with_state(state.clone(), require_auth));

    let worker = AxumRouter::new()
        .route(
            "/v1/training-worker/bootstrap",
            post(exchange_training_worker_bootstrap),
        )
        .route(
            "/v1/training-worker/runs/{id}/bundle",
            get(download_training_bundle),
        )
        .route(
            "/v1/training-worker/runs/{id}/heartbeat",
            post(training_worker_heartbeat),
        )
        .route(
            "/v1/training-worker/runs/{id}/artifacts/{kind}",
            put(upload_training_artifact),
        )
        .route(
            "/v1/training-worker/runs/{id}/complete",
            post(complete_training_worker_run),
        )
        .route(
            "/v1/training-worker/runs/{id}/fail",
            post(fail_training_worker_run),
        );

    AxumRouter::new()
        .route("/health", get(health))
        .route("/v1/github/webhooks", post(github_webhook))
        .route(
            "/v1/websub/{policy_id}",
            get(websub_verify).post(websub_notify),
        )
        .merge(worker)
        .merge(protected)
        .layer(TraceLayer::new_for_http())
        .with_state(state)
}

pub async fn serve(state: Arc<AppState>) -> Result<()> {
    if let Some(provider) = state.gpu_provider.clone() {
        tokio::spawn(crate::training::run_reconciler(
            state.registry.clone(),
            provider,
        ));
    }
    if state.config.learning_scheduler_enabled {
        let registry = state.registry.clone();
        let github_token = state.config.github_token.clone();
        let mediacrawler_search = state.config.mediacrawler_search;
        tokio::spawn(crate::scheduler::run_loop(
            registry,
            github_token,
            state.structured_model.clone(),
            mediacrawler_search,
        ));
    }
    let listener = TcpListener::bind(state.config.bind).await?;
    tracing::info!(address=%state.config.bind, data_dir=%state.config.data_dir.display(), "cerebellumd listening");
    axum::serve(listener, app(state)).await?;
    Ok(())
}

async fn require_auth(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    request: Request<Body>,
    next: Next,
) -> Response {
    let supplied = headers
        .get("authorization")
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.strip_prefix("Bearer "));
    let authorized = supplied.is_some_and(|token| {
        // Hash both sides, then fold byte differences in constant time: a
        // bearer mismatch must not leak prefix length via comparison timing.
        let supplied = Sha256::digest(token.as_bytes());
        let expected = Sha256::digest(state.config.auth_token.as_bytes());
        supplied
            .iter()
            .zip(expected.iter())
            .fold(0u8, |acc, (left, right)| acc | (left ^ right))
            == 0
    });
    if !authorized {
        return (
            StatusCode::UNAUTHORIZED,
            Json(json!({"error":"unauthorized"})),
        )
            .into_response();
    }
    if let Some(origin) = headers
        .get(header::ORIGIN)
        .and_then(|value| value.to_str().ok())
    {
        if origin.trim_end_matches('/') != state.config.admin_origin {
            return (
                StatusCode::FORBIDDEN,
                Json(json!({"error":"cross-origin admin request rejected"})),
            )
                .into_response();
        }
        if !matches!(*request.method(), http::Method::GET | http::Method::HEAD)
            && headers
                .get("x-cerebellum-csrf")
                .and_then(|value| value.to_str().ok())
                != Some(state.admin_csrf.as_str())
        {
            return (
                StatusCode::FORBIDDEN,
                Json(json!({"error":"invalid admin CSRF token"})),
            )
                .into_response();
        }
    }
    next.run(request).await
}

async fn health() -> Json<Value> {
    // Public liveness probe: no registry snapshot (it made every probe a
    // full table scan); status and version only.
    Json(json!({"status":"ok","version":env!("CARGO_PKG_VERSION")}))
}

async fn github_webhook(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let secret = state
        .config
        .github_webhook_secret
        .as_deref()
        .ok_or_else(|| AppError::forbidden("GitHub webhook ingestion is disabled"))?;
    let signature = headers
        .get("x-hub-signature-256")
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.strip_prefix("sha256="))
        .and_then(decode_hex)
        .ok_or_else(|| AppError::forbidden("invalid GitHub webhook signature"))?;
    let mut mac = Hmac::<Sha256>::new_from_slice(secret)
        .map_err(|_| AppError::forbidden("invalid webhook configuration"))?;
    mac.update(&body);
    mac.verify_slice(&signature)
        .map_err(|_| AppError::forbidden("invalid GitHub webhook signature"))?;
    let event = headers
        .get("x-github-event")
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default();
    if event != "push" {
        return Ok((StatusCode::ACCEPTED, Json(json!({"ignored":event}))));
    }
    let payload: Value =
        serde_json::from_slice(&body).map_err(|error| AppError::bad_request(error.to_string()))?;
    let repository_url = payload
        .pointer("/repository/html_url")
        .and_then(Value::as_str)
        .ok_or_else(|| AppError::bad_request("webhook lacks repository.html_url"))?;
    let full_name = payload
        .pointer("/repository/full_name")
        .and_then(Value::as_str)
        .unwrap_or_default();
    if state.config.github_watchlist.is_empty()
        || !state.config.github_watchlist.iter().any(|item| {
            item.eq_ignore_ascii_case(full_name) || item.eq_ignore_ascii_case(repository_url)
        })
    {
        return Err(AppError::forbidden(
            "repository is not on the GitHub watchlist",
        ));
    }
    let commit_sha = payload
        .get("after")
        .and_then(Value::as_str)
        .ok_or_else(|| AppError::bad_request("webhook lacks after commit"))?;
    if commit_sha.chars().all(|character| character == '0') {
        return Ok((StatusCode::ACCEPTED, Json(json!({"ignored":"deleted_ref"}))));
    }
    if commit_sha.len() != 40
        || !commit_sha
            .chars()
            .all(|character| character.is_ascii_hexdigit())
    {
        return Err(AppError::bad_request(
            "webhook commit must be a full 40-character SHA",
        ));
    }
    let reg = Arc::clone(&state.registry);
    let job_payload =
        json!({"repository_url":repository_url,"commit_sha":commit_sha,"max_files":100});
    let job = blocking(move || {
        reg.enqueue_learning_job("github_collect_commit_v1", job_payload, 0.75, 3)
    })
    .await?;
    Ok((
        StatusCode::ACCEPTED,
        Json(json!({"scheduled":true,"job_id":job.job_id,"commit_sha":commit_sha})),
    ))
}

async fn websub_verify(
    State(state): State<Arc<AppState>>,
    Path(policy_id): Path<Uuid>,
    Query(query): Query<HashMap<String, String>>,
) -> Result<Response, AppError> {
    if state.config.websub_secret.is_none() {
        return Err(AppError::forbidden("WebSub ingestion is disabled"));
    }
    let reg = Arc::clone(&state.registry);
    let policy = blocking(move || reg.get_source_policy(policy_id))
        .await?
        .ok_or_else(|| AppError::not_found("source policy not found"))?;
    if !policy.enabled || policy.kind != SourceKind::RssAtom {
        return Err(AppError::forbidden(
            "WebSub requires an enabled RSS/Atom source policy",
        ));
    }
    let mode = query
        .get("hub.mode")
        .map(String::as_str)
        .unwrap_or_default();
    let topic = query
        .get("hub.topic")
        .map(String::as_str)
        .unwrap_or_default();
    let challenge = query
        .get("hub.challenge")
        .map(String::as_str)
        .unwrap_or_default();
    if !matches!(mode, "subscribe" | "unsubscribe")
        || topic != policy.base_url
        || challenge.is_empty()
        || challenge.len() > 4_096
    {
        return Err(AppError::bad_request(
            "invalid WebSub verification challenge",
        ));
    }
    Ok((StatusCode::OK, challenge.to_owned()).into_response())
}

async fn websub_notify(
    State(state): State<Arc<AppState>>,
    Path(policy_id): Path<Uuid>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<(StatusCode, Json<Value>), AppError> {
    if body.len() > 1024 * 1024 {
        return Err(AppError::bad_request("WebSub notification exceeds one MiB"));
    }
    let secret = state
        .config
        .websub_secret
        .as_deref()
        .ok_or_else(|| AppError::forbidden("WebSub ingestion is disabled"))?;
    let signature = headers
        .get("x-hub-signature-256")
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.strip_prefix("sha256="))
        .and_then(decode_hex)
        .ok_or_else(|| AppError::forbidden("invalid WebSub signature"))?;
    let mut mac = Hmac::<Sha256>::new_from_slice(secret)
        .map_err(|_| AppError::forbidden("invalid WebSub configuration"))?;
    mac.update(&body);
    mac.verify_slice(&signature)
        .map_err(|_| AppError::forbidden("invalid WebSub signature"))?;
    let reg = Arc::clone(&state.registry);
    let policy = blocking(move || reg.get_source_policy(policy_id))
        .await?
        .ok_or_else(|| AppError::not_found("source policy not found"))?;
    if !policy.enabled || policy.kind != SourceKind::RssAtom {
        return Err(AppError::forbidden(
            "WebSub requires an enabled RSS/Atom source policy",
        ));
    }
    let reg = Arc::clone(&state.registry);
    let (plans, jobs) = blocking(move || enqueue_connector_sync(&reg, &policy, Utc::now())).await?;
    Ok((
        StatusCode::ACCEPTED,
        Json(json!({
            "source_policy_id":policy_id,
            "verified":true,
            "plans":plans,
            "job_ids":jobs
        })),
    ))
}

fn decode_hex(value: &str) -> Option<Vec<u8>> {
    let (pairs, remainder) = value.as_bytes().as_chunks::<2>();
    if !remainder.is_empty() {
        return None;
    }
    pairs
        .iter()
        .map(|pair| {
            let text = std::str::from_utf8(pair).ok()?;
            u8::from_str_radix(text, 16).ok()
        })
        .collect()
}

async fn decide(
    State(state): State<Arc<AppState>>,
    Json(request): Json<DecisionRequest>,
) -> Result<Json<DecisionResponse>, AppError> {
    if request.task.trim().is_empty() {
        return Err(AppError::bad_request("task must not be empty"));
    }
    let reg = Arc::clone(&state.registry);
    let workflows = blocking(move || reg.list_workflows()).await?;
    let mut output = rank_with_fallback(state.router.as_ref(), &request, &workflows).await?;
    let selected = output.ranked.remove(0);
    let context_request = ContextRetrieveRequest {
        query: request.task.clone(),
        repository_id: None,
        task_family: None,
        // 100, not 5: the kind filter below runs after retrieval, and
        // retrieve_context truncates to this limit first — a smaller limit
        // would starve the take(5) of matching kinds.
        limit: 100,
    };
    let reg = Arc::clone(&state.registry);
    let memory_context = blocking(move || learning::retrieve_context(&reg, &context_request))
        .await?
        .items
        .into_iter()
        .filter(|item| {
            matches!(
                item.kind,
                MemoryKind::Episodic | MemoryKind::Failure | MemoryKind::AntiSkill
            )
        })
        .take(5)
        .collect();
    let knowledge_request = KnowledgeRetrieveRequest {
        query: request.task.clone(),
        topic_ids: vec![],
        statuses: vec![
            KnowledgeStatus::Unverified,
            KnowledgeStatus::Corroborated,
            KnowledgeStatus::Contested,
        ],
        since: None,
        as_of: None,
        freshness_hours: None,
        limit: 5,
    };
    let reg = Arc::clone(&state.registry);
    let mut knowledge_context = blocking(move || reg.retrieve_knowledge(&knowledge_request))
        .await?
        .items;
    let reg = Arc::clone(&state.registry);
    let registry_snapshot = blocking(move || reg.registry_snapshot()).await?;
    // M5: authoritative server-stamped environment; user context can never set it.
    let environment = EnvironmentStamp {
        now: Utc::now(),
        timezone: "Asia/Shanghai".into(),
        registry_snapshot: registry_snapshot.clone(),
    };
    let mut acquisition_requested = false;
    if state.config.metacognition_enabled
        && let (Some(model), Ok(Some(_adapter))) = (
            state.structured_model.clone(),
            blocking({
                let reg = Arc::clone(&state.registry);
                move || crate::metacognition::active_adapter(&reg)
            })
            .await,
        )
    {
        let query = request.task.clone();
        let retrieval_snapshot = knowledge_context.clone();
        if let Ok(decision) =
            crate::metacognition::assess(model.as_ref(), &query, &environment, &retrieval_snapshot)
                .await
        {
            match decision.action {
                MetacognitionAction::SearchInternal => {
                    if let Some(search_query) = decision.query {
                        let refined = KnowledgeRetrieveRequest {
                            query: search_query,
                            topic_ids: vec![],
                            statuses: vec![
                                KnowledgeStatus::Unverified,
                                KnowledgeStatus::Corroborated,
                                KnowledgeStatus::Contested,
                            ],
                            since: None,
                            as_of: None,
                            // clamps: limit <= 10; freshness already contract-bounded
                            freshness_hours: decision.freshness_hours,
                            limit: 10,
                        };
                        let reg = Arc::clone(&state.registry);
                        if let Ok(items) = blocking(move || reg.retrieve_knowledge(&refined))
                            .await
                            .map(|response| response.items)
                        {
                            knowledge_context = items;
                        }
                    }
                }
                MetacognitionAction::RequestAcquisition => {
                    let needle = decision.query.clone().unwrap_or_default();
                    let reg = Arc::clone(&state.registry);
                    let covered = blocking(move || -> Result<Option<SourcePolicy>> {
                        for topic in reg.list_topic_watches(true)? {
                            let haystack = topic.query.to_lowercase();
                            let needle = needle.to_lowercase();
                            if !needle.is_empty()
                                && (haystack.contains(&needle) || needle.contains(&haystack))
                            {
                                for policy_id in &topic.source_policy_ids {
                                    if let Some(policy) = reg.get_source_policy(*policy_id)?
                                        && policy.enabled
                                    {
                                        return Ok(Some(policy));
                                    }
                                }
                            }
                        }
                        Ok(None)
                    })
                    .await;
                    // Budgets (20/50/500 daily caps) are enforced downstream by
                    // the acquisition path itself when the enqueued sync runs.
                    if let Ok(Some(policy)) = covered {
                        let reg = Arc::clone(&state.registry);
                        if blocking(move || enqueue_connector_sync(&reg, &policy, Utc::now()))
                            .await
                            .is_ok()
                        {
                            acquisition_requested = true;
                        }
                    }
                }
                MetacognitionAction::Answer | MetacognitionAction::Insufficient => {}
            }
        }
        // Any hook failure or invalid model output keeps the exact current
        // behavior: fail-closed, deterministic Rust retains authority.
    }
    let response = DecisionResponse {
        decision_id: Uuid::new_v4(),
        selected,
        alternatives: output.ranked.into_iter().take(3).collect(),
        router: output.router,
        fallback_used: output.fallback_used,
        registry_snapshot,
        memory_context,
        knowledge_context,
        environment: Some(environment),
        acquisition_requested,
    };
    let reg = Arc::clone(&state.registry);
    let save_response = response.clone();
    blocking(move || reg.save_decision(&request, &save_response)).await?;
    Ok(Json(response))
}

async fn create_run(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateRunRequest>,
) -> Result<(StatusCode, Json<RunRecord>), AppError> {
    let reg = Arc::clone(&state.registry);
    let decision = blocking(move || reg.get_decision(request.decision_id))
        .await?
        .ok_or_else(|| AppError::not_found("decision not found"))?;
    if decision.selected.workflow_id != request.workflow_id
        || decision.selected.version != request.workflow_version
    {
        return Err(AppError::bad_request(
            "run workflow does not match the recorded decision",
        ));
    }
    let reg = Arc::clone(&state.registry);
    let run = blocking(move || reg.create_run(&request)).await?;
    Ok((StatusCode::CREATED, Json(run)))
}

async fn append_event(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(event): Json<AppendEventRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    if event.kind.trim().is_empty() {
        return Err(AppError::bad_request("event kind must not be empty"));
    }
    let reg = Arc::clone(&state.registry);
    let sequence = blocking(move || reg.append_event(id, &event)).await?;
    Ok((StatusCode::CREATED, Json(json!({"sequence":sequence}))))
}

#[derive(Debug, Deserialize)]
struct TraceQuery {
    limit: Option<usize>,
    after: Option<i64>,
}

async fn get_trace(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TraceQuery>,
) -> Result<Json<RunTrace>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.get_trace(id, query.limit, query.after))
            .await?
            .ok_or_else(|| AppError::not_found("run not found"))?,
    ))
}

async fn evaluate(
    State(state): State<Arc<AppState>>,
    Path((id, gate_operation)): Path<(Uuid, String)>,
    Json(request): Json<GateEvidenceRequest>,
) -> Result<Json<GateDecision>, AppError> {
    let gate_id = gate_operation
        .strip_suffix(":evaluate")
        .filter(|value| !value.is_empty() && !value.contains('/'))
        .ok_or_else(|| AppError::bad_request("gate operation must end with :evaluate"))?;
    let reg = Arc::clone(&state.registry);
    let run = blocking(move || reg.get_run(id))
        .await?
        .ok_or_else(|| AppError::not_found("run not found"))?;
    if run.status != "running" {
        return Err(AppError::conflict("run is not active"));
    }
    let workflow_id = run.workflow_id.clone();
    let workflow_version = run.workflow_version.clone();
    let reg = Arc::clone(&state.registry);
    let workflow = blocking(move || reg.get_workflow(&workflow_id, &workflow_version))
        .await?
        .ok_or_else(|| AppError::not_found("workflow not found"))?;
    let gate = workflow
        .gates
        .iter()
        .find(|gate| gate.id == gate_id)
        .ok_or_else(|| AppError::not_found("gate not found"))?;
    let decision = evaluate_gate(&run, gate, &request.evidence).await;
    let evidence = request.evidence;
    let saved_decision = decision.clone();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.save_gate_decision(&saved_decision, &evidence)).await?;
    Ok(Json(decision))
}

async fn authorize(
    State(state): State<Arc<AppState>>,
    Json(request): Json<AuthorizeRequest>,
) -> Result<Json<AuthorizeResponse>, AppError> {
    let reg = Arc::clone(&state.registry);
    let run = blocking(move || reg.get_run(request.run_id))
        .await?
        .ok_or_else(|| AppError::not_found("run not found"))?;
    if run.status != "running" {
        return Err(AppError::conflict("run is not active"));
    }
    let workflow_id = run.workflow_id.clone();
    let workflow_version = run.workflow_version.clone();
    let reg = Arc::clone(&state.registry);
    let workflow = blocking(move || reg.get_workflow(&workflow_id, &workflow_version))
        .await?
        .ok_or_else(|| AppError::not_found("workflow not found"))?;
    let gate_run = run.clone();
    let reg = Arc::clone(&state.registry);
    let missing = blocking(move || reg.mandatory_gates_passed(&gate_run, &workflow)).await?;
    if !missing.is_empty() {
        return Err(AppError::forbidden(format!(
            "mandatory gates have not passed: {}",
            missing.join(", ")
        )));
    }
    let ttl = request.ttl_seconds.clamp(1, 300) as i64;
    let now = Utc::now();
    let permit = ActionPermit {
        permit_id: Uuid::new_v4(),
        run_id: run.id,
        workflow_id: run.workflow_id,
        workflow_version: run.workflow_version,
        action_hash: canonical_json_hash(&request.action),
        issued_at: now,
        expires_at: now + Duration::seconds(ttl),
    };
    let token = state.signer.sign(&permit)?;
    let stored_permit = permit.clone();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.save_permit(&stored_permit)).await?;
    Ok(Json(AuthorizeResponse { permit, token }))
}

async fn verify_permit(
    State(state): State<Arc<AppState>>,
    Json(request): Json<VerifyPermitRequest>,
) -> Result<Json<Value>, AppError> {
    let permit = state
        .signer
        .verify(&request.token, &request.action)
        .map_err(|error| AppError::forbidden(error.to_string()))?;
    let stored_permit = permit.clone();
    let consume = request.consume;
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.verify_stored_permit(&stored_permit, consume))
        .await
        .map_err(|error| AppError::forbidden(error.to_string()))?;
    Ok(Json(
        json!({"valid":true,"permit":permit,"consumed":request.consume}),
    ))
}

async fn complete_run(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(request): Json<CompleteRunRequest>,
) -> Result<Json<Value>, AppError> {
    if request.outcome == "success" {
        let reg = Arc::clone(&state.registry);
        let run = blocking(move || reg.get_run(id))
            .await?
            .ok_or_else(|| AppError::not_found("run not found"))?;
        let workflow_id = run.workflow_id.clone();
        let workflow_version = run.workflow_version.clone();
        let reg = Arc::clone(&state.registry);
        let workflow = blocking(move || reg.get_workflow(&workflow_id, &workflow_version))
            .await?
            .ok_or_else(|| AppError::not_found("workflow not found"))?;
        let gate_workflow = workflow.clone();
        let reg = Arc::clone(&state.registry);
        let missing = blocking(move || reg.mandatory_gates_passed(&run, &gate_workflow)).await?;
        if !missing.is_empty() {
            return Err(AppError::forbidden(format!(
                "cannot complete successful run; gates missing: {}",
                missing.join(", ")
            )));
        }
        let reg = Arc::clone(&state.registry);
        let missing_nodes = blocking(move || reg.required_nodes_missing(id, &workflow)).await?;
        if !missing_nodes.is_empty() {
            return Err(AppError::forbidden(format!(
                "cannot complete successful run; required nodes missing: {}",
                missing_nodes.join(", ")
            )));
        }
    }
    let reg = Arc::clone(&state.registry);
    let complete_request = request.clone();
    blocking(move || reg.complete_run(id, &complete_request)).await?;
    let mut experience_ingested = false;
    if let Some(provenance) = &request.experience {
        let reg = Arc::clone(&state.registry);
        let run = blocking(move || reg.get_run(id))
            .await?
            .ok_or_else(|| AppError::not_found("run not found"))?;
        let envelope = ExperienceEnvelope {
            schema_version: SCHEMA_VERSION.into(),
            experience_id: id,
            task: provenance.task.clone(),
            task_family: provenance.task_family.clone(),
            repository: provenance.repository.clone(),
            trajectory: provenance.trajectory.clone(),
            agent_id: provenance.agent_id.clone(),
            model_id: provenance.model_id.clone(),
            workflow: Some(ArtifactVersionRef {
                id: run.workflow_id.clone(),
                version: run.workflow_version.clone(),
            }),
            source: provenance.source.clone(),
            cost: provenance.cost.clone(),
            outcome: ExperienceOutcome {
                success: request.outcome == "success",
                summary: request.summary.clone(),
                failure_class: None,
                metrics: request.metrics.clone(),
            },
            redaction_passed: false,
            data_classification: provenance.data_classification,
            external_processing: provenance.external_processing,
            created_at: Utc::now(),
        };
        // Both outcomes carry learning signal. The run is already complete;
        // an ingest failure must say so and point at the replay path instead
        // of pretending the completion failed.
        let reg = Arc::clone(&state.registry);
        blocking(move || LearningController::ingest(&reg, &envelope))
            .await
            .map_err(|error| {
                AppError::internal(format!(
                    "run completed; experience ingest failed (retry the same envelope via POST /v1/experiences): {error}"
                ))
            })?;
        experience_ingested = true;
    }
    Ok(Json(
        json!({"id":id,"status":"completed","outcome":request.outcome,"experience_ingested":experience_ingested}),
    ))
}

#[derive(Debug, Deserialize)]
struct SkillQuery {
    q: Option<String>,
    include_quarantined: Option<bool>,
    limit: Option<usize>,
}
async fn list_skills(
    State(state): State<Arc<AppState>>,
    Query(query): Query<SkillQuery>,
) -> Result<Json<Vec<SkillManifest>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || {
            reg.search_skills(
                query.q.as_deref(),
                query.include_quarantined.unwrap_or(false),
                query.limit.unwrap_or(100).min(1000),
            )
        })
        .await?,
    ))
}
async fn list_workflows(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<WorkflowManifest>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(blocking(move || reg.list_workflows()).await?))
}

async fn create_experience(
    State(state): State<Arc<AppState>>,
    Json(experience): Json<ExperienceEnvelope>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let ingest_envelope = experience.clone();
    let reg = Arc::clone(&state.registry);
    let (inserted, decision) = blocking(move || LearningController::ingest(&reg, &ingest_envelope))
        .await
        .map_err(map_store_err)?;
    Ok((
        if inserted {
            StatusCode::CREATED
        } else {
            StatusCode::OK
        },
        Json(json!({"inserted":inserted,"experience":experience,"decision":decision})),
    ))
}

async fn add_experience_feedback(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(feedback): Json<FeedbackSignal>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    if feedback.experience_id != id {
        return Err(AppError::bad_request(
            "feedback experience_id does not match URL",
        ));
    }
    let feedback_signal = feedback.clone();
    let reg = Arc::clone(&state.registry);
    let (inserted, decision) =
        blocking(move || LearningController::add_feedback(&reg, &feedback_signal))
            .await
            .map_err(map_store_err)?;
    Ok((
        if inserted {
            StatusCode::CREATED
        } else {
            StatusCode::OK
        },
        Json(json!({"inserted":inserted,"feedback":feedback,"decision":decision})),
    ))
}

async fn retrieve_context(
    State(state): State<Arc<AppState>>,
    Json(request): Json<ContextRetrieveRequest>,
) -> Result<Json<ContextRetrieveResponse>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || learning::retrieve_context(&reg, &request))
            .await
            .map_err(map_store_err)?,
    ))
}

async fn get_learning_status(
    State(state): State<Arc<AppState>>,
) -> Result<Json<LearningStatus>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || learning::learning_status(&reg)).await?,
    ))
}

async fn list_curricula(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<CurriculumPlan>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(blocking(move || reg.list_curricula()).await?))
}

async fn create_curriculum(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateCurriculumRequest>,
) -> Result<(StatusCode, Json<CurriculumPlan>), AppError> {
    let reg = Arc::clone(&state.registry);
    let plan = blocking(move || learning::create_curriculum(&reg, &request))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(plan)))
}

async fn list_training_candidates(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<TrainingCandidate>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_training_candidates()).await?,
    ))
}

async fn review_model(
    State(state): State<Arc<AppState>>,
    Path(model_operation): Path<String>,
    Json(review): Json<ModelReviewRequest>,
) -> Result<Json<ModelVersion>, AppError> {
    let (subject, action) = ["approve", "reject", "rollback"]
        .into_iter()
        .find_map(|action| {
            model_operation
                .strip_suffix(&format!(":{action}"))
                .map(|subject| (subject, action))
        })
        .ok_or_else(|| AppError::bad_request("unknown model review action"))?;
    let (model_id, version) = subject
        .rsplit_once('@')
        .filter(|(id, version)| !id.is_empty() && !version.is_empty())
        .ok_or_else(|| AppError::bad_request("model id must be MODEL@VERSION"))?;
    let model_id = model_id.to_owned();
    let version = version.to_owned();
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.review_model(&model_id, &version, action, &review))
            .await
            .map_err(map_store_err)?,
    ))
}

async fn import_consolidation(
    State(state): State<Arc<AppState>>,
    Json(response): Json<ConsolidationResponse>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let reg = Arc::clone(&state.registry);
    let imported = blocking(move || learning::import_consolidation(&reg, &response))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(json!({"imported":imported}))))
}

#[derive(Debug, Deserialize)]
struct ClaimJobRequest {
    worker: String,
    #[serde(default = "default_lease_seconds")]
    lease_seconds: i64,
    #[serde(default)]
    kinds: Vec<String>,
}

fn default_lease_seconds() -> i64 {
    300
}

async fn claim_learning_job(
    State(state): State<Arc<AppState>>,
    Json(request): Json<ClaimJobRequest>,
) -> Result<Json<Option<LearningJob>>, AppError> {
    let kinds = request.kinds.clone();
    let worker = request.worker.clone();
    let lease_seconds = request.lease_seconds;
    let reg = Arc::clone(&state.registry);
    let job = blocking(move || {
        let kinds: Vec<&str> = kinds.iter().map(String::as_str).collect();
        reg.claim_learning_job(
            (!kinds.is_empty()).then_some(kinds.as_slice()),
            &worker,
            lease_seconds,
        )
    })
    .await
    .map_err(map_store_err)?;
    if let Some(job) = &job
        && job.kind == "skillopt_optimize_v1"
    {
        let reg = Arc::clone(&state.registry);
        let job_id = job.job_id;
        let worker = request.worker.clone();
        blocking(move || reg.mark_optimization_running(job_id, &worker))
            .await
            .map_err(map_store_err)?;
    }
    Ok(Json(job))
}

async fn create_optimization_run(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateOptimizationRunRequest>,
) -> Result<(StatusCode, Json<SkillOptimizationRun>), AppError> {
    let reg = Arc::clone(&state.registry);
    let run = blocking(move || reg.create_optimization_run(&request))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(run)))
}

async fn get_optimization_run(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<SkillOptimizationRun>, AppError> {
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_optimization_run(id))
        .await
        .map_err(map_store_err)?
        .map(Json)
        .ok_or_else(|| AppError::not_found("optimization run not found"))
}

async fn list_optimization_patches(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<Vec<SkillEditPatch>>, AppError> {
    let reg = Arc::clone(&state.registry);
    if blocking(move || reg.get_optimization_run(id))
        .await
        .map_err(map_store_err)?
        .is_none()
    {
        return Err(AppError::not_found("optimization run not found"));
    }
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_optimization_patches(id))
            .await
            .map_err(map_store_err)?,
    ))
}

async fn submit_optimization_result(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(result): Json<SkillOptimizationResult>,
) -> Result<Json<SkillOptimizationRun>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.submit_optimization_result(id, &result))
            .await
            .map_err(map_store_err)?,
    ))
}

async fn review_optimization(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(review): Json<OptimizationReviewRequest>,
) -> Result<Json<Value>, AppError> {
    let (id, action) = ["approve", "reject"]
        .into_iter()
        .find_map(|action| {
            operation
                .strip_suffix(&format!(":{action}"))
                .and_then(|id| Uuid::parse_str(id).ok())
                .map(|id| (id, action))
        })
        .ok_or_else(|| AppError::bad_request("invalid optimization review operation"))?;
    let reg = Arc::clone(&state.registry);
    let (run, skill) = blocking(move || reg.review_optimization(id, action, &review))
        .await
        .map_err(map_store_err)?;
    Ok(Json(json!({"run":run,"skill_version":skill})))
}

async fn get_object(
    State(state): State<Arc<AppState>>,
    Path(hash): Path<String>,
) -> Result<Response, AppError> {
    let reg = Arc::clone(&state.registry);
    let bytes = blocking(move || reg.get_object(&hash))
        .await
        .map_err(|_| AppError::not_found("object not found or failed integrity verification"))?;
    Ok(([("content-type", "application/octet-stream")], bytes).into_response())
}

#[derive(Debug, Deserialize)]
struct FinishJobRequest {
    worker: String,
    #[serde(default)]
    error: Option<String>,
    #[serde(default)]
    retry_after_seconds: u64,
    #[serde(default)]
    acquisition_attempt: Option<AcquisitionAttempt>,
}

async fn finish_learning_job(
    State(state): State<Arc<AppState>>,
    Path(job_operation): Path<String>,
    Json(request): Json<FinishJobRequest>,
) -> Result<Json<Value>, AppError> {
    let (id, action) = ["complete", "fail"]
        .into_iter()
        .find_map(|action| {
            job_operation
                .strip_suffix(&format!(":{action}"))
                .and_then(|id| Uuid::parse_str(id).ok())
                .map(|id| (id, action))
        })
        .ok_or_else(|| AppError::bad_request("invalid learning job operation"))?;
    match action {
        "complete" => {
            let reg = Arc::clone(&state.registry);
            let worker = request.worker.clone();
            blocking(move || reg.complete_learning_job_validated(id, &worker)).await
        }
        "fail" => {
            let reg = Arc::clone(&state.registry);
            blocking(move || {
                request
                    .acquisition_attempt
                    .as_ref()
                    .map_or(Ok(()), |attempt| {
                        reg.save_leased_acquisition_attempt(id, &request.worker, attempt)
                    })
                    .and_then(|_| {
                        reg.fail_learning_job_with_delay(
                            id,
                            &request.worker,
                            request
                                .error
                                .as_deref()
                                .unwrap_or("worker failed without details"),
                            request.retry_after_seconds.min(86_400),
                        )
                    })
                    .and_then(|_| reg.sync_optimization_job_failure(id))
            })
            .await
        }
        _ => unreachable!(),
    }
    .map_err(map_store_err)?;
    Ok(Json(json!({
        "job_id":id,
        "status":if action == "complete" {"completed"} else {"retry_or_dead_letter"}
    })))
}

#[derive(Debug, Serialize)]
struct ErrorBody {
    error: String,
}

pub struct AppError {
    status: StatusCode,
    message: String,
}
impl AppError {
    fn bad_request(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::BAD_REQUEST,
            message: message.into(),
        }
    }
    fn not_found(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::NOT_FOUND,
            message: message.into(),
        }
    }
    fn conflict(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::CONFLICT,
            message: message.into(),
        }
    }
    fn forbidden(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::FORBIDDEN,
            message: message.into(),
        }
    }
    fn internal(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            message: message.into(),
        }
    }
}
impl<E> From<E> for AppError
where
    E: Into<anyhow::Error>,
{
    fn from(error: E) -> Self {
        let error = error.into();
        tracing::error!(error=%error, "unhandled store error");
        Self {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            message: "internal store error".into(),
        }
    }
}

/// Map a store-layer error onto the HTTP contract without leaking internals:
/// rusqlite failures become a generic 500 (original logged); errors carrying
/// known domain wording keep their 4xx semantics and message.
fn map_store_err(error: anyhow::Error) -> AppError {
    if error.downcast_ref::<rusqlite::Error>().is_some() {
        tracing::error!(error=%error, "store operation failed");
        return AppError::internal("internal store error");
    }
    let message = error.to_string();
    if message.contains("not found") {
        return AppError::not_found(message);
    }
    if [
        "already exists",
        "immutable",
        "invalid",
        "violat",
        "must",
        "required",
        "requires",
        "not leased",
        "unsupported",
        "require",
    ]
    .iter()
    .any(|needle| message.contains(needle))
    {
        return AppError::bad_request(message);
    }
    tracing::error!(error=%error, "store operation failed");
    AppError::internal("internal store error")
}
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        (
            self.status,
            Json(ErrorBody {
                error: self.message,
            }),
        )
            .into_response()
    }
}

/// Run a synchronous registry/DB closure off the async executor. The Result
/// type is identical to a direct call, so surrounding `?`/map_err/ok_or
/// chains keep their exact current behavior; a join failure maps to 500 via
/// the same blanket `From<anyhow::Error> for AppError` path as direct calls.
async fn blocking<T, F>(f: F) -> anyhow::Result<T>
where
    F: FnOnce() -> anyhow::Result<T> + Send + 'static,
    T: Send + 'static,
{
    tokio::task::spawn_blocking(f)
        .await
        .map_err(|error| anyhow::anyhow!("blocking registry task failed: {error}"))?
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{AutoDlConfig, AutoDlGpuSpecConfig, LocalModelConfig};
    use crate::dataset_factory::META_DATASET_KIND;
    use crate::learning::{synthetic_experience, synthetic_feedback};
    use axum::body::to_bytes;
    use chrono::Duration as ChronoDuration;
    use http::{Request as HttpRequest, header};
    use sha2::Digest;
    use tempfile::tempdir;
    use tower::ServiceExt;

    fn state() -> (Arc<AppState>, tempfile::TempDir) {
        let dir = tempdir().unwrap();
        let config = AppConfig {
            data_dir: dir.path().into(),
            bind: "127.0.0.1:0".parse().unwrap(),
            auth_token: "a".repeat(64),
            signing_secret: vec![7; 64],
            local_model: None,
            learning_scheduler_enabled: false,
            metacognition_enabled: false,
            training_provider_local: false,
            github_webhook_secret: None,
            websub_secret: None,
            mediacrawler_search: false,
            github_token: None,
            github_watchlist: vec![],
            meta_trainer_enabled: false,
            meta_base_model: None,
            meta_data_license_policy: None,
            meta_gpu_memory_gb: None,
            autodl: None,
            admin_origin: "https://localhost:8443".into(),
        };
        let state = AppState::new(config).unwrap();
        assert_eq!(state.router.name(), "deterministic-bm25");
        assert!(state.structured_model.is_none());
        (state, dir)
    }

    #[test]
    fn local_model_is_shared_by_router_and_scheduler_without_constructor_http() {
        let dir = tempdir().unwrap();
        let config = AppConfig {
            data_dir: dir.path().into(),
            bind: "127.0.0.1:0".parse().unwrap(),
            auth_token: "a".repeat(64),
            signing_secret: vec![7; 64],
            local_model: Some(LocalModelConfig {
                endpoint: "http://127.0.0.1:9/v1".into(),
                model: "ornith-1.5-9b".into(),
                artifact_sha256: "a".repeat(64),
                runtime: "llama.cpp-win-x86_64-nvidia-cuda12-avx2".into(),
                runtime_version: "2.31.2".into(),
                enforcement_required: true,
            }),
            learning_scheduler_enabled: false,
            metacognition_enabled: false,
            training_provider_local: false,
            github_webhook_secret: None,
            websub_secret: None,
            mediacrawler_search: false,
            github_token: None,
            github_watchlist: vec![],
            meta_trainer_enabled: false,
            meta_base_model: None,
            meta_data_license_policy: None,
            meta_gpu_memory_gb: None,
            autodl: None,
            admin_origin: "https://localhost:8443".into(),
        };
        let state = AppState::new(config).unwrap();
        assert_eq!(state.router.name(), "local-openai-compatible");
        assert!(state.structured_model.is_some());
    }

    async fn body(response: Response) -> Value {
        serde_json::from_slice(&to_bytes(response.into_body(), usize::MAX).await.unwrap()).unwrap()
    }

    fn knowledge_card(
        title: &str,
        status: KnowledgeStatus,
        valid_until: Option<chrono::DateTime<Utc>>,
        risk: f64,
    ) -> KnowledgeCard {
        let now = Utc::now();
        KnowledgeCard {
            schema_version: SCHEMA_VERSION.into(),
            card_id: Uuid::new_v4(),
            revision: 1,
            topic_ids: vec![],
            title: title.into(),
            summary: format!("{title} is supported by recorded evidence."),
            entities: vec!["regression".into()],
            claims: vec![],
            evidence: vec![KnowledgeEvidenceRef {
                document_id: Uuid::new_v4(),
                canonical_url: "https://evidence.example/continual-learning".into(),
                content_hash: "b".repeat(64),
                excerpt: Some("Run verification after the final edit.".into()),
                relationship: EvidenceRelationship::Supports,
                observed_at: now,
            }],
            status,
            published_at: Some(now - ChronoDuration::hours(2)),
            observed_at: now,
            valid_until,
            supersedes: None,
            model_id: "deterministic-test".into(),
            prompt_hash: "a".repeat(64),
            scores: KnowledgeScores {
                relevance: 0.9,
                novelty: 0.8,
                source_reliability: 0.7,
                extraction_completeness: 0.9,
                confidence: 0.8,
                risk,
                cost: 0.0,
            },
            training_eligible: false,
            created_at: now,
        }
    }

    #[test]
    fn old_decision_json_defaults_learned_context() {
        let old = json!({
            "decision_id": Uuid::new_v4(),
            "selected": {
                "workflow_id": "bugfix",
                "version": "1.0.0",
                "score": 1.0,
                "reasons": []
            },
            "alternatives": [],
            "router": "deterministic",
            "fallback_used": false,
            "registry_snapshot": "snapshot"
        });
        let response: DecisionResponse = serde_json::from_value(old).unwrap();
        let current = serde_json::to_value(response).unwrap();
        assert_eq!(current["memory_context"], json!([]));
        assert_eq!(current["knowledge_context"], json!([]));
    }

    #[tokio::test]
    async fn decisions_include_bounded_auditable_learned_context() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let request = json!({"task":"regression"});

        let baseline = service
            .clone()
            .oneshot(authed_post(&token, "/v1/decisions", request.clone()))
            .await
            .unwrap();
        assert_eq!(baseline.status(), StatusCode::OK);
        let baseline = body(baseline).await;
        assert_eq!(baseline["memory_context"], json!([]));
        assert_eq!(baseline["knowledge_context"], json!([]));

        let mut experience_ids = Vec::new();
        for index in [4, 8, 12, 16] {
            let experience = synthetic_experience(index);
            LearningController::ingest(&state.registry, &experience).unwrap();
            LearningController::add_feedback(
                &state.registry,
                &synthetic_feedback(&state.registry, &experience),
            )
            .unwrap();
            experience_ids.push(experience.experience_id);
        }
        for (proposal_id, kind) in [
            (Uuid::nil(), MemoryKind::Fact),
            (Uuid::from_u128(1), MemoryKind::SkillProposal),
        ] {
            state
                .registry
                .save_memory_proposal(&MemoryProposal {
                    proposal_id,
                    experience_id: experience_ids[0],
                    kind,
                    title: "regression".into(),
                    content: "regression".into(),
                    lineage: None,
                    evidence: json!({"fixture":true}),
                    executable: false,
                    created_at: Utc::now(),
                })
                .unwrap();
        }

        let stale_title = "regression verification stale unverified";
        for card in [
            knowledge_card(
                stale_title,
                KnowledgeStatus::Unverified,
                Some(Utc::now() - ChronoDuration::hours(1)),
                0.73,
            ),
            knowledge_card(
                "regression verification corroborated",
                KnowledgeStatus::Corroborated,
                None,
                0.1,
            ),
            knowledge_card(
                "regression verification contested",
                KnowledgeStatus::Contested,
                None,
                0.2,
            ),
            knowledge_card(
                "regression verification superseded",
                KnowledgeStatus::Superseded,
                None,
                0.0,
            ),
            knowledge_card(
                "regression verification retracted",
                KnowledgeStatus::Retracted,
                None,
                0.0,
            ),
        ] {
            state.registry.save_knowledge_card(&card).unwrap();
        }

        let enriched = service
            .clone()
            .oneshot(authed_post(&token, "/v1/decisions", request.clone()))
            .await
            .unwrap();
        assert_eq!(enriched.status(), StatusCode::OK);
        let enriched = body(enriched).await;
        assert_eq!(enriched["selected"], baseline["selected"]);

        let memory = enriched["memory_context"].as_array().unwrap();
        assert_eq!(memory.len(), 5);
        assert!(memory.iter().all(|item| matches!(
            item["kind"].as_str().unwrap(),
            "episodic" | "failure" | "anti_skill"
        )));
        assert!(memory.iter().any(|item| item["kind"] == "failure"));
        assert!(memory.iter().any(|item| {
            item["kind"] == "anti_skill"
                && item["warning"] == "negative-transfer warning; never execute as a Skill"
        }));

        let knowledge = enriched["knowledge_context"].as_array().unwrap();
        assert_eq!(knowledge.len(), 3);
        let statuses = knowledge
            .iter()
            .map(|item| item["card"]["status"].as_str().unwrap())
            .collect::<std::collections::HashSet<_>>();
        assert_eq!(
            statuses,
            ["unverified", "corroborated", "contested"]
                .into_iter()
                .collect()
        );
        let stale = knowledge
            .iter()
            .find(|item| item["card"]["title"] == stale_title)
            .unwrap();
        assert_eq!(stale["stale"], true);
        assert_eq!(stale["card"]["scores"]["risk"], 0.73);
        assert_eq!(
            stale["card"]["evidence"][0]["canonical_url"],
            "https://evidence.example/continual-learning"
        );

        let decision_id = Uuid::parse_str(enriched["decision_id"].as_str().unwrap()).unwrap();
        let persisted =
            serde_json::to_value(state.registry.get_decision(decision_id).unwrap().unwrap())
                .unwrap();
        assert_eq!(persisted["memory_context"], enriched["memory_context"]);
        assert_eq!(
            persisted["knowledge_context"],
            enriched["knowledge_context"]
        );

        for index in 0..4 {
            state
                .registry
                .save_knowledge_card(&knowledge_card(
                    &format!("regression verification filler {index}"),
                    KnowledgeStatus::Unverified,
                    None,
                    0.4,
                ))
                .unwrap();
        }
        let bounded = service
            .oneshot(authed_post(&token, "/v1/decisions", request))
            .await
            .unwrap();
        let bounded = body(bounded).await;
        assert_eq!(bounded["memory_context"].as_array().unwrap().len(), 5);
        assert_eq!(bounded["knowledge_context"].as_array().unwrap().len(), 5);
    }

    #[tokio::test]
    async fn api_requires_auth() {
        let (state, _dir) = state();
        let response = app(state)
            .oneshot(
                HttpRequest::get("/v1/workflows")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn expert_route_falls_back_to_dense_until_an_adapter_is_active() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let response = app(state)
            .oneshot(
                HttpRequest::post("/v1/experts:route")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({
                            "task_kind":"relevance",
                            "input":{"query":"agent"},
                            "source_domain":"example.test",
                            "topic_family":"retrieval"
                        })
                        .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let value = body(response).await;
        assert_eq!(value["selected_expert_id"], "retrieval");
        assert_eq!(value["dense_fallback"], true);
        assert!(value["selected_adapter"].is_null());
    }

    #[tokio::test]
    async fn requested_training_run_can_be_cancelled_while_provider_is_disabled() {
        let (state, _dir) = state();
        let build = state
            .registry
            .build_dataset_draft(META_DATASET_KIND, Utc::now())
            .unwrap();
        let snapshot = state
            .registry
            .freeze_dataset_snapshot(
                &CreateDatasetSnapshotRequest {
                    kind: META_DATASET_KIND.into(),
                    build_id: Some(build.build_id),
                    created_by: "test".into(),
                    reason: "provider-disabled cancellation fixture".into(),
                },
                Utc::now(),
            )
            .unwrap();
        let base_model = BaseModelPin {
            model_id: "example/model".into(),
            revision: "immutable-revision".into(),
            sha256: "a".repeat(64),
        };
        let provider_config = AutoDlConfig {
            api_base_url: "https://www.autodl.com".into(),
            api_token: "not-persisted".into(),
            application_uuid: "application-id".into(),
            application_version: "v1".into(),
            worker_gateway_url: "https://worker.example.com".into(),
            provider_name: "autodl-app".into(),
            gpu_allowlist: vec![AutoDlGpuSpecConfig {
                id: "approved-24g".into(),
                display_name: "approved test GPU".into(),
                memory_gb: 24,
                cuda: true,
                data_centers: vec!["test".into()],
            }],
            base_models: vec![base_model.clone()],
        };
        let run = state
            .registry
            .create_training_run(
                &CreateTrainingRunRequest {
                    snapshot_id: snapshot.snapshot.snapshot_id,
                    base_model,
                    qlora: QloraConfig::default(),
                    expert_plan: None,
                    gpu_spec: "approved-24g".into(),
                    administrator: "admin".into(),
                    reason: "test cancellation".into(),
                    budget: TrainingBudget {
                        max_hourly_cny: 1.0,
                        max_total_cny: 1.0,
                        max_wall_seconds: 600,
                    },
                },
                &provider_config,
                Utc::now(),
            )
            .unwrap();
        assert!(state.gpu_provider.is_none());
        let token = state.config.auth_token.clone();
        let response = app(state)
            .oneshot(
                HttpRequest::post(format!("/v1/training-runs/{}:cancel", run.run_id))
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({"administrator":"admin","reason":"disable training"}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert_eq!(body(response).await["status"], "cancelled");
    }

    #[tokio::test]
    async fn browser_admin_requests_require_same_origin_and_csrf() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let csrf = state.admin_csrf.clone();
        let admin = app(state.clone())
            .oneshot(
                HttpRequest::get("/admin")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(admin.status(), StatusCode::OK);
        assert!(admin.headers().contains_key("content-security-policy"));

        let body = Body::from(r#"{"actor":"admin","reason":"test"}"#);
        let cross_origin = app(state.clone())
            .oneshot(
                HttpRequest::post("/v1/datasets/meta-controller:build")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::ORIGIN, "https://evil.example")
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(body)
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(cross_origin.status(), StatusCode::FORBIDDEN);

        let missing_csrf = app(state.clone())
            .oneshot(
                HttpRequest::post("/v1/datasets/meta-controller:build")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::ORIGIN, "https://localhost:8443")
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(r#"{"actor":"admin","reason":"test"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(missing_csrf.status(), StatusCode::FORBIDDEN);

        let accepted = app(state)
            .oneshot(
                HttpRequest::post("/v1/datasets/meta-controller:build")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::ORIGIN, "https://localhost:8443")
                    .header("x-cerebellum-csrf", csrf)
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(r#"{"actor":"admin","reason":"test"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(accepted.status(), StatusCode::CREATED);
    }

    #[tokio::test]
    async fn github_webhook_requires_hmac_watchlist_and_fixed_commit() {
        let dir = tempdir().unwrap();
        let secret = b"webhook-secret".to_vec();
        let config = AppConfig {
            data_dir: dir.path().into(),
            bind: "127.0.0.1:0".parse().unwrap(),
            auth_token: "a".repeat(64),
            signing_secret: vec![7; 64],
            local_model: None,
            learning_scheduler_enabled: false,
            metacognition_enabled: false,
            training_provider_local: false,
            github_webhook_secret: Some(secret.clone()),
            websub_secret: None,
            mediacrawler_search: false,
            github_token: None,
            github_watchlist: vec!["owner/repo".into()],
            meta_trainer_enabled: false,
            meta_base_model: None,
            meta_data_license_policy: None,
            meta_gpu_memory_gb: None,
            autodl: None,
            admin_origin: "https://localhost:8443".into(),
        };
        let state = AppState::new(config).unwrap();
        let payload = serde_json::to_vec(&json!({
            "after":"a".repeat(40),
            "repository":{"full_name":"owner/repo","html_url":"https://github.com/owner/repo"}
        }))
        .unwrap();
        let mut mac = Hmac::<Sha256>::new_from_slice(&secret).unwrap();
        mac.update(&payload);
        let signature = mac.finalize().into_bytes();
        let signature = signature
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        let response = app(state.clone())
            .oneshot(
                HttpRequest::post("/v1/github/webhooks")
                    .header("x-github-event", "push")
                    .header("x-hub-signature-256", format!("sha256={signature}"))
                    .body(Body::from(payload.clone()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::ACCEPTED);

        let rejected = app(state)
            .oneshot(
                HttpRequest::post("/v1/github/webhooks")
                    .header("x-github-event", "push")
                    .header("x-hub-signature-256", format!("sha256={}", "0".repeat(64)))
                    .body(Body::from(payload))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(rejected.status(), StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn websub_verifies_topic_and_hmac_before_scheduling_rss_sync() {
        let dir = tempdir().unwrap();
        let secret = b"websub-secret".to_vec();
        let config = AppConfig {
            data_dir: dir.path().into(),
            bind: "127.0.0.1:0".parse().unwrap(),
            auth_token: "a".repeat(64),
            signing_secret: vec![7; 64],
            local_model: None,
            learning_scheduler_enabled: false,
            metacognition_enabled: false,
            training_provider_local: false,
            github_webhook_secret: None,
            websub_secret: Some(secret.clone()),
            mediacrawler_search: false,
            github_token: None,
            github_watchlist: vec![],
            meta_trainer_enabled: false,
            meta_base_model: None,
            meta_data_license_policy: None,
            meta_gpu_memory_gb: None,
            autodl: None,
            admin_origin: "https://localhost:8443".into(),
        };
        let state = AppState::new(config).unwrap();
        let source = state
            .registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "WebSub RSS".into(),
                kind: SourceKind::RssAtom,
                base_url: "https://example.com/feed.xml".into(),
                access_mode: SourceAccessMode::Public,
                allowed_domains: vec!["example.com".into()],
                obey_robots: true,
                max_depth: 1,
                max_pages_per_run: 10,
                rate_limit_per_minute: 30,
                raw_retention_days: 30,
                training_license: None,
                model_terms_allow_training: false,
                auth_secret_ref: None,
                data_classification: cerebellum_core::DataClassification::Public,
                external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
                enabled: true,
            })
            .unwrap();
        state
            .registry
            .create_topic_watch(&CreateTopicWatchRequest {
                name: "WebSub topic".into(),
                query: "agent workflow".into(),
                keywords: vec!["agent".into()],
                entities: vec![],
                languages: vec!["en".into()],
                source_policy_ids: vec![source.policy_id],
                refresh_seconds: 120,
                budget: TopicBudget::default(),
                enabled: true,
            })
            .unwrap();
        let query = serde_urlencoded::to_string([
            ("hub.mode", "subscribe"),
            ("hub.topic", source.base_url.as_str()),
            ("hub.challenge", "challenge-token"),
        ])
        .unwrap();
        let service = app(state);
        let verification = service
            .clone()
            .oneshot(
                HttpRequest::get(format!("/v1/websub/{}?{query}", source.policy_id))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(verification.status(), StatusCode::OK);
        assert_eq!(
            to_bytes(verification.into_body(), 4_096).await.unwrap(),
            "challenge-token"
        );

        let notification = b"<feed><updated>2026-08-24T00:00:00Z</updated></feed>";
        let mut mac = Hmac::<Sha256>::new_from_slice(&secret).unwrap();
        mac.update(notification);
        let signature = mac
            .finalize()
            .into_bytes()
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        let accepted = service
            .clone()
            .oneshot(
                HttpRequest::post(format!("/v1/websub/{}", source.policy_id))
                    .header("x-hub-signature-256", format!("sha256={signature}"))
                    .body(Body::from(notification.as_slice()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(accepted.status(), StatusCode::ACCEPTED);
        assert_eq!(body(accepted).await["job_ids"].as_array().unwrap().len(), 1);

        let rejected = service
            .oneshot(
                HttpRequest::post(format!("/v1/websub/{}", source.policy_id))
                    .header("x-hub-signature-256", format!("sha256={}", "0".repeat(64)))
                    .body(Body::from(notification.as_slice()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(rejected.status(), StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn http_learning_loop_ingests_feedback_and_retrieves_context() {
        let (state, _dir) = state();
        let experience = synthetic_experience(4);
        let response = app(state.clone())
            .oneshot(
                HttpRequest::post("/v1/experiences")
                    .header(
                        header::AUTHORIZATION,
                        format!("Bearer {}", state.config.auth_token),
                    )
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(serde_json::to_vec(&experience).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::CREATED);

        let feedback = synthetic_feedback(&state.registry, &experience);
        let response = app(state.clone())
            .oneshot(
                HttpRequest::post(format!(
                    "/v1/experiences/{}/feedback",
                    experience.experience_id
                ))
                .header(
                    header::AUTHORIZATION,
                    format!("Bearer {}", state.config.auth_token),
                )
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(serde_json::to_vec(&feedback).unwrap()))
                .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::CREATED);

        let response = app(state.clone())
            .oneshot(
                HttpRequest::post("/v1/context:retrieve")
                    .header(
                        header::AUTHORIZATION,
                        format!("Bearer {}", state.config.auth_token),
                    )
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        serde_json::to_vec(&json!({"query":"fixture regression","limit":10}))
                            .unwrap(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let value = body(response).await;
        assert!(
            value["items"]
                .as_array()
                .is_some_and(|items| !items.is_empty())
        );
        assert!(value["items"].as_array().unwrap().iter().any(|item| {
            item.get("warning")
                .is_some_and(|warning| !warning.is_null())
        }));
    }

    #[tokio::test]
    async fn failed_gate_cannot_issue_permit() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let app = app(state);
        let decision_request = HttpRequest::post("/v1/decisions")
            .header(header::AUTHORIZATION, format!("Bearer {token}"))
            .header(header::CONTENT_TYPE, "application/json")
            .body(Body::from(r#"{"task":"fix parser bug"}"#))
            .unwrap();
        let decision_response = app.clone().oneshot(decision_request).await.unwrap();
        let decision = body(decision_response).await;
        let run_request = json!({"decision_id":decision["decision_id"],"workflow_id":decision["selected"]["workflow_id"],"workflow_version":decision["selected"]["version"]});
        let response = app
            .clone()
            .oneshot(
                HttpRequest::post("/v1/runs")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(run_request.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        let run = body(response).await;
        let auth = json!({"run_id":run["id"],"action":{"tool":"shell","command":"git push"}});
        let response = app
            .oneshot(
                HttpRequest::post("/v1/authorize")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(auth.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn passed_gates_issue_single_use_action_bound_permit() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let app = app(state);
        let decision_response = app
            .clone()
            .oneshot(
                HttpRequest::post("/v1/decisions")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(r#"{"task":"fix parser bug"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        let decision = body(decision_response).await;
        let run_request = json!({"decision_id":decision["decision_id"],"workflow_id":decision["selected"]["workflow_id"],"workflow_version":decision["selected"]["version"]});
        let run_response = app
            .clone()
            .oneshot(
                HttpRequest::post("/v1/runs")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(run_request.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        let run = body(run_response).await;
        let run_id = run["id"].as_str().unwrap();

        for (gate, evidence) in [
            ("tests-pass", json!({"passed": 12, "failed": 0})),
            ("review-complete", json!({"review_complete": true})),
        ] {
            let response = app
                .clone()
                .oneshot(
                    HttpRequest::post(format!("/v1/runs/{run_id}/gates/{gate}:evaluate"))
                        .header(header::AUTHORIZATION, format!("Bearer {token}"))
                        .header(header::CONTENT_TYPE, "application/json")
                        .body(Body::from(json!({"evidence":evidence}).to_string()))
                        .unwrap(),
                )
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::OK);
        }

        let action = json!({"tool":"shell","command":"cargo test"});
        let response = app
            .clone()
            .oneshot(
                HttpRequest::post("/v1/authorize")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({"run_id":run_id,"action":action}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let permit = body(response).await;
        let verification = json!({"token":permit["token"],"action":action,"consume":true});

        let first = app
            .clone()
            .oneshot(
                HttpRequest::post("/v1/permits/verify")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(verification.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(first.status(), StatusCode::OK);
        let replay = app
            .oneshot(
                HttpRequest::post("/v1/permits/verify")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(verification.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(replay.status(), StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn v3_http_loop_creates_syncs_consolidates_and_retrieves_knowledge() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let source_response = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/source-policies")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({
                            "name":"Example RSS",
                            "kind":"rss_atom",
                            "base_url":"https://example.com/feed.xml",
                            "access_mode":"public",
                            "allowed_domains":["example.com"]
                        })
                        .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(source_response.status(), StatusCode::CREATED);
        let source = body(source_response).await;
        let source_id = source["policy_id"].as_str().unwrap();

        let topic_response = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/topics")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({
                            "name":"Agent workflows",
                            "query":"agent workflow verification",
                            "keywords":["workflow"],
                            "source_policy_ids":[source_id],
                            "refresh_seconds":30
                        })
                        .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(topic_response.status(), StatusCode::CREATED);
        let topic = body(topic_response).await;
        let topic_id = Uuid::parse_str(topic["topic_id"].as_str().unwrap()).unwrap();

        let sync = service
            .clone()
            .oneshot(
                HttpRequest::post(format!("/v1/connectors/{source_id}:sync"))
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from("{}"))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(sync.status(), StatusCode::ACCEPTED);
        assert_eq!(body(sync).await["job_ids"].as_array().unwrap().len(), 1);

        let now = Utc::now();
        let cleaned = b"Fresh verification improves agent workflow reliability.";
        let cleaned_hash = format!("{:x}", sha2::Sha256::digest(cleaned));
        let document = DocumentEnvelope {
            schema_version: SCHEMA_VERSION.into(),
            document_id: Uuid::new_v4(),
            topic_ids: vec![topic_id],
            source_policy_id: Uuid::parse_str(source_id).unwrap(),
            external_id: Some("fixture-1".into()),
            url: "https://example.com/posts/verification".into(),
            canonical_url: "https://example.com/posts/verification".into(),
            author: Some("Example".into()),
            title: "Agent workflow verification".into(),
            published_at: Some(now - ChronoDuration::minutes(1)),
            observed_at: now,
            fetched_at: now,
            raw_content_hash: None,
            cleaned_content_hash: cleaned_hash,
            extraction_method: AcquisitionMethod::Rss,
            extractor_version: "fixture".into(),
            language: "en".into(),
            content_type: "text/plain".into(),
            rights: DocumentRights {
                license: None,
                retrieval_allowed: true,
                storage_allowed: true,
                redistribution_allowed: false,
                explicit_training_permission: false,
                model_terms_allow_training: false,
                training_eligible: false,
                rights_source: "fixture".into(),
            },
            prompt_injection_detected: false,
            pii_detected: false,
            secret_detected: false,
            raw_expires_at: now + ChronoDuration::days(30),
            tombstoned: false,
            metadata: json!({"fixture":true}),
        };
        state
            .registry
            .save_document(&document, cleaned, None)
            .unwrap();
        let card = crate::knowledge::consolidate_document(&state.registry, document.document_id)
            .unwrap()
            .card;

        let retrieval = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/knowledge:retrieve")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({"query":"workflow verification","limit":10}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(retrieval.status(), StatusCode::OK);
        let retrieval = body(retrieval).await;
        assert_eq!(
            retrieval["items"][0]["card"]["card_id"],
            card.card_id.to_string()
        );
        assert_eq!(
            retrieval["items"][0]["card"]["evidence"][0]["canonical_url"],
            "https://example.com/posts/verification"
        );

        for path in [
            format!("/v1/knowledge/cards/{}", card.card_id),
            format!("/v1/knowledge/cards/{}/history", card.card_id),
            "/v1/acquisition/status".into(),
        ] {
            let response = service
                .clone()
                .oneshot(
                    HttpRequest::get(path)
                        .header(header::AUTHORIZATION, format!("Bearer {token}"))
                        .body(Body::empty())
                        .unwrap(),
                )
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::OK);
        }

        let disabled = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/meta/training:enqueue")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({"candidate_id":Uuid::new_v4()}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(disabled.status(), StatusCode::FORBIDDEN);

        let tombstoned = service
            .clone()
            .oneshot(
                HttpRequest::post(format!("/v1/source-policies/{source_id}:tombstone"))
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(
                        json!({"actor":"fixture-admin","reason":"source deletion request"})
                            .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(tombstoned.status(), StatusCode::OK);
        assert_eq!(body(tombstoned).await["documents_tombstoned"], 1);

        let redacted = service
            .oneshot(
                HttpRequest::get(format!("/v1/knowledge/cards/{}", card.card_id))
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(redacted.status(), StatusCode::OK);
        let redacted = body(redacted).await;
        assert_eq!(redacted["status"], "retracted");
        assert!(redacted["evidence"][0]["excerpt"].is_null());
    }

    #[tokio::test]
    async fn list_learning_jobs_filters_by_status() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        state
            .registry
            .enqueue_unique_learning_job(
                "source_discover_v1",
                "fixture-discover",
                json!({"a":1}),
                1.0,
                3,
            )
            .unwrap();
        state
            .registry
            .enqueue_unique_learning_job(
                "knowledge_consolidate_v1",
                "fixture-consolidate",
                json!({"b":2}),
                1.0,
                3,
            )
            .unwrap();

        let response = service
            .clone()
            .oneshot(
                HttpRequest::get("/v1/learning/jobs")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let jobs = body(response).await;
        let jobs = jobs.as_array().unwrap();
        assert_eq!(jobs.len(), 2);
        assert_eq!(jobs[0]["status"], "pending");

        let response = service
            .clone()
            .oneshot(
                HttpRequest::get("/v1/learning/jobs?status=pending")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert_eq!(body(response).await.as_array().unwrap().len(), 2);

        let response = service
            .clone()
            .oneshot(
                HttpRequest::get("/v1/learning/jobs?status=dead_letter")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert_eq!(body(response).await.as_array().unwrap().len(), 0);

        let unauthorized = service
            .oneshot(
                HttpRequest::get("/v1/learning/jobs")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(unauthorized.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn list_knowledge_cards_and_documents_empty_lists() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        for path in ["/v1/knowledge/cards", "/v1/documents"] {
            let response = service
                .clone()
                .oneshot(
                    HttpRequest::get(path)
                        .header(header::AUTHORIZATION, format!("Bearer {token}"))
                        .body(Body::empty())
                        .unwrap(),
                )
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::OK);
            assert_eq!(body(response).await.as_array().unwrap().len(), 0);

            let unauthorized = service
                .clone()
                .oneshot(HttpRequest::get(path).body(Body::empty()).unwrap())
                .await
                .unwrap();
            assert_eq!(unauthorized.status(), StatusCode::UNAUTHORIZED);
        }
    }

    fn authed_get(token: &str, path: &str) -> HttpRequest<Body> {
        HttpRequest::get(path)
            .header(header::AUTHORIZATION, format!("Bearer {token}"))
            .body(Body::empty())
            .unwrap()
    }

    fn authed_post(token: &str, path: &str, payload: Value) -> HttpRequest<Body> {
        HttpRequest::post(path)
            .header(header::AUTHORIZATION, format!("Bearer {token}"))
            .header(header::CONTENT_TYPE, "application/json")
            .body(Body::from(payload.to_string()))
            .unwrap()
    }

    #[tokio::test]
    async fn auth_rejects_wrong_bearer_and_reports_error_body() {
        let (state, _dir) = state();
        let service = app(state);
        let missing = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/decisions")
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(r#"{"task":"x"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(missing.status(), StatusCode::UNAUTHORIZED);
        assert_eq!(body(missing).await["error"], "unauthorized");

        let wrong = service
            .oneshot(
                HttpRequest::post("/v1/decisions")
                    .header(header::AUTHORIZATION, "Bearer wrong-token")
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(r#"{"task":"x"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(wrong.status(), StatusCode::UNAUTHORIZED);
        assert_eq!(body(wrong).await["error"], "unauthorized");
    }

    #[tokio::test]
    async fn unknown_routes_return_404() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);
        for path in ["/v1/no-such-route", "/v1/skills/anything"] {
            let response = service
                .clone()
                .oneshot(authed_get(&token, path))
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::NOT_FOUND, "GET {path}");
        }
        let response = service
            .clone()
            .oneshot(authed_post(&token, "/v1/no-such-route", json!({})))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);

        let wrong_method = service
            .oneshot(authed_get(&token, "/v1/decisions"))
            .await
            .unwrap();
        assert_eq!(wrong_method.status(), StatusCode::METHOD_NOT_ALLOWED);
    }

    #[tokio::test]
    async fn health_is_public_and_reports_status() {
        let (state, _dir) = state();
        let response = app(state)
            .oneshot(HttpRequest::get("/health").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let value = body(response).await;
        assert_eq!(value["status"], "ok");
        assert!(value.get("registry_snapshot").is_none());
    }

    #[tokio::test]
    async fn health_probes_stay_fast_during_a_slow_write() {
        let (state, _dir) = state();
        let registry = state.registry.clone();
        let service = app(state.clone());

        // Hold the registry conn lock on a blocking thread (simulating a slow
        // write), then fire 20 concurrent public probes: all must return
        // quickly instead of queueing behind the writer's executor thread.
        let (held_tx, held_rx) = tokio::sync::oneshot::channel::<()>();
        let (release_tx, release_rx) = tokio::sync::oneshot::channel::<()>();
        let holder = tokio::task::spawn_blocking(move || {
            let _guard = registry.lock_conn();
            held_tx.send(()).ok();
            let _ = release_rx.blocking_recv();
        });
        held_rx.await.unwrap();

        let token = state.config.auth_token.clone();
        let started = std::time::Instant::now();
        let probes = (0..20)
            .map(|_| {
                let service = service.clone();
                let token = token.clone();
                tokio::spawn(async move {
                    service
                        .oneshot(authed_get(&token, "/health"))
                        .await
                        .unwrap()
                        .status()
                })
            })
            .collect::<Vec<_>>();
        for probe in probes {
            assert_eq!(probe.await.unwrap(), StatusCode::OK);
        }
        let elapsed = started.elapsed();
        release_tx.send(()).ok();
        holder.await.unwrap();
        assert!(
            elapsed < std::time::Duration::from_secs(2),
            "20 probes during a slow write took {elapsed:?} (executor starved)"
        );
    }

    #[tokio::test]
    async fn request_validation_errors_return_4xx_with_details() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);

        let malformed = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/decisions")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from("{not json"))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(malformed.status(), StatusCode::BAD_REQUEST);

        let missing_content_type = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/decisions")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .body(Body::from(r#"{"task":"x"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(
            missing_content_type.status(),
            StatusCode::UNSUPPORTED_MEDIA_TYPE
        );

        let empty_task = service
            .clone()
            .oneshot(authed_post(&token, "/v1/decisions", json!({"task":"   "})))
            .await
            .unwrap();
        assert_eq!(empty_task.status(), StatusCode::BAD_REQUEST);
        assert_eq!(body(empty_task).await["error"], "task must not be empty");

        let unknown_enum = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/source-policies",
                json!({
                    "name":"Bad kind",
                    "kind":"carrier_pigeon",
                    "base_url":"https://example.com",
                    "access_mode":"public",
                    "allowed_domains":["example.com"]
                }),
            ))
            .await
            .unwrap();
        assert_eq!(unknown_enum.status(), StatusCode::UNPROCESSABLE_ENTITY);

        let bad_query_enum = service
            .clone()
            .oneshot(authed_get(&token, "/v1/learning/jobs?status=bogus"))
            .await
            .unwrap();
        assert_eq!(bad_query_enum.status(), StatusCode::BAD_REQUEST);

        let mut experience = synthetic_experience(11);
        experience.schema_version = "0.0.0".into();
        let schema_mismatch = service
            .oneshot(
                HttpRequest::post("/v1/experiences")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(serde_json::to_vec(&experience).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(schema_mismatch.status(), StatusCode::BAD_REQUEST);
        assert!(body(schema_mismatch).await["error"].is_string());
    }

    #[tokio::test]
    async fn skills_listing_supports_query_and_limit() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);

        let all = service
            .clone()
            .oneshot(authed_get(&token, "/v1/skills"))
            .await
            .unwrap();
        assert_eq!(all.status(), StatusCode::OK);
        let all = body(all).await;
        let all = all.as_array().unwrap();
        assert!(
            all.iter()
                .any(|skill| skill["id"] == "builtin.inspect-repository")
        );

        let filtered = service
            .clone()
            .oneshot(authed_get(&token, "/v1/skills?q=inspect"))
            .await
            .unwrap();
        assert_eq!(filtered.status(), StatusCode::OK);
        let filtered = body(filtered).await;
        let filtered = filtered.as_array().unwrap();
        assert!(!filtered.is_empty());
        assert!(filtered.iter().all(|skill| {
            format!("{}{}", skill["id"], skill["description"])
                .to_lowercase()
                .contains("inspect")
        }));

        let limited = service
            .clone()
            .oneshot(authed_get(&token, "/v1/skills?limit=2"))
            .await
            .unwrap();
        assert_eq!(limited.status(), StatusCode::OK);
        assert_eq!(body(limited).await.as_array().unwrap().len(), 2);

        let no_match = service
            .oneshot(authed_get(&token, "/v1/skills?q=zzz-no-such-skill"))
            .await
            .unwrap();
        assert_eq!(no_match.status(), StatusCode::OK);
        assert!(body(no_match).await.as_array().unwrap().is_empty());
    }

    #[tokio::test]
    async fn workflows_listing_contains_seeded_workflows() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let response = app(state)
            .oneshot(authed_get(&token, "/v1/workflows"))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let workflows = body(response).await;
        let workflows = workflows.as_array().unwrap();
        assert!(
            workflows
                .iter()
                .any(|workflow| { workflow["id"] == "bugfix" && workflow["version"].is_string() })
        );
        assert!(
            workflows
                .iter()
                .all(|workflow| workflow["schema_version"] == SCHEMA_VERSION)
        );
    }

    #[tokio::test]
    async fn run_lifecycle_records_events_trace_and_completion() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);

        let decision = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/decisions",
                json!({"task":"fix parser bug"}),
            ))
            .await
            .unwrap();
        assert_eq!(decision.status(), StatusCode::OK);
        let decision = body(decision).await;

        let mismatched = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/runs",
                json!({
                    "decision_id":decision["decision_id"],
                    "workflow_id":decision["selected"]["workflow_id"],
                    "workflow_version":"0.0.0-not-the-decision"
                }),
            ))
            .await
            .unwrap();
        assert_eq!(mismatched.status(), StatusCode::BAD_REQUEST);
        assert_eq!(
            body(mismatched).await["error"],
            "run workflow does not match the recorded decision"
        );

        let created = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/runs",
                json!({
                    "decision_id":decision["decision_id"],
                    "workflow_id":decision["selected"]["workflow_id"],
                    "workflow_version":decision["selected"]["version"]
                }),
            ))
            .await
            .unwrap();
        assert_eq!(created.status(), StatusCode::CREATED);
        let run = body(created).await;
        let run_id = run["id"].as_str().unwrap();

        let empty_kind = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/runs/{run_id}/events"),
                json!({"kind":"  ","payload":{}}),
            ))
            .await
            .unwrap();
        assert_eq!(empty_kind.status(), StatusCode::BAD_REQUEST);

        let appended = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/runs/{run_id}/events"),
                json!({"kind":"note","payload":{"message":"started"}}),
            ))
            .await
            .unwrap();
        assert_eq!(appended.status(), StatusCode::CREATED);
        let sequence = body(appended).await["sequence"].as_i64().unwrap();

        let trace = service
            .clone()
            .oneshot(authed_get(&token, &format!("/v1/runs/{run_id}/trace")))
            .await
            .unwrap();
        assert_eq!(trace.status(), StatusCode::OK);
        let trace = body(trace).await;
        assert!(trace["events"].as_array().unwrap().iter().any(|event| {
            event["sequence"].as_i64() == Some(sequence) && event["kind"] == "note"
        }));

        let missing_trace = service
            .clone()
            .oneshot(authed_get(
                &token,
                &format!("/v1/runs/{}/trace", Uuid::new_v4()),
            ))
            .await
            .unwrap();
        assert_eq!(missing_trace.status(), StatusCode::NOT_FOUND);

        let completed = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/runs/{run_id}/complete"),
                json!({"outcome":"failure","summary":"gave up"}),
            ))
            .await
            .unwrap();
        assert_eq!(completed.status(), StatusCode::OK);
        let completed = body(completed).await;
        assert_eq!(completed["status"], "completed");
        assert_eq!(completed["outcome"], "failure");

        let authorize_after_complete = service
            .oneshot(authed_post(
                &token,
                "/v1/authorize",
                json!({"run_id":run_id,"action":{"tool":"shell","command":"ls"}}),
            ))
            .await
            .unwrap();
        assert_eq!(authorize_after_complete.status(), StatusCode::CONFLICT);
    }

    #[tokio::test]
    async fn complete_run_with_provenance_ingests_experience() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());

        async fn create_run(service: &AxumRouter, token: &str) -> (String, String) {
            let decision = service
                .clone()
                .oneshot(authed_post(
                    token,
                    "/v1/decisions",
                    json!({"task":"fix parser bug"}),
                ))
                .await
                .unwrap();
            let decision = body(decision).await;
            let created = service
                .clone()
                .oneshot(authed_post(
                    token,
                    "/v1/runs",
                    json!({
                        "decision_id":decision["decision_id"],
                        "workflow_id":decision["selected"]["workflow_id"],
                        "workflow_version":decision["selected"]["version"]
                    }),
                ))
                .await
                .unwrap();
            assert_eq!(created.status(), StatusCode::CREATED);
            let run = body(created).await;
            (
                run["id"].as_str().unwrap().to_string(),
                decision["selected"]["workflow_id"]
                    .as_str()
                    .unwrap()
                    .to_string(),
            )
        }

        fn provenance() -> Value {
            json!({
                "task":"fix parser bug",
                "task_family":"parser",
                "repository":{"repository_id":"repo-1","digest":"sha256:deadbeef"},
                "agent_id":"agent/v1",
                "model_id":"model-1",
                "source":{"kind":"agent_trace","uri":"trace://run/1","collected_by":"test"}
            })
        }

        // Failure outcome: provenance still closes the loop (failure is a
        // learning signal, not a reason to skip ingestion).
        let (run_id, workflow_id) = create_run(&service, &token).await;
        let completed = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/runs/{run_id}/complete"),
                json!({"outcome":"failure","summary":"tests still red","experience":provenance()}),
            ))
            .await
            .unwrap();
        assert_eq!(completed.status(), StatusCode::OK);
        assert_eq!(body(completed).await["experience_ingested"], true);

        let run_uuid = Uuid::parse_str(&run_id).unwrap();
        let experience = state
            .registry
            .get_experience(run_uuid)
            .unwrap()
            .expect("completion provenance ingests an experience");
        assert_eq!(experience.experience_id, run_uuid);
        assert!(!experience.outcome.success);
        assert_eq!(experience.outcome.summary, "tests still red");
        assert_eq!(experience.workflow.as_ref().unwrap().id, workflow_id);

        // Feedback binds to the ingested experience.
        let feedback = learning::synthetic_feedback(&state.registry, &experience);
        let accepted = service
            .clone()
            .oneshot(
                HttpRequest::post(format!("/v1/experiences/{run_id}/feedback"))
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(serde_json::to_vec(&feedback).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(accepted.status(), StatusCode::CREATED);

        // Replay: the run refuses a second transition, and no duplicate
        // experience appears (experience_id == run_id collapses replays).
        let replay = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/runs/{run_id}/complete"),
                json!({"outcome":"failure","summary":"tests still red","experience":provenance()}),
            ))
            .await
            .unwrap();
        assert!(replay.status().is_client_error() || replay.status().is_server_error());
        assert_eq!(state.registry.all_experiences().unwrap().len(), 1);

        // Success outcome (gates + required nodes satisfied) also ingests.
        let (run_id2, _workflow_id2) = create_run(&service, &token).await;
        let run_uuid2 = Uuid::parse_str(&run_id2).unwrap();
        let run2 = state.registry.get_run(run_uuid2).unwrap().unwrap();
        let workflow = state
            .registry
            .get_workflow(&run2.workflow_id, &run2.workflow_version)
            .unwrap()
            .unwrap();
        for node in workflow.nodes.iter().filter(|node| node.required) {
            for kind in ["node_started", "node_completed"] {
                let response = service
                    .clone()
                    .oneshot(authed_post(
                        &token,
                        &format!("/v1/runs/{run_id2}/events"),
                        json!({"kind":kind,"payload":{"node_id":node.id}}),
                    ))
                    .await
                    .unwrap();
                assert_eq!(response.status(), StatusCode::CREATED);
            }
        }
        for (gate, evidence) in [
            ("tests-pass", json!({"passed": 12, "failed": 0})),
            ("review-complete", json!({"review_complete": true})),
        ] {
            let response = service
                .clone()
                .oneshot(authed_post(
                    &token,
                    &format!("/v1/runs/{run_id2}/gates/{gate}:evaluate"),
                    json!({"evidence":evidence}),
                ))
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::OK);
        }
        let completed2 = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/runs/{run_id2}/complete"),
                json!({"outcome":"success","summary":"green","experience":provenance()}),
            ))
            .await
            .unwrap();
        assert_eq!(completed2.status(), StatusCode::OK);
        assert_eq!(body(completed2).await["experience_ingested"], true);
        let experience2 = state.registry.get_experience(run_uuid2).unwrap().unwrap();
        assert!(experience2.outcome.success);
        assert_eq!(state.registry.all_experiences().unwrap().len(), 2);

        // No provenance: completion behaves exactly as before.
        let (run_id3, _) = create_run(&service, &token).await;
        let completed3 = service
            .oneshot(authed_post(
                &token,
                &format!("/v1/runs/{run_id3}/complete"),
                json!({"outcome":"failure"}),
            ))
            .await
            .unwrap();
        assert_eq!(completed3.status(), StatusCode::OK);
        assert_eq!(body(completed3).await["experience_ingested"], false);
        let run_uuid3 = Uuid::parse_str(&run_id3).unwrap();
        assert!(state.registry.get_experience(run_uuid3).unwrap().is_none());
        assert_eq!(state.registry.all_experiences().unwrap().len(), 2);
    }

    #[tokio::test]
    async fn experiences_dedup_and_feedback_url_binding() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let experience = synthetic_experience(17);

        let first = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/experiences")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(serde_json::to_vec(&experience).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(first.status(), StatusCode::CREATED);
        assert_eq!(body(first).await["inserted"], true);

        let duplicate = service
            .clone()
            .oneshot(
                HttpRequest::post("/v1/experiences")
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(serde_json::to_vec(&experience).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(duplicate.status(), StatusCode::OK);
        assert_eq!(body(duplicate).await["inserted"], false);

        let feedback = synthetic_feedback(&state.registry, &experience);
        let mismatched = service
            .oneshot(
                HttpRequest::post(format!("/v1/experiences/{}/feedback", Uuid::new_v4()))
                    .header(header::AUTHORIZATION, format!("Bearer {token}"))
                    .header(header::CONTENT_TYPE, "application/json")
                    .body(Body::from(serde_json::to_vec(&feedback).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(mismatched.status(), StatusCode::BAD_REQUEST);
        assert_eq!(
            body(mismatched).await["error"],
            "feedback experience_id does not match URL"
        );
    }

    #[tokio::test]
    async fn learning_jobs_claim_complete_and_fail_cycle() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        state
            .registry
            .enqueue_unique_learning_job(
                "knowledge_consolidate_v1",
                "fixture-consolidate",
                json!({"a":1}),
                1.0,
                3,
            )
            .unwrap();
        state
            .registry
            .enqueue_unique_learning_job(
                "source_discover_v1",
                "fixture-discover",
                json!({"b":2}),
                1.0,
                3,
            )
            .unwrap();

        let unmatched = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/learning/jobs:claim",
                json!({"worker":"w1","kinds":["github_search_v1"]}),
            ))
            .await
            .unwrap();
        assert_eq!(unmatched.status(), StatusCode::OK);
        assert!(body(unmatched).await.is_null());

        let claimed = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/learning/jobs:claim",
                json!({"worker":"w1","kinds":["knowledge_consolidate_v1"]}),
            ))
            .await
            .unwrap();
        assert_eq!(claimed.status(), StatusCode::OK);
        let job = body(claimed).await;
        assert_eq!(job["kind"], "knowledge_consolidate_v1");
        assert_eq!(job["status"], "leased");
        assert_eq!(job["lease_owner"], "w1");
        let job_id = job["job_id"].as_str().unwrap().to_owned();

        let double_claim = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/learning/jobs:claim",
                json!({"worker":"w2","kinds":["knowledge_consolidate_v1"]}),
            ))
            .await
            .unwrap();
        assert_eq!(double_claim.status(), StatusCode::OK);
        assert!(body(double_claim).await.is_null());

        let wrong_worker = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/learning/jobs/{job_id}:complete"),
                json!({"worker":"w2"}),
            ))
            .await
            .unwrap();
        assert_eq!(wrong_worker.status(), StatusCode::BAD_REQUEST);

        let completed = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/learning/jobs/{job_id}:complete"),
                json!({"worker":"w1"}),
            ))
            .await
            .unwrap();
        assert_eq!(completed.status(), StatusCode::OK);
        assert_eq!(body(completed).await["status"], "completed");

        let claimed = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/learning/jobs:claim",
                json!({"worker":"w3","kinds":["source_discover_v1"]}),
            ))
            .await
            .unwrap();
        let fail_id = body(claimed).await["job_id"].as_str().unwrap().to_owned();
        let failed = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/learning/jobs/{fail_id}:fail"),
                json!({"worker":"w3","error":"boom"}),
            ))
            .await
            .unwrap();
        assert_eq!(failed.status(), StatusCode::OK);
        assert_eq!(body(failed).await["status"], "retry_or_dead_letter");

        let bogus_operation = service
            .oneshot(authed_post(
                &token,
                &format!("/v1/learning/jobs/{fail_id}:explode"),
                json!({"worker":"w3"}),
            ))
            .await
            .unwrap();
        assert_eq!(bogus_operation.status(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn knowledge_endpoints_handle_missing_cards_and_empty_corpus() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);
        let missing = Uuid::new_v4();
        for path in [
            format!("/v1/knowledge/cards/{missing}"),
            format!("/v1/knowledge/cards/{missing}/history"),
        ] {
            let response = service
                .clone()
                .oneshot(authed_get(&token, &path))
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::NOT_FOUND, "GET {path}");
            assert!(body(response).await["error"].is_string());
        }

        let retrieval = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/knowledge:retrieve",
                json!({"query":"anything","limit":5}),
            ))
            .await
            .unwrap();
        assert_eq!(retrieval.status(), StatusCode::OK);
        assert!(
            body(retrieval).await["items"]
                .as_array()
                .unwrap()
                .is_empty()
        );

        let zero_limit = service
            .oneshot(authed_post(
                &token,
                "/v1/knowledge:retrieve",
                json!({"query":"anything","limit":0}),
            ))
            .await
            .unwrap();
        assert_eq!(zero_limit.status(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn dataset_build_and_draft_round_trip() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);

        let missing_draft = service
            .clone()
            .oneshot(authed_get(&token, "/v1/datasets/meta-controller/draft"))
            .await
            .unwrap();
        assert_eq!(missing_draft.status(), StatusCode::NOT_FOUND);

        let no_actor = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/datasets/meta-controller:build",
                json!({"actor":"  ","reason":"test"}),
            ))
            .await
            .unwrap();
        assert_eq!(no_actor.status(), StatusCode::BAD_REQUEST);

        let bad_kind = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/datasets/unknown-kind:build",
                json!({"actor":"admin","reason":"test"}),
            ))
            .await
            .unwrap();
        assert_eq!(bad_kind.status(), StatusCode::BAD_REQUEST);

        let no_operation = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/datasets/meta-controller",
                json!({"actor":"admin","reason":"test"}),
            ))
            .await
            .unwrap();
        assert_eq!(no_operation.status(), StatusCode::BAD_REQUEST);

        let built = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/datasets/meta-controller:build",
                json!({"actor":"admin","reason":"coverage build"}),
            ))
            .await
            .unwrap();
        assert_eq!(built.status(), StatusCode::CREATED);
        let build = body(built).await;
        let build_id = build["build_id"].as_str().unwrap();

        let draft = service
            .clone()
            .oneshot(authed_get(&token, "/v1/datasets/meta-controller/draft"))
            .await
            .unwrap();
        assert_eq!(draft.status(), StatusCode::OK);
        let draft = body(draft).await;
        assert_eq!(draft["build"]["build_id"], build_id);
        assert_eq!(draft["draft"]["build_id"], build_id);

        let report = service
            .oneshot(authed_get(
                &token,
                &format!("/v1/dataset-builds/{build_id}/quality-report"),
            ))
            .await
            .unwrap();
        assert_eq!(report.status(), StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn source_policy_and_topic_round_trip_with_validation() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);

        let created = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/source-policies",
                json!({
                    "name":"Example RSS",
                    "kind":"rss_atom",
                    "base_url":"https://example.com/feed.xml",
                    "access_mode":"public",
                    "allowed_domains":["example.com"]
                }),
            ))
            .await
            .unwrap();
        assert_eq!(created.status(), StatusCode::CREATED);
        let policy = body(created).await;
        let policy_id = policy["policy_id"].as_str().unwrap().to_owned();

        let listed = service
            .clone()
            .oneshot(authed_get(&token, "/v1/source-policies"))
            .await
            .unwrap();
        assert_eq!(listed.status(), StatusCode::OK);
        assert!(
            body(listed)
                .await
                .as_array()
                .unwrap()
                .iter()
                .any(|policy| policy["policy_id"] == policy_id)
        );

        let topic = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/topics",
                json!({
                    "name":"Agent workflows",
                    "query":"agent workflow",
                    "keywords":["agent"],
                    "source_policy_ids":[policy_id],
                    "refresh_seconds":60
                }),
            ))
            .await
            .unwrap();
        assert_eq!(topic.status(), StatusCode::CREATED);
        assert_eq!(body(topic).await["name"], "Agent workflows");

        let listed = service
            .clone()
            .oneshot(authed_get(&token, "/v1/topics"))
            .await
            .unwrap();
        assert_eq!(listed.status(), StatusCode::OK);
        assert_eq!(body(listed).await.as_array().unwrap().len(), 1);

        let unknown_source = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/topics",
                json!({
                    "name":"Broken",
                    "query":"x",
                    "source_policy_ids":[Uuid::new_v4()]
                }),
            ))
            .await
            .unwrap();
        assert_eq!(unknown_source.status(), StatusCode::BAD_REQUEST);
        assert!(
            body(unknown_source).await["error"]
                .as_str()
                .unwrap()
                .contains("does not exist")
        );

        let bad_tombstone_id = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/source-policies/not-a-uuid:tombstone",
                json!({"actor":"admin","reason":"x"}),
            ))
            .await
            .unwrap();
        assert_eq!(bad_tombstone_id.status(), StatusCode::BAD_REQUEST);

        let unknown_operation = service
            .oneshot(authed_post(
                &token,
                "/v1/source-policies/anything:shuffle",
                json!({"actor":"admin","reason":"x"}),
            ))
            .await
            .unwrap();
        assert_eq!(unknown_operation.status(), StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn connector_sync_validates_policy_state() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);

        let malformed = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/connectors/not-a-uuid:sync",
                json!({}),
            ))
            .await
            .unwrap();
        assert_eq!(malformed.status(), StatusCode::BAD_REQUEST);

        let missing = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/connectors/{}:sync", Uuid::new_v4()),
                json!({}),
            ))
            .await
            .unwrap();
        assert_eq!(missing.status(), StatusCode::NOT_FOUND);

        let created = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/source-policies",
                json!({
                    "name":"Disabled RSS",
                    "kind":"rss_atom",
                    "base_url":"https://example.com/off",
                    "access_mode":"public",
                    "allowed_domains":["example.com"],
                    "enabled":false
                }),
            ))
            .await
            .unwrap();
        assert_eq!(created.status(), StatusCode::CREATED);
        let policy_id = body(created).await["policy_id"]
            .as_str()
            .unwrap()
            .to_owned();

        let conflict = service
            .oneshot(authed_post(
                &token,
                &format!("/v1/connectors/{policy_id}:sync"),
                json!({}),
            ))
            .await
            .unwrap();
        assert_eq!(conflict.status(), StatusCode::CONFLICT);
        assert_eq!(body(conflict).await["error"], "source policy is disabled");
    }

    #[tokio::test]
    async fn admin_console_serves_static_assets_with_security_headers() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let csrf = state.admin_csrf.clone();
        let service = app(state);

        for (path, content_type) in [
            ("/admin", "text/html; charset=utf-8"),
            ("/admin/app.js", "text/javascript; charset=utf-8"),
            ("/admin/style.css", "text/css; charset=utf-8"),
        ] {
            let response = service
                .clone()
                .oneshot(authed_get(&token, path))
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::OK, "GET {path}");
            assert_eq!(
                response.headers().get(header::CONTENT_TYPE).unwrap(),
                content_type
            );
            assert!(
                response
                    .headers()
                    .contains_key(header::CONTENT_SECURITY_POLICY)
            );
            assert_eq!(
                response
                    .headers()
                    .get(header::X_CONTENT_TYPE_OPTIONS)
                    .unwrap(),
                "nosniff"
            );
        }

        let index = service
            .clone()
            .oneshot(authed_get(&token, "/admin"))
            .await
            .unwrap();
        let html = to_bytes(index.into_body(), usize::MAX).await.unwrap();
        let html = String::from_utf8(html.to_vec()).unwrap();
        assert!(html.contains(&csrf));
        assert!(!html.contains("__CEREBELLUM_CSRF__"));

        let unauthenticated = service
            .oneshot(HttpRequest::get("/admin").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(unauthenticated.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn list_endpoints_honor_limit_parameters() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        for index in 0..3 {
            state
                .registry
                .enqueue_unique_learning_job(
                    "knowledge_consolidate_v1",
                    &format!("fixture-limit-{index}"),
                    json!({"i":index}),
                    1.0,
                    3,
                )
                .unwrap();
        }

        let limited = service
            .clone()
            .oneshot(authed_get(&token, "/v1/learning/jobs?limit=1"))
            .await
            .unwrap();
        assert_eq!(limited.status(), StatusCode::OK);
        assert_eq!(body(limited).await.as_array().unwrap().len(), 1);

        let uncapped = service
            .clone()
            .oneshot(authed_get(&token, "/v1/learning/jobs?limit=100000"))
            .await
            .unwrap();
        assert_eq!(uncapped.status(), StatusCode::OK);
        assert_eq!(body(uncapped).await.as_array().unwrap().len(), 3);

        let zero = service
            .clone()
            .oneshot(authed_get(&token, "/v1/knowledge/cards?limit=0"))
            .await
            .unwrap();
        assert_eq!(zero.status(), StatusCode::OK);
        assert!(body(zero).await.as_array().unwrap().is_empty());

        let documents = service
            .oneshot(authed_get(&token, "/v1/documents?limit=5"))
            .await
            .unwrap();
        assert_eq!(documents.status(), StatusCode::OK);
        assert!(body(documents).await.as_array().unwrap().is_empty());
    }

    #[tokio::test]
    async fn read_only_status_and_list_endpoints_respond() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);
        for path in [
            "/v1/learning/status",
            "/v1/curricula",
            "/v1/training-candidates",
            "/v1/meta/status",
            "/v1/quality/status",
            "/v1/quality/assessments",
            "/v1/quality/model-versions",
            "/v1/synthetic-candidates",
            "/v1/expert-taxonomy",
            "/v1/expert-adapters",
            "/v1/expert-dataset-views",
            "/v1/dataset-snapshots",
            "/v1/training-runs",
            "/v1/meta/training-candidates",
            "/v1/meta-models",
            "/v1/acquisition/status",
            "/v1/events",
        ] {
            let response = service
                .clone()
                .oneshot(authed_get(&token, path))
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::OK, "GET {path}");
        }

        let training_config = service
            .clone()
            .oneshot(authed_get(&token, "/v1/training-config"))
            .await
            .unwrap();
        assert_eq!(training_config.status(), StatusCode::OK);
        assert_eq!(body(training_config).await["enabled"], false);

        let missing = Uuid::new_v4();
        for path in [
            format!("/v1/optimization-runs/{missing}"),
            format!("/v1/optimization-runs/{missing}/patches"),
            format!("/v1/acquisition/results/{missing}"),
            format!("/v1/meta-training/results/{missing}"),
            format!("/v1/dataset-builds/{missing}/quality-report"),
            format!("/v1/events/{missing}"),
            format!("/v1/objects/{}", "0".repeat(64)),
            format!("/v1/training-runs/{missing}"),
        ] {
            let response = service
                .clone()
                .oneshot(authed_get(&token, &path))
                .await
                .unwrap();
            assert_eq!(response.status(), StatusCode::NOT_FOUND, "GET {path}");
        }

        let malformed = service
            .oneshot(authed_get(
                &token,
                "/v1/expert-adapters/no-version-separator",
            ))
            .await
            .unwrap();
        assert_eq!(malformed.status(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn experts_route_rejects_unknown_available_expert() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let response = app(state)
            .oneshot(authed_post(
                &token,
                "/v1/experts:route",
                json!({
                    "task_kind":"relevance",
                    "input":{"query":"agent"},
                    "available_expert_ids":["no-such-expert"]
                }),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        assert_eq!(
            body(response).await["error"],
            "available expert list contains an unknown expert"
        );
    }

    #[tokio::test]
    async fn quality_backfill_requires_configured_quality_model() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let response = app(state)
            .oneshot(authed_post(
                &token,
                "/v1/quality:backfill",
                json!({"actor":"admin","reason":"coverage"}),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::FORBIDDEN);
        assert_eq!(
            body(response).await["error"],
            "local quality model is disabled"
        );
    }

    #[tokio::test]
    async fn training_run_creation_requires_autodl_configuration() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let response = app(state)
            .oneshot(authed_post(
                &token,
                "/v1/training-runs",
                json!({
                    "snapshot_id":Uuid::new_v4(),
                    "base_model":{
                        "model_id":"example/model",
                        "revision":"immutable-revision",
                        "sha256":"a".repeat(64)
                    },
                    "gpu_spec":"approved-24g",
                    "administrator":"admin",
                    "reason":"coverage",
                    "budget":{"max_hourly_cny":1.0,"max_total_cny":1.0,"max_wall_seconds":600}
                }),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::FORBIDDEN);
        assert_eq!(
            body(response).await["error"],
            "AutoDL training orchestration is disabled"
        );
    }

    #[tokio::test]
    async fn curriculum_create_list_and_validation() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state);

        let empty_topic = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/curricula",
                json!({"trigger":"manual","topic":"  ","query":"q","policy":{}}),
            ))
            .await
            .unwrap();
        assert_eq!(empty_topic.status(), StatusCode::BAD_REQUEST);

        let created = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/curricula",
                json!({
                    "trigger":"manual",
                    "topic":"retrieval quality",
                    "query":"agent retrieval evaluation",
                    "policy":{}
                }),
            ))
            .await
            .unwrap();
        assert_eq!(created.status(), StatusCode::CREATED);
        let plan = body(created).await;
        assert_eq!(plan["topic"], "retrieval quality");
        assert_eq!(plan["status"], "scheduled");

        let listed = service
            .oneshot(authed_get(&token, "/v1/curricula"))
            .await
            .unwrap();
        assert_eq!(listed.status(), StatusCode::OK);
        let plans = body(listed).await;
        let plans = plans.as_array().unwrap();
        assert_eq!(plans.len(), 1);
        assert_eq!(plans[0]["query"], "agent retrieval evaluation");
    }

    #[tokio::test]
    async fn acquisition_reservations_follow_job_lease_lifecycle() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());

        let no_lease = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/acquisition/browser-budget:reserve",
                json!({"job_id":Uuid::new_v4(),"worker":"w1"}),
            ))
            .await
            .unwrap();
        assert_eq!(no_lease.status(), StatusCode::BAD_REQUEST);

        let bad_ordinal = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/acquisition/source-rate:reserve",
                json!({"job_id":Uuid::new_v4(),"worker":"w1","ordinal":16}),
            ))
            .await
            .unwrap();
        assert_eq!(bad_ordinal.status(), StatusCode::BAD_REQUEST);

        let created = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/source-policies",
                json!({
                    "name":"Reservation RSS",
                    "kind":"rss_atom",
                    "base_url":"https://example.com/feed.xml",
                    "access_mode":"public",
                    "allowed_domains":["example.com"]
                }),
            ))
            .await
            .unwrap();
        let policy_id = body(created).await["policy_id"]
            .as_str()
            .unwrap()
            .to_owned();
        let topic = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/topics",
                json!({
                    "name":"Reservation topic",
                    "query":"agent workflow",
                    "source_policy_ids":[policy_id],
                    "refresh_seconds":60
                }),
            ))
            .await
            .unwrap();
        let topic_id = body(topic).await["topic_id"].as_str().unwrap().to_owned();

        state
            .registry
            .enqueue_unique_learning_job(
                "document_acquire_v1",
                "fixture-acquire",
                json!({"topic_ids":[topic_id],"source_policy_id":policy_id}),
                1.0,
                3,
            )
            .unwrap();
        let claimed = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/learning/jobs:claim",
                json!({"worker":"w1","kinds":["document_acquire_v1"]}),
            ))
            .await
            .unwrap();
        let job_id = body(claimed).await["job_id"].as_str().unwrap().to_owned();

        let reserved = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/acquisition/browser-budget:reserve",
                json!({"job_id":job_id,"worker":"w1"}),
            ))
            .await
            .unwrap();
        assert_eq!(reserved.status(), StatusCode::OK);
        assert_eq!(body(reserved).await["newly_reserved"], true);

        let idempotent = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/acquisition/browser-budget:reserve",
                json!({"job_id":job_id,"worker":"w1"}),
            ))
            .await
            .unwrap();
        assert_eq!(idempotent.status(), StatusCode::OK);
        assert_eq!(body(idempotent).await["newly_reserved"], false);

        let rate = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/acquisition/source-rate:reserve",
                json!({"job_id":job_id,"worker":"w1","ordinal":3}),
            ))
            .await
            .unwrap();
        assert_eq!(rate.status(), StatusCode::OK);
        assert_eq!(body(rate).await["newly_reserved"], true);

        let rate_repeat = service
            .oneshot(authed_post(
                &token,
                "/v1/acquisition/source-rate:reserve",
                json!({"job_id":job_id,"worker":"w1","ordinal":3}),
            ))
            .await
            .unwrap();
        assert_eq!(rate_repeat.status(), StatusCode::OK);
        assert_eq!(body(rate_repeat).await["newly_reserved"], false);
    }
    #[test]
    fn store_errors_never_leak_sql_and_domain_errors_keep_their_status() {
        let sqlite = map_store_err(anyhow::anyhow!(rusqlite::Error::SqliteFailure(
            rusqlite::ffi::Error::new(19),
            Some("UNIQUE constraint failed: skills.id".into()),
        )));
        assert_eq!(sqlite.status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(sqlite.message, "internal store error");
        assert!(!sqlite.message.contains("UNIQUE"));

        // The blanket From path is generic too.
        let blanket = AppError::from(anyhow::anyhow!(rusqlite::Error::SqliteFailure(
            rusqlite::ffi::Error::new(19),
            Some("UNIQUE constraint failed: skills.id".into()),
        )));
        assert_eq!(blanket.status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(blanket.message, "internal store error");

        let not_found = map_store_err(anyhow::anyhow!("workflow not found"));
        assert_eq!(not_found.status, StatusCode::NOT_FOUND);
        assert_eq!(not_found.message, "workflow not found");

        let invalid = map_store_err(anyhow::anyhow!("manifest invalid"));
        assert_eq!(invalid.status, StatusCode::BAD_REQUEST);
        assert_eq!(invalid.message, "manifest invalid");

        let unknown = map_store_err(anyhow::anyhow!("connection reset by peer"));
        assert_eq!(unknown.status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(unknown.message, "internal store error");
    }

    fn ready_candidate(registry: &Registry, key: &str) -> Uuid {
        let candidate_id = Uuid::new_v4();
        registry
            .save_training_candidate(&TrainingCandidate {
                candidate_id,
                dataset_hash: "a".repeat(64),
                manifest_hash: format!("{:x}", Sha256::digest(key.as_bytes())),
                decision_count: cerebellum_core::MIN_ROUTING_DECISIONS,
                paired_eval_count: cerebellum_core::MIN_PAIRED_EVALS,
                status: TrainingCandidateStatus::ReadyForTraining,
                repository_split_count: 1,
                task_family_split_count: 1,
                trainer_enabled: false,
                created_at: Utc::now(),
            })
            .unwrap();
        candidate_id
    }

    fn seed_model(registry: &Registry, model_id: &str, version: &str) {
        let candidate_id = ready_candidate(registry, &format!("{model_id}@{version}"));
        let now = Utc::now();
        registry
            .register_model(&ModelVersion {
                model_id: model_id.into(),
                version: version.into(),
                artifact_hash: "a".repeat(64),
                training_candidate_id: candidate_id,
                evidence: ModelEvidence {
                    task_success_uplift: 0.1,
                    gate_violation_delta: 0,
                    latency_improvement: 0.3,
                    memory_improvement: 0.0,
                },
                status: ModelStatus::Candidate,
                reviewed_by: None,
                review_reason: None,
                created_at: now,
                updated_at: now,
            })
            .unwrap();
    }

    #[tokio::test]
    async fn review_model_approve_reject_and_bad_operations() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        seed_model(&state.registry, "m", "1.0.0");
        seed_model(&state.registry, "m", "2.0.0");
        let review = || json!({"actor":"admin","reason":"fixture"});

        let approved = service
            .clone()
            .oneshot(authed_post(&token, "/v1/models/m@1.0.0:approve", review()))
            .await
            .unwrap();
        assert_eq!(approved.status(), StatusCode::OK);
        assert_eq!(body(approved).await["status"], "active");

        let rejected = service
            .clone()
            .oneshot(authed_post(&token, "/v1/models/m@2.0.0:reject", review()))
            .await
            .unwrap();
        assert_eq!(rejected.status(), StatusCode::OK);
        assert_eq!(body(rejected).await["status"], "rejected");

        let unknown_action = service
            .clone()
            .oneshot(authed_post(&token, "/v1/models/m@1.0.0:explode", review()))
            .await
            .unwrap();
        assert_eq!(unknown_action.status(), StatusCode::BAD_REQUEST);

        let bad_subject = service
            .oneshot(authed_post(
                &token,
                "/v1/models/no-separator:approve",
                review(),
            ))
            .await
            .unwrap();
        assert_eq!(bad_subject.status(), StatusCode::BAD_REQUEST);
        assert_eq!(
            body(bad_subject).await["error"],
            "model id must be MODEL@VERSION"
        );
    }

    fn seed_optimization_run(registry: &Registry) -> Uuid {
        let content = b"---\nname: evolver-verify\ndescription: verify claims\n---\nVerify with fresh tests.\n";
        let manifest = SkillManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: "evolver-verify".into(),
            version: "1.0.0".into(),
            description: "Verify completion claims".into(),
            triggers: vec![],
            input_schema: json!({"type":"object"}),
            output_schema: json!({"type":"object"}),
            dependencies: vec![],
            permissions: vec![],
            risk_level: RiskLevel::Low,
            compatibility: vec!["coding-agent".into()],
            source: SourceRef {
                repository_url: "https://github.com/example/evolver".into(),
                commit_sha: "c".repeat(40),
                path: "skills/verify/SKILL.md".into(),
                content_hash: format!("{:x}", Sha256::digest(content)),
                license: "NOASSERTION".into(),
                collected_at: Utc::now(),
            },
            evidence: EvidenceCard::default(),
            status: SkillLifecycle::Quarantined,
            legacy_hint: None,
            training_eligible: false,
            lineage: None,
        };
        registry.upsert_skill(&manifest, content).unwrap();
        let mut tasks = Vec::new();
        for (split, families) in [
            (cerebellum_core::BenchmarkSplit::Train, 10),
            (cerebellum_core::BenchmarkSplit::Validation, 5),
            (cerebellum_core::BenchmarkSplit::Holdout, 5),
        ] {
            for family in 0..families {
                for variant in 1..=3 {
                    tasks.push(cerebellum_core::CodingBenchmarkTask {
                        task_id: format!("{split:?}-{family}-{variant}").to_ascii_lowercase(),
                        template_family: format!("{split:?}-{family}").to_ascii_lowercase(),
                        variant,
                        split,
                        bundle_hash: "b".repeat(64),
                        test_command: "pytest -q".into(),
                        expected_status: cerebellum_core::ExpectedTaskStatus::Completed,
                    });
                }
            }
        }
        let benchmark = cerebellum_core::CodingBenchmarkManifest {
            schema_version: SCHEMA_VERSION.into(),
            benchmark_id: "verify-python".into(),
            version: "1.0.0".into(),
            container_image: format!("python@sha256:{}", "a".repeat(64)),
            tasks,
            scoring: cerebellum_core::OptimizationScoringPolicy::default(),
            created_at: Utc::now(),
        };
        let manifest_hash = registry
            .put_object(&serde_json::to_vec(&benchmark).unwrap())
            .unwrap();
        let bundle_hash = registry.put_object(b"aggregate fixture").unwrap();
        let run_id = registry
            .create_optimization_run(&cerebellum_core::CreateOptimizationRunRequest {
                skill_id: manifest.id.clone(),
                skill_version: manifest.version.clone(),
                benchmark_manifest_hash: manifest_hash,
                benchmark_bundle_hash: bundle_hash,
                container_image_digest: benchmark.container_image,
                target_model: "target".into(),
                optimizer_model: "optimizer".into(),
                budget: cerebellum_core::OptimizationBudget::default(),
            })
            .unwrap()
            .run_id;
        let mut run = registry.get_optimization_run(run_id).unwrap().unwrap();
        run.status = cerebellum_core::OptimizationRunStatus::Validated;
        registry
            .lock_conn()
            .execute(
                "UPDATE optimization_runs SET status='validated',run_json=?2 WHERE id=?1",
                rusqlite::params![run_id.to_string(), serde_json::to_string(&run).unwrap()],
            )
            .unwrap();
        run_id
    }

    #[tokio::test]
    async fn review_optimization_reject_and_gate_errors() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let run_id = seed_optimization_run(&state.registry);
        let review = || json!({"actor":"human","reason":"fixture"});

        let rejected = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/optimization-runs/{run_id}:reject"),
                review(),
            ))
            .await
            .unwrap();
        assert_eq!(rejected.status(), StatusCode::OK);
        assert_eq!(body(rejected).await["run"]["status"], "rejected");

        // Approving a run that is not validated fails closed.
        let premature = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/optimization-runs/{run_id}:approve"),
                review(),
            ))
            .await
            .unwrap();
        assert!(premature.status().is_client_error() || premature.status().is_server_error());

        let unknown = service
            .oneshot(authed_post(
                &token,
                &format!("/v1/optimization-runs/{run_id}:explode"),
                review(),
            ))
            .await
            .unwrap();
        assert_eq!(unknown.status(), StatusCode::BAD_REQUEST);
    }

    fn seed_quality_endpoint(registry: &Registry, model_id: &str) -> Uuid {
        let now = Utc::now();
        let version = ModelEndpointVersion {
            schema_version: SCHEMA_VERSION.into(),
            endpoint_version_id: Uuid::new_v4(),
            provider: "local".into(),
            model_id: model_id.into(),
            system_fingerprint: "fp".into(),
            prompt_version: "v1".into(),
            schema_hash: "a".repeat(64),
            status: ModelEndpointStatus::PendingApproval,
            metrics: ModelCalibrationMetrics::default(),
            approved_by: None,
            approval_reason: None,
            first_seen_at: now,
            updated_at: now,
        };
        let id = version.endpoint_version_id;
        registry
            .lock_conn()
            .execute(
                "INSERT INTO quality_model_versions(id,provider,model_id,system_fingerprint,prompt_version,status,version_json,updated_at)
                 VALUES(?1,?2,?3,?4,?5,'pending_approval',?6,?7)",
                rusqlite::params![
                    id.to_string(),
                    version.provider,
                    version.model_id,
                    version.system_fingerprint,
                    version.prompt_version,
                    serde_json::to_string(&version).unwrap(),
                    now.to_rfc3339()
                ],
            )
            .unwrap();
        id
    }

    #[tokio::test]
    async fn review_quality_model_version_approve_and_reject() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let approve_id = seed_quality_endpoint(&state.registry, "model-a");
        let reject_id = seed_quality_endpoint(&state.registry, "model-b");
        let review = || json!({"actor":"admin","reason":"fixture"});

        let approved = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/quality/model-versions/{approve_id}:approve"),
                review(),
            ))
            .await
            .unwrap();
        assert_eq!(approved.status(), StatusCode::OK);
        assert_eq!(body(approved).await["status"], "active");

        let rejected = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/quality/model-versions/{reject_id}:reject"),
                review(),
            ))
            .await
            .unwrap();
        assert_eq!(rejected.status(), StatusCode::OK);
        assert_eq!(body(rejected).await["status"], "rejected");

        let unknown = service
            .oneshot(authed_post(
                &token,
                &format!("/v1/quality/model-versions/{approve_id}:explode"),
                review(),
            ))
            .await
            .unwrap();
        assert_eq!(unknown.status(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn synthetic_verify_endpoint_enforces_objective_evidence() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        builtins::seed(&state.registry).unwrap();
        let now = Utc::now();
        let candidate = SyntheticTrainingCandidate {
            schema_version: SCHEMA_VERSION.into(),
            candidate_id: Uuid::new_v4(),
            parent_subject_kind: QualitySubjectKind::MetaDecision,
            parent_subject_id: Uuid::new_v4().to_string(),
            parent_hash: "a".repeat(64),
            task_kind: cerebellum_core::MetaTaskKind::SkillWorkflowRouting,
            transformation: cerebellum_core::SyntheticTransformation::CounterfactualPair,
            input: json!({"task":"route"}),
            output: json!({"workflow_id":"bugfix"}),
            content_hash: "b".repeat(64),
            evidence_refs: vec!["parent:objective".into()],
            source_license: "policy-qualified-parent".into(),
            verification_kind: cerebellum_core::SyntheticVerificationKind::ExecutableTest,
            objective_verified: false,
            model_assessment_id: Uuid::new_v4(),
            generation_model_id: "generator-v1".into(),
            generation_system_fingerprint: "fingerprint".into(),
            generation_prompt_version: "v1".into(),
            generation_prompt_hash: "c".repeat(64),
            generation_usage: cerebellum_core::ModelTokenUsage::default(),
            generation_estimated_cost_microusd: 0,
            generation_depth: 1,
            status: SyntheticCandidateStatus::Quarantined,
            reviewed_by: None,
            review_reason: None,
            created_at: now,
            updated_at: now,
        };
        state.registry.save_synthetic_candidate(&candidate).unwrap();
        let eval_id = Uuid::new_v4();
        state
            .registry
            .record_paired_eval(&PairedEvalRecord {
                eval_id,
                skill_id: "builtin.inspect-repository".into(),
                skill_version: "1.0.0".into(),
                task_family: "synthetic".into(),
                repository_digest: "d".repeat(64),
                environment_digest: "e".repeat(64),
                model_id: "model".into(),
                seed: 7,
                budget: Value::Null,
                baseline_success: false,
                treatment_success: true,
                baseline_gate_violations: 0,
                treatment_gate_violations: 0,
                baseline_score: 0.2,
                treatment_score: 0.9,
                baseline_latency_ms: 1_200,
                treatment_latency_ms: 900,
                metadata: json!({"candidate_id": candidate.candidate_id.to_string()}),
            })
            .unwrap();
        let verify = |paired_eval_id| json!({"actor":"admin","reason":"objective fixture","paired_eval_id":paired_eval_id});

        // Executable candidate cannot be approved before objective verification.
        let premature = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!(
                    "/v1/synthetic-candidates/{}:approve",
                    candidate.candidate_id
                ),
                json!({"actor":"admin","reason":"try"}),
            ))
            .await
            .unwrap();
        assert_eq!(premature.status(), StatusCode::BAD_REQUEST);

        // A forged paired_eval_id is rejected.
        let forged = service
            .clone()
            .oneshot(authed_post(
                &token,
                &format!("/v1/synthetic-candidates/{}:verify", candidate.candidate_id),
                verify(Uuid::new_v4()),
            ))
            .await
            .unwrap();
        assert_eq!(forged.status(), StatusCode::NOT_FOUND);

        // A real passing evaluation verifies the candidate.
        let verified = service
            .oneshot(authed_post(
                &token,
                &format!("/v1/synthetic-candidates/{}:verify", candidate.candidate_id),
                verify(eval_id),
            ))
            .await
            .unwrap();
        assert_eq!(verified.status(), StatusCode::OK);
        assert_eq!(body(verified).await["status"], "verified");
    }
    fn seed_expert_adapter(registry: &Registry, expert: &str, version: &str) {
        let now = Utc::now();
        let run_id = Uuid::new_v4();
        let snapshot_id = Uuid::new_v4();
        let snapshot = DatasetSnapshot {
            schema_version: SCHEMA_VERSION.into(),
            snapshot_id,
            kind: "meta-controller".into(),
            build_id: Uuid::new_v4(),
            bundle_hash: "a".repeat(64),
            manifest_hash: "b".repeat(64),
            decision_count: 0,
            replay_eval_count: 0,
            split_stats: cerebellum_core::DatasetSplitStats::default(),
            eligibility: cerebellum_core::DatasetEligibilityReport::default(),
            expert_view_id: None,
            expert_manifest_hash: None,
            expert_taxonomy_hash: None,
            quality_report_id: None,
            quality_report_hash: None,
            created_by: "admin".into(),
            reason: "fixture".into(),
            legacy_candidate_id: None,
            created_at: now,
        };
        let record = DatasetSnapshotRecord {
            snapshot,
            revocation: None,
        };
        registry
            .lock_conn()
            .execute(
                "INSERT INTO dataset_snapshots(id,kind,build_id,bundle_hash,manifest_hash,snapshot_json,created_at)
                 VALUES(?1,?2,?3,?4,?5,?6,?7)",
                rusqlite::params![
                    snapshot_id.to_string(),
                    "meta-controller",
                    record.snapshot.build_id.to_string(),
                    record.snapshot.bundle_hash,
                    record.snapshot.manifest_hash,
                    serde_json::to_string(&record).unwrap(),
                    now.to_rfc3339()
                ],
            )
            .unwrap();
        let run = TrainingRun {
            schema_version: SCHEMA_VERSION.into(),
            run_id,
            snapshot_id,
            snapshot_bundle_hash: "a".repeat(64),
            snapshot_manifest_hash: "b".repeat(64),
            training_bundle_hash: None,
            training_manifest_hash: None,
            expert_plan: None,
            base_model: BaseModelPin {
                model_id: "base".into(),
                revision: "r1".into(),
                sha256: "c".repeat(64),
            },
            qlora: QloraConfig::default(),
            provider: "autodl".into(),
            application_uuid: "app".into(),
            application_version: "v1".into(),
            requested_gpu_spec: "none".into(),
            selected_gpu_spec: None,
            administrator: "admin".into(),
            reason: "fixture".into(),
            budget: TrainingBudget {
                max_hourly_cny: 10.0,
                max_total_cny: 100.0,
                max_wall_seconds: 21_600,
            },
            status: TrainingRunStatus::Completed,
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
        registry
            .lock_conn()
            .execute(
                "INSERT INTO training_runs(id,snapshot_id,status,run_json,created_at,updated_at)
                 VALUES(?1,?2,'completed',?3,?4,?4)",
                rusqlite::params![
                    run_id.to_string(),
                    run.snapshot_id.to_string(),
                    serde_json::to_string(&run).unwrap(),
                    now.to_rfc3339()
                ],
            )
            .unwrap();
        let adapter = ExpertAdapterVersion {
            schema_version: SCHEMA_VERSION.into(),
            adapter_id: Uuid::new_v4(),
            expert_id: expert.into(),
            version: version.into(),
            bundle_hash: "a".repeat(64),
            artifact_path: "adapters/a.safetensors".into(),
            artifact_hash: "b".repeat(64),
            byte_length: 16,
            training_records: 1,
            base_model: BaseModelPin {
                model_id: "base".into(),
                revision: "r1".into(),
                sha256: "c".repeat(64),
            },
            training_run_id: run_id,
            snapshot_id: Uuid::new_v4(),
            expert_view_id: Uuid::new_v4(),
            taxonomy_hash: crate::experts::builtin_expert_taxonomy_hash(),
            status: ExpertAdapterStatus::Candidate,
            metrics: None,
            previous_active: None,
            created_at: now,
            updated_at: now,
        };
        registry
            .lock_conn()
            .execute(
                "INSERT INTO expert_adapter_versions(adapter_id,expert_id,version,status,training_run_id,bundle_hash,artifact_hash,adapter_json,updated_at)
                 VALUES(?1,?2,?3,'candidate',?4,?5,?6,?7,?8)",
                rusqlite::params![
                    adapter.adapter_id.to_string(),
                    adapter.expert_id,
                    adapter.version,
                    adapter.training_run_id.to_string(),
                    adapter.bundle_hash,
                    adapter.artifact_hash,
                    serde_json::to_string(&adapter).unwrap(),
                    now.to_rfc3339()
                ],
            )
            .unwrap();
    }

    #[tokio::test]
    async fn expert_adapter_operate_shadow_and_bad_operations() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        seed_expert_adapter(&state.registry, "router", "1.0.0");
        let request =
            || json!({"actor":"admin","reason":"objective replay","metrics":metrics_value()});
        fn metrics_value() -> Value {
            json!({
                "evaluation_count":200,"canary_decisions":0,"canary_duration_seconds":0,
                "old_task_retention":0.99,"task_success_delta":0.02,
                "negative_transfer_rate_delta":-0.01,"routing_accuracy_delta":0.01,
                "policy_violations":0,"injection_regression":false,
            })
        }

        let shadowed = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/expert-adapters/router@1.0.0:shadow",
                request(),
            ))
            .await
            .unwrap();
        assert_eq!(shadowed.status(), StatusCode::OK);
        assert_eq!(body(shadowed).await["status"], "shadow");

        let unknown = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/expert-adapters/router@1.0.0:explode",
                request(),
            ))
            .await
            .unwrap();
        assert_eq!(unknown.status(), StatusCode::BAD_REQUEST);

        let bad_subject = service
            .oneshot(authed_post(
                &token,
                "/v1/expert-adapters/no-separator:shadow",
                request(),
            ))
            .await
            .unwrap();
        assert_eq!(bad_subject.status(), StatusCode::BAD_REQUEST);
        assert_eq!(
            body(bad_subject).await["error"],
            "expert adapter must be EXPERT@VERSION"
        );
    }

    #[tokio::test]
    async fn expert_adapter_eval_reports_endpoint_and_gated_operate() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        seed_expert_adapter(&state.registry, "router", "1.0.0");
        let adapter = state
            .registry
            .get_expert_adapter("router", "1.0.0")
            .unwrap()
            .unwrap();
        let results = b"{\"set\":\"role\"}\n".to_vec();
        let report = ExpertAdapterEvalReport {
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
                .map(|name| EvalSetSummary {
                    set_name: name.into(),
                    record_count: 50,
                    records_sha256: "d".repeat(64),
                })
                .collect(),
            metrics: ExpertAdapterMetrics {
                evaluation_count: 200,
                canary_decisions: 0,
                canary_duration_seconds: 0,
                old_task_retention: 0.99,
                task_success_delta: 0.02,
                negative_transfer_rate_delta: -0.01,
                routing_accuracy_delta: 0.01,
                policy_violations: 0,
                injection_regression: false,
            },
            metacognition: None,
            task_success_delta_ci95_low: 0.01,
            routing_accuracy_delta_ci95_low: 0.005,
            injection_probe_base_violations: 0,
            injection_probe_adapted_violations: 0,
            results_object_hash: format!("{:x}", sha2::Sha256::digest(&results)),
            harness_version: "adapter-eval/1".into(),
            llama_cpp_version: "test-double".into(),
            started_at: Utc::now(),
            finished_at: Utc::now(),
            created_at: Utc::now(),
        };
        let report_id = report.report_id;
        state
            .registry
            .record_expert_adapter_eval_report(&report, &results)
            .unwrap();

        let listed = service
            .clone()
            .oneshot(authed_get(
                &token,
                "/v1/expert-adapter-eval-reports?expert_id=router&version=1.0.0",
            ))
            .await
            .unwrap();
        assert_eq!(listed.status(), StatusCode::OK);
        let reports = body(listed).await;
        assert_eq!(reports.as_array().unwrap().len(), 1);
        assert_eq!(reports[0]["report_id"], json!(report_id.to_string()));

        // Canary via the API now requires the recorded report reference.
        let shadowed = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/expert-adapters/router@1.0.0:shadow",
                json!({"actor":"admin","reason":"review"}),
            ))
            .await
            .unwrap();
        assert_eq!(shadowed.status(), StatusCode::OK);
        let without_evidence = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/expert-adapters/router@1.0.0:canary",
                json!({"actor":"admin","reason":"gate"}),
            ))
            .await
            .unwrap();
        assert_eq!(without_evidence.status(), StatusCode::BAD_REQUEST);
        let with_evidence = service
            .clone()
            .oneshot(authed_post(
                &token,
                "/v1/expert-adapters/router@1.0.0:canary",
                json!({"actor":"admin","reason":"gate","eval_report_id":report_id}),
            ))
            .await
            .unwrap();
        assert_eq!(with_evidence.status(), StatusCode::OK);
        assert_eq!(body(with_evidence).await["status"], "canary");
    }

    // ---- metacognition runtime hook (M5) ---------------------------------

    use crate::quality::{StructuredRequest, StructuredResponse};
    use cerebellum_core::ModelTokenUsage;

    struct FakeMetacogModel {
        value: Value,
        calls: std::sync::atomic::AtomicUsize,
        fail: bool,
    }

    #[async_trait::async_trait]
    impl StructuredModelClient for FakeMetacogModel {
        async fn complete(&self, _request: &StructuredRequest) -> Result<StructuredResponse> {
            self.calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            if self.fail {
                anyhow::bail!("fake model failure");
            }
            Ok(StructuredResponse {
                model_id: "fake-metacog".into(),
                system_fingerprint: "fp".into(),
                value: self.value.clone(),
                raw_content: self.value.to_string(),
                usage: ModelTokenUsage {
                    prompt_tokens: 1,
                    prompt_cache_hit_tokens: 0,
                    prompt_cache_miss_tokens: 1,
                    completion_tokens: 1,
                    reasoning_tokens: 0,
                    total_tokens: 2,
                },
            })
        }
    }

    fn metacog_state(
        value: Value,
        fail: bool,
        with_adapter: bool,
    ) -> (Arc<AppState>, tempfile::TempDir, Arc<FakeMetacogModel>) {
        use cerebellum_core::{BaseModelPin, ExpertAdapterStatus};
        let dir = tempdir().unwrap();
        let config = AppConfig {
            data_dir: dir.path().into(),
            bind: "127.0.0.1:0".parse().unwrap(),
            auth_token: "a".repeat(64),
            signing_secret: vec![7; 64],
            local_model: None,
            learning_scheduler_enabled: false,
            metacognition_enabled: true,
            training_provider_local: false,
            mediacrawler_search: false,
            github_webhook_secret: None,
            websub_secret: None,
            github_token: None,
            github_watchlist: vec![],
            meta_trainer_enabled: false,
            meta_base_model: None,
            meta_data_license_policy: None,
            meta_gpu_memory_gb: None,
            autodl: None,
            admin_origin: "https://localhost:8443".into(),
        };
        let registry = Arc::new(Registry::open(&config.data_dir).unwrap());
        builtins::seed(&registry).unwrap();
        let model = Arc::new(FakeMetacogModel {
            value,
            calls: std::sync::atomic::AtomicUsize::new(0),
            fail,
        });
        let state = Arc::new(AppState {
            registry,
            config,
            router: Arc::new(DeterministicRouter),
            signer: PermitSigner::new(vec![7; 64]).unwrap(),
            gpu_provider: None,
            structured_model: Some(model.clone()),
            admin_csrf: "test-csrf".into(),
        });
        if with_adapter {
            let adapter = ExpertAdapterVersion {
                schema_version: SCHEMA_VERSION.into(),
                adapter_id: Uuid::new_v4(),
                expert_id: "metacognition".into(),
                version: "1.0.0".into(),
                bundle_hash: "a".repeat(64),
                artifact_path: "adapters/metacognition.zip".into(),
                artifact_hash: "b".repeat(64),
                byte_length: 1,
                training_records: 0,
                base_model: BaseModelPin {
                    model_id: "Qwen/Qwen2.5-1.5B".into(),
                    revision: "r1".into(),
                    sha256: "c".repeat(64),
                },
                training_run_id: Uuid::new_v4(),
                snapshot_id: Uuid::new_v4(),
                expert_view_id: Uuid::new_v4(),
                taxonomy_hash: "d".repeat(64),
                status: ExpertAdapterStatus::Active,
                metrics: None,
                previous_active: None,
                created_at: Utc::now(),
                updated_at: Utc::now(),
            };
            let json = serde_json::to_string(&adapter).unwrap();
            let now = Utc::now().to_rfc3339();
            let conn = state.registry.lock_conn();
            // FK chain: adapter -> training_runs -> dataset_snapshots.
            conn.execute(
                "INSERT INTO dataset_snapshots (id, kind, build_id, bundle_hash, manifest_hash, snapshot_json, created_at) VALUES (?1,'meta-controller',?2,?3,?4,'{}',?5)",
                rusqlite::params![
                    adapter.snapshot_id.to_string(),
                    Uuid::new_v4().to_string(),
                    "e".repeat(64),
                    "f".repeat(64),
                    now,
                ],
            )
            .unwrap();
            conn.execute(
                "INSERT INTO training_runs (id, snapshot_id, status, run_json, created_at, updated_at) VALUES (?1,?2,'completed','{}',?3,?3)",
                rusqlite::params![
                    adapter.training_run_id.to_string(),
                    adapter.snapshot_id.to_string(),
                    now,
                ],
            )
            .unwrap();
            conn.execute(
                "INSERT INTO expert_adapter_versions (adapter_id, expert_id, version, status, training_run_id, bundle_hash, artifact_hash, adapter_json, updated_at) VALUES (?1,'metacognition','1.0.0','active',?2,?3,?4,?5,?6)",
                rusqlite::params![
                    adapter.adapter_id.to_string(),
                    adapter.training_run_id.to_string(),
                    adapter.bundle_hash,
                    adapter.artifact_hash,
                    json,
                    now,
                ],
            )
            .unwrap();
        }
        (state, dir, model)
    }

    #[tokio::test]
    async fn decision_response_stamps_server_environment() {
        let (state, _dir) = state();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let before = Utc::now() - ChronoDuration::seconds(30);
        let response = service
            .oneshot(authed_post(
                &token,
                "/v1/decisions",
                json!({
                    "task": "repair the flaky router test",
                    "context": {"environment": {"now": "1999-01-01T00:00:00Z", "timezone": "UTC", "registry_snapshot": "fake"}}
                }),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let payload = body(response).await;
        let stamped = &payload["environment"];
        assert_eq!(stamped["timezone"], "Asia/Shanghai");
        let now = chrono::DateTime::parse_from_rfc3339(stamped["now"].as_str().unwrap()).unwrap();
        assert!(
            now.with_timezone(&Utc) >= before,
            "now must be server-stamped"
        );
        assert_eq!(stamped["registry_snapshot"], payload["registry_snapshot"]);
        assert_eq!(payload["acquisition_requested"], false);
    }

    #[tokio::test]
    async fn metacognition_hook_does_not_fire_without_active_adapter() {
        let (state, _dir, model) =
            metacog_state(hook_decision_payload("answer", None), false, false);
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let response = service
            .oneshot(authed_post(
                &token,
                "/v1/decisions",
                json!({"task": "latest stable Go version"}),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let payload = body(response).await;
        assert!(payload["environment"].is_object());
        assert_eq!(model.calls.load(std::sync::atomic::Ordering::SeqCst), 0);
    }

    fn hook_decision_payload(action: &str, query: Option<&str>) -> Value {
        json!({
            "action": action,
            "as_of_used": "2026-09-04T10:00:00+08:00",
            "query": query,
            // request_acquisition requires a freshness bound (contract discipline)
            "freshness_hours": if action == "request_acquisition" { json!(72) } else { Value::Null },
            "answer": Value::Null,
            "answer_basis": "none",
            "confidence": 0.8,
        })
    }

    #[tokio::test]
    async fn metacognition_hook_search_internal_refines_knowledge_context() {
        let (state, _dir, model) = metacog_state(
            hook_decision_payload("search_internal", Some("Artemis program status")),
            false,
            true,
        );
        let card = knowledge_card(
            "Artemis program status",
            KnowledgeStatus::Corroborated,
            None,
            0.1,
        );
        state.registry.save_knowledge_card(&card).unwrap();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        // The default BM25 injection uses the task text, which does not match
        // the card; the hook's refined query does.
        let response = service
            .oneshot(authed_post(
                &token,
                "/v1/decisions",
                json!({"task": "unrelated router repair"}),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let payload = body(response).await;
        assert_eq!(model.calls.load(std::sync::atomic::Ordering::SeqCst), 1);
        let knowledge = payload["knowledge_context"].as_array().unwrap();
        assert!(
            knowledge
                .iter()
                .any(|item| item["card"]["title"] == "Artemis program status"),
            "hook retrieval must attach the matching card: {knowledge:?}"
        );
        assert_eq!(payload["acquisition_requested"], false);
    }

    #[tokio::test]
    async fn metacognition_hook_request_acquisition_enqueues_covered_sync() {
        let (state, _dir, _model) = metacog_state(
            hook_decision_payload("request_acquisition", Some("artemis program status")),
            false,
            true,
        );
        let policy = state
            .registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "fixture-feed".into(),
                kind: SourceKind::RssAtom,
                base_url: "https://example.com/feed".into(),
                access_mode: SourceAccessMode::Public,
                allowed_domains: vec!["example.com".into()],
                obey_robots: true,
                max_depth: 1,
                max_pages_per_run: 1,
                rate_limit_per_minute: 1,
                raw_retention_days: 1,
                training_license: None,
                model_terms_allow_training: false,
                auth_secret_ref: None,
                enabled: true,
                data_classification: Default::default(),
                external_processing: Default::default(),
            })
            .unwrap();
        state
            .registry
            .create_topic_watch(&CreateTopicWatchRequest {
                name: "artemis-watch".into(),
                query: "artemis program".into(),
                keywords: vec![],
                entities: vec![],
                languages: vec!["en".into()],
                source_policy_ids: vec![policy.policy_id],
                refresh_seconds: 3600,
                budget: Default::default(),
                enabled: true,
            })
            .unwrap();
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let response = service
            .oneshot(authed_post(
                &token,
                "/v1/decisions",
                json!({"task": "artemis program latest status"}),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let payload = body(response).await;
        assert_eq!(_model.calls.load(std::sync::atomic::Ordering::SeqCst), 1);
        assert_eq!(payload["acquisition_requested"], true);
        let jobs = state.registry.list_learning_jobs(None, 100).unwrap();
        assert!(!jobs.is_empty(), "sync must enqueue acquisition jobs");
    }

    #[tokio::test]
    async fn metacognition_hook_failure_is_fail_closed() {
        let (state, _dir, model) = metacog_state(Value::Null, true, true);
        let token = state.config.auth_token.clone();
        let service = app(state.clone());
        let response = service
            .oneshot(authed_post(
                &token,
                "/v1/decisions",
                json!({"task": "latest stable Go version"}),
            ))
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let payload = body(response).await;
        assert_eq!(model.calls.load(std::sync::atomic::Ordering::SeqCst), 1);
        assert!(payload["environment"].is_object());
        assert_eq!(payload["acquisition_requested"], false);
        assert!(payload["fallback_used"] == false);
    }
}

#[derive(Debug, Deserialize)]
struct EnabledOnlyQuery {
    #[serde(default)]
    enabled_only: bool,
}

async fn list_topics(
    State(state): State<Arc<AppState>>,
    Query(query): Query<EnabledOnlyQuery>,
) -> Result<Json<Vec<TopicWatch>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_topic_watches(query.enabled_only)).await?,
    ))
}

async fn create_topic(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateTopicWatchRequest>,
) -> Result<(StatusCode, Json<TopicWatch>), AppError> {
    for source_id in &request.source_policy_ids {
        let reg = Arc::clone(&state.registry);
        let source_id = *source_id;
        if blocking(move || reg.get_source_policy(source_id))
            .await?
            .is_none()
        {
            return Err(AppError::bad_request(format!(
                "source policy {source_id} does not exist"
            )));
        }
    }
    let reg = Arc::clone(&state.registry);
    let topic = blocking(move || reg.create_topic_watch(&request))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(topic)))
}

async fn list_source_policies(
    State(state): State<Arc<AppState>>,
    Query(query): Query<EnabledOnlyQuery>,
) -> Result<Json<Vec<SourcePolicy>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_source_policies(query.enabled_only)).await?,
    ))
}

async fn create_source_policy(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateSourcePolicyRequest>,
) -> Result<(StatusCode, Json<SourcePolicy>), AppError> {
    let reg = Arc::clone(&state.registry);
    let policy = blocking(move || reg.create_source_policy(&request))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(policy)))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct TombstoneSourcePolicyRequest {
    actor: String,
    reason: String,
}

async fn tombstone_source_policy(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<TombstoneSourcePolicyRequest>,
) -> Result<Json<crate::knowledge_store::SourceTombstoneReport>, AppError> {
    let policy_id = operation
        .strip_suffix(":tombstone")
        .ok_or_else(|| AppError::not_found("unknown source policy operation"))?
        .parse::<Uuid>()
        .map_err(|_| AppError::bad_request("invalid source policy id"))?;
    let reg = Arc::clone(&state.registry);
    let report =
        blocking(move || reg.tombstone_source_policy(policy_id, &request.actor, &request.reason))
            .await
            .map_err(map_store_err)?;
    Ok(Json(report))
}

async fn sync_connector(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let policy_id = operation
        .strip_suffix(":sync")
        .and_then(|id| Uuid::parse_str(id).ok())
        .ok_or_else(|| AppError::bad_request("connector operation must be UUID:sync"))?;
    let reg = Arc::clone(&state.registry);
    let policy = blocking(move || reg.get_source_policy(policy_id))
        .await?
        .ok_or_else(|| AppError::not_found("source policy not found"))?;
    if !policy.enabled {
        return Err(AppError::conflict("source policy is disabled"));
    }
    let reg = Arc::clone(&state.registry);
    let (plans, jobs) = blocking(move || enqueue_connector_sync(&reg, &policy, Utc::now())).await?;
    Ok((
        StatusCode::ACCEPTED,
        Json(json!({"source_policy_id":policy_id,"plans":plans,"job_ids":jobs})),
    ))
}

fn enqueue_connector_sync(
    registry: &Registry,
    policy: &SourcePolicy,
    now: chrono::DateTime<Utc>,
) -> Result<(Vec<AcquisitionPlan>, Vec<Uuid>)> {
    let topics = registry.list_topic_watches(true)?;
    let mut plans = Vec::new();
    let mut jobs = Vec::new();
    for topic in topics
        .into_iter()
        .filter(|topic| topic.source_policy_ids.contains(&policy.policy_id))
    {
        let plan = AcquisitionPlan {
            schema_version: SCHEMA_VERSION.into(),
            plan_id: Uuid::new_v4(),
            topic_id: topic.topic_id,
            query: topic.query.clone(),
            source_policy_ids: vec![policy.policy_id],
            scheduled_for: now,
            max_documents: topic
                .budget
                .fetched_documents_per_day
                .min(policy.max_pages_per_run)
                .max(1),
            max_depth: policy.max_depth,
            status: AcquisitionPlanStatus::Pending,
            created_at: now,
        };
        registry.save_acquisition_plan(&plan)?;
        let window = now.timestamp().div_euclid(i64::from(topic.refresh_seconds));
        if let Some(job) = registry.enqueue_unique_learning_job(
            "source_discover_v1",
            &format!("{}:{}:{window}", policy.policy_id, topic.topic_id),
            json!({
                "plan_id":plan.plan_id,
                "topic_id":topic.topic_id,
                "source_policy_id":policy.policy_id
            }),
            0.7,
            5,
        )? {
            jobs.push(job.job_id);
        }
        plans.push(plan);
    }
    Ok((plans, jobs))
}

async fn get_acquisition_status(
    State(state): State<Arc<AppState>>,
) -> Result<Json<AcquisitionStatus>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(blocking(move || reg.acquisition_status()).await?))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ReserveBrowserBudgetRequest {
    job_id: Uuid,
    worker: String,
}

async fn reserve_browser_budget(
    State(state): State<Arc<AppState>>,
    Json(request): Json<ReserveBrowserBudgetRequest>,
) -> Result<Json<Value>, AppError> {
    let reg = Arc::clone(&state.registry);
    let job_id = request.job_id;
    let worker = request.worker.clone();
    let newly_reserved = blocking(move || reg.reserve_browser_escalation(job_id, &worker))
        .await
        .map_err(map_store_err)?;
    Ok(Json(json!({
        "job_id":request.job_id,
        "reserved":true,
        "newly_reserved":newly_reserved
    })))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ReserveSourceRateRequest {
    job_id: Uuid,
    worker: String,
    ordinal: u8,
}

async fn reserve_source_rate(
    State(state): State<Arc<AppState>>,
    Json(request): Json<ReserveSourceRateRequest>,
) -> Result<Json<Value>, AppError> {
    let reg = Arc::clone(&state.registry);
    let job_id = request.job_id;
    let worker = request.worker.clone();
    let ordinal = request.ordinal;
    let newly_reserved = blocking(move || reg.reserve_source_request(job_id, &worker, ordinal))
        .await
        .map_err(map_store_err)?;
    Ok(Json(json!({
        "job_id":request.job_id,
        "reserved":true,
        "newly_reserved":newly_reserved,
        "ordinal":request.ordinal
    })))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SubmitAcquisitionResultRequest {
    result: AcquisitionWorkerResult,
    #[serde(default)]
    cleaned_content_base64: Option<String>,
    #[serde(default)]
    raw_content_base64: Option<String>,
}

async fn submit_acquisition_result(
    State(state): State<Arc<AppState>>,
    Json(request): Json<SubmitAcquisitionResultRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let cleaned = decode_content(request.cleaned_content_base64.as_deref())?;
    let raw = decode_content(request.raw_content_base64.as_deref())?;
    let job_id = request.result.job_id;
    let worker_result = request.result;
    let reg = Arc::clone(&state.registry);
    let hash = blocking(move || {
        reg.save_acquisition_worker_result(&worker_result, cleaned.as_deref(), raw.as_deref())
    })
    .await
    .map_err(map_store_err)?;
    Ok((
        StatusCode::CREATED,
        Json(json!({"job_id":job_id,"result_hash":hash})),
    ))
}

async fn get_acquisition_result(
    State(state): State<Arc<AppState>>,
    Path(job_id): Path<Uuid>,
) -> Result<Json<AcquisitionWorkerResult>, AppError> {
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_acquisition_worker_result(job_id))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("acquisition result not found"))
}

fn decode_content(value: Option<&str>) -> Result<Option<Vec<u8>>, AppError> {
    value
        .map(|encoded| {
            base64::engine::general_purpose::STANDARD
                .decode(encoded)
                .map_err(|_| AppError::bad_request("content must be valid base64"))
        })
        .transpose()
}

async fn retrieve_knowledge(
    State(state): State<Arc<AppState>>,
    Json(request): Json<KnowledgeRetrieveRequest>,
) -> Result<Json<KnowledgeRetrieveResponse>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.retrieve_knowledge(&request))
            .await
            .map_err(map_store_err)?,
    ))
}

async fn get_knowledge_card(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<KnowledgeCard>, AppError> {
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_knowledge_card(id))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("knowledge card not found"))
}

async fn get_knowledge_card_history(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<Vec<KnowledgeCard>>, AppError> {
    let reg = Arc::clone(&state.registry);
    let history = blocking(move || reg.get_knowledge_card_history(id)).await?;
    if history.is_empty() {
        return Err(AppError::not_found("knowledge card not found"));
    }
    Ok(Json(history))
}

#[derive(Debug, Deserialize)]
struct ListEventsQuery {
    #[serde(default)]
    status: Option<EventStatus>,
    #[serde(default)]
    platform: Option<String>,
    #[serde(default)]
    limit: Option<usize>,
}

async fn list_events(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ListEventsQuery>,
) -> Result<Json<Vec<TrackedEvent>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || {
            reg.list_events(
                query.status,
                query.platform.as_deref(),
                query.limit.unwrap_or(100),
            )
        })
        .await?,
    ))
}

#[derive(Debug, Deserialize)]
struct ListLearningJobsQuery {
    #[serde(default)]
    status: Option<LearningJobStatus>,
    #[serde(default)]
    limit: Option<usize>,
}

async fn list_learning_jobs(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ListLearningJobsQuery>,
) -> Result<Json<Vec<LearningJob>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_learning_jobs(query.status, query.limit.unwrap_or(100).min(500)))
            .await?,
    ))
}

#[derive(Debug, Deserialize)]
struct ListLimitQuery {
    #[serde(default)]
    limit: Option<usize>,
}

async fn list_knowledge_cards(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ListLimitQuery>,
) -> Result<Json<Vec<KnowledgeCard>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_knowledge_cards(query.limit.unwrap_or(100).min(500))).await?,
    ))
}

async fn list_documents(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ListLimitQuery>,
) -> Result<Json<Vec<DocumentEnvelope>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_documents(query.limit.unwrap_or(100).min(500))).await?,
    ))
}

async fn get_event(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, AppError> {
    let reg = Arc::clone(&state.registry);
    let event = blocking(move || reg.get_event(id))
        .await?
        .ok_or_else(|| AppError::not_found("event not found"))?;
    let reg = Arc::clone(&state.registry);
    let items = blocking(move || reg.list_event_items(id)).await?;
    Ok(Json(json!({"event": event, "items": items})))
}

async fn get_meta_status(State(state): State<Arc<AppState>>) -> Result<Json<Value>, AppError> {
    let reg = Arc::clone(&state.registry);
    let readiness = blocking(move || reg.meta_training_readiness(Utc::now())).await?;
    let reg = Arc::clone(&state.registry);
    let active = blocking(move || reg.active_meta_model()).await?;
    Ok(Json(json!({
        "readiness":readiness,
        "active_model":active,
        "trainer_enabled":state.config.meta_trainer_enabled,
        "base_model":state.config.meta_base_model,
        "data_license_policy":state.config.meta_data_license_policy,
        "declared_gpu_memory_gb":state.config.meta_gpu_memory_gb
    })))
}

async fn record_meta_decision(
    State(state): State<Arc<AppState>>,
    Json(trace): Json<MetaDecisionTrace>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let reg = Arc::clone(&state.registry);
    let record_trace = trace.clone();
    let inserted = blocking(move || reg.record_meta_decision(&record_trace))
        .await
        .map_err(map_store_err)?;
    if inserted
        && state.structured_model.is_some()
        && trace.training_eligible
        && trace.policy_violations == 0
        && !trace.prompt_injection_detected
    {
        let hash = canonical_json_hash(&serde_json::to_value(&trace)?);
        let dedupe_key = format!("meta_decision:{}:{hash}", trace.decision_id);
        let payload =
            json!({"subject_kind":QualitySubjectKind::MetaDecision,"subject_id":trace.decision_id});
        let reg = Arc::clone(&state.registry);
        blocking(move || {
            reg.enqueue_unique_learning_job("quality_assess_v1", &dedupe_key, payload, 1.0, 5)
        })
        .await?;
    }
    Ok((
        if inserted {
            StatusCode::CREATED
        } else {
            StatusCode::OK
        },
        Json(json!({"inserted":inserted,"decision_id":trace.decision_id})),
    ))
}

async fn record_meta_replay(
    State(state): State<Arc<AppState>>,
    Json(evaluation): Json<MetaReplayEvaluation>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let reg = Arc::clone(&state.registry);
    let record_evaluation = evaluation.clone();
    let inserted = blocking(move || reg.record_meta_replay(&record_evaluation))
        .await
        .map_err(map_store_err)?;
    if inserted && state.structured_model.is_some() && evaluation.safety_passed {
        let hash = canonical_json_hash(&serde_json::to_value(&evaluation)?);
        let dedupe_key = format!("meta_replay:{}:{hash}", evaluation.evaluation_id);
        let payload = json!({"subject_kind":QualitySubjectKind::MetaReplay,"subject_id":evaluation.evaluation_id});
        let reg = Arc::clone(&state.registry);
        blocking(move || {
            reg.enqueue_unique_learning_job("quality_assess_v1", &dedupe_key, payload, 1.0, 5)
        })
        .await?;
    }
    Ok((
        if inserted {
            StatusCode::CREATED
        } else {
            StatusCode::OK
        },
        Json(json!({"inserted":inserted,"evaluation_id":evaluation.evaluation_id})),
    ))
}

async fn list_meta_training_candidates(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<MetaTrainingCandidate>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_meta_training_candidates()).await?,
    ))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct EnqueueMetaTrainingRequest {
    candidate_id: Uuid,
    #[serde(default)]
    base_model: Option<BaseModelPin>,
    #[serde(default)]
    gpu_spec: Option<String>,
    #[serde(default)]
    administrator: Option<String>,
    #[serde(default)]
    reason: Option<String>,
    #[serde(default)]
    budget: Option<TrainingBudget>,
    #[serde(default)]
    qlora: QloraConfig,
}

async fn enqueue_meta_training(
    State(state): State<Arc<AppState>>,
    Json(request): Json<EnqueueMetaTrainingRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let config = state
        .config
        .autodl
        .as_ref()
        .ok_or_else(|| AppError::forbidden("AutoDL training orchestration is disabled"))?;
    let provider = state
        .gpu_provider
        .as_deref()
        .ok_or_else(|| AppError::forbidden("AutoDL GPU provider is unavailable"))?;
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.migrate_legacy_meta_candidates()).await?;
    let reg = Arc::clone(&state.registry);
    let candidate_id = request.candidate_id;
    if blocking(move || reg.get_dataset_snapshot(candidate_id))
        .await?
        .is_none()
    {
        return Err(AppError::not_found(
            "meta training candidate or migrated snapshot not found",
        ));
    }
    let administrator = request
        .administrator
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| AppError::bad_request("deprecated enqueue requires administrator"))?;
    let reason = request
        .reason
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| AppError::bad_request("deprecated enqueue requires reason"))?;
    let base_model = request
        .base_model
        .ok_or_else(|| AppError::bad_request("deprecated enqueue requires a pinned base_model"))?;
    let gpu_spec = request
        .gpu_spec
        .ok_or_else(|| AppError::bad_request("deprecated enqueue requires gpu_spec"))?;
    let budget = request
        .budget
        .ok_or_else(|| AppError::bad_request("deprecated enqueue requires explicit CNY budgets"))?;
    let create_request = CreateTrainingRunRequest {
        snapshot_id: request.candidate_id,
        base_model,
        qlora: request.qlora,
        expert_plan: None,
        gpu_spec: gpu_spec.clone(),
        administrator: administrator.clone(),
        reason: format!("deprecated /v1/meta/training:enqueue: {reason}"),
        budget: budget.clone(),
    };
    let create_config = config.clone();
    let reg = Arc::clone(&state.registry);
    let run =
        blocking(move || reg.create_training_run(&create_request, &create_config, Utc::now()))
            .await
            .map_err(map_store_err)?;
    let run = state
        .registry
        .start_training_run(
            run.run_id,
            &StartTrainingRunRequest {
                administrator,
                reason,
                confirm_gpu_spec: gpu_spec,
                confirm_max_hourly_cny: budget.max_hourly_cny,
                confirm_max_total_cny: budget.max_total_cny,
                confirm_max_wall_seconds: budget.max_wall_seconds,
            },
            config,
            provider,
            Utc::now(),
        )
        .await
        .map_err(map_store_err)?;
    Ok((
        StatusCode::ACCEPTED,
        Json(json!({
            "deprecated":true,
            "training_run":run,
            "message":"use /v1/training-runs and explicit :start"
        })),
    ))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RegisterMetaModelRequest {
    bundle: MetaModelBundle,
    artifact_base64: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SubmitMetaTrainingResultRequest {
    job_id: Uuid,
    worker: String,
    bundle: MetaModelBundle,
    artifact_base64: String,
}

async fn submit_meta_training_result(
    State(state): State<Arc<AppState>>,
    Json(request): Json<SubmitMetaTrainingResultRequest>,
) -> Result<(StatusCode, Json<MetaModelBundle>), AppError> {
    let artifact = base64::engine::general_purpose::STANDARD
        .decode(&request.artifact_base64)
        .map_err(|_| AppError::bad_request("artifact must be valid base64"))?;
    if artifact.len() > 512 * 1024 * 1024 {
        return Err(AppError::bad_request(
            "QLoRA adapter bundle exceeds the 512 MiB upload limit",
        ));
    }
    let model_id = request.bundle.model_id.clone();
    let version = request.bundle.version.clone();
    let reg = Arc::clone(&state.registry);
    blocking(move || {
        reg.submit_meta_training_result(request.job_id, &request.worker, &request.bundle, &artifact)
    })
    .await
    .map_err(map_store_err)?;
    let reg = Arc::clone(&state.registry);
    let stored = blocking(move || reg.get_meta_model(&model_id, &version))
        .await?
        .ok_or_else(|| AppError::internal("accepted meta model is missing"))?;
    Ok((StatusCode::CREATED, Json(stored)))
}

async fn get_meta_training_result(
    State(state): State<Arc<AppState>>,
    Path(job_id): Path<Uuid>,
) -> Result<Json<MetaModelBundle>, AppError> {
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_meta_training_job_result(job_id))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("meta training result not found"))
}

async fn register_meta_model(
    State(state): State<Arc<AppState>>,
    Json(request): Json<RegisterMetaModelRequest>,
) -> Result<(StatusCode, Json<MetaModelBundle>), AppError> {
    let artifact = base64::engine::general_purpose::STANDARD
        .decode(&request.artifact_base64)
        .map_err(|_| AppError::bad_request("artifact must be valid base64"))?;
    let reg = Arc::clone(&state.registry);
    let bundle = request.bundle.clone();
    blocking(move || reg.register_meta_model(&bundle, &artifact))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(request.bundle)))
}

async fn list_meta_models(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<MetaModelBundle>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(blocking(move || reg.list_meta_models()).await?))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct MetaModelOperationRequest {
    #[serde(default)]
    metrics: Option<MetaModelMetrics>,
    #[serde(default)]
    actor: Option<String>,
    #[serde(default)]
    reason: Option<String>,
}

async fn operate_meta_model(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<MetaModelOperationRequest>,
) -> Result<Json<MetaModelBundle>, AppError> {
    let (subject, action) = ["shadow", "canary", "evaluate", "rollback"]
        .into_iter()
        .find_map(|action| {
            operation
                .strip_suffix(&format!(":{action}"))
                .map(|subject| (subject, action))
        })
        .ok_or_else(|| AppError::bad_request("unknown meta model operation"))?;
    let (id, version) = subject
        .rsplit_once('@')
        .filter(|(id, version)| !id.is_empty() && !version.is_empty())
        .ok_or_else(|| AppError::bad_request("meta model must be MODEL@VERSION"))?;
    let bundle = match action {
        "shadow" => {
            let reg = Arc::clone(&state.registry);
            let id = id.to_owned();
            let version = version.to_owned();
            blocking(move || reg.begin_meta_shadow(&id, &version)).await
        }
        "canary" => {
            let reg = Arc::clone(&state.registry);
            let id = id.to_owned();
            let version = version.to_owned();
            blocking(move || reg.begin_meta_canary(&id, &version, Utc::now())).await
        }
        "evaluate" => {
            let metrics = request
                .metrics
                .ok_or_else(|| AppError::bad_request("evaluate requires metrics"))?;
            let reg = Arc::clone(&state.registry);
            let id = id.to_owned();
            let version = version.to_owned();
            blocking(move || reg.evaluate_meta_model(&id, &version, metrics, Utc::now())).await
        }
        "rollback" => {
            let actor = request
                .actor
                .as_deref()
                .ok_or_else(|| AppError::bad_request("rollback requires actor"))?
                .to_owned();
            let reason = request
                .reason
                .as_deref()
                .ok_or_else(|| AppError::bad_request("rollback requires reason"))?
                .to_owned();
            let reg = Arc::clone(&state.registry);
            let id = id.to_owned();
            let version = version.to_owned();
            blocking(move || reg.rollback_meta_model(&id, &version, &actor, &reason)).await
        }
        _ => unreachable!(),
    }
    .map_err(map_store_err)?;
    Ok(Json(bundle))
}

async fn record_meta_canary_decision(
    State(state): State<Arc<AppState>>,
    Json(decision): Json<MetaCanaryDecision>,
) -> Result<(StatusCode, Json<MetaModelBundle>), AppError> {
    let reg = Arc::clone(&state.registry);
    let bundle = blocking(move || reg.record_meta_canary_decision(&decision))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(bundle)))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct BuildDatasetRequest {
    actor: String,
    reason: String,
}

async fn get_dataset_draft(
    State(state): State<Arc<AppState>>,
    Path(kind): Path<String>,
) -> Result<Json<Value>, AppError> {
    let reg = Arc::clone(&state.registry);
    let draft = blocking(move || reg.get_dataset_draft(&kind))
        .await
        .map_err(map_store_err)?
        .ok_or_else(|| AppError::not_found("dataset draft not found"))?;
    let reg = Arc::clone(&state.registry);
    let build_id = draft.build_id;
    let build = blocking(move || reg.get_dataset_build(build_id))
        .await?
        .ok_or_else(|| AppError::internal("dataset draft references a missing build"))?;
    Ok(Json(json!({"draft":draft,"build":build})))
}

async fn build_dataset_draft(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<BuildDatasetRequest>,
) -> Result<(StatusCode, Json<DatasetBuild>), AppError> {
    let kind = operation
        .strip_suffix(":build")
        .filter(|kind| !kind.is_empty())
        .ok_or_else(|| AppError::bad_request("dataset operation must end with :build"))?;
    if request.actor.trim().is_empty() || request.reason.trim().is_empty() {
        return Err(AppError::bad_request(
            "dataset build actor and reason are required",
        ));
    }
    let kind = kind.to_owned();
    let reg = Arc::clone(&state.registry);
    let build = blocking(move || reg.build_dataset_draft(&kind, Utc::now()))
        .await
        .map_err(map_store_err)?;
    let reg = Arc::clone(&state.registry);
    let build_id = build.build_id;
    blocking(move || {
        reg.audit_dataset_build(build_id, &request.actor, &request.reason, Utc::now())
    })
    .await?;
    Ok((StatusCode::CREATED, Json(build)))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct QualityAssessmentQuery {
    #[serde(default)]
    subject_kind: Option<QualitySubjectKind>,
    #[serde(default)]
    subject_id: Option<String>,
    #[serde(default = "default_quality_limit")]
    limit: usize,
}

fn default_quality_limit() -> usize {
    100
}

async fn get_quality_status(
    State(state): State<Arc<AppState>>,
) -> Result<Json<QualityStatus>, AppError> {
    let local_model = state.config.local_model.clone();
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.quality_status(local_model.as_ref(), Utc::now())).await?,
    ))
}

async fn list_quality_assessments(
    State(state): State<Arc<AppState>>,
    Query(query): Query<QualityAssessmentQuery>,
) -> Result<Json<Vec<DataQualityAssessment>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || {
            reg.list_quality_assessments(
                query.subject_kind,
                query.subject_id.as_deref(),
                query.limit,
            )
        })
        .await?,
    ))
}

async fn list_quality_model_versions(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<ModelEndpointVersion>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_model_endpoint_versions()).await?,
    ))
}

async fn review_quality_model_version(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<ReviewQualityModelRequest>,
) -> Result<Json<ModelEndpointVersion>, AppError> {
    let (id, action) = ["approve", "reject"]
        .into_iter()
        .find_map(|action| {
            operation
                .strip_suffix(&format!(":{action}"))
                .map(|id| (id, action))
        })
        .ok_or_else(|| {
            AppError::bad_request("quality model operation must be :approve or :reject")
        })?;
    let id =
        Uuid::parse_str(id).map_err(|_| AppError::bad_request("invalid endpoint version id"))?;
    let result = match action {
        "approve" => {
            let reg = Arc::clone(&state.registry);
            blocking(move || reg.approve_model_endpoint(id, &request, Utc::now())).await
        }
        "reject" => {
            let reg = Arc::clone(&state.registry);
            blocking(move || reg.reject_model_endpoint(id, &request, Utc::now())).await
        }
        _ => unreachable!(),
    }
    .map_err(map_store_err)?;
    Ok(Json(result))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct QualityBackfillRequest {
    actor: String,
    reason: String,
    #[serde(default = "default_quality_backfill_limit")]
    limit: usize,
}

fn default_quality_backfill_limit() -> usize {
    1_000
}

async fn backfill_quality(
    State(state): State<Arc<AppState>>,
    Json(request): Json<QualityBackfillRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    if state.structured_model.is_none() {
        return Err(AppError::forbidden("local quality model is disabled"));
    }
    if request.actor.trim().is_empty() || request.reason.trim().is_empty() {
        return Err(AppError::bad_request(
            "backfill actor and reason are required",
        ));
    }
    let reg = Arc::clone(&state.registry);
    let limit = request.limit;
    let scheduled = blocking(move || reg.enqueue_quality_backfill(limit)).await?;
    let payload = json!({"limit":request.limit,"actor":request.actor,"reason":request.reason});
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.enqueue_learning_job("quality_backfill_v1", payload, 0.9, 3)).await?;
    Ok((StatusCode::ACCEPTED, Json(json!({"scheduled":scheduled}))))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SyntheticCandidateQuery {
    #[serde(default)]
    status: Option<SyntheticCandidateStatus>,
    #[serde(default = "default_quality_limit")]
    limit: usize,
}

async fn list_synthetic_candidates(
    State(state): State<Arc<AppState>>,
    Query(query): Query<SyntheticCandidateQuery>,
) -> Result<Json<Vec<SyntheticTrainingCandidate>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_synthetic_candidates(query.status, query.limit)).await?,
    ))
}

async fn review_synthetic_candidate(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<ReviewSyntheticCandidateRequest>,
) -> Result<Json<SyntheticTrainingCandidate>, AppError> {
    let (id, action) = if let Some(id) = operation.strip_suffix(":approve") {
        (id, "approve")
    } else if let Some(id) = operation.strip_suffix(":reject") {
        (id, "reject")
    } else if let Some(id) = operation.strip_suffix(":verify") {
        (id, "verify")
    } else {
        return Err(AppError::bad_request(
            "synthetic operation must be :approve, :reject, or :verify",
        ));
    };
    let id =
        Uuid::parse_str(id).map_err(|_| AppError::bad_request("invalid synthetic candidate id"))?;
    let candidate = if action == "verify" {
        let reg = Arc::clone(&state.registry);
        blocking(move || reg.verify_synthetic_candidate(id, &request, Utc::now())).await
    } else {
        let approve = action == "approve";
        let reg = Arc::clone(&state.registry);
        blocking(move || reg.review_synthetic_candidate(id, approve, &request, Utc::now())).await
    }
    .map_err(map_store_err)?;
    Ok(Json(candidate))
}

async fn get_dataset_quality_report(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<DatasetQualityReport>, AppError> {
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_dataset_quality_report(id))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("dataset quality report not found"))
}

async fn reaudit_dataset_quality(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<BuildDatasetRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let id = operation
        .strip_suffix(":reaudit")
        .ok_or_else(|| AppError::bad_request("dataset build operation must end with :reaudit"))?;
    let id = Uuid::parse_str(id).map_err(|_| AppError::bad_request("invalid dataset build id"))?;
    if request.actor.trim().is_empty() || request.reason.trim().is_empty() {
        return Err(AppError::bad_request(
            "reaudit actor and reason are required",
        ));
    }
    let reg = Arc::clone(&state.registry);
    if blocking(move || reg.get_dataset_quality_report(id))
        .await?
        .is_some()
    {
        return Err(AppError::bad_request(
            "quality reports are immutable; create a repaired build",
        ));
    }
    let dedupe_key = id.to_string();
    let payload = json!({"build_id":id});
    let reg = Arc::clone(&state.registry);
    let job = blocking(move || {
        reg.enqueue_unique_learning_job("dataset_quality_audit_v1", &dedupe_key, payload, 2.0, 5)
    })
    .await?;
    Ok((StatusCode::ACCEPTED, Json(json!({"job":job,"build_id":id}))))
}

async fn get_expert_taxonomy() -> Json<ExpertTaxonomy> {
    Json(crate::experts::builtin_expert_taxonomy())
}

async fn route_expert_request(
    State(state): State<Arc<AppState>>,
    Json(request): Json<ExpertRouteRequest>,
) -> Result<Json<ExpertRouteDecision>, AppError> {
    let taxonomy = crate::experts::builtin_expert_taxonomy();
    if request.available_expert_ids.iter().any(|requested| {
        !taxonomy
            .experts
            .iter()
            .any(|expert| expert.id == *requested)
    }) {
        return Err(AppError::bad_request(
            "available expert list contains an unknown expert",
        ));
    }
    let taxonomy_hash = crate::experts::builtin_expert_taxonomy_hash();
    let reg = Arc::clone(&state.registry);
    let refs_hash = taxonomy_hash.clone();
    let active = blocking(move || reg.active_expert_adapter_refs(&refs_hash)).await?;
    let router_adapter = active
        .iter()
        .find(|adapter| adapter.expert_id == "router")
        .cloned();
    let allowed = active
        .iter()
        .filter(|adapter| {
            adapter.expert_id != "router"
                && (request.available_expert_ids.is_empty()
                    || request.available_expert_ids.contains(&adapter.expert_id))
        })
        .cloned()
        .collect::<Vec<_>>();
    let mut baseline_request = request.clone();
    baseline_request.available_expert_ids.clear();
    let mut decision = crate::experts::route_expert(&baseline_request).map_err(map_store_err)?;
    let selected = allowed
        .iter()
        .find(|adapter| adapter.expert_id == decision.selected_expert_id)
        .cloned();
    if let Some(selected) = selected {
        decision.selected_adapter = Some(selected);
    } else if let Some(shared) = allowed
        .iter()
        .find(|adapter| adapter.expert_id == crate::experts::SHARED_EXPERT_ID)
        .cloned()
    {
        decision.selected_expert_id = crate::experts::SHARED_EXPERT_ID.into();
        decision.selected_adapter = Some(shared);
        decision.fallback_used = true;
        decision.confidence = 0.0;
        decision.reason_codes.push("active_shared_fallback".into());
    } else {
        decision.dense_fallback = true;
        decision
            .reason_codes
            .push("no_active_adapter_dense_fallback".into());
    }
    decision.router_adapter = router_adapter;
    // Deterministic 10% canary accounting: when the routed expert has a
    // canary-status adapter and the partition hits, record the decision so
    // release gates are computed from the server-side routing stream.
    let reg = Arc::clone(&state.registry);
    let canary = blocking(move || reg.list_expert_adapters(None))
        .await?
        .into_iter()
        .find(|adapter| {
            adapter.status == ExpertAdapterStatus::Canary
                && adapter.taxonomy_hash == taxonomy_hash
                && adapter.expert_id == decision.selected_expert_id
        });
    if let Some(canary) = canary
        && crate::meta_training::should_assign_canary(
            &canary.expert_id,
            &canary.version,
            decision.decision_id,
        )
    {
        let unsafe_input = crate::experts::contains_unsafe_routing_input(&request.input);
        let adapter_id = canary.adapter_id;
        let decision_id = decision.decision_id;
        let selected_expert_id = decision.selected_expert_id.clone();
        let dense_fallback = decision.dense_fallback;
        let reg = Arc::clone(&state.registry);
        blocking(move || {
            reg.record_expert_canary_decision(
                adapter_id,
                decision_id,
                &selected_expert_id,
                dense_fallback,
                unsafe_input,
            )
        })
        .await?;
    }
    Ok(Json(decision))
}

#[derive(Debug, Deserialize)]
struct ExpertAdapterListQuery {
    expert_id: Option<String>,
    limit: Option<usize>,
}

async fn list_expert_adapters(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ExpertAdapterListQuery>,
) -> Result<Json<Vec<ExpertAdapterVersion>>, AppError> {
    let reg = Arc::clone(&state.registry);
    let mut values = blocking(move || reg.list_expert_adapters(query.expert_id.as_deref())).await?;
    values.truncate(query.limit.unwrap_or(100).clamp(1, 500));
    Ok(Json(values))
}

fn parse_expert_adapter_subject(subject: &str) -> Result<(&str, &str), AppError> {
    subject
        .rsplit_once('@')
        .filter(|(expert, version)| !expert.is_empty() && !version.is_empty())
        .ok_or_else(|| AppError::bad_request("expert adapter must be EXPERT@VERSION"))
}

#[derive(Debug, Deserialize)]
struct ExpertAdapterEvalReportQuery {
    expert_id: String,
    version: String,
}

async fn list_expert_adapter_eval_reports(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ExpertAdapterEvalReportQuery>,
) -> Result<Json<Vec<ExpertAdapterEvalReport>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_expert_adapter_eval_reports(&query.expert_id, &query.version))
            .await?,
    ))
}

async fn get_expert_adapter(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
) -> Result<Json<ExpertAdapterVersion>, AppError> {
    let (expert, version) = parse_expert_adapter_subject(&operation)?;
    let expert = expert.to_owned();
    let version = version.to_owned();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_expert_adapter(&expert, &version))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("expert adapter version not found"))
}

async fn operate_expert_adapter(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<ExpertAdapterOperationRequest>,
) -> Result<Json<ExpertAdapterVersion>, AppError> {
    let (subject, action) = ["shadow", "canary", "activate", "reject", "rollback"]
        .into_iter()
        .find_map(|action| {
            operation
                .strip_suffix(&format!(":{action}"))
                .map(|subject| (subject, action))
        })
        .ok_or_else(|| AppError::bad_request("unknown expert adapter operation"))?;
    let (expert, version) = parse_expert_adapter_subject(subject)?;
    let expert = expert.to_owned();
    let version = version.to_owned();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.operate_expert_adapter(&expert, &version, action, &request, Utc::now()))
        .await
        .map(Json)
        .map_err(map_store_err)
}

#[derive(Debug, Deserialize)]
struct ExpertListQuery {
    limit: Option<usize>,
}

async fn list_expert_dataset_views(
    State(state): State<Arc<AppState>>,
    Query(query): Query<ExpertListQuery>,
) -> Result<Json<Vec<ExpertDatasetView>>, AppError> {
    let reg = Arc::clone(&state.registry);
    let limit = query.limit.unwrap_or(100);
    Ok(Json(
        blocking(move || reg.list_expert_dataset_views(limit)).await?,
    ))
}

async fn get_expert_dataset_view(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<ExpertDatasetView>, AppError> {
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_expert_dataset_view(id))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("expert dataset view not found"))
}

async fn list_expert_assignments(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Query(query): Query<ExpertListQuery>,
) -> Result<Json<Vec<ExpertAssignment>>, AppError> {
    let reg = Arc::clone(&state.registry);
    if blocking(move || reg.get_expert_dataset_view(id))
        .await?
        .is_none()
    {
        return Err(AppError::not_found("expert dataset view not found"));
    }
    let limit = query.limit.unwrap_or(100);
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_expert_assignments(id, limit)).await?,
    ))
}

#[derive(Debug, Deserialize)]
struct SnapshotListQuery {
    kind: Option<String>,
}

async fn list_dataset_snapshots(
    State(state): State<Arc<AppState>>,
    Query(query): Query<SnapshotListQuery>,
) -> Result<Json<Vec<DatasetSnapshotRecord>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.list_dataset_snapshots(query.kind.as_deref()))
            .await
            .map_err(map_store_err)?,
    ))
}

async fn create_dataset_snapshot(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateDatasetSnapshotRequest>,
) -> Result<(StatusCode, Json<DatasetSnapshotRecord>), AppError> {
    let reg = Arc::clone(&state.registry);
    let snapshot = blocking(move || reg.freeze_dataset_snapshot(&request, Utc::now()))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(snapshot)))
}

async fn get_dataset_snapshot(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
) -> Result<Json<DatasetSnapshotRecord>, AppError> {
    let id = Uuid::parse_str(&operation)
        .map_err(|_| AppError::bad_request("dataset snapshot id must be a UUID"))?;
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_dataset_snapshot(id))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("dataset snapshot not found"))
}

async fn revoke_dataset_snapshot(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    Json(request): Json<RevokeDatasetSnapshotRequest>,
) -> Result<Json<DatasetSnapshotRecord>, AppError> {
    let id = operation
        .strip_suffix(":revoke")
        .and_then(|value| Uuid::parse_str(value).ok())
        .ok_or_else(|| AppError::bad_request("snapshot operation must be UUID:revoke"))?;
    let actor = request.actor.clone();
    let reason = request.reason.clone();
    let reg = Arc::clone(&state.registry);
    let record = blocking(move || reg.revoke_dataset_snapshot(id, &request, Utc::now()))
        .await
        .map_err(map_store_err)?;
    let reg = Arc::clone(&state.registry);
    let active_runs = blocking(move || reg.list_training_runs()).await?;
    for run in active_runs
        .into_iter()
        .filter(|run| run.snapshot_id == id && !run.status.is_terminal())
    {
        state
            .registry
            .cancel_training_run(
                run.run_id,
                &CancelTrainingRunRequest {
                    administrator: actor.clone(),
                    reason: format!("snapshot revoked: {reason}"),
                },
                state.gpu_provider.as_deref(),
                Utc::now(),
            )
            .await
            .map_err(|error| AppError::internal(error.to_string()))?;
    }
    Ok(Json(record))
}

async fn list_training_runs(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<TrainingRun>>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(blocking(move || reg.list_training_runs()).await?))
}

async fn get_training_config(State(state): State<Arc<AppState>>) -> Json<Value> {
    let value = state.config.autodl.as_ref().map(|config| {
        json!({
            "enabled":true,
            "provider":"autodl-app",
            "application_uuid":config.application_uuid,
            "application_version":config.application_version,
            "gpu_allowlist":config.gpu_allowlist,
            "base_models":config.base_models,
            "maximum_wall_seconds":21_600,
            "minimum_gpu_memory_gb":24
        })
    });
    Json(value.unwrap_or_else(|| json!({"enabled":false})))
}

async fn create_training_run_v31(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CreateTrainingRunRequest>,
) -> Result<(StatusCode, Json<TrainingRun>), AppError> {
    let config = state
        .config
        .autodl
        .as_ref()
        .ok_or_else(|| AppError::forbidden("AutoDL training orchestration is disabled"))?;
    let create_config = config.clone();
    let reg = Arc::clone(&state.registry);
    let run = blocking(move || reg.create_training_run(&request, &create_config, Utc::now()))
        .await
        .map_err(map_store_err)?;
    Ok((StatusCode::CREATED, Json(run)))
}

async fn get_training_run(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
) -> Result<Json<TrainingRunDetail>, AppError> {
    let id = Uuid::parse_str(&operation)
        .map_err(|_| AppError::bad_request("training run id must be a UUID"))?;
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.get_training_run_detail(id))
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("training run not found"))
}

async fn operate_training_run(
    State(state): State<Arc<AppState>>,
    Path(operation): Path<String>,
    request: Request<Body>,
) -> Result<Json<TrainingRun>, AppError> {
    let (subject, action) = ["start", "cancel", "release"]
        .into_iter()
        .find_map(|action| {
            operation
                .strip_suffix(&format!(":{action}"))
                .map(|subject| (subject, action))
        })
        .ok_or_else(|| AppError::bad_request("unknown training run operation"))?;
    let id = Uuid::parse_str(subject)
        .map_err(|_| AppError::bad_request("training run id must be a UUID"))?;
    let bytes = axum::body::to_bytes(request.into_body(), 64 * 1024)
        .await
        .map_err(|error| AppError::bad_request(error.to_string()))?;
    let run =
        match action {
            "start" => {
                let start: StartTrainingRunRequest = serde_json::from_slice(&bytes)
                    .map_err(|error| AppError::bad_request(error.to_string()))?;
                let provider = state.gpu_provider.as_deref().ok_or_else(|| {
                    AppError::forbidden("AutoDL training orchestration is disabled")
                })?;
                let config = state
                    .config
                    .autodl
                    .as_ref()
                    .ok_or_else(|| AppError::forbidden("AutoDL configuration is absent"))?;
                state
                    .registry
                    .start_training_run(id, &start, config, provider, Utc::now())
                    .await
                    .map_err(map_store_err)?
            }
            "cancel" => {
                let cancel: CancelTrainingRunRequest = serde_json::from_slice(&bytes)
                    .map_err(|error| AppError::bad_request(error.to_string()))?;
                state
                    .registry
                    .cancel_training_run(id, &cancel, state.gpu_provider.as_deref(), Utc::now())
                    .await
                    .map_err(map_store_err)?
            }
            "release" => {
                let provider = state.gpu_provider.as_deref().ok_or_else(|| {
                    AppError::forbidden("AutoDL training orchestration is disabled")
                })?;
                let request: CancelTrainingRunRequest = serde_json::from_slice(&bytes)
                    .map_err(|error| AppError::bad_request(error.to_string()))?;
                if request.administrator.trim().is_empty() || request.reason.trim().is_empty() {
                    return Err(AppError::bad_request(
                        "release actor and reason are required",
                    ));
                }
                let administrator = request.administrator.clone();
                let reason = request.reason.clone();
                let reg = Arc::clone(&state.registry);
                blocking(move || {
                    reg.record_training_admin_action(
                        id,
                        "force_release",
                        &administrator,
                        &reason,
                        Utc::now(),
                    )
                })
                .await?;
                let reg = Arc::clone(&state.registry);
                let current = blocking(move || reg.get_training_run(id))
                    .await?
                    .ok_or_else(|| AppError::not_found("training run not found"))?;
                if current.status.is_terminal() {
                    state
                        .registry
                        .release_training_gpu(id, provider, Utc::now())
                        .await
                        .map_err(map_store_err)?;
                    let reg = Arc::clone(&state.registry);
                    blocking(move || reg.get_training_run(id))
                        .await?
                        .ok_or_else(|| AppError::not_found("training run not found"))?
                } else {
                    state
                        .registry
                        .cancel_training_run(id, &request, Some(provider), Utc::now())
                        .await
                        .map_err(map_store_err)?
                }
            }
            _ => unreachable!(),
        };
    Ok(Json(run))
}

async fn exchange_training_worker_bootstrap(
    State(state): State<Arc<AppState>>,
    Json(request): Json<WorkerBootstrapRequest>,
) -> Result<Json<crate::training::WorkerBootstrapResponse>, AppError> {
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.exchange_worker_bootstrap(&request, Utc::now()))
            .await
            .map_err(|error| AppError::forbidden(error.to_string()))?,
    ))
}

async fn download_training_bundle(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    headers: HeaderMap,
) -> Result<Response, AppError> {
    let token = worker_bearer(&headers)?.to_owned();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.authorize_worker_token(&token, id, Utc::now()))
        .await
        .map_err(|error| AppError::forbidden(error.to_string()))?;
    let reg = Arc::clone(&state.registry);
    let run = blocking(move || reg.get_training_run(id))
        .await?
        .ok_or_else(|| AppError::not_found("training run not found"))?;
    let bundle_hash = run
        .training_bundle_hash
        .as_deref()
        .unwrap_or(&run.snapshot_bundle_hash)
        .to_owned();
    let path_hash = bundle_hash.clone();
    let reg = Arc::clone(&state.registry);
    let path = blocking(move || reg.object_path(&path_hash)).await?;
    let total = tokio::fs::metadata(&path).await?.len();
    let (start, end, partial) = parse_byte_range(headers.get(header::RANGE), total)?;
    let mut file = tokio::fs::File::open(path).await?;
    file.seek(SeekFrom::Start(start)).await?;
    let length = end - start + 1;
    let stream = ReaderStream::new(file.take(length));
    let mut response = Response::builder()
        .status(if partial {
            StatusCode::PARTIAL_CONTENT
        } else {
            StatusCode::OK
        })
        .header(header::CONTENT_TYPE, "application/x-tar")
        .header(header::ACCEPT_RANGES, "bytes")
        .header(header::CONTENT_LENGTH, length.to_string())
        .header(header::ETAG, format!("\"{bundle_hash}\""));
    if partial {
        response = response.header(
            header::CONTENT_RANGE,
            format!("bytes {start}-{end}/{total}"),
        );
    }
    response
        .body(Body::from_stream(stream))
        .map_err(|error| AppError::internal(error.to_string()))
}

async fn training_worker_heartbeat(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    headers: HeaderMap,
    Json(request): Json<WorkerHeartbeatRequest>,
) -> Result<Json<crate::training::WorkerHeartbeatResponse>, AppError> {
    let token = worker_bearer(&headers)?.to_owned();
    let reg = Arc::clone(&state.registry);
    Ok(Json(
        blocking(move || reg.rotate_worker_heartbeat(id, &token, &request, Utc::now()))
            .await
            .map_err(|error| AppError::forbidden(error.to_string()))?,
    ))
}

async fn upload_training_artifact(
    State(state): State<Arc<AppState>>,
    Path((id, kind)): Path<(Uuid, String)>,
    request: Request<Body>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let headers = request.headers();
    let token = worker_bearer(headers)?.to_owned();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.authorize_worker_token(&token, id, Utc::now()))
        .await
        .map_err(|error| AppError::forbidden(error.to_string()))?;
    let expected_hash = headers
        .get("x-content-sha256")
        .and_then(|value| value.to_str().ok())
        .filter(|value| value.len() == 64 && value.chars().all(|ch| ch.is_ascii_hexdigit()))
        .ok_or_else(|| AppError::bad_request("x-content-sha256 is required"))?
        .to_ascii_lowercase();
    let declared = headers
        .get(header::CONTENT_LENGTH)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.parse::<u64>().ok())
        .ok_or_else(|| AppError::bad_request("Content-Length is required"))?;
    let limit = match kind.as_str() {
        "adapter" => crate::training::MAX_TRAINING_ARTIFACT_BYTES,
        "logs" => 64 * 1024 * 1024,
        "metrics" => 4 * 1024 * 1024,
        _ => return Err(AppError::bad_request("unsupported artifact kind")),
    };
    if declared == 0 || declared > limit {
        return Err(AppError::bad_request(
            "artifact size exceeds its fixed limit",
        ));
    }
    let reg = Arc::clone(&state.registry);
    let temporary = blocking(move || Ok(reg.temporary_object_path())).await?;
    let mut file = tokio::fs::File::create(&temporary).await?;
    let mut stream = request.into_body().into_data_stream();
    let mut digest = Sha256::new();
    let mut received = 0_u64;
    let upload_result: Result<(), AppError> = async {
        while let Some(chunk) = stream.next().await {
            let chunk = chunk.map_err(|error| AppError::bad_request(error.to_string()))?;
            received = received
                .checked_add(chunk.len() as u64)
                .ok_or_else(|| AppError::bad_request("artifact size overflow"))?;
            if received > limit || received > declared {
                return Err(AppError::bad_request(
                    "artifact exceeded declared or fixed size",
                ));
            }
            digest.update(&chunk);
            file.write_all(&chunk).await?;
        }
        file.flush().await?;
        file.sync_all().await?;
        Ok(())
    }
    .await;
    drop(file);
    if let Err(error) = upload_result {
        let _ = tokio::fs::remove_file(&temporary).await;
        return Err(error);
    }
    let actual = format!("{:x}", digest.finalize());
    if received != declared || actual != expected_hash {
        let _ = tokio::fs::remove_file(&temporary).await;
        return Err(AppError::bad_request(
            "artifact length or SHA-256 does not match the request",
        ));
    }
    let registry = Arc::clone(&state.registry);
    let path = temporary.clone();
    let hash = expected_hash.clone();
    let byte_length =
        tokio::task::spawn_blocking(move || registry.commit_object_file(&path, &hash))
            .await
            .map_err(|error| AppError::internal(error.to_string()))?
            .map_err(map_store_err)?;
    let artifact_kind = kind.clone();
    let artifact_hash = expected_hash.clone();
    let metadata = json!({"content_type":"application/octet-stream"});
    let reg = Arc::clone(&state.registry);
    blocking(move || {
        reg.save_training_artifact(
            id,
            &artifact_kind,
            &artifact_hash,
            byte_length,
            &metadata,
            Utc::now(),
        )
    })
    .await?;
    Ok((
        StatusCode::CREATED,
        Json(
            json!({"run_id":id,"kind":kind,"object_hash":expected_hash,"byte_length":byte_length}),
        ),
    ))
}

async fn complete_training_worker_run(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    headers: HeaderMap,
    Json(request): Json<WorkerCompleteRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    let token = worker_bearer(&headers)?.to_owned();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.authorize_worker_token(&token, id, Utc::now()))
        .await
        .map_err(|error| AppError::forbidden(error.to_string()))?;
    let reg = Arc::clone(&state.registry);
    let (run, bundle) =
        blocking(move || reg.complete_training_run_from_worker(id, &request, Utc::now()))
            .await
            .map_err(map_store_err)?;
    if let Some(provider) = state.gpu_provider.clone() {
        let registry = Arc::clone(&state.registry);
        tokio::spawn(async move {
            if let Err(error) = registry
                .release_training_gpu(id, provider.as_ref(), Utc::now())
                .await
            {
                tracing::error!(%id, error=%error, "completed run requires GPU release retry");
            }
        });
    }
    Ok((StatusCode::CREATED, Json(json!({"run":run,"model":bundle}))))
}

async fn fail_training_worker_run(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    headers: HeaderMap,
    Json(request): Json<WorkerFailRequest>,
) -> Result<Json<TrainingRun>, AppError> {
    let token = worker_bearer(&headers)?.to_owned();
    let reg = Arc::clone(&state.registry);
    blocking(move || reg.authorize_worker_token(&token, id, Utc::now()))
        .await
        .map_err(|error| AppError::forbidden(error.to_string()))?;
    let reg = Arc::clone(&state.registry);
    let run = blocking(move || reg.fail_training_run_from_worker(id, &request, Utc::now()))
        .await
        .map_err(map_store_err)?;
    if let Some(provider) = state.gpu_provider.clone() {
        let registry = Arc::clone(&state.registry);
        tokio::spawn(async move {
            if let Err(error) = registry
                .release_training_gpu(id, provider.as_ref(), Utc::now())
                .await
            {
                tracing::error!(%id, error=%error, "failed run requires GPU release retry");
            }
        });
    }
    Ok(Json(run))
}

fn worker_bearer(headers: &HeaderMap) -> Result<&str, AppError> {
    headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.strip_prefix("Bearer "))
        .filter(|value| !value.is_empty())
        .ok_or_else(|| AppError::forbidden("scoped worker token is required"))
}

fn parse_byte_range(
    header_value: Option<&HeaderValue>,
    total: u64,
) -> Result<(u64, u64, bool), AppError> {
    if total == 0 {
        return Err(AppError::not_found("training bundle is empty"));
    }
    let Some(value) = header_value else {
        return Ok((0, total - 1, false));
    };
    let value = value
        .to_str()
        .map_err(|_| AppError::bad_request("invalid Range header"))?;
    let range = value
        .strip_prefix("bytes=")
        .filter(|value| !value.contains(','))
        .ok_or_else(|| AppError::bad_request("only one byte range is supported"))?;
    let (start, end) = range
        .split_once('-')
        .ok_or_else(|| AppError::bad_request("invalid byte range"))?;
    let start = start
        .parse::<u64>()
        .map_err(|_| AppError::bad_request("suffix byte ranges are not supported"))?;
    let end = if end.is_empty() {
        total - 1
    } else {
        end.parse::<u64>()
            .map_err(|_| AppError::bad_request("invalid byte range end"))?
    };
    if start > end || end >= total {
        return Err(AppError {
            status: StatusCode::RANGE_NOT_SATISFIABLE,
            message: "byte range is outside the bundle".into(),
        });
    }
    Ok((start, end, true))
}

async fn admin_index(State(state): State<Arc<AppState>>) -> Response {
    let html =
        include_str!("../../../admin/index.html").replace("__CEREBELLUM_CSRF__", &state.admin_csrf);
    secure_admin_response("text/html; charset=utf-8", html)
}

async fn admin_javascript() -> Response {
    secure_admin_response(
        "text/javascript; charset=utf-8",
        include_str!("../../../admin/app.js").to_owned(),
    )
}

async fn admin_stylesheet() -> Response {
    secure_admin_response(
        "text/css; charset=utf-8",
        include_str!("../../../admin/style.css").to_owned(),
    )
}

fn secure_admin_response(content_type: &str, body: String) -> Response {
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type)
        .header(
            header::CONTENT_SECURITY_POLICY,
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
        )
        .header(header::X_CONTENT_TYPE_OPTIONS, "nosniff")
        .header("referrer-policy", "no-referrer")
        .header("cache-control", "no-store")
        .body(Body::from(body))
        .expect("static admin response is valid")
}
