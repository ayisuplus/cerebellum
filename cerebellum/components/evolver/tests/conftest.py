import sys
import types

# Mock heavy ML deps before anything imports them
for mod_name in [
    "sentence_transformers", "FlagEmbedding", "fastembed",
    "torchcodec", "torchcodec.decoders", "torchcodec.encoders",
    "torchcodec.samplers", "torchcodec.transforms",
]:
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        if mod_name == "sentence_transformers":
            m.SentenceTransformer = None
        elif mod_name == "fastembed":
            class TextEmbedding:
                """Deterministic test double; never downloads a model."""

                def __init__(self, model_name=None):
                    self.model_name = model_name

                def embed(self, texts):
                    for index, _text in enumerate(texts):
                        vector = [0.0] * 384
                        vector[index % 384] = 1.0
                        yield vector

            m.TextEmbedding = TextEmbedding
        sys.modules[mod_name] = m

import pytest
import numpy as np
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def isolated_test_working_directory(tmp_path, monkeypatch):
    """Keep default memory and generated-skill paths out of the source tree."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def mock_conn():
    """Shared context-manager-style MySQL connection double."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda _ctx: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


@pytest.fixture
def mock_embedding():
    """Mock embedding client that returns fixed-dim vectors."""
    client = MagicMock()
    rng = np.random.default_rng(42)
    client.embed.return_value = [rng.random(384).tolist() for _ in range(10)]
    client.embed_single.return_value = rng.random(384).tolist()
    client.dim = 384
    return client


