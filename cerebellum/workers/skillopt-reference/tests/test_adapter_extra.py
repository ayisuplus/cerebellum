from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
import importlib
import sys

import pytest

from cerebellum_skillopt import adapter as adapter_module
from cerebellum_skillopt.adapter import (
    BatchSpec,
    CerebellumVerifyAdapter,
    CerebellumVerifyDataLoader,
    normalize_split,
    objective_gate,
    required_env,
)
from cerebellum_skillopt.harness import DockerTaskHarness, OpenAICompatibleAgent

IMAGE = "python@sha256:" + "a" * 64

class ConcreteAdapter(CerebellumVerifyAdapter):
    """The installed skillopt EnvAdapter declares an abstract `reflect` the
    pinned upstream revision does not; satisfy it for instantiation."""

    def reflect(self, *args, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def settable_train_items(monkeypatch):
    # The installed skillopt SplitDataLoader makes train_items a read-only
    # property; the pinned upstream allows the adapter's assignment.
    from skillopt.datasets.base import SplitDataLoader

    monkeypatch.delattr(SplitDataLoader, "train_items", raising=False)


def make_task(task_id: str, split: str, family: str = "fix") -> dict:
    return {
        "task_id": task_id,
        "split": split,
        "template_family": family,
        "bundle_hash": "0" * 64,
        "expected_status": "completed",
    }


def sample_tasks() -> list[dict]:
    return (
        [make_task(f"train-{i}", "train") for i in range(6)]
        + [make_task(f"val-{i}", "validation") for i in range(4)]
        + [make_task(f"hold-{i}", "holdout", family="harden") for i in range(3)]
    )


def make_data_root(tmp_path: Path, tasks: list[dict] | None = None) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    manifest = {"container_image": IMAGE, "tasks": tasks or sample_tasks()}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "benchmark.zip").write_bytes(b"aggregate-bytes")
    return root


def make_adapter(tmp_path: Path, **kwargs) -> CerebellumVerifyAdapter:
    root = make_data_root(tmp_path)
    return ConcreteAdapter(str(root), IMAGE, **kwargs)


def setup_env(monkeypatch, cfg: dict | None = None) -> dict:
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "http://fake.local/v1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("TARGET_MODEL", "target-m")
    monkeypatch.setenv("OPTIMIZER_MODEL", "optimizer-m")
    return {
        "target_model": "target-m",
        "optimizer_model": "optimizer-m",
        "target_call_limit": 10,
        "wall_time_seconds": 3600,
        "total_token_limit": 100,
        **(cfg or {}),
    }


class StubHarness:
    def __init__(self, hard_by_skill: dict[str, float] | None = None):
        self.hard_by_skill = hard_by_skill or {}
        self.calls: list[tuple] = []

    def run(self, task_id, skill, agent, seed):
        self.calls.append((task_id, seed))
        return {
            "id": task_id,
            "hard": self.hard_by_skill.get(skill, 0.5),
            "soft": 0.5,
            "safety_violation": False,
            "trajectory": [{"turn": 0}],
            "declared_status": "completed",
        }


class TestFallbackShims:
    def test_batch_and_env_shims_used_without_skillopt(self):
        saved = {key: value for key, value in sys.modules.items() if key.startswith("skillopt")}
        for key in saved:
            del sys.modules[key]
        sys.modules["skillopt"] = None  # makes `import skillopt...` raise ImportError
        try:
            reloaded = importlib.reload(adapter_module)
            spec = reloaded.BatchSpec("train", "train", 1, 2, ["x"])
            assert spec.phase == "train"
            assert spec.payload == ["x"]
            assert spec.metadata == {}
            env = reloaded.EnvAdapter()
            env.setup({"a": 1})
            assert env._cfg == {"a": 1}
            loader = reloaded.CerebellumVerifyDataLoader([])
            assert loader.train_items == []
        finally:
            del sys.modules["skillopt"]
            sys.modules.update(saved)
            importlib.reload(adapter_module)


class TestNormalizeSplit:
    def test_aliases(self):
        assert normalize_split("train") == "train"
        assert normalize_split("val") == "validation"
        assert normalize_split("valid") == "validation"
        assert normalize_split("validation") == "validation"
        assert normalize_split("valid_seen") == "validation"
        assert normalize_split("test") == "holdout"
        assert normalize_split("holdout") == "holdout"
        assert normalize_split("valid_unseen") == "holdout"

    def test_unknown_split_rejected(self):
        with pytest.raises(ValueError, match="unknown benchmark split: prod"):
            normalize_split("prod")


class TestRequiredEnv:
    def test_missing_and_blank_rejected(self, monkeypatch):
        monkeypatch.delenv("SOME_MISSING_VAR", raising=False)
        with pytest.raises(RuntimeError, match="SOME_MISSING_VAR is required"):
            required_env("SOME_MISSING_VAR")
        monkeypatch.setenv("SOME_MISSING_VAR", "   ")
        with pytest.raises(RuntimeError, match="SOME_MISSING_VAR is required"):
            required_env("SOME_MISSING_VAR")

    def test_value_stripped(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "  value  ")
        assert required_env("SOME_VAR") == "value"


class TestObjectiveGate:
    def rows(self, hard: float, soft: float, **extra) -> dict:
        return {"a": {"hard": hard, "soft": soft, **extra}, "b": {"hard": hard, "soft": soft, **extra}}

    def test_key_mismatch_and_empty_baseline_denied(self):
        assert objective_gate(self.rows(0.5, 0.5), {"a": {"hard": 1.0, "soft": 1.0}}) is False
        assert objective_gate({}, {}) is False

    def test_hard_improvement_passes(self):
        assert objective_gate(self.rows(0.0, 0.5), self.rows(1.0, 0.5)) is True

    def test_soft_threshold_boundary(self):
        baseline = {"a": {"hard": 1.0, "soft": 0.5}}
        assert objective_gate(baseline, {"a": {"hard": 1.0, "soft": 0.52}}) is True
        assert objective_gate(baseline, {"a": {"hard": 1.0, "soft": 0.519}}) is False

    def test_safety_violation_denied(self):
        assert objective_gate(
            self.rows(0.0, 0.5), self.rows(1.0, 0.5, safety_violation=True)
        ) is False


class TestDataLoader:
    def test_train_items_and_size(self):
        loader = CerebellumVerifyDataLoader(sample_tasks())
        assert loader.get_train_size() == 6
        assert len(loader.train_items) == 6

    def test_build_train_batch_is_seed_deterministic(self):
        loader = CerebellumVerifyDataLoader(sample_tasks())
        first = loader.build_train_batch(3, 42)
        second = loader.build_train_batch(3, 42)
        assert [t["task_id"] for t in first.payload] == [t["task_id"] for t in second.payload]
        assert first.batch_size == 3
        assert first.phase == "train"
        third = loader.build_train_batch(10, 42)
        assert len(third.payload) == 6

    def test_build_eval_batch_normalizes_split_and_caps_env_num(self):
        loader = CerebellumVerifyDataLoader(sample_tasks())
        batch = loader.build_eval_batch(2, "val", 7)
        assert batch.split == "validation"
        assert [t["task_id"] for t in batch.payload] == ["val-0", "val-1"]
        holdout = loader.build_eval_batch(10, "test", 7)
        assert holdout.split == "holdout"
        assert len(holdout.payload) == 3

    def test_load_split_items_uses_path_name(self):
        loader = CerebellumVerifyDataLoader(sample_tasks())
        items = loader.load_split_items("/some/dir/valid_unseen")
        assert {t["split"] for t in items} == {"holdout"}

    def test_make_base_seeds(self):
        loader = CerebellumVerifyDataLoader(sample_tasks())
        assert loader.make_base_seeds(2, 3, 42) == [43, 44, 45, 46, 47, 48]

    def test_plan_train_epoch_batches(self):
        loader = CerebellumVerifyDataLoader(sample_tasks())
        batches = loader.plan_train_epoch(
            epoch=2, steps_per_epoch=2, accumulation=1, batch_size=2, seed=5
        )
        assert len(batches) == 2
        assert batches[0].seed == 2005
        assert batches[1].seed == 2006
        assert all(len(batch.payload) == 2 for batch in batches)
        repeat = loader.plan_train_epoch(
            epoch=2, steps_per_epoch=2, accumulation=1, batch_size=2, seed=5
        )
        assert [b.payload for b in repeat] == [b.payload for b in batches]


class TestAdapterInit:
    def test_knobs_are_clamped(self, tmp_path):
        adapter = make_adapter(tmp_path, analyst_workers=99, minibatch_size=0, edit_budget=7)
        assert adapter.analyst_workers == 4
        assert adapter.minibatch_size == 1
        assert adapter.edit_budget == 2
        assert adapter.failure_only is False
        assert isinstance(adapter.harness, DockerTaskHarness)
        assert adapter.container_image == IMAGE
        assert adapter.rollout_calls == 0
        assert adapter.stop_requested is False

    def test_default_image_falls_back_to_manifest(self, tmp_path):
        root = make_data_root(tmp_path)
        adapter = ConcreteAdapter(str(root), "")
        assert adapter.container_image == IMAGE


class TestAdapterSetup:
    def test_missing_env_rejected(self, tmp_path, monkeypatch):
        adapter = make_adapter(tmp_path)
        monkeypatch.delenv("OPENAI_COMPATIBLE_BASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="OPENAI_COMPATIBLE_BASE_URL is required"):
            adapter.setup({})

    def test_model_role_mismatch_rejected(self, tmp_path, monkeypatch):
        adapter = make_adapter(tmp_path)
        cfg = setup_env(monkeypatch, {"target_model": "wrong-m"})
        with pytest.raises(RuntimeError, match="exactly match"):
            adapter.setup(cfg)

    def test_successful_setup_wires_agent_and_limits(self, tmp_path, monkeypatch):
        adapter = make_adapter(tmp_path)
        before = time.monotonic()
        adapter.setup(setup_env(monkeypatch))
        assert isinstance(adapter.agent, OpenAICompatibleAgent)
        assert adapter.agent.model == "target-m"
        assert adapter.agent.token_limit == 100
        assert adapter.target_call_limit == 10
        assert before + 3600 <= adapter.deadline <= time.monotonic() + 3600
        assert adapter.get_dataloader() is adapter.dataloader
        assert adapter.requires_ray() is False


class TestAdapterHelpers:
    def test_build_envs_and_task_types(self, tmp_path):
        adapter = make_adapter(tmp_path)
        train_env = adapter.build_train_env(2, 42)
        assert len(train_env) == 2
        assert {item["split"] for item in train_env} == {"train"}
        eval_env = adapter.build_eval_env(2, "validation", 42)
        assert [item["task_id"] for item in eval_env] == ["val-0", "val-1"]
        spec = BatchSpec("eval", "validation", 1, 2, [{"task_id": "x"}])
        assert adapter.build_env_from_batch(spec) == [{"task_id": "x"}]
        assert adapter.get_task_types() == ["fix", "harden"]


class TestRollout:
    def rollout_env(self, split: str, count: int = 2) -> list[dict]:
        return [{"task_id": f"{split}-{i}", "split": split} for i in range(count)]

    def wired_adapter(self, tmp_path, monkeypatch, hard_by_skill=None):
        adapter = make_adapter(tmp_path)
        adapter.setup(setup_env(monkeypatch))
        stub = StubHarness(hard_by_skill)
        adapter.harness = stub
        return adapter, stub

    def test_setup_required_before_rollout(self, tmp_path):
        adapter = make_adapter(tmp_path)
        with pytest.raises(RuntimeError, match=r"setup\(\) must run before rollout"):
            adapter.rollout([], "skill", str(tmp_path / "out"))

    def test_rollout_writes_predictions_and_ledger(self, tmp_path, monkeypatch):
        adapter, stub = self.wired_adapter(tmp_path, monkeypatch)
        out_dir = tmp_path / "out"
        results = adapter.rollout(self.rollout_env("train"), "skill-a", str(out_dir), seed=9)
        assert len(results) == 2
        assert adapter.rollout_calls == 2
        assert stub.calls == [("train-0", 9), ("train-1", 10)]
        for result in results:
            assert "skill_content" not in result
            assert result["split"] == "train"
            assert result["skill_hash"] == hashlib.sha256(b"skill-a").hexdigest()
        conversation = out_dir / "predictions" / "train-0" / "conversation.json"
        assert json.loads(conversation.read_text(encoding="utf-8")) == [{"turn": 0}]
        ledger_lines = adapter.ledger_path.read_text(encoding="utf-8").splitlines()
        assert len(ledger_lines) == 2
        assert json.loads(ledger_lines[0])["skill_content"] == "skill-a"

    def test_rollout_budget_exhausted(self, tmp_path, monkeypatch):
        adapter, _ = self.wired_adapter(tmp_path, monkeypatch)
        adapter.rollout_calls = adapter.target_call_limit
        with pytest.raises(RuntimeError, match="target rollout budget exhausted"):
            adapter.rollout(self.rollout_env("train"), "skill", str(tmp_path / "out"))

    def test_wall_clock_deadline_exhausted(self, tmp_path, monkeypatch):
        adapter, _ = self.wired_adapter(tmp_path, monkeypatch)
        adapter.deadline = time.monotonic() - 1
        with pytest.raises(RuntimeError, match="wall-clock budget exhausted"):
            adapter.rollout(self.rollout_env("train"), "skill", str(tmp_path / "out"))

    def test_token_budget_exhausted(self, tmp_path, monkeypatch):
        adapter, _ = self.wired_adapter(tmp_path, monkeypatch)
        adapter.agent.usage.tokens = 101  # total_token_limit is 100
        with pytest.raises(RuntimeError, match="target token budget exhausted"):
            adapter.rollout(self.rollout_env("train"), "skill", str(tmp_path / "out"))

    def test_two_non_improving_candidates_request_early_stop(self, tmp_path, monkeypatch):
        adapter, _ = self.wired_adapter(tmp_path, monkeypatch)
        env = self.rollout_env("validation")
        adapter.rollout(env, "baseline", str(tmp_path / "o1"))  # establishes baseline
        assert adapter._validation_baseline is not None
        adapter.rollout(env, "worse-1", str(tmp_path / "o2"))
        assert adapter._consecutive_no_improvement == 1
        assert adapter.stop_requested is False
        adapter.rollout(env, "worse-2", str(tmp_path / "o3"))
        assert adapter._consecutive_no_improvement == 2
        assert adapter.stop_requested is True
        with pytest.raises(adapter_module.EarlyStopRequested):
            adapter.rollout(self.rollout_env("train"), "worse-2", str(tmp_path / "o4"))

    def test_improvement_resets_no_improvement_counter(self, tmp_path, monkeypatch):
        adapter, _ = self.wired_adapter(
            tmp_path, monkeypatch, {"better": 1.0}
        )
        env = self.rollout_env("validation")
        adapter.rollout(env, "baseline", str(tmp_path / "o1"))
        adapter.rollout(env, "worse-1", str(tmp_path / "o2"))
        assert adapter._consecutive_no_improvement == 1
        adapter.rollout(env, "better", str(tmp_path / "o3"))
        assert adapter._consecutive_no_improvement == 0
        adapter.rollout(env, "worse-2", str(tmp_path / "o4"))
        assert adapter._consecutive_no_improvement == 1
        assert adapter.stop_requested is False

    def test_repeat_validation_of_same_skill_does_not_count(self, tmp_path, monkeypatch):
        adapter, _ = self.wired_adapter(tmp_path, monkeypatch)
        env = self.rollout_env("validation")
        adapter.rollout(env, "baseline", str(tmp_path / "o1"))
        adapter.rollout(env, "worse-1", str(tmp_path / "o2"))
        adapter.rollout(env, "worse-1", str(tmp_path / "o3"))  # already validated
        assert adapter._consecutive_no_improvement == 1
        assert adapter.stop_requested is False
