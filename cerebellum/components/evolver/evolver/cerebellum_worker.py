"""Lease-based Evolver worker for the Cerebellum JSON/CAS boundary."""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
import uuid


class CerebellumClient:
    def __init__(self, server_url: str, token: str, timeout: float = 30.0):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, value=None) -> bytes:
        data = None if value is None else json.dumps(value).encode("utf-8")
        request = urllib.request.Request(
            f"{self.server_url}{path}", data=data, method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Cerebellum returned HTTP {error.code}: {detail}") from error

    def json(self, method: str, path: str, value=None):
        payload = self._request(method, path, value)
        return json.loads(payload) if payload else None

    def object(self, content_hash: str) -> bytes:
        if len(content_hash) != 64 or any(ch not in "0123456789abcdef" for ch in content_hash):
            raise ValueError("invalid CAS object hash")
        return self._request("GET", f"/v1/objects/{content_hash}")


def process_once(evolver, client: CerebellumClient, worker_id: str) -> bool:
    """Process at most one Evolver job; return False when the queue is empty."""
    job = client.json("POST", "/v1/learning/jobs:claim", {
        "worker": worker_id,
        "lease_seconds": 300,
        "kinds": ["evolver_consolidate_v1"],
    })
    if not job:
        return False
    job_id = job["job_id"]
    try:
        request_hash = job["payload"]["request_hash"]
        request = json.loads(client.object(request_hash).decode("utf-8"))
        response = evolver.consolidate_experience(request, store=True)
        client.json("POST", "/v1/consolidations", response)
        client.json("POST", f"/v1/learning/jobs/{job_id}:complete", {
            "worker": worker_id,
        })
    except Exception as error:
        client.json("POST", f"/v1/learning/jobs/{job_id}:fail", {
            "worker": worker_id,
            "error": str(error)[:2000],
        })
        raise
    return True


def run_worker(evolver, server_url: str, token: str, *, once: bool = False,
               poll_seconds: float = 5.0, worker_id: str | None = None) -> int:
    """Run the leased worker without ever opening Cerebellum's database."""
    worker = worker_id or f"evolver:{socket.gethostname()}:{uuid.uuid4()}"
    client = CerebellumClient(server_url, token)
    processed = 0
    while True:
        if process_once(evolver, client, worker):
            processed += 1
        elif once:
            return processed
        else:
            time.sleep(max(0.1, poll_seconds))
        if once:
            return processed
