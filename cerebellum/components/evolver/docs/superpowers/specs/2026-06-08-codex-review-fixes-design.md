# Codex Review Fixes: Skill Split, Lazy Embeddings, Async Distillation, Routing Config

## Goal

Apply four code-quality issues raised in a Codex review of the evolver codebase, with no public API breakage and full test coverage of the new behavior. Each issue is an independent refactor; together they reduce coupling in the skill layer, cut cold-start import cost, unblock async callers, and remove hard-coded routing strings.

## Current Context

The four findings:

- **P1 — Skill layer responsibility split.** `evolver/skill.py` (587 lines) defines `SkillEngine` which owns three concerns at once: (a) artifact rendering (SKILL.md frontmatter, Jinja templates, file writes), (b) library / index management (delegated to the injected `SkillLibrary`), and (c) quality gating (delegated to the injected `QualityChecker`). `evolver/skill_generator.py` (66 lines) is a thin wrapper that delegates `generate()` straight to `SkillEngine`. The test suite already covers `SkillEngine` and `SkillGenerator` separately.
- **P2-A — Vector-store / embedding startup cost.** `evolver/embedding.py` lines 9 and 14 perform module-level `from fastembed import TextEmbedding` and `from sentence_transformers import SentenceTransformer`. `pyproject.toml` lists both as required dependencies. The two providers under `evolver/embedding_providers.py` already do their imports lazily inside the constructor, so the same pattern should apply at the top of `embedding.py`.
- **P2-B — Distillation engine is sync only.** `evolver/distillation.py` defines `DistillationEngine` with four public methods (`distill`, `build_graph`, `build_links`, plus a tuple of internal helpers) all synchronous. The injected LLM client exposes an `acall_llm` coroutine but the distillation pipeline never uses it, so any caller that wants concurrency has to wrap the whole engine.
- **P3 — Search routing keywords hard-coded.** `evolver/search_engine.py` carries four class-level tuples: `_TIME_KEYWORDS_EN`, `_TIME_KEYWORDS_ZH`, `_FACT_KEYWORDS_EN`, `_FACT_KEYWORDS_ZH`. The auto-routing logic in `_route` / `_is_time_sensitive` / `_is_fact_query` reads them directly. There is no override path and no support for additional languages.

## Design Decision

Each fix is an isolated refactor. Public classes and methods keep their signatures so existing tests and downstream callers continue to work. New behavior is additive.

### P1: Skill layer split into three boundaries

Three classes, each with one clear purpose:

- `ArtifactWriter` (new, `evolver/artifact_writer.py`) — renders a SKILL.md body and an optional Python skill body. Owns frontmatter construction, Jinja template loading, `os.makedirs` and file write. Pure I/O plus string formatting; no storage or quality calls.
- `SkillIndex` (extracted from `SkillLibrary`, lives in `evolver/skill_library.py`) — owns the on-disk library under `evolver-skills/` and the JSON index. Exposes `find_similar_skill`, `add_skill`, `update_skill`, `get_skill`, `get_skill_content`, `list_skills`, `search_skills`, and a new `upsert_skill` that wraps the dedup check. The legacy class name `SkillLibrary` is kept as a thin alias for backward compatibility.
- `QualityChecker` (unchanged at the file level, `evolver/checker.py`) — already a focused class. The refactor only changes the call site inside `SkillEngine` to reach it through the new index abstraction's `add_skill` callback if any quality rejection happens; the existing `check_and_improve` API stays the same.

`SkillEngine` becomes an orchestrator: it gathers memories, asks `SkillIndex.find_similar_skill`, calls `ArtifactWriter.render`, writes the files, calls `SkillIndex.add_skill` / `update_skill`, then calls `QualityChecker.check_and_improve`. The public `generate()`, `_evolve_skill()`, `compose()`, `find_composable_pairs()` signatures are unchanged. `SkillGenerator` becomes a pure facade that only re-exports `SkillEngine.generate()` and adds `export()`.

### P2-A: Lazy embedding imports + optional dependency group

Move `from fastembed import TextEmbedding` and `from sentence_transformers import SentenceTransformer` from module scope into the `_resolve_backend()` helper that already decides which backend to use. The helper catches `ImportError` and raises a `RuntimeError` that names the missing package and the extras group to install. The two `embedding_providers.py` classes already do the same; this brings `embedding.py` in line.

`pyproject.toml` moves the three embedding libraries out of the core `[project].dependencies` list and into a new optional group `[project.optional-dependencies].embeddings`. The dev extras stay unchanged. No new required dependency is added.

### P2-B: Async distillation methods

Add three async mirror methods to `DistillationEngine`: `adistill`, `abuild_graph`, `abuild_links`. They delegate to a new `LLMClient.acall_llm` if available; otherwise they fall back to `asyncio.to_thread` wrappers around the existing sync methods so the async path is always usable.

The sync `distill`, `build_graph`, `build_links` are left untouched. Implementers that want concurrency call `adistill` instead. The two new public methods cover the two LLM-bound paths (`adistill`) and the link-building path (`abuild_links`); `abuild_graph` is included for symmetry since it also calls into storage.

### P3: Routing config dataclass + language packs

Add `evolver/search_routing.py` with:

- `RoutingConfig` — a frozen dataclass with `default_lang: str`, `time_keywords: dict[str, tuple[str, ...]]`, `fact_keywords: dict[str, tuple[str, ...]]`, and a `language(name) -> RoutingConfig` helper.
- A `DEFAULT_ROUTING_CONFIG` constant that extends the current English and Chinese word lists and adds Japanese, Korean, German, and French starter packs (3-5 time keywords and 2-3 fact keywords per language).

`SearchEngine.__init__` accepts an optional `routing_config: RoutingConfig = None` parameter; when `None` it uses `DEFAULT_ROUTING_CONFIG`. The class-level tuples become class attributes of `DEFAULT_ROUTING_CONFIG` and are read from the instance config in `_is_time_sensitive` / `_is_fact_query`. The `EVOLVER_SEARCH_LANG` environment variable (read through `EvolverConfig`) sets the default language for a new config.

## Layer Behavior

### P1 split — call ordering

`SkillEngine.generate(topic)` flow after the refactor:

1. `self._memory.recall(topic, top_k=top_k)` and `self._graph.query(topic)` — unchanged.
2. `self._index.find_similar_skill(topic, description)` — unchanged behavior, new indirection.
3. `self._artifact.render(topic, memories, graph_nodes, lang=lang, ...)` returns `(md_content, py_content_or_none)`.
4. `os.makedirs` + file write — moved into `ArtifactWriter.write`.
5. `self._storage.upsert_skill(...)` and `self._index.add_skill(...)` — unchanged call sites.
6. `self._quality.check_and_improve(skill_id, md_content, topic)` — unchanged.

`SkillEngine._evolve_skill` and `compose` follow the same shape: hand rendering to `ArtifactWriter` and library management to `SkillIndex`.

### P2-A split — import timing

`from evolver.embedding import EmbeddingClient` no longer pulls in `fastembed` or `sentence-transformers` at import time. The two libraries are loaded the first time `EmbeddingClient.embed_single` (or the backend resolver) runs. The behavior under installed dependencies is byte-identical to the current implementation.

### P2-B async path

`DistillationEngine.adistill` runs the same loop as `distill` but calls `await self._llm.acall_llm(...)` for each record and `await asyncio.to_thread(self._archive.search_archive, ...)` for archive I/O. Storage inserts become `await asyncio.to_thread(self._storage.insert_memory, mem)`. Returns the same dict shape as `distill`.

`abuild_graph` and `abuild_links` mirror the sync versions with `await asyncio.to_thread(...)` wrappers around the per-id work.

### P3 routing config

`SearchEngine._route(query)` resolves to a strategy using `self._routing.time_keywords[default_lang]` and `self._routing.fact_keywords[default_lang]`. When a query contains characters from multiple languages the engine matches each keyword list and selects the first hit. `list_strategies` adds a fifth entry `"routing": "auto with config"` so the new dimension is observable.

## Scope

Accepted:

- Move the two embedding imports into the backend resolver and shift them to an optional group.
- Add `adistill`, `abuild_graph`, `abuild_links` async methods and reuse existing sync helpers.
- Extract `ArtifactWriter` and `SkillIndex`; keep `SkillEngine` and `SkillGenerator` signatures stable.
- Introduce `RoutingConfig` + `DEFAULT_ROUTING_CONFIG` with five languages and `EVOLVER_SEARCH_LANG` env hook.
- New tests for the new classes and async methods.

Deferred:

- Persisting routing decisions per query.
- Per-language keyword tuning beyond starter packs.
- Replacing the entire `SkillEngine` orchestrator with a smaller pipeline abstraction.
- Wiring async distillation into the CLI; only the engine API is async.

## Data Flow

Skill generation after the refactor:

```
topic
  → MemoryEngine.recall + GraphEngine.query
  → SkillIndex.find_similar_skill
  → ArtifactWriter.render (frontmatter + Jinja)
  → file system (md, py)
  → Storage.upsert_skill + SkillIndex.add_skill
  → QualityChecker.check_and_improve
  → Storage.upsert_skill (improved version)
  → Event log
```

Distillation after the refactor:

```
archive record list
  → LLMClient.acall_llm (async)  ─┐
  → Storage.insert_memory         ─┼─ wrapped in asyncio.to_thread
  → GraphEngine.build_from_text   ─┘
  → LinkEngine.auto_link_memory
```

Search routing after the refactor:

```
query string
  → lowercase form + original form
  → RoutingConfig.time_keywords[lang] (substring match)
  → RoutingConfig.fact_keywords[lang] (substring match)
  → strategy name → SearchEngine._dispatch
```

## Fit Criteria

- `pytest tests/test_skill.py tests/test_skill_generator.py tests/test_checker.py` passes unchanged.
- `pytest tests/test_distillation.py` passes; new `tests/test_distillation_async.py` covers `adistill` happy path, LLM-unavailable fallback, and exception propagation.
- New `tests/test_artifact_writer.py` covers frontmatter, Jinja fallback path, executable toggle, and output-dir creation.
- New `tests/test_skill_index.py` covers find/add/update/get/list/search, embedding-client-disabled fallback, and `upsert_skill` dedup.
- New `tests/test_embedding_lazy.py` simulates `sys.modules` without `fastembed` and verifies `import evolver.embedding` succeeds and `embed_single` raises a clear `RuntimeError`.
- New `tests/test_search_routing.py` covers the dataclass, language switching via `EVOLVER_SEARCH_LANG`, and the four new language starter packs through `SearchEngine.search(strategy="auto")`.
- `pytest tests/` runs to completion with zero new failures.
- `SkillEngine` line count drops below 500 and contains no direct Jinja calls, no direct `os.makedirs` calls, and no direct `self._library.find_similar_skill` calls.
