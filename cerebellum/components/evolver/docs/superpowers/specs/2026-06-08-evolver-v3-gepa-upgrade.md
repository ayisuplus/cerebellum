# Evolver v3.0 GEPA Skill Evolution — Design Spec

## Requirement

Evolver v2.3.0 generates skills via single-pass LLM synthesis and rule-based quality checking. The v3.0 upgrade adds iterative skill optimization using GEPA (Genetic Evolutionary Policy Algorithm): generate skill variants, evaluate via LLM-as-judge, select best, repeat. This closes the feedback loop from execution traces back into skill quality.

## Architecture

```
SkillEngine.generate()
    └─▶ (if evolve_iterations > 0)
        └─▶ GEPAEngine.optimize(skill_text, topic)
              │
              ├─▶ EvalDatasetBuilder.build() — train/val/holdout from memory or synthetic
              ├─▶ LLMJudge.evaluate() — multi-dimension LLM-as-judge scoring
              ├─▶ GEPA loop: mutate → evaluate → select → repeat
              └─▶ ConstraintValidator.check() — structural + semantic gate
```

Non-goals:
- Replace existing QualityChecker (`checker.py`) — rule-based and LLM-based evaluation coexist
- Add DSPy dependency — GEPA implemented directly via existing `LLMClient`
- Modify storage schema — evolution history stored in `evolution_log` table (already exists)

## Modules

### Module 1: EvolutionConfig (evolution_config.py)
- Data class: optimizer_model, eval_model, max_iterations, max_skill_size, cost_limit, dataset_config
- Default: optimizer=gpt-4.1-mini, eval=gpt-4.1-mini, max_iterations=5

### Module 2: ConstraintValidator (constraints.py)
- Validate skill structure (frontmatter, body, sections)
- Validate skill size (char limit)
- Validate semantic preservation (LLM checks meaning hasn't drifted)
- Validate test gates (eval dataset pass rate)

### Module 3: EvalDatasetBuilder (eval_dataset.py)
- Build train/val/holdout from: memory recall, synthetic generation, manual JSONL
- Reuse existing `EvalExample`, `EvalDataset` from `skill_evolution.py`

### Module 4: LLMJudge (llm_judge.py)
- Evaluate skill quality across 4 LLM dimensions: instruction following, output quality, efficiency, robustness
- Scores 1-10 per dimension, weighted to 0-100 total
- Reuse existing `EvalResult` model

### Module 5: GEPAEngine (gepa_engine.py)
- Population: maintain N skill text variants
- Mutation: LLM generates a variant by applying a directed improvement prompt
- Evaluation: each variant scored by LLMJudge on eval dataset
- Selection: keep top-K variants, discard rest
- Termination: max iterations OR score plateau

### Module 6: ExecutionTracer (execution_tracer.py)
- Collect skill execution traces (input, output, errors, duration)
- Store in `evolution_log` as structured JSON
- Used by GEPA for reflection-based mutation

### Module 7: HermesIntegration (hermes_integration.py)
- Evolve skills in ~/.hermes/skills/ directory
- Auto-backup, evolve, validate, write

### Module 8: SkillEngine modifications (skill.py)
- `__init__`: accept optional `gepa_engine` parameter (None = backward compatible)
- `generate()`: when `evolve_iterations > 0`, call GEPAEngine.post_process() after synthesis

### Module 9: CLI modifications (cli.py)
- `evolver evolve-skill` — evolve an existing skill file with full GEPA pipeline
- `evolver judge-skill` — evaluate skill via LLM-as-judge only

## Data Flow

```
SkillEngine.generate(topic)
  → LLM synthesis (existing)
  → QualityChecker.check_and_improve (existing, rule-based)
  → if evolve_iterations > 0:
      → GEPAEngine.optimize(skill_text, topic)
        1. EvalDatasetBuilder.build() from memories
        2. Loop N iterations:
           a. Mutate skill text (LLM)
           b. Evaluate all variants (LLMJudge)
           c. Select top variant
           d. Check ConstraintValidator
           e. Check plateau → break
        3. Return optimized skill text
  → Write files (existing)
  → Log event
```

## Database

No new tables. Evolution events logged to existing `evolution_log` table with event_type="gepa_evolution".

## Constraints

| Constraint | Check |
|-----------|-------|
| Structure | Frontmatter + body sections exist |
| Size | Skill text ≤ max_skill_size chars |
| Semantic preservation | LLM verifies meaning preserved (score ≥ 7/10) |
| Test gate | Eval dataset pass rate ≥ 0.7 |

## Risk

| Risk | Mitigation |
|------|-----------|
| LLM cost overrun | max_iterations (default 5) + cost_limit |
| Quality regression | ConstraintValidator blocks regressions |
| Semantic drift | Semantic preservation check each iteration |
