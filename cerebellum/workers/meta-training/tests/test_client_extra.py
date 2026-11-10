from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest import mock

from cerebellum_meta_training.client import ControlPlaneClient


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

    def test_claim_posts_meta_training_kind_and_long_lease(self) -> None:
        job = {"job_id": "job-1", "payload": {}}
        self.urlopen.return_value = FakeResponse(json.dumps(job).encode())
        self.assertEqual(self.client.claim("worker-a"), job)
        request, kwargs = self.last_request()
        self.assertEqual(request.full_url, "https://cp.test/v1/learning/jobs:claim")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(
            request.get_header("User-agent"), "cerebellum-meta-training-worker/0.1"
        )
        # Training jobs run for hours: the HTTP timeout is 300s, lease 6h.
        self.assertEqual(kwargs["timeout"], 300)
        body = json.loads(request.data.decode())
        self.assertEqual(
            body,
            {"worker": "worker-a", "lease_seconds": 21_600, "kinds": ["meta_train_v1"]},
        )

    def test_claim_empty_or_non_object_response_means_no_job(self) -> None:
        self.assertIsNone(self.client.claim("worker-a"))
        self.urlopen.return_value = FakeResponse(b'"just a string"')
        self.assertIsNone(self.client.claim("worker-a"))

    def test_http_error_raises_with_status_and_detail(self) -> None:
        self.urlopen.side_effect = http_error(503, b"overloaded")
        with self.assertRaisesRegex(RuntimeError, "HTTP 503: overloaded"):
            self.client.claim("worker-a")
        self.assertEqual(self.urlopen.call_count, 1)

    def test_get_object_uses_cas_path_with_auth(self) -> None:
        self.urlopen.return_value = FakeResponse(b"dataset-bytes")
        digest = "cd" * 32
        self.assertEqual(self.client.get_object(digest), b"dataset-bytes")
        request, kwargs = self.last_request()
        self.assertEqual(request.full_url, f"https://cp.test/v1/objects/{digest}")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(kwargs["timeout"], 300)

    def test_get_result_maps_404_to_none_and_reraises_other_errors(self) -> None:
        self.urlopen.return_value = FakeResponse(b'{"status": "done"}')
        self.assertEqual(self.client.get_result("job-1"), {"status": "done"})
        request, _ = self.last_request()
        self.assertEqual(
            request.full_url, "https://cp.test/v1/meta-training/results/job-1"
        )
        self.assertEqual(request.get_method(), "GET")

        self.urlopen.side_effect = http_error(404, b"not found")
        self.assertIsNone(self.client.get_result("job-2"))

        self.urlopen.side_effect = http_error(500, b"boom")
        with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
            self.client.get_result("job-3")

    def test_submit_result_posts_collection_and_requires_object(self) -> None:
        self.urlopen.return_value = FakeResponse(b'{"result_hash": "abc"}')
        value = self.client.submit_result({"run_id": "run-1"})
        self.assertEqual(value, {"result_hash": "abc"})
        request, _ = self.last_request()
        self.assertEqual(request.full_url, "https://cp.test/v1/meta-training/results")
        self.assertEqual(json.loads(request.data.decode()), {"run_id": "run-1"})

        self.urlopen.return_value = FakeResponse(b"[1]")
        with self.assertRaisesRegex(RuntimeError, "non-object"):
            self.client.submit_result({"run_id": "run-1"})

    def test_complete_and_fail_paths_with_truncation(self) -> None:
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
        self.assertEqual(body["error"], "e" * 2_000)


if __name__ == "__main__":
    unittest.main()
