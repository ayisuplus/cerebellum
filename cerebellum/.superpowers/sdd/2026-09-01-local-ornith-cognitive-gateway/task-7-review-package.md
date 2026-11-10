# Task 7 review package

Task brief: task-7-brief.md
Implementer report: task-7-implementer.md
Comparison: Task 7 artifact snapshots to current working tree; no commits or staging.
Integration correction: exact cargo-fmt-check formatting hunks were applied with apply_patch only to config.rs, lib.rs, local_model.rs, quality.rs, and router.rs; no semantic source change, and fresh full gates passed.

warning: in the working copy of 'README.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\README.md" b/README.md
index e6e474d..5c137eb 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\README.md"
+++ b/README.md
@@ -24,8 +24,8 @@ Learning traces -> daily Dataset Draft -> immutable Snapshot -> manual start
         -> MoE-ready expert views -> temporary AutoDL QLoRA worker
         -> Router + independent expert candidates -> shadow/canary/rollback
 
-Eligible records -> deterministic privacy/license gate -> DeepSeek Flash review
-        -> Pro arbitration/audit -> bounded synthetic candidates -> verified Draft
+Eligible records -> deterministic privacy/license gate -> local Ornith screening
+        -> challenge/audit -> bounded synthetic candidates -> verified Draft
 ```
 
 The current MVP includes:
@@ -71,9 +71,9 @@ The current MVP includes:
 - Request-level Top-1 Routed LoRA over a frozen base model: deterministic
   expert assignment, shared/router/domain/routing-negative shards, independent
   Router/Shared/Expert versions, objective release gates and dense fallback.
-- DeepSeek Flash/Pro semantic quality gates with explicit external-processing
-  permission, local redaction attestations, fingerprint approval, atomic daily
-  CNY budgeting, non-recursive synthetic lineage and Pro-audited Draft promotion.
+- One pinned local Ornith model for strict-schema routing, extraction, semantic
+  screening/challenge and bounded synthesis, with zero monetary model cost,
+  fingerprint approval and Pro-stage audited Draft promotion.
 
 ## Repository layout
 
@@ -130,8 +130,9 @@ The decoupled dataset factory and on-demand AutoDL lifecycle are documented in
 [docs/dataset-factory-v3.1.md](docs/dataset-factory-v3.1.md).
 The MoE-ready dataset and request-routed LoRA lifecycle are documented in
 [docs/routed-lora-moe-v3.2.md](docs/routed-lora-moe-v3.2.md).
-The DeepSeek quality and synthesis lifecycle is documented in
-[docs/deepseek-quality-v3.3.md](docs/deepseek-quality-v3.3.md).
+The active local Ornith quality and synthesis lifecycle is documented in
+[docs/local-ornith-quality-v3.4.md](docs/local-ornith-quality-v3.4.md). The
+former DeepSeek protocol remains as [historical v3.3 documentation](docs/deepseek-quality-v3.3.md).
 
 ## Dataset factory and on-demand training
 
@@ -170,11 +171,10 @@ Knowledge remains usable without a model. SQLite FTS5 and the local
 cerebellum --data-dir .cerebellum rebuild-knowledge-index
 ```
 
-An optional OpenAI-compatible extractor is enabled only when both
-`CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT` and
-`CEREBELLUM_KNOWLEDGE_MODEL_NAME` are present. Invalid JSON, timeout, low
-confidence, prompt injection, PII, secrets, and authenticated-local documents
-all fall back to deterministic consolidation.
+When enabled, the single pinned local model also performs strict-schema weak
+extraction. Invalid output, timeout, low confidence, prompt injection, PII,
+secrets, and authenticated-local documents all fall back to deterministic
+consolidation.
 
 ## SkillOpt reference experiment
 
@@ -207,20 +207,25 @@ cerebellum --data-dir .cerebellum learning-status
 
 ## Local model routing
 
-The service works without a model using `deterministic-bm25`. To route through
-a Rust-native `mistral.rs` server or a `llama.cpp` server, configure its
-OpenAI-compatible endpoint:
+The service works without a model using `deterministic-bm25`. The approved
+optional configuration shares one pinned Ornith model across routing,
+knowledge extraction, quality screening/challenge and synthesis:
 
 ```powershell
-$env:CEREBELLUM_ROUTER_BACKEND = "mistralrs"
-$env:CEREBELLUM_MODEL_ENDPOINT = "http://127.0.0.1:1234"
-$env:CEREBELLUM_MODEL_NAME = "local-router"
+$env:CEREBELLUM_LOCAL_MODEL_ENABLED = "1"
+$env:CEREBELLUM_LOCAL_MODEL_ENDPOINT = "http://127.0.0.1:1234/v1"
+$env:CEREBELLUM_LOCAL_MODEL_NAME = "ornith-1.5-9b"
+$env:CEREBELLUM_LOCAL_MODEL_SHA256 = "894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da"
+$env:CEREBELLUM_LOCAL_MODEL_RUNTIME = "llama.cpp-win-x86_64-nvidia-cuda12-avx2"
+$env:CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION = "2.31.2"
+$env:CEREBELLUM_QUALITY_ENFORCEMENT = "1"
 target\release\cerebellumd.exe --data-dir .cerebellum
 ```
 
-Invalid JSON, invented workflow IDs, confidence below `0.25`, timeouts, and
-backend failures fall back to deterministic routing. Model output never
-changes or bypasses a gate definition.
+Only literal loopback HTTP roots are accepted. Requests use strict JSON Schema,
+carry no API key or tools, and have no hosted fallback. Invalid output,
+identity mismatch, timeouts, and backend failures fall back to deterministic
+routing. Model output never changes or bypasses a gate definition.
 
 ## Import boundaries
 
warning: in the working copy of 'docs\security.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\security.md" "b/docs\\security.md"
index e5e420b..418fb20 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\security.md"
+++ "b/docs\\security.md"
@@ -53,27 +53,25 @@
   receives a sanitized environment; cookies and browser profiles never enter
   HTTP, SQLite, CAS, prompts, or logs.
 - Prompt-injection, PII, and secret detectors mark documents unsafe, redact
-  cleaned text, suppress raw retention, and prohibit training. Hosted knowledge
+  cleaned text, suppress raw retention, and prohibit training. Weak model
   extraction is skipped for sensitive or authenticated-local material.
 - Public readability is not training permission. Knowledge and decision text
   enter meta-training only when the source license, explicit authorization,
   model-provider terms, redaction, and safety flags all allow it.
-- DeepSeek receives only records explicitly marked `external_processing=redacted`
-  after local bounded secret, PII and injection scanning. Historical data is
-  `private+denied`; authenticated browser/OpenCLI material is never exported.
-  Each export has a content-bound redaction attestation. A private export also
-  requires an administrator's provider opt-out attestation.
-- The DeepSeek key is loaded from a secret file first and is excluded from
-  SQLite, CAS, prompts, logs, commands and `/admin`. Redirects and tool calls
-  are disabled; reasoning content is discarded. A 64-character private-input
-  echo, secret, or PII in output invalidates and quarantines the result.
+- The configured model endpoint is literal loopback HTTP only. Hostnames,
+  credentials, query strings, fragments, redirects, proxies, API keys, tools,
+  thinking options and hosted fallbacks are rejected or absent.
+- Local inference does not require `external_processing=redacted` and does not
+  grant training eligibility. Deterministic licence, credential, PII,
+  prompt-injection, output-echo and approval checks still run first or fail
+  closed; authenticated browser/OpenCLI material remains ineligible.
 - Model verdicts are soft denials only: they may veto or quarantine but cannot
   override licenses, external-processing permission, objective feedback, or
   hard safety checks. Exact fingerprints require activation before their
   assessments can satisfy dataset eligibility.
-- DeepSeek cost is reserved atomically before a request. The 10 CNY Shanghai-day
-  ceiling and 30-day pricing-confirmation expiry fail closed under concurrency.
-  Budget exhaustion keeps the old Draft and never admits unreviewed records.
+- Local calls record model identity, stage, token usage and zero monetary cost.
+  Screening and challenge remain the persisted `Flash` and `Pro` stages, but
+  both use the same pinned model and neither may admit an unreviewed record.
 - Source withdrawal is actor/reason audited. It removes unreferenced source
   content from CAS, tombstones documents, strips evidence excerpts from every
   returned revision, and recalculates affected card status.
@@ -136,7 +134,8 @@ must never be exposed directly over a public listener.
 ## Failure policy
 
 - Registry corruption prevents startup.
-- Model failure falls back to deterministic routing; it does not weaken gates.
+- Local-model failure falls back to deterministic routing; it does not weaken
+  gates or trigger a hosted request.
 - Quality-model failure delays new assessments and Draft promotion. It does not
   remove the previous Draft or bypass semantic review for new training data.
 - Missing workflows, runs, evidence or permissions deny authorization.
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\task-7-baseline\cerebellum\docs\protocol.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs\protocol.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\protocol.md" "b/docs\\protocol.md"
index a8a11e8..ab12e80 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\protocol.md"
+++ "b/docs\\protocol.md"
@@ -130,7 +130,7 @@ the active lease owner: `/v1/acquisition/results`,
    Two kinds are built daily under independent dedup keys: `meta-controller`
    (decision traces, replays, synthetic candidates) and `knowledge-web`
    (instruction records mapped from the latest revisions of training-eligible
-   KnowledgeCards that additionally cleared the DeepSeek quality gate;
+   KnowledgeCards that additionally cleared the local Ornith quality gate;
    unassessed or ineligible cards never enter the Build). knowledge-web Builds
    carry no expert view and train through the dense TrainingRun path.
 3. `POST /v1/dataset-snapshots` freezes a successful Build. A revocation is a
@@ -169,7 +169,9 @@ Quality and synthesis routes are:
 
 When quality enforcement is enabled, deterministic eligibility is evaluated
 first and every included record must have an assessment from an active exact
-model fingerprint. A Build is immutable but remains pending until its Pro
+model fingerprint. `Flash` and `Pro` remain storage-compatible stage names for
+screening and challenge by the same pinned local model. Every request uses a
+strict response schema. A Build is immutable but remains pending until its Pro
 sample report passes; only then may it replace `DatasetDraft`. Assessments and
 generated candidates never alter source licenses or deterministic safety facts.
 
warning: in the working copy of 'docs\deployment-v2.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\deployment-v2.md" "b/docs\\deployment-v2.md"
index f0d28af..c8bcf01 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\deployment-v2.md"
+++ "b/docs\\deployment-v2.md"
@@ -46,16 +46,24 @@ hash, and posts a versioned response. It never opens the Registry database.
   limits. The AutoDL developer token exists only in `cerebellumd`; it is never
   included in SQLite, CAS, logs, start commands, or the private application.
 
-The optional weak knowledge-card extractor uses an OpenAI-compatible endpoint:
+The optional cognitive gateway is one pinned OpenAI-compatible local model for
+routing, weak knowledge extraction, quality screening/challenge and synthesis:
 
 ```bash
-CEREBELLUM_KNOWLEDGE_MODEL_ENDPOINT=https://provider.example/v1
-CEREBELLUM_KNOWLEDGE_MODEL_NAME=small-structured-model
-CEREBELLUM_KNOWLEDGE_MODEL_API_KEY=process-only-secret
+CEREBELLUM_LOCAL_MODEL_ENABLED=1
+CEREBELLUM_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:1234/v1
+CEREBELLUM_LOCAL_MODEL_NAME=ornith-1.5-9b
+CEREBELLUM_LOCAL_MODEL_SHA256=894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da
+CEREBELLUM_LOCAL_MODEL_RUNTIME=llama.cpp-win-x86_64-nvidia-cuda12-avx2
+CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION=2.31.2
+CEREBELLUM_QUALITY_ENFORCEMENT=1
 ```
 
-Endpoint and model name must be configured together. The key is process-only.
-Model failure never stops ingestion or BM25 retrieval.
+All pins are required when enabled. The endpoint must be literal loopback HTTP,
+so the daemon and runtime must share the same host or network namespace; do not
+widen it to a container gateway or public listener. Calls use strict JSON
+Schema, have zero monetary model cost, and carry no API key, proxy, tools or
+hosted fallback. Model failure never stops ingestion or BM25 retrieval.
 
 Provider credentials are mounted only into the acquisition worker. They must
 not be placed in TopicWatch, SourcePolicy, job payloads, SQLite, or CAS. For an
warning: in the working copy of 'docs\local-ornith-quality-v3.4.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\local-ornith-quality-v3.4.md" "b/docs\\local-ornith-quality-v3.4.md"
index e69de29..db91619 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\local-ornith-quality-v3.4.md"
+++ "b/docs\\local-ornith-quality-v3.4.md"
@@ -0,0 +1,70 @@
+# v3.4 local Ornith quality and synthesis
+
+## Runtime boundary
+
+Cerebellum uses one optional local OpenAI-compatible model for workflow
+routing, weak KnowledgeCard extraction, data-quality review and bounded
+synthetic-candidate generation. The approved pins are:
+
+```text
+CEREBELLUM_LOCAL_MODEL_ENABLED=1
+CEREBELLUM_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:1234/v1
+CEREBELLUM_LOCAL_MODEL_NAME=ornith-1.5-9b
+CEREBELLUM_LOCAL_MODEL_SHA256=894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da
+CEREBELLUM_LOCAL_MODEL_RUNTIME=llama.cpp-win-x86_64-nvidia-cuda12-avx2
+CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION=2.31.2
+CEREBELLUM_QUALITY_ENFORCEMENT=1
+```
+
+The endpoint accepts only literal IPv4 or IPv6 loopback HTTP roots, optionally
+ending in `/v1`. Requests have no API key, proxy, redirect, tools, thinking
+option, public address or hosted fallback. `/v1/models` must expose the exact
+configured model identity before completion requests are accepted.
+
+Every call uses `response_format.type=json_schema` with `strict=true` and a
+request-specific bounded schema. The client rejects missing or invalid JSON,
+tool calls, truncation, oversized responses and identity mismatch. It retries
+only transport or HTTP 5xx failure, once.
+
+## Quality lifecycle
+
+`Flash` and `Pro` remain the persisted stage names for compatibility. They are
+not different providers or models:
+
+- `Flash` is the first screening pass for each deterministically eligible
+  record.
+- `Pro` is a challenge/arbitration pass for low-confidence, disagreeing,
+  sampled or synthetic records and for Build audits.
+
+Both stages use the same pinned Ornith model. Local calls settle at zero
+monetary cost while retaining stage, model identity, fingerprint, prompt/cache/
+completion token counts and the existing audit evidence. Each completed local
+structured call records `latency_ms` in the structured-call trace. The fixed
+smoke probe separately persists per-call latency and its mean/median/maximum
+summary in the probe JSON evidence. These use the existing trace and probe
+artifacts; no database column or migration is added. Historical hosted usage
+and assessments are not rewritten.
+
+The fingerprint binds model name, GGUF SHA-256, runtime name/version, system
+prompt and response-schema hash. A first fingerprint requires named human
+approval. Drift enters calibration/shadow state and cannot satisfy
+`quality_clear` until its fixture, safety, quality and shadow evidence passes
+and an administrator approves it.
+
+## Deterministic authority
+
+Loopback inference is a processing location, not an authority. Licence,
+credential, PII, prompt-injection, private-output echo, deterministic
+eligibility, objective verification, dataset audit, human approval, activation
+and rollback gates remain authoritative and fail closed. Model output may veto
+or quarantine but cannot turn a deterministic denial into an eligible record.
+Routing failures fall back to deterministic BM25.
+
+Synthetic generation is depth one, lineage-bound and non-recursive. Executable
+or replayable candidates still require objective verification; semantic
+candidates require human approval and an active passing challenge assessment.
+A Build remains pending until its Pro-stage sample report passes.
+
+This lifecycle does not update Ornith weights. Dataset creation, adapter
+training, model promotion and activation remain separate, explicitly approved
+workflows with their existing evaluation and rollback gates.
warning: in the working copy of 'docs\deepseek-quality-v3.3.md', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\deepseek-quality-v3.3.md" "b/docs\\deepseek-quality-v3.3.md"
index 6090e77..b13e1be 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\cerebellum\\docs\\deepseek-quality-v3.3.md"
+++ "b/docs\\deepseek-quality-v3.3.md"
@@ -1,4 +1,7 @@
-# v3.3 DeepSeek intelligent data-quality and synthesis factory
+# Historical: v3.3 DeepSeek intelligent data-quality and synthesis factory
+
+This document records the retired hosted-provider protocol. The active design
+is [v3.4 local Ornith quality and synthesis](local-ornith-quality-v3.4.md).
 
 ## Trust boundary
 
warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\task-7-baseline\coordination\work\lm-studio-ornith-compatibility\probe.ps1', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of '..\.coordination\work\lm-studio-ornith-compatibility\probe.ps1', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1" "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1"
index 63222ff..9f21f38 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1"
+++ "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\probe.ps1"
@@ -2,6 +2,9 @@ param(
     [Parameter(Mandatory = $true)][string]$Endpoint,
     [Parameter(Mandatory = $true)][string]$Model,
     [Parameter(Mandatory = $true)][string]$Backend,
+    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ArtifactSha256,
+    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$RuntimeName,
+    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$RuntimeVersion,
     [Parameter(Mandatory = $true)][string]$OutputPath,
     [int]$Runs = 2
 )
@@ -9,10 +12,42 @@ param(
 $ErrorActionPreference = 'Stop'
 $inputsPath = Join-Path $PSScriptRoot 'probe-inputs.json'
 $inputBytes = [System.IO.File]::ReadAllBytes($inputsPath)
-$inputHash = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($inputBytes)).ToLowerInvariant()
-$inputs = Get-Content -Raw -LiteralPath $inputsPath | ConvertFrom-Json
+$sha256 = [System.Security.Cryptography.SHA256]::Create()
+try {
+    $inputHash = ([BitConverter]::ToString($sha256.ComputeHash($inputBytes))).Replace('-', '').ToLowerInvariant()
+} finally {
+    $sha256.Dispose()
+}
+$inputs = Get-Content -Raw -Encoding UTF8 -LiteralPath $inputsPath | ConvertFrom-Json
 $candidateIds = @($inputs.candidates | ForEach-Object { $_.workflow_id })
 $results = [System.Collections.Generic.List[object]]::new()
+$schema = [ordered]@{
+    type = 'object'
+    additionalProperties = $false
+    required = @('workflow_id', 'confidence', 'reasons')
+    properties = [ordered]@{
+        workflow_id = @{ type = 'string'; enum = $candidateIds }
+        confidence = @{ type = 'number'; minimum = 0; maximum = 1 }
+        reasons = @{ type = 'array'; maxItems = 8; items = @{ type = 'string'; maxLength = 240 } }
+    }
+}
+
+function Get-GpuSnapshot {
+    $rows = & nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
+    if ($LASTEXITCODE -ne 0) { throw "nvidia-smi failed with exit code $LASTEXITCODE" }
+    @($rows | ForEach-Object {
+        $fields = $_ -split ',\s*'
+        [ordered]@{
+            index = [int]$fields[0]
+            name = $fields[1]
+            memoryUsedMiB = [int]$fields[2]
+            memoryTotalMiB = [int]$fields[3]
+            utilizationPercent = [int]$fields[4]
+        }
+    })
+}
+
+$gpuBefore = Get-GpuSnapshot
 
 foreach ($run in 1..$Runs) {
     foreach ($case in $inputs.cases) {
@@ -30,7 +65,10 @@ foreach ($run in 1..$Runs) {
         $body = [ordered]@{
             model = $Model
             temperature = 0
-            response_format = @{ type = 'json_object' }
+            response_format = @{
+                type = 'json_schema'
+                json_schema = @{ name = 'cerebellum_router'; strict = $true; schema = $schema }
+            }
             messages = @(
                 @{ role = 'system'; content = 'Select exactly one supplied workflow. Never invent IDs. Return only the required JSON object.' },
                 @{ role = 'user'; content = ($prompt | ConvertTo-Json -Depth 12 -Compress) }
@@ -38,13 +76,33 @@ foreach ($run in 1..$Runs) {
         }
         $started = [System.Diagnostics.Stopwatch]::StartNew()
         try {
-            $response = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 12 -Compress) -TimeoutSec 10
+            $response = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 12 -Compress) -TimeoutSec 45
             $started.Stop()
             $content = [string]$response.choices[0].message.content
             $selected = $content | ConvertFrom-Json
-            $legalId = $candidateIds -contains [string]$selected.workflow_id
-            $confidence = [double]$selected.confidence
-            $validConfidence = $confidence -ge 0.25 -and $confidence -le 1.0
+            $propertyNames = @($selected.PSObject.Properties.Name)
+            $exactProperties = $propertyNames.Count -eq 3 -and
+                @($propertyNames | Where-Object { $_ -notin @('workflow_id', 'confidence', 'reasons') }).Count -eq 0
+            $workflowIdIsString = $selected.workflow_id -is [string]
+            $legalId = $workflowIdIsString -and $candidateIds -contains $selected.workflow_id
+            $confidenceIsNumber = $selected.confidence -is [byte] -or
+                $selected.confidence -is [sbyte] -or
+                $selected.confidence -is [int16] -or
+                $selected.confidence -is [uint16] -or
+                $selected.confidence -is [int32] -or
+                $selected.confidence -is [uint32] -or
+                $selected.confidence -is [int64] -or
+                $selected.confidence -is [uint64] -or
+                $selected.confidence -is [single] -or
+                $selected.confidence -is [double] -or
+                $selected.confidence -is [decimal]
+            $confidence = if ($confidenceIsNumber) { [double]$selected.confidence } else { $null }
+            $validConfidence = $confidenceIsNumber -and $confidence -ge 0 -and $confidence -le 1
+            $reasonsIsArray = $selected.reasons -is [array]
+            $validReasons = $reasonsIsArray -and @($selected.reasons).Count -le 8 -and
+                @($selected.reasons | Where-Object { $_ -isnot [string] -or $_.Length -gt 240 }).Count -eq 0
+            $schemaValid = $exactProperties -and $workflowIdIsString -and $legalId -and
+                $validConfidence -and $validReasons
             $exact = [string]$selected.workflow_id -eq [string]$case.expected
             $results.Add([ordered]@{
                 run = $run
@@ -56,6 +114,7 @@ foreach ($run in 1..$Runs) {
                 validJson = $true
                 legalId = $legalId
                 validConfidence = $validConfidence
+                schemaValid = $schemaValid
                 exact = $exact
                 accepted = $legalId -and $validConfidence
                 reasoningFieldPresent = $null -ne $response.choices[0].message.reasoning_content
@@ -73,6 +132,7 @@ foreach ($run in 1..$Runs) {
                 validJson = $false
                 legalId = $false
                 validConfidence = $false
+                schemaValid = $false
                 exact = $false
                 accepted = $false
                 reasoningFieldPresent = $false
@@ -82,17 +142,24 @@ foreach ($run in 1..$Runs) {
     }
 }
 
+$gpuAfter = Get-GpuSnapshot
 $latencies = @($results | Where-Object accepted | ForEach-Object elapsedMs | Sort-Object)
 $summary = [ordered]@{
-    schemaVersion = 1
+    schemaVersion = 2
     backend = $Backend
     endpoint = $Endpoint
     model = $Model
+    artifactSha256 = $ArtifactSha256.ToLowerInvariant()
+    runtimeName = $RuntimeName
+    runtimeVersion = $RuntimeVersion
     inputSha256 = $inputHash
+    gpuBefore = $gpuBefore
+    gpuAfter = $gpuAfter
     runs = $Runs
     casesPerRun = @($inputs.cases).Count
     total = $results.Count
     accepted = @($results | Where-Object accepted).Count
+    schemaValid = @($results | Where-Object schemaValid).Count
     exact = @($results | Where-Object exact).Count
     validJson = @($results | Where-Object validJson).Count
     reasoningFieldPresent = @($results | Where-Object reasoningFieldPresent).Count
@@ -104,4 +171,4 @@ $summary = [ordered]@{
 
 $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding utf8
 $summary | ConvertTo-Json -Depth 4
-if ($summary.accepted -ne $summary.total -or $summary.exact -ne $summary.total) { exit 1 }
+if ($summary.accepted -ne $summary.total -or $summary.schemaValid -ne $summary.total) { exit 1 }
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-probe.json" "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-probe.json"
index e69de29..69e7950 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-7-baseline\\coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-probe.json"
+++ "b/..\\.coordination\\work\\lm-studio-ornith-compatibility\\lm-studio-ornith-json-schema-probe.json"
@@ -0,0 +1,293 @@
+﻿{
+    "schemaVersion":  2,
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
+                      "memoryUsedMiB":  31127,
+                      "memoryTotalMiB":  32607,
+                      "utilizationPercent":  0
+                  },
+    "gpuAfter":  {
+                     "index":  0,
+                     "name":  "NVIDIA GeForce RTX 5090",
+                     "memoryUsedMiB":  31253,
+                     "memoryTotalMiB":  32607,
+                     "utilizationPercent":  76
+                 },
+    "runs":  2,
+    "casesPerRun":  8,
+    "total":  16,
+    "accepted":  16,
+    "schemaValid":  16,
+    "exact":  12,
+    "validJson":  16,
+    "reasoningFieldPresent":  16,
+    "meanLatencyMs":  5032,
+    "medianLatencyMs":  3244,
+    "maxLatencyMs":  23154,
+    "results":  [
+                    {
+                        "run":  1,
+                        "case":  "bugfix-en",
+                        "expected":  "bugfix",
+                        "selected":  "bugfix",
+                        "confidence":  0.98,
+                        "elapsedMs":  1466,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "bugfix-zh",
+                        "expected":  "bugfix",
+                        "selected":  "bugfix",
+                        "confidence":  0.4,
+                        "elapsedMs":  23146,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "feature-en",
+                        "expected":  "feature",
+                        "selected":  "feature",
+                        "confidence":  0.95,
+                        "elapsedMs":  779,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "feature-zh",
+                        "expected":  "feature",
+                        "selected":  "code-review",
+                        "confidence":  0.2,
+                        "elapsedMs":  3988,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "review-en",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.96,
+                        "elapsedMs":  2061,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "review-zh",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.3,
+                        "elapsedMs":  3244,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "premerge-en",
+                        "expected":  "pre-merge",
+                        "selected":  "pre-merge",
+                        "confidence":  1,
+                        "elapsedMs":  1570,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  1,
+                        "case":  "premerge-zh",
+                        "expected":  "pre-merge",
+                        "selected":  "code-review",
+                        "confidence":  0.4,
+                        "elapsedMs":  3911,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "bugfix-en",
+                        "expected":  "bugfix",
+                        "selected":  "bugfix",
+                        "confidence":  0.98,
+                        "elapsedMs":  1322,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "bugfix-zh",
+                        "expected":  "bugfix",
+                        "selected":  "bugfix",
+                        "confidence":  0.4,
+                        "elapsedMs":  23154,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "feature-en",
+                        "expected":  "feature",
+                        "selected":  "feature",
+                        "confidence":  0.95,
+                        "elapsedMs":  724,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "feature-zh",
+                        "expected":  "feature",
+                        "selected":  "code-review",
+                        "confidence":  0.2,
+                        "elapsedMs":  4257,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "review-en",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.96,
+                        "elapsedMs":  2107,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "review-zh",
+                        "expected":  "code-review",
+                        "selected":  "code-review",
+                        "confidence":  0.3,
+                        "elapsedMs":  3309,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "premerge-en",
+                        "expected":  "pre-merge",
+                        "selected":  "pre-merge",
+                        "confidence":  1,
+                        "elapsedMs":  1580,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  true,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    },
+                    {
+                        "run":  2,
+                        "case":  "premerge-zh",
+                        "expected":  "pre-merge",
+                        "selected":  "code-review",
+                        "confidence":  0.4,
+                        "elapsedMs":  3898,
+                        "validJson":  true,
+                        "legalId":  true,
+                        "validConfidence":  true,
+                        "schemaValid":  true,
+                        "exact":  false,
+                        "accepted":  true,
+                        "reasoningFieldPresent":  true,
+                        "error":  null
+                    }
+                ]
+}
