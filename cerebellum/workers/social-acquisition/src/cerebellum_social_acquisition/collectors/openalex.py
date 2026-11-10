"""OpenAlex Works API discovery provider.

Ported from hottrack media-scraper src/collectors/openalex_collector.py:
保留令牌桶限流（同步版）与游标分页逻辑；单页采集由 worker 主循环按
max_pages_per_run 控制页大小，游标推进归控制面 source cursor（本 worker
每次任务从 "*" 起采一页，保持无状态）。

Endpoint: https://api.openalex.org/works

payload.query 由控制面 topic watch 下发：非空时作为 OpenAlex 全文搜索
参数 search 传给 API；为空时回退默认学科快照（仅按年份/类型过滤）。
"""

from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlencode

from ..policy import PolicyError, classify_http_status, fetch_public_url, parse_retry_after
from ..platforms.base import BROWSER_UA, BoardItem, BoardResult, board_failure

ENDPOINT = "https://api.openalex.org/works"
ALLOWED_DOMAINS = ["api.openalex.org", "openalex.org", "doi.org"]


class TokenBucket:
    """同步令牌桶限流器（rate 令牌/秒，burst 桶容量）。"""

    def __init__(self, rate: float = 10.0, burst: int = 20) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            time.sleep(1.0 / self._rate)


_LIMITER = TokenBucket(rate=10.0, burst=20)


def build_query(
    per_page: int,
    cursor: str = "*",
    from_year: int = 2024,
    min_citation: int = 0,
    mailto: str = "",
    search: str = "",
) -> str:
    filters = [f"publication_year:{from_year}", "type:article"]
    if min_citation > 0:
        filters.append(f"cited_by_count:>{min_citation}")
    params = {
        "per_page": min(per_page, 200),
        "cursor": cursor,
        "sort": "publication_date:desc",
        "filter": ",".join(filters),
    }
    if mailto:
        params["mailto"] = mailto
    if search:
        # OpenAlex 全文搜索参数（topic watch 关键字）
        params["search"] = search
    return urlencode(params)


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """将 OpenAlex 的 inverted_abstract 重建为纯文本。"""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, offsets in inverted_index.items():
        for offset in offsets:
            positions.append((offset, word))
    positions.sort(key=lambda pair: pair[0])
    return " ".join(word for _, word in positions)


def parse_works(data: dict, limit: int, platform: str = "openalex") -> list[BoardItem]:
    results = data.get("results", []) if isinstance(data, dict) else []
    items: list[BoardItem] = []
    for work in results[:limit]:
        if not isinstance(work, dict):
            continue
        title = str(work.get("title") or "").strip()
        if not title:
            continue
        openalex_id = str(work.get("id") or "")
        doi = str(work.get("doi") or "")
        if doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        if not doi:
            doi = f"openalex:{openalex_id.rsplit('/', 1)[-1] or 'unknown'}"
        url = f"https://doi.org/{doi}" if doi and not doi.startswith("openalex:") else openalex_id
        authorships = work.get("authorships") or []
        authors = [
            str((entry.get("author") or {}).get("display_name") or "")
            for entry in authorships
            if isinstance(entry, dict)
        ]
        authors = [name for name in authors if name]
        primary_location = work.get("primary_location") or {}
        source = primary_location.get("source") or {}
        venue = source.get("display_name") or ""
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
        published = work.get("publication_date")
        items.append(
            BoardItem(
                external_id=doi,
                title=title,
                url=url or openalex_id,
                author=", ".join(authors[:3]) or None,
                published_at=f"{published}T00:00:00Z" if published else None,
                summary=abstract[:500] or None,
                language="en",
                heat=int(work.get("cited_by_count") or 0),
                platform=platform,
                extra={
                    "doi": doi,
                    "openalex_id": openalex_id,
                    "venue": venue,
                    "year": work.get("publication_year"),
                    "citation_count": work.get("cited_by_count", 0),
                    "paper": True,
                },
            )
        )
    return items


class OpenAlexProvider:
    kind = "openalex"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        mailto = os.environ.get("CEREBELLUM_OPENALEX_MAILTO", "").strip()
        # query 由控制面 topic watch 下发；空 query 回退默认学科快照
        query = (payload.get("query") or "").strip()
        url = f"{ENDPOINT}?{build_query(limit, mailto=mailto, search=query)}"
        _LIMITER.acquire()
        headers = {"User-Agent": BROWSER_UA, "Accept": "application/json"}
        try:
            response = fetch_public_url(
                url, policy.get("allowed_domains") or ALLOWED_DOMAINS, headers=headers
            )
        except PolicyError as error:
            return board_failure("api", ENDPOINT, error)
        outcome = classify_http_status(response.status)
        if outcome != "success":
            return BoardResult(
                "api",
                outcome,
                response.final_url,
                http_status=response.status,
                retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
                error_code=f"http_{response.status}",
            )
        import json

        try:
            data = json.loads(response.body.decode("utf-8", "replace"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return BoardResult(
                "api",
                "parse_failed",
                response.final_url,
                http_status=response.status,
                error_code="invalid_json",
            )
        return BoardResult(
            "api", "success", ENDPOINT, items=parse_works(data, limit, self.kind)
        )
