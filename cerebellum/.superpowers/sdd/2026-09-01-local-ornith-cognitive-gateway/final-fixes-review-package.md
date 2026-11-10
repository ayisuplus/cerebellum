# Final fixes static review package

Final review findings: final-reviewer.md
Implementer report: final-fixes-implementer.md
Comparison: final-fix start snapshots to current working tree; no commits/staging.
Runtime note: current usage evidence is intentionally failed 14/16 because unrelated GPU PID 77456 remained at 98-100%; review code/artifact honestly and do not approve completion evidence until a fresh idle-GPU 16/16/16/16 run replaces this task-owned candidate file.

warning: in the working copy of 'deploy\docker-compose.yml', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\deploy\\docker-compose.yml" "b/deploy\\docker-compose.yml"
index 01ca42f..d001acd 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\deploy\\docker-compose.yml"
+++ "b/deploy\\docker-compose.yml"
@@ -10,19 +10,13 @@ services:
       CEREBELLUM_WEBSUB_SECRET: ${CEREBELLUM_WEBSUB_SECRET:-}
       CEREBELLUM_GITHUB_WATCHLIST: ${CEREBELLUM_GITHUB_WATCHLIST:-}
       GITHUB_TOKEN: ${GITHUB_TOKEN:-}
-      CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT: ${CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT:-}
-      CEREBELLUM_KNOWLEDGE_MODEL_NAME: ${CEREBELLUM_KNOWLEDGE_MODEL_NAME:-}
-      CEREBELLUM_KNOWLEDGE_MODEL_API_KEY: ${CEREBELLUM_KNOWLEDGE_MODEL_API_KEY:-}
-      CEREBELLUM_QUALITY_MODEL_ENABLED: ${CEREBELLUM_QUALITY_MODEL_ENABLED:-0}
+      CEREBELLUM_LOCAL_MODEL_ENABLED: ${CEREBELLUM_LOCAL_MODEL_ENABLED:-0}
+      CEREBELLUM_LOCAL_MODEL_ENDPOINT: ${CEREBELLUM_LOCAL_MODEL_ENDPOINT:-http://127.0.0.1:1234/v1}
+      CEREBELLUM_LOCAL_MODEL_NAME: ${CEREBELLUM_LOCAL_MODEL_NAME:-ornith-1.5-9b}
+      CEREBELLUM_LOCAL_MODEL_SHA256: ${CEREBELLUM_LOCAL_MODEL_SHA256:-894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da}
+      CEREBELLUM_LOCAL_MODEL_RUNTIME: ${CEREBELLUM_LOCAL_MODEL_RUNTIME:-llama.cpp-win-x86_64-nvidia-cuda12-avx2}
+      CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION: ${CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION:-2.31.2}
       CEREBELLUM_QUALITY_ENFORCEMENT: ${CEREBELLUM_QUALITY_ENFORCEMENT:-1}
-      CEREBELLUM_PRIVATE_REDACTED_EXTERNAL_PROCESSING: ${CEREBELLUM_PRIVATE_REDACTED_EXTERNAL_PROCESSING:-0}
-      CEREBELLUM_DEEPSEEK_TRAINING_OPTOUT_ATTESTED: ${CEREBELLUM_DEEPSEEK_TRAINING_OPTOUT_ATTESTED:-0}
-      DEEPSEEK_API_BASE_URL: https://api.deepseek.com
-      DEEPSEEK_API_KEY_FILE: /run/secrets/deepseek_api_key
-      DEEPSEEK_FLASH_MODEL: deepseek-v4-flash
-      DEEPSEEK_PRO_MODEL: deepseek-v4-pro
-      DEEPSEEK_DAILY_MAX_CNY: ${DEEPSEEK_DAILY_MAX_CNY:-10}
-      DEEPSEEK_PRICING_CONFIRMED_AT: ${DEEPSEEK_PRICING_CONFIRMED_AT:-}
       CEREBELLUM_META_TRAINER_ENABLED: ${CEREBELLUM_META_TRAINER_ENABLED:-0}
       CEREBELLUM_META_BASE_MODEL: ${CEREBELLUM_META_BASE_MODEL:-}
       CEREBELLUM_META_DATA_LICENSE_POLICY: ${CEREBELLUM_META_DATA_LICENSE_POLICY:-licensed-only}
warning: in the working copy of 'deploy\.env.example', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\deploy\\.env.example" "b/deploy\\.env.example"
index 6f7f8d0..4e50582 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\deploy\\.env.example"
+++ "b/deploy\\.env.example"
@@ -7,23 +7,15 @@ TAVILY_API_KEY=
 TAVILY_BASE_URL=https://api.tavily.com
 FIRECRAWL_BASE_URL=
 FIRECRAWL_API_KEY=
-CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT=
-CEREBELLUM_KNOWLEDGE_MODEL_NAME=
-CEREBELLUM_KNOWLEDGE_MODEL_API_KEY=
-
-# v3.3 DeepSeek semantic quality gate. Keep disabled until the account-level
-# model-improvement opt-out and the current official pricing have been checked.
-CEREBELLUM_QUALITY_MODEL_ENABLED=0
+# Enable only when the model runtime and daemon share the same loopback network
+# namespace. The approved pins stay explicit while the gateway defaults off.
+CEREBELLUM_LOCAL_MODEL_ENABLED=0
+CEREBELLUM_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:1234/v1
+CEREBELLUM_LOCAL_MODEL_NAME=ornith-1.5-9b
+CEREBELLUM_LOCAL_MODEL_SHA256=894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da
+CEREBELLUM_LOCAL_MODEL_RUNTIME=llama.cpp-win-x86_64-nvidia-cuda12-avx2
+CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION=2.31.2
 CEREBELLUM_QUALITY_ENFORCEMENT=1
-CEREBELLUM_PRIVATE_REDACTED_EXTERNAL_PROCESSING=0
-CEREBELLUM_DEEPSEEK_TRAINING_OPTOUT_ATTESTED=0
-DEEPSEEK_API_BASE_URL=https://api.deepseek.com
-DEEPSEEK_API_KEY_FILE=/run/secrets/deepseek_api_key
-DEEPSEEK_API_KEY_HOST_FILE=
-DEEPSEEK_FLASH_MODEL=deepseek-v4-flash
-DEEPSEEK_PRO_MODEL=deepseek-v4-pro
-DEEPSEEK_DAILY_MAX_CNY=10
-DEEPSEEK_PRICING_CONFIRMED_AT=
 CEREBELLUM_META_TRAINER_ENABLED=0
 CEREBELLUM_META_BASE_MODEL=
 CEREBELLUM_META_MODEL_ID=cerebellum-meta-controller
warning: in the working copy of 'deploy\docker-compose.deepseek.yml', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\deploy\\docker-compose.deepseek.yml" "b/deploy\\docker-compose.deepseek.yml"
index 6c97940..dcc92a0 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\deploy\\docker-compose.deepseek.yml"
+++ "b/deploy\\docker-compose.deepseek.yml"
@@ -1,8 +1,3 @@
-services:
-  cerebellum:
-    secrets:
-      - deepseek_api_key
-
-secrets:
-  deepseek_api_key:
-    file: ${DEEPSEEK_API_KEY_HOST_FILE:?set an absolute host path to the DeepSeek key file}
+# Retired compatibility filename. The local Ornith gateway needs no secret or
+# service override; keep this empty file only for old operator commands.
+services: {}
warning: in the working copy of 'admin\index.html', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\admin\\index.html" "b/admin\\index.html"
index 9792d30..33eaf18 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\admin\\index.html"
+++ "b/admin\\index.html"
@@ -72,7 +72,7 @@
 
     <section class="panel">
       <div class="panel-head">
-        <div><p class="eyebrow">DEEPSEEK QUALITY GATE</p><h2>智能数据质量</h2></div>
+        <div><p class="eyebrow">LOCAL ORNITH QUALITY GATE</p><h2>智能数据质量</h2></div>
         <button id="quality-backfill">审核历史合格记录</button>
       </div>
       <div id="quality-status" class="content muted">正在读取…</div>
warning: in the working copy of 'admin\app.js', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\admin\\app.js" "b/admin\\app.js"
index 4eb17ea..baaeff3 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\admin\\app.js"
+++ "b/admin\\app.js"
@@ -35,7 +35,7 @@ function render(acquisition){
     [acquisition.document_count,"采集文档"],[acquisition.knowledge_card_count,"知识卡"],[build?.decision_count||0,"训练决策"],[build?.replay_eval_count||0,"合格回放"],[state.quality?.pending_assessments||0,"待 Flash"],[state.quality?.pending_arbitrations||0,"待 Pro"]
   ].map(([v,k])=>`<div class="metric"><strong>${esc(v)}</strong><span>${esc(k)}</span></div>`).join("");
   const q=state.quality,usage=q?.usage;
-  document.querySelector("#quality-status").innerHTML=q?.enabled?`<div class="card"><div class="card-head"><strong>${esc(q.provider)} · ¥${Number(usage?.estimated_cny||0).toFixed(4)}/¥10 今日</strong><span class="pill">${q.enforcement_required?'enforced':'observe'}</span></div><p>Flash ${esc(q.flash_model)} · Pro ${esc(q.pro_model)} · 隔离 ${q.quarantined_records} · 合成候选 ${q.synthetic_candidates}</p><p>cache hit ${usage?.usage?.prompt_cache_hit_tokens||0} / miss ${usage?.usage?.prompt_cache_miss_tokens||0}</p></div>`:"DeepSeek 质量门禁未启用；现有确定性门禁继续工作。";
+  document.querySelector("#quality-status").innerHTML=q?.enabled?`<div class="card"><div class="card-head"><strong>${esc(q.provider)} · 本地零成本</strong><span class="pill">${q.enforcement_required?'enforced':'observe'}</span></div><p>Flash ${esc(q.flash_model)} · Pro ${esc(q.pro_model)} · 隔离 ${q.quarantined_records} · 合成候选 ${q.synthetic_candidates}</p><p>cache hit ${usage?.usage?.prompt_cache_hit_tokens||0} / miss ${usage?.usage?.prompt_cache_miss_tokens||0}</p></div>`:"本地 Ornith 质量门禁未启用；现有确定性门禁继续工作。";
   document.querySelector("#quality-models").innerHTML=state.qualityModels.length?state.qualityModels.map(v=>`<article class="card"><div class="card-head"><strong>${esc(v.model_id)}</strong><span class="pill ${['rejected','calibration'].includes(v.status)?'bad':''}">${esc(v.status)}</span></div><p class="mono">${esc(v.system_fingerprint)}<br>${esc(v.prompt_version)}</p>${v.status==='pending_approval'?`<button data-quality-model="${v.endpoint_version_id}" data-action="approve">批准首次接入</button> <button data-quality-model="${v.endpoint_version_id}" data-action="reject">拒绝</button>`:''}</article>`).join(""):"模型首次返回 fingerprint 后会在这里等待人工批准。";
   document.querySelector("#synthetic-candidates").innerHTML=state.synthetic.length?state.synthetic.map(c=>`<article class="card"><div class="card-head"><strong>${esc(c.transformation)}</strong><span class="pill ${c.status==='rejected'?'bad':''}">${esc(c.status)}</span></div><p>${esc(c.task_kind)} · ${esc(short(c.parent_hash))} · ${esc(c.verification_kind)}</p><p class="mono">${esc(c.generation_model_id)} · ${esc(c.generation_system_fingerprint)}</p>${c.status==='quarantined'?`<button data-synthetic="${c.candidate_id}" data-action="approve">人工批准</button> <button data-synthetic="${c.candidate_id}" data-action="reject">拒绝</button>`:''}</article>`).join(""):"暂无合成候选";
   document.querySelector("#draft").innerHTML=build ? `<div class="card"><div class="card-head"><strong>${esc(build.build_id)}</strong><span class="pill">draft</span></div><p>决策 ${build.decision_count} · 回放 ${build.replay_eval_count} · 拒绝 ${build.rejected_record_count}</p><p class="mono">manifest ${esc(build.manifest_hash)}<br>bundle ${esc(build.bundle_hash)}<br>expert view ${esc(build.expert_view_id)}</p></div>` : "尚未构建 Draft";
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\final-fix-baseline\cerebellum\README.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'README.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\README.md" b/README.md
index 5c137eb..be27908 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\README.md"
+++ b/README.md
@@ -172,9 +172,10 @@ cerebellum --data-dir .cerebellum rebuild-knowledge-index
 ```
 
 When enabled, the single pinned local model also performs strict-schema weak
-extraction. Invalid output, timeout, low confidence, prompt injection, PII,
-secrets, and authenticated-local documents all fall back to deterministic
-consolidation.
+extraction. Clean, scanner-safe authenticated-local content may use the literal
+loopback client. Secrets, PII, prompt injection, invalid output, timeout, and
+low confidence fall back to deterministic consolidation. Training eligibility
+remains controlled by the licence, safety, and quality gates.
 
 ## SkillOpt reference experiment
 
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\final-fix-baseline\cerebellum\docs\security.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs\security.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\docs\\security.md" "b/docs\\security.md"
index 418fb20..48c01e7 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\docs\\security.md"
+++ "b/docs\\security.md"
@@ -53,8 +53,10 @@
   receives a sanitized environment; cookies and browser profiles never enter
   HTTP, SQLite, CAS, prompts, or logs.
 - Prompt-injection, PII, and secret detectors mark documents unsafe, redact
-  cleaned text, suppress raw retention, and prohibit training. Weak model
-  extraction is skipped for sensitive or authenticated-local material.
+  cleaned text, suppress raw retention, and prohibit training. Clean,
+  scanner-safe authenticated-local content may use the literal-loopback model;
+  secrets, PII, prompt injection, invalid output, timeout, and low confidence
+  force deterministic fallback.
 - Public readability is not training permission. Knowledge and decision text
   enter meta-training only when the source license, explicit authorization,
   model-provider terms, redaction, and safety flags all allow it.
@@ -62,9 +64,9 @@
   credentials, query strings, fragments, redirects, proxies, API keys, tools,
   thinking options and hosted fallbacks are rejected or absent.
 - Local inference does not require `external_processing=redacted` and does not
-  grant training eligibility. Deterministic licence, credential, PII,
-  prompt-injection, output-echo and approval checks still run first or fail
-  closed; authenticated browser/OpenCLI material remains ineligible.
+  grant training eligibility. Licence, safety, and quality gates remain
+  authoritative; credential, PII, prompt-injection, output-echo and approval
+  checks still run first or fail closed.
 - Model verdicts are soft denials only: they may veto or quarantine but cannot
   override licenses, external-processing permission, objective feedback, or
   hard safety checks. Exact fingerprints require activation before their
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\final-fix-baseline\cerebellum\docs\deployment-v2.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs\deployment-v2.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\final-fix-baseline\cerebellum\crates\cerebellum-app\src\knowledge.rs', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'crates\cerebellum-app\src\knowledge.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\crates\\cerebellum-app\\src\\knowledge.rs" "b/crates\\cerebellum-app\\src\\knowledge.rs"
index 7c8add6..f767218 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\crates\\cerebellum-app\\src\\knowledge.rs"
+++ "b/crates\\cerebellum-app\\src\\knowledge.rs"
@@ -2,9 +2,9 @@ use crate::Registry;
 use crate::quality::{StructuredModelClient, StructuredRequest, complete_budgeted};
 use anyhow::{Context, Result, bail};
 use cerebellum_core::{
-    DataClassification, DocumentEnvelope, EvidenceRelationship, ExternalProcessingPermission,
-    KnowledgeCard, KnowledgeClaim, KnowledgeEvidenceRef, KnowledgeScores, KnowledgeStatus,
-    MetaDecisionTrace, MetaTaskKind, SCHEMA_VERSION, canonical_json_hash,
+    DocumentEnvelope, EvidenceRelationship, KnowledgeCard, KnowledgeClaim, KnowledgeEvidenceRef,
+    KnowledgeScores, KnowledgeStatus, MetaDecisionTrace, MetaTaskKind, SCHEMA_VERSION,
+    canonical_json_hash,
 };
 use chrono::Utc;
 use serde::{Deserialize, Serialize};
@@ -337,6 +337,9 @@ fn record_meta_trace(
     prompt_injection_detected: bool,
     fallback_used: bool,
 ) -> Result<()> {
+    let source_policy = registry
+        .get_source_policy(document.source_policy_id)?
+        .context("source policy not found for knowledge trace")?;
     let source_domain = Url::parse(&document.canonical_url)
         .ok()
         .and_then(|url| url.host_str().map(str::to_owned))
@@ -384,8 +387,8 @@ fn record_meta_trace(
             && !document.secret_detected,
         policy_violations: 0,
         prompt_injection_detected,
-        data_classification: DataClassification::Public,
-        external_processing: ExternalProcessingPermission::Redacted,
+        data_classification: source_policy.data_classification,
+        external_processing: source_policy.external_processing,
         redaction_attestation_hash: None,
         created_at: Utc::now(),
     })?;
@@ -530,10 +533,11 @@ mod tests {
     use crate::quality::StructuredResponse;
     use async_trait::async_trait;
     use cerebellum_core::{
-        AcquisitionMethod, CreateSourcePolicyRequest, DocumentRights, ModelTokenUsage,
-        SourceAccessMode, SourceKind,
+        AcquisitionMethod, CreateSourcePolicyRequest, DataClassification, DocumentRights,
+        ExternalProcessingPermission, ModelTokenUsage, SourceAccessMode, SourceKind,
     };
     use chrono::Duration;
+    use rusqlite::params;
     use std::sync::{
         Arc,
         atomic::{AtomicUsize, Ordering},
@@ -799,6 +803,22 @@ mod tests {
         .unwrap();
         assert!(!clean_outcome.model_fallback_used);
         assert_eq!(calls.load(Ordering::SeqCst), 1);
+        let trace_json: String = registry
+            .conn
+            .lock()
+            .unwrap()
+            .query_row(
+                "SELECT trace_json FROM meta_decision_traces WHERE input_hash=?1",
+                params![clean.cleaned_content_hash],
+                |row| row.get(0),
+            )
+            .unwrap();
+        let trace: MetaDecisionTrace = serde_json::from_str(&trace_json).unwrap();
+        assert_eq!(trace.data_classification, DataClassification::Private);
+        assert_eq!(
+            trace.external_processing,
+            ExternalProcessingPermission::Denied
+        );
 
         let secret_content = "A separate local document contains protected material.";
         let secret = save_document(
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\final-fix-baseline\cerebellum\crates\cerebellum-app\src\quality.rs', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'crates\cerebellum-app\src\quality.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\crates\\cerebellum-app\\src\\quality.rs" "b/crates\\cerebellum-app\\src\\quality.rs"
index 5640d4e..d4fd08a 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\cerebellum\\crates\\cerebellum-app\\src\\quality.rs"
+++ "b/crates\\cerebellum-app\\src\\quality.rs"
@@ -8,7 +8,7 @@ use cerebellum_core::{
     ModelEndpointStatus, ModelEndpointVersion, ModelTokenUsage, ModelUsageLedger,
     ProviderPricingPolicy, QualityDimensions, QualityIssueCode, QualityModelStage, QualityStatus,
     QualitySubjectKind, QualityVerdict, RedactionAttestation, ReviewQualityModelRequest,
-    ReviewSyntheticCandidateRequest, SCHEMA_VERSION, SyntheticCandidateStatus,
+    ReviewSyntheticCandidateRequest, SCHEMA_VERSION, SourcePolicy, SyntheticCandidateStatus,
     SyntheticTrainingCandidate, SyntheticTransformation, SyntheticVerificationKind,
     canonical_json_hash, validate_data_quality_assessment, validate_dataset_quality_report,
     validate_model_endpoint_version, validate_provider_pricing_policy,
@@ -64,7 +64,10 @@ pub struct StructuredRequest {
 #[cfg(test)]
 mod tests {
     use super::*;
-    use cerebellum_core::{MetaTaskKind, SCHEMA_VERSION};
+    use cerebellum_core::{
+        CreateSourcePolicyRequest, EvidenceRelationship, KnowledgeEvidenceRef, KnowledgeScores,
+        KnowledgeStatus, MetaTaskKind, SCHEMA_VERSION, SourceAccessMode, SourceKind,
+    };
     use std::sync::{
         Arc,
         atomic::{AtomicUsize, Ordering},
@@ -289,6 +292,118 @@ mod tests {
         assert_eq!(calls.load(Ordering::SeqCst), 0);
     }
 
+    #[test]
+    fn knowledge_card_quality_subject_uses_most_restrictive_evidence_provenance() {
+        let directory = tempdir().unwrap();
+        let registry = Registry::open(directory.path()).unwrap();
+        let now = Utc::now();
+        let evidence = [
+            (
+                DataClassification::Public,
+                ExternalProcessingPermission::Redacted,
+            ),
+            (
+                DataClassification::Internal,
+                ExternalProcessingPermission::Redacted,
+            ),
+            (
+                DataClassification::Private,
+                ExternalProcessingPermission::Denied,
+            ),
+        ]
+        .into_iter()
+        .enumerate()
+        .map(|(index, (classification, permission))| {
+            let domain = format!("provenance-{index}.example");
+            let policy = registry
+                .create_source_policy(&CreateSourcePolicyRequest {
+                    name: format!("provenance-{index}"),
+                    kind: SourceKind::Http,
+                    base_url: format!("https://{domain}/"),
+                    access_mode: SourceAccessMode::Public,
+                    allowed_domains: vec![domain.clone()],
+                    obey_robots: true,
+                    max_depth: 1,
+                    max_pages_per_run: 1,
+                    rate_limit_per_minute: 1,
+                    raw_retention_days: 1,
+                    training_license: None,
+                    model_terms_allow_training: false,
+                    auth_secret_ref: None,
+                    enabled: true,
+                    data_classification: classification,
+                    external_processing: permission,
+                })
+                .unwrap();
+            let document_id = Uuid::new_v4();
+            let content_hash = hash_bytes(format!("evidence-{index}").as_bytes());
+            registry
+                .conn
+                .lock()
+                .unwrap()
+                .execute(
+                    "INSERT INTO documents(
+                       id,source_policy_id,canonical_url,cleaned_content_hash,raw_content_hash,
+                       raw_expires_at,training_eligible,tombstoned,document_json,content_hash,created_at
+                     ) VALUES(?1,?2,?3,?4,NULL,?5,0,0,'{}',?4,?6)",
+                    params![
+                        document_id.to_string(),
+                        policy.policy_id.to_string(),
+                        format!("https://{domain}/article"),
+                        content_hash,
+                        now.to_rfc3339(),
+                        now.to_rfc3339(),
+                    ],
+                )
+                .unwrap();
+            KnowledgeEvidenceRef {
+                document_id,
+                canonical_url: format!("https://{domain}/article"),
+                content_hash,
+                excerpt: None,
+                relationship: EvidenceRelationship::Supports,
+                observed_at: now,
+            }
+        })
+        .collect();
+        let card = KnowledgeCard {
+            schema_version: SCHEMA_VERSION.into(),
+            card_id: Uuid::new_v4(),
+            revision: 1,
+            topic_ids: vec![],
+            title: "Mixed provenance".into(),
+            summary: "A card backed by public, internal, and private evidence.".into(),
+            entities: vec![],
+            claims: vec![],
+            evidence,
+            status: KnowledgeStatus::Corroborated,
+            published_at: None,
+            observed_at: now,
+            valid_until: None,
+            supersedes: None,
+            model_id: "deterministic-v1".into(),
+            prompt_hash: hash_bytes(b"mixed-provenance-prompt"),
+            scores: KnowledgeScores {
+                relevance: 1.0,
+                novelty: 1.0,
+                source_reliability: 1.0,
+                extraction_completeness: 1.0,
+                confidence: 1.0,
+                risk: 0.0,
+                cost: 0.0,
+            },
+            training_eligible: false,
+            created_at: now,
+        };
+        registry.save_knowledge_card(&card).unwrap();
+
+        let subject = registry
+            .load_quality_subject(QualitySubjectKind::KnowledgeCard, &card.card_id.to_string())
+            .unwrap();
+        assert_eq!(subject.classification, DataClassification::Private);
+        assert_eq!(subject.permission, ExternalProcessingPermission::Denied);
+    }
+
     #[tokio::test]
     async fn knowledge_card_is_promoted_after_clean_quality_pass() {
         let directory = tempdir().unwrap();
@@ -1913,16 +2028,42 @@ impl Registry {
                     .context("knowledge card quality subject not found")?;
                 let card: KnowledgeCard = serde_json::from_str(&value)?;
                 let hash = knowledge_card_quality_hash(&card);
+                let mut classification = DataClassification::Public;
+                let mut permission = ExternalProcessingPermission::Redacted;
+                for evidence in &card.evidence {
+                    let policy_json: String = conn
+                        .query_row(
+                            "SELECT sp.policy_json FROM documents d
+                             JOIN source_policies sp ON sp.id=d.source_policy_id
+                             WHERE d.id=?1",
+                            params![evidence.document_id.to_string()],
+                            |row| row.get(0),
+                        )
+                        .context("knowledge card evidence source policy not found")?;
+                    let policy: SourcePolicy = serde_json::from_str(&policy_json)?;
+                    classification = match (classification, policy.data_classification) {
+                        (DataClassification::Private, _) | (_, DataClassification::Private) => {
+                            DataClassification::Private
+                        }
+                        (DataClassification::Internal, _) | (_, DataClassification::Internal) => {
+                            DataClassification::Internal
+                        }
+                        _ => DataClassification::Public,
+                    };
+                    if policy.external_processing == ExternalProcessingPermission::Denied {
+                        permission = ExternalProcessingPermission::Denied;
+                    }
+                }
                 Ok(QualitySubject {
                     kind,
                     id: id.into(),
                     hash,
                     task_kind: None,
-                    // Cards only ever derive from externally processable public
-                    // content: knowledge.rs refuses AuthenticatedLocal and
-                    // non-Redacted sources before a card can exist.
-                    classification: DataClassification::Public,
-                    permission: ExternalProcessingPermission::Redacted,
+                    // Clean authenticated-local evidence may use literal loopback;
+                    // secret/PII/injection/invalid/timeout/low-confidence paths fall
+                    // back, while licence, safety, and quality gates retain authority.
+                    classification,
+                    permission,
                     // The deterministic preconditions for eligibility promotion
                     // (NOT the flag itself — requiring the flag here would make
                     // unpromoted cards unassessable, which is circular). The
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\final-fix-baseline\coordination\work\lm-studio-ornith-compatibility\probe.ps1', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of '..\.coordination\work\lm-studio-ornith-compatibility\probe.ps1', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1" "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1"
index 9f21f38..bff8bd5 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1"
+++ "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1"
@@ -47,6 +47,75 @@ function Get-GpuSnapshot {
     })
 }
 
+function ConvertTo-UsageInteger {
+    param(
+        [object]$Value,
+        [string]$Name,
+        [bool]$Required = $true
+    )
+    if ($null -eq $Value) {
+        if ($Required) { throw "response.usage.$Name is required" }
+        return [uint64]0
+    }
+    $numeric = $Value -is [byte] -or $Value -is [sbyte] -or
+        $Value -is [int16] -or $Value -is [uint16] -or
+        $Value -is [int32] -or $Value -is [uint32] -or
+        $Value -is [int64] -or $Value -is [uint64] -or
+        $Value -is [single] -or $Value -is [double] -or $Value -is [decimal]
+    $number = if ($numeric) { [double]$Value } else { [double]::NaN }
+    if (-not $numeric -or [double]::IsNaN($number) -or [double]::IsInfinity($number) -or
+        $number -lt 0 -or [math]::Truncate($number) -ne $number) {
+        throw "response.usage.$Name must be a non-negative integer"
+    }
+    try {
+        return [uint64]$Value
+    } catch {
+        throw "response.usage.$Name is outside the supported integer range"
+    }
+}
+
+function Read-Usage {
+    param([object]$Response)
+    if ($null -eq $Response.usage) { throw 'response.usage is required' }
+    $usage = $Response.usage
+    $promptTokens = ConvertTo-UsageInteger $usage.prompt_tokens 'prompt_tokens'
+    $completionTokens = ConvertTo-UsageInteger $usage.completion_tokens 'completion_tokens'
+    $totalTokens = ConvertTo-UsageInteger $usage.total_tokens 'total_tokens'
+    $cacheHitValue = $usage.prompt_cache_hit_tokens
+    if ($null -eq $cacheHitValue -and $null -ne $usage.prompt_tokens_details) {
+        $cacheHitValue = $usage.prompt_tokens_details.cached_tokens
+    }
+    $promptCacheHitTokens = ConvertTo-UsageInteger $cacheHitValue 'prompt_cache_hit_tokens' $false
+    if ($promptCacheHitTokens -gt $promptTokens) {
+        throw 'response.usage cached prompt tokens exceed prompt_tokens'
+    }
+    $cacheMissValue = $usage.prompt_cache_miss_tokens
+    $promptCacheMissTokens = if ($null -eq $cacheMissValue) {
+        $promptTokens - $promptCacheHitTokens
+    } else {
+        ConvertTo-UsageInteger $cacheMissValue 'prompt_cache_miss_tokens'
+    }
+    if ($promptCacheHitTokens + $promptCacheMissTokens -ne $promptTokens) {
+        throw 'response.usage cache hit and miss tokens do not equal prompt_tokens'
+    }
+    $reasoningValue = $usage.reasoning_tokens
+    if ($null -eq $reasoningValue -and $null -ne $usage.completion_tokens_details) {
+        $reasoningValue = $usage.completion_tokens_details.reasoning_tokens
+    }
+    $reasoningTokens = ConvertTo-UsageInteger $reasoningValue 'reasoning_tokens' $false
+    if ($totalTokens -ne $promptTokens + $completionTokens) {
+        throw 'response.usage total_tokens does not equal prompt_tokens plus completion_tokens'
+    }
+    [ordered]@{
+        promptTokens = $promptTokens
+        promptCacheHitTokens = $promptCacheHitTokens
+        promptCacheMissTokens = $promptCacheMissTokens
+        completionTokens = $completionTokens
+        reasoningTokens = $reasoningTokens
+        totalTokens = $totalTokens
+    }
+}
+
 $gpuBefore = Get-GpuSnapshot
 
 foreach ($run in 1..$Runs) {
@@ -78,6 +147,7 @@ foreach ($run in 1..$Runs) {
         try {
             $response = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 12 -Compress) -TimeoutSec 45
             $started.Stop()
+            $usage = Read-Usage $response
             $content = [string]$response.choices[0].message.content
             $selected = $content | ConvertFrom-Json
             $propertyNames = @($selected.PSObject.Properties.Name)
@@ -117,6 +187,13 @@ foreach ($run in 1..$Runs) {
                 schemaValid = $schemaValid
                 exact = $exact
                 accepted = $legalId -and $validConfidence
+                promptTokens = $usage.promptTokens
+                promptCacheHitTokens = $usage.promptCacheHitTokens
+                promptCacheMissTokens = $usage.promptCacheMissTokens
+                completionTokens = $usage.completionTokens
+                reasoningTokens = $usage.reasoningTokens
+                totalTokens = $usage.totalTokens
+                usageValid = $true
                 reasoningFieldPresent = $null -ne $response.choices[0].message.reasoning_content
                 error = $null
             })
@@ -135,6 +212,13 @@ foreach ($run in 1..$Runs) {
                 schemaValid = $false
                 exact = $false
                 accepted = $false
+                promptTokens = $null
+                promptCacheHitTokens = $null
+                promptCacheMissTokens = $null
+                completionTokens = $null
+                reasoningTokens = $null
+                totalTokens = $null
+                usageValid = $false
                 reasoningFieldPresent = $false
                 error = $_.Exception.Message
             })
@@ -145,7 +229,7 @@ foreach ($run in 1..$Runs) {
 $gpuAfter = Get-GpuSnapshot
 $latencies = @($results | Where-Object accepted | ForEach-Object elapsedMs | Sort-Object)
 $summary = [ordered]@{
-    schemaVersion = 2
+    schemaVersion = 3
     backend = $Backend
     endpoint = $Endpoint
     model = $Model
@@ -160,9 +244,16 @@ $summary = [ordered]@{
     total = $results.Count
     accepted = @($results | Where-Object accepted).Count
     schemaValid = @($results | Where-Object schemaValid).Count
+    usageValid = @($results | Where-Object usageValid).Count
     exact = @($results | Where-Object exact).Count
     validJson = @($results | Where-Object validJson).Count
     reasoningFieldPresent = @($results | Where-Object reasoningFieldPresent).Count
+    promptTokens = [uint64](($results | Where-Object usageValid | ForEach-Object { $_.promptTokens } | Measure-Object -Sum).Sum)
+    promptCacheHitTokens = [uint64](($results | Where-Object usageValid | ForEach-Object { $_.promptCacheHitTokens } | Measure-Object -Sum).Sum)
+    promptCacheMissTokens = [uint64](($results | Where-Object usageValid | ForEach-Object { $_.promptCacheMissTokens } | Measure-Object -Sum).Sum)
+    completionTokens = [uint64](($results | Where-Object usageValid | ForEach-Object { $_.completionTokens } | Measure-Object -Sum).Sum)
+    reasoningTokens = [uint64](($results | Where-Object usageValid | ForEach-Object { $_.reasoningTokens } | Measure-Object -Sum).Sum)
+    totalTokens = [uint64](($results | Where-Object usageValid | ForEach-Object { $_.totalTokens } | Measure-Object -Sum).Sum)
     meanLatencyMs = if ($latencies.Count) { [math]::Round(($latencies | Measure-Object -Average).Average) } else { $null }
     medianLatencyMs = if ($latencies.Count) { $latencies[[math]::Floor($latencies.Count / 2)] } else { $null }
     maxLatencyMs = if ($latencies.Count) { $latencies[-1] } else { $null }
@@ -171,4 +262,5 @@ $summary = [ordered]@{
 
 $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding utf8
 $summary | ConvertTo-Json -Depth 4
-if ($summary.accepted -ne $summary.total -or $summary.schemaValid -ne $summary.total) { exit 1 }
+if ($summary.accepted -ne $summary.total -or $summary.schemaValid -ne $summary.total -or
+    $summary.usageValid -ne $summary.total) { exit 1 }
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-usage-probe.json" "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-usage-probe.json"
index e69de29..110e60c 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\final-fix-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-usage-probe.json"
+++ "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-usage-probe.json"
@@ -0,0 +1,412 @@
+﻿{
+    "schemaVersion":  3,
+    "backend":  "lm-studio-llama.cpp",
+    "endpoint":  "http://127.0.0.1:1234/v1/chat/completions",
+    "model":  "ornith-1.5-9b",
+    "artifactSha256":  "894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da",
+    "runtimeName":  "llama.cpp-win-x86_64-nvidia-cuda12-avx2",
+    "runtimeVersion":  "2.31.2",
+    "inputSha256":  "7f5a04078e7ead6f137a622f46ae00e545b2b0670dc7fbda296df41e6bee7427",
+    "gpuBefore":  {
+                      "index":  0,
+                      "name":  "NVIDIA GeForce RTX 5090",
+                      "memoryUsedMiB":  31283,
+                      "memoryTotalMiB":  32607,
+                      "utilizationPercent":  23
+                  },
+    "gpuAfter":  {
+                     "index":  0,
+                     "name":  "NVIDIA GeForce RTX 5090",
+                     "memoryUsedMiB":  31321,
+                     "memoryTotalMiB":  32607,
+                     "utilizationPercent":  100
+                 },
+    "runs":  2,
+    "casesPerRun":  8,
+    "total":  16,
+    "accepted":  14,
+    "schemaValid":  14,
+    "usageValid":  14,
+    "exact":  10,
+    "validJson":  14,
+    "reasoningFieldPresent":  14,
+    "promptTokens":  3818,
+    "promptCacheHitTokens":  0,
+    "promptCacheMissTokens":  3818,
+    "completionTokens":  5692,
+    "reasoningTokens":  4838,
+    "totalTokens":  9510,
+    "meanLatencyMs":  18519,
+    "medianLatencyMs":  18999,
+    "maxLatencyMs":  37258,
+    "results":  [
+                    {
+                        "run":  1,
+                        "case":  "bugfix-en",
+                        "expected":  "bugfix",
+                        "selected":  "bugfix",
+                        "confidence":  0.98,
+                        "elapsedMs":  20191,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  276,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  276,
+                        "completionTokens":  251,
+                        "reasoningTokens":  197,
+                        "totalTokens":  527,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "bugfix-zh",
+                        "expected":  "bugfix",
+                        "selected":  null,
+                        "confidence":  null,
+                        "elapsedMs":  45015,
+                        "validJson":  false,
+                        "legalId":  false,
+                        "validConfidence":  false,
+                        "schemaValid":  false,
+                        "exact":  false,
+                        "accepted":  false,
+                        "promptTokens":  null,
+                        "promptCacheHitTokens":  null,
+                        "promptCacheMissTokens":  null,
+                        "completionTokens":  null,
+                        "reasoningTokens":  null,
+                        "totalTokens":  null,
+                        "usageValid":  false,
+                        "reasoningFieldPresent":  false,
+                        "error":  "The request was aborted: The operation has timed out."
+                    },
+                    {
+                        "run":  1,
+                        "case":  "feature-en",
+                        "expected":  "feature",
+                        "selected":  "feature",
+                        "confidence":  0.95,
+                        "elapsedMs":  6412,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  274,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  274,
+                        "completionTokens":  105,
+                        "reasoningTokens":  58,
+                        "totalTokens":  379,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "feature-zh",
+                        "expected":  "feature",
+                        "selected":  "code-review",
+                        "confidence":  0.2,
+                        "elapsedMs":  37258,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "promptTokens":  270,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  270,
+                        "completionTokens":  657,
+                        "reasoningTokens":  593,
+                        "totalTokens":  927,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "review-en",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.96,
+                        "elapsedMs":  15818,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  275,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  275,
+                        "completionTokens":  387,
+                        "reasoningTokens":  304,
+                        "totalTokens":  662,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "review-zh",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.3,
+                        "elapsedMs":  26793,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  270,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  270,
+                        "completionTokens":  530,
+                        "reasoningTokens":  478,
+                        "totalTokens":  800,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "premerge-en",
+                        "expected":  "pre-merge",
+                        "selected":  "pre-merge",
+                        "confidence":  1,
+                        "elapsedMs":  10790,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  275,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  275,
+                        "completionTokens":  283,
+                        "reasoningTokens":  216,
+                        "totalTokens":  558,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "premerge-zh",
+                        "expected":  "pre-merge",
+                        "selected":  "code-review",
+                        "confidence":  0.4,
+                        "elapsedMs":  26619,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "promptTokens":  269,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  269,
+                        "completionTokens":  633,
+                        "reasoningTokens":  573,
+                        "totalTokens":  902,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "bugfix-en",
+                        "expected":  "bugfix",
+                        "selected":  "bugfix",
+                        "confidence":  0.98,
+                        "elapsedMs":  8023,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  276,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  276,
+                        "completionTokens":  251,
+                        "reasoningTokens":  197,
+                        "totalTokens":  527,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "bugfix-zh",
+                        "expected":  "bugfix",
+                        "selected":  null,
+                        "confidence":  null,
+                        "elapsedMs":  45009,
+                        "validJson":  false,
+                        "legalId":  false,
+                        "validConfidence":  false,
+                        "schemaValid":  false,
+                        "exact":  false,
+                        "accepted":  false,
+                        "promptTokens":  null,
+                        "promptCacheHitTokens":  null,
+                        "promptCacheMissTokens":  null,
+                        "completionTokens":  null,
+                        "reasoningTokens":  null,
+                        "totalTokens":  null,
+                        "usageValid":  false,
+                        "reasoningFieldPresent":  false,
+                        "error":  "The request was aborted: The operation has timed out."
+                    },
+                    {
+                        "run":  2,
+                        "case":  "feature-en",
+                        "expected":  "feature",
+                        "selected":  "feature",
+                        "confidence":  0.95,
+                        "elapsedMs":  5210,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  274,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  274,
+                        "completionTokens":  105,
+                        "reasoningTokens":  58,
+                        "totalTokens":  379,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "feature-zh",
+                        "expected":  "feature",
+                        "selected":  "code-review",
+                        "confidence":  0.2,
+                        "elapsedMs":  26936,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "promptTokens":  270,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  270,
+                        "completionTokens":  657,
+                        "reasoningTokens":  593,
+                        "totalTokens":  927,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "review-en",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.96,
+                        "elapsedMs":  13465,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  275,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  275,
+                        "completionTokens":  387,
+                        "reasoningTokens":  304,
+                        "totalTokens":  662,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "review-zh",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.3,
+                        "elapsedMs":  18999,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  270,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  270,
+                        "completionTokens":  530,
+                        "reasoningTokens":  478,
+                        "totalTokens":  800,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "premerge-en",
+                        "expected":  "pre-merge",
+                        "selected":  "pre-merge",
+                        "confidence":  1,
+                        "elapsedMs":  8058,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "promptTokens":  275,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  275,
+                        "completionTokens":  283,
+                        "reasoningTokens":  216,
+                        "totalTokens":  558,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "premerge-zh",
+                        "expected":  "pre-merge",
+                        "selected":  "code-review",
+                        "confidence":  0.4,
+                        "elapsedMs":  34689,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "promptTokens":  269,
+                        "promptCacheHitTokens":  0,
+                        "promptCacheMissTokens":  269,
+                        "completionTokens":  633,
+                        "reasoningTokens":  573,
+                        "totalTokens":  902,
+                        "usageValid":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    }
+                ]
+}
