import pytest

from evolver.utils import nonempty_lines, cosine_similarity, extract_json_from_llm


def test_nonempty_lines_basic():
    assert nonempty_lines("a\nb\nc") == ["a", "b", "c"]


def test_nonempty_lines_skips_empty():
    assert nonempty_lines("a\n\nb\n  \nc") == ["a", "b", "c"]


def test_nonempty_lines_strips_whitespace_only_lines():
    assert nonempty_lines("\n  \nhello\n  \nworld\n") == ["hello", "world"]


def test_nonempty_lines_empty_string():
    assert nonempty_lines("") == []


def test_nonempty_lines_only_whitespace():
    assert nonempty_lines("   \n  \n\t") == []


# --- cosine_similarity ---

def test_cosine_similarity_identical():
    vec = [1.0, 0.0, 0.0]
    assert cosine_similarity(vec, vec) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


# --- extract_json_from_llm ---

def test_extract_json_from_llm_direct():
    result = extract_json_from_llm('{"key": "value"}')
    assert result == {"key": "value"}


def test_extract_json_from_llm_code_fence():
    text = 'Here is the result:\n```json\n{"key": "value"}\n```'
    result = extract_json_from_llm(text)
    assert result == {"key": "value"}


def test_extract_json_from_llm_no_json():
    result = extract_json_from_llm("No JSON here")
    assert result is None
