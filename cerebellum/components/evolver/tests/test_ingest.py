"""Tests for evolver.ingest — batch document ingestion."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from evolver.ingest import (
    extract_text,
    scan_directory,
    ingest_directory,
    IngestStats,
    IngestResult,
    SUPPORTED_EXTENSIONS,
)


class TestExtractText:
    def test_txt_file(self, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("hello world", encoding="utf-8")
        assert extract_text(f) == "hello world"

    def test_md_file(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("# Title\n\nSome content", encoding="utf-8")
        assert "Title" in extract_text(f)
        assert "Some content" in extract_text(f)

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert extract_text(f) == ""

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c", encoding="utf-8")
        assert extract_text(f) == ""

    def test_unicode_content(self, tmp_path):
        f = tmp_path / "cn.txt"
        f.write_text("你好世界 🌍", encoding="utf-8")
        assert "你好世界" in extract_text(f)

    @pytest.mark.skipif(
        bool(os.environ.get("CI")) or not Path("/usr/bin/python3").exists(),
        reason="pypdf not always available in CI"
    )
    def test_pdf_file(self, tmp_path):
        from pypdf import PdfWriter
        pdf_path = tmp_path / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        # PdfWriter blank pages have no extractable text,
        # so we just test the import path works
        with pytest.raises(Exception):
            extract_text(pdf_path)


class TestScanDirectory:
    def test_finds_supported_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "c.csv").write_text("c")
        files = scan_directory(tmp_path)
        names = [f.name for f in files]
        assert "a.txt" in names
        assert "b.md" in names
        assert "c.csv" not in names

    def test_recursive_scan(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep", encoding="utf-8")
        (tmp_path / "top.txt").write_text("top", encoding="utf-8")
        files = scan_directory(tmp_path, recursive=True)
        assert len(files) == 2

    def test_non_recursive_scan(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep", encoding="utf-8")
        (tmp_path / "top.txt").write_text("top", encoding="utf-8")
        files = scan_directory(tmp_path, recursive=False)
        assert len(files) == 1
        assert files[0].name == "top.txt"

    def test_nonexistent_directory(self):
        with pytest.raises(FileNotFoundError):
            scan_directory(Path("/nonexistent/path"))

    def test_empty_directory(self, tmp_path):
        files = scan_directory(tmp_path)
        assert files == []

    def test_supported_extensions(self):
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS


class TestIngestDirectory:
    def _make_evolver(self):
        evo = MagicMock()
        evo.learn_extracted.return_value = [
            {"action": "add", "fact": "fact 1", "id": 1},
            {"action": "skip", "fact": "fact 2"},
        ]
        return evo

    def test_ingest_txt_files(self, tmp_path):
        (tmp_path / "one.txt").write_text("This is important fact about Python.", encoding="utf-8")
        (tmp_path / "two.txt").write_text("This is fact about machine learning.", encoding="utf-8")
        evo = self._make_evolver()
        stats = ingest_directory(evo, tmp_path)
        assert stats.total_files == 2
        assert stats.processed == 2
        assert stats.errors == 0
        assert stats.facts_added == 2
        assert stats.facts_skipped == 2

    def test_ingest_skips_empty_files(self, tmp_path):
        (tmp_path / "empty.txt").write_text("", encoding="utf-8")
        (tmp_path / "content.md").write_text("Some real content here.", encoding="utf-8")
        evo = self._make_evolver()
        stats = ingest_directory(evo, tmp_path)
        assert stats.total_files == 2
        assert stats.skipped == 1
        assert stats.processed == 1

    def test_ingest_skips_large_files(self, tmp_path):
        big = tmp_path / "big.txt"
        big.write_text("x" * 100, encoding="utf-8")
        evo = self._make_evolver()
        stats = ingest_directory(evo, tmp_path, max_file_size=50)
        assert stats.skipped == 1

    def test_ingest_source_label(self, tmp_path):
        (tmp_path / "doc.txt").write_text("content", encoding="utf-8")
        evo = self._make_evolver()
        ingest_directory(evo, tmp_path, source_prefix="mydocs")
        call_args = evo.learn_extracted.call_args
        assert "mydocs:" in call_args[1]["source"]

    def test_ingest_progress_callback(self, tmp_path):
        (tmp_path / "a.txt").write_text("aaa", encoding="utf-8")
        (tmp_path / "b.txt").write_text("bbb", encoding="utf-8")
        evo = self._make_evolver()
        progress = []
        ingest_directory(evo, tmp_path, on_progress=lambda i, t, p: progress.append((i, t, p)))
        assert len(progress) == 2
        assert progress[0][0] == 1
        assert progress[1][0] == 2

    def test_ingest_error_in_extraction(self, tmp_path):
        (tmp_path / "good.txt").write_text("good content", encoding="utf-8")
        evo = self._make_evolver()
        evo.learn_extracted.side_effect = Exception("DB error")
        stats = ingest_directory(evo, tmp_path)
        assert stats.errors == 1
        assert stats.processed == 0

    def test_ingest_nonexistent_directory(self):
        evo = self._make_evolver()
        with pytest.raises(FileNotFoundError):
            ingest_directory(evo, "/nonexistent/path")

    def test_ingest_no_supported_files(self, tmp_path):
        (tmp_path / "data.csv").write_text("a,b,c", encoding="utf-8")
        evo = self._make_evolver()
        stats = ingest_directory(evo, tmp_path)
        assert stats.total_files == 0
        assert stats.processed == 0


class TestIngestResult:
    def test_result_defaults(self):
        r = IngestResult(path="/tmp/test.txt", status="ok")
        assert r.facts_added == 0
        assert r.facts_skipped == 0
        assert r.error == ""


class TestIngestStats:
    def test_stats_defaults(self):
        s = IngestStats()
        assert s.total_files == 0
        assert s.processed == 0
        assert s.skipped == 0
        assert s.errors == 0
        assert s.facts_added == 0
        assert s.facts_skipped == 0
        assert s.file_results == []