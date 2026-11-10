use anyhow::{Context, Result, anyhow, bail};
use base64::Engine;
use cerebellum_core::{
    ActionPermit, AppendEventRequest, CandidateExperience, CompleteRunRequest, CreateRunRequest,
    DecisionRequest, DecisionResponse, FeedbackSignal, GateDecision, GateStatus, GateTrace,
    PairedEvalRecord, RunRecord, RunTrace, SCHEMA_VERSION, SkillLifecycle, SkillManifest,
    TraceEvent, WorkflowEdgeCondition, WorkflowManifest, canonical_json_hash, validate_paired_eval,
    validate_skill, validate_workflow,
};
use chrono::{DateTime, Utc};
use hmac::{Hmac, Mac};
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use uuid::Uuid;

pub struct Registry {
    pub(crate) conn: Mutex<Connection>,
    pub(crate) object_dir: PathBuf,
    feedback_secret: Vec<u8>,
    snapshot_cache: Mutex<Option<String>>,
    #[cfg(test)]
    pub(crate) snapshot_computations: std::sync::atomic::AtomicUsize,
}

type RunRow = (
    String,
    String,
    String,
    Option<String>,
    String,
    String,
    String,
);

impl Registry {
    pub fn open(data_dir: impl AsRef<Path>) -> Result<Self> {
        let data_dir = data_dir.as_ref();
        fs::create_dir_all(data_dir)?;
        let object_dir = data_dir.join("objects");
        fs::create_dir_all(&object_dir)?;
        cleanup_interrupted_uploads(&object_dir)?;
        let conn = Connection::open(data_dir.join("registry.db"))?;
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "synchronous", "NORMAL")?;
        conn.pragma_update(None, "foreign_keys", "ON")?;
        conn.busy_timeout(std::time::Duration::from_secs(5))?;
        conn.execute_batch(MIGRATION)?;
        let feedback_secret = load_or_create_feedback_secret(&data_dir.join("feedback.key"))?;
        let registry = Self {
            conn: Mutex::new(conn),
            object_dir,
            feedback_secret,
            snapshot_cache: Mutex::new(None),
            #[cfg(test)]
            snapshot_computations: std::sync::atomic::AtomicUsize::new(0),
        };
        registry.migrate_legacy_meta_candidates()?;
        Ok(registry)
    }

    /// Lock the registry connection, recovering from mutex poisoning.
    ///
    /// A panic while holding the lock poisons the mutex; the rusqlite
    /// Connection stays usable afterwards (SQLite rolls back any uncommitted
    /// transaction), so refusing every later request would turn one panic
    /// into a permanent outage of all DB endpoints.
    pub(crate) fn lock_conn(&self) -> std::sync::MutexGuard<'_, Connection> {
        self.conn.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// One learning_audit row with the store's standard timestamp.
    pub(crate) fn audit_conn(
        conn: &Connection,
        subject_type: &str,
        subject_id: &str,
        action: &str,
        actor: &str,
        reason: &str,
        now: DateTime<Utc>,
    ) -> Result<()> {
        conn.execute(
            "INSERT INTO learning_audit(subject_type,subject_id,action,actor,reason,created_at)
             VALUES(?1,?2,?3,?4,?5,?6)",
            params![
                subject_type,
                subject_id,
                action,
                actor,
                reason,
                now.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    /// Audit a mutation at the store level (locks the connection itself;
    /// transactional callers must use `audit_conn` with their transaction).
    pub(crate) fn audit(
        &self,
        subject_type: &str,
        subject_id: &str,
        action: &str,
        actor: &str,
        reason: &str,
    ) -> Result<()> {
        Self::audit_conn(
            &self.lock_conn(),
            subject_type,
            subject_id,
            action,
            actor,
            reason,
            Utc::now(),
        )
    }

    pub fn attest_feedback(&self, feedback: &FeedbackSignal) -> Result<String> {
        let payload = feedback_attestation_payload(feedback)?;
        let mut mac = Hmac::<Sha256>::new_from_slice(&self.feedback_secret)
            .map_err(|_| anyhow!("invalid feedback attestation key"))?;
        mac.update(&payload);
        Ok(base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(mac.finalize().into_bytes()))
    }

    pub(crate) fn verify_feedback_attestation(&self, feedback: &FeedbackSignal) -> Result<()> {
        let supplied = feedback
            .attestation
            .as_deref()
            .ok_or_else(|| anyhow!("verifiable feedback requires a sidecar attestation"))?;
        let signature = base64::engine::general_purpose::URL_SAFE_NO_PAD
            .decode(supplied)
            .map_err(|_| anyhow!("invalid feedback attestation encoding"))?;
        let payload = feedback_attestation_payload(feedback)?;
        let mut mac = Hmac::<Sha256>::new_from_slice(&self.feedback_secret)
            .map_err(|_| anyhow!("invalid feedback attestation key"))?;
        mac.update(&payload);
        mac.verify_slice(&signature)
            .map_err(|_| anyhow!("feedback attestation verification failed"))
    }

    pub fn put_object(&self, content: &[u8]) -> Result<String> {
        let hash = format!("{:x}", Sha256::digest(content));
        let prefix = &hash[..2];
        let dir = self.object_dir.join(prefix);
        fs::create_dir_all(&dir)?;
        let path = dir.join(&hash);
        if path.exists() {
            if fs::read(&path)? != content {
                bail!("content-addressed object collision for {hash}");
            }
            return Ok(hash);
        }

        let temporary = dir.join(format!(".{hash}.{}.tmp", Uuid::new_v4().simple()));
        let write_result = (|| -> Result<()> {
            let mut file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temporary)?;
            file.write_all(content)?;
            file.sync_all()?;
            match fs::rename(&temporary, &path) {
                Ok(()) => Ok(()),
                Err(_) if path.exists() && fs::read(&path)? == content => {
                    fs::remove_file(&temporary)?;
                    Ok(())
                }
                Err(error) => Err(error.into()),
            }
        })();
        if write_result.is_err() && temporary.exists() {
            let _ = fs::remove_file(&temporary);
        }
        write_result?;
        Ok(hash)
    }

    pub fn upsert_skill(&self, manifest: &SkillManifest, content: &[u8]) -> Result<()> {
        validate_skill(manifest)?;
        let object_hash = self.put_object(content)?;
        if object_hash != manifest.source.content_hash {
            bail!("manifest content hash does not match supplied content");
        }
        let serialized = serde_json::to_string(manifest)?;
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO skills (id, version, description, status, training_eligible, content_hash, manifest_json, updated_at)\n             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)\n             ON CONFLICT(id, version) DO UPDATE SET description=excluded.description, status=excluded.status,\n               training_eligible=excluded.training_eligible, content_hash=excluded.content_hash,\n               manifest_json=excluded.manifest_json, updated_at=excluded.updated_at",
            params![manifest.id, manifest.version, manifest.description,
                lifecycle_name(manifest.status), manifest.training_eligible as i64,
                object_hash, serialized, Utc::now().to_rfc3339()],
        )?;
        self.invalidate_snapshot_cache();
        Ok(())
    }

    pub fn get_skill(&self, id: &str, version: &str) -> Result<Option<SkillManifest>> {
        let conn = self.lock_conn();
        let value: Option<String> = conn
            .query_row(
                "SELECT manifest_json FROM skills WHERE id=?1 AND version=?2",
                params![id, version],
                |row| row.get(0),
            )
            .optional()?;
        value
            .map(|json| serde_json::from_str(&json).map_err(Into::into))
            .transpose()
    }

    pub fn transition_skill(
        &self,
        id: &str,
        version: &str,
        next: SkillLifecycle,
    ) -> Result<SkillManifest> {
        let mut skill = self
            .get_skill(id, version)?
            .ok_or_else(|| anyhow!("skill not found"))?;
        if !skill.status.can_transition_to(next) {
            bail!(
                "invalid lifecycle transition {:?} -> {:?}",
                skill.status,
                next
            );
        }
        if next == SkillLifecycle::Validated
            && !(skill.source.has_identity_provenance()
                && skill.evidence.schema_passed
                && !skill.evidence.has_blocking_security_finding())
        {
            bail!(
                "skill lacks immutable provenance, a known license, schema validation, or security clearance"
            );
        }
        if next == SkillLifecycle::Experimental && !skill.evidence.qualifies_experimental() {
            bail!("skill lacks experimental evidence thresholds");
        }
        if next == SkillLifecycle::Trusted && !skill.evidence.qualifies_trusted() {
            bail!("skill lacks trusted evidence thresholds");
        }
        skill.status = next;
        skill.recompute_training_eligible();
        let content = self.get_object(&skill.source.content_hash)?;
        self.upsert_skill(&skill, &content)?;
        Ok(skill)
    }

    pub fn search_skills(
        &self,
        query: Option<&str>,
        include_quarantined: bool,
        limit: usize,
    ) -> Result<Vec<SkillManifest>> {
        let conn = self.lock_conn();
        let pattern = format!(
            "%{}%",
            query
                .unwrap_or_default()
                .replace('%', "\\%")
                .replace('_', "\\_")
        );
        let sql = if include_quarantined {
            "SELECT manifest_json FROM skills WHERE (id LIKE ?1 ESCAPE '\\' OR description LIKE ?1 ESCAPE '\\') ORDER BY id, version DESC LIMIT ?2"
        } else {
            "SELECT manifest_json FROM skills WHERE (id LIKE ?1 ESCAPE '\\' OR description LIKE ?1 ESCAPE '\\') AND status IN ('validated','experimental','trusted') ORDER BY id, version DESC LIMIT ?2"
        };
        let mut stmt = conn.prepare(sql)?;
        let rows = stmt.query_map(params![pattern, limit as i64], |row| {
            row.get::<_, String>(0)
        })?;
        rows.map(|row| {
            let json = row?;
            serde_json::from_str(&json).map_err(|error| {
                rusqlite::Error::FromSqlConversionFailure(
                    0,
                    rusqlite::types::Type::Text,
                    Box::new(error),
                )
            })
        })
        .collect::<Result<Vec<_>, _>>()
        .map_err(Into::into)
    }

    pub fn upsert_workflow(&self, workflow: &WorkflowManifest) -> Result<()> {
        validate_workflow(workflow)?;
        let serialized = serde_json::to_string(workflow)?;
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO workflows (id, version, description, manifest_json, updated_at) VALUES (?1,?2,?3,?4,?5)\n             ON CONFLICT(id,version) DO UPDATE SET description=excluded.description, manifest_json=excluded.manifest_json, updated_at=excluded.updated_at",
            params![workflow.id, workflow.version, workflow.description, serialized, Utc::now().to_rfc3339()],
        )?;
        self.invalidate_snapshot_cache();
        Ok(())
    }

    pub fn get_workflow(&self, id: &str, version: &str) -> Result<Option<WorkflowManifest>> {
        let conn = self.lock_conn();
        let value: Option<String> = conn
            .query_row(
                "SELECT manifest_json FROM workflows WHERE id=?1 AND version=?2",
                params![id, version],
                |row| row.get(0),
            )
            .optional()?;
        value
            .map(|json| serde_json::from_str(&json).map_err(Into::into))
            .transpose()
    }

    pub fn list_workflows(&self) -> Result<Vec<WorkflowManifest>> {
        let conn = self.lock_conn();
        let mut stmt =
            conn.prepare("SELECT manifest_json FROM workflows ORDER BY id, version DESC")?;
        let rows = stmt.query_map([], |row| row.get::<_, String>(0))?;
        rows.map(|row| {
            let json = row?;
            serde_json::from_str(&json).map_err(|error| {
                rusqlite::Error::FromSqlConversionFailure(
                    0,
                    rusqlite::types::Type::Text,
                    Box::new(error),
                )
            })
        })
        .collect::<Result<Vec<_>, _>>()
        .map_err(Into::into)
    }

    pub fn registry_snapshot(&self) -> Result<String> {
        if let Some(snapshot) = self
            .snapshot_cache
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .clone()
        {
            return Ok(snapshot);
        }
        let conn = self.lock_conn();
        let mut stmt = conn.prepare(
            "SELECT kind, id, version, content FROM (\n             SELECT 'skill' AS kind,id,version,manifest_json AS content FROM skills\n             UNION ALL SELECT 'workflow',id,version,manifest_json FROM workflows)\n             ORDER BY kind,id,version"
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
            ))
        })?;
        let mut values = Vec::new();
        for row in rows {
            values.push(row?);
        }
        let snapshot = canonical_json_hash(&serde_json::to_value(values)?);
        #[cfg(test)]
        self.snapshot_computations
            .fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        // Refill while still holding the conn lock: concurrent misses
        // serialize here and compute the same value at most once.
        *self
            .snapshot_cache
            .lock()
            .unwrap_or_else(|error| error.into_inner()) = Some(snapshot.clone());
        Ok(snapshot)
    }

    /// Drop the cached snapshot after any skills/workflows mutation.
    pub(crate) fn invalidate_snapshot_cache(&self) {
        *self
            .snapshot_cache
            .lock()
            .unwrap_or_else(|error| error.into_inner()) = None;
    }

    pub fn save_decision(
        &self,
        request: &DecisionRequest,
        response: &DecisionResponse,
    ) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO decisions (id, request_json, response_json, created_at) VALUES (?1,?2,?3,?4)",
            params![response.decision_id.to_string(), serde_json::to_string(request)?, serde_json::to_string(response)?, Utc::now().to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn decision_exists(&self, id: Uuid) -> Result<bool> {
        let conn = self.lock_conn();
        let exists: i64 = conn.query_row(
            "SELECT EXISTS(SELECT 1 FROM decisions WHERE id=?1)",
            params![id.to_string()],
            |row| row.get(0),
        )?;
        Ok(exists != 0)
    }

    pub fn get_decision(&self, id: Uuid) -> Result<Option<DecisionResponse>> {
        let conn = self.lock_conn();
        let value: Option<String> = conn
            .query_row(
                "SELECT response_json FROM decisions WHERE id=?1",
                params![id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        value
            .map(|json| serde_json::from_str(&json).map_err(Into::into))
            .transpose()
    }

    pub fn create_run(&self, request: &CreateRunRequest) -> Result<RunRecord> {
        if !self.decision_exists(request.decision_id)? {
            bail!("decision not found");
        }
        if self
            .get_workflow(&request.workflow_id, &request.workflow_version)?
            .is_none()
        {
            bail!("workflow not found");
        }
        let run = RunRecord {
            id: Uuid::new_v4(),
            decision_id: request.decision_id,
            workflow_id: request.workflow_id.clone(),
            workflow_version: request.workflow_version.clone(),
            repository_path: request.repository_path.clone(),
            capabilities: request.capabilities.clone(),
            status: "running".into(),
            created_at: Utc::now(),
        };
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO runs (id,decision_id,workflow_id,workflow_version,repository_path,capabilities_json,status,created_at) VALUES (?1,?2,?3,?4,?5,?6,?7,?8)",
            params![run.id.to_string(), run.decision_id.to_string(), run.workflow_id, run.workflow_version,
                run.repository_path, serde_json::to_string(&run.capabilities)?, run.status, run.created_at.to_rfc3339()],
        )?;
        Ok(run)
    }

    pub fn get_run(&self, id: Uuid) -> Result<Option<RunRecord>> {
        let conn = self.lock_conn();
        let row: Option<RunRow> = conn.query_row(
            "SELECT decision_id,workflow_id,workflow_version,repository_path,capabilities_json,status,created_at FROM runs WHERE id=?1",
            params![id.to_string()], |row| Ok((row.get(0)?,row.get(1)?,row.get(2)?,row.get(3)?,row.get(4)?,row.get(5)?,row.get(6)?)),
        ).optional()?;
        row.map(
            |(decision, workflow, version, path, caps, status, created)| {
                Ok(RunRecord {
                    id,
                    decision_id: Uuid::parse_str(&decision)?,
                    workflow_id: workflow,
                    workflow_version: version,
                    repository_path: path,
                    capabilities: serde_json::from_str(&caps)?,
                    status,
                    created_at: DateTime::parse_from_rfc3339(&created)?.with_timezone(&Utc),
                })
            },
        )
        .transpose()
    }

    pub fn append_event(&self, run_id: Uuid, event: &AppendEventRequest) -> Result<i64> {
        let run = self
            .get_run(run_id)?
            .ok_or_else(|| anyhow!("run not found"))?;
        if run.status != "running" {
            bail!("run is not active");
        }
        if event.kind.trim().is_empty() {
            bail!("event kind must not be empty");
        }
        let conn = self.lock_conn();
        if matches!(
            event.kind.as_str(),
            "node_started" | "node_completed" | "node_failed"
        ) {
            let workflow_json: String = conn.query_row(
                "SELECT manifest_json FROM workflows WHERE id=?1 AND version=?2",
                params![run.workflow_id, run.workflow_version],
                |row| row.get(0),
            )?;
            let workflow: WorkflowManifest = serde_json::from_str(&workflow_json)?;
            validate_node_event(&conn, run_id, &workflow, event)?;
        }
        conn.execute(
            "INSERT INTO events (run_id,kind,payload_json,created_at) VALUES (?1,?2,?3,?4)",
            params![
                run_id.to_string(),
                event.kind,
                serde_json::to_string(&event.payload)?,
                Utc::now().to_rfc3339()
            ],
        )?;
        Ok(conn.last_insert_rowid())
    }

    pub fn required_nodes_missing(
        &self,
        run_id: Uuid,
        workflow: &WorkflowManifest,
    ) -> Result<Vec<String>> {
        let conn = self.lock_conn();
        let state = load_node_state(&conn, run_id)?;
        Ok(workflow
            .nodes
            .iter()
            .filter(|node| node.required && !state.completed.contains(&node.id))
            .map(|node| node.id.clone())
            .collect())
    }

    /// Trace of one run, paged by event id: `limit` defaults to 1,000 rows
    /// (capped at 10,000); `after_event_id` returns only later events, so
    /// callers page with the last seen `TraceEvent.sequence` as the cursor.
    pub fn get_trace(
        &self,
        run_id: Uuid,
        limit: Option<usize>,
        after_event_id: Option<i64>,
    ) -> Result<Option<RunTrace>> {
        let limit = limit.unwrap_or(1_000).clamp(1, 10_000);
        let run = match self.get_run(run_id)? {
            Some(run) => run,
            None => return Ok(None),
        };
        let conn = self.lock_conn();
        let mut event_statement = conn.prepare(
            "SELECT id,kind,payload_json,created_at FROM events
             WHERE run_id=?1 AND (?2 IS NULL OR id>?2) ORDER BY id LIMIT ?3",
        )?;
        let event_rows = event_statement.query_map(
            params![run_id.to_string(), after_event_id, limit as i64],
            |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                ))
            },
        )?;
        let mut events = Vec::new();
        for row in event_rows {
            let (sequence, kind, payload, created_at) = row?;
            events.push(TraceEvent {
                sequence,
                kind,
                payload: serde_json::from_str(&payload)?,
                created_at: DateTime::parse_from_rfc3339(&created_at)?.with_timezone(&Utc),
            });
        }

        let mut gate_statement = conn.prepare(
            "SELECT gate_id,status,reason,evidence_json,evaluated_at FROM gate_results WHERE run_id=?1 ORDER BY gate_id",
        )?;
        let gate_rows = gate_statement.query_map(params![run_id.to_string()], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, String>(4)?,
            ))
        })?;
        let mut gates = Vec::new();
        for row in gate_rows {
            let (gate_id, status, reason, evidence, evaluated_at) = row?;
            gates.push(GateTrace {
                gate_id,
                status: parse_gate_status(&status)?,
                reason,
                evidence: serde_json::from_str(&evidence)?,
                evaluated_at: DateTime::parse_from_rfc3339(&evaluated_at)?.with_timezone(&Utc),
            });
        }
        let completion: Option<String> = conn
            .query_row(
                "SELECT outcome_json FROM runs WHERE id=?1",
                params![run_id.to_string()],
                |row| row.get(0),
            )
            .optional()?
            .flatten();
        Ok(Some(RunTrace {
            schema_version: SCHEMA_VERSION.into(),
            run,
            events,
            gates,
            completion: completion
                .map(|value| serde_json::from_str(&value))
                .transpose()?,
        }))
    }

    pub fn save_gate_decision(&self, decision: &GateDecision, evidence: &Value) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO gate_results (run_id,gate_id,status,reason,evidence_json,evaluated_at) VALUES (?1,?2,?3,?4,?5,?6)\n             ON CONFLICT(run_id,gate_id) DO UPDATE SET status=excluded.status,reason=excluded.reason,evidence_json=excluded.evidence_json,evaluated_at=excluded.evaluated_at",
            params![decision.run_id.to_string(), decision.gate_id, gate_status_name(decision.status), decision.reason,
                serde_json::to_string(evidence)?, decision.evaluated_at.to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn mandatory_gates_passed(
        &self,
        run: &RunRecord,
        workflow: &WorkflowManifest,
    ) -> Result<Vec<String>> {
        let mandatory: Vec<_> = workflow
            .gates
            .iter()
            .filter(|gate| gate.mandatory)
            .collect();
        let conn = self.lock_conn();
        let mut missing = Vec::new();
        for gate in mandatory {
            let status: Option<String> = conn
                .query_row(
                    "SELECT status FROM gate_results WHERE run_id=?1 AND gate_id=?2",
                    params![run.id.to_string(), gate.id],
                    |row| row.get(0),
                )
                .optional()?;
            if status.as_deref() != Some("pass") {
                missing.push(gate.id.clone());
            }
        }
        Ok(missing)
    }

    pub fn complete_run(&self, run_id: Uuid, request: &CompleteRunRequest) -> Result<()> {
        let conn = self.lock_conn();
        let changed = conn.execute(
            "UPDATE runs SET status=?2,outcome_json=?3,completed_at=?4 WHERE id=?1 AND status='running'",
            params![run_id.to_string(), request.outcome, serde_json::to_string(request)?, Utc::now().to_rfc3339()],
        )?;
        if changed != 1 {
            bail!("run not found or already complete");
        }
        Ok(())
    }

    pub fn save_permit(&self, permit: &ActionPermit) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO permits (id,run_id,action_hash,permit_json,expires_at) VALUES (?1,?2,?3,?4,?5)",
            params![permit.permit_id.to_string(),permit.run_id.to_string(),permit.action_hash,
                serde_json::to_string(permit)?,permit.expires_at.to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn verify_stored_permit(&self, permit: &ActionPermit, consume: bool) -> Result<()> {
        let conn = self.lock_conn();
        let row: Option<(String, Option<String>)> = conn
            .query_row(
                "SELECT action_hash,consumed_at FROM permits WHERE id=?1 AND run_id=?2",
                params![permit.permit_id.to_string(), permit.run_id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        let (hash, consumed) = row.ok_or_else(|| anyhow!("permit is not registered"))?;
        if hash != permit.action_hash {
            bail!("permit action hash mismatch");
        }
        if consumed.is_some() {
            bail!("permit has already been consumed");
        }
        if consume {
            conn.execute(
                "UPDATE permits SET consumed_at=?2 WHERE id=?1 AND consumed_at IS NULL",
                params![permit.permit_id.to_string(), Utc::now().to_rfc3339()],
            )?;
        }
        Ok(())
    }

    pub fn record_paired_eval(&self, eval: &PairedEvalRecord) -> Result<()> {
        validate_paired_eval(eval)?;
        if self
            .get_skill(&eval.skill_id, &eval.skill_version)?
            .is_none()
        {
            bail!("paired evaluation references an unknown Skill version");
        }
        let conn = self.lock_conn();
        conn.execute(
            "INSERT OR REPLACE INTO paired_evals (id,skill_id,skill_version,record_json,created_at) VALUES (?1,?2,?3,?4,?5)",
            params![eval.eval_id.to_string(),eval.skill_id,eval.skill_version,serde_json::to_string(eval)?,Utc::now().to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn import_candidate(&self, candidate: &CandidateExperience, producer: &str) -> Result<()> {
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO candidates (id,producer,kind,content_hash,candidate_json,status,created_at) VALUES (?1,?2,?3,?4,?5,'quarantined',?6)\n             ON CONFLICT(id,content_hash) DO UPDATE SET candidate_json=excluded.candidate_json,producer=excluded.producer",
            params![candidate.candidate_id, producer, candidate.kind, candidate.content_hash,
                serde_json::to_string(candidate)?, Utc::now().to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn candidate_count(&self) -> Result<u64> {
        let conn = self.lock_conn();
        Ok(conn.query_row("SELECT COUNT(*) FROM candidates", [], |row| row.get(0))?)
    }

    pub fn training_counts(&self) -> Result<(u64, u64)> {
        let conn = self.lock_conn();
        let decisions: u64 = conn.query_row(
            "SELECT COUNT(DISTINCT d.id) FROM decisions d JOIN runs r ON r.decision_id=d.id WHERE r.completed_at IS NOT NULL",
            [],
            |row| row.get(0),
        )?;
        let evals: u64 = conn.query_row(
            "SELECT COUNT(*) FROM paired_evals p JOIN skills s ON s.id=p.skill_id AND s.version=p.skill_version WHERE s.training_eligible=1",
            [],
            |row| row.get(0),
        )?;
        Ok((decisions, evals))
    }

    pub fn training_records(&self) -> Result<(Vec<Value>, Vec<Value>)> {
        let conn = self.lock_conn();
        let mut decision_stmt = conn.prepare(
            "SELECT d.request_json,d.response_json,r.outcome_json FROM decisions d JOIN runs r ON r.decision_id=d.id WHERE r.id=(SELECT r2.id FROM runs r2 WHERE r2.decision_id=d.id AND r2.completed_at IS NOT NULL ORDER BY r2.completed_at DESC,r2.id DESC LIMIT 1) ORDER BY d.created_at,d.id",
        )?;
        let decisions = decision_stmt.query_map([], |row| Ok((row.get::<_,String>(0)?,row.get::<_,String>(1)?,row.get::<_,String>(2)?)))?
            .map(|row| -> Result<Value> { let (request,response,outcome)=row?; Ok(serde_json::json!({"kind":"routing","input":serde_json::from_str::<Value>(&request)?,"target":serde_json::from_str::<Value>(&response)?,"outcome":serde_json::from_str::<Value>(&outcome)?})) })
            .collect::<Result<Vec<_>>>()?;
        let mut eval_stmt = conn.prepare(
            "SELECT p.record_json FROM paired_evals p JOIN skills s ON s.id=p.skill_id AND s.version=p.skill_version WHERE s.training_eligible=1 ORDER BY p.created_at,p.id",
        )?;
        let evals = eval_stmt.query_map([], |row| row.get::<_,String>(0))?
            .map(|row| -> Result<Value> { Ok(serde_json::json!({"kind":"paired_eval","record":serde_json::from_str::<Value>(&row?)?})) })
            .collect::<Result<Vec<_>>>()?;
        Ok((decisions, evals))
    }

    pub fn paired_evals_for_skill(
        &self,
        skill_id: &str,
        version: &str,
    ) -> Result<Vec<PairedEvalRecord>> {
        let conn = self.lock_conn();
        let mut stmt = conn.prepare(
            "SELECT record_json FROM paired_evals WHERE skill_id=?1 AND skill_version=?2 ORDER BY created_at,id",
        )?;
        let rows = stmt.query_map(params![skill_id, version], |row| row.get::<_, String>(0))?;
        rows.map(|row| {
            let json = row?;
            serde_json::from_str(&json).map_err(|error| {
                rusqlite::Error::FromSqlConversionFailure(
                    0,
                    rusqlite::types::Type::Text,
                    Box::new(error),
                )
            })
        })
        .collect::<Result<Vec<_>, _>>()
        .map_err(Into::into)
    }

    pub fn get_paired_eval(&self, id: Uuid) -> Result<Option<PairedEvalRecord>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT record_json FROM paired_evals WHERE id=?1",
            params![id.to_string()],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn get_object(&self, hash: &str) -> Result<Vec<u8>> {
        if hash.len() != 64 || !hash.chars().all(|ch| ch.is_ascii_hexdigit()) {
            bail!("invalid object hash");
        }
        let content = fs::read(self.object_dir.join(&hash[..2]).join(hash))
            .with_context(|| format!("read object {hash}"))?;
        let actual = format!("{:x}", Sha256::digest(&content));
        if !actual.eq_ignore_ascii_case(hash) {
            bail!("content-addressed object {hash} failed integrity verification");
        }
        Ok(content)
    }

    pub(crate) fn object_path(&self, hash: &str) -> Result<PathBuf> {
        if hash.len() != 64 || !hash.chars().all(|ch| ch.is_ascii_hexdigit()) {
            bail!("invalid object hash");
        }
        Ok(self.object_dir.join(&hash[..2]).join(hash))
    }

    pub(crate) fn verify_object_hash(&self, hash: &str) -> Result<u64> {
        let path = self.object_path(hash)?;
        let (actual, byte_length) =
            hash_file(&path).with_context(|| format!("verify content-addressed object {hash}"))?;
        if !actual.eq_ignore_ascii_case(hash) {
            bail!("content-addressed object {hash} failed integrity verification");
        }
        Ok(byte_length)
    }

    pub(crate) fn temporary_object_path(&self) -> PathBuf {
        self.object_dir
            .join(format!(".upload.{}.tmp", Uuid::new_v4().simple()))
    }

    pub(crate) fn commit_object_file(&self, temporary: &Path, expected_hash: &str) -> Result<u64> {
        let expected = expected_hash.to_ascii_lowercase();
        if expected.len() != 64 || !expected.chars().all(|ch| ch.is_ascii_hexdigit()) {
            bail!("invalid expected object hash");
        }
        if temporary.parent() != Some(self.object_dir.as_path()) {
            bail!("temporary upload path is outside the object store");
        }
        let (actual, byte_length) = hash_file(temporary)?;
        if actual != expected {
            bail!("uploaded object failed SHA-256 verification");
        }
        let target_dir = self.object_dir.join(&expected[..2]);
        fs::create_dir_all(&target_dir)?;
        let target = target_dir.join(&expected);
        if target.exists() {
            let (existing_hash, existing_length) = hash_file(&target)?;
            if existing_hash != expected || existing_length != byte_length {
                bail!("existing content-addressed object is corrupt");
            }
            fs::remove_file(temporary)?;
            return Ok(byte_length);
        }
        fs::rename(temporary, &target)?;
        Ok(byte_length)
    }
}

fn hash_file(path: &Path) -> Result<(String, u64)> {
    let mut file = fs::File::open(path)?;
    let mut digest = Sha256::new();
    let mut total = 0_u64;
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
        total += read as u64;
    }
    Ok((format!("{:x}", digest.finalize()), total))
}

fn cleanup_interrupted_uploads(object_dir: &Path) -> Result<()> {
    for entry in fs::read_dir(object_dir)? {
        let entry = entry?;
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if entry.file_type()?.is_file() && name.starts_with(".upload.") && name.ends_with(".tmp") {
            fs::remove_file(entry.path())?;
        }
    }
    Ok(())
}

#[derive(Default)]
struct NodeState {
    started: HashSet<String>,
    completed: HashSet<String>,
    failed: HashSet<String>,
}

fn load_node_state(conn: &Connection, run_id: Uuid) -> Result<NodeState> {
    let mut statement = conn.prepare(
        "SELECT kind,payload_json FROM events WHERE run_id=?1 AND kind IN ('node_started','node_completed','node_failed') ORDER BY id",
    )?;
    let rows = statement.query_map(params![run_id.to_string()], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
    })?;
    let mut state = NodeState::default();
    for row in rows {
        let (kind, payload) = row?;
        let payload: Value = serde_json::from_str(&payload)?;
        let node_id = payload
            .get("node_id")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("stored node event lacks node_id"))?
            .to_owned();
        match kind.as_str() {
            "node_started" => {
                state.started.insert(node_id);
            }
            "node_completed" => {
                state.completed.insert(node_id);
            }
            "node_failed" => {
                state.failed.insert(node_id);
            }
            _ => unreachable!("query filters event kinds"),
        }
    }
    Ok(state)
}

fn validate_node_event(
    conn: &Connection,
    run_id: Uuid,
    workflow: &WorkflowManifest,
    event: &AppendEventRequest,
) -> Result<()> {
    let node_id = event
        .payload
        .get("node_id")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| anyhow!("node event requires a non-empty payload.node_id"))?;
    if !workflow.nodes.iter().any(|node| node.id == node_id) {
        bail!("workflow has no node {node_id}");
    }
    let state = load_node_state(conn, run_id)?;
    match event.kind.as_str() {
        "node_started" => {
            if state.started.contains(node_id)
                || state.completed.contains(node_id)
                || state.failed.contains(node_id)
            {
                bail!("node {node_id} has already started or reached a terminal state");
            }
            let missing: Vec<_> = workflow
                .edges
                .iter()
                .filter(|edge| edge.to == node_id)
                .filter_map(|edge| {
                    let satisfied = match edge.condition {
                        None
                        | Some(WorkflowEdgeCondition::Always)
                        | Some(WorkflowEdgeCondition::OnSuccess) => {
                            state.completed.contains(&edge.from)
                        }
                        Some(WorkflowEdgeCondition::OnFailure) => state.failed.contains(&edge.from),
                    };
                    (!satisfied).then_some(edge.from.as_str())
                })
                .collect();
            if !missing.is_empty() {
                bail!(
                    "node {node_id} prerequisites are not satisfied: {}",
                    missing.join(", ")
                );
            }
        }
        "node_completed" | "node_failed" => {
            if !state.started.contains(node_id) {
                bail!("node {node_id} has not started");
            }
            if state.completed.contains(node_id) || state.failed.contains(node_id) {
                bail!("node {node_id} has already reached a terminal state");
            }
        }
        _ => unreachable!("caller filters node event kinds"),
    }
    Ok(())
}

fn lifecycle_name(value: SkillLifecycle) -> &'static str {
    match value {
        SkillLifecycle::Quarantined => "quarantined",
        SkillLifecycle::Validated => "validated",
        SkillLifecycle::Experimental => "experimental",
        SkillLifecycle::Trusted => "trusted",
        SkillLifecycle::Deprecated => "deprecated",
        SkillLifecycle::Revoked => "revoked",
    }
}

fn gate_status_name(value: GateStatus) -> &'static str {
    match value {
        GateStatus::Pass => "pass",
        GateStatus::Deny => "deny",
        GateStatus::NeedsHuman => "needs_human",
    }
}

fn parse_gate_status(value: &str) -> Result<GateStatus> {
    match value {
        "pass" => Ok(GateStatus::Pass),
        "deny" => Ok(GateStatus::Deny),
        "needs_human" => Ok(GateStatus::NeedsHuman),
        other => bail!("invalid stored gate status: {other}"),
    }
}

fn load_or_create_feedback_secret(path: &Path) -> Result<Vec<u8>> {
    if path.exists() {
        let secret = fs::read(path)?;
        if secret.len() < 32 {
            bail!("feedback attestation key is too short");
        }
        return Ok(secret);
    }
    let material = format!("feedback:{}:{}", Uuid::new_v4(), Uuid::new_v4());
    let secret = Sha256::digest(material.as_bytes()).to_vec();
    fs::write(path, &secret)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
    }
    Ok(secret)
}

fn feedback_attestation_payload(feedback: &FeedbackSignal) -> Result<Vec<u8>> {
    let mut value = serde_json::to_value(feedback)?;
    if let Value::Object(map) = &mut value {
        map.insert("attestation".into(), Value::Null);
    }
    Ok(canonical_json_hash(&value).into_bytes())
}

const MIGRATION: &str = r#"
CREATE TABLE IF NOT EXISTS skills (
  id TEXT NOT NULL, version TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL,
  training_eligible INTEGER NOT NULL DEFAULT 0, content_hash TEXT NOT NULL,
  manifest_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(id,version)
);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
CREATE TABLE IF NOT EXISTS workflows (
  id TEXT NOT NULL, version TEXT NOT NULL, description TEXT NOT NULL,
  manifest_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(id,version)
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, request_json TEXT NOT NULL, response_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, decision_id TEXT NOT NULL, workflow_id TEXT NOT NULL, workflow_version TEXT NOT NULL,
  repository_path TEXT, capabilities_json TEXT NOT NULL, status TEXT NOT NULL,
  outcome_json TEXT, created_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, kind TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id,id);
CREATE TABLE IF NOT EXISTS gate_results (
  run_id TEXT NOT NULL, gate_id TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
  evidence_json TEXT NOT NULL, evaluated_at TEXT NOT NULL, PRIMARY KEY(run_id,gate_id)
);
CREATE TABLE IF NOT EXISTS permits (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, action_hash TEXT NOT NULL, permit_json TEXT NOT NULL,
  expires_at TEXT NOT NULL, consumed_at TEXT
);
CREATE TABLE IF NOT EXISTS paired_evals (
  id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, skill_version TEXT NOT NULL,
  record_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
  id TEXT NOT NULL, producer TEXT NOT NULL, kind TEXT NOT NULL, content_hash TEXT NOT NULL,
  candidate_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(id,content_hash)
);
CREATE TABLE IF NOT EXISTS experiences (
  id TEXT PRIMARY KEY, task TEXT NOT NULL, task_family TEXT NOT NULL,
  repository_id TEXT NOT NULL, repository_digest TEXT NOT NULL,
  source_kind TEXT NOT NULL, training_source_eligible INTEGER NOT NULL,
  envelope_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiences_family ON experiences(task_family,created_at);
CREATE INDEX IF NOT EXISTS idx_experiences_repository ON experiences(repository_id,created_at);
CREATE TABLE IF NOT EXISTS feedback_signals (
  id TEXT PRIMARY KEY, experience_id TEXT NOT NULL, kind TEXT NOT NULL,
  signal_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(experience_id) REFERENCES experiences(id)
);
CREATE INDEX IF NOT EXISTS idx_feedback_experience ON feedback_signals(experience_id,created_at,id);
CREATE TABLE IF NOT EXISTS learning_decisions (
  id TEXT PRIMARY KEY, experience_id TEXT NOT NULL, priority REAL NOT NULL,
  training_eligible INTEGER NOT NULL, decision_json TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(experience_id) REFERENCES experiences(id)
);
CREATE INDEX IF NOT EXISTS idx_learning_decisions_experience ON learning_decisions(experience_id,created_at,id);
CREATE TABLE IF NOT EXISTS memory_proposals (
  id TEXT PRIMARY KEY, experience_id TEXT NOT NULL, kind TEXT NOT NULL,
  title TEXT NOT NULL, content TEXT NOT NULL, proposal_json TEXT NOT NULL,
  executable INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
  FOREIGN KEY(experience_id) REFERENCES experiences(id)
);
CREATE INDEX IF NOT EXISTS idx_memory_proposals_search ON memory_proposals(kind,title,created_at);
CREATE TABLE IF NOT EXISTS curricula (
  id TEXT PRIMARY KEY, topic TEXT NOT NULL, query TEXT NOT NULL,
  plan_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_curricula_created ON curricula(created_at);
CREATE TABLE IF NOT EXISTS acquisition_usage (
  day TEXT PRIMARY KEY, search_plans INTEGER NOT NULL DEFAULT 0,
  repositories INTEGER NOT NULL DEFAULT 0, files INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS learning_jobs (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
  priority REAL NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL, lease_owner TEXT, lease_until TEXT, last_error TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_jobs_claim ON learning_jobs(status,priority DESC,created_at);
CREATE TABLE IF NOT EXISTS learning_job_keys (
  kind TEXT NOT NULL, dedup_key TEXT NOT NULL, job_id TEXT NOT NULL,
  PRIMARY KEY(kind,dedup_key), FOREIGN KEY(job_id) REFERENCES learning_jobs(id)
);
CREATE TABLE IF NOT EXISTS learning_job_results (
  job_id TEXT PRIMARY KEY, result_hash TEXT NOT NULL, result_json TEXT NOT NULL,
  created_at TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES learning_jobs(id)
);
CREATE TABLE IF NOT EXISTS learning_job_delays (
  job_id TEXT PRIMARY KEY, next_attempt_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES learning_jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learning_job_delays_due ON learning_job_delays(next_attempt_at);
CREATE TABLE IF NOT EXISTS training_candidates (
  id TEXT PRIMARY KEY, dataset_hash TEXT NOT NULL, manifest_hash TEXT NOT NULL UNIQUE,
  candidate_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_versions (
  model_id TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL,
  model_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(model_id,version)
);
CREATE TABLE IF NOT EXISTS learning_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL,
  action TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS optimization_runs (
  id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
  run_json TEXT NOT NULL, result_hash TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES learning_jobs(id)
);
CREATE INDEX IF NOT EXISTS idx_optimization_runs_status ON optimization_runs(status,created_at);
CREATE TABLE IF NOT EXISTS skill_edit_patches (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
  baseline_hash TEXT NOT NULL, candidate_hash TEXT NOT NULL, patch_json TEXT NOT NULL,
  created_at TEXT NOT NULL, UNIQUE(run_id,sequence),
  FOREIGN KEY(run_id) REFERENCES optimization_runs(id)
);
CREATE TABLE IF NOT EXISTS optimization_evaluations (
  run_id TEXT NOT NULL, candidate_hash TEXT NOT NULL, split TEXT NOT NULL,
  evaluation_json TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(run_id,candidate_hash,split),
  FOREIGN KEY(run_id) REFERENCES optimization_runs(id)
);
CREATE TABLE IF NOT EXISTS topic_watches (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, enabled INTEGER NOT NULL,
  watch_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_topic_watches_enabled ON topic_watches(enabled,updated_at);
CREATE TABLE IF NOT EXISTS topic_acquisition_usage (
  day TEXT NOT NULL, topic_id TEXT NOT NULL,
  events INTEGER NOT NULL DEFAULT 0, documents INTEGER NOT NULL DEFAULT 0,
  browser_escalations INTEGER NOT NULL DEFAULT 0, model_tokens INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(day,topic_id),
  FOREIGN KEY(topic_id) REFERENCES topic_watches(id)
);
CREATE TABLE IF NOT EXISTS source_policies (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, enabled INTEGER NOT NULL,
  policy_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_policies_enabled ON source_policies(enabled,kind);
CREATE TABLE IF NOT EXISTS source_cursors (
  policy_id TEXT PRIMARY KEY, cursor TEXT, etag TEXT, last_modified TEXT,
  next_poll_at TEXT, updated_at TEXT NOT NULL,
  FOREIGN KEY(policy_id) REFERENCES source_policies(id)
);
CREATE TABLE IF NOT EXISTS acquisition_plans (
  id TEXT PRIMARY KEY, topic_id TEXT NOT NULL, status TEXT NOT NULL,
  plan_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(topic_id) REFERENCES topic_watches(id)
);
CREATE INDEX IF NOT EXISTS idx_acquisition_plans_status ON acquisition_plans(status,created_at);
CREATE TABLE IF NOT EXISTS acquisition_attempts (
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, source_policy_id TEXT NOT NULL,
  canonical_url TEXT NOT NULL, method TEXT NOT NULL, outcome TEXT NOT NULL,
  attempt_json TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(plan_id) REFERENCES acquisition_plans(id),
  FOREIGN KEY(source_policy_id) REFERENCES source_policies(id)
);
CREATE INDEX IF NOT EXISTS idx_acquisition_attempts_plan ON acquisition_attempts(plan_id,created_at);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, source_policy_id TEXT NOT NULL, canonical_url TEXT NOT NULL,
  cleaned_content_hash TEXT NOT NULL, raw_content_hash TEXT, raw_expires_at TEXT NOT NULL,
  training_eligible INTEGER NOT NULL DEFAULT 0, tombstoned INTEGER NOT NULL DEFAULT 0,
  document_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(canonical_url,cleaned_content_hash),
  FOREIGN KEY(source_policy_id) REFERENCES source_policies(id)
);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(canonical_url,created_at);
CREATE INDEX IF NOT EXISTS idx_documents_expiry ON documents(raw_expires_at,tombstoned);
CREATE TABLE IF NOT EXISTS document_tombstones (
  document_id TEXT PRIMARY KEY, raw_content_hash TEXT, reason TEXT NOT NULL,
  tombstoned_at TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS knowledge_cards (
  card_id TEXT NOT NULL, revision INTEGER NOT NULL, status TEXT NOT NULL,
  title TEXT NOT NULL, summary TEXT NOT NULL, observed_at TEXT NOT NULL,
  valid_until TEXT, training_eligible INTEGER NOT NULL DEFAULT 0,
  card_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(card_id,revision)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_cards_latest ON knowledge_cards(card_id,revision DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_cards_status ON knowledge_cards(status,observed_at DESC);
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
  card_key UNINDEXED, title, summary, entities, claims, tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS knowledge_embeddings (
  card_id TEXT NOT NULL, revision INTEGER NOT NULL, model TEXT NOT NULL,
  dimensions INTEGER NOT NULL, vector BLOB NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(card_id,revision),
  FOREIGN KEY(card_id,revision) REFERENCES knowledge_cards(card_id,revision)
);
CREATE TABLE IF NOT EXISTS acquisition_worker_results (
  job_id TEXT PRIMARY KEY, worker TEXT NOT NULL, result_json TEXT NOT NULL,
  result_hash TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES learning_jobs(id)
);
CREATE TABLE IF NOT EXISTS acquisition_browser_reservations (
  job_id TEXT PRIMARY KEY, worker TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES learning_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS source_rate_usage (
  minute TEXT NOT NULL, source_policy_id TEXT NOT NULL, requests INTEGER NOT NULL,
  PRIMARY KEY(minute,source_policy_id),
  FOREIGN KEY(source_policy_id) REFERENCES source_policies(id)
);
CREATE TABLE IF NOT EXISTS acquisition_rate_reservations (
  job_id TEXT NOT NULL, ordinal INTEGER NOT NULL, source_policy_id TEXT NOT NULL,
  worker TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(job_id,ordinal),
  FOREIGN KEY(job_id) REFERENCES learning_jobs(id) ON DELETE CASCADE,
  FOREIGN KEY(source_policy_id) REFERENCES source_policies(id)
);
CREATE TABLE IF NOT EXISTS meta_training_candidates (
  id TEXT PRIMARY KEY, manifest_hash TEXT NOT NULL UNIQUE, candidate_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta_decision_traces (
  id TEXT PRIMARY KEY, task_kind TEXT NOT NULL, input_hash TEXT NOT NULL,
  source_domain TEXT NOT NULL, topic_family TEXT NOT NULL,
  training_eligible INTEGER NOT NULL DEFAULT 0, trace_json TEXT NOT NULL,
  content_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meta_decisions_training
  ON meta_decision_traces(training_eligible,task_kind,source_domain,topic_family,created_at);
CREATE INDEX IF NOT EXISTS idx_meta_decisions_dedup
  ON meta_decision_traces(task_kind,input_hash,created_at);
CREATE TABLE IF NOT EXISTS meta_replay_evaluations (
  id TEXT PRIMARY KEY, candidate_id TEXT, source_domain TEXT NOT NULL,
  topic_family TEXT NOT NULL, safety_passed INTEGER NOT NULL,
  evaluation_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES meta_training_candidates(id)
);
CREATE INDEX IF NOT EXISTS idx_meta_replay_candidate
  ON meta_replay_evaluations(candidate_id,safety_passed,source_domain,topic_family);
CREATE TABLE IF NOT EXISTS meta_canary_decisions (
  id TEXT PRIMARY KEY, model_id TEXT NOT NULL, version TEXT NOT NULL,
  assigned_to_canary INTEGER NOT NULL, policy_violation INTEGER NOT NULL,
  decision_json TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(model_id,version) REFERENCES meta_model_bundles(model_id,version)
);
CREATE TABLE IF NOT EXISTS meta_model_bundles (
  model_id TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL,
  bundle_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(model_id,version)
);
CREATE TABLE IF NOT EXISTS meta_training_job_results (
  job_id TEXT PRIMARY KEY, worker TEXT NOT NULL, model_id TEXT NOT NULL,
  version TEXT NOT NULL, artifact_hash TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES learning_jobs(id),
  FOREIGN KEY(model_id,version) REFERENCES meta_model_bundles(model_id,version)
);
CREATE TABLE IF NOT EXISTS dataset_builds (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_watermark TEXT,
  parent_build_id TEXT, bundle_hash TEXT NOT NULL, manifest_hash TEXT NOT NULL,
  dedup_key TEXT NOT NULL, build_json TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(kind,dedup_key)
);
CREATE INDEX IF NOT EXISTS idx_dataset_builds_kind_created
  ON dataset_builds(kind,created_at DESC,id);
CREATE TABLE IF NOT EXISTS dataset_drafts (
  kind TEXT PRIMARY KEY, build_id TEXT NOT NULL, manifest_hash TEXT NOT NULL,
  draft_json TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(build_id) REFERENCES dataset_builds(id)
);
CREATE TABLE IF NOT EXISTS dataset_snapshots (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, build_id TEXT NOT NULL,
  bundle_hash TEXT NOT NULL, manifest_hash TEXT NOT NULL,
  snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dataset_snapshots_kind_created
  ON dataset_snapshots(kind,created_at DESC,id);
CREATE TABLE IF NOT EXISTS dataset_snapshot_revocations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, snapshot_id TEXT NOT NULL,
  actor TEXT NOT NULL, reason TEXT NOT NULL, revocation_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(snapshot_id) REFERENCES dataset_snapshots(id)
);
CREATE INDEX IF NOT EXISTS idx_dataset_snapshot_revocations
  ON dataset_snapshot_revocations(snapshot_id,created_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS expert_dataset_views (
  id TEXT PRIMARY KEY, build_id TEXT NOT NULL UNIQUE, taxonomy_hash TEXT NOT NULL,
  manifest_hash TEXT NOT NULL, bundle_hash TEXT NOT NULL, view_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(build_id) REFERENCES dataset_builds(id)
);
CREATE INDEX IF NOT EXISTS idx_expert_dataset_views_created
  ON expert_dataset_views(created_at DESC,id);
CREATE TABLE IF NOT EXISTS expert_assignments (
  view_id TEXT NOT NULL, record_hash TEXT NOT NULL, split TEXT NOT NULL,
  primary_expert_id TEXT NOT NULL, status TEXT NOT NULL, assignment_json TEXT NOT NULL,
  PRIMARY KEY(view_id,record_hash),
  FOREIGN KEY(view_id) REFERENCES expert_dataset_views(id)
);
CREATE INDEX IF NOT EXISTS idx_expert_assignments_route
  ON expert_assignments(view_id,primary_expert_id,split,status,record_hash);
CREATE TABLE IF NOT EXISTS expert_adapter_versions (
  adapter_id TEXT PRIMARY KEY, expert_id TEXT NOT NULL, version TEXT NOT NULL,
  status TEXT NOT NULL, training_run_id TEXT NOT NULL, bundle_hash TEXT NOT NULL,
  artifact_hash TEXT NOT NULL, adapter_json TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(expert_id,version),
  FOREIGN KEY(training_run_id) REFERENCES training_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_expert_adapters_status
  ON expert_adapter_versions(expert_id,status,updated_at DESC,adapter_id);
CREATE TABLE IF NOT EXISTS training_runs (
  id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, status TEXT NOT NULL,
  run_json TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, updated_at TEXT NOT NULL,
  FOREIGN KEY(snapshot_id) REFERENCES dataset_snapshots(id)
);
CREATE INDEX IF NOT EXISTS idx_training_runs_status
  ON training_runs(status,updated_at,id);
CREATE TABLE IF NOT EXISTS training_run_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, kind TEXT NOT NULL,
  payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES training_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_training_run_events
  ON training_run_events(run_id,id);
CREATE TABLE IF NOT EXISTS gpu_leases (
  run_id TEXT PRIMARY KEY, provider_instance_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL, lease_json TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES training_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_gpu_leases_status ON gpu_leases(status,updated_at);
CREATE TABLE IF NOT EXISTS training_worker_bootstraps (
  run_id TEXT PRIMARY KEY, code_hash TEXT NOT NULL UNIQUE,
  provider_instance_id TEXT, expires_at TEXT NOT NULL, exchanged_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES training_runs(id)
);
CREATE TABLE IF NOT EXISTS training_worker_sessions (
  token_hash TEXT PRIMARY KEY, run_id TEXT NOT NULL,
  provider_instance_id TEXT NOT NULL, expires_at TEXT NOT NULL,
  replaced_at TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES training_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_training_worker_sessions_run
  ON training_worker_sessions(run_id,expires_at);
CREATE TABLE IF NOT EXISTS training_artifacts (
  run_id TEXT NOT NULL, kind TEXT NOT NULL, object_hash TEXT NOT NULL,
  byte_length INTEGER NOT NULL, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(run_id,kind),
  FOREIGN KEY(run_id) REFERENCES training_runs(id)
);
CREATE TABLE IF NOT EXISTS redaction_attestations (
  id TEXT PRIMARY KEY, subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL,
  subject_hash TEXT NOT NULL, exported_payload_hash TEXT NOT NULL,
  attestation_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(subject_kind,subject_id,subject_hash,exported_payload_hash)
);
CREATE TABLE IF NOT EXISTS quality_assessments (
  id TEXT PRIMARY KEY, subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL,
  subject_hash TEXT NOT NULL, stage TEXT NOT NULL, model_id TEXT NOT NULL,
  system_fingerprint TEXT NOT NULL, prompt_version TEXT NOT NULL,
  verdict TEXT NOT NULL, assessment_json TEXT NOT NULL, content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(subject_kind,subject_id,subject_hash,stage,model_id,system_fingerprint,prompt_version)
);
CREATE INDEX IF NOT EXISTS idx_quality_assessments_subject
  ON quality_assessments(subject_kind,subject_id,created_at DESC,id);
CREATE INDEX IF NOT EXISTS idx_quality_assessments_verdict
  ON quality_assessments(verdict,stage,created_at DESC,id);
CREATE TABLE IF NOT EXISTS quality_model_versions (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, model_id TEXT NOT NULL,
  system_fingerprint TEXT NOT NULL, prompt_version TEXT NOT NULL,
  status TEXT NOT NULL, version_json TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(provider,model_id,system_fingerprint,prompt_version)
);
CREATE INDEX IF NOT EXISTS idx_quality_model_versions_status
  ON quality_model_versions(provider,model_id,status,updated_at DESC,id);
CREATE TABLE IF NOT EXISTS quality_shadow_observations (
  endpoint_version_id TEXT NOT NULL, assessment_id TEXT NOT NULL,
  disagreed INTEGER NOT NULL, severe_safety_regression INTEGER NOT NULL,
  created_at TEXT NOT NULL, PRIMARY KEY(endpoint_version_id,assessment_id),
  FOREIGN KEY(endpoint_version_id) REFERENCES quality_model_versions(id),
  FOREIGN KEY(assessment_id) REFERENCES quality_assessments(id)
);
CREATE TABLE IF NOT EXISTS quality_calibration_observations (
  endpoint_version_id TEXT NOT NULL, fixture_id INTEGER NOT NULL,
  expected_verdict TEXT NOT NULL, predicted_verdict TEXT,
  schema_valid INTEGER NOT NULL, critical_safety INTEGER NOT NULL,
  critical_detected INTEGER NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(endpoint_version_id,fixture_id),
  FOREIGN KEY(endpoint_version_id) REFERENCES quality_model_versions(id)
);
CREATE TABLE IF NOT EXISTS provider_pricing_policies (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, policy_json TEXT NOT NULL,
  confirmed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quality_runtime_config (
  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_usage_ledger (
  provider TEXT NOT NULL, shanghai_day TEXT NOT NULL,
  flash_calls INTEGER NOT NULL DEFAULT 0, pro_calls INTEGER NOT NULL DEFAULT 0,
  prompt_tokens INTEGER NOT NULL DEFAULT 0, cache_hit_tokens INTEGER NOT NULL DEFAULT 0,
  cache_miss_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
  reasoning_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0,
  reserved_microusd INTEGER NOT NULL DEFAULT 0, spent_microusd INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL, PRIMARY KEY(provider,shanghai_day)
);
CREATE TABLE IF NOT EXISTS model_usage_reservations (
  request_id TEXT PRIMARY KEY, provider TEXT NOT NULL, shanghai_day TEXT NOT NULL,
  stage TEXT NOT NULL, reserved_microusd INTEGER NOT NULL, spent_microusd INTEGER,
  created_at TEXT NOT NULL, settled_at TEXT,
  FOREIGN KEY(provider,shanghai_day) REFERENCES model_usage_ledger(provider,shanghai_day)
);
CREATE TABLE IF NOT EXISTS synthetic_training_candidates (
  id TEXT PRIMARY KEY, parent_subject_kind TEXT NOT NULL, parent_subject_id TEXT NOT NULL,
  parent_hash TEXT NOT NULL, task_kind TEXT NOT NULL, transformation TEXT NOT NULL,
  status TEXT NOT NULL, candidate_json TEXT NOT NULL, content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(parent_hash,transformation,content_hash)
);
CREATE INDEX IF NOT EXISTS idx_synthetic_candidates_status
  ON synthetic_training_candidates(status,task_kind,created_at DESC,id);
CREATE TABLE IF NOT EXISTS dataset_quality_reports (
  id TEXT PRIMARY KEY, build_id TEXT NOT NULL UNIQUE, report_hash TEXT NOT NULL UNIQUE,
  gate_passed INTEGER NOT NULL, report_json TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(build_id) REFERENCES dataset_builds(id)
);
CREATE INDEX IF NOT EXISTS idx_dataset_quality_reports_gate
  ON dataset_quality_reports(gate_passed,created_at DESC,id);
CREATE TABLE IF NOT EXISTS tracked_events (
  event_id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
  first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
  peak_heat INTEGER NOT NULL, platforms TEXT NOT NULL,
  item_count INTEGER NOT NULL, card_id TEXT,
  event_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tracked_events_last_seen ON tracked_events(last_seen_at);
CREATE TABLE IF NOT EXISTS event_items (
  platform TEXT NOT NULL, external_id TEXT NOT NULL,
  event_id TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,

  author TEXT, published_at TEXT, summary TEXT,
  heat INTEGER NOT NULL, rank INTEGER NOT NULL, observations TEXT NOT NULL,
  document_id TEXT NOT NULL,
  first_observed_at TEXT NOT NULL, last_observed_at TEXT NOT NULL,
  PRIMARY KEY(platform, external_id),
  FOREIGN KEY(event_id) REFERENCES tracked_events(event_id)
);
CREATE INDEX IF NOT EXISTS idx_event_items_event ON event_items(event_id,last_observed_at);
CREATE TABLE IF NOT EXISTS expert_canary_decisions (
  id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL, decision_id TEXT NOT NULL,
  selected_expert TEXT NOT NULL, dense_fallback INTEGER NOT NULL,
  unsafe_input INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expert_canary_adapter ON expert_canary_decisions(adapter_id,created_at);
CREATE TABLE IF NOT EXISTS expert_adapter_eval_reports (
  id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL, expert_id TEXT NOT NULL,
  version TEXT NOT NULL, results_hash TEXT NOT NULL, report_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(adapter_id) REFERENCES expert_adapter_versions(adapter_id)
);
CREATE INDEX IF NOT EXISTS idx_eval_reports_adapter
  ON expert_adapter_eval_reports(expert_id,version,created_at DESC,id);
"#;

#[cfg(test)]
mod tests {
    #[test]
    fn snapshot_is_cached_until_skill_or_workflow_changes() {
        use std::sync::atomic::Ordering;

        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        builtins::seed(&registry).unwrap();
        let first = registry.registry_snapshot().unwrap();
        let second = registry.registry_snapshot().unwrap();
        assert_eq!(first, second);
        assert_eq!(registry.snapshot_computations.load(Ordering::SeqCst), 1);

        // Re-seeding upserts skills/workflows and drops the cache.
        builtins::seed(&registry).unwrap();
        let third = registry.registry_snapshot().unwrap();
        assert_eq!(third, first);
        assert_eq!(registry.snapshot_computations.load(Ordering::SeqCst), 2);
    }
    use super::*;
    use crate::builtins;
    use tempfile::tempdir;

    #[test]
    fn registry_round_trip_and_snapshot_are_stable() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        builtins::seed(&registry).unwrap();
        let first = registry.registry_snapshot().unwrap();
        builtins::seed(&registry).unwrap();
        let second = registry.registry_snapshot().unwrap();
        assert_eq!(first, second);
        assert_eq!(registry.list_workflows().unwrap().len(), 4);
    }

    #[test]
    fn content_store_rejects_tampered_objects() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let hash = registry.put_object(b"original").unwrap();
        let path = dir.path().join("objects").join(&hash[..2]).join(&hash);
        fs::write(path, b"tampered").unwrap();
        assert!(registry.get_object(&hash).is_err());
    }

    #[test]
    fn workflow_state_rejects_out_of_order_nodes_and_replays_from_events() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        builtins::seed(&registry).unwrap();
        let decision_id = Uuid::new_v4();
        registry
            .save_decision(
                &DecisionRequest {
                    task: "fix bug".into(),
                    repository_path: None,
                    capabilities: vec![],
                    context: Value::Null,
                },
                &DecisionResponse {
                    decision_id,
                    selected: cerebellum_core::RankedWorkflow {
                        workflow_id: "bugfix".into(),
                        version: "1.0.0".into(),
                        score: 1.0,
                        reasons: vec![],
                    },
                    alternatives: vec![],
                    router: "test".into(),
                    fallback_used: false,
                    registry_snapshot: "test".into(),
                    memory_context: vec![],
                    knowledge_context: vec![],
                    environment: None,
                    acquisition_requested: false,
                },
            )
            .unwrap();
        let run = registry
            .create_run(&CreateRunRequest {
                decision_id,
                workflow_id: "bugfix".into(),
                workflow_version: "1.0.0".into(),
                repository_path: None,
                capabilities: vec![],
            })
            .unwrap();
        let node_event = |kind: &str, node_id: &str| AppendEventRequest {
            kind: kind.into(),
            payload: serde_json::json!({"node_id":node_id}),
        };

        assert!(
            registry
                .append_event(run.id, &node_event("node_started", "plan"))
                .is_err()
        );
        registry
            .append_event(run.id, &node_event("node_started", "inspect"))
            .unwrap();
        registry
            .append_event(run.id, &node_event("node_completed", "inspect"))
            .unwrap();
        registry
            .append_event(run.id, &node_event("node_started", "plan"))
            .unwrap();

        let workflow = registry.get_workflow("bugfix", "1.0.0").unwrap().unwrap();
        let missing = registry.required_nodes_missing(run.id, &workflow).unwrap();
        assert!(!missing.contains(&"inspect".to_string()));
        assert!(missing.contains(&"plan".to_string()));
        let trace = registry.get_trace(run.id, None, None).unwrap().unwrap();
        assert_eq!(trace.schema_version, SCHEMA_VERSION);
        assert_eq!(trace.events.len(), 3);
        assert_eq!(trace.events[0].kind, "node_started");
        // Pagination: limit and the event-id cursor both apply.
        let page = registry.get_trace(run.id, Some(2), None).unwrap().unwrap();
        assert_eq!(page.events.len(), 2);
        let cursor = page.events.last().unwrap().sequence;
        let rest = registry
            .get_trace(run.id, None, Some(cursor))
            .unwrap()
            .unwrap();
        assert_eq!(rest.events.len(), 1);
        assert_eq!(rest.events[0].kind, "node_started");
    }

    #[test]
    fn wal_uses_synchronous_normal() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let mode: i64 = registry
            .lock_conn()
            .query_row("PRAGMA synchronous", [], |row| row.get(0))
            .unwrap();
        assert_eq!(
            mode, 1,
            "synchronous=NORMAL (1) is the WAL-standard pairing"
        );
    }

    fn paired_eval_record() -> PairedEvalRecord {
        PairedEvalRecord {
            eval_id: Uuid::new_v4(),
            skill_id: "builtin.inspect-repository".into(),
            skill_version: "1.0.0".into(),
            task_family: "bugfix/parser".into(),
            repository_digest: "a".repeat(64),
            environment_digest: "b".repeat(64),
            model_id: "router-baseline".into(),
            seed: 42,
            budget: Value::Null,
            baseline_success: false,
            treatment_success: true,
            baseline_gate_violations: 0,
            treatment_gate_violations: 0,
            baseline_score: 0.2,
            treatment_score: 0.9,
            baseline_latency_ms: 1_200,
            treatment_latency_ms: 1_350,
            metadata: Value::Null,
        }
    }

    #[test]
    fn record_paired_eval_validates_before_persisting() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        builtins::seed(&registry).unwrap();
        registry.record_paired_eval(&paired_eval_record()).unwrap();
        assert_eq!(
            registry
                .paired_evals_for_skill("builtin.inspect-repository", "1.0.0")
                .unwrap()
                .len(),
            1
        );

        let mut invalid = paired_eval_record();
        invalid.treatment_score = f64::NAN;
        assert!(registry.record_paired_eval(&invalid).is_err());
        let mut invalid = paired_eval_record();
        invalid.repository_digest = "sha256:replace-me".into();
        assert!(registry.record_paired_eval(&invalid).is_err());
        let mut invalid = paired_eval_record();
        invalid.task_family = String::new();
        assert!(registry.record_paired_eval(&invalid).is_err());
        assert_eq!(
            registry
                .paired_evals_for_skill("builtin.inspect-repository", "1.0.0")
                .unwrap()
                .len(),
            1
        );
    }

    #[test]
    fn lock_conn_recovers_from_poisoning() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();

        let panicked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _guard = registry.lock_conn();
            panic!("simulated panic inside the critical section");
        }));
        assert!(panicked.is_err());
        assert!(registry.conn.is_poisoned());

        // A poisoned mutex must not take every DB endpoint down: subsequent
        // reads and writes through lock_conn (all registry methods) succeed.
        {
            let conn = registry.lock_conn();
            conn.execute("CREATE TABLE IF NOT EXISTS poison_probe(id INTEGER)", [])
                .unwrap();
            conn.execute("INSERT INTO poison_probe(id) VALUES (1)", [])
                .unwrap();
        }
        assert!(registry.registry_snapshot().is_ok());
        assert!(!registry.decision_exists(Uuid::new_v4()).unwrap());
    }
}
