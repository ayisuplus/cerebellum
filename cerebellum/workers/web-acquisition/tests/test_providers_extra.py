from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

from cerebellum_web_acquisition.policy import (
    MAX_DOCUMENT_BYTES,
    FetchResponse,
    PolicyError,
)
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
    _challenge_outcome,
    _configured_service_url,
    _decode_body,
    _json_service_request,
    _robots_allowed,
    _safe_links,
)

ARTICLE = "https://example.com/article"
LONG_TEXT = "Useful technical evidence for the corpus. " * 8


def payload(access_mode: str = "public", obey_robots: bool = False, **policy) -> dict:
    base = {
        "kind": "http",
        "access_mode": access_mode,
        "base_url": "https://example.com/",
        "allowed_domains": ["example.com"],
        "obey_robots": obey_robots,
        "max_pages_per_run": 10,
    }
    base.update(policy)
    return {"source_policy": base}


def fetched(
    status: int = 200,
    body: bytes = b"",
    content_type: str = "text/html; charset=utf-8",
    final_url: str = ARTICLE,
    headers: dict | None = None,
) -> FetchResponse:
    all_headers = {"content-type": content_type}
    all_headers.update(headers or {})
    return FetchResponse(final_url, status, all_headers, body)


class DecodeBodyTests(unittest.TestCase):
    def test_charset_from_content_type_is_used(self) -> None:
        body = "中文内容".encode("gbk")
        self.assertEqual(
            _decode_body(body, "text/html; charset=GBK"), "中文内容"
        )

    def test_unknown_charset_falls_back_to_utf8(self) -> None:
        body = "héllo".encode("utf-8")
        self.assertEqual(_decode_body(body, "text/html; charset=bogus-charset"), "héllo")

    def test_default_utf8_with_replacement(self) -> None:
        self.assertEqual(_decode_body(b"a\xffb", "text/plain"), "a\ufffdb")


class ChallengeOutcomeTests(unittest.TestCase):
    def test_captcha_markers(self) -> None:
        for marker in ("g-recaptcha", "hcaptcha", "cf-turnstile", "captcha challenge", "verify you are human"):
            with self.subTest(marker=marker):
                self.assertEqual(_challenge_outcome(f"please solve {marker} now"), "captcha")

    def test_explicit_challenge_markers(self) -> None:
        for marker in ("Checking your browser", "Just a moment...", "enable javascript and cookies to continue", "Access Denied |"):
            with self.subTest(marker=marker):
                self.assertEqual(_challenge_outcome(marker), "explicit_challenge")

    def test_clean_text_returns_none(self) -> None:
        self.assertIsNone(_challenge_outcome("an ordinary article about gardening"))


class SafeLinksTests(unittest.TestCase):
    def test_dedup_filters_and_limits(self) -> None:
        values = [
            "https://example.com/a",
            "https://example.com/a#frag",
            "https://evil.test/b",
            "not a url",
            "https://example.com/c?utm_source=x",
        ]
        self.assertEqual(
            _safe_links(values, ["example.com"]),
            ["https://example.com/a", "https://example.com/c"],
        )

    def test_limit_is_enforced(self) -> None:
        values = [f"https://example.com/p{i}" for i in range(600)]
        self.assertEqual(len(_safe_links(values, ["example.com"])), 500)


class RobotsExtraTests(unittest.TestCase):
    def test_obey_robots_disabled_skips_fetch(self) -> None:
        with mock.patch("cerebellum_web_acquisition.providers.fetch_public_url") as fetch:
            self.assertIsNone(_robots_allowed(ARTICLE, {"obey_robots": False}))
        fetch.assert_not_called()

    def test_robots_fetch_policy_error_maps_to_robots_denied(self) -> None:
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            side_effect=PolicyError("denied", "policy_denied"),
        ):
            result = _robots_allowed(ARTICLE, {"obey_robots": True})
        self.assertEqual(result.outcome, "robots_denied")
        self.assertEqual(result.error_code, "robots_policy")

    def test_robots_fetch_server_error_maps_to_unavailable(self) -> None:
        for outcome in ("timeout", "server_error"):
            with self.subTest(outcome=outcome), mock.patch(
                "cerebellum_web_acquisition.providers.fetch_public_url",
                side_effect=PolicyError("down", outcome),
            ):
                result = _robots_allowed(ARTICLE, {"obey_robots": True})
            self.assertEqual(result.outcome, outcome)
            self.assertEqual(result.error_code, "robots_unavailable")

    def test_robots_403_is_forbidden(self) -> None:
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            return_value=fetched(status=403, final_url="https://example.com/robots.txt"),
        ):
            result = _robots_allowed(ARTICLE, {"obey_robots": True})
        self.assertEqual(result.outcome, "robots_denied")
        self.assertEqual(result.error_code, "robots_forbidden")
        self.assertEqual(result.http_status, 403)

    def test_robots_500_is_fetch_failed_with_retry_after(self) -> None:
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            return_value=fetched(
                status=500,
                final_url="https://example.com/robots.txt",
                headers={"retry-after": "7"},
            ),
        ):
            result = _robots_allowed(ARTICLE, {"obey_robots": True})
        self.assertEqual(result.outcome, "server_error")
        self.assertEqual(result.error_code, "robots_fetch_failed")
        self.assertEqual(result.retry_after_seconds, 7)

    def test_robots_disallow_and_allow(self) -> None:
        body = b"User-agent: *\nDisallow: /private\n"
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            return_value=fetched(
                status=200, body=body, final_url="https://example.com/robots.txt"
            ),
        ):
            denied = _robots_allowed("https://example.com/private/x", {"obey_robots": True})
            allowed = _robots_allowed(ARTICLE, {"obey_robots": True})
        self.assertEqual(denied.outcome, "robots_denied")
        self.assertEqual(denied.error_code, "robots_disallow")
        self.assertIsNone(allowed)


class DirectProviderTests(unittest.TestCase):
    def run_direct(self, fetch_side_effect=None, fetch_return=None, data=None):
        data = data or payload()
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            side_effect=fetch_side_effect,
            return_value=fetch_return,
        ):
            return DirectProvider().run(ARTICLE, data)

    def test_robots_deny_short_circuits_fetch(self) -> None:
        robots_body = b"User-agent: *\nDisallow: /\n"
        responses = [
            fetched(status=200, body=robots_body, final_url="https://example.com/robots.txt")
        ]

        def sequential(url, allowed):
            return responses.pop(0)

        data = payload(obey_robots=True)
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            side_effect=sequential,
        ) as fetch:
            result = DirectProvider().run(ARTICLE, data)
        self.assertEqual(result.outcome, "robots_denied")
        self.assertEqual(fetch.call_count, 1)

    def test_policy_error_from_fetch_maps_outcome(self) -> None:
        result = self.run_direct(fetch_side_effect=PolicyError("slow", "timeout"))
        self.assertEqual(result.method, "direct_http")
        self.assertEqual(result.outcome, "timeout")
        self.assertEqual(result.error_code, "timeout")

    def test_http_error_status_maps_outcome_and_retry(self) -> None:
        result = self.run_direct(
            fetch_return=fetched(status=429, headers={"retry-after": "33"})
        )
        self.assertEqual(result.outcome, "rate_limited")
        self.assertEqual(result.http_status, 429)
        self.assertEqual(result.retry_after_seconds, 33)
        self.assertEqual(result.error_code, "http_429")

    def test_challenge_page_keeps_raw_content(self) -> None:
        body = b"<html><body>g-recaptcha required</body></html>"
        result = self.run_direct(fetch_return=fetched(body=body))
        self.assertEqual(result.outcome, "captcha")
        self.assertEqual(result.raw_content, body)

    def test_full_html_success_extracts_title_links_canonical(self) -> None:
        html_body = (
            "<html><head><title>Great Article</title>"
            '<link rel="canonical" href="https://example.com/article"></head>'
            f"<body><h1>Heading</h1><p>{LONG_TEXT}</p>"
            '<a href="/next">next</a><a href="https://other.test/x">ext</a>'
            "<script>var x = 1;</script></body></html>"
        ).encode()
        result = self.run_direct(fetch_return=fetched(body=html_body))
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.title, "Great Article")
        self.assertEqual(result.url, "https://example.com/article")
        self.assertIn("Heading", result.cleaned_content)
        self.assertEqual(result.discovered_urls, ["https://example.com/next"])
        self.assertEqual(result.metadata["canonical_hint"], "https://example.com/article")
        self.assertEqual(result.metadata["script_count"], 1)
        self.assertEqual(result.raw_content, html_body)

    def test_canonical_outside_allowlist_is_dropped(self) -> None:
        html_body = (
            "<html><head>"
            '<link rel="canonical" href="https://evil.test/article"></head>'
            f"<body><p>{LONG_TEXT}</p></body></html>"
        ).encode()
        result = self.run_direct(fetch_return=fetched(body=html_body))
        self.assertEqual(result.url, ARTICLE)
        self.assertIsNone(result.metadata["canonical_hint"])

    def test_short_html_with_scripts_is_js_shell(self) -> None:
        html_body = (
            "<html><body><div id='app'></div>"
            "<script src='/a.js'></script><script src='/b.js'></script>"
            "</body></html>"
        ).encode()
        result = self.run_direct(fetch_return=fetched(body=html_body))
        self.assertEqual(result.outcome, "js_shell")

    def test_short_html_without_scripts_is_partial(self) -> None:
        result = self.run_direct(fetch_return=fetched(body=b"<html><body><p>tiny</p></body></html>"))
        self.assertEqual(result.outcome, "partial_content")

    def test_parser_exception_maps_to_parse_failed(self) -> None:
        class BrokenParser:
            def __init__(self, base_url: str) -> None:
                pass

            def feed(self, text: str) -> None:
                raise ValueError("boom")

        html_body = f"<html><body><p>{LONG_TEXT}</p></body></html>".encode()
        with mock.patch(
            "cerebellum_web_acquisition.providers._ContentParser", BrokenParser
        ), mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            return_value=fetched(body=html_body),
        ):
            result = DirectProvider().run(ARTICLE, payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "invalid_html")

    def test_plain_text_body_thresholds(self) -> None:
        result = self.run_direct(
            fetch_return=fetched(body=b"a plain note with enough text", content_type="text/plain")
        )
        self.assertEqual(result.outcome, "success")
        short = self.run_direct(
            fetch_return=fetched(body=b"tiny", content_type="text/plain")
        )
        self.assertEqual(short.outcome, "partial_content")


class Crawl4AITests(unittest.TestCase):
    def fake_module(self, outcome):
        module = types.ModuleType("crawl4ai")

        class CrawlerRunConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class AsyncWebCrawler:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def arun(self, url=None, config=None):
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

        module.CrawlerRunConfig = CrawlerRunConfig
        module.AsyncWebCrawler = AsyncWebCrawler
        return module

    def run_enabled(self, outcome):
        with mock.patch.dict(os.environ, {"CEREBELLUM_ENABLE_CRAWL4AI": "1"}, clear=True), mock.patch.dict(
            sys.modules, {"crawl4ai": self.fake_module(outcome)}
        ):
            return Crawl4AIProvider().run(ARTICLE, payload())

    def test_disabled_without_env(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = Crawl4AIProvider().run(ARTICLE, payload())
        self.assertEqual(result.error_code, "provider_disabled")

    def test_unavailable_without_package(self) -> None:
        with mock.patch.dict(os.environ, {"CEREBELLUM_ENABLE_CRAWL4AI": "1"}, clear=True), mock.patch.dict(
            sys.modules, {"crawl4ai": None}
        ):
            result = Crawl4AIProvider().run(ARTICLE, payload())
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "provider_unavailable")

    def test_failed_crawl_with_challenge_message(self) -> None:
        outcome = types.SimpleNamespace(success=False, error_message="Cloudflare challenge blocked")
        result = self.run_enabled(outcome)
        self.assertEqual(result.outcome, "explicit_challenge")
        self.assertEqual(result.error_code, "crawl_failed")

    def test_failed_crawl_other_message(self) -> None:
        outcome = types.SimpleNamespace(success=False, error_message="network exploded")
        result = self.run_enabled(outcome)
        self.assertEqual(result.outcome, "parse_failed")

    def test_success_extracts_markdown_and_safe_links(self) -> None:
        markdown = types.SimpleNamespace(raw_markdown=LONG_TEXT)
        outcome = types.SimpleNamespace(
            success=True,
            markdown=markdown,
            html="<html><body>ok</body></html>",
            title="Crawled",
            links={
                "internal": [
                    {"href": "https://example.com/one"},
                    {"href": "https://evil.test/two"},
                    {"href": 42},
                    "junk",
                ]
            },
        )
        result = self.run_enabled(outcome)
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.title, "Crawled")
        self.assertEqual(result.cleaned_content, LONG_TEXT.strip())
        self.assertEqual(result.discovered_urls, ["https://example.com/one"])
        self.assertEqual(result.metadata["provider_version"], "0.9.2")

    def test_short_markdown_is_partial(self) -> None:
        outcome = types.SimpleNamespace(
            success=True, markdown="tiny", html="", title="", links={}
        )
        result = self.run_enabled(outcome)
        self.assertEqual(result.outcome, "partial_content")

    def test_challenge_marker_in_html(self) -> None:
        outcome = types.SimpleNamespace(
            success=True,
            markdown=LONG_TEXT,
            html="<div class='cf-turnstile'></div>",
            title="",
            links={},
        )
        result = self.run_enabled(outcome)
        self.assertEqual(result.outcome, "captcha")

    def test_crawler_exception_maps_to_provider_error(self) -> None:
        result = self.run_enabled(RuntimeError("render exploded"))
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "provider_error")


class ServiceHelpersTests(unittest.TestCase):
    def test_configured_service_url_requires_value(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                _configured_service_url("MISSING_SERVICE_URL")

    def test_configured_service_url_requires_https_or_loopback(self) -> None:
        with mock.patch.dict(
            os.environ, {"SVC_URL": "http://169.254.1.1:9000"}, clear=True
        ):
            with self.assertRaises(RuntimeError):
                _configured_service_url("SVC_URL")
        with mock.patch.dict(
            os.environ, {"SVC_URL": "http://127.0.0.1:9000/"}, clear=True
        ):
            self.assertEqual(_configured_service_url("SVC_URL"), "http://127.0.0.1:9000")
        with mock.patch.dict(
            os.environ, {"SVC_URL": "https://api.example.com/"}, clear=True
        ):
            self.assertEqual(_configured_service_url("SVC_URL"), "https://api.example.com")

    def test_json_service_request_success(self) -> None:
        class FakeHTTPResponse:
            status = 200
            headers = {"Retry-After": "3"}

            def __init__(self):
                self._data = b'{"ok": true}'

            def read(self, size):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch(
            "cerebellum_web_acquisition.providers.urllib.request.urlopen",
            return_value=FakeHTTPResponse(),
        ):
            status, headers, value = _json_service_request(
                "http://127.0.0.1:9000", "/v1/x", {"a": 1}, {"Authorization": "Bearer k"}
            )
        self.assertEqual(status, 200)
        self.assertEqual(headers["retry-after"], "3")
        self.assertEqual(value, {"ok": True})

    def test_json_service_request_oversize_body_rejected(self) -> None:
        class BigResponse:
            status = 200
            headers = {}

            def read(self, size):
                return b"x" * (MAX_DOCUMENT_BYTES + 1)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch(
            "cerebellum_web_acquisition.providers.urllib.request.urlopen",
            return_value=BigResponse(),
        ):
            with self.assertRaises(RuntimeError):
                _json_service_request("http://127.0.0.1:9000", "/v1/x", {}, {})

    def test_json_service_request_http_error_parses_body(self) -> None:
        message = Message()
        message["Retry-After"] = "9"
        error = urllib.error.HTTPError(
            "http://127.0.0.1/v1/x", 429, "limited", message, io.BytesIO(b'{"detail": "slow"}')
        )
        with mock.patch(
            "cerebellum_web_acquisition.providers.urllib.request.urlopen",
            side_effect=error,
        ):
            status, headers, value = _json_service_request("http://127.0.0.1:9000", "/v1/x", {}, {})
        self.assertEqual(status, 429)
        self.assertEqual(headers["retry-after"], "9")
        self.assertEqual(value, {"detail": "slow"})

    def test_json_service_request_http_error_with_non_json_body(self) -> None:
        error = urllib.error.HTTPError(
            "http://127.0.0.1/v1/x", 500, "broken", Message(), io.BytesIO(b"<html>oops")
        )
        with mock.patch(
            "cerebellum_web_acquisition.providers.urllib.request.urlopen",
            side_effect=error,
        ):
            status, _, value = _json_service_request("http://127.0.0.1:9000", "/v1/x", {}, {})
        self.assertEqual(status, 500)
        self.assertEqual(value, {})


class FirecrawlTests(unittest.TestCase):
    def env(self):
        return mock.patch.dict(
            os.environ,
            {"FIRECRAWL_BASE_URL": "http://127.0.0.1:3002", "FIRECRAWL_API_KEY": "fc-key"},
            clear=True,
        )

    def test_run_disabled_without_base_url(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = FirecrawlProvider().run(ARTICLE, payload())
        self.assertEqual(result.error_code, "provider_disabled")

    def test_run_request_exception_maps_to_server_error(self) -> None:
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            side_effect=TimeoutError("slow"),
        ):
            result = FirecrawlProvider().run(ARTICLE, payload())
        self.assertEqual(result.outcome, "server_error")
        self.assertEqual(result.retry_after_seconds, 60)
        self.assertEqual(result.error_code, "provider_error")

    def test_run_non_success_status(self) -> None:
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(429, {"retry-after": "12"}, {}),
        ):
            result = FirecrawlProvider().run(ARTICLE, payload())
        self.assertEqual(result.outcome, "rate_limited")
        self.assertEqual(result.http_status, 429)
        self.assertEqual(result.retry_after_seconds, 12)
        self.assertEqual(result.error_code, "provider_http_429")

    def test_run_challenge_markdown(self) -> None:
        body = {"data": {"markdown": "checking your browser before continuing", "metadata": {}, "links": []}}
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(200, {}, body),
        ):
            result = FirecrawlProvider().run(ARTICLE, payload())
        self.assertEqual(result.outcome, "explicit_challenge")

    def test_run_success_with_filtered_links(self) -> None:
        body = {
            "data": {
                "markdown": LONG_TEXT,
                "metadata": {"title": "Scraped"},
                "links": ["https://example.com/a", "https://evil.test/b", 7],
            }
        }
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(200, {}, body),
        ):
            result = FirecrawlProvider().run(ARTICLE, payload())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.title, "Scraped")
        self.assertEqual(result.discovered_urls, ["https://example.com/a"])
        self.assertEqual(result.content_type, "text/markdown; charset=utf-8")
        self.assertEqual(result.metadata["provider_version"], "2.10")

    def test_run_partial_for_short_markdown_and_top_level_data(self) -> None:
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(200, {}, {"markdown": "tiny", "metadata": {}, "links": []}),
        ):
            result = FirecrawlProvider().run(ARTICLE, payload())
        self.assertEqual(result.outcome, "partial_content")

    def test_search_disabled(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = FirecrawlProvider().search("query", payload())
        self.assertEqual(result.error_code, "provider_disabled")
        self.assertEqual(result.url, "https://example.com/")

    def test_search_exception_maps_to_server_error(self) -> None:
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            side_effect=OSError("down"),
        ):
            result = FirecrawlProvider().search("query", payload())
        self.assertEqual(result.outcome, "server_error")

    def test_search_non_success_status(self) -> None:
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(503, {}, {}),
        ):
            result = FirecrawlProvider().search("query", payload())
        self.assertEqual(result.outcome, "server_error")
        self.assertEqual(result.error_code, "provider_http_503")

    def test_search_success_returns_result_urls(self) -> None:
        body = {"data": [{"url": "https://example.com/a"}, {"url": "https://evil.test/b"}, {"no": "url"}]}
        with self.env(), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(200, {}, body),
        ) as request:
            result = FirecrawlProvider().search("snow gear", payload())
        self.assertEqual(result.outcome, "partial_content")
        self.assertEqual(result.error_code, "search_results_only")
        self.assertEqual(result.discovered_urls, ["https://example.com/a"])
        self.assertEqual(result.http_status, 200)
        self.assertEqual(request.call_args.args[1], "/v1/search")
        self.assertEqual(request.call_args.args[2]["limit"], 10)


class LinkMapperTests(unittest.TestCase):
    def previous(self) -> ProviderResult:
        return ProviderResult(
            "direct_http",
            "js_shell",
            ARTICLE,
            cleaned_content="previous cleaned",
            raw_content=b"previous raw",
            content_type="text/html",
            discovered_urls=["https://example.com/from-previous"],
        )

    def test_sitemap_merges_with_previous_links(self) -> None:
        xml = (
            "<?xml version='1.0'?><urlset>"
            "<url><loc>https://example.com/one</loc></url>"
            "<url><loc>https://example.com/two?utm_source=x</loc></url>"
            "<url><loc>https://evil.test/three</loc></url>"
            "</urlset>"
        ).encode()
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            return_value=fetched(
                status=200, body=xml, content_type="application/xml",
                final_url="https://example.com/sitemap.xml",
            ),
        ):
            result = LinkMapperProvider().run(ARTICLE, payload(), self.previous())
        self.assertEqual(result.outcome, "partial_content")
        self.assertEqual(result.error_code, "link_map_only")
        self.assertEqual(result.cleaned_content, "previous cleaned")
        self.assertEqual(result.raw_content, b"previous raw")
        self.assertEqual(
            result.discovered_urls,
            [
                "https://example.com/from-previous",
                "https://example.com/one",
                "https://example.com/two",
            ],
        )

    def test_sitemap_unavailable_statuses(self) -> None:
        for status in (429, 503):
            with self.subTest(status=status), mock.patch(
                "cerebellum_web_acquisition.providers.fetch_public_url",
                return_value=fetched(
                    status=status,
                    final_url="https://example.com/sitemap.xml",
                    headers={"retry-after": "15"},
                ),
            ):
                result = LinkMapperProvider().run(ARTICLE, payload(), None)
            self.assertEqual(result.error_code, "sitemap_unavailable")
            self.assertEqual(result.retry_after_seconds, 15)

    def test_sitemap_timeout_maps_to_retryable_outcome(self) -> None:
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            side_effect=PolicyError("slow", "timeout"),
        ):
            result = LinkMapperProvider().run(ARTICLE, payload(), None)
        self.assertEqual(result.outcome, "timeout")
        self.assertEqual(result.retry_after_seconds, 60)
        self.assertEqual(result.error_code, "sitemap_unavailable")

    def test_sitemap_policy_denial_falls_back_to_previous_links(self) -> None:
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            side_effect=PolicyError("denied", "policy_denied"),
        ):
            result = LinkMapperProvider().run(ARTICLE, payload(), self.previous())
        self.assertEqual(result.outcome, "partial_content")
        self.assertEqual(result.discovered_urls, ["https://example.com/from-previous"])

    def test_sitemap_404_without_previous(self) -> None:
        with mock.patch(
            "cerebellum_web_acquisition.providers.fetch_public_url",
            return_value=fetched(status=404, final_url="https://example.com/sitemap.xml"),
        ):
            result = LinkMapperProvider().run(ARTICLE, payload(), None)
        self.assertEqual(result.outcome, "partial_content")
        self.assertIsNone(result.cleaned_content)
        self.assertEqual(result.content_type, "text/plain")
        self.assertEqual(result.discovered_urls, [])


class ScraplingTests(unittest.TestCase):
    def fake_modules(self, page):
        scrapling = types.ModuleType("scrapling")
        fetchers = types.ModuleType("scrapling.fetchers")

        class StealthyFetcher:
            @staticmethod
            def fetch(url, **kwargs):
                if isinstance(page, Exception):
                    raise page
                return page

        fetchers.StealthyFetcher = StealthyFetcher
        scrapling.fetchers = fetchers
        return {"scrapling": scrapling, "scrapling.fetchers": fetchers}

    def run_enabled(self, page):
        with mock.patch.dict(os.environ, {"CEREBELLUM_ENABLE_SCRAPLING": "1"}, clear=True), mock.patch.dict(
            sys.modules, self.fake_modules(page)
        ):
            return ScraplingProvider().run(ARTICLE, payload())

    def test_disabled_without_env(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = ScraplingProvider().run(ARTICLE, payload())
        self.assertEqual(result.error_code, "provider_disabled")

    def test_unavailable_without_package(self) -> None:
        with mock.patch.dict(os.environ, {"CEREBELLUM_ENABLE_SCRAPLING": "1"}, clear=True), mock.patch.dict(
            sys.modules, {"scrapling": None}
        ):
            result = ScraplingProvider().run(ARTICLE, payload())
        self.assertEqual(result.error_code, "provider_unavailable")

    def test_success_extracts_text_and_links(self) -> None:
        class Element:
            def __init__(self, href):
                self.attrib = {"href": href}

        class Page:
            text = LONG_TEXT
            html_content = "<html><body>ok</body></html>"

            def css(self, selector):
                return [Element("https://example.com/in"), Element("https://evil.test/out"), Element(None)]

        result = self.run_enabled(Page())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.discovered_urls, ["https://example.com/in"])
        self.assertEqual(result.metadata["provider_version"], "0.4.8")
        self.assertFalse(result.metadata["identity_rotation"])

    def test_challenge_in_html(self) -> None:
        class Page:
            text = "whatever"
            html_content = "<div class='g-recaptcha'></div>"

            def css(self, selector):
                return []

        result = self.run_enabled(Page())
        self.assertEqual(result.outcome, "captcha")

    def test_css_failure_still_succeeds_without_links(self) -> None:
        class Page:
            text = LONG_TEXT
            html_content = "<html>ok</html>"

            def css(self, selector):
                raise RuntimeError("selector exploded")

        result = self.run_enabled(Page())
        self.assertEqual(result.outcome, "success")
        self.assertEqual(result.discovered_urls, [])

    def test_short_text_is_partial(self) -> None:
        class Page:
            text = "tiny"
            html_content = "tiny"

            def css(self, selector):
                return []

        result = self.run_enabled(Page())
        self.assertEqual(result.outcome, "partial_content")

    def test_fetch_exception_maps_to_provider_error(self) -> None:
        result = self.run_enabled(RuntimeError("browser crashed"))
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "provider_error")


class OpenCLITests(unittest.TestCase):
    def bridge_env(self, directory: str, session: str = "session-one") -> dict:
        executable = Path(directory) / "opencli-bridge.exe"
        executable.touch()
        return {
            "CEREBELLUM_ENABLE_OPENCLI": "1",
            "OPENCLI_BRIDGE_EXECUTABLE": str(executable),
            "OPENCLI_SESSION": session,
        }

    def run_bridge(self, completed=None, side_effect=None, env_extra=None, data=None, session="session-one"):
        data = data or payload(access_mode="authenticated_local")
        with tempfile.TemporaryDirectory() as directory:
            env = self.bridge_env(directory, session)
            env.update(env_extra or {})
            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "cerebellum_web_acquisition.providers.subprocess.run",
                return_value=completed,
                side_effect=side_effect,
            ) as run:
                result = OpenCLIProvider().run(ARTICLE, data)
            return result, run

    def test_public_access_mode_is_denied(self) -> None:
        result = OpenCLIProvider().run(ARTICLE, payload(access_mode="public"))
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "local_auth_not_allowed")

    def test_disabled_configurations(self) -> None:
        data = payload(access_mode="authenticated_local")
        cases = [
            {},
            {"CEREBELLUM_ENABLE_OPENCLI": "1"},
            {
                "CEREBELLUM_ENABLE_OPENCLI": "1",
                "OPENCLI_BRIDGE_EXECUTABLE": "relative.exe",
                "OPENCLI_SESSION": "session-one",
            },
            {
                "CEREBELLUM_ENABLE_OPENCLI": "1",
                "OPENCLI_BRIDGE_EXECUTABLE": "E:/missing/opencli.exe",
                "OPENCLI_SESSION": "session-one",
            },
        ]
        for env in cases:
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=True):
                result = OpenCLIProvider().run(ARTICLE, data)
            self.assertEqual(result.outcome, "auth_required")
            self.assertEqual(result.error_code, "local_bridge_disabled")
        # invalid session characters
        with tempfile.TemporaryDirectory() as directory:
            env = self.bridge_env(directory, session="bad session!")
            with mock.patch.dict(os.environ, env, clear=True):
                result = OpenCLIProvider().run(ARTICLE, data)
        self.assertEqual(result.error_code, "local_bridge_disabled")

    def test_command_shape_and_environment_allowlist(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({"url": ARTICLE, "markdown": LONG_TEXT}).encode(), stderr=b""
        )
        result, run = self.run_bridge(
            completed=completed, env_extra={"CEREBELLUM_TOKEN": "leak", "PATH": "/usr/bin"}
        )
        command = run.call_args.args[0]
        self.assertEqual(command[1:], ["--session", "session-one", "--url", ARTICLE, "--json"])
        self.assertTrue(Path(command[0]).is_absolute())
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], 120)
        self.assertFalse(kwargs["shell"])
        self.assertFalse(kwargs["check"])
        self.assertEqual(kwargs["env"], {"PATH": "/usr/bin"})
        self.assertEqual(result.outcome, "success")
        self.assertTrue(result.metadata["local_session"])
        self.assertEqual(result.metadata["provider_version"], "1.8.4")

    def test_nonzero_exit_is_bridge_failed(self) -> None:
        completed = subprocess.CompletedProcess([], 3, stdout=b"", stderr=b"nope")
        result, _ = self.run_bridge(completed=completed)
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "local_bridge_failed")

    def test_oversize_output_is_denied(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0, stdout=b" " * (MAX_DOCUMENT_BYTES + 1), stderr=b""
        )
        result, _ = self.run_bridge(completed=completed)
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "bridge_output_too_large")

    def test_invalid_json_is_bridge_error(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout=b"not json", stderr=b"")
        result, _ = self.run_bridge(completed=completed)
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "local_bridge_error")

    def test_forbidden_redirect_url_in_output_is_bridge_error(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps({"url": "http://127.0.0.1/internal"}).encode(), stderr=b""
        )
        result, _ = self.run_bridge(completed=completed)
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "local_bridge_error")

    def test_timeout_and_oserror_are_bridge_errors(self) -> None:
        for failure in (subprocess.TimeoutExpired(cmd="x", timeout=120), OSError("spawn")):
            with self.subTest(failure=type(failure).__name__):
                result, _ = self.run_bridge(side_effect=failure)
                self.assertEqual(result.error_code, "local_bridge_error")

    def test_challenge_markdown_maps_outcome(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0,
            stdout=json.dumps({"url": ARTICLE, "markdown": "just a moment..."}).encode(),
            stderr=b"",
        )
        result, _ = self.run_bridge(completed=completed)
        self.assertEqual(result.outcome, "explicit_challenge")
        self.assertEqual(result.error_code, "explicit_challenge")

    def test_short_markdown_is_partial_and_links_filtered(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0,
            stdout=json.dumps(
                {
                    "url": ARTICLE,
                    "title": "Note",
                    "markdown": "short",
                    "links": ["https://example.com/ok", "https://evil.test/no", 5],
                }
            ).encode(),
            stderr=b"",
        )
        result, _ = self.run_bridge(completed=completed)
        self.assertEqual(result.outcome, "partial_content")
        self.assertEqual(result.title, "Note")
        self.assertEqual(result.discovered_urls, ["https://example.com/ok"])


class MediaCrawlerPartialTests(unittest.TestCase):
    def test_short_detail_text_is_partial_content(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mc-partial-"))
        out_dir = tmp / "xhs" / "jsonl"
        out_dir.mkdir(parents=True)
        with open(out_dir / "detail_contents_2026-08-29.jsonl", "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"note_id": "n1", "title": "短", "desc": "很短"}) + "\n")
        data = {
            "source_policy": {
                "kind": "xhs",
                "access_mode": "authenticated_local",
                "base_url": "https://www.xiaohongshu.com/",
                "allowed_domains": ["xiaohongshu.com"],
            }
        }
        url = "https://www.xiaohongshu.com/explore/n1?xsec_token=t"
        with mock.patch.dict(os.environ, {"CEREBELLUM_ENABLE_MEDIACRAWLER": "1"}, clear=True), mock.patch(
            "cerebellum_web_acquisition.providers.configured_dir",
            return_value=Path("E:/fake/mc"),
        ), mock.patch(
            "cerebellum_web_acquisition.providers.run_mediacrawler", return_value=tmp
        ):
            result = MediaCrawlerDetailProvider().run(url, data)
        self.assertEqual(result.outcome, "partial_content")
        self.assertEqual(result.title, "短")


class TavilyTests(unittest.TestCase):
    def test_missing_key_requires_auth(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = TavilyProvider().search("query", payload())
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.error_code, "provider_disabled")
        self.assertEqual(result.url, "https://example.com/")

    def test_request_exception_maps_to_server_error(self) -> None:
        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "tv-key"}, clear=True), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            side_effect=TimeoutError("slow"),
        ):
            result = TavilyProvider().search("query", payload())
        self.assertEqual(result.outcome, "server_error")
        self.assertEqual(result.retry_after_seconds, 60)

    def test_non_success_status(self) -> None:
        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "tv-key"}, clear=True), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(403, {}, {}),
        ):
            result = TavilyProvider().search("query", payload())
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.error_code, "provider_http_403")

    def test_success_returns_filtered_result_urls(self) -> None:
        body = {"results": [{"url": "https://example.com/a"}, {"url": "https://evil.test/b"}, "junk"]}
        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "tv-key"}, clear=True), mock.patch(
            "cerebellum_web_acquisition.providers._json_service_request",
            return_value=(200, {}, body),
        ) as request:
            result = TavilyProvider().search("snow gear", payload())
        self.assertEqual(result.outcome, "partial_content")
        self.assertEqual(result.error_code, "search_results_only")
        self.assertEqual(result.discovered_urls, ["https://example.com/a"])
        body_sent = request.call_args.args[2]
        self.assertEqual(body_sent["api_key"], "tv-key")
        self.assertEqual(body_sent["max_results"], 10)


if __name__ == "__main__":
    unittest.main()
