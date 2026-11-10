from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import threading
from pathlib import Path, PurePosixPath

import zstandard

from .remote_client import BootstrapSession, RemoteWorkerClient, file_sha256
from .trainer import TrainingOutput, train_qlora, train_routed_qlora


class HeartbeatLoop:
    def __init__(self, client: RemoteWorkerClient) -> None:
        self.client = client
        self.stop = threading.Event()
        self.progress = "starting"
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._run, name="cerebellum-heartbeat", daemon=True)

    def __enter__(self) -> "HeartbeatLoop":
        self.client.heartbeat(self.progress)
        self.thread.start()
        return self

    def update(self, progress: str) -> None:
        self.progress = progress
        if self.error:
            raise RuntimeError(f"worker heartbeat failed: {self.error}") from self.error

    def _run(self) -> None:
        while not self.stop.wait(30):
            try:
                if self.client.heartbeat(self.progress):
                    raise RuntimeError("control plane requested cancellation")
            except BaseException as error:  # surfaced to the training thread
                self.error = error
                self.stop.set()

    def __exit__(self, *_: object) -> None:
        self.stop.set()
        self.thread.join(timeout=5)


def safe_extract_bundle(bundle: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle, mode="r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if (
                member.issym()
                or member.islnk()
                or member.isdev()
                or path.is_absolute()
                or ".." in path.parts
            ):
                raise RuntimeError("training bundle contains an unsafe tar member")
            if not member.isfile():
                raise RuntimeError("training bundle may contain only regular files")
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError("training bundle member could not be read")
            with source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)


def load_dataset_bundle(
    bundle: Path, session: BootstrapSession, destination: Path
) -> tuple[bytes | dict[str, bytes], dict]:
    if file_sha256(bundle) != session.bundle_hash:
        raise RuntimeError("training Bundle failed SHA-256 verification")
    safe_extract_bundle(bundle, destination)
    manifest_path = destination / "dataset-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != session.snapshot_manifest_hash:
        raise RuntimeError("dataset Manifest failed SHA-256 verification")
    manifest = json.loads(manifest_bytes)
    eligibility = manifest.get("eligibility")
    if (
        manifest.get("schema_version") != "cerebellum/v1"
        or manifest.get("kind") != "dataset_bundle_manifest_v1"
        or manifest.get("contains_raw_documents") is not False
        or not isinstance(eligibility, dict)
        or eligibility.get("passed") is not True
        or eligibility.get("contains_raw_documents") is not False
    ):
        raise RuntimeError("dataset Manifest failed safety or eligibility gates")
    if int(manifest.get("decision_count", 0)) < 5000 or int(
        manifest.get("replay_eval_count", 0)
    ) < 1000:
        raise RuntimeError("dataset Snapshot is below the formal training threshold")
    dataset = bytearray()
    for shard in manifest.get("shards", []):
        name = _base_shard_name(shard)
        value = _load_verified_shard(destination, name, shard)
        dataset.extend(value)
    if not dataset:
        raise RuntimeError("dataset Bundle contains no records")
    # The existing trainer consumes the common JSONL record envelope and selects
    # only train rows itself. Validation/holdout remain available for replay.
    manifest["dataset_hash"] = hashlib.sha256(dataset).hexdigest()
    if session.expert_plan is None:
        if session.manifest_hash != session.snapshot_manifest_hash:
            raise RuntimeError("dense run has mismatched dataset Manifest bindings")
        return bytes(dataset), manifest
    return _load_expert_dataset(destination, session, manifest)


def _base_shard_name(shard: object) -> str:
    if not isinstance(shard, dict):
        raise RuntimeError("dataset shard descriptor is invalid")
    split = shard.get("split")
    record_kind = shard.get("record_kind")
    if not isinstance(split, str) or not isinstance(record_kind, str):
        raise RuntimeError("dataset shard descriptor lacks split or record kind")
    return f"{split}.{record_kind}.jsonl.zst"


def _expert_shard_name(shard: object) -> str:
    if not isinstance(shard, dict):
        raise RuntimeError("expert shard descriptor is invalid")
    split = shard.get("split")
    purpose = shard.get("purpose")
    expert_id = shard.get("expert_id")
    record_kind = shard.get("record_kind")
    if purpose == "expert":
        if not isinstance(expert_id, str) or not expert_id:
            raise RuntimeError("expert shard lacks an expert id")
        purpose_name = f"expert-{expert_id}"
    elif purpose == "routing_negative":
        if expert_id is not None:
            raise RuntimeError("non-domain shard unexpectedly names an expert")
        purpose_name = "routing-negative"
    elif purpose in {"shared", "router"}:
        if expert_id is not None:
            raise RuntimeError("non-domain shard unexpectedly names an expert")
        purpose_name = purpose
    else:
        raise RuntimeError("expert shard purpose is unknown")
    if not isinstance(split, str) or not isinstance(record_kind, str):
        raise RuntimeError("expert shard descriptor lacks split or record kind")
    return f"experts/{split}.{purpose_name}.{record_kind}.jsonl.zst"


def _load_verified_shard(destination: Path, name: str, shard: object) -> bytes:
    if not isinstance(shard, dict):
        raise RuntimeError("dataset shard descriptor is invalid")
    path = destination / name
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != shard.get("object_hash"):
        raise RuntimeError(f"dataset shard {name} failed compressed hash verification")
    value = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(compressed)).read()
    if hashlib.sha256(value).hexdigest() != shard.get("uncompressed_hash"):
        raise RuntimeError(f"dataset shard {name} failed uncompressed hash verification")
    if value.count(b"\n") != int(shard.get("record_count", -1)):
        raise RuntimeError(f"dataset shard {name} record count differs from its Manifest")
    return value


def _load_expert_dataset(
    destination: Path, session: BootstrapSession, base_manifest: dict
) -> tuple[dict[str, bytes], dict]:
    plan = session.expert_plan
    if not isinstance(plan, dict):
        raise RuntimeError("expert plan is invalid")
    expert_manifest_bytes = (destination / "expert-dataset-manifest.json").read_bytes()
    if hashlib.sha256(expert_manifest_bytes).hexdigest() != session.manifest_hash:
        raise RuntimeError("expert dataset Manifest failed SHA-256 verification")
    expert_manifest = json.loads(expert_manifest_bytes)
    taxonomy = expert_manifest.get("taxonomy")
    readiness = expert_manifest.get("readiness")
    expert_ids = plan.get("expert_ids")
    fallback = plan.get("fallback_expert_id")
    train_router = plan.get("train_router") is True
    train_shared = plan.get("train_shared", True) is True
    if (
        expert_manifest.get("schema_version") != "cerebellum/v1"
        or expert_manifest.get("kind") != "expert_dataset_manifest_v1"
        or expert_manifest.get("contains_raw_documents") is not False
        or not isinstance(taxonomy, dict)
        or not isinstance(readiness, dict)
        or plan.get("architecture") != "routed_lora"
        or plan.get("router_top_k") != 1
        or taxonomy.get("router_top_k") != 1
        or taxonomy.get("fallback_expert_id") != fallback
        or not isinstance(expert_ids, list)
        or (not train_router and not train_shared and not expert_ids)
    ):
        raise RuntimeError("expert dataset failed routing or safety gates")
    taxonomy_bytes = json.dumps(taxonomy, sort_keys=True, separators=(",", ":")).encode()
    taxonomy_hash = hashlib.sha256(taxonomy_bytes).hexdigest()
    if taxonomy_hash != expert_manifest.get("taxonomy_hash"):
        raise RuntimeError("expert taxonomy failed canonical SHA-256 verification")
    known = {
        value.get("id")
        for value in taxonomy.get("experts", [])
        if isinstance(value, dict) and isinstance(value.get("id"), str)
    }
    if fallback not in known or any(value not in known or value == fallback for value in expert_ids):
        raise RuntimeError("expert plan references an unknown or fallback expert")
    minimum_router = int(readiness.get("minimum_router_records", 0))
    if train_router and int(readiness.get("router_train_records", 0)) < minimum_router:
        raise RuntimeError("expert router is below its frozen training threshold")
    per_expert = readiness.get("per_expert")
    if not isinstance(per_expert, dict):
        raise RuntimeError("expert readiness statistics are missing")
    for expert_id in expert_ids:
        stats = per_expert.get(expert_id)
        if not isinstance(stats, dict) or not isinstance(stats.get("records"), dict):
            raise RuntimeError(f"expert {expert_id} readiness statistics are missing")
        if int(stats["records"].get("train", 0)) < int(
            readiness.get("minimum_train_records_per_expert", 0)
        ) or int(stats.get("evaluation_replay_records", 0)) < int(
            readiness.get("minimum_replays_per_expert", 0)
        ):
            raise RuntimeError(f"expert {expert_id} is below its frozen training threshold")

    assignments = (destination / "expert-assignments.jsonl").read_bytes()
    if hashlib.sha256(assignments).hexdigest() != expert_manifest.get("assignments_hash"):
        raise RuntimeError("expert assignments failed SHA-256 verification")
    if assignments.count(b"\n") != int(expert_manifest.get("assignment_count", -1)):
        raise RuntimeError("expert assignment count differs from its Manifest")

    datasets: dict[str, bytearray] = {
        **({"router": bytearray()} if train_router else {}),
        **({str(fallback): bytearray()} if train_shared else {}),
        **{str(expert_id): bytearray() for expert_id in expert_ids},
    }
    actual_router_train = 0
    actual_expert_train = {str(expert_id): 0 for expert_id in expert_ids}
    actual_expert_evaluation_replays = {
        str(expert_id): 0 for expert_id in expert_ids
    }
    for shard in expert_manifest.get("shards", []):
        name = _expert_shard_name(shard)
        value = _load_verified_shard(destination, name, shard)
        purpose = shard.get("purpose")
        split = shard.get("split")
        record_kind = shard.get("record_kind")
        record_count = int(shard.get("record_count", 0))
        if purpose == "router" and split == "train":
            actual_router_train += record_count
        if purpose == "expert" and shard.get("expert_id") in actual_expert_train:
            expert_id = str(shard["expert_id"])
            if split == "train":
                actual_expert_train[expert_id] += record_count
            elif split in {"validation", "holdout"} and record_kind == "meta_replay":
                actual_expert_evaluation_replays[expert_id] += record_count
        if purpose in {"router", "routing_negative"} and train_router:
            datasets["router"].extend(value)
        elif purpose == "shared" and train_shared:
            datasets[str(fallback)].extend(value)
        elif purpose == "expert" and shard.get("expert_id") in datasets:
            datasets[str(shard["expert_id"])].extend(value)
    if any(not value for value in datasets.values()):
        raise RuntimeError("expert Bundle contains an empty required adapter dataset")
    if train_router and actual_router_train < minimum_router:
        raise RuntimeError("expert router shard counts are below the frozen threshold")
    for expert_id in expert_ids:
        expert_id = str(expert_id)
        if actual_expert_train[expert_id] < int(
            readiness.get("minimum_train_records_per_expert", 0)
        ) or actual_expert_evaluation_replays[expert_id] < int(
            readiness.get("minimum_replays_per_expert", 0)
        ):
            raise RuntimeError(
                f"expert {expert_id} shard counts do not contain enough train and independent replay evidence"
            )
    result = {key: bytes(value) for key, value in datasets.items()}
    base_manifest["routed_training"] = {
        "snapshot_id": session.snapshot_id,
        "base_model": session.base_model,
        "expert_plan": plan,
        "taxonomy_hash": taxonomy_hash,
        "expert_manifest_hash": session.manifest_hash,
    }
    return result, base_manifest


def resolve_base_model(session: BootstrapSession, download_dir: Path) -> str:
    expected = session.base_model
    declared = {
        "model_id": os.environ.get("META_BASE_MODEL_ID", ""),
        "revision": os.environ.get("META_BASE_MODEL_REVISION", ""),
        "sha256": os.environ.get("META_BASE_MODEL_SHA256", ""),
    }
    if declared != expected:
        raise RuntimeError("private application base-model pin differs from the TrainingRun")
    if os.environ.get("HF_TOKEN"):
        raise RuntimeError("HF_TOKEN must not be passed to an AutoDL TrainingRun")
    model_path = os.environ.get("META_BASE_MODEL_PATH", "").strip()
    if model_path:
        resolved = Path(model_path)
    else:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as error:
            raise RuntimeError(
                "pinned huggingface-hub is required for a public base model"
            ) from error
        resolved = Path(
            snapshot_download(
                repo_id=expected["model_id"],
                revision=expected["revision"],
                local_dir=download_dir,
                token=False,
            )
        )
    if tree_sha256(resolved) != expected["sha256"]:
        raise RuntimeError("base model failed its deterministic tree hash")
    return str(resolved)


def tree_sha256(root: Path) -> str:
    if not root.is_dir():
        raise RuntimeError("META_BASE_MODEL_PATH is not a directory")
    digest = hashlib.sha256()
    # Platform-stable ordering: Path sorting is casefolded on Windows and
    # case-sensitive on POSIX, which would make the digest platform-dependent.
    # Pin the Windows normcase order (the order all sealed pins were computed
    # with) so the same tree hashes identically on every platform.
    paths = sorted(
        (
            item
            for item in root.rglob("*")
            if item.is_file()
            and ".cache" not in item.relative_to(root).parts
            and not item.name.endswith(".lock")
        ),
        key=lambda item: item.relative_to(root).as_posix().replace("/", "\\").lower(),
    )
    if not paths:
        raise RuntimeError("base-model directory contains no hashable files")
    for path in paths:
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def redact(message: str, bootstrap_code: str) -> str:
    result = message.replace(bootstrap_code, "[REDACTED]")
    for name in ("AUTODL_API_TOKEN", "CEREBELLUM_AUTH_TOKEN"):
        value = os.environ.get(name, "")
        if value:
            result = result.replace(value, "[REDACTED]")
    return result[:2000]


def configure_qlora(qlora: dict) -> None:
    mapping = {
        "epochs": "CEREBELLUM_RUN_EPOCHS",
        "max_sequence_length": "CEREBELLUM_RUN_MAX_LENGTH",
        "lora_rank": "CEREBELLUM_RUN_LORA_RANK",
        "lora_alpha": "CEREBELLUM_RUN_LORA_ALPHA",
        "lora_dropout": "CEREBELLUM_RUN_LORA_DROPOUT",
        "learning_rate": "CEREBELLUM_RUN_LEARNING_RATE",
        "gradient_accumulation_steps": "CEREBELLUM_RUN_GRADIENT_ACCUMULATION",
    }
    if set(qlora) != set(mapping):
        raise RuntimeError("TrainingRun QLoRA configuration is incomplete or unknown")
    for key, environment in mapping.items():
        os.environ[environment] = str(qlora[key])


def shutdown_instance() -> None:
    if os.environ.get("CEREBELLUM_SKIP_SHUTDOWN_FOR_TESTS") == "1":
        return
    subprocess.run(["/usr/bin/shutdown", "now"], check=False, timeout=30)


def run(
    gateway: str,
    run_id: str,
    bootstrap_code: str,
    trainer=train_qlora,
    routed_trainer=train_routed_qlora,
) -> None:
    client = RemoteWorkerClient(gateway, run_id)
    reported_terminal = False
    try:
        session = client.bootstrap(bootstrap_code)
        if session.run_id != run_id:
            raise RuntimeError("bootstrap response is scoped to another TrainingRun")
        configure_qlora(session.qlora)
        with tempfile.TemporaryDirectory(prefix="cerebellum-autodl-") as temporary:
            work = Path(temporary)
            base_model_path = resolve_base_model(session, work / "base-model")
            bundle = work / "dataset.bundle.tar"
            with HeartbeatLoop(client) as heartbeat:
                heartbeat.update("downloading")
                client.download_bundle(bundle, session.bundle_hash)
                heartbeat.update("validating")
                dataset, manifest = load_dataset_bundle(bundle, session, work / "dataset")
                heartbeat.update("training")
                selected_trainer = routed_trainer if session.expert_plan else trainer
                output: TrainingOutput = selected_trainer(
                    dataset, manifest, base_model_path, work / "output"
                )
                adapter = work / "adapter.zip"
                adapter.write_bytes(output.artifact)
                metrics = work / "metrics.json"
                metrics.write_text(
                    json.dumps(output.metrics, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                logs = work / "worker-log.json"
                logs.write_text(
                    json.dumps(
                        {
                            "schema_version": "cerebellum/v1",
                            "run_id": run_id,
                            "provider_instance_id": session.provider_instance_id,
                            "status": "trained",
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                heartbeat.update("uploading")
                client.heartbeat("uploading")
                artifact_hash = client.upload_artifact("adapter", adapter)
                client.upload_artifact("metrics", metrics)
                client.upload_artifact("logs", logs)
                heartbeat.update("completing")
                client.complete(
                    required_env("META_MODEL_ID"),
                    required_env("META_MODEL_VERSION"),
                    artifact_hash,
                    output.metrics,
                )
                reported_terminal = True
    except Exception as error:
        if not reported_terminal:
            try:
                client.fail(redact(str(error), bootstrap_code))
                reported_terminal = True
            except Exception:
                pass
        raise
    finally:
        shutdown_instance()


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required private-application setting is missing: {name}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Cerebellum AutoDL scoped QLoRA worker")
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bootstrap-code", required=True)
    args = parser.parse_args()
    run(args.gateway, args.run_id, args.bootstrap_code)


def hash_model_main() -> None:
    parser = argparse.ArgumentParser(description="Hash a pinned base-model directory")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(tree_sha256(args.path))


if __name__ == "__main__":
    main()
