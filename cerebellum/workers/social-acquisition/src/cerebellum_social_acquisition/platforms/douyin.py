"""抖音热点榜 discovery provider（公开接口，无需登录）.

Ported from hottrack media-scraper src/platforms/douyin.py (get_hot_list).
Endpoint: https://www.douyin.com/aweme/v1/web/hot/search/list/ →
data.word_list[] with word / hot_value / sentence_id / position / word_cover.

注意：抖音 web 接口的签名要求会变化，匿名请求可能返回 0 条或非 200
（hottrack 已知现状）；本 worker 保持 fail-closed，不伪造条目。
"""

from __future__ import annotations

from urllib.parse import quote

from .base import BoardItem, BoardResult, fetch_json_board

ENDPOINT = (
    "https://www.douyin.com/aweme/v1/web/hot/search/list/"
    "?device_platform=webapp&aid=6383&channel=channel_pc_web"
)
ALLOWED_DOMAINS = ["douyin.com", "www.douyin.com"]


def parse_hot_board(data: dict, limit: int, platform: str = "douyin") -> list[BoardItem]:
    word_list = data.get("data", {}).get("word_list", []) if isinstance(data, dict) else []
    items: list[BoardItem] = []
    for entry in word_list[:limit]:
        if not isinstance(entry, dict):
            continue
        word = str(entry.get("word") or "").strip()
        if not word:
            continue
        heat = int(entry.get("hot_value") or 0)
        position = int(entry.get("position") or 0)
        sentence_id = str(entry.get("sentence_id") or "")
        search_url = f"https://www.douyin.com/search/{quote(word)}"
        hot_url = f"https://www.douyin.com/hot/{sentence_id}" if sentence_id else search_url
        items.append(
            BoardItem(
                external_id=sentence_id or f"hot_{position}_{word[:10]}",
                title=word,
                url=hot_url,
                author="抖音热点",
                summary=word,
                heat=heat,
                rank=position,
                platform=platform,
                extra={
                    "hot_value": heat,
                    "sentence_id": sentence_id,
                    "group_id": entry.get("group_id", ""),
                    "label": entry.get("label", 0),
                    "search_url": search_url,
                },
            )
        )
    return items


class DouyinProvider:
    kind = "douyin"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        failure, data = fetch_json_board(
            ENDPOINT,
            policy.get("allowed_domains") or ALLOWED_DOMAINS,
            referer="https://www.douyin.com/hot",
        )
        if failure is not None:
            return failure
        return BoardResult("api", "success", ENDPOINT, items=parse_hot_board(data or {}, limit, self.kind))
