from __future__ import annotations

import io
import hashlib
import json
import os
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingOutput:
    artifact: bytes
    metrics: dict

_METACOGNITION_FEWSHOT_KINDS = {
    "temporal_grounding": "tg",
    "knowledge_boundary": "kb",
    "search_planning": "st",
}
_metacognition_fewshot_cache: dict[str, dict[str, list[dict]]] = {}


def _metacognition_fewshot() -> dict[str, list[dict]] | None:
    """Few-shot exemplars for the metacognition evaluation surface, by task_kind.

    Env META_METACOGNITION_FEWSHOT names the manifest-pinned exemplar file
    (benchmarks/metacognition/fewshot.json shape); loaded once per path. Env
    unset -> None (byte-identical legacy single-shot surface). Env set but the
    file is unreadable -> RuntimeError: silently dropping the prefix would
    retrain the rejected single-shot surface.
    """
    path = os.environ.get("META_METACOGNITION_FEWSHOT")
    if not path:
        return None
    if path not in _metacognition_fewshot_cache:
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
            exemplars = doc["exemplars"]
        except (OSError, KeyError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"META_METACOGNITION_FEWSHOT unreadable or malformed: {path}"
            ) from error
        _metacognition_fewshot_cache[path] = {
            task: exemplars[short]
            for task, short in _METACOGNITION_FEWSHOT_KINDS.items()
        }
    return _metacognition_fewshot_cache[path]


def _metacognition_fewshot_prefix(task: str) -> str:
    exemplars = _metacognition_fewshot()
    if exemplars is None or task not in exemplars:
        return ""
    parts = []
    for exemplar in exemplars[task]:
        parts.append(
            "<|meta_task|>" + task + "\n"
            "<|input|>" + json.dumps(exemplar["input"], sort_keys=True, ensure_ascii=False) + "\n"
            "<|response|>" + json.dumps(exemplar["output"], sort_keys=True, ensure_ascii=False) + "\n"
        )
    return "".join(parts)


def _training_text(value: dict) -> str | None:
    record = value.get("record")
    if value.get("split") != "train" or not isinstance(record, dict):
        return None
    if value.get("kind") == "meta_decision":
        task = record.get("task_kind")
        input_value = record.get("input")
        output = record.get("output")
        return (
            _metacognition_fewshot_prefix(str(task))
            + "<|meta_task|>" + str(task) + "\n"
            "<|input|>" + json.dumps(input_value, sort_keys=True, ensure_ascii=False) + "\n"
            "<|response|>" + json.dumps(output, sort_keys=True, ensure_ascii=False)
        )
    if value.get("kind") == "meta_replay":
        target = {
            "candidate_preferred": record.get("candidate_score", 0)
            > record.get("baseline_score", 0),
            "fact_correct": record.get("fact_correct", False),
            "safety_passed": record.get("safety_passed", False),
        }
        input_value = {
            "task_id": record.get("task_id"),
            "source_domain": record.get("source_domain"),
            "topic_family": record.get("topic_family"),
        }
        return (
            "<|meta_task|>replay_preference\n"
            "<|input|>" + json.dumps(input_value, sort_keys=True) + "\n"
            "<|response|>" + json.dumps(target, sort_keys=True)
        )
    if value.get("kind") == "expert_route":
        target = {
            "expert_id": record.get("target_expert_id"),
            "confidence": record.get("confidence"),
            "status": record.get("status"),
        }
        input_value = {
            "record_kind": record.get("record_kind"),
            "task_kind": record.get("task_kind"),
            "source_domain": record.get("source_domain"),
            "topic_family": record.get("topic_family"),
            "reason_codes": record.get("reason_codes", []),
        }
        return (
            "<|meta_task|>expert_route\n"
            "<|input|>" + json.dumps(input_value, sort_keys=True, ensure_ascii=False) + "\n"
            "<|response|>" + json.dumps(target, sort_keys=True, ensure_ascii=False)
        )
    return None


def _load_training_records(dataset: bytes) -> list[str]:
    records: list[str] = []
    for line_number, line in enumerate(dataset.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"invalid dataset JSONL at line {line_number}") from error
        if not isinstance(value, dict):
            raise RuntimeError(f"dataset line {line_number} is not an object")
        text = _training_text(value)
        if text:
            records.append(text)
    if not records:
        raise RuntimeError("training split contains no usable records")
    return records


def _supervised_features(dataset: bytes, tokenizer, mode: str, maximum_length: int):
    if mode not in {"joint_full", "split_full", "split_response"}:
        raise ValueError(f"unknown supervision mode: {mode}")
    if tokenizer.eos_token_id is None:
        raise ValueError("supervised control requires an explicit EOS token")
    features, evidence = [], []
    for line_number, line in enumerate(dataset.splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if value.get("split") != "train" or value.get("kind") != "meta_decision":
            raise ValueError("supervised control accepts only structured train meta_decisions")
        record = value["record"]
        answer = json.dumps(record["output"], sort_keys=True, ensure_ascii=False)
        # Remove the known structured target, never search text for a delimiter.
        text = _training_text(value)
        assert text.endswith(answer)
        prompt = text[:-len(answer)]
        prefix = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        target = tokenizer(answer, add_special_tokens=False)["input_ids"] + [tokenizer.eos_token_id]
        ids = (tokenizer(text, add_special_tokens=False)["input_ids"] + [tokenizer.eos_token_id]
               if mode == "joint_full" else prefix + target)
        if len(ids) > maximum_length:
            raise ValueError(f"record {line_number} exceeds max_length; target truncation forbidden")
        labels = [-100] * len(prefix) + target if mode == "split_response" else ids.copy()
        if not any(token != -100 for token in labels[1:]):
            raise ValueError(f"record {line_number} has no causal supervision")
        source_id = record["decision_id"]
        features.append({"input_ids": ids, "attention_mask": [1] * len(ids),
                         "labels": labels, "source_record_id": source_id})
        evidence.append({"source_record_id": source_id, "input_tokens": len(ids),
                         "prompt_tokens": len(prefix), "answer_tokens_with_eos": len(target),
                         "supervised_tokens": sum(token != -100 for token in labels[1:])})
    if not features:
        raise ValueError("supervised control has no records")
    return features, evidence


def _supervised_batch(features, pad_token_id):
    """Right padding is identified by attention, including when PAD == EOS."""
    width = max(len(row["input_ids"]) for row in features)
    batch = {name: [] for name in ("input_ids", "attention_mask", "labels")}
    for row in features:
        missing = width - len(row["input_ids"])
        attention = row["attention_mask"] + [0] * missing
        batch["input_ids"].append(row["input_ids"] + [pad_token_id] * missing)
        batch["attention_mask"].append(attention)
        batch["labels"].append([label if mask else -100 for label, mask in
                                zip(row["labels"] + [-100] * missing, attention)])
    batch["source_record_id"] = [row["source_record_id"] for row in features]
    return batch


def _training_seed(supervision_mode):
    seed = int(os.environ.get("CEREBELLUM_RUN_SEED", "17")) if supervision_mode else 17
    if not 0 <= seed < 2**32:
        raise ValueError("training seed must fit an unsigned 32-bit integer")
    return seed


def _adapter_hash(model):
    import torch
    from peft import get_peft_model_state_dict
    digest = hashlib.sha256()
    for name, tensor in sorted(get_peft_model_state_dict(model).items()):
        value = tensor.detach().cpu().contiguous()
        if not bool(torch.isfinite(value).all()):
            raise ValueError(f"non-finite adapter tensor: {name}")
        digest.update(json.dumps([name, str(value.dtype), list(value.shape)]).encode())
        digest.update(value.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _resume_control(output_dir, resume, binding):
    if not resume:
        if (output_dir / "control.json").exists():
            raise ValueError("existing supervised run requires an explicit native checkpoint")
        return None
    checkpoint = Path(resume).resolve()
    if checkpoint.parent != (output_dir / "checkpoints").resolve():
        raise ValueError("resume checkpoint is outside this run")
    for name in ("optimizer.pt", "scheduler.pt", "rng_state.pth", "trainer_state.json",
                 "adapter_model.safetensors", "control.json"):
        if not (checkpoint / name).is_file():
            raise ValueError(f"incomplete native checkpoint: {name}")
    control = json.loads((checkpoint / "control.json").read_text())
    if control["binding"] != binding:
        raise ValueError("resume data/configuration hash mismatch")
    state = json.loads((checkpoint / "trainer_state.json").read_text())
    if control["global_step"] != state["global_step"]:
        raise ValueError("resume progress mismatch")
    return control


def _controlled_trainer(model, arguments, features, evidence, tokenizer, binding, output_dir):
    import torch
    from transformers import Trainer, TrainerCallback

    resume = os.environ.get("CEREBELLUM_RUN_RESUME_FROM_CHECKPOINT")
    control = _resume_control(output_dir, resume, binding) or {
        "binding": binding, "initial_adapter_sha256": _adapter_hash(model),
        "global_step": 0, "updates": [], "record_token_counts": evidence,
    }
    expected = os.environ.get("CEREBELLUM_RUN_EXPECTED_INITIAL_SHA256")
    if expected and control["initial_adapter_sha256"] != expected:
        raise ValueError("initial LoRA weights differ from the control arms")
    pending = []

    def save(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    class Progress(TrainerCallback):
        def on_step_end(self, args, state, control_state=None, **kwargs):
            control["global_step"] = state.global_step
            control["updates"].append({"step": state.global_step, "records": pending.copy()})
            pending.clear()
            save(output_dir / "control.json")

        def on_save(self, args, state, control_state=None, **kwargs):
            save(output_dir / "checkpoints" / f"checkpoint-{state.global_step}" / "control.json")

        def on_log(self, args, state, control_state=None, logs=None, **kwargs):
            if logs:
                with (output_dir / "losses.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"step": state.global_step, **logs}) + "\n")

    class ControlledTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            source_ids = inputs.pop("source_record_id")
            if model.training:
                pending.extend({"source_record_id": source, "supervised_tokens": int((labels[1:] != -100).sum())}
                               for source, labels in zip(source_ids, inputs["labels"]))
            return super().compute_loss(model, inputs, return_outputs=return_outputs,
                                        num_items_in_batch=num_items_in_batch)

    def collate(rows):
        batch = _supervised_batch(rows, tokenizer.pad_token_id)
        return {name: value if name == "source_record_id" else torch.tensor(value, dtype=torch.long)
                for name, value in batch.items()}

    output_dir.mkdir(parents=True, exist_ok=True)
    save(output_dir / "control.json")
    trainer = ControlledTrainer(model=model, args=arguments, train_dataset=features,
                                eval_dataset=features, data_collator=collate, callbacks=[Progress()])
    trainer.model_accepts_loss_kwargs = False
    trainer.label_names = ["labels"]
    return trainer, control, save, resume


def verify_gpu(minimum_gib: int = 24) -> None:
    if os.environ.get("META_TRAINER_ENABLED") != "1":
        raise RuntimeError("meta trainer is disabled")
    if os.environ.get("META_DATA_LICENSE_POLICY") != "licensed-only":
        raise RuntimeError("meta trainer requires licensed-only data policy")
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("pinned QLoRA dependencies are not installed") from error
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    memory = int(torch.cuda.get_device_properties(0).total_memory)
    if memory < minimum_gib * 1024**3:
        raise RuntimeError(f"GPU has less than the required {minimum_gib} GiB")


def _deterministic_zip(root: Path) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if path.is_symlink():
                raise RuntimeError("adapter output must not contain symlinks")
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return output.getvalue()


def _deterministic_tar(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:") as archive:
        for name in sorted(entries):
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError("routed adapter path is unsafe")
            value = entries[name]
            info = tarfile.TarInfo(name)
            info.size = len(value)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            archive.addfile(info, io.BytesIO(value))
    return output.getvalue()


def train_qlora(
    dataset: bytes,
    manifest: dict,
    base_model: str,
    output_dir: Path,
) -> TrainingOutput:
    verify_gpu(24)
    remote_pin = all(
        os.environ.get(name)
        for name in ("META_BASE_MODEL_ID", "META_BASE_MODEL_REVISION", "META_BASE_MODEL_SHA256")
    )
    expected_path = os.environ.get("META_BASE_MODEL_PATH", "").strip()
    legacy_model = os.environ.get("META_BASE_MODEL", "").strip()
    identity_matches = (
        expected_path
        and Path(base_model).resolve() == Path(expected_path).resolve()
    ) or (legacy_model and legacy_model == base_model) or remote_pin
    if not base_model or not identity_matches:
        raise RuntimeError("worker base model does not match the immutable job")
    records = _load_training_records(dataset)
    try:
        import accelerate
        import bitsandbytes
        import peft
        import torch
        import transformers
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from torch.utils.data import Dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as error:
        raise RuntimeError("pinned QLoRA dependencies are not installed") from error

    maximum_length = max(
        256,
        min(
            int(
                os.environ.get("CEREBELLUM_RUN_MAX_LENGTH")
                or os.environ.get("META_MAX_LENGTH", "2048")
            ),
            8192,
        ),
    )
    lora_rank = int(os.environ.get("CEREBELLUM_RUN_LORA_RANK", "16"))
    lora_alpha = int(os.environ.get("CEREBELLUM_RUN_LORA_ALPHA", "32"))
    lora_dropout = float(os.environ.get("CEREBELLUM_RUN_LORA_DROPOUT", "0.05"))
    learning_rate = float(os.environ.get("CEREBELLUM_RUN_LEARNING_RATE", "0.0002"))
    gradient_accumulation = int(
        os.environ.get("CEREBELLUM_RUN_GRADIENT_ACCUMULATION", "16")
    )
    supervision_mode = os.environ.get("CEREBELLUM_RUN_SUPERVISION_MODE")
    seed = _training_seed(supervision_mode)
    model_revision = None if Path(base_model).exists() else (
        os.environ.get("META_BASE_MODEL_REVISION") or None
    )
    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        token=False,
        revision=model_revision,
        trust_remote_code=False,
        use_fast=True,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    if supervision_mode:
        features, token_evidence = _supervised_features(dataset, tokenizer, supervision_mode, maximum_length)
        max_steps = int(os.environ["CEREBELLUM_RUN_MAX_STEPS"])
        if max_steps <= 0 or hashlib.sha256(dataset).hexdigest() != manifest["dataset_hash"]:
            raise ValueError("invalid supervised step budget or dataset hash")

    class TokenizedDataset(Dataset):
        def __init__(self, values: list[str]) -> None:
            self.values = values

        def __len__(self) -> int:
            return len(self.values)

        def __getitem__(self, index: int) -> dict:
            return tokenizer(
                self.values[index],
                truncation=True,
                max_length=maximum_length,
                add_special_tokens=True,
            )

    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        token=False,
        revision=model_revision,
        trust_remote_code=False,
        quantization_config=quantization,
        device_map={"": 0},
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    targets = [
        item.strip()
        for item in os.environ.get(
            "META_LORA_TARGET_MODULES", "q_proj,k_proj,v_proj,o_proj"
        ).split(",")
        if item.strip()
    ]
    if supervision_mode:
        transformers.set_seed(seed)
    model = get_peft_model(
        model,
        LoraConfig(
            r=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=targets,
        ),
    )
    adapter_dir = output_dir / "adapter"
    experimental_arguments = ({
        "max_steps": max_steps, "save_steps": 16, "save_only_model": False,
        "per_device_eval_batch_size": 1, "dataloader_num_workers": 0,
        "dataloader_pin_memory": False, "torch_compile": False,
        "lr_scheduler_type": "linear", "disable_tqdm": True,
        "logging_nan_inf_filter": False,
        "logging_dir": str(output_dir / "logs"),
    } if supervision_mode else {})
    arguments = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=max(
            1,
            min(
                int(
                    os.environ.get("CEREBELLUM_RUN_EPOCHS")
                    or os.environ.get("META_EPOCHS", "1")
                ),
                3,
            ),
        ),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=gradient_accumulation,
        learning_rate=learning_rate,
        warmup_ratio=0.03,
        logging_steps=4 if supervision_mode else 10,
        save_strategy="steps" if supervision_mode else "no",
        report_to=[],
        bf16=True,
        fp16=False,
        optim="paged_adamw_8bit",
        remove_unused_columns=False,
        seed=seed,
        data_seed=seed,
        **experimental_arguments,
    )
    if supervision_mode:
        configuration = {"arguments": arguments.to_dict(), "mode": supervision_mode,
                         "max_length": maximum_length, "base": [base_model, model_revision,
                         os.environ.get("META_BASE_MODEL_SHA256")],
                         "lora": [lora_rank, lora_alpha, lora_dropout, targets],
                         "eos": tokenizer.eos_token_id, "pad": tokenizer.pad_token_id,
                         "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        binding = {"dataset_sha256": hashlib.sha256(dataset).hexdigest(),
                   "configuration_sha256": hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest(),
                   "tokenized_data_sha256": hashlib.sha256(json.dumps(features, sort_keys=True).encode()).hexdigest()}
        trainer, control, save_control, resume = _controlled_trainer(
            model, arguments, features, token_evidence, tokenizer, binding, output_dir)
        (output_dir / "configuration.json").write_text(json.dumps(configuration, indent=2) + "\n")
        if os.environ.get("CEREBELLUM_RUN_DIAGNOSTIC_LOSS") == "1" and "initial_eval_loss" not in control:
            control["initial_eval_loss"] = trainer.evaluate(metric_key_prefix="initial")["initial_loss"]
            save_control(output_dir / "control.json")
        train_result = trainer.train(resume_from_checkpoint=resume)
        if os.environ.get("CEREBELLUM_RUN_DIAGNOSTIC_LOSS") == "1":
            control["final_eval_loss"] = trainer.evaluate(metric_key_prefix="final")["final_loss"]
        control["final_adapter_sha256"] = _adapter_hash(model)
        control["actual_optimizer_updates"] = trainer.state.global_step
        control["complete"] = trainer.state.global_step == max_steps
        control["supervised_tokens_consumed"] = sum(row["supervised_tokens"] for update in control["updates"] for row in update["records"])
        save_control(output_dir / "control.json")
    else:
        trainer = Trainer(
            model=model,
            args=arguments,
            train_dataset=TokenizedDataset(records),
            data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
        )
        train_result = trainer.train()
    model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)
    run_manifest = {
        "schema_version": "cerebellum/v1",
        "kind": "meta_qlora_adapter_v1",
        "base_model": os.environ.get("META_BASE_MODEL_ID") or base_model,
        "base_model_revision": os.environ.get("META_BASE_MODEL_REVISION"),
        "base_model_sha256": os.environ.get("META_BASE_MODEL_SHA256"),
        "dataset_hash": manifest["dataset_hash"],
        "training_records": len(records),
        "max_length": maximum_length,
        "lora": {
            "r": lora_rank,
            "alpha": lora_alpha,
            "dropout": lora_dropout,
            "target_modules": targets,
        },
        "learning_rate": learning_rate,
        "gradient_accumulation_steps": gradient_accumulation,
        "libraries": {
            "accelerate": accelerate.__version__,
            "bitsandbytes": bitsandbytes.__version__,
            "peft": peft.__version__,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "train_loss": float(train_result.metrics.get("train_loss", 0.0)),
        "automatic_activation_metrics_included": False,
        "adapter_role": os.environ.get("CEREBELLUM_ADAPTER_ROLE", "dense"),
    }
    if supervision_mode:
        run_manifest["supervised_control"] = control
    (adapter_dir / "cerebellum-training-manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifact = _deterministic_zip(adapter_dir)
    # Training loss is diagnostic only. Activation metrics are supplied by objective shadow replay.
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
    return TrainingOutput(artifact=artifact, metrics=metrics)


def train_routed_qlora(
    datasets: dict[str, bytes],
    manifest: dict,
    base_model: str,
    output_dir: Path,
) -> TrainingOutput:
    context = manifest.get("routed_training")
    if not isinstance(context, dict):
        raise RuntimeError("routed training context is missing")
    plan = context.get("expert_plan")
    base_pin = context.get("base_model")
    if not isinstance(plan, dict) or not isinstance(base_pin, dict):
        raise RuntimeError("routed training plan or base model pin is invalid")
    if (
        plan.get("architecture") != "routed_lora"
        or plan.get("router_top_k") != 1
    ):
        raise RuntimeError("routed training requires an explicit Top-1 router plan")
    expert_ids = plan.get("expert_ids")
    fallback = plan.get("fallback_expert_id")
    train_router = plan.get("train_router") is True
    train_shared = plan.get("train_shared", True) is True
    if (
        not isinstance(expert_ids, list)
        or not isinstance(fallback, str)
        or not fallback
        or len(set(expert_ids)) != len(expert_ids)
        or (not train_router and not train_shared and not expert_ids)
    ):
        raise RuntimeError("routed training expert selection is invalid")
    roles = [
        *(["router"] if train_router else []),
        *([fallback] if train_shared else []),
        *expert_ids,
    ]
    if len(set(roles)) != len(roles) or any(role not in datasets for role in roles):
        raise RuntimeError("routed training Bundle lacks a required adapter dataset")
    if "metacognition" in roles and os.environ.get("META_METACOGNITION_GRPO") == "1":
        # GRPO spawns verl as a subprocess sharing the GPU with this process;
        # run it before any SFT role leaves residual CUDA reservations behind.
        roles = ["metacognition", *(role for role in roles if role != "metacognition")]

    entries: dict[str, bytes] = {}
    artifacts: list[dict] = []
    metrics: dict | None = None
    for role in roles:
        dataset = datasets[role]
        training_records = len(_load_training_records(dataset))
        role_manifest = dict(manifest)
        role_manifest["dataset_hash"] = hashlib.sha256(dataset).hexdigest()
        previous_role = os.environ.get("CEREBELLUM_ADAPTER_ROLE")
        os.environ["CEREBELLUM_ADAPTER_ROLE"] = role
        try:
            if role == "metacognition" and os.environ.get("META_METACOGNITION_GRPO") == "1":
                from .grpo_driver import train_grpo
                result = train_grpo(
                    dataset,
                    role_manifest,
                    base_model,
                    output_dir / role,
                )
            else:
                result = train_qlora(
                    dataset,
                    role_manifest,
                    base_model,
                    output_dir / role,
                )
        finally:
            if previous_role is None:
                os.environ.pop("CEREBELLUM_ADAPTER_ROLE", None)
            else:
                os.environ["CEREBELLUM_ADAPTER_ROLE"] = previous_role
        path = f"adapters/{role}.zip"
        entries[path] = result.artifact
        artifacts.append(
            {
                "expert_id": role,
                "path": path,
                "sha256": hashlib.sha256(result.artifact).hexdigest(),
                "byte_length": len(result.artifact),
                "training_records": training_records,
            }
        )
        metrics = result.metrics

    router = next(
        (item for item in artifacts if item["expert_id"] == "router"), None
    )
    experts = sorted(
        (item for item in artifacts if item["expert_id"] != "router"),
        key=lambda item: item["expert_id"],
    )
    routed_manifest = {
        "schema_version": "cerebellum/v1",
        "kind": "routed_lora_bundle_v1",
        "base_model": base_pin,
        "snapshot_id": context.get("snapshot_id"),
        "expert_view_id": plan.get("expert_view_id"),
        "taxonomy_hash": context.get("taxonomy_hash"),
        "router_top_k": plan.get("router_top_k"),
        "fallback_expert_id": fallback,
        "router": router,
        "experts": experts,
    }
    manifest_bytes = json.dumps(
        routed_manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    entries["cerebellum-routed-adapter-manifest.json"] = manifest_bytes
    return TrainingOutput(
        artifact=_deterministic_tar(entries),
        metrics=metrics or {},
    )
