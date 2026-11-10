from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from cerebellum_social_acquisition.platforms.base import BoardItem, BoardResult
from cerebellum_social_acquisition.worker import (
    _fixture_discovery,
    _provider_for,
    language_for,
    main,
    process_one,
    redact,
    required_env,
    run_discovery,
    sanitize_text,
)


def job(provider: str = "weibo", access_mode: str = "public", **payload_overrides) -> dict:
    job_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    policy_id = str(uuid.uuid4())
    payload = {
        "plan_id": plan_id,
        "topic_ids": [str(uuid.uuid4())],
        "source_policy_id": policy_id,
        "provider": provider,
        "query": "",
        "source_policy": {
            "policy_id": policy_id,
            "kind": provider,
            "name": "微博热榜",
            "base_url": "https://weibo.com/ajax/side/hotSearch",
            "access_mode": access_mode,
            "allowed_domains": ["weibo.com", "s.weibo.com"],
            "obey_robots": True,
            "max_pages_per_run": 10,
            "raw_retention_days": 30,
            "training_license": "CC0-1.0",
            "model_terms_allow_training": True,
        },
    }
    payload.update(payload_overrides)
    return {
        "job_id": job_id,
        "kind": "social_acquisition_v1",
        "attempts": 1,
        "payload": payload,
    }


def board(items: list[BoardItem], outcome: str = "success") -> BoardResult:
    return BoardResult("api", outcome, "https://weibo.com/ajax/side/hotSearch", items=items)


def sample_items() -> list[BoardItem]:
    return [
        BoardItem(
            external_id="hot_1_a",
            title="某重大科技突破",
            url="https://s.weibo.com/weibo?q=%23某重大科技突破%23",
            summary="一项不同于标题的详细摘要内容",
            heat=3_456_789,
            rank=1,
            platform="weibo",
        ),
    ]


class FakeClient:
    def __init__(self, value: dict | None) -> None:
        self.value = value
        self.submitted: list[dict] = []
        self.failed: list[tuple] = []
        self.completed: list[str] = []
        self.reserve_error: Exception | None = None

    def claim(self, worker: str, lease_seconds: int = 0) -> dict | None:
        value, self.value = self.value, None
        return value

    def get_result(self, job_id: str) -> dict | None:
        return None

    def submit_result(self, result: dict, cleaned: str | None, raw: str | None) -> dict:
        self.submitted.append({"result": result, "cleaned": cleaned, "raw": raw})
        return {"result_hash": "0" * 64}

    def complete(self, job_id: str, worker: str) -> None:
        self.completed.append(job_id)

    def fail(self, *args) -> None:
        self.failed.append(args)

    def reserve_source_rate(self, job_id: str, worker: str, ordinal: int) -> bool:
        if self.reserve_error is not None:
            raise self.reserve_error
        return True


def run_job(value: dict, discover_result: BoardResult, provider: str = "weibo") -> FakeClient:
    client = FakeClient(value)
    fake_provider = mock.Mock()
    fake_provider.discover.return_value = discover_result
    with mock.patch.dict(
        "cerebellum_social_acquisition.worker.BOARD_PROVIDERS",
        {provider: fake_provider},
        clear=False,
    ):
        assert process_one(client, "worker-a")
    return client


class EnvAndRedactTests(unittest.TestCase):
    def test_required_env_missing_raises(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CEREBELLUM_MISSING"):
                required_env("CEREBELLUM_MISSING")

    def test_required_env_blank_raises(self) -> None:
        with mock.patch.dict(os.environ, {"CEREBELLUM_X": "   "}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "CEREBELLUM_X"):
                required_env("CEREBELLUM_X")

    def test_required_env_returns_value(self) -> None:
        with mock.patch.dict(os.environ, {"CEREBELLUM_X": "  value  "}, clear=False):
            self.assertEqual(required_env("CEREBELLUM_X"), "value")

    def test_redact_masks_token(self) -> None:
        with mock.patch.dict(os.environ, {"CEREBELLUM_TOKEN": "tok-secret-1"}, clear=False):
            self.assertEqual(redact("failed with tok-secret-1 inside"), "failed with [REDACTED] inside")

    def test_redact_truncates_long_message(self) -> None:
        with mock.patch.dict(os.environ, {"CEREBELLUM_TOKEN": ""}, clear=False):
            self.assertEqual(len(redact("x" * 5000)), 2000)


class SanitizeTests(unittest.TestCase):
    def test_email_and_phone_redacted(self) -> None:
        cleaned, injection, pii, secret = sanitize_text("联系我 user@example.com 或 13800138000")
        self.assertFalse(injection)
        self.assertTrue(pii)
        self.assertFalse(secret)
        self.assertNotIn("user@example.com", cleaned)
        self.assertNotIn("13800138000", cleaned)
        self.assertIn("[REDACTED_EMAIL]", cleaned)
        self.assertIn("[REDACTED_PHONE]", cleaned)

    def test_secret_patterns_redacted(self) -> None:
        cleaned, _, _, secret = sanitize_text("key is sk-abcdefghijklmnop1234 ok")
        self.assertTrue(secret)
        self.assertNotIn("sk-abcdefghijklmnop1234", cleaned)
        self.assertIn("[REDACTED_SECRET]", cleaned)

    def test_github_token_redacted(self) -> None:
        cleaned, _, _, secret = sanitize_text("ghp_" + "A" * 30)
        self.assertTrue(secret)
        self.assertNotIn("ghp_", cleaned)

    def test_clean_text_untouched(self) -> None:
        cleaned, injection, pii, secret = sanitize_text("普通的科技新闻标题")
        self.assertEqual(cleaned, "普通的科技新闻标题")
        self.assertFalse(injection or pii or secret)


class LanguageTests(unittest.TestCase):
    def test_english_when_few_cjk(self) -> None:
        self.assertEqual(language_for("This is an English board title"), "en")

    def test_chinese_when_enough_cjk(self) -> None:
        self.assertEqual(language_for("这是一条中文热榜标题内容"), "zh")


class ProviderDispatchTests(unittest.TestCase):
    def test_mediacrawler_search_dispatch(self) -> None:
        from cerebellum_social_acquisition.mediacrawler import MediaCrawlerSearchProvider

        payload = job(provider="xhs", crawler_type="search", query="滑雪")["payload"]
        kind, provider = _provider_for(payload)
        self.assertEqual(kind, "xhs")
        self.assertIsInstance(provider, MediaCrawlerSearchProvider)

    def test_authenticated_dispatch(self) -> None:
        payload = job(provider="douyin", access_mode="authenticated_local")["payload"]
        kind, provider = _provider_for(payload)
        self.assertEqual(kind, "douyin")
        self.assertEqual(provider.kind, "douyin")

    def test_collector_dispatch(self) -> None:
        payload = job(provider="arxiv")["payload"]
        kind, provider = _provider_for(payload)
        self.assertEqual(kind, "arxiv")
        self.assertIsNotNone(provider)

    def test_unknown_returns_none(self) -> None:
        kind, provider = _provider_for(job(provider="nonexistent")["payload"])
        self.assertEqual(kind, "nonexistent")
        self.assertIsNone(provider)


class FixtureDiscoveryTests(unittest.TestCase):
    def test_missing_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_SOCIAL_FIXTURE_DIR": directory}, clear=False
            ):
                self.assertIsNone(_fixture_discovery("weibo", job()["payload"]))

    def test_unknown_kind_json_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "tavily.json").write_text("{}", encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_SOCIAL_FIXTURE_DIR": directory}, clear=False
            ):
                self.assertIsNone(_fixture_discovery("tavily", job(provider="tavily")["payload"]))

    def test_xhs_html_fixture_success_and_empty(self) -> None:
        html = (
            "<script>window.__INITIAL_STATE__={\"feed\":{\"feeds\":["
            "{\"modelType\":\"note\",\"id\":\"fx1\",\"noteCard\":{\"displayTitle\":\"回放笔记\"}}"
            "]}}</script>"
        )
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "xhs.html").write_text(html, encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_SOCIAL_FIXTURE_DIR": directory}, clear=False
            ):
                result = _fixture_discovery("xhs", job(provider="xhs")["payload"])
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.outcome, "success")
            self.assertEqual(result.items[0].title, "回放笔记")

            (Path(directory) / "xhs.html").write_text("<html>empty</html>", encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_SOCIAL_FIXTURE_DIR": directory}, clear=False
            ):
                result = _fixture_discovery("xhs", job(provider="xhs")["payload"])
            assert result is not None
            self.assertEqual(result.outcome, "parse_failed")
            self.assertEqual(result.error_code, "initial_state_missing")

    def test_openalex_fixture_uses_parse_works(self) -> None:
        fixture = {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "某论文",
                    "doi": "https://doi.org/10.1/x",
                    "publication_date": "2026-01-01",
                    "authorships": [],
                    "cited_by_count": 5,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "openalex.json").write_text(
                json.dumps(fixture, ensure_ascii=False), encoding="utf-8"
            )
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_SOCIAL_FIXTURE_DIR": directory}, clear=False
            ):
                result = _fixture_discovery("openalex", job(provider="openalex")["payload"])
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.items[0].title, "某论文")

    def test_arxiv_xml_fixture(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2601.00001v1</id>
    <title>离线论文标题</title>
    <summary>摘要</summary>
    <published>2026-01-01T00:00:00Z</published>
    <author><name>作者</name></author>
  </entry>
</feed>"""
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "arxiv.xml").write_text(xml, encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_SOCIAL_FIXTURE_DIR": directory}, clear=False
            ):
                result = _fixture_discovery("arxiv", job(provider="arxiv")["payload"])
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.items[0].title, "离线论文标题")


class RateBudgetTests(unittest.TestCase):
    def test_reserve_failure_is_retryable_rate_limited(self) -> None:
        value = job()
        client = FakeClient(value)
        client.reserve_error = RuntimeError("budget exhausted")
        fake_provider = mock.Mock()
        with mock.patch.dict(
            "cerebellum_social_acquisition.worker.BOARD_PROVIDERS",
            {"weibo": fake_provider},
            clear=False,
        ):
            self.assertTrue(process_one(client, "worker-a"))
        fake_provider.discover.assert_not_called()
        self.assertFalse(client.submitted)
        self.assertFalse(client.completed)
        self.assertEqual(client.failed[0][2], "source_rate_budget_exhausted")
        self.assertEqual(client.failed[0][3], 60)
        self.assertEqual(client.failed[0][4]["outcome"], "rate_limited")


class RetryBackoffTests(unittest.TestCase):
    def test_retry_without_hint_uses_exponential_backoff(self) -> None:
        value = job()
        value["attempts"] = 3
        failure = BoardResult(
            "api",
            "timeout",
            "https://weibo.com/ajax/side/hotSearch",
            retry_after_seconds=None,
            error_code="http_504",
        )
        client = run_job(value, failure)
        # attempts=3 -> 30 * 2^2 = 120
        self.assertEqual(client.failed[0][3], 120)
        self.assertEqual(client.failed[0][4]["outcome"], "timeout")

    def test_first_attempt_backoff_is_30(self) -> None:
        value = job()
        failure = BoardResult(
            "api", "server_error", "https://weibo.com/ajax/side/hotSearch", error_code="http_500"
        )
        client = run_job(value, failure)
        self.assertEqual(client.failed[0][3], 30)


class RunDiscoveryEdgeTests(unittest.TestCase):
    def test_missing_policy_raises(self) -> None:
        value = job()
        del value["payload"]["source_policy"]
        client = FakeClient(value)
        fake_provider = mock.Mock()
        with mock.patch.dict(
            "cerebellum_social_acquisition.worker.BOARD_PROVIDERS",
            {"weibo": fake_provider},
            clear=False,
        ):
            self.assertTrue(process_one(client, "worker-a"))
        # run_discovery raised PolicyError -> process_one fail path
        self.assertEqual(len(client.failed), 1)
        self.assertIn("source policy", client.failed[0][2])

    def test_discovered_urls_skip_invalid_dedup_and_cap(self) -> None:
        items = [
            BoardItem(
                external_id=f"i{n}",
                title=f"条目{n}",
                url=url,
                rank=n,
                platform="weibo",
            )
            for n, url in enumerate(
                [
                    "https://s.weibo.com/a",  # valid
                    "https://s.weibo.com/a",  # duplicate -> skipped
                    "https://evil.com/x",  # off-domain -> skipped
                    "https://s.weibo.com/b",
                    "https://s.weibo.com/c",  # beyond cap -> truncated
                ],
                1,
            )
        ]
        value = job()
        value["payload"]["source_policy"]["max_pages_per_run"] = 2
        client = run_job(value, board(items))
        discovered = client.submitted[0]["result"]["discovered_urls"]
        self.assertEqual(discovered, ["https://s.weibo.com/a", "https://s.weibo.com/b"])

    def test_board_url_excluded_from_discovered(self) -> None:
        items = [
            BoardItem(
                external_id="i1",
                title="条目1",
                url="https://weibo.com/ajax/side/hotSearch",  # same as board url
                rank=1,
                platform="weibo",
            )
        ]
        client = run_job(job(), board(items))
        self.assertEqual(client.submitted[0]["result"]["discovered_urls"], [])
    def test_uncanonicalizable_board_url_falls_back_to_raw(self) -> None:
        result = board(sample_items())
        result.url = "\\\\not a url\\\\"  # canonicalize_url raises -> keep raw
        client = run_job(job(), result)
        attempt = client.submitted[0]["result"]["attempt"]
        self.assertEqual(attempt["canonical_url"], "\\\\not a url\\\\")
        self.assertEqual(attempt["outcome"], "success")


class EmptyDocumentTests(unittest.TestCase):
    def test_empty_cleaned_content_downgrades_success_to_partial(self) -> None:
        # 防御分支：渲染结果经 sanitize 后为空（渲染通常总有头部，这里
        # 直接钉住 sanitize 验证 success-without-document 不会死信 400）。
        client = FakeClient(job())
        fake_provider = mock.Mock()
        fake_provider.discover.return_value = board(sample_items())
        with mock.patch.dict(
            "cerebellum_social_acquisition.worker.BOARD_PROVIDERS",
            {"weibo": fake_provider},
            clear=False,
        ), mock.patch(
            "cerebellum_social_acquisition.worker.sanitize_text",
            return_value=("", False, False, False),
        ):
            self.assertTrue(process_one(client, "worker-a"))
        result = client.submitted[0]["result"]
        self.assertIsNone(result["document"])
        self.assertIsNone(client.submitted[0]["cleaned"])
        self.assertEqual(result["attempt"]["outcome"], "partial_content")
        self.assertEqual(result["attempt"]["error_code"], "empty_document")
        self.assertEqual(len(client.completed), 1)
        self.assertFalse(client.failed)


class RenderAndDocumentTests(unittest.TestCase):
    def test_summary_rendered_when_different_from_title(self) -> None:
        client = run_job(job(), board(sample_items()))
        cleaned = base64.b64decode(client.submitted[0]["cleaned"]).decode("utf-8")
        self.assertIn("一项不同于标题的详细摘要内容", cleaned)

    def test_cluster_id_rendered_and_in_metadata(self) -> None:
        items = sample_items()
        items[0].extra["cluster_id"] = "cluster-1-x"
        client = run_job(job(), board(items))
        document = client.submitted[0]["result"]["document"]
        cleaned = base64.b64decode(client.submitted[0]["cleaned"]).decode("utf-8")
        self.assertIn("[跨平台事件 cluster-1-x]", cleaned)
        self.assertEqual(document["metadata"]["items"][0]["cluster_id"], "cluster-1-x")
        # cluster_id must not leak into the pass-through extra blob
        self.assertNotIn("cluster_id", document["metadata"]["items"][0]["extra"])

    def test_cross_platform_batch_gets_cluster_ids(self) -> None:
        items = [
            BoardItem(
                external_id="w1",
                title="某品牌新机型正式发布",
                url="https://s.weibo.com/weibo?q=x",
                heat=9000,
                rank=1,
                platform="weibo",
            ),
            BoardItem(
                external_id="z1",
                title="某品牌新机型正式发布",
                url="https://s.weibo.com/weibo?q=y",
                heat=8000,
                rank=2,
                platform="zhihu",
            ),
        ]
        client = run_job(job(), board(items))
        document = client.submitted[0]["result"]["document"]
        clusters = [item.get("cluster_id") for item in document["metadata"]["items"]]
        self.assertTrue(all(clusters), f"expected cluster ids, got {clusters}")
        self.assertEqual(clusters[0], clusters[1])

    def test_search_payload_title_includes_query(self) -> None:
        # crawler_type=search + non-MC provider keeps board dispatch but still
        # exercises the search-title branch in _document
        value = job(provider="tavily", crawler_type="search", query="滑雪装备")
        client = FakeClient(value)
        fake_provider = mock.Mock()
        fake_provider.discover.return_value = board(sample_items())
        with mock.patch.dict(
            "cerebellum_social_acquisition.worker.BOARD_PROVIDERS",
            {"tavily": fake_provider},
            clear=False,
        ):
            self.assertTrue(process_one(client, "worker-a"))
        document = client.submitted[0]["result"]["document"]
        self.assertIn("搜索「滑雪装备」", document["title"])

    def test_secret_in_board_marks_document(self) -> None:
        items = [
            BoardItem(
                external_id="i1",
                title=" leaked sk-abcdefghijklmnop1234 here",
                url="https://s.weibo.com/weibo?q=%23x%23",
                heat=5,
                rank=1,
                platform="weibo",
            )
        ]
        client = run_job(job(), board(items))
        document = client.submitted[0]["result"]["document"]
        self.assertTrue(document["secret_detected"])
        self.assertFalse(document["rights"]["training_eligible"])
        cleaned = base64.b64decode(client.submitted[0]["cleaned"]).decode("utf-8")
        self.assertNotIn("sk-abcdefghijklmnop1234", cleaned)

    def test_partial_content_board_still_produces_document(self) -> None:
        result = board(sample_items(), outcome="partial_content")
        result.error_code = "stale_board"
        client = run_job(job(), result)
        document = client.submitted[0]["result"]["document"]
        self.assertIsNotNone(document)
        self.assertEqual(client.submitted[0]["result"]["attempt"]["outcome"], "partial_content")
        # partial content never earns explicit training permission
        self.assertFalse(document["rights"]["explicit_training_permission"])

    def test_retention_days_clamped_to_90(self) -> None:
        value = job()
        value["payload"]["source_policy"]["raw_retention_days"] = 365
        client = run_job(value, board(sample_items()))
        document = client.submitted[0]["result"]["document"]
        from datetime import datetime

        observed = datetime.fromisoformat(document["observed_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(document["raw_expires_at"].replace("Z", "+00:00"))
        self.assertEqual((expires - observed).days, 90)


class ProcessOneFailureTests(unittest.TestCase):
    def test_provider_exception_fails_job_with_redaction(self) -> None:
        value = job()
        client = FakeClient(value)
        fake_provider = mock.Mock()
        fake_provider.discover.side_effect = RuntimeError("boom with tok-abc")
        with mock.patch.dict(
            "cerebellum_social_acquisition.worker.BOARD_PROVIDERS",
            {"weibo": fake_provider},
            clear=False,
        ), mock.patch.dict(os.environ, {"CEREBELLUM_TOKEN": "tok-abc"}, clear=False):
            self.assertTrue(process_one(client, "worker-a"))
        self.assertFalse(client.submitted)
        self.assertFalse(client.completed)
        self.assertEqual(len(client.failed), 1)
        self.assertIn("[REDACTED]", client.failed[0][2])
        self.assertNotIn("tok-abc", client.failed[0][2])
        self.assertEqual(client.failed[0][3], 60)

    def test_no_job_returns_false(self) -> None:
        client = FakeClient(None)
        self.assertFalse(process_one(client, "worker-a"))


class MainLoopTests(unittest.TestCase):
    def test_main_once_processes_single_job(self) -> None:
        env = {
            "WORKER_ID": "worker-x",
            "CEREBELLUM_URL": "https://cp.example",
            "CEREBELLUM_TOKEN": "tok",
        }
        with mock.patch.dict(os.environ, env, clear=False), mock.patch(
            "cerebellum_social_acquisition.worker.ControlPlaneClient"
        ) as client_cls, mock.patch(
            "cerebellum_social_acquisition.worker.process_one", return_value=True
        ) as process_mock, mock.patch(
            "sys.argv", ["worker", "--once"]
        ):
            main()
        client_cls.assert_called_once_with("https://cp.example", "tok")
        process_mock.assert_called_once_with(client_cls.return_value, "worker-x")

    def test_main_polls_and_sleeps_when_idle(self) -> None:
        env = {
            "WORKER_ID": "worker-x",
            "CEREBELLUM_URL": "https://cp.example",
            "CEREBELLUM_TOKEN": "tok",
        }
        calls = {"count": 0}

        def fake_process(client, worker_id):
            calls["count"] += 1
            if calls["count"] >= 2:
                raise KeyboardInterrupt  # stop the loop deterministically
            return False

        slept: list[float] = []
        with mock.patch.dict(os.environ, env, clear=False), mock.patch(
            "cerebellum_social_acquisition.worker.ControlPlaneClient"
        ), mock.patch(
            "cerebellum_social_acquisition.worker.process_one", side_effect=fake_process
        ), mock.patch(
            "cerebellum_social_acquisition.worker.time.sleep",
            side_effect=lambda seconds: slept.append(seconds),
        ), mock.patch(
            "sys.argv", ["worker", "--poll-seconds", "7"]
        ):
            with self.assertRaises(KeyboardInterrupt):
                main()
        self.assertEqual(slept, [7.0])

    def test_main_missing_env_raises(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
            "sys.argv", ["worker", "--once"]
        ):
            with self.assertRaisesRegex(RuntimeError, "WORKER_ID"):
                main()


if __name__ == "__main__":
    unittest.main()
