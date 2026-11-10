use crate::Registry;
use crate::experts::prepare_expert_dataset;
use anyhow::{Context, Result, anyhow, bail};
use cerebellum_core::{
    CreateDatasetSnapshotRequest, DatasetBuild, DatasetDraft, DatasetEligibilityReport,
    DatasetShard, DatasetSnapshot, DatasetSnapshotRecord, DatasetSnapshotRevocation, DatasetSplit,
    DatasetSplitStats, ExpertAssignment, ExpertDatasetPurpose, ExpertDatasetShard,
    ExpertDatasetView, KnowledgeCard, MetaDecisionTrace, MetaReplayEvaluation,
    MetaTrainingCandidate, QualitySubjectKind, RevokeDatasetSnapshotRequest, SCHEMA_VERSION,
    SyntheticCandidateStatus, SyntheticTrainingCandidate, canonical_json_hash,
    validate_dataset_build, validate_dataset_snapshot, validate_expert_dataset_view,
};
use chrono::{DateTime, Datelike, Utc};
use rusqlite::{OptionalExtension, params};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::io::Cursor;
use uuid::Uuid;

pub const META_DATASET_KIND: &str = "meta-controller";
pub const KNOWLEDGE_WEB_DATASET_KIND: &str = "knowledge-web";
pub const DATASET_POLICY_VERSION: &str = "licensed-safe-meta-moe-v2";
pub const KNOWLEDGE_WEB_POLICY_VERSION: &str = "licensed-safe-knowledge-web-v1";
pub const RETAIN_DAILY_BUILDS: usize = 30;
pub const RETAIN_WEEKLY_BUILDS: usize = 12;

#[derive(Debug)]
struct DatasetInputs {
    traces: Vec<MetaDecisionTrace>,
    replays: Vec<MetaReplayEvaluation>,
    synthetic: Vec<SyntheticDatasetRecord>,
    rejected_license: u64,
    rejected_safety: u64,
    watermark: Option<DateTime<Utc>>,
}

#[derive(Debug)]
struct SyntheticDatasetRecord {
    candidate: SyntheticTrainingCandidate,
    source_domain: String,
    topic_family: String,
}

impl Registry {
    /// Build a complete deterministic draft from the current eligible ledger.
    ///
    /// A draft deliberately has no minimum-size gate. The 5,000/1,000 gate is
    /// evaluated only when an administrator starts a TrainingRun.
    pub fn build_dataset_draft(&self, kind: &str, now: DateTime<Utc>) -> Result<DatasetBuild> {
        ensure_dataset_kind(kind)?;
        if kind == KNOWLEDGE_WEB_DATASET_KIND {
            return self.build_knowledge_web_draft(kind, now);
        }
        let quality_enforced = self.quality_model_configured()?;
        let parent = self.get_dataset_draft(kind)?;
        let inputs = self.dataset_inputs()?;
        let split_assignments = split_assignments(&inputs);
        let mut grouped: BTreeMap<(DatasetSplit, String), Vec<Value>> = BTreeMap::new();
        let mut routable_records = Vec::<(DatasetSplit, Value)>::new();
        let mut stats = DatasetSplitStats::default();

        for trace in &inputs.traces {
            let split =
                split_assignments[&(trace.source_domain.clone(), trace.topic_family.clone())];
            increment_split(&mut stats, split);
            let envelope = json!({
                "kind":"meta_decision",
                "split":split,
                "record":trace
            });
            grouped
                .entry((split, "meta_decision".into()))
                .or_default()
                .push(envelope.clone());
            routable_records.push((split, envelope));
        }
        for replay in &inputs.replays {
            let split =
                split_assignments[&(replay.source_domain.clone(), replay.topic_family.clone())];
            increment_split(&mut stats, split);
            let envelope = json!({
                "kind":"meta_replay",
                "split":split,
                "record":replay
            });
            grouped
                .entry((split, "meta_replay".into()))
                .or_default()
                .push(envelope.clone());
            routable_records.push((split, envelope));
        }
        for generated in &inputs.synthetic {
            let split = split_assignments[&(
                generated.source_domain.clone(),
                generated.topic_family.clone(),
            )];
            increment_split(&mut stats, split);
            let envelope = json!({
                "kind":"synthetic_candidate",
                "split":split,
                "record":generated.candidate
            });
            grouped
                .entry((split, "synthetic_candidate".into()))
                .or_default()
                .push(envelope.clone());
            routable_records.push((split, envelope));
        }

        let mut shards = Vec::new();
        let mut archive_entries = Vec::new();
        for ((split, record_kind), records) in grouped {
            let mut jsonl = Vec::new();
            for record in records {
                serde_json::to_writer(&mut jsonl, &record)?;
                jsonl.push(b'\n');
            }
            let uncompressed_hash = sha256(&jsonl);
            let compressed = zstd::stream::encode_all(Cursor::new(&jsonl), 9)?;
            let object_hash = self.put_object(&compressed)?;
            let name = format!("{}.{}.jsonl.zst", split_name(split), record_kind);
            archive_entries.push((name, compressed));
            shards.push(DatasetShard {
                split,
                record_kind,
                object_hash,
                uncompressed_hash,
                record_count: jsonl.iter().filter(|byte| **byte == b'\n').count() as u64,
                compressed_bytes: archive_entries.last().expect("entry exists").1.len() as u64,
            });
        }

        let prepared_experts = prepare_expert_dataset(&routable_records)?;
        let mut expert_shards = Vec::new();
        for ((split, purpose, expert_id, record_kind), records) in &prepared_experts.groups {
            let jsonl = encode_jsonl(records)?;
            let uncompressed_hash = sha256(&jsonl);
            let compressed = zstd::stream::encode_all(Cursor::new(&jsonl), 9)?;
            let object_hash = self.put_object(&compressed)?;
            let name = expert_shard_name(*split, *purpose, expert_id.as_deref(), record_kind);
            archive_entries.push((name, compressed.clone()));
            expert_shards.push(ExpertDatasetShard {
                split: *split,
                purpose: *purpose,
                expert_id: expert_id.clone(),
                record_kind: record_kind.clone(),
                object_hash,
                uncompressed_hash,
                record_count: records.len() as u64,
                compressed_bytes: compressed.len() as u64,
            });
        }
        let assignments_bytes = encode_jsonl(
            &prepared_experts
                .assignments
                .iter()
                .map(serde_json::to_value)
                .collect::<serde_json::Result<Vec<_>>>()?,
        )?;
        let assignments_hash = self.put_object(&assignments_bytes)?;
        archive_entries.push(("expert-assignments.jsonl".into(), assignments_bytes));
        let expert_manifest = json!({
            "schema_version":SCHEMA_VERSION,
            "kind":"expert_dataset_manifest_v1",
            "policy_version":prepared_experts.taxonomy.policy_version,
            "taxonomy":prepared_experts.taxonomy,
            "taxonomy_hash":prepared_experts.taxonomy_hash,
            "assignments_hash":assignments_hash,
            "assignment_count":prepared_experts.assignments.len(),
            "ambiguous_count":prepared_experts.ambiguous_count,
            "out_of_distribution_count":prepared_experts.out_of_distribution_count,
            "negative_transfer_count":prepared_experts.negative_transfer_count,
            "readiness":prepared_experts.readiness,
            "shards":expert_shards,
            "contains_raw_documents":false
        });
        let expert_manifest_bytes = serde_json::to_vec(&expert_manifest)?;
        let expert_manifest_hash = self.put_object(&expert_manifest_bytes)?;
        archive_entries.push(("expert-dataset-manifest.json".into(), expert_manifest_bytes));

        let synthetic_count = inputs.synthetic.len() as u64;
        let decision_count = inputs.traces.len() as u64 + synthetic_count;
        let replay_eval_count = inputs.replays.len() as u64;
        let eligibility = DatasetEligibilityReport {
            passed: true,
            policy_version: DATASET_POLICY_VERSION.into(),
            contains_raw_documents: false,
            eligible_records: decision_count + replay_eval_count,
            rejected_license_records: inputs.rejected_license,
            rejected_safety_records: inputs.rejected_safety,
            reasons: Vec::new(),
        };
        let manifest = json!({
            "schema_version":SCHEMA_VERSION,
            "kind":"dataset_bundle_manifest_v1",
            "dataset_kind":kind,
            "source_watermark":inputs.watermark,
            "policy_version":DATASET_POLICY_VERSION,
            "shards":shards,
            "decision_count":decision_count,
            "replay_eval_count":replay_eval_count,
            "synthetic_record_count":synthetic_count,
            "synthetic_ratio":if decision_count + replay_eval_count == 0 {0.0} else {
                synthetic_count as f64 / (decision_count + replay_eval_count) as f64
            },
            "split_stats":stats,
            "split_policy":"source_domain_topic_family_earliest_month_v1",
            "eligibility":eligibility,
            "expert_dataset":{
                "manifest_hash":expert_manifest_hash,
                "taxonomy_hash":prepared_experts.taxonomy_hash,
                "assignment_count":prepared_experts.assignments.len(),
                "ready":prepared_experts.readiness.ready
            },
            "contains_raw_documents":false
        });
        let manifest_bytes = serde_json::to_vec(&manifest)?;
        let manifest_hash = self.put_object(&manifest_bytes)?;
        archive_entries.push(("dataset-manifest.json".into(), manifest_bytes));
        archive_entries.sort_by(|left, right| left.0.cmp(&right.0));
        let bundle = deterministic_tar(&archive_entries)?;
        let bundle_hash = self.put_object(&bundle)?;
        let shanghai_day = crate::shanghai_day(now);
        let dedup_key = canonical_json_hash(&json!({
            "kind":kind,
            "shanghai_day":shanghai_day,
            "source_watermark":inputs.watermark,
            "policy_version":DATASET_POLICY_VERSION,
            "manifest_hash":manifest_hash,
            "bundle_hash":bundle_hash
        }));

        if let Some(existing) = self.find_dataset_build(kind, &dedup_key)? {
            if !quality_enforced {
                self.set_dataset_draft(&existing, now)?;
            } else if self
                .get_dataset_quality_report(existing.build_id)?
                .is_none()
            {
                self.enqueue_unique_learning_job(
                    "dataset_quality_audit_v1",
                    &existing.build_id.to_string(),
                    json!({"build_id":existing.build_id}),
                    1.5,
                    5,
                )?;
            }
            return Ok(existing);
        }

        let build_id = Uuid::new_v4();
        let view_id = Uuid::new_v4();
        let build = DatasetBuild {
            schema_version: SCHEMA_VERSION.into(),
            build_id,
            kind: kind.into(),
            source_watermark: inputs.watermark,
            parent_build_id: parent.map(|draft| draft.build_id),
            shards,
            bundle_hash,
            manifest_hash,
            dedup_key,
            decision_count,
            replay_eval_count,
            rejected_record_count: inputs.rejected_license + inputs.rejected_safety,
            split_stats: stats,
            eligibility,
            expert_view_id: Some(view_id),
            expert_manifest_hash: Some(expert_manifest_hash.clone()),
            expert_taxonomy_hash: Some(prepared_experts.taxonomy_hash.clone()),
            policy_version: DATASET_POLICY_VERSION.into(),
            created_at: now,
        };
        validate_dataset_build(&build)?;
        let expert_view = ExpertDatasetView {
            schema_version: SCHEMA_VERSION.into(),
            view_id,
            build_id,
            taxonomy: prepared_experts.taxonomy,
            taxonomy_hash: prepared_experts.taxonomy_hash,
            assignments_hash,
            manifest_hash: expert_manifest_hash,
            bundle_hash: build.bundle_hash.clone(),
            shards: expert_shards,
            assignment_count: prepared_experts.assignments.len() as u64,
            ambiguous_count: prepared_experts.ambiguous_count,
            out_of_distribution_count: prepared_experts.out_of_distribution_count,
            negative_transfer_count: prepared_experts.negative_transfer_count,
            readiness: prepared_experts.readiness,
            policy_version: crate::experts::EXPERT_POLICY_VERSION.into(),
            created_at: now,
        };
        validate_expert_dataset_view(&expert_view)?;
        let draft = DatasetDraft {
            kind: kind.into(),
            build_id: build.build_id,
            manifest_hash: build.manifest_hash.clone(),
            updated_at: now,
        };
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        transaction.execute(
            "INSERT INTO dataset_builds(
               id,kind,source_watermark,parent_build_id,bundle_hash,manifest_hash,
               dedup_key,build_json,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9)",
            params![
                build.build_id.to_string(),
                build.kind,
                build.source_watermark.map(|value| value.to_rfc3339()),
                build.parent_build_id.map(|value| value.to_string()),
                build.bundle_hash,
                build.manifest_hash,
                build.dedup_key,
                serde_json::to_string(&build)?,
                build.created_at.to_rfc3339()
            ],
        )?;
        transaction.execute(
            "INSERT INTO expert_dataset_views(
               id,build_id,taxonomy_hash,manifest_hash,bundle_hash,view_json,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7)",
            params![
                expert_view.view_id.to_string(),
                expert_view.build_id.to_string(),
                expert_view.taxonomy_hash,
                expert_view.manifest_hash,
                expert_view.bundle_hash,
                serde_json::to_string(&expert_view)?,
                expert_view.created_at.to_rfc3339()
            ],
        )?;
        for assignment in &prepared_experts.assignments {
            transaction.execute(
                "INSERT INTO expert_assignments(
                   view_id,record_hash,split,primary_expert_id,status,assignment_json
                 ) VALUES(?1,?2,?3,?4,?5,?6)",
                params![
                    expert_view.view_id.to_string(),
                    assignment.record_hash,
                    split_name(assignment.split),
                    assignment.primary_expert_id,
                    expert_assignment_status_name(assignment.status),
                    serde_json::to_string(assignment)?
                ],
            )?;
        }
        if !quality_enforced {
            transaction.execute(
                "INSERT INTO dataset_drafts(kind,build_id,manifest_hash,draft_json,updated_at)
                 VALUES(?1,?2,?3,?4,?5)
                 ON CONFLICT(kind) DO UPDATE SET
                   build_id=excluded.build_id,manifest_hash=excluded.manifest_hash,
                   draft_json=excluded.draft_json,updated_at=excluded.updated_at",
                params![
                    draft.kind,
                    draft.build_id.to_string(),
                    draft.manifest_hash,
                    serde_json::to_string(&draft)?,
                    draft.updated_at.to_rfc3339()
                ],
            )?;
        }
        transaction.commit()?;
        drop(conn);
        if quality_enforced {
            self.enqueue_unique_learning_job(
                "dataset_quality_audit_v1",
                &build.build_id.to_string(),
                json!({"build_id":build.build_id}),
                1.5,
                5,
            )?;
        }
        Ok(build)
    }

    /// Build a knowledge-web draft from the latest revisions of training-eligible
    /// KnowledgeCards that cleared the active structured quality gate (`quality_assess_v1`).
    ///
    /// A deliberately fail-closed path: cards are already gated at save time
    /// (`save_knowledge_card` enforces corroborated + low-risk + eligible
    /// evidence) and are included only when an active Flash/Pro assessment
    /// passes. Without a configured quality model no card qualifies and the
    /// draft is empty — empty builds are legal and never trigger training on
    /// their own.
    fn build_knowledge_web_draft(&self, kind: &str, now: DateTime<Utc>) -> Result<DatasetBuild> {
        let quality_enforced = self.quality_model_configured()?;
        let parent = self.get_dataset_draft(kind)?;
        let cards = self.knowledge_web_inputs()?;
        let mut grouped: BTreeMap<(DatasetSplit, String), Vec<Value>> = BTreeMap::new();
        // Every record of a (domain, topic) group resolves through the
        // group's earliest month, so cards of one group never scatter
        // across splits just because they were written in different months.
        let group_months = group_earliest_month(cards.iter().map(|(card, _)| {
            let (domain, topic_family) = knowledge_web_grouping(card);
            (domain, topic_family, card.created_at)
        }));
        let mut stats = DatasetSplitStats::default();
        let mut watermark: Option<DateTime<Utc>> = None;
        let mut included = 0_u64;
        let mut rejected_quality = 0_u64;
        let mut seen_hashes = HashSet::new();
        for (card, content_hash) in cards {
            watermark = max_time(watermark, card.created_at);
            if !seen_hashes.insert(content_hash.clone()) {
                continue;
            }
            let quality_hash = crate::quality::knowledge_card_quality_hash(&card);
            if !self.quality_clear(
                QualitySubjectKind::KnowledgeCard,
                &card.card_id.to_string(),
                &quality_hash,
            )? {
                rejected_quality += 1;
                continue;
            }
            let (domain, topic_family) = knowledge_web_grouping(&card);
            let month = group_months
                .get(&(domain.clone(), topic_family.clone()))
                .expect("group month computed for every card");
            let split = split_group(&domain, &topic_family, month);
            increment_split(&mut stats, split);
            included += 1;
            let record = knowledge_web_record(&card, &quality_hash, &domain, &topic_family);
            let envelope = json!({
                "kind":"knowledge_card",
                "split":split,
                "record":record
            });
            grouped
                .entry((split, "knowledge_card".into()))
                .or_default()
                .push(envelope);
        }

        let mut shards = Vec::new();
        let mut archive_entries = Vec::new();
        for ((split, record_kind), records) in grouped {
            let jsonl = encode_jsonl(&records)?;
            let uncompressed_hash = sha256(&jsonl);
            let compressed = zstd::stream::encode_all(Cursor::new(&jsonl), 9)?;
            let object_hash = self.put_object(&compressed)?;
            let name = format!("{}.{}.jsonl.zst", split_name(split), record_kind);
            let compressed_bytes = compressed.len() as u64;
            let record_count = records.len() as u64;
            archive_entries.push((name, compressed));
            shards.push(DatasetShard {
                split,
                record_kind,
                object_hash,
                uncompressed_hash,
                record_count,
                compressed_bytes,
            });
        }

        let eligibility = DatasetEligibilityReport {
            passed: true,
            policy_version: KNOWLEDGE_WEB_POLICY_VERSION.into(),
            contains_raw_documents: false,
            eligible_records: included,
            rejected_license_records: 0,
            rejected_safety_records: rejected_quality,
            reasons: Vec::new(),
        };
        let manifest = json!({
            "schema_version":SCHEMA_VERSION,
            "kind":"dataset_bundle_manifest_v1",
            "dataset_kind":kind,
            "source_watermark":watermark,
            "policy_version":KNOWLEDGE_WEB_POLICY_VERSION,
            "shards":shards,
            "knowledge_record_count":included,
            "rejected_quality_records":rejected_quality,
            "decision_count":included,
            "replay_eval_count":0,
            "split_stats":stats,
            "split_policy":"source_domain_topic_family_earliest_month_v1",
            "eligibility":eligibility,
            "contains_raw_documents":false
        });
        let manifest_bytes = serde_json::to_vec(&manifest)?;
        let manifest_hash = self.put_object(&manifest_bytes)?;
        archive_entries.push(("dataset-manifest.json".into(), manifest_bytes));
        archive_entries.sort_by(|left, right| left.0.cmp(&right.0));
        let bundle = deterministic_tar(&archive_entries)?;
        let bundle_hash = self.put_object(&bundle)?;
        let shanghai_day = crate::shanghai_day(now);
        let dedup_key = canonical_json_hash(&json!({
            "kind":kind,
            "shanghai_day":shanghai_day,
            "source_watermark":watermark,
            "policy_version":KNOWLEDGE_WEB_POLICY_VERSION,
            "manifest_hash":manifest_hash,
            "bundle_hash":bundle_hash
        }));

        if let Some(existing) = self.find_dataset_build(kind, &dedup_key)? {
            if !quality_enforced {
                self.set_dataset_draft(&existing, now)?;
            } else if self
                .get_dataset_quality_report(existing.build_id)?
                .is_none()
            {
                self.enqueue_unique_learning_job(
                    "dataset_quality_audit_v1",
                    &existing.build_id.to_string(),
                    json!({"build_id":existing.build_id}),
                    1.5,
                    5,
                )?;
            }
            return Ok(existing);
        }

        let build = DatasetBuild {
            schema_version: SCHEMA_VERSION.into(),
            build_id: Uuid::new_v4(),
            kind: kind.into(),
            source_watermark: watermark,
            parent_build_id: parent.map(|draft| draft.build_id),
            shards,
            bundle_hash,
            manifest_hash,
            dedup_key,
            decision_count: included,
            replay_eval_count: 0,
            rejected_record_count: rejected_quality,
            split_stats: stats,
            eligibility,
            expert_view_id: None,
            expert_manifest_hash: None,
            expert_taxonomy_hash: None,
            policy_version: KNOWLEDGE_WEB_POLICY_VERSION.into(),
            created_at: now,
        };
        validate_dataset_build(&build)?;
        let draft = DatasetDraft {
            kind: kind.into(),
            build_id: build.build_id,
            manifest_hash: build.manifest_hash.clone(),
            updated_at: now,
        };
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        transaction.execute(
            "INSERT INTO dataset_builds(
               id,kind,source_watermark,parent_build_id,bundle_hash,manifest_hash,
               dedup_key,build_json,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9)",
            params![
                build.build_id.to_string(),
                build.kind,
                build.source_watermark.map(|value| value.to_rfc3339()),
                build.parent_build_id.map(|value| value.to_string()),
                build.bundle_hash,
                build.manifest_hash,
                build.dedup_key,
                serde_json::to_string(&build)?,
                build.created_at.to_rfc3339()
            ],
        )?;
        if !quality_enforced {
            transaction.execute(
                "INSERT INTO dataset_drafts(kind,build_id,manifest_hash,draft_json,updated_at)
                 VALUES(?1,?2,?3,?4,?5)
                 ON CONFLICT(kind) DO UPDATE SET
                   build_id=excluded.build_id,manifest_hash=excluded.manifest_hash,
                   draft_json=excluded.draft_json,updated_at=excluded.updated_at",
                params![
                    draft.kind,
                    draft.build_id.to_string(),
                    draft.manifest_hash,
                    serde_json::to_string(&draft)?,
                    draft.updated_at.to_rfc3339()
                ],
            )?;
        }
        transaction.commit()?;
        drop(conn);
        if quality_enforced {
            self.enqueue_unique_learning_job(
                "dataset_quality_audit_v1",
                &build.build_id.to_string(),
                json!({"build_id":build.build_id}),
                1.5,
                5,
            )?;
        }
        Ok(build)
    }

    /// Latest-revision training-eligible cards with their stored content hashes.
    /// The `training_eligible=1` column is the invariant enforced by
    /// `save_knowledge_card` (corroborated, low-risk, supports-only evidence),
    /// so NOASSERTION/quarantined corpora never reach this query.
    fn knowledge_web_inputs(&self) -> Result<Vec<(KnowledgeCard, String)>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT k.card_json,k.content_hash FROM knowledge_cards k
             WHERE k.training_eligible=1
               AND k.revision=(SELECT MAX(k2.revision) FROM knowledge_cards k2
                 WHERE k2.card_id=k.card_id)
             ORDER BY k.card_id",
        )?;
        let rows = statement.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?;
        rows.map(|row| {
            let (json, hash) = row?;
            Ok((serde_json::from_str(&json)?, hash))
        })
        .collect()
    }

    pub fn get_dataset_draft(&self, kind: &str) -> Result<Option<DatasetDraft>> {
        ensure_dataset_kind(kind)?;
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT draft_json FROM dataset_drafts WHERE kind=?1",
            params![kind],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn audit_dataset_build(
        &self,
        build_id: Uuid,
        actor: &str,
        reason: &str,
        now: DateTime<Utc>,
    ) -> Result<()> {
        if actor.trim().is_empty() || reason.trim().is_empty() {
            bail!("dataset build audit requires actor and reason");
        }
        Self::audit_conn(
            &self.lock_conn(),
            "dataset_build",
            &build_id.to_string(),
            "manual_build",
            actor.trim(),
            reason.trim(),
            now,
        )
    }

    pub fn get_dataset_build(&self, id: Uuid) -> Result<Option<DatasetBuild>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT build_json FROM dataset_builds WHERE id=?1",
            params![id.to_string()],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn list_dataset_builds(&self, kind: &str, limit: usize) -> Result<Vec<DatasetBuild>> {
        ensure_dataset_kind(kind)?;
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT build_json FROM dataset_builds WHERE kind=?1
             ORDER BY created_at DESC,id LIMIT ?2",
        )?;
        let rows = statement.query_map(params![kind, limit.clamp(1, 500) as i64], |row| {
            row.get::<_, String>(0)
        })?;
        rows.map(|row| Ok(serde_json::from_str(&row?)?)).collect()
    }

    pub fn get_expert_dataset_view(&self, id: Uuid) -> Result<Option<ExpertDatasetView>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT view_json FROM expert_dataset_views WHERE id=?1",
            params![id.to_string()],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn get_expert_dataset_view_for_build(
        &self,
        build_id: Uuid,
    ) -> Result<Option<ExpertDatasetView>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT view_json FROM expert_dataset_views WHERE build_id=?1",
            params![build_id.to_string()],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    pub fn list_expert_dataset_views(&self, limit: usize) -> Result<Vec<ExpertDatasetView>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT view_json FROM expert_dataset_views ORDER BY created_at DESC,id LIMIT ?1",
        )?;
        let rows = statement.query_map(params![limit.clamp(1, 500) as i64], |row| {
            row.get::<_, String>(0)
        })?;
        rows.map(|row| Ok(serde_json::from_str(&row?)?)).collect()
    }

    pub fn list_expert_assignments(
        &self,
        view_id: Uuid,
        limit: usize,
    ) -> Result<Vec<ExpertAssignment>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT assignment_json FROM expert_assignments WHERE view_id=?1
             ORDER BY record_hash LIMIT ?2",
        )?;
        let rows = statement.query_map(
            params![view_id.to_string(), limit.clamp(1, 10_000) as i64],
            |row| row.get::<_, String>(0),
        )?;
        rows.map(|row| Ok(serde_json::from_str(&row?)?)).collect()
    }

    pub fn freeze_dataset_snapshot(
        &self,
        request: &CreateDatasetSnapshotRequest,
        now: DateTime<Utc>,
    ) -> Result<DatasetSnapshotRecord> {
        ensure_dataset_kind(&request.kind)?;
        if request.created_by.trim().is_empty() || request.reason.trim().is_empty() {
            bail!("snapshot creator and reason are required");
        }
        let build_id = match request.build_id {
            Some(id) => id,
            None => {
                self.get_dataset_draft(&request.kind)?
                    .ok_or_else(|| anyhow!("dataset draft not found"))?
                    .build_id
            }
        };
        let build = self
            .get_dataset_build(build_id)?
            .ok_or_else(|| anyhow!("dataset build not found"))?;
        if build.kind != request.kind {
            bail!("dataset build kind does not match snapshot request");
        }
        validate_dataset_build(&build)?;
        let quality_report = if self.quality_model_configured()? {
            let report = self
                .get_dataset_quality_report(build.build_id)?
                .ok_or_else(|| anyhow!("dataset build has not completed quality audit"))?;
            if !report.gate_passed {
                bail!("dataset build quality gate did not pass");
            }
            Some(report)
        } else {
            None
        };
        let snapshot = DatasetSnapshot {
            schema_version: SCHEMA_VERSION.into(),
            snapshot_id: Uuid::new_v4(),
            kind: build.kind,
            build_id: build.build_id,
            bundle_hash: build.bundle_hash,
            manifest_hash: build.manifest_hash,
            decision_count: build.decision_count,
            replay_eval_count: build.replay_eval_count,
            split_stats: build.split_stats,
            eligibility: build.eligibility,
            expert_view_id: build.expert_view_id,
            expert_manifest_hash: build.expert_manifest_hash,
            expert_taxonomy_hash: build.expert_taxonomy_hash,
            quality_report_id: quality_report.as_ref().map(|report| report.report_id),
            quality_report_hash: quality_report
                .as_ref()
                .map(|report| report.report_hash.clone()),
            created_by: request.created_by.trim().into(),
            reason: request.reason.trim().into(),
            legacy_candidate_id: None,
            created_at: now,
        };
        validate_dataset_snapshot(&snapshot)?;
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO dataset_snapshots(
               id,kind,build_id,bundle_hash,manifest_hash,snapshot_json,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7)",
            params![
                snapshot.snapshot_id.to_string(),
                snapshot.kind,
                snapshot.build_id.to_string(),
                snapshot.bundle_hash,
                snapshot.manifest_hash,
                serde_json::to_string(&snapshot)?,
                snapshot.created_at.to_rfc3339()
            ],
        )?;
        Ok(DatasetSnapshotRecord {
            snapshot,
            revocation: None,
        })
    }

    pub fn get_dataset_snapshot(&self, id: Uuid) -> Result<Option<DatasetSnapshotRecord>> {
        let conn = self.lock_conn();
        let row: Option<(String, Option<String>)> = conn
            .query_row(
                "SELECT s.snapshot_json,
                  (SELECT r.revocation_json FROM dataset_snapshot_revocations r
                   WHERE r.snapshot_id=s.id ORDER BY r.id DESC LIMIT 1)
                 FROM dataset_snapshots s WHERE s.id=?1",
                params![id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        row.map(|(snapshot, revocation)| {
            Ok(DatasetSnapshotRecord {
                snapshot: serde_json::from_str(&snapshot)?,
                revocation: revocation
                    .map(|value| serde_json::from_str(&value))
                    .transpose()?,
            })
        })
        .transpose()
    }

    pub fn list_dataset_snapshots(&self, kind: Option<&str>) -> Result<Vec<DatasetSnapshotRecord>> {
        if let Some(kind) = kind {
            ensure_dataset_kind(kind)?;
        }
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT s.snapshot_json,
              (SELECT r.revocation_json FROM dataset_snapshot_revocations r
               WHERE r.snapshot_id=s.id ORDER BY r.id DESC LIMIT 1)
             FROM dataset_snapshots s WHERE (?1 IS NULL OR s.kind=?1)
             ORDER BY s.created_at DESC,s.id",
        )?;
        let rows = statement.query_map(params![kind], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, Option<String>>(1)?))
        })?;
        rows.map(|row| {
            let (snapshot, revocation) = row?;
            Ok(DatasetSnapshotRecord {
                snapshot: serde_json::from_str(&snapshot)?,
                revocation: revocation
                    .map(|value| serde_json::from_str(&value))
                    .transpose()?,
            })
        })
        .collect()
    }

    pub fn revoke_dataset_snapshot(
        &self,
        id: Uuid,
        request: &RevokeDatasetSnapshotRequest,
        now: DateTime<Utc>,
    ) -> Result<DatasetSnapshotRecord> {
        if request.actor.trim().is_empty() || request.reason.trim().is_empty() {
            bail!("snapshot revocation actor and reason are required");
        }
        let current = self
            .get_dataset_snapshot(id)?
            .ok_or_else(|| anyhow!("dataset snapshot not found"))?;
        if current.revocation.is_some() {
            bail!("dataset snapshot is already revoked");
        }
        let revocation = DatasetSnapshotRevocation {
            snapshot_id: id,
            actor: request.actor.trim().into(),
            reason: request.reason.trim().into(),
            revoked_at: now,
        };
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO dataset_snapshot_revocations(
               snapshot_id,actor,reason,revocation_json,created_at
             ) VALUES(?1,?2,?3,?4,?5)",
            params![
                id.to_string(),
                revocation.actor,
                revocation.reason,
                serde_json::to_string(&revocation)?,
                now.to_rfc3339()
            ],
        )?;
        Ok(DatasetSnapshotRecord {
            snapshot: current.snapshot,
            revocation: Some(revocation),
        })
    }

    /// Remove old build rows while preserving every draft, snapshot, the most
    /// recent 30 daily builds and one build from each of the latest 12 weeks.
    /// CAS files are intentionally left for the reference-aware CAS collector.
    pub fn prune_dataset_builds(&self, kind: &str) -> Result<usize> {
        let builds = self.list_dataset_builds(kind, 10_000)?;
        let draft = self.get_dataset_draft(kind)?.map(|value| value.build_id);
        let snapshot_ids: HashSet<Uuid> = self
            .list_dataset_snapshots(Some(kind))?
            .into_iter()
            .map(|record| record.snapshot.build_id)
            .collect();
        let mut keep = HashSet::new();
        keep.extend(
            builds
                .iter()
                .take(RETAIN_DAILY_BUILDS)
                .map(|value| value.build_id),
        );
        if let Some(id) = draft {
            keep.insert(id);
        }
        keep.extend(snapshot_ids);
        let mut weeks = BTreeSet::new();
        for build in &builds {
            let iso = build.created_at.iso_week();
            if weeks.len() < RETAIN_WEEKLY_BUILDS && weeks.insert((iso.year(), iso.week())) {
                keep.insert(build.build_id);
            }
        }
        let delete = builds
            .into_iter()
            .filter(|build| !keep.contains(&build.build_id))
            .map(|build| build.build_id.to_string())
            .collect::<Vec<_>>();
        let mut conn = self.lock_conn();
        // Child rows reference dataset_builds without ON DELETE CASCADE, so a
        // build carrying an expert view or quality report cannot be deleted
        // directly. Remove its derived artifacts first, atomically. Builds
        // referenced by snapshots or the current draft are never in `delete`.
        let transaction = conn.transaction()?;
        for id in &delete {
            // FK chain: expert_assignments -> expert_dataset_views -> dataset_builds.
            transaction.execute(
                "DELETE FROM expert_assignments WHERE view_id IN (
                   SELECT id FROM expert_dataset_views WHERE build_id=?1
                 )",
                params![id],
            )?;
            transaction.execute(
                "DELETE FROM expert_dataset_views WHERE build_id=?1",
                params![id],
            )?;
            transaction.execute(
                "DELETE FROM dataset_quality_reports WHERE build_id=?1",
                params![id],
            )?;
            transaction.execute("DELETE FROM dataset_builds WHERE id=?1", params![id])?;
        }
        transaction.commit()?;
        Ok(delete.len())
    }

    pub(crate) fn migrate_legacy_meta_candidates(&self) -> Result<usize> {
        let candidates = {
            let conn = self.lock_conn();
            let mut statement = conn.prepare(
                "SELECT candidate_json FROM meta_training_candidates c
                 WHERE NOT EXISTS(SELECT 1 FROM dataset_snapshots s WHERE s.id=c.id)
                 ORDER BY c.created_at,c.id",
            )?;
            statement
                .query_map([], |row| row.get::<_, String>(0))?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };
        let mut migrated = 0;
        for value in candidates {
            let candidate: MetaTrainingCandidate = serde_json::from_str(&value)?;
            let split_stats = legacy_split_stats(&self.get_object(&candidate.dataset_hash)?)?;
            let snapshot = DatasetSnapshot {
                schema_version: SCHEMA_VERSION.into(),
                snapshot_id: candidate.candidate_id,
                kind: META_DATASET_KIND.into(),
                build_id: candidate.candidate_id,
                bundle_hash: candidate.dataset_hash,
                manifest_hash: candidate.manifest_hash,
                decision_count: candidate.decision_count,
                replay_eval_count: candidate.replay_eval_count,
                split_stats,
                eligibility: DatasetEligibilityReport {
                    passed: true,
                    policy_version: "legacy-meta-candidate-v1".into(),
                    contains_raw_documents: false,
                    eligible_records: candidate.eligible_record_count,
                    rejected_license_records: 0,
                    rejected_safety_records: 0,
                    reasons: vec!["backfilled from MetaTrainingCandidate".into()],
                },
                expert_view_id: None,
                expert_manifest_hash: None,
                expert_taxonomy_hash: None,
                quality_report_id: None,
                quality_report_hash: None,
                created_by: "migration".into(),
                reason: "v3.1 compatibility backfill".into(),
                legacy_candidate_id: Some(candidate.candidate_id),
                created_at: candidate.created_at,
            };
            let conn = self.lock_conn();
            migrated += conn.execute(
                "INSERT OR IGNORE INTO dataset_snapshots(
                   id,kind,build_id,bundle_hash,manifest_hash,snapshot_json,created_at
                 ) VALUES(?1,?2,?3,?4,?5,?6,?7)",
                params![
                    snapshot.snapshot_id.to_string(),
                    snapshot.kind,
                    snapshot.build_id.to_string(),
                    snapshot.bundle_hash,
                    snapshot.manifest_hash,
                    serde_json::to_string(&snapshot)?,
                    snapshot.created_at.to_rfc3339()
                ],
            )?;
        }
        Ok(migrated)
    }

    fn dataset_inputs(&self) -> Result<DatasetInputs> {
        let (trace_rows, replay_rows, synthetic_rows) = {
            let conn = self.lock_conn();
            let traces = {
                let mut statement = conn.prepare(
                    "SELECT trace_json,created_at FROM meta_decision_traces ORDER BY created_at,id",
                )?;
                statement
                    .query_map([], |row| {
                        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
                    })?
                    .collect::<rusqlite::Result<Vec<_>>>()?
            };
            let replays = {
                let mut statement = conn.prepare(
                    "SELECT evaluation_json,created_at FROM meta_replay_evaluations
                     ORDER BY created_at,id",
                )?;
                statement
                    .query_map([], |row| {
                        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
                    })?
                    .collect::<rusqlite::Result<Vec<_>>>()?
            };
            let synthetic = {
                let mut statement = conn.prepare(
                    "SELECT candidate_json,updated_at FROM synthetic_training_candidates
                     WHERE status IN ('verified','approved') ORDER BY created_at,id",
                )?;
                statement
                    .query_map([], |row| {
                        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
                    })?
                    .collect::<rusqlite::Result<Vec<_>>>()?
            };
            (traces, replays, synthetic)
        };

        let mut watermark = None;
        let mut traces = BTreeMap::new();
        for (value, created_at) in trace_rows {
            watermark = max_time(watermark, parse_time(&created_at)?);
            let trace: MetaDecisionTrace = serde_json::from_str(&value)?;
            traces.insert(
                (format!("{:?}", trace.task_kind), trace.input_hash.clone()),
                trace,
            );
        }
        let mut replays = BTreeMap::new();
        for (value, created_at) in replay_rows {
            watermark = max_time(watermark, parse_time(&created_at)?);
            let replay: MetaReplayEvaluation = serde_json::from_str(&value)?;
            replays.insert(
                (
                    replay.task_id.clone(),
                    replay.source_domain.clone(),
                    replay.topic_family.clone(),
                ),
                replay,
            );
        }
        let mut synthetic_candidates = Vec::new();
        for (value, updated_at) in synthetic_rows {
            watermark = max_time(watermark, parse_time(&updated_at)?);
            synthetic_candidates.push(serde_json::from_str::<SyntheticTrainingCandidate>(&value)?);
        }

        let quality_enforced = self.quality_model_configured()?;
        let mut rejected_license = 0;
        let mut rejected_safety = 0;
        let mut accepted_traces = Vec::new();
        for trace in traces.into_values() {
            let unsafe_record = trace.policy_violations != 0
                || trace.prompt_injection_detected
                || contains_sensitive_value(&trace.input)
                || contains_sensitive_value(&trace.output);
            if unsafe_record {
                rejected_safety += 1;
                continue;
            }
            if !trace.training_eligible {
                rejected_license += 1;
                continue;
            }
            let hash = canonical_json_hash(&serde_json::to_value(&trace)?);
            if quality_enforced
                && !self.quality_clear(
                    cerebellum_core::QualitySubjectKind::MetaDecision,
                    &trace.decision_id.to_string(),
                    &hash,
                )?
            {
                rejected_safety += 1;
                continue;
            }
            accepted_traces.push(trace);
        }
        let mut accepted_replays = Vec::new();
        for replay in replays.into_values() {
            if !replay.safety_passed {
                rejected_safety += 1;
                continue;
            }
            let hash = canonical_json_hash(&serde_json::to_value(&replay)?);
            if quality_enforced
                && !self.quality_clear(
                    cerebellum_core::QualitySubjectKind::MetaReplay,
                    &replay.evaluation_id.to_string(),
                    &hash,
                )?
            {
                rejected_safety += 1;
                continue;
            }
            accepted_replays.push(replay);
        }
        let trace_parent = accepted_traces
            .iter()
            .map(|trace| {
                (
                    trace.decision_id.to_string(),
                    (trace.source_domain.clone(), trace.topic_family.clone()),
                )
            })
            .collect::<BTreeMap<_, _>>();
        let replay_parent = accepted_replays
            .iter()
            .map(|replay| {
                (
                    replay.evaluation_id.to_string(),
                    (replay.source_domain.clone(), replay.topic_family.clone()),
                )
            })
            .collect::<BTreeMap<_, _>>();
        let provisional = DatasetInputs {
            traces: accepted_traces,
            replays: accepted_replays,
            synthetic: Vec::new(),
            rejected_license,
            rejected_safety,
            watermark,
        };
        let base_splits = split_assignments(&provisional);
        let mut original_per_group = BTreeMap::<(String, DatasetSplit), usize>::new();
        for trace in &provisional.traces {
            let split = base_splits[&(trace.source_domain.clone(), trace.topic_family.clone())];
            *original_per_group
                .entry((format!("{:?}", trace.task_kind), split))
                .or_default() += 1;
        }
        let mut generated_per_group = BTreeMap::<(String, DatasetSplit), usize>::new();
        let mut accepted_synthetic = Vec::new();
        for candidate in synthetic_candidates {
            if candidate.generation_depth != 1
                || candidate.parent_subject_kind == QualitySubjectKind::SyntheticCandidate
                || (!candidate.objective_verified
                    && candidate.status != SyntheticCandidateStatus::Approved)
            {
                rejected_safety += 1;
                continue;
            }
            let parent = match candidate.parent_subject_kind {
                QualitySubjectKind::MetaDecision => trace_parent.get(&candidate.parent_subject_id),
                QualitySubjectKind::MetaReplay => replay_parent.get(&candidate.parent_subject_id),
                _ => None,
            };
            let Some((source_domain, topic_family)) = parent.cloned() else {
                rejected_safety += 1;
                continue;
            };
            let hash = candidate.content_hash.clone();
            if quality_enforced
                && !self.quality_clear(
                    QualitySubjectKind::SyntheticCandidate,
                    &candidate.candidate_id.to_string(),
                    &hash,
                )?
            {
                rejected_safety += 1;
                continue;
            }
            let split = base_splits[&(source_domain.clone(), topic_family.clone())];
            let group = (format!("{:?}", candidate.task_kind), split);
            let original = *original_per_group.get(&group).unwrap_or(&0);
            let generated = generated_per_group.entry(group).or_default();
            if *generated >= original / 4 {
                continue;
            }
            *generated += 1;
            accepted_synthetic.push(SyntheticDatasetRecord {
                candidate,
                source_domain,
                topic_family,
            });
        }
        Ok(DatasetInputs {
            synthetic: accepted_synthetic,
            rejected_safety,
            ..provisional
        })
    }

    fn find_dataset_build(&self, kind: &str, dedup_key: &str) -> Result<Option<DatasetBuild>> {
        let conn = self.lock_conn();
        conn.query_row(
            "SELECT build_json FROM dataset_builds WHERE kind=?1 AND dedup_key=?2",
            params![kind, dedup_key],
            |row| row.get::<_, String>(0),
        )
        .optional()?
        .map(|value| serde_json::from_str(&value).map_err(Into::into))
        .transpose()
    }

    fn set_dataset_draft(&self, build: &DatasetBuild, now: DateTime<Utc>) -> Result<()> {
        let draft = DatasetDraft {
            kind: build.kind.clone(),
            build_id: build.build_id,
            manifest_hash: build.manifest_hash.clone(),
            updated_at: now,
        };
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO dataset_drafts(kind,build_id,manifest_hash,draft_json,updated_at)
             VALUES(?1,?2,?3,?4,?5)
             ON CONFLICT(kind) DO UPDATE SET
               build_id=excluded.build_id,manifest_hash=excluded.manifest_hash,
               draft_json=excluded.draft_json,updated_at=excluded.updated_at",
            params![
                draft.kind,
                draft.build_id.to_string(),
                draft.manifest_hash,
                serde_json::to_string(&draft)?,
                now.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    pub(crate) fn promote_dataset_draft_after_quality(
        &self,
        build: &DatasetBuild,
        now: DateTime<Utc>,
    ) -> Result<()> {
        self.set_dataset_draft(build, now)
    }
}

fn ensure_dataset_kind(kind: &str) -> Result<()> {
    if kind != META_DATASET_KIND && kind != KNOWLEDGE_WEB_DATASET_KIND {
        bail!("unsupported dataset kind: {kind}");
    }
    Ok(())
}

/// Deterministic split grouping for knowledge-web cards: first evidence host
/// (fallback "knowledge-web") + first topic id (fallback "unscoped").
fn knowledge_web_grouping(card: &KnowledgeCard) -> (String, String) {
    let domain = card
        .evidence
        .first()
        .and_then(|evidence| {
            url::Url::parse(&evidence.canonical_url)
                .ok()
                .and_then(|url| url.host_str().map(str::to_owned))
        })
        .unwrap_or_else(|| "knowledge-web".into());
    let topic_family = card
        .topic_ids
        .first()
        .map(|topic| topic.to_string())
        .unwrap_or_else(|| "unscoped".into());
    (domain, topic_family)
}

/// Map a quality-cleared card to an instruction record: question = card title
/// plus supporting evidence excerpts, answer = card body (summary + atomic
/// claims), provenance carried in metadata.
fn knowledge_web_record(
    card: &KnowledgeCard,
    content_hash: &str,
    domain: &str,
    topic_family: &str,
) -> Value {
    let evidence_notes = card
        .evidence
        .iter()
        .filter_map(|evidence| evidence.excerpt.as_deref())
        .take(3)
        .collect::<Vec<_>>();
    let question = if evidence_notes.is_empty() {
        card.title.clone()
    } else {
        format!("{}\n\n证据: {}", card.title, evidence_notes.join("；"))
    };
    let claims = card
        .claims
        .iter()
        .map(|claim| {
            format!(
                "- {} {} {}（置信度 {:.2}）",
                claim.subject, claim.predicate, claim.object, claim.confidence
            )
        })
        .collect::<Vec<_>>()
        .join("\n");
    let answer = if claims.is_empty() {
        card.summary.clone()
    } else {
        format!("{}\n\n{}", card.summary, claims)
    };
    json!({
        "question":question,
        "answer":answer,
        "source_domain":domain,
        "topic_family":topic_family,
        "metadata":{
            "card_id":card.card_id,
            "revision":card.revision,
            "content_hash":content_hash,
            "training_eligible":card.training_eligible,
            "topic_ids":card.topic_ids,
            "status":card.status,
            "model_id":card.model_id,
            "observed_at":card.observed_at,
            "valid_until":card.valid_until,
            "confidence":card.scores.confidence,
            "evidence_urls":card
                .evidence
                .iter()
                .map(|evidence| evidence.canonical_url.clone())
                .collect::<Vec<_>>()
        }
    })
}
fn increment_split(stats: &mut DatasetSplitStats, split: DatasetSplit) {
    match split {
        DatasetSplit::Train => stats.train += 1,
        DatasetSplit::Validation => stats.validation += 1,
        DatasetSplit::Holdout => stats.holdout += 1,
    }
}

pub(crate) fn split_name(split: DatasetSplit) -> &'static str {
    match split {
        DatasetSplit::Train => "train",
        DatasetSplit::Validation => "validation",
        DatasetSplit::Holdout => "holdout",
    }
}

/// Canonical dataset split key: one (domain, topic) group is hashed with the
/// group's earliest month, so records of one group always share a split.
pub(crate) fn split_group_key(
    source_domain: &str,
    topic_family: &str,
    earliest_month: &str,
) -> String {
    format!("{source_domain}\n{topic_family}\n{earliest_month}")
}

/// Earliest "%Y-%m" per (domain, topic) group over the given records.
pub(crate) fn group_earliest_month(
    records: impl IntoIterator<Item = (String, String, DateTime<Utc>)>,
) -> BTreeMap<(String, String), String> {
    let mut earliest = BTreeMap::<(String, String), DateTime<Utc>>::new();
    for (domain, topic, created_at) in records {
        earliest
            .entry((domain, topic))
            .and_modify(|current| *current = (*current).min(created_at))
            .or_insert(created_at);
    }
    earliest
        .into_iter()
        .map(|(key, created_at)| (key, created_at.format("%Y-%m").to_string()))
        .collect()
}

fn split_assignments(inputs: &DatasetInputs) -> BTreeMap<(String, String), DatasetSplit> {
    let mut earliest = BTreeMap::<(String, String), DateTime<Utc>>::new();
    for (domain, topic, created_at) in inputs
        .traces
        .iter()
        .map(|trace| (&trace.source_domain, &trace.topic_family, trace.created_at))
        .chain(inputs.replays.iter().map(|replay| {
            (
                &replay.source_domain,
                &replay.topic_family,
                replay.created_at,
            )
        }))
        .chain(inputs.synthetic.iter().map(|generated| {
            (
                &generated.source_domain,
                &generated.topic_family,
                generated.candidate.created_at,
            )
        }))
    {
        earliest
            .entry((domain.clone(), topic.clone()))
            .and_modify(|current| *current = (*current).min(created_at))
            .or_insert(created_at);
    }
    earliest
        .into_iter()
        .map(|((domain, topic), created_at)| {
            let month = created_at.format("%Y-%m");
            let split = split_group(&domain, &topic, &month.to_string());
            ((domain, topic), split)
        })
        .collect()
}

pub(crate) fn split_group(
    source_domain: &str,
    topic_family: &str,
    earliest_month: &str,
) -> DatasetSplit {
    let digest =
        Sha256::digest(split_group_key(source_domain, topic_family, earliest_month).as_bytes());
    match digest[0] % 10 {
        0..=7 => DatasetSplit::Train,
        8 => DatasetSplit::Validation,
        _ => DatasetSplit::Holdout,
    }
}

fn encode_jsonl(records: &[Value]) -> Result<Vec<u8>> {
    let mut jsonl = Vec::new();
    for record in records {
        serde_json::to_writer(&mut jsonl, record)?;
        jsonl.push(b'\n');
    }
    Ok(jsonl)
}

pub(crate) fn expert_shard_name(
    split: DatasetSplit,
    purpose: ExpertDatasetPurpose,
    expert_id: Option<&str>,
    record_kind: &str,
) -> String {
    let purpose = match purpose {
        ExpertDatasetPurpose::Shared => "shared".to_owned(),
        ExpertDatasetPurpose::Router => "router".to_owned(),
        ExpertDatasetPurpose::RoutingNegative => "routing-negative".to_owned(),
        ExpertDatasetPurpose::Expert => format!(
            "expert-{}",
            expert_id.expect("expert-purpose shards always have an expert id")
        ),
    };
    format!(
        "experts/{}.{}.{}.jsonl.zst",
        split_name(split),
        purpose,
        record_kind
    )
}

fn expert_assignment_status_name(status: cerebellum_core::ExpertAssignmentStatus) -> &'static str {
    match status {
        cerebellum_core::ExpertAssignmentStatus::Assigned => "assigned",
        cerebellum_core::ExpertAssignmentStatus::Ambiguous => "ambiguous",
        cerebellum_core::ExpertAssignmentStatus::OutOfDistribution => "out_of_distribution",
        cerebellum_core::ExpertAssignmentStatus::NegativeTransfer => "negative_transfer",
    }
}

fn deterministic_tar(entries: &[(String, Vec<u8>)]) -> Result<Vec<u8>> {
    let mut archive = tar::Builder::new(Vec::new());
    for (name, content) in entries {
        let mut header = tar::Header::new_gnu();
        header.set_size(content.len() as u64);
        header.set_mode(0o644);
        header.set_uid(0);
        header.set_gid(0);
        header.set_mtime(0);
        header.set_cksum();
        archive.append_data(&mut header, name, Cursor::new(content))?;
    }
    archive.finish()?;
    archive.into_inner().map_err(Into::into)
}

fn sha256(content: &[u8]) -> String {
    format!("{:x}", Sha256::digest(content))
}

fn parse_time(value: &str) -> Result<DateTime<Utc>> {
    Ok(DateTime::parse_from_rfc3339(value)
        .with_context(|| format!("invalid ledger timestamp {value}"))?
        .with_timezone(&Utc))
}

fn max_time(current: Option<DateTime<Utc>>, value: DateTime<Utc>) -> Option<DateTime<Utc>> {
    Some(current.map_or(value, |current| current.max(value)))
}

fn contains_sensitive_value(value: &Value) -> bool {
    match value {
        Value::String(value) => {
            let lower = value.to_lowercase();
            lower.contains("-----begin private key-----")
                || lower.contains("authorization: bearer ")
                || lower.contains("cookie:")
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

fn legacy_split_stats(dataset: &[u8]) -> Result<DatasetSplitStats> {
    let mut stats = DatasetSplitStats::default();
    for line in dataset
        .split(|byte| *byte == b'\n')
        .filter(|line| !line.is_empty())
    {
        let value: Value = serde_json::from_slice(line)?;
        match value.get("split").and_then(Value::as_str) {
            Some("validation") => stats.validation += 1,
            Some("holdout") => stats.holdout += 1,
            _ => stats.train += 1,
        }
    }
    Ok(stats)
}

#[cfg(test)]
mod tests {
    use super::*;
    use cerebellum_core::{
        AcquisitionMethod, CreateSourcePolicyRequest, DataQualityAssessment, DocumentEnvelope,
        DocumentRights, EvidenceRelationship, KnowledgeClaim, KnowledgeEvidenceRef,
        KnowledgeScores, KnowledgeStatus, MetaTaskKind, ModelCalibrationMetrics,
        ModelEndpointStatus, ModelEndpointVersion, ModelTokenUsage, QualityDimensions,
        QualityModelStage, QualityVerdict, SCHEMA_VERSION, SourceAccessMode, SourceKind,
    };
    use tempfile::tempdir;

    fn trace(domain: &str, topic: &str, eligible: bool) -> MetaDecisionTrace {
        MetaDecisionTrace {
            schema_version: SCHEMA_VERSION.into(),
            decision_id: Uuid::new_v4(),
            task_kind: MetaTaskKind::Relevance,
            input_hash: sha256(format!("{domain}:{topic}").as_bytes()),
            input: json!({"text":"synthetic"}),
            output: json!({"relevant":true}),
            source_domain: domain.into(),
            topic_family: topic.into(),
            policy_version: "test".into(),
            controller_version: "rules".into(),
            confidence: 1.0,
            cost: 0.0,
            useful: true,
            training_eligible: eligible,
            policy_violations: 0,
            prompt_injection_detected: false,
            data_classification: cerebellum_core::DataClassification::Private,
            external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
            redaction_attestation_hash: None,
            created_at: Utc::now(),
        }
    }

    #[test]
    fn daily_draft_has_no_training_threshold_and_is_deterministic() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        registry
            .record_meta_decision(&trace("example.com", "rust", true))
            .unwrap();
        registry
            .record_meta_decision(&trace("blocked.example", "rust", false))
            .unwrap();
        let first = registry
            .build_dataset_draft(META_DATASET_KIND, Utc::now())
            .unwrap();
        let second = registry
            .build_dataset_draft(META_DATASET_KIND, Utc::now())
            .unwrap();
        assert_eq!(first.build_id, second.build_id);
        assert_eq!(first.bundle_hash, second.bundle_hash);
        assert_eq!(first.decision_count, 1);
        assert_eq!(first.rejected_record_count, 1);
        let bundle = registry.get_object(&first.bundle_hash).unwrap();
        assert!(!String::from_utf8_lossy(&bundle).contains("blocked.example"));
    }

    #[test]
    fn snapshot_is_immutable_and_revocation_is_separate() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        registry
            .record_meta_decision(&trace("example.com", "rust", true))
            .unwrap();
        registry
            .build_dataset_draft(META_DATASET_KIND, Utc::now())
            .unwrap();
        let frozen = registry
            .freeze_dataset_snapshot(
                &CreateDatasetSnapshotRequest {
                    kind: META_DATASET_KIND.into(),
                    build_id: None,
                    created_by: "admin".into(),
                    reason: "test".into(),
                },
                Utc::now(),
            )
            .unwrap();
        let revoked = registry
            .revoke_dataset_snapshot(
                frozen.snapshot.snapshot_id,
                &RevokeDatasetSnapshotRequest {
                    actor: "admin".into(),
                    reason: "bad source".into(),
                },
                Utc::now(),
            )
            .unwrap();
        assert_eq!(frozen.snapshot, revoked.snapshot);
        assert!(revoked.revocation.is_some());
    }

    fn web_document(policy_id: Uuid, topic: Uuid, title: &str) -> DocumentEnvelope {
        let now = Utc::now();
        DocumentEnvelope {
            schema_version: SCHEMA_VERSION.into(),
            document_id: Uuid::new_v4(),
            topic_ids: vec![topic],
            source_policy_id: policy_id,
            external_id: None,
            url: format!("https://example.com/{title}"),
            canonical_url: format!("https://example.com/{title}"),
            author: None,
            title: title.into(),
            published_at: None,
            observed_at: now,
            fetched_at: now,
            raw_content_hash: None,
            cleaned_content_hash: sha256(format!("content-{title}").as_bytes()),
            extraction_method: AcquisitionMethod::Api,
            extractor_version: "test-v1".into(),
            language: "zh".into(),
            content_type: "application/json".into(),
            rights: DocumentRights {
                license: Some("CC0-1.0".into()),
                retrieval_allowed: true,
                storage_allowed: true,
                redistribution_allowed: true,
                explicit_training_permission: true,
                model_terms_allow_training: true,
                training_eligible: true,
                rights_source: "fixture".into(),
            },
            prompt_injection_detected: false,
            pii_detected: false,
            secret_detected: false,
            raw_expires_at: now + chrono::Duration::days(30),
            tombstoned: false,
            metadata: json!({"fixture":true}),
        }
    }

    fn web_card(document: &DocumentEnvelope, topic: Uuid, eligible: bool) -> KnowledgeCard {
        let now = Utc::now();
        KnowledgeCard {
            schema_version: SCHEMA_VERSION.into(),
            card_id: Uuid::new_v4(),
            revision: 1,
            topic_ids: vec![topic],
            title: format!("{} 的事实卡", document.title),
            summary: "该事件已经发生并得到两个独立来源确认。".into(),
            entities: vec!["事件".into()],
            claims: vec![KnowledgeClaim {
                claim_id: Uuid::new_v4(),
                subject: "该事件".into(),
                predicate: "发生于".into(),
                object: "本周".into(),
                valid_from: None,
                valid_until: None,
                confidence: 0.9,
            }],
            evidence: vec![KnowledgeEvidenceRef {
                document_id: document.document_id,
                canonical_url: document.canonical_url.clone(),
                content_hash: document.cleaned_content_hash.clone(),
                excerpt: Some("两个独立来源报道了同一事件。".into()),
                relationship: EvidenceRelationship::Supports,
                observed_at: document.observed_at,
            }],
            status: if eligible {
                KnowledgeStatus::Corroborated
            } else {
                KnowledgeStatus::Unverified
            },
            published_at: None,
            observed_at: now,
            valid_until: None,
            supersedes: None,
            model_id: "deterministic-v1".into(),
            prompt_hash: sha256(b"prompt-v1"),
            scores: KnowledgeScores {
                relevance: 0.9,
                novelty: 0.7,
                source_reliability: 0.8,
                extraction_completeness: 0.9,
                confidence: 0.85,
                risk: 0.1,
                cost: 0.01,
            },
            training_eligible: eligible,
            created_at: now,
        }
    }

    fn seed_quality_pass(registry: &Registry, card: &KnowledgeCard, content_hash: &str) {
        let now = Utc::now();
        let version = ModelEndpointVersion {
            schema_version: SCHEMA_VERSION.into(),
            endpoint_version_id: Uuid::new_v4(),
            provider: crate::quality::LOCAL_MODEL_PROVIDER.into(),
            model_id: "ornith-1.5-9b".into(),
            system_fingerprint: "fp-test".into(),
            prompt_version: crate::quality::QUALITY_PROMPT_VERSION.into(),
            schema_hash: sha256(b"schema"),
            status: ModelEndpointStatus::Active,
            metrics: ModelCalibrationMetrics::default(),
            approved_by: Some("test".into()),
            approval_reason: Some("fixture".into()),
            first_seen_at: now,
            updated_at: now,
        };
        let assessment = DataQualityAssessment {
            schema_version: SCHEMA_VERSION.into(),
            assessment_id: Uuid::new_v4(),
            subject_kind: QualitySubjectKind::KnowledgeCard,
            subject_id: card.card_id.to_string(),
            subject_hash: content_hash.into(),
            stage: QualityModelStage::Flash,
            model_id: "ornith-1.5-9b".into(),
            system_fingerprint: "fp-test".into(),
            prompt_version: crate::quality::QUALITY_PROMPT_VERSION.into(),
            prompt_hash: sha256(b"prompt"),
            schema_hash: sha256(b"schema"),
            verdict: QualityVerdict::Pass,
            dimensions: QualityDimensions {
                groundedness: 1.0,
                correctness: 1.0,
                relevance: 1.0,
                consistency: 1.0,
                completeness: 1.0,
                label_confidence: 1.0,
                ambiguity: 0.0,
                privacy_risk: 0.0,
                injection_risk: 0.0,
            },
            issue_codes: vec![],
            evidence_refs: vec![],
            suggested_actions: vec![],
            confidence: 0.99,
            usage: ModelTokenUsage::default(),
            estimated_cost_microusd: 0,
            redaction_attestation_hash: sha256(b"attestation"),
            parent_assessment_id: None,
            output_hash: sha256(b"output"),
            created_at: now,
        };
        let assessment_hash = canonical_json_hash(&serde_json::to_value(&assessment).unwrap());
        let conn = registry.lock_conn();
        conn.execute(
            "INSERT OR IGNORE INTO quality_model_versions(
               id,provider,model_id,system_fingerprint,prompt_version,status,version_json,updated_at
             ) VALUES(?1,?2,?3,?4,?5,'active',?6,?7)",
            params![
                version.endpoint_version_id.to_string(),
                version.provider,
                version.model_id,
                version.system_fingerprint,
                version.prompt_version,
                serde_json::to_string(&version).unwrap(),
                now.to_rfc3339()
            ],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO quality_assessments(
               id,subject_kind,subject_id,subject_hash,stage,model_id,system_fingerprint,
               prompt_version,verdict,assessment_json,content_hash,created_at
             ) VALUES(?1,'knowledge_card',?2,?3,'flash',?4,?5,?6,'pass',?7,?8,?9)",
            params![
                assessment.assessment_id.to_string(),
                assessment.subject_id,
                assessment.subject_hash,
                assessment.model_id,
                assessment.system_fingerprint,
                assessment.prompt_version,
                serde_json::to_string(&assessment).unwrap(),
                assessment_hash,
                now.to_rfc3339()
            ],
        )
        .unwrap();
    }

    #[test]
    fn knowledge_web_draft_contains_only_eligible_quality_cleared_cards() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "微博热榜".into(),
                kind: SourceKind::Weibo,
                base_url: "https://weibo.com/ajax/side/hotSearch".into(),
                access_mode: SourceAccessMode::Public,
                allowed_domains: vec!["weibo.com".into()],
                obey_robots: true,
                max_depth: 1,
                max_pages_per_run: 50,
                rate_limit_per_minute: 10,
                raw_retention_days: 30,
                training_license: Some("CC0-1.0".into()),
                model_terms_allow_training: true,
                auth_secret_ref: None,
                enabled: true,
                data_classification: cerebellum_core::DataClassification::Public,
                external_processing: cerebellum_core::ExternalProcessingPermission::Redacted,
            })
            .unwrap();
        let topic = Uuid::new_v4();
        // card-a: eligible + quality-cleared → 必须进 draft
        let doc_a = web_document(policy.policy_id, topic, "event-a");
        registry
            .save_document(&doc_a, b"content-event-a", None)
            .unwrap();
        let card_a = web_card(&doc_a, topic, true);
        registry.save_knowledge_card(&card_a).unwrap();
        // 评估记录的 subject_hash 采用 flag 归一化的质量身份（与生产一致：
        // 评估时卡的 flag 恒为 false）。
        let hash_a = crate::quality::knowledge_card_quality_hash(&card_a);
        seed_quality_pass(&registry, &card_a, &hash_a);
        // card-b: training_eligible=false → 永远不进 draft
        let doc_b = web_document(policy.policy_id, topic, "event-b");
        registry
            .save_document(&doc_b, b"content-event-b", None)
            .unwrap();
        let card_b = web_card(&doc_b, topic, false);
        registry.save_knowledge_card(&card_b).unwrap();
        // card-c: eligible 但未经质量评估 → 大模型挑选门拦截
        let doc_c = web_document(policy.policy_id, topic, "event-c");
        registry
            .save_document(&doc_c, b"content-event-c", None)
            .unwrap();
        let card_c = web_card(&doc_c, topic, true);
        registry.save_knowledge_card(&card_c).unwrap();

        let build = registry
            .build_dataset_draft(KNOWLEDGE_WEB_DATASET_KIND, Utc::now())
            .unwrap();
        assert_eq!(build.kind, KNOWLEDGE_WEB_DATASET_KIND);
        assert_eq!(build.decision_count, 1);
        assert_eq!(build.replay_eval_count, 0);
        assert_eq!(build.rejected_record_count, 1); // card-c 质量门拒收
        assert_eq!(build.policy_version, KNOWLEDGE_WEB_POLICY_VERSION);
        assert!(build.expert_view_id.is_none());
        assert!(build.eligibility.passed);
        let draft = registry
            .get_dataset_draft(KNOWLEDGE_WEB_DATASET_KIND)
            .unwrap()
            .unwrap();
        assert_eq!(draft.build_id, build.build_id);

        let shard = build.shards.first().expect("one shard");
        assert_eq!(shard.record_kind, "knowledge_card");
        assert_eq!(shard.record_count, 1);
        let compressed = registry.get_object(&shard.object_hash).unwrap();
        let jsonl = zstd::stream::decode_all(Cursor::new(compressed)).unwrap();
        let text = String::from_utf8(jsonl).unwrap();
        assert!(text.contains("event-a 的事实卡"));
        assert!(text.contains(&card_a.card_id.to_string()));
        assert!(!text.contains("event-b"));
        assert!(!text.contains("event-c"));

        // 确定性：同状态重建命中 dedup，不产生新 build
        let again = registry
            .build_dataset_draft(KNOWLEDGE_WEB_DATASET_KIND, Utc::now())
            .unwrap();
        assert_eq!(again.build_id, build.build_id);
        assert_eq!(again.bundle_hash, build.bundle_hash);
    }

    #[test]
    fn group_earliest_month_picks_the_oldest_month() {
        let jan = DateTime::parse_from_rfc3339("2026-01-15T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let mar = DateTime::parse_from_rfc3339("2026-03-15T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let months = group_earliest_month(vec![
            ("docs".to_string(), "rust".to_string(), mar),
            ("docs".to_string(), "rust".to_string(), jan),
        ]);
        assert_eq!(months[&("docs".to_string(), "rust".to_string())], "2026-01");
    }

    #[test]
    fn knowledge_web_groups_cross_month_cards_into_one_split() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "cross-month".into(),
                kind: SourceKind::Weibo,
                base_url: "https://source.example/feed".into(),
                access_mode: SourceAccessMode::Public,
                allowed_domains: vec!["source.example".into()],
                obey_robots: true,
                max_depth: 1,
                max_pages_per_run: 50,
                rate_limit_per_minute: 10,
                raw_retention_days: 30,
                training_license: Some("CC0-1.0".into()),
                model_terms_allow_training: true,
                auth_secret_ref: None,
                enabled: true,
                data_classification: cerebellum_core::DataClassification::Public,
                external_processing: cerebellum_core::ExternalProcessingPermission::Redacted,
            })
            .unwrap();
        let topic = Uuid::new_v4();
        let jan = DateTime::parse_from_rfc3339("2026-01-15T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let mar = DateTime::parse_from_rfc3339("2026-03-15T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        // Two quality-cleared cards in one (domain, topic) group, written
        // two months apart.
        let mut cards = Vec::new();
        for (title, created_at, bytes) in [
            ("event-jan", jan, &b"content-event-jan"[..]),
            ("event-mar", mar, &b"content-event-mar"[..]),
        ] {
            let doc = web_document(policy.policy_id, topic, title);
            registry.save_document(&doc, bytes, None).unwrap();
            let mut card = web_card(&doc, topic, true);
            card.created_at = created_at;
            registry.save_knowledge_card(&card).unwrap();
            let hash = crate::quality::knowledge_card_quality_hash(&card);
            seed_quality_pass(&registry, &card, &hash);
            cards.push(card);
        }

        let build = registry
            .build_dataset_draft(KNOWLEDGE_WEB_DATASET_KIND, Utc::now())
            .unwrap();
        assert_eq!(build.decision_count, 2);
        assert_eq!(build.shards.len(), 1, "one group resolves to one shard");
        let compressed = registry.get_object(&build.shards[0].object_hash).unwrap();
        let jsonl = zstd::stream::decode_all(Cursor::new(compressed)).unwrap();
        let text = String::from_utf8(jsonl).unwrap();
        let splits: Vec<String> = text
            .lines()
            .map(|line| {
                serde_json::from_str::<Value>(line).unwrap()["split"]
                    .as_str()
                    .unwrap()
                    .to_string()
            })
            .collect();
        assert_eq!(splits.len(), 2);
        assert_eq!(
            splits[0], splits[1],
            "cross-month records of one group must share a split"
        );
        // The manifest declares the real grouping policy.
        let manifest: Value =
            serde_json::from_slice(&registry.get_object(&build.manifest_hash).unwrap()).unwrap();
        assert_eq!(
            manifest["split_policy"],
            "source_domain_topic_family_earliest_month_v1"
        );
    }

    #[test]
    fn bogus_dataset_kind_still_bails() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        assert!(registry.build_dataset_draft("bogus", Utc::now()).is_err());
        assert!(registry.list_dataset_builds("bogus", 10).is_err());
        assert!(registry.get_dataset_draft("bogus").is_err());
    }

    #[test]
    fn build_audit_get_and_list_paths() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        registry
            .record_meta_decision(&trace("example.com", "rust", true))
            .unwrap();
        let build = registry
            .build_dataset_draft(META_DATASET_KIND, Utc::now())
            .unwrap();

        let fetched = registry.get_dataset_build(build.build_id).unwrap().unwrap();
        assert_eq!(fetched.bundle_hash, build.bundle_hash);
        assert!(
            registry
                .get_dataset_build(Uuid::new_v4())
                .unwrap()
                .is_none()
        );
        assert_eq!(
            registry
                .list_dataset_builds(META_DATASET_KIND, 10)
                .unwrap()
                .len(),
            1
        );
        // the limit clamps to at least one row
        assert_eq!(
            registry
                .list_dataset_builds(META_DATASET_KIND, 0)
                .unwrap()
                .len(),
            1
        );
        // a kind without a draft is None, not an error
        assert!(
            registry
                .get_dataset_draft(KNOWLEDGE_WEB_DATASET_KIND)
                .unwrap()
                .is_none()
        );

        // auditing requires an actor and a reason and lands in the audit ledger
        assert!(
            registry
                .audit_dataset_build(build.build_id, " ", "reason", Utc::now())
                .is_err()
        );
        assert!(
            registry
                .audit_dataset_build(build.build_id, "admin", "", Utc::now())
                .is_err()
        );
        registry
            .audit_dataset_build(build.build_id, "admin", "manual rebuild", Utc::now())
            .unwrap();
        let count: i64 = registry
            .lock_conn()
            .query_row(
                "SELECT COUNT(*) FROM learning_audit
                 WHERE subject_type='dataset_build' AND subject_id=?1
                   AND action='manual_build' AND actor='admin'",
                params![build.build_id.to_string()],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(count, 1);
    }

    #[test]
    fn expert_views_and_assignments_are_listed_per_build() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        registry
            .record_meta_decision(&trace("a.example", "rust", true))
            .unwrap();
        registry
            .record_meta_decision(&trace("b.example", "go", true))
            .unwrap();
        let build = registry
            .build_dataset_draft(META_DATASET_KIND, Utc::now())
            .unwrap();
        let view_id = build.expert_view_id.expect("meta builds carry a view");

        let view = registry.get_expert_dataset_view(view_id).unwrap().unwrap();
        assert_eq!(view.build_id, build.build_id);
        assert!(
            registry
                .get_expert_dataset_view(Uuid::new_v4())
                .unwrap()
                .is_none()
        );
        let by_build = registry
            .get_expert_dataset_view_for_build(build.build_id)
            .unwrap()
            .unwrap();
        assert_eq!(by_build.view_id, view_id);
        assert!(
            registry
                .get_expert_dataset_view_for_build(Uuid::new_v4())
                .unwrap()
                .is_none()
        );
        assert_eq!(registry.list_expert_dataset_views(10).unwrap().len(), 1);

        let assignments = registry.list_expert_assignments(view_id, 100).unwrap();
        assert_eq!(assignments.len() as u64, view.assignment_count);
        assert_eq!(assignments.len(), 2);
        assert!(
            assignments
                .iter()
                .all(|assignment| !assignment.record_hash.is_empty()
                    && !assignment.primary_expert_id.is_empty())
        );
        assert!(
            registry
                .list_expert_assignments(Uuid::new_v4(), 100)
                .unwrap()
                .is_empty()
        );

        // knowledge-web builds never carry an expert view
        let web = registry
            .build_dataset_draft(KNOWLEDGE_WEB_DATASET_KIND, Utc::now())
            .unwrap();
        assert!(web.expert_view_id.is_none());
        assert!(
            registry
                .get_expert_dataset_view_for_build(web.build_id)
                .unwrap()
                .is_none()
        );
        assert_eq!(registry.list_expert_dataset_views(10).unwrap().len(), 1);
    }

    #[test]
    fn snapshot_freeze_get_list_and_revoke_paths() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        registry
            .record_meta_decision(&trace("example.com", "rust", true))
            .unwrap();
        let build = registry
            .build_dataset_draft(META_DATASET_KIND, Utc::now())
            .unwrap();

        // freeze input validation
        let bad_kind = CreateDatasetSnapshotRequest {
            kind: "bogus".into(),
            build_id: None,
            created_by: "admin".into(),
            reason: "test".into(),
        };
        assert!(
            registry
                .freeze_dataset_snapshot(&bad_kind, Utc::now())
                .is_err()
        );
        let no_actor = CreateDatasetSnapshotRequest {
            kind: META_DATASET_KIND.into(),
            build_id: None,
            created_by: " ".into(),
            reason: "test".into(),
        };
        assert!(
            registry
                .freeze_dataset_snapshot(&no_actor, Utc::now())
                .is_err()
        );
        let no_reason = CreateDatasetSnapshotRequest {
            kind: META_DATASET_KIND.into(),
            build_id: None,
            created_by: "admin".into(),
            reason: " ".into(),
        };
        assert!(
            registry
                .freeze_dataset_snapshot(&no_reason, Utc::now())
                .is_err()
        );
        let missing_build = CreateDatasetSnapshotRequest {
            kind: META_DATASET_KIND.into(),
            build_id: Some(Uuid::new_v4()),
            created_by: "admin".into(),
            reason: "test".into(),
        };
        let error = registry
            .freeze_dataset_snapshot(&missing_build, Utc::now())
            .unwrap_err();
        assert_eq!(error.to_string(), "dataset build not found");
        let no_draft = CreateDatasetSnapshotRequest {
            kind: KNOWLEDGE_WEB_DATASET_KIND.into(),
            build_id: None,
            created_by: "admin".into(),
            reason: "test".into(),
        };
        let error = registry
            .freeze_dataset_snapshot(&no_draft, Utc::now())
            .unwrap_err();
        assert_eq!(error.to_string(), "dataset draft not found");
        let wrong_kind = CreateDatasetSnapshotRequest {
            kind: KNOWLEDGE_WEB_DATASET_KIND.into(),
            build_id: Some(build.build_id),
            created_by: "admin".into(),
            reason: "test".into(),
        };
        let error = registry
            .freeze_dataset_snapshot(&wrong_kind, Utc::now())
            .unwrap_err();
        assert_eq!(
            error.to_string(),
            "dataset build kind does not match snapshot request"
        );

        // freezing against an explicit build binds the snapshot to it
        let frozen = registry
            .freeze_dataset_snapshot(
                &CreateDatasetSnapshotRequest {
                    kind: META_DATASET_KIND.into(),
                    build_id: Some(build.build_id),
                    created_by: "admin".into(),
                    reason: "pin".into(),
                },
                Utc::now(),
            )
            .unwrap();
        assert_eq!(frozen.snapshot.build_id, build.build_id);
        assert!(frozen.revocation.is_none());
        let fetched = registry
            .get_dataset_snapshot(frozen.snapshot.snapshot_id)
            .unwrap()
            .unwrap();
        assert_eq!(fetched.snapshot, frozen.snapshot);
        assert!(
            registry
                .get_dataset_snapshot(Uuid::new_v4())
                .unwrap()
                .is_none()
        );
        assert_eq!(registry.list_dataset_snapshots(None).unwrap().len(), 1);
        assert_eq!(
            registry
                .list_dataset_snapshots(Some(META_DATASET_KIND))
                .unwrap()
                .len(),
            1
        );
        assert!(
            registry
                .list_dataset_snapshots(Some(KNOWLEDGE_WEB_DATASET_KIND))
                .unwrap()
                .is_empty()
        );
        assert!(registry.list_dataset_snapshots(Some("bogus")).is_err());

        // revocation validation and transitions
        let blank_actor = RevokeDatasetSnapshotRequest {
            actor: " ".into(),
            reason: "x".into(),
        };
        assert!(
            registry
                .revoke_dataset_snapshot(frozen.snapshot.snapshot_id, &blank_actor, Utc::now())
                .is_err()
        );
        let missing = RevokeDatasetSnapshotRequest {
            actor: "admin".into(),
            reason: "x".into(),
        };
        let error = registry
            .revoke_dataset_snapshot(Uuid::new_v4(), &missing, Utc::now())
            .unwrap_err();
        assert_eq!(error.to_string(), "dataset snapshot not found");
        let revoked = registry
            .revoke_dataset_snapshot(
                frozen.snapshot.snapshot_id,
                &RevokeDatasetSnapshotRequest {
                    actor: "admin".into(),
                    reason: "license revoked upstream".into(),
                },
                Utc::now(),
            )
            .unwrap();
        let revocation = revoked.revocation.expect("revocation recorded");
        assert_eq!(revocation.actor, "admin");
        assert_eq!(revoked.snapshot, frozen.snapshot);
        assert_eq!(
            registry
                .get_dataset_snapshot(frozen.snapshot.snapshot_id)
                .unwrap()
                .unwrap()
                .revocation
                .unwrap()
                .reason,
            "license revoked upstream"
        );
        assert_eq!(
            registry.list_dataset_snapshots(None).unwrap()[0]
                .revocation
                .as_ref()
                .unwrap()
                .snapshot_id,
            frozen.snapshot.snapshot_id
        );
        let error = registry
            .revoke_dataset_snapshot(
                frozen.snapshot.snapshot_id,
                &RevokeDatasetSnapshotRequest {
                    actor: "admin".into(),
                    reason: "again".into(),
                },
                Utc::now(),
            )
            .unwrap_err();
        assert_eq!(error.to_string(), "dataset snapshot is already revoked");
    }

    #[test]
    fn prune_keeps_recent_draft_and_snapshotted_builds() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        // fixed start so each build lands on a distinct Shanghai day
        let start = DateTime::parse_from_rfc3339("2026-01-01T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let mut oldest = None;
        let mut second_oldest = None;
        for day in 0..32 {
            let build = registry
                .build_dataset_draft(
                    KNOWLEDGE_WEB_DATASET_KIND,
                    start + chrono::Duration::days(day),
                )
                .unwrap();
            if day == 0 {
                oldest = Some(build.build_id);
            }
            if day == 1 {
                second_oldest = Some(build.build_id);
            }
        }
        assert_eq!(
            registry
                .list_dataset_builds(KNOWLEDGE_WEB_DATASET_KIND, 10_000)
                .unwrap()
                .len(),
            32
        );
        // a frozen snapshot pins its build forever
        registry
            .freeze_dataset_snapshot(
                &CreateDatasetSnapshotRequest {
                    kind: KNOWLEDGE_WEB_DATASET_KIND.into(),
                    build_id: Some(oldest.unwrap()),
                    created_by: "admin".into(),
                    reason: "pin oldest".into(),
                },
                start,
            )
            .unwrap();

        let pruned = registry
            .prune_dataset_builds(KNOWLEDGE_WEB_DATASET_KIND)
            .unwrap();
        assert_eq!(pruned, 1);
        assert_eq!(
            registry
                .list_dataset_builds(KNOWLEDGE_WEB_DATASET_KIND, 10_000)
                .unwrap()
                .len(),
            31
        );
        assert!(
            registry
                .get_dataset_build(oldest.unwrap())
                .unwrap()
                .is_some()
        );
        assert!(
            registry
                .get_dataset_build(second_oldest.unwrap())
                .unwrap()
                .is_none()
        );
        // the live draft is never pruned
        let draft = registry
            .get_dataset_draft(KNOWLEDGE_WEB_DATASET_KIND)
            .unwrap()
            .unwrap();
        assert!(
            registry
                .get_dataset_build(draft.build_id)
                .unwrap()
                .is_some()
        );
        // a second prune is a no-op
        assert_eq!(
            registry
                .prune_dataset_builds(KNOWLEDGE_WEB_DATASET_KIND)
                .unwrap(),
            0
        );
        assert!(registry.prune_dataset_builds("bogus").is_err());
    }

    #[test]
    fn prune_meta_kind_builds_with_expert_views_deletes_derived_rows_first() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        registry
            .record_meta_decision(&trace("example.com", "rust", true))
            .unwrap();
        let start = DateTime::parse_from_rfc3339("2026-01-01T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        for day in 0..32 {
            registry
                .build_dataset_draft(META_DATASET_KIND, start + chrono::Duration::days(day))
                .unwrap_or_else(|error| panic!("day {day}: {error:#}"));
        }
        let pruned = registry.prune_dataset_builds(META_DATASET_KIND).unwrap();
        assert_eq!(pruned, 2);
    }
}
