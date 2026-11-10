from __future__ import annotations

import unittest
from unittest import mock

from cerebellum_social_acquisition.platforms import bilibili, kuaishou, xhs
from cerebellum_social_acquisition.platforms.base import (
    BoardItem,
    BoardResult,
    board_failure,
    fetch_json_board,
    outcome_for_error,
    parse_cn_count,
)
from cerebellum_social_acquisition.policy import PolicyError


class FakeResponse:
    def __init__(self, status: int, body: bytes, headers: dict | None = None, final_url: str = ""):
        self.status = status
        self.body = body
        self.headers = headers or {}
        self.final_url = final_url or "https://example.com/final"


class ParseCnCountTests(unittest.TestCase):
    def test_none_and_non_string_return_zero(self) -> None:
        self.assertEqual(parse_cn_count(None), 0)
        self.assertEqual(parse_cn_count(object()), 0)
        self.assertEqual(parse_cn_count([1, 2]), 0)

    def test_numeric_passthrough(self) -> None:
        self.assertEqual(parse_cn_count(42), 42)
        self.assertEqual(parse_cn_count(3.9), 3)

    def test_chinese_units(self) -> None:
        self.assertEqual(parse_cn_count("1249万"), 12_490_000)
        self.assertEqual(parse_cn_count("463 万热度"), 4_630_000)
        self.assertEqual(parse_cn_count("2亿"), 200_000_000)
        self.assertEqual(parse_cn_count("5w"), 50_000)
        self.assertEqual(parse_cn_count("7K"), 7_000)

    def test_plain_number_and_garbage(self) -> None:
        self.assertEqual(parse_cn_count("12345"), 12_345)
        self.assertEqual(parse_cn_count("热度爆表"), 0)
        self.assertEqual(parse_cn_count(""), 0)


class BaseHelpersTests(unittest.TestCase):
    def test_board_item_as_discovery_shape(self) -> None:
        item = BoardItem(
            external_id="x1",
            title="标题",
            url="https://example.com/1",
            author="作者",
            published_at="2026-01-01T00:00:00Z",
            summary="摘要",
            language="zh",
            heat=9,
            rank=2,
            platform="weibo",
            extra={"noise": True},
        )
        discovery = item.as_discovery()
        self.assertEqual(
            discovery,
            {
                "external_id": "x1",
                "title": "标题",
                "url": "https://example.com/1",
                "author": "作者",
                "published_at": "2026-01-01T00:00:00Z",
                "summary": "摘要",
                "language": "zh",
            },
        )
        self.assertNotIn("extra", discovery)

    def test_outcome_for_error(self) -> None:
        error = PolicyError("nope", outcome="rate_limited")
        self.assertEqual(outcome_for_error(error), ("rate_limited", None))

    def test_board_failure_retry_hint_by_outcome(self) -> None:
        for outcome in ("rate_limited", "timeout", "server_error"):
            result = board_failure("api", "https://x", PolicyError("e", outcome=outcome))
            self.assertEqual(result.retry_after_seconds, 60)
            self.assertEqual(result.error_code, outcome)
        denied = board_failure("api", "https://x", PolicyError("e", outcome="policy_denied"))
        self.assertIsNone(denied.retry_after_seconds)


class FetchJsonBoardTests(unittest.TestCase):
    URL = "https://api.example.com/board"

    def test_policy_error_maps_to_failure(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.platforms.base.fetch_public_url",
            side_effect=PolicyError("blocked", outcome="policy_denied"),
        ):
            failure, data = fetch_json_board(self.URL, ["example.com"])
        self.assertIsNone(data)
        assert failure is not None
        self.assertEqual(failure.outcome, "policy_denied")
        self.assertEqual(failure.url, self.URL)

    def test_http_error_status_with_retry_after(self) -> None:
        response = FakeResponse(429, b"{}", headers={"retry-after": "17"})
        with mock.patch(
            "cerebellum_social_acquisition.platforms.base.fetch_public_url",
            return_value=response,
        ):
            failure, data = fetch_json_board(self.URL, ["example.com"])
        self.assertIsNone(data)
        assert failure is not None
        self.assertEqual(failure.outcome, "rate_limited")
        self.assertEqual(failure.http_status, 429)
        self.assertEqual(failure.error_code, "http_429")
        self.assertEqual(failure.retry_after_seconds, 17)

    def test_invalid_json_body(self) -> None:
        response = FakeResponse(200, b"not-json{")
        with mock.patch(
            "cerebellum_social_acquisition.platforms.base.fetch_public_url",
            return_value=response,
        ):
            failure, data = fetch_json_board(self.URL, ["example.com"])
        self.assertIsNone(data)
        assert failure is not None
        self.assertEqual(failure.outcome, "parse_failed")
        self.assertEqual(failure.error_code, "invalid_json")

    def test_non_object_json_shape(self) -> None:
        response = FakeResponse(200, b'["a", "b"]')
        with mock.patch(
            "cerebellum_social_acquisition.platforms.base.fetch_public_url",
            return_value=response,
        ):
            failure, data = fetch_json_board(self.URL, ["example.com"])
        self.assertIsNone(data)
        assert failure is not None
        self.assertEqual(failure.outcome, "parse_failed")
        self.assertEqual(failure.error_code, "unexpected_json_shape")

    def test_success_sends_headers_and_decodes(self) -> None:
        captured: dict = {}

        def fake_fetch(url, allowed, *, headers=None, **kwargs):
            captured.update(headers or {})
            return FakeResponse(200, b'{"code": 0, "data": {}}')

        with mock.patch(
            "cerebellum_social_acquisition.platforms.base.fetch_public_url",
            side_effect=fake_fetch,
        ):
            failure, data = fetch_json_board(
                self.URL, ["example.com"], referer="https://ref.example/", method="render"
            )
        self.assertIsNone(failure)
        self.assertEqual(data, {"code": 0, "data": {}})
        self.assertEqual(captured.get("Referer"), "https://ref.example/")
        self.assertIn("Mozilla/5.0", captured.get("User-Agent", ""))


class BilibiliParseEdgeTests(unittest.TestCase):
    def test_non_dict_data_and_bad_entries(self) -> None:
        self.assertEqual(bilibili.parse_hot_board(["not", "dict"], 50), [])
        items = bilibili.parse_hot_board(
            {"data": {"list": ["junk", {"title": "   "}, {"title": "有效视频", "bvid": "BV1"}]}},
            50,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "有效视频")

    def test_missing_bvid_and_pubdate_fallbacks(self) -> None:
        items = bilibili.parse_hot_board(
            {"data": {"list": [{"title": "无BV号", "aid": 12345, "owner": {}, "stat": {}}]}},
            50,
        )
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.external_id, "12345")  # aid fallback
        self.assertEqual(item.url, bilibili.POPULAR_ENDPOINT)
        self.assertIsNone(item.published_at)
        self.assertIsNone(item.author)
        self.assertEqual(item.heat, 0)

    def test_limit_truncates_board(self) -> None:
        entries = [{"title": f"视频{i}", "bvid": f"BV{i}"} for i in range(10)]
        items = bilibili.parse_hot_board({"data": {"list": entries}}, 3)
        self.assertEqual(len(items), 3)
        self.assertEqual([item.rank for item in items], [1, 2, 3])


class BilibiliProviderTests(unittest.TestCase):
    def payload(self, limit: int = 5) -> dict:
        return {
            "source_policy": {
                "kind": "bilibili",
                "allowed_domains": bilibili.ALLOWED_DOMAINS,
                "max_pages_per_run": limit,
            }
        }

    def test_wbi_key_failure_returns_none(self) -> None:
        provider = bilibili.BilibiliProvider()
        with mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            return_value=(BoardResult("api", "timeout", bilibili.NAV_ENDPOINT), None),
        ):
            self.assertIsNone(provider._fetch_wbi_key(bilibili.ALLOWED_DOMAINS))

    def test_wbi_key_missing_img_fields_returns_none(self) -> None:
        provider = bilibili.BilibiliProvider()
        with mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            return_value=(None, {"data": {"wbi_img": {"img_url": "https://i/x.png"}}}),
        ):
            self.assertIsNone(provider._fetch_wbi_key(bilibili.ALLOWED_DOMAINS))

    def test_wbi_key_computed_from_nav(self) -> None:
        provider = bilibili.BilibiliProvider()
        nav = {"data": {"wbi_img": {"img_url": "https://i/img.png", "sub_url": "https://i/sub.png"}}}
        with mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            return_value=(None, nav),
        ), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.mixin_key_from_urls",
            return_value="MIXINKEY",
        ) as mixin:
            self.assertEqual(provider._fetch_wbi_key(bilibili.ALLOWED_DOMAINS), "MIXINKEY")
        mixin.assert_called_once_with("https://i/img.png", "https://i/sub.png")

    def test_discover_wbi_signed_path_success(self) -> None:
        provider = bilibili.BilibiliProvider()
        board = {"code": 0, "data": {"list": [{"title": "签名板", "bvid": "BV9"}]}}
        calls: list[str] = []

        def fake_fetch(url, allowed, **kwargs):
            calls.append(url)
            if url == bilibili.NAV_ENDPOINT:
                return None, {"data": {"wbi_img": {"img_url": "i", "sub_url": "s"}}}
            return None, board

        with mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            side_effect=fake_fetch,
        ), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.mixin_key_from_urls",
            return_value="KEY",
        ), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.signed_query",
            return_value="ps=5&pn=1&wts=1&w_rid=abc",
        ) as signed:
            result = provider.discover(self.payload())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.items[0].title, "签名板")
        signed.assert_called_once()
        self.assertIn("w_rid=abc", calls[-1])

    def test_discover_falls_back_to_anonymous_when_wbi_fails(self) -> None:
        provider = bilibili.BilibiliProvider()
        board = {"code": 0, "data": {"list": [{"title": "匿名板", "bvid": "BV2"}]}}
        with mock.patch.object(provider, "_fetch_wbi_key", return_value=None), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            return_value=(None, board),
        ):
            result = provider.discover(self.payload())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.items[0].title, "匿名板")

    def test_discover_wbi_signed_error_then_fallback(self) -> None:
        # wbi key obtained but signed request fails -> anonymous fallback still succeeds
        provider = bilibili.BilibiliProvider()
        board = {"code": 0, "data": {"list": [{"title": "回退板", "bvid": "BV3"}]}}
        failure = BoardResult("api", "rate_limited", bilibili.POPULAR_ENDPOINT, http_status=412)
        responses = iter([(failure, None), (None, board)])
        with mock.patch.object(provider, "_fetch_wbi_key", return_value="KEY"), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.signed_query",
            return_value="ps=5",
        ), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            side_effect=lambda *a, **k: next(responses),
        ):
            result = provider.discover(self.payload())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.items[0].title, "回退板")

    def test_discover_nonzero_code_is_server_error(self) -> None:
        provider = bilibili.BilibiliProvider()
        with mock.patch.object(provider, "_fetch_wbi_key", return_value=None), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            return_value=(None, {"code": -412, "data": {}}),
        ):
            result = provider.discover(self.payload())
        self.assertEqual(result.outcome, "server_error")
        self.assertEqual(result.error_code, "bilibili_code_-412")

    def test_discover_propagates_anonymous_failure(self) -> None:
        provider = bilibili.BilibiliProvider()
        failure = BoardResult("api", "timeout", bilibili.POPULAR_ENDPOINT, error_code="http_504")
        with mock.patch.object(provider, "_fetch_wbi_key", return_value=None), mock.patch(
            "cerebellum_social_acquisition.platforms.bilibili.fetch_json_board",
            return_value=(failure, None),
        ):
            result = provider.discover(self.payload())
        self.assertIs(result, failure)


class KuaishouParseEdgeTests(unittest.TestCase):
    def test_non_dict_and_malformed_entries(self) -> None:
        self.assertEqual(kuaishou.parse_hot_board(None, 50), [])
        items = kuaishou.parse_hot_board(
            {"data": {"visionHotRank": {"items": [42, {"id": "  "}, {"id": "真实热搜", "hotValue": "3k"}]}}},
            50,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "真实热搜")
        self.assertEqual(items[0].heat, 3_000)

    def test_external_id_and_url_shape(self) -> None:
        items = kuaishou.parse_hot_board(
            {"data": {"visionHotRank": {"items": [{"id": "超长热搜词汇截断测试abc", "hotValue": "1万"}]}}},
            50,
        )
        self.assertEqual(items[0].external_id, "hot_1_超长热搜词汇截断测试")
        self.assertIn("searchKey=", items[0].url)
        self.assertEqual(items[0].author, "快手热榜")
        self.assertEqual(items[0].extra["hot_value"], 10_000)

    def test_limit_truncates(self) -> None:
        entries = [{"id": f"词{i}"} for i in range(8)]
        self.assertEqual(len(kuaishou.parse_hot_board({"data": {"visionHotRank": {"items": entries}}}, 2)), 2)


class KuaishouProviderTests(unittest.TestCase):
    def payload(self) -> dict:
        return {
            "source_policy": {
                "kind": "kuaishou",
                "allowed_domains": kuaishou.ALLOWED_DOMAINS,
                "max_pages_per_run": 10,
            }
        }

    def test_policy_error_maps_to_failure(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.platforms.kuaishou.fetch_public_post_json",
            side_effect=PolicyError("denied", outcome="policy_denied"),
        ):
            result = kuaishou.KuaishouProvider().discover(self.payload())
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "policy_denied")

    def test_http_error_status(self) -> None:
        response = FakeResponse(503, b"{}", headers={"retry-after": "9"})
        with mock.patch(
            "cerebellum_social_acquisition.platforms.kuaishou.fetch_public_post_json",
            return_value=response,
        ):
            result = kuaishou.KuaishouProvider().discover(self.payload())
        self.assertEqual(result.outcome, "server_error")
        self.assertEqual(result.http_status, 503)
        self.assertEqual(result.error_code, "http_503")
        self.assertEqual(result.retry_after_seconds, 9)

    def test_invalid_json(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.platforms.kuaishou.fetch_public_post_json",
            return_value=FakeResponse(200, b"\xff\xfe{bad"),
        ):
            result = kuaishou.KuaishouProvider().discover(self.payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "invalid_json")

    def test_success_parses_board(self) -> None:
        body = '{"data":{"visionHotRank":{"items":[{"id":"快手热词","hotValue":"2w"}]}}}'.encode("utf-8")
        captured: dict = {}

        def fake_post(url, body_arg, allowed, *, headers=None, **kwargs):
            captured["body"] = body_arg
            captured.update(headers or {})
            return FakeResponse(200, body)

        with mock.patch(
            "cerebellum_social_acquisition.platforms.kuaishou.fetch_public_post_json",
            side_effect=fake_post,
        ):
            result = kuaishou.KuaishouProvider().discover(self.payload())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.items[0].title, "快手热词")
        self.assertEqual(result.items[0].heat, 20_000)
        self.assertEqual(captured["body"]["operationName"], "visionHotRank")
        self.assertIn("kuaishou.com", captured.get("Referer", ""))


class XhsParseEdgeTests(unittest.TestCase):
    def _html(self, state: str) -> str:
        return f"<html><script>window.__INITIAL_STATE__={state}</script></html>"

    def test_invalid_json_state_returns_empty(self) -> None:
        self.assertEqual(xhs.parse_explore_ssr(self._html("{bad json}"), 50), [])

    def test_undefined_placeholders_become_null(self) -> None:
        html = self._html(
            '{"feed":{"feeds":[{"modelType":"note","id":"n1","xsecToken":undefined,'
            '"noteCard":{"displayTitle":"空token笔记","user":{"nickname":"某"},'
            '"interactInfo":{"likedCount":undefined}}}]}}'
        )
        items = xhs.parse_explore_ssr(html, 50)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].heat, 0)
        self.assertNotIn("xsec_token", items[0].url)

    def test_non_note_and_incomplete_entries_skipped(self) -> None:
        html = self._html(
            '{"feed":{"feeds":['
            '"junk",'
            '{"modelType":"recQuery","id":"q1"},'
            '{"modelType":"note","id":"",'
            '"noteCard":{"displayTitle":"无ID"}},'
            '{"modelType":"note","id":"n2","noteCard":{"displayTitle":"  "}},'
            '{"modelType":"note","id":"n3","noteCard":{"displayTitle":"完整",'
            '"user":{"nickName":"驼峰昵称"},"interactInfo":{"likedCount":"1.5万"}}}'
            "]}}"
        )
        items = xhs.parse_explore_ssr(html, 50)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].external_id, "n3")
        self.assertEqual(items[0].author, "驼峰昵称")  # nickName fallback
        self.assertEqual(items[0].heat, 15_000)

    def test_desc_fallback_and_limit(self) -> None:
        feeds = ",".join(
            f'{{"modelType":"note","id":"m{i}","noteCard":{{"desc":"描述{i}"}}}}' for i in range(5)
        )
        items = xhs.parse_explore_ssr(self._html(f'{{"feed":{{"feeds":[{feeds}]}}}}'), 2)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "描述0")  # displayTitle missing -> desc
        self.assertEqual(items[0].summary, "描述0")
        self.assertEqual([item.rank for item in items], [1, 2])


class XhsProviderTests(unittest.TestCase):
    def payload(self) -> dict:
        return {
            "source_policy": {
                "kind": "xhs",
                "allowed_domains": xhs.ALLOWED_DOMAINS,
                "max_pages_per_run": 10,
            }
        }

    SSR = (
        "<script>window.__INITIAL_STATE__={\"feed\":{\"feeds\":["
        "{\"modelType\":\"note\",\"id\":\"x1\",\"noteCard\":{\"displayTitle\":\"笔记\"}}"
        "]}}</script>"
    )

    def test_policy_error_maps_to_failure(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.platforms.xhs.fetch_public_url",
            side_effect=PolicyError("denied", outcome="policy_denied"),
        ):
            result = xhs.XhsProvider().discover(self.payload())
        self.assertEqual(result.outcome, "policy_denied")

    def test_http_error_status(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.platforms.xhs.fetch_public_url",
            return_value=FakeResponse(403, b""),
        ):
            result = xhs.XhsProvider().discover(self.payload())
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.http_status, 403)
        self.assertEqual(result.error_code, "http_403")

    def test_missing_initial_state_is_parse_failed(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.platforms.xhs.fetch_public_url",
            return_value=FakeResponse(200, b"<html>no state</html>"),
        ):
            result = xhs.XhsProvider().discover(self.payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "initial_state_missing")

    def test_success_parses_ssr_feed(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.platforms.xhs.fetch_public_url",
            return_value=FakeResponse(200, self.SSR.encode("utf-8")),
        ):
            result = xhs.XhsProvider().discover(self.payload())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.items[0].title, "笔记")
        self.assertEqual(result.url, xhs.ENDPOINT)


if __name__ == "__main__":
    unittest.main()
