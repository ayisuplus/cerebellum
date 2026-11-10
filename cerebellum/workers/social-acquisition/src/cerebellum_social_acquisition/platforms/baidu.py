"""百度实时热搜榜 discovery provider（公开接口，无需登录）.

Ported from hottrack media-scraper src/platforms/baidu.py (get_hot_list).
Endpoint: https://top.baidu.com/api/board?platform=wise&tab=realtime →
data.cards[0].content[0].content[] with word / index / url / desc / hotTag.
"""

from __future__ import annotations

from urllib.parse import quote

from .base import BoardItem, BoardResult, fetch_json_board

ENDPOINT = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
ALLOWED_DOMAINS = ["baidu.com", "top.baidu.com", "www.baidu.com"]


def parse_hot_board(data: dict, limit: int, platform: str = "baidu") -> list[BoardItem]:
    cards = data.get("data", {}).get("cards", []) if isinstance(data, dict) else []
    outer = cards[0].get("content", []) if cards and isinstance(cards[0], dict) else []
    inner = outer[0].get("content", []) if outer and isinstance(outer[0], dict) else []
    items: list[BoardItem] = []
    for entry in inner[:limit]:
        if not isinstance(entry, dict):
            continue
        word = str(entry.get("word") or "").strip()
        if not word:
            continue
        rank = int(entry.get("index") or 0)
        url = str(entry.get("url") or "") or f"https://www.baidu.com/s?wd={quote(word)}"
        summary = str(entry.get("desc") or word)
        # 百度接口无 hotScore，沿用 hottrack 的排名反推热度。
        heat = max(1, 51 - rank) if rank else 1
        items.append(
            BoardItem(
                external_id=f"hot_{rank}_{word[:10]}",
                title=word,
                url=url,
                author="百度热搜",
                summary=summary,
                heat=heat,
                rank=rank,
                platform=platform,
                extra={"hot_tag": entry.get("hotTag", "")},
            )
        )
    return items


class BaiduProvider:
    kind = "baidu"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        failure, data = fetch_json_board(
            ENDPOINT,
            policy.get("allowed_domains") or ALLOWED_DOMAINS,
            referer="https://top.baidu.com/board?tab=realtime",
        )
        if failure is not None:
            return failure
        return BoardResult("api", "success", ENDPOINT, items=parse_hot_board(data or {}, limit, self.kind))
