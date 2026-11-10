"""微博实时热搜榜 discovery provider（公开接口，无需登录）.

Ported from hottrack media-scraper src/platforms/weibo.py (get_hot_list).
Endpoint: https://weibo.com/ajax/side/hotSearch → data.realtime[] with
word(话题) / num(热度) / realpos(排名) / label_name.
"""

from __future__ import annotations

from urllib.parse import quote

from .base import BoardItem, BoardResult, fetch_json_board

ENDPOINT = "https://weibo.com/ajax/side/hotSearch"
ALLOWED_DOMAINS = ["weibo.com", "s.weibo.com"]


def parse_hot_board(data: dict, limit: int, platform: str = "weibo") -> list[BoardItem]:
    realtime = data.get("data", {}).get("realtime", []) if isinstance(data, dict) else []
    items: list[BoardItem] = []
    for entry in realtime[:limit]:
        if not isinstance(entry, dict):
            continue
        word = entry.get("word") or entry.get("note") or ""
        word = str(word).strip()
        if not word:
            continue
        heat = int(entry.get("num") or 0)
        rank = int(entry.get("realpos") or entry.get("rank") or 0)
        topic_url = f"https://s.weibo.com/weibo?q={quote('#' + word + '#')}"
        items.append(
            BoardItem(
                external_id=f"hot_{rank}_{word[:10]}",
                title=word,
                url=topic_url,
                author="微博热搜",
                summary=str(entry.get("note") or word),
                heat=heat,
                rank=rank,
                platform=platform,
                extra={
                    "hot_value": heat,
                    "label": entry.get("label_name", ""),
                    "icon_desc": entry.get("icon_desc", ""),
                    "search_url": f"https://s.weibo.com/weibo?q={quote(word)}",
                },
            )
        )
    return items


class WeiboProvider:
    kind = "weibo"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        failure, data = fetch_json_board(
            ENDPOINT,
            policy.get("allowed_domains") or ALLOWED_DOMAINS,
            referer="https://weibo.com/",
        )
        if failure is not None:
            return failure
        return BoardResult("api", "success", ENDPOINT, items=parse_hot_board(data or {}, limit, self.kind))
