from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from . import UPSTREAM_COMMIT
from .client import ControlPlaneClient
from .driver import required_env, run_optimization, sha256_file


def process_one(client: ControlPlaneClient, worker_id: str) -> bool:
    job = client.claim(worker_id, lease_seconds=21_600)
    if job is None:
        return False
    payload = job["payload"]
    job_id = job["job_id"]
    try:
        with tempfile.TemporaryDirectory(prefix="cerebellum-skillopt-") as temporary:
            data_root = Path(temporary)
            materialize_job(client, payload, data_root)
            write_worker_manifest(payload, data_root)
            result = run_optimization(data_root, payload)
            client.submit_result(payload["run_id"], result)
        client.complete(job_id, worker_id)
    except Exception as error:  # keep failure evidence, but never echo the hosted secret.
        message = redact(str(error), os.environ.get("API_KEY", ""))
        try:
            client.submit_result(payload["run_id"], failure_result(payload, worker_id, message))
            client.complete(job_id, worker_id)
        except Exception:
            client.fail(job_id, worker_id, message)
    return True


def materialize_job(client: ControlPlaneClient, payload: dict, root: Path) -> None:
    objects = {
        "baseline.md": payload["baseline_skill"]["content_hash"],
        "manifest.json": payload["benchmark_manifest_hash"],
        "benchmark.zip": payload["benchmark_bundle_hash"],
    }
    for name, expected_hash in objects.items():
        content = client.get_object(expected_hash)
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise RuntimeError(f"CAS object failed integrity verification: {name}")
        (root / name).write_bytes(content)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("container_image") != payload["container_image_digest"]:
        raise RuntimeError("benchmark manifest image differs from immutable run")


def write_worker_manifest(payload: dict, root: Path) -> None:
    source_hash_file = required_env("SKILLOPT_SOURCE_ARCHIVE_SHA256_FILE")
    registration_patch = required_env("CEREBELLUM_REGISTRATION_PATCH")
    manifest = {
        "upstream_repository": "https://github.com/microsoft/SkillOpt",
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_source_archive_sha256": Path(source_hash_file)
        .read_text(encoding="utf-8")
        .strip()
        .split()[0],
        "registration_patch_sha256": sha256_file(registration_patch),
        "container_image_digest": payload["container_image_digest"],
        "target_model": payload["target_model"],
        "optimizer_model": payload["optimizer_model"],
        "budget": payload["budget"],
    }
    (root / "worker-run-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def redact(message: str, secret: str) -> str:
    return message.replace(secret, "[REDACTED]") if secret else message


def failure_result(payload: dict, worker_id: str, message: str) -> dict:
    source_hash = (
        Path(required_env("SKILLOPT_SOURCE_ARCHIVE_SHA256_FILE"))
        .read_text(encoding="utf-8")
        .strip()
        .split()[0]
    )
    return {
        "schema_version": "cerebellum/v1",
        "run_id": payload["run_id"],
        "worker": worker_id,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_source_archive_sha256": source_hash,
        "registration_patch_sha256": sha256_file(required_env("CEREBELLUM_REGISTRATION_PATCH")),
        "patches": [],
        "evaluations": [],
        "holdout": None,
        "best_patch_id": None,
        "stopped_reason": f"failed closed: {message[:1000]}",
        "target_calls": 0,
        "optimizer_calls": 0,
        "total_tokens": 0,
        "elapsed_seconds": 0,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pinned SkillOpt reference worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()
    required_env("OPENAI_COMPATIBLE_BASE_URL")
    required_env("API_KEY")
    required_env("TARGET_MODEL")
    required_env("OPTIMIZER_MODEL")
    worker_id = required_env("WORKER_ID")
    client = ControlPlaneClient(required_env("CEREBELLUM_URL"), required_env("CEREBELLUM_TOKEN"))
    while True:
        processed = process_one(client, worker_id)
        if args.once:
            return
        if not processed:
            time.sleep(min(max(args.poll_seconds, 0.2), 30.0))


if __name__ == "__main__":
    main()
