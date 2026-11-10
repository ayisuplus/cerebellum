from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    from skillopt.datasets.base import BatchSpec, SplitDataLoader
    from skillopt.envs.base import EnvAdapter
except ImportError:  # lets safety/unit tests run without downloading upstream.
    @dataclass(slots=True)
    class BatchSpec:  # type: ignore[no-redef]
        phase: str
        split: str
        seed: int
        batch_size: int
        payload: object | None = None
        metadata: dict = field(default_factory=dict)

    class SplitDataLoader:  # type: ignore[no-redef]
        pass

    class EnvAdapter:  # type: ignore[no-redef]
        def setup(self, cfg: dict) -> None:
            self._cfg = dict(cfg)

from .harness import DockerTaskHarness, OpenAICompatibleAgent


class EarlyStopRequested(RuntimeError):
    """Raised between steps after two objective non-improving candidates."""


class CerebellumVerifyDataLoader(SplitDataLoader):
    """Manifest-backed loader using SkillOpt's public SplitDataLoader boundary."""

    def __init__(self, tasks: list[dict]) -> None:
        self._by_split = {
            split: [dict(task) for task in tasks if task["split"] == split]
            for split in ("train", "validation", "holdout")
        }
        self.train_items = self._by_split["train"]

    def setup(self, cfg: dict) -> None:
        self._cfg = dict(cfg)

    def load_split_items(self, split_path: str) -> list[dict]:
        split = Path(split_path).name
        return list(self._by_split[normalize_split(split)])

    def build_train_batch(self, batch_size: int, seed: int, **_: object) -> BatchSpec:
        rng = random.Random(seed)
        items = list(self._by_split["train"])
        rng.shuffle(items)
        selected = items[:batch_size]
        return BatchSpec("train", "train", seed, len(selected), selected)

    def build_eval_batch(self, env_num: int, split: str, seed: int, **_: object) -> BatchSpec:
        normalized = normalize_split(split)
        items = list(self._by_split[normalized])[:env_num]
        return BatchSpec("eval", normalized, seed, len(items), items)

    def get_train_size(self) -> int:
        return len(self._by_split["train"])

    def make_base_seeds(
        self, steps_per_epoch: int, accumulation: int, seed: int, **_: object
    ) -> list[int]:
        return [seed + index + 1 for index in range(steps_per_epoch * accumulation)]

    def plan_train_epoch(
        self,
        *,
        epoch: int,
        steps_per_epoch: int,
        accumulation: int,
        batch_size: int,
        seed: int,
        **_: object,
    ) -> list[BatchSpec]:
        items = list(self._by_split["train"])
        rng = random.Random(seed + epoch * 1000)
        rng.shuffle(items)
        batches = []
        for index in range(steps_per_epoch * accumulation):
            start = index * batch_size
            selected = items[start : start + batch_size]
            batches.append(BatchSpec("train", "train", seed + epoch * 1000 + index, len(selected), selected))
        return batches


class CerebellumVerifyAdapter(EnvAdapter):
    """Objective Docker rollout adapter for the 60-task Cerebellum benchmark."""

    def __init__(
        self,
        data_root: str,
        container_image: str = "",
        analyst_workers: int = 1,
        minibatch_size: int = 10,
        edit_budget: int = 2,
        failure_only: bool = False,
    ) -> None:
        root = Path(data_root)
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.container_image = container_image or self.manifest["container_image"]
        self.aggregate = (root / "benchmark.zip").read_bytes()
        self.dataloader = CerebellumVerifyDataLoader(self.manifest["tasks"])
        self.harness = DockerTaskHarness(self.aggregate, self.manifest, self.container_image)
        self.analyst_workers = min(max(int(analyst_workers), 1), 4)
        self.minibatch_size = min(max(int(minibatch_size), 1), 10)
        self.edit_budget = min(max(int(edit_budget), 1), 2)
        self.failure_only = bool(failure_only)
        self.ledger_path = root / "adapter-ledger.jsonl"
        self.agent: OpenAICompatibleAgent | None = None
        self.rollout_calls = 0
        self._validation_baseline: dict[str, dict] | None = None
        self._validated_skill_hashes: set[str] = set()
        self._consecutive_no_improvement = 0
        self.stop_requested = False
        self.target_call_limit = 240
        self.deadline = float("inf")

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.dataloader.setup(cfg)
        base_url = required_env("OPENAI_COMPATIBLE_BASE_URL")
        api_key = required_env("API_KEY")
        target_model = required_env("TARGET_MODEL")
        optimizer_model = required_env("OPTIMIZER_MODEL")
        if cfg.get("target_model") != target_model or cfg.get("optimizer_model") != optimizer_model:
            raise RuntimeError("run models must exactly match explicit environment model roles")
        # SkillOpt reads its provider-specific name; Cerebellum accepts API_KEY
        # at the process boundary and maps it without persisting the value.
        os.environ["OPENAI_COMPATIBLE_API_KEY"] = api_key
        os.environ["OPENAI_COMPATIBLE_MODEL"] = target_model
        self.target_call_limit = int(cfg.get("target_call_limit", 240))
        self.deadline = time.monotonic() + int(cfg.get("wall_time_seconds", 21_600))
        self.agent = OpenAICompatibleAgent(
            base_url, api_key, target_model, int(cfg.get("total_token_limit", 2_000_000))
        )

    def get_dataloader(self) -> CerebellumVerifyDataLoader:
        return self.dataloader

    def requires_ray(self) -> bool:
        return False

    def build_env_from_batch(self, batch: BatchSpec, **_: object) -> list[dict]:
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs: object) -> list[dict]:
        return list(self.dataloader.build_train_batch(batch_size, seed, **kwargs).payload or [])

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs: object) -> list[dict]:
        return list(self.dataloader.build_eval_batch(env_num, split, seed, **kwargs).payload or [])

    def rollout(
        self,
        env_manager: list[dict],
        skill_content: str,
        out_dir: str,
        **kwargs: object,
    ) -> list[dict]:
        if self.agent is None:
            raise RuntimeError("adapter.setup() must run before rollout")
        if self.stop_requested and env_manager and env_manager[0].get("split") == "train":
            raise EarlyStopRequested("two consecutive candidates had no objective validation gain")
        seed = int(kwargs.get("seed", 0) or 0)
        results = []
        for offset, item in enumerate(env_manager):
            if self.rollout_calls >= self.target_call_limit:
                raise RuntimeError("target rollout budget exhausted")
            if time.monotonic() >= self.deadline:
                raise RuntimeError("optimization wall-clock budget exhausted")
            self.rollout_calls += 1
            result = self.harness.run(item["task_id"], skill_content, self.agent, seed + offset)
            if self.agent.usage.tokens > int(self._cfg.get("total_token_limit", 2_000_000)):
                raise RuntimeError("target token budget exhausted")
            result["split"] = item["split"]
            result["skill_hash"] = hashlib.sha256(skill_content.encode()).hexdigest()
            result["skill_content"] = skill_content
            prediction = Path(out_dir) / "predictions" / item["task_id"]
            prediction.mkdir(parents=True, exist_ok=True)
            (prediction / "conversation.json").write_text(
                json.dumps(result["trajectory"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with self.ledger_path.open("a", encoding="utf-8") as ledger:
                ledger.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
            results.append({key: value for key, value in result.items() if key != "skill_content"})
        if env_manager and env_manager[0].get("split") == "validation":
            skill_hash = hashlib.sha256(skill_content.encode()).hexdigest()
            by_id = {row["id"]: row for row in results}
            if self._validation_baseline is None:
                self._validation_baseline = by_id
                self._validated_skill_hashes.add(skill_hash)
            elif skill_hash not in self._validated_skill_hashes:
                self._validated_skill_hashes.add(skill_hash)
                improved = objective_gate(self._validation_baseline, by_id)
                self._consecutive_no_improvement = 0 if improved else self._consecutive_no_improvement + 1
                if self._consecutive_no_improvement >= 2:
                    self.stop_requested = True
        return results

    def get_task_types(self) -> list[str]:
        return sorted({task["template_family"] for task in self.manifest["tasks"]})


def normalize_split(split: str) -> str:
    aliases = {
        "train": "train",
        "val": "validation",
        "valid": "validation",
        "validation": "validation",
        "valid_seen": "validation",
        "test": "holdout",
        "holdout": "holdout",
        "valid_unseen": "holdout",
    }
    try:
        return aliases[split]
    except KeyError as error:
        raise ValueError(f"unknown benchmark split: {split}") from error


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required and has no default")
    return value


def objective_gate(baseline: dict[str, dict], candidate: dict[str, dict]) -> bool:
    if set(baseline) != set(candidate) or not baseline:
        return False
    pairs = [(baseline[key], candidate[key]) for key in baseline]
    if any(right.get("safety_violation") for _, right in pairs):
        return False
    if any(float(right["hard"]) < float(left["hard"]) for left, right in pairs):
        return False
    baseline_hard = sum(float(left["hard"]) for left, _ in pairs) / len(pairs)
    candidate_hard = sum(float(right["hard"]) for _, right in pairs) / len(pairs)
    baseline_soft = sum(float(left["soft"]) for left, _ in pairs) / len(pairs)
    candidate_soft = sum(float(right["soft"]) for _, right in pairs) / len(pairs)
    return candidate_hard > baseline_hard or (
        abs(candidate_hard - baseline_hard) <= 1e-12 and candidate_soft >= baseline_soft + 0.02
    )
