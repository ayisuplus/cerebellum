"""Tests for offline skill evolution constraints and output."""
import json
from pathlib import Path

import pytest

from evolver.skill_evolution import (
    ConstraintError,
    EvalDataset,
    EvalExample,
    EvolutionConfig,
    OutputError,
    load_skill_artifact,
    run_dry_run,
    validate_constraints,
    write_run_output,
)


VALID_SKILL = """---
name: git-review
description: Use when reviewing git changes.
---

# Git Review

## Steps
1. Inspect the diff.
"""


NO_WORKFLOW_SKILL = """---
name: git-review
description: Use when reviewing git changes.
---

# Git Review

Only prose here.
"""


def _artifact(tmp_path, content=VALID_SKILL):
    skill_path = tmp_path / "git-review.md"
    skill_path.write_text(content, encoding="utf-8")
    return load_skill_artifact(skill_path)


def _dataset():
    return EvalDataset(
        train=[EvalExample("task one", "expected one")],
        val=[EvalExample("task two", "expected two")],
        holdout=[EvalExample("task three", "expected three")],
    )


def test_validate_constraints_passes_valid_inputs(tmp_path):
    checks = validate_constraints(_artifact(tmp_path), _dataset(), max_skill_size=15_000)

    assert all(check.passed for check in checks)


def test_validate_constraints_fails_oversized_skill(tmp_path):
    checks = validate_constraints(_artifact(tmp_path), _dataset(), max_skill_size=10)

    failed = [check for check in checks if not check.passed]
    assert failed
    assert failed[0].name == "skill_size"


def test_validate_constraints_fails_missing_workflow_section(tmp_path):
    checks = validate_constraints(_artifact(tmp_path, NO_WORKFLOW_SKILL), _dataset(), max_skill_size=15_000)

    assert any(check.name == "workflow_section" and not check.passed for check in checks)


def test_validate_constraints_fails_empty_split(tmp_path):
    dataset = EvalDataset(train=[], val=[EvalExample("task", "expected")], holdout=[EvalExample("task", "expected")])

    checks = validate_constraints(_artifact(tmp_path), dataset, max_skill_size=15_000)

    assert any(check.name == "dataset_splits" and not check.passed for check in checks)


def test_write_run_output_creates_report_files(tmp_path):
    artifact = _artifact(tmp_path)
    dataset = _dataset()
    checks = validate_constraints(artifact, dataset, max_skill_size=15_000)
    config = EvolutionConfig(
        skill_path=artifact.path,
        dataset_source="manual",
        output_dir=tmp_path / "runs",
        timestamp="20260606-120000-000000",
    )

    result = write_run_output(config, artifact, dataset, checks, status="pass")

    assert result.status == "pass"
    assert (result.run_dir / "baseline.md").exists()
    assert (result.run_dir / "dataset.jsonl").exists()
    assert (result.run_dir / "README.md").exists()
    report = json.loads((result.run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["counts"] == {"train": 1, "val": 1, "holdout": 1, "total": 3}
    assert report["next_phase_ready"] is True


def test_write_run_output_rejects_existing_run_dir(tmp_path):
    artifact = _artifact(tmp_path)
    dataset = _dataset()
    checks = validate_constraints(artifact, dataset, max_skill_size=15_000)
    config = EvolutionConfig(
        skill_path=artifact.path,
        output_dir=tmp_path / "runs",
        timestamp="20260606-120000-000000",
    )
    write_run_output(config, artifact, dataset, checks, status="pass")

    with pytest.raises(OutputError, match="already exists"):
        write_run_output(config, artifact, dataset, checks, status="pass")


def test_run_dry_run_writes_fail_report_before_constraint_error(tmp_path):
    artifact = _artifact(tmp_path, NO_WORKFLOW_SKILL)
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        "\n".join([
            json.dumps({"task_input": "one", "expected_behavior": "first"}),
            json.dumps({"task_input": "two", "expected_behavior": "second"}),
            json.dumps({"task_input": "three", "expected_behavior": "third"}),
        ]),
        encoding="utf-8",
    )
    config = EvolutionConfig(
        skill_path=artifact.path,
        dataset_path=dataset_path,
        dataset_source="manual",
        output_dir=tmp_path / "runs",
        timestamp="20260606-120000-000000",
    )

    with pytest.raises(ConstraintError) as excinfo:
        run_dry_run(config)

    report_path = excinfo.value.report_path
    assert report_path is not None
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["next_phase_ready"] is False
