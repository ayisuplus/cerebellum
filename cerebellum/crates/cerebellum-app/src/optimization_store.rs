use anyhow::{Result, anyhow, bail};
use cerebellum_core::*;
use chrono::Utc;
use rusqlite::{OptionalExtension, params};
use semver::{Prerelease, Version};
use serde_json::json;
use std::collections::{HashMap, HashSet};
use uuid::Uuid;

use crate::optimization::{apply_skill_patch, approximate_token_count, content_hash};
use crate::store::Registry;

const OPTIMIZATION_JOB_KIND: &str = "skillopt_optimize_v1";
const SKILLOPT_REPOSITORY: &str = "https://github.com/microsoft/SkillOpt";

impl Registry {
    pub fn create_optimization_run(
        &self,
        request: &CreateOptimizationRunRequest,
    ) -> Result<SkillOptimizationRun> {
        validate_optimization_request(request)?;
        let baseline = self
            .get_skill(&request.skill_id, &request.skill_version)?
            .ok_or_else(|| anyhow!("baseline skill not found"))?;
        if matches!(
            baseline.status,
            SkillLifecycle::Deprecated | SkillLifecycle::Revoked
        ) {
            bail!("deprecated or revoked skills cannot be optimized");
        }
        let baseline_content = self.get_object(&baseline.source.content_hash)?;
        if content_hash(&baseline_content) != baseline.source.content_hash {
            bail!("baseline content failed integrity verification");
        }
        let manifest_bytes = self.get_object(&request.benchmark_manifest_hash)?;
        let manifest: CodingBenchmarkManifest = serde_json::from_slice(&manifest_bytes)?;
        validate_coding_benchmark(&manifest)?;
        if manifest.container_image != request.container_image_digest {
            bail!("benchmark manifest and optimization request use different container images");
        }
        self.get_object(&request.benchmark_bundle_hash)
            .map_err(|_| anyhow!("benchmark bundle is missing or failed integrity verification"))?;

        let run_id = Uuid::new_v4();
        let job_id = Uuid::new_v4();
        let now = Utc::now();
        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        let (release_version, candidate_version) =
            reserve_versions(&tx, &request.skill_id, &request.skill_version, run_id)?;
        let run = SkillOptimizationRun {
            schema_version: SCHEMA_VERSION.into(),
            run_id,
            job_id,
            skill_id: request.skill_id.clone(),
            skill_version: request.skill_version.clone(),
            baseline_content_hash: baseline.source.content_hash.clone(),
            benchmark_manifest_hash: request.benchmark_manifest_hash.clone(),
            benchmark_bundle_hash: request.benchmark_bundle_hash.clone(),
            container_image_digest: request.container_image_digest.clone(),
            upstream_repository: SKILLOPT_REPOSITORY.into(),
            upstream_commit: SKILLOPT_UPSTREAM_COMMIT.into(),
            upstream_source_archive_sha256: SKILLOPT_UPSTREAM_ARCHIVE_SHA256.into(),
            registration_patch_sha256: SKILLOPT_REGISTRATION_PATCH_SHA256.into(),
            target_model: request.target_model.clone(),
            optimizer_model: request.optimizer_model.clone(),
            budget: request.budget.clone(),
            candidate_version,
            release_version,
            status: OptimizationRunStatus::Queued,
            result_hash: None,
            best_candidate_hash: None,
            reviewed_by: None,
            review_reason: None,
            created_at: now,
            updated_at: now,
        };
        let payload = json!({
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "baseline_skill": {"id":run.skill_id,"version":run.skill_version,"content_hash":run.baseline_content_hash},
            "benchmark_manifest_hash": run.benchmark_manifest_hash,
            "benchmark_bundle_hash": run.benchmark_bundle_hash,
            "container_image_digest": run.container_image_digest,
            "upstream_repository": run.upstream_repository,
            "upstream_commit": run.upstream_commit,
            "upstream_source_archive_sha256": run.upstream_source_archive_sha256,
            "registration_patch_sha256": run.registration_patch_sha256,
            "target_model": run.target_model,
            "optimizer_model": run.optimizer_model,
            "budget": run.budget,
            "candidate_version": run.candidate_version
        });
        tx.execute(
            "INSERT INTO learning_jobs (id,kind,payload_json,priority,status,attempts,max_attempts,created_at,updated_at) VALUES (?1,?2,?3,1.0,'pending',0,3,?4,?4)",
            params![job_id.to_string(), OPTIMIZATION_JOB_KIND, serde_json::to_string(&payload)?, now.to_rfc3339()],
        )?;
        tx.execute(
            "INSERT INTO optimization_runs (id,job_id,status,run_json,created_at,updated_at) VALUES (?1,?2,'queued',?3,?4,?4)",
            params![run_id.to_string(),job_id.to_string(),serde_json::to_string(&run)?,now.to_rfc3339()],
        )?;
        tx.commit()?;
        Ok(run)
    }

    pub fn get_optimization_run(&self, id: Uuid) -> Result<Option<SkillOptimizationRun>> {
        let conn = self.lock_conn();
        let json: Option<String> = conn
            .query_row(
                "SELECT run_json FROM optimization_runs WHERE id=?1",
                params![id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        json.map(|value| serde_json::from_str(&value).map_err(Into::into))
            .transpose()
    }

    pub fn list_optimization_patches(&self, id: Uuid) -> Result<Vec<SkillEditPatch>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT patch_json FROM skill_edit_patches WHERE run_id=?1 ORDER BY sequence,id",
        )?;
        let rows = statement.query_map(params![id.to_string()], |row| row.get::<_, String>(0))?;
        rows.map(|row| {
            let value = row?;
            serde_json::from_str(&value).map_err(|error| {
                rusqlite::Error::FromSqlConversionFailure(
                    0,
                    rusqlite::types::Type::Text,
                    Box::new(error),
                )
            })
        })
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(Into::into)
    }

    pub fn mark_optimization_running(&self, job_id: Uuid, worker: &str) -> Result<()> {
        if worker.trim().is_empty() {
            bail!("worker id must not be empty");
        }
        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        let json: Option<String> = tx
            .query_row(
                "SELECT r.run_json FROM optimization_runs r JOIN learning_jobs j ON j.id=r.job_id WHERE r.job_id=?1 AND j.kind=?2 AND j.status='leased' AND j.lease_owner=?3",
                params![job_id.to_string(),OPTIMIZATION_JOB_KIND,worker],
                |row| row.get(0),
            )
            .optional()?;
        let Some(json) = json else {
            bail!("optimization job is not leased by this worker");
        };
        let mut run: SkillOptimizationRun = serde_json::from_str(&json)?;
        if !matches!(
            run.status,
            OptimizationRunStatus::Queued | OptimizationRunStatus::Running
        ) {
            bail!("optimization run is not claimable");
        }
        run.status = OptimizationRunStatus::Running;
        run.updated_at = Utc::now();
        tx.execute(
            "UPDATE optimization_runs SET status='running',run_json=?2,updated_at=?3 WHERE id=?1",
            params![
                run.run_id.to_string(),
                serde_json::to_string(&run)?,
                run.updated_at.to_rfc3339()
            ],
        )?;
        tx.commit()?;
        Ok(())
    }

    pub fn submit_optimization_result(
        &self,
        id: Uuid,
        result: &SkillOptimizationResult,
    ) -> Result<SkillOptimizationRun> {
        if result.schema_version != SCHEMA_VERSION || result.run_id != id {
            bail!("optimization result schema or run id does not match");
        }
        validate_skillopt_provenance(
            &result.upstream_commit,
            &result.upstream_source_archive_sha256,
            &result.registration_patch_sha256,
        )?;
        let mut run = self
            .get_optimization_run(id)?
            .ok_or_else(|| anyhow!("optimization run not found"))?;
        if result.upstream_source_archive_sha256 != run.upstream_source_archive_sha256
            || result.registration_patch_sha256 != run.registration_patch_sha256
        {
            bail!("worker result provenance differs from the immutable run");
        }
        if run.status != OptimizationRunStatus::Running || run.result_hash.is_some() {
            bail!("optimization run is not accepting a result");
        }
        verify_result_budget(&run, result)?;
        let baseline_bytes = self.get_object(&run.baseline_content_hash)?;
        let baseline = String::from_utf8(baseline_bytes)
            .map_err(|_| anyhow!("baseline skill is not valid UTF-8"))?;
        let manifest: CodingBenchmarkManifest =
            serde_json::from_slice(&self.get_object(&run.benchmark_manifest_hash)?)?;
        validate_coding_benchmark(&manifest)?;

        let mut patches = result.patches.clone();
        patches.sort_by_key(|patch| patch.sequence);
        if patches.len() > run.budget.max_candidate_steps as usize {
            bail!("result exceeds the candidate step budget");
        }
        let mut candidate_contents = HashMap::new();
        candidate_contents.insert(run.baseline_content_hash.clone(), baseline);
        let mut candidate_hashes = HashSet::new();
        let mut patch_ids = HashMap::new();
        for (index, patch) in patches.iter().enumerate() {
            validate_skill_edit_patch(patch, &run.budget)?;
            if patch.run_id != id
                || patch.sequence != (index + 1) as u32
                || patch.optimizer_model != run.optimizer_model
            {
                bail!("patch lineage, sequence, or optimizer model is invalid");
            }
            let patch_baseline = candidate_contents
                .get(&patch.baseline_hash)
                .ok_or_else(|| anyhow!("patch baseline hash is outside the candidate lineage"))?;
            let candidate = apply_skill_patch(patch_baseline, patch)?;
            let actual_hash = content_hash(candidate.as_bytes());
            let actual_delta = approximate_token_count(&candidate) as i64
                - approximate_token_count(patch_baseline) as i64;
            if actual_hash != patch.candidate_hash || actual_delta != patch.token_delta as i64 {
                bail!("patch candidate hash or token delta was forged");
            }
            if approximate_token_count(&candidate) > run.budget.max_skill_tokens as usize {
                bail!("candidate skill exceeds the configured token limit");
            }
            self.put_object(candidate.as_bytes())?;
            candidate_hashes.insert(actual_hash.clone());
            patch_ids.insert(patch.patch_id, actual_hash.clone());
            candidate_contents.insert(actual_hash, candidate);
        }

        let expected_by_split = benchmark_task_ids(&manifest);
        let mut passed_validation = HashSet::new();
        let mut evaluation_keys = HashSet::new();
        for evaluation in &result.evaluations {
            if evaluation.split == BenchmarkSplit::Holdout {
                bail!("holdout evidence must use the dedicated paired holdout record");
            }
            if !candidate_hashes.contains(&evaluation.candidate_hash) {
                bail!("evaluation references an unknown candidate hash");
            }
            let expected = expected_by_split
                .get(&split_name(evaluation.split))
                .ok_or_else(|| anyhow!("benchmark split is missing"))?;
            let supplied: HashSet<_> = evaluation
                .task_scores
                .iter()
                .map(|score| score.task_id.as_str())
                .collect();
            if supplied.len() != evaluation.task_scores.len()
                || supplied != expected.iter().map(String::as_str).collect()
            {
                bail!("evaluation task set does not match its family-isolated split");
            }
            let actual_gate = validate_candidate_evaluation(evaluation, &manifest.scoring)?;
            if actual_gate != evaluation.gate_passed {
                bail!("candidate gate result does not match objective scores");
            }
            let key = (
                evaluation.candidate_hash.clone(),
                split_name(evaluation.split),
            );
            if !evaluation_keys.insert(key) {
                bail!("duplicate candidate evaluation");
            }
            if evaluation.split == BenchmarkSplit::Validation && actual_gate {
                passed_validation.insert(evaluation.candidate_hash.clone());
            }
        }

        let mut best_candidate_hash = None;
        let positive = match result.best_patch_id {
            Some(best_patch_id) => {
                let hash = patch_ids
                    .get(&best_patch_id)
                    .ok_or_else(|| anyhow!("best patch id is unknown"))?;
                if !passed_validation.contains(hash) {
                    bail!("best candidate did not pass the validation gate");
                }
                let holdout = result
                    .holdout
                    .as_ref()
                    .ok_or_else(|| anyhow!("best candidate is missing holdout evidence"))?;
                validate_holdout_task_set(holdout, &expected_by_split)?;
                let actual_positive = validate_holdout_evaluation(holdout)?;
                if actual_positive != holdout.positive_result {
                    bail!("holdout positive-result flag does not match objective scores");
                }
                best_candidate_hash = Some(hash.clone());
                actual_positive
            }
            None => {
                if result.holdout.is_some() {
                    bail!("holdout evidence requires a selected best patch");
                }
                false
            }
        };

        let result_bytes = serde_json::to_vec(result)?;
        let result_hash = self.put_object(&result_bytes)?;
        let now = Utc::now();
        run.result_hash = Some(result_hash.clone());
        run.best_candidate_hash = best_candidate_hash;
        run.status = if positive {
            OptimizationRunStatus::Validated
        } else {
            OptimizationRunStatus::Rejected
        };
        run.updated_at = now;

        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        let ownership: i64 = tx.query_row(
            "SELECT EXISTS(SELECT 1 FROM learning_jobs WHERE id=?1 AND kind=?2 AND status='leased' AND lease_owner=?3)",
            params![run.job_id.to_string(),OPTIMIZATION_JOB_KIND,result.worker],
            |row| row.get(0),
        )?;
        if ownership == 0 {
            bail!("optimization result worker does not own the active lease");
        }
        let already_has_result: i64 = tx.query_row(
            "SELECT EXISTS(SELECT 1 FROM optimization_runs WHERE id=?1 AND result_hash IS NOT NULL)",
            params![id.to_string()],
            |row| row.get(0),
        )?;
        if already_has_result != 0 {
            bail!("optimization result is immutable and was already submitted");
        }
        for patch in &patches {
            tx.execute(
                "INSERT INTO skill_edit_patches (id,run_id,sequence,baseline_hash,candidate_hash,patch_json,created_at) VALUES (?1,?2,?3,?4,?5,?6,?7)",
                params![patch.patch_id.to_string(),id.to_string(),patch.sequence,patch.baseline_hash,patch.candidate_hash,serde_json::to_string(patch)?,patch.created_at.to_rfc3339()],
            )?;
        }
        for evaluation in &result.evaluations {
            tx.execute(
                "INSERT INTO optimization_evaluations (run_id,candidate_hash,split,evaluation_json,created_at) VALUES (?1,?2,?3,?4,?5)",
                params![id.to_string(),evaluation.candidate_hash,split_name(evaluation.split),serde_json::to_string(evaluation)?,now.to_rfc3339()],
            )?;
        }
        if let (Some(hash), Some(holdout)) = (&run.best_candidate_hash, &result.holdout) {
            tx.execute(
                "INSERT INTO optimization_evaluations (run_id,candidate_hash,split,evaluation_json,created_at) VALUES (?1,?2,'holdout',?3,?4)",
                params![id.to_string(),hash,serde_json::to_string(holdout)?,now.to_rfc3339()],
            )?;
        }
        tx.execute(
            "UPDATE optimization_runs SET status=?2,run_json=?3,result_hash=?4,updated_at=?5 WHERE id=?1 AND result_hash IS NULL",
            params![id.to_string(),optimization_status_name(run.status),serde_json::to_string(&run)?,result_hash,now.to_rfc3339()],
        )?;
        tx.execute(
            "INSERT INTO learning_job_results (job_id,result_hash,result_json,created_at) VALUES (?1,?2,?3,?4)",
            params![run.job_id.to_string(),run.result_hash,serde_json::to_string(result)?,now.to_rfc3339()],
        )?;
        tx.commit()?;
        Ok(run)
    }

    pub fn review_optimization(
        &self,
        id: Uuid,
        action: &str,
        review: &OptimizationReviewRequest,
    ) -> Result<(SkillOptimizationRun, Option<SkillManifest>)> {
        if review.actor.trim().is_empty() || review.reason.trim().is_empty() {
            bail!("optimization review requires a human actor and reason");
        }
        let mut run = self
            .get_optimization_run(id)?
            .ok_or_else(|| anyhow!("optimization run not found"))?;
        if run.status != OptimizationRunStatus::Validated {
            bail!("only a validated candidate can be reviewed");
        }
        if !matches!(action, "approve" | "reject") {
            bail!("unknown optimization review action");
        }
        let now = Utc::now();
        run.status = if action == "approve" {
            OptimizationRunStatus::Approved
        } else {
            OptimizationRunStatus::Rejected
        };
        run.reviewed_by = Some(review.actor.clone());
        run.review_reason = Some(review.reason.clone());
        run.updated_at = now;

        let candidate_manifest = if action == "approve" {
            let baseline = self
                .get_skill(&run.skill_id, &run.skill_version)?
                .ok_or_else(|| anyhow!("baseline skill no longer exists"))?;
            let result: SkillOptimizationResult = serde_json::from_slice(
                &self.get_object(
                    run.result_hash
                        .as_deref()
                        .ok_or_else(|| anyhow!("validated run has no result"))?,
                )?,
            )?;
            let holdout = result
                .holdout
                .as_ref()
                .ok_or_else(|| anyhow!("validated run has no holdout evidence"))?;
            if !validate_holdout_evaluation(holdout)? {
                bail!("holdout evidence no longer passes validation");
            }
            let candidate_hash = run
                .best_candidate_hash
                .clone()
                .ok_or_else(|| anyhow!("validated run has no best candidate"))?;
            self.get_object(&candidate_hash)?;
            let count = holdout.task_scores.len() as f64;
            let candidate_success = holdout
                .task_scores
                .iter()
                .map(|score| score.candidate_hard)
                .sum::<f64>()
                / count;
            let uplift = holdout
                .task_scores
                .iter()
                .map(|score| score.candidate_hard - score.baseline_hard)
                .sum::<f64>()
                / count;
            let mut candidate = baseline.clone();
            candidate.version = run.release_version.clone();
            candidate.source.content_hash = candidate_hash;
            candidate.source.collected_at = now;
            candidate.status = if candidate.source.has_identity_provenance() {
                SkillLifecycle::Validated
            } else {
                // NOASSERTION content remains internal and non-routable even after a human
                // accepts the measured edit. Optimization approval never weakens provenance.
                SkillLifecycle::Quarantined
            };
            candidate.evidence = EvidenceCard {
                schema_passed: true,
                independent_tasks: holdout
                    .task_scores
                    .iter()
                    .map(|score| score.task_id.as_str())
                    .collect::<HashSet<_>>()
                    .len() as u32,
                paired_runs: holdout.paired_runs,
                success_rate: Some(candidate_success),
                task_uplift: Some(uplift),
                uplift_ci95_low: Some(holdout.bootstrap_ci95_low),
                redaction_passed: false,
                ..EvidenceCard::default()
            };
            candidate.training_eligible = false;
            candidate.lineage = Some(ArtifactLineage {
                parent_id: run.skill_id.clone(),
                parent_version: run.skill_version.clone(),
                reason: format!("SkillOpt optimization {} approved: {}", id, review.reason),
                decision_id: id,
            });
            validate_skill(&candidate)?;
            Some(candidate)
        } else {
            None
        };

        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        if let Some(candidate) = &candidate_manifest {
            let inserted = tx.execute(
                "INSERT INTO skills (id,version,description,status,training_eligible,content_hash,manifest_json,updated_at) VALUES (?1,?2,?3,?4,0,?5,?6,?7)",
                params![candidate.id,candidate.version,candidate.description,skill_status_name(candidate.status),candidate.source.content_hash,serde_json::to_string(candidate)?,now.to_rfc3339()],
            )?;
            if inserted != 1 {
                bail!("candidate SkillVersion could not be created");
            }
        }
        let changed = tx.execute(
            "UPDATE optimization_runs SET status=?2,run_json=?3,updated_at=?4 WHERE id=?1 AND status='validated'",
            params![id.to_string(),optimization_status_name(run.status),serde_json::to_string(&run)?,now.to_rfc3339()],
        )?;
        if changed != 1 {
            bail!("optimization review raced with another reviewer");
        }
        Self::audit_conn(
            &tx,
            "skill_optimization",
            &id.to_string(),
            action,
            &review.actor,
            &review.reason,
            now,
        )?;
        tx.commit()?;
        if candidate_manifest.is_some() {
            self.invalidate_snapshot_cache();
        }
        Ok((run, candidate_manifest))
    }

    pub fn sync_optimization_job_failure(&self, job_id: Uuid) -> Result<()> {
        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        let row: Option<(String, String, String)> = tx
            .query_row(
                "SELECT r.id,r.run_json,j.status FROM optimization_runs r JOIN learning_jobs j ON j.id=r.job_id WHERE r.job_id=?1",
                params![job_id.to_string()],
                |row| Ok((row.get(0)?,row.get(1)?,row.get(2)?)),
            )
            .optional()?;
        let Some((id, json, job_status)) = row else {
            tx.commit()?;
            return Ok(());
        };
        let mut run: SkillOptimizationRun = serde_json::from_str(&json)?;
        if run.result_hash.is_some() {
            tx.commit()?;
            return Ok(());
        }
        run.status = if job_status == "dead_letter" {
            OptimizationRunStatus::Failed
        } else {
            OptimizationRunStatus::Queued
        };
        run.updated_at = Utc::now();
        tx.execute(
            "UPDATE optimization_runs SET status=?2,run_json=?3,updated_at=?4 WHERE id=?1",
            params![
                id,
                optimization_status_name(run.status),
                serde_json::to_string(&run)?,
                run.updated_at.to_rfc3339()
            ],
        )?;
        tx.commit()?;
        Ok(())
    }

    pub fn validate_optimization_job_completion(&self, job_id: Uuid) -> Result<()> {
        let conn = self.lock_conn();
        validate_optimization_completion(&conn, job_id)
    }
}

/// Pure connection-level form of the optimization completion check, so the
/// transactional job-completion path can run it inside its own transaction.
pub(crate) fn validate_optimization_completion(
    conn: &rusqlite::Connection,
    job_id: Uuid,
) -> Result<()> {
    let row: Option<Option<String>> = conn
        .query_row(
            "SELECT result_hash FROM optimization_runs WHERE job_id=?1",
            params![job_id.to_string()],
            |row| row.get(0),
        )
        .optional()?;
    if matches!(row, Some(None)) {
        bail!("optimization worker must submit an immutable result before completing its job");
    }
    Ok(())
}

fn reserve_versions(
    tx: &rusqlite::Transaction<'_>,
    skill_id: &str,
    baseline_version: &str,
    run_id: Uuid,
) -> Result<(String, String)> {
    let mut version = Version::parse(baseline_version)?;
    version.pre = Prerelease::EMPTY;
    version.build = semver::BuildMetadata::EMPTY;
    version.patch += 1;
    loop {
        let exists: i64 = tx.query_row(
            "SELECT EXISTS(SELECT 1 FROM skills WHERE id=?1 AND version=?2)",
            params![skill_id, version.to_string()],
            |row| row.get(0),
        )?;
        let reserved: i64 = tx.query_row(
            "SELECT EXISTS(SELECT 1 FROM optimization_runs WHERE json_extract(run_json,'$.skill_id')=?1 AND json_extract(run_json,'$.release_version')=?2 AND status NOT IN ('rejected','failed'))",
            params![skill_id,version.to_string()],
            |row| row.get(0),
        )?;
        if exists == 0 && reserved == 0 {
            break;
        }
        version.patch += 1;
    }
    let release = version.to_string();
    version.pre = Prerelease::new(&format!("skillopt.{}", run_id.simple()))?;
    Ok((release, version.to_string()))
}

fn verify_result_budget(
    run: &SkillOptimizationRun,
    result: &SkillOptimizationResult,
) -> Result<()> {
    if result.worker.trim().is_empty() || result.stopped_reason.trim().is_empty() {
        bail!("worker and stopped reason are required");
    }
    if result.target_calls > run.budget.target_call_limit
        || result.optimizer_calls > run.budget.optimizer_call_limit
        || result.total_tokens > run.budget.total_token_limit
        || result.elapsed_seconds > run.budget.wall_time_seconds
    {
        bail!("worker result exceeds the immutable optimization budget");
    }
    Ok(())
}

fn benchmark_task_ids(
    manifest: &CodingBenchmarkManifest,
) -> HashMap<&'static str, HashSet<String>> {
    let mut result = HashMap::new();
    for task in &manifest.tasks {
        result
            .entry(split_name(task.split))
            .or_insert_with(HashSet::new)
            .insert(task.task_id.clone());
    }
    result
}

fn validate_holdout_task_set(
    holdout: &HoldoutEvaluation,
    expected_by_split: &HashMap<&'static str, HashSet<String>>,
) -> Result<()> {
    let expected = expected_by_split
        .get("holdout")
        .ok_or_else(|| anyhow!("benchmark has no holdout tasks"))?;
    let mut counts = HashMap::new();
    for score in &holdout.task_scores {
        if !expected.contains(&score.task_id) {
            bail!("holdout contains a task outside the holdout split");
        }
        *counts.entry(score.task_id.as_str()).or_insert(0_u32) += 1;
    }
    if expected
        .iter()
        .any(|task| counts.get(task.as_str()) != Some(&2))
    {
        bail!("holdout must contain exactly two fixed-seed pairs per task");
    }
    Ok(())
}

fn split_name(split: BenchmarkSplit) -> &'static str {
    match split {
        BenchmarkSplit::Train => "train",
        BenchmarkSplit::Validation => "validation",
        BenchmarkSplit::Holdout => "holdout",
    }
}

fn optimization_status_name(status: OptimizationRunStatus) -> &'static str {
    match status {
        OptimizationRunStatus::Queued => "queued",
        OptimizationRunStatus::Running => "running",
        OptimizationRunStatus::Validated => "validated",
        OptimizationRunStatus::Approved => "approved",
        OptimizationRunStatus::Rejected => "rejected",
        OptimizationRunStatus::Failed => "failed",
    }
}

fn skill_status_name(status: SkillLifecycle) -> &'static str {
    match status {
        SkillLifecycle::Quarantined => "quarantined",
        SkillLifecycle::Validated => "validated",
        SkillLifecycle::Experimental => "experimental",
        SkillLifecycle::Trusted => "trusted",
        SkillLifecycle::Deprecated => "deprecated",
        SkillLifecycle::Revoked => "revoked",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::optimization::content_hash;
    use tempfile::tempdir;

    fn benchmark() -> CodingBenchmarkManifest {
        let mut tasks = Vec::new();
        for (split, families) in [
            (BenchmarkSplit::Train, 10),
            (BenchmarkSplit::Validation, 5),
            (BenchmarkSplit::Holdout, 5),
        ] {
            for family in 0..families {
                for variant in 1..=3 {
                    tasks.push(CodingBenchmarkTask {
                        task_id: format!("{:?}-{family}-{variant}", split).to_ascii_lowercase(),
                        template_family: format!("{:?}-{family}", split).to_ascii_lowercase(),
                        variant,
                        split,
                        bundle_hash: "b".repeat(64),
                        test_command: "pytest -q".into(),
                        expected_status: ExpectedTaskStatus::Completed,
                    });
                }
            }
        }
        CodingBenchmarkManifest {
            schema_version: SCHEMA_VERSION.into(),
            benchmark_id: "verify-python".into(),
            version: "1.0.0".into(),
            container_image: format!("python@sha256:{}", "a".repeat(64)),
            tasks,
            scoring: OptimizationScoringPolicy::default(),
            created_at: Utc::now(),
        }
    }

    #[test]
    fn worker_lease_and_failed_closed_result_are_auditable() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let content = b"---\nname: evolver-verify\ndescription: verify claims\n---\nVerify with fresh tests.\n";
        let baseline = SkillManifest {
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
                content_hash: content_hash(content),
                license: "NOASSERTION".into(),
                collected_at: Utc::now(),
            },
            evidence: EvidenceCard::default(),
            status: SkillLifecycle::Quarantined,
            legacy_hint: None,
            training_eligible: false,
            lineage: None,
        };
        registry.upsert_skill(&baseline, content).unwrap();
        let manifest = benchmark();
        let manifest_hash = registry
            .put_object(&serde_json::to_vec(&manifest).unwrap())
            .unwrap();
        let bundle_hash = registry.put_object(b"aggregate fixture").unwrap();
        let run = registry
            .create_optimization_run(&CreateOptimizationRunRequest {
                skill_id: baseline.id.clone(),
                skill_version: baseline.version.clone(),
                benchmark_manifest_hash: manifest_hash,
                benchmark_bundle_hash: bundle_hash,
                container_image_digest: manifest.container_image,
                target_model: "target".into(),
                optimizer_model: "optimizer".into(),
                budget: OptimizationBudget::default(),
            })
            .unwrap();
        let job = registry
            .claim_learning_job(Some(&[OPTIMIZATION_JOB_KIND]), "worker-a", 21_600)
            .unwrap()
            .unwrap();
        assert_eq!(job.job_id, run.job_id);
        registry
            .mark_optimization_running(job.job_id, "worker-a")
            .unwrap();
        assert!(
            registry
                .validate_optimization_job_completion(job.job_id)
                .is_err()
        );
        let result = SkillOptimizationResult {
            schema_version: SCHEMA_VERSION.into(),
            run_id: run.run_id,
            worker: "worker-b".into(),
            upstream_commit: SKILLOPT_UPSTREAM_COMMIT.into(),
            upstream_source_archive_sha256: SKILLOPT_UPSTREAM_ARCHIVE_SHA256.into(),
            registration_patch_sha256: SKILLOPT_REGISTRATION_PATCH_SHA256.into(),
            patches: vec![],
            evaluations: vec![],
            holdout: None,
            best_patch_id: None,
            stopped_reason: "model returned invalid JSON".into(),
            target_calls: 1,
            optimizer_calls: 0,
            total_tokens: 10,
            elapsed_seconds: 1,
            created_at: Utc::now(),
        };
        assert!(
            registry
                .submit_optimization_result(run.run_id, &result)
                .is_err()
        );
        let mut owned_result = result;
        owned_result.worker = "worker-a".into();
        let finished = registry
            .submit_optimization_result(run.run_id, &owned_result)
            .unwrap();
        assert_eq!(finished.status, OptimizationRunStatus::Rejected);
        assert!(
            registry
                .review_optimization(
                    run.run_id,
                    "approve",
                    &OptimizationReviewRequest {
                        actor: "human".into(),
                        reason: "should remain denied".into(),
                    },
                )
                .is_err()
        );
        registry
            .validate_optimization_job_completion(job.job_id)
            .unwrap();
        registry
            .complete_learning_job(job.job_id, "worker-a")
            .unwrap();
    }

    #[test]
    fn positive_holdout_still_requires_human_and_preserves_noassertion_quarantine() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let content = b"---\nname: evolver-verify\ndescription: verify claims\n---\nVerify with fresh tests.\n";
        let baseline = SkillManifest {
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
                content_hash: content_hash(content),
                license: "NOASSERTION".into(),
                collected_at: Utc::now(),
            },
            evidence: EvidenceCard::default(),
            status: SkillLifecycle::Quarantined,
            legacy_hint: None,
            training_eligible: false,
            lineage: None,
        };
        registry.upsert_skill(&baseline, content).unwrap();
        let manifest = benchmark();
        let manifest_hash = registry
            .put_object(&serde_json::to_vec(&manifest).unwrap())
            .unwrap();
        let bundle_hash = registry.put_object(b"aggregate fixture").unwrap();
        let run = registry
            .create_optimization_run(&CreateOptimizationRunRequest {
                skill_id: baseline.id.clone(),
                skill_version: baseline.version.clone(),
                benchmark_manifest_hash: manifest_hash,
                benchmark_bundle_hash: bundle_hash,
                container_image_digest: manifest.container_image.clone(),
                target_model: "target".into(),
                optimizer_model: "optimizer".into(),
                budget: OptimizationBudget::default(),
            })
            .unwrap();
        let job = registry
            .claim_learning_job(Some(&[OPTIMIZATION_JOB_KIND]), "worker-a", 21_600)
            .unwrap()
            .unwrap();
        registry
            .mark_optimization_running(job.job_id, "worker-a")
            .unwrap();
        let mut patch = SkillEditPatch {
            schema_version: SCHEMA_VERSION.into(),
            patch_id: Uuid::new_v4(),
            run_id: run.run_id,
            sequence: 1,
            baseline_hash: baseline.source.content_hash.clone(),
            candidate_hash: "0".repeat(64),
            edits: vec![SkillEdit {
                operation: SkillEditOperation::Append,
                target: String::new(),
                content: "Re-run the complete test suite after the final source edit.".into(),
            }],
            rationale: "fresh verification failures".into(),
            trajectory_ids: vec!["train-1".into()],
            token_delta: 0,
            optimizer_model: "optimizer".into(),
            created_at: Utc::now(),
        };
        let baseline_text = String::from_utf8(content.to_vec()).unwrap();
        let candidate = apply_skill_patch(&baseline_text, &patch).unwrap();
        patch.candidate_hash = content_hash(candidate.as_bytes());
        patch.token_delta = (approximate_token_count(&candidate) as i64
            - approximate_token_count(&baseline_text) as i64) as i32;
        let validation_scores: Vec<_> = manifest
            .tasks
            .iter()
            .filter(|task| task.split == BenchmarkSplit::Validation)
            .map(|task| OptimizationTaskScore {
                task_id: task.task_id.clone(),
                baseline_hard: 0.0,
                candidate_hard: 1.0,
                baseline_soft: 0.0,
                candidate_soft: 1.0,
                safety_violation: false,
            })
            .collect();
        let evaluation = CandidateEvaluation {
            candidate_hash: patch.candidate_hash.clone(),
            split: BenchmarkSplit::Validation,
            task_scores: validation_scores,
            baseline_hard_mean: 0.0,
            candidate_hard_mean: 1.0,
            baseline_soft_mean: 0.0,
            candidate_soft_mean: 1.0,
            gate_passed: true,
            rejection_reasons: vec![],
        };
        let holdout_scores: Vec<_> = manifest
            .tasks
            .iter()
            .filter(|task| task.split == BenchmarkSplit::Holdout)
            .flat_map(|task| {
                [1729, 2718].map(|_| OptimizationTaskScore {
                    task_id: task.task_id.clone(),
                    baseline_hard: 0.0,
                    candidate_hard: 1.0,
                    baseline_soft: 0.0,
                    candidate_soft: 1.0,
                    safety_violation: false,
                })
            })
            .collect();
        let result = SkillOptimizationResult {
            schema_version: SCHEMA_VERSION.into(),
            run_id: run.run_id,
            worker: "worker-a".into(),
            upstream_commit: SKILLOPT_UPSTREAM_COMMIT.into(),
            upstream_source_archive_sha256: SKILLOPT_UPSTREAM_ARCHIVE_SHA256.into(),
            registration_patch_sha256: SKILLOPT_REGISTRATION_PATCH_SHA256.into(),
            patches: vec![patch.clone()],
            evaluations: vec![evaluation],
            holdout: Some(HoldoutEvaluation {
                seeds: vec![1729, 2718],
                task_scores: holdout_scores,
                paired_runs: 30,
                bootstrap_ci95_low: 1.0,
                safety_violation_delta: 0,
                positive_result: true,
            }),
            best_patch_id: Some(patch.patch_id),
            stopped_reason: "positive holdout".into(),
            target_calls: 225,
            optimizer_calls: 12,
            total_tokens: 10_000,
            elapsed_seconds: 100,
            created_at: Utc::now(),
        };
        let validated = registry
            .submit_optimization_result(run.run_id, &result)
            .unwrap();
        assert_eq!(validated.status, OptimizationRunStatus::Validated);
        assert!(
            registry
                .get_skill("evolver-verify", "1.0.1")
                .unwrap()
                .is_none()
        );
        let (approved, skill) = registry
            .review_optimization(
                run.run_id,
                "approve",
                &OptimizationReviewRequest {
                    actor: "human-reviewer".into(),
                    reason: "reviewed all paired evidence".into(),
                },
            )
            .unwrap();
        assert_eq!(approved.status, OptimizationRunStatus::Approved);
        let skill = skill.unwrap();
        assert_eq!(skill.version, "1.0.1");
        assert_eq!(skill.status, SkillLifecycle::Quarantined);
        assert!(!skill.training_eligible);
        assert!(skill.lineage.is_some());
    }
}
