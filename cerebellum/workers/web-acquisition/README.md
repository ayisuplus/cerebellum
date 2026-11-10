# Cerebellum Web Acquisition Worker

This worker claims only document_acquire_v1 jobs. It cannot read the Registry database.
It receives a bounded source policy and task payload, uses a failure-driven provider ladder,
submits one immutable result, and then completes or retries the lease.

Default core dependencies are Python standard library only. Heavy providers are explicit:

- Crawl4AI 0.9.2 for LLM-ready Markdown.
- Firecrawl v2.10 through an independent HTTP service.
- Scrapling 0.4.8 for authorized complex public pages.
- OpenCLI 1.8.4 through a local, explicitly enabled browser-session bridge.
- Tavily through its managed API.

The worker never solves CAPTCHAs, rotates identity, bypasses access controls, or changes identity
after a rate limit. robots_denied, captcha, explicit_challenge, and policy_denied are terminal.
OpenCLI receives only an opaque local session name; cookies and browser profiles are never
serialized.

Run contract tests without Docker or optional providers:

    python -m unittest discover -s tests -v

Run the worker after setting CEREBELLUM_URL and CEREBELLUM_TOKEN:

    python -m cerebellum_web_acquisition.worker

Docker/browser providers remain disabled until explicitly installed and configured.
