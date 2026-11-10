import numpy as np
from unittest.mock import MagicMock
from evolver.stack import truncate_content
from evolver.memory import MemoryEngine
from evolver.models import Memory
from evolver.stack import MemoryStack


def test_truncate_short_text_unchanged():
    text = "Short text."
    assert truncate_content(text, max_chars=200) == text


def test_truncate_at_sentence_boundary():
    text = "First sentence. Second sentence that is much longer and goes on and on."
    result = truncate_content(text, max_chars=30)
    assert result.endswith("...")
    assert len(result) <= 33  # 30 + "..."


def test_truncate_at_newline_boundary():
    text = "Line one\nLine two\nLine three"
    result = truncate_content(text, max_chars=15)
    assert result.endswith("...")


def test_truncate_hard_cut_if_no_boundary():
    text = "a" * 300
    result = truncate_content(text, max_chars=100)
    assert len(result) == 103  # 100 + "..."
    assert result.endswith("...")


def test_truncate_empty_string():
    assert truncate_content("", max_chars=200) == ""


# --- MemoryStack tests ---


def make_stack():
    mock_storage = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.dim = 384
    mock_embedding.embed_single.return_value = np.random.rand(384).tolist()
    mock_embedding.vector_to_bytes.return_value = b"\x00" * (384 * 4)
    mock_embedding.bytes_to_vector.return_value = [0.0] * 384
    engine = MemoryEngine(mock_storage, mock_embedding)
    stack = MemoryStack(engine)
    return stack, engine, mock_storage


def test_wake_up_returns_identity_and_top_memories():
    stack, engine, storage = make_stack()
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content="A" * 300, category="success", importance=0.9, embedding=b"\x00" * 12),
        Memory(id=2, content="B" * 100, category="failure", importance=0.3, embedding=b"\x00" * 12),
    ]
    result = stack.wake_up()
    assert isinstance(result, str)
    assert "IDENTITY" in result or "ESSENTIAL" in result or len(result) > 0


def test_wake_up_empty_when_no_memories():
    stack, engine, storage = make_stack()
    storage.get_all_memories_with_embeddings.return_value = []
    result = stack.wake_up()
    assert isinstance(result, str)
    assert len(result) > 0  # at least L0 identity text


def test_wake_up_respects_max_drawers():
    stack, engine, storage = make_stack()
    memories = [
        Memory(id=i, content=f"Item-{i:02d} " * 50, category="success",
               importance=1.0 - i * 0.01, embedding=b"\x00" * 12)
        for i in range(30)
    ]
    storage.get_all_memories_with_embeddings.return_value = memories
    result = stack.wake_up()
    # Only top 15 (MAX_DRAWERS) should appear, not all 30
    assert "Item-29" not in result  # lowest importance excluded
    assert "Item-00" in result  # highest importance included


def test_wake_up_truncates_long_content():
    stack, engine, storage = make_stack()
    long_content = "x" * 500
    storage.get_all_memories_with_embeddings.return_value = [
        Memory(id=1, content=long_content, category="success", importance=0.9, embedding=b"\x00" * 12),
    ]
    result = stack.wake_up()
    assert "x" * 300 not in result


def test_recall_light_returns_truncated_results():
    stack, engine, storage = make_stack()
    engine.recall = MagicMock(return_value=[
        MagicMock(content="Auth fix " * 50, category="success", score=0.95),
    ])
    result = stack.recall_light("auth")
    assert isinstance(result, str)
    assert "L2" in result
    assert "success" in result


def test_recall_deep_returns_recall_results():
    from evolver.models import RecallResult
    stack, engine, storage = make_stack()
    engine.recall = MagicMock(return_value=[
        RecallResult(content="git merge", score=0.8, source="memory", category="success"),
    ])
    results = stack.recall_deep("git conflict")
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].content == "git merge"


def test_recall_light_empty_when_no_memories():
    stack, engine, storage = make_stack()
    engine.recall = MagicMock(return_value=[])
    result = stack.recall_light("anything")
    assert "No memories" in result
