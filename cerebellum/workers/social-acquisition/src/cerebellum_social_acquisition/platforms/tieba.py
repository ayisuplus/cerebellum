"""百度贴吧热议话题榜 discovery provider（公开接口，无需登录）.

Ported from hottrack media-scraper src/platforms/tieba.py (get_hot_list).
Endpoint: https://tieba.baidu.com/hottopic/browse/topicList →
data.bang_topic.topic_list[] with topic_name / topic_desc / discuss_num /
idx_num / topic_url / topic_id.
"""

from __future__ import annotations

import html

from .base import BoardItem, BoardResult, fetch_json_board

ENDPOINT = "https://tieba.baidu.com/hottopic/browse/topicList"
ALLOWED_DOMAINS = ["baidu.com", "tieba.baidu.com"]


def parse_hot_board(data: dict, limit: int, platform: str = "tieba") -> list[BoardItem]:
    topic_list = (
        data.get("data", {}).get("bang_topic", {}).get("topic_list", [])
        if isinstance(data, dict)
        else []
    )
    items: list[BoardItem] = []
    for entry in topic_list[:limit]:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("topic_name") or "").strip()
        if not name:
            continue
        topic_id = str(entry.get("topic_id") or "")
        rank = int(entry.get("idx_num") or 0)
        discuss_num = int(entry.get("discuss_num") or 0)
        # topic_url 含 &amp; 需反转义
        topic_url = html.unescape(str(entry.get("topic_url") or ""))
        if not topic_url and topic_id:
            topic_url = f"https://tieba.baidu.com/hottopic/browse/hottopic?topic_id={topic_id}"
        if not topic_url:
            continue
        summary = str(entry.get("topic_desc") or entry.get("abstract") or "")
        items.append(
            BoardItem(
                external_id=f"hot_{topic_id}" if topic_id else f"hot_{rank}_{name[:10]}",
                title=name,
                url=topic_url,
                author="贴吧热议",
                summary=summary or None,
                heat=discuss_num,
                rank=rank,
                platform=platform,
                extra={
                    "discuss_num": discuss_num,
                    "topic_id": topic_id,
                    "tag": entry.get("tag", ""),
                },
            )
        )
    return items


class TiebaProvider:
    kind = "tieba"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        failure, data = fetch_json_board(
            ENDPOINT,
            policy.get("allowed_domains") or ALLOWED_DOMAINS,
            referer="https://tieba.baidu.com/",
        )
        if failure is not None:
            return failure
        return BoardResult("api", "success", ENDPOINT, items=parse_hot_board(data or {}, limit, self.kind))
