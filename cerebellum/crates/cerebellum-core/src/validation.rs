use crate::{
    AcquisitionAttempt, AcquisitionPlan, BaseModelPin, BenchmarkSplit, CandidateEvaluation,
    CodingBenchmarkManifest, CreateCurriculumRequest, CreateOptimizationRunRequest,
    CreateTrainingRunRequest, DataQualityAssessment, DatasetBuild, DatasetQualityReport,
    DatasetSnapshot, DocumentEnvelope, EventItem, EvidenceRelationship, ExperienceEnvelope,
    ExpertAdapterVersion, ExpertAssignment, ExpertDatasetPurpose, ExpertDatasetView,
    ExpertTaxonomy, ExternalProcessingPermission, FeedbackSignal, HoldoutEvaluation, KnowledgeCard,
    KnowledgeStatus, LearningDecision, MIN_PAIRED_EVALS, MIN_ROUTING_DECISIONS, MetaCanaryDecision,
    MetaDecisionTrace, MetaModelBundle, MetaModelStatus, MetaReplayEvaluation, MetaTaskKind,
    MetacognitionAction, MetacognitionBasis, MetacognitionDecision, ModelEndpointStatus,
    ModelEndpointVersion, OptimizationBudget, OptimizationScoringPolicy, OptimizationTaskScore,
    PairedEvalRecord, ProviderPricingPolicy, QloraConfig, RedactionAttestation,
    RoutedAdapterBundleManifest, SCHEMA_VERSION, SKILLOPT_REGISTRATION_PATCH_SHA256,
    SKILLOPT_UPSTREAM_ARCHIVE_SHA256, SKILLOPT_UPSTREAM_COMMIT, SkillEditOperation, SkillEditPatch,
    SkillLifecycle, SkillManifest, SourceAccessMode, SourcePolicy, SyntheticCandidateStatus,
    SyntheticTrainingCandidate, TopicWatch, TrackedEvent, TrainingArchitecture, TrainingCandidate,
    TrainingCandidateStatus, WorkflowManifest, canonical_json_hash,
};
use chrono::{Duration, NaiveDate};
use semver::{Version, VersionReq};
use std::collections::{HashMap, HashSet, VecDeque};
use thiserror::Error;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum ValidationError {
    #[error("schema version must be {SCHEMA_VERSION}")]
    SchemaVersion,
    #[error("invalid identifier: {0}")]
    InvalidId(String),
    #[error("invalid semantic version: {0}")]
    InvalidVersion(String),
    #[error("invalid semantic version requirement: {0}")]
    InvalidVersionReq(String),
    #[error("required field is empty: {0}")]
    EmptyField(&'static str),
    #[error("content hash must be a lowercase SHA-256 digest")]
    InvalidContentHash,
    #[error("workflow references unknown node: {0}")]
    UnknownNode(String),
    #[error("workflow contains duplicate node: {0}")]
    DuplicateNode(String),
    #[error("workflow contains a cycle")]
    CyclicWorkflow,
    #[error("workflow contains duplicate gate: {0}")]
    DuplicateGate(String),
    #[error("training eligible skill lacks required provenance or evidence")]
    InvalidTrainingEligibility,
    #[error("routable skill lacks required provenance, schema validation, or security clearance")]
    InvalidRoutableSkill,
    #[error("numeric field must be finite and between zero and one: {0}")]
    InvalidUnitScore(&'static str),
    #[error("experience source lacks a fixed GitHub commit")]
    MissingFixedRevision,
    #[error("trajectory content hash must be a lowercase SHA-256 digest")]
    InvalidTrajectoryHash,
    #[error("curriculum budget exceeds the hard daily ceiling")]
    ExcessiveCurriculumBudget,
    #[error("invalid coding benchmark: {0}")]
    InvalidBenchmark(String),
    #[error("invalid optimization request: {0}")]
    InvalidOptimization(String),
    #[error("invalid topic watch: {0}")]
    InvalidTopic(String),
    #[error("invalid source policy: {0}")]
    InvalidSourcePolicy(String),
    #[error("invalid acquisition contract: {0}")]
    InvalidAcquisition(String),
    #[error("invalid document envelope: {0}")]
    InvalidDocument(String),
    #[error("invalid knowledge card: {0}")]
    InvalidKnowledge(String),
    #[error("invalid tracked event: {0}")]
    InvalidEvent(String),
    #[error("invalid meta-model bundle: {0}")]
    InvalidMetaModel(String),
    #[error("invalid dataset artifact: {0}")]
    InvalidDataset(String),
    #[error("invalid training run: {0}")]
    InvalidTrainingRun(String),
    #[error("invalid quality artifact: {0}")]
    InvalidQuality(String),
    #[error("invalid paired evaluation: {0}")]
    InvalidPairedEval(String),
    #[error("invalid learning decision: {0}")]
    InvalidLearningDecision(String),
    #[error("invalid training candidate: {0}")]
    InvalidTrainingCandidate(String),
}

fn valid_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.'))
}

pub fn validate_skill(skill: &SkillManifest) -> Result<(), ValidationError> {
    if skill.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_id(&skill.id) {
        return Err(ValidationError::InvalidId(skill.id.clone()));
    }
    Version::parse(&skill.version)
        .map_err(|_| ValidationError::InvalidVersion(skill.version.clone()))?;
    if skill.description.trim().is_empty() {
        return Err(ValidationError::EmptyField("description"));
    }
    if skill.source.content_hash.len() != 64
        || !skill
            .source
            .content_hash
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
    {
        return Err(ValidationError::InvalidContentHash);
    }
    for dependency in &skill.dependencies {
        if !valid_id(&dependency.skill_id) {
            return Err(ValidationError::InvalidId(dependency.skill_id.clone()));
        }
        VersionReq::parse(&dependency.version_req)
            .map_err(|_| ValidationError::InvalidVersionReq(dependency.version_req.clone()))?;
    }
    if skill.status.is_routable()
        && !(skill.source.has_identity_provenance()
            && skill.evidence.schema_passed
            && !skill.evidence.has_blocking_security_finding())
    {
        return Err(ValidationError::InvalidRoutableSkill);
    }
    if skill.status == SkillLifecycle::Experimental && !skill.evidence.qualifies_experimental() {
        return Err(ValidationError::InvalidRoutableSkill);
    }
    if skill.status == SkillLifecycle::Trusted && !skill.evidence.qualifies_trusted() {
        return Err(ValidationError::InvalidRoutableSkill);
    }
    if skill.training_eligible
        && !(skill.source.has_training_provenance()
            && skill.evidence.redaction_passed
            && skill.evidence.qualifies_experimental()
            && matches!(
                skill.status,
                SkillLifecycle::Experimental | SkillLifecycle::Trusted
            ))
    {
        return Err(ValidationError::InvalidTrainingEligibility);
    }
    Ok(())
}

pub fn validate_workflow(workflow: &WorkflowManifest) -> Result<(), ValidationError> {
    if workflow.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_id(&workflow.id) {
        return Err(ValidationError::InvalidId(workflow.id.clone()));
    }
    Version::parse(&workflow.version)
        .map_err(|_| ValidationError::InvalidVersion(workflow.version.clone()))?;
    if workflow.description.trim().is_empty() {
        return Err(ValidationError::EmptyField("description"));
    }

    let mut node_ids = HashSet::new();
    for node in &workflow.nodes {
        if !valid_id(&node.id) || !valid_id(&node.skill_id) {
            return Err(ValidationError::InvalidId(node.id.clone()));
        }
        if !node_ids.insert(node.id.clone()) {
            return Err(ValidationError::DuplicateNode(node.id.clone()));
        }
        VersionReq::parse(&node.version_req)
            .map_err(|_| ValidationError::InvalidVersionReq(node.version_req.clone()))?;
    }

    let mut indegree: HashMap<&str, usize> = node_ids.iter().map(|id| (id.as_str(), 0)).collect();
    let mut outgoing: HashMap<&str, Vec<&str>> = HashMap::new();
    for edge in &workflow.edges {
        if !node_ids.contains(&edge.from) {
            return Err(ValidationError::UnknownNode(edge.from.clone()));
        }
        if !node_ids.contains(&edge.to) {
            return Err(ValidationError::UnknownNode(edge.to.clone()));
        }
        *indegree.get_mut(edge.to.as_str()).expect("checked above") += 1;
        outgoing
            .entry(edge.from.as_str())
            .or_default()
            .push(edge.to.as_str());
    }
    let mut queue: VecDeque<&str> = indegree
        .iter()
        .filter_map(|(id, degree)| (*degree == 0).then_some(*id))
        .collect();
    let mut visited = 0;
    while let Some(id) = queue.pop_front() {
        visited += 1;
        for next in outgoing.get(id).into_iter().flatten() {
            let degree = indegree.get_mut(next).expect("known node");
            *degree -= 1;
            if *degree == 0 {
                queue.push_back(next);
            }
        }
    }
    if visited != workflow.nodes.len() {
        return Err(ValidationError::CyclicWorkflow);
    }

    let mut gate_ids = HashSet::new();
    for gate in &workflow.gates {
        if !valid_id(&gate.id) {
            return Err(ValidationError::InvalidId(gate.id.clone()));
        }
        if !gate_ids.insert(gate.id.clone()) {
            return Err(ValidationError::DuplicateGate(gate.id.clone()));
        }
    }
    Ok(())
}

pub fn validate_experience(experience: &ExperienceEnvelope) -> Result<(), ValidationError> {
    if experience.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if experience.task.trim().is_empty() {
        return Err(ValidationError::EmptyField("task"));
    }
    if experience.task_family.trim().is_empty() {
        return Err(ValidationError::EmptyField("task_family"));
    }
    if experience.repository.repository_id.trim().is_empty() {
        return Err(ValidationError::EmptyField("repository.repository_id"));
    }
    if experience.repository.digest.trim().is_empty() {
        return Err(ValidationError::EmptyField("repository.digest"));
    }
    if !experience.source.has_fixed_revision() {
        return Err(ValidationError::MissingFixedRevision);
    }
    if !experience.cost.estimated_usd.is_finite() || experience.cost.estimated_usd < 0.0 {
        return Err(ValidationError::InvalidUnitScore("cost.estimated_usd"));
    }
    if experience.external_processing == ExternalProcessingPermission::Redacted
        && !experience.redaction_passed
    {
        return Err(ValidationError::InvalidQuality(
            "externally processed experiences require successful redaction".into(),
        ));
    }
    for trajectory in &experience.trajectory {
        if trajectory.content_hash.len() != 64
            || !trajectory
                .content_hash
                .chars()
                .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
        {
            return Err(ValidationError::InvalidTrajectoryHash);
        }
    }
    Ok(())
}

pub fn validate_feedback(feedback: &FeedbackSignal) -> Result<(), ValidationError> {
    if feedback.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    for (name, value) in [
        ("feedback.score", feedback.score),
        ("feedback.confidence", feedback.confidence),
    ] {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(ValidationError::InvalidUnitScore(name));
        }
    }
    if feedback.source.trim().is_empty() {
        return Err(ValidationError::EmptyField("feedback.source"));
    }
    Ok(())
}

pub fn validate_paired_eval(record: &PairedEvalRecord) -> Result<(), ValidationError> {
    if record.skill_id.trim().is_empty() {
        return Err(ValidationError::EmptyField("paired_eval.skill_id"));
    }
    if record.skill_version.trim().is_empty() {
        return Err(ValidationError::EmptyField("paired_eval.skill_version"));
    }
    if record.task_family.trim().is_empty() {
        return Err(ValidationError::EmptyField("paired_eval.task_family"));
    }
    if record.model_id.trim().is_empty() {
        return Err(ValidationError::EmptyField("paired_eval.model_id"));
    }
    if !valid_sha256(&record.repository_digest) {
        return Err(ValidationError::InvalidPairedEval(
            "repository_digest must be a lowercase SHA-256 digest".into(),
        ));
    }
    if !valid_sha256(&record.environment_digest) {
        return Err(ValidationError::InvalidPairedEval(
            "environment_digest must be a lowercase SHA-256 digest".into(),
        ));
    }
    if !record.baseline_score.is_finite() || !record.treatment_score.is_finite() {
        return Err(ValidationError::InvalidPairedEval(
            "baseline_score and treatment_score must be finite".into(),
        ));
    }
    if (record.baseline_success && record.baseline_gate_violations > 0)
        || (record.treatment_success && record.treatment_gate_violations > 0)
    {
        return Err(ValidationError::InvalidPairedEval(
            "a successful run must not record gate violations".into(),
        ));
    }
    Ok(())
}

pub fn validate_learning_decision(decision: &LearningDecision) -> Result<(), ValidationError> {
    if decision.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    let scores = &decision.scores;
    validate_unit("scores.correctness", scores.correctness)?;
    validate_unit("scores.utility", scores.utility)?;
    validate_unit("scores.novelty", scores.novelty)?;
    validate_unit("scores.generality", scores.generality)?;
    validate_unit("scores.confidence", scores.confidence)?;
    validate_unit("scores.risk", scores.risk)?;
    validate_unit("scores.cost", scores.cost)?;
    validate_unit("scores.expected_gain", scores.expected_gain)?;
    validate_unit("priority", decision.priority)?;
    if decision.actions.is_empty() {
        return Err(ValidationError::EmptyField("learning_decision.actions"));
    }
    if decision.controller.trim().is_empty() {
        return Err(ValidationError::EmptyField("learning_decision.controller"));
    }
    Ok(())
}

pub fn validate_training_candidate(candidate: &TrainingCandidate) -> Result<(), ValidationError> {
    if !valid_sha256(&candidate.dataset_hash) || !valid_sha256(&candidate.manifest_hash) {
        return Err(ValidationError::InvalidTrainingCandidate(
            "dataset_hash and manifest_hash must be lowercase SHA-256 digests".into(),
        ));
    }
    if candidate.status == TrainingCandidateStatus::ReadyForTraining {
        if candidate.decision_count < MIN_ROUTING_DECISIONS
            || candidate.paired_eval_count < MIN_PAIRED_EVALS
        {
            return Err(ValidationError::InvalidTrainingCandidate(
                "ready candidate does not meet the minimum evidence counts".into(),
            ));
        }
        if candidate.repository_split_count == 0 || candidate.task_family_split_count == 0 {
            return Err(ValidationError::InvalidTrainingCandidate(
                "ready candidate must span at least one repository and task family split".into(),
            ));
        }
    }
    if candidate.trainer_enabled && candidate.status != TrainingCandidateStatus::ReadyForTraining {
        return Err(ValidationError::InvalidTrainingCandidate(
            "trainer_enabled requires ready_for_training status".into(),
        ));
    }
    Ok(())
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
}

fn valid_http_url(value: &str) -> bool {
    let lower = value.trim().to_ascii_lowercase();
    (lower.starts_with("https://") || lower.starts_with("http://"))
        && !lower.contains('@')
        && !lower.contains('\\')
}

fn validate_unit(name: &'static str, value: f64) -> Result<(), ValidationError> {
    if !value.is_finite() || !(0.0..=1.0).contains(&value) {
        return Err(ValidationError::InvalidUnitScore(name));
    }
    Ok(())
}

pub fn validate_topic_watch(topic: &TopicWatch) -> Result<(), ValidationError> {
    if topic.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if topic.name.trim().is_empty() || topic.query.trim().is_empty() {
        return Err(ValidationError::InvalidTopic(
            "name and query are required".into(),
        ));
    }
    if !(30..=3_600).contains(&topic.refresh_seconds) {
        return Err(ValidationError::InvalidTopic(
            "refresh_seconds must be between 30 and 3600".into(),
        ));
    }
    if topic.languages.is_empty()
        || topic.languages.iter().any(|language| {
            language.is_empty()
                || language.len() > 16
                || !language
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || ch == '-')
        })
    {
        return Err(ValidationError::InvalidTopic(
            "invalid language list".into(),
        ));
    }
    if topic.budget.events_per_day == 0
        || topic.budget.events_per_day > 100_000
        || topic.budget.fetched_documents_per_day > 10_000
        || topic.budget.browser_escalations_per_day > 1_000
        || topic.budget.model_tokens_per_day > 10_000_000
    {
        return Err(ValidationError::InvalidTopic(
            "budget exceeds hard ceiling".into(),
        ));
    }
    Ok(())
}

pub fn validate_source_policy(policy: &SourcePolicy) -> Result<(), ValidationError> {
    if policy.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if policy.name.trim().is_empty() || !valid_http_url(&policy.base_url) {
        return Err(ValidationError::InvalidSourcePolicy(
            "name and canonical HTTP(S) base_url are required".into(),
        ));
    }
    if policy.max_depth > 5
        || policy.max_pages_per_run == 0
        || policy.max_pages_per_run > 1_000
        || policy.rate_limit_per_minute == 0
        || policy.rate_limit_per_minute > 600
        || policy.raw_retention_days == 0
        || policy.raw_retention_days > 90
    {
        return Err(ValidationError::InvalidSourcePolicy(
            "crawl or retention limits exceed hard ceilings".into(),
        ));
    }
    if policy.allowed_domains.iter().any(|domain| {
        domain.is_empty()
            || domain.contains('/')
            || domain.contains('@')
            || domain.parse::<std::net::IpAddr>().is_ok()
    }) {
        return Err(ValidationError::InvalidSourcePolicy(
            "allowed_domains must contain DNS names only".into(),
        ));
    }
    if policy.access_mode == SourceAccessMode::AuthenticatedLocal
        && policy
            .auth_secret_ref
            .as_deref()
            .unwrap_or_default()
            .trim()
            .is_empty()
    {
        return Err(ValidationError::InvalidSourcePolicy(
            "authenticated_local requires an opaque local secret reference".into(),
        ));
    }
    if policy.access_mode != SourceAccessMode::AuthenticatedLocal
        && policy.auth_secret_ref.is_some()
    {
        return Err(ValidationError::InvalidSourcePolicy(
            "public/API sources cannot persist an auth secret reference".into(),
        ));
    }
    if policy.access_mode == SourceAccessMode::AuthenticatedLocal
        && policy.external_processing != ExternalProcessingPermission::Denied
    {
        return Err(ValidationError::InvalidSourcePolicy(
            "authenticated local sources cannot be sent to an external model".into(),
        ));
    }
    Ok(())
}

pub fn validate_acquisition_plan(plan: &AcquisitionPlan) -> Result<(), ValidationError> {
    if plan.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if plan.query.trim().is_empty()
        || plan.source_policy_ids.is_empty()
        || plan.max_documents == 0
        || plan.max_documents > 5_000
        || plan.max_depth > 5
    {
        return Err(ValidationError::InvalidAcquisition(
            "invalid query, sources, depth, or document budget".into(),
        ));
    }
    Ok(())
}

pub fn validate_acquisition_attempt(attempt: &AcquisitionAttempt) -> Result<(), ValidationError> {
    if attempt.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_http_url(&attempt.url)
        || !valid_http_url(&attempt.canonical_url)
        || attempt.finished_at < attempt.started_at
        || !attempt.cost.is_finite()
        || attempt.cost < 0.0
    {
        return Err(ValidationError::InvalidAcquisition(
            "invalid URL, timestamps, or cost".into(),
        ));
    }
    if attempt
        .content_hash
        .as_deref()
        .is_some_and(|hash| !valid_sha256(hash))
    {
        return Err(ValidationError::InvalidContentHash);
    }
    Ok(())
}

pub fn validate_document_envelope(document: &DocumentEnvelope) -> Result<(), ValidationError> {
    if document.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_http_url(&document.url)
        || !valid_http_url(&document.canonical_url)
        || document.title.trim().is_empty()
        || document.extractor_version.trim().is_empty()
        || !valid_sha256(&document.cleaned_content_hash)
        || document
            .raw_content_hash
            .as_deref()
            .is_some_and(|hash| !valid_sha256(hash))
        || document.raw_expires_at < document.fetched_at
        || document.raw_expires_at > document.fetched_at + Duration::days(90)
        || document.rights.rights_source.trim().is_empty()
    {
        return Err(ValidationError::InvalidDocument(
            "invalid provenance, hashes, retention, or rights source".into(),
        ));
    }
    let mut rights = document.rights.clone();
    rights.recompute_training_eligible();
    if rights.training_eligible != document.rights.training_eligible
        || (document.rights.training_eligible
            && (document.prompt_injection_detected
                || document.pii_detected
                || document.secret_detected))
    {
        return Err(ValidationError::InvalidDocument(
            "training eligibility is inconsistent with rights or safety scans".into(),
        ));
    }
    Ok(())
}

pub fn validate_event_item(item: &EventItem) -> Result<(), ValidationError> {
    if item.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if item.platform.trim().is_empty()
        || item.external_id.trim().is_empty()
        || item.title.trim().is_empty()
    {
        return Err(ValidationError::InvalidEvent(
            "platform, external_id and title are required".into(),
        ));
    }
    if item.first_observed_at > item.last_observed_at {
        return Err(ValidationError::InvalidEvent(
            "first_observed_at must not exceed last_observed_at".into(),
        ));
    }
    if item
        .observations
        .iter()
        .any(|(day, _)| day.len() != 10 || NaiveDate::parse_from_str(day, "%Y-%m-%d").is_err())
    {
        return Err(ValidationError::InvalidEvent(
            "observation days must have YYYY-MM-DD shape".into(),
        ));
    }
    Ok(())
}

pub fn validate_tracked_event(event: &TrackedEvent) -> Result<(), ValidationError> {
    if event.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if event.title.trim().is_empty() {
        return Err(ValidationError::InvalidEvent("title is required".into()));
    }
    if event.first_seen_at > event.last_seen_at {
        return Err(ValidationError::InvalidEvent(
            "first_seen_at must not exceed last_seen_at".into(),
        ));
    }
    if event.item_count == 0 {
        return Err(ValidationError::InvalidEvent(
            "item_count must be at least 1".into(),
        ));
    }
    Ok(())
}

pub fn validate_knowledge_card(card: &KnowledgeCard) -> Result<(), ValidationError> {
    if card.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if card.revision == 0
        || card.title.trim().is_empty()
        || card.summary.trim().is_empty()
        || card.evidence.is_empty()
        || card.model_id.trim().is_empty()
        || !valid_sha256(&card.prompt_hash)
    {
        return Err(ValidationError::InvalidKnowledge(
            "revision, text, evidence, model and prompt hash are required".into(),
        ));
    }
    for (name, score) in [
        ("knowledge.relevance", card.scores.relevance),
        ("knowledge.novelty", card.scores.novelty),
        (
            "knowledge.source_reliability",
            card.scores.source_reliability,
        ),
        (
            "knowledge.extraction_completeness",
            card.scores.extraction_completeness,
        ),
        ("knowledge.confidence", card.scores.confidence),
        ("knowledge.risk", card.scores.risk),
    ] {
        validate_unit(name, score)?;
    }
    if !card.scores.cost.is_finite() || card.scores.cost < 0.0 {
        return Err(ValidationError::InvalidKnowledge(
            "cost must be non-negative".into(),
        ));
    }
    for claim in &card.claims {
        if claim.subject.trim().is_empty()
            || claim.predicate.trim().is_empty()
            || claim.object.trim().is_empty()
        {
            return Err(ValidationError::InvalidKnowledge(
                "empty atomic claim".into(),
            ));
        }
        validate_unit("claim.confidence", claim.confidence)?;
    }
    for evidence in &card.evidence {
        if !valid_http_url(&evidence.canonical_url) || !valid_sha256(&evidence.content_hash) {
            return Err(ValidationError::InvalidKnowledge(
                "invalid evidence provenance".into(),
            ));
        }
    }
    if card.training_eligible
        && (card.status != KnowledgeStatus::Corroborated
            || card.scores.risk >= 0.5
            || card
                .evidence
                .iter()
                .any(|item| item.relationship != EvidenceRelationship::Supports))
    {
        return Err(ValidationError::InvalidKnowledge(
            "training eligible cards must be low-risk and corroborated".into(),
        ));
    }
    Ok(())
}

pub fn validate_meta_model_bundle(bundle: &MetaModelBundle) -> Result<(), ValidationError> {
    if bundle.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_id(&bundle.model_id)
        || Version::parse(&bundle.version).is_err()
        || !valid_sha256(&bundle.artifact_hash)
        || bundle.base_model.trim().is_empty()
        || bundle.trainer.trim().is_empty()
    {
        return Err(ValidationError::InvalidMetaModel(
            "invalid identity, version, artifact, or trainer".into(),
        ));
    }
    for (name, value) in [
        ("meta.old_task_retention", bundle.metrics.old_task_retention),
        ("meta.ndcg_at_10", bundle.metrics.ndcg_at_10),
        (
            "meta.baseline_ndcg_at_10",
            bundle.metrics.baseline_ndcg_at_10,
        ),
        (
            "meta.max_core_topic_regression",
            bundle.metrics.max_core_topic_regression,
        ),
    ] {
        validate_unit(name, value)?;
    }
    if !bundle.metrics.fact_precision_delta.is_finite()
        || !bundle.metrics.cost_per_useful_card_change.is_finite()
    {
        return Err(ValidationError::InvalidMetaModel(
            "non-finite metric".into(),
        ));
    }
    if matches!(
        bundle.status,
        MetaModelStatus::Canary | MetaModelStatus::Active
    ) && !bundle.metrics.passes_automatic_activation()
    {
        return Err(ValidationError::InvalidMetaModel(
            "canary/active model fails automatic activation gates".into(),
        ));
    }
    Ok(())
}

pub fn validate_curriculum(request: &CreateCurriculumRequest) -> Result<(), ValidationError> {
    if request.topic.trim().is_empty() {
        return Err(ValidationError::EmptyField("curriculum.topic"));
    }
    if request.query.trim().is_empty() {
        return Err(ValidationError::EmptyField("curriculum.query"));
    }
    let budget = request.policy.daily_budget;
    if budget.search_plans == 0
        || budget.search_plans > 20
        || budget.new_repositories > 50
        || budget.files > 500
    {
        return Err(ValidationError::ExcessiveCurriculumBudget);
    }
    if !request.policy.topics.is_empty()
        && !request
            .policy
            .topics
            .iter()
            .any(|topic| topic.eq_ignore_ascii_case(request.topic.trim()))
    {
        return Err(ValidationError::InvalidId(request.topic.clone()));
    }
    Ok(())
}

fn valid_digest(value: &str) -> bool {
    value.len() == 64
        && value
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
}

pub fn validate_coding_benchmark(
    manifest: &CodingBenchmarkManifest,
) -> Result<(), ValidationError> {
    if manifest.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_id(&manifest.benchmark_id) || manifest.version.trim().is_empty() {
        return Err(ValidationError::InvalidBenchmark(
            "benchmark id and version are required".into(),
        ));
    }
    let image_digest = manifest
        .container_image
        .rsplit_once("@sha256:")
        .map(|(_, digest)| digest)
        .filter(|digest| valid_digest(digest))
        .ok_or_else(|| {
            ValidationError::InvalidBenchmark(
                "container image must be pinned by a lowercase sha256 digest".into(),
            )
        })?;
    let _ = image_digest;
    if manifest.tasks.len() != 60 {
        return Err(ValidationError::InvalidBenchmark(
            "verify benchmark must contain exactly 60 tasks".into(),
        ));
    }
    let mut ids = HashSet::new();
    let mut family_split = HashMap::new();
    let mut split_counts = [0_u32; 3];
    for task in &manifest.tasks {
        if !valid_id(&task.task_id) || !valid_id(&task.template_family) {
            return Err(ValidationError::InvalidBenchmark(
                "task and template-family ids must be safe identifiers".into(),
            ));
        }
        if !ids.insert(task.task_id.clone()) {
            return Err(ValidationError::InvalidBenchmark(format!(
                "duplicate task id {}",
                task.task_id
            )));
        }
        if !valid_digest(&task.bundle_hash) {
            return Err(ValidationError::InvalidBenchmark(format!(
                "task {} has an invalid bundle hash",
                task.task_id
            )));
        }
        if task.test_command != "pytest -q" {
            return Err(ValidationError::InvalidBenchmark(format!(
                "task {} does not use the fixed pytest command",
                task.task_id
            )));
        }
        if let Some(previous) = family_split.insert(task.template_family.clone(), task.split)
            && previous != task.split
        {
            return Err(ValidationError::InvalidBenchmark(format!(
                "template family {} leaks across splits",
                task.template_family
            )));
        }
        split_counts[match task.split {
            BenchmarkSplit::Train => 0,
            BenchmarkSplit::Validation => 1,
            BenchmarkSplit::Holdout => 2,
        }] += 1;
    }
    if split_counts != [30, 15, 15] {
        return Err(ValidationError::InvalidBenchmark(format!(
            "split counts must be 30/15/15, got {}/{}/{}",
            split_counts[0], split_counts[1], split_counts[2]
        )));
    }
    let policy = &manifest.scoring;
    let weights = [
        policy.correctness_weight,
        policy.fresh_verification_weight,
        policy.claim_calibration_weight,
        policy.efficiency_weight,
    ];
    if weights
        .iter()
        .any(|value| !value.is_finite() || !(0.0..=1.0).contains(value))
        || (weights.iter().sum::<f64>() - 1.0).abs() > 1e-9
        || !policy.minimum_soft_improvement.is_finite()
        || !(0.0..=1.0).contains(&policy.minimum_soft_improvement)
    {
        return Err(ValidationError::InvalidBenchmark(
            "scoring weights must be finite unit values summing to one".into(),
        ));
    }
    Ok(())
}

pub fn validate_optimization_budget(budget: &OptimizationBudget) -> Result<(), ValidationError> {
    let ceiling = OptimizationBudget::default();
    if budget.epochs == 0
        || budget.epochs > ceiling.epochs
        || budget.batch_size == 0
        || budget.batch_size > ceiling.batch_size
        || budget.max_candidate_steps == 0
        || budget.max_candidate_steps > ceiling.max_candidate_steps
        || budget.max_edits_per_candidate == 0
        || budget.max_edits_per_candidate > ceiling.max_edits_per_candidate
        || budget.max_net_new_tokens <= 0
        || budget.max_net_new_tokens > ceiling.max_net_new_tokens
        || budget.max_skill_tokens == 0
        || budget.max_skill_tokens > ceiling.max_skill_tokens
        || budget.target_call_limit == 0
        || budget.target_call_limit > ceiling.target_call_limit
        || budget.optimizer_call_limit == 0
        || budget.optimizer_call_limit > ceiling.optimizer_call_limit
        || budget.total_token_limit == 0
        || budget.total_token_limit > ceiling.total_token_limit
        || budget.wall_time_seconds == 0
        || budget.wall_time_seconds > ceiling.wall_time_seconds
        || budget.no_improvement_limit == 0
        || budget.no_improvement_limit > ceiling.no_improvement_limit
    {
        return Err(ValidationError::InvalidOptimization(
            "optimization budget exceeds the v2.1 hard ceiling or contains zero values".into(),
        ));
    }
    Ok(())
}

pub fn validate_optimization_request(
    request: &CreateOptimizationRunRequest,
) -> Result<(), ValidationError> {
    if !valid_id(&request.skill_id) {
        return Err(ValidationError::InvalidId(request.skill_id.clone()));
    }
    Version::parse(&request.skill_version)
        .map_err(|_| ValidationError::InvalidVersion(request.skill_version.clone()))?;
    for (name, digest) in [
        ("benchmark_manifest_hash", &request.benchmark_manifest_hash),
        ("benchmark_bundle_hash", &request.benchmark_bundle_hash),
    ] {
        if !valid_digest(digest) {
            return Err(ValidationError::InvalidOptimization(format!(
                "{name} must be a lowercase SHA-256 digest"
            )));
        }
    }
    if request
        .container_image_digest
        .rsplit_once("@sha256:")
        .map(|(_, digest)| valid_digest(digest))
        != Some(true)
    {
        return Err(ValidationError::InvalidOptimization(
            "container image must be digest pinned".into(),
        ));
    }
    if request.target_model.trim().is_empty() || request.optimizer_model.trim().is_empty() {
        return Err(ValidationError::InvalidOptimization(
            "target and optimizer model ids are required".into(),
        ));
    }
    validate_optimization_budget(&request.budget)
}

pub fn validate_skill_edit_patch(
    patch: &SkillEditPatch,
    budget: &OptimizationBudget,
) -> Result<(), ValidationError> {
    if patch.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if patch.edits.is_empty() || patch.edits.len() > budget.max_edits_per_candidate as usize {
        return Err(ValidationError::InvalidOptimization(
            "patch edit count is outside the configured budget".into(),
        ));
    }
    if !valid_digest(&patch.baseline_hash) || !valid_digest(&patch.candidate_hash) {
        return Err(ValidationError::InvalidOptimization(
            "patch hashes must be lowercase SHA-256 digests".into(),
        ));
    }
    if patch.rationale.trim().is_empty() || patch.optimizer_model.trim().is_empty() {
        return Err(ValidationError::InvalidOptimization(
            "patch rationale and optimizer model are required".into(),
        ));
    }
    if patch.token_delta.unsigned_abs() > budget.max_net_new_tokens as u32 {
        return Err(ValidationError::InvalidOptimization(
            "patch token delta exceeds the configured budget".into(),
        ));
    }
    for edit in &patch.edits {
        if !matches!(edit.operation, SkillEditOperation::Append) && edit.target.is_empty() {
            return Err(ValidationError::InvalidOptimization(
                "non-append edits require an exact target".into(),
            ));
        }
        if matches!(
            edit.operation,
            SkillEditOperation::Append
                | SkillEditOperation::InsertAfter
                | SkillEditOperation::Replace
        ) && edit.content.trim().is_empty()
        {
            return Err(ValidationError::InvalidOptimization(
                "content-bearing edit contains empty content".into(),
            ));
        }
    }
    Ok(())
}

fn validate_task_score(score: &OptimizationTaskScore) -> Result<(), ValidationError> {
    if !valid_id(&score.task_id) {
        return Err(ValidationError::InvalidId(score.task_id.clone()));
    }
    for (name, value) in [
        ("baseline_hard", score.baseline_hard),
        ("candidate_hard", score.candidate_hard),
        ("baseline_soft", score.baseline_soft),
        ("candidate_soft", score.candidate_soft),
    ] {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(ValidationError::InvalidOptimization(format!(
                "{name} must be a finite unit score"
            )));
        }
    }
    Ok(())
}

pub fn evaluation_gate_passes(
    policy: &OptimizationScoringPolicy,
    scores: &[OptimizationTaskScore],
) -> bool {
    if scores.is_empty()
        || scores
            .iter()
            .any(|score| validate_task_score(score).is_err())
    {
        return false;
    }
    if scores.iter().any(|score| score.safety_violation) {
        return false;
    }
    if policy.no_hard_regression
        && scores
            .iter()
            .any(|score| score.candidate_hard + 1e-12 < score.baseline_hard)
    {
        return false;
    }
    let count = scores.len() as f64;
    let baseline_hard = scores.iter().map(|score| score.baseline_hard).sum::<f64>() / count;
    let candidate_hard = scores.iter().map(|score| score.candidate_hard).sum::<f64>() / count;
    let baseline_soft = scores.iter().map(|score| score.baseline_soft).sum::<f64>() / count;
    let candidate_soft = scores.iter().map(|score| score.candidate_soft).sum::<f64>() / count;
    candidate_hard > baseline_hard + 1e-12
        || ((candidate_hard - baseline_hard).abs() <= 1e-12
            && candidate_soft >= baseline_soft + policy.minimum_soft_improvement)
}

pub fn validate_candidate_evaluation(
    evaluation: &CandidateEvaluation,
    policy: &OptimizationScoringPolicy,
) -> Result<bool, ValidationError> {
    if !valid_digest(&evaluation.candidate_hash) || evaluation.task_scores.is_empty() {
        return Err(ValidationError::InvalidOptimization(
            "candidate evaluation lacks a valid hash or task scores".into(),
        ));
    }
    for score in &evaluation.task_scores {
        validate_task_score(score)?;
    }
    let count = evaluation.task_scores.len() as f64;
    let means = [
        evaluation
            .task_scores
            .iter()
            .map(|score| score.baseline_hard)
            .sum::<f64>()
            / count,
        evaluation
            .task_scores
            .iter()
            .map(|score| score.candidate_hard)
            .sum::<f64>()
            / count,
        evaluation
            .task_scores
            .iter()
            .map(|score| score.baseline_soft)
            .sum::<f64>()
            / count,
        evaluation
            .task_scores
            .iter()
            .map(|score| score.candidate_soft)
            .sum::<f64>()
            / count,
    ];
    let supplied = [
        evaluation.baseline_hard_mean,
        evaluation.candidate_hard_mean,
        evaluation.baseline_soft_mean,
        evaluation.candidate_soft_mean,
    ];
    if means
        .iter()
        .zip(supplied)
        .any(|(actual, supplied)| (actual - supplied).abs() > 1e-9)
    {
        return Err(ValidationError::InvalidOptimization(
            "candidate evaluation means do not match task scores".into(),
        ));
    }
    Ok(evaluation_gate_passes(policy, &evaluation.task_scores))
}

pub fn paired_bootstrap_ci95_low(scores: &[OptimizationTaskScore]) -> Option<f64> {
    if scores.is_empty() {
        return None;
    }
    let deltas: Vec<f64> = scores
        .iter()
        .map(|score| score.candidate_hard - score.baseline_hard)
        .collect();
    let mut state = 0x9e37_79b9_7f4a_7c15_u64;
    let mut samples = Vec::with_capacity(10_000);
    for _ in 0..10_000 {
        let mut total = 0.0;
        for _ in 0..deltas.len() {
            state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            total += deltas[(state as usize) % deltas.len()];
        }
        samples.push(total / deltas.len() as f64);
    }
    samples.sort_by(f64::total_cmp);
    Some(samples[249])
}

pub fn validate_holdout_evaluation(holdout: &HoldoutEvaluation) -> Result<bool, ValidationError> {
    if holdout.seeds != [1729, 2718] {
        return Err(ValidationError::InvalidOptimization(
            "holdout must use the two protocol-fixed seeds 1729 and 2718".into(),
        ));
    }
    if holdout.paired_runs as usize != holdout.task_scores.len() || holdout.paired_runs < 30 {
        return Err(ValidationError::InvalidOptimization(
            "holdout must contain at least 30 paired runs".into(),
        ));
    }
    for score in &holdout.task_scores {
        validate_task_score(score)?;
    }
    let actual_low = paired_bootstrap_ci95_low(&holdout.task_scores)
        .ok_or_else(|| ValidationError::InvalidOptimization("holdout scores are empty".into()))?;
    if (actual_low - holdout.bootstrap_ci95_low).abs() > 1e-9 {
        return Err(ValidationError::InvalidOptimization(
            "holdout bootstrap bound does not match paired scores".into(),
        ));
    }
    let positive = actual_low > 0.0
        && holdout.safety_violation_delta <= 0
        && !holdout
            .task_scores
            .iter()
            .any(|score| score.safety_violation);
    Ok(positive)
}

pub fn validate_skillopt_commit(commit: &str) -> Result<(), ValidationError> {
    if commit != SKILLOPT_UPSTREAM_COMMIT {
        return Err(ValidationError::InvalidOptimization(
            "worker does not use the pinned SkillOpt commit".into(),
        ));
    }
    Ok(())
}

pub fn validate_skillopt_provenance(
    commit: &str,
    source_archive_sha256: &str,
    registration_patch_sha256: &str,
) -> Result<(), ValidationError> {
    validate_skillopt_commit(commit)?;
    if source_archive_sha256 != SKILLOPT_UPSTREAM_ARCHIVE_SHA256
        || registration_patch_sha256 != SKILLOPT_REGISTRATION_PATCH_SHA256
    {
        return Err(ValidationError::InvalidOptimization(
            "worker source archive or registration patch differs from the pinned provenance".into(),
        ));
    }
    Ok(())
}

pub fn validate_meta_decision_trace(trace: &MetaDecisionTrace) -> Result<(), ValidationError> {
    if trace.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_sha256(&trace.input_hash)
        || trace.source_domain.trim().is_empty()
        || trace.topic_family.trim().is_empty()
        || trace.policy_version.trim().is_empty()
        || trace.controller_version.trim().is_empty()
        || serde_json::to_vec(&trace.input).map_or(true, |value| value.len() > 1_048_576)
        || serde_json::to_vec(&trace.output).map_or(true, |value| value.len() > 1_048_576)
    {
        return Err(ValidationError::InvalidMetaModel(
            "invalid decision provenance, grouping, or payload".into(),
        ));
    }
    validate_unit("meta_decision.confidence", trace.confidence)?;
    if !trace.cost.is_finite() || trace.cost < 0.0 {
        return Err(ValidationError::InvalidMetaModel(
            "decision cost must be non-negative".into(),
        ));
    }
    if trace.training_eligible && (trace.policy_violations != 0 || trace.prompt_injection_detected)
    {
        return Err(ValidationError::InvalidMetaModel(
            "unsafe decisions cannot be training eligible".into(),
        ));
    }
    if trace
        .redaction_attestation_hash
        .as_deref()
        .is_some_and(|hash| !valid_sha256(hash))
    {
        return Err(ValidationError::InvalidQuality(
            "externally processed decisions require a redaction attestation".into(),
        ));
    }
    if matches!(
        trace.task_kind,
        MetaTaskKind::TemporalGrounding
            | MetaTaskKind::KnowledgeBoundary
            | MetaTaskKind::SearchPlanning
    ) {
        let decision: MetacognitionDecision = serde_json::from_value(trace.output.clone())
            .map_err(|_| {
                ValidationError::InvalidMetaModel(
                    "metacognition trace output fails the decision contract".into(),
                )
            })?;
        validate_metacognition_decision(&decision)?;
    }
    Ok(())
}

/// Fail-closed validation of the metacognition decision contract carried in
/// `MetaDecisionTrace.output` for the three metacognition task kinds.
pub fn validate_metacognition_decision(
    decision: &MetacognitionDecision,
) -> Result<(), ValidationError> {
    validate_unit("metacognition.confidence", decision.confidence)?;
    if let Some(hours) = decision.freshness_hours
        && !(1..=8760).contains(&hours)
    {
        return Err(ValidationError::InvalidMetaModel(
            "freshness_hours must be within 1..=8760".into(),
        ));
    }
    if decision.query.as_deref().is_some_and(str::is_empty)
        || decision.answer.as_deref().is_some_and(str::is_empty)
    {
        return Err(ValidationError::InvalidMetaModel(
            "query and answer must be non-empty when present".into(),
        ));
    }
    let discipline_ok = match decision.action {
        MetacognitionAction::Answer => {
            decision.answer.is_some()
                && decision.query.is_none()
                && decision.freshness_hours.is_none()
                && matches!(
                    decision.answer_basis,
                    MetacognitionBasis::Parametric | MetacognitionBasis::Evidence
                )
        }
        MetacognitionAction::SearchInternal => {
            decision.query.is_some()
                && decision.answer.is_none()
                && decision.answer_basis == MetacognitionBasis::None
        }
        MetacognitionAction::RequestAcquisition => {
            decision.query.is_some()
                && decision.freshness_hours.is_some()
                && decision.answer.is_none()
                && decision.answer_basis == MetacognitionBasis::None
        }
        MetacognitionAction::Insufficient => {
            decision.answer.is_none()
                && decision.query.is_none()
                && decision.freshness_hours.is_none()
                && decision.answer_basis == MetacognitionBasis::None
        }
    };
    if !discipline_ok {
        return Err(ValidationError::InvalidMetaModel(
            "metacognition decision violates per-action field discipline".into(),
        ));
    }
    Ok(())
}
pub fn validate_meta_replay_evaluation(
    evaluation: &MetaReplayEvaluation,
) -> Result<(), ValidationError> {
    if evaluation.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if evaluation.task_id.trim().is_empty()
        || evaluation.source_domain.trim().is_empty()
        || evaluation.topic_family.trim().is_empty()
    {
        return Err(ValidationError::InvalidMetaModel(
            "replay task and split groups are required".into(),
        ));
    }
    validate_unit("meta_replay.baseline_score", evaluation.baseline_score)?;
    validate_unit("meta_replay.candidate_score", evaluation.candidate_score)?;
    if evaluation
        .redaction_attestation_hash
        .as_deref()
        .is_some_and(|hash| !valid_sha256(hash))
    {
        return Err(ValidationError::InvalidQuality(
            "externally processed replays require a redaction attestation".into(),
        ));
    }
    Ok(())
}

pub fn validate_meta_canary_decision(decision: &MetaCanaryDecision) -> Result<(), ValidationError> {
    if decision.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_id(&decision.model_id)
        || Version::parse(&decision.version).is_err()
        || !decision.cost.is_finite()
        || decision.cost < 0.0
        || (decision.policy_violation && decision.successful)
    {
        return Err(ValidationError::InvalidMetaModel(
            "invalid canary model, cost, or safety outcome".into(),
        ));
    }
    Ok(())
}

pub fn validate_dataset_build(build: &DatasetBuild) -> Result<(), ValidationError> {
    if build.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if build.kind.trim().is_empty()
        || build.policy_version.trim().is_empty()
        || !valid_sha256(&build.bundle_hash)
        || !valid_sha256(&build.manifest_hash)
        || !valid_sha256(&build.dedup_key)
    {
        return Err(ValidationError::InvalidDataset(
            "build identity, policy, or digest is invalid".into(),
        ));
    }
    let shard_records = build.shards.iter().try_fold(0_u64, |total, shard| {
        if shard.record_kind.trim().is_empty()
            || !valid_sha256(&shard.object_hash)
            || !valid_sha256(&shard.uncompressed_hash)
            || shard.record_count == 0
            || shard.compressed_bytes == 0
        {
            return Err(ValidationError::InvalidDataset(
                "dataset shard is empty or lacks a valid digest".into(),
            ));
        }
        total
            .checked_add(shard.record_count)
            .ok_or_else(|| ValidationError::InvalidDataset("dataset record count overflows".into()))
    })?;
    if shard_records != build.split_stats.total()
        || shard_records != build.decision_count + build.replay_eval_count
        || shard_records != build.eligibility.eligible_records
        || build.eligibility.policy_version != build.policy_version
        || build.eligibility.contains_raw_documents
        || !build.eligibility.passed
    {
        return Err(ValidationError::InvalidDataset(
            "dataset counts or training eligibility report are inconsistent".into(),
        ));
    }
    let expert_fields = [
        build.expert_view_id.is_some(),
        build.expert_manifest_hash.is_some(),
        build.expert_taxonomy_hash.is_some(),
    ];
    if expert_fields.iter().any(|value| *value)
        && (!expert_fields.iter().all(|value| *value)
            || !valid_sha256(build.expert_manifest_hash.as_deref().unwrap_or_default())
            || !valid_sha256(build.expert_taxonomy_hash.as_deref().unwrap_or_default()))
    {
        return Err(ValidationError::InvalidDataset(
            "expert dataset references must be complete SHA-256-bound metadata".into(),
        ));
    }
    Ok(())
}

pub fn validate_dataset_snapshot(snapshot: &DatasetSnapshot) -> Result<(), ValidationError> {
    if snapshot.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if snapshot.kind.trim().is_empty()
        || snapshot.created_by.trim().is_empty()
        || snapshot.reason.trim().is_empty()
        || !valid_sha256(&snapshot.bundle_hash)
        || !valid_sha256(&snapshot.manifest_hash)
        || snapshot.split_stats.total() != snapshot.decision_count + snapshot.replay_eval_count
        || snapshot.eligibility.eligible_records != snapshot.split_stats.total()
        || snapshot.eligibility.contains_raw_documents
        || !snapshot.eligibility.passed
    {
        return Err(ValidationError::InvalidDataset(
            "snapshot provenance, counts, or eligibility are invalid".into(),
        ));
    }
    let expert_fields = [
        snapshot.expert_view_id.is_some(),
        snapshot.expert_manifest_hash.is_some(),
        snapshot.expert_taxonomy_hash.is_some(),
    ];
    if expert_fields.iter().any(|value| *value)
        && (!expert_fields.iter().all(|value| *value)
            || !valid_sha256(snapshot.expert_manifest_hash.as_deref().unwrap_or_default())
            || !valid_sha256(snapshot.expert_taxonomy_hash.as_deref().unwrap_or_default()))
    {
        return Err(ValidationError::InvalidDataset(
            "snapshot expert dataset references are incomplete".into(),
        ));
    }
    let quality_fields = [
        snapshot.quality_report_id.is_some(),
        snapshot.quality_report_hash.is_some(),
    ];
    if quality_fields.iter().any(|value| *value)
        && (!quality_fields.iter().all(|value| *value)
            || !valid_sha256(snapshot.quality_report_hash.as_deref().unwrap_or_default()))
    {
        return Err(ValidationError::InvalidDataset(
            "snapshot quality report references are incomplete".into(),
        ));
    }
    Ok(())
}

pub fn validate_redaction_attestation(
    attestation: &RedactionAttestation,
) -> Result<(), ValidationError> {
    if attestation.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if attestation.subject_id.trim().is_empty()
        || attestation.scanner_version.trim().is_empty()
        || !valid_sha256(&attestation.subject_hash)
        || !valid_sha256(&attestation.exported_payload_hash)
        || attestation.secret_findings != 0
        || attestation.pii_findings != 0
        || attestation.prompt_injection_findings != 0
        || attestation.exported_characters > attestation.source_characters
    {
        return Err(ValidationError::InvalidQuality(
            "redaction attestation is unsafe or incomplete".into(),
        ));
    }
    Ok(())
}

pub fn validate_data_quality_assessment(
    assessment: &DataQualityAssessment,
) -> Result<(), ValidationError> {
    if assessment.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if assessment.subject_id.trim().is_empty()
        || assessment.model_id.trim().is_empty()
        || assessment.system_fingerprint.trim().is_empty()
        || assessment.prompt_version.trim().is_empty()
        || !valid_sha256(&assessment.subject_hash)
        || !valid_sha256(&assessment.prompt_hash)
        || !valid_sha256(&assessment.schema_hash)
        || !valid_sha256(&assessment.redaction_attestation_hash)
        || !valid_sha256(&assessment.output_hash)
        || assessment.issue_codes.len() > 32
        || assessment.evidence_refs.len() > 32
        || assessment.suggested_actions.len() > 16
    {
        return Err(ValidationError::InvalidQuality(
            "quality assessment identity, hashes, or bounded lists are invalid".into(),
        ));
    }
    for (name, value) in [
        ("quality.groundedness", assessment.dimensions.groundedness),
        ("quality.correctness", assessment.dimensions.correctness),
        ("quality.relevance", assessment.dimensions.relevance),
        ("quality.consistency", assessment.dimensions.consistency),
        ("quality.completeness", assessment.dimensions.completeness),
        (
            "quality.label_confidence",
            assessment.dimensions.label_confidence,
        ),
        ("quality.ambiguity", assessment.dimensions.ambiguity),
        ("quality.privacy_risk", assessment.dimensions.privacy_risk),
        (
            "quality.injection_risk",
            assessment.dimensions.injection_risk,
        ),
        ("quality.confidence", assessment.confidence),
    ] {
        validate_unit(name, value)?;
    }
    if assessment.usage.prompt_cache_hit_tokens + assessment.usage.prompt_cache_miss_tokens
        != assessment.usage.prompt_tokens
        || assessment.usage.prompt_tokens + assessment.usage.completion_tokens
            != assessment.usage.total_tokens
    {
        return Err(ValidationError::InvalidQuality(
            "quality assessment token usage is inconsistent".into(),
        ));
    }
    Ok(())
}

pub fn validate_model_endpoint_version(
    version: &ModelEndpointVersion,
) -> Result<(), ValidationError> {
    if version.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if version.provider.trim().is_empty()
        || version.model_id.trim().is_empty()
        || version.system_fingerprint.trim().is_empty()
        || version.prompt_version.trim().is_empty()
        || !valid_sha256(&version.schema_hash)
    {
        return Err(ValidationError::InvalidQuality(
            "model endpoint identity is incomplete".into(),
        ));
    }
    for (name, value) in [
        (
            "calibration.schema_valid_rate",
            version.metrics.schema_valid_rate,
        ),
        (
            "calibration.critical_safety_recall",
            version.metrics.critical_safety_recall,
        ),
        (
            "calibration.verdict_macro_f1",
            version.metrics.verdict_macro_f1,
        ),
    ] {
        validate_unit(name, value)?;
    }
    if let Some(rate) = version.metrics.shadow_disagreement_rate {
        validate_unit("calibration.shadow_disagreement_rate", rate)?;
    }
    if version.status == ModelEndpointStatus::Active
        && (version.approved_by.as_deref().is_none_or(str::is_empty)
            || version.approval_reason.as_deref().is_none_or(str::is_empty))
    {
        return Err(ValidationError::InvalidQuality(
            "the first active model endpoint requires an approval identity and reason".into(),
        ));
    }
    Ok(())
}

pub fn validate_provider_pricing_policy(
    policy: &ProviderPricingPolicy,
) -> Result<(), ValidationError> {
    if policy.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if policy.policy_id.trim().is_empty()
        || policy.provider.trim().is_empty()
        || ![
            policy.flash_input_cache_hit_usd_per_million,
            policy.flash_input_cache_miss_usd_per_million,
            policy.flash_output_usd_per_million,
            policy.pro_input_cache_hit_usd_per_million,
            policy.pro_input_cache_miss_usd_per_million,
            policy.pro_output_usd_per_million,
            policy.usd_to_cny_ceiling,
            policy.daily_max_cny,
        ]
        .into_iter()
        .all(|value| value.is_finite() && value > 0.0)
        || policy.daily_max_cny > 10.0
        || policy.usd_to_cny_ceiling < 1.0
        || policy.usd_to_cny_ceiling > 20.0
    {
        return Err(ValidationError::InvalidQuality(
            "provider pricing or daily budget is invalid".into(),
        ));
    }
    Ok(())
}

pub fn validate_synthetic_training_candidate(
    candidate: &SyntheticTrainingCandidate,
) -> Result<(), ValidationError> {
    if candidate.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if candidate.parent_subject_kind == crate::QualitySubjectKind::SyntheticCandidate
        || candidate.generation_depth != 1
        || candidate.parent_subject_id.trim().is_empty()
        || candidate.source_license.trim().is_empty()
        || candidate.generation_model_id.trim().is_empty()
        || candidate.generation_system_fingerprint.trim().is_empty()
        || candidate.generation_prompt_version.trim().is_empty()
        || !valid_sha256(&candidate.generation_prompt_hash)
        || !valid_sha256(&candidate.parent_hash)
        || !valid_sha256(&candidate.content_hash)
        || candidate.evidence_refs.is_empty()
        || candidate.evidence_refs.len() > 32
        || serde_json::to_vec(&candidate.input).map_or(true, |value| value.len() > 1_048_576)
        || serde_json::to_vec(&candidate.output).map_or(true, |value| value.len() > 1_048_576)
        || (candidate.status == SyntheticCandidateStatus::Verified && !candidate.objective_verified)
        || (candidate.status == SyntheticCandidateStatus::Approved
            && candidate.reviewed_by.as_deref().is_none_or(str::is_empty))
        || candidate.generation_usage.prompt_cache_hit_tokens
            + candidate.generation_usage.prompt_cache_miss_tokens
            != candidate.generation_usage.prompt_tokens
        || candidate.generation_usage.prompt_tokens + candidate.generation_usage.completion_tokens
            != candidate.generation_usage.total_tokens
    {
        return Err(ValidationError::InvalidQuality(
            "synthetic candidate lineage, evidence, or status is invalid".into(),
        ));
    }
    Ok(())
}

pub fn validate_dataset_quality_report(
    report: &DatasetQualityReport,
) -> Result<(), ValidationError> {
    if report.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if report.policy_version.trim().is_empty()
        || !valid_sha256(&report.report_hash)
        || report.assessed_records > report.total_records
        || report.generated_records > report.total_records
        || !report.generated_ratio.is_finite()
        || !(0.0..=1.0).contains(&report.generated_ratio)
        || !report.disagreement_rate.is_finite()
        || !(0.0..=1.0).contains(&report.disagreement_rate)
        || report
            .estimated_cost_cny
            .is_some_and(|cost| !cost.is_finite() || cost < 0.0)
    {
        return Err(ValidationError::InvalidQuality(
            "dataset quality report counts, hashes, or scores are invalid".into(),
        ));
    }
    let actual_generated_ratio = if report.total_records == 0 {
        0.0
    } else {
        report.generated_records as f64 / report.total_records as f64
    };
    let actual_disagreement_rate = if report.pro_audit_sample_size == 0 {
        0.0
    } else {
        report.non_safety_disagreements as f64 / report.pro_audit_sample_size as f64
    };
    if (actual_generated_ratio - report.generated_ratio).abs() > 1e-9
        || (actual_disagreement_rate - report.disagreement_rate).abs() > 1e-9
        || (report.gate_passed
            && (report.assessed_records != report.total_records
                || report.unresolved_records != 0
                || report.deterministic_violations != 0
                || report.split_leakage_count != 0
                || report.lineage_missing_count != 0
                || report.generated_ratio > 0.20
                || report.critical_safety_misses != 0
                || report.disagreement_rate > 0.02))
    {
        return Err(ValidationError::InvalidQuality(
            "dataset quality report gate is inconsistent with its metrics".into(),
        ));
    }
    Ok(())
}

pub fn validate_expert_taxonomy(taxonomy: &ExpertTaxonomy) -> Result<(), ValidationError> {
    if taxonomy.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if !valid_id(&taxonomy.taxonomy_id)
        || Version::parse(&taxonomy.version).is_err()
        || !valid_id(&taxonomy.fallback_expert_id)
        || taxonomy.router_top_k != 1
        || taxonomy.policy_version.trim().is_empty()
        || taxonomy.experts.len() < 2
    {
        return Err(ValidationError::InvalidDataset(
            "expert taxonomy identity or Top-1 routing policy is invalid".into(),
        ));
    }
    let mut ids = HashSet::new();
    let mut task_kinds = HashSet::new();
    let mut fallback_count = 0;
    for expert in &taxonomy.experts {
        if !valid_id(&expert.id)
            || expert.description.trim().is_empty()
            || !ids.insert(expert.id.as_str())
        {
            return Err(ValidationError::InvalidDataset(
                "expert definitions require unique identifiers and descriptions".into(),
            ));
        }
        if expert.is_fallback {
            fallback_count += 1;
            if expert.id != taxonomy.fallback_expert_id || !expert.task_kinds.is_empty() {
                return Err(ValidationError::InvalidDataset(
                    "the fallback expert must be task-agnostic and match the taxonomy".into(),
                ));
            }
        } else if expert.task_kinds.is_empty()
            || expert
                .task_kinds
                .iter()
                .any(|kind| !task_kinds.insert(*kind))
        {
            return Err(ValidationError::InvalidDataset(
                "non-fallback experts require non-overlapping task kinds".into(),
            ));
        }
    }
    if fallback_count != 1 {
        return Err(ValidationError::InvalidDataset(
            "expert taxonomy requires exactly one fallback expert".into(),
        ));
    }
    Ok(())
}

pub fn validate_expert_assignment(
    assignment: &ExpertAssignment,
    taxonomy: &ExpertTaxonomy,
) -> Result<(), ValidationError> {
    validate_expert_taxonomy(taxonomy)?;
    let ids: HashSet<_> = taxonomy
        .experts
        .iter()
        .map(|expert| expert.id.as_str())
        .collect();
    if !valid_sha256(&assignment.record_hash)
        || assignment.record_kind.trim().is_empty()
        || !ids.contains(assignment.primary_expert_id.as_str())
        || assignment
            .secondary_expert_ids
            .iter()
            .any(|id| id == &assignment.primary_expert_id || !ids.contains(id.as_str()))
    {
        return Err(ValidationError::InvalidDataset(
            "expert assignment has an invalid record or route".into(),
        ));
    }
    Ok(())
}

pub fn validate_expert_dataset_view(view: &ExpertDatasetView) -> Result<(), ValidationError> {
    if view.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    validate_expert_taxonomy(&view.taxonomy)?;
    if canonical_json_hash(&serde_json::to_value(&view.taxonomy).expect("taxonomy serializes"))
        != view.taxonomy_hash
        || !valid_sha256(&view.assignments_hash)
        || !valid_sha256(&view.manifest_hash)
        || !valid_sha256(&view.bundle_hash)
        || view.policy_version.trim().is_empty()
    {
        return Err(ValidationError::InvalidDataset(
            "expert dataset view identity, hash, or assignments are invalid".into(),
        ));
    }
    let expert_ids: HashSet<_> = view
        .taxonomy
        .experts
        .iter()
        .map(|expert| expert.id.as_str())
        .collect();
    for shard in &view.shards {
        if shard.record_kind.trim().is_empty()
            || !valid_sha256(&shard.object_hash)
            || !valid_sha256(&shard.uncompressed_hash)
            || shard.record_count == 0
            || shard.compressed_bytes == 0
            || (shard.purpose == ExpertDatasetPurpose::Expert
                && shard
                    .expert_id
                    .as_deref()
                    .is_none_or(|id| !expert_ids.contains(id)))
            || (shard.purpose != ExpertDatasetPurpose::Expert && shard.expert_id.is_some())
        {
            return Err(ValidationError::InvalidDataset(
                "expert dataset shard is invalid or references an unknown expert".into(),
            ));
        }
    }
    for (expert_id, stats) in &view.readiness.per_expert {
        if !expert_ids.contains(expert_id.as_str())
            || stats.records.total() != stats.decision_records + stats.replay_records
            || stats.evaluation_replay_records > stats.replay_records
        {
            return Err(ValidationError::InvalidDataset(
                "expert readiness statistics are inconsistent".into(),
            ));
        }
    }
    Ok(())
}

pub fn validate_base_model_pin(model: &BaseModelPin) -> Result<(), ValidationError> {
    if model.model_id.trim().is_empty()
        || model.model_id.len() > 256
        || model.revision.trim().is_empty()
        || model.revision.len() > 256
        || !valid_sha256(&model.sha256)
    {
        return Err(ValidationError::InvalidTrainingRun(
            "base model must have an immutable id, revision, and SHA-256".into(),
        ));
    }
    Ok(())
}

pub fn validate_qlora_config(config: &QloraConfig) -> Result<(), ValidationError> {
    if !(1..=3).contains(&config.epochs)
        || !(256..=8_192).contains(&config.max_sequence_length)
        || !(1..=256).contains(&config.lora_rank)
        || !(1..=1_024).contains(&config.lora_alpha)
        || !config.lora_dropout.is_finite()
        || !(0.0..=0.5).contains(&config.lora_dropout)
        || !config.learning_rate.is_finite()
        || !(0.000_001..=0.01).contains(&config.learning_rate)
        || !(1..=512).contains(&config.gradient_accumulation_steps)
    {
        return Err(ValidationError::InvalidTrainingRun(
            "QLoRA parameters exceed the bounded training profile".into(),
        ));
    }
    Ok(())
}

pub fn validate_create_training_run(
    request: &CreateTrainingRunRequest,
) -> Result<(), ValidationError> {
    validate_base_model_pin(&request.base_model)?;
    validate_qlora_config(&request.qlora)?;
    if let Some(plan) = &request.expert_plan
        && (plan.architecture != TrainingArchitecture::RoutedLora
            || plan.router_top_k != 1
            || !valid_id(&plan.fallback_expert_id)
            || (!plan.train_router && !plan.train_shared && plan.expert_ids.is_empty())
            || plan.expert_ids.iter().any(|id| !valid_id(id))
            || plan.expert_ids.iter().collect::<HashSet<_>>().len() != plan.expert_ids.len())
    {
        return Err(ValidationError::InvalidTrainingRun(
            "routed LoRA requires Top-1 routing and at least one selected adapter".into(),
        ));
    }
    if request.gpu_spec.trim().is_empty()
        || request.administrator.trim().is_empty()
        || request.reason.trim().is_empty()
        || !request.budget.max_hourly_cny.is_finite()
        || request.budget.max_hourly_cny <= 0.0
        || !request.budget.max_total_cny.is_finite()
        || request.budget.max_total_cny <= 0.0
        || !(60..=21_600).contains(&request.budget.max_wall_seconds)
    {
        return Err(ValidationError::InvalidTrainingRun(
            "administrator, reason, approved GPU, and positive six-hour-capped budgets are required"
                .into(),
        ));
    }
    Ok(())
}

pub fn validate_routed_adapter_bundle(
    manifest: &RoutedAdapterBundleManifest,
) -> Result<(), ValidationError> {
    if manifest.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    validate_base_model_pin(&manifest.base_model)?;
    if manifest.kind != "routed_lora_bundle_v1"
        || !valid_sha256(&manifest.taxonomy_hash)
        || manifest.router_top_k != 1
        || !valid_id(&manifest.fallback_expert_id)
        || manifest
            .router
            .as_ref()
            .is_some_and(|router| router.expert_id != "router")
        || (manifest.router.is_none() && manifest.experts.is_empty())
    {
        return Err(ValidationError::InvalidMetaModel(
            "routed adapter bundle identity or routing policy is invalid".into(),
        ));
    }
    let mut ids = HashSet::new();
    for artifact in manifest.router.iter().chain(manifest.experts.iter()) {
        if !valid_id(&artifact.expert_id)
            || !ids.insert(artifact.expert_id.as_str())
            || artifact.path.starts_with('/')
            || artifact.path.contains('\\')
            || artifact.path.contains(':')
            || artifact
                .path
                .split('/')
                .any(|part| part.is_empty() || part == "..")
            || !valid_sha256(&artifact.sha256)
            || artifact.byte_length == 0
            || artifact.training_records == 0
        {
            return Err(ValidationError::InvalidMetaModel(
                "routed adapter artifact path, hash, or counts are invalid".into(),
            ));
        }
    }
    Ok(())
}

pub fn validate_expert_adapter_version(
    adapter: &ExpertAdapterVersion,
) -> Result<(), ValidationError> {
    if adapter.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    validate_base_model_pin(&adapter.base_model)?;
    if !valid_id(&adapter.expert_id)
        || Version::parse(&adapter.version).is_err()
        || !valid_sha256(&adapter.bundle_hash)
        || !valid_sha256(&adapter.artifact_hash)
        || !valid_sha256(&adapter.taxonomy_hash)
        || adapter.artifact_path.starts_with('/')
        || adapter.artifact_path.contains('\\')
        || adapter.artifact_path.contains(':')
        || adapter
            .artifact_path
            .split('/')
            .any(|part| part.is_empty() || part == "..")
        || adapter.byte_length == 0
        || adapter.training_records == 0
    {
        return Err(ValidationError::InvalidMetaModel(
            "expert adapter identity, provenance, path, or hash is invalid".into(),
        ));
    }
    if let Some(metrics) = &adapter.metrics {
        for (name, value) in [
            ("expert.old_task_retention", metrics.old_task_retention),
            ("expert.task_success_delta", metrics.task_success_delta),
            (
                "expert.negative_transfer_rate_delta",
                metrics.negative_transfer_rate_delta,
            ),
            (
                "expert.routing_accuracy_delta",
                metrics.routing_accuracy_delta,
            ),
        ] {
            if !value.is_finite()
                || (name == "expert.old_task_retention" && !(0.0..=1.0).contains(&value))
                || (name != "expert.old_task_retention" && !(-1.0..=1.0).contains(&value))
            {
                return Err(ValidationError::InvalidMetaModel(format!(
                    "{name} is outside its bounded range"
                )));
            }
        }
    }
    Ok(())
}

fn valid_pinned_file(file: &crate::PinnedFile) -> bool {
    !file.path.trim().is_empty() && valid_sha256(&file.sha256)
}

pub fn validate_expert_adapter_eval_plan(
    plan: &crate::ExpertAdapterEvalPlan,
) -> Result<(), ValidationError> {
    if plan.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    if plan.kind != "expert_adapter_eval_plan_v1"
        || !valid_id(&plan.expert_id)
        || Version::parse(&plan.version).is_err()
        || !valid_pinned_file(&plan.llama_server)
        || !valid_pinned_file(&plan.base_gguf)
        || !valid_pinned_file(&plan.adapted_gguf)
        || !valid_pinned_file(&plan.injection_probes)
        || plan.ports.base == plan.ports.adapted
    {
        return Err(ValidationError::InvalidMetaModel(
            "adapter eval plan identity, pins, or ports are invalid".into(),
        ));
    }
    let sizes = [
        plan.set_sizes.role,
        plan.set_sizes.routing,
        plan.set_sizes.negative_transfer,
        plan.set_sizes.retention,
    ];
    if sizes.iter().any(|size| !(1..=1_000).contains(size))
        || !(1..=4_096).contains(&plan.generation.n_predict)
        || plan.generation.temperature != 0.0
        || plan.generation.stop.is_empty()
        || plan.generation.stop.len() > 4
        || plan.generation.stop.iter().any(|stop| stop.is_empty())
        || !(60..=7_200).contains(&plan.max_wall_seconds)
    {
        return Err(ValidationError::InvalidMetaModel(
            "adapter eval plan sizes, generation, or wall clock exceed their bounds".into(),
        ));
    }
    if let Some(pin) = &plan.metacognition_probes
        && (!valid_pinned_file(pin) || !(1..=150).contains(&plan.set_sizes.metacognition))
    {
        return Err(ValidationError::InvalidMetaModel(
            "metacognition probe pin or set size is invalid".into(),
        ));
    }
    Ok(())
}

pub fn validate_expert_adapter_eval_report(
    report: &crate::ExpertAdapterEvalReport,
) -> Result<(), ValidationError> {
    if report.schema_version != SCHEMA_VERSION {
        return Err(ValidationError::SchemaVersion);
    }
    validate_base_model_pin(&report.base_model)?;
    if report.kind != "expert_adapter_eval_report_v1"
        || !valid_id(&report.expert_id)
        || Version::parse(&report.version).is_err()
        || !valid_sha256(&report.taxonomy_hash)
        || !valid_sha256(&report.base_gguf_sha256)
        || !valid_sha256(&report.adapted_gguf_sha256)
        || !valid_sha256(&report.llama_server_sha256)
        || !valid_sha256(&report.results_object_hash)
        || !matches!(
            report.harness_version.as_str(),
            "adapter-eval/1" | "adapter-eval/2"
        )
        || report.llama_cpp_version.trim().is_empty()
    {
        return Err(ValidationError::InvalidMetaModel(
            "adapter eval report identity, pins, or harness version are invalid".into(),
        ));
    }
    let mut names = report
        .set_summaries
        .iter()
        .map(|summary| summary.set_name.as_str())
        .collect::<Vec<_>>();
    names.sort_unstable();
    if names != ["negative_transfer", "retention", "role", "routing"]
        || report
            .set_summaries
            .iter()
            .any(|summary| !valid_sha256(&summary.records_sha256))
    {
        return Err(ValidationError::InvalidMetaModel(
            "adapter eval report must carry exactly the four named record sets".into(),
        ));
    }
    let metrics = &report.metrics;
    if metrics.canary_decisions != 0 || metrics.canary_duration_seconds != 0 {
        return Err(ValidationError::InvalidMetaModel(
            "adapter eval report canary dimensions are server-computed and must be zero".into(),
        ));
    }
    for (name, value) in [
        ("old_task_retention", metrics.old_task_retention),
        ("task_success_delta", metrics.task_success_delta),
        (
            "negative_transfer_rate_delta",
            metrics.negative_transfer_rate_delta,
        ),
        ("routing_accuracy_delta", metrics.routing_accuracy_delta),
        (
            "task_success_delta_ci95_low",
            report.task_success_delta_ci95_low,
        ),
        (
            "routing_accuracy_delta_ci95_low",
            report.routing_accuracy_delta_ci95_low,
        ),
    ] {
        if !value.is_finite()
            || (name == "old_task_retention" && !(0.0..=1.0).contains(&value))
            || (name != "old_task_retention" && !(-1.0..=1.0).contains(&value))
        {
            return Err(ValidationError::InvalidMetaModel(format!(
                "adapter eval report metric {name} is outside its bounded range"
            )));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{GateFailureAction, RiskLevel, WorkflowEdge, WorkflowNode};

    fn workflow(edges: Vec<WorkflowEdge>) -> WorkflowManifest {
        WorkflowManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: "bugfix".into(),
            version: "1.0.0".into(),
            description: "Fix a bug".into(),
            task_classes: vec![],
            triggers: vec![],
            risk_level: RiskLevel::Medium,
            nodes: vec![
                WorkflowNode {
                    id: "a".into(),
                    skill_id: "a".into(),
                    version_req: "^1".into(),
                    required: true,
                },
                WorkflowNode {
                    id: "b".into(),
                    skill_id: "b".into(),
                    version_req: "^1".into(),
                    required: true,
                },
            ],
            edges,
            gates: vec![],
            on_failure: GateFailureAction::Deny,
            lineage: None,
        }
    }

    #[test]
    fn rejects_cycles() {
        let value = workflow(vec![
            WorkflowEdge {
                from: "a".into(),
                to: "b".into(),
                condition: None,
            },
            WorkflowEdge {
                from: "b".into(),
                to: "a".into(),
                condition: None,
            },
        ]);
        assert_eq!(
            validate_workflow(&value),
            Err(ValidationError::CyclicWorkflow)
        );
    }

    #[test]
    fn optimization_gate_rejects_any_per_task_regression() {
        let scores = vec![
            OptimizationTaskScore {
                task_id: "task-a".into(),
                baseline_hard: 1.0,
                candidate_hard: 0.0,
                baseline_soft: 0.5,
                candidate_soft: 0.9,
                safety_violation: false,
            },
            OptimizationTaskScore {
                task_id: "task-b".into(),
                baseline_hard: 0.0,
                candidate_hard: 1.0,
                baseline_soft: 0.5,
                candidate_soft: 0.9,
                safety_violation: false,
            },
        ];
        assert!(!evaluation_gate_passes(
            &OptimizationScoringPolicy::default(),
            &scores
        ));
    }

    #[test]
    fn paired_bootstrap_is_deterministic_and_strictly_positive() {
        let scores: Vec<_> = (0..30)
            .map(|index| OptimizationTaskScore {
                task_id: format!("task-{index}"),
                baseline_hard: 0.0,
                candidate_hard: 1.0,
                baseline_soft: 0.0,
                candidate_soft: 1.0,
                safety_violation: false,
            })
            .collect();
        assert_eq!(paired_bootstrap_ci95_low(&scores), Some(1.0));
        assert_eq!(
            paired_bootstrap_ci95_low(&scores),
            paired_bootstrap_ci95_low(&scores)
        );
    }

    #[test]
    fn optimization_budget_cannot_exceed_the_protocol_ceiling() {
        let mut budget = OptimizationBudget::default();
        assert!(validate_optimization_budget(&budget).is_ok());
        budget.optimizer_call_limit += 1;
        assert!(validate_optimization_budget(&budget).is_err());
    }

    #[test]
    fn skillopt_provenance_is_exact_not_merely_well_formed() {
        assert!(
            validate_skillopt_provenance(
                SKILLOPT_UPSTREAM_COMMIT,
                SKILLOPT_UPSTREAM_ARCHIVE_SHA256,
                SKILLOPT_REGISTRATION_PATCH_SHA256,
            )
            .is_ok()
        );
        assert!(
            validate_skillopt_provenance(
                SKILLOPT_UPSTREAM_COMMIT,
                &"0".repeat(64),
                SKILLOPT_REGISTRATION_PATCH_SHA256,
            )
            .is_err()
        );
    }

    #[test]
    fn routed_adapter_manifest_allows_one_expert_refresh_but_rejects_unsafe_paths() {
        let mut manifest = RoutedAdapterBundleManifest {
            schema_version: SCHEMA_VERSION.into(),
            kind: "routed_lora_bundle_v1".into(),
            base_model: BaseModelPin {
                model_id: "example/model".into(),
                revision: "immutable".into(),
                sha256: "a".repeat(64),
            },
            snapshot_id: uuid::Uuid::new_v4(),
            expert_view_id: uuid::Uuid::new_v4(),
            taxonomy_hash: "b".repeat(64),
            router_top_k: 1,
            fallback_expert_id: "shared".into(),
            router: None,
            experts: vec![crate::ExpertAdapterArtifact {
                expert_id: "retrieval".into(),
                path: "adapters/retrieval.zip".into(),
                sha256: "c".repeat(64),
                byte_length: 10,
                training_records: 1_000,
            }],
        };
        assert!(validate_routed_adapter_bundle(&manifest).is_ok());
        manifest.experts[0].path = "C:\\outside.zip".into();
        assert!(validate_routed_adapter_bundle(&manifest).is_err());
    }

    #[test]
    fn expert_release_metrics_fail_on_negative_transfer_regression() {
        let mut metrics = crate::ExpertAdapterMetrics {
            evaluation_count: 200,
            canary_decisions: 1_000,
            canary_duration_seconds: 86_400,
            old_task_retention: 0.99,
            task_success_delta: 0.01,
            negative_transfer_rate_delta: 0.0,
            routing_accuracy_delta: 0.0,
            policy_violations: 0,
            injection_regression: false,
        };
        assert!(metrics.passes_release_gate());
        metrics.negative_transfer_rate_delta = 0.001;
        assert!(!metrics.passes_release_gate());
    }

    fn paired_eval_fixture() -> PairedEvalRecord {
        PairedEvalRecord {
            eval_id: uuid::Uuid::new_v4(),
            skill_id: "example.skill".into(),
            skill_version: "1.0.0".into(),
            task_family: "bugfix/parser".into(),
            repository_digest: "a".repeat(64),
            environment_digest: "b".repeat(64),
            model_id: "router-baseline".into(),
            seed: 42,
            budget: serde_json::Value::Null,
            baseline_success: false,
            treatment_success: true,
            baseline_gate_violations: 0,
            treatment_gate_violations: 0,
            baseline_score: 0.2,
            treatment_score: 0.9,
            baseline_latency_ms: 1_200,
            treatment_latency_ms: 1_350,
            metadata: serde_json::Value::Null,
        }
    }

    #[test]
    fn paired_eval_accepts_producer_shaped_record() {
        assert!(validate_paired_eval(&paired_eval_fixture()).is_ok());
    }

    #[test]
    fn paired_eval_rejects_non_finite_scores_and_malformed_digests() {
        let mut record = paired_eval_fixture();
        record.treatment_score = f64::NAN;
        assert!(validate_paired_eval(&record).is_err());
        let mut record = paired_eval_fixture();
        record.baseline_score = f64::INFINITY;
        assert!(validate_paired_eval(&record).is_err());
        let mut record = paired_eval_fixture();
        record.repository_digest = "sha256:replace-me".into();
        assert!(validate_paired_eval(&record).is_err());
        let mut record = paired_eval_fixture();
        record.environment_digest = "A".repeat(64);
        assert!(validate_paired_eval(&record).is_err());
        let mut record = paired_eval_fixture();
        record.task_family = "  ".into();
        assert!(validate_paired_eval(&record).is_err());
        let mut record = paired_eval_fixture();
        record.model_id = String::new();
        assert!(validate_paired_eval(&record).is_err());
    }

    #[test]
    fn paired_eval_rejects_success_with_gate_violations() {
        let mut record = paired_eval_fixture();
        record.treatment_gate_violations = 1;
        assert!(validate_paired_eval(&record).is_err());
        record.treatment_success = false;
        assert!(validate_paired_eval(&record).is_ok());
    }

    fn learning_decision_fixture() -> LearningDecision {
        LearningDecision {
            schema_version: SCHEMA_VERSION.into(),
            decision_id: uuid::Uuid::new_v4(),
            experience_id: uuid::Uuid::new_v4(),
            scores: crate::LearningScores {
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
            actions: vec![crate::LearningAction::Store],
            reasons: vec!["fixture".into()],
            controller: "deterministic-learning-v1".into(),
            registry_snapshot: "c".repeat(64),
            training_eligible: false,
            created_at: chrono::Utc::now(),
        }
    }

    #[test]
    fn learning_decision_accepts_bounded_producer_output() {
        assert!(validate_learning_decision(&learning_decision_fixture()).is_ok());
    }

    #[test]
    fn learning_decision_rejects_unbounded_or_malformed_values() {
        let mut decision = learning_decision_fixture();
        decision.schema_version = "cerebellum/v0".into();
        assert_eq!(
            validate_learning_decision(&decision),
            Err(ValidationError::SchemaVersion)
        );
        let mut decision = learning_decision_fixture();
        decision.scores.confidence = 1.5;
        assert!(validate_learning_decision(&decision).is_err());
        let mut decision = learning_decision_fixture();
        decision.scores.risk = f64::NAN;
        assert!(validate_learning_decision(&decision).is_err());
        let mut decision = learning_decision_fixture();
        decision.priority = -0.1;
        assert!(validate_learning_decision(&decision).is_err());
        let mut decision = learning_decision_fixture();
        decision.actions = Vec::new();
        assert!(validate_learning_decision(&decision).is_err());
    }

    fn training_candidate_fixture() -> TrainingCandidate {
        TrainingCandidate {
            candidate_id: uuid::Uuid::new_v4(),
            dataset_hash: "a".repeat(64),
            manifest_hash: "b".repeat(64),
            decision_count: MIN_ROUTING_DECISIONS,
            paired_eval_count: MIN_PAIRED_EVALS,
            status: TrainingCandidateStatus::ReadyForTraining,
            repository_split_count: 2,
            task_family_split_count: 3,
            trainer_enabled: false,
            created_at: chrono::Utc::now(),
        }
    }

    #[test]
    fn training_candidate_accepts_ready_and_insufficient_shapes() {
        assert!(validate_training_candidate(&training_candidate_fixture()).is_ok());
        let mut candidate = training_candidate_fixture();
        candidate.status = TrainingCandidateStatus::InsufficientEvidence;
        candidate.decision_count = 0;
        candidate.paired_eval_count = 0;
        candidate.repository_split_count = 0;
        candidate.task_family_split_count = 0;
        assert!(validate_training_candidate(&candidate).is_ok());
    }

    #[test]
    fn training_candidate_enforces_hash_status_and_trainer_invariants() {
        let mut candidate = training_candidate_fixture();
        candidate.dataset_hash = "not-a-hash".into();
        assert!(validate_training_candidate(&candidate).is_err());
        let mut candidate = training_candidate_fixture();
        candidate.decision_count = MIN_ROUTING_DECISIONS - 1;
        assert!(validate_training_candidate(&candidate).is_err());
        let mut candidate = training_candidate_fixture();
        candidate.paired_eval_count = MIN_PAIRED_EVALS - 1;
        assert!(validate_training_candidate(&candidate).is_err());
        let mut candidate = training_candidate_fixture();
        candidate.status = TrainingCandidateStatus::InsufficientEvidence;
        candidate.trainer_enabled = true;
        assert!(validate_training_candidate(&candidate).is_err());
        let mut candidate = training_candidate_fixture();
        candidate.trainer_enabled = true;
        assert!(validate_training_candidate(&candidate).is_ok());
    }
}
