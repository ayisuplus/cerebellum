use chrono::{DateTime, Utc};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::PathBuf;
use uuid::Uuid;

pub const SCHEMA_VERSION: &str = "cerebellum/v1";

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ArtifactLineage {
    pub parent_id: String,
    pub parent_version: String,
    pub reason: String,
    pub decision_id: Uuid,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SkillLifecycle {
    Quarantined,
    Validated,
    Experimental,
    Trusted,
    Deprecated,
    Revoked,
}

impl SkillLifecycle {
    pub fn is_routable(self) -> bool {
        matches!(self, Self::Validated | Self::Experimental | Self::Trusted)
    }

    pub fn can_transition_to(self, next: Self) -> bool {
        use SkillLifecycle::*;
        matches!(
            (self, next),
            (Quarantined, Validated)
                | (Validated, Experimental)
                | (Experimental, Trusted)
                | (Validated | Experimental | Trusted, Deprecated)
                | (
                    Quarantined | Validated | Experimental | Trusted | Deprecated,
                    Revoked
                )
        ) || self == next
    }
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, JsonSchema,
)]
#[serde(rename_all = "snake_case")]
pub enum RiskLevel {
    ReadOnly,
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SourceRef {
    pub repository_url: String,
    pub commit_sha: String,
    pub path: String,
    pub content_hash: String,
    pub license: String,
    pub collected_at: DateTime<Utc>,
}

impl SourceRef {
    pub fn has_identity_provenance(&self) -> bool {
        !self.repository_url.trim().is_empty()
            && !self.commit_sha.trim().is_empty()
            && !self.path.trim().is_empty()
            && !matches!(
                self.license.trim().to_ascii_uppercase().as_str(),
                "" | "UNKNOWN" | "NOASSERTION"
            )
    }

    pub fn has_training_provenance(&self) -> bool {
        self.has_identity_provenance() && self.license_allows_training()
    }

    /// Conservative policy for automatic dataset admission.
    ///
    /// Other licenses may be approved by a future explicit policy record, but
    /// a merely recognizable license is not enough to train automatically.
    pub fn license_allows_training(&self) -> bool {
        matches!(
            self.license.trim().to_ascii_uppercase().as_str(),
            "MIT"
                | "APACHE-2.0"
                | "MIT OR APACHE-2.0"
                | "BSD-2-CLAUSE"
                | "BSD-3-CLAUSE"
                | "CC0-1.0"
                | "UNLICENSE"
        )
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EvidenceCard {
    #[serde(default)]
    pub schema_passed: bool,
    #[serde(default)]
    pub security_findings: BTreeMap<String, u32>,
    #[serde(default)]
    pub independent_tasks: u32,
    #[serde(default)]
    pub paired_runs: u32,
    #[serde(default)]
    pub success_rate: Option<f64>,
    #[serde(default)]
    pub task_uplift: Option<f64>,
    #[serde(default)]
    pub uplift_ci95_low: Option<f64>,
    #[serde(default)]
    pub median_latency_ms: Option<f64>,
    #[serde(default)]
    pub median_cost: Option<f64>,
    #[serde(default)]
    pub redaction_passed: bool,
}

impl EvidenceCard {
    pub fn has_blocking_security_finding(&self) -> bool {
        self.security_findings.get("critical").copied().unwrap_or(0) > 0
            || self.security_findings.get("high").copied().unwrap_or(0) > 0
    }

    pub fn qualifies_experimental(&self) -> bool {
        self.schema_passed
            && !self.has_blocking_security_finding()
            && self.independent_tasks >= 10
            && self.paired_runs >= 30
            && self.task_uplift.unwrap_or(f64::NEG_INFINITY) >= 0.0
    }

    pub fn qualifies_trusted(&self) -> bool {
        self.qualifies_experimental()
            && self.independent_tasks >= 50
            && self.uplift_ci95_low.unwrap_or(f64::NEG_INFINITY) > 0.0
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct LegacyHint {
    pub score: Option<f64>,
    pub confidence: Option<String>,
    pub category: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SkillDependency {
    pub skill_id: String,
    pub version_req: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SkillManifest {
    pub schema_version: String,
    pub id: String,
    pub version: String,
    pub description: String,
    #[serde(default)]
    pub triggers: Vec<String>,
    #[serde(default = "empty_schema")]
    pub input_schema: Value,
    #[serde(default = "empty_schema")]
    pub output_schema: Value,
    #[serde(default)]
    pub dependencies: Vec<SkillDependency>,
    #[serde(default)]
    pub permissions: Vec<String>,
    pub risk_level: RiskLevel,
    #[serde(default)]
    pub compatibility: Vec<String>,
    pub source: SourceRef,
    #[serde(default)]
    pub evidence: EvidenceCard,
    pub status: SkillLifecycle,
    #[serde(default)]
    pub legacy_hint: Option<LegacyHint>,
    #[serde(default)]
    pub training_eligible: bool,
    #[serde(default)]
    pub lineage: Option<ArtifactLineage>,
}

fn empty_schema() -> Value {
    serde_json::json!({"type": "object"})
}

impl SkillManifest {
    pub fn recompute_training_eligible(&mut self) {
        self.training_eligible = self.source.has_training_provenance()
            && self.evidence.redaction_passed
            && self.evidence.qualifies_experimental()
            && matches!(
                self.status,
                SkillLifecycle::Experimental | SkillLifecycle::Trusted
            );
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct WorkflowNode {
    pub id: String,
    pub skill_id: String,
    pub version_req: String,
    #[serde(default)]
    pub required: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct WorkflowEdge {
    pub from: String,
    pub to: String,
    #[serde(default)]
    pub condition: Option<WorkflowEdgeCondition>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum WorkflowEdgeCondition {
    Always,
    OnSuccess,
    OnFailure,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum GateEvaluator {
    EvidenceBool {
        key: String,
        expected: bool,
    },
    CommandExit {
        evidence_key: String,
        allowed_codes: Vec<i32>,
    },
    TestReport {
        min_pass_rate: f64,
        max_failed: u32,
    },
    FileExists {
        path: String,
    },
    GitStatus {
        allow_dirty: bool,
    },
    DiffConstraint {
        max_files: u32,
        forbidden_patterns: Vec<String>,
    },
    Permission {
        permission: String,
    },
    Approval {
        role: String,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum GateFailureAction {
    Deny,
    NeedsHuman,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct GateSpec {
    pub id: String,
    pub description: String,
    pub stage: String,
    pub mandatory: bool,
    pub evaluator: GateEvaluator,
    pub on_failure: GateFailureAction,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct WorkflowManifest {
    pub schema_version: String,
    pub id: String,
    pub version: String,
    pub description: String,
    #[serde(default)]
    pub task_classes: Vec<String>,
    #[serde(default)]
    pub triggers: Vec<String>,
    pub risk_level: RiskLevel,
    pub nodes: Vec<WorkflowNode>,
    #[serde(default)]
    pub edges: Vec<WorkflowEdge>,
    #[serde(default)]
    pub gates: Vec<GateSpec>,
    pub on_failure: GateFailureAction,
    #[serde(default)]
    pub lineage: Option<ArtifactLineage>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DecisionRequest {
    pub task: String,
    #[serde(default)]
    pub repository_path: Option<String>,
    #[serde(default)]
    pub capabilities: Vec<String>,
    #[serde(default)]
    pub context: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct RankedWorkflow {
    pub workflow_id: String,
    pub version: String,
    pub score: f64,
    pub reasons: Vec<String>,
}

/// Authoritative server-stamped environment block: generated by the server at
/// decision time, never taken from user-supplied context. The metacognition
/// adapter grounds time-relative behavior on this block alone.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct EnvironmentStamp {
    pub now: DateTime<Utc>,
    pub timezone: String,
    pub registry_snapshot: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct DecisionResponse {
    pub decision_id: Uuid,
    pub selected: RankedWorkflow,
    pub alternatives: Vec<RankedWorkflow>,
    pub router: String,
    pub fallback_used: bool,
    pub registry_snapshot: String,
    #[serde(default)]
    pub memory_context: Vec<ContextItem>,
    #[serde(default)]
    pub knowledge_context: Vec<KnowledgeResult>,
    #[serde(default)]
    pub environment: Option<EnvironmentStamp>,
    #[serde(default)]
    pub acquisition_requested: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreateRunRequest {
    pub decision_id: Uuid,
    pub workflow_id: String,
    pub workflow_version: String,
    #[serde(default)]
    pub repository_path: Option<String>,
    #[serde(default)]
    pub capabilities: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct AppendEventRequest {
    pub kind: String,
    pub payload: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct GateEvidenceRequest {
    #[serde(default)]
    pub evidence: Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum GateStatus {
    Pass,
    Deny,
    NeedsHuman,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct GateDecision {
    pub run_id: Uuid,
    pub gate_id: String,
    pub status: GateStatus,
    pub reason: String,
    pub evaluated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct AuthorizeRequest {
    pub run_id: Uuid,
    pub action: Value,
    #[serde(default = "default_ttl")]
    pub ttl_seconds: u64,
}

fn default_ttl() -> u64 {
    60
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct ActionPermit {
    pub permit_id: Uuid,
    pub run_id: Uuid,
    pub workflow_id: String,
    pub workflow_version: String,
    pub action_hash: String,
    pub issued_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct AuthorizeResponse {
    pub permit: ActionPermit,
    pub token: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct VerifyPermitRequest {
    pub token: String,
    pub action: Value,
    #[serde(default)]
    pub consume: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CompleteRunRequest {
    pub outcome: String,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub metrics: Value,
    #[serde(default)]
    pub experience: Option<RunCompletionExperience>,
}

/// Learning provenance attached to a run completion. When present, the
/// daemon closes the loop by ingesting one experience for the finished run
/// (experience_id == run_id, so replays collapse instead of duplicating).
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct RunCompletionExperience {
    pub task: String,
    pub task_family: String,
    pub repository: RepositorySnapshot,
    pub agent_id: String,
    pub model_id: String,
    pub source: ExperienceSource,
    #[serde(default)]
    pub trajectory: Vec<TrajectoryRef>,
    #[serde(default)]
    pub cost: ExperienceCost,
    #[serde(default)]
    pub data_classification: DataClassification,
    #[serde(default)]
    pub external_processing: ExternalProcessingPermission,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct RunRecord {
    pub id: Uuid,
    pub decision_id: Uuid,
    pub workflow_id: String,
    pub workflow_version: String,
    pub repository_path: Option<String>,
    pub capabilities: Vec<String>,
    pub status: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct TraceEvent {
    pub sequence: i64,
    pub kind: String,
    pub payload: Value,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct GateTrace {
    pub gate_id: String,
    pub status: GateStatus,
    pub reason: String,
    pub evidence: Value,
    pub evaluated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct RunTrace {
    pub schema_version: String,
    pub run: RunRecord,
    pub events: Vec<TraceEvent>,
    pub gates: Vec<GateTrace>,
    #[serde(default)]
    pub completion: Option<CompleteRunRequest>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CandidateExport {
    pub schema_version: String,
    pub exported_at: DateTime<Utc>,
    pub producer: String,
    pub candidates: Vec<CandidateExperience>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CandidateExperience {
    pub candidate_id: String,
    pub kind: String,
    pub content: String,
    #[serde(default)]
    pub category: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub source: Option<String>,
    #[serde(default)]
    pub evidence: Value,
    pub content_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct PairedEvalRecord {
    pub eval_id: Uuid,

    pub skill_id: String,
    pub skill_version: String,
    pub task_family: String,
    pub repository_digest: String,
    pub environment_digest: String,
    pub model_id: String,
    pub seed: u64,
    #[serde(default)]
    pub budget: Value,
    pub baseline_success: bool,
    pub treatment_success: bool,
    #[serde(default)]
    pub baseline_gate_violations: u32,
    #[serde(default)]
    pub treatment_gate_violations: u32,
    pub baseline_score: f64,
    pub treatment_score: f64,
    pub baseline_latency_ms: u64,
    pub treatment_latency_ms: u64,
    #[serde(default)]
    pub metadata: Value,
}
/// One sandboxed arm of a paired evaluation: a pinned image and the command
/// to run against a copied repository snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SandboxCommand {
    pub image: String,
    pub repository_path: PathBuf,
    pub argv: Vec<String>,
    #[serde(default = "default_sandbox_timeout")]
    pub timeout_seconds: u64,
    #[serde(default)]
    pub environment: BTreeMap<String, String>,
}

/// Baseline/treatment pair executed under identical image, timeout, and
/// environment so only the repository content varies.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct PairedSandboxPlan {
    pub skill_id: String,
    pub skill_version: String,
    pub task_family: String,
    pub model_id: String,
    pub seed: u64,
    #[serde(default)]
    pub budget: Value,
    pub baseline: SandboxCommand,
    pub treatment: SandboxCommand,
}

/// Outcome of one sandboxed run (stdout/stderr capped by the runner).
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SandboxResult {
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub duration_ms: u64,
    pub stdout: String,
    pub stderr: String,
}

fn default_sandbox_timeout() -> u64 {
    300
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExperienceSourceKind {
    AgentTrace,
    Github,
    Simulation,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum DataClassification {
    Public,
    Internal,
    #[default]
    Private,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExternalProcessingPermission {
    #[default]
    Denied,
    Redacted,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExperienceSource {
    pub kind: ExperienceSourceKind,
    pub uri: String,
    #[serde(default)]
    pub commit_sha: Option<String>,
    #[serde(default)]
    pub license: Option<String>,
    #[serde(default)]
    pub collected_by: String,
}

impl ExperienceSource {
    pub fn license_allows_training(&self) -> bool {
        matches!(
            self.license
                .as_deref()
                .unwrap_or("NOASSERTION")
                .trim()
                .to_ascii_uppercase()
                .as_str(),
            "MIT"
                | "APACHE-2.0"
                | "MIT OR APACHE-2.0"
                | "BSD-2-CLAUSE"
                | "BSD-3-CLAUSE"
                | "CC0-1.0"
                | "UNLICENSE"
        )
    }

    pub fn has_fixed_revision(&self) -> bool {
        self.kind != ExperienceSourceKind::Github
            || self
                .commit_sha
                .as_deref()
                .is_some_and(|sha| sha.len() == 40 && sha.chars().all(|c| c.is_ascii_hexdigit()))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct RepositorySnapshot {
    pub repository_id: String,
    pub digest: String,
    #[serde(default)]
    pub branch: Option<String>,
    #[serde(default)]
    pub dirty: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TrajectoryRef {
    pub uri: String,
    pub content_hash: String,
    #[serde(default)]
    pub media_type: String,
    #[serde(default)]
    pub redacted: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExperienceCost {
    #[serde(default)]
    pub input_tokens: u64,
    #[serde(default)]
    pub output_tokens: u64,
    #[serde(default)]
    pub wall_time_ms: u64,
    #[serde(default)]
    pub estimated_usd: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExperienceOutcome {
    pub success: bool,
    pub summary: String,
    #[serde(default)]
    pub failure_class: Option<String>,
    #[serde(default)]
    pub metrics: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExperienceEnvelope {
    pub schema_version: String,
    pub experience_id: Uuid,
    pub task: String,
    pub task_family: String,
    pub repository: RepositorySnapshot,
    #[serde(default)]
    pub trajectory: Vec<TrajectoryRef>,
    pub agent_id: String,
    pub model_id: String,
    #[serde(default)]
    pub workflow: Option<ArtifactVersionRef>,
    pub source: ExperienceSource,
    #[serde(default)]
    pub cost: ExperienceCost,
    pub outcome: ExperienceOutcome,
    #[serde(default)]
    pub redaction_passed: bool,
    #[serde(default)]
    pub data_classification: DataClassification,
    #[serde(default)]
    pub external_processing: ExternalProcessingPermission,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ArtifactVersionRef {
    pub id: String,
    pub version: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum FeedbackKind {
    Test,
    Build,
    Gate,
    Human,
    DelayedOutcome,
    LlmCritic,
}

impl FeedbackKind {
    pub fn trust_weight(self) -> f64 {
        match self {
            Self::Test | Self::Build | Self::Gate => 1.0,
            Self::Human | Self::DelayedOutcome => 0.8,
            Self::LlmCritic => 0.25,
        }
    }

    pub fn is_verifiable(self) -> bool {
        matches!(self, Self::Test | Self::Build | Self::Gate)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct FeedbackSignal {
    pub schema_version: String,
    pub feedback_id: Uuid,
    pub experience_id: Uuid,
    pub kind: FeedbackKind,
    pub score: f64,
    pub confidence: f64,
    pub source: String,
    #[serde(default)]
    pub evidence: Value,
    #[serde(default)]
    pub evidence_hash: Option<String>,
    #[serde(default)]
    pub attestation: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct LearningScores {
    pub correctness: f64,
    pub utility: f64,
    pub novelty: f64,
    pub generality: f64,
    pub confidence: f64,
    pub risk: f64,
    pub cost: f64,
    pub expected_gain: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum LearningAction {
    Ignore,
    Store,
    Merge,
    Distill,
    ProposeSkill,
    ProposeWorkflow,
    ScheduleEval,
    TrainingCandidate,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct LearningDecision {
    pub schema_version: String,
    pub decision_id: Uuid,
    pub experience_id: Uuid,
    pub scores: LearningScores,
    pub priority: f64,
    pub actions: Vec<LearningAction>,
    pub reasons: Vec<String>,
    pub controller: String,
    pub registry_snapshot: String,
    #[serde(default)]
    pub training_eligible: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum MemoryKind {
    Episodic,
    Fact,
    Failure,
    AntiSkill,
    SkillProposal,
    WorkflowProposal,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MemoryProposal {
    pub proposal_id: Uuid,
    pub experience_id: Uuid,
    pub kind: MemoryKind,
    pub title: String,
    pub content: String,
    #[serde(default)]
    pub lineage: Option<ArtifactLineage>,
    #[serde(default)]
    pub evidence: Value,
    #[serde(default)]
    pub executable: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ConsolidationRequest {
    pub schema_version: String,
    pub request_id: Uuid,
    pub experience: ExperienceEnvelope,
    pub feedback: Vec<FeedbackSignal>,
    pub decision: LearningDecision,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ConsolidationResponse {
    pub schema_version: String,
    pub request_id: Uuid,
    pub producer: String,
    pub proposals: Vec<MemoryProposal>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ContextRetrieveRequest {
    pub query: String,
    #[serde(default)]
    pub repository_id: Option<String>,
    #[serde(default)]
    pub task_family: Option<String>,
    #[serde(default = "default_context_limit")]
    pub limit: usize,
}

fn default_context_limit() -> usize {
    10
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ContextItem {
    pub kind: MemoryKind,
    pub id: String,
    pub title: String,
    pub content: String,
    pub score: f64,
    #[serde(default)]
    pub warning: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ContextRetrieveResponse {
    pub registry_snapshot: String,
    #[serde(default)]
    pub skipped_dangling: u64,
    pub items: Vec<ContextItem>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DailyBudget {
    pub search_plans: u32,
    pub new_repositories: u32,
    pub files: u32,
}

impl Default for DailyBudget {
    fn default() -> Self {
        Self {
            search_plans: 20,
            new_repositories: 50,
            files: 500,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CurriculumPolicy {
    #[serde(default)]
    pub topics: Vec<String>,
    #[serde(default)]
    pub organizations: Vec<String>,
    #[serde(default)]
    pub licenses: Vec<String>,
    #[serde(default)]
    pub repositories: Vec<String>,
    #[serde(default)]
    pub daily_budget: DailyBudget,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum CurriculumTrigger {
    FrequentFailure,
    CapabilityGap,
    LowConfidence,
    DependencyDrift,
    NewTopic,
    Manual,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreateCurriculumRequest {
    pub trigger: CurriculumTrigger,
    pub topic: String,
    pub query: String,
    pub policy: CurriculumPolicy,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CurriculumPlan {
    pub schema_version: String,
    pub curriculum_id: Uuid,
    pub trigger: CurriculumTrigger,
    pub topic: String,
    pub query: String,
    pub policy: CurriculumPolicy,
    pub status: String,
    pub fixed_commit_required: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum LearningJobStatus {
    Pending,
    Leased,
    Completed,
    DeadLetter,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct LearningJob {
    pub job_id: Uuid,
    pub kind: String,
    pub payload: Value,
    pub priority: f64,
    pub status: LearningJobStatus,
    pub attempts: u32,
    pub max_attempts: u32,
    #[serde(default)]
    pub lease_owner: Option<String>,
    #[serde(default)]
    pub lease_until: Option<DateTime<Utc>>,
    #[serde(default)]
    pub last_error: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum TrainingCandidateStatus {
    InsufficientEvidence,
    ReadyForTraining,
    Superseded,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TrainingCandidate {
    pub candidate_id: Uuid,
    pub dataset_hash: String,
    pub manifest_hash: String,
    pub decision_count: u64,
    pub paired_eval_count: u64,
    pub status: TrainingCandidateStatus,
    pub repository_split_count: u64,
    pub task_family_split_count: u64,
    pub trainer_enabled: bool,
    pub created_at: DateTime<Utc>,
}

pub const SKILLOPT_UPSTREAM_COMMIT: &str = "3c8873f016397817dcd40c3e5436d92fe19372b8";
/// Minimum routing decisions required before a training candidate is ready.
pub const MIN_ROUTING_DECISIONS: u64 = 5_000;
/// Minimum paired evaluations required before a training candidate is ready.
pub const MIN_PAIRED_EVALS: u64 = 1_000;

pub const SKILLOPT_UPSTREAM_ARCHIVE_SHA256: &str =
    "abdc429fe2a59b30d36c3148a107dfb36184821c7996d67d98d362a6603b1999";
pub const SKILLOPT_REGISTRATION_PATCH_SHA256: &str =
    "3f57e82c0518e18fd9ee33c337737f370e9d61c892715f7905b35c98590c1549";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum BenchmarkSplit {
    Train,
    Validation,
    Holdout,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExpectedTaskStatus {
    Completed,
    Blocked,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CodingBenchmarkTask {
    pub task_id: String,
    pub template_family: String,
    pub variant: u32,
    pub split: BenchmarkSplit,
    pub bundle_hash: String,
    pub test_command: String,
    pub expected_status: ExpectedTaskStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct OptimizationScoringPolicy {
    pub correctness_weight: f64,
    pub fresh_verification_weight: f64,
    pub claim_calibration_weight: f64,
    pub efficiency_weight: f64,
    pub minimum_soft_improvement: f64,
    pub no_hard_regression: bool,
}

impl Default for OptimizationScoringPolicy {
    fn default() -> Self {
        Self {
            correctness_weight: 0.45,
            fresh_verification_weight: 0.25,
            claim_calibration_weight: 0.20,
            efficiency_weight: 0.10,
            minimum_soft_improvement: 0.02,
            no_hard_regression: true,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CodingBenchmarkManifest {
    pub schema_version: String,
    pub benchmark_id: String,
    pub version: String,
    pub container_image: String,
    pub tasks: Vec<CodingBenchmarkTask>,
    #[serde(default)]
    pub scoring: OptimizationScoringPolicy,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct OptimizationBudget {
    pub epochs: u32,
    pub batch_size: u32,
    pub max_candidate_steps: u32,
    pub max_edits_per_candidate: u32,
    pub max_net_new_tokens: i32,
    pub max_skill_tokens: u32,
    pub target_call_limit: u32,
    pub optimizer_call_limit: u32,
    pub total_token_limit: u64,
    pub wall_time_seconds: u64,
    pub no_improvement_limit: u32,
}

impl Default for OptimizationBudget {
    fn default() -> Self {
        Self {
            epochs: 2,
            batch_size: 10,
            max_candidate_steps: 6,
            max_edits_per_candidate: 2,
            max_net_new_tokens: 400,
            max_skill_tokens: 2_000,
            target_call_limit: 240,
            optimizer_call_limit: 24,
            total_token_limit: 2_000_000,
            wall_time_seconds: 21_600,
            no_improvement_limit: 2,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreateOptimizationRunRequest {
    pub skill_id: String,
    pub skill_version: String,
    pub benchmark_manifest_hash: String,
    pub benchmark_bundle_hash: String,
    pub container_image_digest: String,
    pub target_model: String,
    pub optimizer_model: String,
    #[serde(default)]
    pub budget: OptimizationBudget,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum OptimizationRunStatus {
    Queued,
    Running,
    Validated,
    Approved,
    Rejected,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SkillOptimizationRun {
    pub schema_version: String,
    pub run_id: Uuid,
    pub job_id: Uuid,
    pub skill_id: String,
    pub skill_version: String,
    pub baseline_content_hash: String,
    pub benchmark_manifest_hash: String,
    pub benchmark_bundle_hash: String,
    pub container_image_digest: String,
    pub upstream_repository: String,
    pub upstream_commit: String,
    pub upstream_source_archive_sha256: String,
    pub registration_patch_sha256: String,
    pub target_model: String,
    pub optimizer_model: String,
    pub budget: OptimizationBudget,
    pub candidate_version: String,
    pub release_version: String,
    pub status: OptimizationRunStatus,
    #[serde(default)]
    pub result_hash: Option<String>,
    #[serde(default)]
    pub best_candidate_hash: Option<String>,
    #[serde(default)]
    pub reviewed_by: Option<String>,
    #[serde(default)]
    pub review_reason: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SkillEditOperation {
    Append,
    InsertAfter,
    Replace,
    Delete,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SkillEdit {
    pub operation: SkillEditOperation,
    #[serde(default)]
    pub target: String,
    #[serde(default)]
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SkillEditPatch {
    pub schema_version: String,
    pub patch_id: Uuid,
    pub run_id: Uuid,
    pub sequence: u32,
    pub baseline_hash: String,
    pub candidate_hash: String,
    pub edits: Vec<SkillEdit>,
    pub rationale: String,
    #[serde(default)]
    pub trajectory_ids: Vec<String>,
    pub token_delta: i32,
    pub optimizer_model: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct OptimizationTaskScore {
    pub task_id: String,
    pub baseline_hard: f64,
    pub candidate_hard: f64,
    pub baseline_soft: f64,
    pub candidate_soft: f64,
    #[serde(default)]
    pub safety_violation: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CandidateEvaluation {
    pub candidate_hash: String,
    pub split: BenchmarkSplit,
    pub task_scores: Vec<OptimizationTaskScore>,
    pub baseline_hard_mean: f64,
    pub candidate_hard_mean: f64,
    pub baseline_soft_mean: f64,
    pub candidate_soft_mean: f64,
    pub gate_passed: bool,
    #[serde(default)]
    pub rejection_reasons: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct HoldoutEvaluation {
    pub seeds: Vec<u64>,
    pub task_scores: Vec<OptimizationTaskScore>,
    pub paired_runs: u32,
    pub bootstrap_ci95_low: f64,
    pub safety_violation_delta: i32,
    pub positive_result: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SkillOptimizationResult {
    pub schema_version: String,
    pub run_id: Uuid,
    pub worker: String,
    pub upstream_commit: String,
    pub upstream_source_archive_sha256: String,
    pub registration_patch_sha256: String,
    pub patches: Vec<SkillEditPatch>,
    pub evaluations: Vec<CandidateEvaluation>,
    #[serde(default)]
    pub holdout: Option<HoldoutEvaluation>,
    #[serde(default)]
    pub best_patch_id: Option<Uuid>,
    pub stopped_reason: String,
    pub target_calls: u32,
    pub optimizer_calls: u32,
    pub total_tokens: u64,
    pub elapsed_seconds: u64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct OptimizationReviewRequest {
    pub actor: String,
    pub reason: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ModelStatus {
    Candidate,
    Approved,
    Rejected,
    Active,
    RolledBack,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ModelEvidence {
    pub task_success_uplift: f64,
    pub gate_violation_delta: i64,
    pub latency_improvement: f64,
    pub memory_improvement: f64,
}

impl ModelEvidence {
    pub fn qualifies_for_activation(&self) -> bool {
        self.task_success_uplift > 0.0
            && self.gate_violation_delta <= 0
            && (self.latency_improvement >= 0.2 || self.memory_improvement >= 0.2)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ModelVersion {
    pub model_id: String,
    pub version: String,
    pub artifact_hash: String,
    pub training_candidate_id: Uuid,
    pub evidence: ModelEvidence,
    pub status: ModelStatus,
    #[serde(default)]
    pub reviewed_by: Option<String>,
    #[serde(default)]
    pub review_reason: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ModelReviewRequest {
    pub actor: String,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct LearningMetrics {
    pub task_success_rate: f64,
    pub forward_transfer: f64,
    pub retention_rate: f64,
    pub negative_transfer_rate: f64,
    pub calibration_error: f64,
    pub gain_per_cost: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct LearningStatus {
    pub experience_count: u64,
    pub feedback_count: u64,
    pub decision_count: u64,
    pub proposal_count: u64,
    pub pending_jobs: u64,
    pub dead_letter_jobs: u64,
    pub training_candidates: u64,
    pub ready_for_training: bool,
    pub model_publication_requires_human: bool,
    pub metrics: LearningMetrics,
}

// v3 real-time knowledge acquisition and autonomous meta-learning contracts.

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TopicBudget {
    #[serde(default = "default_events_per_day")]
    pub events_per_day: u32,
    #[serde(default = "default_documents_per_day")]
    pub fetched_documents_per_day: u32,
    #[serde(default = "default_browser_escalations_per_day")]
    pub browser_escalations_per_day: u32,
    #[serde(default = "default_model_tokens_per_day")]
    pub model_tokens_per_day: u64,
}

fn default_events_per_day() -> u32 {
    2_000
}
fn default_documents_per_day() -> u32 {
    500
}
fn default_browser_escalations_per_day() -> u32 {
    50
}
fn default_model_tokens_per_day() -> u64 {
    500_000
}
fn default_topic_refresh_seconds() -> u32 {
    30
}
fn default_source_max_depth() -> u8 {
    2
}
fn default_source_max_pages() -> u32 {
    50
}
fn default_source_rate_limit() -> u32 {
    30
}
fn default_raw_retention_days() -> u32 {
    30
}
fn default_knowledge_limit() -> usize {
    10
}
fn default_true() -> bool {
    true
}
fn default_topic_languages() -> Vec<String> {
    vec!["en".into(), "zh".into()]
}

impl Default for TopicBudget {
    fn default() -> Self {
        Self {
            events_per_day: default_events_per_day(),
            fetched_documents_per_day: default_documents_per_day(),
            browser_escalations_per_day: default_browser_escalations_per_day(),
            model_tokens_per_day: default_model_tokens_per_day(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreateTopicWatchRequest {
    pub name: String,
    pub query: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub entities: Vec<String>,
    #[serde(default = "default_topic_languages")]
    pub languages: Vec<String>,
    #[serde(default)]
    pub source_policy_ids: Vec<Uuid>,
    #[serde(default = "default_topic_refresh_seconds")]
    pub refresh_seconds: u32,
    #[serde(default)]
    pub budget: TopicBudget,
    #[serde(default = "default_true")]
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TopicWatch {
    pub schema_version: String,
    pub topic_id: Uuid,
    pub name: String,
    pub query: String,
    pub keywords: Vec<String>,
    pub entities: Vec<String>,
    pub languages: Vec<String>,
    pub source_policy_ids: Vec<Uuid>,
    pub refresh_seconds: u32,
    pub budget: TopicBudget,
    pub enabled: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SourceKind {
    Github,
    HackerNews,
    RssAtom,
    Tavily,
    Firecrawl,
    Crawl4ai,
    Scrapling,
    OpenCli,
    Http,
    Weibo,
    Zhihu,
    Douyin,
    Bilibili,
    Xhs,
    Baidu,
    Kuaishou,
    Tieba,
    #[serde(rename = "openalex")]
    OpenAlex,
    Arxiv,
    Journal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SourceAccessMode {
    Public,
    Api,
    AuthenticatedLocal,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreateSourcePolicyRequest {
    pub name: String,
    pub kind: SourceKind,
    pub base_url: String,
    pub access_mode: SourceAccessMode,
    #[serde(default)]
    pub allowed_domains: Vec<String>,
    #[serde(default = "default_true")]
    pub obey_robots: bool,
    #[serde(default = "default_source_max_depth")]
    pub max_depth: u8,
    #[serde(default = "default_source_max_pages")]
    pub max_pages_per_run: u32,
    #[serde(default = "default_source_rate_limit")]
    pub rate_limit_per_minute: u32,
    #[serde(default = "default_raw_retention_days")]
    pub raw_retention_days: u32,
    #[serde(default)]
    pub training_license: Option<String>,
    #[serde(default)]
    pub model_terms_allow_training: bool,
    #[serde(default)]
    pub auth_secret_ref: Option<String>,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub data_classification: DataClassification,
    #[serde(default)]
    pub external_processing: ExternalProcessingPermission,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SourcePolicy {
    pub schema_version: String,
    pub policy_id: Uuid,
    pub name: String,
    pub kind: SourceKind,
    pub base_url: String,
    pub access_mode: SourceAccessMode,
    pub allowed_domains: Vec<String>,
    pub obey_robots: bool,
    pub max_depth: u8,
    pub max_pages_per_run: u32,
    pub rate_limit_per_minute: u32,
    pub raw_retention_days: u32,
    pub training_license: Option<String>,
    pub model_terms_allow_training: bool,
    pub auth_secret_ref: Option<String>,
    pub enabled: bool,
    #[serde(default)]
    pub data_classification: DataClassification,
    #[serde(default)]
    pub external_processing: ExternalProcessingPermission,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl SourcePolicy {
    pub fn text_training_allowed(&self) -> bool {
        self.model_terms_allow_training
            && self
                .training_license
                .as_deref()
                .is_some_and(license_allows_automatic_training)
    }
}

pub fn license_allows_automatic_training(license: &str) -> bool {
    matches!(
        license.trim().to_ascii_uppercase().as_str(),
        "MIT"
            | "APACHE-2.0"
            | "MIT OR APACHE-2.0"
            | "BSD-2-CLAUSE"
            | "BSD-3-CLAUSE"
            | "CC0-1.0"
            | "UNLICENSE"
    )
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum AcquisitionPlanStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct AcquisitionPlan {
    pub schema_version: String,
    pub plan_id: Uuid,
    pub topic_id: Uuid,
    pub query: String,
    pub source_policy_ids: Vec<Uuid>,
    pub scheduled_for: DateTime<Utc>,
    pub max_documents: u32,
    pub max_depth: u8,
    pub status: AcquisitionPlanStatus,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum AcquisitionMethod {
    Api,
    Rss,
    DirectHttp,
    Crawl4ai,
    Firecrawl,
    LinkMapper,
    Scrapling,
    Mediacrawler,
    OpenCli,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum AcquisitionOutcome {
    Success,
    PartialContent,
    JsShell,
    ParseFailed,
    RateLimited,
    Timeout,
    ServerError,
    AuthRequired,
    RobotsDenied,
    Captcha,
    ExplicitChallenge,
    PolicyDenied,
    NotFound,
    Gone,
}

impl AcquisitionOutcome {
    pub fn may_escalate_extractor(self) -> bool {
        matches!(
            self,
            Self::PartialContent | Self::JsShell | Self::ParseFailed
        )
    }
    pub fn is_retryable(self) -> bool {
        matches!(self, Self::RateLimited | Self::Timeout | Self::ServerError)
    }
    pub fn is_terminal_policy_failure(self) -> bool {
        matches!(
            self,
            Self::RobotsDenied
                | Self::Captcha
                | Self::ExplicitChallenge
                | Self::PolicyDenied
                | Self::NotFound
                | Self::Gone
        )
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct AcquisitionAttempt {
    pub schema_version: String,
    pub attempt_id: Uuid,
    pub plan_id: Uuid,
    pub source_policy_id: Uuid,
    pub url: String,
    pub canonical_url: String,
    pub method: AcquisitionMethod,
    pub outcome: AcquisitionOutcome,
    pub http_status: Option<u16>,
    pub retry_after_seconds: Option<u64>,
    pub content_hash: Option<String>,
    pub error_code: Option<String>,
    pub cost: f64,
    pub started_at: DateTime<Utc>,
    pub finished_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DocumentRights {
    pub license: Option<String>,
    pub retrieval_allowed: bool,
    pub storage_allowed: bool,
    pub redistribution_allowed: bool,
    pub explicit_training_permission: bool,
    pub model_terms_allow_training: bool,
    pub training_eligible: bool,
    pub rights_source: String,
}

impl DocumentRights {
    pub fn recompute_training_eligible(&mut self) {
        self.training_eligible = self.storage_allowed
            && self.explicit_training_permission
            && self.model_terms_allow_training
            && self
                .license
                .as_deref()
                .is_some_and(license_allows_automatic_training);
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DocumentEnvelope {
    pub schema_version: String,
    pub document_id: Uuid,
    pub topic_ids: Vec<Uuid>,
    pub source_policy_id: Uuid,
    pub external_id: Option<String>,
    pub url: String,
    pub canonical_url: String,
    pub author: Option<String>,
    pub title: String,
    pub published_at: Option<DateTime<Utc>>,
    pub observed_at: DateTime<Utc>,
    pub fetched_at: DateTime<Utc>,
    pub raw_content_hash: Option<String>,
    pub cleaned_content_hash: String,
    pub extraction_method: AcquisitionMethod,
    pub extractor_version: String,
    pub language: String,
    pub content_type: String,
    pub rights: DocumentRights,
    pub prompt_injection_detected: bool,
    pub pii_detected: bool,
    pub secret_detected: bool,
    pub raw_expires_at: DateTime<Utc>,
    pub tombstoned: bool,
    #[serde(default)]
    pub metadata: Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum EvidenceRelationship {
    Supports,
    Opposes,
    Retracts,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeEvidenceRef {
    pub document_id: Uuid,
    pub canonical_url: String,
    pub content_hash: String,
    pub excerpt: Option<String>,
    pub relationship: EvidenceRelationship,
    pub observed_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeClaim {
    pub claim_id: Uuid,
    pub subject: String,
    pub predicate: String,
    pub object: String,
    pub valid_from: Option<DateTime<Utc>>,
    pub valid_until: Option<DateTime<Utc>>,
    pub confidence: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum KnowledgeStatus {
    Unverified,
    Corroborated,
    Contested,
    Superseded,
    Retracted,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeScores {
    pub relevance: f64,
    pub novelty: f64,
    pub source_reliability: f64,
    pub extraction_completeness: f64,
    pub confidence: f64,
    pub risk: f64,
    pub cost: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeCard {
    pub schema_version: String,
    pub card_id: Uuid,
    pub revision: u32,
    pub topic_ids: Vec<Uuid>,
    pub title: String,
    pub summary: String,
    pub entities: Vec<String>,
    pub claims: Vec<KnowledgeClaim>,
    pub evidence: Vec<KnowledgeEvidenceRef>,
    pub status: KnowledgeStatus,
    pub published_at: Option<DateTime<Utc>>,
    pub observed_at: DateTime<Utc>,
    pub valid_until: Option<DateTime<Utc>>,
    pub supersedes: Option<Uuid>,
    pub model_id: String,
    pub prompt_hash: String,
    pub scores: KnowledgeScores,
    pub training_eligible: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum EventStatus {
    Emerging,
    Peak,
    Fading,
    Resolved,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EventItem {
    pub schema_version: String,
    pub platform: String,
    pub external_id: String,
    pub title: String,
    pub url: String,
    pub author: Option<String>,
    pub published_at: Option<DateTime<Utc>>,
    pub summary: Option<String>,
    pub heat: i64,
    pub rank: i64,
    pub observations: Vec<(String, i64)>,
    pub document_id: Uuid,
    pub first_observed_at: DateTime<Utc>,
    pub last_observed_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TrackedEvent {
    pub schema_version: String,
    pub event_id: Uuid,
    pub title: String,
    pub status: EventStatus,
    pub first_seen_at: DateTime<Utc>,
    pub last_seen_at: DateTime<Utc>,
    pub peak_heat: i64,
    pub platforms: Vec<String>,
    pub item_count: u64,
    pub card_id: Option<Uuid>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeRetrieveRequest {
    pub query: String,
    #[serde(default)]
    pub topic_ids: Vec<Uuid>,
    #[serde(default)]
    pub statuses: Vec<KnowledgeStatus>,
    pub since: Option<DateTime<Utc>>,
    pub as_of: Option<DateTime<Utc>>,
    pub freshness_hours: Option<u32>,
    #[serde(default = "default_knowledge_limit")]
    pub limit: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeResult {
    pub card: KnowledgeCard,
    pub score: f64,
    pub stale: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeRetrieveResponse {
    pub registry_snapshot: String,
    pub items: Vec<KnowledgeResult>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct AcquisitionStatus {
    pub active_topics: u64,
    pub enabled_sources: u64,
    pub document_count: u64,
    pub knowledge_card_count: u64,
    pub pending_jobs: u64,
    pub dead_letter_jobs: u64,
    pub last_success_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct AcquisitionWorkerResult {
    pub schema_version: String,
    pub job_id: Uuid,
    pub worker: String,
    pub attempt: AcquisitionAttempt,
    pub document: Option<DocumentEnvelope>,
    #[serde(default)]
    pub discovered_urls: Vec<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum MetaModelStatus {
    Candidate,
    Shadow,
    Canary,
    Active,
    Superseded,
    Rejected,
    RolledBack,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetaTrainingCandidate {
    pub candidate_id: Uuid,
    pub dataset_hash: String,
    pub manifest_hash: String,
    pub decision_count: u64,
    pub replay_eval_count: u64,
    pub eligible_record_count: u64,
    pub source_domain_count: u64,
    pub topic_family_count: u64,
    pub created_at: DateTime<Utc>,
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, JsonSchema,
)]
#[serde(rename_all = "snake_case")]
pub enum DatasetSplit {
    Train,
    Validation,
    Holdout,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetSplitStats {
    pub train: u64,
    pub validation: u64,
    pub holdout: u64,
}

impl DatasetSplitStats {
    pub fn total(&self) -> u64 {
        self.train + self.validation + self.holdout
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetShard {
    pub split: DatasetSplit,
    pub record_kind: String,
    pub object_hash: String,
    pub uncompressed_hash: String,
    pub record_count: u64,
    pub compressed_bytes: u64,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetEligibilityReport {
    pub passed: bool,
    pub policy_version: String,
    pub contains_raw_documents: bool,
    pub eligible_records: u64,
    pub rejected_license_records: u64,
    pub rejected_safety_records: u64,
    #[serde(default)]
    pub reasons: Vec<String>,
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, JsonSchema,
)]
#[serde(rename_all = "snake_case")]
pub enum ExpertDatasetPurpose {
    Shared,
    Expert,
    Router,
    RoutingNegative,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertDefinition {
    pub id: String,
    pub description: String,
    pub task_kinds: Vec<MetaTaskKind>,
    pub is_fallback: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertTaxonomy {
    pub schema_version: String,
    pub taxonomy_id: String,
    pub version: String,
    pub experts: Vec<ExpertDefinition>,
    pub fallback_expert_id: String,
    pub router_top_k: u8,
    pub policy_version: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExpertAssignmentStatus {
    Assigned,
    Ambiguous,
    OutOfDistribution,
    NegativeTransfer,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAssignment {
    pub record_hash: String,
    pub split: DatasetSplit,
    pub record_kind: String,
    pub primary_expert_id: String,
    pub secondary_expert_ids: Vec<String>,
    pub status: ExpertAssignmentStatus,
    pub reason_codes: Vec<String>,
    pub source_domain: String,
    pub topic_family: String,
    pub task_kind: Option<MetaTaskKind>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertDatasetShard {
    pub split: DatasetSplit,
    pub purpose: ExpertDatasetPurpose,
    pub expert_id: Option<String>,
    pub record_kind: String,
    pub object_hash: String,
    pub uncompressed_hash: String,
    pub record_count: u64,
    pub compressed_bytes: u64,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertDatasetStats {
    pub records: DatasetSplitStats,
    pub decision_records: u64,
    pub replay_records: u64,
    /// Replay evidence outside the training split. This is the value used by
    /// the routed-training readiness gate.
    #[serde(default)]
    pub evaluation_replay_records: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertDatasetReadiness {
    pub ready: bool,
    pub minimum_router_records: u64,
    pub minimum_train_records_per_expert: u64,
    pub minimum_replays_per_expert: u64,
    pub router_train_records: u64,
    pub per_expert: BTreeMap<String, ExpertDatasetStats>,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertDatasetView {
    pub schema_version: String,
    pub view_id: Uuid,
    pub build_id: Uuid,
    pub taxonomy: ExpertTaxonomy,
    pub taxonomy_hash: String,
    pub assignments_hash: String,
    pub manifest_hash: String,
    pub bundle_hash: String,
    pub shards: Vec<ExpertDatasetShard>,
    pub assignment_count: u64,
    pub ambiguous_count: u64,
    pub out_of_distribution_count: u64,
    pub negative_transfer_count: u64,
    pub readiness: ExpertDatasetReadiness,
    pub policy_version: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetBuild {
    pub schema_version: String,
    pub build_id: Uuid,
    pub kind: String,
    pub source_watermark: Option<DateTime<Utc>>,
    pub parent_build_id: Option<Uuid>,
    pub shards: Vec<DatasetShard>,
    pub bundle_hash: String,
    pub manifest_hash: String,
    pub dedup_key: String,
    pub decision_count: u64,
    pub replay_eval_count: u64,
    pub rejected_record_count: u64,
    pub split_stats: DatasetSplitStats,
    pub eligibility: DatasetEligibilityReport,
    #[serde(default)]
    pub expert_view_id: Option<Uuid>,
    #[serde(default)]
    pub expert_manifest_hash: Option<String>,
    #[serde(default)]
    pub expert_taxonomy_hash: Option<String>,
    pub policy_version: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetDraft {
    pub kind: String,
    pub build_id: Uuid,
    pub manifest_hash: String,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetSnapshot {
    pub schema_version: String,
    pub snapshot_id: Uuid,
    pub kind: String,
    pub build_id: Uuid,
    pub bundle_hash: String,
    pub manifest_hash: String,
    pub decision_count: u64,
    pub replay_eval_count: u64,
    pub split_stats: DatasetSplitStats,
    pub eligibility: DatasetEligibilityReport,
    #[serde(default)]
    pub expert_view_id: Option<Uuid>,
    #[serde(default)]
    pub expert_manifest_hash: Option<String>,
    #[serde(default)]
    pub expert_taxonomy_hash: Option<String>,
    #[serde(default)]
    pub quality_report_id: Option<Uuid>,
    #[serde(default)]
    pub quality_report_hash: Option<String>,
    pub created_by: String,
    pub reason: String,
    pub legacy_candidate_id: Option<Uuid>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetSnapshotRevocation {
    pub snapshot_id: Uuid,
    pub actor: String,
    pub reason: String,
    pub revoked_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetSnapshotRecord {
    pub snapshot: DatasetSnapshot,
    pub revocation: Option<DatasetSnapshotRevocation>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreateDatasetSnapshotRequest {
    pub kind: String,
    pub build_id: Option<Uuid>,
    pub created_by: String,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct RevokeDatasetSnapshotRequest {
    pub actor: String,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct BaseModelPin {
    pub model_id: String,
    pub revision: String,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct QloraConfig {
    pub epochs: u8,
    pub max_sequence_length: u32,
    pub lora_rank: u16,
    pub lora_alpha: u16,
    pub lora_dropout: f64,
    pub learning_rate: f64,
    pub gradient_accumulation_steps: u16,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, Default)]
#[serde(rename_all = "snake_case")]
pub enum TrainingArchitecture {
    #[default]
    DenseLora,
    RoutedLora,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertTrainingPlan {
    pub architecture: TrainingArchitecture,
    pub expert_view_id: Uuid,
    pub train_router: bool,
    #[serde(default = "default_true")]
    pub train_shared: bool,
    pub expert_ids: Vec<String>,
    pub router_top_k: u8,
    pub fallback_expert_id: String,
}

impl Default for QloraConfig {
    fn default() -> Self {
        Self {
            epochs: 1,
            max_sequence_length: 2_048,
            lora_rank: 16,
            lora_alpha: 32,
            lora_dropout: 0.05,
            learning_rate: 0.0002,
            gradient_accumulation_steps: 16,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TrainingBudget {
    pub max_hourly_cny: f64,
    pub max_total_cny: f64,
    #[serde(default = "default_training_wall_seconds")]
    pub max_wall_seconds: u32,
}

fn default_training_wall_seconds() -> u32 {
    21_600
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum TrainingRunStatus {
    Requested,
    Provisioning,
    WaitingCapacity,
    WaitingWorker,
    Running,
    Uploading,
    Completed,
    Failed,
    Cancelled,
    TimedOut,
}

impl TrainingRunStatus {
    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            Self::Completed | Self::Failed | Self::Cancelled | Self::TimedOut
        )
    }

    pub fn can_transition_to(self, next: Self) -> bool {
        use TrainingRunStatus::*;
        self == next
            || matches!(
                (self, next),
                (Requested, Provisioning | Cancelled | Failed)
                    | (
                        Provisioning,
                        WaitingCapacity | WaitingWorker | Failed | Cancelled
                    )
                    | (
                        WaitingCapacity,
                        Provisioning | Failed | Cancelled | TimedOut
                    )
                    | (WaitingWorker, Running | Failed | Cancelled | TimedOut)
                    | (Running, Uploading | Failed | Cancelled | TimedOut)
                    | (Uploading, Completed | Failed | Cancelled | TimedOut)
            )
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TrainingRun {
    pub schema_version: String,
    pub run_id: Uuid,
    pub snapshot_id: Uuid,
    pub snapshot_bundle_hash: String,
    pub snapshot_manifest_hash: String,
    #[serde(default)]
    pub training_bundle_hash: Option<String>,
    #[serde(default)]
    pub training_manifest_hash: Option<String>,
    #[serde(default)]
    pub expert_plan: Option<ExpertTrainingPlan>,
    pub base_model: BaseModelPin,
    pub qlora: QloraConfig,
    pub provider: String,
    pub application_uuid: String,
    pub application_version: String,
    pub requested_gpu_spec: String,
    pub selected_gpu_spec: Option<String>,
    pub administrator: String,
    pub reason: String,
    pub budget: TrainingBudget,
    pub status: TrainingRunStatus,
    pub provider_instance_id: Option<String>,
    pub hourly_price_cny: Option<f64>,
    pub estimated_cost_cny: f64,
    pub artifact_hash: Option<String>,
    pub model_id: Option<String>,
    pub model_version: Option<String>,
    pub error: Option<String>,
    pub created_at: DateTime<Utc>,
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CreateTrainingRunRequest {
    pub snapshot_id: Uuid,
    pub base_model: BaseModelPin,
    #[serde(default)]
    pub qlora: QloraConfig,
    #[serde(default)]
    pub expert_plan: Option<ExpertTrainingPlan>,
    pub gpu_spec: String,
    pub administrator: String,
    pub reason: String,
    pub budget: TrainingBudget,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct StartTrainingRunRequest {
    pub administrator: String,
    pub reason: String,
    pub confirm_gpu_spec: String,
    pub confirm_max_hourly_cny: f64,
    pub confirm_max_total_cny: f64,
    pub confirm_max_wall_seconds: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CancelTrainingRunRequest {
    pub administrator: String,
    pub reason: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum GpuLeaseStatus {
    Provisioning,
    WaitingWorker,
    Running,
    ReleaseRequested,
    Released,
    ReleaseFailed,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct GpuLease {
    pub run_id: Uuid,
    pub provider: String,
    pub provider_instance_id: String,
    pub gpu_spec: String,
    pub gpu_memory_gb: u32,
    pub hourly_price_cny: f64,
    pub status: GpuLeaseStatus,
    pub last_provider_status: String,
    pub last_heartbeat_at: Option<DateTime<Utc>>,
    pub release_requested_at: Option<DateTime<Utc>>,
    pub released_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TrainingRunEvent {
    pub sequence: i64,
    pub run_id: Uuid,
    pub kind: String,
    pub payload: Value,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TrainingRunDetail {
    pub run: TrainingRun,
    pub lease: Option<GpuLease>,
    pub events: Vec<TrainingRunEvent>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertRouteRequest {
    pub task_kind: MetaTaskKind,
    #[serde(default)]
    pub input: Value,
    #[serde(default)]
    pub source_domain: String,
    #[serde(default)]
    pub topic_family: String,
    #[serde(default)]
    pub available_expert_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertRouteScore {
    pub expert_id: String,
    pub score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertRouteDecision {
    pub decision_id: Uuid,
    pub taxonomy_hash: String,
    pub selected_expert_id: String,
    pub fallback_used: bool,
    pub confidence: f64,
    pub scores: Vec<ExpertRouteScore>,
    pub reason_codes: Vec<String>,
    pub router_version: String,
    #[serde(default)]
    pub router_adapter: Option<ExpertAdapterRef>,
    #[serde(default)]
    pub selected_adapter: Option<ExpertAdapterRef>,
    #[serde(default)]
    pub dense_fallback: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAdapterArtifact {
    pub expert_id: String,
    pub path: String,
    pub sha256: String,
    pub byte_length: u64,
    pub training_records: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct RoutedAdapterBundleManifest {
    pub schema_version: String,
    pub kind: String,
    pub base_model: BaseModelPin,
    pub snapshot_id: Uuid,
    pub expert_view_id: Uuid,
    pub taxonomy_hash: String,
    pub router_top_k: u8,
    pub fallback_expert_id: String,
    pub router: Option<ExpertAdapterArtifact>,
    pub experts: Vec<ExpertAdapterArtifact>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExpertAdapterStatus {
    Candidate,
    Shadow,
    Canary,
    Active,
    Superseded,
    Rejected,
    RolledBack,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAdapterMetrics {
    pub evaluation_count: u64,
    pub canary_decisions: u64,
    pub canary_duration_seconds: u64,
    pub old_task_retention: f64,
    pub task_success_delta: f64,
    pub negative_transfer_rate_delta: f64,
    pub routing_accuracy_delta: f64,
    pub policy_violations: u64,
    pub injection_regression: bool,
}

impl ExpertAdapterMetrics {
    pub fn passes_canary_gate(&self) -> bool {
        self.evaluation_count >= 200
            && self.policy_violations == 0
            && !self.injection_regression
            && self.old_task_retention >= 0.98
            && self.task_success_delta >= 0.0
            && self.negative_transfer_rate_delta <= 0.0
            && self.routing_accuracy_delta >= 0.0
    }

    pub fn passes_release_gate(&self) -> bool {
        self.passes_canary_gate()
            && self.canary_decisions >= 1_000
            && self.canary_duration_seconds >= 86_400
    }
}

fn default_eval_set_size() -> u64 {
    200
}
fn default_metacognition_set_size() -> u64 {
    150
}

/// A file pinned by path and lowercase SHA-256 so evaluation inputs are
/// immutable and server-checkable.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct PinnedFile {
    pub path: String,
    pub sha256: String,
}

/// Loopback ports for the two evaluation arms (frozen base vs base+adapter).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EvalPorts {
    pub base: u16,
    pub adapted: u16,
}

/// Per-set record caps for the adapter evaluation harness.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EvalSetSizes {
    #[serde(default = "default_eval_set_size")]
    pub role: u64,
    #[serde(default = "default_eval_set_size")]
    pub routing: u64,
    #[serde(default = "default_eval_set_size")]
    pub negative_transfer: u64,
    #[serde(default = "default_eval_set_size")]
    pub retention: u64,
    /// Full frozen metacognition probe suite when the plan pins it; ignored
    /// (set skipped) when `metacognition_probes` is absent.
    #[serde(default = "default_metacognition_set_size")]
    pub metacognition: u64,
}

impl Default for EvalSetSizes {
    fn default() -> Self {
        Self {
            role: default_eval_set_size(),
            routing: default_eval_set_size(),
            negative_transfer: default_eval_set_size(),
            metacognition: default_metacognition_set_size(),
            retention: default_eval_set_size(),
        }
    }
}

/// Deterministic generation settings shared by both evaluation arms.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EvalGeneration {
    #[serde(default = "default_eval_n_predict")]
    pub n_predict: u64,
    #[serde(default)]
    pub temperature: f64,
    #[serde(default)]
    pub seed: u64,
    #[serde(default = "default_eval_stop")]
    pub stop: Vec<String>,
}

fn default_eval_n_predict() -> u64 {
    512
}

fn default_eval_stop() -> Vec<String> {
    vec!["<|meta_task|>".to_owned()]
}

impl Default for EvalGeneration {
    fn default() -> Self {
        Self {
            n_predict: default_eval_n_predict(),
            temperature: 0.0,
            seed: 0,
            stop: default_eval_stop(),
        }
    }
}

fn default_eval_max_wall_seconds() -> u64 {
    3_600
}

/// Operator-supplied plan for a local dual-arm (frozen base GGUF vs merged
/// base+adapter GGUF) llama.cpp evaluation of one expert adapter version.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAdapterEvalPlan {
    pub schema_version: String,
    pub kind: String,
    pub expert_id: String,
    pub version: String,
    pub llama_server: PinnedFile,
    pub base_gguf: PinnedFile,
    pub adapted_gguf: PinnedFile,
    pub ports: EvalPorts,
    #[serde(default)]
    pub set_sizes: EvalSetSizes,
    #[serde(default)]
    pub generation: EvalGeneration,
    pub injection_probes: PinnedFile,
    /// Optional pin of `benchmarks/metacognition/manifest.json`; when present the
    /// harness also runs the frozen TG/KB/ST probe suites on both arms.
    #[serde(default)]
    pub metacognition_probes: Option<PinnedFile>,
    #[serde(default = "default_eval_max_wall_seconds")]
    pub max_wall_seconds: u64,
}

/// Hash-pinned summary of one deterministic evaluation record set.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EvalSetSummary {
    pub set_name: String,
    pub record_count: u64,
    /// SHA-256 of the concatenated per-record hashes in selection order.
    pub records_sha256: String,
}

/// Per-suite metacognition probe metrics for one arm. Suite-specific metrics
/// are `None` when the suite does not define them; rates are computed over
/// executed (non-skipped) probes.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetacognitionSuiteMetrics {
    pub items: u64,
    pub parse_rate: f64,
    pub contract_valid_rate: f64,
    #[serde(default)]
    pub with_environment_accuracy: Option<f64>,
    #[serde(default)]
    pub without_environment_accuracy: Option<f64>,
    #[serde(default)]
    pub fresh_answer_accuracy: Option<f64>,
    #[serde(default)]
    pub as_of_echo_rate: Option<f64>,
    #[serde(default)]
    pub stale_card_misuse_rate: Option<f64>,
    #[serde(default)]
    pub refusal_precision: Option<f64>,
    #[serde(default)]
    pub refusal_recall: Option<f64>,
    #[serde(default)]
    pub refusal_f1: Option<f64>,
    #[serde(default)]
    pub known_set_accuracy: Option<f64>,
    #[serde(default)]
    pub unknown_action_accuracy: Option<f64>,
    #[serde(default)]
    pub search_trigger_precision: Option<f64>,
    #[serde(default)]
    pub search_required_action_accuracy: Option<f64>,
    #[serde(default)]
    pub answer_condition_accuracy: Option<f64>,
}

/// Dual-arm metacognition probe results: per-suite metrics for the base and
/// adapted arms plus element-wise deltas (adapted minus base; `None` when
/// either arm lacks the metric). Suite keys are `tg`, `kb`, `st`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetacognitionEvalBlock {
    pub base: BTreeMap<String, MetacognitionSuiteMetrics>,
    pub adapted: BTreeMap<String, MetacognitionSuiteMetrics>,
    pub delta: BTreeMap<String, MetacognitionSuiteMetrics>,
    pub set_summaries: Vec<EvalSetSummary>,
    pub skipped_fixture_missing: u64,
}

/// Immutable evidence record produced by the adapter evaluation harness.
/// `metrics.canary_*` are always zero here: those dimensions are recomputed
/// from the server-side routing stream and are not harness outputs.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAdapterEvalReport {
    pub schema_version: String,
    pub kind: String,
    pub report_id: Uuid,
    pub adapter_id: Uuid,
    pub expert_id: String,
    pub version: String,
    pub base_model: BaseModelPin,
    pub snapshot_id: Uuid,
    pub expert_view_id: Uuid,
    pub taxonomy_hash: String,
    pub base_gguf_sha256: String,
    pub adapted_gguf_sha256: String,
    pub llama_server_sha256: String,
    pub set_summaries: Vec<EvalSetSummary>,
    pub metrics: ExpertAdapterMetrics,
    pub task_success_delta_ci95_low: f64,
    pub routing_accuracy_delta_ci95_low: f64,
    pub injection_probe_base_violations: u64,
    pub injection_probe_adapted_violations: u64,
    pub results_object_hash: String,
    /// Present iff the plan pinned `metacognition_probes`.
    #[serde(default)]
    pub metacognition: Option<MetacognitionEvalBlock>,
    pub harness_version: String,
    pub llama_cpp_version: String,
    pub started_at: DateTime<Utc>,
    pub finished_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAdapterVersion {
    pub schema_version: String,
    pub adapter_id: Uuid,
    pub expert_id: String,
    pub version: String,
    pub bundle_hash: String,
    pub artifact_path: String,
    pub artifact_hash: String,
    pub byte_length: u64,
    pub training_records: u64,
    pub base_model: BaseModelPin,
    pub training_run_id: Uuid,
    pub snapshot_id: Uuid,
    pub expert_view_id: Uuid,
    pub taxonomy_hash: String,
    pub status: ExpertAdapterStatus,
    pub metrics: Option<ExpertAdapterMetrics>,
    pub previous_active: Option<ArtifactVersionRef>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAdapterOperationRequest {
    pub actor: String,
    pub reason: String,
    #[serde(default)]
    pub metrics: Option<ExpertAdapterMetrics>,
    /// Recorded dual-arm evaluation report gate evidence for canary/activate.
    #[serde(default)]
    pub eval_report_id: Option<Uuid>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ExpertAdapterRef {
    pub expert_id: String,
    pub version: String,
    pub base_model: BaseModelPin,
    pub taxonomy_hash: String,
    pub bundle_hash: String,
    pub artifact_path: String,
    pub artifact_hash: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetaModelMetrics {
    pub old_task_retention: f64,
    pub ndcg_at_10: f64,
    pub baseline_ndcg_at_10: f64,
    pub max_core_topic_regression: f64,
    pub fact_precision_delta: f64,
    pub policy_violations: u64,
    pub injection_regression: bool,
    pub cost_per_useful_card_change: f64,
}

impl MetaModelMetrics {
    pub fn passes_automatic_activation(&self) -> bool {
        self.policy_violations == 0
            && !self.injection_regression
            && self.old_task_retention >= 0.98
            && (if self.baseline_ndcg_at_10 > 0.0 {
                (self.ndcg_at_10 - self.baseline_ndcg_at_10) / self.baseline_ndcg_at_10 >= 0.03
            } else {
                self.ndcg_at_10 >= 0.03
            })
            && self.max_core_topic_regression <= 0.02
            && self.fact_precision_delta >= 0.0
            && self.cost_per_useful_card_change <= 0.10
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetaModelBundle {
    pub schema_version: String,
    pub model_id: String,
    pub version: String,
    pub artifact_hash: String,
    pub base_model: String,
    pub training_candidate_id: Uuid,
    pub trainer: String,
    pub metrics: MetaModelMetrics,
    pub status: MetaModelStatus,
    pub previous_active: Option<ArtifactVersionRef>,
    pub canary_started_at: Option<DateTime<Utc>>,
    pub canary_decisions: u64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum MetaTaskKind {
    Relevance,
    NoiseFilter,
    Deduplication,
    RetrievalRanking,
    ClaimRelationship,
    AcquisitionEscalation,
    CurriculumPriority,
    ExpectedInformationGain,
    SkillWorkflowRouting,
    SkillWorkflowEvolution,
    TemporalGrounding,
    KnowledgeBoundary,
    SearchPlanning,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum MetacognitionAction {
    Answer,
    SearchInternal,
    RequestAcquisition,
    Insufficient,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum MetacognitionBasis {
    Parametric,
    Evidence,
    None,
}

/// Strict output contract for temporal-grounding, knowledge-boundary and
/// search-planning decisions (`MetaTaskKind::{TemporalGrounding,
/// KnowledgeBoundary, SearchPlanning}`). Probes, generated training traces and
/// the runtime assessment hook all parse this shape; per-action field
/// discipline is enforced by `validate_metacognition_decision`.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetacognitionDecision {
    pub action: MetacognitionAction,
    pub as_of_used: Option<DateTime<Utc>>,
    pub query: Option<String>,
    pub freshness_hours: Option<u32>,
    pub answer: Option<String>,
    pub answer_basis: MetacognitionBasis,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetaDecisionTrace {
    pub schema_version: String,
    pub decision_id: Uuid,
    pub task_kind: MetaTaskKind,
    pub input_hash: String,
    pub input: Value,
    pub output: Value,
    pub source_domain: String,
    pub topic_family: String,
    pub policy_version: String,
    pub controller_version: String,
    pub confidence: f64,
    pub cost: f64,
    pub useful: bool,
    pub training_eligible: bool,
    pub policy_violations: u32,
    pub prompt_injection_detected: bool,
    #[serde(default)]
    pub data_classification: DataClassification,
    #[serde(default)]
    pub external_processing: ExternalProcessingPermission,
    #[serde(default)]
    pub redaction_attestation_hash: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetaReplayEvaluation {
    pub schema_version: String,
    pub evaluation_id: Uuid,
    pub candidate_id: Option<Uuid>,
    pub task_id: String,
    pub source_domain: String,
    pub topic_family: String,
    pub baseline_score: f64,
    pub candidate_score: f64,
    pub fact_correct: bool,
    pub safety_passed: bool,
    #[serde(default)]
    pub data_classification: DataClassification,
    #[serde(default)]
    pub external_processing: ExternalProcessingPermission,
    #[serde(default)]
    pub redaction_attestation_hash: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum QualitySubjectKind {
    MetaDecision,
    MetaReplay,
    SyntheticCandidate,
    DatasetBuild,
    KnowledgeCard,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum QualityModelStage {
    Flash,
    Pro,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum QualityVerdict {
    Pass,
    Veto,
    Quarantine,
    NeedsArbitration,
}

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, JsonSchema,
)]
#[serde(rename_all = "snake_case")]
pub enum QualityIssueCode {
    PrivacyLeak,
    PromptInjection,
    LabelContradiction,
    Hallucination,
    Unsupported,
    Ambiguous,
    Incomplete,
    Irrelevant,
    Duplicate,
    LowQuality,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct QualityDimensions {
    pub groundedness: f64,
    pub correctness: f64,
    pub relevance: f64,
    pub consistency: f64,
    pub completeness: f64,
    pub label_confidence: f64,
    pub ambiguity: f64,
    pub privacy_risk: f64,
    pub injection_risk: f64,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ModelTokenUsage {
    pub prompt_tokens: u64,
    pub prompt_cache_hit_tokens: u64,
    pub prompt_cache_miss_tokens: u64,
    pub completion_tokens: u64,
    pub reasoning_tokens: u64,
    pub total_tokens: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct RedactionAttestation {
    pub schema_version: String,
    pub attestation_id: Uuid,
    pub subject_kind: QualitySubjectKind,
    pub subject_id: String,
    pub subject_hash: String,
    pub exported_payload_hash: String,
    pub scanner_version: String,
    pub secret_findings: u32,
    pub pii_findings: u32,
    pub prompt_injection_findings: u32,
    pub source_characters: u64,
    pub exported_characters: u64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DataQualityAssessment {
    pub schema_version: String,
    pub assessment_id: Uuid,
    pub subject_kind: QualitySubjectKind,
    pub subject_id: String,
    pub subject_hash: String,
    pub stage: QualityModelStage,
    pub model_id: String,
    pub system_fingerprint: String,
    pub prompt_version: String,
    pub prompt_hash: String,
    pub schema_hash: String,
    pub verdict: QualityVerdict,
    pub dimensions: QualityDimensions,
    #[serde(default)]
    pub issue_codes: Vec<QualityIssueCode>,
    #[serde(default)]
    pub evidence_refs: Vec<String>,
    #[serde(default)]
    pub suggested_actions: Vec<String>,
    pub confidence: f64,
    pub usage: ModelTokenUsage,
    pub estimated_cost_microusd: u64,
    pub redaction_attestation_hash: String,
    pub parent_assessment_id: Option<Uuid>,
    pub output_hash: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ModelEndpointStatus {
    PendingApproval,
    Calibration,
    Shadow,
    Active,
    Superseded,
    Rejected,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ModelCalibrationMetrics {
    pub fixture_count: u64,
    pub schema_valid_rate: f64,
    pub critical_safety_recall: f64,
    pub verdict_macro_f1: f64,
    #[serde(default)]
    pub shadow_count: Option<u64>,
    #[serde(default)]
    pub shadow_disagreement_rate: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ModelEndpointVersion {
    pub schema_version: String,
    pub endpoint_version_id: Uuid,
    pub provider: String,
    pub model_id: String,
    pub system_fingerprint: String,
    pub prompt_version: String,
    pub schema_hash: String,
    pub status: ModelEndpointStatus,
    pub metrics: ModelCalibrationMetrics,
    pub approved_by: Option<String>,
    pub approval_reason: Option<String>,
    pub first_seen_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ProviderPricingPolicy {
    pub schema_version: String,
    pub policy_id: String,
    pub provider: String,
    pub flash_input_cache_hit_usd_per_million: f64,
    pub flash_input_cache_miss_usd_per_million: f64,
    pub flash_output_usd_per_million: f64,
    pub pro_input_cache_hit_usd_per_million: f64,
    pub pro_input_cache_miss_usd_per_million: f64,
    pub pro_output_usd_per_million: f64,
    pub usd_to_cny_ceiling: f64,
    pub daily_max_cny: f64,
    pub confirmed_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ModelUsageLedger {
    pub provider: String,
    pub shanghai_day: String,
    pub flash_calls: u64,
    pub pro_calls: u64,
    pub usage: ModelTokenUsage,
    pub reserved_microusd: u64,
    pub spent_microusd: u64,
    pub estimated_cny: f64,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SyntheticTransformation {
    LabelRepair,
    HardNegative,
    CounterfactualPair,
    PreferencePair,
    FailureExplanation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SyntheticVerificationKind {
    ExecutableTest,
    GateReplay,
    PairedReplay,
    SemanticReview,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SyntheticCandidateStatus {
    Quarantined,
    Verified,
    Approved,
    Rejected,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SyntheticTrainingCandidate {
    pub schema_version: String,
    pub candidate_id: Uuid,
    pub parent_subject_kind: QualitySubjectKind,
    pub parent_subject_id: String,
    pub parent_hash: String,
    pub task_kind: MetaTaskKind,
    pub transformation: SyntheticTransformation,
    pub input: Value,
    pub output: Value,
    pub content_hash: String,
    #[serde(default)]
    pub evidence_refs: Vec<String>,
    pub source_license: String,
    pub verification_kind: SyntheticVerificationKind,
    pub objective_verified: bool,
    pub model_assessment_id: Uuid,
    pub generation_model_id: String,
    pub generation_system_fingerprint: String,
    pub generation_prompt_version: String,
    pub generation_prompt_hash: String,
    #[serde(default)]
    pub generation_usage: ModelTokenUsage,
    pub generation_estimated_cost_microusd: u64,
    pub generation_depth: u8,
    pub status: SyntheticCandidateStatus,
    pub reviewed_by: Option<String>,
    pub review_reason: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatasetQualityReport {
    pub schema_version: String,
    pub report_id: Uuid,
    pub build_id: Uuid,
    pub report_hash: String,
    pub policy_version: String,
    pub total_records: u64,
    pub assessed_records: u64,
    pub unresolved_records: u64,
    pub deterministic_violations: u64,
    pub split_leakage_count: u64,
    pub lineage_missing_count: u64,
    pub generated_records: u64,
    pub generated_ratio: f64,
    pub pro_audit_sample_size: u64,
    pub critical_safety_misses: u64,
    pub non_safety_disagreements: u64,
    pub disagreement_rate: f64,
    pub model_ids: Vec<String>,
    pub system_fingerprints: Vec<String>,
    pub prompt_versions: Vec<String>,
    #[serde(default)]
    pub estimated_cost_cny: Option<f64>,
    pub gate_passed: bool,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ReviewQualityModelRequest {
    pub actor: String,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ReviewSyntheticCandidateRequest {
    pub actor: String,
    pub reason: String,
    /// Objective evidence for the `:verify` action: a passing paired
    /// evaluation whose metadata references the candidate.
    #[serde(default)]
    pub paired_eval_id: Option<Uuid>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct QualityStatus {
    pub enabled: bool,
    pub enforcement_required: bool,
    pub provider: String,
    pub flash_model: String,
    pub pro_model: String,
    pub pending_assessments: u64,
    pub pending_arbitrations: u64,
    pub quarantined_records: u64,
    pub synthetic_candidates: u64,
    pub latest_passed_build_id: Option<Uuid>,
    pub usage: Option<ModelUsageLedger>,
    pub active_model_versions: Vec<ModelEndpointVersion>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MetaCanaryDecision {
    pub schema_version: String,
    pub decision_id: Uuid,
    pub model_id: String,
    pub version: String,
    pub assigned_to_canary: bool,
    pub successful: bool,
    pub policy_violation: bool,
    pub useful: bool,
    pub cost: f64,
    pub created_at: DateTime<Utc>,
}
