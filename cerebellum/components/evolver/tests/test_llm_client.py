import pytest
from evolver.llm_client import LLMClient, PROMPTS, PROVIDERS


@pytest.fixture
def fake_client():
    c = LLMClient(api_key="fake-key")
    assert c.available is True
    return c


def test_llm_client_no_key_uses_heuristic():
    client = LLMClient()
    assert client.available is False
    result = client.compress("line1\nline2\nline3", level="today", max_tokens=100)
    assert "line1" in result


def test_heuristic_compress_respects_budget():
    client = LLMClient()
    long_text = "\n".join(f"line {i} " * 20 for i in range(100))
    result = client.heuristic_compress(long_text, max_tokens=10)
    assert len(result) < len(long_text)


def test_heuristic_compress_empty():
    client = LLMClient()
    assert client.compress("", level="today") == ""
    assert client.compress("   ", level="today") == ""


def test_default_model_openai():
    client = LLMClient(provider="openai")
    assert client.model == "gpt-4o-mini"


def test_default_model_anthropic():
    client = LLMClient(provider="anthropic")
    assert client.model == "claude-3-haiku-20240307"


def test_prompts_cover_all_levels():
    for level in ("today", "week", "longterm", "facts"):
        assert level in PROMPTS
        assert "zh" in PROMPTS[level]
        assert "en" in PROMPTS[level]


def test_compress_falls_back_to_heuristic_on_llm_error(fake_client, monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(fake_client, "call_llm", fail)
    result = fake_client.compress("some text\nmore text", level="today", max_tokens=100)
    assert "some text" in result


def test_call_llm_timeout(fake_client, monkeypatch):
    """compress() catches TimeoutError from _call_llm and falls back to heuristic."""
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out after 120s")

    monkeypatch.setattr(fake_client, "call_llm", raise_timeout)
    result = fake_client.compress("line1\nline2\nline3", level="today", max_tokens=100)
    assert "line1" in result


def test_call_llm_json_decode_error(fake_client, monkeypatch):
    """_extract_final_answer handles non-JSON plain text without crashing."""
    def fake_llm(*args, **kwargs):
        return "not json at all"

    monkeypatch.setattr(fake_client, "call_llm", fake_llm)
    result = fake_client.compress("some content here", level="today", max_tokens=100)
    # Real _extract_final_answer passes through short non-thinking text as-is
    assert isinstance(result, str)
    assert len(result) > 0


def test_provider_model_mapping():
    """Every provider in PROVIDERS has base_url and non-empty models."""
    for provider, cfg in PROVIDERS.items():
        assert "base_url" in cfg, f"{provider} missing base_url"
        assert "models" in cfg, f"{provider} missing models"
        assert cfg["models"], f"{provider} has empty models dict"
        for tier, model_name in cfg["models"].items():
            assert model_name, f"{provider}.models['{tier}'] is empty"


def test_verify_fidelity_low_score(fake_client, monkeypatch):
    """verify() returns verdict='fail' when fidelity < 0.7."""
    def fake_verify_llm(*args, **kwargs):
        return '{"fidelity": 0.3, "issues": ["minor hallucination"], "verdict": "fail"}'

    monkeypatch.setattr(fake_client, "call_llm", fake_verify_llm)
    result = fake_client.verify("original text", "distilled summary")
    assert result["fidelity"] < 0.7
    assert result["verdict"] == "fail"


def test_verify_malformed_response(fake_client, monkeypatch):
    """verify() returns safe defaults when LLM returns non-JSON garbage."""
    def fake_verify_llm(*args, **kwargs):
        return "not valid json {{{"

    monkeypatch.setattr(fake_client, "call_llm", fake_verify_llm)
    result = fake_client.verify("original text", "distilled summary")
    assert result["fidelity"] == 1.0
    assert result["verdict"] == "pass"
