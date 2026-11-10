### Task 7: Update active documentation and produce the fixed local GPU evidence

**Files:**
- Modify: `README.md:1-210`
- Modify: `docs/security.md:56-76, 128-145`
- Modify: `docs/protocol.md:125-175`
- Modify: `docs/deployment-v2.md:45-65`
- Create: `docs/local-ornith-quality-v3.4.md`
- Modify: `docs/deepseek-quality-v3.3.md:1-8`
- Modify: `../.coordination/work/lm-studio-ornith-compatibility/probe.ps1`
- Create: `../.coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json`

**Interfaces:**
- Documents final environment variables and trust boundary.
- Probe accepts artifact/runtime identity parameters and emits strict-schema, latency, semantic-baseline, and GPU evidence.
- Previous `lm-studio-probe.json` remains immutable.

- [ ] **Step 1: Update the probe contract before allocating the GPU**

Add mandatory parameters:

```powershell
[Parameter(Mandatory = $true)][string]$ArtifactSha256,
[Parameter(Mandatory = $true)][string]$RuntimeName,
[Parameter(Mandatory = $true)][string]$RuntimeVersion,
```

Build a dynamic schema using the candidate IDs:

```powershell
$schema = [ordered]@{
    type = 'object'
    additionalProperties = $false
    required = @('workflow_id', 'confidence', 'reasons')
    properties = [ordered]@{
        workflow_id = @{ type = 'string'; enum = $candidateIds }
        confidence = @{ type = 'number'; minimum = 0; maximum = 1 }
        reasons = @{ type = 'array'; maxItems = 8; items = @{ type = 'string'; maxLength = 240 } }
    }
}
$body.response_format = @{
    type = 'json_schema'
    json_schema = @{ name = 'cerebellum_router'; strict = $true; schema = $schema }
}
```

Validate that the parsed object has exactly the required properties, a legal ID, bounded confidence, and an array of strings. Add `schemaValid` per result and summary. Keep `exact` as a reported semantic baseline, but change the exit gate to:

```powershell
if ($summary.accepted -ne $summary.total -or $summary.schemaValid -ne $summary.total) { exit 1 }
```

Add artifact SHA, runtime name/version, and `nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits` snapshots to the summary. Do not include paths outside the approved model artifact or any secret.

- [ ] **Step 2: Update active documentation**

Document these exact variables:

```text
CEREBELLUM_LOCAL_MODEL_ENABLED=1
CEREBELLUM_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:1234/v1
CEREBELLUM_LOCAL_MODEL_NAME=ornith-1.5-9b
CEREBELLUM_LOCAL_MODEL_SHA256=894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da
CEREBELLUM_LOCAL_MODEL_RUNTIME=llama.cpp-win-x86_64-nvidia-cuda12-avx2
CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION=2.31.2
CEREBELLUM_QUALITY_ENFORCEMENT=1
```

`docs/local-ornith-quality-v3.4.md` must describe one local model, strict schema, local zero cost, screening/challenge semantics, calibration/approval, deterministic authority, and no weight update. Mark `docs/deepseek-quality-v3.3.md` as historical and link to the new active document; do not erase its historical protocol description.

- [ ] **Step 3: Run formatting, focused tests, and source scans before GPU use**

Run:

```powershell
cargo fmt --all -- --check
cargo clippy -p cerebellum-app --all-targets -- -D warnings
cargo test -p cerebellum-app --all-targets
rg -n "DeepSeekClient|api\.deepseek\.com|DEEPSEEK_API_KEY|CEREBELLUM_KNOWLEDGE_MODEL_API_KEY" crates/cerebellum-app/src README.md docs/security.md docs/protocol.md docs/deployment-v2.md
```

Expected: Rust checks pass and the scan finds no active provider request/key configuration. Historical documentation and test fixtures are outside this active-path assertion.

- [ ] **Step 4: Load the already-approved Ornith model in LM Studio and confirm identity**

The user has already approved this local RTX 5090 probe and the existing hard-linked artifact. Run:

```powershell
lms ls
lms server status
lms load ornith-1.5-9b --identifier ornith-1.5-9b --gpu max --context-length 4096 --parallel 1 --yes
Invoke-RestMethod http://127.0.0.1:1234/v1/models | ConvertTo-Json -Depth 6
nvidia-smi
```

Expected: the server is running and model ID `ornith-1.5-9b` is listed. If
`lms server status` reports stopped, run `lms server start` once before loading.
Record the actual context echoed by LM Studio; if it remains 262,144, retain
the known-defect warning and continue only because the approved RTX 5090 probe
fits.

- [ ] **Step 5: Run the immutable 16-call strict-schema probe**

Run from the workspace root:

```powershell
powershell -ExecutionPolicy Bypass -File .coordination/work/lm-studio-ornith-compatibility/probe.ps1 `
  -Endpoint http://127.0.0.1:1234/v1/chat/completions `
  -Model ornith-1.5-9b `
  -Backend lm-studio-llama.cpp `
  -ArtifactSha256 894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da `
  -RuntimeName llama.cpp-win-x86_64-nvidia-cuda12-avx2 `
  -RuntimeVersion 2.31.2 `
  -Runs 2 `
  -OutputPath .coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json
```

Expected: `total=16`, `accepted=16`, `schemaValid=16`, exit code zero. `exact` is reported but is not the package gate.

- [ ] **Step 6: Unload the model and hash the evidence**

Run:

```powershell
lms unload ornith-1.5-9b
nvidia-smi
Get-FileHash .coordination/work/lm-studio-ornith-compatibility/lm-studio-ornith-json-schema-probe.json -Algorithm SHA256
```

Expected: Ornith is unloaded, GPU memory returns near baseline, and the evidence receives a stable SHA-256. Do not overwrite the previous failed probe.

- [ ] **Step 7: Run the full project gate**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1
```

Expected: all Rust, JavaScript, monorepo, Python, worker, and benchmark checks pass. If an unrelated pre-existing dirty-tree failure appears, preserve its exact command/output and do not claim package completion until the scoped Rust checks and ownership of the unrelated failure are clear.

- [ ] **Step 8: Final scope and history verification**

Run:

```powershell
git status --short
git diff --check
git diff --stat
rg -n "DeepSeekClient|api\.deepseek\.com|DEEPSEEK_API_KEY" crates/cerebellum-app/src
```

Expected: only approved paths changed, no whitespace errors, no active DeepSeek request/key path, and all pre-existing unrelated user changes remain present.

- [ ] **Step 9: Present the combined diff before any implementation commit**

Because `config.rs`, `quality.rs`, `router.rs`, `knowledge.rs`, `scheduler.rs`, `api.rs`, and documentation were already dirty before this package, do not run `git add` or `git commit`. Present:

```powershell
git diff -- crates/cerebellum-app/src/local_model.rs crates/cerebellum-app/src/config.rs crates/cerebellum-app/src/quality.rs crates/cerebellum-app/src/router.rs crates/cerebellum-app/src/knowledge.rs crates/cerebellum-app/src/scheduler.rs crates/cerebellum-app/src/api.rs crates/cerebellum-app/src/dataset_factory.rs README.md docs/security.md docs/protocol.md docs/deployment-v2.md docs/local-ornith-quality-v3.4.md docs/deepseek-quality-v3.3.md
```

Expected: user chooses whether to incorporate pre-existing changes into a commit, split them manually, or leave the verified implementation uncommitted.
