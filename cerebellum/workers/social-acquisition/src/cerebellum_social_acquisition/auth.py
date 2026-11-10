"""认证采集链（fail-closed）—— 抖音/小红书 cookie 直采 provider.

语义对齐超级达人分析网站 src/crawler/gateway.rs 的门禁：
前置条件不满足即 blocked，绝不造假数据：
  - SourcePolicy.access_mode != "authenticated_local" → policy_denied
  - 对应 cookie 文件环境变量缺失 / 文件不存在 / 内容不合格 → auth_required
cookie 从环境变量指定的本地文件读取（如 CEREBELLUM_XHS_COOKIE_FILE），
绝不进入日志、错误消息或提交内容；本仓库不携带任何明文 cookie。
"""

from __future__ import annotations

import os
from pathlib import Path

from .policy import PolicyError, classify_http_status, fetch_public_url, parse_retry_after
from .platforms.base import BROWSER_UA, BoardResult, board_failure
from .platforms.douyin import ENDPOINT as DOUYIN_ENDPOINT
from .platforms.douyin import parse_hot_board as parse_douyin_board
from .platforms.xhs import ENDPOINT as XHS_ENDPOINT
from .platforms.xhs import parse_explore_ssr

MAX_COOKIE_BYTES = 16_384


def _cookie_from_env(env_name: str, required_marker: str | None) -> str | None:
    """读取 cookie 文件；任何环节不满足都返回 None（调用方按 auth_required 处理）。"""
    path = os.environ.get(env_name, "").strip()
    if not path:
        return None
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    if not raw or len(raw) > MAX_COOKIE_BYTES:
        return None
    try:
        cookie = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not cookie:
        return None
    if required_marker and required_marker not in cookie:
        return None
    return cookie


class AuthenticatedDouyinProvider:
    """抖音认证直采：cookie + 热点榜 JSON 接口。"""

    kind = "douyin"
    cookie_env = "CEREBELLUM_DOUYIN_COOKIE_FILE"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        if policy.get("access_mode") != "authenticated_local":
            return BoardResult(
                "api",
                "policy_denied",
                DOUYIN_ENDPOINT,
                error_code="authenticated_provider_requires_authenticated_local",
            )
        cookie = _cookie_from_env(self.cookie_env, required_marker=None)
        if cookie is None:
            return BoardResult(
                "api",
                "auth_required",
                DOUYIN_ENDPOINT,
                error_code="cookie_file_missing_or_invalid",
            )
        limit = int(policy.get("max_pages_per_run") or 50)
        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "application/json",
            "Referer": "https://www.douyin.com/hot",
            "Cookie": cookie,
        }
        try:
            response = fetch_public_url(
                DOUYIN_ENDPOINT,
                policy.get("allowed_domains") or ["douyin.com", "www.douyin.com"],
                headers=headers,
            )
        except PolicyError as error:
            return board_failure("api", DOUYIN_ENDPOINT, error)
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
        items = parse_douyin_board(data, limit, self.kind)
        if not items:
            # 登录态失效的典型表现是 200 但空列表——按 auth_required 上报，不出假数据
            return BoardResult(
                "api",
                "auth_required",
                DOUYIN_ENDPOINT,
                http_status=response.status,
                error_code="empty_board_under_authentication",
            )
        return BoardResult("api", "success", DOUYIN_ENDPOINT, items=items)


class AuthenticatedXhsProvider:
    """小红书认证直采：cookie + 首页 SSR（无需 x-s 签名；cookie 仅提升可用性）。"""

    kind = "xhs"
    cookie_env = "CEREBELLUM_XHS_COOKIE_FILE"

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        if policy.get("access_mode") != "authenticated_local":
            return BoardResult(
                "api",
                "policy_denied",
                XHS_ENDPOINT,
                error_code="authenticated_provider_requires_authenticated_local",
            )
        # 对齐达人站 gateway.rs 的轻量检查：必须含 web_session
        cookie = _cookie_from_env(self.cookie_env, required_marker="web_session")
        if cookie is None:
            return BoardResult(
                "api",
                "auth_required",
                XHS_ENDPOINT,
                error_code="cookie_file_missing_or_invalid",
            )
        limit = int(policy.get("max_pages_per_run") or 50)
        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml",
            "Referer": "https://www.xiaohongshu.com/",
            "Cookie": cookie,
        }
        try:
            response = fetch_public_url(
                XHS_ENDPOINT,
                policy.get("allowed_domains") or ["xiaohongshu.com", "www.xiaohongshu.com"],
                headers=headers,
            )
        except PolicyError as error:
            return board_failure("api", XHS_ENDPOINT, error)
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
        items = parse_explore_ssr(response.body.decode("utf-8", "replace"), limit, self.kind)
        if not items:
            return BoardResult(
                "api",
                "auth_required",
                XHS_ENDPOINT,
                http_status=response.status,
                error_code="empty_feed_under_authentication",
            )
        return BoardResult("api", "success", XHS_ENDPOINT, items=items)


AUTHENTICATED_PROVIDERS = {
    "douyin": AuthenticatedDouyinProvider(),
    "xhs": AuthenticatedXhsProvider(),
}
