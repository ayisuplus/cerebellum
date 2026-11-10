"""Extra tests for evolver.cli_helpers — real load_config/format_output/make_evolver."""

import json

import pytest

from evolver.cli_helpers import load_config, format_output, make_evolver

_EVOLVER_ENV_VARS = [
    "EVOLVER_DB_URL", "EVOLVER_DATA_URL", "EVOLVER_EMBEDDING_MODEL",
    "EVOLVER_EMBEDDING_DIM", "EVOLVER_EMBEDDING_PROVIDER",
    "EVOLVER_LLM_PROVIDER", "EVOLVER_LLM_API_KEY", "EVOLVER_LLM_MODEL",
    "EVOLVER_LLM_BASE_URL",
]


@pytest.fixture
def clean_env(monkeypatch):
    for var in _EVOLVER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class TestLoadConfig:
    def test_defaults(self, clean_env):
        cfg = load_config()
        assert cfg.mysql_url == "evolver.db"
        assert cfg.data_url is None
        assert cfg.embedding_model == "BAAI/bge-m3"
        assert cfg.embedding_dim == 1024
        assert cfg.embedding_provider == "flagembedding"
        assert cfg.llm_provider == "openai"
        assert cfg.llm_api_key is None
        assert cfg.llm_model is None
        assert cfg.llm_base_url is None

    def test_env_overrides(self, clean_env):
        clean_env.setenv("EVOLVER_DB_URL", "sqlite:///env.db")
        clean_env.setenv("EVOLVER_DATA_URL", "mysql://u:p@h/archive")
        clean_env.setenv("EVOLVER_EMBEDDING_DIM", "384")
        clean_env.setenv("EVOLVER_LLM_MODEL", "gpt-test")
        cfg = load_config()
        assert cfg.mysql_url == "sqlite:///env.db"
        assert cfg.data_url == "mysql://u:p@h/archive"
        assert cfg.embedding_dim == 384
        assert cfg.llm_model == "gpt-test"

    def test_explicit_args_beat_env(self, clean_env):
        clean_env.setenv("EVOLVER_DB_URL", "sqlite:///env.db")
        cfg = load_config(db_url="sqlite:///arg.db", data_url="mysql://u:p@h/arg")
        assert cfg.mysql_url == "sqlite:///arg.db"
        assert cfg.data_url == "mysql://u:p@h/arg"

    def test_empty_env_db_url_falls_back_to_default(self, clean_env):
        clean_env.setenv("EVOLVER_DB_URL", "")
        cfg = load_config()
        assert cfg.mysql_url == "evolver.db"


class TestFormatOutput:
    def test_json_format(self):
        data = {"name": "测试", "n": 1}
        out = format_output(data, fmt="json")
        assert json.loads(out) == data
        assert "测试" in out  # ensure_ascii=False

    def test_json_format_non_serializable_uses_str(self):
        class Thing:
            def __str__(self):
                return "thing!"
        out = format_output({"obj": Thing()}, fmt="json")
        assert json.loads(out) == {"obj": "thing!"}

    def test_dict_text_format(self):
        assert format_output({"a": 1, "b": 2}) == "a: 1\nb: 2"

    def test_list_text_format(self):
        assert format_output(["x", "y"]) == "x\ny"

    def test_scalar_text_format(self):
        assert format_output(42) == "42"
        assert format_output("plain") == "plain"


class TestMakeEvolver:
    def test_builds_real_evolver_with_sqlite(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        evolver = make_evolver(
            db_url=f"sqlite:///{tmp_path}/cli.db",
            fallback_embeddings=True,
        )
        try:
            assert evolver.config.mysql_url == f"sqlite:///{tmp_path}/cli.db"
            assert evolver.stats()["memories"] == 0
        finally:
            evolver.close()

    def test_kwargs_override_config(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        evolver = make_evolver(
            db_url=f"sqlite:///{tmp_path}/cli2.db",
            fallback_embeddings=True,
            embedding_model="custom-model",
            recall_top_k=9,
        )
        try:
            assert evolver.config.embedding_model == "custom-model"
            assert evolver.config.recall_top_k == 9
        finally:
            evolver.close()
