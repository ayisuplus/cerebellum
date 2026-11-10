use anyhow::{Result, anyhow, bail};
use cerebellum_core::*;
use chrono::{DateTime, Duration, Utc};
use rusqlite::{OptionalExtension, params};
use serde_json::Value;
use uuid::Uuid;

use crate::store::Registry;

impl Registry {
    pub fn insert_experience(&self, experience: &ExperienceEnvelope) -> Result<bool> {
        validate_experience(experience)?;
        let value = serde_json::to_value(experience)?;
        let content_hash = canonical_json_hash(&value);
        let serialized = serde_json::to_string(experience)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT content_hash FROM experiences WHERE id=?1",
                params![experience.experience_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == content_hash {
                return Ok(false);
            }
            bail!("experience id already exists with different immutable content");
        }
        let training_source_eligible = experience.source.kind != ExperienceSourceKind::Github
            || experience.source.license_allows_training();
        conn.execute(
            "INSERT INTO experiences (id,task,task_family,repository_id,repository_digest,source_kind,training_source_eligible,envelope_json,content_hash,created_at) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
            params![
                experience.experience_id.to_string(),
                experience.task,
                experience.task_family,
                experience.repository.repository_id,
                experience.repository.digest,
                source_kind(experience.source.kind),
                training_source_eligible as i64,
                serialized,
                content_hash,
                experience.created_at.to_rfc3339(),
            ],
        )?;
        Ok(true)
    }

    pub fn get_experience(&self, id: Uuid) -> Result<Option<ExperienceEnvelope>> {
        let conn = self.lock_conn();
        let json: Option<String> = conn
            .query_row(
                "SELECT envelope_json FROM experiences WHERE id=?1",
                params![id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        deserialize_optional(json)
    }

    pub fn all_experiences(&self) -> Result<Vec<ExperienceEnvelope>> {
        let conn = self.lock_conn();
        let mut statement =
            conn.prepare("SELECT envelope_json FROM experiences ORDER BY created_at,id")?;
        deserialize_rows(statement.query_map([], |row| row.get::<_, String>(0))?)
    }

    pub fn experience_family_stats(&self, task_family: &str) -> Result<(u64, u64)> {
        let conn = self.lock_conn();
        let count: u64 = conn.query_row(
            "SELECT COUNT(*) FROM experiences WHERE task_family=?1",
            params![task_family],
            |row| row.get(0),
        )?;
        let repositories: u64 = conn.query_row(
            "SELECT COUNT(DISTINCT repository_id) FROM experiences WHERE task_family=?1",
            params![task_family],
            |row| row.get(0),
        )?;
        Ok((count, repositories))
    }

    pub fn insert_feedback(&self, feedback: &FeedbackSignal) -> Result<bool> {
        validate_feedback(feedback)?;
        if self.get_experience(feedback.experience_id)?.is_none() {
            bail!("feedback references an unknown experience");
        }
        if feedback.kind.is_verifiable() {
            let expected = canonical_json_hash(&feedback.evidence);
            if feedback.evidence_hash.as_deref() != Some(expected.as_str())
                || feedback.evidence.get("verified").and_then(Value::as_bool) != Some(true)
                || !feedback.source.starts_with("cerebellum:")
            {
                bail!("verifiable feedback requires sidecar provenance and matching evidence hash");
            }
            self.verify_feedback_attestation(feedback)?;
        }
        let value = serde_json::to_value(feedback)?;
        let content_hash = canonical_json_hash(&value);
        let serialized = serde_json::to_string(feedback)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT content_hash FROM feedback_signals WHERE id=?1",
                params![feedback.feedback_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == content_hash {
                return Ok(false);
            }
            bail!("feedback id already exists with different immutable content");
        }
        conn.execute(
            "INSERT INTO feedback_signals (id,experience_id,kind,signal_json,content_hash,created_at) VALUES (?1,?2,?3,?4,?5,?6)",
            params![
                feedback.feedback_id.to_string(),
                feedback.experience_id.to_string(),
                feedback_kind(feedback.kind),
                serialized,
                content_hash,
                feedback.created_at.to_rfc3339(),
            ],
        )?;
        Ok(true)
    }

    pub fn feedback_for_experience(&self, id: Uuid) -> Result<Vec<FeedbackSignal>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT signal_json FROM feedback_signals WHERE experience_id=?1 ORDER BY created_at,id",
        )?;
        deserialize_rows(
            statement.query_map(params![id.to_string()], |row| row.get::<_, String>(0))?,
        )
    }

    pub fn save_learning_decision(&self, decision: &LearningDecision) -> Result<()> {
        validate_learning_decision(decision)?;
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO learning_decisions (id,experience_id,priority,training_eligible,decision_json,created_at) VALUES (?1,?2,?3,?4,?5,?6)",
            params![
                decision.decision_id.to_string(),
                decision.experience_id.to_string(),
                decision.priority,
                decision.training_eligible as i64,
                serde_json::to_string(decision)?,
                decision.created_at.to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn latest_learning_decision(&self, id: Uuid) -> Result<Option<LearningDecision>> {
        let conn = self.lock_conn();
        let json: Option<String> = conn
            .query_row(
                "SELECT decision_json FROM learning_decisions WHERE experience_id=?1 ORDER BY created_at DESC,id DESC LIMIT 1",
                params![id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        deserialize_optional(json)
    }

    pub fn all_learning_decisions(&self) -> Result<Vec<LearningDecision>> {
        let conn = self.lock_conn();
        let mut statement =
            conn.prepare("SELECT decision_json FROM learning_decisions ORDER BY created_at,id")?;
        deserialize_rows(statement.query_map([], |row| row.get::<_, String>(0))?)
    }

    pub fn latest_learning_decisions(&self) -> Result<Vec<LearningDecision>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT d.decision_json FROM learning_decisions d WHERE d.id=(SELECT d2.id FROM learning_decisions d2 WHERE d2.experience_id=d.experience_id ORDER BY d2.created_at DESC,d2.id DESC LIMIT 1) ORDER BY d.created_at,d.id",
        )?;
        deserialize_rows(statement.query_map([], |row| row.get::<_, String>(0))?)
    }

    pub fn save_memory_proposal(&self, proposal: &MemoryProposal) -> Result<()> {
        if proposal.executable {
            bail!("learned proposals are never executable before publication review");
        }
        let conn = self.lock_conn();
        conn.execute(
            "INSERT OR IGNORE INTO memory_proposals (id,experience_id,kind,title,content,proposal_json,executable,created_at) VALUES (?1,?2,?3,?4,?5,?6,0,?7)",
            params![
                proposal.proposal_id.to_string(),
                proposal.experience_id.to_string(),
                memory_kind(proposal.kind),
                proposal.title,
                proposal.content,
                serde_json::to_string(proposal)?,
                proposal.created_at.to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn proposals_for_experience(&self, id: Uuid) -> Result<Vec<MemoryProposal>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT proposal_json FROM memory_proposals WHERE experience_id=?1 ORDER BY created_at,id",
        )?;
        deserialize_rows(
            statement.query_map(params![id.to_string()], |row| row.get::<_, String>(0))?,
        )
    }

    /// Proposals joined with their experiences in one query; dangling
    /// references (experience deleted) are counted, not fatal.
    pub fn proposals_with_experiences(
        &self,
        limit: usize,
    ) -> Result<(Vec<(MemoryProposal, ExperienceEnvelope)>, u64)> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT p.proposal_json, e.envelope_json FROM memory_proposals p
             LEFT JOIN experiences e ON e.id = p.experience_id
             ORDER BY p.created_at DESC, p.id LIMIT ?1",
        )?;
        let rows = statement.query_map(params![limit as i64], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, Option<String>>(1)?))
        })?;
        let mut joined = Vec::new();
        let mut dangling = 0_u64;
        for row in rows {
            let (proposal_json, envelope_json) = row?;
            match envelope_json {
                Some(envelope_json) => joined.push((
                    serde_json::from_str::<MemoryProposal>(&proposal_json)?,
                    serde_json::from_str::<ExperienceEnvelope>(&envelope_json)?,
                )),
                None => dangling += 1,
            }
        }
        Ok((joined, dangling))
    }

    pub fn search_memory_proposals(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<MemoryProposal>> {
        let escaped = query.replace('%', "\\%").replace('_', "\\_");
        let pattern = format!("%{escaped}%");
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT proposal_json FROM memory_proposals WHERE title LIKE ?1 ESCAPE '\\' OR content LIKE ?1 ESCAPE '\\' ORDER BY created_at DESC,id LIMIT ?2",
        )?;
        deserialize_rows(statement.query_map(params![pattern, limit as i64], |row| {
            row.get::<_, String>(0)
        })?)
    }
}

/// SQL-computed inputs for `learning_status`; no envelope is deserialized.
pub(crate) struct LearningAggregates {
    pub decision_count: u64,
    pub success_count: u64,
    pub old_successes: u64,
    pub old_total: u64,
    pub new_successes: u64,
    pub new_total: u64,
    pub retained_successes: u64,
    pub retained_count: u64,
    pub negative_transfer_count: u64,
    pub calibration_error: f64,
    pub total_cost: f64,
}

impl Registry {
    pub(crate) fn learning_status_aggregates(&self) -> Result<LearningAggregates> {
        let conn = self.lock_conn();
        let success = "json_extract(envelope_json,'$.outcome.success')";
        let experience_total: u64 =
            conn.query_row("SELECT COUNT(*) FROM experiences", [], |row| row.get(0))?;
        let midpoint = experience_total / 2;
        let decision_count: u64 = conn.query_row(
            "SELECT COUNT(*) FROM learning_decisions d
             WHERE d.id=(SELECT d2.id FROM learning_decisions d2
               WHERE d2.experience_id=d.experience_id
               ORDER BY d2.created_at DESC,d2.id DESC LIMIT 1)",
            [],
            |row| row.get(0),
        )?;
        let success_count: u64 = conn.query_row(
            &format!("SELECT COUNT(*) FROM experiences WHERE {success}=1"),
            [],
            |row| row.get(0),
        )?;
        let (old_successes, old_total): (u64, u64) = conn.query_row(
            &format!(
                "SELECT COALESCE(SUM({success}=1),0), COUNT(*) FROM (
                   SELECT envelope_json FROM experiences ORDER BY created_at,id LIMIT ?1
                 )"
            ),
            params![midpoint as i64],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )?;
        let (new_successes, new_total): (u64, u64) = conn.query_row(
            &format!(
                "SELECT COALESCE(SUM({success}=1),0), COUNT(*) FROM (
                   SELECT envelope_json FROM experiences ORDER BY created_at,id LIMIT -1 OFFSET ?1
                 )"
            ),
            params![midpoint as i64],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )?;
        let (retained_successes, retained_count): (u64, u64) = conn.query_row(
            &format!(
                "SELECT COALESCE(SUM({success}=1),0), COUNT(*) FROM experiences
                 WHERE task_family IN (
                   SELECT task_family FROM experiences GROUP BY task_family HAVING COUNT(*)>1
                 )"
            ),
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )?;
        let negative_transfer_count: u64 = conn.query_row(
            "SELECT COUNT(*) FROM experiences e WHERE EXISTS(
               SELECT 1 FROM feedback_signals f
               WHERE f.experience_id=e.id
                 AND json_extract(f.signal_json,'$.evidence.negative_transfer')=1
             )",
            [],
            |row| row.get(0),
        )?;
        let calibration_error: f64 = conn
            .query_row(
                &format!(
                    "SELECT AVG(ABS(json_extract(d.decision_json,'$.scores.correctness')
                        - COALESCE({success},0)))
                     FROM learning_decisions d JOIN experiences e ON e.id=d.experience_id
                     WHERE d.id=(SELECT d2.id FROM learning_decisions d2
                       WHERE d2.experience_id=d.experience_id
                       ORDER BY d2.created_at DESC,d2.id DESC LIMIT 1)",
                    success = success.replace("envelope_json", "e.envelope_json")
                ),
                [],
                |row| row.get::<_, Option<f64>>(0),
            )?
            .unwrap_or(0.0);
        let total_cost: f64 = conn.query_row(
            "SELECT COALESCE(SUM(json_extract(envelope_json,'$.cost.estimated_usd')),0.0)
             FROM experiences",
            [],
            |row| row.get(0),
        )?;
        Ok(LearningAggregates {
            decision_count,
            success_count,
            old_successes,
            old_total,
            new_successes,
            new_total,
            retained_successes,
            retained_count,
            negative_transfer_count,
            calibration_error,
            total_cost,
        })
    }
}

impl Registry {
    pub fn create_curriculum(&self, request: &CreateCurriculumRequest) -> Result<CurriculumPlan> {
        validate_curriculum(request)?;
        self.reserve_acquisition_budget(1, 0, 0)?;
        let conn = self.lock_conn();
        let plan = CurriculumPlan {
            schema_version: SCHEMA_VERSION.into(),
            curriculum_id: Uuid::new_v4(),
            trigger: request.trigger,
            topic: request.topic.trim().to_owned(),
            query: request.query.trim().to_owned(),
            policy: request.policy.clone(),
            status: "scheduled".into(),
            fixed_commit_required: true,
            created_at: Utc::now(),
        };
        conn.execute(
            "INSERT INTO curricula (id,topic,query,plan_json,status,created_at) VALUES (?1,?2,?3,?4,?5,?6)",
            params![
                plan.curriculum_id.to_string(),
                plan.topic,
                plan.query,
                serde_json::to_string(&plan)?,
                plan.status,
                plan.created_at.to_rfc3339(),
            ],
        )?;
        Ok(plan)
    }

    pub fn reserve_acquisition_budget(
        &self,
        search_plans: u32,
        repositories: u32,
        files: u32,
    ) -> Result<()> {
        let day = Utc::now().format("%Y-%m-%d").to_string();
        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        tx.execute(
            "INSERT OR IGNORE INTO acquisition_usage (day,search_plans,repositories,files) VALUES (?1,0,0,0)",
            params![day],
        )?;
        let current: (u32, u32, u32) = tx.query_row(
            "SELECT search_plans,repositories,files FROM acquisition_usage WHERE day=?1",
            params![day],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )?;
        if current.0.saturating_add(search_plans) > 20
            || current.1.saturating_add(repositories) > 50
            || current.2.saturating_add(files) > 500
        {
            bail!("global daily GitHub acquisition budget exhausted");
        }
        tx.execute(
            "UPDATE acquisition_usage SET search_plans=search_plans+?2,repositories=repositories+?3,files=files+?4 WHERE day=?1",
            params![day,search_plans,repositories,files],
        )?;
        tx.commit()?;
        Ok(())
    }

    pub fn list_curricula(&self) -> Result<Vec<CurriculumPlan>> {
        let conn = self.lock_conn();
        let mut statement =
            conn.prepare("SELECT plan_json FROM curricula ORDER BY created_at DESC,id")?;
        deserialize_rows(statement.query_map([], |row| row.get::<_, String>(0))?)
    }

    pub fn enqueue_learning_job(
        &self,
        kind: &str,
        payload: Value,
        priority: f64,
        max_attempts: u32,
    ) -> Result<LearningJob> {
        if kind.trim().is_empty() || max_attempts == 0 {
            bail!("learning job requires kind and at least one attempt");
        }
        let now = Utc::now();
        let job = LearningJob {
            job_id: Uuid::new_v4(),
            kind: kind.into(),
            payload,
            priority: priority.max(0.0),
            status: LearningJobStatus::Pending,
            attempts: 0,
            max_attempts,
            lease_owner: None,
            lease_until: None,
            last_error: None,
            created_at: now,
        };
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO learning_jobs (id,kind,payload_json,priority,status,attempts,max_attempts,created_at,updated_at) VALUES (?1,?2,?3,?4,'pending',0,?5,?6,?6)",
            params![
                job.job_id.to_string(),
                job.kind,
                serde_json::to_string(&job.payload)?,
                job.priority,
                job.max_attempts,
                now.to_rfc3339(),
            ],
        )?;
        Ok(job)
    }

    pub fn enqueue_unique_learning_job(
        &self,
        kind: &str,
        dedup_key: &str,
        payload: Value,
        priority: f64,
        max_attempts: u32,
    ) -> Result<Option<LearningJob>> {
        if kind.trim().is_empty() || dedup_key.trim().is_empty() || max_attempts == 0 {
            bail!("unique learning job requires kind, dedup key, and attempts");
        }
        let now = Utc::now();
        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        let active: i64 = tx.query_row(
            "SELECT EXISTS(SELECT 1 FROM learning_job_keys k JOIN learning_jobs j ON j.id=k.job_id WHERE k.kind=?1 AND k.dedup_key=?2 AND j.status IN ('pending','leased'))",
            params![kind,dedup_key],
            |row| row.get(0),
        )?;
        if active != 0 {
            tx.commit()?;
            return Ok(None);
        }
        let job = LearningJob {
            job_id: Uuid::new_v4(),
            kind: kind.into(),
            payload,
            priority: priority.max(0.0),
            status: LearningJobStatus::Pending,
            attempts: 0,
            max_attempts,
            lease_owner: None,
            lease_until: None,
            last_error: None,
            created_at: now,
        };
        tx.execute(
            "INSERT INTO learning_jobs (id,kind,payload_json,priority,status,attempts,max_attempts,created_at,updated_at) VALUES (?1,?2,?3,?4,'pending',0,?5,?6,?6)",
            params![job.job_id.to_string(),job.kind,serde_json::to_string(&job.payload)?,job.priority,job.max_attempts,now.to_rfc3339()],
        )?;
        tx.execute(
            "INSERT INTO learning_job_keys (kind,dedup_key,job_id) VALUES (?1,?2,?3) ON CONFLICT(kind,dedup_key) DO UPDATE SET job_id=excluded.job_id",
            params![kind,dedup_key,job.job_id.to_string()],
        )?;
        tx.commit()?;
        Ok(Some(job))
    }

    /// Claim the highest-priority pending job (optionally restricted to
    /// `kinds`) with the same race-safe UPDATE guard for both variants.
    pub fn claim_learning_job(
        &self,
        kinds: Option<&[&str]>,
        worker: &str,
        lease_seconds: i64,
    ) -> Result<Option<LearningJob>> {
        if worker.trim().is_empty() || kinds.is_some_and(|kinds| kinds.is_empty()) {
            bail!("worker id must not be empty");
        }
        let now = Utc::now();
        let lease_until = now + Duration::seconds(lease_seconds.clamp(1, 21_600));
        let mut conn = self.lock_conn();
        let tx = conn.transaction()?;
        tx.execute(
            "UPDATE learning_jobs SET status='pending',lease_owner=NULL,lease_until=NULL,updated_at=?1 WHERE status='leased' AND lease_until<?1",
            params![now.to_rfc3339()],
        )?;
        type JobRow = (String, String, String, f64, u32, u32, String);
        // Kind filter stays in SQL (never after the LIMIT window): a backlog
        // of high-priority jobs of other kinds would otherwise fill the
        // window and starve every allowed kind indefinitely.
        let kind_filter =
            kinds.map(|kinds| format!("AND kind IN ({})", vec!["?"; kinds.len()].join(",")));
        let candidates: Vec<JobRow> = {
            let mut statement = tx.prepare(&format!(
                "SELECT id,kind,payload_json,priority,attempts,max_attempts,created_at
                 FROM learning_jobs j WHERE status='pending'
                 {}
                 AND NOT EXISTS(
                   SELECT 1 FROM learning_job_delays d
                   WHERE d.job_id=j.id AND d.next_attempt_at>?{}
                 ) ORDER BY priority DESC,created_at,id LIMIT 100",
                kind_filter.as_deref().unwrap_or(""),
                kinds.map_or(1, |kinds| kinds.len() + 1)
            ))?;
            let bound: Vec<String> = kinds
                .unwrap_or_default()
                .iter()
                .map(|kind| (*kind).to_string())
                .chain(std::iter::once(now.to_rfc3339()))
                .collect();
            statement
                .query_map(rusqlite::params_from_iter(bound), |row| {
                    Ok((
                        row.get(0)?,
                        row.get(1)?,
                        row.get(2)?,
                        row.get(3)?,
                        row.get(4)?,
                        row.get(5)?,
                        row.get(6)?,
                    ))
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };
        // A concurrent process may lease a candidate between our SELECT and
        // UPDATE (WAL allows cross-process readers); the status guard makes
        // the UPDATE a no-op in that case, so try candidates until one sticks.
        let mut claimed: Option<JobRow> = None;
        for candidate in candidates {
            let changed = tx.execute(
                "UPDATE learning_jobs SET status='leased',attempts=attempts+1,lease_owner=?2,lease_until=?3,updated_at=?4 WHERE id=?1 AND status='pending'",
                params![candidate.0, worker, lease_until.to_rfc3339(), now.to_rfc3339()],
            )?;
            if changed == 1 {
                tx.execute(
                    "DELETE FROM learning_job_delays WHERE job_id=?1",
                    params![candidate.0],
                )?;
                claimed = Some(candidate);
                break;
            }
        }
        let Some((id, kind, payload, priority, attempts, max_attempts, created_at)) = claimed
        else {
            tx.commit()?;
            return Ok(None);
        };
        tx.commit()?;
        Ok(Some(LearningJob {
            job_id: Uuid::parse_str(&id)?,
            kind,
            payload: serde_json::from_str(&payload)?,
            priority,
            status: LearningJobStatus::Leased,
            attempts: attempts + 1,
            max_attempts,
            lease_owner: Some(worker.into()),
            lease_until: Some(lease_until),
            last_error: None,
            created_at: DateTime::parse_from_rfc3339(&created_at)?.with_timezone(&Utc),
        }))
    }

    pub fn list_learning_jobs(
        &self,
        status: Option<LearningJobStatus>,
        limit: usize,
    ) -> Result<Vec<LearningJob>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT id,kind,payload_json,priority,attempts,max_attempts,status,lease_owner,lease_until,last_error,created_at
             FROM learning_jobs WHERE (?1 IS NULL OR status=?1)
             ORDER BY created_at DESC,id LIMIT ?2",
        )?;
        let status_name = status.map(learning_job_status_name);
        let rows = statement
            .query_map(params![status_name, limit as i64], |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, f64>(3)?,
                    row.get::<_, u32>(4)?,
                    row.get::<_, u32>(5)?,
                    row.get::<_, String>(6)?,
                    row.get::<_, Option<String>>(7)?,
                    row.get::<_, Option<String>>(8)?,
                    row.get::<_, Option<String>>(9)?,
                    row.get::<_, String>(10)?,
                ))
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?;
        rows.into_iter()
            .map(
                |(
                    id,
                    kind,
                    payload,
                    priority,
                    attempts,
                    max_attempts,
                    status,
                    lease_owner,
                    lease_until,
                    last_error,
                    created_at,
                )| {
                    let status: LearningJobStatus = serde_json::from_value(Value::String(status))?;
                    let lease_until = lease_until
                        .map(|value| {
                            DateTime::parse_from_rfc3339(&value)
                                .map(|parsed| parsed.with_timezone(&Utc))
                        })
                        .transpose()?;
                    Ok(LearningJob {
                        job_id: Uuid::parse_str(&id)?,
                        kind,
                        payload: serde_json::from_str(&payload)?,
                        priority,
                        status,
                        attempts,
                        max_attempts,
                        lease_owner,
                        lease_until,
                        last_error,
                        created_at: DateTime::parse_from_rfc3339(&created_at)?.with_timezone(&Utc),
                    })
                },
            )
            .collect()
    }

    pub fn save_learning_job_result(&self, id: Uuid, result: &Value) -> Result<String> {
        let bytes = serde_json::to_vec(result)?;
        let hash = self.put_object(&bytes)?;
        let conn = self.lock_conn();
        let exists: i64 = conn.query_row(
            "SELECT EXISTS(SELECT 1 FROM learning_jobs WHERE id=?1)",
            params![id.to_string()],
            |row| row.get(0),
        )?;
        if exists == 0 {
            bail!("learning job not found");
        }
        conn.execute(
            "INSERT OR REPLACE INTO learning_job_results (job_id,result_hash,result_json,created_at) VALUES (?1,?2,?3,?4)",
            params![id.to_string(),hash,serde_json::to_string(result)?,Utc::now().to_rfc3339()],
        )?;
        Ok(hash)
    }

    pub fn complete_learning_job(&self, id: Uuid, worker: &str) -> Result<()> {
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let changed = transaction.execute(
            "UPDATE learning_jobs SET status='completed',lease_owner=NULL,lease_until=NULL,updated_at=?3 WHERE id=?1 AND status='leased' AND lease_owner=?2",
            params![id.to_string(), worker, Utc::now().to_rfc3339()],
        )?;
        if changed != 1 {
            bail!("job is not leased by this worker");
        }
        transaction.execute(
            "DELETE FROM learning_job_delays WHERE job_id=?1",
            params![id.to_string()],
        )?;
        transaction.commit()?;
        Ok(())
    }

    /// Complete a leased job only after its kind-specific validator passes —
    /// kind lookup, validation, and the status transition in ONE transaction,
    /// so concurrent completes and validator/completion races are impossible.
    /// New job kinds register their validator in this match, not in HTTP.
    pub fn complete_learning_job_validated(&self, id: Uuid, worker: &str) -> Result<()> {
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let kind: Option<String> = transaction
            .query_row(
                "SELECT kind FROM learning_jobs WHERE id=?1",
                params![id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        let kind = kind.ok_or_else(|| anyhow!("learning job not found"))?;
        match kind.as_str() {
            "skillopt_optimize_v1" => {
                crate::optimization_store::validate_optimization_completion(&transaction, id)?
            }
            "document_acquire_v1" | "social_acquisition_v1" => {
                crate::knowledge_store::validate_acquisition_completion(&transaction, id)?
            }
            "meta_train_v1" => {
                crate::meta_training::validate_meta_training_completion(&transaction, id)?
            }
            _ => {}
        }
        let changed = transaction.execute(
            "UPDATE learning_jobs SET status='completed',lease_owner=NULL,lease_until=NULL,updated_at=?3 WHERE id=?1 AND status='leased' AND lease_owner=?2",
            params![id.to_string(), worker, Utc::now().to_rfc3339()],
        )?;
        if changed != 1 {
            bail!("job is not leased by this worker");
        }
        transaction.execute(
            "DELETE FROM learning_job_delays WHERE job_id=?1",
            params![id.to_string()],
        )?;
        transaction.commit()?;
        Ok(())
    }

    pub fn fail_learning_job(&self, id: Uuid, worker: &str, error: &str) -> Result<()> {
        self.fail_learning_job_with_delay(id, worker, error, 0)
    }

    pub fn fail_learning_job_with_delay(
        &self,
        id: Uuid,
        worker: &str,
        error: &str,
        retry_after_seconds: u64,
    ) -> Result<()> {
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let row: Option<(u32, u32)> = transaction
            .query_row(
                "SELECT attempts,max_attempts FROM learning_jobs WHERE id=?1 AND status='leased' AND lease_owner=?2",
                params![id.to_string(), worker],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        let (attempts, max_attempts) =
            row.ok_or_else(|| anyhow!("job is not leased by this worker"))?;
        let status = if attempts >= max_attempts {
            "dead_letter"
        } else {
            "pending"
        };
        transaction.execute(
            "UPDATE learning_jobs SET status=?3,lease_owner=NULL,lease_until=NULL,last_error=?4,updated_at=?5 WHERE id=?1 AND lease_owner=?2",
            params![id.to_string(),worker,status,error, Utc::now().to_rfc3339()],
        )?;
        if status == "pending" && retry_after_seconds > 0 {
            let next_attempt_at =
                Utc::now() + Duration::seconds(retry_after_seconds.min(86_400) as i64);
            transaction.execute(
                "INSERT INTO learning_job_delays(job_id,next_attempt_at) VALUES(?1,?2)
                 ON CONFLICT(job_id) DO UPDATE SET next_attempt_at=excluded.next_attempt_at",
                params![id.to_string(), next_attempt_at.to_rfc3339()],
            )?;
        } else {
            transaction.execute(
                "DELETE FROM learning_job_delays WHERE job_id=?1",
                params![id.to_string()],
            )?;
        }
        transaction.commit()?;
        Ok(())
    }

    pub fn save_training_candidate(&self, candidate: &TrainingCandidate) -> Result<()> {
        validate_training_candidate(candidate)?;
        let conn = self.lock_conn();
        let transaction = conn.unchecked_transaction()?;
        // A newer candidate supersedes every previously-ready dataset, so at
        // most one ready_for_training candidate exists at any time. Status is
        // lifecycle metadata: manifest and dataset hashes stay untouched.
        let mut statement = transaction.prepare(
            "SELECT id,candidate_json FROM training_candidates WHERE status='ready_for_training'",
        )?;
        let outdated: Vec<(String, String)> = statement
            .query_map([], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        drop(statement);
        for (id, outdated_json) in outdated {
            let mut parsed: TrainingCandidate = serde_json::from_str(&outdated_json)?;
            parsed.status = TrainingCandidateStatus::Superseded;
            transaction.execute(
                "UPDATE training_candidates SET status='superseded',candidate_json=?2 WHERE id=?1",
                params![id, serde_json::to_string(&parsed)?],
            )?;
        }
        transaction.execute(
            "INSERT OR IGNORE INTO training_candidates (id,dataset_hash,manifest_hash,candidate_json,status,created_at) VALUES (?1,?2,?3,?4,?5,?6)",
            params![
                candidate.candidate_id.to_string(),
                candidate.dataset_hash,
                candidate.manifest_hash,
                serde_json::to_string(candidate)?,
                training_status(candidate.status),
                candidate.created_at.to_rfc3339(),
            ],
        )?;
        transaction.commit()?;
        Ok(())
    }

    pub fn list_training_candidates(&self) -> Result<Vec<TrainingCandidate>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT candidate_json FROM training_candidates ORDER BY created_at DESC,id",
        )?;
        deserialize_rows(statement.query_map([], |row| row.get::<_, String>(0))?)
    }

    pub fn register_model(&self, model: &ModelVersion) -> Result<()> {
        if model.status != ModelStatus::Candidate {
            bail!("new model versions must start as candidate");
        }
        if model.artifact_hash.len() != 64
            || !model
                .artifact_hash
                .chars()
                .all(|character| character.is_ascii_hexdigit() && !character.is_ascii_uppercase())
        {
            bail!("model artifact hash must be a lowercase SHA-256 digest");
        }
        let training_candidate = self
            .list_training_candidates()?
            .iter()
            .find(|candidate| candidate.candidate_id == model.training_candidate_id)
            .cloned()
            .ok_or_else(|| anyhow!("model references an unknown training candidate"))?;
        if training_candidate.status != TrainingCandidateStatus::ReadyForTraining {
            bail!("model requires a training candidate with sufficient evidence");
        }
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO model_versions (model_id,version,status,model_json,updated_at) VALUES (?1,?2,'candidate',?3,?4)",
            params![model.model_id,model.version,serde_json::to_string(model)?,model.updated_at.to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn review_model(
        &self,
        model_id: &str,
        version: &str,
        action: &str,
        review: &ModelReviewRequest,
    ) -> Result<ModelVersion> {
        if review.actor.trim().is_empty() || review.reason.trim().is_empty() {
            bail!("model review requires a human actor and reason");
        }
        let conn = self.lock_conn();
        let json: String = conn
            .query_row(
                "SELECT model_json FROM model_versions WHERE model_id=?1 AND version=?2",
                params![model_id, version],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("model version not found"))?;
        let mut model: ModelVersion = serde_json::from_str(&json)?;
        model.status = match action {
            "approve"
                if model.status == ModelStatus::Candidate
                    && model.evidence.qualifies_for_activation() =>
            {
                ModelStatus::Active
            }
            "approve" if model.status == ModelStatus::Candidate => {
                bail!(
                    "model evidence does not beat the rule baseline safely by the required margin"
                )
            }
            "reject" if model.status == ModelStatus::Candidate => ModelStatus::Rejected,
            "rollback" if model.status == ModelStatus::Active => ModelStatus::RolledBack,
            _ => bail!("invalid model review transition"),
        };
        model.reviewed_by = Some(review.actor.clone());
        model.review_reason = Some(review.reason.clone());
        model.updated_at = Utc::now();
        if model.status == ModelStatus::Active {
            conn.execute(
                "UPDATE model_versions SET status='approved' WHERE status='active' AND NOT (model_id=?1 AND version=?2)",
                params![model_id, version],
            )?;
        }
        conn.execute(
            "UPDATE model_versions SET status=?3,model_json=?4,updated_at=?5 WHERE model_id=?1 AND version=?2",
            params![model_id,version,model_status(model.status),serde_json::to_string(&model)?,model.updated_at.to_rfc3339()],
        )?;
        Self::audit_conn(
            &conn,
            "model",
            &format!("{model_id}@{version}"),
            action,
            review.actor.trim(),
            review.reason.trim(),
            Utc::now(),
        )?;
        Ok(model)
    }

    pub fn learning_training_records(&self) -> Result<Vec<Value>> {
        let decisions = self.latest_learning_decisions()?;
        let mut records = Vec::with_capacity(decisions.len());
        for decision in decisions {
            let experience = self
                .get_experience(decision.experience_id)?
                .ok_or_else(|| anyhow!("learning decision references missing experience"))?;
            records.push(serde_json::json!({
                "kind": "learning_decision",
                "repository_split": experience.repository.repository_id,
                "task_family_split": experience.task_family,
                "experience": experience,
                "feedback": self.feedback_for_experience(decision.experience_id)?,
                "target": decision,
            }));
        }
        Ok(records)
    }

    pub fn learning_table_counts(&self) -> Result<(u64, u64, u64, u64, u64, u64, u64)> {
        let conn = self.lock_conn();
        let count = |table: &str, condition: &str| -> Result<u64> {
            let query = format!("SELECT COUNT(*) FROM {table} {condition}");
            Ok(conn.query_row(&query, [], |row| row.get(0))?)
        };
        Ok((
            count("experiences", "")?,
            count("feedback_signals", "")?,
            count("learning_decisions", "")?,
            count("memory_proposals", "")?,
            count("learning_jobs", "WHERE status IN ('pending','leased')")?,
            count("learning_jobs", "WHERE status='dead_letter'")?,
            count("training_candidates", "")?,
        ))
    }

    pub fn split_counts(&self) -> Result<(u64, u64)> {
        let conn = self.lock_conn();
        let repositories = conn.query_row(
            "SELECT COUNT(DISTINCT repository_id) FROM experiences",
            [],
            |row| row.get(0),
        )?;
        let families = conn.query_row(
            "SELECT COUNT(DISTINCT task_family) FROM experiences",
            [],
            |row| row.get(0),
        )?;
        Ok((repositories, families))
    }
}

fn deserialize_optional<T: serde::de::DeserializeOwned>(json: Option<String>) -> Result<Option<T>> {
    json.map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
}

fn deserialize_rows<T, I>(rows: I) -> Result<Vec<T>>
where
    T: serde::de::DeserializeOwned,
    I: Iterator<Item = rusqlite::Result<String>>,
{
    rows.map(|row| Ok(serde_json::from_str(&row?)?)).collect()
}

fn source_kind(value: ExperienceSourceKind) -> &'static str {
    match value {
        ExperienceSourceKind::AgentTrace => "agent_trace",
        ExperienceSourceKind::Github => "github",
        ExperienceSourceKind::Simulation => "simulation",
    }
}

fn feedback_kind(value: FeedbackKind) -> &'static str {
    match value {
        FeedbackKind::Test => "test",
        FeedbackKind::Build => "build",
        FeedbackKind::Gate => "gate",
        FeedbackKind::Human => "human",
        FeedbackKind::DelayedOutcome => "delayed_outcome",
        FeedbackKind::LlmCritic => "llm_critic",
    }
}

pub(crate) fn memory_kind(value: MemoryKind) -> &'static str {
    match value {
        MemoryKind::Episodic => "episodic",
        MemoryKind::Fact => "fact",
        MemoryKind::Failure => "failure",
        MemoryKind::AntiSkill => "anti_skill",
        MemoryKind::SkillProposal => "skill_proposal",
        MemoryKind::WorkflowProposal => "workflow_proposal",
    }
}

fn learning_job_status_name(value: LearningJobStatus) -> &'static str {
    match value {
        LearningJobStatus::Pending => "pending",
        LearningJobStatus::Leased => "leased",
        LearningJobStatus::Completed => "completed",
        LearningJobStatus::DeadLetter => "dead_letter",
    }
}

fn training_status(value: TrainingCandidateStatus) -> &'static str {
    match value {
        TrainingCandidateStatus::InsufficientEvidence => "insufficient_evidence",
        TrainingCandidateStatus::ReadyForTraining => "ready_for_training",
        TrainingCandidateStatus::Superseded => "superseded",
    }
}

fn model_status(value: ModelStatus) -> &'static str {
    match value {
        ModelStatus::Candidate => "candidate",
        ModelStatus::Approved => "approved",
        ModelStatus::Rejected => "rejected",
        ModelStatus::Active => "active",
        ModelStatus::RolledBack => "rolled_back",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::Digest as _;
    #[test]
    fn concurrent_completion_succeeds_exactly_once() {
        let dir = tempdir().unwrap();
        let registry = std::sync::Arc::new(Registry::open(dir.path()).unwrap());
        let enqueued = registry
            .enqueue_learning_job("training_manifest_refresh", serde_json::json!({}), 0.5, 3)
            .unwrap();
        let job = registry
            .claim_learning_job(None, "w1", 300)
            .unwrap()
            .expect("job claimed");
        assert_eq!(job.job_id, enqueued.job_id);
        let first = {
            let registry = registry.clone();
            std::thread::spawn(move || registry.complete_learning_job_validated(job.job_id, "w1"))
        };
        let second = {
            let registry = registry.clone();
            std::thread::spawn(move || registry.complete_learning_job_validated(job.job_id, "w1"))
        };
        let outcomes = [first.join().unwrap(), second.join().unwrap()];
        assert_eq!(
            outcomes.iter().filter(|outcome| outcome.is_ok()).count(),
            1,
            "exactly one concurrent completion may win: {outcomes:?}"
        );
    }

    #[test]
    fn validator_failure_leaves_job_uncompleted() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let enqueued = registry
            .enqueue_learning_job("meta_train_v1", serde_json::json!({}), 0.5, 3)
            .unwrap();
        let job = registry
            .claim_learning_job(None, "w1", 300)
            .unwrap()
            .expect("job claimed");
        assert_eq!(job.job_id, enqueued.job_id);
        // No meta_training_job_results row: validation fails, and the job
        // stays leased instead of half-completing.
        assert!(
            registry
                .complete_learning_job_validated(job.job_id, "w1")
                .is_err()
        );
        let status: String = registry
            .lock_conn()
            .query_row(
                "SELECT status FROM learning_jobs WHERE id=?1",
                params![job.job_id.to_string()],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(status, "leased");
    }
    use crate::learning::{synthetic_experience, synthetic_feedback};
    use tempfile::tempdir;

    #[test]
    fn durable_jobs_retry_then_dead_letter() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let job = registry
            .enqueue_learning_job("test", serde_json::json!({}), 1.0, 2)
            .unwrap();
        let first = registry
            .claim_learning_job(None, "worker", 30)
            .unwrap()
            .unwrap();
        assert_eq!(first.job_id, job.job_id);
        registry
            .fail_learning_job(job.job_id, "worker", "first")
            .unwrap();
        let second = registry
            .claim_learning_job(None, "worker", 30)
            .unwrap()
            .unwrap();
        assert_eq!(second.attempts, 2);
        registry
            .fail_learning_job(job.job_id, "worker", "second")
            .unwrap();
        let (_, _, _, _, pending, dead, _) = registry.learning_table_counts().unwrap();
        assert_eq!(pending, 0);
        assert_eq!(dead, 1);
    }
    #[test]
    fn delayed_retry_is_not_claimed_before_its_due_time() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let delayed = registry
            .enqueue_learning_job("delayed", serde_json::json!({}), 10.0, 2)
            .unwrap();
        let ready = registry
            .enqueue_learning_job("ready", serde_json::json!({}), 1.0, 2)
            .unwrap();
        let leased = registry
            .claim_learning_job(None, "worker", 30)
            .unwrap()
            .unwrap();
        assert_eq!(leased.job_id, delayed.job_id);
        registry
            .fail_learning_job_with_delay(delayed.job_id, "worker", "rate limited", 3_600)
            .unwrap();
        let next = registry
            .claim_learning_job(None, "worker", 30)
            .unwrap()
            .unwrap();
        assert_eq!(next.job_id, ready.job_id);
    }

    #[test]
    fn kind_filtering_is_not_starved_by_other_kinds_backlog() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        // More than one LIMIT-100 window of higher-priority jobs of a kind the
        // worker does not serve must not hide the allowed low-priority job.
        for index in 0..150 {
            registry
                .enqueue_learning_job("bulk_acquire", serde_json::json!({"index":index}), 100.0, 1)
                .unwrap();
        }
        let wanted = registry
            .enqueue_learning_job("dataset_build", serde_json::json!({}), 0.1, 1)
            .unwrap();
        let claimed = registry
            .claim_learning_job(Some(&["dataset_build"]), "scheduler", 30)
            .unwrap()
            .expect("allowed kind must be claimable despite the backlog");
        assert_eq!(claimed.job_id, wanted.job_id);
        // The disallowed backlog remains pending and untouched.
        assert!(
            registry
                .claim_learning_job(Some(&["dataset_build"]), "scheduler", 30)
                .unwrap()
                .is_none()
        );
    }

    fn candidate_model(registry: &Registry, model_id: &str, version: &str) -> ModelVersion {
        let now = Utc::now();
        let candidate = TrainingCandidate {
            candidate_id: Uuid::new_v4(),
            dataset_hash: "a".repeat(64),
            manifest_hash: format!("{:x}", sha2::Sha256::digest(version.as_bytes())),
            decision_count: cerebellum_core::MIN_ROUTING_DECISIONS,
            paired_eval_count: cerebellum_core::MIN_PAIRED_EVALS,
            status: TrainingCandidateStatus::ReadyForTraining,
            repository_split_count: 1,
            task_family_split_count: 1,
            trainer_enabled: false,
            created_at: now,
        };
        registry.save_training_candidate(&candidate).unwrap();
        ModelVersion {
            model_id: model_id.into(),
            version: version.into(),
            artifact_hash: "a".repeat(64),
            training_candidate_id: candidate.candidate_id,
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
        }
    }

    #[test]
    fn review_model_reject_marks_candidate_rejected_and_terminal() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        registry
            .register_model(&candidate_model(&registry, "m", "1.0.0"))
            .unwrap();
        let rejected = registry
            .review_model(
                "m",
                "1.0.0",
                "reject",
                &ModelReviewRequest {
                    actor: "admin".into(),
                    reason: "insufficient margin".into(),
                },
            )
            .unwrap();
        assert_eq!(rejected.status, ModelStatus::Rejected);
        // Rejected is terminal: no further transitions are possible.
        assert!(
            registry
                .review_model(
                    "m",
                    "1.0.0",
                    "approve",
                    &ModelReviewRequest {
                        actor: "admin".into(),
                        reason: "retry".into(),
                    },
                )
                .is_err()
        );
        let action: String = registry
            .lock_conn()
            .query_row(
                "SELECT action FROM learning_audit WHERE subject_type='model' AND subject_id='m@1.0.0'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(action, "reject");
    }

    #[test]
    fn approving_a_new_model_demotes_the_previous_active() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let review = || ModelReviewRequest {
            actor: "admin".into(),
            reason: "promote".into(),
        };
        registry
            .register_model(&candidate_model(&registry, "m", "1.0.0"))
            .unwrap();
        registry
            .review_model("m", "1.0.0", "approve", &review())
            .unwrap();
        registry
            .register_model(&candidate_model(&registry, "m", "1.1.0"))
            .unwrap();
        registry
            .review_model("m", "1.1.0", "approve", &review())
            .unwrap();

        // The previous Active row is demoted to approved on every surface.
        let old_status: String = registry
            .lock_conn()
            .query_row(
                "SELECT status FROM model_versions WHERE model_id='m' AND version='1.0.0'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(old_status, "approved");
        let new_status: String = registry
            .lock_conn()
            .query_row(
                "SELECT status FROM model_versions WHERE model_id='m' AND version='1.1.0'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(new_status, "active");
    }

    #[test]
    fn immutable_ids_are_idempotent_but_reject_changed_content() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let experience = synthetic_experience(1);
        assert!(registry.insert_experience(&experience).unwrap());
        assert!(!registry.insert_experience(&experience).unwrap());
        let mut changed = experience.clone();
        changed.task = "different immutable content".into();
        assert!(registry.insert_experience(&changed).is_err());
    }

    #[test]
    fn forged_objective_feedback_is_rejected() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let experience = synthetic_experience(1);
        registry.insert_experience(&experience).unwrap();
        let mut feedback = synthetic_feedback(&registry, &experience);
        feedback.attestation = Some("Zm9yZ2Vk".into());
        assert!(registry.insert_feedback(&feedback).is_err());
    }

    #[test]
    fn global_acquisition_budget_is_atomic_and_strict() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        for index in 0..20 {
            registry
                .create_curriculum(&CreateCurriculumRequest {
                    trigger: CurriculumTrigger::Manual,
                    topic: format!("topic-{index}"),
                    query: format!("query-{index}"),
                    policy: CurriculumPolicy {
                        topics: vec![],
                        organizations: vec![],
                        licenses: vec![],
                        repositories: vec![],
                        daily_budget: DailyBudget::default(),
                    },
                })
                .unwrap();
        }
        let overflow = CreateCurriculumRequest {
            trigger: CurriculumTrigger::Manual,
            topic: "overflow".into(),
            query: "overflow".into(),
            policy: CurriculumPolicy {
                topics: vec![],
                organizations: vec![],
                licenses: vec![],
                repositories: vec![],
                daily_budget: DailyBudget::default(),
            },
        };
        assert!(registry.create_curriculum(&overflow).is_err());
        assert!(registry.reserve_acquisition_budget(0, 50, 500).is_ok());
        assert!(registry.reserve_acquisition_budget(0, 1, 0).is_err());
        assert!(registry.reserve_acquisition_budget(0, 0, 1).is_err());
    }

    #[test]
    fn model_activation_requires_ready_data_safe_gain_and_human_review() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let candidate = TrainingCandidate {
            candidate_id: Uuid::new_v4(),
            dataset_hash: "a".repeat(64),
            manifest_hash: "b".repeat(64),
            decision_count: 5_000,
            paired_eval_count: 1_000,
            status: TrainingCandidateStatus::ReadyForTraining,
            repository_split_count: 100,
            task_family_split_count: 20,
            trainer_enabled: false,
            created_at: Utc::now(),
        };
        registry.save_training_candidate(&candidate).unwrap();
        let now = Utc::now();
        let model = ModelVersion {
            model_id: "controller".into(),
            version: "1.0.0".into(),
            artifact_hash: "c".repeat(64),
            training_candidate_id: candidate.candidate_id,
            evidence: ModelEvidence {
                task_success_uplift: 0.01,
                gate_violation_delta: 0,
                latency_improvement: 0.2,
                memory_improvement: 0.0,
            },
            status: ModelStatus::Candidate,
            reviewed_by: None,
            review_reason: None,
            created_at: now,
            updated_at: now,
        };
        registry.register_model(&model).unwrap();
        assert!(
            registry
                .review_model(
                    "controller",
                    "1.0.0",
                    "approve",
                    &ModelReviewRequest {
                        actor: "".into(),
                        reason: "ship".into(),
                    },
                )
                .is_err()
        );
        let active = registry
            .review_model(
                "controller",
                "1.0.0",
                "approve",
                &ModelReviewRequest {
                    actor: "operator@example".into(),
                    reason: "passed held-out evaluation".into(),
                },
            )
            .unwrap();
        assert_eq!(active.status, ModelStatus::Active);
        let rolled_back = registry
            .review_model(
                "controller",
                "1.0.0",
                "rollback",
                &ModelReviewRequest {
                    actor: "operator@example".into(),
                    reason: "production regression".into(),
                },
            )
            .unwrap();
        assert_eq!(rolled_back.status, ModelStatus::RolledBack);
    }

    fn learning_decision(experience_id: Uuid) -> LearningDecision {
        LearningDecision {
            schema_version: SCHEMA_VERSION.into(),
            decision_id: Uuid::new_v4(),
            experience_id,
            scores: LearningScores {
                correctness: 0.8,
                utility: 0.7,
                novelty: 0.5,
                generality: 0.4,
                confidence: 0.6,
                risk: 0.2,
                cost: 0.3,
                expected_gain: 0.5,
            },
            priority: 0.5,
            actions: vec![LearningAction::Store],
            reasons: vec!["fixture".into()],
            controller: "deterministic-learning-v1".into(),
            registry_snapshot: "c".repeat(64),
            training_eligible: false,
            created_at: Utc::now(),
        }
    }

    #[test]
    fn save_learning_decision_rejects_out_of_bounds_scores() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let experience = crate::learning::synthetic_experience(1);
        registry.insert_experience(&experience).unwrap();
        let experience_id = experience.experience_id;
        registry
            .save_learning_decision(&learning_decision(experience_id))
            .unwrap();
        assert!(
            registry
                .latest_learning_decision(experience_id)
                .unwrap()
                .is_some()
        );

        let mut invalid = learning_decision(Uuid::new_v4());
        invalid.scores.expected_gain = 1.5;
        assert!(registry.save_learning_decision(&invalid).is_err());
        let mut invalid = learning_decision(Uuid::new_v4());
        invalid.priority = f64::NAN;
        assert!(registry.save_learning_decision(&invalid).is_err());
        let mut invalid = learning_decision(Uuid::new_v4());
        invalid.schema_version = "cerebellum/v0".into();
        assert!(registry.save_learning_decision(&invalid).is_err());
        let mut invalid = learning_decision(Uuid::new_v4());
        invalid.actions = Vec::new();
        assert!(registry.save_learning_decision(&invalid).is_err());
    }

    #[test]
    fn save_training_candidate_rejects_inconsistent_evidence() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let candidate = TrainingCandidate {
            candidate_id: Uuid::new_v4(),
            dataset_hash: "a".repeat(64),
            manifest_hash: "b".repeat(64),
            decision_count: 3,
            paired_eval_count: 0,
            status: TrainingCandidateStatus::InsufficientEvidence,
            repository_split_count: 1,
            task_family_split_count: 1,
            trainer_enabled: false,
            created_at: Utc::now(),
        };
        registry.save_training_candidate(&candidate).unwrap();

        let mut invalid = candidate.clone();
        invalid.candidate_id = Uuid::new_v4();
        invalid.manifest_hash = "B".repeat(64);
        assert!(registry.save_training_candidate(&invalid).is_err());
        let mut invalid = candidate.clone();
        invalid.candidate_id = Uuid::new_v4();
        invalid.status = TrainingCandidateStatus::ReadyForTraining;
        assert!(registry.save_training_candidate(&invalid).is_err());
        let mut invalid = candidate.clone();
        invalid.candidate_id = Uuid::new_v4();
        invalid.trainer_enabled = true;
        assert!(registry.save_training_candidate(&invalid).is_err());
        assert_eq!(registry.list_training_candidates().unwrap().len(), 1);
    }

    #[test]
    fn new_ready_candidate_supersedes_prior_ready_candidates() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let first = TrainingCandidate {
            candidate_id: Uuid::new_v4(),
            dataset_hash: "a".repeat(64),
            manifest_hash: "b".repeat(64),
            decision_count: cerebellum_core::MIN_ROUTING_DECISIONS,
            paired_eval_count: cerebellum_core::MIN_PAIRED_EVALS,
            status: TrainingCandidateStatus::ReadyForTraining,
            repository_split_count: 1,
            task_family_split_count: 1,
            trainer_enabled: false,
            created_at: Utc::now(),
        };
        registry.save_training_candidate(&first).unwrap();

        let mut second = first.clone();
        second.candidate_id = Uuid::new_v4();
        second.manifest_hash = "c".repeat(64);
        registry.save_training_candidate(&second).unwrap();

        // Exactly one ready candidate remains; the older one reports
        // superseded on both the status column and the stored JSON.
        let status: String = registry
            .lock_conn()
            .query_row(
                "SELECT status FROM training_candidates WHERE id=?1",
                params![first.candidate_id.to_string()],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(status, "superseded");
        let candidates = registry.list_training_candidates().unwrap();
        assert_eq!(candidates.len(), 2);
        let ready: Vec<_> = candidates
            .iter()
            .filter(|candidate| candidate.status == TrainingCandidateStatus::ReadyForTraining)
            .collect();
        assert_eq!(ready.len(), 1);
        assert_eq!(ready[0].candidate_id, second.candidate_id);
        let superseded = candidates
            .iter()
            .find(|candidate| candidate.candidate_id == first.candidate_id)
            .unwrap();
        assert_eq!(superseded.status, TrainingCandidateStatus::Superseded);
    }
}
