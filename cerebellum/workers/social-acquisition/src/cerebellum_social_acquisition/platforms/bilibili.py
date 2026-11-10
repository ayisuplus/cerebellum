"""B站综合热门榜 discovery provider（公开接口，无需登录）.

主路径移植自超级达人分析网站 src/crawler/bilibili_api.rs 的 wbi 直采
（nav 取 mixin key → wbi 签名请求，实测 0.1s 稳定，规避风控）；失败时
回退 hottrack media-scraper src/platforms/bilibili.py 的匿名热门接口。
解析逻辑两侧一致：data.list[] with title / bvid / owner / stat / pubdate.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..wbi import mixin_key_from_urls, signed_query
from .base import BoardItem, BoardResult, fetch_json_board

POPULAR_ENDPOINT = "https://api.bilibili.com/x/web-interface/popular"
NAV_ENDPOINT = "https://api.bilibili.com/x/web-interface/nav"
ALLOWED_DOMAINS = ["bilibili.com", "api.bilibili.com", "www.bilibili.com"]


def parse_hot_board(data: dict, limit: int, platform: str = "bilibili") -> list[BoardItem]:
    entries = data.get("data", {}).get("list", []) if isinstance(data, dict) else []
    items: list[BoardItem] = []
    for rank, entry in enumerate(entries[:limit], 1):
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        bvid = str(entry.get("bvid") or "")
        aid = entry.get("aid") or ""
        owner = entry.get("owner") or {}
        stat = entry.get("stat") or {}
        pubdate = entry.get("pubdate") or 0
        published_at = (
            datetime.fromtimestamp(int(pubdate), tz=timezone.utc).isoformat().replace("+00:00", "Z")
            if pubdate
            else None
        )
        video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else POPULAR_ENDPOINT
        items.append(
            BoardItem(
                external_id=bvid or str(aid),
                title=title,
                url=video_url,
                author=owner.get("name") or None,
                published_at=published_at,
                summary=str(entry.get("desc") or title),
                heat=int(stat.get("view") or 0),
                rank=rank,
                platform=platform,
                extra={
                    "bvid": bvid,
                    "aid": aid,
                    "view": stat.get("view", 0),
                    "like": stat.get("like", 0),
                    "reply": stat.get("reply", 0),
                    "share": stat.get("share", 0),
                    "danmaku": stat.get("danmaku", 0),
                    "favorite": stat.get("favorite", 0),
                    "coin": stat.get("coin", 0),
                    "tname": entry.get("tname", ""),
                },
            )
        )
    return items


class BilibiliProvider:
    kind = "bilibili"

    def _fetch_wbi_key(self, allowed_domains: list[str]) -> str | None:
        """从 nav 接口取 wbi 密钥并计算 mixin_key；失败返回 None（退化为裸调）。"""
        failure, nav = fetch_json_board(
            NAV_ENDPOINT,
            allowed_domains,
            referer="https://www.bilibili.com/",
        )
        if failure is not None or not isinstance(nav, dict):
            return None
        wbi_img = (nav.get("data") or {}).get("wbi_img") or {}
        img_url = wbi_img.get("img_url")
        sub_url = wbi_img.get("sub_url")
        if not img_url or not sub_url:
            return None
        return mixin_key_from_urls(str(img_url), str(sub_url))

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        allowed = policy.get("allowed_domains") or ALLOWED_DOMAINS
        limit = int(policy.get("max_pages_per_run") or 50)
        page_size = min(limit, 20)
        # 主路径：wbi 签名请求（达人站实测稳定）；失败回退匿名裸调。
        key = self._fetch_wbi_key(allowed)
        if key:
            query = signed_query([("ps", str(page_size)), ("pn", "1")], key)
            failure, data = fetch_json_board(
                f"{POPULAR_ENDPOINT}?{query}",
                allowed,
                referer="https://www.bilibili.com/v/popular/all",
            )
            if failure is None and isinstance(data, dict) and data.get("code") == 0:
                return BoardResult(
                    "api",
                    "success",
                    POPULAR_ENDPOINT,
                    items=parse_hot_board(data, limit, self.kind),
                )
        failure, data = fetch_json_board(
            f"{POPULAR_ENDPOINT}?ps={page_size}&pn=1",
            allowed,
            referer="https://www.bilibili.com/v/popular/all",
        )
        if failure is not None:
            return failure
        if isinstance(data, dict) and data.get("code") not in (0, None):
            return BoardResult(
                "api",
                "server_error",
                POPULAR_ENDPOINT,
                error_code=f"bilibili_code_{data.get('code')}",
            )
        return BoardResult(
            "api", "success", POPULAR_ENDPOINT, items=parse_hot_board(data or {}, limit, self.kind)
        )
