"""小红书推荐页 discovery provider（公开 SSR 初始状态解析，无需登录/签名）.

Ported from hottrack media-scraper src/platforms/xhs.py (get_hot_list).
小红书是 SSR 渲染，推荐笔记数据注入在首页 HTML 的 window.__INITIAL_STATE__
中，直接解析即可，无需 x-s/x-t 签名。搜索/详情 TODO stub 按约定不移植。
"""

from __future__ import annotations

import json
import re

from ..policy import PolicyError, classify_http_status, fetch_public_url, parse_retry_after
from .base import BROWSER_UA, BoardItem, BoardResult, board_failure, parse_cn_count

ENDPOINT = "https://www.xiaohongshu.com/explore"
ALLOWED_DOMAINS = ["xiaohongshu.com", "www.xiaohongshu.com"]

_STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*({.*?})</script>", re.S)


def parse_explore_ssr(html_text: str, limit: int, platform: str = "xhs") -> list[BoardItem]:
    match = _STATE_RE.search(html_text)
    if not match:
        return []
    # 小红书用 undefined 占位，替换为 null 才能 JSON 解析
    raw = match.group(1).replace("undefined", "null")
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return []
    feeds = state.get("feed", {}).get("feeds", []) if isinstance(state, dict) else []
    items: list[BoardItem] = []
    for entry in feeds:
        if len(items) >= limit:
            break
        if not isinstance(entry, dict) or entry.get("modelType") != "note":
            continue
        card = entry.get("noteCard") or {}
        note_id = str(entry.get("id") or "")
        title = str(card.get("displayTitle") or card.get("desc") or "").strip()
        if not note_id or not title:
            continue
        user = card.get("user") or {}
        like_count = parse_cn_count((card.get("interactInfo") or {}).get("likedCount", "0"))
        # 带 xsec_token 的链接才能正常打开
        xsec = str(entry.get("xsecToken") or "")
        note_url = (
            f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec}&xsec_source=pc_feed"
            if xsec
            else f"https://www.xiaohongshu.com/explore/{note_id}"
        )
        items.append(
            BoardItem(
                external_id=note_id,
                title=title,
                url=note_url,
                author=user.get("nickname") or user.get("nickName") or None,
                summary=str(card.get("desc") or title),
                heat=like_count,
                rank=len(items) + 1,
                platform=platform,
                extra={"type": card.get("type", ""), "like_count": like_count},
            )
        )
    return items


class XhsProvider:
    kind = "xhs"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        limit = int(policy.get("max_pages_per_run") or 50)
        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml",
            "Referer": "https://www.xiaohongshu.com/",
        }
        try:
            response = fetch_public_url(
                ENDPOINT,
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
        text = response.body.decode("utf-8", "replace")
        items = parse_explore_ssr(text, limit, self.kind)
        if not items:
            return BoardResult(
                "api",
                "parse_failed",
                response.final_url,
                http_status=response.status,
                error_code="initial_state_missing",
            )
        return BoardResult("api", "success", ENDPOINT, items=items)
