use anyhow::Result;
use cerebellum_app::{Registry, builtins, gates::evaluate_gate, permit::PermitSigner};
use cerebellum_core::{
    ActionPermit, CreateRunRequest, DecisionRequest, DecisionResponse, EvidenceCard, GateDecision,
    GateEvaluator, GateFailureAction, GateSpec, GateStatus, RankedWorkflow, RiskLevel, RunRecord,
    SCHEMA_VERSION, SkillLifecycle, SkillManifest, SourceRef, canonical_json_hash,
};
use chrono::{DateTime, Duration as ChronoDuration, Utc};
use sha2::{Digest, Sha256};
use std::time::{Duration, Instant};
use tempfile::tempdir;
use uuid::Uuid;

fn main() -> Result<()> {
    let dir = tempdir()?;
    let registry = Registry::open(dir.path())?;
    builtins::seed(&registry)?;
    let content = b"# benchmark\n\nSynthetic benchmark fixture.\n";
    let content_hash = format!("{:x}", Sha256::digest(content));
    let collected_at = DateTime::parse_from_rfc3339("2026-08-22T00:00:00Z")?.with_timezone(&Utc);

    let seed_started = Instant::now();
    for index in 0..10_000 {
        let manifest = SkillManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: format!("benchmark.skill-{index:05}"),
            version: "1.0.0".into(),
            description: format!("Synthetic benchmark Skill number {index}"),
            triggers: vec![format!("benchmark-{index}")],
            input_schema: serde_json::json!({"type":"object"}),
            output_schema: serde_json::json!({"type":"object"}),
            dependencies: vec![],
            permissions: vec![],
            risk_level: RiskLevel::ReadOnly,
            compatibility: vec!["benchmark".into()],
            source: SourceRef {
                repository_url: "builtin://benchmark".into(),
                commit_sha: "benchmark".into(),
                path: format!("skills/{index}"),
                content_hash: content_hash.clone(),
                license: "MIT".into(),
                collected_at,
            },
            evidence: EvidenceCard {
                schema_passed: true,
                ..Default::default()
            },
            status: SkillLifecycle::Validated,
            legacy_hint: None,
            training_eligible: false,
            lineage: None,
        };
        registry.upsert_skill(&manifest, content)?;
    }
    let seed_elapsed = seed_started.elapsed();

    let mut samples = Vec::with_capacity(250);
    for index in 0..250 {
        let query = format!("skill-{:05}", index * 39 % 10_000);
        let started = Instant::now();
        let result = registry.search_skills(Some(&query), false, 10)?;
        samples.push(started.elapsed());
        assert_eq!(result.len(), 1);
    }
    samples.sort_unstable();
    let p95 = samples[samples.len() * 95 / 100];
    println!(
        "skills=10000 seed_ms={} query_p95_ms={:.3}",
        seed_elapsed.as_millis(),
        p95.as_secs_f64() * 1000.0
    );
    if p95 > Duration::from_millis(50) {
        anyhow::bail!("Registry query p95 exceeded 50 ms: {p95:?}");
    }

    let run = RunRecord {
        id: Uuid::new_v4(),
        decision_id: Uuid::new_v4(),
        workflow_id: "benchmark".into(),
        workflow_version: "1.0.0".into(),
        repository_path: None,
        capabilities: vec![],
        status: "running".into(),
        created_at: Utc::now(),
    };
    let gate = GateSpec {
        id: "benchmark".into(),
        description: "In-process deterministic gate benchmark".into(),
        stage: "pre".into(),
        mandatory: true,
        evaluator: GateEvaluator::EvidenceBool {
            key: "ready".into(),
            expected: true,
        },
        on_failure: GateFailureAction::Deny,
    };
    let evidence = serde_json::json!({"ready":true});
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?;
    let mut gate_samples = Vec::with_capacity(10_000);
    for _ in 0..10_000 {
        let started = Instant::now();
        let decision = runtime.block_on(evaluate_gate(&run, &gate, &evidence));
        gate_samples.push(started.elapsed());
        assert_eq!(decision.status, cerebellum_core::GateStatus::Pass);
    }
    gate_samples.sort_unstable();
    let gate_p95 = gate_samples[gate_samples.len() * 95 / 100];
    println!("gate_p95_ms={:.3}", gate_p95.as_secs_f64() * 1000.0);
    if gate_p95 > Duration::from_millis(20) {
        anyhow::bail!("Gate evaluation p95 exceeded 20 ms: {gate_p95:?}");
    }

    let decision_id = Uuid::new_v4();
    let decision_request = DecisionRequest {
        task: "benchmark authorization".into(),
        repository_path: None,
        capabilities: vec![],
        context: serde_json::Value::Null,
    };
    let decision_response = DecisionResponse {
        decision_id,
        selected: RankedWorkflow {
            workflow_id: "bugfix".into(),
            version: "1.0.0".into(),
            score: 1.0,
            reasons: vec!["benchmark fixture".into()],
        },
        alternatives: vec![],
        router: "benchmark".into(),
        fallback_used: false,
        registry_snapshot: registry.registry_snapshot()?,
        memory_context: vec![],
        knowledge_context: vec![],
        environment: None,
        acquisition_requested: false,
    };
    registry.save_decision(&decision_request, &decision_response)?;
    let authorization_run = registry.create_run(&CreateRunRequest {
        decision_id,
        workflow_id: "bugfix".into(),
        workflow_version: "1.0.0".into(),
        repository_path: None,
        capabilities: vec![],
    })?;
    let workflow = registry
        .get_workflow("bugfix", "1.0.0")?
        .expect("built-in workflow exists");
    for gate in &workflow.gates {
        registry.save_gate_decision(
            &GateDecision {
                run_id: authorization_run.id,
                gate_id: gate.id.clone(),
                status: GateStatus::Pass,
                reason: "benchmark fixture".into(),
                evaluated_at: Utc::now(),
            },
            &serde_json::json!({"benchmark":true}),
        )?;
    }
    let signer = PermitSigner::new(vec![42; 32])?;
    let action = serde_json::json!({"tool":"write_file","path":"src/lib.rs"});
    let mut authorization_samples = Vec::with_capacity(1_000);
    for _ in 0..1_000 {
        let started = Instant::now();
        let stored_run = registry
            .get_run(authorization_run.id)?
            .expect("benchmark run exists");
        let stored_workflow = registry
            .get_workflow(&stored_run.workflow_id, &stored_run.workflow_version)?
            .expect("benchmark workflow exists");
        assert!(
            registry
                .mandatory_gates_passed(&stored_run, &stored_workflow)?
                .is_empty()
        );
        let now = Utc::now();
        let permit = ActionPermit {
            permit_id: Uuid::new_v4(),
            run_id: stored_run.id,
            workflow_id: stored_run.workflow_id,
            workflow_version: stored_run.workflow_version,
            action_hash: canonical_json_hash(&action),
            issued_at: now,
            expires_at: now + ChronoDuration::seconds(60),
        };
        let _token = signer.sign(&permit)?;
        registry.save_permit(&permit)?;
        authorization_samples.push(started.elapsed());
    }
    authorization_samples.sort_unstable();
    let authorization_p95 = authorization_samples[authorization_samples.len() * 95 / 100];
    println!(
        "authorization_p95_ms={:.3}",
        authorization_p95.as_secs_f64() * 1000.0
    );
    if authorization_p95 > Duration::from_millis(20) {
        anyhow::bail!("Authorization p95 exceeded 20 ms: {authorization_p95:?}");
    }
    Ok(())
}
