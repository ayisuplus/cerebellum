from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .client import ControlPlaneClient
from .trainer import TrainingOutput, train_qlora

SCHEMA_VERSION = "cerebellum/v1"
MAX_ADAPTER_BYTES = 512 * 1024 * 1024


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def redact(message: str) -> str:
    result = message
    for name in ("CEREBELLUM_TOKEN", "HF_TOKEN"):
        value = os.environ.get(name, "")
        if value:
            result = result.replace(value, "[REDACTED]")
    return result[:2000]


def validate_inputs(payload: dict, dataset: bytes, manifest_bytes: bytes) -> dict:
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict):
        raise RuntimeError("training job lacks an immutable candidate")
    if digest(dataset) != candidate.get("dataset_hash"):
        raise RuntimeError("dataset failed CAS integrity verification")
    if digest(manifest_bytes) != candidate.get("manifest_hash"):
        raise RuntimeError("manifest failed CAS integrity verification")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise RuntimeError("training manifest is invalid JSON") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("kind") != "meta_training_manifest_v1"
        or manifest.get("dataset_hash") != candidate.get("dataset_hash")
        or manifest.get("contains_raw_documents") is not False
        or int(manifest.get("decision_count", -1)) != int(candidate.get("decision_count", -2))
        or int(manifest.get("replay_eval_count", -1))
        != int(candidate.get("replay_eval_count", -2))
    ):
        raise RuntimeError("training manifest does not match the candidate or contains raw text")
    if payload.get("data_license_policy") != "licensed-only":
        raise RuntimeError("training job does not enforce licensed-only data")
    if int(payload.get("declared_gpu_memory_gb", 0)) < 24:
        raise RuntimeError("training job does not declare a 24 GiB GPU")
    if os.environ.get("META_DATA_LICENSE_POLICY") != "licensed-only":
        raise RuntimeError("worker does not enforce licensed-only data")
    if os.environ.get("META_BASE_MODEL") != payload.get("base_model"):
        raise RuntimeError("worker base model differs from the immutable job")
    return manifest


def process_one(
    client: ControlPlaneClient,
    worker_id: str,
    trainer: Callable[[bytes, dict, str, Path], TrainingOutput] = train_qlora,
) -> bool:
    job = client.claim(worker_id)
    if job is None:
        return False
    job_id = job["job_id"]
    try:
        if client.get_result(job_id) is not None:
            client.complete(job_id, worker_id)
            return True
        payload = job["payload"]
        candidate = payload["candidate"]
        dataset = client.get_object(candidate["dataset_hash"])
        manifest_bytes = client.get_object(candidate["manifest_hash"])
        manifest = validate_inputs(payload, dataset, manifest_bytes)
        with tempfile.TemporaryDirectory(prefix="cerebellum-meta-training-") as temporary:
            output = trainer(dataset, manifest, payload["base_model"], Path(temporary))
        if not output.artifact or len(output.artifact) > MAX_ADAPTER_BYTES:
            raise RuntimeError("QLoRA adapter Bundle is empty or exceeds 512 MiB")
        now = iso_now()
        bundle = {
            "schema_version": SCHEMA_VERSION,
            "model_id": required_env("META_MODEL_ID"),
            "version": required_env("META_MODEL_VERSION"),
            "artifact_hash": digest(output.artifact),
            "base_model": payload["base_model"],
            "training_candidate_id": candidate["candidate_id"],
            "trainer": worker_id,
            "metrics": output.metrics,
            "status": "candidate",
            "previous_active": None,
            "canary_started_at": None,
            "canary_decisions": 0,
            "created_at": now,
            "updated_at": now,
        }
        client.submit_result(
            {
                "job_id": job_id,
                "worker": worker_id,
                "bundle": bundle,
                "artifact_base64": base64.b64encode(output.artifact).decode("ascii"),
            }
        )
        client.complete(job_id, worker_id)
    except Exception as error:
        client.fail(job_id, worker_id, redact(str(error)))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Cerebellum v3 QLoRA meta-training worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if os.environ.get("META_TRAINER_ENABLED") != "1":
        raise RuntimeError("META_TRAINER_ENABLED=1 is required")
    required_env("META_BASE_MODEL")
    required_env("META_MODEL_ID")
    required_env("META_MODEL_VERSION")
    worker_id = required_env("WORKER_ID")
    client = ControlPlaneClient(
        required_env("CEREBELLUM_URL"), required_env("CEREBELLUM_TOKEN")
    )
    while True:
        processed = process_one(client, worker_id)
        if args.once:
            return
        if not processed:
            time.sleep(min(max(args.poll_seconds, 1.0), 300.0))


if __name__ == "__main__":
    main()
