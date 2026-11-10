from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


class ControlPlaneError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlPlaneClient:
    base_url: str
    token: str
    timeout_seconds: float = 60.0

    def _request(self, method: str, path: str, body: object | None = None) -> object:
        payload = None
        if body is not None:
            payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "cerebellum-social-acquisition-worker/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read(4096).decode("utf-8", "replace")
            raise ControlPlaneError(
                f"control plane returned HTTP {error.code}: {detail}"
            ) from error
        except urllib.error.URLError as error:
            raise ControlPlaneError(f"control plane unavailable: {error.reason}") from error
        return json.loads(data) if data else None

    def claim(self, worker: str, lease_seconds: int = 900) -> dict | None:
        value = self._request(
            "POST",
            "/v1/learning/jobs:claim",
            {
                "worker": worker,
                "lease_seconds": lease_seconds,
                "kinds": ["social_acquisition_v1"],
            },
        )
        return value if isinstance(value, dict) else None

    def reserve_source_rate(self, job_id: str, worker: str, ordinal: int) -> bool:
        value = self._request(
            "POST",
            "/v1/acquisition/source-rate:reserve",
            {"job_id": job_id, "worker": worker, "ordinal": ordinal},
        )
        return bool(isinstance(value, dict) and value.get("reserved"))

    def get_result(self, job_id: str) -> dict | None:
        try:
            value = self._request("GET", f"/v1/acquisition/results/{job_id}")
        except ControlPlaneError as error:
            if "HTTP 404:" in str(error):
                return None
            raise
        return value if isinstance(value, dict) else None

    def submit_result(
        self,
        result: dict,
        cleaned_content_base64: str | None = None,
        raw_content_base64: str | None = None,
    ) -> dict:
        value = self._request(
            "POST",
            "/v1/acquisition/results",
            {
                "result": result,
                "cleaned_content_base64": cleaned_content_base64,
                "raw_content_base64": raw_content_base64,
            },
        )
        if not isinstance(value, dict):
            raise ControlPlaneError("control plane returned a non-object acquisition result")
        return value

    def complete(self, job_id: str, worker: str) -> None:
        self._request(
            "POST", f"/v1/learning/jobs/{job_id}:complete", {"worker": worker}
        )

    def fail(
        self,
        job_id: str,
        worker: str,
        message: str,
        retry_after_seconds: int = 0,
        acquisition_attempt: dict | None = None,
    ) -> None:
        self._request(
            "POST",
            f"/v1/learning/jobs/{job_id}:fail",
            {
                "worker": worker,
                "error": message[:2000],
                "retry_after_seconds": max(0, min(int(retry_after_seconds), 86_400)),
                "acquisition_attempt": acquisition_attempt,
            },
        )
