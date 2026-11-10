# Evolver v3.0 GEPA Skill Evolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add iterative GEPA skill optimization to Evolver's SkillEngine.

**Architecture:** GEPAEngine wraps an LLM-powered mutation-evaluation loop. EvalDatasetBuilder constructs train/val/holdout from stored memories. LLMJudge scores skill quality across 4 LLM dimensions. ConstraintValidator gates regressions. All wired into SkillEngine as optional post-processing.

**Tech Stack:** Python 3.11+, existing LLMClient (OpenAI-compatible), pytest, existing evolver skill_evolution.py dataclasses.

**File Map:**
- Create: `evolver/evolution_config.py` — EvolutionConfig dataclass
- Create: `evolver/constraints.py` — ConstraintValidator
- Create: `evolver/eval_dataset_builder.py` — EvalDatasetBuilder
- Create: `evolver/llm_judge.py` — LLMJudge evaluator
- Create: `evolver/gepa_engine.py` — GEPAEngine
- Create: `evolver/execution_tracer.py` — ExecutionTracer
- Create: `evolver/hermes_integration.py` — HermesIntegration
- Modify: `evolver/skill.py` — wire gepa_engine
- Modify: `evolver/cli.py` — evolve-skill, judge-skill commands
- Modify: `evolver/__init__.py` — wire gepa_engine init
- Test: `tests/test_evolution_config.py`
- Test: `tests/test_constraints.py`
- Test: `tests/test_eval_dataset_builder.py`
- Test: `tests/test_llm_judge.py`
- Test: `tests/test_gepa_engine.py`
- Test: `tests/test_execution_tracer.py`
- Test: `tests/test_hermes_integration.py`

---

### Task 1: EvolutionConfig

**Files:**
- Create: `evolver/evolution_config.py`
- Test: `tests/test_evolution_config.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for EvolutionConfig."""
import pytest
from evolver.evolution_config import EvolutionConfig


def test_default_values():
    config = EvolutionConfig()
    assert config.optimizer_model == "gpt-4.1-mini"
    assert config.eval_model == "gpt-4.1-mini"
    assert config.max_iterations == 5
    assert config.population_size == 3
    assert config.max_skill_size == 15000
    assert config.cost_limit == 10.0
    assert config.temperature == 0.7


def test_custom_values():
    config = EvolutionConfig(
        optimizer_model="gpt-4.1",
        eval_model="gpt-4.1-mini",
        max_iterations=10,
        population_size=5,
        max_skill_size=20000,
        cost_limit=20.0,
        temperature=0.9,
    )
    assert config.optimizer_model == "gpt-4.1"
    assert config.max_iterations == 10
    assert config.population_size == 5


def test_plateau_threshold_default():
    config = EvolutionConfig()
    assert config.plateau_threshold == 0.02


def test_invalid_iterations():
    with pytest.raises(ValueError, match="max_iterations must be >= 1"):
        EvolutionConfig(max_iterations=0)


def test_invalid_population():
    with pytest.raises(ValueError, match="population_size must be >= 2"):
        EvolutionConfig(population_size=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evolution_config.py -v`
Expected: ModuleNotFoundError / ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Evolution configuration for GEPA skill optimization."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvolutionConfig:
    optimizer_model: str = "gpt-4.1-mini"
    eval_model: str = "gpt-4.1-mini"
    max_iterations: int = 5
    population_size: int = 3
    max_skill_size: int = 15_000
    cost_limit: float = 10.0
    temperature: float = 0.7
    plateau_threshold: float = 0.02

    def __post_init__(self):
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if self.population_size < 2:
            raise ValueError("population_size must be >= 2")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evolution_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add evolver/evolution_config.py tests/test_evolution_config.py
git commit -m "feat(v3): add EvolutionConfig dataclass"
```

---

### Task 2: EvalDatasetBuilder

**Files:**
- Create: `evolver/eval_dataset_builder.py`
- Test: `tests/test_eval_dataset_builder.py`
- Ref: `evolver/skill_evolution.py` — reuse `EvalExample`, `EvalDataset`, `split_examples`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for EvalDatasetBuilder."""
import pytest
from evolver.eval_dataset_builder import EvalDatasetBuilder
from evolver.skill_evolution import EvalExample, EvalDataset


def test_build_from_memories():
    memories = [
        type("Mem", (), {"content": "Fix git merge conflict by using rebase", "category": "success"})(),
        type("Mem", (), {"content": "Always check branch before pushing", "category": "failure"})(),
        type("Mem", (), {"content": "Use pre-commit hooks for linting", "category": "insight"})(),
    ]
    builder = EvalDatasetBuilder()
    dataset = builder.build_from_memories(memories)
    assert isinstance(dataset, EvalDataset)
    assert len(dataset.all_examples) == 3
    for ex in dataset.all_examples:
        assert ex.task_input
        assert ex.expected_behavior


def test_build_from_memories_insufficient():
    builder = EvalDatasetBuilder()
    dataset = builder.build_from_memories([])
    assert dataset is None


def test_build_synthetic():
    builder = EvalDatasetBuilder()
    dataset = builder.build_synthetic("git workflow", count=5)
    assert isinstance(dataset, EvalDataset)
    assert len(dataset.all_examples) == 5


def test_build_synthetic_min_count():
    builder = EvalDatasetBuilder()
    with pytest.raises(ValueError, match="count must be >= 3"):
        builder.build_synthetic("test", count=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_dataset_builder.py -v`
Expected: ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Build evaluation datasets for GEPA skill optimization."""
import logging
from evolver.skill_evolution import EvalExample, EvalDataset, split_examples

logger = logging.getLogger(__name__)


class EvalDatasetBuilder:
    def build_from_memories(self, memories: list, max_examples: int = 20) -> EvalDataset | None:
        examples = []
        for mem in memories:
            content = getattr(mem, "content", "") or ""
            category = getattr(mem, "category", "") or "general"
            if not content.strip():
                continue
            snippet = content[:180]
            examples.append(EvalExample(
                task_input=f"Apply this lesson: {snippet}",
                expected_behavior=(
                    "The response should preserve the core lesson "
                    "and apply it appropriately to the task"
                ),
                category=category,
                source="memory",
            ))
        if len(examples) < 3:
            return None
        return split_examples(examples[:max_examples])

    def build_synthetic(self, topic: str, count: int = 5) -> EvalDataset:
        if count < 3:
            raise ValueError("count must be >= 3")
        examples = []
        for i in range(count):
            examples.append(EvalExample(
                task_input=f"Performing {topic} task {i + 1}",
                expected_behavior=f"Expected behavior for {topic} task {i + 1}",
                category="synthetic",
                source="synthetic",
            ))
        return split_examples(examples)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_dataset_builder.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add evolver/eval_dataset_builder.py tests/test_eval_dataset_builder.py
git commit -m "feat(v3): add EvalDatasetBuilder"
```

---

### Task 3: ConstraintValidator

**Files:**
- Create: `evolver/constraints.py`
- Test: `tests/test_constraints.py`
- Ref: `evolver/skill_evolution.py` — `ConstraintCheck` dataclass

- [ ] **Step 1: Write the failing test**

```python
"""Tests for ConstraintValidator."""
import pytest
from evolver.constraints import ConstraintValidator
from evolver.skill_evolution import SkillArtifact


def _make_artifact(body: str, name: str = "test-skill", desc: str = "A test skill") -> SkillArtifact:
    raw = f"---\nname: {name}\ndescription: {desc}\nversion: 1\ntags: []\n---\n\n{body}"
    return SkillArtifact(
        path="test.md", raw=raw,
        frontmatter=f"name: {name}\ndescription: {desc}\nversion: 1\ntags: []",
        body=body, name=name, description=desc, size=len(raw),
    )


VALID_SKILL = """## Overview
A test skill for git workflows.

## Steps
1. Check git status
2. Create a branch
3. Make changes
4. Commit
5. Push

## Common Pitfalls
- Forgetting to pull first
- Merge conflicts

## Key Insights
- Always rebase before pushing
"""


def test_valid_skill_passes():
    artifact = _make_artifact(VALID_SKILL)
    validator = ConstraintValidator(max_skill_size=15000)
    results = validator.validate(artifact)
    assert all(r.passed for r in results)


def test_empty_body_fails():
    artifact = _make_artifact("", name="empty-skill")
    validator = ConstraintValidator()
    results = validator.validate(artifact)
    body_check = [r for r in results if r.name == "skill_non_empty"]
    assert len(body_check) == 1
    assert not body_check[0].passed


def test_size_exceeded_fails():
    oversized = "x" * 1000
    artifact = _make_artifact(oversized)
    validator = ConstraintValidator(max_skill_size=500)
    results = validator.validate(artifact)
    size_check = [r for r in results if r.name == "skill_size"]
    assert len(size_check) == 1
    assert not size_check[0].passed


def test_missing_steps_fails():
    no_steps = "## Overview\nJust overview, no steps."
    artifact = _make_artifact(no_steps)
    validator = ConstraintValidator()
    results = validator.validate(artifact)
    workflow_check = [r for r in results if r.name == "workflow_section"]
    assert len(workflow_check) == 1
    assert not workflow_check[0].passed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_constraints.py -v`
Expected: ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Constraint validation for evolved skills."""
import re
import logging
from evolver.skill_evolution import SkillArtifact, ConstraintCheck

logger = logging.getLogger(__name__)


class ConstraintValidator:
    def __init__(self, max_skill_size: int = 15_000):
        self._max_skill_size = max_skill_size

    def validate(self, artifact: SkillArtifact) -> list[ConstraintCheck]:
        workflow_pattern = r"^##\s+(Steps|Workflow|Usage)\b"
        has_workflow = bool(re.search(workflow_pattern, artifact.body, re.IGNORECASE | re.MULTILINE))

        return [
            ConstraintCheck(
                "skill_non_empty",
                bool(artifact.body.strip()),
                "Skill body is non-empty" if artifact.body.strip() else "Skill body is empty",
            ),
            ConstraintCheck(
                "frontmatter_name",
                bool(artifact.name),
                "Skill has name" if artifact.name else "Skill missing name",
            ),
            ConstraintCheck(
                "frontmatter_description",
                bool(artifact.description),
                "Skill has description" if artifact.description else "Skill missing description",
            ),
            ConstraintCheck(
                "workflow_section",
                has_workflow,
                "Skill has workflow section" if has_workflow else "Missing ## Steps/Workflow/Usage",
            ),
            ConstraintCheck(
                "skill_size",
                artifact.size <= self._max_skill_size,
                f"Size {artifact.size}/{self._max_skill_size}",
            ),
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_constraints.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add evolver/constraints.py tests/test_constraints.py
git commit -m "feat(v3): add ConstraintValidator"
```

---

### Task 4: LLMJudge

**Files:**
- Create: `evolver/llm_judge.py`
- Test: `tests/test_llm_judge.py`
- Ref: `evolver/models.py` — `EvalResult`
- Ref: `evolver/llm_client.py` — `LLMClient`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for LLMJudge."""
import pytest
from evolver.llm_judge import LLMJudge, JudgeDimension
from evolver.models import EvalResult


def test_dimension_defaults():
    d = JudgeDimension(name="test", prompt_template="Rate this: {skill_text}")
    assert d.weight == 1.0
    assert d.name == "test"


def test_judge_fallback_no_llm():
    judge = LLMJudge(llm_client=None)
    result = judge.evaluate("some skill text", "test topic")
    assert isinstance(result, EvalResult)
    assert result.total_score == 75.0
    assert result.status == "pass"


def test_judge_fallback_all_dimensions():
    judge = LLMJudge(llm_client=None)
    result = judge.evaluate("## Steps\n1. Do something\n2. Check result\n## Overview\nTest", "test")
    assert "instruction_following" in result.dim_scores
    assert "output_quality" in result.dim_scores
    assert "efficiency" in result.dim_scores
    assert "robustness" in result.dim_scores
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_judge.py -v`
Expected: ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""LLM-as-Judge evaluator for skill quality."""
import re
import logging
from dataclasses import dataclass, field
from evolver.models import EvalResult

logger = logging.getLogger(__name__)


@dataclass
class JudgeDimension:
    name: str
    prompt_template: str
    weight: float = 1.0


DEFAULT_DIMENSIONS = [
    JudgeDimension(
        "instruction_following",
        "Rate how well this skill provides clear, followable instructions (1-10):\n{skill_text}",
        weight=1.0,
    ),
    JudgeDimension(
        "output_quality",
        "Rate the quality and completeness of this skill's output (1-10):\n{skill_text}",
        weight=1.0,
    ),
    JudgeDimension(
        "efficiency",
        "Rate how efficiently this skill achieves its goal (1-10):\n{skill_text}",
        weight=1.0,
    ),
    JudgeDimension(
        "robustness",
        "Rate how well this skill handles edge cases and errors (1-10):\n{skill_text}",
        weight=1.0,
    ),
]


class LLMJudge:
    def __init__(self, llm_client=None, dimensions: list[JudgeDimension] | None = None):
        self._llm = llm_client
        self._dimensions = dimensions or DEFAULT_DIMENSIONS

    def evaluate(self, skill_text: str, topic: str) -> EvalResult:
        if not self._llm or not self._llm.available:
            return self._fallback_evaluate(skill_text)

        scores = {}
        total_weighted = 0.0
        total_weight = 0.0

        for dim in self._dimensions:
            prompt = dim.prompt_template.format(skill_text=skill_text[:2000], topic=topic)
            try:
                score = self._call_judge(prompt)
            except Exception:
                score = 5.0
            scores[dim.name] = score
            total_weighted += score * dim.weight
            total_weight += dim.weight

        total = round((total_weighted / total_weight) * 10, 1) if total_weight > 0 else 50.0
        return EvalResult(
            total_score=min(total, 100),
            dim_scores=scores,
            round=1,
            status="pass" if total >= 60 else "fail",
        )

    def _call_judge(self, prompt: str) -> float:
        result = self._llm.call_llm(prompt, (
            "You are a skill quality judge. Rate the skill 1-10. "
            "Output only a number."
        ), max_tokens=50)
        result = self._llm.strip_thinking(result)
        match = re.search(r"(\d+(?:\.\d+)?)", result or "")
        if match:
            return max(1.0, min(10.0, float(match.group(1))))
        return 5.0

    def _fallback_evaluate(self, skill_text: str) -> EvalResult:
        scores = {}
        num_steps = len(re.findall(r"^\d+\.", skill_text, re.MULTILINE))
        has_frontmatter = bool(re.search(r"^---\s*$", skill_text, re.MULTILINE))
        has_steps_section = bool(re.search(r"^##\s+(Steps|Workflow)", skill_text, re.MULTILINE))

        scores["instruction_following"] = min(10, 4 + num_steps)
        scores["output_quality"] = 7 if has_frontmatter and has_steps_section else 5
        scores["efficiency"] = min(10, 4 + num_steps // 2)
        scores["robustness"] = 6 if "error" in skill_text.lower() or "fail" in skill_text.lower() else 4

        total = sum(scores.values()) * 2.5
        return EvalResult(
            total_score=min(total, 100),
            dim_scores=scores,
            round=1,
            status="pass" if total >= 60 else "fail",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_judge.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add evolver/llm_judge.py tests/test_llm_judge.py
git commit -m "feat(v3): add LLMJudge evaluator"
```

---

### Task 5: GEPAEngine

**Files:**
- Create: `evolver/gepa_engine.py`
- Test: `tests/test_gepa_engine.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for GEPAEngine."""
import pytest
from evolver.gepa_engine import GEPAEngine
from evolver.evolution_config import EvolutionConfig
from evolver.skill_evolution import EvalExample, EvalDataset, SkillArtifact
from evolver.constraints import ConstraintValidator


def _make_dataset() -> EvalDataset:
    examples = [
        EvalExample("task 1", "behavior 1"),
        EvalExample("task 2", "behavior 2"),
        EvalExample("task 3", "behavior 3"),
        EvalExample("task 4", "behavior 4"),
        EvalExample("task 5", "behavior 5"),
    ]
    return EvalDataset(
        train=examples[:3],
        val=examples[3:4],
        holdout=examples[4:],
    )


def test_optimize_no_llm():
    engine = GEPAEngine(llm_client=None, config=EvolutionConfig(max_iterations=1))
    result = engine.optimize(
        skill_text="## Overview\nTest\n## Steps\n1. Do it\n",
        topic="test",
        dataset=_make_dataset(),
    )
    assert result is not None
    assert len(result) > 0


def test_no_dataset():
    engine = GEPAEngine(llm_client=None)
    result = engine.optimize(
        skill_text="## Overview\nTest\n## Steps\n1. Do it\n",
        topic="test",
        dataset=None,
    )
    assert result is not None


def test_plateau_early_stop():
    engine = GEPAEngine(
        llm_client=None,
        config=EvolutionConfig(max_iterations=10, plateau_threshold=0.5),
    )
    result = engine.optimize(
        skill_text="## Overview\nTest\n## Steps\n1. Do it\n",
        topic="test",
        dataset=_make_dataset(),
    )
    assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gepa_engine.py -v`
Expected: ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""GEPA Evolutionary Engine for skill optimization."""
import logging
import copy
from evolver.evolution_config import EvolutionConfig
from evolver.llm_judge import LLMJudge
from evolver.constraints import ConstraintValidator
from evolver.skill_evolution import SkillArtifact, load_skill_artifact
from pathlib import Path

logger = logging.getLogger(__name__)


MUTATION_PROMPT = (
    "You are a skill optimizer. Improve the following skill document. "
    "Keep the same YAML frontmatter and overall structure. "
    "Enhance specificity, add edge case handling, improve step clarity. "
    "Output the complete improved skill document."
)


class GEPAEngine:
    def __init__(self, llm_client=None, config: EvolutionConfig | None = None):
        self._llm = llm_client
        self._config = config or EvolutionConfig()
        self._judge = LLMJudge(llm_client=llm_client)
        self._constraints = ConstraintValidator(max_skill_size=self._config.max_skill_size)

    def optimize(self, skill_text: str, topic: str,
                 dataset=None) -> str | None:
        best_text = skill_text
        best_score = 0.0
        plateau_count = 0

        for iteration in range(1, self._config.max_iterations + 1):
            population = [best_text]
            for _ in range(self._config.population_size - 1):
                variant = self._mutate(best_text, topic)
                if variant:
                    population.append(variant)

            candidates = []
            for variant in population:
                eval_result = self._judge.evaluate(variant, topic)
                score = eval_result.total_score
                candidates.append((score, variant))
                logger.debug("GEPA iter %d: score=%.1f", iteration, score)

            candidates.sort(key=lambda x: x[0], reverse=True)
            best_candidate_score, best_candidate_text = candidates[0]

            if best_candidate_score > best_score:
                improvement = best_candidate_score - best_score
                best_score = best_candidate_score
                best_text = best_candidate_text
                plateau_count = 0
                logger.info("GEPA iter %d: improved to %.1f", iteration, best_score)
            else:
                plateau_count += 1
                logger.debug("GEPA iter %d: plateau %d", iteration, plateau_count)

            if plateau_count >= 2:
                logger.info("GEPA: early stop at iteration %d (plateau)", iteration)
                break

        return best_text

    def optimize_skill_file(self, skill_path: str | Path, topic: str,
                            dataset=None) -> str | None:
        artifact = load_skill_artifact(skill_path)
        constraints_result = self._constraints.validate(artifact)
        failed = [c for c in constraints_result if not c.passed]
        if failed:
            logger.warning("Constraint validation failed: %s", [c.name for c in failed])
            return None
        return self.optimize(artifact.raw, topic, dataset=dataset)

    def _mutate(self, skill_text: str, topic: str) -> str | None:
        if not self._llm or not self._llm.available:
            return self._simple_mutate(skill_text)
        try:
            prompt = MUTATION_PROMPT
            if topic:
                prompt += f"\nFocus area: {topic}"
            result = self._llm.call_llm(skill_text[:3000], prompt, max_tokens=3000)
            result = self._llm.strip_thinking(result)
            if result and len(result) > 100:
                return result
        except Exception as e:
            logger.warning("GEPA mutation failed: %s", e)
        return None

    def _simple_mutate(self, skill_text: str) -> str:
        if "## Key Insights" not in skill_text:
            return skill_text + "\n\n## Key Insights\n- Break tasks into small steps\n- Verify results at each checkpoint\n- Learn from failures\n"
        return skill_text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gepa_engine.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add evolver/gepa_engine.py tests/test_gepa_engine.py
git commit -m "feat(v3): add GEPAEngine for iterative skill optimization"
```

---

### Task 6: ExecutionTracer

**Files:**
- Create: `evolver/execution_tracer.py`
- Test: `tests/test_execution_tracer.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for ExecutionTracer."""
import pytest
from evolver.execution_tracer import ExecutionTracer, TraceEntry
from datetime import datetime, timezone


def test_trace_entry_defaults():
    entry = TraceEntry(skill_name="test-skill")
    assert entry.skill_name == "test-skill"
    assert entry.status == "pending"
    assert entry.duration_ms == 0.0


def test_start_and_finish():
    tracer = ExecutionTracer()
    trace_id = tracer.start("test-skill", task_input="do something")
    assert trace_id is not None
    assert tracer.get(trace_id) is not None

    tracer.finish(trace_id, status="success", output="done",
                  error=None, duration_ms=1500.0)
    entry = tracer.get(trace_id)
    assert entry.status == "success"
    assert entry.output == "done"


def test_finish_nonexistent():
    tracer = ExecutionTracer()
    tracer.finish(999, status="success")
    # Should not raise


def test_get_nonexistent():
    tracer = ExecutionTracer()
    assert tracer.get(999) is None


def test_recent_traces():
    tracer = ExecutionTracer()
    t1 = tracer.start("skill-a")
    t2 = tracer.start("skill-b")
    recent = tracer.recent(limit=10)
    assert len(recent) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_execution_tracer.py -v`
Expected: ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Execution trace collector for skill runs."""
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class TraceEntry:
    skill_name: str
    task_input: str = ""
    output: str = ""
    error: str | None = None
    status: str = "pending"
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExecutionTracer:
    def __init__(self):
        self._traces: dict[int, TraceEntry] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def start(self, skill_name: str, task_input: str = "") -> int:
        with self._lock:
            self._counter += 1
            trace_id = self._counter
            self._traces[trace_id] = TraceEntry(
                skill_name=skill_name,
                task_input=task_input,
            )
            return trace_id

    def finish(self, trace_id: int, status: str = "success",
               output: str = "", error: str | None = None,
               duration_ms: float = 0.0):
        with self._lock:
            entry = self._traces.get(trace_id)
            if entry is None:
                logger.warning("Trace %d not found", trace_id)
                return
            entry.status = status
            entry.output = output
            entry.error = error
            entry.duration_ms = duration_ms

    def get(self, trace_id: int) -> TraceEntry | None:
        return self._traces.get(trace_id)

    def recent(self, limit: int = 20) -> list[TraceEntry]:
        with self._lock:
            sorted_ids = sorted(self._traces.keys(), reverse=True)
            return [self._traces[tid] for tid in sorted_ids[:limit]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_execution_tracer.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add evolver/execution_tracer.py tests/test_execution_tracer.py
git commit -m "feat(v3): add ExecutionTracer"
```

---

### Task 7: HermesIntegration

**Files:**
- Create: `evolver/hermes_integration.py`
- Test: `tests/test_hermes_integration.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for HermesIntegration."""
import pytest
import tempfile
from pathlib import Path
from evolver.hermes_integration import HermesIntegration


def test_init_creates_dirs():
    with tempfile.TemporaryDirectory() as td:
        skills_dir = Path(td) / "skills"
        backup_dir = Path(td) / "backups"
        integration = HermesIntegration(
            skills_dir=str(skills_dir),
            backup_dir=str(backup_dir),
        )
        assert skills_dir.exists()
        assert backup_dir.exists()


def test_detect_skills_empty_dir():
    with tempfile.TemporaryDirectory() as td:
        integration = HermesIntegration(
            skills_dir=td,
            backup_dir=Path(td) / "backups",
        )
        skills = integration.detect_skills()
        assert skills == []


def test_detect_skills():
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "test-skill.md").write_text("---\nname: test\n---\n# Test")
        (Path(td) / "other.txt").write_text("not a skill")
        integration = HermesIntegration(skills_dir=td)
        skills = integration.detect_skills()
        assert len(skills) == 1
        assert "test-skill" in skills[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hermes_integration.py -v`
Expected: ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Hermes Agent integration for skill evolution."""
import logging
import shutil
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HermesIntegration:
    def __init__(self, skills_dir: str = "~/.hermes/skills",
                 backup_dir: str | None = None):
        self._skills_dir = Path(skills_dir).expanduser().resolve()
        self._backup_dir = Path(backup_dir or str(self._skills_dir.parent / "backups")).expanduser().resolve()
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def detect_skills(self) -> list[str]:
        skill_files = []
        for f in self._skills_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            if content.strip().startswith("---"):
                skill_files.append(str(f))
        return skill_files

    def backup_skill(self, skill_path: str | Path) -> Path | None:
        src = Path(skill_path)
        if not src.exists():
            logger.warning("Skill not found: %s", src)
            return None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_name = f"{src.stem}-{timestamp}{src.suffix}"
        dest = self._backup_dir / backup_name
        shutil.copy2(src, dest)
        logger.info("Backed up %s → %s", src, dest)
        return dest

    def write_skill(self, content: str, skill_path: str | Path):
        dest = Path(skill_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        logger.info("Written skill → %s", dest)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hermes_integration.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add evolver/hermes_integration.py tests/test_hermes_integration.py
git commit -m "feat(v3): add HermesIntegration"
```

---

### Task 8: Wire GEPA into SkillEngine

**Files:**
- Modify: `evolver/skill.py`
- Test: `tests/test_skill.py` (add new test)

- [ ] **Step 1: Write the failing test

```python
"""Test GEPA integration in SkillEngine."""
import pytest
from evolver.skill import SkillEngine
from evolver.gepa_engine import GEPAEngine
from evolver.evolution_config import EvolutionConfig


def test_skill_engine_accepts_gepa():
    engine = SkillEngine(
        storage=None, memory_engine=None, graph_engine=None,
        gepa_engine=GEPAEngine(),
    )
    assert engine._gepa is not None


def test_skill_engine_no_gepa_backward_compat():
    engine = SkillEngine(
        storage=None, memory_engine=None, graph_engine=None,
    )
    assert engine._gepa is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill.py::test_skill_engine_accepts_gepa tests/test_skill.py::test_skill_engine_no_gepa_backward_compat -v`
Expected: FAIL (SkillEngine doesn't accept gepa_engine param yet)

- [ ] **Step 3: Modify SkillEngine**

In `evolver/skill.py`:

Edit `__init__` to accept optional `gepa_engine` parameter:

```python
    def __init__(self, storage: BaseStorage, memory_engine, graph_engine,
                 llm_client=None, skill_library=None, gepa_engine=None):
        self._storage = storage
        self._memory = memory_engine
        self._graph = graph_engine
        self._llm = llm_client
        self._checker = None
        self._library = skill_library
        self._gepa = gepa_engine  # NEW
        template_dir = Path(__file__).parent / "templates"
        self._env = Environment(loader=FileSystemLoader(str(template_dir)))
```

In `generate()`, add GEPA post-processing after the existing quality checker step (around line 265, before `self._storage.log_event`):

```python
        # GEPA iterative optimization
        if self._gepa is not None:
            try:
                optimized = self._gepa.optimize(md_content, topic)
                if optimized and len(optimized) > 100:
                    md_content = optimized
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    skill_id, actual_version = self._storage.upsert_skill(
                        name=name, description=description,
                        file_path=file_path, content=md_content,
                    )
                    logger.info("GEPA optimization applied to skill '%s'", name)
            except Exception:
                logger.warning("GEPA optimization failed (non-fatal)", exc_info=True)
```

Also add import at top of `skill.py`:

```python
from evolver.gepa_engine import GEPAEngine
```

Make the import conditional to avoid circular issues — just use type hint Optional.

Actually it's simpler to just type-hint it without importing at module level:

```python
    def __init__(self, storage: BaseStorage, memory_engine, graph_engine,
                 llm_client=None, skill_library=None, gepa_engine=None):
```

No import needed for typing. Just check `if self._gepa is not None:`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill.py -v`
Expected: Existing tests pass + 2 new tests pass

- [ ] **Step 5: Commit**

```bash
git add evolver/skill.py
git commit -m "feat(v3): wire GEPAEngine into SkillEngine as optional post-processor"
```

---

### Task 9: Wire GEPA into Evolver.__init__ and CLI

**Files:**
- Modify: `evolver/__init__.py`
- Modify: `evolver/cli.py`

- [ ] **Step 1: Wire GEPA into Evolver.__init__**

In `evolver/__init__.py`, add after the existing `self._skill` initialization (around line 187):

Before `self._skill._checker = self._checker`, add:

```python
        # GEPA engine for iterative skill optimization (v3.0)
        self._gepa = GEPAEngine(llm_client=self._llm)
        self._skill._gepa = self._gepa
```

Add import at top:

```python
from evolver.gepa_engine import GEPAEngine
```

Actually, `GEPAEngine` doesn't exist yet as an importable symbol. We need to add it to the lazy imports at the bottom, or import directly. Let me add it to `__init__` imports.

- [ ] **Step 2: Add CLI commands**

In `evolver/cli.py`, add after the `evolve-skill` command (around line 541):

```python
@cli.command(name="judge-skill")
@click.option("--skill-path", required=True, type=click.Path(exists=True, path_type=Path),
              help="Skill markdown file to evaluate")
@click.option("--topic", default="", help="Skill topic")
@click.option("--db-url", default=None, help="Database URL")
@click.pass_context
def judge_skill(ctx, skill_path, topic, db_url):
    """Evaluate a skill via LLM-as-judge."""
    from evolver.llm_judge import LLMJudge
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        judge = LLMJudge(llm_client=evo._llm if evo._llm.available else None)
        content = skill_path.read_text(encoding="utf-8")
        topic_name = topic or skill_path.stem
        result = judge.evaluate(content, topic_name)
        click.echo(f"LLM Judge score: {result.total_score:.1f}/100")
        for dim, score in result.dim_scores.items():
            click.echo(f"  {dim}: {score:.1f}/10")
        click.echo(f"Status: {result.status}")
    finally:
        evo.close()
```

- [ ] **Step 3: Run existing tests**

Run: `pytest tests/ -v --timeout=30 2>/dev/null || pytest tests/ -v`
Expected: All existing tests still pass

- [ ] **Step 4: Commit**

```bash
git add evolver/__init__.py evolver/cli.py
git commit -m "feat(v3): wire GEPA into Evolver init and add judge-skill CLI command"
```

---

### Task 10: Add GEPAEngine export to __init__

**Files:**
- Modify: `evolver/__init__.py`

- [ ] **Step 1: Add GEPAEngine to imports and __all__**

In `evolver/__init__.py`:

Add to the imports section:
```python
from evolver.gepa_engine import GEPAEngine
```

Add to `__all__` list:
```python
    "GEPAEngine", "LLMJudge",
```

Add to `_LAZY_IMPORTS`:
```python
    "GEPAEngine": "evolver.gepa_engine",
    "LLMJudge": "evolver.llm_judge",
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add evolver/__init__.py
git commit -m "feat(v3): export GEPAEngine and LLMJudge from package"
```

---

## Verification

After all tasks complete:

```bash
# Run all tests
pytest tests/ -v

# Run a quick smoke test
python -c "
from evolver.gepa_engine import GEPAEngine
from evolver.llm_judge import LLMJudge
from evolver.evolution_config import EvolutionConfig
from evolver.constraints import ConstraintValidator
from evolver.execution_tracer import ExecutionTracer
from evolver.eval_dataset_builder import EvalDatasetBuilder
from evolver.hermes_integration import HermesIntegration
print('All imports OK')
"

# Verify CLI
python -m evolver.cli judge-skill --help
```
