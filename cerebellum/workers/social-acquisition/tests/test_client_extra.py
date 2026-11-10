from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest import mock

from cerebellum_social_acquisition.client import ControlPlaneClient, ControlPlaneError


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

    def test_claim_posts_social_kind_and_lease(self) -> None:
        job = {"job_id": "job-1", "payload": {}}
        self.urlopen.return_value = FakeResponse(json.dumps(job).encode())
        self.assertEqual(self.client.claim("worker-a"), job)
        request, kwargs = self.last_request()
        self.assertEqual(request.full_url, "https://cp.test/v1/learning/jobs:claim")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(
            request.get_header("User-agent"),
            "cerebellum-social-acquisition-worker/0.1",
        )
        self.assertEqual(kwargs["timeout"], 60.0)
        body = json.loads(request.data.decode())
        self.assertEqual(
            body,
            {
                "worker": "worker-a",
                "lease_seconds": 900,
                "kinds": ["social_acquisition_v1"],
            },
        )

    def test_claim_empty_or_non_object_response_means_no_job(self) -> None:
        self.assertIsNone(self.client.claim("worker-a"))
        self.urlopen.return_value = FakeResponse(b"[1, 2]")
        self.assertIsNone(self.client.claim("worker-a"))

    def test_http_and_network_errors_raise_control_plane_error(self) -> None:
        self.urlopen.side_effect = http_error(429, b"slow down")
        with self.assertRaisesRegex(ControlPlaneError, "HTTP 429: slow down"):
            self.client.claim("worker-a")
        self.assertEqual(self.urlopen.call_count, 1)

        self.urlopen.side_effect = urllib.error.URLError("dns failure")
        with self.assertRaisesRegex(ControlPlaneError, "control plane unavailable"):
            self.client.claim("worker-a")

    def test_reserve_source_rate_reads_reserved_flag(self) -> None:
        self.urlopen.return_value = FakeResponse(b'{"reserved": true}')
        self.assertTrue(self.client.reserve_source_rate("job-1", "worker-a", 7))
        request, _ = self.last_request()
        self.assertEqual(
            request.full_url, "https://cp.test/v1/acquisition/source-rate:reserve"
        )
        self.assertEqual(
            json.loads(request.data.decode()),
            {"job_id": "job-1", "worker": "worker-a", "ordinal": 7},
        )
        self.urlopen.return_value = FakeResponse(b'{"reserved": false}')
        self.assertFalse(self.client.reserve_source_rate("job-1", "worker-a", 7))
        self.urlopen.return_value = FakeResponse(b"null")
        self.assertFalse(self.client.reserve_source_rate("job-1", "worker-a", 7))

    def test_get_result_maps_404_to_none(self) -> None:
        self.urlopen.return_value = FakeResponse(b'{"status": "done"}')
        self.assertEqual(self.client.get_result("job-1"), {"status": "done"})
        request, _ = self.last_request()
        self.assertEqual(request.full_url, "https://cp.test/v1/acquisition/results/job-1")

        self.urlopen.side_effect = http_error(404, b"missing")
        self.assertIsNone(self.client.get_result("job-2"))

        self.urlopen.side_effect = http_error(500, b"boom")
        with self.assertRaises(ControlPlaneError):
            self.client.get_result("job-3")

    def test_submit_result_bundles_optional_content(self) -> None:
        self.urlopen.return_value = FakeResponse(b'{"result_hash": "abc"}')
        value = self.client.submit_result({"job_id": "job-1"}, "Y2xlYW4=", None)
        self.assertEqual(value, {"result_hash": "abc"})
        body = json.loads(self.last_request()[0].data.decode())
        self.assertEqual(body["result"], {"job_id": "job-1"})
        self.assertEqual(body["cleaned_content_base64"], "Y2xlYW4=")
        self.assertIsNone(body["raw_content_base64"])

        self.urlopen.return_value = FakeResponse(b'"oops"')
        with self.assertRaisesRegex(ControlPlaneError, "non-object"):
            self.client.submit_result({"job_id": "job-1"})

    def test_complete_posts_worker(self) -> None:
        self.client.complete("job-1", "worker-a")
        request, _ = self.last_request()
        self.assertEqual(
            request.full_url, "https://cp.test/v1/learning/jobs/job-1:complete"
        )
        self.assertEqual(json.loads(request.data.decode()), {"worker": "worker-a"})

    def test_fail_truncates_message_and_clamps_retry_after(self) -> None:
        attempt = {"url": "https://weibo.com", "outcome": "rate_limited"}
        self.client.fail("job-1", "worker-a", "e" * 5_000, 30, attempt)
        request, _ = self.last_request()
        self.assertEqual(request.full_url, "https://cp.test/v1/learning/jobs/job-1:fail")
        body = json.loads(request.data.decode())
        self.assertEqual(body["error"], "e" * 2_000)
        self.assertEqual(body["retry_after_seconds"], 30)
        self.assertEqual(body["acquisition_attempt"], attempt)

        self.client.fail("job-1", "worker-a", "x", -1)
        self.assertEqual(
            json.loads(self.last_request()[0].data.decode())["retry_after_seconds"], 0
        )
        self.client.fail("job-1", "worker-a", "x", 999_999)
        self.assertEqual(
            json.loads(self.last_request()[0].data.decode())["retry_after_seconds"],
            86_400,
        )


if __name__ == "__main__":
    unittest.main()
