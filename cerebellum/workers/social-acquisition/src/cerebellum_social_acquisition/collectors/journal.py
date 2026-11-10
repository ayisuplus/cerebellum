"""Nature / Science 期刊 RSS discovery provider.

Ported from hottrack media-scraper src/collectors/journal_collector.py.
各期刊 RSS → 最新论文条目；venue 作为平台标记，供事件聚类跨期刊归并。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape

from ..policy import PolicyError, classify_http_status, fetch_public_url, parse_retry_after
from ..platforms.base import BROWSER_UA, BoardItem, BoardResult, board_failure

JOURNAL_FEEDS = {
    "nature": {
        "name": "Nature",
        "rss_url": "https://www.nature.com/nature.rss",
    },
    "science": {
        "name": "Science",
        "rss_url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    },
    "nature_biotech": {
        "name": "Nature Biotechnology",
        "rss_url": "https://www.nature.com/nbt.rss",
    },
    "nature_machine_intelligence": {
        "name": "Nature Machine Intelligence",
        "rss_url": "https://www.nature.com/natmachintell.rss",
    },
    "nature_methods": {
        "name": "Nature Methods",
        "rss_url": "https://www.nature.com/nmeth.rss",
    },
}

ALLOWED_DOMAINS = ["nature.com", "www.nature.com", "science.org", "www.science.org"]

_HTML_TAG = re.compile(r"<[^>]+>")
_YEAR_RE = re.compile(r"(\d{4})")


def _clean_html(value: str | None) -> str:
    if not value:
        return ""
    return unescape(_HTML_TAG.sub("", value)).strip()


def _parse_year(value: str) -> int | None:
    match = _YEAR_RE.search(value or "")
    return int(match.group(1)) if match else None


def _extract_doi(url: str) -> str:
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", url or "")
    return match.group(0) if match else ""


def parse_feed(xml_text: str, journal_key: str, limit: int) -> list[BoardItem]:
    """解析 RSS 2.0 / RDF（Nature 用 RDF）两种格式。"""
    feed = JOURNAL_FEEDS[journal_key]
    journal_name = feed["name"]
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    ns = {
        "rss": "http://purl.org/rss/1.0/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    items: list[BoardItem] = []

    def add(title: str, url: str, abstract: str, author: str, date_text: str) -> None:
        if len(items) >= limit or not title or not url:
            return
        doi = _extract_doi(url)
        items.append(
            BoardItem(
                external_id=doi or url,
                title=title,
                url=url,
                author=author or None,
                published_at=None,
                summary=abstract[:500] or None,
                language="en",
                platform=journal_key,
                extra={
                    "doi": doi,
                    "venue": journal_name,
                    "year": _parse_year(date_text),
                    "paper": True,
                },
            )
        )

    channel = root.find("channel")
    if channel is not None:
        for entry in channel.findall("item"):
            title = _clean_html(entry.findtext("title"))
            url = (entry.findtext("link") or "").strip()
            abstract = _clean_html(entry.findtext("description"))
            author_el = entry.find("author")
            if author_el is None:
                author_el = entry.find("{http://purl.org/dc/elements/1.1/}creator")
            author = _clean_html(author_el.text) if author_el is not None else ""
            date_text = (entry.findtext("pubDate") or "").strip()
            add(title, url, abstract, author, date_text)
        return items

    # RDF 格式：item 在根级别，使用 rss: 命名空间
    for entry in root.findall("rss:item", ns) or root.findall("{http://purl.org/rss/1.0/}item"):
        title = ""
        for path in ("rss:title", "{http://purl.org/rss/1.0/}title"):
            el = entry.find(path, ns)
            if el is not None and el.text:
                title = _clean_html(el.text)
                break
        url = ""
        for path in ("rss:link", "{http://purl.org/rss/1.0/}link"):
            el = entry.find(path, ns)
            if el is not None and el.text:
                url = el.text.strip()
                break
        if not url:
            url = entry.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "")
        abstract = ""
        for path in ("rss:description", "{http://purl.org/rss/1.0/}description"):
            el = entry.find(path, ns)
            if el is not None and el.text:
                abstract = _clean_html(el.text)
                break
        author = ""
        el = entry.find("dc:creator", ns)
        if el is not None and el.text:
            author = _clean_html(el.text)
        date_text = ""
        el = entry.find("dc:date", ns)
        if el is not None and el.text:
            date_text = el.text.strip()
        add(title, url, abstract, author, date_text)
    return items


class JournalProvider:
    kind = "journal"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        allowed = policy.get("allowed_domains") or ALLOWED_DOMAINS
        per_journal = max(1, limit // len(JOURNAL_FEEDS))
        items: list[BoardItem] = []
        for journal_key, feed in JOURNAL_FEEDS.items():
            headers = {
                "User-Agent": BROWSER_UA,
                "Accept": "application/rss+xml, application/xml, text/xml",
            }
            try:
                response = fetch_public_url(feed["rss_url"], allowed, headers=headers)
            except PolicyError as error:
                if items:
                    return BoardResult(
                        "api", "partial_content", feed["rss_url"], items=items,
                        error_code=error.outcome,
                    )
                return board_failure("api", feed["rss_url"], error)
            outcome = classify_http_status(response.status)
            if outcome != "success":
                if items:
                    return BoardResult(
                        "api",
                        "partial_content",
                        feed["rss_url"],
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
                parse_feed(
                    response.body.decode("utf-8", "replace"), journal_key, per_journal
                )
            )
        return BoardResult("api", "success", JOURNAL_FEEDS["nature"]["rss_url"], items=items[:limit])
