from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from cerebellum_meta_training import trainer
from cerebellum_meta_training.trainer import (
    TrainingOutput,
    _deterministic_tar,
    _deterministic_zip,
    _load_training_records,
    _training_text,
    train_qlora,
    train_routed_qlora,
    verify_gpu,
)

MODULE = "cerebellum_meta_training.trainer"

ENABLED_ENV = {
    "META_TRAINER_ENABLED": "1",
    "META_DATA_LICENSE_POLICY": "licensed-only",
}


def fake_torch(*, cuda_available: bool = True, memory_gib: int = 24) -> types.ModuleType:
    module = types.ModuleType("torch")
    cuda = types.SimpleNamespace(
        is_available=lambda: cuda_available,
        get_device_properties=lambda index: types.SimpleNamespace(
            total_memory=memory_gib * 1024**3
        ),
    )
    module.cuda = cuda
    return module


class VerifyGpuTests(unittest.TestCase):
    def test_refuses_when_license_policy_missing(self) -> None:
        with mock.patch.dict(os.environ, {"META_TRAINER_ENABLED": "1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "licensed-only"):
                verify_gpu()

    def test_refuses_when_torch_is_not_installed(self) -> None:
        with mock.patch.dict(os.environ, ENABLED_ENV, clear=True), mock.patch.dict(
            sys.modules, {"torch": None}
        ):
            with self.assertRaisesRegex(RuntimeError, "pinned QLoRA dependencies"):
                verify_gpu()

    def test_refuses_when_cuda_is_unavailable(self) -> None:
        with mock.patch.dict(os.environ, ENABLED_ENV, clear=True), mock.patch.dict(
            sys.modules, {"torch": fake_torch(cuda_available=False)}
        ):
            with self.assertRaisesRegex(RuntimeError, "CUDA is unavailable"):
                verify_gpu()

    def test_refuses_non_allowlisted_small_gpu(self) -> None:
        with mock.patch.dict(os.environ, ENABLED_ENV, clear=True), mock.patch.dict(
            sys.modules, {"torch": fake_torch(memory_gib=16)}
        ):
            with self.assertRaisesRegex(RuntimeError, "less than the required 24 GiB"):
                verify_gpu()

    def test_accepts_allowlisted_gpu(self) -> None:
        with mock.patch.dict(os.environ, ENABLED_ENV, clear=True), mock.patch.dict(
            sys.modules, {"torch": fake_torch(memory_gib=24)}
        ):
            self.assertIsNone(verify_gpu())


def decision_record(**record: object) -> dict:
    base = {
        "task_kind": "relevance",
        "input": {"query": "agent"},
        "output": {"relevant": True},
    }
    base.update(record)
    return {"kind": "meta_decision", "split": "train", "record": base}


class TrainingTextTests(unittest.TestCase):
    def test_meta_decision_format_is_stable(self) -> None:
        text = _training_text(decision_record())
        assert text is not None
        self.assertTrue(text.startswith("<|meta_task|>relevance\n<|input|>"))
        self.assertIn('"query": "agent"', text)
        self.assertIn("\n<|response|>", text)

    def test_non_train_split_and_unknown_kind_are_skipped(self) -> None:
        self.assertIsNone(_training_text({**decision_record(), "split": "holdout"}))
        self.assertIsNone(_training_text({"kind": "mystery", "split": "train", "record": {}}))
        self.assertIsNone(_training_text({"kind": "meta_decision", "split": "train"}))

    def test_meta_replay_targets_preference_and_flags(self) -> None:
        text = _training_text(
            {
                "kind": "meta_replay",
                "split": "train",
                "record": {
                    "task_id": "task-1",
                    "source_domain": "example.test",
                    "topic_family": "retrieval",
                    "baseline_score": 0.2,
                    "candidate_score": 0.9,
                    "fact_correct": True,
                    "safety_passed": True,
                },
            }
        )
        assert text is not None
        self.assertIn("<|meta_task|>replay_preference", text)
        response = json.loads(text.split("<|response|>", 1)[1])
        self.assertEqual(
            response,
            {
                "candidate_preferred": True,
                "fact_correct": True,
                "safety_passed": True,
            },
        )

    def test_meta_replay_candidate_not_preferred_when_scores_tie(self) -> None:
        text = _training_text(
            {
                "kind": "meta_replay",
                "split": "train",
                "record": {"baseline_score": 0.5, "candidate_score": 0.5},
            }
        )
        assert text is not None
        response = json.loads(text.split("<|response|>", 1)[1])
        self.assertEqual(
            response,
            {
                "candidate_preferred": False,
                "fact_correct": False,
                "safety_passed": False,
            },
        )

    def test_expert_route_format(self) -> None:
        text = _training_text(
            {
                "kind": "expert_route",
                "split": "train",
                "record": {
                    "record_kind": "meta_decision",
                    "task_kind": "relevance",
                    "source_domain": "example.test",
                    "topic_family": "retrieval",
                    "target_expert_id": "retrieval",
                    "confidence": 0.9,
                    "status": "assigned",
                    "reason_codes": ["task_kind_mapping"],
                },
            }
        )
        assert text is not None
        self.assertIn("<|meta_task|>expert_route", text)
        target = json.loads(text.split("<|response|>", 1)[1])
        self.assertEqual(
            target,
            {"expert_id": "retrieval", "confidence": 0.9, "status": "assigned"},
        )
        input_value = json.loads(text.split("<|input|>", 1)[1].split("\n<|response|>")[0])
        self.assertEqual(input_value["reason_codes"], ["task_kind_mapping"])


class MetacognitionFewshotTests(unittest.TestCase):
    """META_METACOGNITION_FEWSHOT prepends the pinned evaluation surface."""

    def setUp(self) -> None:
        trainer._metacognition_fewshot_cache.clear()

    def tearDown(self) -> None:
        trainer._metacognition_fewshot_cache.clear()

    @staticmethod
    def metacognition_record() -> dict:
        return decision_record(
            task_kind="temporal_grounding",
            input={"query": "q", "environment": {"now": "2026-06-18T10:00:00+08:00"}},
            output={"action": "answer", "answer": "a"},
        )

    @staticmethod
    def legacy_render() -> str:
        record = MetacognitionFewshotTests.metacognition_record()["record"]
        return (
            "<|meta_task|>temporal_grounding\n"
            "<|input|>" + json.dumps(record["input"], sort_keys=True, ensure_ascii=False) + "\n"
            "<|response|>" + json.dumps(record["output"], sort_keys=True, ensure_ascii=False)
        )

    @staticmethod
    def write_fixture(directory: str) -> Path:
        exemplar = {
            "input": {"query": "exemplar-q",
                      "environment": {"now": "2026-01-01T00:00:00+08:00"}},
            "output": {"action": "search_internal", "query": "sq"},
        }
        path = Path(directory) / "fewshot.json"
        path.write_text(
            json.dumps({"exemplars": {"tg": [exemplar], "kb": [], "st": []}},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_unset_env_keeps_legacy_single_shot_render(self) -> None:
        with mock.patch.dict(os.environ):
            os.environ.pop("META_METACOGNITION_FEWSHOT", None)
            text = _training_text(self.metacognition_record())
        self.assertEqual(text, self.legacy_render())

    def test_fewshot_prefix_precedes_record_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.write_fixture(directory)
            exemplar = json.loads(fixture.read_text(encoding="utf-8"))["exemplars"]["tg"][0]
            with mock.patch.dict(os.environ, {"META_METACOGNITION_FEWSHOT": str(fixture)}):
                text = _training_text(self.metacognition_record())
        prefix = (
            "<|meta_task|>temporal_grounding\n"
            "<|input|>" + json.dumps(exemplar["input"], sort_keys=True, ensure_ascii=False) + "\n"
            "<|response|>" + json.dumps(exemplar["output"], sort_keys=True, ensure_ascii=False) + "\n"
        )
        self.assertEqual(text, prefix + self.legacy_render())

    def test_non_metacognition_kind_never_prefixed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.write_fixture(directory)
            with mock.patch.dict(os.environ, {"META_METACOGNITION_FEWSHOT": str(fixture)}):
                text = _training_text(decision_record())
        assert text is not None
        self.assertTrue(text.startswith("<|meta_task|>relevance\n<|input|>"))

    def test_unreadable_fewshot_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "missing.json")
            with mock.patch.dict(os.environ, {"META_METACOGNITION_FEWSHOT": missing}):
                with self.assertRaisesRegex(RuntimeError, "META_METACOGNITION_FEWSHOT"):
                    _training_text(self.metacognition_record())


class LoadTrainingRecordsTests(unittest.TestCase):
    def test_skips_blank_lines_and_unusable_records(self) -> None:
        dataset = (
            b"\n"
            + json.dumps(decision_record()).encode()
            + b"\n"
            + json.dumps({**decision_record(), "split": "holdout"}).encode()
            + b"\n"
        )
        self.assertEqual(len(_load_training_records(dataset)), 1)

    def test_invalid_jsonl_reports_line_number(self) -> None:
        dataset = json.dumps(decision_record()).encode() + b"\nnot-json\n"
        with self.assertRaisesRegex(RuntimeError, "invalid dataset JSONL at line 2"):
            _load_training_records(dataset)

    def test_non_object_line_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "line 1 is not an object"):
            _load_training_records(b"[1, 2]\n")

    def test_empty_training_split_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "no usable records"):
            _load_training_records(b"")


class DeterministicArchiveTests(unittest.TestCase):
    def test_zip_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.txt").write_text("x", encoding="utf-8")
            try:
                (root / "link.txt").symlink_to(root / "target.txt")
            except OSError:
                self.skipTest("symlink creation is not permitted on this host")
            with self.assertRaisesRegex(RuntimeError, "must not contain symlinks"):
                _deterministic_zip(root)

    def test_zip_uses_fixed_timestamps_and_sorted_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z.txt").write_text("z", encoding="utf-8")
            (root / "a.txt").write_text("a", encoding="utf-8")
            artifact = _deterministic_zip(root)
            with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
                self.assertEqual(archive.namelist(), ["a.txt", "z.txt"])
                for info in archive.infolist():
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))

    def test_tar_is_deterministic_regardless_of_insertion_order(self) -> None:
        first = _deterministic_tar({"b/x": b"2", "a/x": b"1"})
        second = _deterministic_tar({"a/x": b"1", "b/x": b"2"})
        self.assertEqual(first, second)
        with tarfile.open(fileobj=io.BytesIO(first), mode="r:") as archive:
            self.assertEqual(archive.getnames(), ["a/x", "b/x"])
            for member in archive.getmembers():
                self.assertEqual(member.mtime, 0)
                self.assertEqual(member.uid, 0)
                self.assertEqual(member.mode, 0o644)

    def test_tar_rejects_unsafe_paths(self) -> None:
        absolute = (Path.cwd().drive + "/absolute") if os.name == "nt" else "/absolute"
        for name in ("../escape", "a/../../escape", absolute):
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, "path is unsafe"):
                    _deterministic_tar({name: b"x"})


class FakeTokenizer:
    instance: "FakeTokenizer | None" = None

    def __init__(self) -> None:
        self.pad_token_id = None
        self.eos_token = "<eos>"
        self.pad_token = None
        self.max_lengths: list[int] = []
        FakeTokenizer.instance = self

    def __call__(self, text, truncation, max_length, add_special_tokens):
        self.max_lengths.append(max_length)
        return {"input_ids": [1, 2]}

    def save_pretrained(self, directory) -> None:
        Path(directory).mkdir(parents=True, exist_ok=True)
        Path(directory, "tokenizer.json").write_text("{}", encoding="utf-8")


class FakeModel:
    instance: "FakeModel | None" = None

    def __init__(self) -> None:
        self.config = types.SimpleNamespace(use_cache=True)
        self.saved: tuple[str, bool] | None = None
        FakeModel.instance = self

    def save_pretrained(self, directory, safe_serialization=False) -> None:
        self.saved = (str(directory), safe_serialization)
        Path(directory).mkdir(parents=True, exist_ok=True)
        Path(directory, "adapter_model.safetensors").write_bytes(b"weights")


class CapturedCall:
    def __init__(self) -> None:
        self.kwargs: dict = {}


def build_fake_training_stack(capture: dict) -> dict:
    """Fake accelerate/bitsandbytes/peft/torch/transformers for train_qlora."""

    torch_module = fake_torch()
    torch_module.__version__ = "2.0.0"
    torch_module.bfloat16 = "bfloat16"
    utils_module = types.ModuleType("torch.utils")
    data_module = types.ModuleType("torch.utils.data")

    class Dataset:
        pass

    data_module.Dataset = Dataset
    utils_module.data = data_module
    torch_module.utils = utils_module

    peft_module = types.ModuleType("peft")
    peft_module.__version__ = "0.10.0"

    class LoraConfig:
        def __init__(self, **kwargs):
            capture["lora"] = kwargs

    def prepare_model_for_kbit_training(model, use_gradient_checkpointing=False):
        capture["gradient_checkpointing"] = use_gradient_checkpointing
        return model

    def get_peft_model(model, config):
        return model

    peft_module.LoraConfig = LoraConfig
    peft_module.get_peft_model = get_peft_model
    peft_module.prepare_model_for_kbit_training = prepare_model_for_kbit_training

    transformers_module = types.ModuleType("transformers")
    transformers_module.__version__ = "4.40.0"

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(model, **kwargs):
            capture["tokenizer_from_pretrained"] = (model, kwargs)
            return FakeTokenizer()

    class AutoModelForCausalLM:
        @staticmethod
        def from_pretrained(model, **kwargs):
            capture["model_from_pretrained"] = (model, kwargs)
            return FakeModel()

    class BitsAndBytesConfig:
        def __init__(self, **kwargs):
            capture["quantization"] = kwargs

    class DataCollatorForLanguageModeling:
        def __init__(self, **kwargs):
            capture["collator"] = kwargs

    class TrainingArguments:
        def __init__(self, **kwargs):
            capture["training_arguments"] = kwargs

    class Trainer:
        def __init__(self, model, args, train_dataset, data_collator):
            capture["dataset_size"] = len(train_dataset)
            train_dataset[0]  # exercise tokenization with the configured max_length

        def train(self):
            return types.SimpleNamespace(metrics={"train_loss": 0.25})

    transformers_module.AutoTokenizer = AutoTokenizer
    transformers_module.AutoModelForCausalLM = AutoModelForCausalLM
    transformers_module.BitsAndBytesConfig = BitsAndBytesConfig
    transformers_module.DataCollatorForLanguageModeling = DataCollatorForLanguageModeling
    transformers_module.TrainingArguments = TrainingArguments
    transformers_module.Trainer = Trainer

    accelerate_module = types.ModuleType("accelerate")
    accelerate_module.__version__ = "0.29.0"
    bitsandbytes_module = types.ModuleType("bitsandbytes")
    bitsandbytes_module.__version__ = "0.43.0"

    return {
        "accelerate": accelerate_module,
        "bitsandbytes": bitsandbytes_module,
        "peft": peft_module,
        "torch": torch_module,
        "torch.utils": utils_module,
        "torch.utils.data": data_module,
        "transformers": transformers_module,
    }


def dataset_bytes(lines: int = 3) -> bytes:
    return b"".join(json.dumps(decision_record()).encode() + b"\n" for _ in range(lines))


class TrainQloraIdentityTests(unittest.TestCase):
    """Fail-closed identity checks run before any heavyweight import."""

    def setUp(self) -> None:
        self.verify = mock.patch(f"{MODULE}.verify_gpu").start()
        self.addCleanup(mock.patch.stopall)

    def test_base_model_mismatch_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"META_BASE_MODEL": "other/model"}, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "does not match the immutable job"):
                train_qlora(dataset_bytes(), {"dataset_hash": "0" * 64}, "test/model", Path(directory))

    def test_empty_base_model_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {}, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "does not match the immutable job"):
                train_qlora(dataset_bytes(), {"dataset_hash": "0" * 64}, "", Path(directory))

    def test_remote_pin_satisfies_identity(self) -> None:
        environment = {
            "META_BASE_MODEL_ID": "example/model",
            "META_BASE_MODEL_REVISION": "rev",
            "META_BASE_MODEL_SHA256": "0" * 64,
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, environment, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "no usable records"):
                train_qlora(b"", {"dataset_hash": "0" * 64}, "test/model", Path(directory))

    def test_model_path_identity_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory) / "model"
            model_dir.mkdir()
            with mock.patch.dict(
                os.environ, {"META_BASE_MODEL_PATH": str(model_dir)}, clear=True
            ):
                with self.assertRaisesRegex(RuntimeError, "no usable records"):
                    train_qlora(b"", {"dataset_hash": "0" * 64}, str(model_dir), Path(directory) / "out")


class TrainQloraConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verify = mock.patch(f"{MODULE}.verify_gpu").start()
        self.addCleanup(mock.patch.stopall)
        FakeTokenizer.instance = None
        FakeModel.instance = None

    def run_training(self, environment: dict, dataset: bytes | None = None):
        capture: dict = {}
        manifest = {"dataset_hash": hashlib.sha256(dataset or dataset_bytes()).hexdigest()}
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, environment, clear=True
        ), mock.patch.dict(sys.modules, build_fake_training_stack(capture)):
            output = train_qlora(
                dataset if dataset is not None else dataset_bytes(),
                manifest,
                "test/model-1b",
                Path(directory),
            )
        return output, capture, manifest

    def test_qlora_config_bounds_and_deterministic_artifact(self) -> None:
        environment = {
            "META_BASE_MODEL": "test/model-1b",
            "META_BASE_MODEL_REVISION": "rev-1",
            "CEREBELLUM_RUN_MAX_LENGTH": "999999",
            "CEREBELLUM_RUN_EPOCHS": "99",
            "CEREBELLUM_RUN_LORA_RANK": "8",
            "CEREBELLUM_RUN_LORA_ALPHA": "16",
            "CEREBELLUM_RUN_LORA_DROPOUT": "0.1",
            "CEREBELLUM_RUN_LEARNING_RATE": "0.001",
            "CEREBELLUM_RUN_GRADIENT_ACCUMULATION": "4",
            "META_LORA_TARGET_MODULES": " q_proj ,, v_proj ",
            "CEREBELLUM_ADAPTER_ROLE": "retrieval",
        }
        output, capture, manifest = self.run_training(environment)

        # Quantization contract: 4-bit nf4 with double quantization (qlora-24gb.example.yaml).
        quantization = capture["quantization"]
        self.assertTrue(quantization["load_in_4bit"])
        self.assertEqual(quantization["bnb_4bit_quant_type"], "nf4")
        self.assertTrue(quantization["bnb_4bit_use_double_quant"])

        # LoRA config honors run overrides and trims empty target modules.
        lora = capture["lora"]
        self.assertEqual(lora["r"], 8)
        self.assertEqual(lora["lora_alpha"], 16)
        self.assertEqual(lora["lora_dropout"], 0.1)
        self.assertEqual(lora["target_modules"], ["q_proj", "v_proj"])
        self.assertTrue(capture["gradient_checkpointing"])

        # Sequence length and epochs are clamped to their bounds.
        arguments = capture["training_arguments"]
        self.assertEqual(arguments["num_train_epochs"], 3)
        self.assertEqual(arguments["gradient_accumulation_steps"], 4)
        self.assertEqual(arguments["learning_rate"], 0.001)
        self.assertEqual(arguments["seed"], 17)
        self.assertEqual(arguments["data_seed"], 17)
        self.assertTrue(arguments["bf16"])
        self.assertFalse(arguments["fp16"])
        self.assertEqual(arguments["optim"], "paged_adamw_8bit")
        self.assertEqual(arguments["save_strategy"], "no")
        tokenizer = FakeTokenizer.instance
        assert tokenizer is not None
        self.assertTrue(tokenizer.max_lengths)
        self.assertTrue(all(length == 8192 for length in tokenizer.max_lengths))
        self.assertEqual(tokenizer.pad_token, "<eos>")
        self.assertEqual(capture["dataset_size"], 3)

        # Non-local base model passes the pinned revision through.
        model_call = capture["model_from_pretrained"]
        self.assertEqual(model_call[1]["revision"], "rev-1")
        self.assertFalse(model_call[1]["trust_remote_code"])
        model = FakeModel.instance
        assert model is not None
        self.assertFalse(model.config.use_cache)
        assert model.saved is not None
        self.assertTrue(model.saved[1])

        # Artifact is a deterministic zip carrying the run manifest.
        self.assertIsInstance(output.artifact, bytes)
        self.assertGreater(len(output.artifact), 0)
        with zipfile.ZipFile(io.BytesIO(output.artifact)) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            self.assertIn("adapter_model.safetensors", names)
            self.assertIn("tokenizer.json", names)
            run_manifest = json.loads(archive.read("cerebellum-training-manifest.json"))
        self.assertEqual(run_manifest["schema_version"], "cerebellum/v1")
        self.assertEqual(run_manifest["kind"], "meta_qlora_adapter_v1")
        self.assertEqual(run_manifest["dataset_hash"], manifest["dataset_hash"])
        self.assertEqual(run_manifest["training_records"], 3)
        self.assertEqual(run_manifest["max_length"], 8192)
        self.assertEqual(run_manifest["lora"]["r"], 8)
        self.assertEqual(run_manifest["lora"]["target_modules"], ["q_proj", "v_proj"])
        self.assertEqual(run_manifest["train_loss"], 0.25)
        self.assertEqual(run_manifest["adapter_role"], "retrieval")
        self.assertFalse(run_manifest["automatic_activation_metrics_included"])
        self.assertEqual(
            set(run_manifest["libraries"]),
            {"accelerate", "bitsandbytes", "peft", "torch", "transformers"},
        )

        # Metrics are diagnostic zeros; activation comes from shadow replay, not the worker.
        self.assertEqual(
            output.metrics,
            {
                "old_task_retention": 0.0,
                "ndcg_at_10": 0.0,
                "baseline_ndcg_at_10": 0.0,
                "max_core_topic_regression": 0.0,
                "fact_precision_delta": 0.0,
                "policy_violations": 0,
                "injection_regression": False,
                "cost_per_useful_card_change": 0.0,
            },
        )

    def test_lower_bounds_and_defaults(self) -> None:
        environment = {"META_BASE_MODEL": "test/model-1b", "CEREBELLUM_RUN_MAX_LENGTH": "8"}
        _, capture, _ = self.run_training(environment)
        tokenizer = FakeTokenizer.instance
        assert tokenizer is not None
        self.assertTrue(all(length == 256 for length in tokenizer.max_lengths))
        arguments = capture["training_arguments"]
        self.assertEqual(arguments["num_train_epochs"], 1)
        self.assertEqual(arguments["learning_rate"], 0.0002)
        self.assertEqual(arguments["gradient_accumulation_steps"], 16)
        self.assertEqual(capture["lora"]["r"], 16)
        self.assertEqual(
            capture["lora"]["target_modules"], ["q_proj", "k_proj", "v_proj", "o_proj"]
        )

    def test_deterministic_artifact_bytes(self) -> None:
        environment = {"META_BASE_MODEL": "test/model-1b"}
        first, _, _ = self.run_training(environment)
        second, _, _ = self.run_training(environment)
        self.assertEqual(first.artifact, second.artifact)


def routed_manifest(**plan_overrides: object) -> dict:
    plan = {
        "architecture": "routed_lora",
        "expert_view_id": "view-1",
        "train_router": True,
        "train_shared": True,
        "expert_ids": ["retrieval"],
        "router_top_k": 1,
        "fallback_expert_id": "shared",
    }
    plan.update(plan_overrides)
    return {
        "routed_training": {
            "snapshot_id": "snap-1",
            "taxonomy_hash": "a" * 64,
            "base_model": {"model_id": "example/model"},
            "expert_plan": plan,
        }
    }


class RoutedTrainingValidationTests(unittest.TestCase):
    def run_routed(self, manifest: dict, datasets: dict | None = None) -> None:
        datasets = datasets or {
            "router": dataset_bytes(1),
            "shared": dataset_bytes(1),
            "retrieval": dataset_bytes(1),
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            f"{MODULE}.train_qlora",
            side_effect=lambda *args: TrainingOutput(b"artifact", {"ok": 1}),
        ):
            with self.assertRaises(RuntimeError):
                train_routed_qlora(datasets, manifest, "example/model", Path(directory))

    def test_missing_context_is_rejected(self) -> None:
        self.run_routed({})

    def test_invalid_plan_or_pin_is_rejected(self) -> None:
        self.run_routed({"routed_training": {"expert_plan": None, "base_model": {}}})
        self.run_routed({"routed_training": {"expert_plan": {}, "base_model": "model"}})

    def test_requires_top1_routed_architecture(self) -> None:
        self.run_routed(routed_manifest(architecture="dense"))
        self.run_routed(routed_manifest(router_top_k=2))

    def test_expert_selection_validation(self) -> None:
        self.run_routed(routed_manifest(expert_ids=["retrieval", "retrieval"]))
        self.run_routed(routed_manifest(fallback_expert_id=""))
        self.run_routed(
            routed_manifest(train_router=False, train_shared=False, expert_ids=[])
        )
        self.run_routed(routed_manifest(expert_ids="retrieval"))

    def test_role_collision_with_fallback_is_rejected(self) -> None:
        # train_shared adds the fallback id; an expert list repeating it collides.
        self.run_routed(routed_manifest(expert_ids=["shared"]))

    def test_missing_role_dataset_is_rejected(self) -> None:
        self.run_routed(routed_manifest(), datasets={"router": dataset_bytes(1)})


class RoutedTrainingBehaviorTests(unittest.TestCase):
    def test_role_environment_is_restored_after_each_expert(self) -> None:
        seen_roles: list[str] = []

        def fake_train(dataset, role_manifest, base_model, output):
            seen_roles.append(os.environ.get("CEREBELLUM_ADAPTER_ROLE"))
            return TrainingOutput(b"artifact", {"ok": 1})

        datasets = {
            "router": dataset_bytes(1),
            "shared": dataset_bytes(1),
            "retrieval": dataset_bytes(1),
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"CEREBELLUM_ADAPTER_ROLE": "dense"}, clear=True
        ), mock.patch(f"{MODULE}.train_qlora", side_effect=fake_train):
            train_routed_qlora(datasets, routed_manifest(), "example/model", Path(directory))
            self.assertEqual(os.environ["CEREBELLUM_ADAPTER_ROLE"], "dense")
        self.assertEqual(seen_roles, ["router", "shared", "retrieval"])

    def test_role_environment_is_restored_on_failure(self) -> None:
        def failing_train(dataset, role_manifest, base_model, output):
            raise RuntimeError("boom")

        datasets = {"router": dataset_bytes(1), "shared": dataset_bytes(1), "retrieval": dataset_bytes(1)}
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {}, clear=True
        ), mock.patch(f"{MODULE}.train_qlora", side_effect=failing_train):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                train_routed_qlora(datasets, routed_manifest(), "example/model", Path(directory))
            self.assertNotIn("CEREBELLUM_ADAPTER_ROLE", os.environ)

    def test_bundle_is_deterministic_and_manifest_is_verified(self) -> None:
        per_role_records: dict[str, int] = {}

        def fake_train(dataset, role_manifest, base_model, output):
            role = os.environ["CEREBELLUM_ADAPTER_ROLE"]
            artifact = f"weights:{role}".encode()
            per_role_records[role] = dataset.count(b"\n")
            return TrainingOutput(artifact, {"policy_violations": 0})

        datasets = {
            "router": dataset_bytes(5),
            "shared": dataset_bytes(7),
            "retrieval": dataset_bytes(11),
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            f"{MODULE}.train_qlora", side_effect=fake_train
        ):
            first = train_routed_qlora(datasets, routed_manifest(), "example/model", Path(directory))
            second = train_routed_qlora(datasets, routed_manifest(), "example/model", Path(directory))
        self.assertEqual(first.artifact, second.artifact)
        self.assertEqual(first.metrics, {"policy_violations": 0})
        with tarfile.open(fileobj=io.BytesIO(first.artifact), mode="r:") as archive:
            routed = json.loads(
                archive.extractfile("cerebellum-routed-adapter-manifest.json").read()
            )
            for entry in routed["experts"] + [routed["router"]]:
                stored = archive.extractfile(entry["path"]).read()
                self.assertEqual(hashlib.sha256(stored).hexdigest(), entry["sha256"])
                self.assertEqual(len(stored), entry["byte_length"])
        self.assertEqual(routed["kind"], "routed_lora_bundle_v1")
        self.assertEqual(routed["fallback_expert_id"], "shared")
        self.assertEqual(routed["router_top_k"], 1)
        self.assertEqual(routed["router"]["training_records"], 5)
        records = {item["expert_id"]: item["training_records"] for item in routed["experts"]}
        self.assertEqual(records, {"retrieval": 11, "shared": 7})
        self.assertEqual([item["expert_id"] for item in routed["experts"]], ["retrieval", "shared"])


if __name__ == "__main__":
    unittest.main()
