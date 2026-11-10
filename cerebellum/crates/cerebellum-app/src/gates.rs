use cerebellum_core::{
    GateDecision, GateEvaluator, GateFailureAction, GateSpec, GateStatus, RunRecord,
};
use chrono::Utc;
use regex::Regex;
use serde_json::Value;
use std::path::{Component, Path};
use tokio::process::Command;
use tokio::time::{Duration, timeout};

pub async fn evaluate_gate(run: &RunRecord, gate: &GateSpec, evidence: &Value) -> GateDecision {
    let result = match &gate.evaluator {
        GateEvaluator::EvidenceBool { key, expected } => {
            match lookup(evidence, key).and_then(Value::as_bool) {
                Some(actual) if actual == *expected => Ok(format!("{key} matched expected value")),
                Some(actual) => Err(format!("{key} was {actual}, expected {expected}")),
                None => Err(format!("missing boolean evidence: {key}")),
            }
        }
        GateEvaluator::CommandExit {
            evidence_key,
            allowed_codes,
        } => match lookup(evidence, evidence_key).and_then(Value::as_i64) {
            Some(code) if allowed_codes.contains(&(code as i32)) => {
                Ok(format!("exit code {code} is allowed"))
            }
            Some(code) => Err(format!("exit code {code} is not allowed")),
            None => Err(format!("missing numeric exit code: {evidence_key}")),
        },
        GateEvaluator::TestReport {
            min_pass_rate,
            max_failed,
        } => {
            let passed = lookup(evidence, "passed").and_then(Value::as_u64);
            let failed = lookup(evidence, "failed").and_then(Value::as_u64);
            match (passed, failed) {
                (Some(passed), Some(failed)) => {
                    let total = passed + failed;
                    let rate = if total == 0 {
                        0.0
                    } else {
                        passed as f64 / total as f64
                    };
                    if failed <= *max_failed as u64 && rate >= *min_pass_rate {
                        Ok(format!(
                            "{passed} passed, {failed} failed, pass rate {rate:.3}"
                        ))
                    } else {
                        Err(format!(
                            "test threshold failed: {passed} passed, {failed} failed, pass rate {rate:.3}"
                        ))
                    }
                }
                _ => Err("missing test evidence fields: passed and failed".into()),
            }
        }
        GateEvaluator::FileExists { path } => check_file_exists(run, path),
        GateEvaluator::GitStatus { allow_dirty } => check_git_status(run, *allow_dirty).await,
        GateEvaluator::DiffConstraint {
            max_files,
            forbidden_patterns,
        } => {
            let changed = evidence.get("changed_files").and_then(Value::as_array);
            match changed {
                None => Err("missing changed_files evidence".into()),
                Some(files) if files.len() > *max_files as usize => Err(format!(
                    "{} changed files exceeds limit {max_files}",
                    files.len()
                )),
                Some(files) => {
                    let patterns: Result<Vec<_>, _> = forbidden_patterns
                        .iter()
                        .map(|pattern| Regex::new(pattern))
                        .collect();
                    match patterns {
                        Err(error) => Err(format!("invalid configured forbidden pattern: {error}")),
                        Ok(patterns) => {
                            let blocked = files
                                .iter()
                                .filter_map(Value::as_str)
                                .find(|file| patterns.iter().any(|pattern| pattern.is_match(file)));
                            blocked.map_or_else(
                                || Ok(format!("{} changed files satisfy constraints", files.len())),
                                |file| Err(format!("forbidden changed path: {file}")),
                            )
                        }
                    }
                }
            }
        }
        GateEvaluator::Permission { permission } => {
            if run.capabilities.iter().any(|value| value == permission) {
                Ok(format!("permission {permission} is present"))
            } else {
                Err(format!("missing permission {permission}"))
            }
        }
        GateEvaluator::Approval { role } => {
            let approved = evidence
                .get("approvals")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(Value::as_str)
                .any(|value| value == role);
            if approved {
                Ok(format!("approval from {role} is present"))
            } else {
                Err(format!("missing approval from {role}"))
            }
        }
    };

    let (status, reason) = match result {
        Ok(reason) => (GateStatus::Pass, reason),
        Err(reason) => (
            match gate.on_failure {
                GateFailureAction::Deny => GateStatus::Deny,
                GateFailureAction::NeedsHuman => GateStatus::NeedsHuman,
            },
            reason,
        ),
    };
    GateDecision {
        run_id: run.id,
        gate_id: gate.id.clone(),
        status,
        reason,
        evaluated_at: Utc::now(),
    }
}

fn lookup<'a>(value: &'a Value, dotted_key: &str) -> Option<&'a Value> {
    dotted_key
        .split('.')
        .try_fold(value, |current, key| current.get(key))
}

fn safe_relative(path: &str) -> Option<&Path> {
    let path = Path::new(path);
    if path.as_os_str().is_empty() || path.is_absolute() {
        return None;
    }
    if path.components().any(|part| {
        matches!(
            part,
            Component::ParentDir | Component::RootDir | Component::Prefix(_)
        )
    }) {
        return None;
    }
    Some(path)
}

fn check_file_exists(run: &RunRecord, configured: &str) -> Result<String, String> {
    let relative = safe_relative(configured)
        .ok_or_else(|| "configured path is not a safe repository-relative path".to_string())?;
    let root = run
        .repository_path
        .as_deref()
        .ok_or_else(|| "run has no repository path".to_string())?;
    let root = Path::new(root)
        .canonicalize()
        .map_err(|error| format!("invalid repository path: {error}"))?;
    let target = root.join(relative);
    if !target.exists() {
        return Err(format!("{} does not exist", target.display()));
    }
    // A symlink inside the repository must not turn this gate into an
    // existence oracle for host paths outside the repository root.
    let resolved = target
        .canonicalize()
        .map_err(|error| format!("invalid target path: {error}"))?;
    if !resolved.starts_with(&root) {
        return Err(format!("{} escapes the repository root", target.display()));
    }
    Ok(format!("{} exists", target.display()))
}

const GIT_STATUS_TIMEOUT: Duration = Duration::from_secs(30);

/// Spawn a status command and wait for its output with a hard deadline.
///
/// `kill_on_drop` makes the timeout path terminate the subprocess when the
/// output future is dropped, so a hung child never outlives the wait.
async fn run_status_command(
    command: &mut Command,
    deadline: Duration,
) -> Result<std::process::Output, String> {
    command.kill_on_drop(true);
    match timeout(deadline, command.output()).await {
        Ok(result) => result.map_err(|error| format!("failed to inspect git status: {error}")),
        Err(_) => Err(format!("git status timed out after {deadline:?}")),
    }
}

async fn check_git_status(run: &RunRecord, allow_dirty: bool) -> Result<String, String> {
    let root = run
        .repository_path
        .as_deref()
        .ok_or_else(|| "run has no repository path".to_string())?;
    let output = run_status_command(
        Command::new("git")
            .args(["status", "--porcelain=v1"])
            .current_dir(root),
        GIT_STATUS_TIMEOUT,
    )
    .await?;
    if !output.status.success() {
        return Err("git status failed".into());
    }
    let dirty = !output.stdout.is_empty();
    if dirty && !allow_dirty {
        Err("working tree is dirty".into())
    } else {
        Ok(if dirty {
            "working tree is dirty but allowed".into()
        } else {
            "working tree is clean".into()
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cerebellum_core::{GateFailureAction, GateSpec};
    use chrono::Utc;
    use uuid::Uuid;

    fn run() -> RunRecord {
        RunRecord {
            id: Uuid::new_v4(),
            decision_id: Uuid::new_v4(),
            workflow_id: "x".into(),
            workflow_version: "1.0.0".into(),
            repository_path: None,
            capabilities: vec![],
            status: "running".into(),
            created_at: Utc::now(),
        }
    }

    #[tokio::test]
    async fn missing_test_evidence_fails_closed() {
        let gate = GateSpec {
            id: "test".into(),
            description: "".into(),
            stage: "post".into(),
            mandatory: true,
            evaluator: GateEvaluator::TestReport {
                min_pass_rate: 1.0,
                max_failed: 0,
            },
            on_failure: GateFailureAction::Deny,
        };
        assert_eq!(
            evaluate_gate(&run(), &gate, &serde_json::json!({}))
                .await
                .status,
            GateStatus::Deny
        );
    }

    #[tokio::test]
    async fn path_traversal_is_rejected() {
        assert!(safe_relative("../secret").is_none());
        assert!(safe_relative("/root").is_none());
    }
    fn gate(evaluator: GateEvaluator, on_failure: GateFailureAction) -> GateSpec {
        GateSpec {
            id: "g".into(),
            description: "".into(),
            stage: "post".into(),
            mandatory: true,
            evaluator,
            on_failure,
        }
    }

    #[tokio::test]
    async fn evidence_bool_matches_mismatches_and_missing() {
        let g = gate(
            GateEvaluator::EvidenceBool {
                key: "build.green".into(),
                expected: true,
            },
            GateFailureAction::Deny,
        );
        let r = run();
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"build":{"green":true}}))
                .await
                .status,
            GateStatus::Pass
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"build":{"green":false}}))
                .await
                .status,
            GateStatus::Deny
        );
        // Missing evidence and wrong JSON types both fail closed.
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"build":{"green":"yes"}}))
                .await
                .status,
            GateStatus::Deny
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
            GateStatus::Deny
        );
    }

    #[tokio::test]
    async fn command_exit_respects_allowed_codes() {
        let g = gate(
            GateEvaluator::CommandExit {
                evidence_key: "exit".into(),
                allowed_codes: vec![0, 2],
            },
            GateFailureAction::NeedsHuman,
        );
        let r = run();
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"exit": 2}))
                .await
                .status,
            GateStatus::Pass
        );
        // on_failure=NeedsHuman maps failures to NeedsHuman, not Deny.
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"exit": 1}))
                .await
                .status,
            GateStatus::NeedsHuman
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
            GateStatus::NeedsHuman
        );
    }

    #[tokio::test]
    async fn test_report_enforces_both_thresholds() {
        let g = gate(
            GateEvaluator::TestReport {
                min_pass_rate: 0.8,
                max_failed: 1,
            },
            GateFailureAction::Deny,
        );
        let r = run();
        // 4/5 pass with 1 failure: rate and count both at the boundary.
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"passed":4,"failed":1}))
                .await
                .status,
            GateStatus::Pass
        );
        // Rate high enough but too many failures.
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"passed":10,"failed":2}))
                .await
                .status,
            GateStatus::Deny
        );
        // Zero tests ran: pass rate is 0.0, not a pass.
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"passed":0,"failed":0}))
                .await
                .status,
            GateStatus::Deny
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"passed":3}))
                .await
                .status,
            GateStatus::Deny
        );
    }

    #[tokio::test]
    async fn diff_constraint_enforces_limits_and_forbidden_paths() {
        let g = gate(
            GateEvaluator::DiffConstraint {
                max_files: 2,
                forbidden_patterns: vec!["^secrets/".into(), "\\.env$".into()],
            },
            GateFailureAction::Deny,
        );
        let r = run();
        assert_eq!(
            evaluate_gate(
                &r,
                &g,
                &serde_json::json!({"changed_files":["a.rs","b.rs"]})
            )
            .await
            .status,
            GateStatus::Pass
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"changed_files":["a","b","c"]}))
                .await
                .status,
            GateStatus::Deny
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"changed_files":["src/.env"]}))
                .await
                .status,
            GateStatus::Deny
        );
        assert_eq!(
            evaluate_gate(
                &r,
                &g,
                &serde_json::json!({"changed_files":["secrets/key.pem"]})
            )
            .await
            .status,
            GateStatus::Deny
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
            GateStatus::Deny
        );
    }

    #[tokio::test]
    async fn invalid_forbidden_pattern_fails_closed() {
        let g = gate(
            GateEvaluator::DiffConstraint {
                max_files: 10,
                forbidden_patterns: vec!["([".into()],
            },
            GateFailureAction::Deny,
        );
        let decision =
            evaluate_gate(&run(), &g, &serde_json::json!({"changed_files":["a.rs"]})).await;
        assert_eq!(decision.status, GateStatus::Deny);
        assert!(
            decision
                .reason
                .contains("invalid configured forbidden pattern")
        );
    }

    #[tokio::test]
    async fn permission_requires_exact_capability() {
        let g = gate(
            GateEvaluator::Permission {
                permission: "fs:write".into(),
            },
            GateFailureAction::Deny,
        );
        let mut r = run();
        r.capabilities = vec!["fs:read".into()];
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
            GateStatus::Deny
        );
        r.capabilities.push("fs:write".into());
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
            GateStatus::Pass
        );
    }

    #[tokio::test]
    async fn approval_requires_the_named_role() {
        let g = gate(
            GateEvaluator::Approval {
                role: "security".into(),
            },
            GateFailureAction::NeedsHuman,
        );
        let r = run();
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"approvals":["qa"]}))
                .await
                .status,
            GateStatus::NeedsHuman
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"approvals":["qa","security"]}))
                .await
                .status,
            GateStatus::Pass
        );
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({"approvals":"security"}))
                .await
                .status,
            GateStatus::NeedsHuman
        );
    }

    #[tokio::test]
    async fn file_exists_gate_respects_repository_boundary() {
        let directory = std::env::temp_dir().join(format!("cerebellum-gate-{}", Uuid::new_v4()));
        std::fs::create_dir_all(directory.join("src")).unwrap();
        std::fs::write(directory.join("src/lib.rs"), "fn main() {}").unwrap();
        let mut r = run();
        r.repository_path = Some(directory.to_string_lossy().into_owned());

        let exists = gate(
            GateEvaluator::FileExists {
                path: "src/lib.rs".into(),
            },
            GateFailureAction::Deny,
        );
        assert_eq!(
            evaluate_gate(&r, &exists, &serde_json::json!({}))
                .await
                .status,
            GateStatus::Pass
        );

        let missing = gate(
            GateEvaluator::FileExists {
                path: "src/nope.rs".into(),
            },
            GateFailureAction::Deny,
        );
        assert_eq!(
            evaluate_gate(&r, &missing, &serde_json::json!({}))
                .await
                .status,
            GateStatus::Deny
        );

        for escape in ["../outside.txt", "src/../../outside.txt", "/etc/passwd", ""] {
            let g = gate(
                GateEvaluator::FileExists {
                    path: escape.into(),
                },
                GateFailureAction::Deny,
            );
            assert_eq!(
                evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
                GateStatus::Deny,
                "escape path accepted: {escape}"
            );
        }
        std::fs::remove_dir_all(&directory).ok();
    }

    #[tokio::test]
    async fn file_exists_without_repository_path_fails_closed() {
        let g = gate(
            GateEvaluator::FileExists {
                path: "src/lib.rs".into(),
            },
            GateFailureAction::Deny,
        );
        let decision = evaluate_gate(&run(), &g, &serde_json::json!({})).await;
        assert_eq!(decision.status, GateStatus::Deny);
        assert!(decision.reason.contains("no repository path"));
    }

    #[tokio::test]
    async fn git_status_fails_closed_outside_a_repository() {
        let directory = std::env::temp_dir().join(format!("cerebellum-gate-{}", Uuid::new_v4()));
        std::fs::create_dir_all(&directory).unwrap();
        let mut r = run();
        r.repository_path = Some(directory.to_string_lossy().into_owned());
        let g = gate(
            GateEvaluator::GitStatus { allow_dirty: true },
            GateFailureAction::Deny,
        );
        // Not a git repository: the gate must not pass.
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
            GateStatus::Deny
        );
        r.repository_path = None;
        assert_eq!(
            evaluate_gate(&r, &g, &serde_json::json!({})).await.status,
            GateStatus::Deny
        );
        std::fs::remove_dir_all(&directory).ok();
    }

    #[tokio::test]
    async fn git_status_enforces_clean_tree() {
        let directory = std::env::temp_dir().join(format!("cerebellum-gate-{}", Uuid::new_v4()));
        std::fs::create_dir_all(&directory).unwrap();
        let init = std::process::Command::new("git")
            .args(["init", "-q"])
            .current_dir(&directory)
            .output();
        if !init.map(|o| o.status.success()).unwrap_or(false) {
            // git unavailable in this environment; skip rather than fail.
            std::fs::remove_dir_all(&directory).ok();
            return;
        }
        std::fs::write(directory.join("dirty.txt"), "x").unwrap();
        let mut r = run();

        r.repository_path = Some(directory.to_string_lossy().into_owned());
        let strict = gate(
            GateEvaluator::GitStatus { allow_dirty: false },
            GateFailureAction::Deny,
        );
        assert_eq!(
            evaluate_gate(&r, &strict, &serde_json::json!({}))
                .await
                .status,
            GateStatus::Deny
        );
        let lenient = gate(
            GateEvaluator::GitStatus { allow_dirty: true },
            GateFailureAction::Deny,
        );
        assert_eq!(
            evaluate_gate(&r, &lenient, &serde_json::json!({}))
                .await
                .status,
            GateStatus::Pass
        );
        std::fs::remove_dir_all(&directory).ok();
    }

    #[tokio::test]
    async fn status_command_times_out_instead_of_hanging() {
        // A subprocess that sleeps far beyond the deadline must be killed and
        // surface as a "timed out" failure, never as a pass or a hang.
        #[cfg(windows)]
        let mut command = {
            let mut c = Command::new("cmd");
            c.args(["/c", "ping", "-n", "30", "127.0.0.1", ">nul"]);
            c
        };
        #[cfg(not(windows))]
        let mut command = {
            let mut c = Command::new("sleep");
            c.arg("30");
            c
        };
        let started = std::time::Instant::now();
        let result = run_status_command(&mut command, Duration::from_millis(200)).await;
        assert!(
            matches!(&result, Err(error) if error.contains("timed out")),
            "expected timeout failure, got {result:?}"
        );
        assert!(
            started.elapsed() < Duration::from_secs(5),
            "deadline not enforced: {:?}",
            started.elapsed()
        );
    }

    #[tokio::test]
    async fn status_command_reports_spawn_failure() {
        let mut command = Command::new("cerebellum-definitely-not-a-binary-xyz");
        let result = run_status_command(&mut command, Duration::from_secs(1)).await;
        assert!(
            matches!(&result, Err(error) if error.contains("failed to inspect git status")),
            "expected spawn failure, got {result:?}"
        );
    }
}
