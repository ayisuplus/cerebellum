"""Extra tests for evolver.ingest — PDF/DOCX extraction and error paths."""

import builtins
import importlib
from unittest.mock import MagicMock

import pytest

import evolver.ingest as ingest_mod
from evolver.ingest import extract_text, ingest_directory


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakePdfReader:
    def __init__(self, path):
        self.pages = [_FakePage("page one text"), _FakePage(""), _FakePage("page two text")]


class _FakeParagraph:
    def __init__(self, text):
        self.text = text


class _FakeDocxDocument:
    def __init__(self, path):
        self.paragraphs = [
            _FakeParagraph("first paragraph"),
            _FakeParagraph("   "),
            _FakeParagraph("second paragraph"),
        ]


class TestExtractTextOptionalFormats:
    def test_pdf_extraction_joins_non_empty_pages(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "PdfReader", _FakePdfReader)
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        assert extract_text(pdf) == "page one text\n\npage two text"

    def test_pdf_without_library_raises_import_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "PdfReader", None)
        monkeypatch.setitem(ingest_mod._IMPORT_ERRORS, "pdf", "pip install pypdf")
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        with pytest.raises(ImportError, match="pip install pypdf"):
            extract_text(pdf)

    def test_docx_extraction_skips_blank_paragraphs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "DocxDocument", _FakeDocxDocument)
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"PK fake")
        assert extract_text(docx) == "first paragraph\n\nsecond paragraph"

    def test_docx_without_library_raises_import_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest_mod, "DocxDocument", None)
        monkeypatch.setitem(ingest_mod._IMPORT_ERRORS, "docx", "pip install python-docx")
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"PK fake")
        with pytest.raises(ImportError, match="pip install python-docx"):
            extract_text(docx)


class TestOptionalImportFallbacks:
    def test_missing_pypdf_sets_fallback_state(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("No module named 'pypdf'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        try:
            importlib.reload(ingest_mod)
            assert ingest_mod.PdfReader is None
            assert ingest_mod._IMPORT_ERRORS["pdf"] == "pip install pypdf"
        finally:
            monkeypatch.undo()
            importlib.reload(ingest_mod)

    def test_missing_docx_sets_fallback_state(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("No module named 'docx'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        try:
            importlib.reload(ingest_mod)
            assert ingest_mod.DocxDocument is None
            assert ingest_mod._IMPORT_ERRORS["docx"] == "pip install python-docx"
        finally:
            monkeypatch.undo()
            importlib.reload(ingest_mod)


class TestIngestDirectoryErrorPaths:
    def _make_evolver(self):
        evo = MagicMock()
        evo.learn_extracted.return_value = [{"action": "add", "fact": "f", "id": 1}]
        return evo

    def test_progress_callback_exception_is_swallowed(self, tmp_path):
        (tmp_path / "a.txt").write_text("content here", encoding="utf-8")
        evo = self._make_evolver()

        def bad_callback(i, total, path):
            raise RuntimeError("callback boom")

        stats = ingest_directory(evo, tmp_path, on_progress=bad_callback)
        assert stats.processed == 1
        assert stats.errors == 0

    def test_import_error_during_extract_marks_error(self, tmp_path, monkeypatch):
        (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4 fake")
        monkeypatch.setattr(ingest_mod, "PdfReader", None)
        monkeypatch.setitem(ingest_mod._IMPORT_ERRORS, "pdf", "pip install pypdf")
        evo = self._make_evolver()

        stats = ingest_directory(evo, tmp_path)

        assert stats.errors == 1
        assert stats.processed == 0
        assert stats.file_results[0].status == "error"
        assert "pip install pypdf" in stats.file_results[0].error
        evo.learn_extracted.assert_not_called()

    def test_generic_extract_error_marks_error(self, tmp_path, monkeypatch):
        (tmp_path / "a.txt").write_text("content", encoding="utf-8")
        monkeypatch.setattr(
            ingest_mod, "extract_text",
            MagicMock(side_effect=ValueError("corrupt file")),
        )
        evo = self._make_evolver()

        stats = ingest_directory(evo, tmp_path)

        assert stats.errors == 1
        assert stats.file_results[0].status == "error"
        assert stats.file_results[0].error == "corrupt file"

    def test_source_uses_relative_path(self, tmp_path):
        sub = tmp_path / "nested"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep content", encoding="utf-8")
        evo = self._make_evolver()

        stats = ingest_directory(evo, tmp_path)

        assert stats.processed == 1
        source = evo.learn_extracted.call_args[1]["source"]
        assert source.startswith("ingest:nested")
        assert source.endswith("deep.txt")
