"""Cerebellum v3 social acquisition worker 主循环.

claim `social_acquisition_v1` job → 按 payload 中 source_policy 选 discovery
provider（热榜/论文/认证链）→ 组装板级快照 Document + discovered_urls 按
schemas/acquisition-worker-result.schema.json 提交。存储、调度、详情页抓取
归控制面与 web-acquisition worker；本 worker 只有作业级输出权。
"""

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

from .auth import AUTHENTICATED_PROVIDERS
from .client import ControlPlaneClient
from .collectors import COLLECTOR_PROVIDERS
from .event_cluster import assign_cluster_ids
from .mediacrawler import MC_PLATFORM_CODES, MediaCrawlerSearchProvider
from .platforms import BOARD_PROVIDERS
from .platforms.base import BoardResult
from .policy import PolicyError, canonicalize_url

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
# 与 web-acquisition worker 保持一致的确定性内容安全检测
# （控制面 validate_worker_document_policy 会重跑等价检测并对账）。
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

RETRYABLE_OUTCOMES = {"rate_limited", "timeout", "server_error"}


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
    value = os.environ.get("CEREBELLUM_TOKEN", "")
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


def language_for(text: str) -> str:
    cjk = sum("\u4e00" <= character <= "\u9fff" for character in text[:5000])
    return "zh" if cjk >= 5 else "en"


@dataclass
class RunOutcome:
    result: BoardResult
    original_url: str
    canonical_url: str
    started_at: datetime
    discovered_urls: list[str]
    retry: bool = False


def _provider_for(payload: dict):
    policy = payload["source_policy"]
    kind = str(payload.get("provider") or policy.get("kind") or "")
    if payload.get("crawler_type") == "search" and kind in MC_PLATFORM_CODES:
        return kind, MediaCrawlerSearchProvider(kind)
    if policy.get("access_mode") == "authenticated_local" and kind in AUTHENTICATED_PROVIDERS:
        return kind, AUTHENTICATED_PROVIDERS[kind]
    if kind in BOARD_PROVIDERS:
        return kind, BOARD_PROVIDERS[kind]
    if kind in COLLECTOR_PROVIDERS:
        return kind, COLLECTOR_PROVIDERS[kind]
    return kind, None


def _fixture_discovery(kind: str, payload: dict) -> BoardResult | None:
    """离线 fixture 回放（测试/调试专用）：设置 CEREBELLUM_SOCIAL_FIXTURE_DIR
    后，按 {kind}.json / {kind}.html 从该目录读取预先录制的响应体并走真实
    解析器，不访问外网。未设置或文件缺失时返回 None（走真实网络）。"""
    import json
    from pathlib import Path

    directory = os.environ.get("CEREBELLUM_SOCIAL_FIXTURE_DIR", "").strip()
    if not directory:
        return None
    policy = payload["source_policy"]
    limit = int(policy.get("max_pages_per_run") or 50)
    base = Path(directory)
    json_path = base / f"{kind}.json"
    html_path = base / f"{kind}.html"
    url = str(policy.get("base_url") or "https://fixture.local/")
    if json_path.is_file():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        parsers = {
            "weibo": ("weibo", None),
            "zhihu": ("zhihu", None),
            "douyin": ("douyin", None),
            "bilibili": ("bilibili", None),
            "baidu": ("baidu", None),
            "kuaishou": ("kuaishou", None),
            "tieba": ("tieba", None),
        }
        entry = parsers.get(kind)
        if entry is not None:
            module = __import__(f"cerebellum_social_acquisition.platforms.{kind}", fromlist=["parse_hot_board"])
            items = module.parse_hot_board(data, limit, kind)
            return BoardResult("api", "success", url, items=items)
        if kind == "openalex":
            from .collectors.openalex import parse_works

            return BoardResult("api", "success", url, items=parse_works(data, limit, kind))
        return None
    if html_path.is_file() and kind == "xhs":
        from .platforms.xhs import parse_explore_ssr

        text = html_path.read_text(encoding="utf-8")
        items = parse_explore_ssr(text, limit, kind)
        if not items:
            return BoardResult("api", "parse_failed", url, error_code="initial_state_missing")
        return BoardResult("api", "success", url, items=items)
    if kind == "arxiv" and (base / "arxiv.xml").is_file():
        from .collectors.arxiv import parse_atom_feed

        text = (base / "arxiv.xml").read_text(encoding="utf-8")
        return BoardResult("api", "success", url, items=parse_atom_feed(text, "cs.AI", limit, kind))
    return None


def run_discovery(
    client: ControlPlaneClient,
    job: dict,
    worker_id: str,
) -> RunOutcome:
    payload = job["payload"]
    policy = payload.get("source_policy")
    if not isinstance(policy, dict):
        raise PolicyError("job does not contain a source policy")
    started_at = utc_now()
    base_url = str(policy.get("base_url") or "https://invalid.example/")
    kind, provider = _provider_for(payload)
    if provider is None:
        result = BoardResult(
            "api",
            "policy_denied",
            base_url,
            error_code="provider_not_supported_by_social_worker",
        )
        return RunOutcome(result, base_url, base_url, started_at, [])

    try:
        client.reserve_source_rate(job["job_id"], worker_id, 0)
    except Exception:
        result = BoardResult(
            "api",
            "rate_limited",
            base_url,
            retry_after_seconds=60,
            error_code="source_rate_budget_exhausted",
        )
        return RunOutcome(result, base_url, base_url, started_at, [], retry=True)

    result = _fixture_discovery(kind, payload) or provider.discover(payload)
    canonical = result.url
    try:
        canonical = canonicalize_url(result.url, [str(v) for v in policy.get("allowed_domains", [])])
    except PolicyError:
        pass

    # 空榜不出假成功：有抓取无条目按 partial_content 证据上报
    if result.outcome == "success" and not result.items:
        result.outcome = "partial_content"
        result.error_code = result.error_code or "empty_board"

    if result.items:
        assign_cluster_ids(result.items)

    allowed = [str(value) for value in policy.get("allowed_domains", [])]
    discovered: list[str] = []
    for item in result.items:
        try:
            url = canonicalize_url(item.url, allowed)
        except PolicyError:
            continue
        if url != canonical and url not in discovered:
            discovered.append(url)
        if len(discovered) >= int(policy.get("max_pages_per_run", 50)):
            break

    return RunOutcome(
        result,
        result.url,
        canonical,
        started_at,
        discovered,
        retry=result.outcome in RETRYABLE_OUTCOMES,
    )


def _attempt(job: dict, run: RunOutcome, content_hash: str | None) -> dict:
    payload = job["payload"]
    value = run.result
    return {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": str(uuid.uuid5(uuid.UUID(job["job_id"]), f"attempt:{job.get('attempts', 1)}")),
        "plan_id": payload["plan_id"],
        "source_policy_id": payload["source_policy_id"],
        "url": run.original_url,
        "canonical_url": run.canonical_url,
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


def _render_board(job: dict, run: RunOutcome) -> str:
    policy = job["payload"]["source_policy"]
    lines = [
        f"{policy.get('name', 'board')} — {run.result.url}",
        "",
    ]
    for index, item in enumerate(run.result.items, 1):
        rank = item.rank or index
        heat = f" （热度 {item.heat}）" if item.heat else ""
        cluster = f" [跨平台事件 {item.extra['cluster_id']}]" if item.extra.get("cluster_id") else ""
        lines.append(f"{rank}. {item.title}{heat}{cluster}")
        if item.summary and item.summary != item.title:
            lines.append(f"   {item.summary[:200]}")
        lines.append(f"   {item.url}")
    return "\n".join(lines)


def _document(job: dict, run: RunOutcome) -> tuple[dict | None, bytes | None]:
    value = run.result
    if not value.items or value.outcome not in {"success", "partial_content"}:
        return None, None
    payload = job["payload"]
    policy = payload["source_policy"]
    cleaned, injection, pii, secret = sanitize_text(_render_board(job, run))
    if not cleaned:
        return None, None
    cleaned_bytes = cleaned.encode("utf-8")
    cleaned_hash = hashlib.sha256(cleaned_bytes).hexdigest()
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
    fetched_at = utc_now()
    retention_days = max(0, min(int(policy.get("raw_retention_days", 30)), 90))
    title = f"{policy.get('name', 'hot board')} {fetched_at.date().isoformat()}"[:500]
    if payload.get("crawler_type") == "search":
        title = f"{policy.get('name','hot board')} 搜索「{str(payload.get('query','')).strip()[:60]}」 {fetched_at.date().isoformat()}"[:500]
    metadata = {
        "provider": value.method,
        "source_kind": policy.get("kind"),
        "item_count": len(value.items),
        "discovered_url_count": len(run.discovered_urls),
        "items": [
            {
                **item.as_discovery(),
                "heat": item.heat,
                "rank": item.rank,
                "platform": item.platform,
                **({"cluster_id": item.extra["cluster_id"]} if item.extra.get("cluster_id") else {}),
                "extra": {k: v for k, v in item.extra.items() if k != "cluster_id"},
            }
            for item in value.items
        ],
    }
    document = {
        "schema_version": SCHEMA_VERSION,
        "document_id": str(uuid.uuid5(uuid.UUID(job["job_id"]), f"board:{cleaned_hash}")),
        "topic_ids": payload.get("topic_ids", []),
        "source_policy_id": payload["source_policy_id"],
        "external_id": None,
        "url": run.original_url,
        "canonical_url": run.canonical_url,
        "author": None,
        "title": title or "Hot board snapshot",
        "published_at": None,
        "observed_at": iso(fetched_at),
        "fetched_at": iso(fetched_at),
        "raw_content_hash": None,
        "cleaned_content_hash": cleaned_hash,
        "extraction_method": value.method,
        "extractor_version": "social-board/0.1",
        "language": language_for(cleaned),
        "content_type": "application/json",
        "rights": {
            "license": license_value,
            "retrieval_allowed": True,
            "storage_allowed": True,
            "redistribution_allowed": licensed,
            "explicit_training_permission": explicit_permission,
            "model_terms_allow_training": bool(policy.get("model_terms_allow_training")),
            "training_eligible": explicit_permission and safe_for_training,
            "rights_source": f"source_policy:{payload['source_policy_id']}",
        },
        "prompt_injection_detected": injection,
        "pii_detected": pii,
        "secret_detected": secret,
        "raw_expires_at": iso(fetched_at + timedelta(days=retention_days)),
        "tombstoned": False,
        "metadata": metadata,
    }
    return document, cleaned_bytes


def process_one(client: ControlPlaneClient, worker_id: str) -> bool:
    job = client.claim(worker_id, lease_seconds=3_600)
    if job is None:
        return False
    job_id = job["job_id"]
    try:
        if client.get_result(job_id) is not None:
            client.complete(job_id, worker_id)
            return True
        run = run_discovery(client, job, worker_id)
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
        document, cleaned = _document(job, run)
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
            None,
        )
        client.complete(job_id, worker_id)
    except Exception as error:
        client.fail(job_id, worker_id, redact(str(error)), 60)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Cerebellum v3 social acquisition worker")
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
