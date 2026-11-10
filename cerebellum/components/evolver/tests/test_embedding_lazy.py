import sys
import importlib
import builtins
import pytest


def test_embedding_module_imports_without_fastembed(monkeypatch):
    """Importing evolver.embedding should not require fastembed or sentence_transformers."""
    blocked = {"fastembed", "sentence_transformers"}
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in blocked or any(name.startswith(b + ".") for b in blocked):
            raise ImportError(f"Blocked {name} for this test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
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
