"""Control-arm boundaries and an opt-in, real CPU Trainer resume check."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cerebellum_meta_training.trainer import (
    _adapter_hash, _controlled_trainer, _resume_control,
    _supervised_batch, _supervised_features, _training_text, _training_seed,
)


class CharacterTokenizer:
    eos_token_id = pad_token_id = 0

    def __call__(self, text, add_special_tokens=False):
        assert not add_special_tokens
        return {"input_ids": [ord(character) + 1 for character in text]}


def record(query):
    return {"kind": "meta_decision", "split": "train", "record": {
        "decision_id": query, "task_kind": "knowledge_boundary",
        "input": {"query": query}, "output": {"answer": "中文\n答案<|response|>"}}}


class SupervisedControlTests(unittest.TestCase):
    def test_seed_override_is_scoped_to_supervised_experiments(self):
        with patch.dict(os.environ, {"CEREBELLUM_RUN_SEED": "23"}):
            self.assertEqual(_training_seed("split_response"), 23)
            self.assertEqual(_training_seed(None), 17)
        for value in ("-1", "4294967296", "invalid"):
            with patch.dict(os.environ, {"CEREBELLUM_RUN_SEED": value}), self.assertRaises(ValueError):
                _training_seed("split_response")

    def test_structured_boundary_padding_and_exact_length(self):
        tokenizer = CharacterTokenizer()
        values = [record("中文\n输入<|response|>还有内容"), record("short")]
        data = "\n".join(json.dumps(value) for value in values).encode()
        with patch.dict(os.environ, {"META_METACOGNITION_FEWSHOT": ""}):
            full, _ = _supervised_features(data, tokenizer, "split_full", 2048)
            response, evidence = _supervised_features(data, tokenizer, "split_response", 2048)
            joint, _ = _supervised_features(data, tokenizer, "joint_full", 2048)
            self.assertEqual(joint, full)  # Character tokens cannot merge across a boundary.
            for value, before, after, counts in zip(values, full, response, evidence):
                self.assertEqual(before["input_ids"], after["input_ids"])
                self.assertEqual(before["attention_mask"], after["attention_mask"])
                answer = json.dumps(value["record"]["output"], sort_keys=True, ensure_ascii=False)
                prefix = _training_text(value)[:-len(answer)]
                self.assertEqual(after["input_ids"][:len(prefix)], tokenizer(prefix)["input_ids"])
                self.assertEqual(after["labels"][:len(prefix)], [-100] * len(prefix))
                self.assertEqual(after["labels"][len(prefix):], tokenizer(answer)["input_ids"] + [0])
                self.assertEqual(counts["supervised_tokens"], len(answer) + 1)
            width = max(len(row["input_ids"]) for row in response)
            _supervised_features(data, tokenizer, "split_response", width)
            with self.assertRaisesRegex(ValueError, "truncation forbidden"):
                _supervised_features(data, tokenizer, "split_response", width - 1)
        batch = _supervised_batch(response, 0)
        for row, labels, attention in zip(response, batch["labels"], batch["attention_mask"]):
            self.assertEqual(labels[len(row["input_ids"]) - 1], 0)
            self.assertTrue(all(label == -100 for label, mask in zip(labels, attention) if mask == 0))
        with self.assertRaises(ValueError):
            _supervised_features(data, tokenizer, "typo", 2048)
        with self.assertRaises(ValueError):
            _supervised_features(b"", tokenizer, "split_response", 2048)

    @unittest.skipUnless(os.environ.get("CEREBELLUM_TEST_NATIVE_TRAINER") == "1", "opt-in native CPU check")
    def test_native_resume_matches_uninterrupted_updates(self):
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import Qwen2Config, Qwen2ForCausalLM, TrainingArguments, TrainerCallback, set_seed
        torch.set_num_threads(2)
        features = [{"input_ids": [1, 2, 3, 4, i + 5, 0], "attention_mask": [1] * 6,
                     "labels": [-100, -100, -100, 4, i + 5, 0], "source_record_id": str(i)} for i in range(8)]
        binding = {"data": "fixed", "config": "fixed"}

        def create(folder):
            set_seed(17)
            model = get_peft_model(Qwen2ForCausalLM(Qwen2Config(vocab_size=32, hidden_size=16,
                intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)),
                LoraConfig(r=2, lora_alpha=4, lora_dropout=0, target_modules=["q_proj"], task_type="CAUSAL_LM"))
            args = TrainingArguments(output_dir=str(folder / "checkpoints"), use_cpu=True,
                max_steps=4, per_device_train_batch_size=1, gradient_accumulation_steps=2,
                save_strategy="steps", save_steps=2, report_to=[], learning_rate=0.01,
                dataloader_pin_memory=False, remove_unused_columns=False, disable_tqdm=True,
                seed=17, data_seed=17, logging_steps=1)
            return model, _controlled_trainer(model, args, features, [], CharacterTokenizer(), binding, folder)

        class StopAtTwo(TrainerCallback):
            def on_step_end(self, args, state, control, **kwargs):
                if state.global_step == 2:
                    control.should_training_stop = True

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CEREBELLUM_RUN_RESUME_FROM_CHECKPOINT", None)
            root = Path(directory)
            model, (trainer, whole, _, _) = create(root / "whole")
            self.assertGreater(trainer.evaluate()["eval_loss"], 0)
            self.assertEqual(whole["updates"], [])
            trainer.train()
            expected_hash = _adapter_hash(model)
            _, (trainer, partial, _, _) = create(root / "resumed")
            trainer.add_callback(StopAtTwo())
            trainer.train()
            checkpoint = root / "resumed/checkpoints/checkpoint-2"
            self.assertEqual(partial["global_step"], 2)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                _resume_control(root / "resumed", str(checkpoint), {"data": "changed"})
            os.environ["CEREBELLUM_RUN_RESUME_FROM_CHECKPOINT"] = str(checkpoint)
            model, (trainer, resumed, _, resume) = create(root / "resumed")
            trainer.train(resume_from_checkpoint=resume)
            self.assertEqual(resumed["global_step"], 4)
            self.assertEqual(resumed["updates"], whole["updates"])
            self.assertEqual(_adapter_hash(model), expected_hash)
            self.assertEqual(sum(len(row["records"]) for row in resumed["updates"]), 8)


if __name__ == "__main__":
    unittest.main()
