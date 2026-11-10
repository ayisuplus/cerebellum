#!/usr/bin/env python3
"""Reward-scorer gold-arm tests: the gold output of every generator arm must
score 1.0, the canonical wrong action 0.0, and contract-invalid input 0.0.
Scoring goes through probe.py itself, pinning reward semantics to eval
semantics."""
from __future__ import annotations

import json
import unittest

from cerebellum_meta_training.meta_reward import score_completion

NOW = "2026-06-18T02:00:00Z"

KB_KNOWN_GOLD = {"action": "answer", "answer": "22", "answer_basis": "parametric",
                 "as_of_used": NOW, "confidence": 0.85, "freshness_hours": None, "query": None}
KB_UNKNOWN_GOLD = {"action": "search_internal", "answer": None, "answer_basis": "none",
                   "as_of_used": NOW, "confidence": 0.75, "freshness_hours": None,
                   "query": "2026 年图灵奖得主"}
KB_INVENTED_GOLD = {"action": "insufficient", "answer": None, "answer_basis": "none",
                    "as_of_used": NOW, "confidence": 0.8, "freshness_hours": None, "query": None}
TG_FRESH_GOLD = dict(KB_KNOWN_GOLD, answer="32GB GDDR7", answer_basis="evidence", confidence=0.9)
TG_STALE_GOLD = dict(KB_UNKNOWN_GOLD, confidence=0.8, freshness_hours=1403,
                     query="RTX 5090 VRAM specification")
ST_FRESH_GOLD = dict(TG_FRESH_GOLD, answer="《哪吒之魔童闹海》")
ST_EMPTY_GOLD = dict(KB_KNOWN_GOLD, answer="当前无在轨任务", answer_basis="evidence")


def render(output: dict) -> str:
    return json.dumps(output, ensure_ascii=False)


class GoldArmTests(unittest.TestCase):
    def test_gold_outputs_score_one(self) -> None:
        for gold in (KB_KNOWN_GOLD, KB_UNKNOWN_GOLD, KB_INVENTED_GOLD,
                     TG_FRESH_GOLD, TG_STALE_GOLD, ST_FRESH_GOLD, ST_EMPTY_GOLD):
            with self.subTest(action=gold["action"], answer=gold["answer"]):
                result = score_completion(gold, render(gold))
                self.assertEqual(result["reward"], 1.0, result)
                self.assertTrue(result["contract_valid"])

    def test_wrong_action_scores_zero(self) -> None:
        # known answered with refusal
        self.assertEqual(score_completion(KB_KNOWN_GOLD, render(KB_UNKNOWN_GOLD))["reward"], 0.0)
        # unknown answered with a hallucination (the W1 failure mode)
        hallucination = dict(KB_KNOWN_GOLD, answer="Yann LeCun", query=None)
        self.assertEqual(score_completion(KB_UNKNOWN_GOLD, render(hallucination))["reward"], 0.0)
        # invented answered with search instead of insufficient
        self.assertEqual(score_completion(KB_INVENTED_GOLD, render(KB_UNKNOWN_GOLD))["reward"], 0.0)
        # stale answered from the stale card
        stale_answer = dict(KB_KNOWN_GOLD, answer="32GB GDDR7", answer_basis="evidence")
        self.assertEqual(score_completion(TG_STALE_GOLD, render(stale_answer))["reward"], 0.0)

    def test_wrong_answer_text_scores_zero(self) -> None:
        wrong = dict(KB_KNOWN_GOLD, answer="23")
        result = score_completion(KB_KNOWN_GOLD, render(wrong))
        self.assertEqual(result["reward"], 0.0)
        self.assertFalse(result["answer_match"])

    def test_as_of_mismatch_scores_zero(self) -> None:
        wrong = dict(KB_KNOWN_GOLD, as_of_used="1999-01-01T00:00:00Z")
        result = score_completion(KB_KNOWN_GOLD, render(wrong))
        self.assertEqual(result["reward"], 0.0)
        self.assertFalse(result["as_of_match"])

    def test_contract_invalid_scores_zero(self) -> None:
        result = score_completion(KB_KNOWN_GOLD, "the answer is 22, obviously")
        self.assertEqual(result["reward"], 0.0)
        self.assertFalse(result["parsed"])

    def test_discipline_invalid_scores_zero(self) -> None:
        # answer action without an answer field value fails discipline
        broken = dict(KB_KNOWN_GOLD, answer=None)
        result = score_completion(KB_KNOWN_GOLD, render(broken))
        self.assertEqual(result["reward"], 0.0)
        self.assertFalse(result["contract_valid"])

    def test_extra_text_around_json_still_parses(self) -> None:
        # parse_contract extracts the first JSON object; trailing tokens are tolerated
        result = score_completion(KB_KNOWN_GOLD, render(KB_KNOWN_GOLD) + "\nextra reasoning")
        self.assertEqual(result["reward"], 1.0)


if __name__ == "__main__":
    unittest.main()
