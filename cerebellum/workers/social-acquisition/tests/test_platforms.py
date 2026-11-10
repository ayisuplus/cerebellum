from __future__ import annotations

import json
import unittest
from pathlib import Path

from cerebellum_social_acquisition.platforms import (
    baidu,
    bilibili,
    douyin,
    kuaishou,
    tieba,
    weibo,
    xhs,
    zhihu,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class PlatformParseTests(unittest.TestCase):
    def test_weibo_hot_board(self) -> None:
        items = weibo.parse_hot_board(load("weibo_hot.json"), 50)
        self.assertEqual(len(items), 3)  # 空 word 条目被丢弃
        first = items[0]
        self.assertEqual(first.title, "某重大科技突破")
        self.assertEqual(first.heat, 3_456_789)
        self.assertEqual(first.rank, 1)
        self.assertIn("s.weibo.com/weibo?q=", first.url)
        self.assertEqual(first.extra["label"], "沸")
        self.assertEqual(first.platform, "weibo")
        self.assertTrue(first.external_id)
        # rank 缺失时回退 rank 字段
        self.assertEqual(items[2].rank, 4)

    def test_baidu_hot_board(self) -> None:
        items = baidu.parse_hot_board(load("baidu_hot.json"), 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "某政策正式发布")
        self.assertEqual(first.rank, 1)
        self.assertEqual(first.heat, 50)  # 51 - rank 反推
        self.assertEqual(first.summary, "某政策今日正式发布，全文共十条。")
        # 无 url 时回退搜索链接
        self.assertIn("baidu.com/s?wd=", items[1].url)

    def test_zhihu_hot_board(self) -> None:
        items = zhihu.parse_hot_board(load("zhihu_hot.json"), 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "如何看待某新发布的开源模型？")
        self.assertEqual(first.external_id, "hot_1955123456789")
        self.assertEqual(first.url, "https://www.zhihu.com/question/1955123456789")
        self.assertEqual(first.heat, 4_630_000)  # "463 万热度"
        self.assertNotIn("<p>", first.summary or "")
        self.assertEqual(first.extra["answer_count"], 342)
        self.assertEqual(items[1].heat, 120_000)

    def test_douyin_hot_board(self) -> None:
        items = douyin.parse_hot_board(load("douyin_hot.json"), 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.external_id, "7345678901234567890")
        self.assertEqual(first.heat, 9_876_543)
        self.assertEqual(first.rank, 1)
        self.assertIn("douyin.com/hot/7345678901234567890", first.url)
        # sentence_id 缺失回退搜索链接
        self.assertIn("douyin.com/search/", items[1].url)

    def test_kuaishou_hot_board(self) -> None:
        items = kuaishou.parse_hot_board(load("kuaishou_hot.json"), 50)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "某国产动画票房破纪录")
        self.assertEqual(items[0].heat, 12_490_000)  # "1249万"
        self.assertEqual(items[1].heat, 11_008_000)  # "1100.8万"
        self.assertIn("kuaishou.com/search/video?searchKey=", items[0].url)

    def test_tieba_hot_board(self) -> None:
        items = tieba.parse_hot_board(load("tieba_hot.json"), 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "某游戏新版本上线")
        self.assertEqual(first.external_id, "hot_888001")
        self.assertEqual(first.heat, 234_567)
        self.assertNotIn("&amp;", first.url)  # &amp; 反转义
        self.assertIn("topic_id=888001", first.url)
        # topic_url 缺失时按 topic_id 重建
        self.assertIn("topic_id=888002", items[1].url)
        self.assertEqual(items[1].summary, "立体设计引发讨论。")

    def test_bilibili_hot_board(self) -> None:
        items = bilibili.parse_hot_board(load("bilibili_popular.json"), 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "某硬核科技测评视频")
        self.assertEqual(first.external_id, "BV1fixture001")
        self.assertEqual(first.url, "https://www.bilibili.com/video/BV1fixture001")
        self.assertEqual(first.author, "某UP主")
        self.assertEqual(first.heat, 345_678)
        self.assertEqual(first.extra["coin"], 3_456)
        self.assertTrue((first.published_at or "").endswith("Z"))

    def test_xhs_explore_ssr(self) -> None:
        html = (FIXTURES / "xhs_explore.html").read_text(encoding="utf-8")
        items = xhs.parse_explore_ssr(html, 50)
        self.assertEqual(len(items), 2)  # recQuery 非 note 被丢弃
        first = items[0]
        self.assertEqual(first.external_id, "65f0000000000000000aa001")
        self.assertEqual(first.title, "某城市周末徒步路线推荐")
        self.assertEqual(first.heat, 12_000)  # "1.2万"
        self.assertIn("xsec_token=ABtoken001", first.url)
        self.assertEqual(first.author, "某户外博主")
        # 无 xsec_token 时纯 note 链接
        self.assertNotIn("xsec_token", items[1].url)

    def test_xhs_missing_initial_state(self) -> None:
        self.assertEqual(xhs.parse_explore_ssr("<html></html>", 50), [])


if __name__ == "__main__":
    unittest.main()
