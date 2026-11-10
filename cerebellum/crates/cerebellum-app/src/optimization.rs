use anyhow::{Result, anyhow, bail};
use cerebellum_core::{SkillEditOperation, SkillEditPatch};
use sha2::{Digest, Sha256};

pub fn content_hash(content: &[u8]) -> String {
    format!("{:x}", Sha256::digest(content))
}

pub fn approximate_token_count(content: &str) -> usize {
    content.split_whitespace().count()
}

pub fn apply_skill_patch(baseline: &str, patch: &SkillEditPatch) -> Result<String> {
    let (frontmatter, mut body) = split_frontmatter(baseline)?;
    for edit in &patch.edits {
        match edit.operation {
            SkillEditOperation::Append => {
                if !body.ends_with('\n') {
                    body.push('\n');
                }
                body.push('\n');
                body.push_str(edit.content.trim());
                body.push('\n');
            }
            SkillEditOperation::InsertAfter => {
                let index = unique_target(&body, &edit.target)?;
                let insertion = format!("{}\n{}", edit.target, edit.content.trim());
                body.replace_range(index..index + edit.target.len(), &insertion);
            }
            SkillEditOperation::Replace => {
                let index = unique_target(&body, &edit.target)?;
                body.replace_range(index..index + edit.target.len(), edit.content.trim());
            }
            SkillEditOperation::Delete => {
                let index = unique_target(&body, &edit.target)?;
                body.replace_range(index..index + edit.target.len(), "");
            }
        }
    }
    let candidate = format!("{frontmatter}{}\n", body.trim());
    if frontmatter_bytes(&candidate)? != frontmatter.as_bytes() {
        bail!("candidate patch changed protected frontmatter");
    }
    Ok(candidate)
}

fn unique_target(body: &str, target: &str) -> Result<usize> {
    if target.is_empty() {
        bail!("patch target is empty");
    }
    let mut matches = body.match_indices(target);
    let (index, _) = matches
        .next()
        .ok_or_else(|| anyhow!("patch target does not exist in baseline body"))?;
    if matches.next().is_some() {
        bail!("patch target is ambiguous in baseline body");
    }
    Ok(index)
}

fn split_frontmatter(content: &str) -> Result<(String, String)> {
    let normalized = content.replace("\r\n", "\n");
    if !normalized.starts_with("---\n") {
        bail!("skill lacks YAML frontmatter");
    }
    let closing = normalized[4..]
        .find("\n---\n")
        .map(|index| index + 4)
        .ok_or_else(|| anyhow!("skill frontmatter is not closed"))?;
    let frontmatter_end = closing + "\n---\n".len();
    Ok((
        normalized[..frontmatter_end].to_owned(),
        normalized[frontmatter_end..].trim().to_owned(),
    ))
}

fn frontmatter_bytes(content: &str) -> Result<&[u8]> {
    if !content.starts_with("---\n") {
        bail!("skill lacks YAML frontmatter");
    }
    let closing = content[4..]
        .find("\n---\n")
        .map(|index| index + 4)
        .ok_or_else(|| anyhow!("skill frontmatter is not closed"))?;
    Ok(&content.as_bytes()[..closing + "\n---\n".len()])
}

#[cfg(test)]
mod tests {
    use super::*;
    use cerebellum_core::{SCHEMA_VERSION, SkillEdit, SkillEditOperation};
    use chrono::Utc;
    use uuid::Uuid;

    fn patch(operation: SkillEditOperation, target: &str, content: &str) -> SkillEditPatch {
        SkillEditPatch {
            schema_version: SCHEMA_VERSION.into(),
            patch_id: Uuid::new_v4(),
            run_id: Uuid::new_v4(),
            sequence: 1,
            baseline_hash: "a".repeat(64),
            candidate_hash: "b".repeat(64),
            edits: vec![SkillEdit {
                operation,
                target: target.into(),
                content: content.into(),
            }],
            rationale: "test".into(),
            trajectory_ids: vec![],
            token_delta: 1,
            optimizer_model: "optimizer".into(),
            created_at: Utc::now(),
        }
    }

    #[test]
    fn patch_changes_only_the_body() {
        let baseline =
            "---\nname: verify\ndescription: verify\n---\n\n# Verify\n\n## Steps\nRun tests.\n";
        let candidate = apply_skill_patch(
            baseline,
            &patch(
                SkillEditOperation::Replace,
                "Run tests.",
                "Run the full test suite after the final edit.",
            ),
        )
        .unwrap();
        assert!(candidate.starts_with("---\nname: verify\ndescription: verify\n---\n"));
        assert!(candidate.contains("after the final edit"));
    }

    #[test]
    fn ambiguous_targets_are_rejected() {
        let baseline = "---\nname: verify\ndescription: verify\n---\n\nRun tests. Run tests.\n";
        assert!(
            apply_skill_patch(
                baseline,
                &patch(SkillEditOperation::Delete, "Run tests.", "")
            )
            .is_err()
        );
    }
}
