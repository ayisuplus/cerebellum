"""CLI helper utilities."""
import dataclasses
import os
import json
from evolver.config import EvolverConfig


def load_config(db_url: str = None, data_url: str = None) -> EvolverConfig:
    """Load config via the canonical from_env parser, overriding
    db_url/data_url if provided. Falls back to a local file DB when neither
    the argument nor EVOLVER_DB_URL/EVOLVER_MYSQL_URL is set."""
    url = db_url or os.environ.get("EVOLVER_DB_URL", "") or os.environ.get("EVOLVER_MYSQL_URL", "")
    if not url:
        url = "evolver.db"
    # from_env is the single parser; give it the resolved URL without
    # leaking a mutation into the caller's environment.
    previous = os.environ.get("EVOLVER_DB_URL")
    os.environ["EVOLVER_DB_URL"] = url
    try:
        cfg = EvolverConfig.from_env()
    finally:
        if previous is None:
            del os.environ["EVOLVER_DB_URL"]
        else:
            os.environ["EVOLVER_DB_URL"] = previous
    return dataclasses.replace(cfg, data_url=data_url or cfg.data_url)


def format_output(data, fmt: str = "text") -> str:
    """Format data for CLI output."""
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if isinstance(data, dict):
        return "\n".join(f"{k}: {v}" for k, v in data.items())
    if isinstance(data, list):
        return "\n".join(str(item) for item in data)
    return str(data)


def make_evolver(db_url: str = None, data_url: str = None, **kwargs):
    """Build Evolver instance from CLI args + env vars."""
    from evolver import Evolver
    cfg = load_config(db_url, data_url)
    return Evolver(
        db_url=cfg.mysql_url,
        data_url=cfg.data_url,
        embedding_model=kwargs.get("embedding_model", cfg.embedding_model),
        embedding_dim=kwargs.get("embedding_dim", cfg.embedding_dim),
        recall_top_k=kwargs.get("recall_top_k", cfg.recall_top_k),
        log_level=kwargs.get("log_level", cfg.log_level),
        fallback_embeddings=kwargs.get("fallback_embeddings", False),
        llm_provider=kwargs.get("llm_provider", cfg.llm_provider),
        llm_api_key=kwargs.get("llm_api_key", cfg.llm_api_key),
        llm_model=kwargs.get("llm_model", cfg.llm_model),
        llm_base_url=kwargs.get("llm_base_url", cfg.llm_base_url),
        embedding_provider=kwargs.get("embedding_provider", cfg.embedding_provider),
    )
