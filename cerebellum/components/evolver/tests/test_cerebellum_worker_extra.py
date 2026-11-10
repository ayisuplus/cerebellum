"""Extra tests for evolver.cerebellum_worker — HTTP client, error paths, run loop."""

import json
import urllib.error

import pytest
from unittest.mock import MagicMock, patch

from evolver.cerebellum_worker import CerebellumClient, process_once, run_worker


def _mock_response(payload: bytes):
    resp = MagicMock()
    resp.read.return_value = payload
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestCerebellumClient:
    def test_init_strips_trailing_slash(self):
        client = CerebellumClient("http://localhost:8080/", "tok")
        assert client.server_url == "http://localhost:8080"
        assert client.token == "tok"
        assert client.timeout == 30.0

    @patch("evolver.cerebellum_worker.urllib.request.urlopen")
    def test_request_sends_auth_headers_and_json_body(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(b'{"ok": true}')
        client = CerebellumClient("http://server", "secret-token", timeout=5.0)

        result = client._request("POST", "/v1/things", {"a": 1})

        assert result == b'{"ok": true}'
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "http://server/v1/things"
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer secret-token"
        assert request.headers["Content-type"] == "application/json"
        assert json.loads(request.data.decode("utf-8")) == {"a": 1}

    @patch("evolver.cerebellum_worker.urllib.request.urlopen")
    def test_request_get_sends_no_body(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(b"raw-bytes")
        client = CerebellumClient("http://server", "tok")

        result = client._request("GET", "/v1/objects/x")

        assert result == b"raw-bytes"
        assert mock_urlopen.call_args[0][0].data is None

    @patch("evolver.cerebellum_worker.urllib.request.urlopen")
    def test_request_http_error_raises_runtime_error_with_detail(self, mock_urlopen):
        error = urllib.error.HTTPError(
            url="http://server/v1/x", code=500, msg="Server Error", hdrs={}, fp=None,
        )
        error.read = lambda: b'{"detail": "boom"}'
        mock_urlopen.side_effect = error
        client = CerebellumClient("http://server", "tok")

        with pytest.raises(RuntimeError, match="HTTP 500") as exc_info:
            client._request("GET", "/v1/x")
        assert "boom" in str(exc_info.value)

    @patch("evolver.cerebellum_worker.urllib.request.urlopen")
    def test_json_parses_payload(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(b'{"job_id": "j1"}')
        client = CerebellumClient("http://server", "tok")
        assert client.json("POST", "/v1/learning/jobs:claim", {"worker": "w"}) == {"job_id": "j1"}

    @patch("evolver.cerebellum_worker.urllib.request.urlopen")
    def test_json_empty_payload_returns_none(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(b"")
        client = CerebellumClient("http://server", "tok")
        assert client.json("GET", "/v1/empty") is None

    def test_object_rejects_invalid_hash(self):
        client = CerebellumClient("http://server", "tok")
        with pytest.raises(ValueError, match="invalid CAS object hash"):
            client.object("tooshort")
        with pytest.raises(ValueError, match="invalid CAS object hash"):
            client.object("z" * 64)

    @patch("evolver.cerebellum_worker.urllib.request.urlopen")
    def test_object_fetches_valid_hash(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(b"blob")
        client = CerebellumClient("http://server", "tok")
        content_hash = "ab" * 32
        assert client.object(content_hash) == b"blob"
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == f"http://server/v1/objects/{content_hash}"
        assert request.method == "GET"


class TestProcessOnce:
    def test_empty_queue_returns_false(self):
        client = MagicMock()
        client.json.return_value = None
        assert process_once(MagicMock(), client, "worker-1") is False
        client.json.assert_called_once()
        assert client.json.call_args[0][1] == "/v1/learning/jobs:claim"
        client.object.assert_not_called()

    def test_failure_posts_fail_and_reraises(self):
        client = MagicMock()
        client.json.side_effect = [
            {"job_id": "job-9", "payload": {"request_hash": "cd" * 32}},
            {"status": "failed"},
        ]
        client.object.return_value = b"not-json"
        evolver = MagicMock()

        with pytest.raises(json.JSONDecodeError):
            process_once(evolver, client, "worker-2")

        fail_call = client.json.call_args_list[-1]
        assert fail_call[0][1] == "/v1/learning/jobs/job-9:fail"
        assert fail_call[0][2]["worker"] == "worker-2"
        assert "error" in fail_call[0][2]
        evolver.consolidate_experience.assert_not_called()

    def test_error_message_truncated_to_2000_chars(self):
        client = MagicMock()
        client.json.side_effect = [
            {"job_id": "job-10", "payload": {"request_hash": "ef" * 32}},
            {"status": "failed"},
        ]
        client.object.return_value = json.dumps({"x": 1}).encode("utf-8")
        evolver = MagicMock()
        evolver.consolidate_experience.side_effect = RuntimeError("x" * 5000)

        with pytest.raises(RuntimeError):
            process_once(evolver, client, "worker-3")

        error_text = client.json.call_args_list[-1][0][2]["error"]
        assert len(error_text) == 2000


class TestRunWorker:
    def test_once_with_empty_queue_processes_nothing(self):
        client = MagicMock()
        client.json.return_value = None
        with patch("evolver.cerebellum_worker.CerebellumClient", return_value=client):
            processed = run_worker(MagicMock(), "http://server", "tok", once=True)
        assert processed == 0

    def test_once_with_job_processes_one(self):
        client = MagicMock()
        request = {"schema_version": "cerebellum/v1"}
        client.json.side_effect = [
            {"job_id": "j1", "payload": {"request_hash": "ab" * 32}},
            {"imported": 1},
            {"status": "completed"},
        ]
        client.object.return_value = json.dumps(request).encode("utf-8")
        evolver = MagicMock()
        evolver.consolidate_experience.return_value = {"proposals": []}
        with patch("evolver.cerebellum_worker.CerebellumClient", return_value=client):
            processed = run_worker(evolver, "http://server", "tok", once=True)
        assert processed == 1

    def test_worker_id_defaults_to_host_and_uuid(self):
        client = MagicMock()
        client.json.return_value = None
        with patch("evolver.cerebellum_worker.CerebellumClient", return_value=client):
            run_worker(MagicMock(), "http://server", "tok", once=True)
        claim_body = client.json.call_args[0][2]
        assert claim_body["worker"].startswith("evolver:")
        assert claim_body["lease_seconds"] == 300
        assert claim_body["kinds"] == ["evolver_consolidate_v1"]

    def test_poll_loop_sleeps_when_queue_empty(self):
        class StopLoop(Exception):
            pass

        client = MagicMock()
        with patch("evolver.cerebellum_worker.CerebellumClient", return_value=client), \
             patch("evolver.cerebellum_worker.process_once",
                   side_effect=[True, False]) as mock_process, \
             patch("evolver.cerebellum_worker.time.sleep",
                   side_effect=StopLoop) as mock_sleep:
            with pytest.raises(StopLoop):
                run_worker(MagicMock(), "http://server", "tok",
                           once=False, poll_seconds=0.01, worker_id="w")

        assert mock_process.call_count == 2
        mock_sleep.assert_called_once_with(0.1)  # clamped to minimum 0.1
