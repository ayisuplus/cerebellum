"""快手热榜 discovery provider（公开 GraphQL 接口，无需登录）.

Ported from hottrack media-scraper src/platforms/kuaishou.py (get_hot_list).
Endpoint: POST https://www.kuaishou.com/graphql operationName=visionHotRank →
data.visionHotRank.items[] with id(热搜词) / hotValue(热度如"1249万").
"""

from __future__ import annotations

from urllib.parse import quote

from ..policy import PolicyError, classify_http_status, fetch_public_post_json, parse_retry_after
from .base import BROWSER_UA, BoardItem, BoardResult, board_failure, parse_cn_count

ENDPOINT = "https://www.kuaishou.com/graphql"
ALLOWED_DOMAINS = ["kuaishou.com", "www.kuaishou.com"]

_GRAPHQL_BODY = {
    "operationName": "visionHotRank",
    "variables": {},
    "query": (
        "query visionHotRank { visionHotRank { result items "
        "{ id hotValue iconUrl __typename } __typename } }"
    ),
}


def parse_hot_board(data: dict, limit: int, platform: str = "kuaishou") -> list[BoardItem]:
    entries = (
        data.get("data", {}).get("visionHotRank", {}).get("items", [])
        if isinstance(data, dict)
        else []
    )
    items: list[BoardItem] = []
    for rank, entry in enumerate(entries[:limit], 1):
        if not isinstance(entry, dict):
            continue
        word = str(entry.get("id") or "").strip()
        if not word:
            continue
        hot_text = str(entry.get("hotValue") or "")
        heat = parse_cn_count(hot_text)
        search_url = f"https://www.kuaishou.com/search/video?searchKey={quote(word)}"
        items.append(
            BoardItem(
                external_id=f"hot_{rank}_{word[:10]}",
                title=word,
                url=search_url,
                author="快手热榜",
                summary=word,
                heat=heat,
                rank=rank,
                platform=platform,
                extra={"hot_text": hot_text, "hot_value": heat},
            )
        )
    return items


class KuaishouProvider:
    kind = "kuaishou"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        headers = {
            "User-Agent": BROWSER_UA,
            "Referer": "https://www.kuaishou.com/brilliant",
        }
        try:
            response = fetch_public_post_json(
                ENDPOINT,
                _GRAPHQL_BODY,
                policy.get("allowed_domains") or ALLOWED_DOMAINS,
                headers=headers,
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
            "api", "success", ENDPOINT, items=parse_hot_board(data, limit, self.kind)
        )
