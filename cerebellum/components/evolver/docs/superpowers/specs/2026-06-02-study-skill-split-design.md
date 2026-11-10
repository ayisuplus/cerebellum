# Study And Skill Channel Split Design

## Goal

Rename and rebalance the active Evolver agent skills so agents see four clear channels:

- `evolver-study` for the SQLite experience tier lifecycle.
- `evolver-skill` for generated skill artifacts.
- `evolver-store` for MySQL dead-data writes.
- `evolver-query` for MySQL dead-data reads.

## Current Context

The project currently exposes four effective skills as `evolver-learn`, `evolver-summary`, `evolver-store`, and `evolver-query`. This is close, but `learn` and `summary` split one conceptual workflow: study. The summary skill also mixes distillation and skill generation, which are different outcomes.

## Design Decision

Use these final agent-facing skills:

| Skill | Tier | Owns | Does not own |
|---|---|---|---|
| `evolver-study` | SQLite experience tier | `learn`, `recall`, `recall-light`, `wake-up`, `facts`, `add-fact`, `distill`, `memory_context`, targeted `forget` | skill file generation, MySQL archive |
| `evolver-skill` | SQLite-derived artifact tier | `skillgen`, `evaluate`, generated skill repair/reject decisions, skill library quality gate | raw experience storage, MySQL archive |
| `evolver-store` | MySQL data tier | `archive` write path for logs, records, payloads, transcripts, image/file references | semantic recall, distillation, skill generation |
| `evolver-query` | MySQL data tier | `query-archive` read path by keyword or id | SQLite experience recall |

## Rationale

`study` is the right name for the experience lifecycle because it includes learning, recall, facts, and time-weighted distillation. `memory` is too generic, and `learn` is too narrow.

`skill` is the right name for generated skill artifacts because agents and users naturally ask for `/evolver-skill`, `generate a skill`, or `repair this skill`. It should not own normal memory distillation.

## Channel Semantics

### Evolver Study

This is living memory. It writes and reads semantic experiences in SQLite. Distillation is time-weighted: old memories become quieter, while `evergreen` lifecycle and high `importance` memories resist decay.

### Evolver Skill

This turns already-stored experiences into reusable operational documents. It requires enough source experience and should reject memory-dump outputs. It may use `skillgen` and `evaluate`, but it does not store ordinary lessons.

### Evolver Store

This stores dead data in MySQL. The content is fetched later by id or keyword. Images and large files are stored by reference.

### Evolver Query

This reads dead data from MySQL. It never searches the SQLite experience tier.

## Migration Scope

Accepted:

- Replace `.claude/skills/evolver-learn` with `.claude/skills/evolver-study`.
- Replace `.claude/skills/evolver-summary` with `.claude/skills/evolver-skill`.
- Keep `.claude/skills/evolver-store` and `.claude/skills/evolver-query`.
- Update `tests/test_skill_docs.py` to enforce the four final skill names and tier boundaries.
- Update global opencode skills under `C:/Users/36322/.config/opencode/skills/` so future opencode sessions discover the new names.
- Preserve existing CLI commands. Skill names change; CLI commands do not.

Deferred:

- Renaming CLI commands from `learn`/`distill`/`skillgen`.
- Adding new slash command infrastructure.
- Changing database schema.
- Changing distillation algorithms beyond the already-implemented time-weighted behavior.

## Compatibility

Old skill directories `evolver-learn` and `evolver-summary` should be removed from active skill locations to avoid duplicate triggering. If backwards compatibility is needed later, add thin alias skills that only route to `evolver-study` or `evolver-skill`, but do not keep full duplicate workflows.

## Testing

Update skill-doc contract tests to assert:

- Active skills are exactly `evolver-study`, `evolver-skill`, `evolver-store`, and `evolver-query`.
- All active skills use only `name` and `description` frontmatter.
- Descriptions start with `Use when` and remain compact.
- Study and skill both mention SQLite experience tier but own different outcomes.
- Store and query both mention MySQL data tier and dead data.
- Study documents time-weighted distillation semantics.
- Skill documents generation/evaluation quality gates.

## Success Criteria

- Agents can choose the right skill from the name alone.
- No active skill mixes SQLite study operations with MySQL archive operations.
- No active skill splits the study lifecycle into artificial learn/summary halves.
- Generated skill work is separated from memory distillation.
- `tests/test_skill_docs.py` passes.
