"""Tests for the SQLite archive migration check script."""

import os
import sys
from pathlib import Path

import pytest


def test_check_sqlite_archive_empty(tmp_path, monkeypatch):
    """check_sqlite_archive() should return [] when no files present."""
    from evolver.migrate_archive import check_sqlite_archive

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "evolver.migrate_archive._candidate_paths",
        lambda: [str(tmp_path / "evolver_archive.db"), str(tmp_path / "evolver.db")],
    )
    found = check_sqlite_archive()
    assert found == []


def test_check_sqlite_archive_finds_db(tmp_path, monkeypatch):
    """check_sqlite_archive() should find SQLite archive files in known locations."""
    from evolver.migrate_archive import check_sqlite_archive

    db = tmp_path / "evolver_archive.db"
    db.write_bytes(b"x" * 1024)
    db2 = tmp_path / "evolver.db"
    db2.write_bytes(b"y" * 512)

    monkeypatch.setattr(
        "evolver.migrate_archive._candidate_paths",
        lambda: [str(db), str(db2)],
    )
    found = check_sqlite_archive()
    paths = {item["path"] for item in found}
    assert str(db) in paths
    assert str(db2) in paths


def test_check_sqlite_archive_includes_size(tmp_path, monkeypatch):
    """check_sqlite_archive() should include file size."""
    from evolver.migrate_archive import check_sqlite_archive

    db = tmp_path / "evolver_archive.db"
    db.write_bytes(b"z" * 2048)

    monkeypatch.setattr(
        "evolver.migrate_archive._candidate_paths",
        lambda: [str(db)],
    )
    found = check_sqlite_archive()
    assert len(found) == 1
    assert found[0]["path"] == str(db)
    assert found[0]["size"] == 2048


def test_main_prints_bash_and_powershell_examples(tmp_path, monkeypatch, capsys):
    """main() should print both Bash and PowerShell configuration examples when legacy data found."""
    from evolver.migrate_archive import main

    monkeypatch.setattr(
        "evolver.migrate_archive.check_sqlite_archive",
        lambda: [{"path": "/tmp/legacy.db", "size": 100}],
    )
    rc = main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "Bash" in out
    assert "PowerShell" in out
    assert "EVOLVER_DATA_URL" in out


def test_main_returns_nonzero_when_found(tmp_path, monkeypatch, capsys):
    """main() should return non-zero exit code when legacy data is found."""
    from evolver.migrate_archive import main

    monkeypatch.setattr(
        "evolver.migrate_archive.check_sqlite_archive",
        lambda: [{"path": "/tmp/old.db", "size": 100}],
    )
    rc = main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "Migration steps" in out


def test_main_runs_without_argv():
    """main() should be callable with no arguments (uses defaults)."""
    from evolver.migrate_archive import main

    rc = main()
    assert rc in (0, 1)
