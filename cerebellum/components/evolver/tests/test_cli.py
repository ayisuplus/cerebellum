"""Tests for evolver CLI."""
import json
import pytest
from click.testing import CliRunner
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from evolver.cli import cli, _receipt_database


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Evolver" in result.output


def test_cli_version_uses_source_version(runner):
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "2.3.0" in result.output


def test_export_candidates_command(runner, tmp_path):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db", memory_dir="./memory")
        evo.export_candidates.return_value = {
            "schema_version": "cerebellum/v1",
            "candidates": [{"candidate_id": "memory:1"}],
        }
        mock.return_value = evo
        output = tmp_path / "candidates.json"

        result = runner.invoke(cli, [
            "export-candidates", "--output", str(output), "--limit", "25",
            "--category", "success",
        ])

        assert result.exit_code == 0
        assert "Exported 1 candidates" in result.output
        evo.export_candidates.assert_called_once_with(
            path=str(output), limit=25, categories=["success"]
        )
        evo.close.assert_called_once()


def test_consolidate_experience_command(runner, tmp_path):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db", memory_dir="./memory")
        evo.consolidate_experience.return_value = {"proposals": [{"kind": "failure"}]}
        mock.return_value = evo
        input_path = tmp_path / "request.json"
        input_path.write_text(json.dumps({"schema_version": "cerebellum/v1"}), encoding="utf-8")
        output = tmp_path / "response.json"

        result = runner.invoke(cli, [
            "consolidate-experience", "--input", str(input_path),
            "--output", str(output), "--no-store",
        ])

        assert result.exit_code == 0
        assert "Consolidated 1 proposals" in result.output
        evo.consolidate_experience.assert_called_once_with(
            {"schema_version": "cerebellum/v1"}, path=str(output), store=False,
        )
        evo.close.assert_called_once()


def test_receipt_database_resolves_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    evo = SimpleNamespace(config=SimpleNamespace(mysql_url="evolver.db"))

    result = _receipt_database(evo)

    assert "evolver.db" in result
    assert str(Path(tmp_path / "evolver.db")).replace("\\", "/") in result


def test_learn_command(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.learn.return_value = [1, 2, 3]
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db", memory_dir="./memory")
        evo.stats.return_value = {"memories": 0}
        mock.return_value = evo
        result = runner.invoke(cli, [
            "learn", "--task", "fix bug", "--outcome", "success",
            "--solution", "fixed it", "--lessons", "check logs first",
        ])
        assert result.exit_code == 0
        assert "3 memories" in result.output
        assert "Storage receipt" in result.output
        assert "Database: sqlite:///test.db" in result.output
        assert "memories: [1, 2, 3]" in result.output
        evo.learn.assert_called_once()
        evo.close.assert_called_once()


def test_recall_command(runner):
    with patch("evolver.cli.make_evolver") as mock:
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
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.recall.return_value = []
        mock.return_value = evo
        result = runner.invoke(cli, ["recall", "--query", "x", "--format", "json"])
        assert result.exit_code == 0
        assert "[]" in result.output


def test_stats_command(runner):
    with patch("evolver.cli.make_evolver") as mock:
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
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db", memory_dir="./memory")
        evo.distill.return_value = {"today": "lesson 1", "week": ""}
        mock.return_value = evo
        result = runner.invoke(cli, ["distill", "--level", "all"])
        assert result.exit_code == 0
        assert "Storage receipt" in result.output
        assert "Database: sqlite:///test.db" in result.output
        assert "memory/today.md" in result.output
        assert "memory/week.md" in result.output
        evo.distill.assert_called_once()


def test_add_fact_command(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db")
        mock.return_value = evo
        result = runner.invoke(cli, ["add-fact", "--fact", "user prefers Python", "--tags", "python"])
        assert result.exit_code == 0
        assert "added" in result.output.lower()
        assert "Storage receipt" in result.output
        assert "facts: inserted" in result.output


def test_skillgen_no_memories(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.skillgen.return_value = None
        mock.return_value = evo
        result = runner.invoke(cli, ["skillgen", "--topic", "unknown"])
        assert result.exit_code == 0
        assert "no relevant" in result.output.lower()


def test_skillgen_command_prints_storage_receipt(runner, tmp_path):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db")
        evo._skill_library = SimpleNamespace(_library_path=tmp_path / "evolver-skills")
        result_obj = SimpleNamespace(
            name="git-workflow",
            path=str(tmp_path / "skills" / "git-workflow.md"),
            content="# Git workflow",
            version=1,
        )
        evo.skillgen.return_value = result_obj
        mock.return_value = evo

        result = runner.invoke(cli, ["skillgen", "--topic", "git workflow"])

        assert result.exit_code == 0
        assert "Generated:" in result.output
        assert "Storage receipt" in result.output
        assert "Database: sqlite:///test.db" in result.output
        assert f"skill file: {result_obj.path}" in result.output
        assert f"skill library: {tmp_path / 'evolver-skills'}" in result.output


def test_evaluate_command(runner, tmp_path):
    skill_file = tmp_path / "test-skill.md"
    skill_file.write_text("# Test Skill\n\nDo this and that.")
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        from evolver.models import EvalResult
        evo.eval_skill.return_value = EvalResult(
            total_score=78.5,
            dim_scores={"frontmatter": 8, "workflow": 7, "edge_cases": 7.5,
                        "checkpoints": 7, "specificity": 8, "resources": 7.5,
                        "architecture": 8, "effectiveness": 7},
            round=1,
            status="pass",
        )
        mock.return_value = evo
        result = runner.invoke(cli, ["evaluate", "-f", str(skill_file)])
        assert result.exit_code == 0
        assert "78.5" in result.output
        assert "pass" in result.output


def test_dedup_dry_run(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo._storage.get_all_memories_with_embeddings.return_value = []
        mock.return_value = evo
        result = runner.invoke(cli, ["dedup", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Kept" in result.output


def test_archive_command(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.archive.return_value = 42
        evo.config = SimpleNamespace(data_url="mysql://root:root@localhost:3306/data")
        mock.return_value = evo
        result = runner.invoke(cli, [
            "archive", "--content", "deploy log payload", "--kind", "log",
            "--tags", "prod", "--source", "ci",
            "--data-url", "mysql://root:root@localhost:3306/data",
        ])
        assert result.exit_code == 0
        assert "Archived record id=42" in result.output
        assert "Storage receipt" in result.output
        assert "mysql://root:root@localhost:3306/data" in result.output
        evo.archive.assert_called_once()
        evo.close.assert_called_once()


def test_archive_invalid_meta_json(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        mock.return_value = evo
        result = runner.invoke(cli, [
            "archive", "--content", "x", "--kind", "log", "--meta", "{not json",
        ])
        assert result.exit_code == 0
        assert "must be a valid JSON" in result.output
        # make_evolver should not even be invoked on bad meta
        mock.assert_not_called()


def test_query_archive_search(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.search_archive.return_value = [
            {"id": 1, "content": "git rebase notes", "kind": "log",
             "ref": None, "tags": ["git"], "source": "ci", "meta": None,
             "created_at": "2026-05-29"},
        ]
        mock.return_value = evo
        result = runner.invoke(cli, ["query-archive", "--query", "git"])
        assert result.exit_code == 0
        assert "git rebase notes" in result.output
        assert "[1]" in result.output
        evo.search_archive.assert_called_once()


def test_query_archive_by_id(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.get_archive.return_value = {
            "id": 7, "content": "single record", "kind": "record",
            "ref": None, "tags": None, "source": None, "meta": None,
            "created_at": "2026-05-29",
        }
        mock.return_value = evo
        result = runner.invoke(cli, ["query-archive", "--id", "7"])
        assert result.exit_code == 0
        assert "single record" in result.output
        evo.get_archive.assert_called_once_with(7)


def test_query_archive_requires_query_or_id(runner):
    result = runner.invoke(cli, ["query-archive"])
    assert "specify" in result.output.lower()


def test_archive_not_configured_prints_guidance(runner):
    from evolver.exceptions import EvolverError
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.archive.side_effect = EvolverError(
            "Archive layer not configured. Pass data_url= to enable it."
        )
        mock.return_value = evo
        result = runner.invoke(cli, ["archive", "--content", "x", "--kind", "log"])
        assert result.exit_code == 0
        assert "data_url" in result.output
        evo.close.assert_called_once()


def test_query_archive_not_found(runner):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.search_archive.return_value = []
        mock.return_value = evo
        result = runner.invoke(cli, ["query-archive", "--query", "nothing"])
        assert result.exit_code == 0
        assert "No archive records found" in result.output


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


def test_ingest_command(runner, tmp_path):
    (tmp_path / "notes.txt").write_text("Python is great for scripting.", encoding="utf-8")
    (tmp_path / "guide.md").write_text("# Guide\n\nUse git for version control.", encoding="utf-8")
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db", memory_dir="./memory")
        evo.learn_extracted.return_value = [
            {"action": "add", "fact": "Python scripting", "id": 1},
            {"action": "skip", "fact": "version control"},
        ]
        mock.return_value = evo
        result = runner.invoke(cli, ["ingest", str(tmp_path)])
        assert result.exit_code == 0
        assert "Ingest complete" in result.output
        assert "Storage receipt" in result.output


def test_ingest_empty_directory(runner, tmp_path):
    with patch("evolver.cli.make_evolver") as mock:
        evo = MagicMock()
        evo.config = SimpleNamespace(mysql_url="sqlite:///test.db")
        mock.return_value = evo
        result = runner.invoke(cli, ["ingest", str(tmp_path)])
        assert result.exit_code == 0
        assert "Files scanned: 0" in result.output


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
