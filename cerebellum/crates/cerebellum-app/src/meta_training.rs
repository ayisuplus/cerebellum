use crate::Registry;
use anyhow::{Result, anyhow, bail};
use cerebellum_core::{
    MetaCanaryDecision, MetaDecisionTrace, MetaModelBundle, MetaModelMetrics, MetaModelStatus,
    MetaReplayEvaluation, MetaTaskKind, MetaTrainingCandidate, SCHEMA_VERSION, canonical_json_hash,
    validate_meta_canary_decision, validate_meta_decision_trace, validate_meta_model_bundle,
    validate_meta_replay_evaluation,
};
use chrono::{DateTime, Duration, Utc};
use rusqlite::{OptionalExtension, params};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use uuid::Uuid;

pub const MIN_META_DECISIONS: usize = 5_000;
pub const MIN_META_REPLAYS: usize = 1_000;
pub const META_TRAINING_COOLDOWN_DAYS: i64 = 7;
pub const MIN_CANARY_DECISIONS: u64 = 1_000;
pub const MIN_CANARY_HOURS: i64 = 24;

impl Registry {
    pub fn record_meta_decision(&self, trace: &MetaDecisionTrace) -> Result<bool> {
        validate_meta_decision_trace(trace)?;
        if trace.training_eligible && contains_sensitive_value(&trace.input) {
            bail!("training-eligible meta decision contains sensitive material");
        }
        let value = serde_json::to_value(trace)?;
        let content_hash = canonical_json_hash(&value);
        let json = serde_json::to_string(trace)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT content_hash FROM meta_decision_traces WHERE id=?1",
                params![trace.decision_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == content_hash {
                return Ok(false);
            }
            bail!("meta decision ids are immutable");
        }
        conn.execute(
            "INSERT INTO meta_decision_traces(
               id,task_kind,input_hash,source_domain,topic_family,training_eligible,
               trace_json,content_hash,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9)",
            params![
                trace.decision_id.to_string(),
                meta_task_name(trace.task_kind),
                trace.input_hash,
                trace.source_domain,
                trace.topic_family,
                trace.training_eligible as i64,
                json,
                content_hash,
                trace.created_at.to_rfc3339()
            ],
        )?;
        Ok(true)
    }

    pub fn record_meta_replay(&self, evaluation: &MetaReplayEvaluation) -> Result<bool> {
        validate_meta_replay_evaluation(evaluation)?;
        let value = serde_json::to_value(evaluation)?;
        let content_hash = canonical_json_hash(&value);
        let json = serde_json::to_string(evaluation)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT content_hash FROM meta_replay_evaluations WHERE id=?1",
                params![evaluation.evaluation_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == content_hash {
                return Ok(false);
            }
            bail!("meta replay ids are immutable");
        }
        conn.execute(
            "INSERT INTO meta_replay_evaluations(
               id,candidate_id,source_domain,topic_family,safety_passed,
               evaluation_json,content_hash,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8)",
            params![
                evaluation.evaluation_id.to_string(),
                evaluation.candidate_id.map(|id| id.to_string()),
                evaluation.source_domain,
                evaluation.topic_family,
                evaluation.safety_passed as i64,
                json,
                content_hash,
                evaluation.created_at.to_rfc3339()
            ],
        )?;
        Ok(true)
    }

    pub fn prepare_meta_training_candidate(
        &self,
        now: DateTime<Utc>,
    ) -> Result<MetaTrainingCandidate> {
        self.prepare_meta_training_candidate_with_thresholds(
            now,
            MIN_META_DECISIONS,
            MIN_META_REPLAYS,
        )
    }

    pub(crate) fn prepare_meta_training_candidate_with_thresholds(
        &self,
        now: DateTime<Utc>,
        minimum_decisions: usize,
        minimum_replays: usize,
    ) -> Result<MetaTrainingCandidate> {
        let (traces, replays, latest_candidate) = {
            let conn = self.lock_conn();
            let trace_json = {
                let mut statement = conn.prepare(
                    "SELECT trace_json FROM meta_decision_traces
                     WHERE training_eligible=1 ORDER BY created_at,id",
                )?;
                statement
                    .query_map([], |row| row.get::<_, String>(0))?
                    .collect::<rusqlite::Result<Vec<_>>>()?
            };
            let replay_json = {
                let mut statement = conn.prepare(
                    "SELECT evaluation_json FROM meta_replay_evaluations
                     WHERE safety_passed=1 ORDER BY created_at,id",
                )?;
                statement
                    .query_map([], |row| row.get::<_, String>(0))?
                    .collect::<rusqlite::Result<Vec<_>>>()?
            };
            let latest: Option<String> = conn.query_row(
                "SELECT MAX(created_at) FROM meta_training_candidates",
                [],
                |row| row.get(0),
            )?;
            (trace_json, replay_json, latest)
        };
        if let Some(latest) = latest_candidate {
            let latest = parse_time(&latest)?;
            if now < latest + Duration::days(META_TRAINING_COOLDOWN_DAYS) {
                bail!("meta training candidates may be prepared at most once per week");
            }
        }
        let mut deduplicated = BTreeMap::new();
        for json in traces {
            let trace: MetaDecisionTrace = serde_json::from_str(&json)?;
            deduplicated.insert(
                (
                    meta_task_name(trace.task_kind).to_owned(),
                    trace.input_hash.clone(),
                ),
                trace,
            );
        }
        let traces = deduplicated.into_values().collect::<Vec<_>>();
        let mut replay_keys = BTreeSet::new();
        let mut replay_records = Vec::new();
        for json in replays {
            let replay: MetaReplayEvaluation = serde_json::from_str(&json)?;
            let key = (
                replay.task_id.clone(),
                replay.source_domain.clone(),
                replay.topic_family.clone(),
            );
            if replay_keys.insert(key) {
                replay_records.push(replay);
            }
        }
        if traces.len() < minimum_decisions || replay_records.len() < minimum_replays {
            bail!(
                "insufficient meta-learning evidence: {} decisions and {} replay evaluations",
                traces.len(),
                replay_records.len()
            );
        }

        let mut dataset = Vec::new();
        let group_months = crate::dataset_factory::group_earliest_month(
            traces
                .iter()
                .map(|trace| {
                    (
                        trace.source_domain.clone(),
                        trace.topic_family.clone(),
                        trace.created_at,
                    )
                })
                .chain(replay_records.iter().map(|replay| {
                    (
                        replay.source_domain.clone(),
                        replay.topic_family.clone(),
                        replay.created_at,
                    )
                })),
        );
        let group_month = |domain: &str, family: &str| -> &str {
            group_months
                .get(&(domain.to_string(), family.to_string()))
                .expect("group month computed for every record")
        };
        let mut domains = BTreeSet::new();
        let mut topics = BTreeSet::new();
        for trace in &traces {
            domains.insert(trace.source_domain.clone());
            topics.insert(trace.topic_family.clone());
            let record = json!({
                "kind":"meta_decision",
                "split":split_group(&trace.source_domain,&trace.topic_family,group_month(&trace.source_domain,&trace.topic_family)),
                "record":trace
            });
            serde_json::to_writer(&mut dataset, &record)?;
            dataset.push(b'\n');
        }
        for replay in &replay_records {
            domains.insert(replay.source_domain.clone());
            topics.insert(replay.topic_family.clone());
            let record = json!({
                "kind":"meta_replay",
                "split":split_group(&replay.source_domain,&replay.topic_family,group_month(&replay.source_domain,&replay.topic_family)),
                "record":replay
            });
            serde_json::to_writer(&mut dataset, &record)?;
            dataset.push(b'\n');
        }
        let dataset_hash = self.put_object(&dataset)?;
        let manifest = json!({
            "schema_version":SCHEMA_VERSION,
            "kind":"meta_training_manifest_v1",
            "created_at":now,
            "dataset_hash":dataset_hash,
            "decision_count":traces.len(),
            "replay_eval_count":replay_records.len(),
            "split_policy":"source_domain_topic_family_earliest_month_v1",
            "source_domains":domains,
            "topic_families":topics,
            "contains_raw_documents":false
        });
        let manifest_bytes = serde_json::to_vec(&manifest)?;
        let manifest_hash = self.put_object(&manifest_bytes)?;
        let candidate = MetaTrainingCandidate {
            candidate_id: Uuid::new_v4(),
            dataset_hash,
            manifest_hash,
            decision_count: traces.len() as u64,
            replay_eval_count: replay_records.len() as u64,
            eligible_record_count: (traces.len() + replay_records.len()) as u64,
            source_domain_count: domains.len() as u64,
            topic_family_count: topics.len() as u64,
            created_at: now,
        };
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO meta_training_candidates(id,manifest_hash,candidate_json,created_at)
             VALUES(?1,?2,?3,?4)",
            params![
                candidate.candidate_id.to_string(),
                candidate.manifest_hash,
                serde_json::to_string(&candidate)?,
                candidate.created_at.to_rfc3339()
            ],
        )?;
        Ok(candidate)
    }

    pub fn get_meta_training_candidate(&self, id: Uuid) -> Result<Option<MetaTrainingCandidate>> {
        read_optional_json(
            self,
            "SELECT candidate_json FROM meta_training_candidates WHERE id=?1",
            &id.to_string(),
        )
    }

    pub fn list_meta_training_candidates(&self) -> Result<Vec<MetaTrainingCandidate>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT candidate_json FROM meta_training_candidates ORDER BY created_at DESC,id",
        )?;
        decode_rows(statement.query_map([], |row| row.get::<_, String>(0))?)
    }
}

impl Registry {
    pub fn submit_meta_training_result(
        &self,
        job_id: Uuid,
        worker: &str,
        bundle: &MetaModelBundle,
        artifact: &[u8],
    ) -> Result<()> {
        let now = Utc::now();
        let payload: String = {
            let conn = self.lock_conn();
            conn.query_row(
                "SELECT payload_json FROM learning_jobs
                 WHERE id=?1 AND kind='meta_train_v1' AND status='leased'
                 AND lease_owner=?2 AND lease_until>?3",
                params![job_id.to_string(), worker, now.to_rfc3339()],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("meta training result requires an active worker-owned lease"))?
        };
        let payload: Value = serde_json::from_str(&payload)?;
        let candidate_id = payload
            .pointer("/candidate/candidate_id")
            .and_then(Value::as_str)
            .and_then(|value| Uuid::parse_str(value).ok())
            .ok_or_else(|| anyhow!("meta training job lacks a candidate id"))?;
        let base_model = payload
            .get("base_model")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("meta training job lacks a base model"))?;
        let license_policy = payload
            .get("data_license_policy")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let gpu_memory = payload
            .get("declared_gpu_memory_gb")
            .and_then(Value::as_u64)
            .unwrap_or_default();
        if bundle.training_candidate_id != candidate_id
            || bundle.base_model != base_model
            || bundle.trainer != worker
            || license_policy != "licensed-only"
            || gpu_memory < 24
        {
            bail!("meta training result does not match the fail-closed job manifest");
        }
        let existing: Option<(String, String, String)> = {
            let conn = self.lock_conn();
            conn.query_row(
                "SELECT model_id,version,artifact_hash FROM meta_training_job_results
                 WHERE job_id=?1",
                params![job_id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()?
        };
        if let Some(existing) = existing {
            if existing
                == (
                    bundle.model_id.clone(),
                    bundle.version.clone(),
                    bundle.artifact_hash.clone(),
                )
            {
                if self
                    .get_meta_model(&bundle.model_id, &bundle.version)?
                    .is_some_and(|stored| stored.status == MetaModelStatus::Candidate)
                {
                    self.begin_meta_shadow(&bundle.model_id, &bundle.version)?;
                }
                return Ok(());
            }
            bail!("meta training job results are immutable");
        }
        self.register_meta_model(bundle, artifact)?;
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO meta_training_job_results(
               job_id,worker,model_id,version,artifact_hash,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6)",
            params![
                job_id.to_string(),
                worker,
                bundle.model_id,
                bundle.version,
                bundle.artifact_hash,
                now.to_rfc3339()
            ],
        )?;
        drop(conn);
        self.begin_meta_shadow(&bundle.model_id, &bundle.version)?;
        Ok(())
    }

    pub fn validate_meta_training_job_completion(&self, job_id: Uuid) -> Result<()> {
        let conn = self.lock_conn();
        validate_meta_training_completion(&conn, job_id)
    }
}

/// Pure connection-level form of the meta-training completion check, so the
/// transactional job-completion path can run it inside its own transaction.
pub(crate) fn validate_meta_training_completion(
    conn: &rusqlite::Connection,
    job_id: Uuid,
) -> Result<()> {
    let row: Option<(String, i64)> = conn
        .query_row(
            "SELECT j.kind,EXISTS(
               SELECT 1 FROM meta_training_job_results r WHERE r.job_id=j.id
             ) FROM learning_jobs j WHERE j.id=?1",
            params![job_id.to_string()],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()?;
    if matches!(row, Some((ref kind, 0)) if kind == "meta_train_v1") {
        bail!("meta training worker must submit a verified model bundle before completion");
    }
    Ok(())
}

impl Registry {
    pub fn get_meta_training_job_result(&self, job_id: Uuid) -> Result<Option<MetaModelBundle>> {
        let conn = self.lock_conn();
        let value: Option<String> = conn
            .query_row(
                "SELECT b.bundle_json FROM meta_training_job_results r
                 JOIN meta_model_bundles b
                   ON b.model_id=r.model_id AND b.version=r.version
                 WHERE r.job_id=?1",
                params![job_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        value
            .map(|json| serde_json::from_str(&json).map_err(Into::into))
            .transpose()
    }

    pub fn register_meta_model(&self, bundle: &MetaModelBundle, artifact: &[u8]) -> Result<()> {
        let artifact_hash = self.put_object(artifact)?;
        if artifact_hash != bundle.artifact_hash {
            bail!("meta model artifact hash mismatch");
        }
        self.register_meta_model_from_stored_artifact(bundle)
    }

    pub(crate) fn register_meta_model_from_stored_artifact(
        &self,
        bundle: &MetaModelBundle,
    ) -> Result<()> {
        if bundle.status != MetaModelStatus::Candidate
            || bundle.canary_started_at.is_some()
            || bundle.canary_decisions != 0
        {
            bail!("new meta models must start as an unused candidate");
        }
        validate_meta_model_bundle(bundle)?;
        if self
            .get_meta_training_candidate(bundle.training_candidate_id)?
            .is_none()
            && self
                .get_dataset_snapshot(bundle.training_candidate_id)?
                .is_none()
        {
            bail!("meta training candidate or dataset snapshot not found");
        }
        self.verify_object_hash(&bundle.artifact_hash)?;
        let json = serde_json::to_string(bundle)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT bundle_json FROM meta_model_bundles WHERE model_id=?1 AND version=?2",
                params![bundle.model_id, bundle.version],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == json {
                return Ok(());
            }
            bail!("meta model versions are immutable at registration");
        }
        conn.execute(
            "INSERT INTO meta_model_bundles(model_id,version,status,bundle_json,updated_at)
             VALUES(?1,?2,?3,?4,?5)",
            params![
                bundle.model_id,
                bundle.version,
                meta_status_name(bundle.status),
                json,
                bundle.updated_at.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    pub fn get_meta_model(&self, id: &str, version: &str) -> Result<Option<MetaModelBundle>> {
        let conn = self.lock_conn();
        let value: Option<String> = conn
            .query_row(
                "SELECT bundle_json FROM meta_model_bundles WHERE model_id=?1 AND version=?2",
                params![id, version],
                |row| row.get(0),
            )
            .optional()?;
        value
            .map(|json| serde_json::from_str(&json).map_err(Into::into))
            .transpose()
    }

    pub fn list_meta_models(&self) -> Result<Vec<MetaModelBundle>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT bundle_json FROM meta_model_bundles ORDER BY updated_at DESC,model_id,version",
        )?;
        decode_rows(statement.query_map([], |row| row.get::<_, String>(0))?)
    }

    pub fn begin_meta_shadow(&self, id: &str, version: &str) -> Result<MetaModelBundle> {
        let mut bundle = self
            .get_meta_model(id, version)?
            .ok_or_else(|| anyhow!("meta model not found"))?;
        if bundle.status != MetaModelStatus::Candidate {
            bail!("only candidate models can enter shadow replay");
        }
        bundle.status = MetaModelStatus::Shadow;
        bundle.updated_at = Utc::now();
        self.persist_meta_model(&bundle)?;
        Ok(bundle)
    }

    pub fn begin_meta_canary(
        &self,
        id: &str,
        version: &str,
        now: DateTime<Utc>,
    ) -> Result<MetaModelBundle> {
        let mut bundle = self
            .get_meta_model(id, version)?
            .ok_or_else(|| anyhow!("meta model not found"))?;
        if bundle.status != MetaModelStatus::Shadow {
            bail!("only shadow models can enter canary");
        }
        if !bundle.metrics.passes_automatic_activation() {
            bundle.status = MetaModelStatus::Rejected;
            bundle.updated_at = now;
            self.persist_meta_model(&bundle)?;
            bail!("shadow replay failed automatic activation gates");
        }
        bundle.previous_active =
            self.active_meta_model()?
                .map(|active| cerebellum_core::ArtifactVersionRef {
                    id: active.model_id,
                    version: active.version,
                });
        bundle.status = MetaModelStatus::Canary;
        bundle.canary_started_at = Some(now);
        bundle.canary_decisions = 0;
        bundle.updated_at = now;
        validate_meta_model_bundle(&bundle)?;
        self.persist_meta_model(&bundle)?;
        Ok(bundle)
    }

    pub fn evaluate_meta_model(
        &self,
        id: &str,
        version: &str,
        metrics: MetaModelMetrics,
        now: DateTime<Utc>,
    ) -> Result<MetaModelBundle> {
        let bundle = self
            .get_meta_model(id, version)?
            .ok_or_else(|| anyhow!("meta model not found"))?;
        match bundle.status {
            MetaModelStatus::Shadow => self.evaluate_meta_shadow(id, version, metrics, now),
            MetaModelStatus::Canary => self.evaluate_meta_canary(id, version, metrics, now),
            _ => bail!("only shadow or canary models can be evaluated"),
        }
    }

    fn evaluate_meta_shadow(
        &self,
        id: &str,
        version: &str,
        metrics: MetaModelMetrics,
        now: DateTime<Utc>,
    ) -> Result<MetaModelBundle> {
        let mut bundle = self
            .get_meta_model(id, version)?
            .ok_or_else(|| anyhow!("meta model not found"))?;
        if bundle.status != MetaModelStatus::Shadow {
            bail!("model is not in shadow state");
        }
        bundle.metrics = metrics;
        bundle.updated_at = now;
        if !bundle.metrics.passes_automatic_activation() {
            bundle.status = MetaModelStatus::Rejected;
            self.persist_meta_model(&bundle)?;
            return Ok(bundle);
        }
        self.persist_meta_model(&bundle)?;
        self.begin_meta_canary(id, version, now)
    }

    pub fn record_meta_canary_decision(
        &self,
        decision: &MetaCanaryDecision,
    ) -> Result<MetaModelBundle> {
        validate_meta_canary_decision(decision)?;
        if decision.assigned_to_canary
            != should_assign_canary(&decision.model_id, &decision.version, decision.decision_id)
        {
            bail!("canary assignment does not match deterministic 10 percent policy");
        }
        let mut bundle = self
            .get_meta_model(&decision.model_id, &decision.version)?
            .ok_or_else(|| anyhow!("meta model not found"))?;
        if bundle.status != MetaModelStatus::Canary {
            bail!("model is not in canary state");
        }
        let value = serde_json::to_value(decision)?;
        let content_hash = canonical_json_hash(&value);
        let json = serde_json::to_string(decision)?;
        let inserted = {
            let conn = self.lock_conn();
            let existing: Option<String> = conn
                .query_row(
                    "SELECT decision_json FROM meta_canary_decisions WHERE id=?1",
                    params![decision.decision_id.to_string()],
                    |row| row.get(0),
                )
                .optional()?;
            if let Some(existing) = existing {
                let existing_hash = canonical_json_hash(&serde_json::from_str::<Value>(&existing)?);
                if existing_hash != content_hash {
                    bail!("canary decision ids are immutable");
                }
                false
            } else {
                conn.execute(
                    "INSERT INTO meta_canary_decisions(
                       id,model_id,version,assigned_to_canary,policy_violation,
                       decision_json,created_at
                     ) VALUES(?1,?2,?3,?4,?5,?6,?7)",
                    params![
                        decision.decision_id.to_string(),
                        decision.model_id,
                        decision.version,
                        decision.assigned_to_canary as i64,
                        decision.policy_violation as i64,
                        json,
                        decision.created_at.to_rfc3339()
                    ],
                )?;
                true
            }
        };
        if inserted && decision.assigned_to_canary {
            bundle.canary_decisions = bundle.canary_decisions.saturating_add(1);
        }
        if decision.policy_violation {
            bundle.status = MetaModelStatus::RolledBack;
        }
        bundle.updated_at = Utc::now();
        self.persist_meta_model(&bundle)?;
        Ok(bundle)
    }

    pub fn evaluate_meta_canary(
        &self,
        id: &str,
        version: &str,
        metrics: MetaModelMetrics,
        now: DateTime<Utc>,
    ) -> Result<MetaModelBundle> {
        let mut bundle = self
            .get_meta_model(id, version)?
            .ok_or_else(|| anyhow!("meta model not found"))?;
        if bundle.status != MetaModelStatus::Canary {
            bail!("model is not in canary state");
        }
        bundle.metrics = metrics;
        bundle.updated_at = now;
        if !bundle.metrics.passes_automatic_activation() {
            bundle.status = MetaModelStatus::RolledBack;
            self.persist_meta_model(&bundle)?;
            return Ok(bundle);
        }
        let elapsed = bundle
            .canary_started_at
            .map(|started| now - started)
            .unwrap_or_default();
        if elapsed < Duration::hours(MIN_CANARY_HOURS)
            || bundle.canary_decisions < MIN_CANARY_DECISIONS
        {
            self.persist_meta_model(&bundle)?;
            return Ok(bundle);
        }
        bundle.status = MetaModelStatus::Active;
        self.activate_meta_model(&bundle)?;
        Ok(bundle)
    }

    pub fn rollback_meta_model(
        &self,
        id: &str,
        version: &str,
        actor: &str,
        reason: &str,
    ) -> Result<MetaModelBundle> {
        if actor.trim().is_empty() || reason.trim().is_empty() {
            bail!("rollback requires actor and reason");
        }
        let mut bundle = self
            .get_meta_model(id, version)?
            .ok_or_else(|| anyhow!("meta model not found"))?;
        if !matches!(
            bundle.status,
            MetaModelStatus::Shadow | MetaModelStatus::Canary | MetaModelStatus::Active
        ) {
            bail!("model state cannot be rolled back");
        }
        let was_active = bundle.status == MetaModelStatus::Active;
        bundle.status = MetaModelStatus::RolledBack;
        bundle.updated_at = Utc::now();
        self.persist_meta_model(&bundle)?;
        if was_active
            && let Some(previous) = &bundle.previous_active
            && let Some(mut prior) = self.get_meta_model(&previous.id, &previous.version)?
        {
            prior.status = MetaModelStatus::Active;
            prior.updated_at = Utc::now();
            self.persist_meta_model(&prior)?;
        }
        self.audit(
            "meta_model",
            &format!("{id}@{version}"),
            "rollback",
            actor,
            reason,
        )?;
        Ok(bundle)
    }

    pub fn active_meta_model(&self) -> Result<Option<MetaModelBundle>> {
        let conn = self.lock_conn();
        let value: Option<String> = conn
            .query_row(
                "SELECT bundle_json FROM meta_model_bundles
                 WHERE status='active' ORDER BY updated_at DESC LIMIT 1",
                [],
                |row| row.get(0),
            )
            .optional()?;
        value
            .map(|json| serde_json::from_str(&json).map_err(Into::into))
            .transpose()
    }

    fn persist_meta_model(&self, bundle: &MetaModelBundle) -> Result<()> {
        validate_meta_model_bundle(bundle)?;
        let conn = self.lock_conn();
        let changed = conn.execute(
            "UPDATE meta_model_bundles SET status=?3,bundle_json=?4,updated_at=?5
             WHERE model_id=?1 AND version=?2",
            params![
                bundle.model_id,
                bundle.version,
                meta_status_name(bundle.status),
                serde_json::to_string(bundle)?,
                bundle.updated_at.to_rfc3339()
            ],
        )?;
        if changed != 1 {
            bail!("meta model not found");
        }
        Ok(())
    }

    fn activate_meta_model(&self, bundle: &MetaModelBundle) -> Result<()> {
        validate_meta_model_bundle(bundle)?;
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let old_models = {
            let mut statement = transaction.prepare(
                "SELECT bundle_json FROM meta_model_bundles
                 WHERE status='active' AND NOT(model_id=?1 AND version=?2)",
            )?;
            statement
                .query_map(params![bundle.model_id, bundle.version], |row| {
                    row.get::<_, String>(0)
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };
        for json in old_models {
            let mut old: MetaModelBundle = serde_json::from_str(&json)?;
            old.status = MetaModelStatus::Superseded;
            old.updated_at = bundle.updated_at;
            transaction.execute(
                "UPDATE meta_model_bundles SET status='superseded',bundle_json=?3,updated_at=?4
                 WHERE model_id=?1 AND version=?2",
                params![
                    old.model_id,
                    old.version,
                    serde_json::to_string(&old)?,
                    old.updated_at.to_rfc3339()
                ],
            )?;
        }
        transaction.execute(
            "UPDATE meta_model_bundles SET status='active',bundle_json=?3,updated_at=?4
             WHERE model_id=?1 AND version=?2",
            params![
                bundle.model_id,
                bundle.version,
                serde_json::to_string(bundle)?,
                bundle.updated_at.to_rfc3339()
            ],
        )?;
        transaction.commit()?;
        Ok(())
    }
}

pub fn should_assign_canary(model_id: &str, version: &str, decision_id: Uuid) -> bool {
    let digest = Sha256::digest(format!("{model_id}@{version}:{decision_id}").as_bytes());
    u64::from_be_bytes(digest[..8].try_into().expect("sha256 prefix")) % 10 == 0
}

fn read_optional_json<T: serde::de::DeserializeOwned>(
    registry: &Registry,
    sql: &str,
    id: &str,
) -> Result<Option<T>> {
    let conn = registry.lock_conn();
    let value: Option<String> = conn
        .query_row(sql, params![id], |row| row.get(0))
        .optional()?;
    value
        .map(|json| serde_json::from_str(&json).map_err(Into::into))
        .transpose()
}

fn decode_rows<T, I>(rows: I) -> Result<Vec<T>>
where
    T: serde::de::DeserializeOwned,
    I: IntoIterator<Item = rusqlite::Result<String>>,
{
    rows.into_iter()
        .map(|row| Ok(serde_json::from_str(&row?)?))
        .collect()
}

fn contains_sensitive_value(value: &Value) -> bool {
    match value {
        Value::String(value) => {
            let lower = value.to_lowercase();
            lower.contains("-----begin private key-----")
                || lower.contains("authorization: bearer ")
                || lower.contains("api_key=")
                || lower.contains("api-key=")
                || lower
                    .split(|character: char| !character.is_ascii_alphanumeric() && character != '-')
                    .any(|token| token.starts_with("sk-") && token.len() >= 20)
        }
        Value::Array(values) => values.iter().any(contains_sensitive_value),
        Value::Object(values) => values.iter().any(|(key, value)| {
            matches!(
                key.to_lowercase().as_str(),
                "api_key" | "apikey" | "password" | "cookie" | "authorization"
            ) || contains_sensitive_value(value)
        }),
        _ => false,
    }
}

fn split_group(source_domain: &str, topic_family: &str, earliest_month: &str) -> &'static str {
    let digest = Sha256::digest(
        crate::dataset_factory::split_group_key(source_domain, topic_family, earliest_month)
            .as_bytes(),
    );
    match digest[0] % 10 {
        0..=7 => "train",
        8 => "validation",
        _ => "holdout",
    }
}

#[cfg(test)]
mod unified_split_tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn meta_manifest_declares_the_unified_split_policy() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let candidate = registry
            .prepare_meta_training_candidate_with_thresholds(Utc::now(), 0, 0)
            .unwrap();
        let manifest: serde_json::Value =
            serde_json::from_slice(&registry.get_object(&candidate.manifest_hash).unwrap())
                .unwrap();
        assert_eq!(
            manifest["split_policy"],
            "source_domain_topic_family_earliest_month_v1"
        );
    }

    #[test]
    fn meta_and_factory_splits_agree_on_the_same_group() {
        for (domain, topic, month) in [
            ("docs", "rust", "2026-01"),
            ("web", "k8s", "2025-12"),
            ("github.com", "tuning", "2026-07"),
        ] {
            assert_eq!(
                split_group(domain, topic, month),
                crate::dataset_factory::split_name(crate::dataset_factory::split_group(
                    domain, topic, month
                )),
                "meta and factory disagree on {domain}/{topic}@{month}"
            );
        }
    }
}

fn parse_time(value: &str) -> Result<DateTime<Utc>> {
    Ok(DateTime::parse_from_rfc3339(value)?.with_timezone(&Utc))
}

fn meta_task_name(task: MetaTaskKind) -> &'static str {
    match task {
        MetaTaskKind::Relevance => "relevance",
        MetaTaskKind::NoiseFilter => "noise_filter",
        MetaTaskKind::Deduplication => "deduplication",
        MetaTaskKind::RetrievalRanking => "retrieval_ranking",
        MetaTaskKind::ClaimRelationship => "claim_relationship",
        MetaTaskKind::AcquisitionEscalation => "acquisition_escalation",
        MetaTaskKind::CurriculumPriority => "curriculum_priority",
        MetaTaskKind::ExpectedInformationGain => "expected_information_gain",
        MetaTaskKind::SkillWorkflowRouting => "skill_workflow_routing",
        MetaTaskKind::SkillWorkflowEvolution => "skill_workflow_evolution",
        MetaTaskKind::TemporalGrounding => "temporal_grounding",
        MetaTaskKind::KnowledgeBoundary => "knowledge_boundary",
        MetaTaskKind::SearchPlanning => "search_planning",
    }
}

fn meta_status_name(status: MetaModelStatus) -> &'static str {
    match status {
        MetaModelStatus::Candidate => "candidate",
        MetaModelStatus::Shadow => "shadow",
        MetaModelStatus::Canary => "canary",
        MetaModelStatus::Active => "active",
        MetaModelStatus::Superseded => "superseded",
        MetaModelStatus::Rejected => "rejected",
        MetaModelStatus::RolledBack => "rolled_back",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cerebellum_core::{MetaModelMetrics, MetaTaskKind};
    use tempfile::tempdir;

    fn hash(value: &[u8]) -> String {
        format!("{:x}", Sha256::digest(value))
    }

    fn good_metrics() -> MetaModelMetrics {
        MetaModelMetrics {
            old_task_retention: 0.99,
            ndcg_at_10: 0.52,
            baseline_ndcg_at_10: 0.50,
            max_core_topic_regression: 0.01,
            fact_precision_delta: 0.01,
            policy_violations: 0,
            injection_regression: false,
            cost_per_useful_card_change: 0.05,
        }
    }

    fn seed_candidate(registry: &Registry, now: DateTime<Utc>) -> MetaTrainingCandidate {
        for index in 0..5 {
            registry
                .record_meta_decision(&MetaDecisionTrace {
                    schema_version: SCHEMA_VERSION.into(),
                    decision_id: Uuid::new_v4(),
                    task_kind: MetaTaskKind::Relevance,
                    input_hash: hash(format!("input-{index}").as_bytes()),
                    input: json!({"query":format!("agent {index}")}),
                    output: json!({"relevant":index % 2 == 0}),
                    source_domain: format!("source-{}.example", index % 2),
                    topic_family: format!("topic-{}", index % 3),
                    policy_version: "1.0.0".into(),
                    controller_version: "deterministic-v1".into(),
                    confidence: 0.9,
                    cost: 0.0,
                    useful: true,
                    training_eligible: true,
                    policy_violations: 0,
                    prompt_injection_detected: false,
                    data_classification: cerebellum_core::DataClassification::Private,
                    external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
                    redaction_attestation_hash: None,
                    created_at: now + Duration::seconds(index),
                })
                .unwrap();
        }
        for index in 0..3 {
            registry
                .record_meta_replay(&MetaReplayEvaluation {
                    schema_version: SCHEMA_VERSION.into(),
                    evaluation_id: Uuid::new_v4(),
                    candidate_id: None,
                    task_id: format!("replay-{index}"),
                    source_domain: format!("source-{index}.example"),
                    topic_family: format!("topic-{index}"),
                    baseline_score: 0.5,
                    candidate_score: 0.55,
                    fact_correct: true,
                    safety_passed: true,
                    data_classification: cerebellum_core::DataClassification::Private,
                    external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
                    redaction_attestation_hash: None,
                    created_at: now + Duration::seconds(index + 10),
                })
                .unwrap();
        }
        registry
            .prepare_meta_training_candidate_with_thresholds(now + Duration::minutes(1), 5, 3)
            .unwrap()
    }

    #[test]
    fn candidate_manifest_requires_deduplicated_safe_evidence_and_weekly_cooldown() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let now = Utc::now();
        let candidate = seed_candidate(&registry, now);
        assert_eq!(candidate.decision_count, 5);
        assert_eq!(candidate.replay_eval_count, 3);
        assert!(registry.get_object(&candidate.dataset_hash).is_ok());
        assert!(registry.get_object(&candidate.manifest_hash).is_ok());
        assert!(
            registry
                .prepare_meta_training_candidate_with_thresholds(now + Duration::days(1), 5, 3)
                .is_err()
        );

        let unsafe_trace = MetaDecisionTrace {
            schema_version: SCHEMA_VERSION.into(),
            decision_id: Uuid::new_v4(),
            task_kind: MetaTaskKind::NoiseFilter,
            input_hash: hash(b"secret"),
            input: json!({"api_key":"sk-this-is-a-secret-value"}),
            output: json!({"ignore":true}),
            source_domain: "example.com".into(),
            topic_family: "security".into(),
            policy_version: "1.0.0".into(),
            controller_version: "deterministic-v1".into(),
            confidence: 1.0,
            cost: 0.0,
            useful: false,
            training_eligible: true,
            policy_violations: 0,
            prompt_injection_detected: false,
            data_classification: cerebellum_core::DataClassification::Private,
            external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
            redaction_attestation_hash: None,
            created_at: now,
        };
        assert!(registry.record_meta_decision(&unsafe_trace).is_err());
    }

    #[test]
    fn model_uses_shadow_canary_activation_and_immediate_safety_rollback() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let now = Utc::now();
        let candidate = seed_candidate(&registry, now);
        let artifact = b"immutable-model-bundle";
        let bundle = MetaModelBundle {
            schema_version: SCHEMA_VERSION.into(),
            model_id: "meta-router".into(),
            version: "1.0.0".into(),
            artifact_hash: hash(artifact),
            base_model: "test-1b".into(),
            training_candidate_id: candidate.candidate_id,
            trainer: "fake-qlora-worker".into(),
            metrics: good_metrics(),
            status: MetaModelStatus::Candidate,
            previous_active: None,
            canary_started_at: None,
            canary_decisions: 0,
            created_at: now,
            updated_at: now,
        };
        registry.register_meta_model(&bundle, artifact).unwrap();
        registry.begin_meta_shadow("meta-router", "1.0.0").unwrap();
        let mut canary = registry
            .begin_meta_canary("meta-router", "1.0.0", now)
            .unwrap();
        canary.canary_decisions = MIN_CANARY_DECISIONS;
        registry.persist_meta_model(&canary).unwrap();
        let active = registry
            .evaluate_meta_canary(
                "meta-router",
                "1.0.0",
                good_metrics(),
                now + Duration::hours(25),
            )
            .unwrap();
        assert_eq!(active.status, MetaModelStatus::Active);

        let artifact = b"unsafe-model-bundle";
        let mut unsafe_bundle = bundle;
        unsafe_bundle.version = "1.1.0".into();
        unsafe_bundle.artifact_hash = hash(artifact);
        unsafe_bundle.created_at = now + Duration::days(8);
        unsafe_bundle.updated_at = unsafe_bundle.created_at;
        registry
            .register_meta_model(&unsafe_bundle, artifact)
            .unwrap();
        registry.begin_meta_shadow("meta-router", "1.1.0").unwrap();
        registry
            .begin_meta_canary("meta-router", "1.1.0", now + Duration::days(8))
            .unwrap();
        let decision_id = (0..10_000)
            .map(|_| Uuid::new_v4())
            .find(|id| should_assign_canary("meta-router", "1.1.0", *id))
            .unwrap();
        let rolled_back = registry
            .record_meta_canary_decision(&MetaCanaryDecision {
                schema_version: SCHEMA_VERSION.into(),
                decision_id,
                model_id: "meta-router".into(),
                version: "1.1.0".into(),
                assigned_to_canary: true,
                successful: false,
                policy_violation: true,
                useful: false,
                cost: 0.1,
                created_at: now + Duration::days(8),
            })
            .unwrap();
        assert_eq!(rolled_back.status, MetaModelStatus::RolledBack);
        assert_eq!(
            registry.active_meta_model().unwrap().unwrap().version,
            "1.0.0"
        );
    }

    #[test]
    fn canary_assignment_is_stable_and_close_to_ten_percent() {
        let ids = (0..1_000).map(|_| Uuid::new_v4()).collect::<Vec<_>>();
        let first = ids
            .iter()
            .filter(|id| should_assign_canary("model", "1.0.0", **id))
            .count();
        let second = ids
            .iter()
            .filter(|id| should_assign_canary("model", "1.0.0", **id))
            .count();
        assert_eq!(first, second);
        assert!((70..=130).contains(&first));
    }

    #[test]
    fn qlora_worker_result_is_lease_bound_and_required_for_completion() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let now = Utc::now();
        let candidate = seed_candidate(&registry, now);
        let job = registry
            .enqueue_learning_job(
                "meta_train_v1",
                json!({
                    "candidate":candidate,
                    "base_model":"test-1b",
                    "data_license_policy":"licensed-only",
                    "declared_gpu_memory_gb":24
                }),
                1.0,
                2,
            )
            .unwrap();
        registry
            .claim_learning_job(Some(&["meta_train_v1"]), "qlora-worker", 300)
            .unwrap()
            .unwrap();
        assert!(
            registry
                .validate_meta_training_job_completion(job.job_id)
                .is_err()
        );
        let artifact = b"qlora-adapter-bundle";
        let bundle = MetaModelBundle {
            schema_version: SCHEMA_VERSION.into(),
            model_id: "meta-router".into(),
            version: "1.0.0-test".into(),
            artifact_hash: hash(artifact),
            base_model: "test-1b".into(),
            training_candidate_id: candidate.candidate_id,
            trainer: "qlora-worker".into(),
            metrics: MetaModelMetrics::default(),
            status: MetaModelStatus::Candidate,
            previous_active: None,
            canary_started_at: None,
            canary_decisions: 0,
            created_at: now,
            updated_at: now,
        };
        assert!(
            registry
                .submit_meta_training_result(job.job_id, "forged-worker", &bundle, artifact)
                .is_err()
        );
        registry
            .submit_meta_training_result(job.job_id, "qlora-worker", &bundle, artifact)
            .unwrap();
        assert_eq!(
            registry
                .get_meta_training_job_result(job.job_id)
                .unwrap()
                .unwrap()
                .status,
            MetaModelStatus::Shadow
        );
        registry
            .submit_meta_training_result(job.job_id, "qlora-worker", &bundle, artifact)
            .unwrap();
        assert_eq!(
            registry
                .evaluate_meta_model("meta-router", "1.0.0-test", good_metrics(), now)
                .unwrap()
                .status,
            MetaModelStatus::Canary
        );
        registry
            .validate_meta_training_job_completion(job.job_id)
            .unwrap();
        registry
            .complete_learning_job(job.job_id, "qlora-worker")
            .unwrap();
    }

    #[test]
    #[ignore = "v3 fixed 1,000-event acceptance fixture"]
    fn one_thousand_events_reach_candidate_canary_activation_and_rollback() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let now = Utc::now();
        let task_kinds = [
            MetaTaskKind::Relevance,
            MetaTaskKind::NoiseFilter,
            MetaTaskKind::Deduplication,
            MetaTaskKind::RetrievalRanking,
            MetaTaskKind::ClaimRelationship,
            MetaTaskKind::AcquisitionEscalation,
            MetaTaskKind::CurriculumPriority,
            MetaTaskKind::ExpectedInformationGain,
        ];

        for event in 0..1_000_u128 {
            let source_domain = format!("source-{}.example", event % 100);
            let topic_family = format!("topic-{}", event % 50);
            for slot in 0..5_u128 {
                let sequence = event * 5 + slot;
                registry
                    .record_meta_decision(&MetaDecisionTrace {
                        schema_version: SCHEMA_VERSION.into(),
                        decision_id: Uuid::from_u128(0x1000_0000_0000_0000_u128 + sequence),
                        task_kind: task_kinds[(sequence as usize) % task_kinds.len()],
                        input_hash: hash(format!("fixture-input-{event}-{slot}").as_bytes()),
                        input: json!({"event":event,"slot":slot}),
                        output: json!({"accepted":slot % 2 == 0}),
                        source_domain: source_domain.clone(),
                        topic_family: topic_family.clone(),
                        policy_version: "v3-fixture".into(),
                        controller_version: "deterministic-v1".into(),
                        confidence: 0.9,
                        cost: 0.01,
                        useful: slot % 2 == 0,
                        training_eligible: true,
                        policy_violations: 0,
                        prompt_injection_detected: false,
                        data_classification: cerebellum_core::DataClassification::Private,
                        external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
                        redaction_attestation_hash: None,
                        created_at: now + Duration::milliseconds(sequence as i64),
                    })
                    .unwrap();
            }
            registry
                .record_meta_replay(&MetaReplayEvaluation {
                    schema_version: SCHEMA_VERSION.into(),
                    evaluation_id: Uuid::from_u128(0x2000_0000_0000_0000_u128 + event),
                    candidate_id: None,
                    task_id: format!("fixture-task-{event}"),
                    source_domain,
                    topic_family,
                    baseline_score: 0.50,
                    candidate_score: 0.55,
                    fact_correct: true,
                    safety_passed: true,
                    data_classification: cerebellum_core::DataClassification::Private,
                    external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
                    redaction_attestation_hash: None,
                    created_at: now + Duration::seconds(event as i64),
                })
                .unwrap();
        }

        let candidate = registry
            .prepare_meta_training_candidate(now + Duration::hours(1))
            .unwrap();
        assert_eq!(candidate.decision_count, MIN_META_DECISIONS as u64);
        assert_eq!(candidate.replay_eval_count, MIN_META_REPLAYS as u64);
        let artifact = b"fixed-1000-event-adapter";
        let bundle = MetaModelBundle {
            schema_version: SCHEMA_VERSION.into(),
            model_id: "fixture-meta-controller".into(),
            version: "1.0.0".into(),
            artifact_hash: hash(artifact),
            base_model: "fixture-1b".into(),
            training_candidate_id: candidate.candidate_id,
            trainer: "fixture-worker".into(),
            metrics: good_metrics(),
            status: MetaModelStatus::Candidate,
            previous_active: None,
            canary_started_at: None,
            canary_decisions: 0,
            created_at: now + Duration::hours(1),
            updated_at: now + Duration::hours(1),
        };
        registry.register_meta_model(&bundle, artifact).unwrap();
        registry
            .begin_meta_shadow("fixture-meta-controller", "1.0.0")
            .unwrap();
        registry
            .begin_meta_canary("fixture-meta-controller", "1.0.0", now + Duration::hours(2))
            .unwrap();

        for event in 0..1_000_u128 {
            let decision_id = (0_u128..10_000)
                .map(|nonce| Uuid::from_u128(((event + 1) << 64) | nonce))
                .find(|id| should_assign_canary("fixture-meta-controller", "1.0.0", *id))
                .expect("ten-percent partition must select a fixture id");
            registry
                .record_meta_canary_decision(&MetaCanaryDecision {
                    schema_version: SCHEMA_VERSION.into(),
                    decision_id,
                    model_id: "fixture-meta-controller".into(),
                    version: "1.0.0".into(),
                    assigned_to_canary: true,
                    successful: true,
                    policy_violation: false,
                    useful: true,
                    cost: 0.01,
                    created_at: now + Duration::hours(2) + Duration::seconds(event as i64),
                })
                .unwrap();
        }
        let active = registry
            .evaluate_meta_canary(
                "fixture-meta-controller",
                "1.0.0",
                good_metrics(),
                now + Duration::hours(27),
            )
            .unwrap();
        assert_eq!(active.status, MetaModelStatus::Active);
        let rolled_back = registry
            .rollback_meta_model(
                "fixture-meta-controller",
                "1.0.0",
                "acceptance-fixture",
                "verify rollback path",
            )
            .unwrap();
        assert_eq!(rolled_back.status, MetaModelStatus::RolledBack);
    }

    fn extra_trace(decision_id: Uuid, input: &str, now: DateTime<Utc>) -> MetaDecisionTrace {
        MetaDecisionTrace {
            schema_version: SCHEMA_VERSION.into(),
            decision_id,
            task_kind: MetaTaskKind::Relevance,
            input_hash: hash(input.as_bytes()),
            input: json!({"query":input}),
            output: json!({"relevant":true}),
            source_domain: "extra.example".into(),
            topic_family: "extra-topic".into(),
            policy_version: "1.0.0".into(),
            controller_version: "deterministic-v1".into(),
            confidence: 0.9,
            cost: 0.0,
            useful: true,
            training_eligible: true,
            policy_violations: 0,
            prompt_injection_detected: false,
            data_classification: cerebellum_core::DataClassification::Private,
            external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
            redaction_attestation_hash: None,
            created_at: now,
        }
    }

    #[test]
    fn candidate_readiness_get_list_and_idempotent_recording() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let now = Utc::now();

        assert!(
            registry
                .get_meta_training_candidate(Uuid::new_v4())
                .unwrap()
                .is_none()
        );
        assert!(registry.list_meta_training_candidates().unwrap().is_empty());
        let empty = registry.meta_training_readiness(now).unwrap();
        assert_eq!(empty.deduplicated_decisions, 0);
        assert_eq!(empty.independent_replays, 0);
        assert!(!empty.ready);
        assert!(empty.latest_candidate_at.is_none());
        assert!(empty.cooldown_until.is_none());
        // the production entrypoint enforces the 5,000/1,000 minimums
        let error = registry.prepare_meta_training_candidate(now).unwrap_err();
        assert!(
            error
                .to_string()
                .contains("insufficient meta-learning evidence")
        );

        let candidate = seed_candidate(&registry, now);
        let fetched = registry
            .get_meta_training_candidate(candidate.candidate_id)
            .unwrap()
            .unwrap();
        assert_eq!(fetched.decision_count, 5);
        assert_eq!(fetched.replay_eval_count, 3);
        assert_eq!(registry.list_meta_training_candidates().unwrap().len(), 1);
        let readiness = registry
            .meta_training_readiness(now + Duration::days(30))
            .unwrap();
        assert_eq!(readiness.deduplicated_decisions, 5);
        assert_eq!(readiness.independent_replays, 3);
        assert_eq!(readiness.latest_candidate_at, Some(candidate.created_at));
        assert_eq!(
            readiness.cooldown_until,
            Some(candidate.created_at + Duration::days(META_TRAINING_COOLDOWN_DAYS))
        );
        // past cooldown but still below the production minimums
        assert!(!readiness.ready);

        // re-recording an identical decision is idempotent; a conflicting id is rejected
        let trace = extra_trace(Uuid::new_v4(), "unique-extra", now);
        assert!(registry.record_meta_decision(&trace).unwrap());
        assert!(!registry.record_meta_decision(&trace).unwrap());
        let mut conflicting = trace.clone();
        conflicting.output = json!({"relevant":false});
        let error = registry.record_meta_decision(&conflicting).unwrap_err();
        assert_eq!(error.to_string(), "meta decision ids are immutable");
        // a new id with the same (task_kind, input_hash) is stored but deduplicated
        let duplicate = extra_trace(Uuid::new_v4(), "unique-extra", now);
        assert!(registry.record_meta_decision(&duplicate).unwrap());
        let readiness = registry
            .meta_training_readiness(now + Duration::days(30))
            .unwrap();
        assert_eq!(readiness.deduplicated_decisions, 6);
    }

    fn model_bundle(
        candidate: &MetaTrainingCandidate,
        version: &str,
        artifact_hash: String,
        at: DateTime<Utc>,
    ) -> MetaModelBundle {
        MetaModelBundle {
            schema_version: SCHEMA_VERSION.into(),
            model_id: "meta-router".into(),
            version: version.into(),
            artifact_hash,
            base_model: "test-1b".into(),
            training_candidate_id: candidate.candidate_id,
            trainer: "test".into(),
            metrics: good_metrics(),
            status: MetaModelStatus::Candidate,
            previous_active: None,
            canary_started_at: None,
            canary_decisions: 0,
            created_at: at,
            updated_at: at,
        }
    }

    #[test]
    fn meta_model_registration_listing_and_state_gates() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let now = Utc::now();
        let candidate = seed_candidate(&registry, now);

        assert!(
            registry
                .get_meta_model("meta-router", "0.0.0")
                .unwrap()
                .is_none()
        );
        assert!(registry.list_meta_models().unwrap().is_empty());

        let artifact = b"model-bundle-v1";
        let bundle = model_bundle(&candidate, "1.0.0", hash(artifact), now);
        // CAS integrity: the artifact must hash to the pinned digest
        let forged = model_bundle(&candidate, "1.0.0", hash(b"other-bytes"), now);
        let error = registry.register_meta_model(&forged, artifact).unwrap_err();
        assert_eq!(error.to_string(), "meta model artifact hash mismatch");
        registry.register_meta_model(&bundle, artifact).unwrap();
        assert_eq!(
            registry
                .get_meta_model("meta-router", "1.0.0")
                .unwrap()
                .unwrap()
                .status,
            MetaModelStatus::Candidate
        );
        assert_eq!(registry.list_meta_models().unwrap().len(), 1);

        // candidates cannot be evaluated, canaried, or rolled back
        assert!(
            registry
                .evaluate_meta_model("meta-router", "1.0.0", good_metrics(), now)
                .is_err()
        );
        assert!(
            registry
                .begin_meta_canary("meta-router", "1.0.0", now)
                .is_err()
        );
        assert!(
            registry
                .rollback_meta_model("meta-router", "1.0.0", "admin", "reason")
                .is_err()
        );
        assert!(registry.begin_meta_shadow("meta-router", "0.0.0").is_err());

        // a shadow replay that fails the automatic gates rejects the model
        registry.begin_meta_shadow("meta-router", "1.0.0").unwrap();
        let mut failing = good_metrics();
        failing.old_task_retention = 0.5;
        let rejected = registry
            .evaluate_meta_model("meta-router", "1.0.0", failing, now)
            .unwrap();
        assert_eq!(rejected.status, MetaModelStatus::Rejected);
        // rejected models cannot re-enter the pipeline
        assert!(registry.begin_meta_shadow("meta-router", "1.0.0").is_err());
        assert!(
            registry
                .evaluate_meta_model("meta-router", "1.0.0", good_metrics(), now)
                .is_err()
        );
    }

    #[test]
    fn rollback_of_active_model_restores_the_previous_active_version() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let now = Utc::now();
        let candidate = seed_candidate(&registry, now);

        let v1_artifact = b"model-v1";
        let v1 = model_bundle(&candidate, "1.0.0", hash(v1_artifact), now);
        registry.register_meta_model(&v1, v1_artifact).unwrap();
        registry.begin_meta_shadow("meta-router", "1.0.0").unwrap();
        let mut canary = registry
            .begin_meta_canary("meta-router", "1.0.0", now)
            .unwrap();
        canary.canary_decisions = MIN_CANARY_DECISIONS;
        registry.persist_meta_model(&canary).unwrap();
        let active = registry
            .evaluate_meta_canary(
                "meta-router",
                "1.0.0",
                good_metrics(),
                now + Duration::hours(25),
            )
            .unwrap();
        assert_eq!(active.status, MetaModelStatus::Active);

        let later = now + Duration::days(8);
        let v2_artifact = b"model-v2";
        let v2 = model_bundle(&candidate, "2.0.0", hash(v2_artifact), later);
        registry.register_meta_model(&v2, v2_artifact).unwrap();
        registry.begin_meta_shadow("meta-router", "2.0.0").unwrap();
        let mut canary2 = registry
            .begin_meta_canary("meta-router", "2.0.0", later)
            .unwrap();
        assert_eq!(canary2.previous_active.as_ref().unwrap().version, "1.0.0");
        canary2.canary_decisions = MIN_CANARY_DECISIONS;
        registry.persist_meta_model(&canary2).unwrap();
        registry
            .evaluate_meta_canary(
                "meta-router",
                "2.0.0",
                good_metrics(),
                later + Duration::hours(25),
            )
            .unwrap();
        assert_eq!(
            registry
                .get_meta_model("meta-router", "1.0.0")
                .unwrap()
                .unwrap()
                .status,
            MetaModelStatus::Superseded
        );

        let rolled = registry
            .rollback_meta_model("meta-router", "2.0.0", "admin", "post-deploy regression")
            .unwrap();
        assert_eq!(rolled.status, MetaModelStatus::RolledBack);
        assert_eq!(
            registry.active_meta_model().unwrap().unwrap().version,
            "1.0.0"
        );
        // a rolled-back model cannot be rolled back again
        assert!(
            registry
                .rollback_meta_model("meta-router", "2.0.0", "admin", "again")
                .is_err()
        );
        // rollback requires a non-empty actor and reason
        assert!(
            registry
                .rollback_meta_model("meta-router", "1.0.0", "", "reason")
                .is_err()
        );
        assert!(
            registry
                .rollback_meta_model("meta-router", "1.0.0", "admin", " ")
                .is_err()
        );
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetaTrainingReadiness {
    pub deduplicated_decisions: u64,
    pub independent_replays: u64,
    pub latest_candidate_at: Option<DateTime<Utc>>,
    pub cooldown_until: Option<DateTime<Utc>>,
    pub ready: bool,
}

impl Registry {
    pub fn meta_training_readiness(&self, now: DateTime<Utc>) -> Result<MetaTrainingReadiness> {
        let conn = self.lock_conn();
        let decisions: u64 = conn.query_row(
            "SELECT COUNT(*) FROM (
               SELECT 1 FROM meta_decision_traces WHERE training_eligible=1
               GROUP BY task_kind,input_hash
             )",
            [],
            |row| row.get(0),
        )?;
        let replays: u64 = conn.query_row(
            "SELECT COUNT(*) FROM (
               SELECT 1 FROM meta_replay_evaluations WHERE safety_passed=1
               GROUP BY json_extract(evaluation_json,'$.task_id'),source_domain,topic_family
             )",
            [],
            |row| row.get(0),
        )?;
        let latest: Option<String> = conn.query_row(
            "SELECT MAX(created_at) FROM meta_training_candidates",
            [],
            |row| row.get(0),
        )?;
        let latest_candidate_at = latest.map(|value| parse_time(&value)).transpose()?;
        let cooldown_until =
            latest_candidate_at.map(|value| value + Duration::days(META_TRAINING_COOLDOWN_DAYS));
        Ok(MetaTrainingReadiness {
            deduplicated_decisions: decisions,
            independent_replays: replays,
            latest_candidate_at,
            cooldown_until,
            ready: decisions >= MIN_META_DECISIONS as u64
                && replays >= MIN_META_REPLAYS as u64
                && cooldown_until.is_none_or(|until| now >= until),
        })
    }
}
