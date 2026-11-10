"""B站 wbi 签名（mixin key 重排 + md5）—— Python 标准库重写.

移植自超级达人分析网站 src/crawler/bilibili_api.rs（实测 0.1s 稳定的直采实现）：
  1. GET nav 拿 wbi_img.img_url / sub_url，取末段文件名去扩展名得 img_key / sub_key
  2. img_key + sub_key 拼成 64 位原始 key，按 MIXIN_KEY_ENC_TAB 重排前 32 位得 mixin_key
  3. 参数按 key 字典序排序 + 追加 wts，value 过滤 !'()* 后 urlencode，
     query + mixin_key 做 MD5 得 w_rid
"""

from __future__ import annotations

import hashlib
import time

# B站固定的 mixin key 编码重排表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19,
    29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30,
    4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
)


def urlencode(value: str) -> str:
    """最小 URL 编码（保留 RFC3986 unreserved）。"""
    out: list[str] = []
    for byte in value.encode("utf-8"):
        char = chr(byte)
        if char in _UNRESERVED:
            out.append(char)
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def key_from_url(url: str) -> str:
    """从 img_url/sub_url 取末段文件名并去掉扩展名。"""
    return url.rsplit("/", 1)[-1].split(".", 1)[0]


def mixin_key(orig: str) -> str:
    """按 MIXIN_KEY_ENC_TAB 重排原始 key 前 32 位。"""
    return "".join(orig[index] for index in MIXIN_KEY_ENC_TAB if index < len(orig))[:32]


def mixin_key_from_urls(img_url: str, sub_url: str) -> str:
    return mixin_key(key_from_url(img_url) + key_from_url(sub_url))


def wbi_sign(params: list[tuple[str, str]], key: str, wts: int | None = None) -> tuple[str, str]:
    """对请求参数做 wbi 签名，返回 (wts, w_rid)。"""
    timestamp = str(int(wts if wts is not None else time.time()))
    combined = sorted(params + [("wts", timestamp)], key=lambda pair: pair[0])
    forbidden = set("!'()*")
    query = "&".join(
        f"{name}={urlencode(''.join(char for char in value if char not in forbidden))}"
        for name, value in combined
    )
    digest = hashlib.md5((query + key).encode("utf-8")).hexdigest()  # noqa: S324 — B站协议要求 md5
    return timestamp, digest


def signed_query(params: list[tuple[str, str]], key: str, wts: int | None = None) -> str:
    """返回带 wts/w_rid 的完整 query string。"""
    timestamp, w_rid = wbi_sign(params, key, wts)
    combined = sorted(params + [("wts", timestamp), ("w_rid", w_rid)], key=lambda pair: pair[0])
    return "&".join(f"{name}={urlencode(value)}" for name, value in combined)
