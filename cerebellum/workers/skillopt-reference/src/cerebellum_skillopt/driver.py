from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import UPSTREAM_COMMIT
from .adapter import CerebellumVerifyAdapter, EarlyStopRequested, required_env
from .harness import docker_available


def run_optimization(data_root: Path, payload: dict) -> dict:
    started = time.monotonic()
    docker_available()
    assert_pinned_inputs(payload)
    target_model = required_env("TARGET_MODEL")
    optimizer_model = required_env("OPTIMIZER_MODEL")
    api_key = required_env("API_KEY")
    base_url = required_env("OPENAI_COMPATIBLE_BASE_URL")
    if payload["target_model"] != target_model or payload["optimizer_model"] != optimizer_model:
        raise RuntimeError("job model roles do not match explicit environment configuration")
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = api_key
    os.environ["OPTIMIZER_OPENAI_COMPATIBLE_API_KEY"] = api_key
    os.environ["TARGET_OPENAI_COMPATIBLE_API_KEY"] = api_key
    os.environ["OPTIMIZER_OPENAI_COMPATIBLE_MODEL"] = optimizer_model
    os.environ["TARGET_OPENAI_COMPATIBLE_MODEL"] = target_model
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = base_url

    baseline = (data_root / "baseline.md").read_text(encoding="utf-8")
    out_root = data_root / "skillopt-output"
    cfg = skillopt_config(data_root, out_root, payload)
    adapter = CerebellumVerifyAdapter(
        str(data_root),
        payload["container_image_digest"],
        analyst_workers=1,
        minibatch_size=10,
        edit_budget=2,
        failure_only=False,
    )
    from skillopt.engine.trainer import ReflACTTrainer

    try:
        summary = ReflACTTrainer(cfg, adapter).train()
    except EarlyStopRequested:
        summary = read_json(out_root / "summary.json", default={})
        if not isinstance(summary, dict):
            summary = {}
    ledger = read_ledger(data_root / "adapter-ledger.jsonl")
    patches, evaluations, raw_to_canonical = build_candidates(
        payload, baseline, ledger, out_root, optimizer_model
    )
    passed = [evaluation for evaluation in evaluations if evaluation["gate_passed"]]
    best_evaluation = max(
        passed,
        key=lambda value: (value["candidate_hard_mean"], value["candidate_soft_mean"]),
        default=None,
    )
    best_patch = None
    holdout = None
    if best_evaluation is not None:
        best_patch = next(
            patch for patch in patches if patch["candidate_hash"] == best_evaluation["candidate_hash"]
        )
        raw_hash = next(
            raw for raw, canonical in raw_to_canonical.items() if canonical == best_evaluation["candidate_hash"]
        )
        candidate = next(row["skill_content"] for row in ledger if row["skill_hash"] == raw_hash)
        holdout = run_holdout(adapter, baseline, candidate, data_root / "holdout")

    optimizer_calls = optimizer_call_total(summary.get("token_summary", {}))
    if optimizer_calls == 0:
        optimizer_calls = count_optimizer_artifacts(out_root)
    total_tokens = adapter.agent.usage.tokens if adapter.agent else 0
    total_tokens += token_total(summary.get("token_summary", {}))
    budget = payload["budget"]
    if adapter.rollout_calls > int(budget["target_call_limit"]):
        raise RuntimeError("SkillOpt exceeded the target rollout budget")
    if optimizer_calls > int(budget["optimizer_call_limit"]):
        raise RuntimeError("SkillOpt exceeded the optimizer call budget")
    if total_tokens > int(budget["total_token_limit"]):
        raise RuntimeError("SkillOpt exceeded the total token budget")
    elapsed = int(time.monotonic() - started)
    if elapsed > int(budget["wall_time_seconds"]):
        raise RuntimeError("SkillOpt exceeded the wall-clock budget")
    source_archive_hash = read_digest(required_env("SKILLOPT_SOURCE_ARCHIVE_SHA256_FILE"))
    registration_patch_hash = sha256_file(required_env("CEREBELLUM_REGISTRATION_PATCH"))
    return {
        "schema_version": "cerebellum/v1",
        "run_id": payload["run_id"],
        "worker": required_env("WORKER_ID"),
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_source_archive_sha256": source_archive_hash,
        "registration_patch_sha256": registration_patch_hash,
        "patches": patches,
        "evaluations": evaluations,
        "holdout": holdout,
        "best_patch_id": best_patch["patch_id"] if holdout else None,
        "stopped_reason": (
            "two consecutive candidates had no objective validation gain"
            if adapter.stop_requested
            else "positive holdout candidate awaiting human review"
            if holdout and holdout["positive_result"]
            else "no improvement or insufficient objective evidence"
        ),
        "target_calls": adapter.rollout_calls,
        "optimizer_calls": optimizer_calls,
        "total_tokens": total_tokens,
        "elapsed_seconds": elapsed,
        "created_at": now(),
    }


def skillopt_config(data_root: Path, out_root: Path, payload: dict) -> dict:
    budget = payload["budget"]
    return {
        "backend": "openai_compatible",
        "model_backend": "openai_compatible",
        "optimizer_backend": "openai_compatible",
        "target_backend": "openai_compatible",
        "optimizer_model": payload["optimizer_model"],
        "target_model": payload["target_model"],
        "skill_init": str(data_root / "baseline.md"),
        "data_root": str(data_root),
        "container_image": payload["container_image_digest"],
        "out_root": str(out_root),
        "num_epochs": int(budget["epochs"]),
        "train_size": 30,
        "batch_size": int(budget["batch_size"]),
        "accumulation": 1,
        "seed": 42,
        "edit_budget": int(budget["max_edits_per_candidate"]),
        "min_edit_budget": 1,
        "lr_scheduler": "constant",
        "lr_control_mode": "fixed",
        "merge_batch_size": 2,
        "analyst_workers": 1,
        "failure_only": False,
        "minibatch_size": 10,
        "skill_update_mode": "patch",
        "longitudinal_pair_policy": "mixed",
        "use_slow_update": False,
        "use_meta_skill": False,
        "use_skill_aware_reflection": False,
        "use_gate": True,
        "gate_metric": "mixed",
        "gate_mixed_weight": 0.8,
        "sel_env_num": 15,
        "test_env_num": 15,
        "eval_test": False,
        "max_api_workers": 1,
        "max_steps": 12,
        "target_call_limit": int(budget["target_call_limit"]),
        "total_token_limit": int(budget["total_token_limit"]),
        "wall_time_seconds": int(budget["wall_time_seconds"]),
        "rewrite_reasoning_effort": "",
    }


def build_candidates(
    payload: dict,
    baseline: str,
    ledger: list[dict],
    out_root: Path,
    optimizer_model: str,
) -> tuple[list[dict], list[dict], dict[str, str]]:
    baseline_hash = hashlib.sha256(baseline.encode()).hexdigest()
    baseline_rows = latest_scores(ledger, baseline_hash, "validation")
    raw_order = []
    for row in ledger:
        raw = row["skill_hash"]
        if raw != baseline_hash and raw not in raw_order:
            raw_order.append(raw)
    history = read_json(out_root / "history.json", default=[])
    patches = []
    evaluations = []
    raw_to_canonical: dict[str, str] = {}
    max_steps = int(payload["budget"]["max_candidate_steps"])
    for raw_hash in raw_order:
        if len(patches) >= max_steps:
            break
        candidate = next(row["skill_content"] for row in ledger if row["skill_hash"] == raw_hash)
        patch = body_replacement_patch(
            payload["run_id"], len(patches) + 1, baseline, candidate, optimizer_model, raw_hash
        )
        if patch is None:
            continue
        if abs(patch["token_delta"]) > int(payload["budget"]["max_net_new_tokens"]):
            continue
        if len(canonical_candidate(baseline, candidate).split()) > int(payload["budget"]["max_skill_tokens"]):
            continue
        patches.append(patch)
        raw_to_canonical[raw_hash] = patch["candidate_hash"]
        candidate_rows = latest_scores(ledger, raw_hash, "validation")
        if len(baseline_rows) == 15 and len(candidate_rows) == 15:
            evaluation = paired_evaluation(
                patch["candidate_hash"], baseline_rows, candidate_rows, "validation"
            )
            history_row = history[min(len(patches) - 1, len(history) - 1)] if history else {}
            if not evaluation["gate_passed"]:
                action = history_row.get("action", "rejected")
                evaluation["rejection_reasons"] = [f"objective Cerebellum gate denied; SkillOpt action={action}"]
            evaluations.append(evaluation)
    return patches, evaluations, raw_to_canonical


def run_holdout(
    adapter: CerebellumVerifyAdapter,
    baseline: str,
    candidate: str,
    out_root: Path,
) -> dict:
    scores = []
    baseline_safety = candidate_safety = 0
    for seed in (1729, 2718):
        env = adapter.build_eval_env(15, "holdout", seed)
        baseline_rows = adapter.rollout(env, baseline, str(out_root / f"seed-{seed}" / "baseline"), seed=seed)
        candidate_rows = adapter.rollout(env, candidate, str(out_root / f"seed-{seed}" / "candidate"), seed=seed)
        for left, right in zip(baseline_rows, candidate_rows, strict=True):
            baseline_safety += int(left.get("safety_violation", False))
            candidate_safety += int(right.get("safety_violation", False))
            scores.append(task_score(left, right))
    low = bootstrap_low(scores)
    safety_delta = candidate_safety - baseline_safety
    positive = low > 0 and safety_delta <= 0 and not any(row["safety_violation"] for row in scores)
    return {
        "seeds": [1729, 2718],
        "task_scores": scores,
        "paired_runs": len(scores),
        "bootstrap_ci95_low": low,
        "safety_violation_delta": safety_delta,
        "positive_result": positive,
    }


def paired_evaluation(
    candidate_hash: str, baseline_rows: dict[str, dict], candidate_rows: dict[str, dict], split: str
) -> dict:
    scores = [task_score(baseline_rows[key], candidate_rows[key]) for key in sorted(baseline_rows)]
    means = {
        key: sum(score[key] for score in scores) / len(scores)
        for key in ("baseline_hard", "candidate_hard", "baseline_soft", "candidate_soft")
    }
    no_regression = not any(row["candidate_hard"] < row["baseline_hard"] for row in scores)
    no_safety = not any(row["safety_violation"] for row in scores)
    gate = no_regression and no_safety and (
        means["candidate_hard"] > means["baseline_hard"]
        or (
            abs(means["candidate_hard"] - means["baseline_hard"]) <= 1e-12
            and means["candidate_soft"] >= means["baseline_soft"] + 0.02
        )
    )
    return {
        "candidate_hash": candidate_hash,
        "split": split,
        "task_scores": scores,
        "baseline_hard_mean": means["baseline_hard"],
        "candidate_hard_mean": means["candidate_hard"],
        "baseline_soft_mean": means["baseline_soft"],
        "candidate_soft_mean": means["candidate_soft"],
        "gate_passed": gate,
        "rejection_reasons": [],
    }


def task_score(baseline: dict, candidate: dict) -> dict:
    if baseline["id"] != candidate["id"]:
        raise RuntimeError("paired rollout task ids differ")
    return {
        "task_id": baseline["id"],
        "baseline_hard": float(baseline["hard"]),
        "candidate_hard": float(candidate["hard"]),
        "baseline_soft": float(baseline["soft"]),
        "candidate_soft": float(candidate["soft"]),
        "safety_violation": bool(candidate.get("safety_violation", False)),
    }


def body_replacement_patch(
    run_id: str,
    sequence: int,
    baseline: str,
    candidate: str,
    optimizer_model: str,
    raw_hash: str,
) -> dict | None:
    baseline_frontmatter, baseline_body = split_skill(baseline)
    candidate_frontmatter, candidate_body = split_skill(candidate)
    if baseline_frontmatter != candidate_frontmatter or baseline_body == candidate_body:
        return None
    canonical = baseline_frontmatter + candidate_body.strip() + "\n"
    return {
        "schema_version": "cerebellum/v1",
        "patch_id": str(uuid.uuid5(uuid.UUID(run_id), raw_hash)),
        "run_id": run_id,
        "sequence": sequence,
        "baseline_hash": hashlib.sha256(baseline.encode()).hexdigest(),
        "candidate_hash": hashlib.sha256(canonical.encode()).hexdigest(),
        "edits": [{"operation": "replace", "target": baseline_body, "content": candidate_body}],
        "rationale": "SkillOpt reflection over successful and failed objective trajectories",
        "trajectory_ids": [],
        "token_delta": len(canonical.split()) - len(baseline.split()),
        "optimizer_model": optimizer_model,
        "created_at": now(),
    }


def canonical_candidate(baseline: str, candidate: str) -> str:
    frontmatter, _ = split_skill(baseline)
    _, body = split_skill(candidate)
    return frontmatter + body.strip() + "\n"


def split_skill(content: str) -> tuple[str, str]:
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise RuntimeError("Skill is missing YAML frontmatter")
    closing = normalized.find("\n---\n", 4)
    if closing < 0:
        raise RuntimeError("Skill frontmatter is not closed")
    end = closing + len("\n---\n")
    return normalized[:end], normalized[end:].strip()


def latest_scores(rows: list[dict], skill_hash: str, split: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        if row.get("skill_hash") == skill_hash and row.get("split") == split:
            result[row["id"]] = row
    return result


def bootstrap_low(scores: list[dict]) -> float:
    deltas = [score["candidate_hard"] - score["baseline_hard"] for score in scores]
    state = 0x9E3779B97F4A7C15
    samples = []
    for _ in range(10_000):
        total = 0.0
        for _ in deltas:
            state = (state * 6_364_136_223_846_793_005 + 1_442_695_040_888_963_407) & ((1 << 64) - 1)
            total += deltas[state % len(deltas)]
        samples.append(total / len(deltas))
    samples.sort()
    return samples[249]


def count_optimizer_artifacts(out_root: Path) -> int:
    patterns = ("**/patches/*.json", "**/merge*.json", "**/rewrite*.json")
    return len({path for pattern in patterns for path in out_root.glob(pattern)})


def optimizer_call_total(value: object) -> int:
    if isinstance(value, dict):
        if isinstance(value.get("calls"), int):
            return int(value["calls"])
        return sum(optimizer_call_total(item) for item in value.values())
    if isinstance(value, list):
        return sum(optimizer_call_total(item) for item in value)
    return 0


def token_total(value: object) -> int:
    if isinstance(value, dict):
        if "prompt_tokens" in value or "completion_tokens" in value:
            return int(value.get("prompt_tokens", 0)) + int(value.get("completion_tokens", 0))
        return sum(token_total(item) for item in value.values())
    if isinstance(value, list):
        return sum(token_total(item) for item in value)
    return 0


def read_ledger(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def read_json(path: Path, default: object) -> object:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def assert_pinned_inputs(payload: dict) -> None:
    if payload.get("upstream_commit") != UPSTREAM_COMMIT:
        raise RuntimeError("job does not pin the approved SkillOpt commit")
    if payload.get("upstream_source_archive_sha256") != "abdc429fe2a59b30d36c3148a107dfb36184821c7996d67d98d362a6603b1999":
        raise RuntimeError("job does not pin the approved SkillOpt source archive")
    if payload.get("registration_patch_sha256") != "3f57e82c0518e18fd9ee33c337737f370e9d61c892715f7905b35c98590c1549":
        raise RuntimeError("job does not pin the approved registration patch")
    image = str(payload.get("container_image_digest", ""))
    if "@sha256:" not in image or len(image.rsplit("@sha256:", 1)[1]) != 64:
        raise RuntimeError("job container image is not digest pinned")


def read_digest(path: str) -> str:
    value = Path(path).read_text(encoding="utf-8").strip().split()[0]
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise RuntimeError("upstream source archive hash file is invalid")
    return value


def sha256_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
