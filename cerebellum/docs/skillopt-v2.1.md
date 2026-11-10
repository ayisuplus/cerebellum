# SkillOpt v2.1 reference loop

This milestone tests one claim: external objective feedback can improve a
real Skill without allowing an optimizer to publish it. It does not train a
small model or deploy the central learning server.

## Trust and process boundary

`cerebellumd` owns the Registry, CAS, immutable run state, validation policy
and human review. The Python worker only leases `skillopt_optimize_v1` jobs and
downloads named CAS objects over HTTP. It never opens `registry.db`.

The worker uses Microsoft SkillOpt at commit
`3c8873f016397817dcd40c3e5436d92fe19372b8`. The checked archive hash is
`abdc429fe2a59b30d36c3148a107dfb36184821c7996d67d98d362a6603b1999`.
The small registration patch is checked both by SHA-256 and by
`git apply --check` during image build. Upstream code and the patch are
recorded in each result; API credentials are never part of a request or run
manifest.

The worker maps the required process variable `API_KEY` to SkillOpt's
provider-specific environment variable only in memory. Missing endpoint,
secret or either model role fails closed. There are no default models.

## Benchmark construction

`benchmarks/verify/generate.py` deterministically builds 20 template families
with three variants each:

- Train: 10 families / 30 tasks.
- Validation: 5 families / 15 tasks.
- Holdout: 5 families / 15 tasks.
- Across all splits: 12 fixable families, 4 already-passing families and 4
  correctly-blocked families.

Families never cross a split. Each task bundle has a `public/` repository and
a separate `grader/` root. The worker mounts the grader at `/grader` but its
file broker only serves paths under `/workspace`; there is no arbitrary shell
action. The complete fixed test command remains `pytest -q`.

Build and publish the benchmark image first. Both the base and final image
must be referenced by registry digest:

```powershell
docker build --build-arg PYTHON_BASE_IMAGE=python@sha256:<approved-base-digest> `
  -t ghcr.io/<owner>/cerebellum-python311-pytest:1 `
  benchmarks/verify/image
docker push ghcr.io/<owner>/cerebellum-python311-pytest:1
docker buildx imagetools inspect ghcr.io/<owner>/cerebellum-python311-pytest:1

python benchmarks/verify/generate.py `
  --image ghcr.io/<owner>/cerebellum-python311-pytest@sha256:<published-digest> `
  --output benchmarks/verify/generated
```

The generator writes `manifest.json`, `benchmark.zip` and `SHA256SUMS`.

## Register the first run

The imported Evolver snapshot has no standalone license declaration, so it is
explicitly `NOASSERTION` and internal-only:

```powershell
$env:TARGET_MODEL = "provider-target-model"
$env:OPTIMIZER_MODEL = "provider-optimizer-model"
$env:CEREBELLUM_SOURCE_COMMIT = git rev-parse HEAD

target/debug/cerebellum --data-dir .cerebellum optimize-skill `
  evolver-verify 1.0.0 `
  benchmarks/verify/generated/manifest.json `
  benchmarks/verify/generated/benchmark.zip `
  --baseline-file components/evolver/evolver/skills/verify-before-claim/SKILL.md `
  --source-repository-url https://github.com/ayisuplus/cerebellum.git `
  --source-commit-sha $env:CEREBELLUM_SOURCE_COMMIT `
  --source-path components/evolver/evolver/skills/verify-before-claim/SKILL.md `
  --source-license NOASSERTION
```

Build the isolated worker image with an explicitly pinned Python base (the
Dockerfile intentionally has no floating default), or install the worker in a
Python 3.11 virtual environment. Then supply all secrets at runtime:

```powershell
$env:CEREBELLUM_URL = "http://127.0.0.1:3927"
$env:CEREBELLUM_TOKEN = (Get-Content .cerebellum/auth.token -Raw).Trim()
$env:WORKER_ID = "skillopt-worker-1"
$env:OPENAI_COMPATIBLE_BASE_URL = "https://provider.example/v1"
$env:API_KEY = "..."
$env:TARGET_MODEL = "provider-target-model"
$env:OPTIMIZER_MODEL = "provider-optimizer-model"
$env:SKILLOPT_SOURCE_ARCHIVE_SHA256_FILE = "<worker>/skillopt-source.sha256"
$env:CEREBELLUM_REGISTRATION_PATCH = "workers/skillopt-reference/patches/register-cerebellum-verify.patch"

python -m cerebellum_skillopt --once
```

The worker runs two epochs, batches of ten and at most six candidate steps. It
stops before the next step after two objective non-improvements. Candidate
edits are converted to the restricted Cerebellum patch contract; Rust applies
them again, verifies hashes and token limits, recomputes every score and
recomputes the deterministic 10,000-sample paired bootstrap.

## Review

```powershell
cerebellum --data-dir .cerebellum optimization-status <RUN_ID>
cerebellum --data-dir .cerebellum review-optimization <RUN_ID> approve `
  --actor "operator@example" --reason "paired holdout evidence reviewed"
```

Only a `validated` run can be approved. Approval creates a new stable semantic
version with lineage; it never overwrites the baseline. A known-license source
becomes lifecycle `validated`. `NOASSERTION`, including the initial Evolver
fixture, remains `quarantined`, non-routable and non-training-eligible even
after the measured edit is accepted.

## Current-machine acceptance boundary

The checked-in Rust and Python tests do not need Docker or hosted credentials.
The real 60-task report additionally requires Docker Desktop in Linux
containers mode, a published digest-pinned benchmark image, and explicitly
configured OpenAI-compatible target and optimizer models. Absence of any of
these is an expected fail-closed result, not a skipped publication gate.
