use anyhow::Result;
use cerebellum_core::*;
use chrono::{DateTime, Utc};
use sha2::{Digest, Sha256};

use crate::store::Registry;

type BuiltinSkill = (
    &'static str,
    &'static str,
    Vec<&'static str>,
    Vec<&'static str>,
    RiskLevel,
);

pub fn seed(registry: &Registry) -> Result<()> {
    for (id, description, triggers, permissions, risk) in builtin_skills() {
        let content = format!("# {id}\n\n{description}\n");
        let hash = format!("{:x}", Sha256::digest(content.as_bytes()));
        let mut manifest = SkillManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: id.into(),
            version: "1.0.0".into(),
            description: description.into(),
            triggers: triggers.into_iter().map(str::to_owned).collect(),
            input_schema: serde_json::json!({"type":"object"}),
            output_schema: serde_json::json!({"type":"object"}),
            dependencies: vec![],
            permissions: permissions.into_iter().map(str::to_owned).collect(),
            risk_level: risk,
            compatibility: vec!["coding-agent".into()],
            source: SourceRef {
                repository_url: "builtin://cerebellum".into(),
                commit_sha: "builtin-0.1.0".into(),
                path: format!("builtins/{id}"),
                content_hash: hash,
                license: "MIT OR Apache-2.0".into(),
                collected_at: builtin_timestamp(),
            },
            evidence: EvidenceCard {
                schema_passed: true,
                security_findings: Default::default(),
                independent_tasks: 50,
                paired_runs: 150,
                success_rate: Some(1.0),
                task_uplift: Some(1.0),
                uplift_ci95_low: Some(0.01),
                median_latency_ms: Some(0.0),
                median_cost: Some(0.0),
                redaction_passed: true,
            },
            status: SkillLifecycle::Trusted,
            legacy_hint: None,
            training_eligible: false,
            lineage: None,
        };
        manifest.recompute_training_eligible();
        registry.upsert_skill(&manifest, content.as_bytes())?;
    }
    for workflow in workflows() {
        registry.upsert_workflow(&workflow)?;
    }
    seed_source_policies(registry)?;
    Ok(())
}

/// Default technical SourcePolicy seeds: paper collectors (OpenAlex, arXiv),
/// engineering RSS/Atom feeds, and the HackerNews updates feed. All public,
/// all `enabled=false` — an administrator enables each source explicitly
/// (fail-closed tradition), and no training license is granted by default.
fn seed_source_policies(registry: &Registry) -> Result<()> {
    let existing: std::collections::HashSet<String> = registry
        .list_source_policies(false)?
        .into_iter()
        .map(|policy| policy.name)
        .collect();
    for (name, kind, base_url, domains) in default_source_seeds() {
        if existing.contains(name) {
            continue;
        }
        registry.create_source_policy(&CreateSourcePolicyRequest {
            name: name.into(),
            kind,
            base_url: base_url.into(),
            access_mode: SourceAccessMode::Public,
            allowed_domains: domains.iter().map(|domain| domain.to_string()).collect(),
            obey_robots: true,
            max_depth: 1,
            max_pages_per_run: 50,
            rate_limit_per_minute: 10,
            raw_retention_days: 30,
            training_license: None,
            model_terms_allow_training: false,
            auth_secret_ref: None,
            enabled: false,
            data_classification: DataClassification::Public,
            external_processing: ExternalProcessingPermission::Redacted,
        })?;
    }
    Ok(())
}

fn default_source_seeds() -> Vec<(&'static str, SourceKind, &'static str, Vec<&'static str>)> {
    vec![
        (
            "OpenAlex 最新论文",
            SourceKind::OpenAlex,
            "https://api.openalex.org/works",
            vec!["api.openalex.org", "openalex.org", "doi.org"],
        ),
        (
            "arXiv 最新预印本",
            SourceKind::Arxiv,
            "https://export.arxiv.org/api/query",
            vec!["export.arxiv.org", "arxiv.org"],
        ),
        (
            "Cloudflare 工程博客",
            SourceKind::RssAtom,
            "https://blog.cloudflare.com/rss/",
            vec![],
        ),
        (
            "GitHub 官方博客",
            SourceKind::RssAtom,
            "https://github.blog/feed/",
            vec![],
        ),
        (
            "Netflix 技术博客",
            SourceKind::RssAtom,
            "https://netflixtechblog.com/feed",
            vec![],
        ),
        (
            "Meta 工程博客",
            SourceKind::RssAtom,
            "https://engineering.fb.com/feed/",
            vec![],
        ),
        (
            "Rust 官方博客",
            SourceKind::RssAtom,
            "https://blog.rust-lang.org/feed.xml",
            vec![],
        ),
        (
            "Go 官方博客",
            SourceKind::RssAtom,
            "https://go.dev/blog/feed.atom",
            vec![],
        ),
        (
            "Kubernetes 官方博客",
            SourceKind::RssAtom,
            "https://kubernetes.io/feed.xml",
            vec![],
        ),
        (
            "Microsoft 开发者博客",
            SourceKind::RssAtom,
            "https://devblogs.microsoft.com/feed/",
            vec![],
        ),
        (
            "HackerNews 技术动态",
            SourceKind::HackerNews,
            "https://hacker-news.firebaseio.com",
            vec![],
        ),
    ]
}

fn builtin_timestamp() -> DateTime<Utc> {
    DateTime::parse_from_rfc3339("2026-08-22T00:00:00Z")
        .expect("fixed built-in timestamp is valid")
        .with_timezone(&Utc)
}

fn builtin_skills() -> Vec<BuiltinSkill> {
    vec![
        (
            "builtin.inspect-repository",
            "Inspect repository state without mutation.",
            vec!["inspect", "recon", "analyze", "检查", "分析"],
            vec!["fs.read", "git.read"],
            RiskLevel::ReadOnly,
        ),
        (
            "builtin.plan-change",
            "Create a bounded implementation plan.",
            vec!["plan", "feature", "方案", "功能"],
            vec!["fs.read"],
            RiskLevel::ReadOnly,
        ),
        (
            "builtin.implement-change",
            "Apply a scoped code change.",
            vec!["implement", "fix", "refactor", "实现", "修复", "重构"],
            vec!["fs.write", "process.exec"],
            RiskLevel::High,
        ),
        (
            "builtin.run-tests",
            "Run relevant automated checks and capture structured results.",
            vec!["test", "verify", "测试", "验证"],
            vec!["process.exec"],
            RiskLevel::Medium,
        ),
        (
            "builtin.review-diff",
            "Review a code diff for correctness, scope and maintainability.",
            vec!["review", "diff", "审查"],
            vec!["fs.read", "git.read"],
            RiskLevel::ReadOnly,
        ),
        (
            "builtin.security-review",
            "Inspect changes for security-sensitive behavior.",
            vec!["security", "permission", "auth", "安全", "权限"],
            vec!["fs.read", "git.read"],
            RiskLevel::ReadOnly,
        ),
    ]
}

fn node(id: &str, skill_id: &str) -> WorkflowNode {
    WorkflowNode {
        id: id.into(),
        skill_id: skill_id.into(),
        version_req: "^1.0".into(),
        required: true,
    }
}

fn edge(from: &str, to: &str) -> WorkflowEdge {
    WorkflowEdge {
        from: from.into(),
        to: to.into(),
        condition: None,
    }
}

fn bool_gate(id: &str, description: &str, key: &str, on_failure: GateFailureAction) -> GateSpec {
    GateSpec {
        id: id.into(),
        description: description.into(),
        stage: "post".into(),
        mandatory: true,
        evaluator: GateEvaluator::EvidenceBool {
            key: key.into(),
            expected: true,
        },
        on_failure,
    }
}

pub fn workflows() -> Vec<WorkflowManifest> {
    let inspect = node("inspect", "builtin.inspect-repository");
    let plan = node("plan", "builtin.plan-change");
    let implement = node("implement", "builtin.implement-change");
    let test = node("test", "builtin.run-tests");
    let review = node("review", "builtin.review-diff");
    let security = node("security", "builtin.security-review");

    vec![
        WorkflowManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: "bugfix".into(),
            version: "1.0.0".into(),
            description: "Reproduce, fix and verify an observable software defect.".into(),
            task_classes: vec!["bugfix".into()],
            triggers: vec![
                "bug".into(),
                "fix".into(),
                "error".into(),
                "failure".into(),
                "修复".into(),
                "报错".into(),
            ],
            risk_level: RiskLevel::High,
            nodes: vec![
                inspect.clone(),
                plan.clone(),
                implement.clone(),
                test.clone(),
                review.clone(),
            ],
            edges: vec![
                edge("inspect", "plan"),
                edge("plan", "implement"),
                edge("implement", "test"),
                edge("test", "review"),
            ],
            gates: vec![
                GateSpec {
                    id: "tests-pass".into(),
                    description: "Relevant tests must pass.".into(),
                    stage: "post".into(),
                    mandatory: true,
                    evaluator: GateEvaluator::TestReport {
                        min_pass_rate: 1.0,
                        max_failed: 0,
                    },
                    on_failure: GateFailureAction::Deny,
                },
                bool_gate(
                    "review-complete",
                    "Diff review must complete.",
                    "review_complete",
                    GateFailureAction::Deny,
                ),
            ],
            on_failure: GateFailureAction::Deny,
            lineage: None,
        },
        WorkflowManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: "feature".into(),
            version: "1.0.0".into(),
            description: "Design, implement, test and review a new behavior.".into(),
            task_classes: vec!["feature".into()],
            triggers: vec![
                "feature".into(),
                "implement".into(),
                "add".into(),
                "build".into(),
                "功能".into(),
                "实现".into(),
                "新增".into(),
            ],
            risk_level: RiskLevel::High,
            nodes: vec![
                inspect.clone(),
                plan.clone(),
                implement.clone(),
                test.clone(),
                review.clone(),
            ],
            edges: vec![
                edge("inspect", "plan"),
                edge("plan", "implement"),
                edge("implement", "test"),
                edge("test", "review"),
            ],
            gates: vec![
                bool_gate(
                    "spec-present",
                    "A bounded specification is required.",
                    "spec_present",
                    GateFailureAction::NeedsHuman,
                ),
                GateSpec {
                    id: "tests-pass".into(),
                    description: "Relevant tests must pass.".into(),
                    stage: "post".into(),
                    mandatory: true,
                    evaluator: GateEvaluator::TestReport {
                        min_pass_rate: 1.0,
                        max_failed: 0,
                    },
                    on_failure: GateFailureAction::Deny,
                },
                bool_gate(
                    "review-complete",
                    "Diff review must complete.",
                    "review_complete",
                    GateFailureAction::Deny,
                ),
            ],
            on_failure: GateFailureAction::Deny,
            lineage: None,
        },
        WorkflowManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: "code-review".into(),
            version: "1.0.0".into(),
            description: "Inspect a proposed change and report actionable findings.".into(),
            task_classes: vec!["code-review".into()],
            triggers: vec![
                "review".into(),
                "audit".into(),
                "pull request".into(),
                "审查".into(),
                "评审".into(),
            ],
            risk_level: RiskLevel::ReadOnly,
            nodes: vec![inspect.clone(), review.clone(), security.clone()],
            edges: vec![edge("inspect", "review"), edge("review", "security")],
            gates: vec![bool_gate(
                "review-complete",
                "Review output must be complete.",
                "review_complete",
                GateFailureAction::Deny,
            )],
            on_failure: GateFailureAction::Deny,
            lineage: None,
        },
        WorkflowManifest {
            schema_version: SCHEMA_VERSION.into(),
            id: "pre-merge".into(),
            version: "1.0.0".into(),
            description: "Verify tests, review and security evidence before merge or release."
                .into(),
            task_classes: vec!["pre-merge".into()],
            triggers: vec![
                "merge".into(),
                "ship".into(),
                "release".into(),
                "pre-merge".into(),
                "合并".into(),
                "发布".into(),
            ],
            risk_level: RiskLevel::Critical,
            nodes: vec![inspect, test, review, security],
            edges: vec![
                edge("inspect", "test"),
                edge("test", "review"),
                edge("review", "security"),
            ],
            gates: vec![
                GateSpec {
                    id: "tests-pass".into(),
                    description: "Full required suite must pass.".into(),
                    stage: "pre-merge".into(),
                    mandatory: true,
                    evaluator: GateEvaluator::TestReport {
                        min_pass_rate: 1.0,
                        max_failed: 0,
                    },
                    on_failure: GateFailureAction::Deny,
                },
                bool_gate(
                    "review-complete",
                    "Diff review must complete.",
                    "review_complete",
                    GateFailureAction::Deny,
                ),
                bool_gate(
                    "security-clear",
                    "Security review must be clear.",
                    "security_clear",
                    GateFailureAction::NeedsHuman,
                ),
            ],
            on_failure: GateFailureAction::Deny,
            lineage: None,
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn builtin_workflows_pass_structural_validation() {
        // Structural errors (dangling edge ids, duplicate nodes/gates, cycles)
        // must surface here, not at runtime when a workflow is first executed.
        for workflow in workflows() {
            validate_workflow(&workflow).unwrap_or_else(|error| {
                panic!("builtin workflow {} is invalid: {error}", workflow.id)
            });
        }
    }

    #[test]
    fn source_seeds_are_technical_and_fail_closed() {
        // The seed set has pivoted away from entertainment hot boards to
        // technical sources: papers, engineering blogs, and HackerNews.
        let seeds = default_source_seeds();
        let banned = [
            SourceKind::Weibo,
            SourceKind::Zhihu,
            SourceKind::Douyin,
            SourceKind::Bilibili,
            SourceKind::Xhs,
            SourceKind::Baidu,
            SourceKind::Kuaishou,
            SourceKind::Tieba,
        ];
        for (name, kind, base_url, _) in &seeds {
            assert!(
                !banned.contains(kind),
                "seed {name} uses an entertainment board kind {kind:?}"
            );
            assert!(
                base_url.starts_with("https://"),
                "seed {name} must use https, got {base_url}"
            );
        }
        let kinds: Vec<SourceKind> = seeds.iter().map(|(_, kind, _, _)| *kind).collect();
        for required in [
            SourceKind::Arxiv,
            SourceKind::OpenAlex,
            SourceKind::HackerNews,
        ] {
            assert!(
                kinds.contains(&required),
                "seed set is missing {required:?}"
            );
        }
        assert!(
            kinds
                .iter()
                .filter(|kind| **kind == SourceKind::RssAtom)
                .count()
                >= 8,
            "expected at least 8 engineering RSS/Atom feeds"
        );

        // Fail-closed: seeding into a fresh registry must leave every policy
        // disabled and without a training license.
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        seed(&registry).unwrap();
        let policies = registry.list_source_policies(false).unwrap();
        assert_eq!(policies.len(), seeds.len());
        for policy in &policies {
            assert!(
                !policy.enabled,
                "seeded policy {} must be disabled",
                policy.name
            );
            assert!(
                policy.training_license.is_none(),
                "seeded policy {} must have no training license",
                policy.name
            );
        }
    }
}
