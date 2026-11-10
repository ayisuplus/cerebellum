from __future__ import annotations

import email.utils
import gzip
import socket
import time
import unittest
import zlib
from unittest import mock

from cerebellum_web_acquisition.policy import (
    MAX_REDIRECTS,
    PolicyError,
    _normalize_allowed_domain,
    _PinnedHTTPConnection,
    _PinnedHTTPSConnection,
    _read_bounded,
    canonicalize_url,
    classify_http_status,
    escalation_action,
    fetch_public_url,
    host_allowed,
    parse_retry_after,
    resolve_public_addresses,
)


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self.body = body
        self.headers = headers
        self.offset = 0

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name.lower(), default)

    def read(self, size: int) -> bytes:
        value = self.body[self.offset : self.offset + size]
        self.offset += len(value)
        return value


class StubHTTPResponse:
    def __init__(self, status: int, headers: dict | None = None, body: bytes = b"") -> None:
        self.status = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.body = body
        self.offset = 0

    def getheaders(self) -> list:
        return list(self.headers.items())

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name.lower(), default)

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self.body) - self.offset
        value = self.body[self.offset : self.offset + size]
        self.offset += len(value)
        return value


def scripted_connection_class(script: list):
    made: list = []

    class StubConnection:
        def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
            self.host = host
            self.port = port
            self.address = address
            self.timeout = timeout
            self.requests: list = []
            self.closed = False
            made.append(self)

        def request(self, method: str, path: str, headers: dict | None = None) -> None:
            self.requests.append((method, path, headers or {}))
            item = script.pop(0)
            if isinstance(item, Exception):
                raise item
            self._response = item

        def getresponse(self) -> StubHTTPResponse:
            return self._response

        def close(self) -> None:
            self.closed = True

    return StubConnection, made


class CanonicalizeExtraTests(unittest.TestCase):
    def test_rejects_empty_oversize_and_forbidden_characters(self) -> None:
        for value in ("", "   ", "http://example.com/" + "a" * 8_200):
            with self.subTest(value=value[:30]), self.assertRaises(PolicyError):
                canonicalize_url(value)
        for value in ("http://example.com/a\\b", "http://example.com/a\x00b"):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                canonicalize_url(value)

    def test_rejects_non_http_schemes_and_missing_host(self) -> None:
        for value in ("ftp://example.com/a", "gopher://example.com/", "http:///path"):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                canonicalize_url(value)

    def test_rejects_local_hostnames(self) -> None:
        for host in (
            "localhost",
            "localhost.localdomain",
            "app.localhost",
            "printer.local",
            "nas.internal",
            "gw.home.arpa",
        ):
            with self.subTest(host=host), self.assertRaises(PolicyError):
                canonicalize_url(f"http://{host}/")

    def test_rejects_non_public_ip_literals(self) -> None:
        for value in (
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://[::1]/",
            "http://[fe80::1]/",
            "http://0.0.0.0/",
            "http://224.0.0.1/",
        ):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                canonicalize_url(value)

    def test_public_ip_literal_is_allowed(self) -> None:
        self.assertEqual(canonicalize_url("http://93.184.216.34/a"), "http://93.184.216.34/a")

    def test_invalid_idna_host_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            canonicalize_url("http://\ud800example.com/")

    def test_port_validation_and_default_port_stripping(self) -> None:
        self.assertEqual(canonicalize_url("http://example.com:80/a"), "http://example.com/a")
        self.assertEqual(canonicalize_url("https://example.com:443/a"), "https://example.com/a")
        self.assertEqual(
            canonicalize_url("http://example.com:8080/a"), "http://example.com:8080/a"
        )
        for value in (
            "http://example.com:99999/",
            "http://example.com:0/",
            "http://example.com:65536/",
        ):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                canonicalize_url(value)

    def test_ipv6_host_is_bracketed(self) -> None:
        self.assertEqual(
            canonicalize_url("http://[2606:2800:220:1:248:1893:25c8:1946]:8080/a"),
            "http://[2606:2800:220:1:248:1893:25c8:1946]:8080/a",
        )

    def test_tracking_parameters_removed_and_query_sorted(self) -> None:
        self.assertEqual(
            canonicalize_url(
                "https://example.com/a?utm_medium=x&b=2&fbclid=y&A=1&gclid=z&mc_cid=m&mc_eid=n&ref_src=r&c="
            ),
            "https://example.com/a?A=1&b=2&c=",
        )

    def test_allowlist_validation(self) -> None:
        for bad in ("bad:domain", "bad/domain", "bad@domain"):
            with self.subTest(bad=bad), self.assertRaises(PolicyError):
                canonicalize_url("https://example.com/", [bad])
        self.assertEqual(
            canonicalize_url("https://sub.example.com/", ["example.com"]),
            "https://sub.example.com/",
        )
        with self.assertRaises(PolicyError):
            canonicalize_url("https://notexample.com/", ["example.com"])

    def test_normalize_allowed_domain_rejects_invalid(self) -> None:
        with self.assertRaises(PolicyError):
            _normalize_allowed_domain("a:b")
        self.assertEqual(_normalize_allowed_domain(" Example.COM. "), "example.com")

    def test_host_allowed_semantics(self) -> None:
        self.assertTrue(host_allowed("anything.test", []))
        self.assertTrue(host_allowed("example.com", ["example.com"]))
        self.assertTrue(host_allowed("deep.sub.example.com", ["example.com"]))
        self.assertFalse(host_allowed("evil-example.com", ["example.com"]))
        self.assertFalse(host_allowed("example.com.evil.test", ["example.com"]))


class ResolveExtraTests(unittest.TestCase):
    def test_public_literal_returns_itself_without_dns(self) -> None:
        with mock.patch("socket.getaddrinfo") as dns:
            self.assertEqual(resolve_public_addresses("8.8.8.8", 443), ["8.8.8.8"])
        dns.assert_not_called()

    def test_dns_failure_maps_to_timeout_outcome(self) -> None:
        with mock.patch("socket.getaddrinfo", side_effect=socket.gaierror("no host")):
            with self.assertRaises(PolicyError) as ctx:
                resolve_public_addresses("missing.example", 443)
        self.assertEqual(ctx.exception.outcome, "timeout")

    def test_empty_dns_answer_is_forbidden(self) -> None:
        with mock.patch("socket.getaddrinfo", return_value=[]):
            with self.assertRaises(PolicyError):
                resolve_public_addresses("empty.example", 443)

    def test_answers_are_sorted(self) -> None:
        answer = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443)),
        ]
        with mock.patch("socket.getaddrinfo", return_value=answer):
            self.assertEqual(
                resolve_public_addresses("example.com", 443), ["8.8.8.8", "93.184.216.34"]
            )


class ReadBoundedExtraTests(unittest.TestCase):
    def test_identity_body_is_fully_read(self) -> None:
        body = b"x" * 200_000
        response = FakeResponse(body, {})
        self.assertEqual(_read_bounded(response, 300_000), body)

    def test_content_length_over_limit_is_denied(self) -> None:
        response = FakeResponse(b"", {"content-length": "5000"})
        with self.assertRaises(PolicyError) as ctx:
            _read_bounded(response, 1_024)
        self.assertEqual(ctx.exception.outcome, "policy_denied")

    def test_invalid_content_length_is_parse_failed(self) -> None:
        response = FakeResponse(b"abc", {"content-length": "not-a-number"})
        with self.assertRaises(PolicyError) as ctx:
            _read_bounded(response, 1_024)
        self.assertEqual(ctx.exception.outcome, "parse_failed")

    def test_unsupported_encoding_is_parse_failed(self) -> None:
        response = FakeResponse(b"abc", {"content-encoding": "br"})
        with self.assertRaises(PolicyError) as ctx:
            _read_bounded(response, 1_024)
        self.assertEqual(ctx.exception.outcome, "parse_failed")

    def test_gzip_within_limit_round_trips(self) -> None:
        payload = b"hello world " * 100
        response = FakeResponse(gzip.compress(payload), {"content-encoding": "gzip"})
        self.assertEqual(_read_bounded(response, 100_000), payload)

    def test_x_gzip_alias_is_accepted(self) -> None:
        payload = b"data"
        response = FakeResponse(gzip.compress(payload), {"content-encoding": "x-gzip"})
        self.assertEqual(_read_bounded(response, 1_024), payload)

    def test_deflate_within_limit_round_trips(self) -> None:
        payload = b"deflated payload " * 20
        response = FakeResponse(zlib.compress(payload), {"content-encoding": "deflate"})
        self.assertEqual(_read_bounded(response, 100_000), payload)

    def test_compressed_stream_over_limit_is_denied(self) -> None:
        response = FakeResponse(b"\xff" * 5_000, {"content-encoding": "gzip"})
        with self.assertRaises(PolicyError):
            _read_bounded(response, 1_000)

    def test_plain_body_over_limit_is_denied(self) -> None:
        response = FakeResponse(b"y" * 5_000, {})
        with self.assertRaises(PolicyError):
            _read_bounded(response, 1_000)


class PinnedConnectionTests(unittest.TestCase):
    def test_http_connection_dials_the_resolved_address(self) -> None:
        connection = _PinnedHTTPConnection("example.com", 80, "93.184.216.34", 5.0)
        fake_socket = mock.Mock()
        with mock.patch("socket.create_connection", return_value=fake_socket) as dial:
            connection.connect()
        dial.assert_called_once_with(("93.184.216.34", 80), 5.0, None)
        self.assertIs(connection.sock, fake_socket)

    def test_https_connection_wraps_socket_with_sni_hostname(self) -> None:
        connection = _PinnedHTTPSConnection("example.com", 443, "93.184.216.34", 5.0)
        connection._context = mock.Mock()
        wrapped = mock.Mock()
        connection._context.wrap_socket.return_value = wrapped
        raw_socket = mock.Mock()
        with mock.patch("socket.create_connection", return_value=raw_socket) as dial:
            connection.connect()
        dial.assert_called_once_with(("93.184.216.34", 443), 5.0, None)
        connection._context.wrap_socket.assert_called_once_with(
            raw_socket, server_hostname="example.com"
        )
        self.assertIs(connection.sock, wrapped)


class FetchPublicUrlTests(unittest.TestCase):
    def _fetch(self, script: list, url: str = "http://example.com/a", **kwargs):
        StubConnection, made = scripted_connection_class(script)
        with mock.patch(
            "cerebellum_web_acquisition.policy.resolve_public_addresses",
            return_value=["93.184.216.34"],
        ), mock.patch(
            "cerebellum_web_acquisition.policy._PinnedHTTPConnection", StubConnection
        ), mock.patch(
            "cerebellum_web_acquisition.policy._PinnedHTTPSConnection", StubConnection
        ):
            return fetch_public_url(url, **kwargs), made

    def test_simple_get_returns_response(self) -> None:
        result, made = self._fetch([StubHTTPResponse(200, {"content-type": "text/plain"}, b"hi")])
        self.assertEqual(result.status, 200)
        self.assertEqual(result.body, b"hi")
        self.assertEqual(result.final_url, "http://example.com/a")
        method, path, headers = made[0].requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/a")
        self.assertEqual(headers["Host"], "example.com")
        self.assertTrue(made[0].closed)

    def test_custom_headers_are_merged(self) -> None:
        _, made = self._fetch(
            [StubHTTPResponse(200)], headers={"X-Custom": "yes"}
        )
        self.assertEqual(made[0].requests[0][2]["X-Custom"], "yes")

    def test_redirect_is_followed_and_final_url_canonicalized(self) -> None:
        script = [
            StubHTTPResponse(302, {"location": "/next?utm_source=x&b=1"}),
            StubHTTPResponse(200, {}, b"done"),
        ]
        result, made = self._fetch(script)
        self.assertEqual(result.final_url, "http://example.com/next?b=1")
        self.assertEqual(len(made), 2)
        self.assertEqual(made[1].requests[0][1], "/next?b=1")

    def test_redirect_to_forbidden_target_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            self._fetch([StubHTTPResponse(302, {"location": "http://127.0.0.1/"})])

    def test_redirect_limit_exceeded(self) -> None:
        script = [StubHTTPResponse(302, {"location": "/loop"}) for _ in range(MAX_REDIRECTS + 1)]
        with self.assertRaises(PolicyError) as ctx:
            self._fetch(script)
        self.assertIn("redirect limit", str(ctx.exception))

    def test_redirect_without_location_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            self._fetch([StubHTTPResponse(302, {})])

    def test_timeout_maps_to_timeout_outcome(self) -> None:
        with self.assertRaises(PolicyError) as ctx:
            self._fetch([socket.timeout("slow")])
        self.assertEqual(ctx.exception.outcome, "timeout")

    def test_oserror_maps_to_server_error(self) -> None:
        with self.assertRaises(PolicyError) as ctx:
            self._fetch([OSError("connection reset")])
        self.assertEqual(ctx.exception.outcome, "server_error")

    def test_https_uses_tls_connection_and_443(self) -> None:
        _, made = self._fetch([StubHTTPResponse(200)], url="https://example.com/s")
        self.assertEqual(made[0].port, 443)


class ClassifyAndRetryAfterTests(unittest.TestCase):
    def test_classify_http_status_full_matrix(self) -> None:
        cases = {
            200: "success",
            299: "success",
            401: "auth_required",
            403: "auth_required",
            404: "not_found",
            410: "gone",
            429: "rate_limited",
            500: "server_error",
            599: "server_error",
            418: "policy_denied",
            302: "policy_denied",
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertEqual(classify_http_status(status), expected)

    def test_parse_retry_after_defaults_and_clamps(self) -> None:
        self.assertEqual(parse_retry_after(None), 60)
        self.assertEqual(parse_retry_after(""), 60)
        self.assertEqual(parse_retry_after("120"), 120)
        self.assertEqual(parse_retry_after("0"), 1)
        self.assertEqual(parse_retry_after("99999999"), 86_400)
        self.assertEqual(parse_retry_after("not-a-date"), 60)

    def test_parse_retry_after_http_date(self) -> None:
        future = email.utils.formatdate(time.time() + 120, usegmt=True)
        value = parse_retry_after(future)
        self.assertGreaterEqual(value, 1)
        self.assertLessEqual(value, 130)
        past = email.utils.formatdate(time.time() - 120, usegmt=True)
        self.assertEqual(parse_retry_after(past), 1)


class EscalationExtraTests(unittest.TestCase):
    def test_success_and_unknown_outcomes_do_not_escalate(self) -> None:
        self.assertIsNone(escalation_action("direct_http", "success", "public"))
        self.assertIsNone(escalation_action("direct_http", "mystery", "public"))

    def test_search_methods_escalate_to_crawl4ai(self) -> None:
        for method in ("api", "rss"):
            for outcome in ("partial_content", "js_shell", "parse_failed"):
                with self.subTest(method=method, outcome=outcome):
                    self.assertEqual(escalation_action(method, outcome, "public"), "crawl4ai")

    def test_ladder_ordering(self) -> None:
        ladder = {
            "direct_http": "crawl4ai",
            "crawl4ai": "firecrawl",
            "firecrawl": "link_mapper",
            "link_mapper": "scrapling",
            "scrapling": "mediacrawler",
        }
        for method, expected in ladder.items():
            with self.subTest(method=method):
                self.assertEqual(escalation_action(method, "parse_failed", "public"), expected)
        self.assertIsNone(escalation_action("open_cli", "parse_failed", "authenticated_local"))
        self.assertIsNone(escalation_action("unknown_method", "parse_failed", "public"))


if __name__ == "__main__":
    unittest.main()
