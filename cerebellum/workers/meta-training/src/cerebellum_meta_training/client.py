from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlPlaneClient:
    base_url: str
    token: str

    def _request(self, method: str, path: str, body: object | None = None) -> object:
        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "cerebellum-meta-training-worker/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read(4096).decode("utf-8", "replace")
            raise RuntimeError(f"control plane returned HTTP {error.code}: {detail}") from error
        return json.loads(data) if data else None

    def claim(self, worker: str) -> dict | None:
        value = self._request(
            "POST",
            "/v1/learning/jobs:claim",
            {"worker": worker, "lease_seconds": 21_600, "kinds": ["meta_train_v1"]},
        )
        return value if isinstance(value, dict) else None

    def get_object(self, digest: str) -> bytes:
        request = urllib.request.Request(
            self.base_url.rstrip("/") + f"/v1/objects/{digest}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read()

    def get_result(self, job_id: str) -> dict | None:
        try:
            value = self._request("GET", f"/v1/meta-training/results/{job_id}")
        except RuntimeError as error:
            if "HTTP 404:" in str(error):
                return None
            raise
        return value if isinstance(value, dict) else None

    def submit_result(self, value: dict) -> dict:
        result = self._request("POST", "/v1/meta-training/results", value)
        if not isinstance(result, dict):
            raise RuntimeError("control plane returned a non-object training result")
        return result

    def complete(self, job_id: str, worker: str) -> None:
        self._request("POST", f"/v1/learning/jobs/{job_id}:complete", {"worker": worker})

    def fail(self, job_id: str, worker: str, message: str) -> None:
        self._request(
            "POST",
            f"/v1/learning/jobs/{job_id}:fail",
            {"worker": worker, "error": message[:2000]},
        )
