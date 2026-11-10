from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_skillopt import UPSTREAM_COMMIT
from cerebellum_skillopt.driver import sha256_file
from cerebellum_skillopt.worker import (
    failure_result,
    main,
    materialize_job,
    process_one,
    redact,
    write_worker_manifest,
)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fixture() -> tuple[dict, dict[str, bytes]]:
    baseline = b"# baseline skill\n"
    manifest = json.dumps({"container_image": "sha256:pinned@1"}).encode()
    bundle = b"benchmark-zip-bytes"
    payload = {
        "run_id": "run-1",
        "baseline_skill": {"content_hash": sha(baseline)},
        "benchmark_manifest_hash": sha(manifest),
        "benchmark_bundle_hash": sha(bundle),
        "container_image_digest": "sha256:pinned@1",
        "target_model": "target-model",
        "optimizer_model": "optimizer-model",
        "budget": {"episodes": 1},
    }
    objects = {
        sha(baseline): baseline,
        sha(manifest): manifest,
        sha(bundle): bundle,
    }
    return payload, objects


class FakeClient:
    def __init__(self, job: dict | None, objects: dict[str, bytes] | None = None) -> None:
        self.job = job
        self.objects = objects or {}
        self.claimed: list[tuple] = []
        self.submitted: list[tuple] = []
        self.completed: list[str] = []
        self.failed: list[tuple] = []
        self.submit_error: Exception | None = None

    def claim(self, worker: str, lease_seconds: int = 0) -> dict | None:
        self.claimed.append((worker, lease_seconds))
        job, self.job = self.job, None
        return job

    def get_object(self, digest: str) -> bytes:
        return self.objects[digest]

    def submit_result(self, run_id: str, result: dict) -> dict:
        if self.submit_error is not None:
            raise self.submit_error
        self.submitted.append((run_id, result))
        return {"result_hash": "0" * 64}

    def complete(self, job_id: str, worker: str) -> None:
        self.completed.append(job_id)

    def fail(self, job_id: str, worker: str, message: str) -> None:
        self.failed.append((job_id, message))


class EnvMixin:
    """Point the worker-manifest env vars at real temp files."""

    def worker_env(self, directory: str) -> dict:
        source_hash_file = Path(directory) / "source.sha256"
        source_hash_file.write_text("ab" * 32 + "  skillopt.tar.gz\n", encoding="utf-8")
        patch_file = Path(directory) / "registration.patch"
        patch_file.write_text("patch-bytes", encoding="utf-8")
        return {
            "SKILLOPT_SOURCE_ARCHIVE_SHA256_FILE": str(source_hash_file),
            "CEREBELLUM_REGISTRATION_PATCH": str(patch_file),
        }


class ProcessOneTests(EnvMixin, unittest.TestCase):
    def run_job(
        self,
        client: FakeClient,
        env: dict,
        run_result: dict | None = None,
        run_error: Exception | None = None,
    ) -> bool:
        runner = mock.Mock()
        if run_error is not None:
            runner.side_effect = run_error
        else:
            runner.return_value = run_result if run_result is not None else {"patches": []}
        with (
            mock.patch.dict(os.environ, env),
            mock.patch("cerebellum_skillopt.worker.run_optimization", runner),
        ):
            return process_one(client, "worker-a")

    def test_no_job_returns_false_and_claims_with_long_lease(self) -> None:
        client = FakeClient(None)
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(self.run_job(client, self.worker_env(directory)))
        self.assertEqual(client.claimed, [("worker-a", 21_600)])
        self.assertFalse(client.submitted)
        self.assertFalse(client.completed)
        self.assertFalse(client.failed)

    def test_success_submits_result_and_completes(self) -> None:
        payload, objects = fixture()
        job = {"job_id": "job-1", "payload": payload}
        client = FakeClient(job, objects)
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(
                self.run_job(client, self.worker_env(directory), run_result={"patches": [1]})
            )
        self.assertEqual(client.submitted, [("run-1", {"patches": [1]})])
        self.assertEqual(client.completed, ["job-1"])
        self.assertFalse(client.failed)

    def test_hash_mismatch_fails_closed_with_evidence(self) -> None:
        payload, objects = fixture()
        objects[payload["benchmark_bundle_hash"]] = b"tampered"
        job = {"job_id": "job-1", "payload": payload}
        client = FakeClient(job, objects)
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(self.run_job(client, self.worker_env(directory)))
        self.assertEqual(len(client.submitted), 1)
        run_id, result = client.submitted[0]
        self.assertEqual(run_id, "run-1")
        self.assertEqual(result["schema_version"], "cerebellum/v1")
        self.assertTrue(result["stopped_reason"].startswith("failed closed: "))
        self.assertIn("integrity verification", result["stopped_reason"])
        self.assertEqual(result["patches"], [])
        self.assertEqual(result["target_calls"], 0)
        # A failure with preserved evidence still completes the job (no retry).
        self.assertEqual(client.completed, ["job-1"])
        self.assertFalse(client.failed)

    def test_manifest_image_mismatch_fails_closed(self) -> None:
        payload, objects = fixture()
        manifest = json.dumps({"container_image": "sha256:other@2"}).encode()
        del objects[payload["benchmark_manifest_hash"]]
        objects[sha(manifest)] = manifest
        payload["benchmark_manifest_hash"] = sha(manifest)
        job = {"job_id": "job-1", "payload": payload}
        client = FakeClient(job, objects)
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(self.run_job(client, self.worker_env(directory)))
        _, result = client.submitted[0]
        self.assertIn("image differs", result["stopped_reason"])
        self.assertEqual(client.completed, ["job-1"])

    def test_failure_redacts_the_hosted_api_key(self) -> None:
        payload, objects = fixture()
        job = {"job_id": "job-1", "payload": payload}
        client = FakeClient(job, objects)
        with tempfile.TemporaryDirectory() as directory:
            env = self.worker_env(directory) | {"API_KEY": "sk-hosted-secret"}
            self.assertTrue(
                self.run_job(
                    client, env, run_error=RuntimeError("call failed for sk-hosted-secret")
                )
            )
        _, result = client.submitted[0]
        self.assertIn("[REDACTED]", result["stopped_reason"])
        self.assertNotIn("sk-hosted-secret", result["stopped_reason"])

    def test_dead_letter_when_failure_result_cannot_be_submitted(self) -> None:
        payload, objects = fixture()
        job = {"job_id": "job-1", "payload": payload}
        client = FakeClient(job, objects)
        client.submit_error = RuntimeError("control plane down")
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(
                self.run_job(
                    client, self.worker_env(directory), run_error=RuntimeError("boom")
                )
            )
        self.assertFalse(client.submitted)
        self.assertFalse(client.completed)
        self.assertEqual(len(client.failed), 1)
        job_id, message = client.failed[0]
        self.assertEqual(job_id, "job-1")
        self.assertIn("boom", message)


class MaterializeJobTests(unittest.TestCase):
    def test_writes_all_objects_and_verifies_hashes(self) -> None:
        payload, objects = fixture()
        client = FakeClient(None, objects)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materialize_job(client, payload, root)
            self.assertEqual(
                (root / "baseline.md").read_bytes(),
                objects[payload["baseline_skill"]["content_hash"]],
            )
            self.assertEqual(
                (root / "benchmark.zip").read_bytes(),
                objects[payload["benchmark_bundle_hash"]],
            )
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["container_image"], "sha256:pinned@1")


class WorkerManifestTests(EnvMixin, unittest.TestCase):
    def test_manifest_records_pinned_provenance(self) -> None:
        payload, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            env = self.worker_env(directory)
            with mock.patch.dict(os.environ, env):
                root = Path(directory) / "run"
                root.mkdir()
                write_worker_manifest(payload, root)
            manifest = json.loads(
                (root / "worker-run-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["upstream_commit"], UPSTREAM_COMMIT)
            self.assertEqual(manifest["upstream_source_archive_sha256"], "ab" * 32)
            self.assertEqual(
                manifest["registration_patch_sha256"],
                sha256_file(env["CEREBELLUM_REGISTRATION_PATCH"]),
            )
            self.assertEqual(manifest["container_image_digest"], "sha256:pinned@1")
            self.assertEqual(manifest["target_model"], "target-model")

    def test_failure_result_is_zeroed_and_pinned(self) -> None:
        payload, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            env = self.worker_env(directory)
            with mock.patch.dict(os.environ, env):
                result = failure_result(payload, "worker-a", "something broke")
        self.assertEqual(result["schema_version"], "cerebellum/v1")
        self.assertEqual(result["run_id"], "run-1")
        self.assertEqual(result["worker"], "worker-a")
        self.assertEqual(result["upstream_commit"], UPSTREAM_COMMIT)
        self.assertEqual(result["upstream_source_archive_sha256"], "ab" * 32)
        self.assertEqual(result["stopped_reason"], "failed closed: something broke")
        self.assertEqual(result["patches"], [])
        self.assertEqual(result["evaluations"], [])
        self.assertIsNone(result["holdout"])
        self.assertIsNone(result["best_patch_id"])
        self.assertEqual(result["target_calls"], 0)
        self.assertEqual(result["optimizer_calls"], 0)
        self.assertEqual(result["total_tokens"], 0)
        self.assertTrue(result["created_at"].endswith("Z"))


class RedactTests(unittest.TestCase):
    def test_redact_only_replaces_a_non_empty_secret(self) -> None:
        self.assertEqual(redact("plain message", ""), "plain message")
        self.assertEqual(redact("a SECRET b SECRET", "SECRET"), "a [REDACTED] b [REDACTED]")

class MainTests(unittest.TestCase):
    ENV = {
        "OPENAI_COMPATIBLE_BASE_URL": "https://api.test/v1",
        "API_KEY": "sk-test",
        "TARGET_MODEL": "target-model",
        "OPTIMIZER_MODEL": "optimizer-model",
        "WORKER_ID": "worker-a",
        "CEREBELLUM_URL": "https://cp.test/",
        "CEREBELLUM_TOKEN": "token",
    }

    def test_once_processes_a_single_job_and_returns(self) -> None:
        seen = []
        with (
            mock.patch.dict(os.environ, self.ENV),
            mock.patch.object(sys, "argv", ["worker", "--once"]),
            mock.patch(
                "cerebellum_skillopt.worker.process_one",
                side_effect=lambda client, worker: seen.append(worker) or True,
            ),
            mock.patch("urllib.request.urlopen") as urlopen,
        ):
            main()
        self.assertEqual(seen, ["worker-a"])
        urlopen.assert_not_called()

    def test_idle_loop_sleeps_with_clamped_poll_interval(self) -> None:
        with (
            mock.patch.dict(os.environ, self.ENV),
            mock.patch.object(sys, "argv", ["worker", "--poll-seconds", "0.01"]),
            mock.patch(
                "cerebellum_skillopt.worker.process_one",
                side_effect=[False, False, SystemExit],
            ),
            mock.patch("cerebellum_skillopt.worker.time.sleep") as sleep,
        ):
            with self.assertRaises(SystemExit):
                main()
        # Two idle iterations, each clamped up to the 0.2s floor; never real sleep.
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.2, 0.2])


if __name__ == "__main__":
    unittest.main()
