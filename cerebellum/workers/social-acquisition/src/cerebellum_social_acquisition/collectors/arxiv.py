"""arXiv 最新预印本 discovery provider.

Ported from hottrack media-scraper src/collectors/arxiv_collector.py.
arXiv API: https://export.arxiv.org/api/query （限流 1 请求/3 秒，本 worker
每次任务按分类串行采集并遵守 3.5s 间隔）。

单页采集：按 max_pages_per_run 控制总条数，均摊到各分类。

payload.query 由控制面 topic watch 下发：非空时走单次关键字检索
（all:"<query>"，不跑分类循环、不 sleep）；为空时回退下方默认学科
快照分类循环。
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from ..policy import PolicyError, classify_http_status, fetch_public_url, parse_retry_after
from ..platforms.base import BROWSER_UA, BoardItem, BoardResult, board_failure

ENDPOINT = "https://export.arxiv.org/api/query"
ALLOWED_DOMAINS = ["export.arxiv.org", "arxiv.org"]

ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

ARXIV_CATEGORIES = [
    "cs.AI",
    "cs.CL",
    "cs.CV",
    "cs.LG",
    "cs.MA",
    "cs.NE",
    "cs.RO",
    "cs.IR",
    "cs.SE",
    "stat.ML",
]

_FIELD_BY_CATEGORY = {
    "cs.AI": "Artificial Intelligence",
    "cs.CL": "Computational Linguistics",
    "cs.CV": "Computer Vision",
    "cs.LG": "Machine Learning",
    "cs.MA": "Multiagent Systems",
    "cs.NE": "Neural Computing",
    "cs.RO": "Robotics",
    "cs.IR": "Information Retrieval",
    "cs.SE": "Software Engineering",
    "stat.ML": "Machine Learning",
}

_RATE_LIMIT_SECONDS = 3.5


def parse_atom_feed(xml_text: str, default_category: str, limit: int, platform: str = "arxiv") -> list[BoardItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items: list[BoardItem] = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        if len(items) >= limit:
            break
        title_el = entry.find("atom:title", ARXIV_NS)
        title = " ".join(title_el.text.split()) if title_el is not None and title_el.text else ""
        if not title:
            continue
        summary_el = entry.find("atom:summary", ARXIV_NS)
        abstract = " ".join(summary_el.text.split()) if summary_el is not None and summary_el.text else ""
        id_el = entry.find("atom:id", ARXIV_NS)
        arxiv_url = id_el.text.strip() if id_el is not None and id_el.text else ""
        arxiv_id = arxiv_url.rsplit("/abs/", 1)[-1] if "/abs/" in arxiv_url else ""
        if not arxiv_url:
            continue
        authors: list[str] = []
        for author_el in entry.findall("atom:author", ARXIV_NS):
            name_el = author_el.find("atom:name", ARXIV_NS)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())
        published_el = entry.find("atom:published", ARXIV_NS)
        published = published_el.text.strip() if published_el is not None and published_el.text else ""
        primary_el = entry.find("arxiv:primary_category", ARXIV_NS)
        primary = primary_el.get("term", "") if primary_el is not None else default_category
        categories = [
            cat_el.get("term", "")
            for cat_el in entry.findall("atom:category", ARXIV_NS)
            if cat_el.get("term")
        ]
        items.append(
            BoardItem(
                external_id=f"arxiv:{arxiv_id}" if arxiv_id else arxiv_url,
                title=title,
                url=arxiv_url,
                author=", ".join(authors[:3]) or None,
                published_at=published or None,
                summary=abstract[:500] or None,
                language="en",
                platform=platform,
                extra={
                    "arxiv_id": arxiv_id,
                    "venue": f"arXiv ({primary})",
                    "categories": categories,
                    "primary_category": primary,
                    "field": _FIELD_BY_CATEGORY.get(primary, primary),
                    "paper": True,
                },
            )
        )
    return items


class ArxivProvider:
    kind = "arxiv"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        allowed = policy.get("allowed_domains") or ALLOWED_DOMAINS
        # query 由控制面 topic watch 下发；空 query 回退默认学科快照分类循环
        watch_query = (payload.get("query") or "").strip()
        if watch_query:
            return self._discover_by_query(watch_query, limit, allowed)
        per_category = max(1, limit // len(ARXIV_CATEGORIES))
        items: list[BoardItem] = []
        endpoint_url = ENDPOINT
        for index, category in enumerate(ARXIV_CATEGORIES):
            if index:
                time.sleep(_RATE_LIMIT_SECONDS)
            query = urlencode(
                {
                    "search_query": f"cat:{category}",
                    "start": 0,
                    "max_results": per_category,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }
            )
            url = f"{ENDPOINT}?{query}"
            headers = {"User-Agent": BROWSER_UA, "Accept": "application/atom+xml"}
            try:
                response = fetch_public_url(url, allowed, headers=headers)
            except PolicyError as error:
                # 单分类失败不拖垮整榜：保留已采条目，最终按 partial 上报
                failure = board_failure("api", ENDPOINT, error)
                if items:
                    partial = BoardResult(
                        "api", "partial_content", endpoint_url, items=items,
                        error_code=failure.error_code,
                    )
                    return partial
                return failure
            outcome = classify_http_status(response.status)
            if outcome != "success":
                if items:
                    return BoardResult(
                        "api",
                        "partial_content",
                        endpoint_url,
                        items=items,
                        http_status=response.status,
                        retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
                        error_code=f"http_{response.status}",
                    )
                return BoardResult(
                    "api",
                    outcome,
                    response.final_url,
                    http_status=response.status,
                    retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
                    error_code=f"http_{response.status}",
                )
            items.extend(
                parse_atom_feed(
                    response.body.decode("utf-8", "replace"),
                    category,
                    per_category,
                    self.kind,
                )
            )
            if len(items) >= limit:
                break
        return BoardResult("api", "success", endpoint_url, items=items[:limit])

    def _discover_by_query(self, query: str, limit: int, allowed: list[str]) -> BoardResult:
        """topic watch 关键字检索：单次请求，不跑分类循环也不 sleep。"""
        # 去掉双引号防 arXiv 查询语法注入
        sanitized = query.replace('"', "")
        params = urlencode(
            {
                "search_query": f'all:"{sanitized}"',
                "start": 0,
                "max_results": limit,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        url = f"{ENDPOINT}?{params}"
        headers = {"User-Agent": BROWSER_UA, "Accept": "application/atom+xml"}
        try:
            response = fetch_public_url(url, allowed, headers=headers)
        except PolicyError as error:
            # 与分类循环的单分类失败语义一致：直接返回失败 BoardResult
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
        items = parse_atom_feed(
            response.body.decode("utf-8", "replace"), sanitized, limit, self.kind
        )
        return BoardResult("api", "success", ENDPOINT, items=items[:limit])
