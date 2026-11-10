from __future__ import annotations

import gzip
import socket
import unittest
import zlib
from unittest import mock

from cerebellum_social_acquisition import policy
from cerebellum_social_acquisition.policy import (
    MAX_REDIRECTS,
    PolicyError,
    _read_bounded,
    canonicalize_url,
    classify_http_status,
    escalation_action,
    fetch_public_post_json,
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


class CanonicalizeUrlTests(unittest.TestCase):
    def test_strips_tracking_parameters_and_sorts_query(self) -> None:
        value = canonicalize_url(
            "HTTPS://Example.COM:443/a?utm_source=x&b=2&a=1&fbclid=z"
            "&gclid=z&mc_cid=z&mc_eid=z&ref_src=z#frag"
        )
        self.assertEqual(value, "https://example.com/a?a=1&b=2")

    def test_keeps_non_default_port_and_default_path(self) -> None:
        self.assertEqual(
            canonicalize_url("http://example.com:8080"), "http://example.com:8080/"
        )
        self.assertEqual(canonicalize_url("http://example.com:80/x"), "http://example.com/x")

    def test_rejects_non_http_schemes_credentials_and_local_hosts(self) -> None:
        for value in (
            "file:///etc/passwd",
            "ftp://example.com/x",
            "https://user:password@example.com/",
            "http://localhost/",
            "http://foo.localhost/",
            "http://printer.local/",
            "http://nas.internal/",
            "http://router.home.arpa/",
        ):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                canonicalize_url(value)

    def test_rejects_private_loopback_and_link_local_ip_literals(self) -> None:
        for value in (
            "http://127.0.0.1/admin",
            "http://10.0.0.8/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data",
            "http://[::1]/",
        ):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                canonicalize_url(value)

    def test_rejects_malformed_and_oversized_urls(self) -> None:
        for value in (
            "",
            "   ",
            "https://example.com/" + "a" * 8_192,
            "https://example.com\\@127.0.0.1/",
            "https://example.com/\x00",
            "http://example.com:99999/",
        ):
            with self.subTest(value=value[:40]), self.assertRaises(PolicyError):
                canonicalize_url(value)

    def test_allowlist_enforces_domain_boundary(self) -> None:
        self.assertEqual(
            canonicalize_url("https://s.weibo.com/x", ["weibo.com"]),
            "https://s.weibo.com/x",
        )
        for host in ("evilweibo.com", "weibo.com.evil.test"):
            with self.subTest(host=host), self.assertRaises(PolicyError):
                canonicalize_url(f"https://{host}/", ["weibo.com"])

    def test_invalid_allowlist_entry_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            host_allowed("example.com", ["exa mple.com/"])


class HostAllowedTests(unittest.TestCase):
    def test_empty_allowlist_allows_everything(self) -> None:
        self.assertTrue(host_allowed("anything.example", []))

    def test_exact_and_subdomain_match_only(self) -> None:
        allowed = ["Example.COM."]
        self.assertTrue(host_allowed("example.com", allowed))
        self.assertTrue(host_allowed("a.b.example.com", allowed))
        self.assertFalse(host_allowed("notexample.com", allowed))
        self.assertFalse(host_allowed("example.com.evil.test", allowed))


class ResolvePublicAddressesTests(unittest.TestCase):
    def test_public_ip_literal_skips_dns(self) -> None:
        self.assertEqual(resolve_public_addresses("93.184.216.34", 443), ["93.184.216.34"])

    def test_private_ip_literal_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            resolve_public_addresses("127.0.0.1", 80)

    def test_dns_failure_maps_to_timeout_outcome(self) -> None:
        with mock.patch("socket.getaddrinfo", side_effect=socket.gaierror("nope")):
            with self.assertRaises(PolicyError) as caught:
                resolve_public_addresses("example.com", 443)
        self.assertEqual(caught.exception.outcome, "timeout")

    def test_mixed_public_private_resolution_is_rejected(self) -> None:
        answer = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ]
        with mock.patch("socket.getaddrinfo", return_value=answer):
            with self.assertRaises(PolicyError):
                resolve_public_addresses("example.com", 443)


class ReadBoundedTests(unittest.TestCase):
    def test_oversized_content_length_is_denied_before_reading(self) -> None:
        response = FakeResponse(b"x" * 2_048, {"content-length": "2048"})
        with self.assertRaises(PolicyError):
            _read_bounded(response, 1_024)
        self.assertEqual(response.offset, 0)

    def test_invalid_content_length_maps_to_parse_failed(self) -> None:
        response = FakeResponse(b"body", {"content-length": "not-a-number"})
        with self.assertRaises(PolicyError) as caught:
            _read_bounded(response, 1_024)
        self.assertEqual(caught.exception.outcome, "parse_failed")

    def test_unsupported_encoding_maps_to_parse_failed(self) -> None:
        response = FakeResponse(b"body", {"content-encoding": "br"})
        with self.assertRaises(PolicyError) as caught:
            _read_bounded(response, 1_024)
        self.assertEqual(caught.exception.outcome, "parse_failed")

    def test_gzip_and_deflate_bodies_are_decoded(self) -> None:
        raw = b"hello world" * 100
        gz = FakeResponse(gzip.compress(raw), {"content-encoding": "gzip"})
        self.assertEqual(_read_bounded(gz, len(raw)), raw)
        df = FakeResponse(zlib.compress(raw), {"content-encoding": "deflate"})
        self.assertEqual(_read_bounded(df, len(raw)), raw)

    def test_gzip_bomb_is_bounded(self) -> None:
        compressed = gzip.compress(b"A" * 100_000)
        response = FakeResponse(compressed, {"content-encoding": "gzip"})
        with self.assertRaises(PolicyError):
            _read_bounded(response, 1_024)


class ClassificationTests(unittest.TestCase):
    def test_classify_http_status_matrix(self) -> None:
        self.assertEqual(classify_http_status(200), "success")
        self.assertEqual(classify_http_status(204), "success")
        self.assertEqual(classify_http_status(401), "auth_required")
        self.assertEqual(classify_http_status(403), "auth_required")
        self.assertEqual(classify_http_status(404), "not_found")
        self.assertEqual(classify_http_status(410), "gone")
        self.assertEqual(classify_http_status(429), "rate_limited")
        self.assertEqual(classify_http_status(500), "server_error")
        self.assertEqual(classify_http_status(503), "server_error")
        self.assertEqual(classify_http_status(301), "policy_denied")
        self.assertEqual(classify_http_status(100), "policy_denied")

    def test_parse_retry_after_numeric_bounds(self) -> None:
        self.assertEqual(parse_retry_after(None), 60)
        self.assertEqual(parse_retry_after(""), 60)
        self.assertEqual(parse_retry_after("30"), 30)
        self.assertEqual(parse_retry_after("0"), 1)
        self.assertEqual(parse_retry_after("-5"), 1)
        self.assertEqual(parse_retry_after("999999"), 86_400)
        self.assertEqual(parse_retry_after("garbage"), 60)
        self.assertEqual(parse_retry_after("not a date at all"), 60)

    def test_parse_retry_after_http_date(self) -> None:
        # A date far in the past clamps to the 1 second floor.
        self.assertEqual(parse_retry_after("Thu, 01 Jan 1970 00:00:00 GMT"), 1)
        # A date far in the future clamps to the 86400 second ceiling.
        self.assertEqual(parse_retry_after("Fri, 01 Jan 2100 00:00:00 GMT"), 86_400)


class EscalationTests(unittest.TestCase):
    def test_success_and_terminal_outcomes_never_escalate(self) -> None:
        for method in ("api", "rss", "direct_http", "crawl4ai", "open_cli"):
            self.assertIsNone(escalation_action(method, "success", "public"))
        for outcome in (
            "robots_denied",
            "captcha",
            "explicit_challenge",
            "policy_denied",
            "not_found",
            "gone",
        ):
            self.assertIsNone(escalation_action("direct_http", outcome, "authenticated_local"))

    def test_retryable_outcomes_always_retry_in_place(self) -> None:
        for outcome in ("rate_limited", "timeout", "server_error"):
            for method in ("api", "scrapling", "open_cli"):
                self.assertEqual(escalation_action(method, outcome, "public"), "retry")

    def test_auth_required_escalates_only_for_local_credentials(self) -> None:
        self.assertEqual(
            escalation_action("api", "auth_required", "authenticated_local"), "open_cli"
        )
        self.assertIsNone(escalation_action("api", "auth_required", "public"))

    def test_degraded_content_walks_the_method_ladder(self) -> None:
        for outcome in ("partial_content", "js_shell", "parse_failed"):
            self.assertEqual(escalation_action("api", outcome, "public"), "crawl4ai")
            self.assertEqual(escalation_action("rss", outcome, "public"), "crawl4ai")
            self.assertEqual(
                escalation_action("direct_http", outcome, "public"), "crawl4ai"
            )
            self.assertEqual(escalation_action("crawl4ai", outcome, "public"), "firecrawl")
            self.assertEqual(
                escalation_action("firecrawl", outcome, "public"), "link_mapper"
            )
            self.assertEqual(
                escalation_action("link_mapper", outcome, "public"), "scrapling"
            )
            # The final rung needs locally installed credentials.
            self.assertEqual(
                escalation_action("scrapling", outcome, "authenticated_local"), "open_cli"
            )
            self.assertIsNone(escalation_action("scrapling", outcome, "public"))
            self.assertIsNone(
                escalation_action("open_cli", outcome, "authenticated_local")
            )


class FakeConnection:
    """Stands in for _PinnedHTTPConnection; records the request, replays a script."""

    instances: list["FakeConnection"] = []
    script: list[dict] = []

    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        self.host = host
        self.port = port
        self.address = address
        self.timeout = timeout
        self.requests: list[tuple] = []
        FakeConnection.instances.append(self)

    def request(self, method: str, path: str, **kwargs: object) -> None:
        self.requests.append((method, path, kwargs))

    def getresponse(self) -> "FakeHTTPResponse":
        step = FakeConnection.script.pop(0)
        if "error" in step:
            raise step["error"]
        return FakeHTTPResponse(step["status"], step.get("headers", []), step.get("body", b""))

    def close(self) -> None:
        pass


class FakeHTTPResponse:
    def __init__(self, status: int, headers: list[tuple], body: bytes) -> None:
        self.status = status
        self._headers = headers
        self._body = body
        self._offset = 0

    def getheaders(self) -> list[tuple]:
        return self._headers

    def getheader(self, name: str, default: str | None = None) -> str | None:
        lowered = {key.lower(): value for key, value in self._headers}
        return lowered.get(name.lower(), default)

    def read(self, size: int) -> bytes:
        value = self._body[self._offset : self._offset + size]
        self._offset += len(value)
        return value


class PinnedConnectionTests(unittest.TestCase):
    def test_http_connection_dials_the_pinned_address(self) -> None:
        with mock.patch("socket.create_connection", return_value=mock.Mock()) as create:
            connection = policy._PinnedHTTPConnection("example.com", 80, "93.184.216.34", 5.0)
            connection.connect()
        create.assert_called_once_with(("93.184.216.34", 80), 5.0, None)
        self.assertIs(connection.sock, create.return_value)

    def test_https_connection_wraps_socket_with_original_hostname(self) -> None:
        sock = mock.Mock()
        context = mock.Mock()
        with (
            mock.patch("socket.create_connection", return_value=sock),
            mock.patch("ssl.create_default_context", return_value=context),
        ):
            connection = policy._PinnedHTTPSConnection("example.com", 443, "93.184.216.34", 5.0)
            connection.connect()
        context.wrap_socket.assert_called_once_with(sock, server_hostname="example.com")
        self.assertIs(connection.sock, context.wrap_socket.return_value)


class FetchPublicUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeConnection.instances = []
        FakeConnection.script = []
        patches = [
            mock.patch.object(policy, "_PinnedHTTPConnection", FakeConnection),
            mock.patch.object(policy, "_PinnedHTTPSConnection", FakeConnection),
            mock.patch.object(
                policy, "resolve_public_addresses", return_value=["93.184.216.34"]
            ),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_follows_redirect_and_recanonizes_location(self) -> None:
        FakeConnection.script = [
            {"status": 302, "headers": [("Location", "/next?utm_source=x&b=1")]},
            {"status": 200, "body": b"final"},
        ]
        result = fetch_public_url("http://example.com/start")
        self.assertEqual(result.status, 200)
        self.assertEqual(result.body, b"final")
        self.assertEqual(result.final_url, "http://example.com/next?b=1")
        self.assertEqual(len(FakeConnection.instances), 2)
        # Every hop pins the socket to the DNS-verified address.
        for connection in FakeConnection.instances:
            self.assertEqual(connection.address, "93.184.216.34")

    def test_redirect_limit_is_enforced(self) -> None:
        FakeConnection.script = [
            {"status": 302, "headers": [("Location", "/loop")]}
            for _ in range(MAX_REDIRECTS + 1)
        ]
        with self.assertRaisesRegex(PolicyError, "redirect limit"):
            fetch_public_url("http://example.com/loop")

    def test_redirect_without_location_is_denied(self) -> None:
        FakeConnection.script = [{"status": 301, "headers": []}]
        with self.assertRaisesRegex(PolicyError, "Location"):
            fetch_public_url("http://example.com/x")

    def test_timeout_maps_to_timeout_outcome(self) -> None:
        FakeConnection.script = [{"error": socket.timeout("slow")}]
        with self.assertRaises(PolicyError) as caught:
            fetch_public_url("http://example.com/x")
        self.assertEqual(caught.exception.outcome, "timeout")

    def test_network_failure_maps_to_server_error_outcome(self) -> None:
        FakeConnection.script = [{"error": OSError("reset")}]
        with self.assertRaises(PolicyError) as caught:
            fetch_public_url("http://example.com/x")
        self.assertEqual(caught.exception.outcome, "server_error")

    def test_post_json_sends_body_and_bounds_request_size(self) -> None:
        FakeConnection.script = [{"status": 200, "body": b'{"ok": true}'}]
        result = fetch_public_post_json("https://example.com/graphql", {"q": "hot"})
        self.assertEqual(result.status, 200)
        connection = FakeConnection.instances[0]
        method, path, kwargs = connection.requests[0]
        self.assertEqual(method, "POST")
        self.assertEqual(kwargs["body"], b'{"q":"hot"}')
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")

        with self.assertRaisesRegex(PolicyError, "maximum size"):
            fetch_public_post_json("https://example.com/graphql", {"q": "x" * 70_000})
        # The oversized request never reaches the network.
        self.assertEqual(len(FakeConnection.instances), 1)
    def test_post_json_maps_timeout_and_network_failures(self) -> None:
        FakeConnection.script = [{"error": socket.timeout("slow")}]
        with self.assertRaises(PolicyError) as caught:
            fetch_public_post_json("https://example.com/graphql", {"q": "hot"})
        self.assertEqual(caught.exception.outcome, "timeout")

        FakeConnection.script = [{"error": OSError("reset")}]
        with self.assertRaises(PolicyError) as caught:
            fetch_public_post_json("https://example.com/graphql", {"q": "hot"})
        self.assertEqual(caught.exception.outcome, "server_error")


if __name__ == "__main__":
    unittest.main()
