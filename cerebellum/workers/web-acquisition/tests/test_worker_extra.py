from __future__ import annotations

import base64
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

from cerebellum_web_acquisition.policy import PolicyError
from cerebellum_web_acquisition.providers import (
    Crawl4AIProvider,
    DirectProvider,
    FirecrawlProvider,
    LinkMapperProvider,
    MediaCrawlerDetailProvider,
    OpenCLIProvider,
    ProviderResult,
    ScraplingProvider,
    TavilyProvider,
)
from cerebellum_web_acquisition.worker import (
    RunOutcome,
    _attempt,
    _document,
    _provider,
    _reserve_source_stage,
    language_for,
    main,
    process_one,
    provider_version,
    redact,
    required_env,
    run_acquisition,
    sanitize_text,
    urlsplit_host,
)

ARTICLE = "https://example.com/article"


def job(**overrides) -> dict:
    job_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    policy_id = str(uuid.uuid4())
    value = {
        "job_id": job_id,
        "kind": "document_acquire_v1",
        "attempts": 1,
        "payload": {
            "plan_id": plan_id,
            "topic_ids": [str(uuid.uuid4())],
            "source_policy_id": policy_id,
            "canonical_url": ARTICLE,
            "item": {
                "external_id": "item-1",
                "title": "Article",
                "url": ARTICLE,
                "author": "author",
                "published_at": None,
                "language": "en",
            },
            "source_policy": {
                "policy_id": policy_id,
                "kind": "http",
                "base_url": "https://example.com/",
                "access_mode": "public",
                "allowed_domains": ["example.com"],
                "obey_robots": False,
                "max_pages_per_run": 10,
                "raw_retention_days": 30,
                "training_license": "MIT",
                "model_terms_allow_training": True,
            },
        },
    }
    for key, item in overrides.items():
        value[key] = item
    return value


class FakeClient:
    def __init__(self, value: dict | None, existing_result: dict | None = None) -> None:
        self.value = value
        self.existing_result = existing_result
        self.submitted: list[dict] = []
        self.failed: list[tuple] = []
        self.completed: list[str] = []
        self.browser_reservations = 0
        self.rate_reservations: list[int] = []
        self.fail_on_browser = False
        self.fail_rate_ordinals: set[int] = set()

    def claim(self, worker: str, lease_seconds: int = 0) -> dict | None:
        value, self.value = self.value, None
        return value

    def get_result(self, job_id: str) -> dict | None:
        return self.existing_result

    def submit_result(self, result: dict, cleaned: str | None, raw: str | None) -> dict:
        self.submitted.append({"result": result, "cleaned": cleaned, "raw": raw})
        return {"result_hash": "0" * 64}

    def complete(self, job_id: str, worker: str) -> None:
        self.completed.append(job_id)

    def fail(self, *args) -> None:
        self.failed.append(args)

    def reserve_browser_budget(self, job_id: str, worker: str) -> bool:
        self.browser_reservations += 1
        if self.fail_on_browser:
            raise RuntimeError("budget service down")
        return True

    def reserve_source_rate(self, job_id: str, worker: str, ordinal: int) -> bool:
        self.rate_reservations.append(ordinal)
        if ordinal in self.fail_rate_ordinals:
            raise RuntimeError("rate budget exhausted")
        return True


def success_result(method: str = "direct_http", text: str | None = None, **kwargs) -> ProviderResult:
    return ProviderResult(
        method,
        "success",
        ARTICLE,
        title="Article",
        cleaned_content=text or ("Useful technical evidence " * 10),
        content_type="text/html",
        **kwargs,
    )


def run_job(value: dict | None = None) -> RunOutcome:
    return run_acquisition(FakeClient(None), value or job(), "worker-a")


class RedactAndSanitizeTests(unittest.TestCase):
    def test_redact_replaces_known_secrets_and_truncates(self) -> None:
        env = {"CEREBELLUM_TOKEN": "tok-abc", "TAVILY_API_KEY": "tv-xyz", "FIRECRAWL_API_KEY": "fc-123"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                redact("failed with tok-abc and tv-xyz plus fc-123"),
                "failed with [REDACTED] and [REDACTED] plus [REDACTED]",
            )
            self.assertEqual(len(redact("y" * 5_000)), 2_000)

    def test_sanitize_phone_and_clean_text(self) -> None:
        cleaned, injection, pii, secret = sanitize_text("Call +1 415 555 0132 for details.")
        self.assertIn("[REDACTED_PHONE]", cleaned)
        self.assertFalse(injection)
        self.assertTrue(pii)
        self.assertFalse(secret)
        cleaned, injection, pii, secret = sanitize_text("ordinary prose about gardens")
        self.assertEqual(cleaned, "ordinary prose about gardens")
        self.assertFalse(any((injection, pii, secret)))

    def test_sanitize_github_token(self) -> None:
        token = "ghp_" + "a" * 24
        cleaned, _, _, secret = sanitize_text(f"token {token} leaked")
        self.assertTrue(secret)
        self.assertNotIn(token, cleaned)


class LanguageForTests(unittest.TestCase):
    def test_declared_language_wins(self) -> None:
        self.assertEqual(language_for("text", {"language": " FR "}), "fr")

    def test_cjk_detection(self) -> None:
        self.assertEqual(language_for("这是一段中文内容用于测试", {}), "zh")
        self.assertEqual(language_for("plain english text", {}), "en")


class ProviderRegistryTests(unittest.TestCase):
    def test_all_ladder_providers_resolve(self) -> None:
        expected = {
            "crawl4ai": Crawl4AIProvider,
            "firecrawl": FirecrawlProvider,
            "link_mapper": LinkMapperProvider,
            "scrapling": ScraplingProvider,
            "mediacrawler": MediaCrawlerDetailProvider,
            "open_cli": OpenCLIProvider,
        }
        for name, cls in expected.items():
            with self.subTest(name=name):
                self.assertIsInstance(_provider(name), cls)
        with self.assertRaises(KeyError):
            _provider("unknown")


class ReserveSourceStageTests(unittest.TestCase):
    def test_exception_maps_to_rate_limited(self) -> None:
        client = FakeClient(None)
        client.fail_rate_ordinals = {0}
        result = _reserve_source_stage(client, job(), "worker-a", 0, "api", ARTICLE)
        self.assertIsNotNone(result)
        self.assertEqual(result.outcome, "rate_limited")
        self.assertEqual(result.error_code, "source_rate_budget_exhausted")
        self.assertEqual(result.retry_after_seconds, 60)

    def test_success_returns_none(self) -> None:
        self.assertIsNone(_reserve_source_stage(FakeClient(None), job(), "worker-a", 0, "api", ARTICLE))


class RunAcquisitionValidationTests(unittest.TestCase):
    def test_missing_source_policy_raises(self) -> None:
        value = job()
        del value["payload"]["source_policy"]
        with self.assertRaises(PolicyError):
            run_job(value)

    def test_missing_url_and_query_raises(self) -> None:
        value = job()
        del value["payload"]["canonical_url"]
        value["payload"]["item"] = {}
        with self.assertRaises(PolicyError):
            run_job(value)

    def test_non_string_candidate_url_raises(self) -> None:
        value = job()
        value["payload"]["canonical_url"] = 42
        with self.assertRaises(PolicyError):
            run_job(value)


class RunAcquisitionSearchTests(unittest.TestCase):
    def query_job(self, provider_kind: str) -> dict:
        value = job()
        del value["payload"]["canonical_url"]
        value["payload"]["item"] = {"url": None}
        value["payload"]["query"] = "  snow gear  "
        value["payload"]["provider"] = provider_kind
        return value

    def test_tavily_search_path(self) -> None:
        found = ProviderResult(
            "api", "partial_content", "https://api-tavily.internal/",
            discovered_urls=["https://example.com/a"],
        )
        with mock.patch.object(TavilyProvider, "search", return_value=found) as search:
            run = run_acquisition(FakeClient(None), self.query_job("tavily"), "worker-a")
        search.assert_called_once()
        self.assertEqual(search.call_args.args[0], "snow gear")
        self.assertEqual(run.original_url, "https://example.com/")
        self.assertEqual(run.result.url, "https://example.com/")
        self.assertEqual(run.discovered_urls, ["https://example.com/a"])
        self.assertFalse(run.retry)

    def test_firecrawl_search_path(self) -> None:
        found = ProviderResult("api", "server_error", "x", retry_after_seconds=30)
        with mock.patch.object(FirecrawlProvider, "search", return_value=found):
            run = run_acquisition(FakeClient(None), self.query_job("firecrawl"), "worker-a")
        self.assertTrue(run.retry)

    def test_unknown_search_provider_is_denied(self) -> None:
        run = run_acquisition(FakeClient(None), self.query_job("bing"), "worker-a")
        self.assertEqual(run.result.outcome, "policy_denied")
        self.assertEqual(run.result.error_code, "provider_does_not_support_search")
        self.assertFalse(run.retry)

    def test_search_rate_budget_denied_retries(self) -> None:
        client = FakeClient(None)
        client.fail_rate_ordinals = {0}
        run = run_acquisition(client, self.query_job("tavily"), "worker-a")
        self.assertEqual(run.result.outcome, "rate_limited")
        self.assertEqual(run.result.error_code, "source_rate_budget_exhausted")
        self.assertTrue(run.retry)


class RunAcquisitionLadderTests(unittest.TestCase):
    def test_retryable_direct_outcome_short_circuits(self) -> None:
        failure = ProviderResult("direct_http", "timeout", ARTICLE, error_code="timeout")
        with mock.patch.object(DirectProvider, "run", return_value=failure):
            run = run_job()
        self.assertTrue(run.retry)
        self.assertEqual(run.result.method, "direct_http")

    def test_full_ladder_to_mediacrawler_with_best_content_fallback(self) -> None:
        direct = ProviderResult(
            "direct_http", "partial_content", ARTICLE,
            cleaned_content="partial but useful body text",
        )
        dead = ProviderResult("x", "parse_failed", ARTICLE, error_code="")
        last = ProviderResult("mediacrawler", "parse_failed", ARTICLE, error_code="empty_detail")
        client = FakeClient(None)
        with mock.patch.object(DirectProvider, "run", return_value=direct), mock.patch.object(
            Crawl4AIProvider, "run", return_value=ProviderResult("crawl4ai", "parse_failed", ARTICLE)
        ), mock.patch.object(
            FirecrawlProvider, "run", return_value=ProviderResult("firecrawl", "parse_failed", ARTICLE)
        ), mock.patch.object(
            LinkMapperProvider, "run", return_value=ProviderResult("link_mapper", "parse_failed", ARTICLE)
        ), mock.patch.object(
            ScraplingProvider, "run", return_value=ProviderResult("scrapling", "parse_failed", ARTICLE)
        ), mock.patch.object(
            MediaCrawlerDetailProvider, "run", return_value=last
        ):
            run = run_acquisition(client, job(), "worker-a")
        # best partial content is retained and reclassified
        self.assertEqual(run.result.method, "direct_http")
        self.assertEqual(run.result.outcome, "partial_content")
        self.assertEqual(run.result.cleaned_content, "partial but useful body text")
        self.assertEqual(run.result.error_code, "empty_detail")
        # browser budget reserved exactly once across crawl4ai/scrapling/mediacrawler
        self.assertEqual(client.browser_reservations, 1)
        self.assertEqual(client.rate_reservations, [0, 1, 2, 3, 4, 5])

    def test_fallback_error_code_default_when_missing(self) -> None:
        direct = ProviderResult(
            "direct_http", "partial_content", ARTICLE, cleaned_content="some content"
        )
        silent = ProviderResult("crawl4ai", "parse_failed", ARTICLE, error_code=None)
        with mock.patch.object(DirectProvider, "run", return_value=direct), mock.patch.object(
            Crawl4AIProvider, "run", return_value=silent
        ), mock.patch.object(
            FirecrawlProvider, "run", return_value=silent
        ), mock.patch.object(
            LinkMapperProvider, "run", return_value=silent
        ), mock.patch.object(
            ScraplingProvider, "run", return_value=silent
        ), mock.patch.object(
            MediaCrawlerDetailProvider, "run", return_value=silent
        ):
            run = run_job()
        self.assertEqual(run.result.error_code, "extraction_incomplete")

    def test_escalation_stops_at_first_success(self) -> None:
        direct = ProviderResult("direct_http", "js_shell", ARTICLE)
        crawled = success_result(method="crawl4ai")
        client = FakeClient(None)
        with mock.patch.object(DirectProvider, "run", return_value=direct), mock.patch.object(
            Crawl4AIProvider, "run", return_value=crawled
        ) as crawl, mock.patch.object(FirecrawlProvider, "run") as firecrawl:
            run = run_acquisition(client, job(), "worker-a")
        self.assertEqual(run.result.method, "crawl4ai")
        self.assertEqual(run.result.outcome, "success")
        firecrawl.assert_not_called()
        self.assertEqual(client.browser_reservations, 1)

    def test_retryable_outcome_in_later_stage_retries_with_method(self) -> None:
        direct = ProviderResult("direct_http", "js_shell", ARTICLE)
        timed_out = ProviderResult("crawl4ai", "timeout", ARTICLE, error_code="provider_error")
        with mock.patch.object(DirectProvider, "run", return_value=direct), mock.patch.object(
            Crawl4AIProvider, "run", return_value=timed_out
        ):
            run = run_job()
        self.assertTrue(run.retry)
        self.assertEqual(run.result.method, "crawl4ai")

    def test_browser_budget_failure_denies_escalation(self) -> None:
        direct = ProviderResult("direct_http", "js_shell", ARTICLE)
        client = FakeClient(None)
        client.fail_on_browser = True
        with mock.patch.object(DirectProvider, "run", return_value=direct), mock.patch.object(
            Crawl4AIProvider, "run"
        ) as crawl:
            run = run_acquisition(client, job(), "worker-a")
        crawl.assert_not_called()
        self.assertFalse(run.retry)
        self.assertEqual(run.result.outcome, "policy_denied")
        self.assertEqual(run.result.error_code, "browser_budget_denied")

    def test_rate_budget_denial_at_later_stage_retries(self) -> None:
        direct = ProviderResult("direct_http", "js_shell", ARTICLE)
        client = FakeClient(None)
        client.fail_rate_ordinals = {1}
        with mock.patch.object(DirectProvider, "run", return_value=direct), mock.patch.object(
            Crawl4AIProvider, "run"
        ) as crawl:
            run = run_acquisition(client, job(), "worker-a")
        crawl.assert_not_called()
        self.assertTrue(run.retry)
        self.assertEqual(run.result.error_code, "source_rate_budget_exhausted")

    def test_discovered_urls_accumulate_across_stages(self) -> None:
        direct = ProviderResult(
            "direct_http", "js_shell", ARTICLE,
            discovered_urls=["https://example.com/one"],
        )
        crawled = success_result(
            method="crawl4ai",
            discovered_urls=["https://example.com/one", "https://example.com/two"],
        )
        with mock.patch.object(DirectProvider, "run", return_value=direct), mock.patch.object(
            Crawl4AIProvider, "run", return_value=crawled
        ):
            run = run_job()
        self.assertEqual(
            run.discovered_urls, ["https://example.com/one", "https://example.com/two"]
        )


class AttemptTests(unittest.TestCase):
    def test_attempt_is_deterministic_and_carries_fields(self) -> None:
        value = job()
        run = RunOutcome(
            success_result(), ARTICLE, datetime(2026, 8, 30, tzinfo=timezone.utc), []
        )
        first = _attempt(value, run, "hash-1")
        second = _attempt(value, run, "hash-1")
        self.assertEqual(first["attempt_id"], second["attempt_id"])
        self.assertEqual(first["plan_id"], value["payload"]["plan_id"])
        self.assertEqual(first["source_policy_id"], value["payload"]["source_policy_id"])
        self.assertEqual(first["content_hash"], "hash-1")
        self.assertEqual(first["schema_version"], "cerebellum/v1")
        self.assertEqual(first["cost"], 0.0)
        self.assertTrue(first["started_at"].endswith("Z"))


class DocumentExtraTests(unittest.TestCase):
    def build(self, result: ProviderResult, value: dict | None = None):
        run = RunOutcome(result, ARTICLE, datetime.now(timezone.utc), [])
        return _document(value or job(), run)

    def test_no_cleaned_content_yields_no_document(self) -> None:
        document, cleaned, raw = self.build(ProviderResult("direct_http", "gone", ARTICLE))
        self.assertEqual((document, cleaned, raw), (None, None, None))

    def test_content_that_sanitizes_to_empty_yields_no_document(self) -> None:
        result = success_result(text="   ")
        document, cleaned, raw = self.build(result)
        self.assertEqual((document, cleaned, raw), (None, None, None))

    def test_authenticated_local_never_retains_raw(self) -> None:
        value = job()
        value["payload"]["source_policy"]["access_mode"] = "authenticated_local"
        result = success_result(raw_content=b"raw bytes")
        document, cleaned, raw = self.build(result, value)
        self.assertIsNotNone(document)
        self.assertIsNone(raw)
        self.assertIsNone(document["raw_content_hash"])

    def test_clean_public_content_retains_raw_and_is_training_eligible(self) -> None:
        result = success_result(raw_content=b"<html>raw</html>")
        document, cleaned, raw = self.build(result)
        self.assertEqual(raw, b"<html>raw</html>")
        rights = document["rights"]
        self.assertTrue(rights["redistribution_allowed"])
        self.assertTrue(rights["explicit_training_permission"])
        self.assertTrue(rights["training_eligible"])
        self.assertEqual(rights["rights_source"], f"source_policy:{job.__name__ and document['source_policy_id']}")
        self.assertEqual(document["extractor_version"], "stdlib-pinned-http/0.1")

    def test_unlicensed_content_is_not_redistributable(self) -> None:
        value = job()
        value["payload"]["source_policy"]["training_license"] = "CC-BY-NC-4.0"
        document, _, _ = self.build(success_result(), value)
        rights = document["rights"]
        self.assertFalse(rights["redistribution_allowed"])
        self.assertFalse(rights["training_eligible"])

    def test_non_success_outcome_blocks_explicit_permission(self) -> None:
        result = success_result()
        result.outcome = "partial_content"
        document, _, _ = self.build(result)
        self.assertFalse(document["rights"]["explicit_training_permission"])
        self.assertFalse(document["rights"]["training_eligible"])

    def test_terms_not_allowing_training_blocks_permission(self) -> None:
        value = job()
        value["payload"]["source_policy"]["model_terms_allow_training"] = False
        document, _, _ = self.build(success_result(), value)
        self.assertFalse(document["rights"]["explicit_training_permission"])

    def test_retention_days_are_clamped(self) -> None:
        for days, expected in ((365, 90), (-5, 0), (7, 7)):
            value = job()
            value["payload"]["source_policy"]["raw_retention_days"] = days
            document, _, _ = self.build(success_result(), value)
            expires = datetime.fromisoformat(document["raw_expires_at"].replace("Z", "+00:00"))
            delta = expires - datetime.now(timezone.utc)
            with self.subTest(days=days):
                self.assertAlmostEqual(delta.total_seconds(), expected * 86_400, delta=120)

    def test_title_falls_back_to_host(self) -> None:
        value = job()
        value["payload"]["item"] = {}
        result = success_result()
        result.title = ""
        document, _, _ = self.build(result, value)
        self.assertEqual(document["title"], "example.com")

    def test_language_detection_and_declared_override(self) -> None:
        value = job()
        value["payload"]["item"] = {"language": None}
        document, _, _ = self.build(success_result(text="这是一段足够长的中文技术内容，包含多个汉字用于语言检测"), value)
        self.assertEqual(document["language"], "zh")

    def test_metadata_records_provider_and_discovery(self) -> None:
        result = success_result(metadata={"provider_version": "0.9.2"})
        run = RunOutcome(
            result, ARTICLE, datetime.now(timezone.utc),
            ["https://example.com/a", "https://example.com/b"],
        )
        document, _, _ = _document(job(), run)
        self.assertEqual(document["metadata"]["provider"], "direct_http")
        self.assertEqual(document["metadata"]["discovered_url_count"], 2)
        self.assertEqual(document["metadata"]["source_kind"], "http")
        self.assertEqual(
            base64.b64decode(base64.b64encode(document["cleaned_content_hash"].encode())).decode(),
            document["cleaned_content_hash"],
        )


class UrlsplitHostTests(unittest.TestCase):
    def test_host_and_fallback(self) -> None:
        self.assertEqual(urlsplit_host("https://sub.example.com/a"), "sub.example.com")
        self.assertEqual(urlsplit_host("not a url"), "Untitled document")


class ProviderVersionTests(unittest.TestCase):
    def test_every_method_has_a_version(self) -> None:
        for method in (
            "direct_http", "api", "rss", "crawl4ai", "firecrawl",
            "link_mapper", "scrapling", "mediacrawler", "open_cli",
        ):
            with self.subTest(method=method):
                self.assertTrue(provider_version(method))
        with self.assertRaises(KeyError):
            provider_version("mystery")


class ProcessOneExtraTests(unittest.TestCase):
    def test_no_job_returns_false(self) -> None:
        client = FakeClient(None)
        self.assertFalse(process_one(client, "worker-a"))
        self.assertFalse(client.failed)

    def test_existing_result_completes_idempotently(self) -> None:
        value = job()
        client = FakeClient(value, existing_result={"result_hash": "abc"})
        with mock.patch.object(DirectProvider, "run") as run:
            self.assertTrue(process_one(client, "worker-a"))
        run.assert_not_called()
        self.assertEqual(client.completed, [value["job_id"]])
        self.assertFalse(client.submitted)

    def test_retry_default_delay_uses_exponential_backoff(self) -> None:
        failure = ProviderResult(
            "direct_http", "server_error", ARTICLE,
            http_status=500, retry_after_seconds=None, error_code="http_500",
        )
        for attempts, expected in ((1, 30), (4, 240), (20, 3_600)):
            value = job(attempts=attempts)
            client = FakeClient(value)
            with mock.patch.object(DirectProvider, "run", return_value=failure):
                self.assertTrue(process_one(client, "worker-a"))
            with self.subTest(attempts=attempts):
                self.assertEqual(client.failed[0][3], expected)
                self.assertEqual(client.failed[0][2], "http_500")

    def test_unexpected_exception_fails_with_redacted_message(self) -> None:
        value = job()
        client = FakeClient(value)
        with mock.patch.dict(os.environ, {"CEREBELLUM_TOKEN": "super-secret"}, clear=True), mock.patch.object(
            DirectProvider, "run", side_effect=RuntimeError("dial failed with super-secret")
        ):
            self.assertTrue(process_one(client, "worker-a"))
        self.assertEqual(len(client.failed), 1)
        _, _, message, delay = client.failed[0]
        self.assertIn("[REDACTED]", message)
        self.assertNotIn("super-secret", message)
        self.assertEqual(delay, 60)
        self.assertFalse(client.completed)

    def test_discovered_urls_truncated_to_max_pages(self) -> None:
        value = job()
        value["payload"]["source_policy"]["max_pages_per_run"] = 2
        client = FakeClient(value)
        result = success_result(
            discovered_urls=[f"https://example.com/p{i}" for i in range(5)]
        )
        with mock.patch.object(DirectProvider, "run", return_value=result):
            self.assertTrue(process_one(client, "worker-a"))
        self.assertEqual(
            client.submitted[0]["result"]["discovered_urls"],
            ["https://example.com/p0", "https://example.com/p1"],
        )

    def test_cleaned_and_raw_are_base64_encoded_on_submit(self) -> None:
        value = job()
        client = FakeClient(value)
        result = success_result(raw_content=b"raw-bytes")
        with mock.patch.object(DirectProvider, "run", return_value=result):
            self.assertTrue(process_one(client, "worker-a"))
        submitted = client.submitted[0]
        self.assertEqual(base64.b64decode(submitted["raw"]), b"raw-bytes")
        self.assertIn(b"Useful technical evidence", base64.b64decode(submitted["cleaned"]))
        self.assertEqual(client.completed, [value["job_id"]])


class MainTests(unittest.TestCase):
    def test_required_env_raises_when_missing(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                required_env("DEFINITELY_MISSING_VAR")

    def test_main_once_processes_a_single_job(self) -> None:
        env = {
            "WORKER_ID": "worker-x",
            "CEREBELLUM_URL": "http://127.0.0.1:9000",
            "CEREBELLUM_TOKEN": "tok",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch(
            "sys.argv", ["worker", "--once"]
        ), mock.patch(
            "cerebellum_web_acquisition.worker.ControlPlaneClient"
        ) as client_cls, mock.patch(
            "cerebellum_web_acquisition.worker.process_one", return_value=True
        ) as process:
            main()
        client_cls.assert_called_once_with("http://127.0.0.1:9000", "tok")
        process.assert_called_once_with(client_cls.return_value, "worker-x")

    def test_main_requires_worker_id(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
            "sys.argv", ["worker", "--once"]
        ):
            with self.assertRaises(RuntimeError):
                main()


if __name__ == "__main__":
    unittest.main()
