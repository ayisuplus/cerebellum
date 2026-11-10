use anyhow::{Context, Result, bail};
use cerebellum_core::{
    PairedEvalRecord, PairedSandboxPlan, SandboxCommand, SandboxResult, canonical_json_hash,
};
#[cfg(test)]
use serde_json::Value;
use sha2::{Digest, Sha256};
#[cfg(test)]
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Instant;
use tokio::io::{AsyncRead, AsyncReadExt};
use tokio::process::Command;
use tokio::time::{Duration, timeout};
use uuid::Uuid;
use walkdir::WalkDir;

const MAX_REPOSITORY_BYTES: u64 = 512 * 1024 * 1024;
const MAX_OUTPUT_BYTES: usize = 1024 * 1024;

fn validate_sandbox_command(spec: &SandboxCommand) -> Result<()> {
    if !is_pinned_image(&spec.image) {
        bail!("sandbox image must be pinned with @sha256:<64 hex characters>");
    }
    if spec.argv.is_empty() || spec.argv[0].trim().is_empty() {
        bail!("sandbox argv must not be empty");
    }
    if !(1..=3_600).contains(&spec.timeout_seconds) {
        bail!("sandbox timeout must be between 1 and 3600 seconds");
    }
    let root = spec
        .repository_path
        .canonicalize()
        .with_context(|| format!("invalid repository path {}", spec.repository_path.display()))?;
    if !root.is_dir() {
        bail!("repository path is not a directory");
    }
    for key in spec.environment.keys() {
        if key.is_empty()
            || !key
                .chars()
                .all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
        {
            bail!("invalid environment variable name: {key}");
        }
    }
    Ok(())
}

fn validate_paired_sandbox_plan(plan: &PairedSandboxPlan) -> Result<()> {
    validate_sandbox_command(&plan.baseline)?;
    validate_sandbox_command(&plan.treatment)?;
    if plan.skill_id.trim().is_empty()
        || plan.skill_version.trim().is_empty()
        || plan.task_family.trim().is_empty()
        || plan.model_id.trim().is_empty()
    {
        bail!("paired evaluation identity fields must not be empty");
    }
    if plan.baseline.image != plan.treatment.image
        || plan.baseline.timeout_seconds != plan.treatment.timeout_seconds
        || plan.baseline.environment != plan.treatment.environment
    {
        bail!("baseline and treatment must use identical image, timeout, and environment");
    }
    if plan.baseline.repository_path.canonicalize()?
        != plan.treatment.repository_path.canonicalize()?
    {
        bail!("baseline and treatment must start from the same repository snapshot");
    }
    Ok(())
}

pub async fn run_paired(data_dir: &Path, plan: &PairedSandboxPlan) -> Result<PairedEvalRecord> {
    validate_paired_sandbox_plan(plan)?;
    docker_available().await?;
    let eval_id = Uuid::new_v4();
    let run_dir = data_dir.join("sandboxes").join(eval_id.to_string());
    fs::create_dir_all(&run_dir)?;
    // Workspaces hold multi-hundred-MB copies; never leak them, and never
    // fail an otherwise-good evaluation because cleanup failed.
    let _cleanup = RunDirCleanup(run_dir.clone());
    let environment_digest = canonical_json_hash(&serde_json::json!({
        "image":&plan.baseline.image,
        "timeout_seconds":plan.baseline.timeout_seconds,
        "environment":&plan.baseline.environment,
        "budget":&plan.budget,
    }));

    let baseline_workspace = run_dir.join("baseline");
    let treatment_workspace = run_dir.join("treatment");
    // Large blocking copies stay off the async executor; the baseline copy
    // computes the repository digest in the same walk (no third traversal).
    let (digest_copy, treatment_copy) = tokio::join!(
        {
            let source = plan.baseline.repository_path.clone();
            let target = baseline_workspace.clone();
            tokio::task::spawn_blocking(move || copy_repository_with_digest(&source, &target))
        },
        {
            let source = plan.treatment.repository_path.clone();
            let target = treatment_workspace.clone();
            tokio::task::spawn_blocking(move || copy_repository(&source, &target))
        },
    );
    let repository_digest = digest_copy.context("join baseline repository copy")??;
    treatment_copy.context("join treatment repository copy")??;

    let (baseline, treatment) = tokio::join!(
        run_container(
            &DockerRunner,
            &plan.baseline,
            &baseline_workspace,
            eval_id,
            "baseline"
        ),
        run_container(
            &DockerRunner,
            &plan.treatment,
            &treatment_workspace,
            eval_id,
            "treatment"
        ),
    );
    let baseline = baseline?;
    let treatment = treatment?;

    let record = PairedEvalRecord {
        eval_id,
        skill_id: plan.skill_id.clone(),
        skill_version: plan.skill_version.clone(),
        task_family: plan.task_family.clone(),
        repository_digest,
        environment_digest,
        model_id: plan.model_id.clone(),
        seed: plan.seed,
        budget: plan.budget.clone(),
        baseline_success: baseline.exit_code == Some(0) && !baseline.timed_out,
        treatment_success: treatment.exit_code == Some(0) && !treatment.timed_out,
        baseline_gate_violations: if baseline.timed_out { 1 } else { 0 },
        treatment_gate_violations: if treatment.timed_out { 1 } else { 0 },
        baseline_score: if baseline.exit_code == Some(0) {
            1.0
        } else {
            0.0
        },
        treatment_score: if treatment.exit_code == Some(0) {
            1.0
        } else {
            0.0
        },
        baseline_latency_ms: baseline.duration_ms,
        treatment_latency_ms: treatment.duration_ms,
        metadata: serde_json::json!({
            "sandbox":"docker","network":"none","image":&plan.baseline.image,
            "baseline":baseline,"treatment":treatment,
            "receipt_directory":run_dir,
        }),
    };
    fs::write(
        run_dir.join("paired-eval.json"),
        format!("{}\n", serde_json::to_string_pretty(&record)?),
    )?;
    Ok(record)
}

async fn docker_available() -> Result<()> {
    let output = timeout(
        Duration::from_secs(10),
        Command::new("docker")
            .args(["version", "--format", "{{.Server.Version}}"])
            .output(),
    )
    .await
    .context("docker availability check timed out")??;
    if !output.status.success() {
        bail!("Docker daemon is unavailable; imported content will not be executed on the host");
    }
    Ok(())
}

fn container_command(
    spec: &SandboxCommand,
    workspace: &Path,
    eval_id: Uuid,
    arm: &str,
) -> Result<Command> {
    let name = format!("cerebellum-{}-{arm}", eval_id.simple());
    let mount = format!("{}:/workspace:rw", workspace.canonicalize()?.display());
    let mut command = Command::new("docker");
    command.kill_on_drop(true).args([
        "run",
        "--rm",
        "--pull",
        "never",
        "--name",
        &name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
        "--volume",
        &mount,
        "--workdir",
        "/workspace",
    ]);
    for (key, value) in &spec.environment {
        command.env(key, value).args(["--env", key]);
    }
    command.arg(&spec.image).args(&spec.argv);
    Ok(command)
}

/// Raw output of one container run, before timeout policy is applied.
struct ContainerOutput {
    exit_code: Option<i32>,
    stdout: String,
    stderr: String,
}

/// Low-level container execution seam. Timeout, kill, and removal policy
/// lives in run_container; implementations only start, drain, and reap.
#[async_trait::async_trait]
trait ContainerRunner {
    async fn run(
        &self,
        spec: &SandboxCommand,
        workspace: &Path,
        eval_id: Uuid,
        arm: &str,
    ) -> Result<ContainerOutput>;
    /// Best-effort force removal of this arm's container after a timeout.
    async fn remove(&self, eval_id: Uuid, arm: &str);
}

struct DockerRunner;

#[async_trait::async_trait]
impl ContainerRunner for DockerRunner {
    async fn run(
        &self,
        spec: &SandboxCommand,
        workspace: &Path,
        eval_id: Uuid,
        arm: &str,
    ) -> Result<ContainerOutput> {
        let mut command = container_command(spec, workspace, eval_id, arm)?;
        let mut child = command
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context("start Docker sandbox")?;
        let stdout = child.stdout.take().context("capture sandbox stdout")?;
        let stderr = child.stderr.take().context("capture sandbox stderr")?;
        let stdout_task = tokio::spawn(drain_limited(stdout));
        let stderr_task = tokio::spawn(drain_limited(stderr));
        let status = child.wait().await?;
        Ok(ContainerOutput {
            exit_code: status.code(),
            stdout: stdout_task.await.context("join stdout collector")??,
            stderr: stderr_task.await.context("join stderr collector")??,
        })
    }

    async fn remove(&self, eval_id: Uuid, arm: &str) {
        let name = format!("cerebellum-{}-{arm}", eval_id.simple());
        let _ = timeout(
            Duration::from_secs(10),
            Command::new("docker")
                .args(["rm", "--force", &name])
                .output(),
        )
        .await;
    }
}

async fn run_container(
    runner: &(impl ContainerRunner + Sync),
    spec: &SandboxCommand,
    workspace: &Path,
    eval_id: Uuid,
    arm: &str,
) -> Result<SandboxResult> {
    let started = Instant::now();
    match timeout(
        Duration::from_secs(spec.timeout_seconds),
        runner.run(spec, workspace, eval_id, arm),
    )
    .await
    {
        Ok(result) => {
            let output = result?;
            Ok(SandboxResult {
                exit_code: output.exit_code,
                timed_out: false,
                duration_ms: started.elapsed().as_millis() as u64,
                stdout: output.stdout,
                stderr: output.stderr,
            })
        }
        Err(_) => {
            // Dropping the run future kills the child (kill_on_drop); make
            // sure the container itself is also gone, with its own deadline.
            runner.remove(eval_id, arm).await;
            Ok(SandboxResult {
                exit_code: None,
                timed_out: true,
                duration_ms: started.elapsed().as_millis() as u64,
                stdout: String::new(),
                stderr: "sandbox timed out".into(),
            })
        }
    }
}

/// Removes the per-eval workspace directory on every exit path; cleanup
/// failures are logged, never fatal to the evaluation.
struct RunDirCleanup(PathBuf);

impl Drop for RunDirCleanup {
    fn drop(&mut self) {
        if !self.0.exists() {
            return;
        }
        if let Err(error) = fs::remove_dir_all(&self.0) {
            tracing::warn!(%error, path = %self.0.display(), "failed to clean sandbox run directory");
        }
    }
}

fn copy_repository(source: &Path, target: &Path) -> Result<()> {
    fs::create_dir_all(target)?;
    let source = source.canonicalize()?;
    let mut copied = 0u64;
    let mut entries: Vec<_> = WalkDir::new(&source)
        .into_iter()
        .filter_entry(|entry| {
            entry
                .path()
                .strip_prefix(&source)
                .map_or(true, |relative| !excluded(relative))
        })
        .collect::<std::result::Result<_, _>>()?;
    entries.sort_by(|a, b| a.path().cmp(b.path()));
    for entry in entries {
        let relative = entry.path().strip_prefix(&source)?;
        if relative.as_os_str().is_empty() || excluded(relative) {
            continue;
        }
        if entry.file_type().is_symlink() {
            bail!(
                "repository contains a symlink, which is not copied into the sandbox: {}",
                relative.display()
            );
        }
        let destination = target.join(relative);
        if entry.file_type().is_dir() {
            fs::create_dir_all(destination)?;
        } else if entry.file_type().is_file() {
            copied = copied.saturating_add(entry.metadata()?.len());
            if copied > MAX_REPOSITORY_BYTES {
                bail!("repository snapshot exceeds {} bytes", MAX_REPOSITORY_BYTES);
            }
            if let Some(parent) = destination.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::copy(entry.path(), destination)?;
        }
    }
    Ok(())
}

/// Copy the repository into `target`, computing the digest in the same walk.
/// Digest semantics must stay identical to digest_tree (pinned by tests).
fn copy_repository_with_digest(source: &Path, target: &Path) -> Result<String> {
    fs::create_dir_all(target)?;
    let source = source.canonicalize()?;
    let mut entries: Vec<_> = WalkDir::new(&source)
        .into_iter()
        .filter_entry(|entry| {
            entry
                .path()
                .strip_prefix(&source)
                .map_or(true, |relative| !excluded(relative))
        })
        .collect::<std::result::Result<_, _>>()?;
    entries.sort_by(|a, b| a.path().cmp(b.path()));
    let mut copied = 0u64;
    let mut digest = Sha256::new();
    for entry in entries {
        let relative = entry.path().strip_prefix(&source)?;
        if relative.as_os_str().is_empty() || excluded(relative) {
            continue;
        }
        if entry.file_type().is_symlink() {
            bail!(
                "repository contains a symlink, which is not copied into the sandbox: {}",
                relative.display()
            );
        }
        let destination = target.join(relative);
        if entry.file_type().is_dir() {
            fs::create_dir_all(destination)?;
        } else if entry.file_type().is_file() {
            copied = copied.saturating_add(entry.metadata()?.len());
            if copied > MAX_REPOSITORY_BYTES {
                bail!("repository snapshot exceeds {} bytes", MAX_REPOSITORY_BYTES);
            }
            if let Some(parent) = destination.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::copy(entry.path(), &destination)?;
            let bytes = fs::read(entry.path())?;
            digest.update(relative.to_string_lossy().replace('\\', "/").as_bytes());
            digest.update([0]);
            digest.update(&bytes);
            digest.update([0]);
        }
    }
    Ok(format!("sha256:{:x}", digest.finalize()))
}

#[cfg(test)]
fn digest_tree(root: &Path) -> Result<String> {
    let root = root.canonicalize()?;
    let mut entries: Vec<_> = WalkDir::new(&root)
        .into_iter()
        .filter_entry(|entry| {
            entry
                .path()
                .strip_prefix(&root)
                .map_or(true, |relative| !excluded(relative))
        })
        .collect::<std::result::Result<_, _>>()?;
    entries.sort_by(|a, b| a.path().cmp(b.path()));
    let mut digest = Sha256::new();
    let mut total = 0u64;
    for entry in entries {
        let relative = entry.path().strip_prefix(&root)?;
        if entry.file_type().is_symlink() {
            bail!("repository digest rejects symlinks");
        }
        if !entry.file_type().is_file() || excluded(relative) {
            continue;
        }
        let bytes = fs::read(entry.path())?;
        total = total.saturating_add(bytes.len() as u64);
        if total > MAX_REPOSITORY_BYTES {
            bail!("repository snapshot exceeds digest limit");
        }
        digest.update(relative.to_string_lossy().replace('\\', "/").as_bytes());
        digest.update([0]);
        digest.update(&bytes);
        digest.update([0]);
    }
    Ok(format!("sha256:{:x}", digest.finalize()))
}

fn excluded(relative: &Path) -> bool {
    relative
        .components()
        .next()
        .and_then(|part| part.as_os_str().to_str())
        .is_some_and(|part| matches!(part, ".git" | "target" | ".cerebellum"))
}

async fn drain_limited<R>(mut reader: R) -> Result<String>
where
    R: AsyncRead + Unpin,
{
    let mut retained = Vec::with_capacity(MAX_OUTPUT_BYTES.min(16 * 1024));
    let mut buffer = [0u8; 16 * 1024];
    loop {
        let read = reader.read(&mut buffer).await?;
        if read == 0 {
            break;
        }
        let remaining = MAX_OUTPUT_BYTES.saturating_sub(retained.len());
        retained.extend_from_slice(&buffer[..read.min(remaining)]);
    }
    Ok(String::from_utf8_lossy(&retained).into_owned())
}

fn is_pinned_image(image: &str) -> bool {
    image.rsplit_once("@sha256:").is_some_and(|(_, digest)| {
        digest.len() == 64 && digest.chars().all(|ch| ch.is_ascii_hexdigit())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn command(root: &Path) -> SandboxCommand {
        SandboxCommand {
            image: format!("example/test@sha256:{}", "a".repeat(64)),
            repository_path: root.into(),
            argv: vec!["test-runner".into()],
            timeout_seconds: 60,
            environment: BTreeMap::new(),
        }
    }

    #[test]
    fn requires_digest_pinned_images() {
        let dir = tempdir().unwrap();
        let mut value = command(dir.path());
        value.image = "example/test:latest".into();
        assert!(validate_sandbox_command(&value).is_err());
    }

    #[test]
    fn paired_arms_must_have_identical_environment() {
        let dir = tempdir().unwrap();
        let baseline = command(dir.path());
        let mut treatment = baseline.clone();
        treatment.timeout_seconds += 1;
        let plan = PairedSandboxPlan {
            skill_id: "example".into(),
            skill_version: "1.0.0".into(),
            task_family: "bugfix".into(),
            model_id: "model".into(),
            seed: 1,
            budget: Value::Null,
            baseline,
            treatment,
        };
        assert!(validate_paired_sandbox_plan(&plan).is_err());
    }

    #[test]
    fn repository_digest_changes_with_content() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("a.txt"), "one").unwrap();
        let first = digest_tree(dir.path()).unwrap();
        fs::write(dir.path().join("a.txt"), "two").unwrap();
        assert_ne!(first, digest_tree(dir.path()).unwrap());
    }

    fn plan(root: &Path) -> PairedSandboxPlan {
        let command = command(root);
        PairedSandboxPlan {
            skill_id: "example".into(),
            skill_version: "1.0.0".into(),
            task_family: "bugfix".into(),
            model_id: "model".into(),
            seed: 1,
            budget: Value::Null,
            baseline: command.clone(),
            treatment: command,
        }
    }

    #[test]
    fn pinned_image_requires_full_sha256_digest() {
        let valid = format!("example/test@sha256:{}", "a".repeat(64));
        assert!(is_pinned_image(&valid));
        let uppercase = format!("example/test@sha256:{}", "A".repeat(64));
        assert!(is_pinned_image(&uppercase));
        assert!(!is_pinned_image("example/test:latest"));
        assert!(!is_pinned_image("example/test@sha256:abc"));
        assert!(!is_pinned_image(&format!(
            "example/test@sha256:{}",
            "a".repeat(63)
        )));
        assert!(!is_pinned_image(&format!(
            "example/test@sha256:{}",
            "a".repeat(65)
        )));
        assert!(!is_pinned_image(&format!(
            "example/test@sha256:{}",
            "g".repeat(64)
        )));
        assert!(!is_pinned_image("example/test@sha256:"));
    }

    #[test]
    fn valid_command_passes_validation() {
        let dir = tempdir().unwrap();
        validate_sandbox_command(&command(dir.path())).unwrap();
    }

    #[test]
    fn argv_must_not_be_empty_or_blank() {
        let dir = tempdir().unwrap();
        let mut value = command(dir.path());
        value.argv = vec![];
        assert!(validate_sandbox_command(&value).is_err());
        value.argv = vec!["   ".into()];
        assert!(validate_sandbox_command(&value).is_err());
    }

    #[test]
    fn timeout_is_bounded_to_one_hour() {
        let dir = tempdir().unwrap();
        for timeout_seconds in [1, 300, 3_600] {
            let mut value = command(dir.path());
            value.timeout_seconds = timeout_seconds;
            validate_sandbox_command(&value).unwrap();
        }
        for timeout_seconds in [0, 3_601] {
            let mut value = command(dir.path());
            value.timeout_seconds = timeout_seconds;
            assert!(validate_sandbox_command(&value).is_err());
        }
    }

    #[test]
    fn timeout_defaults_to_five_minutes() {
        let dir = tempdir().unwrap();
        let parsed: SandboxCommand = serde_json::from_value(serde_json::json!({
            "image": format!("example/test@sha256:{}", "a".repeat(64)),
            "repository_path": dir.path(),
            "argv": ["run"],
        }))
        .unwrap();
        assert_eq!(parsed.timeout_seconds, 300);
        assert!(parsed.environment.is_empty());
    }

    #[test]
    fn command_deserialization_rejects_unknown_fields() {
        let dir = tempdir().unwrap();
        let error = serde_json::from_value::<SandboxCommand>(serde_json::json!({
            "image": format!("example/test@sha256:{}", "a".repeat(64)),
            "repository_path": dir.path(),
            "argv": ["run"],
            "bogus": 1,
        }))
        .unwrap_err();
        assert!(error.to_string().contains("unknown field"));
    }

    #[test]
    fn environment_names_must_be_safe_tokens() {
        let dir = tempdir().unwrap();
        for key in ["", "HAS-DASH", "HAS SPACE", "UNICODÉ", "TAB\tNAME"] {
            let mut value = command(dir.path());
            value.environment.insert(key.to_string(), "value".into());
            assert!(
                validate_sandbox_command(&value).is_err(),
                "expected rejection of {key:?}"
            );
        }
        let mut value = command(dir.path());
        value
            .environment
            .insert("VALID_NAME_1".into(), "value".into());
        validate_sandbox_command(&value).unwrap();
    }

    #[test]
    fn repository_path_must_be_an_existing_directory() {
        let dir = tempdir().unwrap();
        let missing = command(&dir.path().join("missing"));
        assert!(validate_sandbox_command(&missing).is_err());
        let file = dir.path().join("file.txt");
        fs::write(&file, "data").unwrap();
        assert!(validate_sandbox_command(&command(&file)).is_err());
    }

    #[test]
    fn paired_plan_requires_identity_fields() {
        let dir = tempdir().unwrap();
        for mutate in [
            (|p: &mut PairedSandboxPlan| p.skill_id = " ".into()) as fn(&mut PairedSandboxPlan),
            |p| p.skill_version = String::new(),
            |p| p.task_family = String::new(),
            |p| p.model_id = "  ".into(),
        ] {
            let mut value = plan(dir.path());
            mutate(&mut value);
            assert!(validate_paired_sandbox_plan(&value).is_err());
        }
        validate_paired_sandbox_plan(&plan(dir.path())).unwrap();
    }

    #[test]
    fn paired_arms_must_share_the_repository_snapshot() {
        let baseline_dir = tempdir().unwrap();
        let treatment_dir = tempdir().unwrap();
        let mut value = plan(baseline_dir.path());
        value.treatment.repository_path = treatment_dir.path().into();
        assert!(validate_paired_sandbox_plan(&value).is_err());
    }

    #[test]
    fn paired_arms_must_use_the_same_image_and_environment() {
        let dir = tempdir().unwrap();
        let mut value = plan(dir.path());
        value.treatment.image = format!("example/other@sha256:{}", "b".repeat(64));
        assert!(validate_paired_sandbox_plan(&value).is_err());
        let mut value = plan(dir.path());
        value
            .treatment
            .environment
            .insert("EXTRA".into(), "1".into());
        assert!(validate_paired_sandbox_plan(&value).is_err());
    }

    #[test]
    fn exclusion_only_matches_top_level_special_directories() {
        assert!(excluded(Path::new(".git")));
        assert!(excluded(Path::new(".git/config")));
        assert!(excluded(Path::new("target/debug/build")));
        assert!(excluded(Path::new(".cerebellum/state.json")));
        assert!(!excluded(Path::new("src/target/helper.rs")));
        assert!(!excluded(Path::new("src/main.rs")));
    }

    #[test]
    fn digest_tree_is_deterministic_and_ignores_excluded_directories() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("a.txt"), "one").unwrap();
        fs::create_dir_all(dir.path().join("nested")).unwrap();
        fs::write(dir.path().join("nested/b.txt"), "two").unwrap();
        let baseline = digest_tree(dir.path()).unwrap();
        assert!(baseline.starts_with("sha256:"));
        assert_eq!(digest_tree(dir.path()).unwrap(), baseline);
        fs::create_dir_all(dir.path().join(".git")).unwrap();
        fs::write(dir.path().join(".git/index"), "noise").unwrap();
        fs::create_dir_all(dir.path().join("target")).unwrap();
        fs::write(dir.path().join("target/artifact"), "noise").unwrap();
        assert_eq!(digest_tree(dir.path()).unwrap(), baseline);
    }

    #[test]
    fn digest_tree_includes_relative_paths() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("a.txt"), "same").unwrap();
        let first = digest_tree(dir.path()).unwrap();
        fs::rename(dir.path().join("a.txt"), dir.path().join("b.txt")).unwrap();
        assert_ne!(first, digest_tree(dir.path()).unwrap());
    }

    #[test]
    fn copy_repository_copies_files_and_skips_excluded_directories() {
        let source = tempdir().unwrap();
        let target = tempdir().unwrap();
        fs::create_dir_all(source.path().join("src")).unwrap();
        fs::write(source.path().join("src/main.rs"), "fn main() {}").unwrap();
        fs::create_dir_all(source.path().join(".git")).unwrap();
        fs::write(source.path().join(".git/index"), "noise").unwrap();
        fs::create_dir_all(source.path().join("target")).unwrap();
        fs::write(source.path().join("target/artifact"), "noise").unwrap();
        let destination = target.path().join("copy");
        copy_repository(source.path(), &destination).unwrap();
        assert_eq!(
            fs::read_to_string(destination.join("src/main.rs")).unwrap(),
            "fn main() {}"
        );
        assert!(!destination.join(".git").exists());
        assert!(!destination.join("target").exists());
    }

    #[test]
    fn copy_repository_is_byte_identical() {
        let source = tempdir().unwrap();
        let target = tempdir().unwrap();
        fs::write(source.path().join("data.bin"), b"\x00\x01\x02\xff").unwrap();
        copy_repository(source.path(), target.path()).unwrap();
        assert_eq!(
            fs::read(target.path().join("data.bin")).unwrap(),
            b"\x00\x01\x02\xff"
        );
    }

    #[tokio::test]
    async fn drain_limited_passes_through_small_output() {
        let output = drain_limited(&b"hello sandbox"[..]).await.unwrap();
        assert_eq!(output, "hello sandbox");
    }

    #[tokio::test]
    async fn drain_limited_caps_output_at_max_bytes() {
        let payload = vec![b'a'; MAX_OUTPUT_BYTES + 4 * 1024];
        let output = drain_limited(&payload[..]).await.unwrap();
        assert_eq!(output.len(), MAX_OUTPUT_BYTES);
        assert!(output.bytes().all(|byte| byte == b'a'));
    }

    #[tokio::test]
    async fn drain_limited_lossy_decodes_invalid_utf8() {
        let output = drain_limited(&b"ok\xff\xfe"[..]).await.unwrap();
        assert!(output.starts_with("ok"));
        assert!(output.contains(char::REPLACEMENT_CHARACTER));
    }

    #[test]
    fn container_command_is_hermetic_and_shell_free() {
        let dir = tempdir().unwrap();
        let eval_id = Uuid::new_v4();
        let mut spec = command(dir.path());
        spec.argv = vec![
            "test-runner".into(),
            "--flag=value; rm -rf / $(whoami) `id`".into(),
        ];
        spec.environment.insert("API_KEY".into(), "a b;c".into());
        let command = container_command(&spec, dir.path(), eval_id, "treatment").unwrap();
        let std = command.as_std();
        assert_eq!(std.get_program(), "docker");
        let args: Vec<String> = std
            .get_args()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect();
        // No shell wrapper: every argument is passed to docker verbatim.
        assert!(
            args.iter()
                .all(|arg| arg != "-c" && arg != "sh" && arg != "bash")
        );
        for expected in [
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            "2g",
            "--cpus",
            "2",
        ] {
            assert!(args.iter().any(|arg| arg == expected), "missing {expected}");
        }
        let name = format!("cerebellum-{}-treatment", eval_id.simple());
        assert!(args.iter().any(|arg| arg == &name));
        // Shell metacharacters survive as one discrete argument, never interpolated.
        assert!(
            args.iter()
                .any(|arg| arg == "--flag=value; rm -rf / $(whoami) `id`")
        );
        // Exactly one volume mount, and it is the copied workspace, not a host path.
        let mounts: Vec<&String> = args
            .windows(2)
            .filter(|pair| pair[0] == "--volume")
            .map(|pair| &pair[1])
            .collect();
        assert_eq!(mounts.len(), 1);
        assert!(mounts[0].ends_with(":/workspace:rw"));
        // Environment reaches the container via --env flags plus a scrubbed child env entry.
        assert!(
            args.windows(2)
                .any(|pair| pair[0] == "--env" && pair[1] == "API_KEY")
        );
        assert!(
            std.get_envs().any(
                |(key, value)| key == "API_KEY" && value == Some(std::ffi::OsStr::new("a b;c"))
            )
        );
        // Image is pinned and immediately precedes the container argv.
        let image = args.iter().position(|arg| arg == &spec.image).unwrap();
        assert_eq!(args[image + 1], "test-runner");
    }

    #[test]
    fn sandbox_result_round_trips_with_null_exit_code() {
        let result = SandboxResult {
            exit_code: None,
            timed_out: true,
            duration_ms: 42,
            stdout: String::new(),
            stderr: "sandbox timed out".into(),
        };
        let value = serde_json::to_value(&result).unwrap();
        assert_eq!(value["exit_code"], Value::Null);
        let parsed: SandboxResult = serde_json::from_value(value).unwrap();
        assert_eq!(parsed.exit_code, None);
        assert!(parsed.timed_out);
        assert_eq!(parsed.duration_ms, 42);
    }

    /// Drops a flag unless the future runs to completion; set ⟺ cancelled.
    struct CancelProbe(std::sync::Arc<std::sync::atomic::AtomicBool>);

    impl Drop for CancelProbe {
        fn drop(&mut self) {
            self.0.store(true, std::sync::atomic::Ordering::SeqCst);
        }
    }

    struct FakeRunner {
        latency: Duration,
        removed: std::sync::Arc<tokio::sync::Mutex<Vec<String>>>,
        cancelled: std::sync::Arc<std::sync::atomic::AtomicBool>,
    }

    #[async_trait::async_trait]
    impl ContainerRunner for FakeRunner {
        async fn run(
            &self,
            _spec: &SandboxCommand,
            _workspace: &Path,
            _eval_id: Uuid,
            _arm: &str,
        ) -> Result<ContainerOutput> {
            let probe = CancelProbe(self.cancelled.clone());
            tokio::time::sleep(self.latency).await;
            std::mem::forget(probe); // completed normally: disarm
            Ok(ContainerOutput {
                exit_code: Some(0),
                stdout: "ok".into(),
                stderr: String::new(),
            })
        }

        async fn remove(&self, _eval_id: Uuid, arm: &str) {
            self.removed.lock().await.push(arm.to_string());
        }
    }

    fn fake_runner(
        latency: Duration,
    ) -> (
        FakeRunner,
        std::sync::Arc<tokio::sync::Mutex<Vec<String>>>,
        std::sync::Arc<std::sync::atomic::AtomicBool>,
    ) {
        let removed = std::sync::Arc::new(tokio::sync::Mutex::new(Vec::new()));
        let cancelled = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
        (
            FakeRunner {
                latency,
                removed: removed.clone(),
                cancelled: cancelled.clone(),
            },
            removed,
            cancelled,
        )
    }

    #[tokio::test]
    async fn run_container_kills_and_removes_on_timeout() {
        let (runner, removed, cancelled) = fake_runner(Duration::from_secs(60));
        let dir = tempdir().unwrap();
        let mut spec = command(dir.path());
        spec.timeout_seconds = 1;
        let started = Instant::now();
        let result = run_container(&runner, &spec, dir.path(), Uuid::new_v4(), "treatment")
            .await
            .unwrap();

        assert!(result.timed_out);
        assert_eq!(result.exit_code, None);
        assert_eq!(result.stderr, "sandbox timed out");
        assert!(started.elapsed() < Duration::from_secs(10));
        assert!(
            cancelled.load(std::sync::atomic::Ordering::SeqCst),
            "timed-out run future must be dropped (the kill path)"
        );
        assert_eq!(removed.lock().await.as_slice(), ["treatment"]);
    }

    #[tokio::test]
    async fn run_container_propagates_success_output() {
        let (runner, removed, _) = fake_runner(Duration::ZERO);
        let dir = tempdir().unwrap();
        let spec = command(dir.path());
        let result = run_container(&runner, &spec, dir.path(), Uuid::new_v4(), "baseline")
            .await
            .unwrap();

        assert!(!result.timed_out);
        assert_eq!(result.exit_code, Some(0));
        assert_eq!(result.stdout, "ok");
        assert!(removed.lock().await.is_empty());
    }

    #[test]
    fn copy_with_digest_matches_digest_tree() {
        let source = tempdir().unwrap();
        fs::create_dir_all(source.path().join("src")).unwrap();
        fs::write(source.path().join("src/main.rs"), "fn main() {}").unwrap();
        fs::write(source.path().join("note.txt"), "hello").unwrap();
        fs::create_dir_all(source.path().join("target")).unwrap();
        fs::write(source.path().join("target/noise"), "x").unwrap();
        let target = tempdir().unwrap();
        let digest = copy_repository_with_digest(source.path(), target.path()).unwrap();
        assert_eq!(digest, digest_tree(source.path()).unwrap());
        assert_eq!(
            fs::read_to_string(target.path().join("src/main.rs")).unwrap(),
            "fn main() {}"
        );
        assert!(!target.path().join("target").exists());
    }

    #[tokio::test]
    #[ignore = "requires a running Docker daemon and a pinned image"]
    async fn run_paired_executes_against_real_docker_and_cleans_up() {
        let Ok(image) = std::env::var("CEREBELLUM_SMOKE_IMAGE") else {
            eprintln!("set CEREBELLUM_SMOKE_IMAGE to an @sha256-pinned image to run");
            return;
        };
        let source = tempdir().unwrap();
        fs::write(source.path().join("README.md"), "sandbox smoke").unwrap();
        let data = tempdir().unwrap();
        let mut plan = plan(source.path());
        plan.baseline.image = image.clone();
        plan.treatment.image = image;
        plan.baseline.argv = vec!["true".into()];
        plan.treatment.argv = vec!["true".into()];

        let record = run_paired(data.path(), &plan).await.unwrap();

        assert!(record.baseline_success);
        assert!(record.treatment_success);
        let run_dir = data
            .path()
            .join("sandboxes")
            .join(record.eval_id.to_string());
        assert!(!run_dir.exists(), "workspace directories must not leak");
    }
}
