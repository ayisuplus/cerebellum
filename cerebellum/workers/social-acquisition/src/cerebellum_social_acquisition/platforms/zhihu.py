"""知乎热榜 discovery provider（公开 APP 域名接口，无需登录）.

Ported from hottrack media-scraper src/platforms/zhihu.py (get_hot_list).
关键：走 APP 域名 api.zhihu.com（网页端 www.zhihu.com/api/v3 匿名 401）。
Endpoint: https://api.zhihu.com/topstory/hot-list → data[] with
target{title,id,excerpt,author,answer_count,follower_count} / detail_text / trend.

注意：知乎 APP 接口对部分出口 IP 仍可能返回 0 条或 401（hottrack 已知现状），
本 worker 保持 fail-closed：非 200 即按 outcome 上报，不造假数据。
"""

from __future__ import annotations

import re

from .base import BoardItem, BoardResult, fetch_json_board, parse_cn_count

ENDPOINT = "https://api.zhihu.com/topstory/hot-list"
ALLOWED_DOMAINS = ["zhihu.com", "api.zhihu.com", "www.zhihu.com"]

_HTML_TAG = re.compile(r"<[^>]+>")


def _clean_html(value: str) -> str:
    return _HTML_TAG.sub("", value or "").strip()


def parse_hot_board(data: dict, limit: int, platform: str = "zhihu") -> list[BoardItem]:
    entries = data.get("data", []) if isinstance(data, dict) else []
    items: list[BoardItem] = []
    for rank, entry in enumerate(entries[:limit], 1):
        if not isinstance(entry, dict):
            continue
        target = entry.get("target") or {}
        title = str(target.get("title") or "").strip()
        if not title:
            continue
        question_id = str(target.get("id") or "")
        web_url = f"https://www.zhihu.com/question/{question_id}" if question_id else ENDPOINT
        author = target.get("author") or {}
        detail_text = str(entry.get("detail_text") or "")
        items.append(
            BoardItem(
                external_id=f"hot_{question_id}" if question_id else f"hot_{rank}_{title[:10]}",
                title=title,
                url=web_url,
                author=author.get("name") or "知乎热榜",
                summary=_clean_html(str(target.get("excerpt") or "")) or None,
                heat=parse_cn_count(detail_text),
                rank=rank,
                platform=platform,
                extra={
                    "hot_text": detail_text,
                    "question_id": question_id,
                    "answer_count": target.get("answer_count", 0),
                    "follower_count": target.get("follower_count", 0),
                    "trend": entry.get("trend", 0),
                },
            )
        )
    return items


class ZhihuProvider:
    kind = "zhihu"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        url = f"{ENDPOINT}?limit={min(limit, 50)}"
        failure, data = fetch_json_board(
            url,
            policy.get("allowed_domains") or ALLOWED_DOMAINS,
            referer="https://www.zhihu.com/hot",
        )
        if failure is not None:
            return failure
        return BoardResult("api", "success", ENDPOINT, items=parse_hot_board(data or {}, limit, self.kind))
