#!/usr/bin/env python3
"""Validate the monorepo layout and imported knowledge artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVOLVER = ROOT / "components" / "evolver"
WIKI = ROOT / "knowledge" / "skill-wiki"
TRAINING = WIKI / "data" / "training"

REQUIRED_PATHS = (
    ROOT / "Cargo.toml",
    ROOT / "IMPORT_MANIFEST.json",
    EVOLVER / "pyproject.toml",
    EVOLVER / "evolver" / "cerebellum_worker.py",
    EVOLVER / ".claude" / "skills" / "evolver-query" / "SKILL.md",
    EVOLVER / ".claude" / "skills" / "evolver-skill" / "SKILL.md",
    EVOLVER / ".claude" / "skills" / "evolver-store" / "SKILL.md",
    EVOLVER / ".claude" / "skills" / "evolver-study" / "SKILL.md",
    WIKI / "README.md",
    WIKI / "skill-wiki",
    ROOT / "workers" / "social-acquisition" / "pyproject.toml",
    ROOT / "workers" / "social-acquisition" / "Dockerfile",
    ROOT / "workers" / "social-acquisition" / "README.md",
    ROOT
    / "workers"
    / "social-acquisition"
    / "src"
    / "cerebellum_social_acquisition"
    / "worker.py",
    ROOT / "workers" / "social-acquisition" / "tests" / "test_platforms.py",
)
REQUIRED_JSONL_FIELDS = {"prompt", "completion", "metadata"}
FORBIDDEN_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".ann"}


def validate_layout(errors: list[str]) -> None:
    for path in REQUIRED_PATHS:
        if not path.exists():
            errors.append(f"missing required path: {path.relative_to(ROOT)}")

    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "ls-files",
            "-z",
            "--",
            "components/evolver",
            "knowledge/skill-wiki",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"cannot inspect tracked import files: {result.stderr.decode(errors='replace')}")
        return

    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(raw_path.decode("utf-8"))
        if FORBIDDEN_DIRS.intersection(relative.parts):
            errors.append(f"generated path is tracked: {relative}")
        elif relative.suffix in FORBIDDEN_SUFFIXES or relative.name.endswith(".ann.ids"):
            errors.append(f"runtime artifact is tracked: {relative}")
        elif relative.name == ".env":
            errors.append(f"secret environment file is tracked: {relative}")


def validate_manifest(errors: list[str]) -> None:
    path = ROOT / "IMPORT_MANIFEST.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid import manifest: {exc}")
        return

    destinations = {item.get("destination") for item in manifest.get("imports", [])}
    expected = {"components/evolver", "knowledge/skill-wiki"}
    if destinations != expected:
        errors.append(f"unexpected import destinations: {sorted(destinations)}")


def validate_training_jsonl(errors: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    files = sorted(TRAINING.glob("*.jsonl"))
    if not files:
        errors.append("no training JSONL files found")
        return counts

    for path in files:
        count = 0
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    if not raw_line.strip():
                        continue
                    count += 1
                    try:
                        record = json.loads(raw_line)
                    except json.JSONDecodeError as exc:
                        errors.append(
                            f"{path.relative_to(ROOT)}:{line_number}: invalid JSON: {exc}"
                        )
                        continue
                    missing = REQUIRED_JSONL_FIELDS.difference(record)
                    if missing:
                        errors.append(
                            f"{path.relative_to(ROOT)}:{line_number}: "
                            f"missing fields {sorted(missing)}"
                        )
        except OSError as exc:
            errors.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        counts[path.name] = count
    return counts


def validate_wiki(errors: list[str]) -> int:
    pages = sorted((WIKI / "skill-wiki").rglob("*.md"))
    if len(pages) < 1_000:
        errors.append(f"expected at least 1000 Wiki pages, found {len(pages)}")
    for path in pages:
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read Wiki page {path.relative_to(ROOT)}: {exc}")
    return len(pages)


def main() -> int:
    errors: list[str] = []
    validate_layout(errors)
    validate_manifest(errors)
    counts = validate_training_jsonl(errors)
    wiki_pages = validate_wiki(errors)

    print(f"Evolver package: {EVOLVER.relative_to(ROOT)}")
    print(f"Wiki pages: {wiki_pages}")
    for name, count in counts.items():
        print(f"Training records [{name}]: {count}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Monorepo validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
