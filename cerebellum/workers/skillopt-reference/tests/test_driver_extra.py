from __future__ import annotations

import hashlib
import json
import sys
import types
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from cerebellum_skillopt import UPSTREAM_COMMIT
from cerebellum_skillopt import driver as driver_module
from cerebellum_skillopt.adapter import EarlyStopRequested
from cerebellum_skillopt.driver import (
    assert_pinned_inputs,
    body_replacement_patch,
    bootstrap_low,
    build_candidates,
    canonical_candidate,
    count_optimizer_artifacts,
    latest_scores,
    now,
    optimizer_call_total,
    paired_evaluation,
    read_digest,
    read_json,
    read_ledger,
    run_holdout,
    run_optimization,
    sha256_file,
    skillopt_config,
    split_skill,
    task_score,
    token_total,
)

RUN_ID = "11111111-1111-4111-8111-111111111111"
IMAGE = "python@sha256:" + "a" * 64
ARCHIVE_SHA = "abdc429fe2a59b30d36c3148a107dfb36184821c7996d67d98d362a6603b1999"
REGISTRATION_SHA = "3f57e82c0518e18fd9ee33c337737f370e9d61c892715f7905b35c98590c1549"
BASELINE = "---\nname: verify\n---\nOld body text\n"
CANDIDATE = "---\nname: verify\n---\nNew body text\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def ledger_rows(skill: str, split: str, count: int, hard: float, soft: float) -> list[dict]:
    return [
        {
            "id": f"task-{index}",
            "split": split,
            "skill_hash": sha(skill),
            "skill_content": skill,
            "hard": hard,
            "soft": soft,
            "safety_violation": False,
        }
        for index in range(count)
    ]


def make_budget(**overrides) -> dict:
    budget = {
        "epochs": 1,
        "batch_size": 2,
        "max_edits_per_candidate": 2,
        "target_call_limit": 240,
        "optimizer_call_limit": 40,
        "total_token_limit": 2_000_000,
        "wall_time_seconds": 21_600,
        "max_candidate_steps": 5,
        "max_net_new_tokens": 200,
        "max_skill_tokens": 2_000,
    }
    budget.update(overrides)
    return budget


def make_payload(**overrides) -> dict:
    payload = {
        "run_id": RUN_ID,
        "target_model": "target-m",
        "optimizer_model": "optimizer-m",
        "container_image_digest": IMAGE,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_source_archive_sha256": ARCHIVE_SHA,
        "registration_patch_sha256": REGISTRATION_SHA,
        "budget": make_budget(),
    }
    payload.update(overrides)
    return payload


class TestSplitSkill:
    def test_splits_frontmatter_and_body(self):
        frontmatter, body = split_skill(BASELINE)
        assert frontmatter == "---\nname: verify\n---\n"
        assert body == "Old body text"

    def test_crlf_normalized(self):
        frontmatter, body = split_skill("---\r\nname: x\r\n---\r\nbody\r\n")
        assert "\r" not in frontmatter
        assert body == "body"

    def test_missing_frontmatter_rejected(self):
        with pytest.raises(RuntimeError, match="missing YAML frontmatter"):
            split_skill("no frontmatter")

    def test_unclosed_frontmatter_rejected(self):
        with pytest.raises(RuntimeError, match="not closed"):
            split_skill("---\nname: x\nbody without closing")


class TestBodyReplacementPatch:
    def test_identical_body_yields_no_patch(self):
        same = "---\nname: verify\n---\nOld body text\n"
        assert body_replacement_patch(RUN_ID, 1, BASELINE, same, "opt", "a" * 64) is None

    def test_successful_patch_has_deterministic_id_and_delta(self):
        raw_hash = sha(CANDIDATE)
        patch = body_replacement_patch(RUN_ID, 3, BASELINE, CANDIDATE, "optimizer-m", raw_hash)
        assert patch["patch_id"] == str(uuid.uuid5(uuid.UUID(RUN_ID), raw_hash))
        assert patch["sequence"] == 3
        assert patch["schema_version"] == "cerebellum/v1"
        assert patch["baseline_hash"] == sha(BASELINE)
        canonical = canonical_candidate(BASELINE, CANDIDATE)
        assert patch["candidate_hash"] == sha(canonical)
        assert patch["token_delta"] == len(canonical.split()) - len(BASELINE.split())
        assert patch["edits"] == [
            {"operation": "replace", "target": "Old body text", "content": "New body text"}
        ]
        assert patch["optimizer_model"] == "optimizer-m"

    def test_canonical_candidate_keeps_baseline_frontmatter(self):
        canonical = canonical_candidate(BASELINE, CANDIDATE)
        assert canonical.startswith("---\nname: verify\n---\n")
        assert canonical.endswith("New body text\n")


class TestScoringHelpers:
    def test_task_score_rejects_mismatched_ids(self):
        with pytest.raises(RuntimeError, match="task ids differ"):
            task_score({"id": "a", "hard": 1, "soft": 0}, {"id": "b", "hard": 1, "soft": 0})

    def test_task_score_coerces_numeric_strings(self):
        score = task_score(
            {"id": "a", "hard": 1, "soft": 0.5},
            {"id": "a", "hard": 0, "soft": 0.25, "safety_violation": True},
        )
        assert score == {
            "task_id": "a",
            "baseline_hard": 1.0,
            "candidate_hard": 0.0,
            "baseline_soft": 0.5,
            "candidate_soft": 0.25,
            "safety_violation": True,
        }

    def test_paired_evaluation_gate_passes_on_hard_gain(self):
        baseline = {f"t{i}": {"id": f"t{i}", "hard": 0.0, "soft": 0.5} for i in range(15)}
        candidate = {f"t{i}": {"id": f"t{i}", "hard": 1.0, "soft": 0.5} for i in range(15)}
        evaluation = paired_evaluation("h", baseline, candidate, "validation")
        assert evaluation["gate_passed"] is True
        assert evaluation["candidate_hard_mean"] == 1.0
        assert evaluation["rejection_reasons"] == []

    def test_paired_evaluation_gate_passes_on_soft_gain(self):
        baseline = {f"t{i}": {"id": f"t{i}", "hard": 1.0, "soft": 0.5} for i in range(15)}
        candidate = {f"t{i}": {"id": f"t{i}", "hard": 1.0, "soft": 0.53} for i in range(15)}
        assert paired_evaluation("h", baseline, candidate, "validation")["gate_passed"] is True

    def test_paired_evaluation_gate_denies_small_soft_gain(self):
        baseline = {f"t{i}": {"id": f"t{i}", "hard": 1.0, "soft": 0.5} for i in range(15)}
        candidate = {f"t{i}": {"id": f"t{i}", "hard": 1.0, "soft": 0.51} for i in range(15)}
        assert paired_evaluation("h", baseline, candidate, "validation")["gate_passed"] is False

    def test_paired_evaluation_gate_denies_regression_and_safety(self):
        baseline = {"t": {"id": "t", "hard": 1.0, "soft": 0.5}}
        regression = {"t": {"id": "t", "hard": 0.0, "soft": 1.0}}
        assert paired_evaluation("h", baseline, regression, "validation")["gate_passed"] is False
        unsafe = {"t": {"id": "t", "hard": 1.0, "soft": 0.9, "safety_violation": True}}
        assert paired_evaluation("h", baseline, unsafe, "validation")["gate_passed"] is False

    def test_latest_scores_keeps_most_recent_row(self):
        rows = [
            {"id": "a", "skill_hash": "h", "split": "validation", "hard": 0.0, "soft": 0.0},
            {"id": "a", "skill_hash": "h", "split": "validation", "hard": 1.0, "soft": 1.0},
            {"id": "a", "skill_hash": "h", "split": "train", "hard": 0.0, "soft": 0.0},
            {"id": "b", "skill_hash": "other", "split": "validation", "hard": 0.0, "soft": 0.0},
        ]
        scores = latest_scores(rows, "h", "validation")
        assert list(scores) == ["a"]
        assert scores["a"]["hard"] == 1.0

    def test_bootstrap_low_is_deterministic(self):
        scores = [
            {"baseline_hard": 0.5, "candidate_hard": value}
            for value in (0.4, 0.6, 0.5, 0.7, 0.3, 0.9, 0.5, 0.5)
        ]
        first = bootstrap_low(scores)
        assert first == bootstrap_low(scores)
        assert -0.2 <= first <= 0.4

    def test_bootstrap_low_all_negative(self):
        scores = [{"baseline_hard": 1.0, "candidate_hard": 0.0} for _ in range(30)]
        assert bootstrap_low(scores) == -1.0


class TestPinnedInputs:
    def test_valid_payload_passes(self):
        assert_pinned_inputs(make_payload())

    def test_wrong_commit_rejected(self):
        with pytest.raises(RuntimeError, match="approved SkillOpt commit"):
            assert_pinned_inputs(make_payload(upstream_commit="deadbeef"))

    def test_wrong_archive_rejected(self):
        with pytest.raises(RuntimeError, match="source archive"):
            assert_pinned_inputs(make_payload(upstream_source_archive_sha256="0" * 64))

    def test_wrong_registration_patch_rejected(self):
        with pytest.raises(RuntimeError, match="registration patch"):
            assert_pinned_inputs(make_payload(registration_patch_sha256="0" * 64))

    def test_unpinned_or_short_digest_rejected(self):
        with pytest.raises(RuntimeError, match="digest pinned"):
            assert_pinned_inputs(make_payload(container_image_digest="python:latest"))
        with pytest.raises(RuntimeError, match="digest pinned"):
            assert_pinned_inputs(make_payload(container_image_digest="python@sha256:abc"))


class TestFileAndCounterHelpers:
    def test_read_digest_validates_hex(self, tmp_path):
        good = tmp_path / "digest.txt"
        good.write_text("ab12cd" + "0" * 58 + "  extra\n", encoding="utf-8")
        assert read_digest(str(good)) == "ab12cd" + "0" * 58
        short = tmp_path / "short.txt"
        short.write_text("abc\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="invalid"):
            read_digest(str(short))
        upper = tmp_path / "upper.txt"
        upper.write_text("A" * 64, encoding="utf-8")
        with pytest.raises(RuntimeError, match="invalid"):
            read_digest(str(upper))

    def test_sha256_file_and_read_ledger(self, tmp_path):
        blob = tmp_path / "blob.bin"
        blob.write_bytes(b"payload")
        assert sha256_file(str(blob)) == hashlib.sha256(b"payload").hexdigest()
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text('{"a": 1}\n\n{"b": 2}\n', encoding="utf-8")
        assert read_ledger(ledger) == [{"a": 1}, {"b": 2}]

    def test_read_json_default_and_present(self, tmp_path):
        assert read_json(tmp_path / "missing.json", default={"x": 1}) == {"x": 1}
        present = tmp_path / "present.json"
        present.write_text('{"y": 2}', encoding="utf-8")
        assert read_json(present, default={}) == {"y": 2}

    def test_optimizer_call_total_recurses(self):
        summary = {"optimizer": {"calls": 3}, "nested": [{"calls": 2}, {"other": 1}]}
        assert optimizer_call_total(summary) == 5
        assert optimizer_call_total({"calls": "not-an-int"}) == 0
        assert optimizer_call_total("junk") == 0

    def test_token_total_recurses(self):
        summary = {
            "step": {"prompt_tokens": 10, "completion_tokens": 5},
            "list": [{"prompt_tokens": 1}, {"completion_tokens": 2}, {"none": 0}],
        }
        assert token_total(summary) == 18
        assert token_total(42) == 0

    def test_count_optimizer_artifacts_dedupes(self, tmp_path):
        patches = tmp_path / "run" / "patches"
        patches.mkdir(parents=True)
        (patches / "p1.json").write_text("{}", encoding="utf-8")
        (tmp_path / "run" / "merge-1.json").write_text("{}", encoding="utf-8")
        (tmp_path / "rewrite.json").write_text("{}", encoding="utf-8")
        (tmp_path / "run" / "notes.txt").write_text("x", encoding="utf-8")
        assert count_optimizer_artifacts(tmp_path) == 3
        assert count_optimizer_artifacts(tmp_path / "empty") == 0

    def test_now_returns_zulu_timestamp(self):
        assert now().endswith("Z")


class TestSkilloptConfig:
    def test_budget_fields_map_into_config(self, tmp_path):
        payload = make_payload(budget=make_budget(epochs=3, batch_size=7, max_edits_per_candidate=1))
        cfg = skillopt_config(tmp_path, tmp_path / "out", payload)
        assert cfg["num_epochs"] == 3
        assert cfg["batch_size"] == 7
        assert cfg["edit_budget"] == 1
        assert cfg["optimizer_model"] == "optimizer-m"
        assert cfg["target_model"] == "target-m"
        assert cfg["container_image"] == IMAGE
        assert cfg["skill_init"] == str(tmp_path / "baseline.md")
        assert cfg["seed"] == 42
        assert cfg["use_gate"] is True
        assert cfg["target_call_limit"] == 240


class TestBuildCandidates:
    def build(self, tmp_path, ledger, budget=None, payload=None):
        out_root = tmp_path / "out"
        out_root.mkdir()
        return build_candidates(
            payload or make_payload(budget=budget or make_budget()),
            BASELINE,
            ledger,
            out_root,
            "optimizer-m",
        )

    def test_patch_and_passing_evaluation(self, tmp_path):
        ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
        ledger += ledger_rows(CANDIDATE, "validation", 15, 1.0, 0.5)
        patches, evaluations, mapping = self.build(tmp_path, ledger)
        assert len(patches) == 1
        assert len(evaluations) == 1
        assert evaluations[0]["gate_passed"] is True
        assert mapping[sha(CANDIDATE)] == patches[0]["candidate_hash"]

    def test_gate_failure_records_rejection_reason(self, tmp_path):
        ledger = ledger_rows(BASELINE, "validation", 15, 1.0, 0.5)
        ledger += ledger_rows(CANDIDATE, "validation", 15, 1.0, 0.51)
        patches, evaluations, _ = self.build(tmp_path, ledger)
        assert evaluations[0]["gate_passed"] is False
        assert evaluations[0]["rejection_reasons"] == [
            "objective Cerebellum gate denied; SkillOpt action=rejected"
        ]

    def test_max_candidate_steps_caps_patches(self, tmp_path):
        other = "---\nname: verify\n---\nAnother body\n"
        ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
        ledger += ledger_rows(CANDIDATE, "validation", 15, 1.0, 0.5)
        ledger += ledger_rows(other, "validation", 15, 1.0, 0.5)
        patches, _, mapping = self.build(tmp_path, ledger, make_budget(max_candidate_steps=1))
        assert len(patches) == 1
        assert len(mapping) == 1

    def test_net_new_token_budget_skips_candidate(self, tmp_path):
        ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
        ledger += ledger_rows("---\nname: verify\n---\nOld body text plus several additional tokens\n", "validation", 15, 1.0, 0.5)
        patches, evaluations, _ = self.build(tmp_path, ledger, make_budget(max_net_new_tokens=0))
        assert patches == []
        assert evaluations == []

    def test_max_skill_tokens_skips_candidate(self, tmp_path):
        ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
        ledger += ledger_rows(CANDIDATE, "validation", 15, 1.0, 0.5)
        patches, _, _ = self.build(tmp_path, ledger, make_budget(max_skill_tokens=1))
        assert patches == []

    def test_identical_body_candidate_skipped(self, tmp_path):
        ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
        ledger += ledger_rows(BASELINE, "validation", 15, 1.0, 0.5)
        patches, _, _ = self.build(tmp_path, ledger)
        assert patches == []
    def test_frontmatter_deviation_yields_no_patch(self, tmp_path):
        deviant = "---\nname: attacker\n---\nOld body text\n"
        ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
        ledger += ledger_rows(deviant, "validation", 15, 1.0, 0.5)
        patches, evaluations, _ = self.build(tmp_path, ledger)
        assert patches == []
        assert evaluations == []

    def test_evaluation_requires_full_15_task_coverage(self, tmp_path):
        ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
        ledger += ledger_rows(CANDIDATE, "validation", 14, 1.0, 0.5)
        patches, evaluations, _ = self.build(tmp_path, ledger)
        assert len(patches) == 1
        assert evaluations == []


class StubHoldoutAdapter:
    def __init__(self, rows_per_skill):
        self.rows_per_skill = rows_per_skill

    def build_eval_env(self, env_num, split, seed):
        return [{"split": split, "seed": seed}] * env_num

    def rollout(self, env_manager, skill_content, out_dir, **kwargs):
        rows = self.rows_per_skill[skill_content]
        return [dict(row) for row in rows]


class TestRunHoldout:
    def test_positive_holdout_when_candidate_wins(self):
        adapter = StubHoldoutAdapter(
            {
                "base": [{"id": f"h{i}", "hard": 0.0, "soft": 0.5} for i in range(15)],
                "cand": [{"id": f"h{i}", "hard": 1.0, "soft": 0.5} for i in range(15)],
            }
        )
        result = run_holdout(adapter, "base", "cand", Path("unused"))
        assert result["seeds"] == [1729, 2718]
        assert result["paired_runs"] == 30
        assert result["bootstrap_ci95_low"] == 1.0
        assert result["safety_violation_delta"] == 0
        assert result["positive_result"] is True

    def test_no_gain_is_not_positive(self):
        adapter = StubHoldoutAdapter(
            {
                "base": [{"id": f"h{i}", "hard": 0.5, "soft": 0.5} for i in range(15)],
                "cand": [{"id": f"h{i}", "hard": 0.5, "soft": 0.5} for i in range(15)],
            }
        )
        result = run_holdout(adapter, "base", "cand", Path("unused"))
        assert result["bootstrap_ci95_low"] == 0.0
        assert result["positive_result"] is False

    def test_candidate_safety_violation_blocks_positive(self):
        adapter = StubHoldoutAdapter(
            {
                "base": [{"id": f"h{i}", "hard": 0.0, "soft": 0.5} for i in range(15)],
                "cand": [
                    {"id": f"h{i}", "hard": 1.0, "soft": 0.5, "safety_violation": True}
                    for i in range(15)
                ],
            }
        )
        result = run_holdout(adapter, "base", "cand", Path("unused"))
        assert result["safety_violation_delta"] == 30
        assert result["positive_result"] is False


class FakeAdapter:
    def __init__(self, data_root, image, **kwargs):
        self.agent = SimpleNamespace(usage=SimpleNamespace(tokens=0))
        self.rollout_calls = 0
        self.stop_requested = False
        self.baseline = (Path(data_root) / "baseline.md").read_text(encoding="utf-8")

    def build_eval_env(self, env_num, split, seed):
        return [{"split": split, "seed": seed}] * env_num

    def rollout(self, env_manager, skill_content, out_dir, **kwargs):
        hard = 0.0 if skill_content == self.baseline else 1.0
        return [{"id": f"h{i}", "hard": hard, "soft": 0.5} for i in range(len(env_manager))]


class FakeTrainer:
    summary: dict = {"token_summary": {"optimizer": {"calls": 2, "prompt_tokens": 10, "completion_tokens": 5}}}
    error: Exception | None = None

    def __init__(self, cfg, adapter):
        self.cfg = cfg
        self.adapter = adapter

    def train(self):
        if FakeTrainer.error is not None:
            raise FakeTrainer.error
        return FakeTrainer.summary


@pytest.fixture
def skillopt_stub(monkeypatch):
    skillopt = types.ModuleType("skillopt")
    engine = types.ModuleType("skillopt.engine")
    trainer = types.ModuleType("skillopt.engine.trainer")
    trainer.ReflACTTrainer = FakeTrainer
    engine.trainer = trainer
    skillopt.engine = engine
    monkeypatch.setitem(sys.modules, "skillopt", skillopt)
    monkeypatch.setitem(sys.modules, "skillopt.engine", engine)
    monkeypatch.setitem(sys.modules, "skillopt.engine.trainer", trainer)
    FakeTrainer.error = None
    FakeTrainer.summary = {
        "token_summary": {"optimizer": {"calls": 2, "prompt_tokens": 10, "completion_tokens": 5}}
    }
    yield trainer


@pytest.fixture
def run_environment(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "baseline.md").write_text(BASELINE, encoding="utf-8")
    digest_file = tmp_path / "archive.sha256"
    digest_file.write_text(ARCHIVE_SHA + "\n", encoding="utf-8")
    registration = tmp_path / "registration.patch"
    registration.write_bytes(b"patch-bytes")
    monkeypatch.setenv("TARGET_MODEL", "target-m")
    monkeypatch.setenv("OPTIMIZER_MODEL", "optimizer-m")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "http://fake.local/v1")
    monkeypatch.setenv("WORKER_ID", "skillopt-test")
    monkeypatch.setenv("SKILLOPT_SOURCE_ARCHIVE_SHA256_FILE", str(digest_file))
    monkeypatch.setenv("CEREBELLUM_REGISTRATION_PATCH", str(registration))
    monkeypatch.setattr(driver_module, "docker_available", lambda: None)
    monkeypatch.setattr(driver_module, "CerebellumVerifyAdapter", FakeAdapter)
    ledger = ledger_rows(BASELINE, "validation", 15, 0.0, 0.5)
    ledger += ledger_rows(CANDIDATE, "validation", 15, 1.0, 0.5)
    (data_root / "adapter-ledger.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in ledger), encoding="utf-8"
    )
    return data_root


class TestRunOptimization:
    def test_full_run_returns_registration_payload(self, run_environment, skillopt_stub):
        result = run_optimization(run_environment, make_payload())
        assert result["schema_version"] == "cerebellum/v1"
        assert result["run_id"] == RUN_ID
        assert result["worker"] == "skillopt-test"
        assert result["upstream_commit"] == UPSTREAM_COMMIT
        assert result["upstream_source_archive_sha256"] == ARCHIVE_SHA
        assert result["registration_patch_sha256"] == hashlib.sha256(b"patch-bytes").hexdigest()
        assert len(result["patches"]) == 1
        assert result["evaluations"][0]["gate_passed"] is True
        assert result["holdout"]["positive_result"] is True
        assert result["best_patch_id"] == result["patches"][0]["patch_id"]
        assert result["stopped_reason"] == "positive holdout candidate awaiting human review"
        assert result["optimizer_calls"] == 2
        assert result["total_tokens"] == 15
        assert result["created_at"].endswith("Z")

    def test_model_role_mismatch_rejected(self, run_environment, skillopt_stub):
        with pytest.raises(RuntimeError, match="model roles"):
            run_optimization(run_environment, make_payload(target_model="other-model"))

    def test_early_stop_reads_summary_from_disk(self, run_environment, skillopt_stub):
        out_root = run_environment / "skillopt-output"
        out_root.mkdir()
        (out_root / "summary.json").write_text(
            json.dumps({"token_summary": {"optimizer": {"calls": 1}}}), encoding="utf-8"
        )
        FakeTrainer.error = EarlyStopRequested("stop")
        result = run_optimization(run_environment, make_payload())
        assert result["optimizer_calls"] == 1
    def test_early_stop_with_non_dict_summary_falls_back(self, run_environment, skillopt_stub):
        out_root = run_environment / "skillopt-output"
        out_root.mkdir()
        (out_root / "summary.json").write_text('["not", "a", "dict"]', encoding="utf-8")
        FakeTrainer.error = EarlyStopRequested("stop")
        result = run_optimization(run_environment, make_payload())
        assert result["optimizer_calls"] == 0

    def test_wall_clock_budget_enforced(self, run_environment, skillopt_stub, monkeypatch):
        ticks = iter([0.0, 999_999.0])
        monkeypatch.setattr(driver_module.time, "monotonic", lambda: next(ticks))
        with pytest.raises(RuntimeError, match="wall-clock budget"):
            run_optimization(run_environment, make_payload())

    def test_optimizer_call_budget_enforced(self, run_environment, skillopt_stub):
        FakeTrainer.summary = {"token_summary": {"optimizer": {"calls": 99}}}
        with pytest.raises(RuntimeError, match="optimizer call budget"):
            run_optimization(run_environment, make_payload())

    def test_rollout_budget_enforced(self, run_environment, skillopt_stub, monkeypatch):
        class BusyAdapter(FakeAdapter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.rollout_calls = 999

        monkeypatch.setattr(driver_module, "CerebellumVerifyAdapter", BusyAdapter)
        with pytest.raises(RuntimeError, match="target rollout budget"):
            run_optimization(run_environment, make_payload())

    def test_token_budget_enforced(self, run_environment, skillopt_stub):
        FakeTrainer.summary = {"token_summary": {"optimizer": {"prompt_tokens": 3_000_000}}}
        with pytest.raises(RuntimeError, match="total token budget"):
            run_optimization(run_environment, make_payload())

    def test_missing_env_var_rejected(self, run_environment, skillopt_stub, monkeypatch):
        monkeypatch.delenv("API_KEY")
        with pytest.raises(RuntimeError, match="API_KEY is required"):
            run_optimization(run_environment, make_payload())
