//! Stable protocol types shared by the Cerebellum sidecar and its clients.

mod models;
mod validation;

pub use models::*;
pub use validation::{
    ValidationError, evaluation_gate_passes, paired_bootstrap_ci95_low,
    validate_acquisition_attempt, validate_acquisition_plan, validate_base_model_pin,
    validate_candidate_evaluation, validate_coding_benchmark, validate_create_training_run,
    validate_curriculum, validate_data_quality_assessment, validate_dataset_build,
    validate_dataset_quality_report, validate_dataset_snapshot, validate_document_envelope,
    validate_event_item, validate_experience, validate_expert_adapter_eval_plan,
    validate_expert_adapter_eval_report, validate_expert_adapter_version,
    validate_expert_assignment, validate_expert_dataset_view, validate_expert_taxonomy,
    validate_feedback, validate_holdout_evaluation, validate_knowledge_card,
    validate_learning_decision, validate_meta_canary_decision, validate_meta_decision_trace,
    validate_meta_model_bundle, validate_meta_replay_evaluation, validate_metacognition_decision,
    validate_model_endpoint_version, validate_optimization_budget, validate_optimization_request,
    validate_paired_eval, validate_provider_pricing_policy, validate_qlora_config,
    validate_redaction_attestation, validate_routed_adapter_bundle, validate_skill,
    validate_skill_edit_patch, validate_skillopt_commit, validate_skillopt_provenance,
    validate_source_policy, validate_synthetic_training_candidate, validate_topic_watch,
    validate_tracked_event, validate_training_candidate, validate_workflow,
};

use serde_json::Value;
use sha2::{Digest, Sha256};

/// Return a deterministic SHA-256 digest for arbitrary JSON.
pub fn canonical_json_hash(value: &Value) -> String {
    fn canonical(value: &Value) -> Value {
        match value {
            Value::Object(map) => {
                let mut keys: Vec<_> = map.keys().collect();
                keys.sort();
                let mut result = serde_json::Map::new();
                for key in keys {
                    result.insert(key.clone(), canonical(&map[key]));
                }
                Value::Object(result)
            }
            Value::Array(values) => Value::Array(values.iter().map(canonical).collect()),
            _ => value.clone(),
        }
    }

    let bytes = serde_json::to_vec(&canonical(value)).expect("JSON values are serializable");
    format!("{:x}", Sha256::digest(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use serde_json::json;

    #[test]
    fn canonical_hash_ignores_object_key_order() {
        assert_eq!(
            canonical_json_hash(&json!({"a": 1, "b": {"c": 2}})),
            canonical_json_hash(&json!({"b": {"c": 2}, "a": 1}))
        );
    }

    #[test]
    fn evidence_thresholds_are_explicit() {
        let mut evidence = EvidenceCard {
            schema_passed: true,
            independent_tasks: 10,
            paired_runs: 30,
            task_uplift: Some(0.0),
            ..Default::default()
        };
        assert!(evidence.qualifies_experimental());
        assert!(!evidence.qualifies_trusted());
        evidence.independent_tasks = 50;
        evidence.uplift_ci95_low = Some(0.001);
        assert!(evidence.qualifies_trusted());
        evidence.security_findings.insert("high".into(), 1);
        assert!(!evidence.qualifies_experimental());
    }

    #[test]
    fn recognizable_copyleft_license_is_not_automatically_training_eligible() {
        let source = SourceRef {
            repository_url: "https://github.com/example/project".into(),
            commit_sha: "a".repeat(40),
            path: "skills/example/SKILL.md".into(),
            content_hash: "b".repeat(64),
            license: "GPL-3.0".into(),
            collected_at: Utc::now(),
        };
        assert!(!source.has_training_provenance());
        let mut permissive = source;
        permissive.license = "Apache-2.0".into();
        assert!(permissive.has_training_provenance());
    }
}
