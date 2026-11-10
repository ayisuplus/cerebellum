from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from cerebellum_meta_training import remote_client
from cerebellum_meta_training.remote_client import (
    BootstrapSession,
    ControlPlaneError,
    RemoteWorkerClient,
    file_sha256,
)

MODULE = "cerebellum_meta_training.remote_client"


class FakeHTTPResponse:
    """Minimal stand-in for the object returned by urllib.request.urlopen."""

    def __init__(self, payload: bytes = b"", status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk, self._payload = self._payload, b""
            return chunk
        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class FlakyHTTPResponse(FakeHTTPResponse):
    """Streams a fixed number of chunks, then breaks the connection."""

    def __init__(self, chunks: list[bytes], status: int = 200) -> None:
        super().__init__(b"", status)
        self._chunks = list(chunks)

    def read(self, size: int = -1) -> bytes:
        if not self._chunks:
            raise OSError("connection reset by peer")
        return self._chunks.pop(0)


def http_error(code: int, detail: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://gateway.example/x", code, "error", None, io.BytesIO(detail.encode())
    )


def bootstrap_payload(**overrides: object) -> dict:
    value = {
        "worker_token": "token-a",
        "run_id": "run-1",
        "snapshot_id": "snap-1",
        "provider_instance_id": "pro-1",
        "bundle_hash": "b" * 64,
        "manifest_hash": "m" * 64,
        "snapshot_manifest_hash": "s" * 64,
        "base_model": {"model_id": "example/model"},
        "qlora": {"rank": 16},
        "expert_plan": None,
    }
    value.update(overrides)
    return value


def json_response(value: dict) -> FakeHTTPResponse:
    return FakeHTTPResponse(json.dumps(value).encode())


class GatewayValidationTests(unittest.TestCase):
    def test_gateway_must_be_an_absolute_http_url(self) -> None:
        for gateway in ("", "gateway.example", "ftp://gateway.example", "https://"):
            with self.subTest(gateway=gateway):
                with self.assertRaises(ValueError):
                    RemoteWorkerClient(gateway, "run-1")
        client = RemoteWorkerClient("https://gateway.example/", "run-1")
        self.assertEqual(client.gateway, "https://gateway.example")

    def test_request_without_scoped_token_fails_closed(self) -> None:
        client = RemoteWorkerClient("https://gateway.example", "run-1")
        with mock.patch(f"{MODULE}.urllib.request.urlopen") as urlopen:
            with self.assertRaisesRegex(ControlPlaneError, "no scoped session token"):
                client.heartbeat("starting")
            with self.assertRaisesRegex(ControlPlaneError, "no scoped session token"):
                client.download_bundle(Path(tempfile.mkdtemp()) / "bundle.tar", "0" * 64)
            with self.assertRaisesRegex(ControlPlaneError, "no scoped session token"):
                client.upload_artifact("adapter", Path(__file__))
        urlopen.assert_not_called()


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_retries_pending_binding_then_scopes_token(self) -> None:
        client = RemoteWorkerClient("https://gateway.example", "run-1")
        responses = [
            http_error(409, "run is not bound to a worker yet"),
            json_response(bootstrap_payload()),
        ]
        requests: list = []

        def fake_urlopen(request, timeout=0):
            requests.append(request)
            outcome = responses.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with mock.patch(f"{MODULE}.urllib.request.urlopen", side_effect=fake_urlopen), mock.patch(
            f"{MODULE}.time.sleep"
        ) as sleep:
            session = client.bootstrap("one-use-code")
        sleep.assert_called_once_with(2)
        self.assertEqual(len(requests), 2)
        for request in requests:
            self.assertNotIn("Authorization", request.headers)
            self.assertEqual(request.get_method(), "POST")
            body = json.loads(request.data)
            self.assertEqual(body["bootstrap_code"], "one-use-code")
            self.assertEqual(body["run_id"], "run-1")
        self.assertIsInstance(session, BootstrapSession)
        self.assertEqual(session.run_id, "run-1")
        self.assertEqual(session.snapshot_id, "snap-1")
        self.assertEqual(session.provider_instance_id, "pro-1")
        self.assertEqual(session.bundle_hash, "b" * 64)
        self.assertEqual(session.base_model, {"model_id": "example/model"})
        self.assertEqual(session.qlora, {"rank": 16})

    def test_bootstrap_rejected_code_is_not_retried(self) -> None:
        client = RemoteWorkerClient("https://gateway.example", "run-1")
        with mock.patch(
            f"{MODULE}.urllib.request.urlopen",
            side_effect=http_error(403, "bootstrap code already consumed"),
        ) as urlopen, mock.patch(f"{MODULE}.time.sleep") as sleep:
            with self.assertRaisesRegex(ControlPlaneError, "HTTP 403"):
                client.bootstrap("consumed-code")
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_bootstrap_gives_up_after_deadline_on_pending_binding(self) -> None:
        client = RemoteWorkerClient("https://gateway.example", "run-1")
        with mock.patch(
            f"{MODULE}.urllib.request.urlopen",
            side_effect=http_error(409, "worker is not accepting bootstrap"),
        ), mock.patch(f"{MODULE}.time.sleep"), mock.patch(
            f"{MODULE}.time.monotonic", side_effect=[0.0, 301.0]
        ):
            with self.assertRaisesRegex(ControlPlaneError, "not accepting"):
                client.bootstrap("one-use-code")

    def test_bootstrap_response_without_token_is_rejected(self) -> None:
        client = RemoteWorkerClient("https://gateway.example", "run-1")
        payload = bootstrap_payload()
        del payload["worker_token"]
        with mock.patch(
            f"{MODULE}.urllib.request.urlopen", return_value=json_response(payload)
        ):
            with self.assertRaisesRegex(ControlPlaneError, "lacks a scoped worker token"):
                client.bootstrap("one-use-code")

    def test_bootstrap_defaults_snapshot_fields_to_run_and_manifest(self) -> None:
        client = RemoteWorkerClient("https://gateway.example", "run-1")
        payload = bootstrap_payload()
        del payload["snapshot_id"]
        del payload["snapshot_manifest_hash"]
        del payload["expert_plan"]
        with mock.patch(
            f"{MODULE}.urllib.request.urlopen", return_value=json_response(payload)
        ):
            session = client.bootstrap("one-use-code")
        self.assertEqual(session.snapshot_id, "run-1")
        self.assertEqual(session.snapshot_manifest_hash, "m" * 64)
        self.assertIsNone(session.expert_plan)


def bootstrapped_client(token: str = "token-a") -> RemoteWorkerClient:
    client = RemoteWorkerClient("https://gateway.example", "run-1")
    with mock.patch(
        f"{MODULE}.urllib.request.urlopen",
        return_value=json_response(bootstrap_payload(worker_token=token)),
    ):
        client.bootstrap("one-use-code")
    return client


class HeartbeatTests(unittest.TestCase):
    def test_heartbeat_sends_bearer_token_and_rotates_it(self) -> None:
        client = bootstrapped_client()
        seen_auth: list[str] = []
        responses = [
            json_response({"worker_token": "token-b", "cancel_requested": False}),
            json_response({"worker_token": "token-c", "cancel_requested": True}),
        ]

        def fake_urlopen(request, timeout=0):
            seen_auth.append(request.headers["Authorization"])
            return responses.pop(0)

        with mock.patch(f"{MODULE}.urllib.request.urlopen", side_effect=fake_urlopen):
            self.assertFalse(client.heartbeat("training", "half-way"))
            self.assertTrue(client.heartbeat("training"))
        self.assertEqual(seen_auth, ["Bearer token-a", "Bearer token-b"])
        self.assertEqual(client._token, "token-c")

    def test_heartbeat_without_rotated_token_is_rejected(self) -> None:
        client = bootstrapped_client()
        with mock.patch(
            f"{MODULE}.urllib.request.urlopen",
            return_value=json_response({"cancel_requested": False}),
        ):
            with self.assertRaisesRegex(ControlPlaneError, "rotated worker token"):
                client.heartbeat("training")

    def test_http_error_detail_is_mapped_to_control_plane_error(self) -> None:
        client = bootstrapped_client()
        with mock.patch(
            f"{MODULE}.urllib.request.urlopen",
            side_effect=http_error(500, "internal detail"),
        ):
            with self.assertRaisesRegex(ControlPlaneError, "HTTP 500: internal detail"):
                client.heartbeat("training")


class BundleDownloadTests(unittest.TestCase):
    def test_download_resumes_after_disconnect_and_verifies_hash(self) -> None:
        client = bootstrapped_client()
        content = b"bundle-payload" * 100
        partial, remainder = content[:200], content[200:]
        responses = [
            FlakyHTTPResponse([partial]),
            FakeHTTPResponse(remainder, status=206),
        ]
        ranges: list[str | None] = []

        def fake_urlopen(request, timeout=0):
            ranges.append(request.headers.get("Range"))
            return responses.pop(0)

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "nested" / "bundle.tar"
            with mock.patch(f"{MODULE}.urllib.request.urlopen", side_effect=fake_urlopen):
                client.download_bundle(destination, hashlib.sha256(content).hexdigest())
            self.assertEqual(destination.read_bytes(), content)
        self.assertEqual(ranges, [None, f"bytes={len(partial)}-"])

    def test_download_restarts_when_server_ignores_range(self) -> None:
        client = bootstrapped_client()
        content = b"full-bundle" * 50
        responses = [
            FlakyHTTPResponse([content[:64]]),
            FakeHTTPResponse(content, status=200),
        ]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle.tar"
            with mock.patch(f"{MODULE}.urllib.request.urlopen", side_effect=responses):
                client.download_bundle(destination, hashlib.sha256(content).hexdigest())
            self.assertEqual(destination.read_bytes(), content)

    def test_download_fails_when_hash_never_matches(self) -> None:
        client = bootstrapped_client()
        corrupt = b"corrupt" * 32
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle.tar"
            with mock.patch(
                f"{MODULE}.urllib.request.urlopen",
                side_effect=lambda request, timeout=0: FakeHTTPResponse(corrupt),
            ):
                with self.assertRaisesRegex(ControlPlaneError, "could not resume"):
                    client.download_bundle(destination, "0" * 64)
            self.assertTrue(destination.exists())

    def test_download_maps_http_error(self) -> None:
        client = bootstrapped_client()
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch(
                f"{MODULE}.urllib.request.urlopen",
                side_effect=http_error(404, "bundle expired"),
            ):
                with self.assertRaisesRegex(
                    ControlPlaneError, "bundle download returned HTTP 404"
                ):
                    client.download_bundle(Path(directory) / "bundle.tar", "0" * 64)


class FakeUploadConnection:
    instances: list["FakeUploadConnection"] = []
    status = 200
    payload = b"{}"

    def __init__(self, host: str, port: int | None, timeout: int = 0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.request: tuple[str, str] | None = None
        self.headers: dict[str, str] = {}
        self.body = b""
        self.closed = False
        FakeUploadConnection.instances.append(self)

    def putrequest(self, method: str, path: str) -> None:
        self.request = (method, path)

    def putheader(self, name: str, value: str) -> None:
        self.headers[name] = value

    def endheaders(self) -> None:
        pass

    def send(self, data: bytes) -> None:
        self.body += data

    def getresponse(self) -> FakeHTTPResponse:
        return FakeHTTPResponse(self.payload, self.status)

    def close(self) -> None:
        self.closed = True


class ArtifactUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeUploadConnection.instances = []
        FakeUploadConnection.status = 200
        FakeUploadConnection.payload = b"{}"

    def _patch_connections(self):
        return mock.patch.multiple(
            f"{MODULE}.http.client",
            HTTPSConnection=FakeUploadConnection,
            HTTPConnection=FakeUploadConnection,
        )

    def test_upload_streams_file_and_verifies_acknowledged_hash(self) -> None:
        client = RemoteWorkerClient("https://gateway.example/base", "run-1")
        client._token = "token-a"
        content = (b"adapter-weights" * 200000)[: 2 * 1024 * 1024 + 7]
        digest = hashlib.sha256(content).hexdigest()
        FakeUploadConnection.payload = json.dumps({"object_hash": digest}).encode()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "adapter.zip"
            source.write_bytes(content)
            with self._patch_connections():
                self.assertEqual(client.upload_artifact("adapter", source), digest)
        self.assertEqual(len(FakeUploadConnection.instances), 1)
        connection = FakeUploadConnection.instances[0]
        self.assertEqual(connection.host, "gateway.example")
        self.assertEqual(connection.timeout, 300)
        self.assertEqual(
            connection.request,
            ("PUT", "/base/v1/training-worker/runs/run-1/artifacts/adapter"),
        )
        self.assertEqual(connection.headers["Authorization"], "Bearer token-a")
        self.assertEqual(connection.headers["X-Content-SHA256"], digest)
        self.assertEqual(connection.headers["Content-Length"], str(len(content)))
        self.assertEqual(connection.body, content)
        self.assertTrue(connection.closed)

    def test_upload_without_token_fails_closed(self) -> None:
        client = RemoteWorkerClient("https://gateway.example", "run-1")
        with self._patch_connections():
            with self.assertRaisesRegex(ControlPlaneError, "no scoped session token"):
                client.upload_artifact("adapter", Path(__file__))
        self.assertEqual(FakeUploadConnection.instances[0].body, b"")

    def test_upload_rejects_mismatched_acknowledgement_hash(self) -> None:
        client = bootstrapped_client()
        FakeUploadConnection.payload = json.dumps({"object_hash": "0" * 64}).encode()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "adapter.zip"
            source.write_bytes(b"adapter")
            with self._patch_connections():
                with self.assertRaisesRegex(ControlPlaneError, "mismatched hash"):
                    client.upload_artifact("adapter", source)

    def test_upload_maps_http_failure(self) -> None:
        client = bootstrapped_client()
        FakeUploadConnection.status = 413
        FakeUploadConnection.payload = b"too large"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "adapter.zip"
            source.write_bytes(b"adapter")
            with self._patch_connections():
                with self.assertRaisesRegex(
                    ControlPlaneError, "artifact upload returned HTTP 413: too large"
                ):
                    client.upload_artifact("adapter", source)

    def test_http_gateway_uses_plain_http_connection(self) -> None:
        client = RemoteWorkerClient("http://gateway.example:9000", "run-1")
        client._token = "token-a"
        digest = hashlib.sha256(b"adapter").hexdigest()
        FakeUploadConnection.payload = json.dumps({"object_hash": digest}).encode()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "adapter.zip"
            source.write_bytes(b"adapter")
            with mock.patch.multiple(
                f"{MODULE}.http.client",
                HTTPConnection=FakeUploadConnection,
                HTTPSConnection=mock.Mock(side_effect=AssertionError("must not use TLS")),
            ):
                client.upload_artifact("adapter", source)
        self.assertEqual(FakeUploadConnection.instances[0].port, 9000)


class CompletionTests(unittest.TestCase):
    def test_complete_posts_bundle_fields_and_returns_response(self) -> None:
        client = bootstrapped_client()
        captured: list = []

        def fake_urlopen(request, timeout=0):
            captured.append(request)
            return json_response({"status": "candidate", "activated": False})

        with mock.patch(f"{MODULE}.urllib.request.urlopen", side_effect=fake_urlopen):
            value = client.complete("meta-controller", "1.0.0", "a" * 64, {"loss": 0.1})
        self.assertEqual(value, {"status": "candidate", "activated": False})
        request = captured[0]
        self.assertEqual(
            request.full_url,
            "https://gateway.example/v1/training-worker/runs/run-1/complete",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer token-a")
        body = json.loads(request.data)
        self.assertEqual(body["model_id"], "meta-controller")
        self.assertEqual(body["model_version"], "1.0.0")
        self.assertEqual(body["artifact_hash"], "a" * 64)
        self.assertEqual(body["metrics"], {"loss": 0.1})
        # Payloads are compact: no incidental whitespace.
        self.assertNotIn(b" ", request.data)

    def test_complete_rejects_non_object_response(self) -> None:
        client = bootstrapped_client()
        with mock.patch(
            f"{MODULE}.urllib.request.urlopen",
            return_value=FakeHTTPResponse(b"[1,2]"),
        ):
            with self.assertRaisesRegex(ControlPlaneError, "not an object"):
                client.complete("m", "1", "h", {})

    def test_fail_truncates_error_detail(self) -> None:
        client = bootstrapped_client()
        captured: list = []

        def fake_urlopen(request, timeout=0):
            captured.append(request)
            return FakeHTTPResponse(b"")

        with mock.patch(f"{MODULE}.urllib.request.urlopen", side_effect=fake_urlopen):
            client.fail("x" * 5000)
        body = json.loads(captured[0].data)
        self.assertEqual(len(body["error"]), 2000)


class FileHashTests(unittest.TestCase):
    def test_file_sha256_matches_hashlib(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.bin"
            path.write_bytes(b"\x00" * 1024 * 1024 + b"tail")
            self.assertEqual(
                file_sha256(path), hashlib.sha256(path.read_bytes()).hexdigest()
            )


if __name__ == "__main__":
    unittest.main()
