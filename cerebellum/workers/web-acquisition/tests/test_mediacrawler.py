from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_web_acquisition.mediacrawler_bridge import MC_HOST_TO_KIND, kind_for_url
from cerebellum_web_acquisition.policy import escalation_action
from cerebellum_web_acquisition.providers import MediaCrawlerDetailProvider

XHS_URL = "https://www.xiaohongshu.com/explore/n1?xsec_token=tok&xsec_source=pc_search"


def payload(access_mode: str = "authenticated_local") -> dict:
    return {
        "source_policy": {
            "kind": "xhs",
            "access_mode": access_mode,
            "base_url": "https://www.xiaohongshu.com/",
            "allowed_domains": ["xiaohongshu.com"],
        }
    }


def enabled():
    return mock.patch.dict(os.environ, {"CEREBELLUM_ENABLE_MEDIACRAWLER": "1"}, clear=True)


def configured():
    return mock.patch(
        "cerebellum_web_acquisition.providers.configured_dir",
        return_value=Path("E:/fake/mc"),
    )


class DetailProviderGateTests(unittest.TestCase):
    def test_public_access_mode_denies(self) -> None:
        result = MediaCrawlerDetailProvider().run(XHS_URL, payload(access_mode="public"))
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "local_auth_not_allowed")

    def test_disabled_env_denies(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = MediaCrawlerDetailProvider().run(XHS_URL, payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "provider_disabled")

    def test_unconfigured_install_denies(self) -> None:
        with enabled(), mock.patch(
            "cerebellum_web_acquisition.providers.configured_dir", return_value=None
        ):
            result = MediaCrawlerDetailProvider().run(XHS_URL, payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "provider_disabled")

    def test_host_table_and_not_applicable(self) -> None:
        self.assertEqual(MC_HOST_TO_KIND["b23.tv"], "bilibili")
        self.assertEqual(kind_for_url("https://space.bilibili.com/123"), "bilibili")
        self.assertEqual(kind_for_url("https://m.weibo.com/u/1"), "weibo")
        self.assertIsNone(kind_for_url("https://www.example.com/"))
        with enabled(), configured():
            result = MediaCrawlerDetailProvider().run("https://www.example.com/post/1", payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "provider_not_applicable")

    def test_xhs_without_token_is_not_applicable(self) -> None:
        with enabled(), configured():
            result = MediaCrawlerDetailProvider().run("https://www.xiaohongshu.com/explore/n1", payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "provider_not_applicable")

    def test_ladder_scrapling_to_mediacrawler_to_open_cli(self) -> None:
        self.assertEqual(
            escalation_action("scrapling", "parse_failed", "authenticated_local"),
            "mediacrawler",
        )
        self.assertEqual(
            escalation_action("scrapling", "parse_failed", "public"),
            "mediacrawler",
        )
        self.assertEqual(
            escalation_action("mediacrawler", "parse_failed", "authenticated_local"),
            "open_cli",
        )
        self.assertIsNone(escalation_action("mediacrawler", "parse_failed", "public"))


class DetailProviderRunTests(unittest.TestCase):
    def _fixture_tmp(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="mc-detail-"))
        out_dir = tmp / "xhs" / "jsonl"
        out_dir.mkdir(parents=True)
        content = {
            "note_id": "n1",
            "note_url": XHS_URL,
            "title": "雪场攻略",
            "desc": "崇礼滑雪场三日攻略，包含装备清单、住宿推荐、交通路线、教练选择的完整说明与避坑建议，适合第一次去的雪友参考。",
            "liked_count": "512",
            "nickname": "雪**友",
        }
        comments = [
            {"comment_id": "c1", "note_id": "n1", "content": "补充：周末人非常多", "like_count": 9},
            {"comment_id": "c2", "note_id": "n1", "content": "感谢分享，已收藏", "like_count": 128},
        ]
        with open(out_dir / "detail_contents_2026-08-29.jsonl", "w", encoding="utf-8") as handle:
            handle.write(json.dumps(content, ensure_ascii=False) + "\n")
        with open(out_dir / "detail_comments_2026-08-29.jsonl", "w", encoding="utf-8") as handle:
            for comment in comments:
                handle.write(json.dumps(comment, ensure_ascii=False) + "\n")
        return tmp

    def test_detail_success_contains_body_and_comments(self) -> None:
        tmp = self._fixture_tmp()
        with enabled(), configured(), mock.patch(
            "cerebellum_web_acquisition.providers.run_mediacrawler", return_value=tmp
        ) as run_mock:
            result = MediaCrawlerDetailProvider().run(XHS_URL, payload())
        self.assertEqual(result.method, "mediacrawler")
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.title, "雪场攻略")
        assert result.cleaned_content is not None
        self.assertIn("雪场攻略\n\n崇礼滑雪场三日攻略", result.cleaned_content)
        self.assertIn("评论：\n- 感谢分享，已收藏（赞 128）\n- 补充：周末人非常多（赞 9）", result.cleaned_content)
        self.assertEqual(result.content_type, "text/markdown; charset=utf-8")
        self.assertEqual(result.discovered_urls, [])
        self.assertEqual(result.metadata["provider_version"], "2026.08.14")
        self.assertTrue(result.metadata["local_session"])
        self.assertEqual(run_mock.call_args.args[:2], ("xhs", "detail"))
        self.assertEqual(run_mock.call_args.kwargs["specified"], XHS_URL)
        self.assertEqual(run_mock.call_args.kwargs["notes_limit"], 1)

    def test_empty_detail_is_parse_failed(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mc-detail-empty-"))
        with enabled(), configured(), mock.patch(
            "cerebellum_web_acquisition.providers.run_mediacrawler", return_value=tmp
        ):
            result = MediaCrawlerDetailProvider().run(XHS_URL, payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "empty_detail")

    def test_subprocess_failure_is_parse_failed(self) -> None:
        with enabled(), configured(), mock.patch(
            "cerebellum_web_acquisition.providers.run_mediacrawler",
            side_effect=RuntimeError("exit 2"),
        ):
            result = MediaCrawlerDetailProvider().run(XHS_URL, payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "mediacrawler_failed")


if __name__ == "__main__":
    unittest.main()
