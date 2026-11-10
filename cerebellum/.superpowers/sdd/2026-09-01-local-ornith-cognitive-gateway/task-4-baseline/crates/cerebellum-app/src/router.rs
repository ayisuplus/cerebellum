use anyhow::{Context, Result, bail};
use async_trait::async_trait;
use cerebellum_core::{DecisionRequest, RankedWorkflow, WorkflowManifest};
use reqwest::Client;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::time::Duration;
/// Workflow nudged ahead of other zero-score ties so an unmatched request
/// still routes deterministically to the most general built-in workflow.
const DEFAULT_WORKFLOW_ID: &str = "feature";

#[derive(Debug)]
pub struct RouterOutput {
    pub ranked: Vec<RankedWorkflow>,
    pub router: String,
    pub fallback_used: bool,
}

#[async_trait]
pub trait RouterModel: Send + Sync {
    async fn rank(
        &self,
        request: &DecisionRequest,
        workflows: &[WorkflowManifest],
    ) -> Result<Vec<RankedWorkflow>>;
    fn name(&self) -> &str;
}

pub struct DeterministicRouter;

#[async_trait]
impl RouterModel for DeterministicRouter {
    async fn rank(
        &self,
        request: &DecisionRequest,
        workflows: &[WorkflowManifest],
    ) -> Result<Vec<RankedWorkflow>> {
        if workflows.is_empty() {
            bail!("registry contains no workflows");
        }
        let documents: Vec<Vec<String>> = workflows.iter().map(workflow_tokens).collect();
        let mut query = tokenize(&format!("{} {}", request.task, request.context));
        // Each distinct term scores once: duplicates would double-count the
        // term's contribution and repeat it in the reasons list.
        let mut seen = HashSet::new();
        query.retain(|term| seen.insert(term.clone()));
        let average_len =
            documents.iter().map(Vec::len).sum::<usize>() as f64 / documents.len() as f64;
        let mut document_frequency: HashMap<&str, usize> = HashMap::new();
        for doc in &documents {
            let unique: HashSet<_> = doc.iter().map(String::as_str).collect();
            for token in unique {
                *document_frequency.entry(token).or_default() += 1;
            }
        }

        let mut ranked: Vec<_> = workflows
            .iter()
            .zip(documents.iter())
            .map(|(workflow, doc)| {
                let mut score = 0.0;
                let mut matched = Vec::new();
                for term in &query {
                    let frequency = doc.iter().filter(|token| *token == term).count() as f64;
                    if frequency == 0.0 {
                        continue;
                    }
                    let df = document_frequency.get(term.as_str()).copied().unwrap_or(0) as f64;
                    let idf = ((workflows.len() as f64 - df + 0.5) / (df + 0.5) + 1.0).ln();
                    let denominator = frequency
                        + 1.2 * (1.0 - 0.75 + 0.75 * doc.len() as f64 / average_len.max(1.0));
                    score += idf * frequency * 2.2 / denominator;
                    matched.push(term.clone());
                }
                if workflow.id == DEFAULT_WORKFLOW_ID && matched.is_empty() {
                    score += 0.001;
                }
                RankedWorkflow {
                    workflow_id: workflow.id.clone(),
                    version: workflow.version.clone(),
                    score,
                    reasons: if matched.is_empty() {
                        vec!["deterministic default".into()]
                    } else {
                        vec![format!("matched: {}", matched.join(", "))]
                    },
                }
            })
            .collect();
        ranked.sort_by(|a, b| {
            b.score
                .total_cmp(&a.score)
                .then_with(|| a.workflow_id.cmp(&b.workflow_id))
        });
        Ok(ranked)
    }
    fn name(&self) -> &str {
        "deterministic-bm25"
    }
}

pub struct OpenAiCompatibleRouter {
    client: Client,
    endpoint: String,
    model: String,
    api_key: Option<String>,
    backend_name: String,
}

impl OpenAiCompatibleRouter {
    pub fn new(
        endpoint: String,
        model: String,
        api_key: Option<String>,
        backend_name: String,
    ) -> Self {
        let endpoint = crate::chat_completions_url(&endpoint);
        Self {
            client: Client::new(),
            endpoint,
            model,
            api_key,
            backend_name,
        }
    }
}

#[async_trait]
impl RouterModel for OpenAiCompatibleRouter {
    async fn rank(
        &self,
        request: &DecisionRequest,
        workflows: &[WorkflowManifest],
    ) -> Result<Vec<RankedWorkflow>> {
        let candidates: Vec<_> = workflows.iter().map(|w| json!({
            "workflow_id":w.id,"version":w.version,"description":w.description,"triggers":w.triggers,"risk_level":w.risk_level
        })).collect();
        let prompt = json!({
            "task": request.task, "context": request.context, "capabilities": request.capabilities,
            "candidates": candidates,
            "required_output": {"workflow_id":"candidate id","confidence":"number 0..1","reasons":["short reason"]}
        });
        let body = json!({"model":self.model,"temperature":0,"response_format":{"type":"json_object"},"messages":[
            {"role":"system","content":"Select exactly one supplied workflow. Never invent IDs. Return only the required JSON object."},
            {"role":"user","content":serde_json::to_string(&prompt)?}
        ]});
        let mut builder = self
            .client
            .post(&self.endpoint)
            .timeout(Duration::from_secs(10))
            .json(&body);
        if let Some(key) = &self.api_key {
            builder = builder.bearer_auth(key);
        }
        let response: Value = builder.send().await?.error_for_status()?.json().await?;
        let content = response
            .pointer("/choices/0/message/content")
            .and_then(Value::as_str)
            .context("model response lacks choices[0].message.content")?;
        let selected: Value =
            serde_json::from_str(content).context("model output is not valid JSON")?;
        let id = selected
            .get("workflow_id")
            .and_then(Value::as_str)
            .context("missing workflow_id")?;
        let confidence = selected
            .get("confidence")
            .and_then(Value::as_f64)
            .context("missing confidence")?;
        if !(0.25..=1.0).contains(&confidence) {
            bail!("model confidence is below threshold or invalid");
        }
        let workflow = workflows
            .iter()
            .find(|workflow| workflow.id == id)
            .context("model invented a workflow ID")?;
        let reasons = selected
            .get("reasons")
            .and_then(Value::as_array)
            .map(|values| {
                values
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_owned)
                    .collect()
            })
            .unwrap_or_default();
        Ok(vec![RankedWorkflow {
            workflow_id: workflow.id.clone(),
            version: workflow.version.clone(),
            score: confidence,
            reasons,
        }])
    }
    fn name(&self) -> &str {
        &self.backend_name
    }
}

pub async fn rank_with_fallback(
    primary: &dyn RouterModel,
    request: &DecisionRequest,
    workflows: &[WorkflowManifest],
) -> Result<RouterOutput> {
    match primary.rank(request, workflows).await {
        Ok(ranked) if !ranked.is_empty() => Ok(RouterOutput {
            ranked,
            router: primary.name().into(),
            fallback_used: false,
        }),
        outcome if primary.name() != "deterministic-bm25" => {
            match &outcome {
                Ok(_) => tracing::warn!(
                    router = primary.name(),
                    "primary router returned no candidates; falling back to deterministic-bm25"
                ),
                Err(error) => tracing::warn!(
                    router = primary.name(),
                    %error,
                    "primary router failed; falling back to deterministic-bm25"
                ),
            }
            let fallback = DeterministicRouter;
            Ok(RouterOutput {
                ranked: fallback.rank(request, workflows).await?,
                router: fallback.name().into(),
                fallback_used: true,
            })
        }
        Ok(_) => bail!("router returned no candidates"),
        Err(error) => Err(error),
    }
}

fn workflow_tokens(workflow: &WorkflowManifest) -> Vec<String> {
    tokenize(&format!(
        "{} {} {} {}",
        workflow.id,
        workflow.description,
        workflow.task_classes.join(" "),
        workflow.triggers.join(" ")
    ))
}

fn tokenize(value: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut run = String::new();
    let mut run_is_cjk = false;
    // Split on punctuation and on CJK<->non-CJK boundaries so mixed text
    // like "修复parser" yields both a CJK run and a Latin token.
    for ch in value.to_lowercase().chars() {
        let word_char = ch.is_alphanumeric() || ch == '-';
        let cjk = is_cjk(ch);
        if word_char && !run.is_empty() && cjk == run_is_cjk {
            run.push(ch);
            continue;
        }
        if !run.is_empty() {
            tokens.extend(cjk_aware_tokens(&run, run_is_cjk));
            run.clear();
        }
        if word_char {
            run.push(ch);
            run_is_cjk = cjk;
        }
    }
    if !run.is_empty() {
        tokens.extend(cjk_aware_tokens(&run, run_is_cjk));
    }
    tokens
}

/// CJK text has no word boundaries, so a contiguous CJK run would otherwise
/// stay a single opaque token that only exact queries can match. Index
/// overlapping bigrams instead (a 1-2 char run is its own token).
fn cjk_aware_tokens(run: &str, is_cjk_run: bool) -> Vec<String> {
    let chars: Vec<char> = run.chars().collect();
    if is_cjk_run && chars.len() > 2 {
        chars.windows(2).map(|pair| pair.iter().collect()).collect()
    } else {
        vec![run.to_string()]
    }
}

fn is_cjk(ch: char) -> bool {
    matches!(
        ch,
        '一'..='\u{9fff}' | '\u{3400}'..='\u{4dbf}' | '\u{f900}'..='\u{faff}'
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::builtins;
    use async_trait::async_trait;

    struct BrokenRouter;
    #[async_trait]
    impl RouterModel for BrokenRouter {
        async fn rank(
            &self,
            _request: &DecisionRequest,
            _workflows: &[WorkflowManifest],
        ) -> Result<Vec<RankedWorkflow>> {
            anyhow::bail!("model unavailable")
        }
        fn name(&self) -> &str {
            "broken-model"
        }
    }

    #[tokio::test]
    async fn routes_all_builtin_task_classes_deterministically() {
        let cases = [
            ("fix failing parser bug", "bugfix"),
            ("implement a new feature", "feature"),
            ("review this pull request", "code-review"),
            ("run pre-merge release checks", "pre-merge"),
        ];
        for (task, expected) in cases {
            let request = DecisionRequest {
                task: task.into(),
                repository_path: None,
                capabilities: vec![],
                context: Value::Null,
            };
            let first = DeterministicRouter
                .rank(&request, &builtins::workflows())
                .await
                .unwrap();
            let second = DeterministicRouter
                .rank(&request, &builtins::workflows())
                .await
                .unwrap();
            assert_eq!(first[0].workflow_id, expected);
            assert_eq!(first[0].workflow_id, second[0].workflow_id);
            assert_eq!(first[0].score, second[0].score);
        }
    }

    #[tokio::test]
    async fn model_failure_falls_back_without_losing_a_decision() {
        let request = DecisionRequest {
            task: "review this pull request".into(),
            repository_path: None,
            capabilities: vec![],
            context: Value::Null,
        };
        let output = rank_with_fallback(&BrokenRouter, &request, &builtins::workflows())
            .await
            .unwrap();
        assert!(output.fallback_used);
        assert_eq!(output.router, "deterministic-bm25");
        assert_eq!(output.ranked[0].workflow_id, "code-review");
    }
    #[test]
    fn tokenizer_indexes_cjk_runs_as_bigrams() {
        let tokens = tokenize("修复parser的crash问题");
        assert!(tokens.contains(&"修复".to_string()));
        assert!(tokens.contains(&"问题".to_string()));
        // Latin runs stay whole; no opaque multi-char CJK token remains.
        assert!(tokens.contains(&"parser".to_string()));
        assert!(!tokens.contains(&"修复parser的crash问题".to_string()));
        // Short CJK runs stay intact (a bigram of two chars is the run itself).
        assert_eq!(tokenize("修复"), vec!["修复".to_string()]);
    }

    #[tokio::test]
    async fn cjk_query_matches_cjk_workflow_text() {
        fn zh_workflow(id: &str, description: &str) -> WorkflowManifest {
            WorkflowManifest {
                schema_version: "workflow/v1".into(),
                id: id.into(),
                version: "1.0.0".into(),
                description: description.into(),
                task_classes: vec![],
                triggers: vec![],
                risk_level: cerebellum_core::RiskLevel::Low,
                nodes: vec![],
                edges: vec![],
                gates: vec![],
                on_failure: cerebellum_core::GateFailureAction::Deny,
                lineage: None,
            }
        }
        let workflows = vec![
            zh_workflow("zh-review", "审查代码变更并生成报告"),
            zh_workflow("zh-train", "训练模型并评估效果"),
        ];
        let request = DecisionRequest {
            task: "审查这个变更".into(),
            repository_path: None,
            capabilities: vec![],
            context: Value::Null,
        };
        let ranked = DeterministicRouter
            .rank(&request, &workflows)
            .await
            .unwrap();
        assert_eq!(ranked[0].workflow_id, "zh-review");
        assert!(ranked[0].score > ranked[1].score);
    }

    #[tokio::test]
    async fn duplicate_query_terms_score_once() {
        let workflows = builtins::workflows();
        let once = DecisionRequest {
            task: "fix bug".into(),
            repository_path: None,
            capabilities: vec![],
            context: Value::Null,
        };
        let thrice = DecisionRequest {
            task: "fix fix fix bug".into(),
            repository_path: None,
            capabilities: vec![],
            context: Value::Null,
        };
        let a = DeterministicRouter.rank(&once, &workflows).await.unwrap();
        let b = DeterministicRouter.rank(&thrice, &workflows).await.unwrap();
        assert_eq!(a[0].workflow_id, b[0].workflow_id);
        assert_eq!(a[0].score, b[0].score);
    }

    #[tokio::test]
    async fn unmatched_request_routes_to_default_workflow_deterministically() {
        let request = DecisionRequest {
            task: "zzzz qqqq".into(),
            repository_path: None,
            capabilities: vec![],
            context: Value::Null,
        };
        let ranked = DeterministicRouter
            .rank(&request, &builtins::workflows())
            .await
            .unwrap();
        assert_eq!(ranked[0].workflow_id, DEFAULT_WORKFLOW_ID);
        assert!(ranked[0].score > 0.0);
    }
}
