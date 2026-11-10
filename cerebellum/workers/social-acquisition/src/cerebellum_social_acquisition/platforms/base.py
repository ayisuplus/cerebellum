"""Discovery provider base contract for social hot boards and paper collectors.

Every provider turns one source policy into a list of `BoardItem`s that map
onto the control-plane `DiscoveryItem` contract (external_id/title/url plus
heat/rank extensions carried in `extra`). Providers never persist anything;
storage, scheduling, and per-document fetching all belong to the control
plane and the web-acquisition worker.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..policy import PolicyError, classify_http_status, fetch_public_url, parse_retry_after

# A single modern desktop UA. Chinese hot-board endpoints reject obvious bot
# agents; a fixed browser-like UA is sufficient for the public JSON APIs used
# here (rotation pools belong to the authenticated runners, not this worker).
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_COUNT_RE = re.compile(r"([\d.]+)\s*(亿|万|w|k)?", re.I)


def parse_cn_count(value: object) -> int:
    """Parse Chinese heat text: '1249万' -> 12490000, '463 万热度' -> 4630000."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return 0
    match = _COUNT_RE.search(value)
    if not match:
        return 0
    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit == "亿":
        number *= 100_000_000
    elif unit in {"万", "w"}:
        number *= 10_000
    elif unit == "k":
        number *= 1_000
    return int(number)


@dataclass
class BoardItem:
    """One discovered entry; mirrors the control-plane DiscoveryItem shape."""

    external_id: str | None
    title: str
    url: str
    author: str | None = None
    published_at: str | None = None
    summary: str | None = None
    language: str | None = None
    heat: int = 0
    rank: int = 0
    platform: str = ""
    extra: dict = field(default_factory=dict)

    def as_discovery(self) -> dict:
        return {
            "external_id": self.external_id,
            "title": self.title,
            "url": self.url,
            "author": self.author,
            "published_at": self.published_at,
            "summary": self.summary,
            "language": self.language,
        }


@dataclass
class BoardResult:
    method: str
    outcome: str
    url: str
    items: list[BoardItem] = field(default_factory=list)
    http_status: int | None = None
    retry_after_seconds: int | None = None
    error_code: str | None = None


def outcome_for_error(error: PolicyError) -> tuple[str, int | None]:
    return error.outcome, None


def board_failure(method: str, url: str, error: PolicyError) -> BoardResult:
    return BoardResult(
        method,
        error.outcome,
        url,
        error_code=error.outcome,
        retry_after_seconds=60 if error.outcome in {"rate_limited", "timeout", "server_error"} else None,
    )


def fetch_json_board(
    url: str,
    allowed_domains: list[str],
    *,
    referer: str | None = None,
    accept: str = "application/json",
    method: str = "api",
) -> tuple[BoardResult | None, dict | None]:
    """Fetch a JSON hot board through the pinned policy HTTP stack.

    Returns (failure, None) on any non-success outcome, (None, decoded) on
    success. Callers keep parsing separate so fixtures can exercise it
    without network access.
    """
    headers = {"User-Agent": BROWSER_UA, "Accept": accept}
    if referer:
        headers["Referer"] = referer
    try:
        response = fetch_public_url(url, allowed_domains, headers=headers)
    except PolicyError as error:
        return board_failure(method, url, error), None
    outcome = classify_http_status(response.status)
    if outcome != "success":
        return BoardResult(
            method,
            outcome,
            response.final_url,
            http_status=response.status,
            retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
            error_code=f"http_{response.status}",
        ), None
    try:
        decoded = json.loads(response.body.decode("utf-8", "replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return BoardResult(
            method,
            "parse_failed",
            response.final_url,
            http_status=response.status,
            error_code="invalid_json",
        ), None
    if not isinstance(decoded, dict):
        return BoardResult(
            method,
            "parse_failed",
            response.final_url,
            http_status=response.status,
            error_code="unexpected_json_shape",
        ), None
    return None, decoded
