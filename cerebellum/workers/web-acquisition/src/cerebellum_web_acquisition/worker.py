from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .client import ControlPlaneClient
from .policy import PolicyError, canonicalize_url, escalation_action
from .providers import (
    Crawl4AIProvider,
    DirectProvider,
    FirecrawlProvider,
    LinkMapperProvider,
    MediaCrawlerDetailProvider,
    OpenCLIProvider,
    ProviderResult,
    ScraplingProvider,
    TavilyProvider,
)

SCHEMA_VERSION = "cerebellum/v1"
LICENSES_ALLOWING_TRAINING = {
    "MIT",
    "APACHE-2.0",
    "MIT OR APACHE-2.0",
    "BSD-2-CLAUSE",
    "BSD-3-CLAUSE",
    "CC0-1.0",
    "UNLICENSE",
}
PROMPT_INJECTION = re.compile(
    r"(?i)(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt|developer\s+message|"
    r"reveal\s+(your\s+)?(prompt|secret)|do\s+not\s+follow\s+the\s+user)"
)
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)")
SECRETS = [
    re.compile(r"(?i)\b(?:sk|pk)-[a-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"),
]
# 控制面权威检测的逐字镜像（crates/cerebellum-app/src/knowledge.rs
# detects_prompt_injection 与 knowledge_store.rs LIKELY_PII / LIKELY_SECRET）。
# 服务端会在提交的 cleaned 内容上重跑这些确定性检测并对账，worker 漏报会被
# 400 "worker omitted a deterministic content safety finding" 拒绝并死信，因此
# worker 检出集必须是服务端检出集的超集；上方 worker 自有规则只许更宽。
PROMPT_INJECTION_SUBSTRINGS = (
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "developer message",
    "jailbreak",
    "exfiltrate",
    "忽略之前",
    "忽略以上",
    "系统提示词",
    "开发者消息",
    "泄露密钥",
)
SERVER_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
SERVER_PHONE = re.compile(r"\+?\d[\d ()-]{7,}\d")
SERVER_SECRET = re.compile(
    r"(?i)-----BEGIN PRIVATE KEY-----|\b(?:sk|pk)-[a-z0-9_-]{16,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|authorization:\s*bearer\s+\S+|"
    r"(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret)\s*[:=]\s*\S{12,}"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


def redact(message: str) -> str:
    result = message
    for name in (
        "CEREBELLUM_TOKEN",
        "TAVILY_API_KEY",
        "FIRECRAWL_API_KEY",
    ):
        value = os.environ.get(name, "")
        if value:
            result = result.replace(value, "[REDACTED]")
    return result[:2000]


def sanitize_text(value: str) -> tuple[str, bool, bool, bool]:
    lowered = value.lower()
    prompt_injection = bool(PROMPT_INJECTION.search(value)) or any(
        needle in lowered for needle in PROMPT_INJECTION_SUBSTRINGS
    )
    pii = bool(
        EMAIL.search(value)
        or PHONE.search(value)
        or SERVER_EMAIL.search(value)
        or SERVER_PHONE.search(value)
    )
    secret = any(pattern.search(value) for pattern in SECRETS) or bool(
        SERVER_SECRET.search(value)
    )
    cleaned = EMAIL.sub("[REDACTED_EMAIL]", value)
    cleaned = SERVER_EMAIL.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = PHONE.sub("[REDACTED_PHONE]", cleaned)
    cleaned = SERVER_PHONE.sub("[REDACTED_PHONE]", cleaned)
    for pattern in SECRETS:
        cleaned = pattern.sub("[REDACTED_SECRET]", cleaned)
    cleaned = SERVER_SECRET.sub("[REDACTED_SECRET]", cleaned)
    return cleaned.strip(), prompt_injection, pii, secret


def language_for(text: str, item: dict) -> str:
    declared = item.get("language")
    if isinstance(declared, str) and declared.strip():
        return declared.strip().lower()[:16]
    cjk = sum("\u4e00" <= character <= "\u9fff" for character in text[:5000])
    return "zh" if cjk >= 5 else "en"


@dataclass
class RunOutcome:
    result: ProviderResult
    original_url: str
    started_at: datetime
    discovered_urls: list[str]
    retry: bool = False


def _provider(name: str):
    return {
        "crawl4ai": Crawl4AIProvider(),
        "firecrawl": FirecrawlProvider(),
        "link_mapper": LinkMapperProvider(),
        "scrapling": ScraplingProvider(),
        "mediacrawler": MediaCrawlerDetailProvider(),
        "open_cli": OpenCLIProvider(),
    }[name]


def _reserve_source_stage(
    client: ControlPlaneClient,
    job: dict,
    worker_id: str,
    ordinal: int,
    method: str,
    url: str,
) -> ProviderResult | None:
    try:
        client.reserve_source_rate(job["job_id"], worker_id, ordinal)
        return None
    except Exception:
        return ProviderResult(
            method,
            "rate_limited",
            url,
            retry_after_seconds=60,
            error_code="source_rate_budget_exhausted",
        )


def run_acquisition(
    client: ControlPlaneClient,
    job: dict,
    worker_id: str,
) -> RunOutcome:
    payload = job["payload"]
    policy = payload.get("source_policy")
    if not isinstance(policy, dict):
        raise PolicyError("job does not contain a source policy")
    started_at = utc_now()
    source_kind = str(payload.get("provider") or policy.get("kind") or "")
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    candidate_url = payload.get("canonical_url") or item.get("url")
    query = payload.get("query")

    if not candidate_url and isinstance(query, str) and query.strip():
        original = canonicalize_url(str(policy.get("base_url")), [])
        denied = _reserve_source_stage(client, job, worker_id, 0, "api", original)
        if denied is not None:
            result = denied
        elif source_kind == "tavily":
            result = TavilyProvider().search(query.strip(), payload)
        elif source_kind == "firecrawl":
            result = FirecrawlProvider().search(query.strip(), payload)
        else:
            result = ProviderResult(
                "api",
                "policy_denied",
                str(policy.get("base_url", "https://invalid.example/")),
                error_code="provider_does_not_support_search",
            )
        result.url = original
        return RunOutcome(
            result,
            original,
            started_at,
            result.discovered_urls,
            retry=result.outcome in {"rate_limited", "timeout", "server_error"},
        )

    if not isinstance(candidate_url, str):
        raise PolicyError("job does not contain an acquisition URL")
    allowed_domains = [str(value) for value in policy.get("allowed_domains", [])]
    original = canonicalize_url(candidate_url, allowed_domains)
    current = _reserve_source_stage(client, job, worker_id, 0, "direct_http", original)
    if current is None:
        current = DirectProvider().run(original, payload)
    discovered: list[str] = list(current.discovered_urls)
    best = current if current.cleaned_content else None
    browser_reserved = False
    stage_ordinal = 1

    while True:
        if current.cleaned_content and (
            best is None
            or len(current.cleaned_content) > len(best.cleaned_content or "")
        ):
            best = current
        for link in current.discovered_urls:
            if link not in discovered:
                discovered.append(link)
        action = escalation_action(current.method, current.outcome, str(policy.get("access_mode", "public")))
        if action == "retry":
            return RunOutcome(current, original, started_at, discovered, retry=True)
        if action is None:
            break
        if action in {"crawl4ai", "scrapling", "mediacrawler", "open_cli"} and not browser_reserved:
            try:
                browser_reserved = client.reserve_browser_budget(job["job_id"], worker_id)
            except Exception:
                current = ProviderResult(
                    current.method,
                    "policy_denied",
                    current.url,
                    error_code="browser_budget_denied",
                )
                break
        # 服务端 reserve_source_request 拒绝 ordinal > 15（knowledge_store.rs），
        # 超出即停止升级，而不是提交必然 400 的预留。
        if stage_ordinal > 15:
            break
        rate_denied = _reserve_source_stage(
            client, job, worker_id, stage_ordinal, action, original
        )
        stage_ordinal += 1
        if rate_denied is not None:
            current = rate_denied
        else:
            current = _provider(action).run(original, payload, current)

    if current.outcome in {"parse_failed", "partial_content", "js_shell"} and best is not None:
        best.outcome = "partial_content"
        best.error_code = current.error_code or "extraction_incomplete"
        current = best
    return RunOutcome(current, original, started_at, discovered)


def _attempt(job: dict, run: RunOutcome, content_hash: str | None) -> dict:
    payload = job["payload"]
    value = run.result
    return {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": str(uuid.uuid5(uuid.UUID(job["job_id"]), f"attempt:{job.get('attempts', 1)}")),
        "plan_id": payload["plan_id"],
        "source_policy_id": payload["source_policy_id"],
        "url": run.original_url,
        "canonical_url": value.url,
        "method": value.method,
        "outcome": value.outcome,
        "http_status": value.http_status,
        "retry_after_seconds": value.retry_after_seconds,
        "content_hash": content_hash,
        "error_code": value.error_code,
        "cost": 0.0,
        "started_at": iso(run.started_at),
        "finished_at": iso(utc_now()),
    }


def _document(job: dict, run: RunOutcome) -> tuple[dict | None, bytes | None, bytes | None]:
    value = run.result
    if not value.cleaned_content:
        return None, None, None
    payload = job["payload"]
    policy = payload["source_policy"]
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    cleaned, injection, pii, secret = sanitize_text(value.cleaned_content)
    if not cleaned:
        return None, None, None
    cleaned_bytes = cleaned.encode("utf-8")
    cleaned_hash = hashlib.sha256(cleaned_bytes).hexdigest()
    raw_bytes = value.raw_content
    if pii or secret or policy.get("access_mode") == "authenticated_local":
        raw_bytes = None
    raw_hash = hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else None
    license_value = policy.get("training_license")
    normalized_license = str(license_value or "").strip().upper()
    licensed = normalized_license in LICENSES_ALLOWING_TRAINING
    safe_for_training = not (injection or pii or secret)
    explicit_permission = (
        licensed
        and bool(policy.get("model_terms_allow_training"))
        and safe_for_training
        and value.outcome == "success"
    )
    training_eligible = explicit_permission and safe_for_training
    fetched_at = utc_now()
    retention_days = max(0, min(int(policy.get("raw_retention_days", 30)), 90))
    title = str(value.title or item.get("title") or urlsplit_host(value.url)).strip()[:500]
    metadata = {
        "provider": value.method,
        "provider_metadata": value.metadata,
        "discovered_url_count": len(run.discovered_urls),
        "source_kind": policy.get("kind"),
    }
    document = {
        "schema_version": SCHEMA_VERSION,
        "document_id": str(uuid.uuid5(uuid.UUID(job["job_id"]), f"document:{cleaned_hash}")),
        "topic_ids": payload.get("topic_ids", []),
        "source_policy_id": payload["source_policy_id"],
        "external_id": item.get("external_id"),
        "url": run.original_url,
        "canonical_url": value.url,
        "author": item.get("author"),
        "title": title or "Untitled document",
        "published_at": item.get("published_at"),
        "observed_at": iso(fetched_at),
        "fetched_at": iso(fetched_at),
        "raw_content_hash": raw_hash,
        "cleaned_content_hash": cleaned_hash,
        "extraction_method": value.method,
        "extractor_version": provider_version(value.method),
        "language": language_for(cleaned, item),
        "content_type": value.content_type[:255],
        "rights": {
            "license": license_value,
            "retrieval_allowed": True,
            "storage_allowed": True,
            "redistribution_allowed": licensed,
            "explicit_training_permission": explicit_permission,
            "model_terms_allow_training": bool(policy.get("model_terms_allow_training")),
            "training_eligible": training_eligible,
            "rights_source": f"source_policy:{payload['source_policy_id']}",
        },
        "prompt_injection_detected": injection,
        "pii_detected": pii,
        "secret_detected": secret,
        "raw_expires_at": iso(fetched_at + timedelta(days=retention_days)),
        "tombstoned": False,
        "metadata": metadata,
    }
    return document, cleaned_bytes, raw_bytes


def urlsplit_host(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).hostname or "Untitled document"


def provider_version(method: str) -> str:
    return {
        "direct_http": "stdlib-pinned-http/0.1",
        "api": "managed-api/1",
        "rss": "stdlib-rss/1",
        "crawl4ai": "crawl4ai/0.9.2",
        "firecrawl": "firecrawl/2.10",
        "link_mapper": "builtin-link-mapper/1",
        "scrapling": "scrapling/0.4.8",
        "mediacrawler": "mediacrawler/2026.08.14",
        "open_cli": "opencli-local-bridge/1.8.4",
    }[method]


def process_one(client: ControlPlaneClient, worker_id: str) -> bool:
    job = client.claim(worker_id, lease_seconds=3_600)
    if job is None:
        return False
    job_id = job["job_id"]
    try:
        if client.get_result(job_id) is not None:
            client.complete(job_id, worker_id)
            return True
        run = run_acquisition(client, job, worker_id)
        if run.retry:
            attempt = _attempt(job, run, None)
            retry_after = run.result.retry_after_seconds
            if retry_after is None:
                retry_after = min(3_600, 30 * (2 ** max(0, int(job.get("attempts", 1)) - 1)))
            client.fail(
                job_id,
                worker_id,
                run.result.error_code or run.result.outcome,
                retry_after,
                attempt,
            )
            return True
        document, cleaned, raw = _document(job, run)
        if document is None and run.result.outcome == "success":
            # 服务端拒绝 success 但无 document 的结果（knowledge_store.rs:
            # "successful acquisition must include a document"）；来源可达但
            # 无可提交内容按 partial_content 证据上报，避免确定性 400 死信。
            run.result.outcome = "partial_content"
            run.result.error_code = run.result.error_code or "empty_document"
        content_hash = document["cleaned_content_hash"] if document else None
        attempt = _attempt(job, run, content_hash)
        result = {
            "schema_version": SCHEMA_VERSION,
            "job_id": job_id,
            "worker": worker_id,
            "attempt": attempt,
            "document": document,
            "discovered_urls": run.discovered_urls[: int(job["payload"]["source_policy"].get("max_pages_per_run", 50))],
            "created_at": iso(utc_now()),
        }
        client.submit_result(
            result,
            base64.b64encode(cleaned).decode("ascii") if cleaned else None,
            base64.b64encode(raw).decode("ascii") if raw else None,
        )
        client.complete(job_id, worker_id)
    except Exception as error:
        client.fail(job_id, worker_id, redact(str(error)), 60)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Cerebellum v3 web acquisition worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()
    worker_id = required_env("WORKER_ID")
    client = ControlPlaneClient(
        required_env("CEREBELLUM_URL"), required_env("CEREBELLUM_TOKEN")
    )
    while True:
        processed = process_one(client, worker_id)
        if args.once:
            return
        if not processed:
            time.sleep(min(max(args.poll_seconds, 0.2), 30.0))


if __name__ == "__main__":
    main()
