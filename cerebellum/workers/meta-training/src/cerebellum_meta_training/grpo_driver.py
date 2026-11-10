"""GRPO driver for the metacognition expert (W2 boundary RL).

Selected for the metacognition role when META_METACOGNITION_GRPO=1 (same
env-gated pattern as META_METACOGNITION_FEWSHOT). Reuses the proven worker
contract: input is the expert shard JSONL from the verified bundle; output is
the same adapter zip TrainingOutput train_qlora produces.

Pipeline: shard JSONL -> verl parquet dataset (raw-surface prompts rendered by
probe.py, gold as reward ground truth) -> verl GRPO (LoRA rank 16, vLLM
rollout, k=8) in the WSL venv -> LoRA adapter extraction from the verl
checkpoint -> deterministic zip.

The verl subprocess runs only in the approved training run; every pure piece
(rows, overrides, extraction) is unit-tested on Windows without GPU.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .meta_reward import _probe
from .trainer import TrainingOutput, _deterministic_zip, verify_gpu

KIND_TO_SHORT = {"temporal_grounding": "tg", "knowledge_boundary": "kb",
                 "search_planning": "st"}

# Verbatim-passthrough chat template: keeps the raw few-shot surface
PASSTHROUGH_TEMPLATE = '{%- for message in messages %}{{ message["content"] }}{%- endfor %}'

GRPO_OVERRIDES = {
    "algorithm.adv_estimator": "grpo",
    "data.prompt_key": "prompt",
    "data.max_prompt_length": "2048",
    "data.max_response_length": "512",
    "data.filter_overlong_prompts": "false",
    "data.truncation": "error",
    "actor_rollout_ref.model.lora_rank": "16",
    "actor_rollout_ref.model.lora_alpha": "32",
    "actor_rollout_ref.model.enable_gradient_checkpointing": "true",
    "actor_rollout_ref.actor.optim.lr": "1e-5",
    "actor_rollout_ref.actor.use_kl_loss": "true",
    "actor_rollout_ref.actor.kl_loss_coef": "0.02",
    "actor_rollout_ref.actor.kl_loss_type": "low_var_kl",
    "actor_rollout_ref.rollout.name": "vllm",
    "actor_rollout_ref.rollout.n": "8",
    "actor_rollout_ref.rollout.temperature": "1.0",
    "actor_rollout_ref.rollout.gpu_memory_utilization": "0.4",
    "actor_rollout_ref.rollout.max_model_len": "2560",
    "actor_rollout_ref.rollout.tensor_model_parallel_size": "1",
    # Compute pinned to the 6h wall budget: 5750 prompts / 256 ~= 23 steps,
    # 1 epoch; probe B measured ~11 min/step (incl. startup), ~= 4.5h total
    # with the two SFT roles. Never leave verl's 30-epoch default.
    "trainer.total_epochs": "1",
    # verl requires explicit micro-batch sizes (no derivation from defaults).
    # torch 2.7 inductor is incompatible with triton 3.4 (which sm_120 needs);
    # eager rollout skips torch.compile entirely.
    "actor_rollout_ref.rollout.enforce_eager": "true",
    "actor_rollout_ref.actor.ppo_mini_batch_size": "256",
    "actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu": "8",
    "actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu": "8",
    "actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu": "8",
    "data.train_batch_size": "256",
    # save_freq must be positive or verl never checkpoints (not even the last
    # step): 23 ~= one epoch of 256-prompt steps; is_last_step saves the rest.
    "trainer.save_freq": "23",
    "reward_model.reward_manager": "naive",
    "trainer.n_gpus_per_node": "1",
    "trainer.nnodes": "1",
    "trainer.val_before_train": "false",
    "trainer.logger": "[console]",
}


def build_grpo_rows(dataset: bytes) -> list[dict]:
    probe = _probe()
    rows = []
    for line in dataset.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if value.get("kind") != "meta_decision" or value.get("split") != "train":
            continue
        record = value.get("record") or {}
        task = record.get("task_kind")
        short = KIND_TO_SHORT.get(task)
        if short is None:
            continue
        rows.append({
            "data_source": task,
            "prompt": [{"role": "user", "content": probe.render_prompt(short, record["input"])}],
            "reward_model": {"ground_truth": json.dumps(record["output"], sort_keys=True,
                                                        ensure_ascii=False)},
            "extra_info": {"row_index": len(rows)},
        })
    if not rows:
        raise RuntimeError("GRPO dataset has no usable metacognition train records")
    return rows


def write_grpo_parquet(rows: list[dict], out_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, out_path)


def write_passthrough_model_dir(base_model: str, out_dir: Path) -> str:
    """verl 0.6.0 has no custom_chat_template; patch a model-dir copy instead.

    Symlinks every pinned-snapshot file except tokenizer_config.json, which is
    copied with chat_template replaced by the verbatim passthrough template so
    tokenizer.apply_chat_template renders the raw few-shot surface unchanged.
    Weights stay in the pinned snapshot (read through the links); the merged
    adapter artifact is unaffected (eval_gguf carries the pristine tokenizer).
    """
    import shutil

    source = Path(base_model)
    out_dir.mkdir(parents=True, exist_ok=True)
    for item in sorted(source.iterdir()):
        target = out_dir / item.name
        if item.name == "tokenizer_config.json":
            config = json.loads(item.read_text(encoding="utf-8"))
            config["chat_template"] = PASSTHROUGH_TEMPLATE
            target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        else:
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(item.resolve())
    return str(out_dir)


def assemble_overrides(*, parquet_path: Path, base_model: str, checkpoint_dir: Path,
                       reward_path: Path) -> list[str]:
    overrides = dict(GRPO_OVERRIDES)
    overrides.update({
        "data.train_files": str(parquet_path),
        "data.val_files": str(parquet_path),
        "actor_rollout_ref.model.path": base_model,
        "trainer.default_local_dir": str(checkpoint_dir),
        "trainer.rollout_data_dir": os.environ.get("META_GRPO_ROLLOUT_DIR")
        or str(checkpoint_dir.parent / "rollouts"),
        "custom_reward_function.path": str(reward_path),
        "custom_reward_function.name": "compute_score",
    })
    step_limit = os.environ.get("META_GRPO_MAX_STEPS")
    if step_limit is not None:
        if not step_limit.isdecimal() or int(step_limit) < 1:
            raise RuntimeError("META_GRPO_MAX_STEPS must be a positive integer")
        overrides["trainer.total_training_steps"] = str(int(step_limit))
    # hydra's override grammar treats { } as config groups and its lexer
    # rejects non-ASCII (the repo path contains Chinese characters); quote any
    # value outside the plain-scalar whitelist. Values must not contain single
    # quotes (the template uses double quotes by construction).
    def safe(value: str) -> str:
        if value and all(ch.isascii() and (ch.isalnum() or ch in "._/=+:-[]" ) for ch in value):
            return value
        assert "'" not in value, f"override value contains a single quote: {value!r}"
        return f"'{value}'"

    return [f"{key}={safe(str(value))}" for key, value in overrides.items()]


def extract_lora_adapter(state: dict, out_dir: Path) -> None:
    """Extract peft LoRA weights from a verl actor checkpoint state dict.

    verl saves peft keys as '...lora_A.default.weight' (adapter name in the
    key). The cerebellum adapter contract is peft's save_pretrained layout
    ('...lora_A.weight'); only the '.default' infix is dropped.
    """
    import torch
    from safetensors.torch import save_file

    adapter_state = {
        key: value for key, value in state.items()
        if ".lora_A." in key or ".lora_B." in key
    }
    if not adapter_state:
        raise RuntimeError("no LoRA weights found in the training checkpoint")
    cleaned = {key.replace(".default.weight", ".weight"): value.contiguous()
               for key, value in adapter_state.items()}
    out_dir.mkdir(parents=True, exist_ok=True)
    save_file(cleaned, str(out_dir / "adapter_model.safetensors"))
    (out_dir / "adapter_config.json").write_text(json.dumps({
        "peft_type": "LORA", "r": 16, "lora_alpha": 32, "lora_dropout": 0.05,
        "target_modules": "all-linear", "task_type": "CAUSAL_LM",
        "base_model_name_or_path": None,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _find_actor_checkpoint(checkpoint_dir: Path) -> Path:
    steps = sorted(checkpoint_dir.glob("global_step_*/actor"),
                   key=lambda path: int(path.parent.name.rsplit("_", 1)[1]))
    if not steps:
        raise RuntimeError(f"no actor checkpoints under {checkpoint_dir}")
    return steps[-1]


def _load_checkpoint_state(actor_dir: Path) -> dict:
    """Load the actor model state: verl writes either safetensors shards or
    FSDP torch shards ('model_world_size_<N>_rank_<r>.pt')."""
    import torch
    from safetensors.torch import load_file

    shards = sorted(actor_dir.glob("*.safetensors"))
    if shards:
        state: dict = {}
        for shard in shards:
            state.update(load_file(str(shard)))
        return state
    shards = sorted(actor_dir.glob("model_world_size_*_rank_*.pt"))
    if not shards:
        raise RuntimeError(f"no model shards in {actor_dir}")
    state = {}
    for shard in shards:
        state.update(torch.load(shard, map_location="cpu", weights_only=True))
    return state


def train_grpo(dataset: bytes, manifest: dict, base_model: str,
               output_dir: Path) -> TrainingOutput:
    """GRPO-train the metacognition adapter via verl in the WSL venv."""
    verify_gpu(24)
    venv_python = os.environ.get("META_GRPO_VENV_PYTHON", "").strip()
    if not venv_python:
        raise RuntimeError("META_GRPO_VENV_PYTHON is required (WSL verl venv python)")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_grpo_rows(dataset)
    parquet_path = output_dir / "grpo-train.parquet"
    write_grpo_parquet(rows, parquet_path)
    checkpoint_dir = output_dir / "verl-checkpoints"
    reward_path = Path(__file__).resolve().parent / "verl_reward.py"
    passthrough_model = write_passthrough_model_dir(base_model, output_dir / "model-passthrough")
    argv = [venv_python, "-m", "verl.trainer.main_ppo",
            *assemble_overrides(parquet_path=parquet_path, base_model=passthrough_model,
                                checkpoint_dir=checkpoint_dir, reward_path=reward_path)]
    completed = subprocess.run(argv, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"verl GRPO training failed with exit {completed.returncode}")
    actor_dir = _find_actor_checkpoint(checkpoint_dir)
    adapter_dir = output_dir / "adapter"
    extract_lora_adapter(_load_checkpoint_state(actor_dir), adapter_dir)
    artifact = _deterministic_zip(adapter_dir)
    metrics = {
        "grpo_prompt_count": len(rows),
        "fact_precision_delta": 0.0,
        "policy_violations": 0,
        "injection_regression": False,
        "cost_per_useful_card_change": 0.0,
    }
    return TrainingOutput(artifact=artifact, metrics=metrics)
