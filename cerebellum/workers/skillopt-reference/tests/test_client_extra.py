from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest import mock

from cerebellum_skillopt.client import ControlPlaneClient


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def http_error(code: int, detail: bytes = b"detail") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://cp.test/x", code, "msg", {}, io.BytesIO(detail))


class ControlPlaneClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = ControlPlaneClient("https://cp.test/", "secret-token")
        patcher = mock.patch("urllib.request.urlopen")
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)
        self.urlopen.return_value = FakeResponse(b"")

    def last_request(self) -> tuple:
        args, kwargs = self.urlopen.call_args
        return args[0], kwargs

    def test_claim_posts_auth_kind_and_lease(self) -> None:
        job = {"job_id": "job-1", "payload": {"run_id": "run-1"}}
        self.urlopen.return_value = FakeResponse(json.dumps(job).encode())
        self.assertEqual(self.client.claim("worker-a", lease_seconds=123), job)
        request, kwargs = self.last_request()
        self.assertEqual(request.full_url, "https://cp.test/v1/learning/jobs:claim")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(kwargs["timeout"], 60)
        body = json.loads(request.data.decode())
        self.assertEqual(
            body,
            {"worker": "worker-a", "lease_seconds": 123, "kinds": ["skillopt_optimize_v1"]},
        )

    def test_claim_empty_response_means_no_job(self) -> None:
        self.assertIsNone(self.client.claim("worker-a"))

    def test_claim_non_object_response_means_no_job(self) -> None:
        self.urlopen.return_value = FakeResponse(b"[1, 2]")
        self.assertIsNone(self.client.claim("worker-a"))

    def test_http_error_raises_with_status_and_truncated_detail(self) -> None:
        self.urlopen.side_effect = http_error(500, b"boom")
        with self.assertRaisesRegex(RuntimeError, "HTTP 500: boom"):
            self.client.claim("worker-a")
        self.urlopen.side_effect = http_error(502, b"x" * 10_000)
        with self.assertRaises(RuntimeError) as caught:
            self.client.claim("worker-a")
        # Only 4096 bytes of the error body may be echoed.
        self.assertLessEqual(len(str(caught.exception)), 4_200)

    def test_network_error_propagates_without_retry(self) -> None:
        self.urlopen.side_effect = urllib.error.URLError("connection refused")
        with self.assertRaises(urllib.error.URLError):
            self.client.claim("worker-a")
        self.assertEqual(self.urlopen.call_count, 1)

    def test_get_object_returns_raw_bytes_with_auth(self) -> None:
        self.urlopen.return_value = FakeResponse(b"\x00\x01binary")
        digest = "ab" * 32
        self.assertEqual(self.client.get_object(digest), b"\x00\x01binary")
        request, _ = self.last_request()
        self.assertEqual(request.full_url, f"https://cp.test/v1/objects/{digest}")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")

    def test_submit_result_posts_to_run_scoped_path(self) -> None:
        self.urlopen.return_value = FakeResponse(b'{"result_hash": "abc"}')
        value = self.client.submit_result("run-9", {"patches": []})
        self.assertEqual(value, {"result_hash": "abc"})
        request, _ = self.last_request()
        self.assertEqual(
            request.full_url, "https://cp.test/v1/optimization-runs/run-9/result"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data.decode()), {"patches": []})

    def test_submit_result_requires_an_object_response(self) -> None:
        self.urlopen.return_value = FakeResponse(b"null")
        with self.assertRaises(AssertionError):
            self.client.submit_result("run-9", {})

    def test_complete_and_fail_paths(self) -> None:
        self.client.complete("job-1", "worker-a")
        request, _ = self.last_request()
        self.assertEqual(
            request.full_url, "https://cp.test/v1/learning/jobs/job-1:complete"
        )
        self.assertEqual(json.loads(request.data.decode()), {"worker": "worker-a"})

        self.client.fail("job-2", "worker-a", "e" * 5_000)
        request, _ = self.last_request()
        self.assertEqual(request.full_url, "https://cp.test/v1/learning/jobs/job-2:fail")
        body = json.loads(request.data.decode())
        self.assertEqual(body["worker"], "worker-a")
        # Failure evidence is truncated to the 2000 character evidence budget.
        self.assertEqual(body["error"], "e" * 2_000)

    def test_base_url_trailing_slash_is_stripped_once(self) -> None:
        client = ControlPlaneClient("https://cp.test", "t")
        client.complete("job-1", "w")
        request, _ = self.last_request()
        self.assertEqual(
            request.full_url, "https://cp.test/v1/learning/jobs/job-1:complete"
        )


if __name__ == "__main__":
    unittest.main()
