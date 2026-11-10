use anyhow::{Result, bail};
use cerebellum_core::{
    AcquisitionAttempt, AcquisitionMethod, AcquisitionOutcome, AcquisitionPlan,
    AcquisitionPlanStatus, CurriculumPlan, SCHEMA_VERSION, SourceAccessMode, SourceKind,
};
use chrono::Timelike;
use chrono::{Duration as ChronoDuration, Utc};
use serde_json::Value;
use std::sync::Arc;
use std::time::Duration;
use uuid::Uuid;

use crate::acquisition::{self, ConditionalHeaders};
use crate::collector;
use crate::knowledge;
use crate::learning;
use crate::quality::{self, StructuredModelClient};
use crate::store::Registry;
use crate::text;

const AUTOMATED_JOB_KINDS: &[&str] = &[
    "github_search_v1",
    "github_collect_commit_v1",
    "training_manifest_refresh",
    "source_discover_v1",
    "knowledge_consolidate_v1",
    "retention_gc_v1",
    "dataset_draft_build_v1",
    "model_canary_eval_v1",
    "quality_assess_v1",
    "quality_arbitrate_v1",
    "synthetic_generate_v1",
    "dataset_quality_audit_v1",
    "quality_model_calibrate_v1",
    "quality_backfill_v1",
];

pub async fn run_loop(
    registry: Arc<Registry>,
    github_token: Option<String>,
    structured_model: Option<Arc<dyn StructuredModelClient>>,
    mediacrawler_search: bool,
) {
    let worker = format!("cerebellumd:{}", Uuid::new_v4());
    let mut interval = tokio::time::interval(Duration::from_secs(15));
    let mut maintenance_day = None;
    let mut dataset_day = None;
    loop {
        interval.tick().await;
        if let Err(error) = schedule_due_sources(&registry) {
            tracing::warn!(error=%error, "failed to schedule due knowledge sources");
        }
        let today = Utc::now().date_naive();
        if maintenance_day != Some(today) {
            let outcome = schedule_maintenance(&registry);
            advance_day_marker(
                &mut maintenance_day,
                today,
                outcome,
                "failed to schedule knowledge maintenance",
            );
        }
        let now = Utc::now();
        let shanghai_day = crate::shanghai_day(now);
        if crate::shanghai_time(now).hour() >= 3 && dataset_day != Some(shanghai_day) {
            let outcome = schedule_daily_dataset(registry.as_ref(), shanghai_day);
            advance_day_marker(
                &mut dataset_day,
                shanghai_day,
                outcome,
                "failed to schedule daily dataset draft",
            );
        }
        let outcome = {
            let registry = registry.clone();
            let worker = worker.clone();
            let github_token = github_token.clone();
            let structured_model = structured_model.clone();
            // The job execution body runs synchronous rusqlite work; drive it
            // on a blocking thread so the executor stays responsive.
            tokio::task::spawn_blocking(move || {
                tokio::runtime::Handle::current().block_on(run_once_with_model(
                    &registry,
                    &worker,
                    github_token.as_deref(),
                    structured_model.as_deref(),
                    mediacrawler_search,
                ))
            })
            .await
        };
        match outcome {
            Ok(Ok(Some((job_id, result_hash)))) => {
                tracing::info!(%job_id, %result_hash, "completed automated learning job");
            }
            Ok(Ok(None)) => {}
            Ok(Err(error)) => tracing::warn!(error=%error, "automated learning job failed"),
            Err(error) => tracing::warn!(error=%error, "automated learning job task failed"),
        }
    }
}

pub async fn run_once(
    registry: &Registry,
    worker: &str,
    github_token: Option<&str>,
    mediacrawler_search: bool,
) -> Result<Option<(Uuid, String)>> {
    run_once_with_model(registry, worker, github_token, None, mediacrawler_search).await
}

async fn run_once_with_model(
    registry: &Registry,
    worker: &str,
    github_token: Option<&str>,
    structured_model: Option<&dyn StructuredModelClient>,
    mediacrawler_search: bool,
) -> Result<Option<(Uuid, String)>> {
    let allowed = AUTOMATED_JOB_KINDS
        .iter()
        .copied()
        .filter(|kind| {
            structured_model.is_some()
                || !matches!(
                    *kind,
                    "quality_assess_v1"
                        | "quality_arbitrate_v1"
                        | "synthetic_generate_v1"
                        | "dataset_quality_audit_v1"
                        | "quality_model_calibrate_v1"
                        | "quality_backfill_v1"
                )
        })
        .collect::<Vec<_>>();
    let Some(job) = registry.claim_learning_job(Some(&allowed), worker, 300)? else {
        return Ok(None);
    };
    let result = execute(
        registry,
        &job.kind,
        &job.payload,
        github_token,
        structured_model,
        mediacrawler_search,
    )
    .await;
    match result {
        Ok(value) => {
            let hash = registry.save_learning_job_result(job.job_id, &value)?;
            registry.complete_learning_job(job.job_id, worker)?;
            Ok(Some((job.job_id, hash)))
        }
        Err(error) => {
            let retry_after = if job.kind == "source_discover_v1" {
                30_u64
                    .saturating_mul(2_u64.saturating_pow(job.attempts.saturating_sub(1)))
                    .min(3_600)
            } else if matches!(
                job.kind.as_str(),
                "quality_assess_v1"
                    | "quality_arbitrate_v1"
                    | "synthetic_generate_v1"
                    | "dataset_quality_audit_v1"
                    | "quality_model_calibrate_v1"
            ) {
                300_u64
                    .saturating_mul(2_u64.saturating_pow(job.attempts.saturating_sub(1)))
                    .min(21_600)
            } else {
                0
            };
            registry.fail_learning_job_with_delay(
                job.job_id,
                worker,
                &format!("{error:#}"),
                retry_after,
            )?;
            // Terminal failure (attempts exhausted -> dead-letter): advance the
            // source cursor so the next scheduler tick does not immediately
            // enqueue a fresh job for the failing source.
            if job.kind == "source_discover_v1" && job.attempts >= job.max_attempts {
                defer_source_after_terminal_failure(registry, &job.payload);
            }
            Err(error)
        }
    }
}

async fn execute(
    registry: &Registry,
    kind: &str,
    payload: &Value,
    github_token: Option<&str>,
    structured_model: Option<&dyn StructuredModelClient>,
    mediacrawler_search: bool,
) -> Result<Value> {
    match kind {
        "github_search_v1" => {
            let plan: CurriculumPlan = serde_json::from_value(payload.clone())?;
            registry.reserve_acquisition_budget(
                0,
                plan.policy.daily_budget.new_repositories,
                plan.policy.daily_budget.files,
            )?;
            Ok(serde_json::to_value(
                collector::execute_curriculum(registry, &plan, github_token).await?,
            )?)
        }
        "github_collect_commit_v1" => {
            let repository_url = payload
                .get("repository_url")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow::anyhow!("webhook job lacks repository_url"))?;
            let commit_sha = payload
                .get("commit_sha")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow::anyhow!("webhook job lacks commit_sha"))?;
            let source_policy_id = payload
                .get("source_policy_id")
                .and_then(Value::as_str)
                .map(|value| {
                    Uuid::parse_str(value)
                        .map_err(|_| anyhow::anyhow!("webhook job has invalid source_policy_id"))
                })
                .transpose()?;
            let topic_ids = payload
                .get("topic_ids")
                .and_then(Value::as_array)
                .map(|values| {
                    values
                        .iter()
                        .map(|value| {
                            value
                                .as_str()
                                .and_then(|raw| Uuid::parse_str(raw).ok())
                                .ok_or_else(|| {
                                    anyhow::anyhow!("webhook job has invalid topic_ids entry")
                                })
                        })
                        .collect::<Result<Vec<_>>>()
                })
                .transpose()?
                .unwrap_or_default();
            let max_files = payload
                .get("max_files")
                .and_then(Value::as_u64)
                .unwrap_or(100)
                .min(500) as usize;
            registry.reserve_acquisition_budget(0, 1, max_files as u32)?;
            Ok(serde_json::to_value(
                collector::collect_github_bounded(
                    registry,
                    repository_url,
                    commit_sha,
                    github_token,
                    max_files,
                    source_policy_id,
                    topic_ids,
                )
                .await?,
            )?)
        }
        "source_discover_v1" => {
            execute_source_discovery(registry, payload, github_token, mediacrawler_search).await
        }
        "knowledge_consolidate_v1" => {
            let document_id = payload
                .get("document_id")
                .and_then(Value::as_str)
                .and_then(|value| Uuid::parse_str(value).ok())
                .ok_or_else(|| anyhow::anyhow!("consolidation job lacks document_id"))?;
            let outcome = if let Some(client) = structured_model {
                knowledge::consolidate_document_with_structured_model_fallback(
                    registry,
                    document_id,
                    client,
                )
                .await?
            } else {
                knowledge::consolidate_document(registry, document_id)?
            };
            Ok(serde_json::to_value(outcome)?)
        }
        "retention_gc_v1" => {
            Ok(serde_json::json!({"removed_objects":registry.retention_gc(Utc::now())?}))
        }
        "dataset_draft_build_v1" => {
            let kind = payload
                .get("kind")
                .and_then(Value::as_str)
                .unwrap_or(crate::dataset_factory::META_DATASET_KIND);
            Ok(serde_json::to_value(
                registry.build_dataset_draft(kind, Utc::now())?,
            )?)
        }
        "quality_assess_v1" | "quality_arbitrate_v1" => {
            let client = structured_model
                .ok_or_else(|| anyhow::anyhow!("local structured model is unavailable"))?;
            let subject_kind = serde_json::from_value(
                payload
                    .get("subject_kind")
                    .cloned()
                    .ok_or_else(|| anyhow::anyhow!("quality job lacks subject_kind"))?,
            )?;
            let subject_id = payload
                .get("subject_id")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow::anyhow!("quality job lacks subject_id"))?;
            let parent = payload
                .get("parent_assessment_id")
                .and_then(Value::as_str)
                .map(Uuid::parse_str)
                .transpose()?;
            let stage = if kind == "quality_assess_v1" {
                cerebellum_core::QualityModelStage::Flash
            } else {
                cerebellum_core::QualityModelStage::Pro
            };
            Ok(serde_json::to_value(
                quality::assess_subject(
                    registry,
                    client,
                    quality::QualityAssessmentTarget {
                        subject_kind,
                        subject_id,
                        stage,
                        parent_assessment_id: parent,
                        now: Utc::now(),
                    },
                )
                .await?,
            )?)
        }
        "synthetic_generate_v1" => {
            let client = structured_model
                .ok_or_else(|| anyhow::anyhow!("local structured model is unavailable"))?;
            let subject_kind = serde_json::from_value(
                payload
                    .get("subject_kind")
                    .cloned()
                    .ok_or_else(|| anyhow::anyhow!("synthetic job lacks subject_kind"))?,
            )?;
            let subject_id = payload
                .get("subject_id")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow::anyhow!("synthetic job lacks subject_id"))?;
            Ok(serde_json::to_value(
                quality::generate_synthetic_candidate(
                    registry,
                    client,
                    subject_kind,
                    subject_id,
                    Utc::now(),
                )
                .await?,
            )?)
        }
        "quality_backfill_v1" => Ok(serde_json::json!({
            "scheduled": registry.enqueue_quality_backfill(
                payload.get("limit").and_then(Value::as_u64).unwrap_or(1_000) as usize
            )?
        })),
        "quality_model_calibrate_v1" => {
            let endpoint_id = payload
                .get("endpoint_version_id")
                .and_then(Value::as_str)
                .and_then(|value| Uuid::parse_str(value).ok())
                .ok_or_else(|| anyhow::anyhow!("calibration job lacks endpoint_version_id"))?;
            if let Some(metrics) = payload.get("metrics") {
                Ok(serde_json::to_value(
                    registry.apply_model_calibration_metrics(
                        endpoint_id,
                        serde_json::from_value(metrics.clone())?,
                        Utc::now(),
                    )?,
                )?)
            } else {
                let client = structured_model
                    .ok_or_else(|| anyhow::anyhow!("local structured model is unavailable"))?;
                Ok(serde_json::to_value(
                    quality::run_fixed_model_calibration(registry, client, endpoint_id, Utc::now())
                        .await?,
                )?)
            }
        }
        "dataset_quality_audit_v1" => {
            let build_id = payload
                .get("build_id")
                .and_then(Value::as_str)
                .and_then(|value| Uuid::parse_str(value).ok())
                .ok_or_else(|| anyhow::anyhow!("dataset audit job lacks build_id"))?;
            Ok(serde_json::to_value(
                registry.audit_dataset_quality(build_id, Utc::now())?,
            )?)
        }
        "model_canary_eval_v1" => {
            let model_id = payload
                .get("model_id")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow::anyhow!("canary eval job lacks model_id"))?;
            let version = payload
                .get("version")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow::anyhow!("canary eval job lacks version"))?;
            let metrics = serde_json::from_value(
                payload
                    .get("metrics")
                    .cloned()
                    .ok_or_else(|| anyhow::anyhow!("canary eval job lacks metrics"))?,
            )?;
            Ok(serde_json::to_value(registry.evaluate_meta_model(
                model_id,
                version,
                metrics,
                Utc::now(),
            )?)?)
        }
        "training_manifest_refresh" => Ok(serde_json::to_value(
            learning::build_training_candidate(registry)?,
        )?),
        other => bail!("automated scheduler refuses unsupported job kind: {other}"),
    }
}

pub fn schedule_due_sources(registry: &Registry) -> Result<usize> {
    let now = Utc::now();
    let mut scheduled = 0;
    for topic in registry.list_topic_watches(true)? {
        for policy_id in &topic.source_policy_ids {
            let Some(policy) = registry.get_source_policy(*policy_id)? else {
                continue;
            };
            if !policy.enabled {
                continue;
            }
            let cursor = registry.get_source_cursor(*policy_id)?;
            if cursor
                .as_ref()
                .and_then(|cursor| cursor.next_poll_at)
                .is_some_and(|next| next > now)
            {
                continue;
            }
            let interval = source_interval_seconds(policy.kind, topic.refresh_seconds);
            let window = now.timestamp().div_euclid(i64::from(interval));
            let plan = AcquisitionPlan {
                schema_version: SCHEMA_VERSION.into(),
                plan_id: Uuid::new_v4(),
                topic_id: topic.topic_id,
                query: topic.query.clone(),
                source_policy_ids: vec![*policy_id],
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
            let job = registry.enqueue_unique_learning_job(
                "source_discover_v1",
                &format!("{}:{}:{window}", policy.policy_id, topic.topic_id),
                serde_json::json!({
                    "plan_id":plan.plan_id,
                    "topic_id":topic.topic_id,
                    "source_policy_id":policy.policy_id
                }),
                0.7,
                5,
            )?;
            if job.is_some() {
                scheduled += 1;
            } else {
                registry
                    .transition_acquisition_plan(plan.plan_id, AcquisitionPlanStatus::Cancelled)?;
            }
        }
    }
    Ok(scheduled)
}

fn schedule_maintenance(registry: &Registry) -> Result<()> {
    registry.training_token_gc(Utc::now())?;
    // Day-scoped dedup: the in-memory maintenance_day marker is lost on
    // restart, so without a dedup key every same-day restart would enqueue
    // another retention GC.
    registry.enqueue_unique_learning_job(
        "retention_gc_v1",
        &format!("retention_gc:{}", Utc::now().date_naive()),
        serde_json::json!({"scheduled_at":Utc::now()}),
        0.1,
        3,
    )?;
    registry.prune_dataset_builds(crate::dataset_factory::META_DATASET_KIND)?;
    registry.prune_dataset_builds(crate::dataset_factory::KNOWLEDGE_WEB_DATASET_KIND)?;
    Ok(())
}

fn schedule_daily_dataset(registry: &Registry, shanghai_day: chrono::NaiveDate) -> Result<()> {
    for kind in [
        crate::dataset_factory::META_DATASET_KIND,
        crate::dataset_factory::KNOWLEDGE_WEB_DATASET_KIND,
    ] {
        registry.enqueue_unique_learning_job(
            "dataset_draft_build_v1",
            &format!("{kind}:{shanghai_day}"),
            serde_json::json!({
                "kind":kind,
                "scheduled_for":"03:00 Asia/Shanghai",
                "shanghai_day":shanghai_day
            }),
            0.55,
            3,
        )?;
    }
    Ok(())
}

/// Advance a once-per-day marker only when the schedule succeeded; a
/// transient error leaves the marker untouched so the next tick retries
/// instead of permanently skipping the day until restart.
fn advance_day_marker(
    marker: &mut Option<chrono::NaiveDate>,
    day: chrono::NaiveDate,
    outcome: Result<()>,
    context: &str,
) {
    match outcome {
        Ok(()) => *marker = Some(day),
        Err(error) => tracing::warn!(error=%error, "{}", context),
    }
}

/// A terminally failed discovery run must not let the next scheduler tick
/// enqueue a fresh multi-attempt job for a source that keeps failing: push
/// the poll cursor out by the policy interval so the source is retried on
/// its normal cadence instead of every tick.
fn defer_source_after_terminal_failure(registry: &Registry, payload: &Value) {
    let outcome = (|| -> Result<()> {
        let policy_id = payload_uuid(payload, "source_policy_id")?;
        let topic_id = payload_uuid(payload, "topic_id")?;
        let policy = registry
            .get_source_policy(policy_id)?
            .ok_or_else(|| anyhow::anyhow!("source policy not found"))?;
        let topic = registry
            .get_topic_watch(topic_id)?
            .ok_or_else(|| anyhow::anyhow!("topic watch not found"))?;
        let interval = source_interval_seconds(policy.kind, topic.refresh_seconds);
        let next_poll = Utc::now() + ChronoDuration::seconds(i64::from(interval));
        let cursor = registry.get_source_cursor(policy_id)?;
        // Never pull the cursor back when a later success already scheduled
        // a poll further out.
        if cursor
            .as_ref()
            .and_then(|cursor| cursor.next_poll_at)
            .is_some_and(|existing| existing >= next_poll)
        {
            return Ok(());
        }
        registry.upsert_source_cursor(
            policy_id,
            cursor.as_ref().and_then(|cursor| cursor.cursor.as_deref()),
            cursor.as_ref().and_then(|cursor| cursor.etag.as_deref()),
            cursor
                .as_ref()
                .and_then(|cursor| cursor.last_modified.as_deref()),
            Some(next_poll),
        )
    })();
    if let Err(error) = outcome {
        tracing::warn!(error=%error, "failed to defer source after terminal discovery failure");
    }
}

async fn execute_source_discovery(
    registry: &Registry,
    payload: &Value,
    github_token: Option<&str>,
    mediacrawler_search: bool,
) -> Result<Value> {
    let plan_id = payload_uuid(payload, "plan_id")?;
    let source_policy_id = payload_uuid(payload, "source_policy_id")?;
    let plan = registry.transition_acquisition_plan(plan_id, AcquisitionPlanStatus::Running)?;
    let result = execute_source_discovery_inner(
        registry,
        &plan,
        source_policy_id,
        github_token,
        mediacrawler_search,
    )
    .await;
    match result {
        Ok(value) => {
            registry.transition_acquisition_plan(plan_id, AcquisitionPlanStatus::Completed)?;
            Ok(value)
        }
        Err(error) => {
            let _ = registry.transition_acquisition_plan(plan_id, AcquisitionPlanStatus::Failed);
            Err(error)
        }
    }
}

async fn execute_source_discovery_inner(
    registry: &Registry,
    plan: &AcquisitionPlan,
    source_policy_id: Uuid,
    github_token: Option<&str>,
    mediacrawler_search: bool,
) -> Result<Value> {
    let topic = registry
        .get_topic_watch(plan.topic_id)?
        .ok_or_else(|| anyhow::anyhow!("topic watch not found"))?;
    let policy = registry
        .get_source_policy(source_policy_id)?
        .ok_or_else(|| anyhow::anyhow!("source policy not found"))?;
    registry.reserve_topic_budget(topic.topic_id, 1, 0, 0, 0)?;
    let interval = source_interval_seconds(policy.kind, topic.refresh_seconds);
    let next_poll = Utc::now() + ChronoDuration::seconds(i64::from(interval));

    if matches!(
        policy.kind,
        SourceKind::Weibo
            | SourceKind::Zhihu
            | SourceKind::Douyin
            | SourceKind::Bilibili
            | SourceKind::Xhs
            | SourceKind::Baidu
            | SourceKind::Kuaishou
            | SourceKind::Tieba
            | SourceKind::OpenAlex
            | SourceKind::Arxiv
            | SourceKind::Journal
    ) {
        // List-type discovery (hot boards / paper collections) is delegated to
        // the isolated social acquisition worker under its own job kind; the
        // claim protocol discriminates workers by job kind, so reusing
        // document_acquire_v1 would let either worker steal the other's jobs.
        let job = registry.enqueue_unique_learning_job(
            "social_acquisition_v1",
            &format!("social:{}:{}", policy.policy_id, plan.plan_id),
            serde_json::json!({
                "plan_id":plan.plan_id,
                "topic_ids":[topic.topic_id],
                "source_policy_id":policy.policy_id,
                "provider":policy.kind,
                "query":plan.query,
                "source_policy":policy
            }),
            0.65,
            5,
        )?;
        if mediacrawler_search && policy.access_mode == SourceAccessMode::AuthenticatedLocal {
            // Platform keyword search rides the same job kind but is
            // dispatched by the worker via payload["crawler_type"]=="search"
            // (see social worker _provider_for); documents of the two batches
            // carry distinct titles so they never share stable ids.
            registry.enqueue_unique_learning_job(
                "social_acquisition_v1",
                &format!("social-search:{}:{}", policy.policy_id, plan.plan_id),
                serde_json::json!({"plan_id":plan.plan_id,"topic_ids":[topic.topic_id],
                  "source_policy_id":policy.policy_id,"provider":policy.kind,"query":plan.query,
                  "source_policy":policy,"crawler_type":"search"}),
                0.6,
                5,
            )?;
        }
        registry.upsert_source_cursor(policy.policy_id, None, None, None, Some(next_poll))?;
        return Ok(serde_json::json!({
            "delegated":true,
            "job_id":job.map(|job| job.job_id),
            "provider":policy.kind
        }));
    }

    if matches!(
        policy.kind,
        SourceKind::Tavily
            | SourceKind::Firecrawl
            | SourceKind::Crawl4ai
            | SourceKind::Scrapling
            | SourceKind::OpenCli
    ) {
        let job = registry.enqueue_unique_learning_job(
            "document_acquire_v1",
            &format!("provider:{}:{}", policy.policy_id, plan.plan_id),
            serde_json::json!({
                "plan_id":plan.plan_id,
                "topic_ids":[topic.topic_id],
                "source_policy_id":policy.policy_id,
                "provider":policy.kind,
                "query":plan.query,
                "source_policy":policy
            }),
            0.65,
            5,
        )?;
        registry.upsert_source_cursor(policy.policy_id, None, None, None, Some(next_poll))?;
        return Ok(serde_json::json!({
            "delegated":true,
            "job_id":job.map(|job| job.job_id),
            "provider":policy.kind
        }));
    }

    let cursor = registry.get_source_cursor(policy.policy_id)?;
    let conditional = ConditionalHeaders {
        etag: cursor.as_ref().and_then(|cursor| cursor.etag.clone()),
        last_modified: cursor
            .as_ref()
            .and_then(|cursor| cursor.last_modified.clone()),
    };
    let reserved_requests = if policy.kind == SourceKind::HackerNews {
        policy.rate_limit_per_minute
    } else {
        1
    };
    registry.reserve_source_poll(policy.policy_id, reserved_requests)?;
    let started_at = Utc::now();
    let batch = acquisition::discover_source(
        &policy,
        cursor.as_ref().and_then(|cursor| cursor.cursor.as_deref()),
        &conditional,
        github_token,
    )
    .await?;
    let mut accepted = Vec::new();
    let mut rejected = Vec::new();
    for item in batch
        .items
        .into_iter()
        .filter(|item| acquisition::topic_matches(item, &topic.query, &topic.keywords))
        .take(plan.max_documents as usize)
    {
        match text::canonicalize_public_url(&item.url, &policy.allowed_domains) {
            Ok(canonical_url) => accepted.push((item, canonical_url)),
            Err(error) => rejected.push(serde_json::json!({
                "url":item.url,
                "reason":error.to_string()
            })),
        }
    }
    registry.reserve_topic_budget(topic.topic_id, 0, accepted.len() as u32, 0, 0)?;
    let mut job_ids = Vec::new();
    for (item, canonical_url) in accepted {
        let key = format!(
            "{}:{}:{}",
            policy.policy_id,
            item.external_id.as_deref().unwrap_or_default(),
            canonical_url
        );
        if let Some(job) = registry.enqueue_unique_learning_job(
            "document_acquire_v1",
            &key,
            serde_json::json!({
                "plan_id":plan.plan_id,
                "topic_ids":[topic.topic_id],
                "source_policy_id":policy.policy_id,
                "source_policy":policy,
                "item":item,
                "canonical_url":canonical_url
            }),
            0.75,
            5,
        )? {
            job_ids.push(job.job_id);
        }
    }
    registry.save_acquisition_attempt(&AcquisitionAttempt {
        schema_version: SCHEMA_VERSION.into(),
        attempt_id: Uuid::new_v4(),
        plan_id: plan.plan_id,
        source_policy_id: policy.policy_id,
        url: policy.base_url.clone(),
        canonical_url: text::canonicalize_public_url(&policy.base_url, &policy.allowed_domains)?,
        method: source_method(policy.kind),
        outcome: AcquisitionOutcome::Success,
        http_status: Some(if batch.not_modified { 304 } else { 200 }),
        retry_after_seconds: None,
        content_hash: None,
        error_code: None,
        cost: 0.0,
        started_at,
        finished_at: Utc::now(),
    })?;
    registry.upsert_source_cursor(
        policy.policy_id,
        batch.cursor.as_deref(),
        batch.etag.as_deref(),
        batch.last_modified.as_deref(),
        Some(next_poll),
    )?;
    Ok(serde_json::json!({
        "not_modified":batch.not_modified,
        "scheduled_documents":job_ids.len(),
        "job_ids":job_ids,
        "rejected":rejected
    }))
}

fn payload_uuid(payload: &Value, field: &str) -> Result<Uuid> {
    payload
        .get(field)
        .and_then(Value::as_str)
        .and_then(|value| Uuid::parse_str(value).ok())
        .ok_or_else(|| anyhow::anyhow!("job lacks valid {field}"))
}

fn source_method(kind: SourceKind) -> AcquisitionMethod {
    match kind {
        SourceKind::RssAtom => AcquisitionMethod::Rss,
        SourceKind::Github | SourceKind::HackerNews => AcquisitionMethod::Api,
        _ => AcquisitionMethod::DirectHttp,
    }
}

fn source_interval_seconds(kind: SourceKind, configured: u32) -> u32 {
    let floor = match kind {
        SourceKind::HackerNews => 30,
        SourceKind::Github | SourceKind::RssAtom => 120,
        SourceKind::Tavily | SourceKind::Firecrawl => 1_800,
        SourceKind::Weibo
        | SourceKind::Zhihu
        | SourceKind::Douyin
        | SourceKind::Bilibili
        | SourceKind::Xhs
        | SourceKind::Baidu
        | SourceKind::Kuaishou
        | SourceKind::Tieba => 300,
        SourceKind::OpenAlex | SourceKind::Arxiv | SourceKind::Journal => 3_600,
        _ => 120,
    };
    configured.max(floor)
}

#[cfg(test)]
mod tests {
    use super::*;
    use cerebellum_core::{
        CreateSourcePolicyRequest, CreateTopicWatchRequest, DataClassification,
        ExternalProcessingPermission,
    };
    use tempfile::tempdir;

    #[tokio::test]
    async fn worker_only_claims_allowlisted_automatic_jobs() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let manual = registry
            .enqueue_learning_job("evolver_consolidate_v1", serde_json::json!({}), 10.0, 3)
            .unwrap();
        let automatic = registry
            .enqueue_learning_job("training_manifest_refresh", serde_json::json!({}), 1.0, 2)
            .unwrap();

        let result = run_once(&registry, "scheduler-test", None, false)
            .await
            .unwrap()
            .unwrap();

        assert_eq!(result.0, automatic.job_id);
        let claimed = registry
            .claim_learning_job(None, "evolver-worker", 30)
            .unwrap()
            .unwrap();
        assert_eq!(claimed.job_id, manual.job_id);
    }

    #[test]
    fn daily_dataset_schedule_is_idempotent_and_never_enqueues_training() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let day = chrono::NaiveDate::from_ymd_opt(2026, 8, 24).unwrap();
        schedule_daily_dataset(&registry, day).unwrap();
        schedule_daily_dataset(&registry, day).unwrap();
        // 每日各入队一次：meta-controller 与 knowledge-web（dedup key 含 kind，
        // 重复调度幂等，仍是每 kind 恰好一个 job）。
        let first = registry
            .claim_learning_job(Some(&["dataset_draft_build_v1"]), "test", 30)
            .unwrap()
            .unwrap();
        let second = registry
            .claim_learning_job(Some(&["dataset_draft_build_v1"]), "test", 30)
            .unwrap()
            .unwrap();
        let mut kinds = vec![
            first.payload["kind"].as_str().unwrap().to_owned(),
            second.payload["kind"].as_str().unwrap().to_owned(),
        ];
        kinds.sort();
        assert_eq!(kinds, vec!["knowledge-web", "meta-controller"]);
        assert!(
            registry
                .claim_learning_job(Some(&["dataset_draft_build_v1"]), "test", 30)
                .unwrap()
                .is_none()
        );
        assert!(
            registry
                .claim_learning_job(Some(&["meta_train_v1"]), "test", 30)
                .unwrap()
                .is_none()
        );
    }

    #[test]
    fn restart_schedules_current_day_only_without_missed_day_catchup() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let missed = chrono::NaiveDate::from_ymd_opt(2026, 8, 24).unwrap();
        let today = chrono::NaiveDate::from_ymd_opt(2026, 8, 25).unwrap();
        // The daemon was down on `missed`. After a restart the in-memory day
        // marker is empty and only the current day is scheduled: the dedup key
        // carries the day, so no job for the missed day is ever enqueued.
        // Skipping the missed day is the intended semantic (pinned, not a bug).
        schedule_daily_dataset(&registry, today).unwrap();
        let mut scheduled_days = Vec::new();
        while let Some(job) = registry
            .claim_learning_job(Some(&["dataset_draft_build_v1"]), "test", 30)
            .unwrap()
        {
            scheduled_days.push(job.payload["shanghai_day"].as_str().unwrap().to_owned());
        }
        assert_eq!(scheduled_days.len(), 2);
        assert!(scheduled_days.iter().all(|day| day == &today.to_string()));
        assert!(!scheduled_days.iter().any(|day| day == &missed.to_string()));
    }

    #[test]
    fn day_marker_only_advances_on_success() {
        let day = chrono::NaiveDate::from_ymd_opt(2026, 1, 2).unwrap();
        let mut marker = None;
        // A transient schedule error must leave the marker unset so the next
        // tick retries; the old behavior marked the day anyway and skipped it
        // until restart.
        advance_day_marker(
            &mut marker,
            day,
            Err(anyhow::anyhow!("transient store error")),
            "test context",
        );
        assert_eq!(marker, None);
        advance_day_marker(&mut marker, day, Ok(()), "test context");
        assert_eq!(marker, Some(day));
        // Once marked, a failed retry later that day keeps the marker.
        advance_day_marker(
            &mut marker,
            day,
            Err(anyhow::anyhow!("transient store error")),
            "test context",
        );
        assert_eq!(marker, Some(day));
    }

    #[test]
    fn same_day_maintenance_enqueues_single_retention_gc() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        // Simulates a same-day restart: maintenance_day is in-memory, so the
        // dedup key must keep a second same-day schedule from enqueuing
        // another retention GC.
        schedule_maintenance(&registry).unwrap();
        schedule_maintenance(&registry).unwrap();
        let job = registry
            .claim_learning_job(Some(&["retention_gc_v1"]), "test", 30)
            .unwrap();
        assert!(job.is_some());
        assert!(
            registry
                .claim_learning_job(Some(&["retention_gc_v1"]), "test", 30)
                .unwrap()
                .is_none()
        );
    }

    #[tokio::test]
    async fn terminal_discovery_failure_defers_next_poll() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let source = registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "Failing RSS".into(),
                kind: SourceKind::RssAtom,
                base_url: "https://example.com/feed.xml".into(),
                access_mode: SourceAccessMode::Public,
                allowed_domains: vec!["example.com".into()],
                obey_robots: true,
                max_depth: 2,
                max_pages_per_run: 20,
                rate_limit_per_minute: 30,
                raw_retention_days: 30,
                training_license: None,
                model_terms_allow_training: false,
                auth_secret_ref: None,
                data_classification: DataClassification::Public,
                external_processing: ExternalProcessingPermission::Denied,
                enabled: true,
            })
            .unwrap();
        let topic = registry
            .create_topic_watch(&CreateTopicWatchRequest {
                name: "Agent memory".into(),
                query: "agent memory workflow".into(),
                keywords: vec!["workflow".into()],
                entities: vec![],
                languages: vec!["en".into()],
                source_policy_ids: vec![source.policy_id],
                refresh_seconds: 120,
                budget: Default::default(),
                enabled: true,
            })
            .unwrap();
        // The plan id does not exist, so execution fails deterministically
        // before any network access; a single attempt makes it terminal.
        registry
            .enqueue_learning_job(
                "source_discover_v1",
                serde_json::json!({
                    "plan_id":Uuid::new_v4(),
                    "topic_id":topic.topic_id,
                    "source_policy_id":source.policy_id
                }),
                0.7,
                1,
            )
            .unwrap();

        let before = Utc::now();
        let result = run_once(&registry, "scheduler-test", None, false).await;
        assert!(result.is_err());

        let cursor = registry
            .get_source_cursor(source.policy_id)
            .unwrap()
            .expect("terminal failure must advance the source cursor");
        let next_poll = cursor
            .next_poll_at
            .expect("terminal failure must set next_poll_at");
        let interval = i64::from(source_interval_seconds(source.kind, 120));
        assert!(next_poll >= before + ChronoDuration::seconds(interval));
        assert!(next_poll <= Utc::now() + ChronoDuration::seconds(interval));
    }

    #[test]
    fn shanghai_day_rolls_over_at_utc_plus_eight_midnight() {
        let before = chrono::DateTime::parse_from_rfc3339("2026-01-01T15:59:59Z")
            .unwrap()
            .with_timezone(&Utc);
        let after = chrono::DateTime::parse_from_rfc3339("2026-01-01T16:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        assert_eq!(
            crate::shanghai_day(before),
            chrono::NaiveDate::from_ymd_opt(2026, 1, 1).unwrap()
        );
        assert_eq!(
            crate::shanghai_day(after),
            chrono::NaiveDate::from_ymd_opt(2026, 1, 2).unwrap()
        );
        // The shifted civil time the scheduler gates on shares the same offset.
        assert_eq!(crate::shanghai_time(after).hour(), 0);
    }

    #[tokio::test]
    async fn github_collect_rejects_malformed_policy_and_topic_ids_before_network() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let sha = "a".repeat(40);
        let base = serde_json::json!({
            "repository_url": "https://github.com/openai/example",
            "commit_sha": sha,
        });
        let mut invalid_policy = base.clone();
        invalid_policy["source_policy_id"] = serde_json::json!("not-a-uuid");
        let error = execute(
            &registry,
            "github_collect_commit_v1",
            &invalid_policy,
            None,
            None,
            false,
        )
        .await
        .unwrap_err();
        assert!(
            format!("{error:#}").contains("invalid source_policy_id"),
            "unexpected error: {error:#}"
        );
        let mut invalid_topics = base.clone();
        invalid_topics["topic_ids"] = serde_json::json!([Uuid::new_v4().to_string(), "nope"]);
        let error = execute(
            &registry,
            "github_collect_commit_v1",
            &invalid_topics,
            None,
            None,
            false,
        )
        .await
        .unwrap_err();
        assert!(
            format!("{error:#}").contains("invalid topic_ids"),
            "unexpected error: {error:#}"
        );
    }
}
