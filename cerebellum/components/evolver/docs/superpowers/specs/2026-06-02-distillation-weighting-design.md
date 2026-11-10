# Time-Weighted Distillation Design

## Goal

Preserve the project trait that memory influence fades over time during distillation, while allowing important and evergreen memories to resist decay.

## Current Context

Evolver currently has several memory-context systems:

- `MemoryCompiler` performs batch distillation into `today.md`, `week.md`, `longterm.md`, `facts`, and `memory_context.md`.
- `MemoryExtractor` extracts atomic facts from arbitrary text through `learn_extracted()`.
- `MemoryStack` provides wake-up and recall context using identity, essential memories, on-demand recall, and deep recall.

This design targets `MemoryCompiler` first. It keeps `MemoryStack` as retrieval context, not the source of distillation truth.

## Design Decision

Use a blended distillation weight for every memory before it enters any distillation layer:

```text
age_weight = 0.5 ** (age_days / half_life_days)

lifecycle_multiplier:
  seed      = 1.00
  growing   = 1.15
  evergreen = 1.60
  stale     = 0.25

importance_multiplier = 0.5 + importance

distill_weight = age_weight * lifecycle_multiplier * importance_multiplier
```

Default `half_life_days` should be `7` for weekly distillation. This means a memory's base influence halves every week unless lifecycle or importance counteracts it.

## Layer Behavior

### Today And Week

`compile_today()` and `compile_week()` should rank candidate memories by `distill_weight`, not only by database query order. Higher-weight memories get more prompt budget and appear earlier in input text.

### Long-Term

`compile_longterm()` should keep the old long-term profile, but frame it as lower-authority context than the latest weekly summary. The prompt should make new recurring weekly patterns able to override stale long-term traits.

Long-term profile should not simply grow forever. It should remain a compact skill/profile view shaped by recent recurring evidence.

### Facts

`compile_facts()` should extract facts from high-weight memories first. Existing facts should remain stored, but prompt/context injection should prefer facts derived from higher-weight or evergreen memories.

### Memory Context

`assemble()` should use weighted ordering for active and fact-like content where applicable. Old memories are not deleted; they become quieter.

## Scope

Accepted:

- Add a reusable weight calculation helper.
- Use weighted ordering in distillation input construction.
- Preserve lifecycle and importance as anti-decay signals.
- Keep DB schema unchanged for first implementation.
- Keep `MemoryStack` unchanged except documentation alignment if needed.

Deferred:

- Persisting `distill_weight` in the database.
- Adding per-fact provenance from source memory IDs.
- Rewriting `MemoryExtractor` and `compile_facts()` into one unified fact pipeline.
- Adding a full separate distillation LLM.

## Data Flow

1. Storage returns candidate memories for a time range.
2. Compiler calculates `distill_weight` for each memory from `created_at`, `importance`, and `lifecycle`.
3. Compiler sorts or budgets memories by weight.
4. LLM receives weighted input with strongest memories first.
5. Distilled output is cached in `distill_runs` and exported to memory files.
6. `memory_context.md` assembles the latest distilled artifacts.

## Error Handling

- If `created_at` is missing or unparsable, treat `age_days` as `0` to avoid silently discarding memories.
- If `importance` is missing, default to `0.5`.
- If `lifecycle` is unknown, use `seed` multiplier.
- Weight calculation must be deterministic and side-effect free.

## Testing

Tests should cover:

- Newer memories have higher weight than equivalent older memories.
- Evergreen old memories can outrank stale newer low-importance memories.
- `compile_week()` sends memories to the LLM in weighted order.
- Unknown lifecycle and missing importance fall back safely.
- Existing distillation cache behavior remains intact.

## Success Criteria

- Distillation keeps the fading-memory behavior explicitly.
- Important evergreen memories resist decay.
- Old low-importance memories lose prompt share without being deleted.
- No DB migration is required for the first implementation.
- Public API remains unchanged.
