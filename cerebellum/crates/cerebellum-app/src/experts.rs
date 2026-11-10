use anyhow::{Result, bail};
use cerebellum_core::{
    DatasetSplit, DatasetSplitStats, ExpertAssignment, ExpertAssignmentStatus,
    ExpertDatasetPurpose, ExpertDatasetReadiness, ExpertDatasetStats, ExpertDefinition,
    ExpertRouteDecision, ExpertRouteRequest, ExpertRouteScore, ExpertTaxonomy, MetaDecisionTrace,
    MetaReplayEvaluation, MetaTaskKind, SCHEMA_VERSION, canonical_json_hash,
    validate_expert_assignment, validate_expert_taxonomy,
};
use chrono::Utc;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet, HashSet};
use uuid::Uuid;

pub const EXPERT_POLICY_VERSION: &str = "request-routed-lora-v1";
pub const EXPERT_TAXONOMY_ID: &str = "cerebellum-meta-experts";
pub const EXPERT_TAXONOMY_VERSION: &str = "1.1.0";
pub const SHARED_EXPERT_ID: &str = "shared";
pub const RETRIEVAL_EXPERT_ID: &str = "retrieval";
pub const EVIDENCE_EXPERT_ID: &str = "evidence";
pub const ACQUISITION_EXPERT_ID: &str = "acquisition";
pub const SKILL_WORKFLOW_EXPERT_ID: &str = "skill_workflow";
pub const METACOGNITION_EXPERT_ID: &str = "metacognition";
pub const MIN_ROUTER_TRAIN_RECORDS: u64 = 5_000;
pub const MIN_EXPERT_TRAIN_RECORDS: u64 = 1_000;
pub const MIN_EXPERT_REPLAY_RECORDS: u64 = 200;

pub(crate) type ExpertGroupKey = (DatasetSplit, ExpertDatasetPurpose, Option<String>, String);

#[derive(Debug)]
pub(crate) struct PreparedExpertDataset {
    pub taxonomy: ExpertTaxonomy,
    pub taxonomy_hash: String,
    pub assignments: Vec<ExpertAssignment>,
    pub groups: BTreeMap<ExpertGroupKey, Vec<Value>>,
    pub readiness: ExpertDatasetReadiness,
    pub ambiguous_count: u64,
    pub out_of_distribution_count: u64,
    pub negative_transfer_count: u64,
}

pub fn builtin_expert_taxonomy() -> ExpertTaxonomy {
    let taxonomy = ExpertTaxonomy {
        schema_version: SCHEMA_VERSION.into(),
        taxonomy_id: EXPERT_TAXONOMY_ID.into(),
        version: EXPERT_TAXONOMY_VERSION.into(),
        experts: vec![
            ExpertDefinition {
                id: RETRIEVAL_EXPERT_ID.into(),
                description: "Relevance, noise filtering, deduplication, and retrieval ranking"
                    .into(),
                task_kinds: vec![
                    MetaTaskKind::Relevance,
                    MetaTaskKind::NoiseFilter,
                    MetaTaskKind::Deduplication,
                    MetaTaskKind::RetrievalRanking,
                ],
                is_fallback: false,
            },
            ExpertDefinition {
                id: EVIDENCE_EXPERT_ID.into(),
                description: "Claim support, contradiction, provenance, and consolidation".into(),
                task_kinds: vec![MetaTaskKind::ClaimRelationship],
                is_fallback: false,
            },
            ExpertDefinition {
                id: ACQUISITION_EXPERT_ID.into(),
                description: "Acquisition escalation, curriculum priority, and information gain"
                    .into(),
                task_kinds: vec![
                    MetaTaskKind::AcquisitionEscalation,
                    MetaTaskKind::CurriculumPriority,
                    MetaTaskKind::ExpectedInformationGain,
                ],
                is_fallback: false,
            },
            ExpertDefinition {
                id: SKILL_WORKFLOW_EXPERT_ID.into(),
                description: "Skill and workflow routing, evaluation, and evolution".into(),
                task_kinds: vec![
                    MetaTaskKind::SkillWorkflowRouting,
                    MetaTaskKind::SkillWorkflowEvolution,
                ],
                is_fallback: false,
            },
            ExpertDefinition {
                id: METACOGNITION_EXPERT_ID.into(),
                description:
                    "Temporal grounding, knowledge-boundary and information-seeking decisions"
                        .into(),
                task_kinds: vec![
                    MetaTaskKind::TemporalGrounding,
                    MetaTaskKind::KnowledgeBoundary,
                    MetaTaskKind::SearchPlanning,
                ],
                is_fallback: false,
            },
            ExpertDefinition {
                id: SHARED_EXPERT_ID.into(),
                description: "Low-confidence, cross-domain, and out-of-distribution fallback"
                    .into(),
                task_kinds: vec![],
                is_fallback: true,
            },
        ],
        fallback_expert_id: SHARED_EXPERT_ID.into(),
        router_top_k: 1,
        policy_version: EXPERT_POLICY_VERSION.into(),
    };
    validate_expert_taxonomy(&taxonomy).expect("built-in expert taxonomy must be valid");
    taxonomy
}

pub fn builtin_expert_taxonomy_hash() -> String {
    canonical_json_hash(
        &serde_json::to_value(builtin_expert_taxonomy()).expect("taxonomy serializes"),
    )
}

pub(crate) fn prepare_expert_dataset(
    records: &[(DatasetSplit, Value)],
) -> Result<PreparedExpertDataset> {
    let taxonomy = builtin_expert_taxonomy();
    let taxonomy_hash = canonical_json_hash(&serde_json::to_value(&taxonomy)?);
    let mut assignments = Vec::with_capacity(records.len());
    let mut groups = BTreeMap::<ExpertGroupKey, Vec<Value>>::new();
    let mut stats = taxonomy
        .experts
        .iter()
        .filter(|expert| !expert.is_fallback)
        .map(|expert| (expert.id.clone(), ExpertDatasetStats::default()))
        .collect::<BTreeMap<_, _>>();
    let mut router_train_records = 0_u64;
    let mut ambiguous_count = 0_u64;
    let mut out_of_distribution_count = 0_u64;
    let mut negative_transfer_count = 0_u64;

    for (split, envelope) in records {
        let assignment = classify_envelope(*split, envelope, &taxonomy)?;
        match assignment.status {
            ExpertAssignmentStatus::Assigned => {}
            ExpertAssignmentStatus::Ambiguous => ambiguous_count += 1,
            ExpertAssignmentStatus::OutOfDistribution => out_of_distribution_count += 1,
            ExpertAssignmentStatus::NegativeTransfer => negative_transfer_count += 1,
        }
        let kind = assignment.record_kind.clone();
        groups
            .entry((*split, ExpertDatasetPurpose::Shared, None, kind.clone()))
            .or_default()
            .push(envelope.clone());

        let router_record = json!({
            "kind":"expert_route",
            "split":split,
            "record":{
                "record_hash":assignment.record_hash,
                "record_kind":assignment.record_kind,
                "task_kind":assignment.task_kind,
                "source_domain":assignment.source_domain,
                "topic_family":assignment.topic_family,
                "target_expert_id":assignment.primary_expert_id,
                "secondary_expert_ids":assignment.secondary_expert_ids,
                "status":assignment.status,
                "reason_codes":assignment.reason_codes
            }
        });
        groups
            .entry((
                *split,
                ExpertDatasetPurpose::Router,
                None,
                "expert_route".into(),
            ))
            .or_default()
            .push(router_record.clone());
        if *split == DatasetSplit::Train {
            router_train_records += 1;
        }
        if assignment.status != ExpertAssignmentStatus::Assigned {
            groups
                .entry((
                    *split,
                    ExpertDatasetPurpose::RoutingNegative,
                    None,
                    "expert_route".into(),
                ))
                .or_default()
                .push(router_record);
        } else if assignment.primary_expert_id != taxonomy.fallback_expert_id {
            groups
                .entry((
                    *split,
                    ExpertDatasetPurpose::Expert,
                    Some(assignment.primary_expert_id.clone()),
                    kind.clone(),
                ))
                .or_default()
                .push(envelope.clone());
            let expert_stats = stats
                .get_mut(&assignment.primary_expert_id)
                .expect("assigned expert exists in taxonomy");
            increment_split(&mut expert_stats.records, *split);
            match kind.as_str() {
                "meta_decision" => expert_stats.decision_records += 1,
                "meta_replay" => {
                    expert_stats.replay_records += 1;
                    if *split != DatasetSplit::Train {
                        expert_stats.evaluation_replay_records += 1;
                    }
                }
                _ => unreachable!("classified records have a fixed kind"),
            }
        }
        assignments.push(assignment);
    }

    let mut reasons = Vec::new();
    if router_train_records < MIN_ROUTER_TRAIN_RECORDS {
        reasons.push(format!(
            "router has {router_train_records} train records; requires {MIN_ROUTER_TRAIN_RECORDS}"
        ));
    }
    for (expert_id, expert_stats) in &stats {
        if expert_stats.records.train < MIN_EXPERT_TRAIN_RECORDS {
            reasons.push(format!(
                "expert {expert_id} has {} train records; requires {MIN_EXPERT_TRAIN_RECORDS}",
                expert_stats.records.train
            ));
        }
        if expert_stats.evaluation_replay_records < MIN_EXPERT_REPLAY_RECORDS {
            reasons.push(format!(
                "expert {expert_id} has {} validation/holdout replay records; requires {MIN_EXPERT_REPLAY_RECORDS}",
                expert_stats.evaluation_replay_records
            ));
        }
    }
    let readiness = ExpertDatasetReadiness {
        ready: reasons.is_empty(),
        minimum_router_records: MIN_ROUTER_TRAIN_RECORDS,
        minimum_train_records_per_expert: MIN_EXPERT_TRAIN_RECORDS,
        minimum_replays_per_expert: MIN_EXPERT_REPLAY_RECORDS,
        router_train_records,
        per_expert: stats,
        reasons,
    };
    Ok(PreparedExpertDataset {
        taxonomy,
        taxonomy_hash,
        assignments,
        groups,
        readiness,
        ambiguous_count,
        out_of_distribution_count,
        negative_transfer_count,
    })
}

pub fn route_expert(request: &ExpertRouteRequest) -> Result<ExpertRouteDecision> {
    let taxonomy = builtin_expert_taxonomy();
    let taxonomy_hash = canonical_json_hash(&serde_json::to_value(&taxonomy)?);
    let known = taxonomy
        .experts
        .iter()
        .map(|expert| expert.id.as_str())
        .collect::<HashSet<_>>();
    if request
        .available_expert_ids
        .iter()
        .any(|expert| !known.contains(expert.as_str()))
    {
        bail!("available expert list contains an unknown expert");
    }
    let available = if request.available_expert_ids.is_empty() {
        known
    } else {
        request
            .available_expert_ids
            .iter()
            .map(String::as_str)
            .collect()
    };
    let mapped = task_expert(request.task_kind);
    let unsafe_input = contains_unsafe_routing_input(&request.input);
    let selected = if !unsafe_input && available.contains(mapped) {
        mapped
    } else if available.contains(taxonomy.fallback_expert_id.as_str()) {
        taxonomy.fallback_expert_id.as_str()
    } else {
        bail!("neither the mapped expert nor the shared fallback is available");
    };
    let fallback_used = selected == taxonomy.fallback_expert_id;
    // Confidence is an assignment indicator, not a probability: a direct
    // taxonomy hit is 1.0; fallback/unsafe-gated routing is 0.0.
    let confidence = f64::from(!(unsafe_input || fallback_used));
    let mut scores = taxonomy
        .experts
        .iter()
        .filter(|expert| available.contains(expert.id.as_str()))
        .map(|expert| ExpertRouteScore {
            expert_id: expert.id.clone(),
            score: if expert.id == selected {
                confidence
            } else {
                0.0
            },
        })
        .collect::<Vec<_>>();
    scores.sort_by(|left, right| {
        right
            .score
            .total_cmp(&left.score)
            .then_with(|| left.expert_id.cmp(&right.expert_id))
    });
    Ok(ExpertRouteDecision {
        decision_id: Uuid::new_v4(),
        taxonomy_hash,
        selected_expert_id: selected.into(),
        fallback_used,
        confidence,
        scores,
        reason_codes: if unsafe_input {
            vec!["unsafe_input_requires_hard_policy_gate".into()]
        } else if fallback_used {
            vec!["mapped_expert_unavailable".into(), "shared_fallback".into()]
        } else {
            vec!["deterministic_task_mapping".into()]
        },
        router_version: "deterministic-expert-router-v1".into(),
        router_adapter: None,
        selected_adapter: None,
        dense_fallback: false,
        created_at: Utc::now(),
    })
}

fn classify_envelope(
    split: DatasetSplit,
    envelope: &Value,
    taxonomy: &ExpertTaxonomy,
) -> Result<ExpertAssignment> {
    let record_kind = envelope
        .get("kind")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow::anyhow!("dataset record lacks kind"))?;
    let record = envelope
        .get("record")
        .ok_or_else(|| anyhow::anyhow!("dataset record lacks payload"))?;
    let record_hash = canonical_json_hash(envelope);
    let assignment = match record_kind {
        "meta_decision" => {
            let trace: MetaDecisionTrace = serde_json::from_value(record.clone())?;
            let mapped = task_expert(trace.task_kind).to_owned();
            let mut status = ExpertAssignmentStatus::Assigned;
            let mut primary = mapped.clone();
            let mut secondary = Vec::new();
            let mut reasons = vec!["task_kind_mapping".into()];
            if trace.source_domain.trim().is_empty() || trace.topic_family.trim().is_empty() {
                status = ExpertAssignmentStatus::OutOfDistribution;
                primary = taxonomy.fallback_expert_id.clone();
                secondary.push(mapped);
                reasons = vec!["missing_routing_metadata".into(), "shared_fallback".into()];
            } else if !trace.useful {
                status = ExpertAssignmentStatus::NegativeTransfer;
                primary = taxonomy.fallback_expert_id.clone();
                secondary.push(mapped);
                reasons = vec![
                    "negative_transfer".into(),
                    "do_not_route_to_domain_expert".into(),
                ];
            } else if trace.confidence <= 0.0 {
                status = ExpertAssignmentStatus::Ambiguous;
                primary = taxonomy.fallback_expert_id.clone();
                secondary.push(mapped);
                reasons = vec!["low_source_confidence".into(), "shared_fallback".into()];
            }
            ExpertAssignment {
                record_hash,
                split,
                record_kind: record_kind.into(),
                primary_expert_id: primary,
                secondary_expert_ids: secondary,
                status,
                reason_codes: reasons,
                source_domain: trace.source_domain,
                topic_family: trace.topic_family,
                task_kind: Some(trace.task_kind),
            }
        }
        "meta_replay" => {
            let replay: MetaReplayEvaluation = serde_json::from_value(record.clone())?;
            classify_replay(split, record_hash, replay, taxonomy)
        }
        "synthetic_candidate" => {
            let candidate: cerebellum_core::SyntheticTrainingCandidate =
                serde_json::from_value(record.clone())?;
            let mapped = task_expert(candidate.task_kind).to_owned();
            ExpertAssignment {
                record_hash,
                split,
                record_kind: record_kind.into(),
                primary_expert_id: mapped,
                secondary_expert_ids: vec![],
                status: ExpertAssignmentStatus::Assigned,
                reason_codes: vec!["quality_cleared_synthetic_lineage".into()],
                source_domain: format!("synthetic:{}", candidate.parent_subject_id),
                topic_family: format!("{:?}", candidate.task_kind).to_ascii_lowercase(),
                task_kind: Some(candidate.task_kind),
            }
        }
        _ => bail!("unsupported record kind for expert routing: {record_kind}"),
    };
    validate_expert_assignment(&assignment, taxonomy)?;
    Ok(assignment)
}

fn classify_replay(
    split: DatasetSplit,
    record_hash: String,
    replay: MetaReplayEvaluation,
    taxonomy: &ExpertTaxonomy,
) -> ExpertAssignment {
    let text = format!(
        "{} {} {}",
        replay.task_id, replay.source_domain, replay.topic_family
    )
    .to_lowercase();
    let candidates = replay_candidates(&text);
    let harmful = replay.candidate_score < replay.baseline_score || !replay.fact_correct;
    let (status, primary, secondary, reason_codes) = if harmful {
        (
            ExpertAssignmentStatus::NegativeTransfer,
            taxonomy.fallback_expert_id.clone(),
            candidates.into_iter().collect(),
            vec!["paired_replay_regression".into(), "shared_fallback".into()],
        )
    } else if candidates.len() == 1 {
        (
            ExpertAssignmentStatus::Assigned,
            candidates.iter().next().expect("one candidate").clone(),
            vec![],
            vec!["replay_metadata_mapping".into()],
        )
    } else if candidates.len() > 1 {
        (
            ExpertAssignmentStatus::Ambiguous,
            taxonomy.fallback_expert_id.clone(),
            candidates.into_iter().collect(),
            vec!["cross_expert_replay".into(), "shared_fallback".into()],
        )
    } else {
        (
            ExpertAssignmentStatus::OutOfDistribution,
            taxonomy.fallback_expert_id.clone(),
            vec![],
            vec![
                "unrecognized_replay_family".into(),
                "shared_fallback".into(),
            ],
        )
    };
    ExpertAssignment {
        record_hash,
        split,
        record_kind: "meta_replay".into(),
        primary_expert_id: primary,
        secondary_expert_ids: secondary,
        status,
        reason_codes,
        source_domain: replay.source_domain,
        topic_family: replay.topic_family,
        task_kind: None,
    }
}

fn replay_candidates(text: &str) -> BTreeSet<String> {
    let groups = [
        (
            RETRIEVAL_EXPERT_ID,
            [
                "search", "retriev", "rank", "dedup", "noise", "检索", "搜索", "去重",
            ]
            .as_slice(),
        ),
        (
            EVIDENCE_EXPERT_ID,
            [
                "claim",
                "fact",
                "evidence",
                "conflict",
                "knowledge",
                "事实",
                "证据",
                "冲突",
            ]
            .as_slice(),
        ),
        (
            ACQUISITION_EXPERT_ID,
            [
                "crawl",
                "scrape",
                "github",
                "rss",
                "acquisition",
                "采集",
                "爬虫",
            ]
            .as_slice(),
        ),
        (
            SKILL_WORKFLOW_EXPERT_ID,
            ["skill", "workflow", "agent", "技能", "工作流"].as_slice(),
        ),
        (
            METACOGNITION_EXPERT_ID,
            [
                "time", "date", "current", "latest", "fresh", "stale", "deadline", "时间", "日期",
                "最新", "当前", "过期", "搜索",
            ]
            .as_slice(),
        ),
    ];
    groups
        .into_iter()
        .filter(|(_, keywords)| keywords.iter().any(|keyword| text.contains(keyword)))
        .map(|(expert, _)| expert.to_owned())
        .collect()
}

pub fn task_expert(kind: MetaTaskKind) -> &'static str {
    match kind {
        MetaTaskKind::Relevance
        | MetaTaskKind::NoiseFilter
        | MetaTaskKind::Deduplication
        | MetaTaskKind::RetrievalRanking => RETRIEVAL_EXPERT_ID,
        MetaTaskKind::ClaimRelationship => EVIDENCE_EXPERT_ID,
        MetaTaskKind::AcquisitionEscalation
        | MetaTaskKind::CurriculumPriority
        | MetaTaskKind::ExpectedInformationGain => ACQUISITION_EXPERT_ID,
        MetaTaskKind::SkillWorkflowRouting | MetaTaskKind::SkillWorkflowEvolution => {
            SKILL_WORKFLOW_EXPERT_ID
        }
        MetaTaskKind::TemporalGrounding
        | MetaTaskKind::KnowledgeBoundary
        | MetaTaskKind::SearchPlanning => METACOGNITION_EXPERT_ID,
    }
}

pub fn contains_unsafe_routing_input(value: &Value) -> bool {
    match value {
        Value::String(value) => {
            let lower = value.to_lowercase();
            lower.contains("ignore previous instructions")
                || lower.contains("system prompt")
                || lower.contains("authorization: bearer")
                || lower.contains("-----begin private key-----")
        }
        Value::Array(values) => values.iter().any(contains_unsafe_routing_input),
        Value::Object(values) => values.iter().any(|(key, value)| {
            matches!(
                key.to_lowercase().as_str(),
                "api_key" | "apikey" | "password" | "cookie" | "authorization"
            ) || contains_unsafe_routing_input(value)
        }),
        _ => false,
    }
}

fn increment_split(stats: &mut DatasetSplitStats, split: DatasetSplit) {
    match split {
        DatasetSplit::Train => stats.train += 1,
        DatasetSplit::Validation => stats.validation += 1,
        DatasetSplit::Holdout => stats.holdout += 1,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn trace(task_kind: MetaTaskKind, useful: bool, confidence: f64) -> Value {
        serde_json::to_value(MetaDecisionTrace {
            schema_version: SCHEMA_VERSION.into(),
            decision_id: Uuid::new_v4(),
            task_kind,
            input_hash: "a".repeat(64),
            input: json!({"query":"agent"}),
            output: json!({"accepted":useful}),
            source_domain: "example.test".into(),
            topic_family: "retrieval".into(),
            policy_version: "test".into(),
            controller_version: "test".into(),
            confidence,
            cost: 0.0,
            useful,
            training_eligible: true,
            policy_violations: 0,
            prompt_injection_detected: false,
            data_classification: cerebellum_core::DataClassification::Private,
            external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
            redaction_attestation_hash: None,
            created_at: Utc::now(),
        })
        .unwrap()
    }

    fn replay(task_id: &str) -> Value {
        serde_json::to_value(MetaReplayEvaluation {
            schema_version: SCHEMA_VERSION.into(),
            evaluation_id: Uuid::new_v4(),
            candidate_id: None,
            task_id: task_id.into(),
            source_domain: "search.example".into(),
            topic_family: "retrieval".into(),
            baseline_score: 0.5,
            candidate_score: 0.8,
            fact_correct: true,
            safety_passed: true,
            data_classification: cerebellum_core::DataClassification::Private,
            external_processing: cerebellum_core::ExternalProcessingPermission::Denied,
            redaction_attestation_hash: None,
            created_at: Utc::now(),
        })
        .unwrap()
    }

    #[test]
    fn every_meta_task_routes_to_one_domain_expert() {
        for (task, expected) in [
            (MetaTaskKind::Relevance, RETRIEVAL_EXPERT_ID),
            (MetaTaskKind::ClaimRelationship, EVIDENCE_EXPERT_ID),
            (MetaTaskKind::AcquisitionEscalation, ACQUISITION_EXPERT_ID),
            (MetaTaskKind::SkillWorkflowRouting, SKILL_WORKFLOW_EXPERT_ID),
        ] {
            assert_eq!(task_expert(task), expected);
        }
    }

    #[test]
    fn unavailable_or_unsafe_routes_fall_back_instead_of_crossing_experts() {
        let unavailable = route_expert(&ExpertRouteRequest {
            task_kind: MetaTaskKind::ClaimRelationship,
            input: json!({"claim":"x"}),
            source_domain: "example.com".into(),
            topic_family: "evidence".into(),
            available_expert_ids: vec![SHARED_EXPERT_ID.into(), RETRIEVAL_EXPERT_ID.into()],
        })
        .unwrap();
        assert!(unavailable.fallback_used);
        assert_eq!(unavailable.selected_expert_id, SHARED_EXPERT_ID);

        let unsafe_route = route_expert(&ExpertRouteRequest {
            task_kind: MetaTaskKind::Relevance,
            input: json!({"authorization":"Bearer secret"}),
            source_domain: "example.com".into(),
            topic_family: "search".into(),
            available_expert_ids: vec![],
        })
        .unwrap();
        assert!(unsafe_route.fallback_used);
        assert_eq!(unsafe_route.confidence, 0.0);
    }

    #[test]
    fn dataset_assignment_preserves_splits_and_negative_transfer_as_router_negatives() {
        let positive = json!({
            "kind":"meta_decision",
            "split":"train",
            "record":trace(MetaTaskKind::Relevance, true, 0.9)
        });
        let negative = json!({
            "kind":"meta_decision",
            "split":"holdout",
            "record":trace(MetaTaskKind::Relevance, false, 0.9)
        });
        let records = vec![
            (DatasetSplit::Train, positive),
            (DatasetSplit::Holdout, negative),
        ];
        let first = prepare_expert_dataset(&records).unwrap();
        let second = prepare_expert_dataset(&records).unwrap();
        assert_eq!(first.taxonomy_hash, second.taxonomy_hash);
        assert_eq!(first.assignments, second.assignments);
        assert_eq!(first.groups, second.groups);

        assert_eq!(first.assignments[0].primary_expert_id, RETRIEVAL_EXPERT_ID);
        assert_eq!(
            first.assignments[1].status,
            ExpertAssignmentStatus::NegativeTransfer
        );
        assert_eq!(first.assignments[1].primary_expert_id, SHARED_EXPERT_ID);
        assert!(first.groups.contains_key(&(
            DatasetSplit::Holdout,
            ExpertDatasetPurpose::RoutingNegative,
            None,
            "expert_route".into()
        )));
        assert!(!first.groups.contains_key(&(
            DatasetSplit::Holdout,
            ExpertDatasetPurpose::Expert,
            Some(RETRIEVAL_EXPERT_ID.into()),
            "meta_decision".into()
        )));
    }

    #[test]
    fn route_confidence_is_a_binary_assignment_indicator() {
        let hit = route_expert(&ExpertRouteRequest {
            task_kind: MetaTaskKind::Relevance,
            input: json!({"query":"x"}),
            source_domain: "example.com".into(),
            topic_family: "search".into(),
            available_expert_ids: vec![],
        })
        .unwrap();
        assert_eq!(hit.confidence, 1.0);
        assert!(
            hit.scores
                .iter()
                .all(|score| score.score == 1.0 || score.score == 0.0),
            "route scores must only contain 1.0/0.0: {:?}",
            hit.scores
        );
        assert_eq!(
            hit.scores
                .iter()
                .find(|score| score.expert_id == hit.selected_expert_id)
                .map(|score| score.score),
            Some(1.0)
        );

        // Unsafe input: even the selected expert reports 0.0.
        let unsafe_route = route_expert(&ExpertRouteRequest {
            task_kind: MetaTaskKind::Relevance,
            input: json!({"authorization":"Bearer secret"}),
            source_domain: "example.com".into(),
            topic_family: "search".into(),
            available_expert_ids: vec![],
        })
        .unwrap();
        assert_eq!(unsafe_route.confidence, 0.0);
        assert!(unsafe_route.scores.iter().all(|score| score.score == 0.0));
    }

    #[test]
    fn router_training_records_carry_labels_not_pseudo_confidence() {
        let records = vec![(
            DatasetSplit::Train,
            json!({"kind":"meta_decision","split":"train","record":trace(MetaTaskKind::Relevance, true, 0.9)}),
        )];
        let prepared = prepare_expert_dataset(&records).unwrap();
        let router_records = &prepared.groups[&(
            DatasetSplit::Train,
            ExpertDatasetPurpose::Router,
            None,
            "expert_route".into(),
        )];
        assert_eq!(router_records.len(), 1);
        let record = &router_records[0]["record"];
        assert_eq!(record["target_expert_id"], RETRIEVAL_EXPERT_ID);
        assert!(
            record.get("confidence").is_none(),
            "router training records must not carry pseudo confidence: {record}"
        );
    }

    #[test]
    fn training_split_replays_do_not_satisfy_the_independent_replay_gate() {
        let records = vec![
            (
                DatasetSplit::Train,
                json!({"kind":"meta_replay","split":"train","record":replay("retrieval-train")}),
            ),
            (
                DatasetSplit::Holdout,
                json!({"kind":"meta_replay","split":"holdout","record":replay("retrieval-holdout")}),
            ),
        ];
        let prepared = prepare_expert_dataset(&records).unwrap();
        let stats = &prepared.readiness.per_expert[RETRIEVAL_EXPERT_ID];
        assert_eq!(stats.replay_records, 2);
        assert_eq!(stats.evaluation_replay_records, 1);
        assert!(
            prepared
                .readiness
                .reasons
                .iter()
                .any(|reason| reason.contains("validation/holdout replay"))
        );
    }
}
