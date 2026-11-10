use anyhow::{Context, Result, bail};
use cerebellum_core::EvidenceCard;
use regex::Regex;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;
use std::sync::LazyLock;

use crate::store::Registry;

pub use cerebellum_core::{MIN_PAIRED_EVALS, MIN_ROUTING_DECISIONS};

pub fn export_training(
    registry: &Registry,
    output: &Path,
    allow_insufficient: bool,
) -> Result<usize> {
    let (decision_count, eval_count) = registry.training_counts()?;
    if !allow_insufficient
        && (decision_count < MIN_ROUTING_DECISIONS || eval_count < MIN_PAIRED_EVALS)
    {
        bail!(
            "training export blocked: {decision_count}/{MIN_ROUTING_DECISIONS} decisions and {eval_count}/{MIN_PAIRED_EVALS} paired evals"
        );
    }
    let (decisions, evals) = registry.training_records()?;
    let file = File::create(output)?;
    let mut writer = BufWriter::new(file);
    let mut count = 0;
    for mut record in decisions.into_iter().chain(evals) {
        let split_key = training_split_key(&record);
        redact(&mut record);
        let digest = Sha256::digest(split_key.as_bytes());
        let split = match digest[0] % 10 {
            0 => "test",
            1 => "validation",
            _ => "train",
        };
        if let Value::Object(map) = &mut record {
            map.insert("split".into(), Value::String(split.into()));
        }
        serde_json::to_writer(&mut writer, &record)?;
        writer.write_all(b"\n")?;
        count += 1;
    }
    writer.flush()?;
    Ok(count)
}

fn training_split_key(record: &Value) -> String {
    let repository = record
        .pointer("/record/repository_digest")
        .and_then(Value::as_str)
        .or_else(|| {
            record
                .pointer("/input/repository_path")
                .and_then(Value::as_str)
        });
    let family = record
        .pointer("/record/task_family")
        .and_then(Value::as_str)
        .or_else(|| {
            record
                .pointer("/input/context/task_family")
                .and_then(Value::as_str)
        })
        .or_else(|| {
            record
                .pointer("/target/selected/workflow_id")
                .and_then(Value::as_str)
        })
        .unwrap_or("unknown");
    match repository {
        // One (repository, family) pair is keyed identically no matter which
        // lineage field carried the value; preferring repository alone used
        // to merge different families of one repository into one group.
        Some(repository) => format!("repository:{repository}\ntask_family:{family}"),
        None => format!("task_family:{family}"),
    }
}

pub fn refresh_skill_evidence(
    registry: &Registry,
    skill_id: &str,
    version: &str,
) -> Result<EvidenceCard> {
    let mut skill = registry
        .get_skill(skill_id, version)?
        .context("skill not found")?;
    let records = registry.paired_evals_for_skill(skill_id, version)?;
    if records.is_empty() {
        bail!("no paired evaluations recorded for {skill_id}@{version}");
    }

    let independent: HashSet<(&str, &str)> = records
        .iter()
        .map(|record| {
            (
                record.task_family.as_str(),
                record.repository_digest.as_str(),
            )
        })
        .collect();
    let deltas: Vec<f64> = records
        .iter()
        .map(|record| record.treatment_score - record.baseline_score)
        .collect();
    let mut latencies: Vec<u64> = records
        .iter()
        .map(|record| record.treatment_latency_ms)
        .collect();
    latencies.sort_unstable();
    let treatment_success = records
        .iter()
        .filter(|record| record.treatment_success)
        .count() as f64
        / records.len() as f64;
    let uplift = deltas.iter().sum::<f64>() / deltas.len() as f64;
    let ci_low = bootstrap_lower_bound(&deltas, 2_000);
    let gate_regressions = records
        .iter()
        .filter(|record| record.treatment_gate_violations > record.baseline_gate_violations)
        .count() as u32;
    let mut findings = skill.evidence.security_findings.clone();
    if gate_regressions > 0 {
        findings.insert("gate_regression".into(), gate_regressions);
    }

    // `records` is non-empty (checked above), so `latencies` is non-empty too.
    let median_latency = if latencies.len() % 2 == 1 {
        latencies[latencies.len() / 2] as f64
    } else {
        (latencies[latencies.len() / 2 - 1] as f64 + latencies[latencies.len() / 2] as f64) / 2.0
    };
    skill.evidence = EvidenceCard {
        schema_passed: skill.evidence.schema_passed,
        security_findings: findings,
        independent_tasks: independent.len() as u32,
        paired_runs: records.len() as u32,
        success_rate: Some(treatment_success),
        task_uplift: Some(uplift),
        uplift_ci95_low: Some(ci_low),
        median_latency_ms: Some(median_latency),
        median_cost: skill.evidence.median_cost,
        redaction_passed: skill.evidence.redaction_passed,
    };
    skill.recompute_training_eligible();
    let content = registry.get_object(&skill.source.content_hash)?;
    registry.upsert_skill(&skill, &content)?;
    Ok(skill.evidence)
}

pub(crate) fn bootstrap_lower_bound(values: &[f64], samples: usize) -> f64 {
    if values.len() == 1 {
        return values[0];
    }
    let mut state = 0x9e3779b97f4a7c15u64 ^ (values.len() as u64);
    let mut means = Vec::with_capacity(samples);
    for _ in 0..samples {
        let mut total = 0.0;
        for _ in 0..values.len() {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            // Lemire mapping over the full 64-bit state: the low bits of this
            // LCG cycle through every residue of power-of-two lengths, which
            // would make every replicate mean identical to the sample mean.
            total += values[(((state as u128) * (values.len() as u128)) >> 64) as usize];
        }
        means.push(total / values.len() as f64);
    }
    means.sort_by(f64::total_cmp);
    means[((samples as f64 * 0.025).floor() as usize).min(samples - 1)]
}

pub(crate) fn redact(value: &mut Value) {
    match value {
        Value::Object(map) => {
            for (key, value) in map.iter_mut() {
                let lower = key.to_ascii_lowercase();
                if ["token", "secret", "password", "api_key", "authorization"]
                    .iter()
                    .any(|needle| lower.contains(needle))
                {
                    *value = Value::String("[REDACTED]".into());
                } else if lower == "repository_path" {
                    let digest = Sha256::digest(value.to_string().as_bytes());
                    *value = Value::String(format!("repo:{:x}", digest));
                } else {
                    redact(value);
                }
            }
        }
        Value::Array(values) => values.iter_mut().for_each(redact),
        Value::String(text) => redact_text(text),
        _ => {}
    }
}

fn redact_text(text: &mut String) {
    static SECRETS: LazyLock<Vec<Regex>> = LazyLock::new(|| {
        [
            r"(?i)bearer\s+[a-z0-9._~+/=-]{12,}",
            r"(?i)gh[pousr]_[a-z0-9]{20,}",
            r"(?i)sk-[a-z0-9_-]{20,}",
            r"(?i)(?:api[_-]?key|password|secret)\s*[:=]\s*[^\s,;]+",
        ]
        .into_iter()
        .map(|pattern| Regex::new(pattern).expect("fixed redaction pattern is valid"))
        .collect()
    });
    static LOCAL_PATHS: LazyLock<Vec<Regex>> = LazyLock::new(|| {
        [r#"(?i)[a-z]:[\\/][^\s"']+"#, r#"/(?:home|users)/[^\s"']+"#]
            .into_iter()
            .map(|pattern| Regex::new(pattern).expect("fixed path pattern is valid"))
            .collect()
    });
    let mut redacted = text.clone();
    for pattern in SECRETS.iter() {
        redacted = pattern.replace_all(&redacted, "[REDACTED]").into_owned();
    }
    for pattern in LOCAL_PATHS.iter() {
        redacted = pattern.replace_all(&redacted, "[LOCAL_PATH]").into_owned();
    }
    *text = redacted;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::builtins;
    use cerebellum_core::{
        CompleteRunRequest, CreateRunRequest, DecisionRequest, DecisionResponse, EvidenceCard,
        PairedEvalRecord, RiskLevel, SkillLifecycle, SkillManifest, SourceRef,
    };
    use chrono::Utc;
    use tempfile::tempdir;
    use uuid::Uuid;

    #[test]
    fn removes_secrets_and_raw_paths() {
        let mut value = serde_json::json!({
            "api_key":"abc",
            "repository_path":"D:/private/repo",
            "task":"debug D:/private/repo/src using Bearer abcdefghijklmnopqrstuvwxyz"
        });
        redact(&mut value);
        assert_eq!(value["api_key"], "[REDACTED]");
        assert!(
            value["repository_path"]
                .as_str()
                .unwrap()
                .starts_with("repo:")
        );
        assert_eq!(value["task"], "debug [LOCAL_PATH] using [REDACTED]");
    }

    #[test]
    fn bootstrap_is_deterministic_and_positive_for_positive_values() {
        let first = bootstrap_lower_bound(&[0.1, 0.2, 0.3, 0.4], 500);
        let second = bootstrap_lower_bound(&[0.1, 0.2, 0.3, 0.4], 500);
        assert_eq!(first, second);
        assert!(first > 0.0);
    }

    fn paired_eval(family: &str, digest: &str, treatment_latency_ms: u64) -> PairedEvalRecord {
        PairedEvalRecord {
            eval_id: Uuid::new_v4(),
            skill_id: "evidence-fixture".into(),
            skill_version: "1.0.0".into(),
            task_family: family.into(),
            repository_digest: digest.into(),
            environment_digest: "e".repeat(64),
            model_id: "model".into(),
            seed: 7,
            budget: Value::Null,
            baseline_success: false,
            treatment_success: true,
            baseline_gate_violations: 0,
            treatment_gate_violations: 0,
            baseline_score: 0.0,
            treatment_score: 1.0,
            baseline_latency_ms: 100,
            treatment_latency_ms,
            metadata: Value::Null,
        }
    }

    fn evidence_fixture_skill(registry: &Registry) {
        let content = b"# evidence fixture\n";
        let manifest = SkillManifest {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            id: "evidence-fixture".into(),
            version: "1.0.0".into(),
            description: "evidence fixture".into(),
            triggers: vec![],
            input_schema: serde_json::json!({"type":"object"}),
            output_schema: serde_json::json!({"type":"object"}),
            dependencies: vec![],
            permissions: vec![],
            risk_level: RiskLevel::Low,
            compatibility: vec![],
            source: SourceRef {
                repository_url: "https://example.com/repo".into(),
                commit_sha: "c".repeat(40),
                path: "skills/evidence/SKILL.md".into(),
                content_hash: format!("{:x}", Sha256::digest(content)),
                license: "NOASSERTION".into(),
                collected_at: Utc::now(),
            },
            evidence: EvidenceCard::default(),
            status: SkillLifecycle::Quarantined,
            legacy_hint: None,
            training_eligible: false,
            lineage: None,
        };
        registry.upsert_skill(&manifest, content).unwrap();
    }

    #[test]
    fn bootstrap_lower_bound_spreads_below_mean_for_alternating_values() {
        // Alternating ±1 with a power-of-two length: low-bit modulo indexing
        // visits every index once per replicate, so every replicate mean
        // equals the sample mean and the CI collapses onto it.
        let values = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0];
        let mean = values.iter().sum::<f64>() / values.len() as f64;
        let ci_low = bootstrap_lower_bound(&values, 2_000);
        assert_eq!(ci_low, bootstrap_lower_bound(&values, 2_000));
        assert!(
            ci_low < mean,
            "ci_low {ci_low} must fall below the sample mean {mean}"
        );
    }

    #[test]
    fn refresh_skill_evidence_averages_even_median_and_counts_tuple_keys() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        evidence_fixture_skill(&registry);
        // Distinct (task_family, repository_digest) tuples count as independent
        // tasks even when the family names share a prefix.
        registry
            .record_paired_eval(&paired_eval("a:b", &"c".repeat(64), 100))
            .unwrap();
        registry
            .record_paired_eval(&paired_eval("a", &"b".repeat(64), 200))
            .unwrap();
        let evidence = refresh_skill_evidence(&registry, "evidence-fixture", "1.0.0").unwrap();
        assert_eq!(evidence.independent_tasks, 2);
        assert_eq!(evidence.median_latency_ms, Some(150.0));
    }

    #[test]
    fn training_split_key_joins_repository_and_task_family() {
        let first = serde_json::json!({
            "input":{"repository_path":"D:/repo","task":"fix one"},
            "target":{"selected":{"workflow_id":"bugfix"}}
        });
        let second = serde_json::json!({
            "input":{"repository_path":"D:/repo","task":"add feature"},
            "target":{"selected":{"workflow_id":"feature"}}
        });
        // Same repository, different families: distinct groups, so one
        // family's records never merge with another family's there.
        assert_ne!(training_split_key(&first), training_split_key(&second));
        assert!(training_split_key(&first).starts_with("repository:D:/repo\ntask_family:bugfix"));
        let repo_less = serde_json::json!({
            "input":{"task":"fix one"},
            "target":{"selected":{"workflow_id":"bugfix"}}
        });
        assert_eq!(training_split_key(&repo_less), "task_family:bugfix");
    }

    #[test]
    fn training_export_is_byte_identical_across_runs() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        builtins::seed(&registry).unwrap();
        evidence_fixture_skill(&registry);
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
        registry
            .complete_run(
                run.id,
                &CompleteRunRequest {
                    outcome: "failure".into(),
                    summary: "still red".into(),
                    metrics: Value::Null,
                    experience: None,
                },
            )
            .unwrap();
        registry
            .record_paired_eval(&paired_eval("fam", &"b".repeat(64), 100))
            .unwrap();

        let first = dir.path().join("first.jsonl");
        let second = dir.path().join("second.jsonl");
        export_training(&registry, &first, true).unwrap();
        export_training(&registry, &second, true).unwrap();
        assert_eq!(
            std::fs::read(&first).unwrap(),
            std::fs::read(&second).unwrap(),
            "two exports of the same records must be byte identical"
        );
    }
}
