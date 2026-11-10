from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import zstandard
except ImportError:  # dependency is installed in the pinned AutoDL application
    zstandard = None


@unittest.skipUnless(zstandard is not None, "zstandard contract dependency is not installed")
class RemoteWorkerContractTests(unittest.TestCase):
    def _bundle(self, root: Path):
        from cerebellum_meta_training.remote_client import BootstrapSession

        decision = json.dumps(
            {
                "kind": "meta_decision",
                "split": "train",
                "record": {
                    "task_kind": "relevance",
                    "input": {"query": "agent"},
                    "output": {"relevant": True},
                },
            },
            separators=(",", ":"),
        ).encode() + b"\n"
        replay = json.dumps(
            {
                "kind": "meta_replay",
                "split": "holdout",
                "record": {
                    "task_id": "task",
                    "baseline_score": 0.0,
                    "candidate_score": 1.0,
                },
            },
            separators=(",", ":"),
        ).encode() + b"\n"
        values = {
            "train.meta_decision.jsonl.zst": decision * 5000,
            "holdout.meta_replay.jsonl.zst": replay * 1000,
        }
        shards = []
        compressed = {}
        for name, value in values.items():
            encoded = zstandard.ZstdCompressor(level=9).compress(value)
            compressed[name] = encoded
            split, record_kind, *_ = name.split(".")
            shards.append(
                {
                    "split": split,
                    "record_kind": record_kind,
                    "object_hash": hashlib.sha256(encoded).hexdigest(),
                    "uncompressed_hash": hashlib.sha256(value).hexdigest(),
                    "record_count": value.count(b"\n"),
                    "compressed_bytes": len(encoded),
                }
            )
        manifest = {
            "schema_version": "cerebellum/v1",
            "kind": "dataset_bundle_manifest_v1",
            "dataset_kind": "meta-controller",
            "decision_count": 5000,
            "replay_eval_count": 1000,
            "contains_raw_documents": False,
            "eligibility": {"passed": True, "contains_raw_documents": False},
            "shards": shards,
        }
        manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode()
        entries = {**compressed, "dataset-manifest.json": manifest_bytes}
        bundle = root / "bundle.tar"
        with tarfile.open(bundle, "w") as archive:
            for name in sorted(entries):
                value = entries[name]
                info = tarfile.TarInfo(name)
                info.size = len(value)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(value))
        session = BootstrapSession(
            run_id="run",
            snapshot_id="00000000-0000-0000-0000-000000000001",
            provider_instance_id="pro-test",
            bundle_hash=hashlib.sha256(bundle.read_bytes()).hexdigest(),
            manifest_hash=hashlib.sha256(manifest_bytes).hexdigest(),
            snapshot_manifest_hash=hashlib.sha256(manifest_bytes).hexdigest(),
            base_model={
                "model_id": "example/model",
                "revision": "revision",
                "sha256": "0" * 64,
            },
            qlora={},
        )
        return bundle, session

    def _routed_bundle(self, root: Path, *, independent_replays: bool = True):
        from cerebellum_meta_training.remote_client import BootstrapSession

        decision = json.dumps(
            {
                "kind": "meta_decision",
                "split": "train",
                "record": {
                    "task_kind": "relevance",
                    "input": {"query": "agent"},
                    "output": {"relevant": True},
                },
            },
            separators=(",", ":"),
        ).encode() + b"\n"
        replay = json.dumps(
            {
                "kind": "meta_replay",
                "split": "train",
                "record": {
                    "task_id": "retrieval-task",
                    "source_domain": "example.test",
                    "topic_family": "retrieval",
                    "baseline_score": 0.0,
                    "candidate_score": 1.0,
                    "fact_correct": True,
                    "safety_passed": True,
                },
            },
            separators=(",", ":"),
        ).encode() + b"\n"
        route = json.dumps(
            {
                "kind": "expert_route",
                "split": "train",
                "record": {
                    "record_hash": "1" * 64,
                    "record_kind": "meta_decision",
                    "task_kind": "relevance",
                    "source_domain": "example.test",
                    "topic_family": "retrieval",
                    "target_expert_id": "retrieval",
                    "secondary_expert_ids": [],
                    "confidence": 0.9,
                    "status": "assigned",
                    "reason_codes": ["task_kind_mapping"],
                },
            },
            separators=(",", ":"),
        ).encode() + b"\n"
        negative = route.replace(b'"assigned"', b'"out_of_distribution"').replace(
            b'"retrieval"', b'"shared"', 1
        )
        expert_replay_name = (
            "experts/holdout.expert-retrieval.meta_replay.jsonl.zst"
            if independent_replays
            else "experts/train.expert-retrieval.meta_replay.jsonl.zst"
        )
        expert_replay = (
            replay.replace(b'"train"', b'"holdout"', 1)
            if independent_replays
            else replay
        )
        values = {
            "train.meta_decision.jsonl.zst": decision * 5000,
            "holdout.meta_replay.jsonl.zst": replay.replace(
                b'"train"', b'"holdout"', 1
            )
            * 1000,
            "experts/train.router.expert_route.jsonl.zst": route * 5000,
            "experts/train.routing-negative.expert_route.jsonl.zst": negative * 10,
            "experts/train.shared.meta_decision.jsonl.zst": decision * 5000,
            "experts/train.expert-retrieval.meta_decision.jsonl.zst": decision * 1000,
            expert_replay_name: expert_replay * 200,
        }
        compressed = {
            name: zstandard.ZstdCompressor(level=9).compress(value)
            for name, value in values.items()
        }

        def descriptor(name: str, *, purpose: str | None = None, expert_id=None):
            value = values[name]
            result = {
                "split": name.split("/")[-1].split(".")[0],
                "record_kind": name.split(".")[-3 if name.endswith(".jsonl.zst") else -1],
                "object_hash": hashlib.sha256(compressed[name]).hexdigest(),
                "uncompressed_hash": hashlib.sha256(value).hexdigest(),
                "record_count": value.count(b"\n"),
                "compressed_bytes": len(compressed[name]),
            }
            if purpose is not None:
                result["purpose"] = purpose
                result["expert_id"] = expert_id
                result["record_kind"] = name.split(".")[-3]
            return result

        base_shards = [
            descriptor("train.meta_decision.jsonl.zst"),
            descriptor("holdout.meta_replay.jsonl.zst"),
        ]
        taxonomy = {
            "schema_version": "cerebellum/v1",
            "taxonomy_id": "cerebellum-meta-experts",
            "version": "1.0.0",
            "experts": [
                {
                    "id": "retrieval",
                    "description": "retrieval",
                    "task_kinds": ["relevance"],
                    "is_fallback": False,
                },
                {
                    "id": "shared",
                    "description": "fallback",
                    "task_kinds": [],
                    "is_fallback": True,
                },
            ],
            "fallback_expert_id": "shared",
            "router_top_k": 1,
            "policy_version": "request-routed-lora-v1",
        }
        taxonomy_hash = hashlib.sha256(
            json.dumps(taxonomy, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        expert_shards = [
            descriptor(
                "experts/train.router.expert_route.jsonl.zst", purpose="router"
            ),
            descriptor(
                "experts/train.routing-negative.expert_route.jsonl.zst",
                purpose="routing_negative",
            ),
            descriptor(
                "experts/train.shared.meta_decision.jsonl.zst", purpose="shared"
            ),
            descriptor(
                "experts/train.expert-retrieval.meta_decision.jsonl.zst",
                purpose="expert",
                expert_id="retrieval",
            ),
            descriptor(expert_replay_name, purpose="expert", expert_id="retrieval"),
        ]
        assignments = b'{"record_hash":"' + b"1" * 64 + b'"}\n'
        expert_manifest = {
            "schema_version": "cerebellum/v1",
            "kind": "expert_dataset_manifest_v1",
            "policy_version": "request-routed-lora-v1",
            "taxonomy": taxonomy,
            "taxonomy_hash": taxonomy_hash,
            "assignments_hash": hashlib.sha256(assignments).hexdigest(),
            "assignment_count": 1,
            "ambiguous_count": 0,
            "out_of_distribution_count": 10,
            "negative_transfer_count": 0,
            "readiness": {
                "ready": True,
                "minimum_router_records": 5000,
                "minimum_train_records_per_expert": 1000,
                "minimum_replays_per_expert": 200,
                "router_train_records": 5000,
                "per_expert": {
                    "retrieval": {
                        "records": {"train": 1000, "validation": 0, "holdout": 200},
                        "decision_records": 1000,
                        "replay_records": 200,
                        "evaluation_replay_records": 200,
                    }
                },
                "reasons": [],
            },
            "shards": expert_shards,
            "contains_raw_documents": False,
        }
        expert_bytes = json.dumps(expert_manifest, separators=(",", ":")).encode()
        base_manifest = {
            "schema_version": "cerebellum/v1",
            "kind": "dataset_bundle_manifest_v1",
            "dataset_kind": "meta-controller",
            "decision_count": 5000,
            "replay_eval_count": 1000,
            "contains_raw_documents": False,
            "eligibility": {"passed": True, "contains_raw_documents": False},
            "shards": base_shards,
        }
        base_bytes = json.dumps(base_manifest, separators=(",", ":")).encode()
        entries = {
            **compressed,
            "dataset-manifest.json": base_bytes,
            "expert-dataset-manifest.json": expert_bytes,
            "expert-assignments.jsonl": assignments,
        }
        bundle = root / "routed-bundle.tar"
        with tarfile.open(bundle, "w") as archive:
            for name in sorted(entries):
                value = entries[name]
                info = tarfile.TarInfo(name)
                info.size = len(value)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(value))
        session = BootstrapSession(
            run_id="run",
            snapshot_id="00000000-0000-0000-0000-000000000001",
            provider_instance_id="pro-test",
            bundle_hash=hashlib.sha256(bundle.read_bytes()).hexdigest(),
            manifest_hash=hashlib.sha256(expert_bytes).hexdigest(),
            snapshot_manifest_hash=hashlib.sha256(base_bytes).hexdigest(),
            base_model={
                "model_id": "example/model",
                "revision": "revision",
                "sha256": "0" * 64,
            },
            qlora={},
            expert_plan={
                "architecture": "routed_lora",
                "expert_view_id": "00000000-0000-0000-0000-000000000002",
                "train_router": True,
                "train_shared": True,
                "expert_ids": ["retrieval"],
                "router_top_k": 1,
                "fallback_expert_id": "shared",
            },
        )
        return bundle, session

    def test_bundle_verifies_every_shard_and_training_threshold(self) -> None:
        from cerebellum_meta_training.remote_worker import load_dataset_bundle

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, session = self._bundle(root)
            dataset, manifest = load_dataset_bundle(bundle, session, root / "extract")
            self.assertEqual(dataset.count(b"\n"), 6000)
            self.assertFalse(manifest["contains_raw_documents"])

    def test_routed_bundle_verifies_router_shared_domain_and_negative_shards(self) -> None:
        from cerebellum_meta_training.remote_worker import load_dataset_bundle

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, session = self._routed_bundle(root)
            datasets, manifest = load_dataset_bundle(bundle, session, root / "extract")
            self.assertEqual(set(datasets), {"router", "shared", "retrieval"})
            self.assertEqual(datasets["router"].count(b"\n"), 5010)
            self.assertEqual(datasets["retrieval"].count(b"\n"), 1200)
            self.assertEqual(
                manifest["routed_training"]["expert_manifest_hash"],
                session.manifest_hash,
            )

    def test_routed_bundle_does_not_trust_forged_independent_replay_statistics(self) -> None:
        from cerebellum_meta_training.remote_worker import load_dataset_bundle

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, session = self._routed_bundle(root, independent_replays=False)
            with self.assertRaisesRegex(RuntimeError, "independent replay evidence"):
                load_dataset_bundle(bundle, session, root / "extract")

    def test_tar_path_traversal_is_rejected(self) -> None:
        from cerebellum_meta_training.remote_worker import safe_extract_bundle

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bad.tar"
            with tarfile.open(bundle, "w") as archive:
                value = b"bad"
                info = tarfile.TarInfo("../escape")
                info.size = len(value)
                archive.addfile(info, io.BytesIO(value))
            with self.assertRaises(RuntimeError):
                safe_extract_bundle(bundle, root / "extract")
            self.assertFalse((root / "escape").exists())

    def test_base_model_tree_hash_and_secret_redaction_are_deterministic(self) -> None:
        from cerebellum_meta_training.remote_worker import redact, tree_sha256

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b").write_bytes(b"b")
            (root / "a").write_bytes(b"a")
            self.assertEqual(tree_sha256(root), tree_sha256(root))
        with mock.patch.dict(
            os.environ,
            {"AUTODL_API_TOKEN": "autodl-secret", "CEREBELLUM_AUTH_TOKEN": "root-secret"},
            clear=True,
        ):
            value = redact("boot autodl-secret root-secret", "boot")
        self.assertNotIn("boot", value)
        self.assertNotIn("autodl-secret", value)
        self.assertNotIn("root-secret", value)

    def test_tree_hash_order_is_platform_stable(self) -> None:
        # Case-mixed names: POSIX sorts uppercase-first, Windows casefolds.
        # The pinned key must reproduce the Windows normcase order everywhere
        # (sealed base-model pins were computed in that order).
        import hashlib

        from cerebellum_meta_training.remote_worker import tree_sha256

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "LICENSE").write_bytes(b"l")
            (root / "config.json").write_bytes(b"c")
            (root / "README.md").write_bytes(b"r")
            actual = tree_sha256(root)
        digest = hashlib.sha256()
        for name, content in (("config.json", b"c"), ("LICENSE", b"l"), ("README.md", b"r")):
            encoded = name.encode()
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
            digest.update(content)
        self.assertEqual(actual, digest.hexdigest())

    def test_finally_shutdown_uses_fixed_argv_without_shell(self) -> None:
        from cerebellum_meta_training.remote_worker import shutdown_instance

        with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
            "subprocess.run"
        ) as run:
            shutdown_instance()
        run.assert_called_once_with(
            ["/usr/bin/shutdown", "now"], check=False, timeout=30
        )


if __name__ == "__main__":
    unittest.main()
