# Security and trust boundary

## Enforced guarantees

- The daemon refuses non-loopback bind addresses.
- Every `/v1` request except GitHub/WebSub callbacks and the isolated training
  worker protocol requires a local bearer token. Worker routes use one-use or
  Run-scoped credentials instead. GitHub additionally requires HMAC plus a repository watchlist;
  WebSub requires an exact RSS topic challenge and HMAC-SHA256 notification.
- Imported content is inert data and starts in `quarantined`.
- A Skill without immutable source provenance and a known license cannot be
  training eligible.
- Gate evaluators are a closed enum. Imported text and model output cannot
  introduce executable gate code.
- Missing evidence, invalid evaluator input, model errors and unknown workflow
  IDs fail closed.
- Action permits are signed, short-lived, action-bound and replay-protectable.
- Content-addressed objects are verified before Registry insertion.
- Experience and feedback IDs are immutable: replaying identical content is
  idempotent, while changing content under an existing ID is rejected.
- Verifiable feedback requires a matching canonical evidence hash, a verified
  marker, sidecar provenance and an HMAC attestation from `feedback.key`.
  LLM self-critique remains weak evidence.
- Prompt-injection patterns, unknown GitHub licenses, missing redaction and
  negative transfer raise risk and cannot become training-eligible content.
- Automated workers claim only allowlisted job kinds. Model activation is an
  explicit human-reviewed transition with an audit entry.
- Paired dynamic evaluation accepts only digest-pinned container images and
  starts Docker with no network, no Linux capabilities, no-new-privileges,
  resource limits, a read-only root filesystem and a copied workspace.
- Sandbox stdout and stderr are drained with a one-megabyte retention cap per
  stream, and source snapshots reject symlinks and files above the size limit.
- SkillOpt is isolated in a Python worker pinned by commit, source-archive
  hash and registration-patch hash. The Rust daemon never imports it.
- Coding optimization exposes only six JSON actions. The file broker rejects
  traversal and hidden-grader paths, only `solution.py` is mutable, and test
  execution is always the fixed `pytest -q` command in a digest-pinned,
  network-disabled container.
- A Worker cannot adopt a candidate. Result ownership is bound to the active
  lease; Rust replays patches and recomputes gates. Adoption requires a human
  identity and reason, and `NOASSERTION` content remains quarantined.
- Every acquired URL is canonicalized and checked against exact/subdomain
  allowlists. All DNS answers and every redirect are revalidated; loopback,
  private, link-local, multicast, unspecified, local-file and non-HTTP targets
  are denied. Responses and decompression are bounded to 10 MiB.
- The acquisition ladder is failure-driven. Rate limits and server failures
  retry the same identity; robots denial, CAPTCHA, explicit challenge and
  policy denial stop. CAPTCHA solving, identity rotation, access-control
  bypass, and geographic restriction bypass are intentionally absent.
- Browser escalation and every provider request consume atomic, lease-bound
  budgets. OpenCLI is available only to an `authenticated_local` policy through
  an explicitly enabled local executable and opaque session name. Its process
  receives a sanitized environment; cookies and browser profiles never enter
  HTTP, SQLite, CAS, prompts, or logs.
- Prompt-injection, PII, and secret detectors mark documents unsafe, redact
  cleaned text, suppress raw retention, and prohibit training. Weak model
  extraction is skipped for sensitive or authenticated-local material.
- Public readability is not training permission. Knowledge and decision text
  enter meta-training only when the source license, explicit authorization,
  model-provider terms, redaction, and safety flags all allow it.
- The configured model endpoint is literal loopback HTTP only. Hostnames,
  credentials, query strings, fragments, redirects, proxies, API keys, tools,
  thinking options and hosted fallbacks are rejected or absent.
- Local inference does not require `external_processing=redacted` and does not
  grant training eligibility. Deterministic licence, credential, PII,
  prompt-injection, output-echo and approval checks still run first or fail
  closed; authenticated browser/OpenCLI material remains ineligible.
- Model verdicts are soft denials only: they may veto or quarantine but cannot
  override licenses, external-processing permission, objective feedback, or
  hard safety checks. Exact fingerprints require activation before their
  assessments can satisfy dataset eligibility.
- Local calls record model identity, stage, token usage and zero monetary cost.
  Screening and challenge remain the persisted `Flash` and `Pro` stages, but
  both use the same pinned model and neither may admit an unreviewed record.
- Source withdrawal is actor/reason audited. It removes unreferenced source
  content from CAS, tombstones documents, strips evidence excerpts from every
  returned revision, and recalculates affected card status.
- Meta adapters start as candidates. Rust verifies dataset/manifest/artifact
  hashes; deterministic policy retains authority through shadow and 10% canary.
  Any canary policy violation rolls back immediately.
- Dataset Draft creation and TrainingRun creation cannot call a GPU provider.
  Formal `:start` rechecks license/safety, 5,000/1,000 evidence thresholds,
  weekly frequency, a pinned base-model hash, an approved 24+ GB CUDA spec and
  exact CNY/time confirmations. The provider price is read after creation; an
  over-budget instance is immediately powered off and released.
- AutoDL workers never receive the root token, provider token, arbitrary CAS,
  Registry, queue, Cookie, login state, or Hugging Face token. Bootstrap is
  one-use and ten-minute; scoped tokens expire in fifteen minutes and rotate on
  every heartbeat. Tokens are stored only as SHA-256 digests.
- Bundle downloads are Run-bound, resumable and hash-checked. Artifact uploads
  are streamed, immutable, size-bounded and hash-checked. Terminal states
  request release immediately; a 30-second reconciler retries release after
  restart and times out stale heartbeats, wall clocks and costs.
- Expert assignment preserves the precomputed source/topic split. Ambiguous,
  OOD and negative-transfer examples are routed to shared/routing-negative
  shards and cannot silently contaminate a domain expert.
- Routed training is bound to Snapshot, expert view, taxonomy, selected expert
  set and base-model hashes. The outer adapter tar may contain only referenced
  regular files with safe paths; every inner adapter hash and length is checked.
- Router, Shared and domain adapters start as independent candidates. Training
  completion cannot activate them. Canary/activation rejects policy or prompt
  injection regressions, retention below 98%, task regression, increased
  negative transfer or reduced routing accuracy. Canary requires 200 objective
  evaluations; activation requires a 24-hour/1,000-decision report. Missing active experts fall
  back to Shared and then the permanent dense/deterministic baseline. Active
  adapters in one taxonomy must share one immutable base-model ID, revision and
  hash.

## Explicit limitations

Cerebellum cannot stop an agent from calling tools that bypass its broker. A
host integration must verify and consume a permit immediately before every
covered mutation. The collector performs static screening only. Dynamic
evaluation is an explicit operator action and requires a working Docker daemon,
an operator-reviewed command and a locally available pinned image. Container
isolation reduces risk but is not a substitute for a dedicated disposable VM
when evaluating hostile native code.

License detection is deliberately conservative. `NOASSERTION` means the
artifact may be retained for provenance review but cannot be trained on,
published, or redistributed.

The synthetic benchmark and Skill text are allowed to reach the configured
hosted model. Personal Codex history, arbitrary third-party repositories,
hidden grader source and local credentials are outside this data boundary.
`API_KEY` is process-only and must not be placed in SQLite, CAS, model prompts,
traces, logs or worker manifests.

The JSON API token authenticates the local control plane but is not a remote
identity system. Production remote agents terminate at the separate mTLS
gateway described in [`deployment-v2.md`](deployment-v2.md). A bearer token
must never be exposed directly over a public listener.

## Failure policy

- Registry corruption prevents startup.
- Local-model failure falls back to deterministic routing; it does not weaken
  gates or trigger a hosted request.
- Quality-model failure delays new assessments and Draft promotion. It does not
  remove the previous Draft or bypass semantic review for new training data.
- Missing workflows, runs, evidence or permissions deny authorization.
- Revoked and deprecated Skills are excluded from runtime search.
- Sensitive values and raw repository paths are redacted or hashed during
  training export.
