# v3 deployment (v2 network boundary retained)

The server topology deliberately keeps `cerebellumd` on
`127.0.0.1:3927`. Caddy shares its container network namespace and exposes three
separate TLS surfaces:

- `8443`: mTLS is mandatory for remote coding-agent sidecars. Caddy replaces
  the public request authorization header with the local control-plane token.
- `8444`: only `/v1/github/webhooks` and `/v1/websub/*` are reachable.
  GitHub's HMAC/watchlist and WebSub's exact topic challenge/HMAC protect the
  respective endpoints; every other route returns 404.
- `8445`: only `/v1/training-worker/*` is reachable. Caddy does not inject the
  Registry token. AutoDL workers authenticate with one-use/scoped credentials.

Copy `deploy/.env.example` to an operator-managed secret location, issue a
server certificate and client CA under `deploy/certs`, then run from the
`deploy` directory:

```bash
docker compose --env-file /secure/cerebellum.env up --build -d
```

The Caddy and Evolver containers use `network_mode: service:cerebellum`; they
can reach the loopback API without making it directly routable. Evolver claims
only `evolver_consolidate_v1` leases, downloads the immutable request by CAS
hash, and posts a versioned response. It never opens the Registry database.

## Operating modes

- Laptop/default: `CEREBELLUM_LEARNING_SCHEDULER` is false, the deterministic
  controller works offline, Docker evaluation fails closed, and no trainer is
  started.
- Server: enable the scheduler and provide a scoped GitHub token. Search and
  collection remain bounded to 20 plans, 50 repositories, and 500 files per
  UTC day. All GitHub results are pinned to a 40-character commit and remain
  quarantined.
- Realtime knowledge server: the isolated web-acquisition worker shares only
  loopback HTTP with the daemon. Direct HTTP, RSS, GitHub and HN work without a
  browser. Crawl4AI and Scrapling are optional pinned extras; Firecrawl remains
  an independent AGPL HTTP service. Server Compose keeps OpenCLI disabled
  because authenticated browser state belongs on the user's local bridge.
- Dataset/AutoDL: the central Compose stack remains CPU-only. Set
  `CEREBELLUM_AUTODL_ENABLED=1` only after pinning the private application
  UUID/version, ordered GPU allowlist, base model revisions/tree hashes, and
  public HTTPS worker gateway. Each Run supplies its own hourly and total CNY
  limits. The AutoDL developer token exists only in `cerebellumd`; it is never
  included in SQLite, CAS, logs, start commands, or the private application.

The optional cognitive gateway is one pinned OpenAI-compatible local model for
routing, weak knowledge extraction, quality screening/challenge and synthesis:

```bash
CEREBELLUM_LOCAL_MODEL_ENABLED=1
CEREBELLUM_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:1234/v1
CEREBELLUM_LOCAL_MODEL_NAME=ornith-1.5-9b
CEREBELLUM_LOCAL_MODEL_SHA256=894078836a862a45f85607f8ee672fe3509f345a8e0643c1de31b92d91df25da
CEREBELLUM_LOCAL_MODEL_RUNTIME=llama.cpp-win-x86_64-nvidia-cuda12-avx2
CEREBELLUM_LOCAL_MODEL_RUNTIME_VERSION=2.31.2
CEREBELLUM_QUALITY_ENFORCEMENT=1
```

All pins are required when enabled. The endpoint must be literal loopback HTTP,
so the daemon and runtime must share the same host or network namespace; do not
widen it to a container gateway or public listener. Calls use strict JSON
Schema, have zero monetary model cost, and carry no API key, proxy, tools or
hosted fallback. Model failure never stops ingestion or BM25 retrieval.

Provider credentials are mounted only into the acquisition worker. They must
not be placed in TopicWatch, SourcePolicy, job payloads, SQLite, or CAS. For an
authenticated-local source, run a separate local acquisition worker with an
absolute `OPENCLI_BRIDGE_EXECUTABLE`, a non-secret `OPENCLI_SESSION` name, and
`CEREBELLUM_ENABLE_OPENCLI=1`; do not copy the browser profile to the server.

The `/admin` console is served on the mTLS listener. Caddy injects the local
root token, while the browser receives only a non-authenticating CSRF token.
The daemon rejects cross-origin browser requests and serves strict CSP,
frame-ancestor, MIME-sniffing and referrer headers.

Do not mount the Docker socket into the public control-plane container. Run
paired evaluations in a separately permissioned worker and submit signed or
otherwise attested reports. PostgreSQL/S3 migration should implement the same
Registry/CAS and queue contracts rather than expose internal tables.
