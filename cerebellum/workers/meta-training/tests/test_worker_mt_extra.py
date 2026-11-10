from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

from cerebellum_meta_training import worker
from cerebellum_meta_training.trainer import TrainingOutput
from cerebellum_meta_training.worker import (
    MAX_ADAPTER_BYTES,
    iso_now,
    main,
    process_one,
    redact,
    required_env,
    validate_inputs,
)

MODULE = "cerebellum_meta_training.worker"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fixture() -> tuple[dict, bytes, bytes]:
    dataset = (
        json.dumps(
            {
                "kind": "meta_decision",
                "split": "train",
                "record": {
                    "task_kind": "relevance",
                    "input": {"query": "agent"},
                    "output": {"relevant": True},
                },
            }
        ).encode()
        + b"\n"
    )
    manifest = {
        "schema_version": "cerebellum/v1",
        "kind": "meta_training_manifest_v1",
        "dataset_hash": sha(dataset),
        "decision_count": 5000,
        "replay_eval_count": 1000,
        "contains_raw_documents": False,
    }
    manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode()
    candidate = {
        "candidate_id": str(uuid.uuid4()),
        "dataset_hash": sha(dataset),
        "manifest_hash": sha(manifest_bytes),
        "decision_count": 5000,
        "replay_eval_count": 1000,
    }
    job = {
        "job_id": str(uuid.uuid4()),
        "payload": {
            "candidate": candidate,
            "base_model": "test/model-1b",
            "data_license_policy": "licensed-only",
            "declared_gpu_memory_gb": 24,
        },
    }
    return job, dataset, manifest_bytes


VALID_ENV = {
    "META_BASE_MODEL": "test/model-1b",
    "META_DATA_LICENSE_POLICY": "licensed-only",
    "META_MODEL_ID": "meta-controller",
    "META_MODEL_VERSION": "1.0.0",
}


class RecordingClient:
    def __init__(self, job: dict | None, dataset: bytes, manifest: bytes) -> None:
        self.job = job
        self.objects: dict[str, bytes] = {}
        if job is not None:
            candidate = job["payload"]["candidate"]
            self.objects[candidate["dataset_hash"]] = dataset
            self.objects[candidate["manifest_hash"]] = manifest
        self.calls: list[str] = []
        self.submitted: list[dict] = []
        self.completed: list[str] = []
        self.failed: list[str] = []
        self.result: dict | None = None

    def claim(self, worker_id: str) -> dict | None:
        self.calls.append("claim")
        value, self.job = self.job, None
        return value

    def get_result(self, job_id: str) -> dict | None:
        self.calls.append("get_result")
        return self.result

    def get_object(self, value: str) -> bytes:
        return self.objects[value]

    def submit_result(self, value: dict) -> dict:
        self.calls.append("submit")
        self.submitted.append(value)
        return value["bundle"]

    def complete(self, job_id: str, worker_id: str) -> None:
        self.calls.append("complete")
        self.completed.append(job_id)

    def fail(self, job_id: str, worker_id: str, message: str) -> None:
        self.calls.append("fail")
        self.failed.append(message)


def fake_trainer(artifact: bytes = b"adapter"):
    def trainer_fn(dataset: bytes, manifest: dict, base_model: str, output: Path) -> TrainingOutput:
        return TrainingOutput(artifact, {"policy_violations": 0})

    return trainer_fn


class RequiredEnvTests(unittest.TestCase):
    def test_missing_and_blank_values_are_rejected(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "META_BASE_MODEL"):
                required_env("META_BASE_MODEL")
        with mock.patch.dict(os.environ, {"META_BASE_MODEL": "   "}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "META_BASE_MODEL"):
                required_env("META_BASE_MODEL")

    def test_value_is_stripped(self) -> None:
        with mock.patch.dict(os.environ, {"X": "  value  "}, clear=True):
            self.assertEqual(required_env("X"), "value")


class IsoNowTests(unittest.TestCase):
    def test_timestamp_is_utc_zulu(self) -> None:
        value = iso_now()
        self.assertTrue(value.endswith("Z"))
        self.assertNotIn("+00:00", value)


class RedactTests(unittest.TestCase):
    def test_tokens_are_redacted_and_message_truncated(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"CEREBELLUM_TOKEN": "control-secret", "HF_TOKEN": "hf-secret"},
            clear=True,
        ):
            value = redact("failure control-secret hf-secret " + "x" * 5000)
        self.assertNotIn("control-secret", value)
        self.assertNotIn("hf-secret", value)
        self.assertEqual(value.count("[REDACTED]"), 2)
        self.assertLessEqual(len(value), 2000)

    def test_unset_tokens_leave_message_unchanged(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(redact("plain failure"), "plain failure")


class ValidateInputsTests(unittest.TestCase):
    def validate(self, payload: dict, dataset: bytes, manifest: bytes, env: dict | None = None) -> dict:
        with mock.patch.dict(os.environ, env or VALID_ENV, clear=True):
            return validate_inputs(payload, dataset, manifest)

    def test_missing_candidate_is_rejected(self) -> None:
        job, dataset, manifest = fixture()
        job["payload"].pop("candidate")
        with self.assertRaisesRegex(RuntimeError, "immutable candidate"):
            self.validate(job["payload"], dataset, manifest)

    def test_invalid_manifest_json_is_rejected(self) -> None:
        job, dataset, _ = fixture()
        broken = b"not-json"
        job["payload"]["candidate"]["manifest_hash"] = sha(broken)
        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            self.validate(job["payload"], dataset, broken)

    def test_schema_version_tampering_is_rejected(self) -> None:
        job, dataset, manifest = fixture()
        value = json.loads(manifest)
        value["schema_version"] = "cerebellum/v2"
        tampered = json.dumps(value).encode()
        job["payload"]["candidate"]["manifest_hash"] = sha(tampered)
        with self.assertRaisesRegex(RuntimeError, "does not match the candidate"):
            self.validate(job["payload"], dataset, tampered)

    def test_decision_count_tampering_is_rejected(self) -> None:
        job, dataset, manifest = fixture()
        value = json.loads(manifest)
        value["decision_count"] = 1
        tampered = json.dumps(value).encode()
        job["payload"]["candidate"]["manifest_hash"] = sha(tampered)
        with self.assertRaisesRegex(RuntimeError, "does not match the candidate"):
            self.validate(job["payload"], dataset, tampered)

    def test_unlicensed_data_policy_is_rejected(self) -> None:
        job, dataset, manifest = fixture()
        job["payload"]["data_license_policy"] = "any"
        with self.assertRaisesRegex(RuntimeError, "licensed-only data"):
            self.validate(job["payload"], dataset, manifest)

    def test_undersized_gpu_declaration_is_rejected(self) -> None:
        job, dataset, manifest = fixture()
        job["payload"]["declared_gpu_memory_gb"] = 16
        with self.assertRaisesRegex(RuntimeError, "24 GiB GPU"):
            self.validate(job["payload"], dataset, manifest)

    def test_worker_license_environment_must_match(self) -> None:
        job, dataset, manifest = fixture()
        env = {**VALID_ENV, "META_DATA_LICENSE_POLICY": "any"}
        with self.assertRaisesRegex(RuntimeError, "worker does not enforce licensed-only"):
            self.validate(job["payload"], dataset, manifest, env)

    def test_worker_base_model_must_match_job(self) -> None:
        job, dataset, manifest = fixture()
        env = {**VALID_ENV, "META_BASE_MODEL": "other/model"}
        with self.assertRaisesRegex(RuntimeError, "base model differs"):
            self.validate(job["payload"], dataset, manifest, env)

    def test_valid_inputs_return_manifest(self) -> None:
        job, dataset, manifest = fixture()
        value = self.validate(job["payload"], dataset, manifest)
        self.assertEqual(value["kind"], "meta_training_manifest_v1")
        self.assertEqual(value["dataset_hash"], sha(dataset))


class ProcessOneTests(unittest.TestCase):
    def test_no_claimed_job_returns_false(self) -> None:
        client = RecordingClient(None, b"", b"")
        self.assertFalse(process_one(client, "worker-a"))
        self.assertEqual(client.calls, ["claim"])

    def test_completed_result_skips_retraining(self) -> None:
        job, dataset, manifest = fixture()
        client = RecordingClient(job, dataset, manifest)
        client.result = {"status": "candidate"}
        with mock.patch.dict(os.environ, VALID_ENV, clear=True):
            self.assertTrue(process_one(client, "worker-a", fake_trainer()))
        self.assertEqual(client.calls, ["claim", "get_result", "complete"])
        self.assertEqual(client.submitted, [])
        self.assertEqual(client.failed, [])

    def test_submit_precedes_complete_and_bundle_is_candidate(self) -> None:
        job, dataset, manifest = fixture()
        client = RecordingClient(job, dataset, manifest)
        with mock.patch.dict(os.environ, VALID_ENV, clear=True):
            self.assertTrue(process_one(client, "worker-a", fake_trainer()))
        self.assertEqual(client.calls, ["claim", "get_result", "submit", "complete"])
        bundle = client.submitted[0]["bundle"]
        self.assertEqual(bundle["status"], "candidate")
        self.assertIsNone(bundle["previous_active"])
        self.assertIsNone(bundle["canary_started_at"])
        self.assertEqual(bundle["canary_decisions"], 0)
        self.assertEqual(bundle["artifact_hash"], sha(b"adapter"))
        self.assertEqual(bundle["model_id"], "meta-controller")
        self.assertEqual(bundle["version"], "1.0.0")
        self.assertEqual(bundle["base_model"], "test/model-1b")
        import base64

        self.assertEqual(
            base64.b64decode(client.submitted[0]["artifact_base64"]), b"adapter"
        )

    def test_trainer_failure_fails_job_with_redacted_message(self) -> None:
        job, dataset, manifest = fixture()
        client = RecordingClient(job, dataset, manifest)

        def broken_trainer(dataset, manifest, base_model, output):
            raise RuntimeError("cuda blew up control-secret")

        env = {**VALID_ENV, "CEREBELLUM_TOKEN": "control-secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(process_one(client, "worker-a", broken_trainer))
        self.assertEqual(client.calls, ["claim", "get_result", "fail"])
        self.assertEqual(client.completed, [])
        self.assertEqual(len(client.failed), 1)
        self.assertNotIn("control-secret", client.failed[0])
        self.assertIn("[REDACTED]", client.failed[0])

    def test_empty_artifact_is_rejected(self) -> None:
        job, dataset, manifest = fixture()
        client = RecordingClient(job, dataset, manifest)
        with mock.patch.dict(os.environ, VALID_ENV, clear=True):
            process_one(client, "worker-a", fake_trainer(b""))
        self.assertIn("empty or exceeds 512 MiB", client.failed[0])
        self.assertEqual(client.submitted, [])

    def test_oversized_artifact_is_rejected(self) -> None:
        job, dataset, manifest = fixture()
        client = RecordingClient(job, dataset, manifest)
        with mock.patch.dict(os.environ, VALID_ENV, clear=True), mock.patch(
            f"{MODULE}.MAX_ADAPTER_BYTES", 4
        ):
            process_one(client, "worker-a", fake_trainer(b"adapter"))
        self.assertIn("empty or exceeds 512 MiB", client.failed[0])
        self.assertEqual(client.submitted, [])

    def test_artifact_size_limit_is_512_mib(self) -> None:
        self.assertEqual(MAX_ADAPTER_BYTES, 512 * 1024 * 1024)


class StopLoop(Exception):
    pass


class MainTests(unittest.TestCase):
    def test_requires_explicit_enable(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            sys, "argv", ["worker", "--once"]
        ):
            with self.assertRaisesRegex(RuntimeError, "META_TRAINER_ENABLED=1"):
                main()

    def test_once_processes_a_single_job(self) -> None:
        env = {
            "META_TRAINER_ENABLED": "1",
            "META_BASE_MODEL": "test/model-1b",
            "META_MODEL_ID": "meta-controller",
            "META_MODEL_VERSION": "1.0.0",
            "WORKER_ID": "worker-a",
            "CEREBELLUM_URL": "https://control.example",
            "CEREBELLUM_TOKEN": "token",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            sys, "argv", ["worker", "--once"]
        ), mock.patch(f"{MODULE}.ControlPlaneClient") as client_cls, mock.patch(
            f"{MODULE}.process_one", return_value=True
        ) as process:
            main()
        client_cls.assert_called_once_with("https://control.example", "token")
        process.assert_called_once_with(client_cls.return_value, "worker-a")

    def test_poll_sleep_is_clamped_to_bounds(self) -> None:
        env = {
            "META_TRAINER_ENABLED": "1",
            "META_BASE_MODEL": "test/model-1b",
            "META_MODEL_ID": "meta-controller",
            "META_MODEL_VERSION": "1.0.0",
            "WORKER_ID": "worker-a",
            "CEREBELLUM_URL": "https://control.example",
            "CEREBELLUM_TOKEN": "token",
        }
        for argv_seconds, expected in (("10000", 300.0), ("0", 1.0)):
            with self.subTest(argv_seconds=argv_seconds):
                with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                    sys, "argv", ["worker", "--poll-seconds", argv_seconds]
                ), mock.patch(f"{MODULE}.ControlPlaneClient"), mock.patch(
                    f"{MODULE}.process_one", return_value=False
                ), mock.patch(f"{MODULE}.time.sleep", side_effect=StopLoop) as sleep:
                    with self.assertRaises(StopLoop):
                        main()
                sleep.assert_called_once_with(expected)


if __name__ == "__main__":
    unittest.main()
