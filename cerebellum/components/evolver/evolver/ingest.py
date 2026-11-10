"""Batch document ingestion — extract text and feed into learn_extracted.

Supports: .txt, .md, .pdf (pypdf), .docx (python-docx).
PDF and DOCX handling is optional; missing libraries are reported with a
helpful message rather than crashing the whole batch.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}

_IMPORT_ERRORS: dict[str, str] = {}

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
    _IMPORT_ERRORS["pdf"] = "pip install pypdf"

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None
    _IMPORT_ERRORS["docx"] = "pip install python-docx"


@dataclass
class IngestResult:
    """Result for a single file ingestion."""
    path: str
    status: str  # "ok" | "skipped" | "error"
    facts_added: int = 0
    facts_skipped: int = 0
    error: str = ""


@dataclass
class IngestStats:
    """Aggregate ingestion statistics."""
    total_files: int = 0
    processed: int = 0
    skipped: int = 0
    errors: int = 0
    facts_added: int = 0
    facts_skipped: int = 0
    file_results: list[IngestResult] = field(default_factory=list)


def extract_text(path: Path) -> str:
    """Extract plain text from a file based on its extension.

    Returns empty string for unsupported formats or unreadable files.
    """
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        if PdfReader is None:
            raise ImportError(_IMPORT_ERRORS["pdf"])
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    if suffix == ".docx":
        if DocxDocument is None:
            raise ImportError(_IMPORT_ERRORS["docx"])
        doc = DocxDocument(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    return ""


def scan_directory(directory: Path, recursive: bool = True) -> list[Path]:
    """Scan a directory for supported document files.

    Args:
        directory: Root directory to scan.
        recursive: Whether to scan subdirectories.

    Returns:
        Sorted list of file paths with supported extensions.
    """
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    pattern = "**/*" if recursive else "*"
    files = []
    for f in directory.glob(pattern):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(f)
    return sorted(files)


def ingest_directory(
    evolver,
    directory: str | Path,
    recursive: bool = True,
    source_prefix: str = "ingest",
    max_file_size: int = 10 * 1024 * 1024,
    on_progress=None,
) -> IngestStats:
    """Ingest all supported documents from a directory.

    For each file:
    1. Extract text content
    2. Call evolver.learn_extracted() to extract and store atomic facts
    3. Track progress and results

    Args:
        evolver: Evolver instance with learn_extracted() method.
        directory: Path to the directory to scan.
        recursive: Whether to scan subdirectories (default True).
        source_prefix: Source label for learn_extracted (default "ingest").
        max_file_size: Skip files larger than this (bytes, default 10MB).
        on_progress: Optional callback(file_index, total_files, file_path).

    Returns:
        IngestStats with aggregate results.
    """
    directory = Path(directory)
    files = scan_directory(directory, recursive=recursive)

    stats = IngestStats(total_files=len(files))

    if not files:
        logger.info("No supported files found in %s", directory)
        return stats

    for i, file_path in enumerate(files, 1):
        result = IngestResult(path=str(file_path), status="ok")

        if on_progress:
            try:
                on_progress(i, len(files), str(file_path))
            except Exception:
                pass

        file_size = file_path.stat().st_size
        if file_size > max_file_size:
            result.status = "skipped"
            result.error = f"File too large ({file_size} bytes, limit {max_file_size})"
            stats.skipped += 1
            stats.file_results.append(result)
            logger.warning("Skipping %s: %s", file_path, result.error)
            continue

        try:
            text = extract_text(file_path)
        except ImportError as e:
            result.status = "error"
            result.error = str(e)
            stats.errors += 1
            stats.file_results.append(result)
            logger.error("Cannot extract %s: %s", file_path, e)
            continue
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            stats.errors += 1
            stats.file_results.append(result)
            logger.error("Failed to extract %s: %s", file_path, e)
            continue

        if not text.strip():
            result.status = "skipped"
            result.error = "Empty content"
            stats.skipped += 1
            stats.file_results.append(result)
            logger.info("Skipping %s: empty content", file_path)
            continue

        source = f"{source_prefix}:{file_path.relative_to(directory)}"
        try:
            results = evolver.learn_extracted(text, source=source)
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            stats.errors += 1
            stats.file_results.append(result)
            logger.error("Ingest %s failed: %s", file_path, e)
            continue

        added = sum(1 for r in results if r.get("action") == "add")
        skipped = sum(1 for r in results if r.get("action") == "skip")
        result.facts_added = added
        result.facts_skipped = skipped
        stats.facts_added += added
        stats.facts_skipped += skipped
        stats.processed += 1
        stats.file_results.append(result)
        logger.info("Ingested %s: %d facts added, %d skipped",
                     file_path, added, skipped)

    return stats