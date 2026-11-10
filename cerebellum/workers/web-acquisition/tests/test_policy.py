from __future__ import annotations

import gzip
import socket
import unittest
from unittest import mock

from cerebellum_web_acquisition.policy import (
    PolicyError,
    _read_bounded,
    canonicalize_url,
    escalation_action,
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


class PolicyTests(unittest.TestCase):
    def test_canonicalization_and_domain_boundary(self) -> None:
        self.assertEqual(
            canonicalize_url(
                "HTTPS://Docs.Example.com:443/a?utm_source=x&b=2&a=1#fragment",
                ["example.com"],
            ),
            "https://docs.example.com/a?a=1&b=2",
        )
        for value in (
            "file:///etc/passwd",
            "http://127.0.0.1/admin",
            "http://169.254.169.254/latest/meta-data",
            "https://user:password@example.com/",
            "https://example.com\\@127.0.0.1/",
            "https://example.com.evil.test/",
        ):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                canonicalize_url(value, ["example.com"])

    def test_dns_rebinding_target_is_rejected(self) -> None:
        answer = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ]
        with mock.patch("socket.getaddrinfo", return_value=answer):
            with self.assertRaises(PolicyError):
                resolve_public_addresses("example.com", 443)

    def test_decompression_bomb_is_bounded(self) -> None:
        compressed = gzip.compress(b"A" * 100_000)
        response = FakeResponse(compressed, {"content-encoding": "gzip"})
        with self.assertRaises(PolicyError):
            _read_bounded(response, 1_024)

    def test_escalation_matrix_never_switches_identity_for_retryable_errors(self) -> None:
        for outcome in ("rate_limited", "timeout", "server_error"):
            self.assertEqual(escalation_action("direct_http", outcome, "public"), "retry")
        for outcome in (
            "robots_denied",
            "captcha",
            "explicit_challenge",
            "policy_denied",
            "not_found",
            "gone",
        ):
            self.assertIsNone(escalation_action("direct_http", outcome, "authenticated_local"))
        self.assertEqual(
            escalation_action("direct_http", "auth_required", "authenticated_local"),
            "open_cli",
        )
        self.assertIsNone(escalation_action("direct_http", "auth_required", "public"))


if __name__ == "__main__":
    unittest.main()
