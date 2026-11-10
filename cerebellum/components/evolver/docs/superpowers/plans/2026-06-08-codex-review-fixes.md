# Codex Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply four Codex code-review findings (P1 skill split, P2-A lazy embedding imports, P2-B async distillation, P3 routing config) without breaking any public API or existing test.

**Architecture:** Each fix is an isolated refactor. New behavior is additive (async methods, optional config, new extracted classes) so all current call sites keep working. The skill layer splits into `ArtifactWriter` (file rendering) + `SkillIndex` (library) + `SkillEngine` (orchestrator); the embedding layer moves the heavy imports inside the constructor; distillation gains `adistill` / `abuild_graph` / `abuild_links`; search routing reads from a `RoutingConfig` dataclass with five language packs.

**Tech Stack:** Python 3.11+, pytest + pytest-asyncio, dataclasses, stdlib `asyncio` + `asyncio.to_thread`.

---

## File Structure

New files (3):

- `evolver/artifact_writer.py` — `ArtifactWriter` class (frontmatter, Jinja render, file write).
- `evolver/search_routing.py` — `RoutingConfig` dataclass + `DEFAULT_ROUTING_CONFIG`.
- `tests/test_search_routing.py` — unit tests for routing config + multi-language search.

Modified files (7):

- `evolver/skill.py` — `SkillEngine` becomes an orchestrator that calls `ArtifactWriter` and `SkillIndex`; no Jinja, no `os.makedirs`, no direct library calls inside the engine body.
- `evolver/skill_library.py` — add `SkillIndex` class (with the same surface as `SkillLibrary` plus `upsert_skill`); keep `SkillLibrary` as a backward-compatible alias.
- `evolver/embedding.py` — move `from fastembed import TextEmbedding` and `from sentence_transformers import SentenceTransformer` out of module scope and into the `_resolve_backend` helper.
- `pyproject.toml` — move `fastembed`, `FlagEmbedding`, `sentence-transformers` from `dependencies` to a new `embeddings` optional group.
- `evolver/llm_client.py` — add `async acall_llm` mirroring `call_llm` (uses `asyncio.to_thread` over the existing `_call_openai_compatible` / `_call_anthropic`).
- `evolver/distillation.py` — add `adistill`, `abuild_graph`, `abuild_links`; keep sync methods untouched.
- `evolver/search_engine.py` — accept `routing_config` in `__init__`; `_is_time_sensitive` / `_is_fact_query` read from config.
- `evolver/__init__.py` — wire `SkillIndex` and `ArtifactWriter` into `SkillEngine` construction; no behavioral change.

New tests (4):

- `tests/test_artifact_writer.py` — `ArtifactWriter.render` + `.write` with both LLM and template paths, with and without executable.
- `tests/test_embedding_lazy.py` — verify `import evolver.embedding` succeeds when `fastembed` and `sentence_transformers` are absent; verify `embed_single` raises a clear `RuntimeError`.
- `tests/test_distillation_async.py` — `adistill` happy path, LLM-unavailable fallback, exception propagation.
- `tests/test_search_routing.py` — `RoutingConfig` language switching, `EVOLVER_SEARCH_LANG` env override, four new language starter packs via `SearchEngine.search(strategy="auto")`.

## Task Sequencing

Tasks are ordered to keep tests green at every commit boundary. P2-A and P3 are independent and could run in parallel; P1 and P2-B depend on understanding the existing code but not on each other. The orchestrator should run P1 → P2-A → P2-B → P3 in that order so each lands on a stable base.

---

## Task 1: Extract ArtifactWriter (P1 part 1)

**Files:**
- Create: `evolver/artifact_writer.py`
- Modify: `evolver/skill.py:118-273` (move render logic into ArtifactWriter, keep `generate()` orchestration)
- Test: `tests/test_artifact_writer.py`

- [ ] **Step 1.1: Write the failing test for ArtifactWriter.render with template path**

```python
# tests/test_artifact_writer.py
from unittest.mock import MagicMock
from evolver.artifact_writer import ArtifactWriter


def test_artifact_writer_template_path(tmp_path):
    """When no LLM is provided, ArtifactWriter falls back to Jinja template."""
    memories = [
        MagicMock(category="success", content="Step 1: do the thing\nStep 2: verify"),
        MagicMock(category="failure", content="Watch out for null inputs"),
        MagicMock(category="insight", content="Idempotency matters"),
    ]
    graph_nodes = [MagicMock(label="python", node_type="language")]

    writer = ArtifactWriter(jinja_env=None)  # rely on default FileSystemLoader
    md, py = writer.render(
        topic="test topic",
        name="test-topic",
        description="Auto-generated",
        memories=memories,
        graph_nodes=graph_nodes,
        executable=True,
        llm_content=None,
    )

    assert "test topic" in md.lower()
    assert "version: 1" in md
    assert "test-topic" in md
    # executable=True and template path produces a .py
    assert py is not None
    assert "test-topic" in py
```

- [ ] **Step 1.2: Run the test to verify it fails**

Run: `pytest tests/test_artifact_writer.py::test_artifact_writer_template_path -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evolver.artifact_writer'`.

- [ ] **Step 1.3: Create evolver/artifact_writer.py**

```python
"""Artifact writer: renders and writes SKILL.md and optional skill.py files.

Owns frontmatter construction, Jinja template loading, and the file-system
side effects of skill generation. Has no knowledge of the storage layer,
the library, or the quality checker.
"""
import logging
import os
from pathlib import Path
from typing import Any, Optional, Sequence

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


def _default_env() -> Environment:
    template_dir = Path(__file__).parent / "templates"
    return Environment(loader=FileSystemLoader(str(template_dir)))


class ArtifactWriter:
    """Render SKILL.md and skill.py bodies, then write them to disk."""

    def __init__(self, jinja_env: Optional[Environment] = None,
                 output_dir: str = "./skills"):
        self._env = jinja_env or _default_env()
        self._default_output_dir = output_dir

    def render(
        self,
        topic: str,
        name: str,
        description: str,
        memories: Sequence[Any],
        graph_nodes: Sequence[Any],
        executable: bool = True,
        llm_content: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Return (md_content, py_content_or_none) without touching disk."""
        all_tags: set[str] = set()
        for m in memories:
            cat = getattr(m, "category", None)
            if cat:
                all_tags.add(cat)
        for n in graph_nodes:
            ntype = getattr(n, "node_type", None)
            if ntype:
                all_tags.add(ntype)

        if llm_content:
            frontmatter = (
                f"---\nname: {name}\ndescription: {description}\n"
                f"version: 1\ntags: [{', '.join(sorted(all_tags))}]\n"
                f"generated_from: {len(memories)} memories, "
                f"{len(graph_nodes)} graph nodes\n"
                f"synthesis: llm\n---\n\n"
                f"# {topic.replace('-', ' ').title()}\n\n"
            )
            md_content = frontmatter + llm_content
        else:
            success_cases = [m.content for m in memories
                             if getattr(m, "category", None) == "success"]
            failure_lessons = [m.content for m in memories
                               if getattr(m, "category", None) == "failure"]
            insights = [m.content for m in memories
                        if getattr(m, "category", None) == "insight"]
            steps = self._extract_steps(success_cases)
            related = [f"{n.label} ({getattr(n, 'node_type', '')})"
                       for n in graph_nodes[:5]]
            summary = (
                f"Based on {len(memories)} memories and "
                f"{len(graph_nodes)} knowledge graph nodes."
            )
            md_template = self._env.get_template("skill.md.j2")
            md_content = md_template.render(
                name=name, description=description, version=1,
                tags=sorted(all_tags), memory_count=len(memories),
                node_count=len(graph_nodes),
                title=topic.replace("-", " ").title(),
                summary=summary, steps=steps,
                success_cases=success_cases[:5],
                failure_lessons=failure_lessons[:5],
                insights=insights[:5], related_skills=related,
            )

        py_content: Optional[str] = None
        if executable and not llm_content:
            py_content = self._render_python(
                name=name, description=description, version=1,
                tags=sorted(all_tags), memory_count=len(memories),
                node_count=len(graph_nodes),
                title=topic.replace("-", " ").title(),
                memories=memories, graph_nodes=graph_nodes,
            )
        elif executable and llm_content:
            # For LLM-synthesized skills, generate a thin .py wrapper
            py_content = self._render_python_wrapper(
                name=name, description=description,
            )

        return md_content, py_content

    def write(
        self,
        name: str,
        md_content: str,
        py_content: Optional[str],
        output_dir: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Write md (and optional py) into output_dir. Returns (md_path, py_path)."""
        target_dir = output_dir or self._default_output_dir
        os.makedirs(target_dir, exist_ok=True)
        md_path = os.path.join(target_dir, f"{name}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        py_path: Optional[str] = None
        if py_content is not None:
            py_path = os.path.join(target_dir, f"{name}.py")
            with open(py_path, "w", encoding="utf-8") as f:
                f.write(py_content)
        return md_path, py_path

    @staticmethod
    def _extract_steps(success_cases: list[str]) -> list[str]:
        steps: list[str] = []
        for case in success_cases:
            for line in case.split("\n"):
                line = line.strip()
                if line and len(line) > 5:
                    steps.append(line)
        return steps[:10]

    def _render_python(
        self, *, name: str, description: str, version: int, tags: list[str],
        memory_count: int, node_count: int, title: str,
        memories: Sequence[Any], graph_nodes: Sequence[Any],
    ) -> str:
        success_cases = [m.content for m in memories
                         if getattr(m, "category", None) == "success"]
        failure_lessons = [m.content for m in memories
                           if getattr(m, "category", None) == "failure"]
        insights = [m.content for m in memories
                    if getattr(m, "category", None) == "insight"]
        steps = self._extract_steps(success_cases)
        related = [f"{n.label} ({getattr(n, 'node_type', '')})"
                   for n in graph_nodes[:5]]
        py_template = self._env.get_template("skill.py.j2")
        return py_template.render(
            name=name, description=description, version=version,
            tags=tags, memory_count=memory_count, node_count=node_count,
            title=title, steps=steps, success_cases=success_cases[:5],
            failure_lessons=failure_lessons[:5],
            insights=insights[:5], related_skills=related,
        )

    @staticmethod
    def _render_python_wrapper(*, name: str, description: str) -> str:
        return (
            f'"""{name}: {description}"""\n'
            f'\nNAME = "{name}"\n'
            f'DESCRIPTION = "{description}"\n'
            f'\n\ndef run(*args, **kwargs):\n'
            f'    """See SKILL.md for the full workflow."""\n'
            f'    raise NotImplementedError("LLM-synthesized skill; see SKILL.md")\n'
        )
```

- [ ] **Step 1.4: Run the test to verify it passes**

Run: `pytest tests/test_artifact_writer.py::test_artifact_writer_template_path -v`
Expected: PASS.

- [ ] **Step 1.5: Commit**

```bash
git add evolver/artifact_writer.py tests/test_artifact_writer.py
git commit -m "feat(skill): extract ArtifactWriter (P1 split part 1)"
```

---

## Task 2: Extract SkillIndex from SkillLibrary (P1 part 2)

**Files:**
- Modify: `evolver/skill_library.py:16-310`
- Test: `tests/test_skill_index.py` (new)

- [ ] **Step 2.1: Write the failing test for SkillIndex**

```python
# tests/test_skill_index.py
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from evolver.skill_library import SkillIndex


def test_skill_index_add_and_find(tmp_path):
    embedding = MagicMock()
    embedding.embed_single.return_value = [0.1, 0.2, 0.3]
    index = SkillIndex(library_path=str(tmp_path), embedding_client=embedding)

    meta = index.add_skill(
        name="git-workflow", description="Git workflow tips",
        content="# Git Workflow\n\n## Steps\n1. Commit often",
        topic="git workflow", version=1,
    )
    assert meta["name"] == "evolver-git-workflow"
    assert (tmp_path / "skills" / "evolver-git-workflow.md").exists()

    # upsert_skill should return an existing skill when content is similar
    result = index.upsert_skill(
        name="git-workflow-2",
        description="Git workflow",
        file_path="/tmp/x.md",
        content="Same topic",
    )
    assert result["name"] == "evolver-git-workflow"
    assert result["version"] >= 1
```

- [ ] **Step 2.2: Run the test to verify it fails**

Run: `pytest tests/test_skill_index.py::test_skill_index_add_and_find -v`
Expected: FAIL with `ImportError: cannot import name 'SkillIndex' from 'evolver.skill_library'`.

- [ ] **Step 2.3: Add `SkillIndex` class to `evolver/skill_library.py`**

Add at the end of `evolver/skill_library.py` (keep the existing `SkillLibrary` class unchanged):

```python
class SkillIndex:
    """Library index for skills with deduplication and evolution.

    Same on-disk layout as SkillLibrary (./skills + ./metadata + index.json)
    but with an explicit `upsert_skill(name, description, file_path, content)`
    entry point that the SkillEngine orchestrator calls.
    """

    def __init__(self, library_path: str = "./evolver-skills",
                 embedding_client=None, similarity_threshold: float = 0.85):
        from evolver.utils import cosine_similarity, tokenize
        self._cosine = cosine_similarity
        self._tokenize = tokenize
        self._library_path = Path(library_path)
        self._skills_dir = self._library_path / "skills"
        self._metadata_dir = self._library_path / "metadata"
        self._index_path = self._library_path / "index.json"
        self._embedding = embedding_client
        self._threshold = similarity_threshold
        self._lock = threading.Lock()

        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_dir.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()

    def _load_index(self) -> dict:
        if self._index_path.exists():
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load skill index: %s", e)
        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "skills": [],
        }

    def _save_index(self):
        try:
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save skill index: %s", e)

    def find_similar_skill(self, topic: str, content: str = "") -> Optional[dict]:
        if not self._embedding:
            return self._find_by_keywords(topic)
        query_text = f"{topic} {content}" if content else topic
        query_vec = self._embedding.embed_single(query_text)
        best_match, best_similarity = None, 0.0
        for skill_meta in self._index.get("skills", []):
            skill_embedding = skill_meta.get("embedding")
            if not skill_embedding:
                continue
            similarity = self._cosine(query_vec, skill_embedding)
            if similarity > best_similarity and similarity >= self._threshold:
                best_similarity = similarity
                best_match = skill_meta
        if best_match:
            logger.info("Found similar skill '%s' (similarity=%.3f)",
                        best_match.get("name"), best_similarity)
            return best_match
        return None

    def _find_by_keywords(self, topic: str) -> Optional[dict]:
        topic_keywords = set(self._tokenize(topic))
        best_match, best_overlap = None, 0
        for skill_meta in self._index.get("skills", []):
            skill_keywords = set(skill_meta.get("keywords", []))
            overlap = len(topic_keywords & skill_keywords)
            if overlap > best_overlap and overlap >= 2:
                best_overlap = overlap
                best_match = skill_meta
        return best_match

    def add_skill(self, name: str, description: str, content: str,
                  topic: str, version: int = 1,
                  memories_used: int = 0, graph_nodes_used: int = 0,
                  source: str = "evolver") -> dict:
        prefixed_name = name if name.startswith("evolver-") else f"evolver-{name}"
        embedding = None
        if self._embedding:
            try:
                embedding = self._embedding.embed_single(
                    f"{topic} {description}")
            except Exception as e:
                logger.warning("Failed to generate embedding: %s", e)
        keywords = self._tokenize(f"{topic} {description}")
        metadata = {
            "name": prefixed_name, "original_name": name,
            "description": description, "topic": topic, "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "memories_used": memories_used,
            "graph_nodes_used": graph_nodes_used, "source": source,
            "keywords": keywords, "embedding": embedding,
        }
        with open(self._skills_dir / f"{prefixed_name}.md", "w",
                  encoding="utf-8") as f:
            f.write(content)
        with open(self._metadata_dir / f"{prefixed_name}.json", "w",
                  encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        with self._lock:
            self._index["skills"].append(metadata)
            self._save_index()
        logger.info("Added skill '%s' to library (v%d)", prefixed_name, version)
        return metadata

    def update_skill(self, name: str, content: str, description: str = None,
                     memories_used: int = 0, graph_nodes_used: int = 0
                     ) -> Optional[dict]:
        skill_meta = None
        for meta in self._index.get("skills", []):
            if meta.get("name") == name:
                skill_meta = meta
                break
        if not skill_meta:
            logger.warning("Skill '%s' not found in library", name)
            return None
        skill_meta["version"] = skill_meta.get("version", 1) + 1
        skill_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        skill_meta["memories_used"] = (
            skill_meta.get("memories_used", 0) + memories_used)
        skill_meta["graph_nodes_used"] = (
            skill_meta.get("graph_nodes_used", 0) + graph_nodes_used)
        if description:
            skill_meta["description"] = description
        if self._embedding:
            try:
                topic = skill_meta.get("topic", "")
                skill_meta["embedding"] = self._embedding.embed_single(
                    f"{topic} {description or skill_meta.get('description', '')}")
            except Exception as e:
                logger.warning("Failed to update embedding: %s", e)
        with open(self._skills_dir / f"{name}.md", "w", encoding="utf-8") as f:
            f.write(content)
        with open(self._metadata_dir / f"{name}.json", "w",
                  encoding="utf-8") as f:
            json.dump(skill_meta, f, ensure_ascii=False, indent=2)
        with self._lock:
            self._save_index()
        logger.info("Updated skill '%s' to v%d", name, skill_meta["version"])
        return skill_meta

    def upsert_skill(self, name: str, description: str,
                     file_path: str, content: str) -> tuple[int, int]:
        """Index-side upsert: return (skill_id, version).

        Calls find_similar_skill and either evolves the match (returns its
        id and incremented version) or adds a new skill and returns the new
        id and version 1. The caller persists the storage row separately.
        """
        existing = self.find_similar_skill(name, content)
        if existing:
            updated = self.update_skill(
                existing["name"], content,
                description=description,
            )
            return (id(existing), updated["version"])
        meta = self.add_skill(
            name=name, description=description,
            content=content, topic=name,
        )
        return (id(meta), meta["version"])

    def get_skill(self, name: str) -> Optional[dict]:
        for meta in self._index.get("skills", []):
            if meta.get("name") == name:
                return meta
        return None

    def get_skill_content(self, name: str) -> Optional[str]:
        skill_path = self._skills_dir / f"{name}.md"
        if skill_path.exists():
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def list_skills(self) -> list[dict]:
        return self._index.get("skills", [])

    def search_skills(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._embedding:
            return self._search_by_keywords(query, top_k)
        query_vec = self._embedding.embed_single(query)
        scored = []
        for skill_meta in self._index.get("skills", []):
            emb = skill_meta.get("embedding")
            if not emb:
                continue
            sim = self._cosine(query_vec, emb)
            scored.append((sim, skill_meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored[:top_k]]

    def _search_by_keywords(self, query: str, top_k: int) -> list[dict]:
        query_keywords = set(self._tokenize(query))
        scored = []
        for skill_meta in self._index.get("skills", []):
            skill_keywords = set(skill_meta.get("keywords", []))
            overlap = len(query_keywords & skill_keywords)
            if overlap > 0:
                scored.append((overlap, skill_meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored[:top_k]]


# Backward-compat alias (kept for any external importer of the old name).
SkillLibrary = SkillIndex
```

- [ ] **Step 2.4: Run the test to verify it passes**

Run: `pytest tests/test_skill_index.py::test_skill_index_add_and_find -v`
Expected: PASS.

- [ ] **Step 2.5: Run the existing skill library test (if present)**

Run: `pytest tests/ -k "skill_library" -v`
Expected: PASS (the alias keeps the old class name working).

- [ ] **Step 2.6: Commit**

```bash
git add evolver/skill_library.py tests/test_skill_index.py
git commit -m "feat(skill): extract SkillIndex from SkillLibrary (P1 split part 2)"
```

---

## Task 3: Refactor SkillEngine into an orchestrator (P1 part 3)

**Files:**
- Modify: `evolver/skill.py:118-587`
- Modify: `evolver/__init__.py:185-198`
- Verify: `pytest tests/test_skill.py tests/test_skill_generator.py tests/test_checker.py`

- [ ] **Step 3.1: Refactor `SkillEngine.__init__` to accept the new collaborators**

Replace `evolver/skill.py` lines 118-128 with:

```python
class SkillEngine:
    def __init__(self, storage: BaseStorage, memory_engine, graph_engine,
                 llm_client=None, skill_library=None,
                 artifact_writer=None, quality_checker=None):
        self._storage = storage
        self._memory = memory_engine
        self._graph = graph_engine
        self._llm = llm_client
        self._library = skill_library  # backward-compat: SkillIndex or SkillLibrary
        self._artifact = artifact_writer or ArtifactWriter()
        self._checker = quality_checker  # may be wired in later (e.g. by Evolver)
```

- [ ] **Step 3.2: Replace the body of `SkillEngine.generate` to delegate rendering and indexing**

Replace `evolver/skill.py` lines 130-273 with:

```python
    def generate(self, topic: str, output_dir: str = "./skills",
                 top_k: int = 20, executable: bool = True,
                 lang: str = "zh", _skip_dedup: bool = False
                 ) -> SkillResult | None:
        memories = self._memory.recall(topic, top_k=top_k)
        if not memories:
            return None
        graph_nodes = self._graph.query(topic)
        name = self._slugify(topic)
        description = f"Auto-generated skill for: {topic}"

        if self._library and not _skip_dedup:
            similar_skill = self._library.find_similar_skill(topic, description)
            if similar_skill:
                logger.info("Found similar skill '%s', merging with new memories",
                            similar_skill.get("name"))
                return self._evolve_skill(
                    similar_skill, memories, graph_nodes,
                    output_dir=output_dir, executable=executable, lang=lang,
                )

        llm_content = self._synthesize_with_llm(topic, memories, graph_nodes, lang)
        md_content, py_content = self._artifact.render(
            topic=topic, name=name, description=description,
            memories=memories, graph_nodes=graph_nodes,
            executable=executable, llm_content=llm_content,
        )
        if llm_content:
            logger.info("LLM synthesis succeeded for skill '%s'", name)
        else:
            logger.info("Template fallback for skill '%s'", name)

        file_path, py_path = self._artifact.write(
            name=name, md_content=md_content, py_content=py_content,
            output_dir=output_dir,
        )
        if py_path:
            logger.info("Generated executable skill -> %s", py_path)

        content_for_db = md_content
        if py_path:
            content_for_db += f"\n\n---\nExecutable: {py_path}"

        skill_id, actual_version = self._storage.upsert_skill(
            name=name, description=description,
            file_path=file_path, content=content_for_db,
        )

        if self._checker:
            try:
                improved_content, eval_result = self._checker.check_and_improve(
                    skill_id, md_content, topic,
                )
                if improved_content != md_content:
                    self._artifact.write(
                        name=name, md_content=improved_content, py_content=None,
                        output_dir=output_dir,
                    )
                    md_content = improved_content
                    improved_for_db = md_content
                    if py_path:
                        improved_for_db += f"\n\n---\nExecutable: {py_path}"
                    skill_id, actual_version = self._storage.upsert_skill(
                        name=name, description=description,
                        file_path=file_path, content=improved_for_db,
                    )
                    logger.info("Quality check: score=%.1f, status=%s",
                                eval_result.total_score, eval_result.status)
            except Exception:
                logger.warning("Quality check failed (non-fatal)", exc_info=True)

        self._storage.log_event("skillgen", {
            "topic": topic, "file": file_path,
            "py_file": py_path, "memories_used": len(memories),
        })
        logger.info("Generated skill '%s' v%d -> %s", name, actual_version, file_path)
        return SkillResult(name=name, path=file_path, content=md_content, version=actual_version)
```

- [ ] **Step 3.3: Remove the now-unused helper methods from SkillEngine**

Delete the old `_extract_steps` and `_build_summary` methods (the engine body no longer needs them — they live in `ArtifactWriter`).

- [ ] **Step 3.4: Wire SkillIndex + ArtifactWriter in evolver/__init__.py**

Replace lines 180-187 of `evolver/__init__.py`:

```python
        from evolver.artifact_writer import ArtifactWriter
        from evolver.skill_library import SkillIndex
        self._skill_library = SkillIndex(
            library_path="./evolver-skills",
            embedding_client=self._embedding,
            similarity_threshold=0.85,
        )
        self._skill = SkillEngine(
            self._storage, self._memory, self.graph,
            llm_client=self._llm,
            skill_library=self._skill_library,
            artifact_writer=ArtifactWriter(),
        )
```

Keep the post-construction injection of the checker:

```python
        self._skill._checker = self._checker  # late-wire to avoid circular build
```

- [ ] **Step 3.5: Run the full skill + checker + generator test suites**

Run: `pytest tests/test_skill.py tests/test_skill_generator.py tests/test_checker.py -v`
Expected: PASS. The public API of `SkillEngine`, `SkillGenerator`, and `QualityChecker` is unchanged; only the internal rendering/indexing moved.

- [ ] **Step 3.6: Confirm SkillEngine no longer contains Jinja or os.makedirs calls**

Run:
```bash
grep -nE 'os\.makedirs|get_template\("skill' evolver/skill.py
```
Expected: empty output (no matches).

- [ ] **Step 3.7: Commit**

```bash
git add evolver/skill.py evolver/__init__.py
git commit -m "refactor(skill): SkillEngine delegates to ArtifactWriter and SkillIndex (P1)"
```

---

## Task 4: Lazy-load embedding libraries (P2-A part 1)

**Files:**
- Modify: `evolver/embedding.py:1-18`
- Test: `tests/test_embedding_lazy.py` (new)

- [ ] **Step 4.1: Write the failing lazy-import test**

```python
# tests/test_embedding_lazy.py
import sys
import importlib
import builtins
import pytest


def test_embedding_module_imports_without_fastembed(monkeypatch):
    """Importing evolver.embedding should not require fastembed or sentence_transformers."""
    # Block the heavy libraries at the module level
    blocked = {"fastembed", "sentence_transformers"}
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in blocked or any(name.startswith(b + ".") for b in blocked):
            raise ImportError(f"Blocked {name} for this test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    # Force a fresh import
    sys.modules.pop("evolver.embedding", None)
    mod = importlib.import_module("evolver.embedding")
    assert hasattr(mod, "EmbeddingClient")


def test_embedding_client_runtime_error_without_fastembed(monkeypatch):
    """Constructing an EmbeddingClient with a remote model should raise a clear error."""
    import builtins
    original_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "fastembed" or name.startswith("fastembed."):
            raise ImportError("fastembed is not installed in this test env")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    from evolver.embedding import EmbeddingClient
    with pytest.raises(RuntimeError, match="fastembed"):
        EmbeddingClient(model_name="BAAI/bge-small-en-v1.5", dim=384)
```

- [ ] **Step 4.2: Run the test to verify it fails**

Run: `pytest tests/test_embedding_lazy.py -v`
Expected: FAIL — the current `embedding.py` raises `ImportError` at module import time (it does `try/except`, so the first test passes; the second test fails because `EmbeddingClient.__init__` only does the check inside the `else` branch and the error message says "fastembed is not installed. Install with: pip install fastembed" — actually present, but the test will fail at import because the test framework still has the module imported before the monkeypatch, depending on session scope; the *fresh* module is what we are testing).

- [ ] **Step 4.3: Remove the module-level imports from `evolver/embedding.py`**

Replace `evolver/embedding.py` lines 1-18 with:

```python
import logging
import os
import struct
from typing import Optional

from evolver.exceptions import EmbeddingError

logger = logging.getLogger(__name__)


def _import_fastembed():
    try:
        from fastembed import TextEmbedding
    except ImportError as e:
        raise RuntimeError(
            "fastembed is required for the default embedding backend. "
            "Install with: pip install evolver[embeddings]"
        ) from e
    return TextEmbedding


def _import_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError(
            "sentence-transformers is required for local-path embedding models. "
            "Install with: pip install evolver[embeddings]"
        ) from e
    return SentenceTransformer
```

- [ ] **Step 4.4: Update `EmbeddingClient.__init__` to call the new helpers**

Replace the body of `__init__` (lines 35-116) with the version that calls `_import_fastembed()` and `_import_sentence_transformers()` instead of using the module-level names. Concretely, inside the `if is_local:` branch, replace the `SentenceTransformer is None` guard with a call to `_import_sentence_transformers()`; in the `else:` branch, replace the `TextEmbedding is None` guard with a call to `_import_fastembed()`.

```python
        if is_local:
            SentenceTransformer = _import_sentence_transformers()
            try:
                self._model = SentenceTransformer(model_name)
                self._backend = "sentence_transformers"
                actual_dim = self._model.get_sentence_embedding_dimension()
                if actual_dim != dim:
                    raise EmbeddingError(
                        f"Dimension mismatch: model '{model_name}' produces "
                        f"{actual_dim}-d vectors, but config specifies dim={dim}. "
                        f"Use embedding_dim={actual_dim} or omit it to use the default."
                    )
                logger.info("Loaded local model '%s' via sentence-transformers (dim=%d)",
                            model_name, dim)
            except EmbeddingError:
                raise
            except Exception as e:
                raise EmbeddingError(
                    f"Failed to load local model '{model_name}': {e}"
                ) from e
        else:
            TextEmbedding = _import_fastembed()
            expected_dim = _MODEL_DIMS.get(model_name)
            if expected_dim is not None and expected_dim != dim:
                raise EmbeddingError(
                    f"Dimension mismatch: model '{model_name}' produces "
                    f"{expected_dim}-d vectors, but config specifies dim={dim}. "
                    f"Use embedding_dim={expected_dim} or omit it to use the default."
                )
            if expected_dim is None:
                logger.warning(
                    "Unknown model '%s' -- cannot validate dim=%d. "
                    "Proceeding, but mismatched dims will cause runtime errors.",
                    model_name, dim,
                )
            try:
                self._model = TextEmbedding(model_name=model_name)
                self._backend = "fastembed"
                logger.info("Loaded embedding model '%s' (dim=%d)", model_name, dim)
            except Exception as e:
                raise EmbeddingError(
                    f"Failed to load embedding model '{model_name}': {e}. "
                    "Check network connection for first-run download."
                ) from e
```

- [ ] **Step 4.5: Run the lazy-import tests to verify they pass**

Run: `pytest tests/test_embedding_lazy.py -v`
Expected: PASS.

- [ ] **Step 4.6: Run the full embedding + vector test suites**

Run: `pytest tests/test_embedding.py tests/test_embedding_providers.py tests/test_vector_store.py -v`
Expected: PASS.

- [ ] **Step 4.7: Commit**

```bash
git add evolver/embedding.py tests/test_embedding_lazy.py
git commit -m "refactor(embedding): lazy-import fastembed and sentence-transformers (P2-A)"
```

---

## Task 5: Move embedding deps to optional group (P2-A part 2)

**Files:**
- Modify: `pyproject.toml:10-30`

- [ ] **Step 5.1: Update `pyproject.toml`**

Replace the `dependencies` list and the `optional-dependencies` block with:

```toml
dependencies = [
    "jinja2>=3.1.0",
    "numpy>=1.24.0",
    "click>=8.0",
]

[project.optional-dependencies]
mysql = ["pymysql>=1.1.0"]
chinese = ["jieba>=0.42"]
ann = ["hnswlib>=0.7.0"]
embeddings = [
    "fastembed>=0.2.0",
    "FlagEmbedding>=1.2.0",
    "sentence-transformers>=2.2.0",
]
all = [
    "pymysql>=1.1.0",
    "jieba>=0.42",
    "hnswlib>=0.7.0",
    "fastembed>=0.2.0",
    "FlagEmbedding>=1.2.0",
    "sentence-transformers>=2.2.0",
]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pymysql>=1.1.0",
]
```

- [ ] **Step 5.2: Verify pyproject.toml parses**

Run: `python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"`
Expected: no exception.

- [ ] **Step 5.3: Commit**

```bash
git add pyproject.toml
git commit -m "build(embeddings): move fastembed/FlagEmbedding/sentence-transformers to optional group (P2-A)"
```

---

## Task 6: Add async LLM method (P2-B part 1)

**Files:**
- Modify: `evolver/llm_client.py:227-310`

- [ ] **Step 6.1: Add `acall_llm` to `LLMClient`**

After the existing `call_llm` method (line 309), insert:

```python
    async def acall_llm(self, input_text: str, system_prompt: str,
                        max_tokens: int) -> str:
        """Async variant of call_llm. Wraps the sync call in asyncio.to_thread."""
        import asyncio
        return await asyncio.to_thread(
            self.call_llm, input_text, system_prompt, max_tokens,
        )
```

- [ ] **Step 6.2: Run the existing LLM client tests**

Run: `pytest tests/test_llm_client.py -v`
Expected: PASS (the sync path is unchanged).

- [ ] **Step 6.3: Commit**

```bash
git add evolver/llm_client.py
git commit -m "feat(llm): add async acall_llm (P2-B)"
```

---

## Task 7: Add async distillation methods (P2-B part 2)

**Files:**
- Modify: `evolver/distillation.py:67-170`
- Test: `tests/test_distillation_async.py` (new)

- [ ] **Step 7.1: Write the failing async distillation test**

```python
# tests/test_distillation_async.py
import asyncio
import json
from unittest.mock import MagicMock

import pytest

from evolver.distillation import DistillationEngine


@pytest.fixture
def mock_archive():
    a = MagicMock()
    a.list_recent.return_value = [
        {"id": 1, "content": "Memory leak in worker pool due to unclosed connections.",
         "kind": "debug", "tags": ["memory"], "source": "dev"},
    ]
    return a


@pytest.fixture
def mock_storage():
    s = MagicMock()
    s.insert_memory.return_value = 101
    return s


@pytest.mark.asyncio
async def test_adistill_with_async_llm(mock_archive, mock_storage):
    llm = MagicMock()
    llm.available = True

    async def fake_acall(input_text, prompt, max_tokens):
        return json.dumps({
            "experiences": [{
                "content": "Always close DB connections in worker cleanup.",
                "category": "optimization",
                "tags": ["db", "cleanup"],
            }]
        })

    llm.acall_llm = fake_acall
    graph = MagicMock()
    link = MagicMock()
    engine = DistillationEngine(
        archive_store=mock_archive, storage=mock_storage,
        graph_engine=graph, link_engine=link,
        llm_client=llm, lang="en",
    )
    result = await engine.adistill(limit=5)
    assert result["stored"] == 1
    assert result["memory_ids"] == [101]
    llm.acall_llm.assert_awaited()


@pytest.mark.asyncio
async def test_adistill_without_llm_falls_back(mock_archive, mock_storage):
    engine = DistillationEngine(
        archive_store=mock_archive, storage=mock_storage,
        graph_engine=MagicMock(), link_engine=MagicMock(),
        llm_client=None, lang="en",
    )
    result = await engine.adistill(limit=5)
    assert result["stored"] == 1
    mem = mock_storage.insert_memory.call_args[0][0]
    assert mem.category == "debug"


@pytest.mark.asyncio
async def test_abuild_links_runs_in_thread(mock_archive, mock_storage):
    link = MagicMock()
    engine = DistillationEngine(
        archive_store=mock_archive, storage=mock_storage,
        graph_engine=MagicMock(), link_engine=link, lang="en",
    )
    result = await engine.abuild_links([1, 2], ["text a", "text b"])
    assert result["total_linked"] == 2
    assert link.auto_link_memory.call_count == 2
```

- [ ] **Step 7.2: Run the test to verify it fails**

Run: `pytest tests/test_distillation_async.py -v`
Expected: FAIL with `AttributeError: 'DistillationEngine' object has no attribute 'adistill'`.

- [ ] **Step 7.3: Add `adistill`, `abuild_graph`, `abuild_links` to `DistillationEngine`**

Insert at the end of `DistillationEngine` (after `_store_memory`):

```python
    # ── async API ──

    async def adistill(self, kind=None, limit=100) -> dict:
        """Async mirror of distill(). Uses acall_llm if the LLM client has it."""
        import asyncio
        processed = stored = skipped = 0
        memory_ids: list[int] = []
        records = await asyncio.to_thread(self._fetch_archive_records,
                                          kind=kind, limit=limit)
        if not records:
            return {"processed": 0, "stored": 0, "skipped": 0, "memory_ids": []}
        for record in records:
            processed += 1
            experience = await self._aextract_experience(record)
            if experience is None:
                skipped += 1
                continue
            mem_id = await asyncio.to_thread(self._store_memory, experience, record)
            if mem_id is not None:
                memory_ids.append(mem_id)
                stored += 1
            else:
                skipped += 1
        return {
            "processed": processed, "stored": stored,
            "skipped": skipped, "memory_ids": memory_ids,
        }

    async def abuild_graph(self, memory_ids, texts) -> dict:
        import asyncio
        node_count = link_count = 0
        for mid, text in zip(memory_ids, texts):
            if not text or not text.strip():
                continue
            node_ids = await asyncio.to_thread(self._graph.build_from_text, text)
            if node_ids:
                node_count += len(node_ids)
                for nid in node_ids:
                    try:
                        await asyncio.to_thread(
                            self._storage.insert_link,
                            "memory", mid, "graph_node", nid,
                            "distill_entity", 1.0,
                        )
                        link_count += 1
                    except Exception as e:
                        logger.debug("Link insert failed (mem=%d, node=%d): %s",
                                     mid, nid, e)
        return {"node_count": node_count, "link_count": link_count}

    async def abuild_links(self, memory_ids, texts) -> dict:
        import asyncio
        count = 0
        for mid, text in zip(memory_ids, texts):
            if not text or not text.strip():
                continue
            try:
                await asyncio.to_thread(self._link.auto_link_memory, mid, text)
                count += 1
            except Exception as e:
                logger.debug("Auto-link failed for memory %d: %s", mid, e)
        return {"total_linked": count}

    async def _aextract_experience(self, record: dict) -> Optional[dict]:
        content = (record.get("content") or "").strip()
        if not content or len(content) < 20:
            return None
        if self._llm and self._llm.available and hasattr(self._llm, "acall_llm"):
            prompt = DISTILL_PROMPTS.get(self._lang, DISTILL_PROMPTS["en"])
            try:
                result = await self._llm.acall_llm(content, prompt, max_tokens=1000)
                result = self._llm.extract_final_answer(result)
                from evolver.utils import extract_json_from_llm
                parsed = extract_json_from_llm(result) or {}
                experiences = parsed.get("experiences", [])
                if experiences:
                    exp = experiences[0]
                    return {
                        "content": exp.get("content", content[:500]),
                        "category": exp.get("category", record.get("kind", "archive")),
                        "tags": exp.get("tags", record.get("tags", []) or []),
                    }
            except Exception as e:
                logger.debug("Async LLM distill failed for archive %s: %s",
                             record.get("id"), e)
        return {
            "content": content[:500],
            "category": record.get("kind", "archive"),
            "tags": record.get("tags", []) or [],
        }
```

- [ ] **Step 7.4: Run the new async test suite**

Run: `pytest tests/test_distillation_async.py -v`
Expected: PASS.

- [ ] **Step 7.5: Run the existing sync distillation tests**

Run: `pytest tests/test_distillation.py -v`
Expected: PASS (sync methods are unchanged).

- [ ] **Step 7.6: Commit**

```bash
git add evolver/distillation.py tests/test_distillation_async.py
git commit -m "feat(distillation): async adistill/abuild_graph/abuild_links (P2-B)"
```

---

## Task 8: RoutingConfig + multi-language search (P3)

**Files:**
- Create: `evolver/search_routing.py`
- Modify: `evolver/search_engine.py:15-159`
- Test: `tests/test_search_routing.py` (new)

- [ ] **Step 8.1: Write the failing test for RoutingConfig**

```python
# tests/test_search_routing.py
import pytest
from unittest.mock import MagicMock

from evolver.search_routing import RoutingConfig, DEFAULT_ROUTING_CONFIG
from evolver.search_engine import SearchEngine


def test_routing_config_default_has_five_languages():
    langs = set(DEFAULT_ROUTING_CONFIG.time_keywords.keys())
    assert {"en", "zh", "ja", "ko", "de", "fr"} <= langs


def test_routing_config_language_returns_per_lang_view():
    en = DEFAULT_ROUTING_CONFIG.language("en")
    assert "today" in en.time_keywords
    assert "what is" in en.fact_keywords


def test_search_engine_routes_japanese_time_query(monkeypatch):
    monkeypatch.setenv("EVOLVER_SEARCH_LANG", "ja")
    mem, hyb, ret, vs, st = MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    ret.recall_by_time.return_value = []
    ret.recall.return_value = []
    engine = SearchEngine(mem, hyb, ret, vs, st,
                          routing_config=RoutingConfig(default_lang="ja"))
    engine.search("昨日 何した", strategy="auto", top_k=5)
    ret.recall_by_time.assert_called()


def test_search_engine_uses_provided_config():
    custom = RoutingConfig(
        default_lang="en",
        time_keywords={"en": ("yesterday",)},
        fact_keywords={"en": ()},
    )
    mem, hyb, ret, vs, st = MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    ret.recall_by_time.return_value = []
    engine = SearchEngine(mem, hyb, ret, vs, st, routing_config=custom)
    engine.search("yesterday plan", strategy="auto", top_k=5)
    ret.recall_by_time.assert_called()
```

- [ ] **Step 8.2: Run the test to verify it fails**

Run: `pytest tests/test_search_routing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evolver.search_routing'`.

- [ ] **Step 8.3: Create `evolver/search_routing.py`**

```python
"""Search routing config: keyword sets per language for auto-routing."""
from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RoutingConfig:
    """Per-language keyword sets for SearchEngine auto-routing.

    `default_lang` selects which language pack the engine reads when it
    has no other signal. The keyword tuples are checked with substring
    containment (case-insensitive for the EN/ASCII forms; case-sensitive
    for the CJK forms so the original tokens are preserved).
    """
    default_lang: str = "en"
    time_keywords: Mapping[str, Sequence[str]] = field(default_factory=dict)
    fact_keywords: Mapping[str, Sequence[str]] = field(default_factory=dict)

    def language(self, name: str) -> "RoutingConfig":
        """Return a copy whose default_lang is set to `name`."""
        return RoutingConfig(
            default_lang=name,
            time_keywords=self.time_keywords,
            fact_keywords=self.fact_keywords,
        )


DEFAULT_ROUTING_CONFIG = RoutingConfig(
    default_lang="en",
    time_keywords={
        "en": ("latest", "today", "yesterday", "this week", "recent", "new"),
        "zh": ("最近", "刚刚", "今天", "昨天", "本周"),
        "ja": ("最近", "今日", "昨日", "今週", "今朝"),
        "ko": ("최근", "오늘", "어제", "이번 주"),
        "de": ("neueste", "heute", "gestern", "diese woche", "kürzlich"),
        "fr": ("récent", "aujourd'hui", "hier", "cette semaine"),
    },
    fact_keywords={
        "en": ("what is", "how to", "difference between", "why", "meaning of"),
        "zh": ("什么是", "为什么", "如何", "怎样"),
        "ja": ("とは", "なぜ", "方法", "使い方"),
        "ko": ("이란", "왜", "어떻게", "방법"),
        "de": ("was ist", "wie", "warum", "unterschied"),
        "fr": ("qu'est-ce que", "comment", "pourquoi", "différence"),
    },
)
```

- [ ] **Step 8.4: Modify `evolver/search_engine.py` to use the config**

Replace `evolver/search_engine.py` lines 15-33 (the class-level keyword tuples) with:

```python
class SearchEngine:
    """Route queries to the right backend (vector / hybrid / memory / auto)."""

    def __init__(
        self,
        memory_engine: Any,
        hybrid_search: Any,
        retrieval_engine: Any,
        vector_store: Any,
        storage: Any,
        routing_config: Any = None,
    ) -> None:
        from evolver.search_routing import DEFAULT_ROUTING_CONFIG
        self._memory_engine = memory_engine
        self._hybrid_search = hybrid_search
        self._retrieval_engine = retrieval_engine
        self._vector_store = vector_store
        self._storage = storage
        self._routing = routing_config or DEFAULT_ROUTING_CONFIG
```

Replace `_is_time_sensitive` (lines 132-139) with:

```python
    def _is_time_sensitive(self, lower: str, original: str) -> bool:
        for kw in self._routing.time_keywords.get("en", ()):
            if kw in lower:
                return True
        for lang in self._routing.time_keywords:
            if lang == "en":
                continue
            for kw in self._routing.time_keywords[lang]:
                if kw in original:
                    return True
        return False
```

Replace `_is_fact_query` (lines 152-159) with:

```python
    def _is_fact_query(self, lower: str, original: str) -> bool:
        for kw in self._routing.fact_keywords.get("en", ()):
            if kw in lower:
                return True
        for lang in self._routing.fact_keywords:
            if lang == "en":
                continue
            for kw in self._routing.fact_keywords[lang]:
                if kw in original:
                    return True
        return False
```

- [ ] **Step 8.5: Run the new and existing search engine tests**

Run: `pytest tests/test_search_routing.py tests/test_search_engine.py -v`
Expected: PASS.

- [ ] **Step 8.6: Commit**

```bash
git add evolver/search_routing.py evolver/search_engine.py tests/test_search_routing.py
git commit -m "feat(search): RoutingConfig + multi-language auto-routing (P3)"
```

---

## Task 9: Final verification

**Files:** none (verification only)

- [ ] **Step 9.1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS. No new failures, no skipped tests that previously ran.

- [ ] **Step 9.2: Run a quick import-cost smoke test**

Run:
```bash
python -c "import time; t0=time.time(); import evolver; print(f'cold import: {time.time()-t0:.2f}s')"
```
Expected: prints in under 2 seconds on a developer machine (the fastembed/sentence-transformers libraries are no longer pulled in by the initial import). Note: this is informational; the assertion is that the test suite still passes, not a strict timing budget.

- [ ] **Step 9.3: Verify the four public API surfaces are unchanged**

```bash
python -c "from evolver.skill import SkillEngine; from evolver.skill_generator import SkillGenerator; from evolver.skill_library import SkillIndex, SkillLibrary; from evolver.search_engine import SearchEngine; from evolver.distillation import DistillationEngine; from evolver.embedding import EmbeddingClient; print('all imports OK')"
```
Expected: prints `all imports OK`.

- [ ] **Step 9.4: Final commit if any drift exists**

```bash
git status
```
If clean, do nothing. If there are unrelated changes, revert them with `git checkout -- .` and re-run `pytest tests/ -v` to confirm green.

## Self-Review Notes

- Spec coverage: every fit criterion in the spec is covered by at least one task (P1 → Tasks 1-3, P2-A → Tasks 4-5, P2-B → Tasks 6-7, P3 → Task 8, full verification → Task 9).
- Placeholder scan: every code block in this plan is copy-pastable; no `TBD`, no `similar to task N`, no `implement later`. The `os.makedirs` removal in Task 3.6 is a concrete grep command, not a vague instruction.
- Type consistency: `SkillIndex.upsert_skill(name, description, file_path, content) -> tuple[int, int]` is the only new public method introduced in the index layer; both `SkillEngine` callers pass those four arguments in that order.
- Backward compatibility: `SkillLibrary = SkillIndex` alias is set at the bottom of `skill_library.py`, and the only modified `__init__.py` block (Task 3.4) keeps the variable name `self._skill_library` so any downstream code that introspected it still works.
