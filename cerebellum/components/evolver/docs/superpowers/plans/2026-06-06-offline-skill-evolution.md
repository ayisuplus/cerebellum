# Offline Skill Evolution Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic `evolver evolve-skill --dry-run` preflight that validates one skill file, prepares an evaluation dataset, and writes a local report without external optimizer dependencies.

**Architecture:** Add a focused `evolver/skill_evolution.py` module that owns artifact parsing, dataset preparation, constraint checks, and run output writing. Wire it into `evolver/cli.py` as a dry-run-only command, keeping `SkillEngine.generate()` and database schema unchanged.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, json/jsonl, click, pytest, existing `Evolver.recall()` API.

---

## File Structure

- Create: `evolver/skill_evolution.py`
  - Owns offline dry-run dataclasses, named errors, skill artifact loading, dataset loading/building, constraint validation, and report writing.
- Create: `tests/test_skill_evolution_artifact.py`
  - Tests skill markdown loading and frontmatter validation.
- Create: `tests/test_skill_evolution_dataset.py`
  - Tests manual JSONL loading and memory-derived dataset behavior.
- Create: `tests/test_skill_evolution_constraints.py`
  - Tests constraints and dry-run output files.
- Modify: `evolver/cli.py`
  - Adds `evolve-skill` command. Keeps command dry-run-only in Phase 1.
- Modify: `tests/test_cli.py`
  - Adds CLI tests for dry-run success and invalid input failure.

## Task 1: Skill Artifact Loader

**Files:**
- Create: `tests/test_skill_evolution_artifact.py`
- Create: `evolver/skill_evolution.py`

- [ ] **Step 1: Write failing artifact loader tests**

Create `tests/test_skill_evolution_artifact.py` with:

```python
"""Tests for offline skill evolution artifact loading."""
from pathlib import Path

import pytest

from evolver.skill_evolution import (
    SkillFormatError,
    SkillLoadError,
    load_skill_artifact,
)


VALID_SKILL = """---
name: git-review
description: Use when reviewing git changes.
---

# Git Review

## Steps
1. Inspect the diff.
2. Report risky changes.
"""


def test_load_skill_artifact_parses_frontmatter(tmp_path):
    skill_path = tmp_path / "git-review.md"
    skill_path.write_text(VALID_SKILL, encoding="utf-8")

    artifact = load_skill_artifact(skill_path)

    assert artifact.path == skill_path
    assert artifact.name == "git-review"
    assert artifact.description == "Use when reviewing git changes."
    assert "## Steps" in artifact.body
    assert artifact.size == len(VALID_SKILL)


def test_load_skill_artifact_rejects_missing_file(tmp_path):
    missing_path = tmp_path / "missing.md"

    with pytest.raises(SkillLoadError, match="does not exist"):
        load_skill_artifact(missing_path)


def test_load_skill_artifact_rejects_missing_name(tmp_path):
    skill_path = tmp_path / "bad.md"
    skill_path.write_text(
        """---
description: Use when reviewing git changes.
---

## Steps
1. Inspect the diff.
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillFormatError, match="name"):
        load_skill_artifact(skill_path)


def test_load_skill_artifact_rejects_missing_description(tmp_path):
    skill_path = tmp_path / "bad.md"
    skill_path.write_text(
        """---
name: git-review
---

## Steps
1. Inspect the diff.
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillFormatError, match="description"):
        load_skill_artifact(skill_path)


def test_load_skill_artifact_rejects_empty_body(tmp_path):
    skill_path = tmp_path / "bad.md"
    skill_path.write_text(
        """---
name: git-review
description: Use when reviewing git changes.
---
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillFormatError, match="body"):
        load_skill_artifact(skill_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_evolution_artifact.py -v
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'evolver.skill_evolution'`.

- [ ] **Step 3: Add minimal artifact implementation**

Create `evolver/skill_evolution.py` with:

```python
"""Offline skill evolution dry-run helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evolver.exceptions import EvolverError


class SkillEvolutionError(EvolverError):
    """Base error for offline skill evolution."""


class SkillLoadError(SkillEvolutionError):
    """Skill file could not be loaded."""


class SkillFormatError(SkillEvolutionError):
    """Skill markdown does not have the required structure."""


class DatasetError(SkillEvolutionError):
    """Evaluation dataset is missing or invalid."""


class ConstraintError(SkillEvolutionError):
    """Dry-run constraints failed."""


class OutputError(SkillEvolutionError):
    """Dry-run output could not be written."""


@dataclass(frozen=True)
class SkillArtifact:
    path: Path
    raw: str
    frontmatter: str
    body: str
    name: str
    description: str
    size: int


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str, str]:
    normalized = raw.lstrip()
    if not normalized.startswith("---"):
        raise SkillFormatError("Skill frontmatter is missing opening ---")

    parts = normalized.split("---", 2)
    if len(parts) < 3:
        raise SkillFormatError("Skill frontmatter is missing closing ---")

    frontmatter = parts[1].strip()
    body = parts[2].strip()
    fields: dict[str, str] = {}

    for line in frontmatter.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")

    return fields, frontmatter, body


def load_skill_artifact(path: str | Path) -> SkillArtifact:
    skill_path = Path(path)
    if not skill_path.exists():
        raise SkillLoadError(f"Skill file does not exist: {skill_path}")
    if not skill_path.is_file():
        raise SkillLoadError(f"Skill path is not a file: {skill_path}")

    try:
        raw = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillLoadError(f"Failed to read skill file: {skill_path}") from exc

    if not raw.strip():
        raise SkillFormatError("Skill file is empty")

    fields, frontmatter, body = _parse_frontmatter(raw)
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()

    if not name:
        raise SkillFormatError("Skill frontmatter must include name")
    if not description:
        raise SkillFormatError("Skill frontmatter must include description")
    if not body:
        raise SkillFormatError("Skill body must not be empty")

    return SkillArtifact(
        path=skill_path,
        raw=raw,
        frontmatter=frontmatter,
        body=body,
        name=name,
        description=description,
        size=len(raw),
    )
```

- [ ] **Step 4: Run artifact tests to verify they pass**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_evolution_artifact.py -v
```

Expected: PASS, 5 tests passed.

- [ ] **Step 5: Commit Task 1**

```bash
git add evolver/skill_evolution.py tests/test_skill_evolution_artifact.py
git commit -m "feat: add offline skill artifact loader"
```

## Task 2: Evaluation Dataset Builder

**Files:**
- Create: `tests/test_skill_evolution_dataset.py`
- Modify: `evolver/skill_evolution.py`

- [ ] **Step 1: Write failing dataset tests**

Create `tests/test_skill_evolution_dataset.py` with:

```python
"""Tests for offline skill evolution dataset building."""
import json
from types import SimpleNamespace

import pytest

from evolver.models import RecallResult
from evolver.skill_evolution import (
    DatasetError,
    build_dataset,
    build_memory_dataset,
    load_manual_dataset,
    load_skill_artifact,
    split_examples,
)


VALID_SKILL = """---
name: git-review
description: Use when reviewing git changes.
---

# Git Review

## Steps
1. Inspect the diff.
"""


def _write_valid_skill(tmp_path):
    skill_path = tmp_path / "git-review.md"
    skill_path.write_text(VALID_SKILL, encoding="utf-8")
    return load_skill_artifact(skill_path)


def test_load_manual_dataset_splits_valid_jsonl(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    rows = [
        {"task_input": "review diff 1", "expected_behavior": "find risky change 1"},
        {"task_input": "review diff 2", "expected_behavior": "find risky change 2"},
        {"task_input": "review diff 3", "expected_behavior": "find risky change 3"},
        {"task_input": "review diff 4", "expected_behavior": "find risky change 4"},
        {"task_input": "review diff 5", "expected_behavior": "find risky change 5"},
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )

    dataset = load_manual_dataset(dataset_path)

    assert len(dataset.train) == 3
    assert len(dataset.val) == 1
    assert len(dataset.holdout) == 1
    assert dataset.train[0].source == "manual"


def test_load_manual_dataset_rejects_missing_required_field(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        json.dumps({"task_input": "review diff"}),
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="expected_behavior"):
        load_manual_dataset(dataset_path)


def test_load_manual_dataset_rejects_invalid_json(tmp_path):
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(DatasetError, match="Invalid JSON"):
        load_manual_dataset(dataset_path)


def test_split_examples_requires_three_examples():
    with pytest.raises(DatasetError, match="at least 3"):
        split_examples([])


def test_build_memory_dataset_from_recall_results():
    evo = SimpleNamespace()
    evo.recall = lambda query, top_k=20: [
        RecallResult(content="Always inspect auth middleware", score=0.9, source="memory", category="success"),
        RecallResult(content="Check expired token failures", score=0.8, source="memory", category="failure"),
        RecallResult(content="Report security risk first", score=0.7, source="memory", category="insight"),
    ]

    dataset = build_memory_dataset(evo, "git review")

    assert len(dataset.train) == 1
    assert len(dataset.val) == 1
    assert len(dataset.holdout) == 1
    assert dataset.train[0].source == "memory"
    assert "lesson" in dataset.train[0].expected_behavior.lower()


def test_build_memory_dataset_rejects_too_few_memories():
    evo = SimpleNamespace()
    evo.recall = lambda query, top_k=20: [
        RecallResult(content="Only one memory", score=0.9, source="memory", category="success"),
    ]

    with pytest.raises(DatasetError, match="at least 3"):
        build_memory_dataset(evo, "git review")


def test_build_dataset_uses_manual_source(tmp_path):
    artifact = _write_valid_skill(tmp_path)
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        "\n".join([
            json.dumps({"task_input": "one", "expected_behavior": "first"}),
            json.dumps({"task_input": "two", "expected_behavior": "second"}),
            json.dumps({"task_input": "three", "expected_behavior": "third"}),
        ]),
        encoding="utf-8",
    )
    config = SimpleNamespace(dataset_source="manual", dataset_path=dataset_path)

    dataset = build_dataset(config, artifact)

    assert len(dataset.all_examples) == 3
```

- [ ] **Step 2: Run dataset tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_evolution_dataset.py -v
```

Expected: FAIL because `build_dataset`, `build_memory_dataset`, `load_manual_dataset`, and `split_examples` are not defined.

- [ ] **Step 3: Replace module with artifact + dataset implementation**

Replace `evolver/skill_evolution.py` with:

```python
"""Offline skill evolution dry-run helpers."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from evolver.exceptions import EvolverError


class SkillEvolutionError(EvolverError):
    """Base error for offline skill evolution."""


class SkillLoadError(SkillEvolutionError):
    """Skill file could not be loaded."""


class SkillFormatError(SkillEvolutionError):
    """Skill markdown does not have the required structure."""


class DatasetError(SkillEvolutionError):
    """Evaluation dataset is missing or invalid."""


class ConstraintError(SkillEvolutionError):
    """Dry-run constraints failed."""


class OutputError(SkillEvolutionError):
    """Dry-run output could not be written."""


@dataclass(frozen=True)
class EvolutionConfig:
    skill_path: Path
    db_url: str | None = None
    dataset_path: Path | None = None
    dataset_source: str = "memory"
    output_dir: Path = Path("output/evolution-runs")
    max_skill_size: int = 15_000
    dry_run: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S-%f"))


@dataclass(frozen=True)
class SkillArtifact:
    path: Path
    raw: str
    frontmatter: str
    body: str
    name: str
    description: str
    size: int


@dataclass(frozen=True)
class EvalExample:
    task_input: str
    expected_behavior: str
    category: str = "general"
    source: str = "manual"

    def to_dict(self) -> dict:
        return {
            "task_input": self.task_input,
            "expected_behavior": self.expected_behavior,
            "category": self.category,
            "source": self.source,
        }


@dataclass(frozen=True)
class EvalDataset:
    train: list[EvalExample]
    val: list[EvalExample]
    holdout: list[EvalExample]

    @property
    def all_examples(self) -> list[EvalExample]:
        return self.train + self.val + self.holdout

    @property
    def counts(self) -> dict[str, int]:
        return {
            "train": len(self.train),
            "val": len(self.val),
            "holdout": len(self.holdout),
            "total": len(self.all_examples),
        }


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str, str]:
    normalized = raw.lstrip()
    if not normalized.startswith("---"):
        raise SkillFormatError("Skill frontmatter is missing opening ---")

    parts = normalized.split("---", 2)
    if len(parts) < 3:
        raise SkillFormatError("Skill frontmatter is missing closing ---")

    frontmatter = parts[1].strip()
    body = parts[2].strip()
    fields: dict[str, str] = {}

    for line in frontmatter.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")

    return fields, frontmatter, body


def load_skill_artifact(path: str | Path) -> SkillArtifact:
    skill_path = Path(path)
    if not skill_path.exists():
        raise SkillLoadError(f"Skill file does not exist: {skill_path}")
    if not skill_path.is_file():
        raise SkillLoadError(f"Skill path is not a file: {skill_path}")

    try:
        raw = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillLoadError(f"Failed to read skill file: {skill_path}") from exc

    if not raw.strip():
        raise SkillFormatError("Skill file is empty")

    fields, frontmatter, body = _parse_frontmatter(raw)
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()

    if not name:
        raise SkillFormatError("Skill frontmatter must include name")
    if not description:
        raise SkillFormatError("Skill frontmatter must include description")
    if not body:
        raise SkillFormatError("Skill body must not be empty")

    return SkillArtifact(
        path=skill_path,
        raw=raw,
        frontmatter=frontmatter,
        body=body,
        name=name,
        description=description,
        size=len(raw),
    )


def _normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _example_from_dict(row: dict, line_no: int, source: str) -> EvalExample:
    missing = [key for key in ("task_input", "expected_behavior") if key not in row]
    if missing:
        raise DatasetError(f"Dataset line {line_no} missing required field: {', '.join(missing)}")

    task_input = _normalize_text(row["task_input"])
    expected_behavior = _normalize_text(row["expected_behavior"])
    if not task_input:
        raise DatasetError(f"Dataset line {line_no} has empty task_input")
    if not expected_behavior:
        raise DatasetError(f"Dataset line {line_no} has empty expected_behavior")

    return EvalExample(
        task_input=task_input,
        expected_behavior=expected_behavior,
        category=_normalize_text(row.get("category")) or "general",
        source=_normalize_text(row.get("source")) or source,
    )


def split_examples(examples: Iterable[EvalExample]) -> EvalDataset:
    items = list(examples)
    if len(items) < 3:
        raise DatasetError("Evaluation dataset requires at least 3 examples for train/val/holdout")

    train_count = max(1, int(len(items) * 0.6))
    val_count = max(1, int(len(items) * 0.2))
    if train_count + val_count >= len(items):
        train_count = len(items) - 2
        val_count = 1

    return EvalDataset(
        train=items[:train_count],
        val=items[train_count:train_count + val_count],
        holdout=items[train_count + val_count:],
    )


def load_manual_dataset(path: str | Path) -> EvalDataset:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise DatasetError(f"Dataset file does not exist: {dataset_path}")
    if not dataset_path.is_file():
        raise DatasetError(f"Dataset path is not a file: {dataset_path}")

    examples: list[EvalExample] = []
    try:
        lines = dataset_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetError(f"Failed to read dataset file: {dataset_path}") from exc

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"Invalid JSON on dataset line {line_no}: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise DatasetError(f"Dataset line {line_no} must be a JSON object")
        examples.append(_example_from_dict(row, line_no, source="manual"))

    return split_examples(examples)


def _recall_to_example(result) -> EvalExample | None:
    content = _normalize_text(getattr(result, "content", ""))
    if not content:
        return None
    category = _normalize_text(getattr(result, "category", "")) or "memory"
    snippet = content[:180]
    lesson = content[:240]
    return EvalExample(
        task_input=f"Apply this Evolver lesson: {snippet}",
        expected_behavior=(
            "The response should preserve this lesson, apply it to the task, "
            f"and avoid repeating the failure mode if present: {lesson}"
        ),
        category=category,
        source="memory",
    )


def build_memory_dataset(evolver, query: str, top_k: int = 20) -> EvalDataset:
    if evolver is None:
        raise DatasetError("Memory dataset source requires an Evolver instance")
    results = evolver.recall(query, top_k=top_k)
    examples = []
    for result in results:
        example = _recall_to_example(result)
        if example is not None:
            examples.append(example)
    return split_examples(examples)


def build_dataset(config, artifact: SkillArtifact, evolver=None) -> EvalDataset:
    source = getattr(config, "dataset_source", "memory")
    if source == "manual":
        dataset_path = getattr(config, "dataset_path", None)
        if dataset_path is None:
            raise DatasetError("Manual dataset source requires dataset_path")
        return load_manual_dataset(dataset_path)
    if source == "memory":
        query = artifact.name.replace("-", " ") or artifact.description
        return build_memory_dataset(evolver, query)
    raise DatasetError(f"Unsupported dataset source: {source}")
```

- [ ] **Step 4: Run artifact and dataset tests to verify they pass**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_evolution_artifact.py tests/test_skill_evolution_dataset.py -v
```

Expected: PASS, 12 tests passed.

- [ ] **Step 5: Commit Task 2**

```bash
git add evolver/skill_evolution.py tests/test_skill_evolution_dataset.py
git commit -m "feat: add skill evolution dataset builder"
```

## Task 3: Constraints And Dry-Run Output

**Files:**
- Create: `tests/test_skill_evolution_constraints.py`
- Modify: `evolver/skill_evolution.py`

- [ ] **Step 1: Write failing constraint and report tests**

Create `tests/test_skill_evolution_constraints.py` with:

```python
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
```

- [ ] **Step 2: Run constraint tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_evolution_constraints.py -v
```

Expected: FAIL because `validate_constraints`, `write_run_output`, and `run_dry_run` are not defined.

- [ ] **Step 3: Replace module with complete dry-run implementation**

Replace `evolver/skill_evolution.py` with:

```python
"""Offline skill evolution dry-run helpers."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from evolver.exceptions import EvolverError


class SkillEvolutionError(EvolverError):
    """Base error for offline skill evolution."""


class SkillLoadError(SkillEvolutionError):
    """Skill file could not be loaded."""


class SkillFormatError(SkillEvolutionError):
    """Skill markdown does not have the required structure."""


class DatasetError(SkillEvolutionError):
    """Evaluation dataset is missing or invalid."""


class ConstraintError(SkillEvolutionError):
    """Dry-run constraints failed."""

    def __init__(self, message: str, report_path: Path | None = None):
        super().__init__(message)
        self.report_path = report_path


class OutputError(SkillEvolutionError):
    """Dry-run output could not be written."""


@dataclass(frozen=True)
class EvolutionConfig:
    skill_path: Path
    db_url: str | None = None
    dataset_path: Path | None = None
    dataset_source: str = "memory"
    output_dir: Path = Path("output/evolution-runs")
    max_skill_size: int = 15_000
    dry_run: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S-%f"))


@dataclass(frozen=True)
class SkillArtifact:
    path: Path
    raw: str
    frontmatter: str
    body: str
    name: str
    description: str
    size: int


@dataclass(frozen=True)
class EvalExample:
    task_input: str
    expected_behavior: str
    category: str = "general"
    source: str = "manual"

    def to_dict(self) -> dict:
        return {
            "task_input": self.task_input,
            "expected_behavior": self.expected_behavior,
            "category": self.category,
            "source": self.source,
        }


@dataclass(frozen=True)
class EvalDataset:
    train: list[EvalExample]
    val: list[EvalExample]
    holdout: list[EvalExample]

    @property
    def all_examples(self) -> list[EvalExample]:
        return self.train + self.val + self.holdout

    @property
    def counts(self) -> dict[str, int]:
        return {
            "train": len(self.train),
            "val": len(self.val),
            "holdout": len(self.holdout),
            "total": len(self.all_examples),
        }


@dataclass(frozen=True)
class ConstraintCheck:
    name: str
    passed: bool
    message: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "message": self.message}


@dataclass(frozen=True)
class DryRunResult:
    status: str
    run_dir: Path
    report_path: Path
    constraints: list[ConstraintCheck]
    errors: list[str]
    warnings: list[str]

    @property
    def next_phase_ready(self) -> bool:
        return self.status == "pass"


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str, str]:
    normalized = raw.lstrip()
    if not normalized.startswith("---"):
        raise SkillFormatError("Skill frontmatter is missing opening ---")

    parts = normalized.split("---", 2)
    if len(parts) < 3:
        raise SkillFormatError("Skill frontmatter is missing closing ---")

    frontmatter = parts[1].strip()
    body = parts[2].strip()
    fields: dict[str, str] = {}

    for line in frontmatter.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")

    return fields, frontmatter, body


def load_skill_artifact(path: str | Path) -> SkillArtifact:
    skill_path = Path(path)
    if not skill_path.exists():
        raise SkillLoadError(f"Skill file does not exist: {skill_path}")
    if not skill_path.is_file():
        raise SkillLoadError(f"Skill path is not a file: {skill_path}")

    try:
        raw = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillLoadError(f"Failed to read skill file: {skill_path}") from exc

    if not raw.strip():
        raise SkillFormatError("Skill file is empty")

    fields, frontmatter, body = _parse_frontmatter(raw)
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()

    if not name:
        raise SkillFormatError("Skill frontmatter must include name")
    if not description:
        raise SkillFormatError("Skill frontmatter must include description")
    if not body:
        raise SkillFormatError("Skill body must not be empty")

    return SkillArtifact(
        path=skill_path,
        raw=raw,
        frontmatter=frontmatter,
        body=body,
        name=name,
        description=description,
        size=len(raw),
    )


def _normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _example_from_dict(row: dict, line_no: int, source: str) -> EvalExample:
    missing = [key for key in ("task_input", "expected_behavior") if key not in row]
    if missing:
        raise DatasetError(f"Dataset line {line_no} missing required field: {', '.join(missing)}")

    task_input = _normalize_text(row["task_input"])
    expected_behavior = _normalize_text(row["expected_behavior"])
    if not task_input:
        raise DatasetError(f"Dataset line {line_no} has empty task_input")
    if not expected_behavior:
        raise DatasetError(f"Dataset line {line_no} has empty expected_behavior")

    return EvalExample(
        task_input=task_input,
        expected_behavior=expected_behavior,
        category=_normalize_text(row.get("category")) or "general",
        source=_normalize_text(row.get("source")) or source,
    )


def split_examples(examples: Iterable[EvalExample]) -> EvalDataset:
    items = list(examples)
    if len(items) < 3:
        raise DatasetError("Evaluation dataset requires at least 3 examples for train/val/holdout")

    train_count = max(1, int(len(items) * 0.6))
    val_count = max(1, int(len(items) * 0.2))
    if train_count + val_count >= len(items):
        train_count = len(items) - 2
        val_count = 1

    return EvalDataset(
        train=items[:train_count],
        val=items[train_count:train_count + val_count],
        holdout=items[train_count + val_count:],
    )


def load_manual_dataset(path: str | Path) -> EvalDataset:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise DatasetError(f"Dataset file does not exist: {dataset_path}")
    if not dataset_path.is_file():
        raise DatasetError(f"Dataset path is not a file: {dataset_path}")

    examples: list[EvalExample] = []
    try:
        lines = dataset_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetError(f"Failed to read dataset file: {dataset_path}") from exc

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"Invalid JSON on dataset line {line_no}: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise DatasetError(f"Dataset line {line_no} must be a JSON object")
        examples.append(_example_from_dict(row, line_no, source="manual"))

    return split_examples(examples)


def _recall_to_example(result) -> EvalExample | None:
    content = _normalize_text(getattr(result, "content", ""))
    if not content:
        return None
    category = _normalize_text(getattr(result, "category", "")) or "memory"
    snippet = content[:180]
    lesson = content[:240]
    return EvalExample(
        task_input=f"Apply this Evolver lesson: {snippet}",
        expected_behavior=(
            "The response should preserve this lesson, apply it to the task, "
            f"and avoid repeating the failure mode if present: {lesson}"
        ),
        category=category,
        source="memory",
    )


def build_memory_dataset(evolver, query: str, top_k: int = 20) -> EvalDataset:
    if evolver is None:
        raise DatasetError("Memory dataset source requires an Evolver instance")
    results = evolver.recall(query, top_k=top_k)
    examples = []
    for result in results:
        example = _recall_to_example(result)
        if example is not None:
            examples.append(example)
    return split_examples(examples)


def build_dataset(config, artifact: SkillArtifact, evolver=None) -> EvalDataset:
    source = getattr(config, "dataset_source", "memory")
    if source == "manual":
        dataset_path = getattr(config, "dataset_path", None)
        if dataset_path is None:
            raise DatasetError("Manual dataset source requires dataset_path")
        return load_manual_dataset(dataset_path)
    if source == "memory":
        query = artifact.name.replace("-", " ") or artifact.description
        return build_memory_dataset(evolver, query)
    raise DatasetError(f"Unsupported dataset source: {source}")


def validate_constraints(
    artifact: SkillArtifact,
    dataset: EvalDataset,
    max_skill_size: int,
) -> list[ConstraintCheck]:
    checks = [
        ConstraintCheck(
            "skill_non_empty",
            bool(artifact.body.strip()),
            "Skill body is non-empty" if artifact.body.strip() else "Skill body is empty",
        ),
        ConstraintCheck(
            "frontmatter_name",
            bool(artifact.name.strip()),
            "Skill frontmatter has name" if artifact.name.strip() else "Skill frontmatter missing name",
        ),
        ConstraintCheck(
            "frontmatter_description",
            bool(artifact.description.strip()),
            "Skill frontmatter has description" if artifact.description.strip() else "Skill frontmatter missing description",
        ),
        ConstraintCheck(
            "workflow_section",
            bool(re.search(r"^##\s+(Steps|Workflow|Usage)\b", artifact.body, re.IGNORECASE | re.MULTILINE)),
            "Skill body has workflow section" if re.search(r"^##\s+(Steps|Workflow|Usage)\b", artifact.body, re.IGNORECASE | re.MULTILINE) else "Skill body missing ## Steps, ## Workflow, or ## Usage",
        ),
        ConstraintCheck(
            "skill_size",
            artifact.size <= max_skill_size,
            f"Skill size {artifact.size}/{max_skill_size}",
        ),
        ConstraintCheck(
            "dataset_splits",
            bool(dataset.train and dataset.val and dataset.holdout),
            f"Dataset split counts: {dataset.counts}",
        ),
        ConstraintCheck(
            "dataset_fields",
            all(example.task_input and example.expected_behavior for example in dataset.all_examples),
            "All dataset examples have task_input and expected_behavior",
        ),
    ]
    return checks


def _write_dataset_jsonl(path: Path, dataset: EvalDataset):
    lines = [json.dumps(example.to_dict(), ensure_ascii=False) for example in dataset.all_examples]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _report_payload(
    config: EvolutionConfig,
    artifact: SkillArtifact,
    dataset: EvalDataset,
    constraints: list[ConstraintCheck],
    status: str,
    errors: list[str],
    warnings: list[str],
) -> dict:
    return {
        "status": status,
        "skill_name": artifact.name,
        "skill_path": str(artifact.path),
        "dataset_source": config.dataset_source,
        "counts": dataset.counts,
        "constraints": [check.to_dict() for check in constraints],
        "errors": errors,
        "warnings": warnings,
        "next_phase_ready": status == "pass",
    }


def _readme_text(result: DryRunResult, artifact: SkillArtifact) -> str:
    return (
        f"# Offline Skill Evolution Dry Run: {artifact.name}\n\n"
        f"Status: `{result.status}`\n\n"
        f"Report: `{result.report_path.name}`\n\n"
        "Files:\n"
        "- `baseline.md`: source skill snapshot\n"
        "- `dataset.jsonl`: evaluation examples used by the dry run\n"
        "- `report.json`: machine-readable dry-run result\n"
    )


def write_run_output(
    config: EvolutionConfig,
    artifact: SkillArtifact,
    dataset: EvalDataset,
    constraints: list[ConstraintCheck],
    status: str,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> DryRunResult:
    run_dir = Path(config.output_dir) / f"{artifact.name}-{config.timestamp}"
    if run_dir.exists():
        raise OutputError(f"Run directory already exists: {run_dir}")

    try:
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "baseline.md").write_text(artifact.raw, encoding="utf-8")
        _write_dataset_jsonl(run_dir / "dataset.jsonl", dataset)
        report_path = run_dir / "report.json"
        payload = _report_payload(
            config=config,
            artifact=artifact,
            dataset=dataset,
            constraints=constraints,
            status=status,
            errors=errors or [],
            warnings=warnings or [],
        )
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        result = DryRunResult(
            status=status,
            run_dir=run_dir,
            report_path=report_path,
            constraints=constraints,
            errors=errors or [],
            warnings=warnings or [],
        )
        (run_dir / "README.md").write_text(_readme_text(result, artifact), encoding="utf-8")
        return result
    except OSError as exc:
        raise OutputError(f"Failed to write dry-run output: {run_dir}") from exc


def run_dry_run(config: EvolutionConfig, evolver=None) -> DryRunResult:
    if not config.dry_run:
        raise SkillEvolutionError("Only --dry-run is supported in Phase 1")

    artifact = load_skill_artifact(config.skill_path)
    dataset = build_dataset(config, artifact, evolver=evolver)
    constraints = validate_constraints(artifact, dataset, max_skill_size=config.max_skill_size)
    failed = [check for check in constraints if not check.passed]
    status = "fail" if failed else "pass"
    errors = [check.message for check in failed]
    result = write_run_output(config, artifact, dataset, constraints, status=status, errors=errors)

    if failed:
        raise ConstraintError(
            f"Constraint validation failed: {len(failed)} failure(s). Report: {result.report_path}",
            report_path=result.report_path,
        )
    return result
```

- [ ] **Step 4: Run skill evolution tests to verify they pass**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_evolution_*.py -v
```

Expected: PASS, 19 tests passed.

- [ ] **Step 5: Commit Task 3**

```bash
git add evolver/skill_evolution.py tests/test_skill_evolution_constraints.py
git commit -m "feat: add skill evolution dry-run reports"
```

## Task 4: CLI Command

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `evolver/cli.py`

- [ ] **Step 1: Write failing CLI tests**

Modify imports at the top of `tests/test_cli.py` to include `json`:

```python
"""Tests for evolver CLI."""
import json
import pytest
from click.testing import CliRunner
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from evolver.cli import cli, _receipt_database
```

Append these tests to `tests/test_cli.py`:

```python

def test_evolve_skill_dry_run_manual_dataset(runner, tmp_path):
    skill_path = tmp_path / "git-review.md"
    skill_path.write_text(
        """---
name: git-review
description: Use when reviewing git changes.
---

# Git Review

## Steps
1. Inspect the diff.
""",
        encoding="utf-8",
    )
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        "\n".join([
            json.dumps({"task_input": "one", "expected_behavior": "first"}),
            json.dumps({"task_input": "two", "expected_behavior": "second"}),
            json.dumps({"task_input": "three", "expected_behavior": "third"}),
        ]),
        encoding="utf-8",
    )
    output_dir = tmp_path / "runs"

    result = runner.invoke(cli, [
        "evolve-skill",
        "--skill-path", str(skill_path),
        "--dry-run",
        "--dataset-source", "manual",
        "--dataset-path", str(dataset_path),
        "--output-dir", str(output_dir),
    ])

    assert result.exit_code == 0
    assert "Dry-run pass" in result.output
    run_dirs = list(output_dir.iterdir())
    assert len(run_dirs) == 1
    report = json.loads((run_dirs[0] / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"


def test_evolve_skill_requires_dry_run(runner, tmp_path):
    skill_path = tmp_path / "git-review.md"
    skill_path.write_text(
        """---
name: git-review
description: Use when reviewing git changes.
---

## Steps
1. Inspect the diff.
""",
        encoding="utf-8",
    )

    result = runner.invoke(cli, ["evolve-skill", "--skill-path", str(skill_path)])

    assert result.exit_code == 2
    assert "only supports --dry-run" in result.output


def test_evolve_skill_invalid_skill_returns_code_2(runner, tmp_path):
    skill_path = tmp_path / "bad.md"
    skill_path.write_text("# Missing frontmatter", encoding="utf-8")
    output_dir = tmp_path / "runs"

    result = runner.invoke(cli, [
        "evolve-skill",
        "--skill-path", str(skill_path),
        "--dry-run",
        "--dataset-source", "manual",
        "--dataset-path", str(tmp_path / "missing.jsonl"),
        "--output-dir", str(output_dir),
    ])

    assert result.exit_code == 2
    assert "Error:" in result.output
    assert "pass" not in result.output.lower()
    assert not output_dir.exists()
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_cli.py::test_evolve_skill_dry_run_manual_dataset tests/test_cli.py::test_evolve_skill_requires_dry_run tests/test_cli.py::test_evolve_skill_invalid_skill_returns_code_2 -v
```

Expected: FAIL because the `evolve-skill` command does not exist.

- [ ] **Step 3: Add imports to CLI**

Modify the top of `evolver/cli.py` from:

```python
"""Evolver CLI — agent self-evolution engine."""
from pathlib import Path

import click
from evolver import __version__
from evolver.cli_helpers import make_evolver, format_output
from evolver.exceptions import EvolverError
```

to:

```python
"""Evolver CLI — agent self-evolution engine."""
from pathlib import Path

import click
from evolver import __version__
from evolver.cli_helpers import make_evolver, format_output
from evolver.exceptions import EvolverError
from evolver.skill_evolution import (
    ConstraintError,
    EvolutionConfig,
    OutputError,
    SkillEvolutionError,
    run_dry_run,
)
```

- [ ] **Step 4: Add `evolve-skill` command**

Add this command after the existing `skillgen()` command in `evolver/cli.py`:

```python
@cli.command(name="evolve-skill")
@click.option("--skill-path", required=True, type=click.Path(path_type=Path),
              help="Skill markdown file to validate for offline evolution")
@click.option("--db-url", default=None, help="Database URL for memory dataset source")
@click.option("--dataset-path", default=None, type=click.Path(path_type=Path),
              help="Manual JSONL dataset path")
@click.option("--dataset-source", type=click.Choice(["manual", "memory"]), default="memory",
              help="Dataset source for dry-run preflight")
@click.option("--output-dir", default="output/evolution-runs", type=click.Path(path_type=Path),
              help="Directory for dry-run run folders")
@click.option("--max-skill-size", default=15000, type=int,
              help="Maximum allowed skill file size in characters")
@click.option("--dry-run", is_flag=True, default=False,
              help="Run deterministic preflight without optimizer calls")
@click.pass_context
def evolve_skill(ctx, skill_path, db_url, dataset_path, dataset_source,
                 output_dir, max_skill_size, dry_run):
    """Validate a skill for offline evolution without optimizer calls."""
    if not dry_run:
        click.echo("Error: evolve-skill currently only supports --dry-run")
        ctx.exit(2)

    config = EvolutionConfig(
        skill_path=skill_path,
        db_url=db_url,
        dataset_path=dataset_path,
        dataset_source=dataset_source,
        output_dir=output_dir,
        max_skill_size=max_skill_size,
        dry_run=dry_run,
    )

    evo = None
    try:
        if dataset_source == "memory":
            kwargs = _build_kwargs(ctx)
            evo = make_evolver(db_url, **kwargs)
        result = run_dry_run(config, evolver=evo)
        click.echo(f"Dry-run {result.status}: {result.report_path}")
    except OutputError as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)
    except ConstraintError as e:
        click.echo(f"Error: {e}")
        ctx.exit(2)
    except SkillEvolutionError as e:
        click.echo(f"Error: {e}")
        ctx.exit(2)
    finally:
        if evo is not None:
            evo.close()
```

- [ ] **Step 5: Run targeted CLI tests to verify they pass**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_cli.py::test_evolve_skill_dry_run_manual_dataset tests/test_cli.py::test_evolve_skill_requires_dry_run tests/test_cli.py::test_evolve_skill_invalid_skill_returns_code_2 -v
```

Expected: PASS, 3 tests passed.

- [ ] **Step 6: Run full CLI tests to catch command regressions**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_cli.py -v
```

Expected: PASS, all CLI tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add evolver/cli.py tests/test_cli.py
git commit -m "feat: add evolve-skill dry-run command"
```

## Task 5: Final Verification

**Files:**
- Verify only; no expected file changes.

- [ ] **Step 1: Run skill evolution and CLI target suite**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill_evolution_*.py tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 2: Run existing focused skill/checker tests for regressions**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_skill.py tests/test_checker.py -v
```

Expected: PASS.

- [ ] **Step 3: Inspect git diff**

Run:

```bash
git diff --stat HEAD~4..HEAD
git diff HEAD~4..HEAD -- evolver/skill_evolution.py evolver/cli.py tests/test_skill_evolution_artifact.py tests/test_skill_evolution_dataset.py tests/test_skill_evolution_constraints.py tests/test_cli.py
```

Expected: Diff contains only the offline skill evolution module, CLI command, and tests described in this plan.

- [ ] **Step 4: Commit any verification-only adjustments**

If Step 1 or Step 2 required small fixes, commit only those files:

```bash
git add evolver/skill_evolution.py evolver/cli.py tests/test_skill_evolution_artifact.py tests/test_skill_evolution_dataset.py tests/test_skill_evolution_constraints.py tests/test_cli.py
git commit -m "fix: stabilize skill evolution dry-run"
```

Expected: If no fixes were needed, skip this commit.

## Plan Self-Review

- Spec coverage: artifact loading maps to Task 1; manual and memory datasets map to Task 2; constraints and report output map to Task 3; CLI and exit codes map to Task 4; verification maps to Task 5.
- Scope control: no DSPy, GEPA, model calls, database migrations, Hermes writes, or `SkillEngine.generate()` changes are included.
- Type consistency: `EvolutionConfig`, `SkillArtifact`, `EvalExample`, `EvalDataset`, `ConstraintCheck`, and `DryRunResult` are defined before use in later tasks.
- Test coverage: tests cover artifact parsing, invalid formats, manual JSONL, memory recall, constraints, report writing, CLI success, CLI dry-run requirement, and invalid input failure.
