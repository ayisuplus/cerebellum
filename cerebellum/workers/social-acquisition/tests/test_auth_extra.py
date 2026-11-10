from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from cerebellum_social_acquisition.auth import (
    AUTHENTICATED_PROVIDERS,
    AuthenticatedDouyinProvider,
    AuthenticatedXhsProvider,
    _cookie_from_env,
)
from cerebellum_social_acquisition.policy import PolicyError


def payload(access_mode: str, kind: str = "douyin") -> dict:
    return {
        "plan_id": str(uuid.uuid4()),
        "source_policy_id": str(uuid.uuid4()),
        "source_policy": {
            "kind": kind,
            "base_url": "https://www.douyin.com/",
            "access_mode": access_mode,
            "allowed_domains": ["douyin.com", "xiaohongshu.com"],
            "max_pages_per_run": 10,
        },
    }


class FakeResponse:
    def __init__(self, status: int, body: bytes, headers: dict | None = None, final_url: str = ""):
        self.status = status
        self.body = body
        self.headers = headers or {}
        self.final_url = final_url or "https://www.douyin.com/final"


class CookieFromEnvTests(unittest.TestCase):
    def test_unset_env_returns_none(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(_cookie_from_env("CEREBELLUM_NOPE", None))

    def test_unreadable_path_returns_none(self) -> None:
        with mock.patch.dict(
            os.environ, {"CEREBELLUM_COOKIE_FILE": "E:/no/such/dir/cookie.txt"}, clear=False
        ):
            self.assertIsNone(_cookie_from_env("CEREBELLUM_COOKIE_FILE", None))

    def test_oversized_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookie.txt"
            path.write_bytes(b"a=1; " * 4000)  # > 16 KiB
            with mock.patch.dict(os.environ, {"CEREBELLUM_COOKIE_FILE": str(path)}, clear=False):
                self.assertIsNone(_cookie_from_env("CEREBELLUM_COOKIE_FILE", None))

    def test_empty_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookie.txt"
            path.write_bytes(b"   \n  ")
            with mock.patch.dict(os.environ, {"CEREBELLUM_COOKIE_FILE": str(path)}, clear=False):
                self.assertIsNone(_cookie_from_env("CEREBELLUM_COOKIE_FILE", None))

    def test_non_utf8_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookie.txt"
            path.write_bytes(b"\xff\xfe\x00bad")
            with mock.patch.dict(os.environ, {"CEREBELLUM_COOKIE_FILE": str(path)}, clear=False):
                self.assertIsNone(_cookie_from_env("CEREBELLUM_COOKIE_FILE", None))

    def test_valid_cookie_is_stripped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookie.txt"
            path.write_text("  sessionid=abc123  \n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"CEREBELLUM_COOKIE_FILE": str(path)}, clear=False):
                self.assertEqual(_cookie_from_env("CEREBELLUM_COOKIE_FILE", None), "sessionid=abc123")


class DouyinProviderEdgeTests(unittest.TestCase):
    def _with_cookie(self, directory: str) -> str:
        path = Path(directory) / "douyin_cookie.txt"
        path.write_text("sessionid=valid-session", encoding="utf-8")
        return str(path)

    def test_http_error_status_maps_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_DOUYIN_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url",
                return_value=FakeResponse(429, b"{}", headers={"retry-after": "33"}),
            ):
                result = AuthenticatedDouyinProvider().discover(payload("authenticated_local"))
        self.assertEqual(result.outcome, "rate_limited")
        self.assertEqual(result.http_status, 429)
        self.assertEqual(result.error_code, "http_429")
        self.assertEqual(result.retry_after_seconds, 33)

    def test_policy_error_from_fetch_maps_to_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_DOUYIN_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url",
                side_effect=PolicyError("dns blocked", outcome="timeout"),
            ):
                result = AuthenticatedDouyinProvider().discover(payload("authenticated_local"))
        self.assertEqual(result.outcome, "timeout")
        self.assertEqual(result.error_code, "timeout")
        self.assertEqual(result.retry_after_seconds, 60)

    def test_invalid_json_is_parse_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_DOUYIN_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url",
                return_value=FakeResponse(200, b"<html>login wall</html>"),
            ):
                result = AuthenticatedDouyinProvider().discover(payload("authenticated_local"))
        self.assertEqual(result.outcome, "parse_failed")
        self.assertEqual(result.error_code, "invalid_json")

    def test_empty_board_under_authentication_is_auth_required(self) -> None:
        # 登录态失效的典型表现：200 但 word_list 为空
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_DOUYIN_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url",
                return_value=FakeResponse(200, b'{"data":{"word_list":[]}}'),
            ):
                result = AuthenticatedDouyinProvider().discover(payload("authenticated_local"))
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.error_code, "empty_board_under_authentication")
        self.assertEqual(result.http_status, 200)


class XhsProviderEdgeTests(unittest.TestCase):
    SSR = (
        "<script>window.__INITIAL_STATE__={\"feed\":{\"feeds\":["
        "{\"modelType\":\"note\",\"id\":\"x1\",\"xsecToken\":\"tok\","
        "\"noteCard\":{\"displayTitle\":\"认证笔记\",\"user\":{\"nickname\":\"某\"}}}"
        "]}}</script>"
    )

    def _with_cookie(self, directory: str) -> str:
        path = Path(directory) / "xhs_cookie.txt"
        path.write_text("web_session=valid; a1=other", encoding="utf-8")
        return str(path)

    def test_public_policy_is_policy_denied(self) -> None:
        result = AuthenticatedXhsProvider().discover(payload("public", kind="xhs"))
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "authenticated_provider_requires_authenticated_local")

    def test_success_with_valid_cookie_sends_it(self) -> None:
        captured: dict = {}

        def fake_fetch(url, allowed, *, headers=None, **kwargs):
            captured.update(headers or {})
            return FakeResponse(200, self.SSR.encode("utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_XHS_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url", side_effect=fake_fetch
            ):
                result = AuthenticatedXhsProvider().discover(payload("authenticated_local", kind="xhs"))
        self.assertEqual(result.outcome, "success")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "认证笔记")
        self.assertIn("web_session=valid", captured.get("Cookie", ""))
        self.assertIn("xsec_token=tok", result.items[0].url)

    def test_empty_feed_under_authentication_is_auth_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_XHS_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url",
                return_value=FakeResponse(200, b"<html>no state</html>"),
            ):
                result = AuthenticatedXhsProvider().discover(payload("authenticated_local", kind="xhs"))
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.error_code, "empty_feed_under_authentication")

    def test_http_error_status_maps_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_XHS_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url",
                return_value=FakeResponse(403, b""),
            ):
                result = AuthenticatedXhsProvider().discover(payload("authenticated_local", kind="xhs"))
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.http_status, 403)
        self.assertEqual(result.error_code, "http_403")
    def test_fetch_policy_error_maps_to_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_XHS_COOKIE_FILE": self._with_cookie(directory)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url",
                side_effect=PolicyError("dns blocked", outcome="timeout"),
            ):
                result = AuthenticatedXhsProvider().discover(payload("authenticated_local", kind="xhs"))
        self.assertEqual(result.outcome, "timeout")
        self.assertEqual(result.error_code, "timeout")
        self.assertEqual(result.retry_after_seconds, 60)


class RegistryTests(unittest.TestCase):
    def test_authenticated_providers_registry(self) -> None:
        self.assertEqual(set(AUTHENTICATED_PROVIDERS), {"douyin", "xhs"})
        self.assertIsInstance(AUTHENTICATED_PROVIDERS["douyin"], AuthenticatedDouyinProvider)
        self.assertIsInstance(AUTHENTICATED_PROVIDERS["xhs"], AuthenticatedXhsProvider)


if __name__ == "__main__":
    unittest.main()
