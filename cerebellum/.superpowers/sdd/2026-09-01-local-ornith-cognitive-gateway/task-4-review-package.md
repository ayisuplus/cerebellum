# Task 4 review package

Task brief: task-4-brief.md
Implementer report: task-4-implementer.md
Comparison: task-start snapshot to current working tree; no commits or staging.
Ruling: cargo GREEN is deferred to Task 5 because api.rs still uses the old constructor; no temporary compatibility API is permitted.

warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\task-4-baseline\crates\cerebellum-app\src\router.rs', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'crates\cerebellum-app\src\router.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-4-baseline\\crates\\cerebellum-app\\src\\router.rs" "b/crates\\cerebellum-app\\src\\router.rs"
index 0d92730..9727887 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-4-baseline\\crates\\cerebellum-app\\src\\router.rs"
+++ "b/crates\\cerebellum-app\\src\\router.rs"
@@ -1,13 +1,16 @@
+use crate::Registry;
+use crate::quality::{StructuredModelClient, StructuredRequest, complete_budgeted};
 use anyhow::{Context, Result, bail};
 use async_trait::async_trait;
-use cerebellum_core::{DecisionRequest, RankedWorkflow, WorkflowManifest};
-use reqwest::Client;
+use cerebellum_core::{DecisionRequest, QualityModelStage, RankedWorkflow, WorkflowManifest};
+use chrono::Utc;
 use serde_json::{Value, json};
 use std::collections::{HashMap, HashSet};
-use std::time::Duration;
+use std::sync::Arc;
 /// Workflow nudged ahead of other zero-score ties so an unmatched request
 /// still routes deterministically to the most general built-in workflow.
 const DEFAULT_WORKFLOW_ID: &str = "feature";
+const ROUTER_SYSTEM_PROMPT: &str = "Select exactly one supplied workflow. Never invent IDs. Return only the required JSON object.";
 
 #[derive(Debug)]
 pub struct RouterOutput {
@@ -100,28 +103,13 @@ impl RouterModel for DeterministicRouter {
 }
 
 pub struct OpenAiCompatibleRouter {
-    client: Client,
-    endpoint: String,
-    model: String,
-    api_key: Option<String>,
-    backend_name: String,
+    registry: Arc<Registry>,
+    client: Arc<dyn StructuredModelClient>,
 }
 
 impl OpenAiCompatibleRouter {
-    pub fn new(
-        endpoint: String,
-        model: String,
-        api_key: Option<String>,
-        backend_name: String,
-    ) -> Self {
-        let endpoint = crate::chat_completions_url(&endpoint);
-        Self {
-            client: Client::new(),
-            endpoint,
-            model,
-            api_key,
-            backend_name,
-        }
+    pub fn new(registry: Arc<Registry>, client: Arc<dyn StructuredModelClient>) -> Self {
+        Self { registry, client }
     }
 }
 
@@ -132,33 +120,41 @@ impl RouterModel for OpenAiCompatibleRouter {
         request: &DecisionRequest,
         workflows: &[WorkflowManifest],
     ) -> Result<Vec<RankedWorkflow>> {
+        if workflows.is_empty() {
+            bail!("registry contains no workflows");
+        }
         let candidates: Vec<_> = workflows.iter().map(|w| json!({
             "workflow_id":w.id,"version":w.version,"description":w.description,"triggers":w.triggers,"risk_level":w.risk_level
         })).collect();
-        let prompt = json!({
-            "task": request.task, "context": request.context, "capabilities": request.capabilities,
-            "candidates": candidates,
-            "required_output": {"workflow_id":"candidate id","confidence":"number 0..1","reasons":["short reason"]}
+        let schema = json!({
+            "type":"object",
+            "additionalProperties":false,
+            "required":["workflow_id","confidence","reasons"],
+            "properties":{
+                "workflow_id":{"type":"string","enum":workflows.iter().map(|workflow| workflow.id.as_str()).collect::<Vec<_>>()},
+                "confidence":{"type":"number","minimum":0,"maximum":1},
+                "reasons":{"type":"array","maxItems":4,"items":{"type":"string","minLength":1,"maxLength":200}}
+            }
         });
-        let body = json!({"model":self.model,"temperature":0,"response_format":{"type":"json_object"},"messages":[
-            {"role":"system","content":"Select exactly one supplied workflow. Never invent IDs. Return only the required JSON object."},
-            {"role":"user","content":serde_json::to_string(&prompt)?}
-        ]});
-        let mut builder = self
-            .client
-            .post(&self.endpoint)
-            .timeout(Duration::from_secs(10))
-            .json(&body);
-        if let Some(key) = &self.api_key {
-            builder = builder.bearer_auth(key);
-        }
-        let response: Value = builder.send().await?.error_for_status()?.json().await?;
-        let content = response
-            .pointer("/choices/0/message/content")
-            .and_then(Value::as_str)
-            .context("model response lacks choices[0].message.content")?;
-        let selected: Value =
-            serde_json::from_str(content).context("model output is not valid JSON")?;
+        let selected = complete_budgeted(
+            &self.registry,
+            self.client.as_ref(),
+            &StructuredRequest {
+                stage: QualityModelStage::Flash,
+                system_prompt: ROUTER_SYSTEM_PROMPT,
+                payload: json!({
+                    "output_schema":schema,
+                    "task":request.task,
+                    "context":request.context,
+                    "capabilities":request.capabilities,
+                    "candidates":candidates,
+                }),
+                max_tokens: 512,
+            },
+            Utc::now(),
+        )
+        .await?
+        .value;
         let id = selected
             .get("workflow_id")
             .and_then(Value::as_str)
@@ -177,14 +173,20 @@ impl RouterModel for OpenAiCompatibleRouter {
         let reasons = selected
             .get("reasons")
             .and_then(Value::as_array)
-            .map(|values| {
-                values
-                    .iter()
-                    .filter_map(Value::as_str)
-                    .map(str::to_owned)
-                    .collect()
+            .context("missing reasons")?;
+        if reasons.len() > 4 {
+            bail!("model supplied too many reasons");
+        }
+        let reasons = reasons
+            .iter()
+            .map(|reason| {
+                let reason = reason.as_str().context("model reason is not a string")?;
+                if reason.is_empty() || reason.chars().count() > 200 {
+                    bail!("model reason violates local bounds");
+                }
+                Ok(reason.to_owned())
             })
-            .unwrap_or_default();
+            .collect::<Result<Vec<_>>>()?;
         Ok(vec![RankedWorkflow {
             workflow_id: workflow.id.clone(),
             version: workflow.version.clone(),
@@ -193,7 +195,7 @@ impl RouterModel for OpenAiCompatibleRouter {
         }])
     }
     fn name(&self) -> &str {
-        &self.backend_name
+        "local-openai-compatible"
     }
 }
 
@@ -293,7 +295,35 @@ fn is_cjk(ch: char) -> bool {
 mod tests {
     use super::*;
     use crate::builtins;
+    use crate::quality::{StructuredModelClient, StructuredRequest, StructuredResponse};
+    use crate::Registry;
     use async_trait::async_trait;
+    use cerebellum_core::{ModelTokenUsage, QualityModelStage};
+    use std::sync::{Arc, Mutex};
+    use tempfile::tempdir;
+
+    struct FakeStructuredRouter {
+        captured: Arc<Mutex<Option<StructuredRequest>>>,
+    }
+
+    #[async_trait]
+    impl StructuredModelClient for FakeStructuredRouter {
+        async fn complete(&self, request: &StructuredRequest) -> Result<StructuredResponse> {
+            *self.captured.lock().unwrap() = Some(request.clone());
+            let value = json!({
+                "workflow_id": "code-review",
+                "confidence": 0.9,
+                "reasons": ["matches review task"]
+            });
+            Ok(StructuredResponse {
+                model_id: "ornith-1.5-9b".into(),
+                system_fingerprint: "a".repeat(64),
+                raw_content: value.to_string(),
+                value,
+                usage: ModelTokenUsage::default(),
+            })
+        }
+    }
 
     struct BrokenRouter;
     #[async_trait]
@@ -354,6 +384,34 @@ mod tests {
         assert_eq!(output.router, "deterministic-bm25");
         assert_eq!(output.ranked[0].workflow_id, "code-review");
     }
+
+    #[tokio::test]
+    async fn local_router_uses_candidate_bounded_schema() {
+        let directory = tempdir().unwrap();
+        let registry = Arc::new(Registry::open(directory.path()).unwrap());
+        let captured = Arc::new(Mutex::new(None));
+        let client = Arc::new(FakeStructuredRouter {
+            captured: captured.clone(),
+        });
+        let router = OpenAiCompatibleRouter::new(registry, client);
+        let request = DecisionRequest {
+            task: "review this pull request".into(),
+            repository_path: None,
+            capabilities: vec![],
+            context: Value::Null,
+        };
+        let ranked = router.rank(&request, &builtins::workflows()).await.unwrap();
+        assert_eq!(ranked[0].workflow_id, "code-review");
+        let request = captured.lock().unwrap().clone().unwrap();
+        let allowed = request
+            .payload
+            .pointer("/output_schema/properties/workflow_id/enum")
+            .unwrap()
+            .as_array()
+            .unwrap();
+        assert!(allowed.iter().any(|id| id == "code-review"));
+        assert_eq!(request.stage, QualityModelStage::Flash);
+    }
     #[test]
     fn tokenizer_indexes_cjk_runs_as_bigrams() {
         let tokens = tokenize("修复parser的crash问题");
