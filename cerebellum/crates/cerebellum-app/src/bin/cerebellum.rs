use anyhow::{Context, Result};
use cerebellum_app::{
    Registry, builtins, collector, eval, importer, learning, mcp, metacognition, sandbox,
    scheduler, schemas,
};
use cerebellum_core::*;
use clap::{Parser, Subcommand};
use serde::Serialize;
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(version, about = "Manage the Cerebellum workflow registry")]
struct Args {
    #[arg(
        long,
        env = "CEREBELLUM_DATA_DIR",
        default_value = ".cerebellum",
        global = true
    )]
    data_dir: PathBuf,
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    Init {
        #[arg(long)]
        wiki: Option<PathBuf>,
        #[arg(long)]
        limit: Option<usize>,
    },
    ImportWiki {
        path: PathBuf,
        #[arg(long)]
        limit: Option<usize>,
    },
    ImportEvolver {
        path: PathBuf,
    },
    CollectGithub {
        repository_url: String,
        commit_sha: String,
        #[arg(long, env = "GITHUB_TOKEN")]
        token: Option<String>,
    },
    ListSkills {
        #[arg(long)]
        query: Option<String>,
        #[arg(long)]
        include_quarantined: bool,
        #[arg(long, default_value_t = 100)]
        limit: usize,
    },
    ListWorkflows,
    TransitionSkill {
        id: String,
        version: String,
        status: String,
    },
    RecordEval {
        path: PathBuf,
    },
    RefreshEvidence {
        id: String,
        version: String,
    },
    RunPairedEval {
        plan: PathBuf,
        #[arg(long)]
        record: bool,
    },
    RunAdapterEval {
        plan: PathBuf,
        #[arg(long)]
        record: bool,
    },
    TrainingStatus,
    ExportTraining {
        output: PathBuf,
        #[arg(long)]
        allow_insufficient: bool,
    },
    ExportSchemas {
        output_dir: PathBuf,
    },
    IngestExperience {
        path: PathBuf,
    },
    AddFeedback {
        path: PathBuf,
    },
    AttestFeedback {
        path: PathBuf,
        output: PathBuf,
    },
    LearningStatus,
    RebuildKnowledgeIndex,
    CreateCurriculum {
        path: PathBuf,
    },
    ListCurricula,
    BuildTrainingCandidate,
    ListTrainingCandidates,
    OptimizeSkill {
        skill_id: String,
        skill_version: String,
        benchmark_manifest: PathBuf,
        benchmark_bundle: PathBuf,
        #[arg(long, env = "TARGET_MODEL")]
        target_model: String,
        #[arg(long, env = "OPTIMIZER_MODEL")]
        optimizer_model: String,
        #[arg(long)]
        baseline_file: Option<PathBuf>,
        #[arg(long)]
        source_repository_url: Option<String>,
        #[arg(long)]
        source_commit_sha: Option<String>,
        #[arg(long)]
        source_path: Option<String>,
        #[arg(long, default_value = "NOASSERTION")]
        source_license: String,
    },
    OptimizationStatus {
        run_id: uuid::Uuid,
    },
    ReviewOptimization {
        run_id: uuid::Uuid,
        action: String,
        #[arg(long)]
        actor: String,
        #[arg(long)]
        reason: String,
    },
    ImportConsolidation {
        path: PathBuf,
    },
    SimulateLearning {
        #[arg(long, default_value_t = 100)]
        count: u64,
    },
    SimulateMetacognition {
        #[arg(long, default_value_t = 2_500)]
        count: u64,
    },
    RegisterModel {
        model_id: String,
        version: String,
        artifact_hash: String,
        training_candidate_id: uuid::Uuid,
        #[arg(long)]
        evidence: PathBuf,
    },
    WorkerOnce {
        #[arg(long, default_value = "cerebellum-cli-worker")]
        worker: String,
        #[arg(long, env = "GITHUB_TOKEN")]
        github_token: Option<String>,
        #[arg(long, env = "CEREBELLUM_MEDIACRAWLER_SEARCH")]
        mediacrawler_search: bool,
    },
    ListExpertViews,
    RouteExpert {
        request: PathBuf,
    },
    ListExpertAdapters {
        #[arg(long)]
        expert_id: Option<String>,
    },
    ReviewExpertAdapter {
        expert_id: String,
        version: String,
        action: String,
        #[arg(long)]
        actor: String,
        #[arg(long)]
        reason: String,
        #[arg(long)]
        metrics: Option<PathBuf>,
        #[arg(long)]
        eval_report_id: Option<uuid::Uuid>,
    },
    QualityAssessments {
        #[arg(long)]
        subject_kind: Option<String>,
        #[arg(long)]
        subject_id: Option<String>,
        #[arg(long, default_value_t = 100)]
        limit: usize,
    },
    QualityModelVersions,
    ReviewQualityModel {
        endpoint_version_id: uuid::Uuid,
        action: String,
        #[arg(long)]
        actor: String,
        #[arg(long)]
        reason: String,
    },
    QualityBackfill {
        #[arg(long, default_value_t = 1000)]
        limit: usize,
    },
    ListSyntheticCandidates {
        #[arg(long)]
        status: Option<String>,
        #[arg(long, default_value_t = 100)]
        limit: usize,
    },
    ReviewSyntheticCandidate {
        candidate_id: uuid::Uuid,
        action: String,
        #[arg(long)]
        actor: String,
        #[arg(long)]
        reason: String,
    },
    Mcp {
        #[arg(long, default_value = "http://127.0.0.1:3927")]
        server_url: String,
        #[arg(long)]
        token: Option<String>,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    match args.command {
        Command::Mcp { server_url, token } => {
            let token = match token {
                Some(value) => value,
                None => fs::read_to_string(args.data_dir.join("auth.token"))
                    .context("read auth token; start cerebellumd once or pass --token")?
                    .trim()
                    .to_owned(),
            };
            mcp::run_stdio(&server_url, &token).await?;
        }
        command => {
            let registry = Registry::open(&args.data_dir)?;
            match command {
                Command::Init { wiki, limit } => {
                    builtins::seed(&registry)?;
                    let report = wiki
                        .map(|path| importer::import_wiki(&registry, &path, limit))
                        .transpose()?;
                    print_json(&serde_json::json!({"initialized":true,"wiki":report}))?;
                }
                Command::ImportWiki { path, limit } => {
                    print_json(&importer::import_wiki(&registry, &path, limit)?)?
                }
                Command::ImportEvolver { path } => print_json(
                    &serde_json::json!({"imported":importer::import_evolver_export(&registry,&path)?}),
                )?,
                Command::CollectGithub {
                    repository_url,
                    commit_sha,
                    token,
                } => print_json(
                    &collector::collect_github(
                        &registry,
                        &repository_url,
                        &commit_sha,
                        token.as_deref(),
                    )
                    .await?,
                )?,
                Command::ListSkills {
                    query,
                    include_quarantined,
                    limit,
                } => print_json(&registry.search_skills(
                    query.as_deref(),
                    include_quarantined,
                    limit.min(10000),
                )?)?,
                Command::ListWorkflows => print_json(&registry.list_workflows()?)?,
                Command::TransitionSkill {
                    id,
                    version,
                    status,
                } => print_json(&registry.transition_skill(
                    &id,
                    &version,
                    parse_status(&status)?,
                )?)?,
                Command::RecordEval { path } => {
                    let value: PairedEvalRecord = serde_json::from_str(&fs::read_to_string(path)?)?;
                    registry.record_paired_eval(&value)?;
                    print_json(&serde_json::json!({"recorded":value.eval_id}))?;
                }
                Command::RefreshEvidence { id, version } => {
                    print_json(&eval::refresh_skill_evidence(&registry, &id, &version)?)?;
                }
                Command::RunPairedEval { plan, record } => {
                    let plan: cerebellum_core::PairedSandboxPlan =
                        serde_json::from_str(&fs::read_to_string(plan)?)?;
                    if registry
                        .get_skill(&plan.skill_id, &plan.skill_version)?
                        .is_none()
                    {
                        anyhow::bail!(
                            "paired evaluation references unknown Skill {}@{}",
                            plan.skill_id,
                            plan.skill_version
                        );
                    }
                    let result = sandbox::run_paired(&args.data_dir, &plan).await?;
                    if record {
                        registry.record_paired_eval(&result)?;
                    }
                    print_json(&result)?;
                }
                Command::RunAdapterEval { plan, record } => {
                    let plan: ExpertAdapterEvalPlan =
                        serde_json::from_str(&fs::read_to_string(plan)?)?;
                    let (report, results) =
                        cerebellum_app::adapter_eval::run_adapter_eval(&registry, &plan).await?;
                    if record {
                        registry.record_expert_adapter_eval_report(&report, &results)?;
                    }
                    print_json(&report)?;
                }
                Command::TrainingStatus => {
                    let (decisions, paired_evals) = registry.training_counts()?;
                    print_json(
                        &serde_json::json!({"routing_decisions":decisions,"paired_evals":paired_evals,"required":{"routing_decisions":eval::MIN_ROUTING_DECISIONS,"paired_evals":eval::MIN_PAIRED_EVALS},"ready":decisions>=eval::MIN_ROUTING_DECISIONS&&paired_evals>=eval::MIN_PAIRED_EVALS}),
                    )?;
                }
                Command::ExportTraining {
                    output,
                    allow_insufficient,
                } => print_json(
                    &serde_json::json!({"records":eval::export_training(&registry,&output,allow_insufficient)?,"output":output}),
                )?,
                Command::ExportSchemas { output_dir } => {
                    export_schemas(&output_dir)?;
                    print_json(&serde_json::json!({"output_dir":output_dir}))?;
                }
                Command::IngestExperience { path } => {
                    let experience: ExperienceEnvelope =
                        serde_json::from_str(&fs::read_to_string(path)?)?;
                    let (inserted, decision) =
                        learning::LearningController::ingest(&registry, &experience)?;
                    print_json(&serde_json::json!({"inserted":inserted,"decision":decision}))?;
                }
                Command::AddFeedback { path } => {
                    let feedback: FeedbackSignal =
                        serde_json::from_str(&fs::read_to_string(path)?)?;
                    let (inserted, decision) =
                        learning::LearningController::add_feedback(&registry, &feedback)?;
                    print_json(&serde_json::json!({"inserted":inserted,"decision":decision}))?;
                }
                Command::AttestFeedback { path, output } => {
                    let mut feedback: FeedbackSignal =
                        serde_json::from_str(&fs::read_to_string(path)?)?;
                    validate_feedback(&feedback)?;
                    feedback.attestation = Some(registry.attest_feedback(&feedback)?);
                    fs::write(
                        &output,
                        format!("{}\n", serde_json::to_string_pretty(&feedback)?),
                    )?;
                    print_json(
                        &serde_json::json!({"output":output,"feedback_id":feedback.feedback_id}),
                    )?;
                }
                Command::LearningStatus => print_json(&learning::learning_status(&registry)?)?,
                Command::RebuildKnowledgeIndex => print_json(&serde_json::json!({
                    "embedded_revisions":registry.rebuild_knowledge_embeddings()?,
                    "model":"feature-hash-v1"
                }))?,
                Command::CreateCurriculum { path } => {
                    let request: CreateCurriculumRequest =
                        serde_json::from_str(&fs::read_to_string(path)?)?;
                    print_json(&learning::create_curriculum(&registry, &request)?)?;
                }
                Command::ListCurricula => print_json(&registry.list_curricula()?)?,
                Command::BuildTrainingCandidate => {
                    print_json(&learning::build_training_candidate(&registry)?)?
                }
                Command::ListTrainingCandidates => {
                    print_json(&registry.list_training_candidates()?)?
                }
                Command::OptimizeSkill {
                    skill_id,
                    skill_version,
                    benchmark_manifest,
                    benchmark_bundle,
                    target_model,
                    optimizer_model,
                    baseline_file,
                    source_repository_url,
                    source_commit_sha,
                    source_path,
                    source_license,
                } => {
                    ensure_optimization_baseline(
                        &registry,
                        &skill_id,
                        &skill_version,
                        baseline_file.as_ref(),
                        source_repository_url.as_deref(),
                        source_commit_sha.as_deref(),
                        source_path.as_deref(),
                        &source_license,
                    )?;
                    let manifest_bytes = fs::read(&benchmark_manifest)?;
                    let manifest: CodingBenchmarkManifest =
                        serde_json::from_slice(&manifest_bytes)?;
                    validate_coding_benchmark(&manifest)?;
                    let manifest_hash = registry.put_object(&manifest_bytes)?;
                    let bundle_hash = registry.put_object(&fs::read(&benchmark_bundle)?)?;
                    let request = CreateOptimizationRunRequest {
                        skill_id,
                        skill_version,
                        benchmark_manifest_hash: manifest_hash,
                        benchmark_bundle_hash: bundle_hash,
                        container_image_digest: manifest.container_image,
                        target_model,
                        optimizer_model,
                        budget: OptimizationBudget::default(),
                    };
                    print_json(&registry.create_optimization_run(&request)?)?;
                }
                Command::OptimizationStatus { run_id } => print_json(
                    &registry
                        .get_optimization_run(run_id)?
                        .ok_or_else(|| anyhow::anyhow!("optimization run not found"))?,
                )?,
                Command::ReviewOptimization {
                    run_id,
                    action,
                    actor,
                    reason,
                } => {
                    let (run, skill_version) = registry.review_optimization(
                        run_id,
                        &action,
                        &OptimizationReviewRequest { actor, reason },
                    )?;
                    print_json(&serde_json::json!({"run":run,"skill_version":skill_version}))?;
                }
                Command::ImportConsolidation { path } => {
                    let response: ConsolidationResponse =
                        serde_json::from_str(&fs::read_to_string(path)?)?;
                    print_json(
                        &serde_json::json!({"imported":learning::import_consolidation(&registry,&response)?}),
                    )?;
                }
                Command::SimulateLearning { count } => {
                    if count > 10_000 {
                        anyhow::bail!("simulation count is capped at 10,000");
                    }
                    for index in 0..count {
                        let experience = learning::synthetic_experience(index);
                        learning::LearningController::ingest(&registry, &experience)?;
                        learning::LearningController::add_feedback(
                            &registry,
                            &learning::synthetic_feedback(&registry, &experience),
                        )?;
                    }
                    let candidate = learning::build_training_candidate(&registry)?;
                    print_json(
                        &serde_json::json!({"simulated":count,"status":learning::learning_status(&registry)?,"training_candidate":candidate}),
                    )?;
                }
                Command::SimulateMetacognition { count } => {
                    if count > 10_000 {
                        anyhow::bail!("simulation count is capped at 10,000");
                    }
                    print_json(&metacognition::simulate_metacognition(&registry, count)?)?;
                }
                Command::RegisterModel {
                    model_id,
                    version,
                    artifact_hash,
                    training_candidate_id,
                    evidence,
                } => {
                    let now = chrono::Utc::now();
                    let evidence: ModelEvidence =
                        serde_json::from_str(&fs::read_to_string(evidence)?)?;
                    let model = ModelVersion {
                        model_id,
                        version,
                        artifact_hash,
                        training_candidate_id,
                        evidence,
                        status: ModelStatus::Candidate,
                        reviewed_by: None,
                        review_reason: None,
                        created_at: now,
                        updated_at: now,
                    };
                    registry.register_model(&model)?;
                    print_json(&model)?;
                }
                Command::WorkerOnce {
                    worker,
                    github_token,
                    mediacrawler_search,
                } => print_json(
                    &scheduler::run_once(
                        &registry,
                        &worker,
                        github_token.as_deref(),
                        mediacrawler_search,
                    )
                    .await?,
                )?,
                Command::ListExpertViews => print_json(&registry.list_expert_dataset_views(500)?)?,
                Command::RouteExpert { request } => {
                    let request: ExpertRouteRequest =
                        serde_json::from_str(&fs::read_to_string(request)?)?;
                    print_json(&cerebellum_app::experts::route_expert(&request)?)?;
                }
                Command::ListExpertAdapters { expert_id } => {
                    print_json(&registry.list_expert_adapters(expert_id.as_deref())?)?
                }
                Command::ReviewExpertAdapter {
                    expert_id,
                    version,
                    action,
                    actor,
                    reason,
                    metrics,
                    eval_report_id,
                } => {
                    let metrics = metrics
                        .map(|path| -> Result<ExpertAdapterMetrics> {
                            Ok(serde_json::from_str::<ExpertAdapterMetrics>(
                                &fs::read_to_string(path)?,
                            )?)
                        })
                        .transpose()?;
                    print_json(&registry.operate_expert_adapter(
                        &expert_id,
                        &version,
                        &action,
                        &ExpertAdapterOperationRequest {
                            actor,
                            reason,
                            metrics,
                            eval_report_id,
                        },
                        chrono::Utc::now(),
                    )?)?;
                }

                Command::QualityAssessments {
                    subject_kind,
                    subject_id,
                    limit,
                } => {
                    let kind = subject_kind
                        .as_deref()
                        .map(parse_quality_subject_kind)
                        .transpose()?;
                    print_json(&registry.list_quality_assessments(
                        kind,
                        subject_id.as_deref(),
                        limit,
                    )?)?;
                }
                Command::QualityModelVersions => {
                    print_json(&registry.list_model_endpoint_versions()?)?;
                }
                Command::ReviewQualityModel {
                    endpoint_version_id,
                    action,
                    actor,
                    reason,
                } => {
                    let request = ReviewQualityModelRequest { actor, reason };
                    let version = match action.as_str() {
                        "approve" => registry.approve_model_endpoint(
                            endpoint_version_id,
                            &request,
                            chrono::Utc::now(),
                        )?,
                        "reject" => registry.reject_model_endpoint(
                            endpoint_version_id,
                            &request,
                            chrono::Utc::now(),
                        )?,
                        _ => anyhow::bail!("quality model action must be approve or reject"),
                    };
                    print_json(&version)?;
                }
                Command::QualityBackfill { limit } => {
                    print_json(
                        &serde_json::json!({"scheduled":registry.enqueue_quality_backfill(limit)?}),
                    )?;
                }
                Command::ListSyntheticCandidates { status, limit } => {
                    let status = status.as_deref().map(parse_synthetic_status).transpose()?;
                    print_json(&registry.list_synthetic_candidates(status, limit)?)?;
                }
                Command::ReviewSyntheticCandidate {
                    candidate_id,
                    action,
                    actor,
                    reason,
                } => {
                    let approve = match action.as_str() {
                        "approve" => true,
                        "reject" => false,
                        _ => anyhow::bail!("synthetic action must be approve or reject"),
                    };
                    print_json(&registry.review_synthetic_candidate(
                        candidate_id,
                        approve,
                        &ReviewSyntheticCandidateRequest {
                            actor,
                            reason,
                            paired_eval_id: None,
                        },
                        chrono::Utc::now(),
                    )?)?;
                }
                Command::Mcp { .. } => unreachable!(),
            }
        }
    }
    Ok(())
}

fn parse_quality_subject_kind(value: &str) -> Result<QualitySubjectKind> {
    Ok(match value {
        "meta_decision" => QualitySubjectKind::MetaDecision,
        "meta_replay" => QualitySubjectKind::MetaReplay,
        "synthetic_candidate" => QualitySubjectKind::SyntheticCandidate,
        "dataset_build" => QualitySubjectKind::DatasetBuild,
        other => anyhow::bail!("unknown quality subject kind: {other}"),
    })
}

fn parse_synthetic_status(value: &str) -> Result<SyntheticCandidateStatus> {
    Ok(match value {
        "quarantined" => SyntheticCandidateStatus::Quarantined,
        "verified" => SyntheticCandidateStatus::Verified,
        "approved" => SyntheticCandidateStatus::Approved,
        "rejected" => SyntheticCandidateStatus::Rejected,
        other => anyhow::bail!("unknown synthetic candidate status: {other}"),
    })
}

fn parse_status(value: &str) -> Result<SkillLifecycle> {
    Ok(match value {
        "quarantined" => SkillLifecycle::Quarantined,
        "validated" => SkillLifecycle::Validated,
        "experimental" => SkillLifecycle::Experimental,
        "trusted" => SkillLifecycle::Trusted,
        "deprecated" => SkillLifecycle::Deprecated,
        "revoked" => SkillLifecycle::Revoked,
        _ => anyhow::bail!("unknown lifecycle status: {value}"),
    })
}

fn print_json(value: &impl Serialize) -> Result<()> {
    serde_json::to_writer_pretty(io::stdout().lock(), value)?;
    io::stdout().write_all(b"\n")?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn ensure_optimization_baseline(
    registry: &Registry,
    skill_id: &str,
    skill_version: &str,
    baseline_file: Option<&PathBuf>,
    source_repository_url: Option<&str>,
    source_commit_sha: Option<&str>,
    source_path: Option<&str>,
    source_license: &str,
) -> Result<()> {
    if let Some(existing) = registry.get_skill(skill_id, skill_version)? {
        if let Some(path) = baseline_file {
            let supplied_hash = registry.put_object(&fs::read(path)?)?;
            if supplied_hash != existing.source.content_hash {
                anyhow::bail!("baseline file does not match the immutable registered Skill");
            }
        }
        return Ok(());
    }
    let path = baseline_file.context(
        "baseline Skill is not registered; pass --baseline-file and immutable source metadata",
    )?;
    let repository_url = source_repository_url.context("--source-repository-url is required")?;
    let commit_sha = source_commit_sha.context("--source-commit-sha is required")?;
    let source_path = source_path.context("--source-path is required")?;
    let content = fs::read(path)?;
    let content_hash = registry.put_object(&content)?;
    let manifest = SkillManifest {
        schema_version: SCHEMA_VERSION.into(),
        id: skill_id.into(),
        version: skill_version.into(),
        description: "Verify completion claims against fresh objective evidence".into(),
        triggers: vec!["verify before completion claim".into()],
        input_schema: serde_json::json!({"type":"object"}),
        output_schema: serde_json::json!({"type":"object"}),
        dependencies: vec![],
        permissions: vec!["read_repository".into(), "run_fixed_tests".into()],
        risk_level: RiskLevel::Low,
        compatibility: vec!["coding-agent".into()],
        source: SourceRef {
            repository_url: repository_url.into(),
            commit_sha: commit_sha.into(),
            path: source_path.into(),
            content_hash,
            license: source_license.into(),
            collected_at: chrono::Utc::now(),
        },
        evidence: EvidenceCard {
            schema_passed: true,
            ..EvidenceCard::default()
        },
        status: SkillLifecycle::Quarantined,
        legacy_hint: None,
        training_eligible: false,
        lineage: None,
    };
    registry.upsert_skill(&manifest, &content)
}

fn export_schemas(dir: &PathBuf) -> Result<()> {
    fs::create_dir_all(dir)?;
    for (name, schema) in schemas::schema_exports()? {
        fs::write(
            dir.join(name),
            format!("{}\n", serde_json::to_string_pretty(&schema)?),
        )?;
    }
    Ok(())
}
