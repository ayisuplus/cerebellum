import os
import pytest
from evolver.search_routing import RoutingConfig, DEFAULT_ROUTING_CONFIG


def test_routing_config_defaults():
    config = RoutingConfig()
    assert config.default_strategy == "auto"
    assert "时间" in config.time_keywords_zh


def test_routing_config_from_env(monkeypatch):
    monkeypatch.setenv("EVOLVER_SEARCH_LANG", "en")
    config = RoutingConfig.from_env()
    assert config.lang == "en"


def test_default_routing_config_has_all_languages():
    assert "zh" in DEFAULT_ROUTING_CONFIG
    assert "en" in DEFAULT_ROUTING_CONFIG
    assert "ja" in DEFAULT_ROUTING_CONFIG
