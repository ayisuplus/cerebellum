from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_social_acquisition.mediacrawler import (
    MC_SEARCH_URLS,
    MediaCrawlerSearchProvider,
    compose_detail_text,
    content_to_board_item,
    kind_for_url,
    read_jsonl,
)


def policy(access_mode: str = "authenticated_local") -> dict:
    return {
        "kind": "xhs",
        "name": "小红书",
        "access_mode": access_mode,
        "base_url": "https://www.xiaohongshu.com/",
        "max_pages_per_run": 50,
        "allowed_domains": ["xiaohongshu.com"],
    }


class MapperTests(unittest.TestCase):
    def test_xhs_style_row_maps_to_board_item(self) -> None:
        row = {
            "note_id": "64ab12",
            "note_url": "https://www.xiaohongshu.com/explore/64ab12?xsec_token=t&xsec_source=pc_search",
            "title": "滑雪初体验",
            "desc": "第一次滑雪的全记录",
            "liked_count": "1234",
            "nickname": "小**酱",
            "create_time": 1_790_000_000_000,  # epoch ms
            "source_keyword": "滑雪",
        }
        item = content_to_board_item(row, "xhs", 1)
        assert item is not None
        self.assertEqual(item.external_id, "64ab12")
        self.assertEqual(item.url, row["note_url"])
        self.assertEqual(item.title, "滑雪初体验")
        self.assertEqual(item.summary, "第一次滑雪的全记录")
        self.assertEqual(item.author, "小**酱")
        self.assertEqual(item.heat, 1234)
        self.assertEqual(item.rank, 1)
        self.assertEqual(item.platform, "xhs")
        self.assertTrue(item.published_at and item.published_at.endswith("Z"))
        self.assertEqual(item.extra["source_keyword"], "滑雪")

    def test_douyin_style_row_maps_to_board_item(self) -> None:
        row = {
            "aweme_id": "7331",
            "aweme_url": "https://www.douyin.com/video/7331",
            "title": "",
            "desc": "只有描述没有标题的抖音视频",
            "liked_count": "567",
            "nickname": "抖**音",
            "time": 1_790_000_000,  # epoch seconds
            "source_keyword": "滑雪",
        }
        item = content_to_board_item(row, "douyin", 2)
        assert item is not None
        self.assertEqual(item.external_id, "7331")
        self.assertEqual(item.title, "只有描述没有标题的抖音视频"[:80])
        self.assertEqual(item.heat, 567)
        self.assertTrue(item.published_at and item.published_at.endswith("Z"))

    def test_missing_id_or_url_returns_none(self) -> None:
        self.assertIsNone(content_to_board_item({"note_url": "https://x"}, "xhs", 1))
        self.assertIsNone(content_to_board_item({"note_id": "1"}, "xhs", 1))

    def test_bad_heat_and_time_degrade_not_crash(self) -> None:
        row = {"note_id": "1", "note_url": "https://x", "liked_count": "N/A", "create_time": "soon"}
        item = content_to_board_item(row, "xhs", 1)
        assert item is not None
        self.assertEqual(item.heat, 0)
        self.assertIsNone(item.published_at)

    def test_kind_for_url_subdomain_semantics(self) -> None:
        self.assertEqual(kind_for_url("https://www.xiaohongshu.com/explore/1"), "xhs")
        self.assertEqual(kind_for_url("https://b23.tv/abc"), "bilibili")
        self.assertEqual(kind_for_url("https://tieba.baidu.com/p/1"), "tieba")
        self.assertIsNone(kind_for_url("https://notxiaohongshu.com/"))
        self.assertIsNone(kind_for_url("https://example.com/"))


class SearchProviderGateTests(unittest.TestCase):
    def test_unconfigured_install_denies(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = MediaCrawlerSearchProvider("xhs").discover(
                {"source_policy": policy(), "query": "滑雪"}
            )
        self.assertEqual(result.method, "api")
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "mediacrawler_not_configured")

    def test_public_access_mode_denies(self) -> None:
        result = MediaCrawlerSearchProvider("xhs").discover(
            {"source_policy": policy(access_mode="public"), "query": "滑雪"}
        )
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "local_auth_not_allowed")

    def test_empty_query_denies(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.mediacrawler.configured_dir",
            return_value=Path("E:/fake/mc"),
        ):
            result = MediaCrawlerSearchProvider("xhs").discover(
                {"source_policy": policy(), "query": "   "}
            )
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "empty_query")

    def test_subprocess_failure_maps_to_parse_failed(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.mediacrawler.configured_dir",
            return_value=Path("E:/fake/mc"),
        ), mock.patch(
            "cerebellum_social_acquisition.mediacrawler.run_mediacrawler",
            side_effect=RuntimeError("exit 2"),
        ):
            result = MediaCrawlerSearchProvider("xhs").discover(
                {"source_policy": policy(), "query": "滑雪"}
            )
        self.assertEqual(result.method, "mediacrawler")
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "mediacrawler_failed")


class SearchParseChainTests(unittest.TestCase):
    def test_discover_reads_fixture_jsonl_in_rank_order(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mc-fixture-"))
        out_dir = tmp / "xhs" / "jsonl"
        out_dir.mkdir(parents=True)
        rows = [
            {
                "note_id": "n1",
                "note_url": "https://www.xiaohongshu.com/explore/n1?xsec_token=a",
                "title": "第一条",
                "desc": "描述一",
                "liked_count": "88",
                "nickname": "用**一",
                "create_time": 1_790_000_000_000,
                "source_keyword": "滑雪",
            },
            {
                "note_id": "n2",
                "note_url": "https://www.xiaohongshu.com/explore/n2?xsec_token=b",
                "title": "第二条",
                "desc": "描述二",
                "liked_count": "9999",
                "nickname": "用**二",
                "create_time": 1_790_000_100_000,
                "source_keyword": "滑雪",
            },
        ]
        with open(out_dir / "search_contents_2026-08-29.jsonl", "w", encoding="utf-8") as handle:
            handle.write(json.dumps(rows[0], ensure_ascii=False) + "\n")
            handle.write("{broken json line\n")
            handle.write(json.dumps(rows[1], ensure_ascii=False) + "\n")

        with mock.patch(
            "cerebellum_social_acquisition.mediacrawler.configured_dir",
            return_value=Path("E:/fake/mc"),
        ), mock.patch(
            "cerebellum_social_acquisition.mediacrawler.run_mediacrawler",
            return_value=tmp,
        ) as run_mock:
            result = MediaCrawlerSearchProvider("xhs").discover(
                {"source_policy": policy(), "query": "滑雪"}
            )

        self.assertEqual(result.method, "mediacrawler")
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.url, MC_SEARCH_URLS["xhs"].format(q="%E6%BB%91%E9%9B%AA"))
        self.assertEqual([item.external_id for item in result.items], ["n1", "n2"])
        self.assertEqual([item.rank for item in result.items], [1, 2])
        self.assertEqual([item.heat for item in result.items], [88, 9999])
        # notes_limit is capped at 30 even when the policy allows 50 pages
        self.assertEqual(run_mock.call_args.kwargs["notes_limit"], 30)

    def test_read_jsonl_skips_missing_and_bad(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mc-jsonl-"))
        self.assertEqual(read_jsonl(tmp, "xhs", "search", "contents"), [])

    def test_compose_detail_text_sorts_comments_by_likes(self) -> None:
        contents = [{"title": "标题", "desc": "正文内容"}]
        comments = [
            {"content": "低赞评论", "like_count": 2},
            {"content": "高赞评论", "like_count": 100},
            {"content": "  ", "like_count": 999},  # blank content dropped
        ]
        title, text = compose_detail_text(contents, comments, max_comments=20)
        self.assertEqual(title, "标题")
        self.assertIn("标题\n\n正文内容", text)
        self.assertIn("评论：\n- 高赞评论（赞 100）\n- 低赞评论（赞 2）", text)
        self.assertNotIn("999", text)


if __name__ == "__main__":
    unittest.main()
