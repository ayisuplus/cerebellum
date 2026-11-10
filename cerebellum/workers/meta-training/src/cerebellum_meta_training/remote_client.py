from __future__ import annotations

import hashlib
import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class ControlPlaneError(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapSession:
    run_id: str
    snapshot_id: str
    provider_instance_id: str
    bundle_hash: str
    manifest_hash: str
    snapshot_manifest_hash: str
    base_model: dict
    qlora: dict
    expert_plan: dict | None = None


class RemoteWorkerClient:
    def __init__(self, gateway: str, run_id: str) -> None:
        parsed = urllib.parse.urlsplit(gateway.rstrip("/"))
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("worker gateway must be an absolute HTTP(S) URL")
        self.gateway = gateway.rstrip("/")
        self.run_id = run_id
        self._token: str | None = None
        self._token_lock = threading.Lock()

    def _json_request(
        self,
        method: str,
        path: str,
        body: object | None = None,
        *,
        authenticated: bool = True,
        rotate_token: bool = False,
    ) -> object:
        encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        with self._token_lock:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "cerebellum-autodl-worker/0.1",
            }
            if authenticated:
                if not self._token:
                    raise ControlPlaneError("worker has no scoped session token")
                headers["Authorization"] = f"Bearer {self._token}"
            request = urllib.request.Request(
                self.gateway + path, data=encoded, method=method, headers=headers
            )
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    payload = response.read()
            except urllib.error.HTTPError as error:
                detail = error.read(4096).decode("utf-8", "replace")
                raise ControlPlaneError(
                    f"control plane returned HTTP {error.code}: {detail}"
                ) from error
            value = json.loads(payload) if payload else None
            if rotate_token:
                if not isinstance(value, dict) or not isinstance(
                    value.get("worker_token"), str
                ):
                    raise ControlPlaneError("response lacks a rotated worker token")
                self._token = value["worker_token"]
            return value

    def bootstrap(self, code: str) -> BootstrapSession:
        deadline = time.monotonic() + 300
        while True:
            try:
                value = self._json_request(
                    "POST",
                    "/v1/training-worker/bootstrap",
                    {"run_id": self.run_id, "bootstrap_code": code},
                    authenticated=False,
                )
                break
            except ControlPlaneError as error:
                message = str(error).lower()
                retryable = any(
                    marker in message
                    for marker in ("not bound", "not accepting", "http 409")
                )
                if not retryable or time.monotonic() >= deadline:
                    raise
                time.sleep(2)
        if not isinstance(value, dict) or not isinstance(value.get("worker_token"), str):
            raise ControlPlaneError("bootstrap response lacks a scoped worker token")
        with self._token_lock:
            self._token = value["worker_token"]
        return BootstrapSession(
            run_id=value["run_id"],
            snapshot_id=value.get("snapshot_id", value["run_id"]),
            provider_instance_id=value["provider_instance_id"],
            bundle_hash=value["bundle_hash"],
            manifest_hash=value["manifest_hash"],
            snapshot_manifest_hash=value.get("snapshot_manifest_hash", value["manifest_hash"]),
            base_model=value["base_model"],
            qlora=value["qlora"],
            expert_plan=value.get("expert_plan"),
        )

    def heartbeat(self, progress: str, message: str | None = None) -> bool:
        value = self._json_request(
            "POST",
            f"/v1/training-worker/runs/{self.run_id}/heartbeat",
            {"progress": progress, "message": message},
            rotate_token=True,
        )
        if not isinstance(value, dict):
            raise ControlPlaneError("heartbeat response is not an object")
        return bool(value.get("cancel_requested", False))

    def download_bundle(self, destination: Path, expected_hash: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(4):
            offset = destination.stat().st_size if destination.exists() else 0
            with self._token_lock:
                if not self._token:
                    raise ControlPlaneError("worker has no scoped session token")
                headers = {
                    "Authorization": f"Bearer {self._token}",
                    "User-Agent": "cerebellum-autodl-worker/0.1",
                }
                if offset:
                    headers["Range"] = f"bytes={offset}-"
                request = urllib.request.Request(
                    self.gateway
                    + f"/v1/training-worker/runs/{self.run_id}/bundle",
                    headers=headers,
                )
                try:
                    response = urllib.request.urlopen(request, timeout=90)
                except urllib.error.HTTPError as error:
                    detail = error.read(4096).decode("utf-8", "replace")
                    raise ControlPlaneError(
                        f"bundle download returned HTTP {error.code}: {detail}"
                    ) from error
            mode = "ab" if offset and response.status == 206 else "wb"
            try:
                with response, destination.open(mode) as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
            except (OSError, http.client.HTTPException):
                continue
            if file_sha256(destination) == expected_hash:
                return
        raise ControlPlaneError("bundle download could not resume to the expected SHA-256")

    def upload_artifact(self, kind: str, source: Path) -> str:
        digest = file_sha256(source)
        size = source.stat().st_size
        parsed = urllib.parse.urlsplit(self.gateway)
        connection_type = (
            http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_type(parsed.hostname, parsed.port, timeout=300)
        path = (
            parsed.path.rstrip("/")
            + f"/v1/training-worker/runs/{self.run_id}/artifacts/{kind}"
        )
        with source.open("rb") as content:
            with self._token_lock:
                if not self._token:
                    raise ControlPlaneError("worker has no scoped session token")
                connection.putrequest("PUT", path)
                connection.putheader("Authorization", f"Bearer {self._token}")
                connection.putheader("Content-Type", "application/octet-stream")
                connection.putheader("Content-Length", str(size))
                connection.putheader("X-Content-SHA256", digest)
                connection.endheaders()
                first = content.read(1024 * 1024)
                if first:
                    connection.send(first)
            while True:
                chunk = content.read(1024 * 1024)
                if not chunk:
                    break
                connection.send(chunk)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        if response.status >= 300:
            raise ControlPlaneError(
                f"artifact upload returned HTTP {response.status}: "
                + payload[:4096].decode("utf-8", "replace")
            )
        value = json.loads(payload) if payload else {}
        if value.get("object_hash") != digest:
            raise ControlPlaneError("artifact upload acknowledgement has a mismatched hash")
        return digest

    def complete(self, model_id: str, version: str, artifact_hash: str, metrics: dict) -> dict:
        value = self._json_request(
            "POST",
            f"/v1/training-worker/runs/{self.run_id}/complete",
            {
                "model_id": model_id,
                "model_version": version,
                "artifact_hash": artifact_hash,
                "metrics": metrics,
            },
        )
        if not isinstance(value, dict):
            raise ControlPlaneError("completion response is not an object")
        return value

    def fail(self, error: str) -> None:
        self._json_request(
            "POST",
            f"/v1/training-worker/runs/{self.run_id}/fail",
            {"error": error[:2000]},
        )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
