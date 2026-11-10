from __future__ import annotations

import hashlib
import json
import os
import tempfile
import tarfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from cerebellum_meta_training.trainer import (
    TrainingOutput,
    _deterministic_zip,
    train_routed_qlora,
    verify_gpu,
)
from cerebellum_meta_training.worker import process_one, validate_inputs


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


class FakeClient:
    def __init__(self, job: dict, dataset: bytes, manifest: bytes) -> None:
        self.job = job
        self.objects = {
            job["payload"]["candidate"]["dataset_hash"]: dataset,
            job["payload"]["candidate"]["manifest_hash"]: manifest,
        }
        self.submitted: list[dict] = []
        self.completed: list[str] = []
        self.failed: list[str] = []

    def claim(self, worker: str) -> dict | None:
        value, self.job = self.job, None
        return value

    def get_result(self, job_id: str) -> dict | None:
        return None

    def get_object(self, value: str) -> bytes:
        return self.objects[value]

    def submit_result(self, value: dict) -> dict:
        self.submitted.append(value)
        return value["bundle"]

    def complete(self, job_id: str, worker: str) -> None:
        self.completed.append(job_id)

    def fail(self, job_id: str, worker: str, message: str) -> None:
        self.failed.append(message)


class MetaTrainingWorkerTests(unittest.TestCase):
    def test_manifest_rejects_raw_documents_and_hash_tampering(self) -> None:
        job, dataset, manifest = fixture()
        environment = {
            "META_BASE_MODEL": "test/model-1b",
            "META_DATA_LICENSE_POLICY": "licensed-only",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            validate_inputs(job["payload"], dataset, manifest)
            value = json.loads(manifest)
            value["contains_raw_documents"] = True
            unsafe = json.dumps(value).encode()
            job["payload"]["candidate"]["manifest_hash"] = sha(unsafe)
            with self.assertRaises(RuntimeError):
                validate_inputs(job["payload"], dataset, unsafe)
            with self.assertRaises(RuntimeError):
                validate_inputs(job["payload"], dataset + b"tamper", manifest)

    def test_worker_submits_candidate_but_never_activates_it(self) -> None:
        job, dataset, manifest = fixture()
        original_job_id = job["job_id"]
        client = FakeClient(job, dataset, manifest)
        metrics = {
            "old_task_retention": 0.0,
            "ndcg_at_10": 0.0,
            "baseline_ndcg_at_10": 0.0,
            "max_core_topic_regression": 0.0,
            "fact_precision_delta": 0.0,
            "policy_violations": 0,
            "injection_regression": False,
            "cost_per_useful_card_change": 0.0,
        }

        def fake_trainer(dataset: bytes, manifest: dict, base_model: str, output: Path) -> TrainingOutput:
            return TrainingOutput(b"adapter", metrics)

        environment = {
            "META_BASE_MODEL": "test/model-1b",
            "META_DATA_LICENSE_POLICY": "licensed-only",
            "META_MODEL_ID": "meta-controller",
            "META_MODEL_VERSION": "1.0.0",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            self.assertTrue(process_one(client, "worker-a", fake_trainer))
        self.assertFalse(client.failed)
        self.assertEqual(client.completed, [original_job_id])
        self.assertEqual(client.submitted[0]["bundle"]["status"], "candidate")
        self.assertEqual(client.submitted[0]["bundle"]["trainer"], "worker-a")

    def test_gpu_gate_fails_closed_before_training(self) -> None:
        with mock.patch.dict(os.environ, {"META_TRAINER_ENABLED": "0"}, clear=True):
            with self.assertRaises(RuntimeError):
                verify_gpu()

    def test_adapter_archive_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.txt").write_text("b", encoding="utf-8")
            (root / "a.txt").write_text("a", encoding="utf-8")
            first = _deterministic_zip(root)
            second = _deterministic_zip(root)
            self.assertEqual(first, second)

    def test_routed_training_packages_independent_adapter_hashes(self) -> None:
        record = (
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
        route = (
            json.dumps(
                {
                    "kind": "expert_route",
                    "split": "train",
                    "record": {
                        "target_expert_id": "retrieval",
                        "status": "assigned",
                    },
                }
            ).encode()
            + b"\n"
        )
        datasets = {"router": route, "shared": record, "retrieval": record}
        manifest = {
            "routed_training": {
                "snapshot_id": "00000000-0000-0000-0000-000000000001",
                "taxonomy_hash": "a" * 64,
                "base_model": {
                    "model_id": "example/model",
                    "revision": "revision",
                    "sha256": "b" * 64,
                },
                "expert_plan": {
                    "architecture": "routed_lora",
                    "expert_view_id": "00000000-0000-0000-0000-000000000002",
                    "train_router": True,
                    "train_shared": True,
                    "expert_ids": ["retrieval"],
                    "router_top_k": 1,
                    "fallback_expert_id": "shared",
                },
            }
        }

        def fake_train(dataset, role_manifest, base_model, output):
            role = os.environ["CEREBELLUM_ADAPTER_ROLE"]
            return TrainingOutput(
                artifact=f"adapter:{role}".encode(),
                metrics={"policy_violations": 0},
            )

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "cerebellum_meta_training.trainer.train_qlora", side_effect=fake_train
        ):
            output = train_routed_qlora(
                datasets, manifest, "example/model", Path(directory)
            )
            archive_path = Path(directory) / "routed.tar"
            archive_path.write_bytes(output.artifact)
            with tarfile.open(archive_path, "r:") as archive:
                names = set(archive.getnames())
                routed = json.load(
                    archive.extractfile("cerebellum-routed-adapter-manifest.json")
                )
        self.assertEqual(
            names,
            {
                "adapters/router.zip",
                "adapters/shared.zip",
                "adapters/retrieval.zip",
                "cerebellum-routed-adapter-manifest.json",
            },
        )
        self.assertEqual(routed["router"]["expert_id"], "router")
        self.assertEqual(
            {item["expert_id"] for item in routed["experts"]},
            {"shared", "retrieval"},
        )

    def test_one_expert_can_be_retrained_without_router_or_shared(self) -> None:
        record = (
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
            "routed_training": {
                "snapshot_id": "00000000-0000-0000-0000-000000000001",
                "taxonomy_hash": "a" * 64,
                "base_model": {
                    "model_id": "example/model",
                    "revision": "revision",
                    "sha256": "b" * 64,
                },
                "expert_plan": {
                    "architecture": "routed_lora",
                    "expert_view_id": "00000000-0000-0000-0000-000000000002",
                    "train_router": False,
                    "train_shared": False,
                    "expert_ids": ["retrieval"],
                    "router_top_k": 1,
                    "fallback_expert_id": "shared",
                },
            }
        }

        def fake_train(dataset, role_manifest, base_model, output):
            return TrainingOutput(
                artifact=f"adapter:{os.environ['CEREBELLUM_ADAPTER_ROLE']}".encode(),
                metrics={"policy_violations": 0},
            )

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "cerebellum_meta_training.trainer.train_qlora", side_effect=fake_train
        ):
            root = Path(directory)
            output = train_routed_qlora(
                {"retrieval": record}, manifest, "example/model", root
            )
            bundle = root / "single.tar"
            bundle.write_bytes(output.artifact)
            with tarfile.open(bundle, "r:") as archive:
                self.assertEqual(
                    set(archive.getnames()),
                    {
                        "adapters/retrieval.zip",
                        "cerebellum-routed-adapter-manifest.json",
                    },
                )
                routed = json.load(
                    archive.extractfile("cerebellum-routed-adapter-manifest.json")
                )
        self.assertIsNone(routed["router"])
        self.assertEqual([item["expert_id"] for item in routed["experts"]], ["retrieval"])


if __name__ == "__main__":
    unittest.main()
