"""Verified-reward scorer for W2 boundary RL (metacognition adapter 2.0.0).

Rewards are programmatic and deterministic: a completion earns 1.0 iff it is
contract-valid AND fully correct against the generator's gold, using the SAME
code the frozen evaluation harness uses (benchmarks/metacognition/probe.py,
imported by path; stdlib+requests only, no server). Reward semantics == eval
semantics by construction; there is no learned reward model.

Correctness mirrors probe.score_item's fully_correct: action match, as_of_used
echo match, and — for answer golds — gold-token containment. Gold answer token
groups derive from the gold answer itself via probe.norm (alphanumeric/CJK
casefolded), the same rule W1's pool verification used.
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_PATH = REPO / "benchmarks" / "metacognition" / "probe.py"


@lru_cache(maxsize=1)
def _probe():
    spec = importlib.util.spec_from_file_location("metacognition_probe", PROBE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load probe module from {PROBE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_completion(gold_output: dict, completion: str) -> dict:
    """Score one sampled completion against the gold decision output."""
    probe = _probe()
    pred, error = probe.parse_contract(completion)
    contract_valid = bool(error is None and pred is not None and probe.discipline_ok(pred))
    if pred is None:
        return {"reward": 0.0, "parsed": False, "contract_valid": False, "correct": False}
    check: dict = {}
    if gold_output.get("action") == "answer" and gold_output.get("answer"):
        check["answer_contains"] = [probe.norm(gold_output["answer"])]
    scores = probe.score_item({"gold": gold_output, "check": check}, pred, contract_valid)
    correct = bool(contract_valid and scores["fully_correct"])
    return {
        "reward": 1.0 if correct else 0.0,
        "parsed": True,
        "contract_valid": contract_valid,
        "correct": correct,
        "action_match": scores["action_match"],
        "as_of_match": scores["as_of_match"],
        "answer_match": scores["answer_match"],
    }
