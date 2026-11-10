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
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as error:
            # The control-plane response cannot contain the hosted model API key.
            detail = error.read(4096).decode("utf-8", "replace")
            raise RuntimeError(f"control plane returned HTTP {error.code}: {detail}") from error
        return json.loads(data) if data else None

    def claim(self, worker: str, lease_seconds: int = 3600) -> dict | None:
        value = self._request(
            "POST",
            "/v1/learning/jobs:claim",
            {"worker": worker, "lease_seconds": lease_seconds, "kinds": ["skillopt_optimize_v1"]},
        )
        return value if isinstance(value, dict) else None

    def get_object(self, digest: str) -> bytes:
        request = urllib.request.Request(
            self.base_url.rstrip("/") + f"/v1/objects/{digest}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()

    def submit_result(self, run_id: str, result: dict) -> dict:
        value = self._request("POST", f"/v1/optimization-runs/{run_id}/result", result)
        assert isinstance(value, dict)
        return value

    def complete(self, job_id: str, worker: str) -> None:
        self._request("POST", f"/v1/learning/jobs/{job_id}:complete", {"worker": worker})

    def fail(self, job_id: str, worker: str, message: str) -> None:
        self._request(
            "POST",
            f"/v1/learning/jobs/{job_id}:fail",
            {"worker": worker, "error": message[:2000]},
        )
