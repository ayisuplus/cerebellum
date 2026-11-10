#!/usr/bin/env python3
"""Cross-language surface parity: meta-training's few-shot render must be
byte-identical to the evaluation surface rendered by benchmarks/metacognition/
probe.py from the same manifest-pinned fewshot.json.

probe.py is imported by path; its module imports are stdlib + requests, so no
server is contacted.
"""
from __future__ import annotations

import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_meta_training import trainer
from cerebellum_meta_training.trainer import _training_text

REPO = Path(__file__).resolve().parents[3]
PROBE_PATH = REPO / "benchmarks" / "metacognition" / "probe.py"
FEWSHOT_PATH = REPO / "benchmarks" / "metacognition" / "fewshot.json"
KINDS = {"tg": "temporal_grounding", "kb": "knowledge_boundary", "st": "search_planning"}


def load_probe():
    spec = importlib.util.spec_from_file_location("metacognition_probe", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MetacognitionSurfaceParityTests(unittest.TestCase):
    def setUp(self) -> None:
        trainer._metacognition_fewshot_cache.clear()

    def tearDown(self) -> None:
        trainer._metacognition_fewshot_cache.clear()

    def test_training_text_matches_probe_render_byte_for_byte(self) -> None:
        probe = load_probe()
        with mock.patch.dict(os.environ, {"META_METACOGNITION_FEWSHOT": str(FEWSHOT_PATH)}):
            for short, task_kind in KINDS.items():
                with self.subTest(task_kind=task_kind):
                    record = {
                        "task_kind": task_kind,
                        "input": {
                            "query": "parity 查询: pinned surface?",
                            "environment": {
                                "now": "2026-06-18T10:00:00+08:00",
                                "registry_snapshot": "ab" * 32,
                                "timezone": "Asia/Shanghai",
                            },
                        },
                        "output": {
                            "action": "search_internal",
                            "answer": None,
                            "answer_basis": "none",
                            "as_of_used": "2026-06-18T02:00:00Z",
                            "confidence": 0.75,
                            "freshness_hours": None,
                            "query": "parity search query",
                        },
                    }
                    text = _training_text(
                        {"kind": "meta_decision", "split": "train", "record": record}
                    )
                    expected = probe.render_prompt(short, record["input"]) + json.dumps(
                        record["output"], sort_keys=True, ensure_ascii=False
                    )
                    self.assertEqual(text, expected)


class MetacognitionScoringTests(unittest.TestCase):
    def test_all_gold_outputs_are_correct(self) -> None:
        probe = load_probe()
        for kind in KINDS:
            for item in probe.load_suite(kind):
                with self.subTest(id=item["id"]):
                    pred, error = probe.parse_contract(json.dumps(item["gold"]))
                    self.assertIsNone(error)
                    score = probe.score_item(item, pred, probe.discipline_ok(pred))
                    self.assertTrue(score["fully_correct"])

    def test_shared_scoring_cases(self) -> None:
        probe = load_probe()
        fixtures = json.loads((PROBE_PATH.parent / "scoring-cases.json").read_text(encoding="utf-8"))
        self.assertEqual(fixtures["scoring_version"], probe.SCORING_VERSION)
        for group in fixtures["groups"]:
            rows = []
            for case in group["cases"]:
                pred, _ = probe.parse_contract(case["completion"])
                score = probe.score_item(case["probe"], pred, pred is not None and probe.discipline_ok(pred))
                rows.append({"item": case["probe"], "score": score})
                for key, expected in case["expected"].items():
                    with self.subTest(group=group["name"], id=case["probe"]["id"], field=key):
                        self.assertEqual(score[key], expected)
            metrics = probe.suite_metrics(group["kind"], rows)
            for key in ("with_environment", "without_environment", "fresh_answer_accuracy"):
                if isinstance(metrics.get(key), dict):
                    target = key if key.endswith("accuracy") else key + "_accuracy"
                    metrics[target] = metrics[key]["accuracy"]
            for key, expected in group["expected_metrics"].items():
                with self.subTest(group=group["name"], field=key):
                    if expected is None:
                        self.assertIsNone(metrics[key])
                    else:
                        self.assertIsNotNone(metrics[key])
                        self.assertAlmostEqual(metrics[key], expected)


if __name__ == "__main__":
    unittest.main()
