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
    except (OSError, ValueError) as exc:
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

    if any(c in name for c in ("..", "/", "\\")):
        raise SkillFormatError("Skill name must not contain path separators")

    return SkillArtifact(
        path=skill_path,
        raw=raw,
        frontmatter=frontmatter,
        body=body,
        name=name,
        description=description,
        size=len(raw),
    )


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
    except (OSError, ValueError) as exc:
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
    source = config.dataset_source
    if source == "manual":
        dataset_path = config.dataset_path
        if dataset_path is None:
            raise DatasetError("Manual dataset source requires dataset_path")
        return load_manual_dataset(dataset_path)
    if source == "memory":
        query = artifact.name.replace("-", " ") or artifact.description
        return build_memory_dataset(evolver, query)
    raise DatasetError(f"Unsupported dataset source: {source}")


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


def validate_constraints(
    artifact: SkillArtifact,
    dataset: EvalDataset,
    max_skill_size: int,
) -> list[ConstraintCheck]:
    workflow_pattern = r"^##\s+(Steps|Workflow|Usage)\b"
    has_workflow = bool(re.search(workflow_pattern, artifact.body, re.IGNORECASE | re.MULTILINE))
    has_non_empty_body = bool(artifact.body)
    has_name = bool(artifact.name)
    has_description = bool(artifact.description)
    has_splits = bool(dataset.train and dataset.val and dataset.holdout)
    has_fields = all(example.task_input and example.expected_behavior for example in dataset.all_examples)

    checks = [
        ConstraintCheck(
            "skill_non_empty",
            has_non_empty_body,
            "Skill body is non-empty" if has_non_empty_body else "Skill body is empty",
        ),
        ConstraintCheck(
            "frontmatter_name",
            has_name,
            "Skill frontmatter has name" if has_name else "Skill frontmatter missing name",
        ),
        ConstraintCheck(
            "frontmatter_description",
            has_description,
            "Skill frontmatter has description" if has_description else "Skill frontmatter missing description",
        ),
        ConstraintCheck(
            "workflow_section",
            has_workflow,
            "Skill body has workflow section" if has_workflow else "Skill body missing ## Steps, ## Workflow, or ## Usage",
        ),
        ConstraintCheck(
            "skill_size",
            artifact.size <= max_skill_size,
            f"Skill size {artifact.size}/{max_skill_size}",
        ),
        ConstraintCheck(
            "dataset_splits",
            has_splits,
            f"Dataset split counts: {dataset.counts}",
        ),
        ConstraintCheck(
            "dataset_fields",
            has_fields,
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
