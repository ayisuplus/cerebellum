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


def _display_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _receipt_database(evo) -> str:
    """Return the configured database target for CLI receipts."""
    config = getattr(evo, "config", None)
    url = getattr(config, "mysql_url", "unknown")
    if url in ("unknown", ":memory:", "sqlite:///:memory:", "sqlite://:memory:"):
        return url
    if url.startswith("sqlite:///"):
        db_path = url.removeprefix("sqlite:///")
        path = Path(db_path)
        if not path.is_absolute():
            path = path.resolve()
        return f"{url} ({_display_path(path)})"
    if "://" not in url:
        path = Path(url)
        if not path.is_absolute():
            path = path.resolve()
        return f"{url} ({_display_path(path)})"
    return url


def _receipt_memory_dir(evo) -> str:
    """Return a stable display path for memory distillation files."""
    config = getattr(evo, "config", None)
    memory_dir = getattr(config, "memory_dir", "./memory")
    return _display_path(Path(memory_dir)).removeprefix("./")


def _echo_receipt(evo, lines: list[str]):
    """Print where a write command stored or derived data."""
    click.echo("Storage receipt")
    click.echo(f"  Database: {_receipt_database(evo)}")
    for line in lines:
        click.echo(f"  - {line}")


def _build_kwargs(ctx):
    """Build Evolver kwargs from CLI context."""
    kwargs = {"fallback_embeddings": ctx.obj["fallback"]}
    if ctx.obj["embedding_model"]:
        kwargs["embedding_model"] = ctx.obj["embedding_model"]
    if ctx.obj["embedding_dim"]:
        kwargs["embedding_dim"] = ctx.obj["embedding_dim"]
    return kwargs


@click.group()
@click.version_option(version=__version__, package_name="evolver")
@click.option("--fallback", is_flag=True, default=False,
              help="Use hash-based embeddings (offline mode, no semantic search)")
@click.option("--embedding-model", default=None,
              help="Embedding model name or local path")
@click.option("--embedding-dim", default=None, type=int,
              help="Embedding dimension")
@click.pass_context
def cli(ctx, fallback, embedding_model, embedding_dim):
    """Evolver: agent self-evolution engine."""
    ctx.ensure_object(dict)
    ctx.obj["fallback"] = fallback
    ctx.obj["embedding_model"] = embedding_model
    ctx.obj["embedding_dim"] = embedding_dim


@cli.command()
@click.option("--db-url", default=None, help="Database URL (sqlite:///path or mysql://...)")
@click.pass_context
def init(ctx, db_url):
    """Initialize evolver database and verify setup."""
    kwargs = _build_kwargs(ctx)
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
@click.pass_context
def learn(ctx, db_url, task, outcome, context, solution, lessons):
    """Learn from an interaction."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        ids = evo.learn(
            task=task, outcome=outcome,
            context=context, solution=solution, lessons=lessons,
        )
        click.echo(f"Stored {len(ids)} memories: {ids}")
        _echo_receipt(evo, [
            f"memories: {ids}",
            "interactions: inserted",
            "event_log: learn",
            "graph: derived from task, solution, and lessons when enough content exists",
            "distill: may run in the background when cached summaries are stale",
        ])
    finally:
        evo.close()


@cli.command(name="export-candidates")
@click.option("--db-url", default=None, help="Database URL")
@click.option("--output", required=True, type=click.Path(path_type=Path),
              help="CandidateExport v1 JSON output path")
@click.option("--limit", default=1000, show_default=True, type=click.IntRange(min=1))
@click.option("--category", "categories", multiple=True,
              help="Include only these memory categories (repeatable)")
@click.pass_context
def export_candidates(ctx, db_url, output, limit, categories):
    """Export quarantined candidate experiences for Cerebellum."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        result = evo.export_candidates(
            path=str(output), limit=limit, categories=list(categories) or None,
        )
        click.echo(f"Exported {len(result['candidates'])} candidates to {_display_path(output)}")
        _echo_receipt(evo, [f"candidate_export: {_display_path(output)}"])
    finally:
        evo.close()


@cli.command(name="consolidate-experience")
@click.option("--db-url", default=None, help="Database URL")
@click.option("--input", "input_path", required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="ConsolidationRequest v1 JSON")
@click.option("--output", required=True, type=click.Path(path_type=Path),
              help="ConsolidationResponse v1 JSON output path")
@click.option("--no-store", is_flag=True,
              help="Produce a deterministic proposal response without updating Evolver memory")
@click.pass_context
def consolidate_experience(ctx, db_url, input_path, output, no_store):
    """Consolidate a Cerebellum experience without sharing databases."""
    import json

    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        request = json.loads(input_path.read_text(encoding="utf-8"))
        result = evo.consolidate_experience(
            request, path=str(output), store=not no_store,
        )
        click.echo(
            f"Consolidated {len(result['proposals'])} proposals to {_display_path(output)}"
        )
        _echo_receipt(evo, [f"consolidation_response: {_display_path(output)}"])
    finally:
        evo.close()


@cli.command(name="cerebellum-worker")
@click.option("--db-url", required=True, help="Evolver database URL")
@click.option("--server-url", default="http://127.0.0.1:3927", show_default=True,
              envvar="CEREBELLUM_SERVER_URL")
@click.option("--token", required=True, envvar="CEREBELLUM_AUTH_TOKEN",
              help="Cerebellum local/gateway token")
@click.option("--once", is_flag=True, help="Process at most one job")
@click.option("--poll-seconds", default=5.0, show_default=True, type=float)
@click.pass_context
def cerebellum_worker(ctx, db_url, server_url, token, once, poll_seconds):
    """Run the lease-based Evolver consolidation worker."""
    from evolver.cerebellum_worker import run_worker

    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        processed = run_worker(
            evo, server_url, token, once=once, poll_seconds=poll_seconds,
        )
        click.echo(f"Processed {processed} consolidation jobs")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--query", required=True, help="Search query")
@click.option("--top-k", default=5, type=int, help="Number of results")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def recall(ctx, db_url, query, top_k, fmt):
    """Recall relevant memories."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
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
@click.pass_context
def skillgen(ctx, db_url, topic, output_dir):
    """Generate a skill.md file."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        result = evo.skillgen(topic, output_dir=output_dir)
        if result:
            click.echo(f"Generated: {result.path} (v{result.version})")
            library = getattr(getattr(evo, "_skill_library", None), "_library_path", "./evolver-skills")
            _echo_receipt(evo, [
                f"skills: upserted {result.name} v{result.version}",
                f"skill file: {result.path}",
                f"skill library: {library}",
                "event_log: skillgen",
            ])
        else:
            click.echo("No relevant memories found for this topic.")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--level", type=click.Choice(["today", "week", "longterm", "facts", "all"]),
              default="all", help="Distillation level")
@click.option("--days", default=7, type=int, help="Time range in days")
@click.pass_context
def distill(ctx, db_url, level, days):
    """Run memory distillation pipeline."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
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
            memory_dir = _receipt_memory_dir(evo)
            files = [f"{memory_dir}/{name}" for name in [
                "today.md", "week.md", "longterm.md", "memory_context.md",
            ]]
            _echo_receipt(evo, [
                "distill_runs: cached by level fingerprint",
                "facts: inserted when facts extraction returns new facts",
                "memory files: " + ", ".join(files),
            ])
        else:
            click.echo(result)
            _echo_receipt(evo, [
                f"distill_runs: cached level {level}",
            ])
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--fact", required=True, help="Fact text")
@click.option("--tags", multiple=True, help="Tags (repeatable)")
@click.pass_context
def add_fact(ctx, db_url, fact, tags):
    """Add a fact manually."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        evo.add_fact(fact, tags=list(tags))
        click.echo("Fact added.")
        _echo_receipt(evo, [
            "facts: inserted",
        ])
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--query", default=None, help="Search query")
@click.option("--limit", default=10, type=int)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def facts(ctx, db_url, query, limit, fmt):
    """List or search facts."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
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
@click.option("--data-url", default=None, help="Archive layer MySQL URL (or EVOLVER_DATA_URL)")
@click.option("--content", default="", help="Record text content")
@click.option("--kind", required=True, help="Record category: record | log | image | ...")
@click.option("--tags", multiple=True, help="Tags (repeatable)")
@click.option("--source", default=None, help="Source identifier")
@click.option("--ref", default=None, help="Path/URL reference for images or large files")
@click.option("--meta", default=None, help="Extra metadata as a JSON string")
@click.pass_context
def archive(ctx, data_url, content, kind, tags, source, ref, meta):
    """Store a dead-data record in the archive layer (MySQL)."""
    import json as _json
    meta_dict = None
    if meta:
        try:
            meta_dict = _json.loads(meta)
        except ValueError:
            click.echo("Error: --meta must be a valid JSON string")
            return
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(None, data_url=data_url, **kwargs)
    try:
        new_id = evo.archive(
            content, kind=kind, tags=list(tags) or None,
            source=source, ref=ref, meta=meta_dict,
        )
        click.echo(f"Archived record id={new_id}")
        click.echo("Storage receipt")
        click.echo(f"  Archive: {evo.config.data_url}")
        click.echo(f"  - archive: inserted id={new_id} (kind={kind})")
    except EvolverError as e:
        click.echo(f"Error: {e}")
    finally:
        evo.close()


@cli.command(name="query-archive")
@click.option("--data-url", default=None, help="Archive layer MySQL URL (or EVOLVER_DATA_URL)")
@click.option("--query", default=None, help="Full-text search query")
@click.option("--id", "archive_id", type=int, default=None, help="Fetch a single record by id")
@click.option("--limit", default=20, type=int, help="Max results for search")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def query_archive(ctx, data_url, query, archive_id, limit, fmt):
    """Query the archive layer by full-text search or by id."""
    if not query and archive_id is None:
        click.echo("Error: specify --query or --id")
        return
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(None, data_url=data_url, **kwargs)
    try:
        if archive_id is not None:
            row = evo.get_archive(archive_id)
            results = [row] if row else []
        else:
            results = evo.search_archive(query, limit=limit)
        if fmt == "json":
            click.echo(format_output(results, "json"))
        else:
            if not results:
                click.echo("No archive records found.")
                return
            for r in results:
                tags = r.get("tags") or []
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                ref_str = f" ref={r['ref']}" if r.get("ref") else ""
                snippet = (r.get("content") or "")[:200]
                click.echo(f"[{r['id']}] ({r.get('kind')}){tag_str}{ref_str}")
                click.echo(f"    {snippet}")
                click.echo()
    except EvolverError as e:
        click.echo(f"Error: {e}")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.pass_context
def stats(ctx, db_url):
    """Show engine statistics."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
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
@click.option("--stale", is_flag=True, help="Delete all stale lifecycle memories")
@click.pass_context
def forget(ctx, db_url, memory_id, older_than, below, stale):
    """Forget memories."""
    if not any([memory_id, older_than, below, stale]):
        click.echo("Error: specify --id, --older-than, --below, or --stale")
        return
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        if stale:
            deleted = evo._storage.delete_memories_by_lifecycle("stale")
            evo._storage.log_event("forget", {"batch": True, "lifecycle": "stale", "count": deleted})
            click.echo(f"Forgot {deleted} stale memories.")
        else:
            evo.forget(memory_id=memory_id, older_than_days=older_than, low_importance=below)
            click.echo("Done.")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--file", "-f", required=True, type=click.Path(exists=True), help="Skill file path")
@click.option("--topic", default="", help="Skill topic (auto-detected from filename if omitted)")
def evaluate(db_url, file, topic):
    """Evaluate a skill file quality."""
    import os
    content = open(file, encoding="utf-8").read()
    topic_name = topic or os.path.splitext(os.path.basename(file))[0]
    evo = make_evolver(db_url)
    try:
        result = evo.eval_skill(content, topic_name)
        click.echo(f"Overall: {result.total_score:.1f}/100")
        for dim, score in result.dim_scores.items():
            weight = evo._checker.DIMENSIONS.get(dim, 0)
            click.echo(f"  {dim}: {score:.1f}/{weight}")
        click.echo(f"Status: {result.status}")
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--category", default=None, help="Filter L1 by category")
@click.pass_context
def wake_up(ctx, db_url, category):
    """L0+L1 progressive memory context for agent wake-up."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        click.echo(evo.wake_up(category=category))
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--query", required=True, help="Search query")
@click.option("--category", default=None, help="Filter by category")
@click.option("--top-k", default=10, type=int)
@click.pass_context
def recall_light(ctx, db_url, query, category, top_k):
    """L2 on-demand recall with truncated snippets."""
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        click.echo(evo.recall_light(query, category=category, top_k=top_k))
    finally:
        evo.close()


@cli.command()
@click.option("--db-url", default=None, help="Database URL")
@click.option("--dry-run", is_flag=True, default=False, help="Preview without deleting")
@click.option("--threshold", type=float, default=0.15, help="Cosine distance threshold")
@click.option("--category", default=None, help="Filter by category")
@click.pass_context
def dedup(ctx, db_url, dry_run, threshold, category):
    """Remove near-duplicate memories."""
    from evolver.dedup import Deduplicator
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        deduplicator = Deduplicator(evo._storage, evo._embedding, threshold=threshold)
        kept, deleted = deduplicator.dedup(category=category, dry_run=dry_run)
        mode = "DRY RUN" if dry_run else "LIVE"
        click.echo(f"[{mode}] Kept: {kept}, Deleted: {deleted}")
    finally:
        evo.close()


@cli.command(name="ingest")
@click.option("--db-url", default=None, help="Database URL")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, help="Scan subdirectories (default: recursive)")
@click.option("--max-size", default=10, type=int, help="Max file size in MB (default: 10)")
@click.option("--source", default="ingest", help="Source label prefix")
@click.pass_context
def ingest(ctx, db_url, directory, recursive, max_size, source):
    """Batch ingest documents from a directory.

    Scans DIRECTORY for .txt, .md, .pdf, .docx files,
    extracts text, and feeds into learn_extracted for intelligent
    fact extraction and storage.
    """
    from evolver.ingest import ingest_directory, SUPPORTED_EXTENSIONS
    max_bytes = max_size * 1024 * 1024
    kwargs = _build_kwargs(ctx)
    evo = make_evolver(db_url, **kwargs)
    try:
        total_files = 0
        def show_progress(idx, total, path):
            nonlocal total_files
            total_files = total
            click.echo(f"  [{idx}/{total}] {path}")

        click.echo(f"Ingesting from: {_display_path(Path(directory))}")
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        click.echo(f"  Supported: {supported}")
        click.echo(f"  Recursive: {recursive}")
        click.echo()

        stats = ingest_directory(
            evo, directory,
            recursive=recursive,
            source_prefix=source,
            max_file_size=max_bytes,
            on_progress=show_progress,
        )

        click.echo()
        click.echo("Ingest complete.")
        click.echo(f"  Files scanned: {stats.total_files}")
        click.echo(f"  Processed: {stats.processed}")
        click.echo(f"  Skipped: {stats.skipped}")
        click.echo(f"  Errors: {stats.errors}")
        click.echo(f"  Facts added: {stats.facts_added}")
        click.echo(f"  Facts skipped (duplicate): {stats.facts_skipped}")

        if stats.errors > 0:
            click.echo()
            click.echo("Errors:")
            for r in stats.file_results:
                if r.status == "error":
                    click.echo(f"  {r.path}: {r.error}")

        _echo_receipt(evo, [
            f"files_scanned: {stats.total_files}",
            f"facts_added: {stats.facts_added}",
            f"facts_skipped: {stats.facts_skipped}",
        ])
    finally:
        evo.close()


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
