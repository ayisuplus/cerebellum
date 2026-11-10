# CLI + Skill Implementation Plan

> **Goal:** Add a `click`-based CLI and a Claude Code skill file for evolver-engine.

**Architecture:** Single `evolver/cli.py` module with click group. Entry point in `pyproject.toml`. Skill at `.claude/skills/evolver-engine.md`.

**Tech Stack:** click, pytest

---

## File Map

| File | Purpose |
|---|---|
| `evolver/cli.py` | CLI commands (click group) |
| `evolver/cli_helpers.py` | Shared formatting/config helpers |
| `tests/test_cli.py` | CLI tests with click.testing.CliRunner |
| `.claude/skills/evolver-engine.md` | Claude Code skill file |
| `pyproject.toml` | Add click dep + [project.scripts] entry |

---

### Task 1: Add click dependency + entry point

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

```toml
[project]
dependencies = [
    "fastembed>=0.2.0",
    "jinja2>=3.1.0",
    "numpy>=1.24.0",
    "click>=8.0",
]

[project.scripts]
evolver = "evolver.cli:cli"
```

- [ ] **Step 2: Install in dev mode**

Run: `pip install -e ".[dev]"`
Expected: success

---

### Task 2: Build CLI core (cli.py + cli_helpers.py)

**Files:**
- Create: `evolver/cli.py`
- Create: `evolver/cli_helpers.py`

- [ ] **Step 1: Create cli_helpers.py**

Shared config loader and output formatter.

```python
"""CLI helper utilities."""
import os
import json
from evolver.config import EvolverConfig


def load_config(db_url: str = None) -> EvolverConfig:
    """Load config from args > env > default."""
    url = db_url or os.environ.get("EVOLVER_DB_URL", "")
    if not url:
        url = "evolver.db"  # default SQLite
    return EvolverConfig(mysql_url=url)


def format_output(data, fmt: str = "text") -> str:
    """Format data for CLI output."""
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if isinstance(data, dict):
        return "\n".join(f"{k}: {v}" for k, v in data.items())
    if isinstance(data, list):
        return "\n".join(str(item) for item in data)
    return str(data)


def make_evolver(db_url: str = None, **kwargs):
    """Build Evolver instance from CLI args."""
    from evolver import Evolver
    cfg = load_config(db_url)
    return Evolver(
        db_url=cfg.mysql_url,
        embedding_model=kwargs.get("embedding_model", cfg.embedding_model),
        embedding_dim=kwargs.get("embedding_dim", cfg.embedding_dim),
        recall_top_k=kwargs.get("recall_top_k", cfg.recall_top_k),
        log_level=kwargs.get("log_level", cfg.log_level),
    )
```

- [ ] **Step 2: Create cli.py with all commands**

```python
"""Evolver CLI — agent self-evolution engine."""
import click
from evolver.cli_helpers import make_evolver, format_output


@click.group()
@click.version_option(package_name="evolver")
def cli():
    """Evolver: agent self-evolution engine."""
    pass


@cli.command()
@click.option("--db-url", default=None, help="Database URL (sqlite:///path or mysql://...)")
@click.option("--embedding-model", default=None, help="Embedding model name")
@click.option("--embedding-dim", default=None, type=int, help="Embedding dimension")
def init(db_url, embedding_model, embedding_dim):
    """Initialize evolver database and verify setup."""
    kwargs = {}
    if embedding_model:
        kwargs["embedding_model"] = embedding_model
    if embedding_dim:
        kwargs["embedding_dim"] = embedding_dim
    evo = make_evolver(db_url, **kwargs)
    stats = evo.stats()
    click.echo(f"Database initialized: {stats}")
    evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--task", required=True, help="Task description")
@click.option("--outcome", required=True, type=click.Choice(["success", "failure"]))
@click.option("--context", default="", help="Context information")
@click.option("--solution", default="", help="Solution description")
@click.option("--lessons", default="", help="Lessons learned")
def learn(db_url, task, outcome, context, solution, lessons):
    """Learn from an interaction."""
    evo = make_evolver(db_url)
    try:
        ids = evo.learn(
            task=task, outcome=outcome,
            context=context, solution=solution, lessons=lessons,
        )
        click.echo(f"Stored {len(ids)} memories: {ids}")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--query", required=True, help="Search query")
@click.option("--top-k", default=5, type=int, help="Number of results")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def recall(db_url, query, top_k, fmt):
    """Recall relevant memories."""
    evo = make_evolver(db_url)
    try:
        results = evo.recall(query, top_k=top_k)
        if fmt == "json":
            data = [{"content": r.content, "score": r.score,
                     "category": r.category, "related_nodes": r.related_nodes}
                    for r in results]
            click.echo(format_output(data, "json"))
        else:
            if not results:
                click.echo("No memories found.")
                return
            for i, r in enumerate(results, 1):
                click.echo(f"[{i}] ({r.category}) score={r.score:.3f}")
                click.echo(f"    {r.content[:200]}")
                if r.related_nodes:
                    nodes = ", ".join(n["label"] for n in r.related_nodes[:3])
                    click.echo(f"    nodes: {nodes}")
                click.echo()
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--topic", required=True, help="Skill topic")
@click.option("--output-dir", default="./skills", help="Output directory")
def skillgen(db_url, topic, output_dir):
    """Generate a skill.md file."""
    evo = make_evolver(db_url)
    try:
        result = evo.skillgen(topic, output_dir=output_dir)
        if result:
            click.echo(f"Generated: {result.path} (v{result.version})")
        else:
            click.echo("No relevant memories found for this topic.")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--level", type=click.Choice(["today", "week", "longterm", "facts", "all"]),
              default="all", help="Distillation level")
@click.option("--days", default=7, type=int, help="Time range in days")
def distill(db_url, level, days):
    """Run memory distillation pipeline."""
    evo = make_evolver(db_url)
    try:
        result = evo.distill(level=level, days=days)
        if isinstance(result, dict):
            for k, v in result.items():
                if isinstance(v, str) and len(v) > 100:
                    click.echo(f"[{k}] ({len(v)} chars)")
                    click.echo(v[:500])
                    if len(v) > 500:
                        click.echo("...")
                elif isinstance(v, list):
                    click.echo(f"[{k}] {len(v)} items")
                    for item in v[:5]:
                        click.echo(f"  - {item.get('fact', item)}")
                else:
                    click.echo(f"[{k}] {v}")
                click.echo()
        else:
            click.echo(result)
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--fact", required=True, help="Fact text")
@click.option("--tags", multiple=True, help="Tags (repeatable)")
def add_fact(db_url, fact, tags):
    """Add a fact manually."""
    evo = make_evolver(db_url)
    try:
        evo.add_fact(fact, tags=list(tags))
        click.echo("Fact added.")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--query", default=None, help="Search query")
@click.option("--limit", default=10, type=int)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def facts(db_url, query, limit, fmt):
    """List or search facts."""
    evo = make_evolver(db_url)
    try:
        if query:
            results = evo.search_facts(query, limit=limit)
        else:
            results = evo._storage.get_all_facts(limit=limit)
        if fmt == "json":
            data = [{"id": f.id, "fact": f.fact, "tags": f.tags, "time": f.time}
                    for f in results]
            click.echo(format_output(data, "json"))
        else:
            if not results:
                click.echo("No facts found.")
                return
            for f in results:
                tags = f" [{', '.join(f.tags)}]" if f.tags else ""
                click.echo(f"- {f.fact}{tags}")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
def stats(db_url):
    """Show engine statistics."""
    evo = make_evolver(db_url)
    try:
        s = evo.stats()
        for k, v in s.items():
            click.echo(f"{k}: {v}")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--id", "memory_id", type=int, help="Memory ID to delete")
@click.option("--older-than", type=int, help="Delete memories older than N days")
@click.option("--below", type=float, help="Delete memories with importance below threshold")
def forget(db_url, memory_id, older_than, below):
    """Forget memories."""
    if not any([memory_id, older_than, below]):
        click.echo("Error: specify --id, --older-than, or --below")
        return
    evo = make_evolver(db_url)
    try:
        evo.forget(memory_id=memory_id, older_than_days=older_than, low_importance=below)
        click.echo("Done.")
    finally:
        evo.close()
```

- [ ] **Step 3: Verify CLI loads**

Run: `python -m evolver.cli --help`
Expected: help text with all commands

---

### Task 3: Write CLI tests

**Files:**
- Create: `tests/test_cli.py`

```python
"""Tests for evolver CLI."""
import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from evolver.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Evolver" in result.output


def test_learn_command(runner):
    with patch("evolver.cli_helpers.make_evolver") as mock:
        evo = MagicMock()
        evo.learn.return_value = [1, 2, 3]
        evo.stats.return_value = {"memories": 0}
        mock.return_value = evo
        result = runner.invoke(cli, [
            "learn", "--task", "fix bug", "--outcome", "success",
            "--solution", "fixed it", "--lessons", "check logs first",
        ])
        assert result.exit_code == 0
        assert "3 memories" in result.output
        evo.learn.assert_called_once()
        evo.close.assert_called_once()


def test_recall_command(runner):
    with patch("evolver.cli_helpers.make_evolver") as mock:
        evo = MagicMock()
        from evolver.models import RecallResult
        evo.recall.return_value = [
            RecallResult(content="test memory", score=0.95,
                         source="memory", category="success"),
        ]
        mock.return_value = evo
        result = runner.invoke(cli, ["recall", "--query", "git merge"])
        assert result.exit_code == 0
        assert "test memory" in result.output
        assert "0.95" in result.output


def test_recall_json(runner):
    with patch("evolver.cli_helpers.make_evolver") as mock:
        evo = MagicMock()
        evo.recall.return_value = []
        mock.return_value = evo
        result = runner.invoke(cli, ["recall", "--query", "x", "--format", "json"])
        assert result.exit_code == 0
        assert "[]" in result.output


def test_stats_command(runner):
    with patch("evolver.cli_helpers.make_evolver") as mock:
        evo = MagicMock()
        evo.stats.return_value = {"memories": 42, "nodes": 10, "edges": 15}
        mock.return_value = evo
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "42" in result.output


def test_forget_requires_option(runner):
    result = runner.invoke(cli, ["forget"])
    assert "specify" in result.output.lower()


def test_distill_command(runner):
    with patch("evolver.cli_helpers.make_evolver") as mock:
        evo = MagicMock()
        evo.distill.return_value = {"today": "lesson 1", "week": ""}
        mock.return_value = evo
        result = runner.invoke(cli, ["distill", "--level", "all"])
        assert result.exit_code == 0
        evo.distill.assert_called_once()


def test_add_fact_command(runner):
    with patch("evolver.cli_helpers.make_evolver") as mock:
        evo = MagicMock()
        mock.return_value = evo
        result = runner.invoke(cli, ["add-fact", "--fact", "user prefers Python", "--tags", "python"])
        assert result.exit_code == 0
        assert "added" in result.output.lower()


def test_skillgen_no_memories(runner):
    with patch("evolver.cli_helpers.make_evolver") as mock:
        evo = MagicMock()
        evo.skillgen.return_value = None
        mock.return_value = evo
        result = runner.invoke(cli, ["skillgen", "--topic", "unknown"])
        assert result.exit_code == 0
        assert "no relevant" in result.output.lower()
```

- [ ] **Step 1: Write tests**

Create the file above.

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: all PASS

---

### Task 4: Create Claude Code skill file

**Files:**
- Create: `.claude/skills/evolver-engine.md`

```markdown
---
name: evolver-engine
description: Agent self-evolution engine — learn from interactions, recall memories, generate skills, distill knowledge
tags: [memory, learning, skill-generation, knowledge-graph]
version: 1
---

# Evolver Engine

Agent self-evolution engine. Stores learning experiences, builds knowledge graphs, generates skills, and distills memory over time.

## When to Use

- After completing a task: store the experience with `evolver learn`
- Before starting a task: check for relevant past experiences with `evolver recall`
- Periodically: distill accumulated knowledge with `evolver distill`
- For recurring topics: generate a reusable skill with `evolver skillgen`

## Quick Start

### Learn from an interaction

```bash
evolver learn --task "fix auth timeout" --outcome success \
  --solution "increased JWT expiry to 24h" \
  --lessons "always check token expiry when debugging 401s"
```

### Recall relevant memories

```bash
evolver recall --query "authentication error"
```

### Generate a skill

```bash
evolver skillgen --topic "authentication debugging"
```

### Distill knowledge

```bash
evolver distill --level all --days 7
```

### View statistics

```bash
evolver stats
```

## Programmatic Usage

```python
from evolver import Evolver

with Evolver(db_url="sqlite:///evolver.db") as evo:
    # Learn
    evo.learn(task="fix bug", outcome="success", solution="...")

    # Recall
    results = evo.recall("similar problem")

    # Generate skill
    evo.skillgen("debugging workflow")

    # Distill
    evo.distill(level="all")
    context = evo.memory_context()
```

## Configuration

Set via environment variables or CLI flags:

| Env Var | Default | Description |
|---|---|---|
| `EVOLVER_DB_URL` | `evolver.db` | Database URL |
| `EVOLVER_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model |
| `EVOLVER_EMBEDDING_DIM` | `384` | Vector dimension |
| `EVOLVER_RECALL_TOP_K` | `5` | Default recall results |

## Architecture

- **MemoryEngine**: Store/recall with embedding similarity + graph boost
- **GraphEngine**: Extract entities, build knowledge graph
- **LinkEngine**: Auto-link related memories
- **SkillEngine**: Generate skill.md from memories
- **QualityChecker**: 8-dimension skill evaluation + auto-improve
- **MemoryCompiler**: 4-layer distillation (today/week/longterm/facts)
```

- [ ] **Step 1: Create skill file**

Create `.claude/skills/evolver-engine.md` with the content above.

---

### Task 5: Verify end-to-end

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Test CLI manually**

Run: `evolver --help`
Expected: help text with all commands

Run: `evolver stats`
Expected: shows current stats

- [ ] **Step 3: Commit**

```bash
git add evolver/cli.py evolver/cli_helpers.py tests/test_cli.py \
  .claude/skills/evolver-engine.md pyproject.toml
git commit -m "feat: add CLI and evolver-engine skill"
```
