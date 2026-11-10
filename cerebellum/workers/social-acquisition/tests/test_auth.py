from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from cerebellum_social_acquisition.auth import (
    AuthenticatedDouyinProvider,
    AuthenticatedXhsProvider,
)


def payload(access_mode: str) -> dict:
    return {
        "plan_id": str(uuid.uuid4()),
        "source_policy_id": str(uuid.uuid4()),
        "source_policy": {
            "kind": "douyin",
            "base_url": "https://www.douyin.com/",
            "access_mode": access_mode,
            "allowed_domains": ["douyin.com"],
            "max_pages_per_run": 10,
        },
    }


class AuthenticatedFailClosedTests(unittest.TestCase):
    def test_public_policy_is_policy_denied(self) -> None:
        result = AuthenticatedDouyinProvider().discover(payload("public"))
        self.assertEqual(result.outcome, "policy_denied")
        self.assertEqual(result.error_code, "authenticated_provider_requires_authenticated_local")

    def test_missing_cookie_file_is_auth_required(self) -> None:
        with mock.patch.dict(os.environ, {"CEREBELLUM_DOUYIN_COOKIE_FILE": ""}, clear=False):
            result = AuthenticatedDouyinProvider().discover(payload("authenticated_local"))
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.error_code, "cookie_file_missing_or_invalid")

    def test_xhs_cookie_without_web_session_is_auth_required(self) -> None:
        value = payload("authenticated_local")
        value["source_policy"]["kind"] = "xhs"
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "xhs_cookie.txt"
            cookie_file.write_text("a1=some-value; other=1", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_XHS_COOKIE_FILE": str(cookie_file)},
                clear=False,
            ):
                result = AuthenticatedXhsProvider().discover(value)
        self.assertEqual(result.outcome, "auth_required")
        self.assertEqual(result.error_code, "cookie_file_missing_or_invalid")

    def test_authenticated_request_sends_cookie_and_never_echoes_it(self) -> None:
        value = payload("authenticated_local")
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "douyin_cookie.txt"
            cookie_file.write_text("sessionid=secret-session-value", encoding="utf-8")
            captured: dict = {}

            class FakeResponse:
                status = 200
                final_url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
                headers = {"content-type": "application/json"}
                body = b'{"data":{"word_list":[{"word":"\xce\xe7","hot_value":1,"sentence_id":"s1","position":1}]}}'

            def fake_fetch(url, allowed, *, timeout_seconds=30.0, headers=None):
                captured.update(headers or {})
                return FakeResponse()

            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_DOUYIN_COOKIE_FILE": str(cookie_file)},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.auth.fetch_public_url", side_effect=fake_fetch
            ):
                result = AuthenticatedDouyinProvider().discover(value)
        self.assertEqual(captured.get("Cookie"), "sessionid=secret-session-value")
        self.assertEqual(result.outcome, "success")
        self.assertEqual(len(result.items), 1)


if __name__ == "__main__":
    unittest.main()
