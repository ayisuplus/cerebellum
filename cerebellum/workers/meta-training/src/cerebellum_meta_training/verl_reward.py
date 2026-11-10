"""verl-facing reward adapter (W2). verl's naive reward manager calls
compute_score(data_source, solution_str, ground_truth, extra_info); the heavy
lifting lives in meta_reward.score_completion, which reuses probe.py so reward
semantics == eval semantics."""
from __future__ import annotations

import json

from cerebellum_meta_training.meta_reward import score_completion


def compute_score(data_source: str, solution_str: str, ground_truth: str,
                  extra_info: dict | None = None, **_kwargs) -> dict:
    result = score_completion(json.loads(ground_truth), solution_str)
    return {"score": result["reward"], "contract_valid": result["contract_valid"],
            "correct": result["correct"]}
