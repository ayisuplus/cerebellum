from __future__ import annotations

import unittest

from cerebellum_social_acquisition.wbi import (
    key_from_url,
    mixin_key,
    mixin_key_from_urls,
    urlencode,
    wbi_sign,
)

# 与超级达人分析网站 src/crawler/bilibili_api.rs 相同的公开测试向量
ORIG_KEY = "7cd084941338484aae1ad9425b84077c4932caff0ff746eab6f01bf08b70ac45"
EXPECTED_MIXIN = "ea1db124af3c7062474693fa704f4ff8"


class WbiTests(unittest.TestCase):
    def test_key_from_url(self) -> None:
        self.assertEqual(
            key_from_url("https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"),
            "7cd084941338484aae1ad9425b84077c",
        )

    def test_mixin_key_matches_reference(self) -> None:
        self.assertEqual(mixin_key(ORIG_KEY), EXPECTED_MIXIN)
        self.assertEqual(len(EXPECTED_MIXIN), 32)

    def test_mixin_key_from_urls(self) -> None:
        value = mixin_key_from_urls(
            "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
            "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png",
        )
        self.assertEqual(value, EXPECTED_MIXIN)

    def test_urlencode_unreserved(self) -> None:
        self.assertEqual(urlencode("a b"), "a%20b")
        self.assertEqual(urlencode("-_.~"), "-_.~")
        self.assertEqual(urlencode("中文"), "%E4%B8%AD%E6%96%87")

    def test_wbi_sign_deterministic(self) -> None:
        wts, first = wbi_sign([("foo", "114"), ("bar", "514"), ("baz", "1919810")], EXPECTED_MIXIN, wts=1_684_746_387)
        _, second = wbi_sign([("baz", "1919810"), ("foo", "114"), ("bar", "514")], EXPECTED_MIXIN, wts=1_684_746_387)
        self.assertEqual(wts, "1684746387")
        self.assertEqual(first, second)  # 参数顺序无关（按 key 排序）
        self.assertEqual(first, "cf8c26a9acd82f9e961cf282adb501a2")
        self.assertEqual(len(first), 32)

    def test_wbi_sign_filters_special_chars(self) -> None:
        # value 中 !'()* 被过滤后才参与签名（与 Rust 版一致）
        _, signed = wbi_sign([("q", "a!b'c(d)e*f")], "abc", wts=1)
        _, plain = wbi_sign([("q", "abcdef")], "abc", wts=1)
        self.assertEqual(signed, plain)


if __name__ == "__main__":
    unittest.main()
