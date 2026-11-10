use crate::{Registry, text};
use anyhow::{Result, anyhow, bail};
use cerebellum_core::{
    AcquisitionAttempt, AcquisitionMethod, AcquisitionOutcome, AcquisitionPlan,
    AcquisitionPlanStatus, AcquisitionStatus, AcquisitionWorkerResult, CreateSourcePolicyRequest,
    CreateTopicWatchRequest, DataClassification, DocumentEnvelope, ExternalProcessingPermission,
    KnowledgeCard, KnowledgeResult, KnowledgeRetrieveRequest, KnowledgeRetrieveResponse,
    KnowledgeStatus, MetaDecisionTrace, MetaTaskKind, SCHEMA_VERSION, SourceAccessMode, SourceKind,
    SourcePolicy, TopicWatch, canonical_json_hash, license_allows_automatic_training,
    validate_acquisition_attempt, validate_acquisition_plan, validate_document_envelope,
    validate_knowledge_card, validate_source_policy, validate_topic_watch,
};
use chrono::{DateTime, Utc};
use regex::Regex;
use rusqlite::{OptionalExtension, params};
use sha2::{Digest, Sha256};
use std::{fs, sync::LazyLock};
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourceCursor {
    pub cursor: Option<String>,
    pub etag: Option<String>,
    pub last_modified: Option<String>,
    pub next_poll_at: Option<DateTime<Utc>>,
    pub updated_at: DateTime<Utc>,
}

type SourceCursorRow = (
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
    String,
);

#[derive(Debug, Clone, serde::Serialize)]
pub struct SourceTombstoneReport {
    pub source_policy_id: Uuid,
    pub documents_tombstoned: usize,
    pub knowledge_revisions_created: usize,
    pub cas_objects_removed: usize,
    pub tombstoned_at: DateTime<Utc>,
}

impl Registry {
    pub fn create_topic_watch(&self, request: &CreateTopicWatchRequest) -> Result<TopicWatch> {
        let now = Utc::now();
        let watch = TopicWatch {
            schema_version: SCHEMA_VERSION.into(),
            topic_id: Uuid::new_v4(),
            name: request.name.trim().to_owned(),
            query: request.query.trim().to_owned(),
            keywords: normalize_terms(&request.keywords),
            entities: normalize_terms(&request.entities),
            languages: normalize_terms(&request.languages),
            source_policy_ids: request.source_policy_ids.clone(),
            refresh_seconds: request.refresh_seconds,
            budget: request.budget.clone(),
            enabled: request.enabled,
            created_at: now,
            updated_at: now,
        };
        validate_topic_watch(&watch)?;
        let json = serde_json::to_string(&watch)?;
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO topic_watches(id,name,enabled,watch_json,created_at,updated_at)
             VALUES(?1,?2,?3,?4,?5,?6)",
            params![
                watch.topic_id.to_string(),
                watch.name,
                watch.enabled as i64,
                json,
                watch.created_at.to_rfc3339(),
                watch.updated_at.to_rfc3339()
            ],
        )?;
        Ok(watch)
    }

    pub fn get_topic_watch(&self, id: Uuid) -> Result<Option<TopicWatch>> {
        self.read_json_optional(
            "SELECT watch_json FROM topic_watches WHERE id=?1",
            id.to_string(),
        )
    }

    pub fn list_topic_watches(&self, enabled_only: bool) -> Result<Vec<TopicWatch>> {
        let conn = self.lock_conn();
        let sql = if enabled_only {
            "SELECT watch_json FROM topic_watches WHERE enabled=1 ORDER BY name,id"
        } else {
            "SELECT watch_json FROM topic_watches ORDER BY name,id"
        };
        let mut statement = conn.prepare(sql)?;
        let rows = statement.query_map([], |row| row.get::<_, String>(0))?;
        decode_rows(rows)
    }

    pub fn create_source_policy(
        &self,
        request: &CreateSourcePolicyRequest,
    ) -> Result<SourcePolicy> {
        let now = Utc::now();
        let policy = SourcePolicy {
            schema_version: SCHEMA_VERSION.into(),
            policy_id: Uuid::new_v4(),
            name: request.name.trim().to_owned(),
            kind: request.kind,
            base_url: request.base_url.trim().to_owned(),
            access_mode: request.access_mode,
            allowed_domains: normalize_domains(&request.allowed_domains),
            obey_robots: request.obey_robots,
            max_depth: request.max_depth,
            max_pages_per_run: request.max_pages_per_run,
            rate_limit_per_minute: request.rate_limit_per_minute,
            raw_retention_days: request.raw_retention_days,
            training_license: request.training_license.clone(),
            model_terms_allow_training: request.model_terms_allow_training,
            auth_secret_ref: request.auth_secret_ref.clone(),
            data_classification: request.data_classification,
            external_processing: request.external_processing,
            enabled: request.enabled,
            created_at: now,
            updated_at: now,
        };
        validate_source_policy(&policy)?;
        let json = serde_json::to_string(&policy)?;
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO source_policies(id,kind,enabled,policy_json,created_at,updated_at)
             VALUES(?1,?2,?3,?4,?5,?6)",
            params![
                policy.policy_id.to_string(),
                source_kind_name(policy.kind),
                policy.enabled as i64,
                json,
                policy.created_at.to_rfc3339(),
                policy.updated_at.to_rfc3339()
            ],
        )?;
        Ok(policy)
    }

    pub fn get_source_policy(&self, id: Uuid) -> Result<Option<SourcePolicy>> {
        self.read_json_optional(
            "SELECT policy_json FROM source_policies WHERE id=?1",
            id.to_string(),
        )
    }

    pub fn list_source_policies(&self, enabled_only: bool) -> Result<Vec<SourcePolicy>> {
        let conn = self.lock_conn();
        let sql = if enabled_only {
            "SELECT policy_json FROM source_policies WHERE enabled=1 ORDER BY kind,id"
        } else {
            "SELECT policy_json FROM source_policies ORDER BY kind,id"
        };
        let mut statement = conn.prepare(sql)?;
        let rows = statement.query_map([], |row| row.get::<_, String>(0))?;
        decode_rows(rows)
    }

    pub fn list_knowledge_cards(&self, limit: usize) -> Result<Vec<KnowledgeCard>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT card_json FROM knowledge_cards k
             WHERE revision=(SELECT MAX(revision) FROM knowledge_cards k2 WHERE k2.card_id=k.card_id)
             ORDER BY created_at DESC,card_id LIMIT ?1",
        )?;
        let rows = statement.query_map(params![limit as i64], |row| row.get::<_, String>(0))?;
        decode_rows(rows)
    }

    pub fn list_documents(&self, limit: usize) -> Result<Vec<DocumentEnvelope>> {
        let conn = self.lock_conn();
        let mut statement = conn.prepare(
            "SELECT document_json FROM documents WHERE tombstoned=0
             ORDER BY created_at DESC,id LIMIT ?1",
        )?;
        let rows = statement.query_map(params![limit as i64], |row| row.get::<_, String>(0))?;
        decode_rows(rows)
    }

    pub fn save_acquisition_plan(&self, plan: &AcquisitionPlan) -> Result<()> {
        validate_acquisition_plan(plan)?;
        let json = serde_json::to_string(plan)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT plan_json FROM acquisition_plans WHERE id=?1",
                params![plan.plan_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == json {
                return Ok(());
            }
            bail!("acquisition plan ids are immutable");
        }
        conn.execute(
            "INSERT INTO acquisition_plans(id,topic_id,status,plan_json,created_at,updated_at)
             VALUES(?1,?2,?3,?4,?5,?6)",
            params![
                plan.plan_id.to_string(),
                plan.topic_id.to_string(),
                plan_status_name(plan.status),
                json,
                plan.created_at.to_rfc3339(),
                Utc::now().to_rfc3339()
            ],
        )?;
        Ok(())
    }

    pub fn get_acquisition_plan(&self, id: Uuid) -> Result<Option<AcquisitionPlan>> {
        self.read_json_optional(
            "SELECT plan_json FROM acquisition_plans WHERE id=?1",
            id.to_string(),
        )
    }

    pub fn save_acquisition_attempt(&self, attempt: &AcquisitionAttempt) -> Result<()> {
        validate_acquisition_attempt(attempt)?;
        let json = serde_json::to_string(attempt)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT attempt_json FROM acquisition_attempts WHERE id=?1",
                params![attempt.attempt_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == json {
                return Ok(());
            }
            bail!("acquisition attempt ids are immutable");
        }
        conn.execute(
            "INSERT INTO acquisition_attempts(
               id,plan_id,source_policy_id,canonical_url,method,outcome,attempt_json,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8)",
            params![
                attempt.attempt_id.to_string(),
                attempt.plan_id.to_string(),
                attempt.source_policy_id.to_string(),
                attempt.canonical_url,
                acquisition_method_name(attempt.method),
                acquisition_outcome_name(attempt.outcome),
                json,
                attempt.finished_at.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    pub fn save_document(
        &self,
        document: &DocumentEnvelope,
        cleaned_content: &[u8],
        raw_content: Option<&[u8]>,
    ) -> Result<()> {
        validate_document_envelope(document)?;
        let cleaned_hash = self.put_object(cleaned_content)?;
        if cleaned_hash != document.cleaned_content_hash {
            bail!("cleaned document hash does not match supplied content");
        }
        match (&document.raw_content_hash, raw_content) {
            (Some(expected), Some(raw)) if self.put_object(raw)? == *expected => {}
            (Some(_), Some(_)) => bail!("raw document hash does not match supplied content"),
            (None, None) => {}
            _ => bail!("raw document hash and supplied content must agree"),
        }
        let value = serde_json::to_value(document)?;
        let content_hash = canonical_json_hash(&value);
        let json = serde_json::to_string(document)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT content_hash FROM documents WHERE id=?1",
                params![document.document_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == content_hash {
                return Ok(());
            }
            bail!("document ids are immutable");
        }
        conn.execute(
            "INSERT INTO documents(
               id,source_policy_id,canonical_url,cleaned_content_hash,raw_content_hash,
               raw_expires_at,training_eligible,tombstoned,document_json,content_hash,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)",
            params![
                document.document_id.to_string(),
                document.source_policy_id.to_string(),
                document.canonical_url,
                document.cleaned_content_hash,
                document.raw_content_hash,
                document.raw_expires_at.to_rfc3339(),
                document.rights.training_eligible as i64,
                document.tombstoned as i64,
                json,
                content_hash,
                document.fetched_at.to_rfc3339()
            ],
        )?;
        drop(conn);
        if let Err(error) = crate::events::ingest_board_document(self, document) {
            tracing::warn!(%error, document_id=%document.document_id, "event threading ingest failed");
        }
        Ok(())
    }

    pub fn get_document(&self, id: Uuid) -> Result<Option<DocumentEnvelope>> {
        let conn = self.lock_conn();
        let row: Option<(String, i64, Option<String>)> = conn
            .query_row(
                "SELECT document_json,tombstoned,raw_content_hash FROM documents WHERE id=?1",
                params![id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()?;
        row.map(|(json, tombstoned, raw_hash)| {
            let mut document: DocumentEnvelope = serde_json::from_str(&json)?;
            document.tombstoned = tombstoned != 0;
            document.raw_content_hash = raw_hash;
            if document.tombstoned {
                document.rights.training_eligible = false;
            }
            Ok(document)
        })
        .transpose()
    }

    fn read_json_optional<T: serde::de::DeserializeOwned>(
        &self,
        sql: &str,
        id: String,
    ) -> Result<Option<T>> {
        let conn = self.lock_conn();
        let value: Option<String> = conn
            .query_row(sql, params![id], |row| row.get(0))
            .optional()?;
        value
            .map(|json| serde_json::from_str(&json).map_err(Into::into))
            .transpose()
    }
}

impl Registry {
    /// Promote the latest revision of a knowledge card to training eligibility
    /// after it cleared the model quality gate. Fail-closed no-ops: the
    /// assessed revision is no longer latest (a newer revision needs its own
    /// assessment), the card is already eligible, or any deterministic
    /// precondition (corroborated, low-risk, supports-only, eligible evidence
    /// documents) fails. On success a new contiguous revision with
    /// `training_eligible=true` is saved; the save path re-enforces every
    /// invariant, so promotion can never mint an ineligible training record.
    pub fn promote_knowledge_card_eligibility(
        &self,
        card_id: &str,
        assessed_hash: &str,
    ) -> Result<bool> {
        let row: Option<(String, String, i64)> = {
            let conn = self.lock_conn();
            conn.query_row(
                "SELECT k.card_json,k.content_hash,k.training_eligible FROM knowledge_cards k
                 WHERE k.card_id=?1
                   AND k.revision=(SELECT MAX(k2.revision) FROM knowledge_cards k2
                     WHERE k2.card_id=k.card_id)",
                params![card_id],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()?
        };
        let Some((json, _stored_hash, eligible)) = row else {
            return Ok(false);
        };
        if eligible != 0 {
            return Ok(false);
        }
        let mut card: KnowledgeCard = serde_json::from_str(&json)?;
        // 与评估记录比对时使用质量身份（剔除 revision/created_at/flag 的哈希）
        if crate::quality::knowledge_card_quality_hash(&card) != assessed_hash {
            return Ok(false);
        }
        if !crate::quality::knowledge_card_promotion_preconditions(&card) {
            return Ok(false);
        }
        {
            let conn = self.lock_conn();
            for evidence in &card.evidence {
                let doc_eligible: Option<i64> = conn
                    .query_row(
                        "SELECT training_eligible FROM documents
                         WHERE id=?1 AND tombstoned=0",
                        params![evidence.document_id.to_string()],
                        |row| row.get(0),
                    )
                    .optional()?;
                if doc_eligible != Some(1) {
                    return Ok(false);
                }
            }
        }
        card.revision += 1;
        card.training_eligible = true;
        card.created_at = Utc::now();
        self.save_knowledge_card(&card)?;
        Ok(true)
    }

    pub fn save_knowledge_card(&self, card: &KnowledgeCard) -> Result<()> {
        validate_knowledge_card(card)?;
        if card.training_eligible {
            let conn = self.lock_conn();
            for evidence in &card.evidence {
                let eligible: Option<i64> = conn
                    .query_row(
                        "SELECT training_eligible FROM documents
                         WHERE id=?1 AND tombstoned=0",
                        params![evidence.document_id.to_string()],
                        |row| row.get(0),
                    )
                    .optional()?;
                if eligible != Some(1) {
                    bail!("training-eligible card references ineligible evidence");
                }
            }
        }

        let value = serde_json::to_value(card)?;
        let content_hash = canonical_json_hash(&value);
        let json = serde_json::to_string(card)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT content_hash FROM knowledge_cards WHERE card_id=?1 AND revision=?2",
                params![card.card_id.to_string(), card.revision],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == content_hash {
                return Ok(());
            }
            bail!("knowledge card revisions are immutable");
        }
        let latest: Option<u32> = conn.query_row(
            "SELECT MAX(revision) FROM knowledge_cards WHERE card_id=?1",
            params![card.card_id.to_string()],
            |row| row.get(0),
        )?;
        match latest {
            None if card.revision != 1 => bail!("first knowledge card revision must be 1"),
            Some(revision) if card.revision != revision + 1 => {
                bail!("knowledge card revisions must be contiguous")
            }
            _ => {}
        }

        let transaction = conn.unchecked_transaction()?;
        // A newer revision supersedes every earlier revision of this card.
        // Status is lifecycle metadata: content and content_hash stay
        // untouched while both read surfaces (column and card_json) reflect
        // the supersession.
        let mut statement = transaction.prepare(
            "SELECT revision,card_json FROM knowledge_cards
             WHERE card_id=?1 AND revision<?2 AND status<>'superseded'",
        )?;
        let outdated: Vec<(i64, String)> = statement
            .query_map(params![card.card_id.to_string(), card.revision], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        drop(statement);
        for (revision, outdated_json) in outdated {
            let mut parsed: KnowledgeCard = serde_json::from_str(&outdated_json)?;
            parsed.status = KnowledgeStatus::Superseded;
            transaction.execute(
                "UPDATE knowledge_cards SET status='superseded',card_json=?3
                 WHERE card_id=?1 AND revision=?2",
                params![
                    card.card_id.to_string(),
                    revision,
                    serde_json::to_string(&parsed)?
                ],
            )?;
        }
        transaction.execute(
            "INSERT INTO knowledge_cards(
               card_id,revision,status,title,summary,observed_at,valid_until,
               training_eligible,card_json,content_hash,created_at
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)",
            params![
                card.card_id.to_string(),
                card.revision,
                knowledge_status_name(card.status),
                card.title,
                card.summary,
                card.observed_at.to_rfc3339(),
                card.valid_until.map(|value| value.to_rfc3339()),
                card.training_eligible as i64,
                json,
                content_hash,
                card.created_at.to_rfc3339()
            ],
        )?;
        let entities = card.entities.join(" ");
        let claims = card
            .claims
            .iter()
            .map(|claim| format!("{} {} {}", claim.subject, claim.predicate, claim.object))
            .collect::<Vec<_>>()
            .join(" ");
        transaction.execute(
            "INSERT INTO knowledge_fts(card_key,title,summary,entities,claims)
             VALUES(?1,?2,?3,?4,?5)",
            params![
                format!("{}:{}", card.card_id, card.revision),
                fts_text(&card.title),
                fts_text(&card.summary),
                fts_text(&entities),
                fts_text(&claims)
            ],
        )?;
        transaction.execute(
            "INSERT INTO knowledge_embeddings(
               card_id,revision,model,dimensions,vector,created_at
             ) VALUES(?1,?2,'feature-hash-v1',64,?3,?4)",
            params![
                card.card_id.to_string(),
                card.revision,
                encode_embedding(&card_embedding(card)),
                card.created_at.to_rfc3339()
            ],
        )?;
        transaction.commit()?;
        Ok(())
    }

    pub fn get_knowledge_card(&self, id: Uuid) -> Result<Option<KnowledgeCard>> {
        Ok(self.get_knowledge_card_history(id)?.pop())
    }

    pub fn get_knowledge_card_history(&self, id: Uuid) -> Result<Vec<KnowledgeCard>> {
        let conn = self.lock_conn();
        let mut statement = conn
            .prepare("SELECT card_json FROM knowledge_cards WHERE card_id=?1 ORDER BY revision")?;
        let rows = statement.query_map(params![id.to_string()], |row| row.get::<_, String>(0))?;
        let mut cards: Vec<KnowledgeCard> = decode_rows(rows)?;
        let tombstoned = {
            let mut statement = conn.prepare("SELECT id FROM documents WHERE tombstoned=1")?;
            statement
                .query_map([], |row| row.get::<_, String>(0))?
                .filter_map(|row| row.ok())
                .filter_map(|value| Uuid::parse_str(&value).ok())
                .collect::<std::collections::BTreeSet<_>>()
        };
        if !tombstoned.is_empty() {
            for card in &mut cards {
                let mut redacted = false;
                for evidence in &mut card.evidence {
                    if tombstoned.contains(&evidence.document_id) {
                        evidence.excerpt = None;
                        redacted = true;
                    }
                }
                if redacted {
                    card.training_eligible = false;
                }
            }
        }
        Ok(cards)
    }

    pub fn retrieve_knowledge(
        &self,
        request: &KnowledgeRetrieveRequest,
    ) -> Result<KnowledgeRetrieveResponse> {
        if request.limit == 0 || request.limit > 100 {
            bail!("knowledge retrieval limit must be between 1 and 100");
        }
        let as_of = request.as_of.unwrap_or_else(Utc::now);
        let query = fts_query(&request.query);
        let candidate_limit = (request.limit.saturating_mul(20)).clamp(100, 2_000);
        let query_embedding = text_embedding(&request.query);
        let since = request.since.map(|since| since.to_rfc3339());
        let statuses_json = if request.statuses.is_empty() {
            None
        } else {
            Some(serde_json::to_string(
                &request
                    .statuses
                    .iter()
                    .map(|status| knowledge_status_name(*status))
                    .collect::<Vec<_>>(),
            )?)
        };
        let candidates: Vec<(String, f64, Option<Vec<u8>>)> = {
            let conn = self.lock_conn();
            if query.is_empty() {
                let mut statement = conn.prepare(
                    "SELECT k.card_json,0.0,e.vector FROM knowledge_cards k
                     LEFT JOIN knowledge_embeddings e
                       ON e.card_id=k.card_id AND e.revision=k.revision
                     WHERE k.revision=(
                       SELECT MAX(k2.revision) FROM knowledge_cards k2
                       WHERE k2.card_id=k.card_id
                     )
                       AND (?2 IS NULL OR k.observed_at>=?2)
                       AND (?3 IS NULL OR k.observed_at<=?3)
                       AND (?4 IS NULL OR k.status IN (SELECT value FROM json_each(?4)))
                     ORDER BY k.observed_at DESC,k.card_id LIMIT ?1",
                )?;
                let rows = statement.query_map(
                    params![
                        candidate_limit as i64,
                        since,
                        as_of.to_rfc3339(),
                        statuses_json
                    ],
                    |row| {
                        Ok((
                            row.get::<_, String>(0)?,
                            row.get::<_, f64>(1)?,
                            row.get::<_, Option<Vec<u8>>>(2)?,
                        ))
                    },
                )?;
                rows.collect::<std::result::Result<Vec<_>, _>>()?
            } else {
                let mut statement = conn.prepare(
                    "WITH ranked AS MATERIALIZED (
                       SELECT card_key,bm25(knowledge_fts) AS score FROM knowledge_fts
                       WHERE knowledge_fts MATCH ?1
                       ORDER BY bm25(knowledge_fts)
                       LIMIT ?2
                     )
                     SELECT k.card_json,ranked.score,e.vector FROM ranked
                     JOIN knowledge_cards k
                       ON k.card_id=substr(ranked.card_key,1,36)
                      AND k.revision=CAST(substr(ranked.card_key,38) AS INTEGER)
                     LEFT JOIN knowledge_embeddings e
                       ON e.card_id=k.card_id AND e.revision=k.revision
                     WHERE k.revision=(
                         SELECT MAX(k2.revision) FROM knowledge_cards k2
                         WHERE k2.card_id=k.card_id
                       )
                       AND (?3 IS NULL OR k.observed_at>=?3)
                       AND (?4 IS NULL OR k.observed_at<=?4)
                       AND (?5 IS NULL OR k.status IN (SELECT value FROM json_each(?5)))
                     ORDER BY ranked.score,k.observed_at DESC,k.card_id",
                )?;
                let rows = statement.query_map(
                    params![
                        query,
                        candidate_limit as i64,
                        since,
                        as_of.to_rfc3339(),
                        statuses_json
                    ],
                    |row| {
                        Ok((
                            row.get::<_, String>(0)?,
                            row.get::<_, f64>(1)?,
                            row.get::<_, Option<Vec<u8>>>(2)?,
                        ))
                    },
                )?;
                rows.collect::<std::result::Result<Vec<_>, _>>()?
            }
        };

        // bm25() 返回负值且越负匹配越好；以候选集内的最佳 rank 为基准，
        // 使最佳文本匹配得分为 1.0，并随 rank 差距单调衰减。
        // 空（退化）查询走 recency 分支，保持 None，文本分取中性 0.5。
        let best_rank = if query.is_empty() {
            None
        } else {
            candidates
                .iter()
                .map(|(_, rank, _)| *rank)
                .min_by(f64::total_cmp)
        };
        let mut items = Vec::new();
        for (json, rank, embedding) in candidates {
            let card: KnowledgeCard = serde_json::from_str(&json)?;
            if !request.topic_ids.is_empty()
                && !card
                    .topic_ids
                    .iter()
                    .any(|topic| request.topic_ids.contains(topic))
            {
                continue;
            }
            let stale = card.valid_until.is_some_and(|until| until < as_of)
                || request.freshness_hours.is_some_and(|hours| {
                    card.observed_at + chrono::Duration::hours(i64::from(hours)) < as_of
                });
            let text_score = match best_rank {
                None => 0.5,
                Some(best_rank) => 1.0 / (1.0 + (rank - best_rank)),
            };
            let embedding_score = embedding
                .as_deref()
                .and_then(decode_embedding)
                .map(|embedding| cosine_similarity(&query_embedding, &embedding))
                .unwrap_or(0.0)
                .max(0.0);
            let score = (0.45 * text_score
                + 0.10 * embedding_score
                + 0.20 * card.scores.confidence
                + 0.15 * card.scores.relevance
                + 0.10 * card.scores.novelty
                - 0.20 * card.scores.risk)
                .clamp(0.0, 1.0);
            items.push(KnowledgeResult { card, score, stale });
        }
        items.sort_by(|left, right| {
            right
                .score
                .total_cmp(&left.score)
                .then_with(|| right.card.observed_at.cmp(&left.card.observed_at))
                .then_with(|| left.card.card_id.cmp(&right.card.card_id))
        });
        items.truncate(request.limit);
        Ok(KnowledgeRetrieveResponse {
            registry_snapshot: self.registry_snapshot()?,
            items,
        })
    }

    pub fn rebuild_knowledge_embeddings(&self) -> Result<usize> {
        // Read the card list under the lock, compute every embedding off-lock
        // (the heavy part), then swap the table in one short transaction so
        // readers are blocked for milliseconds, not for the full rebuild.
        let cards = {
            let conn = self.lock_conn();
            let mut statement =
                conn.prepare("SELECT card_json FROM knowledge_cards ORDER BY card_id,revision")?;
            let rows = statement.query_map([], |row| row.get::<_, String>(0))?;
            decode_rows::<KnowledgeCard, _>(rows)?
        };
        let now = Utc::now().to_rfc3339();
        let embeddings: Vec<(String, i64, Vec<u8>)> = cards
            .iter()
            .map(|card| {
                (
                    card.card_id.to_string(),
                    i64::from(card.revision),
                    encode_embedding(&card_embedding(card)),
                )
            })
            .collect();
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        transaction.execute("DELETE FROM knowledge_embeddings", [])?;
        for (card_id, revision, vector) in &embeddings {
            transaction.execute(
                "INSERT INTO knowledge_embeddings(
                   card_id,revision,model,dimensions,vector,created_at
                 ) VALUES(?1,?2,'feature-hash-v1',64,?3,?4)",
                params![card_id, revision, vector, now],
            )?;
        }
        transaction.commit()?;
        Ok(cards.len())
    }
}

impl Registry {
    pub fn acquisition_status(&self) -> Result<AcquisitionStatus> {
        let conn = self.lock_conn();
        let count = |sql: &str| -> Result<u64> {
            Ok(conn.query_row(sql, [], |row| row.get::<_, i64>(0))? as u64)
        };
        let last_success: Option<String> = conn.query_row(
            "SELECT MAX(created_at) FROM acquisition_attempts WHERE outcome='success'",
            [],
            |row| row.get(0),
        )?;
        Ok(AcquisitionStatus {
            active_topics: count("SELECT COUNT(*) FROM topic_watches WHERE enabled=1")?,
            enabled_sources: count("SELECT COUNT(*) FROM source_policies WHERE enabled=1")?,
            document_count: count("SELECT COUNT(*) FROM documents")?,
            knowledge_card_count: count(
                "SELECT COUNT(*) FROM knowledge_cards k WHERE revision=(
                   SELECT MAX(k2.revision) FROM knowledge_cards k2 WHERE k2.card_id=k.card_id
                 )",
            )?,
            pending_jobs: count(
                "SELECT COUNT(*) FROM learning_jobs WHERE status IN ('pending','leased')",
            )?,
            dead_letter_jobs: count(
                "SELECT COUNT(*) FROM learning_jobs WHERE status='dead_letter'",
            )?,
            last_success_at: last_success.map(|value| parse_time(&value)).transpose()?,
        })
    }

    pub fn get_source_cursor(&self, policy_id: Uuid) -> Result<Option<SourceCursor>> {
        let conn = self.lock_conn();
        let row: Option<SourceCursorRow> = conn
            .query_row(
                "SELECT cursor,etag,last_modified,next_poll_at,updated_at
                 FROM source_cursors WHERE policy_id=?1",
                params![policy_id.to_string()],
                |row| {
                    Ok((
                        row.get(0)?,
                        row.get(1)?,
                        row.get(2)?,
                        row.get(3)?,
                        row.get(4)?,
                    ))
                },
            )
            .optional()?;
        row.map(|(cursor, etag, last_modified, next_poll_at, updated_at)| {
            Ok(SourceCursor {
                cursor,
                etag,
                last_modified,
                next_poll_at: next_poll_at.map(|value| parse_time(&value)).transpose()?,
                updated_at: parse_time(&updated_at)?,
            })
        })
        .transpose()
    }

    pub fn upsert_source_cursor(
        &self,
        policy_id: Uuid,
        cursor: Option<&str>,
        etag: Option<&str>,
        last_modified: Option<&str>,
        next_poll_at: Option<DateTime<Utc>>,
    ) -> Result<()> {
        if self.get_source_policy(policy_id)?.is_none() {
            bail!("source policy not found");
        }
        let now = Utc::now();
        let conn = self.lock_conn();
        conn.execute(
            "INSERT INTO source_cursors(
               policy_id,cursor,etag,last_modified,next_poll_at,updated_at
             ) VALUES(?1,?2,?3,?4,?5,?6)
             ON CONFLICT(policy_id) DO UPDATE SET
               cursor=excluded.cursor,etag=excluded.etag,last_modified=excluded.last_modified,
               next_poll_at=excluded.next_poll_at,updated_at=excluded.updated_at",
            params![
                policy_id.to_string(),
                cursor,
                etag,
                last_modified,
                next_poll_at.map(|value| value.to_rfc3339()),
                now.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    pub fn retention_gc(&self, now: DateTime<Utc>) -> Result<usize> {
        let expired: Vec<(String, Option<String>)> = {
            let conn = self.lock_conn();
            let mut statement = conn.prepare(
                "SELECT id,raw_content_hash FROM documents
                 WHERE tombstoned=0 AND raw_content_hash IS NOT NULL AND raw_expires_at<=?1",
            )?;
            let rows = statement.query_map(params![now.to_rfc3339()], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, Option<String>>(1)?))
            })?;
            rows.collect::<std::result::Result<Vec<_>, _>>()?
        };
        let mut removed = 0;
        for (document_id, hash) in expired {
            let Some(hash) = hash else { continue };
            let referenced_elsewhere: i64 = {
                let conn = self.lock_conn();
                conn.query_row(
                    "SELECT COUNT(*) FROM documents
                     WHERE id<>?1 AND tombstoned=0
                       AND (raw_content_hash=?2 OR cleaned_content_hash=?2)",
                    params![document_id, hash],
                    |row| row.get(0),
                )?
            };
            if referenced_elsewhere == 0 && valid_sha256(&hash) {
                let path = self.object_dir.join(&hash[..2]).join(&hash);
                if path.exists() {
                    fs::remove_file(path)?;
                    removed += 1;
                }
            }
            let conn = self.lock_conn();
            conn.execute(
                "UPDATE documents SET raw_content_hash=NULL WHERE id=?1",
                params![document_id],
            )?;
            conn.execute(
                "INSERT OR IGNORE INTO document_tombstones(
                   document_id,raw_content_hash,reason,tombstoned_at
                 ) VALUES(?1,?2,'retention_expired',?3)",
                params![document_id, hash, now.to_rfc3339()],
            )?;
        }
        Ok(removed)
    }

    pub fn tombstone_source_policy(
        &self,
        policy_id: Uuid,
        actor: &str,
        reason: &str,
    ) -> Result<SourceTombstoneReport> {
        if actor.trim().is_empty() {
            bail!("source tombstone requires an actor");
        }
        if reason.trim().is_empty() {
            bail!("source tombstone requires a reason");
        }
        let mut policy = self
            .get_source_policy(policy_id)?
            .ok_or_else(|| anyhow!("source policy not found"))?;
        let now = Utc::now();
        let documents: Vec<(Uuid, Option<String>, String)> = {
            let conn = self.lock_conn();
            let mut statement = conn.prepare(
                "SELECT id,raw_content_hash,cleaned_content_hash FROM documents
                 WHERE source_policy_id=?1 AND tombstoned=0",
            )?;
            statement
                .query_map(params![policy_id.to_string()], |row| {
                    let id: String = row.get(0)?;
                    Ok((id, row.get(1)?, row.get(2)?))
                })?
                .map(|row| {
                    let (id, raw, cleaned) = row?;
                    Ok((Uuid::parse_str(&id)?, raw, cleaned))
                })
                .collect::<Result<Vec<_>>>()?
        };
        policy.enabled = false;
        policy.updated_at = now;
        {
            let mut conn = self.lock_conn();
            let transaction = conn.transaction()?;
            transaction.execute(
                "UPDATE source_policies SET enabled=0,policy_json=?2,updated_at=?3 WHERE id=?1",
                params![
                    policy_id.to_string(),
                    serde_json::to_string(&policy)?,
                    now.to_rfc3339()
                ],
            )?;
            for (document_id, raw_hash, _) in &documents {
                transaction.execute(
                    "UPDATE documents SET tombstoned=1,training_eligible=0,raw_content_hash=NULL
                     WHERE id=?1",
                    params![document_id.to_string()],
                )?;
                transaction.execute(
                    "INSERT INTO document_tombstones(
                       document_id,raw_content_hash,reason,tombstoned_at
                     ) VALUES(?1,?2,?3,?4)
                     ON CONFLICT(document_id) DO UPDATE SET
                       raw_content_hash=COALESCE(document_tombstones.raw_content_hash,excluded.raw_content_hash),
                       reason=excluded.reason,tombstoned_at=excluded.tombstoned_at",
                    params![
                        document_id.to_string(),
                        raw_hash,
                        format!("source_deleted:{}", reason.trim()),
                        now.to_rfc3339()
                    ],
                )?;
            }
            Self::audit_conn(
                &transaction,
                "source_policy",
                &policy_id.to_string(),
                "tombstone",
                actor.trim(),
                reason.trim(),
                now,
            )?;
            transaction.commit()?;
        }

        let removed_ids = documents
            .iter()
            .map(|(id, _, _)| *id)
            .collect::<std::collections::BTreeSet<_>>();
        let tombstoned_ids = {
            let conn = self.lock_conn();
            let mut statement = conn.prepare("SELECT id FROM documents WHERE tombstoned=1")?;
            statement
                .query_map([], |row| row.get::<_, String>(0))?
                .filter_map(|row| row.ok())
                .filter_map(|value| Uuid::parse_str(&value).ok())
                .collect::<std::collections::BTreeSet<_>>()
        };
        let latest_cards: Vec<KnowledgeCard> = {
            let conn = self.lock_conn();
            let mut statement = conn.prepare(
                "SELECT k.card_json FROM knowledge_cards k
                 WHERE k.revision=(SELECT MAX(k2.revision) FROM knowledge_cards k2
                   WHERE k2.card_id=k.card_id)
                 ORDER BY k.card_id",
            )?;
            decode_rows(statement.query_map([], |row| row.get::<_, String>(0))?)?
        };
        let mut revisions = 0;
        for mut card in latest_cards.into_iter().filter(|card| {
            card.evidence
                .iter()
                .any(|evidence| removed_ids.contains(&evidence.document_id))
        }) {
            for evidence in &mut card.evidence {
                if tombstoned_ids.contains(&evidence.document_id) {
                    evidence.excerpt = None;
                }
            }
            let active = card
                .evidence
                .iter()
                .filter(|evidence| !tombstoned_ids.contains(&evidence.document_id))
                .collect::<Vec<_>>();
            let supporting_domains = active
                .iter()
                .filter(|evidence| {
                    evidence.relationship == cerebellum_core::EvidenceRelationship::Supports
                })
                .filter_map(|evidence| {
                    url::Url::parse(&evidence.canonical_url)
                        .ok()
                        .and_then(|url| url.host_str().map(str::to_owned))
                })
                .collect::<std::collections::BTreeSet<_>>()
                .len();
            card.revision += 1;
            card.supersedes = Some(card.card_id);
            card.status = if active.is_empty()
                || active.iter().any(|evidence| {
                    evidence.relationship == cerebellum_core::EvidenceRelationship::Retracts
                }) {
                KnowledgeStatus::Retracted
            } else if active.iter().any(|evidence| {
                evidence.relationship == cerebellum_core::EvidenceRelationship::Opposes
            }) {
                KnowledgeStatus::Contested
            } else if supporting_domains >= 2 {
                KnowledgeStatus::Corroborated
            } else {
                KnowledgeStatus::Unverified
            };
            if active.is_empty() {
                card.scores.confidence = card.scores.confidence.min(0.3);
                card.scores.risk = card.scores.risk.max(0.5);
            }
            card.training_eligible = false;
            card.created_at = now;
            self.save_knowledge_card(&card)?;
            revisions += 1;
        }

        let mut hashes = documents
            .iter()
            .flat_map(|(_, raw, cleaned)| raw.iter().chain(std::iter::once(cleaned)))
            .cloned()
            .collect::<Vec<_>>();
        hashes.sort();
        hashes.dedup();
        let mut cas_objects_removed = 0;
        for hash in hashes {
            let referenced: i64 = {
                let conn = self.lock_conn();
                conn.query_row(
                    "SELECT COUNT(*) FROM documents WHERE tombstoned=0
                     AND (raw_content_hash=?1 OR cleaned_content_hash=?1)",
                    params![hash],
                    |row| row.get(0),
                )?
            };
            if referenced == 0 && valid_sha256(&hash) {
                let path = self.object_dir.join(&hash[..2]).join(&hash);
                if path.exists() {
                    fs::remove_file(path)?;
                    cas_objects_removed += 1;
                }
            }
        }
        Ok(SourceTombstoneReport {
            source_policy_id: policy_id,
            documents_tombstoned: documents.len(),
            knowledge_revisions_created: revisions,
            cas_objects_removed,
            tombstoned_at: now,
        })
    }
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

fn stable_meta_uuid(value: &[u8]) -> Uuid {
    let digest = Sha256::digest(value);
    let mut bytes = [0_u8; 16];
    bytes.copy_from_slice(&digest[..16]);
    bytes[6] = (bytes[6] & 0x0f) | 0x50;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    Uuid::from_bytes(bytes)
}

fn validate_worker_document_policy(
    document: &DocumentEnvelope,
    cleaned_content: &[u8],
    raw_content: Option<&[u8]>,
    policy: &SourcePolicy,
    acquisition_succeeded: bool,
) -> Result<()> {
    for value in [&document.url, &document.canonical_url] {
        let canonical = text::canonicalize_public_url(value, &policy.allowed_domains)?;
        if value == &document.canonical_url && canonical != document.canonical_url {
            bail!("worker document canonical URL is not normalized");
        }
    }
    let content = std::str::from_utf8(cleaned_content)
        .map_err(|_| anyhow!("cleaned worker content must be UTF-8"))?;
    let injection = text::detects_prompt_injection(content);
    let pii = LIKELY_PII.is_match(content);
    let secret = LIKELY_SECRET.is_match(content);
    if (injection && !document.prompt_injection_detected)
        || (pii && !document.pii_detected)
        || (secret && !document.secret_detected)
    {
        bail!("worker omitted a deterministic content safety finding");
    }
    if (document.pii_detected
        || document.secret_detected
        || policy.access_mode == SourceAccessMode::AuthenticatedLocal)
        && (raw_content.is_some() || document.raw_content_hash.is_some())
    {
        bail!("sensitive or authenticated-local documents cannot retain raw content");
    }
    let expected_training = policy.text_training_allowed()
        && acquisition_succeeded
        && !document.prompt_injection_detected
        && !document.pii_detected
        && !document.secret_detected;
    let expected_redistribution = policy
        .training_license
        .as_deref()
        .is_some_and(license_allows_automatic_training);
    if document.rights.license != policy.training_license
        || !document.rights.retrieval_allowed
        || !document.rights.storage_allowed
        || document.rights.redistribution_allowed != expected_redistribution
        || document.rights.explicit_training_permission != expected_training
        || document.rights.model_terms_allow_training != policy.model_terms_allow_training
        || document.rights.training_eligible != expected_training
        || document.rights.rights_source != format!("source_policy:{}", policy.policy_id)
    {
        bail!("worker document rights differ from the registered source policy");
    }
    let maximum_expiry =
        document.fetched_at + chrono::Duration::days(i64::from(policy.raw_retention_days));
    if document.raw_expires_at > maximum_expiry {
        bail!("worker document exceeds the source raw-retention policy");
    }
    Ok(())
}

pub(crate) static LIKELY_PII: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\+?\d[\d ()-]{7,}\d")
        .expect("fixed PII regex")
});

pub(crate) static LIKELY_SECRET: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)-----BEGIN PRIVATE KEY-----|\b(?:sk|pk)-[a-z0-9_-]{16,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bAKIA[0-9A-Z]{16}\b|authorization:\s*bearer\s+\S+|(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret)\s*[:=]\s*\S{12,}",
    )
    .expect("fixed secret regex")
});

fn normalize_terms(values: &[String]) -> Vec<String> {
    let mut values = values
        .iter()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .collect::<Vec<_>>();
    values.sort_by_key(|value| value.to_lowercase());
    values.dedup_by(|left, right| left.eq_ignore_ascii_case(right));
    values
}

fn normalize_domains(values: &[String]) -> Vec<String> {
    normalize_terms(values)
        .into_iter()
        .map(|value| value.trim_end_matches('.').to_ascii_lowercase())
        .collect()
}

fn card_embedding(card: &KnowledgeCard) -> [f32; 64] {
    let claims = card
        .claims
        .iter()
        .map(|claim| format!("{} {} {}", claim.subject, claim.predicate, claim.object))
        .collect::<Vec<_>>()
        .join(" ");
    text_embedding(&format!(
        "{} {} {} {}",
        card.title,
        card.summary,
        card.entities.join(" "),
        claims
    ))
}

fn text_embedding(value: &str) -> [f32; 64] {
    let mut vector = [0.0_f32; 64];
    for token in crate::text::tokenize_text(value) {
        let digest = Sha256::digest(token.as_bytes());
        let index = usize::from(digest[0]) % vector.len();
        let sign = if digest[1] & 1 == 0 { 1.0 } else { -1.0 };
        vector[index] += sign;
    }
    let norm = vector.iter().map(|value| value * value).sum::<f32>().sqrt();
    if norm > 0.0 {
        for value in &mut vector {
            *value /= norm;
        }
    }
    vector
}

fn encode_embedding(vector: &[f32; 64]) -> Vec<u8> {
    vector
        .iter()
        .flat_map(|value| value.to_le_bytes())
        .collect()
}

fn decode_embedding(value: &[u8]) -> Option<[f32; 64]> {
    if value.len() != 64 * std::mem::size_of::<f32>() {
        return None;
    }
    let mut vector = [0.0_f32; 64];
    for (index, chunk) in value.as_chunks::<4>().0.iter().enumerate() {
        vector[index] = f32::from_le_bytes(*chunk);
    }
    Some(vector)
}

fn cosine_similarity(left: &[f32; 64], right: &[f32; 64]) -> f64 {
    left.iter()
        .zip(right.iter())
        .map(|(left, right)| f64::from(*left) * f64::from(*right))
        .sum::<f64>()
        .clamp(-1.0, 1.0)
}

fn fts_query(query: &str) -> String {
    crate::text::tokenize_text(query)
        .iter()
        .map(|term| crate::text::fts_query_escape(term))
        .collect::<Vec<_>>()
        .join(" AND ")
}

/// FTS index text: the same token stream MATCH queries are built from, so a
/// CJK passage is indexed as searchable bigrams instead of one opaque token.
fn fts_text(value: &str) -> String {
    crate::text::tokenize_text(value).join(" ")
}

fn parse_time(value: &str) -> Result<DateTime<Utc>> {
    Ok(DateTime::parse_from_rfc3339(value)
        .map_err(|error| anyhow!("invalid stored timestamp: {error}"))?
        .with_timezone(&Utc))
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64 && value.chars().all(|character| character.is_ascii_hexdigit())
}

fn source_kind_name(kind: SourceKind) -> &'static str {
    match kind {
        SourceKind::Github => "github",
        SourceKind::HackerNews => "hacker_news",
        SourceKind::RssAtom => "rss_atom",
        SourceKind::Tavily => "tavily",
        SourceKind::Firecrawl => "firecrawl",
        SourceKind::Crawl4ai => "crawl4ai",
        SourceKind::Scrapling => "scrapling",
        SourceKind::OpenCli => "open_cli",
        SourceKind::Http => "http",
        SourceKind::Weibo => "weibo",
        SourceKind::Zhihu => "zhihu",
        SourceKind::Douyin => "douyin",
        SourceKind::Bilibili => "bilibili",
        SourceKind::Xhs => "xhs",
        SourceKind::Baidu => "baidu",
        SourceKind::Kuaishou => "kuaishou",
        SourceKind::Tieba => "tieba",
        SourceKind::OpenAlex => "openalex",
        SourceKind::Arxiv => "arxiv",
        SourceKind::Journal => "journal",
    }
}

fn plan_status_name(status: AcquisitionPlanStatus) -> &'static str {
    match status {
        AcquisitionPlanStatus::Pending => "pending",
        AcquisitionPlanStatus::Running => "running",
        AcquisitionPlanStatus::Completed => "completed",
        AcquisitionPlanStatus::Failed => "failed",
        AcquisitionPlanStatus::Cancelled => "cancelled",
    }
}

fn acquisition_method_name(method: AcquisitionMethod) -> &'static str {
    match method {
        AcquisitionMethod::Api => "api",
        AcquisitionMethod::Rss => "rss",
        AcquisitionMethod::DirectHttp => "direct_http",
        AcquisitionMethod::Crawl4ai => "crawl4ai",
        AcquisitionMethod::Firecrawl => "firecrawl",
        AcquisitionMethod::LinkMapper => "link_mapper",
        AcquisitionMethod::Scrapling => "scrapling",
        AcquisitionMethod::Mediacrawler => "mediacrawler",
        AcquisitionMethod::OpenCli => "open_cli",
    }
}

fn acquisition_outcome_name(outcome: AcquisitionOutcome) -> &'static str {
    match outcome {
        AcquisitionOutcome::Success => "success",
        AcquisitionOutcome::PartialContent => "partial_content",
        AcquisitionOutcome::JsShell => "js_shell",
        AcquisitionOutcome::ParseFailed => "parse_failed",
        AcquisitionOutcome::RateLimited => "rate_limited",
        AcquisitionOutcome::Timeout => "timeout",
        AcquisitionOutcome::ServerError => "server_error",
        AcquisitionOutcome::AuthRequired => "auth_required",
        AcquisitionOutcome::RobotsDenied => "robots_denied",
        AcquisitionOutcome::Captcha => "captcha",
        AcquisitionOutcome::ExplicitChallenge => "explicit_challenge",
        AcquisitionOutcome::PolicyDenied => "policy_denied",
        AcquisitionOutcome::NotFound => "not_found",
        AcquisitionOutcome::Gone => "gone",
    }
}

fn knowledge_status_name(status: KnowledgeStatus) -> &'static str {
    match status {
        KnowledgeStatus::Unverified => "unverified",
        KnowledgeStatus::Corroborated => "corroborated",
        KnowledgeStatus::Contested => "contested",
        KnowledgeStatus::Superseded => "superseded",
        KnowledgeStatus::Retracted => "retracted",
    }
}

#[cfg(test)]
#[allow(clippy::items_after_test_module)]
mod tests {
    use super::*;
    use cerebellum_core::{
        AcquisitionAttempt, AcquisitionMethod, AcquisitionOutcome, AcquisitionPlan,
        AcquisitionPlanStatus, AcquisitionWorkerResult, CreateSourcePolicyRequest,
        CreateTopicWatchRequest, DocumentRights, EvidenceRelationship, KnowledgeClaim,
        KnowledgeEvidenceRef, KnowledgeScores, KnowledgeStatus, SourceAccessMode, SourceKind,
        TopicBudget,
    };
    use chrono::Duration;
    use sha2::{Digest, Sha256};
    use tempfile::tempdir;

    fn hash(content: &[u8]) -> String {
        format!("{:x}", Sha256::digest(content))
    }

    fn seed_source(registry: &Registry) -> SourcePolicy {
        registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "Test RSS".into(),
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
            .unwrap()
    }

    fn seed_topic(registry: &Registry, source: Uuid) -> TopicWatch {
        registry
            .create_topic_watch(&CreateTopicWatchRequest {
                name: "Agent memory".into(),
                query: "agent memory workflow".into(),
                keywords: vec!["workflow".into(), "agent".into()],
                entities: vec!["Cerebellum".into()],
                languages: vec!["en".into(), "zh".into()],
                source_policy_ids: vec![source],
                refresh_seconds: 120,
                budget: Default::default(),
                enabled: true,
            })
            .unwrap()
    }

    fn document(
        topic: Uuid,
        source: Uuid,
        fetched_at: DateTime<Utc>,
        cleaned: &[u8],
        raw: &[u8],
    ) -> DocumentEnvelope {
        DocumentEnvelope {
            schema_version: SCHEMA_VERSION.into(),
            document_id: Uuid::new_v4(),
            topic_ids: vec![topic],
            source_policy_id: source,
            external_id: Some("story-1".into()),
            url: "https://example.com/posts/agent-memory".into(),
            canonical_url: "https://example.com/posts/agent-memory".into(),
            author: Some("Example".into()),
            title: "Agent workflow memory improves verification".into(),
            published_at: Some(fetched_at - Duration::hours(1)),
            observed_at: fetched_at,
            fetched_at,
            raw_content_hash: Some(hash(raw)),
            cleaned_content_hash: hash(cleaned),
            extraction_method: AcquisitionMethod::Rss,
            extractor_version: "test-v1".into(),
            language: "en".into(),
            content_type: "text/markdown".into(),
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
            raw_expires_at: fetched_at + Duration::days(30),
            tombstoned: false,
            metadata: serde_json::json!({"fixture": true}),
        }
    }

    fn card(document: &DocumentEnvelope, topic: Uuid) -> KnowledgeCard {
        KnowledgeCard {
            schema_version: SCHEMA_VERSION.into(),
            card_id: Uuid::new_v4(),
            revision: 1,
            topic_ids: vec![topic],
            title: document.title.clone(),
            summary: "Fresh verification improves workflow reliability.".into(),
            entities: vec!["Agent".into(), "workflow memory".into()],
            claims: vec![KnowledgeClaim {
                claim_id: Uuid::new_v4(),
                subject: "fresh verification".into(),
                predicate: "improves".into(),
                object: "workflow reliability".into(),
                valid_from: document.published_at,
                valid_until: None,
                confidence: 0.8,
            }],
            evidence: vec![KnowledgeEvidenceRef {
                document_id: document.document_id,
                canonical_url: document.canonical_url.clone(),
                content_hash: document.cleaned_content_hash.clone(),
                excerpt: Some("Verification is run after the final edit.".into()),
                relationship: EvidenceRelationship::Supports,
                observed_at: document.observed_at,
            }],
            status: KnowledgeStatus::Unverified,
            published_at: document.published_at,
            observed_at: document.observed_at,
            valid_until: None,
            supersedes: None,
            model_id: "deterministic-v1".into(),
            prompt_hash: hash(b"prompt-v1"),
            scores: KnowledgeScores {
                relevance: 0.9,
                novelty: 0.7,
                source_reliability: 0.6,
                extraction_completeness: 0.9,
                confidence: 0.8,
                risk: 0.1,
                cost: 0.01,
            },
            training_eligible: false,
            created_at: document.observed_at,
        }
    }

    #[test]
    fn rebuild_embeddings_is_consistent_and_lock_friendly() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let document = document(
            topic.topic_id,
            source.policy_id,
            Utc::now(),
            b"embed me",
            b"raw",
        );
        registry
            .save_document(&document, b"embed me", Some(b"raw"))
            .unwrap();
        let card = card(&document, topic.topic_id);
        registry.save_knowledge_card(&card).unwrap();

        assert_eq!(registry.rebuild_knowledge_embeddings().unwrap(), 1);
        let stored: Vec<u8> = registry
            .lock_conn()
            .query_row(
                "SELECT vector FROM knowledge_embeddings WHERE card_id=?1 AND revision=1",
                params![card.card_id.to_string()],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(stored, encode_embedding(&card_embedding(&card)));
        // Second rebuild: identical rows, no duplicates.
        assert_eq!(registry.rebuild_knowledge_embeddings().unwrap(), 1);
        let count: i64 = registry
            .lock_conn()
            .query_row("SELECT COUNT(*) FROM knowledge_embeddings", [], |row| {
                row.get(0)
            })
            .unwrap();
        assert_eq!(count, 1);

        // A rebuild running concurrently with readers completes without
        // deadlock or read errors (the heavy compute holds no lock).
        let registry = std::sync::Arc::new(registry);
        let writer = {
            let registry = registry.clone();
            std::thread::spawn(move || registry.rebuild_knowledge_embeddings().unwrap())
        };
        for _ in 0..20 {
            registry.list_knowledge_cards(10).unwrap();
        }
        assert_eq!(writer.join().unwrap(), 1);
    }
    #[test]
    fn new_revision_supersedes_prior_revisions() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let now = Utc::now();
        let doc = document(topic.topic_id, source.policy_id, now, b"content", b"raw");
        registry
            .save_document(&doc, b"content", Some(b"raw"))
            .unwrap();

        let first = card(&doc, topic.topic_id);
        registry.save_knowledge_card(&first).unwrap();
        let mut second = first.clone();
        second.revision = 2;
        second.summary = "Updated conclusion replaces the first.".into();
        registry.save_knowledge_card(&second).unwrap();

        // The prior revision reports superseded on every read surface.
        let status: String = registry
            .lock_conn()
            .query_row(
                "SELECT status FROM knowledge_cards WHERE card_id=?1 AND revision=1",
                params![first.card_id.to_string()],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(status, "superseded");
        let history = registry.get_knowledge_card_history(first.card_id).unwrap();
        assert_eq!(history.len(), 2);
        assert_eq!(history[0].status, KnowledgeStatus::Superseded);
        assert_eq!(history[1].status, KnowledgeStatus::Unverified);
        // Retrieval keeps returning only the latest revision.
        let latest = registry.get_knowledge_card(first.card_id).unwrap().unwrap();
        assert_eq!(latest.revision, 2);
        assert_eq!(latest.status, KnowledgeStatus::Unverified);
    }

    #[test]
    fn quality_cleared_card_promotes_only_with_assessed_latest_revision() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let now = Utc::now();
        let mut doc = document(topic.topic_id, source.policy_id, now, b"eligible", b"raw");
        doc.rights.license = Some("CC0-1.0".into());
        doc.rights.redistribution_allowed = true;
        doc.rights.explicit_training_permission = true;
        doc.rights.model_terms_allow_training = true;
        doc.rights.training_eligible = true;
        registry
            .save_document(&doc, b"eligible", Some(b"raw"))
            .unwrap();
        let mut card = card(&doc, topic.topic_id);
        card.status = KnowledgeStatus::Corroborated;
        registry.save_knowledge_card(&card).unwrap();
        let assessed_hash = crate::quality::knowledge_card_quality_hash(&card);

        // hash 不匹配（评估对象已不是最新 revision）→ fail-closed 不晋升
        assert!(
            !registry
                .promote_knowledge_card_eligibility(&card.card_id.to_string(), &hash(b"stale"))
                .unwrap()
        );
        assert_eq!(
            registry
                .get_knowledge_card(card.card_id)
                .unwrap()
                .unwrap()
                .revision,
            1
        );

        // 正确 hash → 晋升：新 contiguous revision，flag 置位
        assert!(
            registry
                .promote_knowledge_card_eligibility(&card.card_id.to_string(), &assessed_hash)
                .unwrap()
        );
        let promoted = registry.get_knowledge_card(card.card_id).unwrap().unwrap();
        assert_eq!(promoted.revision, 2);
        assert!(promoted.training_eligible);
        assert_eq!(promoted.status, KnowledgeStatus::Corroborated);

        // 已晋升 → 幂等 no-op
        assert!(
            !registry
                .promote_knowledge_card_eligibility(&card.card_id.to_string(), &assessed_hash)
                .unwrap()
        );
        assert_eq!(
            registry
                .get_knowledge_card_history(card.card_id)
                .unwrap()
                .len(),
            2
        );
    }

    #[test]
    fn promotion_refuses_unverified_card_and_ineligible_evidence() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let now = Utc::now();
        // 证据文档 training_eligible=false → 前置失败
        let doc = document(
            topic.topic_id,
            source.policy_id,
            now,
            b"not eligible",
            b"raw",
        );
        registry
            .save_document(&doc, b"not eligible", Some(b"raw"))
            .unwrap();
        let mut first_card = card(&doc, topic.topic_id);
        first_card.status = KnowledgeStatus::Corroborated;
        registry.save_knowledge_card(&first_card).unwrap();
        let assessed_hash = crate::quality::knowledge_card_quality_hash(&first_card);
        assert!(
            !registry
                .promote_knowledge_card_eligibility(&first_card.card_id.to_string(), &assessed_hash)
                .unwrap()
        );

        // 证据合格但卡未 corroborated → 前置失败
        let mut doc2 = document(
            topic.topic_id,
            source.policy_id,
            now,
            b"eligible 2",
            b"raw 2",
        );
        doc2.document_id = Uuid::new_v4();
        doc2.rights.license = Some("CC0-1.0".into());
        doc2.rights.redistribution_allowed = true;
        doc2.rights.explicit_training_permission = true;
        doc2.rights.model_terms_allow_training = true;
        doc2.rights.training_eligible = true;
        registry
            .save_document(&doc2, b"eligible 2", Some(b"raw 2"))
            .unwrap();
        let mut card2 = card(&doc2, topic.topic_id);
        card2.status = KnowledgeStatus::Unverified;
        registry.save_knowledge_card(&card2).unwrap();
        let hash2 = crate::quality::knowledge_card_quality_hash(&card2);
        assert!(
            !registry
                .promote_knowledge_card_eligibility(&card2.card_id.to_string(), &hash2)
                .unwrap()
        );
        assert_eq!(
            registry
                .get_knowledge_card(card2.card_id)
                .unwrap()
                .unwrap()
                .revision,
            1
        );
    }

    #[test]
    fn knowledge_round_trip_searches_latest_revision() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let cleaned = b"Agent workflow memory requires fresh verification.";
        let raw = b"<p>Agent workflow memory requires fresh verification.</p>";
        let document = document(topic.topic_id, source.policy_id, Utc::now(), cleaned, raw);
        registry
            .save_document(&document, cleaned, Some(raw))
            .unwrap();
        let first = card(&document, topic.topic_id);
        registry.save_knowledge_card(&first).unwrap();

        let mut second = first.clone();
        second.revision = 2;
        second.summary = "Fresh verification materially improves workflow reliability.".into();
        second.created_at += Duration::seconds(1);
        registry.save_knowledge_card(&second).unwrap();

        let response = registry
            .retrieve_knowledge(&KnowledgeRetrieveRequest {
                query: "workflow verification".into(),
                topic_ids: vec![topic.topic_id],
                statuses: vec![],
                since: None,
                as_of: None,
                freshness_hours: None,
                limit: 10,
            })
            .unwrap();
        assert_eq!(response.items.len(), 1);
        assert_eq!(response.items[0].card.revision, 2);
        assert_eq!(
            registry
                .get_knowledge_card_history(first.card_id)
                .unwrap()
                .len(),
            2
        );
    }

    fn text_heavy_card(
        document: &DocumentEnvelope,
        topic: Uuid,
        title: &str,
        summary: &str,
        entity: &str,
    ) -> KnowledgeCard {
        let mut card = card(document, topic);
        card.title = title.into();
        card.summary = summary.into();
        card.entities = vec![entity.into()];
        card.claims = vec![KnowledgeClaim {
            claim_id: Uuid::new_v4(),
            subject: entity.into(),
            predicate: "describes".into(),
            object: summary.into(),
            valid_from: None,
            valid_until: None,
            confidence: 0.8,
        }];
        card
    }

    #[test]
    fn hybrid_retrieval_ranks_best_text_match_first() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let document = document(
            topic.topic_id,
            source.policy_id,
            Utc::now(),
            b"hybrid ranking",
            b"raw",
        );
        registry
            .save_document(&document, b"hybrid ranking", Some(b"raw"))
            .unwrap();

        // 文本强匹配：查询词在多个索引字段中反复出现，bm25 更负（更好）。
        let strong = text_heavy_card(
            &document,
            topic.topic_id,
            "verification verification verification",
            "verification verification verification verification",
            "verification",
        );
        registry.save_knowledge_card(&strong).unwrap();
        // 文本弱匹配：查询词仅出现一次。
        let weak = text_heavy_card(
            &document,
            topic.topic_id,
            "unrelated operational notes",
            "verification appears once among unrelated operational notes",
            "operations",
        );
        registry.save_knowledge_card(&weak).unwrap();

        let response = registry
            .retrieve_knowledge(&KnowledgeRetrieveRequest {
                query: "verification".into(),
                topic_ids: vec![],
                statuses: vec![],
                since: None,
                as_of: None,
                freshness_hours: None,
                limit: 10,
            })
            .unwrap();
        assert_eq!(response.items.len(), 2);
        assert_eq!(response.items[0].card.card_id, strong.card_id);
        let score_of = |card_id: Uuid| {
            response
                .items
                .iter()
                .find(|item| item.card.card_id == card_id)
                .unwrap()
                .score
        };
        assert!(score_of(strong.card_id) > score_of(weak.card_id));
    }

    #[test]
    fn hybrid_retrieval_candidate_pool_prefers_best_bm25_matches() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let document = document(
            topic.topic_id,
            source.policy_id,
            Utc::now(),
            b"candidate pool",
            b"raw",
        );
        registry
            .save_document(&document, b"candidate pool", Some(b"raw"))
            .unwrap();

        // limit=1 → candidate_limit=100；先插入 120 条弱匹配填满旧实现的
        // 无序 LIMIT 子集，最后插入的最佳匹配在旧实现下会被挤出候选池。
        for index in 0..120 {
            let filler = text_heavy_card(
                &document,
                topic.topic_id,
                &format!("unrelated operational notes {index}"),
                "verification appears once among unrelated operational notes",
                "operations",
            );
            registry.save_knowledge_card(&filler).unwrap();
        }
        let best = text_heavy_card(
            &document,
            topic.topic_id,
            "verification verification verification",
            "verification verification verification verification",
            "verification",
        );
        registry.save_knowledge_card(&best).unwrap();

        let response = registry
            .retrieve_knowledge(&KnowledgeRetrieveRequest {
                query: "verification".into(),
                topic_ids: vec![],
                statuses: vec![],
                since: None,
                as_of: None,
                freshness_hours: None,
                limit: 1,
            })
            .unwrap();
        assert_eq!(response.items.len(), 1);
        assert_eq!(response.items[0].card.card_id, best.card_id);
    }

    #[test]
    fn degenerate_query_uses_neutral_text_score() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let document = document(
            topic.topic_id,
            source.policy_id,
            Utc::now(),
            b"degenerate query",
            b"raw",
        );
        registry
            .save_document(&document, b"degenerate query", Some(b"raw"))
            .unwrap();
        let card = card(&document, topic.topic_id);
        registry.save_knowledge_card(&card).unwrap();

        // 仅由引号组成的原始查询：fts_query 转换后为空，走 recency 分支，
        // 文本分必须是中性 0.5 而不是 1.0。
        let query = "\"\"\"";
        let response = registry
            .retrieve_knowledge(&KnowledgeRetrieveRequest {
                query: query.into(),
                topic_ids: vec![],
                statuses: vec![],
                since: None,
                as_of: None,
                freshness_hours: None,
                limit: 10,
            })
            .unwrap();
        assert_eq!(response.items.len(), 1);
        let embedding_score =
            cosine_similarity(&text_embedding(query), &card_embedding(&card)).max(0.0);
        let expected = (0.45 * 0.5_f64
            + 0.10 * embedding_score
            + 0.20 * card.scores.confidence
            + 0.15 * card.scores.relevance
            + 0.10 * card.scores.novelty
            - 0.20 * card.scores.risk)
            .clamp(0.0, 1.0);
        assert!((response.items[0].score - expected).abs() < 1e-9);
    }

    #[test]
    fn cjk_card_is_found_by_cjk_query() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let document = document(
            topic.topic_id,
            source.policy_id,
            Utc::now(),
            b"cjk content",
            b"raw",
        );
        registry
            .save_document(&document, b"cjk content", Some(b"raw"))
            .unwrap();
        let mut card = card(&document, topic.topic_id);

        card.title = "回归测试提升发布质量".into();
        card.summary = "持续集成中的回归测试如何阻断缺陷发布。".into();
        registry.save_knowledge_card(&card).unwrap();

        // Before CJK-aware indexing this query missed the card: the whole
        // passage was one opaque unicode61 token and one hash vector.
        let request = |query: &str| KnowledgeRetrieveRequest {
            query: query.into(),
            topic_ids: vec![],
            statuses: vec![],
            since: None,
            as_of: None,
            freshness_hours: None,
            limit: 10,
        };
        let response = registry.retrieve_knowledge(&request("回归测试")).unwrap();
        assert!(
            response
                .items
                .iter()
                .any(|item| item.card.card_id == card.card_id),
            "Chinese query must surface the Chinese card"
        );
        // A single CJK character must not panic the query path.
        registry.retrieve_knowledge(&request("修")).unwrap();
    }

    #[test]
    fn retrieval_pushes_status_and_recency_filters_into_sql() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let now = Utc::now();
        let old_document = document(
            topic.topic_id,
            source.policy_id,
            now - Duration::days(10),
            b"old verification report",
            b"raw",
        );
        registry
            .save_document(&old_document, b"old verification report", Some(b"raw"))
            .unwrap();
        let old_card = card(&old_document, topic.topic_id);
        registry.save_knowledge_card(&old_card).unwrap();
        let new_document = document(
            topic.topic_id,
            source.policy_id,
            now,
            b"fresh verification report",
            b"raw",
        );
        registry
            .save_document(&new_document, b"fresh verification report", Some(b"raw"))
            .unwrap();
        let mut corroborated = card(&new_document, topic.topic_id);
        corroborated.status = KnowledgeStatus::Corroborated;
        registry.save_knowledge_card(&corroborated).unwrap();

        let request = |statuses: Vec<KnowledgeStatus>, since| KnowledgeRetrieveRequest {
            query: String::new(),
            topic_ids: vec![],
            statuses,
            since,
            as_of: None,
            freshness_hours: None,
            limit: 10,
        };
        // Status filter in SQL: only the corroborated card survives.
        let response = registry
            .retrieve_knowledge(&request(vec![KnowledgeStatus::Corroborated], None))
            .unwrap();
        assert_eq!(response.items.len(), 1);
        assert_eq!(response.items[0].card.card_id, corroborated.card_id);
        // Recency filter in SQL: the old card drops out.
        let response = registry
            .retrieve_knowledge(&request(vec![], Some(now - Duration::days(1))))
            .unwrap();
        assert_eq!(response.items.len(), 1);
        assert_eq!(response.items[0].card.card_id, corroborated.card_id);
        // Both filters together through the FTS branch keep the same rows.
        let mut queried = request(vec![KnowledgeStatus::Unverified], None);
        queried.query = "verification".into();
        let response = registry.retrieve_knowledge(&queried).unwrap();
        assert_eq!(response.items.len(), 1);
        assert_eq!(response.items[0].card.card_id, old_card.card_id);
    }

    #[test]
    fn retention_removes_only_expired_raw_object() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let fetched_at = Utc::now() - Duration::days(31);
        let cleaned = b"cleaned retained content";
        let raw = b"expired raw content";
        let mut document = document(topic.topic_id, source.policy_id, fetched_at, cleaned, raw);
        document.raw_expires_at = Utc::now() - Duration::hours(1);
        let raw_hash = document.raw_content_hash.clone().unwrap();
        registry
            .save_document(&document, cleaned, Some(raw))
            .unwrap();

        assert_eq!(registry.retention_gc(Utc::now()).unwrap(), 1);
        assert!(registry.get_object(&raw_hash).is_err());
        assert!(registry.get_object(&document.cleaned_content_hash).is_ok());
    }

    #[test]
    fn source_tombstone_redacts_evidence_removes_content_and_records_audit() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let cleaned = b"source content that must be removed";
        let raw = b"<p>source content that must be removed</p>";
        let document = document(topic.topic_id, source.policy_id, Utc::now(), cleaned, raw);
        let raw_hash = document.raw_content_hash.clone().unwrap();
        let cleaned_hash = document.cleaned_content_hash.clone();
        registry
            .save_document(&document, cleaned, Some(raw))
            .unwrap();
        let card = card(&document, topic.topic_id);
        registry.save_knowledge_card(&card).unwrap();

        let report = registry
            .tombstone_source_policy(source.policy_id, "admin@example", "source deletion request")
            .unwrap();
        assert_eq!(report.documents_tombstoned, 1);
        assert_eq!(report.knowledge_revisions_created, 1);
        assert_eq!(report.cas_objects_removed, 2);
        assert!(registry.get_object(&raw_hash).is_err());
        assert!(registry.get_object(&cleaned_hash).is_err());

        let stored = registry
            .get_document(document.document_id)
            .unwrap()
            .unwrap();
        assert!(stored.tombstoned);
        assert!(!stored.rights.training_eligible);
        assert!(stored.raw_content_hash.is_none());
        let history = registry.get_knowledge_card_history(card.card_id).unwrap();
        assert_eq!(history.len(), 2);
        assert_eq!(history.last().unwrap().status, KnowledgeStatus::Retracted);
        assert!(
            history
                .iter()
                .flat_map(|revision| &revision.evidence)
                .all(|evidence| evidence.excerpt.is_none())
        );
        assert!(
            registry
                .list_source_policies(false)
                .unwrap()
                .iter()
                .find(|policy| policy.policy_id == source.policy_id)
                .is_some_and(|policy| !policy.enabled)
        );

        let conn = registry.lock_conn();
        let audit: (String, String, String) = conn
            .query_row(
                "SELECT actor,reason,action FROM learning_audit
                 WHERE subject_type='source_policy' AND subject_id=?1",
                params![source.policy_id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .unwrap();
        assert_eq!(
            audit,
            (
                "admin@example".into(),
                "source deletion request".into(),
                "tombstone".into()
            )
        );
    }

    #[test]
    fn training_card_rejects_ineligible_document() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let cleaned = b"not licensed for training";
        let raw = b"not licensed for training";
        let document = document(topic.topic_id, source.policy_id, Utc::now(), cleaned, raw);
        registry
            .save_document(&document, cleaned, Some(raw))
            .unwrap();
        let mut candidate = card(&document, topic.topic_id);
        candidate.status = KnowledgeStatus::Corroborated;
        candidate.training_eligible = true;
        assert!(registry.save_knowledge_card(&candidate).is_err());
    }

    #[test]
    fn acquisition_worker_cannot_forge_source_license_or_training_eligibility() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let now = Utc::now();
        let plan = AcquisitionPlan {
            schema_version: SCHEMA_VERSION.into(),
            plan_id: Uuid::new_v4(),
            topic_id: topic.topic_id,
            query: "agent".into(),
            source_policy_ids: vec![source.policy_id],
            scheduled_for: now,
            max_documents: 1,
            max_depth: 1,
            status: AcquisitionPlanStatus::Pending,
            created_at: now,
        };
        registry.save_acquisition_plan(&plan).unwrap();
        let job = registry
            .enqueue_learning_job(
                "document_acquire_v1",
                serde_json::json!({
                    "plan_id":plan.plan_id,
                    "topic_ids":[topic.topic_id],
                    "source_policy_id":source.policy_id,
                    "source_policy":source
                }),
                1.0,
                1,
            )
            .unwrap();
        registry
            .claim_learning_job(None, "worker-a", 300)
            .unwrap()
            .unwrap();
        let cleaned = b"objective technical result";
        let raw = b"<p>objective technical result</p>";
        let mut forged = document(topic.topic_id, source.policy_id, now, cleaned, raw);
        forged.rights = DocumentRights {
            license: Some("MIT".into()),
            retrieval_allowed: true,
            storage_allowed: true,
            redistribution_allowed: true,
            explicit_training_permission: true,
            model_terms_allow_training: true,
            training_eligible: true,
            rights_source: format!("source_policy:{}", source.policy_id),
        };
        let attempt = AcquisitionAttempt {
            schema_version: SCHEMA_VERSION.into(),
            attempt_id: Uuid::new_v4(),
            plan_id: plan.plan_id,
            source_policy_id: source.policy_id,
            url: forged.url.clone(),
            canonical_url: forged.canonical_url.clone(),
            method: AcquisitionMethod::DirectHttp,
            outcome: AcquisitionOutcome::Success,
            http_status: Some(200),
            retry_after_seconds: None,
            content_hash: Some(forged.cleaned_content_hash.clone()),
            error_code: None,
            cost: 0.0,
            started_at: now,
            finished_at: now,
        };
        assert!(
            registry
                .save_acquisition_worker_result(
                    &AcquisitionWorkerResult {
                        schema_version: SCHEMA_VERSION.into(),
                        job_id: job.job_id,
                        worker: "worker-a".into(),
                        attempt: attempt.clone(),
                        document: Some(forged.clone()),
                        discovered_urls: vec![],
                        created_at: now,
                    },
                    Some(cleaned),
                    Some(raw),
                )
                .is_err()
        );
        assert!(registry.get_document(forged.document_id).unwrap().is_none());

        forged.rights = DocumentRights {
            license: None,
            retrieval_allowed: true,
            storage_allowed: true,
            redistribution_allowed: false,
            explicit_training_permission: false,
            model_terms_allow_training: false,
            training_eligible: false,
            rights_source: format!("source_policy:{}", source.policy_id),
        };
        registry
            .save_acquisition_worker_result(
                &AcquisitionWorkerResult {
                    schema_version: SCHEMA_VERSION.into(),
                    job_id: job.job_id,
                    worker: "worker-a".into(),
                    attempt,
                    document: Some(forged.clone()),
                    discovered_urls: vec![],
                    created_at: now,
                },
                Some(cleaned),
                Some(raw),
            )
            .unwrap();
        assert!(registry.get_document(forged.document_id).unwrap().is_some());
    }

    #[test]
    fn provider_discovery_enqueues_only_canonical_allowlisted_children() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let now = Utc::now();
        let plan = AcquisitionPlan {
            schema_version: SCHEMA_VERSION.into(),
            plan_id: Uuid::new_v4(),
            topic_id: topic.topic_id,
            query: "agent workflow".into(),
            source_policy_ids: vec![source.policy_id],
            scheduled_for: now,
            max_documents: 10,
            max_depth: 2,
            status: AcquisitionPlanStatus::Pending,
            created_at: now,
        };
        registry.save_acquisition_plan(&plan).unwrap();
        let parent = registry
            .enqueue_learning_job(
                "document_acquire_v1",
                serde_json::json!({
                    "plan_id":plan.plan_id,
                    "topic_ids":[topic.topic_id],
                    "source_policy_id":source.policy_id,
                    "source_policy":source
                }),
                1.0,
                3,
            )
            .unwrap();
        registry
            .claim_learning_job(Some(&["document_acquire_v1"]), "worker-a", 300)
            .unwrap()
            .unwrap();
        let attempt = AcquisitionAttempt {
            schema_version: SCHEMA_VERSION.into(),
            attempt_id: Uuid::new_v4(),
            plan_id: plan.plan_id,
            source_policy_id: source.policy_id,
            url: source.base_url.clone(),
            canonical_url: source.base_url.clone(),
            method: AcquisitionMethod::Firecrawl,
            outcome: AcquisitionOutcome::PartialContent,
            http_status: Some(200),
            retry_after_seconds: None,
            content_hash: None,
            error_code: Some("search_results_only".into()),
            cost: 0.0,
            started_at: now,
            finished_at: now,
        };
        registry
            .save_acquisition_worker_result(
                &AcquisitionWorkerResult {
                    schema_version: SCHEMA_VERSION.into(),
                    job_id: parent.job_id,
                    worker: "worker-a".into(),
                    attempt,
                    document: None,
                    discovered_urls: vec![
                        "https://example.com/post?utm_source=test".into(),
                        "https://example.com/post".into(),
                        "https://evil.example/post".into(),
                        "http://127.0.0.1/private".into(),
                    ],
                    created_at: now,
                },
                None,
                None,
            )
            .unwrap();
        let trace: MetaDecisionTrace = {
            let conn = registry.lock_conn();
            let json: String = conn
                .query_row(
                    "SELECT trace_json FROM meta_decision_traces
                     WHERE task_kind='acquisition_escalation'",
                    [],
                    |row| row.get(0),
                )
                .unwrap();
            serde_json::from_str(&json).unwrap()
        };
        assert_eq!(trace.task_kind, MetaTaskKind::AcquisitionEscalation);
        assert!(trace.training_eligible);
        assert_eq!(trace.output["action"], "store_partial_or_escalate");
        let child = registry
            .claim_learning_job(Some(&["document_acquire_v1"]), "worker-b", 300)
            .unwrap()
            .unwrap();
        assert_ne!(child.job_id, parent.job_id);
        assert_eq!(
            child
                .payload
                .get("canonical_url")
                .and_then(serde_json::Value::as_str),
            Some("https://example.com/post")
        );
        assert!(
            registry
                .claim_learning_job(Some(&["document_acquire_v1"]), "worker-c", 300)
                .unwrap()
                .is_none()
        );
    }

    #[test]
    fn browser_budget_is_atomic_idempotent_and_worker_bound() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let request = CreateTopicWatchRequest {
            name: "Strict browser budget".into(),
            query: "agent".into(),
            keywords: vec![],
            entities: vec![],
            languages: vec!["en".into()],
            source_policy_ids: vec![source.policy_id],
            refresh_seconds: 120,
            budget: TopicBudget {
                browser_escalations_per_day: 1,
                ..Default::default()
            },
            enabled: true,
        };
        let topic = registry.create_topic_watch(&request).unwrap();
        let plan_id = Uuid::new_v4();
        let enqueue = |registry: &Registry| {
            registry
                .enqueue_learning_job(
                    "document_acquire_v1",
                    serde_json::json!({
                        "plan_id":plan_id,
                        "topic_ids":[topic.topic_id],
                        "source_policy_id":source.policy_id,
                        "source_policy":source
                    }),
                    1.0,
                    1,
                )
                .unwrap()
        };
        let first = enqueue(&registry);
        registry
            .claim_learning_job(None, "worker-a", 300)
            .unwrap()
            .unwrap();
        assert!(
            registry
                .reserve_browser_escalation(first.job_id, "forged-worker")
                .is_err()
        );
        assert!(
            registry
                .reserve_browser_escalation(first.job_id, "worker-a")
                .unwrap()
        );
        assert!(
            !registry
                .reserve_browser_escalation(first.job_id, "worker-a")
                .unwrap()
        );
        registry
            .complete_learning_job(first.job_id, "worker-a")
            .unwrap();
        let second = enqueue(&registry);
        registry
            .claim_learning_job(None, "worker-b", 300)
            .unwrap()
            .unwrap();
        assert!(
            registry
                .reserve_browser_escalation(second.job_id, "worker-b")
                .is_err()
        );
    }

    #[test]
    fn source_rate_budget_is_atomic_idempotent_and_worker_bound() {
        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "One request per minute".into(),
                kind: SourceKind::RssAtom,
                base_url: "https://example.com/feed.xml".into(),
                access_mode: SourceAccessMode::Public,
                allowed_domains: vec!["example.com".into()],
                obey_robots: true,
                max_depth: 1,
                max_pages_per_run: 1,
                rate_limit_per_minute: 1,
                raw_retention_days: 30,
                training_license: None,
                model_terms_allow_training: false,
                auth_secret_ref: None,
                data_classification: DataClassification::Public,
                external_processing: ExternalProcessingPermission::Denied,
                enabled: true,
            })
            .unwrap();
        let topic = seed_topic(&registry, source.policy_id);
        let plan = AcquisitionPlan {
            schema_version: SCHEMA_VERSION.into(),
            plan_id: Uuid::new_v4(),
            topic_id: topic.topic_id,
            query: "agent".into(),
            source_policy_ids: vec![source.policy_id],
            scheduled_for: Utc::now(),
            max_documents: 1,
            max_depth: 1,
            status: AcquisitionPlanStatus::Pending,
            created_at: Utc::now(),
        };
        registry.save_acquisition_plan(&plan).unwrap();
        let plan_id = plan.plan_id;
        let enqueue = |registry: &Registry| {
            registry
                .enqueue_learning_job(
                    "document_acquire_v1",
                    serde_json::json!({
                        "plan_id":plan_id,
                        "topic_ids":[topic.topic_id],
                        "source_policy_id":source.policy_id,
                        "source_policy":source
                    }),
                    1.0,
                    1,
                )
                .unwrap()
        };
        let first = enqueue(&registry);
        registry
            .claim_learning_job(None, "worker-a", 300)
            .unwrap()
            .unwrap();
        assert!(
            registry
                .reserve_source_request(first.job_id, "forged-worker", 0)
                .is_err()
        );
        assert!(
            registry
                .reserve_source_request(first.job_id, "worker-a", 0)
                .unwrap()
        );
        assert!(
            !registry
                .reserve_source_request(first.job_id, "worker-a", 0)
                .unwrap()
        );
        let retry_attempt = AcquisitionAttempt {
            schema_version: SCHEMA_VERSION.into(),
            attempt_id: Uuid::new_v4(),
            plan_id,
            source_policy_id: source.policy_id,
            url: source.base_url.clone(),
            canonical_url: source.base_url.clone(),
            method: AcquisitionMethod::DirectHttp,
            outcome: AcquisitionOutcome::Timeout,
            http_status: None,
            retry_after_seconds: Some(60),
            content_hash: None,
            error_code: Some("timeout".into()),
            cost: 0.0,
            started_at: Utc::now(),
            finished_at: Utc::now(),
        };
        registry
            .save_leased_acquisition_attempt(first.job_id, "worker-a", &retry_attempt)
            .unwrap();
        let retry_trace: String = {
            let conn = registry.lock_conn();
            conn.query_row(
                "SELECT trace_json FROM meta_decision_traces WHERE input_hash=?1",
                params![canonical_json_hash(&serde_json::json!({
                    "method":retry_attempt.method,
                    "outcome":retry_attempt.outcome,
                    "http_status_class":serde_json::Value::Null,
                    "source_kind":source.kind,
                    "has_partial_document":false
                }))],
                |row| row.get(0),
            )
            .unwrap()
        };
        assert_eq!(
            serde_json::from_str::<MetaDecisionTrace>(&retry_trace)
                .unwrap()
                .output["action"],
            "retry_same_identity"
        );
        registry
            .fail_learning_job(first.job_id, "worker-a", "fixture complete")
            .unwrap();

        let second = enqueue(&registry);
        registry
            .claim_learning_job(None, "worker-b", 300)
            .unwrap()
            .unwrap();
        assert!(
            registry
                .reserve_source_request(second.job_id, "worker-b", 0)
                .is_err()
        );
    }

    #[test]
    #[ignore = "release-mode 100k-card acceptance benchmark"]
    fn knowledge_retrieval_100k_cards_meets_p95_target() {
        use std::time::Instant;

        let directory = tempdir().unwrap();
        let registry = Registry::open(directory.path()).unwrap();
        let source = seed_source(&registry);
        let topic = seed_topic(&registry, source.policy_id);
        let now = Utc::now();
        let cleaned = b"benchmark fixture";
        let raw = b"benchmark fixture";
        let document = document(topic.topic_id, source.policy_id, now, cleaned, raw);
        let template = card(&document, topic.topic_id);
        {
            let mut conn = registry.lock_conn();
            let transaction = conn.transaction().unwrap();
            for index in 0..100_000_u32 {
                let mut candidate = template.clone();
                candidate.card_id = Uuid::new_v4();
                candidate.title = format!("Agent workflow verification record {index}");
                candidate.summary = format!(
                    "Fresh verification improves workflow reliability in benchmark family {}.",
                    index % 100
                );
                candidate.claims[0].claim_id = Uuid::new_v4();
                candidate.claims[0].object = candidate.summary.clone();
                let json = serde_json::to_string(&candidate).unwrap();
                let content_hash = canonical_json_hash(&serde_json::to_value(&candidate).unwrap());
                transaction
                    .execute(
                        "INSERT INTO knowledge_cards(
                           card_id,revision,status,title,summary,observed_at,valid_until,
                           training_eligible,card_json,content_hash,created_at
                         ) VALUES(?1,1,'unverified',?2,?3,?4,NULL,0,?5,?6,?4)",
                        params![
                            candidate.card_id.to_string(),
                            candidate.title,
                            candidate.summary,
                            now.to_rfc3339(),
                            json,
                            content_hash
                        ],
                    )
                    .unwrap();
                transaction
                    .execute(
                        "INSERT INTO knowledge_fts(card_key,title,summary,entities,claims)
                         VALUES(?1,?2,?3,?4,?5)",
                        params![
                            format!("{}:1", candidate.card_id),
                            fts_text(&candidate.title),
                            fts_text(&candidate.summary),
                            fts_text(&candidate.entities.join(" ")),
                            fts_text(&candidate.claims[0].object)
                        ],
                    )
                    .unwrap();
                transaction
                    .execute(
                        "INSERT INTO knowledge_embeddings(
                           card_id,revision,model,dimensions,vector,created_at
                         ) VALUES(?1,1,'feature-hash-v1',64,?2,?3)",
                        params![
                            candidate.card_id.to_string(),
                            encode_embedding(&card_embedding(&candidate)),
                            now.to_rfc3339()
                        ],
                    )
                    .unwrap();
            }
            transaction.commit().unwrap();
        }
        eprintln!("seeded 100,000 knowledge cards");
        let request = KnowledgeRetrieveRequest {
            query: "workflow verification".into(),
            topic_ids: vec![],
            statuses: vec![],
            since: None,
            as_of: None,
            freshness_hours: None,
            limit: 10,
        };
        let mut latencies = (0..200)
            .map(|_| {
                let started = Instant::now();
                assert_eq!(
                    registry.retrieve_knowledge(&request).unwrap().items.len(),
                    10
                );
                started.elapsed()
            })
            .collect::<Vec<_>>();
        latencies.sort();
        let p95 = latencies[189];
        eprintln!("100k-card retrieval p95: {p95:?}");
        if !cfg!(debug_assertions) {
            assert!(p95 <= std::time::Duration::from_millis(150));
        }
    }
}

impl Registry {
    pub fn reserve_source_poll(&self, policy_id: Uuid, requests: u32) -> Result<()> {
        if requests == 0 {
            bail!("source poll must reserve at least one request");
        }
        let policy = self
            .get_source_policy(policy_id)?
            .ok_or_else(|| anyhow!("source policy not found"))?;
        if !policy.enabled {
            bail!("source policy is disabled");
        }
        let now = Utc::now();
        let minute = now.format("%Y-%m-%dT%H:%M").to_string();
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let current: u64 = transaction
            .query_row(
                "SELECT requests FROM source_rate_usage
                 WHERE minute=?1 AND source_policy_id=?2",
                params![minute, policy_id.to_string()],
                |row| row.get(0),
            )
            .optional()?
            .unwrap_or(0);
        if current.saturating_add(u64::from(requests)) > u64::from(policy.rate_limit_per_minute) {
            bail!("source rate limit exhausted for the current minute");
        }
        transaction.execute(
            "INSERT INTO source_rate_usage(minute,source_policy_id,requests)
             VALUES(?1,?2,?3)
             ON CONFLICT(minute,source_policy_id) DO UPDATE SET requests=requests+excluded.requests",
            params![minute, policy_id.to_string(), requests],
        )?;
        transaction.commit()?;
        Ok(())
    }

    pub fn reserve_source_request(&self, job_id: Uuid, worker: &str, ordinal: u8) -> Result<bool> {
        if worker.trim().is_empty() || ordinal > 15 {
            bail!("source request reservation has invalid identity or ordinal");
        }
        let now = Utc::now();
        let minute = now.format("%Y-%m-%dT%H:%M").to_string();
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let existing: i64 = transaction.query_row(
            "SELECT EXISTS(
               SELECT 1 FROM acquisition_rate_reservations
               WHERE job_id=?1 AND ordinal=?2
             )",
            params![job_id.to_string(), ordinal],
            |row| row.get(0),
        )?;
        if existing != 0 {
            transaction.commit()?;
            return Ok(false);
        }
        let payload: String = transaction
            .query_row(
                "SELECT payload_json FROM learning_jobs
                 WHERE id=?1 AND kind IN ('document_acquire_v1','social_acquisition_v1')
                 AND status='leased'
                 AND lease_owner=?2 AND lease_until>?3",
                params![job_id.to_string(), worker, now.to_rfc3339()],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("source request requires an active worker-owned lease"))?;
        let payload: serde_json::Value = serde_json::from_str(&payload)?;
        let policy_id = payload
            .get("source_policy_id")
            .and_then(serde_json::Value::as_str)
            .and_then(|value| Uuid::parse_str(value).ok())
            .ok_or_else(|| anyhow!("source request job lacks a policy id"))?;
        let policy_json: String = transaction
            .query_row(
                "SELECT policy_json FROM source_policies WHERE id=?1 AND enabled=1",
                params![policy_id.to_string()],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("source policy is missing or disabled"))?;
        let policy: SourcePolicy = serde_json::from_str(&policy_json)?;
        let current: u64 = transaction
            .query_row(
                "SELECT requests FROM source_rate_usage
                 WHERE minute=?1 AND source_policy_id=?2",
                params![minute, policy_id.to_string()],
                |row| row.get(0),
            )
            .optional()?
            .unwrap_or(0);
        if current.saturating_add(1) > u64::from(policy.rate_limit_per_minute) {
            bail!("source rate limit exhausted for the current minute");
        }
        transaction.execute(
            "INSERT INTO source_rate_usage(minute,source_policy_id,requests)
             VALUES(?1,?2,1)
             ON CONFLICT(minute,source_policy_id) DO UPDATE SET requests=requests+1",
            params![minute, policy_id.to_string()],
        )?;
        transaction.execute(
            "INSERT INTO acquisition_rate_reservations(
               job_id,ordinal,source_policy_id,worker,created_at
             ) VALUES(?1,?2,?3,?4,?5)",
            params![
                job_id.to_string(),
                ordinal,
                policy_id.to_string(),
                worker,
                now.to_rfc3339()
            ],
        )?;
        transaction.commit()?;
        Ok(true)
    }

    pub fn save_leased_acquisition_attempt(
        &self,
        job_id: Uuid,
        worker: &str,
        attempt: &AcquisitionAttempt,
    ) -> Result<()> {
        validate_acquisition_attempt(attempt)?;
        let now = Utc::now();
        let conn = self.lock_conn();
        let payload: String = conn
            .query_row(
                "SELECT payload_json FROM learning_jobs
                 WHERE id=?1 AND kind IN ('document_acquire_v1','social_acquisition_v1')
                 AND status='leased'
                 AND lease_owner=?2 AND lease_until>?3",
                params![job_id.to_string(), worker, now.to_rfc3339()],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("attempt requires an active worker-owned lease"))?;
        drop(conn);
        let payload: serde_json::Value = serde_json::from_str(&payload)?;
        let payload_plan = payload
            .get("plan_id")
            .and_then(serde_json::Value::as_str)
            .and_then(|value| Uuid::parse_str(value).ok());
        let payload_source = payload
            .get("source_policy_id")
            .and_then(serde_json::Value::as_str)
            .and_then(|value| Uuid::parse_str(value).ok());
        if payload_plan != Some(attempt.plan_id) || payload_source != Some(attempt.source_policy_id)
        {
            bail!("attempt provenance does not match leased job");
        }
        self.save_acquisition_attempt(attempt)?;
        self.record_acquisition_attempt_meta_trace(
            &payload,
            attempt,
            false,
            false,
            0,
            attempt.finished_at,
        )
    }

    pub fn reserve_browser_escalation(&self, job_id: Uuid, worker: &str) -> Result<bool> {
        if worker.trim().is_empty() {
            bail!("worker id must not be empty");
        }
        let now = Utc::now();
        let day = now.date_naive().to_string();
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let existing: i64 = transaction.query_row(
            "SELECT EXISTS(SELECT 1 FROM acquisition_browser_reservations WHERE job_id=?1)",
            params![job_id.to_string()],
            |row| row.get(0),
        )?;
        if existing != 0 {
            transaction.commit()?;
            return Ok(false);
        }
        let payload: String = transaction
            .query_row(
                "SELECT payload_json FROM learning_jobs
                 WHERE id=?1 AND kind IN ('document_acquire_v1','social_acquisition_v1')
                 AND status='leased'
                 AND lease_owner=?2 AND lease_until>?3",
                params![job_id.to_string(), worker, now.to_rfc3339()],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("browser escalation requires an active worker-owned lease"))?;
        let payload: serde_json::Value = serde_json::from_str(&payload)?;
        let topic_ids = payload
            .get("topic_ids")
            .and_then(serde_json::Value::as_array)
            .into_iter()
            .flatten()
            .map(|value| {
                value
                    .as_str()
                    .ok_or_else(|| anyhow!("topic id must be a string"))
                    .and_then(|value| Uuid::parse_str(value).map_err(Into::into))
            })
            .collect::<Result<Vec<_>>>()?;
        if topic_ids.is_empty() {
            bail!("browser escalation job has no topic budget");
        }
        for topic_id in &topic_ids {
            let watch_json: String = transaction
                .query_row(
                    "SELECT watch_json FROM topic_watches WHERE id=?1 AND enabled=1",
                    params![topic_id.to_string()],
                    |row| row.get(0),
                )
                .optional()?
                .ok_or_else(|| anyhow!("topic watch is missing or disabled"))?;
            let topic: TopicWatch = serde_json::from_str(&watch_json)?;
            let current: u64 = transaction
                .query_row(
                    "SELECT COALESCE(browser_escalations,0) FROM topic_acquisition_usage
                     WHERE day=?1 AND topic_id=?2",
                    params![day, topic_id.to_string()],
                    |row| row.get(0),
                )
                .optional()?
                .unwrap_or(0);
            if current.saturating_add(1) > u64::from(topic.budget.browser_escalations_per_day) {
                bail!("topic browser escalation budget exhausted");
            }
        }
        for topic_id in &topic_ids {
            transaction.execute(
                "INSERT INTO topic_acquisition_usage(
                   day,topic_id,events,documents,browser_escalations,model_tokens
                 ) VALUES(?1,?2,0,0,1,0)
                 ON CONFLICT(day,topic_id) DO UPDATE SET
                   browser_escalations=browser_escalations+1",
                params![day, topic_id.to_string()],
            )?;
        }
        transaction.execute(
            "INSERT INTO acquisition_browser_reservations(job_id,worker,created_at)
             VALUES(?1,?2,?3)",
            params![job_id.to_string(), worker, now.to_rfc3339()],
        )?;
        transaction.commit()?;
        Ok(true)
    }

    pub fn save_acquisition_worker_result(
        &self,
        result: &AcquisitionWorkerResult,
        cleaned_content: Option<&[u8]>,
        raw_content: Option<&[u8]>,
    ) -> Result<String> {
        if result.schema_version != SCHEMA_VERSION || result.worker.trim().is_empty() {
            bail!("invalid acquisition worker result identity");
        }
        validate_acquisition_attempt(&result.attempt)?;
        let (kind, status, lease_owner, lease_until, payload): (
            String,
            String,
            Option<String>,
            Option<String>,
            String,
        ) = {
            let conn = self.lock_conn();
            conn.query_row(
                "SELECT kind,status,lease_owner,lease_until,payload_json
                 FROM learning_jobs WHERE id=?1",
                params![result.job_id.to_string()],
                |row| {
                    Ok((
                        row.get(0)?,
                        row.get(1)?,
                        row.get(2)?,
                        row.get(3)?,
                        row.get(4)?,
                    ))
                },
            )
            .optional()?
            .ok_or_else(|| anyhow!("learning job not found"))?
        };
        if !matches!(
            kind.as_str(),
            "document_acquire_v1" | "social_acquisition_v1"
        ) || status != "leased"
            || lease_owner.as_deref() != Some(result.worker.as_str())
            || lease_until
                .as_deref()
                .map(parse_time)
                .transpose()?
                .is_none_or(|until| until <= Utc::now())
        {
            bail!("acquisition result requires an active worker-owned lease");
        }
        let payload: serde_json::Value = serde_json::from_str(&payload)?;
        if let Some(plan_id) = payload.get("plan_id").and_then(serde_json::Value::as_str)
            && plan_id != result.attempt.plan_id.to_string()
        {
            bail!("acquisition result plan does not match leased job");
        }
        let source_policy = self
            .get_source_policy(result.attempt.source_policy_id)?
            .ok_or_else(|| anyhow!("source policy not found"))?;
        if !source_policy.enabled {
            bail!("source policy is disabled");
        }

        match (&result.document, cleaned_content, raw_content) {
            (Some(document), Some(cleaned), raw) => {
                if document.source_policy_id != result.attempt.source_policy_id
                    || document.canonical_url != result.attempt.canonical_url
                    || result
                        .attempt
                        .content_hash
                        .as_deref()
                        .is_some_and(|hash| hash != document.cleaned_content_hash)
                    || (result.attempt.outcome != AcquisitionOutcome::Success
                        && document.rights.training_eligible)
                {
                    bail!("document provenance does not match acquisition attempt");
                }
                validate_worker_document_policy(
                    document,
                    cleaned,
                    raw,
                    &source_policy,
                    result.attempt.outcome == AcquisitionOutcome::Success,
                )?;
                self.save_document(document, cleaned, raw)?;
            }
            (None, None, None) if result.attempt.outcome != AcquisitionOutcome::Success => {}
            (None, _, _) => bail!("successful acquisition must include a document"),
            (Some(_), None, _) => bail!("document result requires cleaned content"),
        }
        self.save_acquisition_attempt(&result.attempt)?;

        let value = serde_json::to_value(result)?;
        let result_hash = canonical_json_hash(&value);
        let json = serde_json::to_string(result)?;
        let conn = self.lock_conn();
        let existing: Option<String> = conn
            .query_row(
                "SELECT result_hash FROM acquisition_worker_results WHERE job_id=?1",
                params![result.job_id.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(existing) = existing {
            if existing == result_hash {
                drop(conn);
                if let Some(document) = &result.document {
                    self.enqueue_unique_learning_job(
                        "knowledge_consolidate_v1",
                        &document.document_id.to_string(),
                        serde_json::json!({"document_id":document.document_id}),
                        0.8,
                        3,
                    )?;
                }
                self.record_acquisition_meta_trace(&payload, result)?;
                return Ok(existing);
            }
            bail!("acquisition worker results are immutable");
        }
        conn.execute(
            "INSERT INTO acquisition_worker_results(
               job_id,worker,result_json,result_hash,created_at
             ) VALUES(?1,?2,?3,?4,?5)",
            params![
                result.job_id.to_string(),
                result.worker,
                json,
                result_hash,
                result.created_at.to_rfc3339()
            ],
        )?;
        drop(conn);
        if let Some(document) = &result.document {
            self.enqueue_unique_learning_job(
                "knowledge_consolidate_v1",
                &document.document_id.to_string(),
                serde_json::json!({"document_id":document.document_id}),
                0.8,
                3,
            )?;
        }
        self.enqueue_discovered_documents(&payload, result)?;
        self.record_acquisition_meta_trace(&payload, result)?;
        Ok(result_hash)
    }

    fn record_acquisition_meta_trace(
        &self,
        payload: &serde_json::Value,
        result: &AcquisitionWorkerResult,
    ) -> Result<()> {
        let unsafe_document = result.document.as_ref().is_some_and(|document| {
            document.prompt_injection_detected || document.pii_detected || document.secret_detected
        });
        self.record_acquisition_attempt_meta_trace(
            payload,
            &result.attempt,
            result.document.is_some(),
            unsafe_document,
            result.discovered_urls.len(),
            result.created_at,
        )
    }

    fn record_acquisition_attempt_meta_trace(
        &self,
        payload: &serde_json::Value,
        attempt: &AcquisitionAttempt,
        document_created: bool,
        unsafe_document: bool,
        discovered_url_count: usize,
        created_at: DateTime<Utc>,
    ) -> Result<()> {
        let source_domain = url::Url::parse(&attempt.canonical_url)
            .ok()
            .and_then(|url| url.host_str().map(str::to_owned))
            .unwrap_or_else(|| "unknown".into());
        let topic_family = payload
            .get("topic_ids")
            .and_then(serde_json::Value::as_array)
            .and_then(|topics| topics.first())
            .and_then(serde_json::Value::as_str)
            .unwrap_or("unscoped")
            .to_owned();
        let input = serde_json::json!({
            "method":attempt.method,
            "outcome":attempt.outcome,
            "http_status_class":attempt.http_status.map(|status| status / 100),
            "source_kind":payload.pointer("/source_policy/kind"),
            "has_partial_document":document_created
        });
        let action = match attempt.outcome {
            AcquisitionOutcome::Success => "store",
            AcquisitionOutcome::PartialContent
            | AcquisitionOutcome::JsShell
            | AcquisitionOutcome::ParseFailed => "store_partial_or_escalate",
            AcquisitionOutcome::RateLimited
            | AcquisitionOutcome::Timeout
            | AcquisitionOutcome::ServerError => "retry_same_identity",
            _ => "stop",
        };
        self.record_meta_decision(&MetaDecisionTrace {
            schema_version: SCHEMA_VERSION.into(),
            decision_id: stable_meta_uuid(
                format!("acquisition-attempt:{}", attempt.attempt_id).as_bytes(),
            ),
            task_kind: MetaTaskKind::AcquisitionEscalation,
            input_hash: canonical_json_hash(&input),
            input,
            output: serde_json::json!({
                "action":action,
                "document_created":document_created,
                "discovered_url_count":discovered_url_count
            }),
            source_domain,
            topic_family,
            policy_version: "acquisition-policy-v1".into(),
            controller_version: "deterministic-v1".into(),
            confidence: 1.0,
            cost: attempt.cost,
            useful: document_created,
            training_eligible: !unsafe_document,
            policy_violations: 0,
            prompt_injection_detected: unsafe_document,
            data_classification: DataClassification::Public,
            external_processing: ExternalProcessingPermission::Redacted,
            redaction_attestation_hash: None,
            created_at,
        })?;
        Ok(())
    }

    fn enqueue_discovered_documents(
        &self,
        parent_payload: &serde_json::Value,
        result: &AcquisitionWorkerResult,
    ) -> Result<()> {
        if result.discovered_urls.is_empty() {
            return Ok(());
        }
        let policy = self
            .get_source_policy(result.attempt.source_policy_id)?
            .ok_or_else(|| anyhow!("source policy not found"))?;
        let plan = self
            .get_acquisition_plan(result.attempt.plan_id)?
            .ok_or_else(|| anyhow!("acquisition plan not found"))?;
        let topic_ids = parent_payload
            .get("topic_ids")
            .and_then(serde_json::Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(serde_json::Value::as_str)
            .filter_map(|value| Uuid::parse_str(value).ok())
            .collect::<Vec<_>>();
        if topic_ids.is_empty() {
            return Ok(());
        }
        let mut urls = result
            .discovered_urls
            .iter()
            .filter_map(|url| text::canonicalize_public_url(url, &policy.allowed_domains).ok())
            .filter(|url| url != &result.attempt.canonical_url)
            .collect::<Vec<_>>();
        urls.sort();
        urls.dedup();
        urls.truncate(
            usize::try_from(plan.max_documents.min(policy.max_pages_per_run)).unwrap_or(usize::MAX),
        );
        if urls.is_empty() {
            return Ok(());
        }

        // Budget reservations are deliberately conservative: a duplicate URL may consume a slot,
        // but concurrent workers can never exceed a TopicWatch limit.
        for topic_id in &topic_ids {
            if self
                .reserve_topic_budget(*topic_id, 0, urls.len() as u32, 0, 0)
                .is_err()
            {
                return Ok(());
            }
        }
        for canonical_url in urls {
            let key = format!("{}:{}", policy.policy_id, canonical_url);
            self.enqueue_unique_learning_job(
                "document_acquire_v1",
                &key,
                serde_json::json!({
                    "plan_id":plan.plan_id,
                    "topic_ids":topic_ids,
                    "source_policy_id":policy.policy_id,
                    "source_policy":policy,
                    "canonical_url":canonical_url,
                    "item":{
                        "external_id":serde_json::Value::Null,
                        "title":canonical_url,
                        "url":canonical_url,
                        "author":serde_json::Value::Null,
                        "published_at":serde_json::Value::Null,
                        "summary":serde_json::Value::Null,
                        "language":serde_json::Value::Null
                    }
                }),
                0.7,
                5,
            )?;
        }
        Ok(())
    }

    pub fn get_acquisition_worker_result(
        &self,
        job_id: Uuid,
    ) -> Result<Option<AcquisitionWorkerResult>> {
        self.read_json_optional(
            "SELECT result_json FROM acquisition_worker_results WHERE job_id=?1",
            job_id.to_string(),
        )
    }

    pub fn validate_acquisition_job_completion(&self, job_id: Uuid) -> Result<()> {
        let conn = self.lock_conn();
        validate_acquisition_completion(&conn, job_id)
    }
}

/// Pure connection-level form of the acquisition completion check, so the
/// transactional job-completion path can run it inside its own transaction.
pub(crate) fn validate_acquisition_completion(
    conn: &rusqlite::Connection,
    job_id: Uuid,
) -> Result<()> {
    let row: Option<(String, i64)> = conn
        .query_row(
            "SELECT j.kind,EXISTS(
               SELECT 1 FROM acquisition_worker_results r WHERE r.job_id=j.id
             ) FROM learning_jobs j WHERE j.id=?1",
            params![job_id.to_string()],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()?;
    if matches!(&row, Some((kind, 0)) if matches!(kind.as_str(), "document_acquire_v1" | "social_acquisition_v1"))
    {
        bail!("acquisition worker must submit an immutable result before completing its job");
    }
    Ok(())
}

impl Registry {
    pub fn reserve_topic_budget(
        &self,
        topic_id: Uuid,
        events: u32,
        documents: u32,
        browser_escalations: u32,
        model_tokens: u64,
    ) -> Result<()> {
        let topic = self
            .get_topic_watch(topic_id)?
            .ok_or_else(|| anyhow!("topic watch not found"))?;
        let day = Utc::now().date_naive().to_string();
        let mut conn = self.lock_conn();
        let transaction = conn.transaction()?;
        let current: (u64, u64, u64, u64) = transaction
            .query_row(
                "SELECT events,documents,browser_escalations,model_tokens
                 FROM topic_acquisition_usage WHERE day=?1 AND topic_id=?2",
                params![day, topic_id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .optional()?
            .unwrap_or_default();
        let next = (
            current.0.saturating_add(u64::from(events)),
            current.1.saturating_add(u64::from(documents)),
            current.2.saturating_add(u64::from(browser_escalations)),
            current.3.saturating_add(model_tokens),
        );
        if next.0 > u64::from(topic.budget.events_per_day)
            || next.1 > u64::from(topic.budget.fetched_documents_per_day)
            || next.2 > u64::from(topic.budget.browser_escalations_per_day)
            || next.3 > topic.budget.model_tokens_per_day
        {
            bail!("topic daily acquisition budget exceeded");
        }
        transaction.execute(
            "INSERT INTO topic_acquisition_usage(
               day,topic_id,events,documents,browser_escalations,model_tokens
             ) VALUES(?1,?2,?3,?4,?5,?6)
             ON CONFLICT(day,topic_id) DO UPDATE SET
               events=excluded.events,documents=excluded.documents,
               browser_escalations=excluded.browser_escalations,
               model_tokens=excluded.model_tokens",
            params![day, topic_id.to_string(), next.0, next.1, next.2, next.3],
        )?;
        transaction.commit()?;
        Ok(())
    }
}

impl Registry {
    pub fn transition_acquisition_plan(
        &self,
        plan_id: Uuid,
        next: AcquisitionPlanStatus,
    ) -> Result<AcquisitionPlan> {
        let mut plan = self
            .get_acquisition_plan(plan_id)?
            .ok_or_else(|| anyhow!("acquisition plan not found"))?;
        let allowed = matches!(
            (plan.status, next),
            (
                AcquisitionPlanStatus::Pending,
                AcquisitionPlanStatus::Running | AcquisitionPlanStatus::Cancelled
            ) | (
                AcquisitionPlanStatus::Running,
                AcquisitionPlanStatus::Completed | AcquisitionPlanStatus::Failed
            )
        );
        if !allowed {
            bail!(
                "invalid acquisition plan transition {:?} -> {:?}",
                plan.status,
                next
            );
        }
        plan.status = next;
        let json = serde_json::to_string(&plan)?;
        let conn = self.lock_conn();
        let changed = conn.execute(
            "UPDATE acquisition_plans SET status=?2,plan_json=?3,updated_at=?4 WHERE id=?1",
            params![
                plan_id.to_string(),
                plan_status_name(next),
                json,
                Utc::now().to_rfc3339()
            ],
        )?;
        if changed != 1 {
            bail!("acquisition plan not found");
        }
        Ok(plan)
    }
}
