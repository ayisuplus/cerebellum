#!/usr/bin/env python3
"""GRPO driver unit tests: dataset rows byte-match probe.py's evaluation
surface, overrides assemble the pinned GRPO config, LoRA extraction strips
peft prefixes, and the env-gated role wiring selects GRPO only for the
metacognition expert. No GPU, no verl subprocess."""
from __future__ import annotations

import importlib.util
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_meta_training.grpo_driver import (
    GRPO_OVERRIDES,
    PASSTHROUGH_TEMPLATE,
    assemble_overrides,
    build_grpo_rows,
    extract_lora_adapter,
)
from cerebellum_meta_training.trainer import TrainingOutput, train_routed_qlora

REPO = Path(__file__).resolve().parents[3]
PROBE_PATH = REPO / "benchmarks" / "metacognition" / "probe.py"
MODULE = "cerebellum_meta_training.trainer"


def load_probe():
    spec = importlib.util.spec_from_file_location("metacognition_probe", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def meta_record(task_kind: str, split: str = "train") -> dict:
    return {
        "kind": "meta_decision",
        "split": split,
        "record": {
            "task_kind": task_kind,
            "input": {"query": "q", "environment": {"now": "2026-06-18T10:00:00+08:00"}},
            "output": {"action": "answer", "answer": "a", "as_of_used": "2026-06-18T02:00:00Z"},
        },
    }


def to_bytes(*records: dict) -> bytes:
    return b"".join(json.dumps(r, ensure_ascii=False).encode() + b"\n" for r in records)


class BuildGrpoRowsTests(unittest.TestCase):
    def test_rows_render_exact_eval_surface(self) -> None:
        probe = load_probe()
        dataset = to_bytes(meta_record("temporal_grounding"),
                           meta_record("knowledge_boundary"),
                           meta_record("search_planning"))
        rows = build_grpo_rows(dataset)
        self.assertEqual(len(rows), 3)
        for row, (short, task) in zip(rows, [("tg", "temporal_grounding"),
                                             ("kb", "knowledge_boundary"),
                                             ("st", "search_planning")]):
            record = meta_record(task)["record"]
            self.assertEqual(row["data_source"], task)
            self.assertEqual(row["prompt"][0]["role"], "user")
            self.assertEqual(row["prompt"][0]["content"],
                             probe.render_prompt(short, record["input"]))
            self.assertEqual(json.loads(row["reward_model"]["ground_truth"]), record["output"])

    def test_non_train_and_non_decision_records_are_skipped(self) -> None:
        dataset = to_bytes(meta_record("temporal_grounding", split="holdout"),
                           {"kind": "expert_route", "split": "train", "record": {}},
                           meta_record("relevance"))
        with self.assertRaisesRegex(RuntimeError, "no usable metacognition"):
            build_grpo_rows(dataset)


class OverrideTests(unittest.TestCase):
    def test_explicit_step_limit_and_rollout_capture(self) -> None:
        arguments = dict(parquet_path=Path("train.parquet"), base_model="base",
                         checkpoint_dir=Path("run/checkpoints"), reward_path=Path("reward.py"))
        with mock.patch.dict(os.environ, {"META_GRPO_MAX_STEPS": "2"}):
            values = assemble_overrides(**arguments)
        self.assertIn("trainer.total_training_steps=2", values)
        options = dict(value.split("=", 1) for value in values)
        self.assertEqual(options["trainer.rollout_data_dir"].strip("'"), str(Path("run/rollouts")))
        with mock.patch.dict(os.environ, {"META_GRPO_ROLLOUT_DIR": "persistent/rollouts"}):
            self.assertIn("trainer.rollout_data_dir=persistent/rollouts", assemble_overrides(**arguments))
        for invalid in ("0", "-1", "two", "1.5", ""):
            with self.subTest(invalid=invalid), mock.patch.dict(os.environ, {"META_GRPO_MAX_STEPS": invalid}):
                with self.assertRaisesRegex(RuntimeError, "positive integer"):
                    assemble_overrides(**arguments)

    def test_pinned_grpo_shape(self) -> None:
        self.assertEqual(GRPO_OVERRIDES["algorithm.adv_estimator"], "grpo")
        self.assertEqual(GRPO_OVERRIDES["actor_rollout_ref.model.lora_rank"], "16")
        self.assertEqual(GRPO_OVERRIDES["actor_rollout_ref.rollout.n"], "8")
        self.assertEqual(GRPO_OVERRIDES["actor_rollout_ref.actor.kl_loss_coef"], "0.02")
        self.assertEqual(GRPO_OVERRIDES["trainer.total_epochs"], "1")
        self.assertEqual(GRPO_OVERRIDES["data.train_batch_size"], "256")
        assembled = assemble_overrides(parquet_path=Path("t.parquet"),
                                       base_model="Qwen/Qwen2.5-1.5B",
                                       checkpoint_dir=Path("ckpt"),
                                       reward_path=Path("verl_reward.py"))
        joined = "\n".join(assembled)
        self.assertIn("data.train_files=t.parquet", joined)
        self.assertIn("actor_rollout_ref.model.path=Qwen/Qwen2.5-1.5B", joined)
        self.assertIn("custom_reward_function.name=compute_score", joined)
        self.assertIn("reward_model.reward_manager=naive", joined)

    def test_passthrough_model_dir_patches_only_template(self) -> None:
        import json as jsonlib
        from cerebellum_meta_training.grpo_driver import write_passthrough_model_dir
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "base"
            source.mkdir()
            (source / "model.safetensors").write_bytes(b"weights")
            (source / "tokenizer_config.json").write_text(
                jsonlib.dumps({"chat_template": "<|im_start|>original"}), encoding="utf-8")
            out = Path(directory) / "patched"
            write_passthrough_model_dir(str(source), out)
            patched = jsonlib.loads((out / "tokenizer_config.json").read_text(encoding="utf-8"))
            self.assertEqual(patched["chat_template"], PASSTHROUGH_TEMPLATE)
            self.assertTrue((out / "model.safetensors").is_symlink())

    def test_passthrough_template_renders_verbatim(self) -> None:
        # jinja evaluation of the template equals identity on message content
        import jinja2
        env = jinja2.Environment()
        template = env.from_string(PASSTHROUGH_TEMPLATE)
        surface = "<|meta_task|>temporal_grounding\n<|input|>{\"x\": 1}\n<|response|>"
        self.assertEqual(template.render(messages=[{"content": surface}]), surface)


class ExtractLoraAdapterTests(unittest.TestCase):
    def test_lora_keys_extracted_and_default_suffix_dropped(self) -> None:
        import torch
        # verl checkpoint naming: peft adapter name '.default' inside the key
        state = {
            "base_model.model.model.layers.0.self_attn.q_proj.lora_A.default.weight": torch.zeros(16, 8),
            "base_model.model.model.layers.0.self_attn.q_proj.lora_B.default.weight": torch.zeros(8, 16),
            "base_model.model.model.layers.0.self_attn.q_proj.base_layer.weight": torch.zeros(8, 8),
            "lm_head.weight": torch.zeros(4, 8),
        }
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            extract_lora_adapter(state, out)
            from safetensors import safe_open
            with safe_open(str(out / "adapter_model.safetensors"), framework="pt") as fh:
                keys = sorted(fh.keys())
            # peft save_pretrained contract (W1 adapter bundle verified)
            self.assertEqual(
                keys,
                ["base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight",
                 "base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight"],
            )
            config = json.loads((out / "adapter_config.json").read_text(encoding="utf-8"))
            self.assertEqual((config["r"], config["lora_alpha"]), (16, 32))

    def test_missing_lora_weights_fail_closed(self) -> None:
        import torch
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "no LoRA weights"):
                extract_lora_adapter({"weight": torch.zeros(2)}, Path(directory))


class GrpoRoleWiringTests(unittest.TestCase):
    def test_metacognition_role_uses_grpo_only_when_flagged(self) -> None:
        from test_trainer_extra import routed_manifest  # reuse the shared fixture

        manifest = routed_manifest(expert_ids=["metacognition"])
        datasets = {"router": to_bytes(meta_record("relevance")),
                    "shared": to_bytes(meta_record("relevance")),
                    "metacognition": to_bytes(meta_record("temporal_grounding"))}
        seen: list[str] = []

        def fake_qlora(dataset, role_manifest, base_model, output):
            seen.append("qlora:" + os.environ["CEREBELLUM_ADAPTER_ROLE"])
            return TrainingOutput(b"w", {"ok": 1})

        def fake_grpo(dataset, role_manifest, base_model, output):
            seen.append("grpo:" + os.environ["CEREBELLUM_ADAPTER_ROLE"])
            return TrainingOutput(b"w2", {"ok": 1})

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"META_METACOGNITION_GRPO": "1"}
        ), mock.patch(f"{MODULE}.train_qlora", side_effect=fake_qlora), mock.patch(
            "cerebellum_meta_training.grpo_driver.train_grpo", side_effect=fake_grpo
        ):
            train_routed_qlora(datasets, manifest, "example/model", Path(directory))
        # GRPO runs before SFT roles: the verl subprocess needs a clean GPU
        self.assertEqual(seen, ["grpo:metacognition", "qlora:router", "qlora:shared"])

    def test_flag_unset_keeps_qlora_for_metacognition(self) -> None:
        from test_trainer_extra import routed_manifest

        manifest = routed_manifest(expert_ids=["metacognition"])
        datasets = {"router": to_bytes(meta_record("relevance")),
                    "shared": to_bytes(meta_record("relevance")),
                    "metacognition": to_bytes(meta_record("temporal_grounding"))}
        seen: list[str] = []

        def fake_qlora(dataset, role_manifest, base_model, output):
            seen.append("qlora:" + os.environ["CEREBELLUM_ADAPTER_ROLE"])
            return TrainingOutput(b"w", {"ok": 1})

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ
        ), mock.patch(f"{MODULE}.train_qlora", side_effect=fake_qlora):
            os.environ.pop("META_METACOGNITION_GRPO", None)
            train_routed_qlora(datasets, manifest, "example/model", Path(directory))
        self.assertEqual(seen, ["qlora:router", "qlora:shared", "qlora:metacognition"])


class VerlRewardAdapterTests(unittest.TestCase):
    def test_compute_score_wraps_meta_reward(self) -> None:
        from cerebellum_meta_training.verl_reward import compute_score
        gold = {"action": "answer", "answer": "22", "answer_basis": "parametric",
                "as_of_used": "2026-06-18T02:00:00Z", "confidence": 0.85,
                "freshness_hours": None, "query": None}
        good = compute_score("knowledge_boundary", json.dumps(gold, ensure_ascii=False),
                             json.dumps(gold, ensure_ascii=False))
        self.assertEqual(good["score"], 1.0)
        bad = compute_score("knowledge_boundary", "no json here",
                            json.dumps(gold, ensure_ascii=False))
        self.assertEqual(bad["score"], 0.0)
        self.assertFalse(bad["contract_valid"])


if __name__ == "__main__":
    unittest.main()
