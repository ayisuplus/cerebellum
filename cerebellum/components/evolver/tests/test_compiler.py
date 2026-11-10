import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from evolver.compiler import MemoryCompiler, TOKEN_LIMITS
from evolver.models import Memory


def make_compiler(tmp_path="./test_memory"):
    storage = MagicMock()
    llm = MagicMock()
    llm.compress.return_value = "compressed output"
    compiler = MemoryCompiler(storage, llm, memory_dir=tmp_path, lang="zh")
    return compiler, storage, llm


def test_memories_to_text():
    compiler, _, _ = make_compiler()
    memories = [
        Memory(content="fix auth bug", category="debug", tags=["auth"]),
        Memory(content="deploy to prod", category="ops"),
    ]
    text = compiler._memories_to_text(memories)
    assert "[debug]" in text
    assert "fix auth bug" in text
    assert "(auth)" in text
    assert "[ops]" in text


def test_fingerprint_deterministic():
    compiler, _, _ = make_compiler()
    fp1 = compiler._fingerprint("hello world")
    fp2 = compiler._fingerprint("hello world")
    fp3 = compiler._fingerprint("different")
    assert fp1 == fp2
    assert fp1 != fp3


def test_distill_weight_decays_with_age():
    compiler, _, _ = make_compiler()
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    newer = Memory(
        content="new",
        category="test",
        importance=0.5,
        lifecycle="seed",
        created_at=now.isoformat(),
    )
    older = Memory(
        content="old",
        category="test",
        importance=0.5,
        lifecycle="seed",
        created_at=(now - timedelta(days=7)).isoformat(),
    )

    assert compiler._distill_weight(newer, now=now) > compiler._distill_weight(older, now=now)
    assert compiler._distill_weight(older, now=now) == pytest.approx(0.5)


def test_distill_weight_evergreen_importance_resists_decay():
    compiler, _, _ = make_compiler()
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    evergreen_old = Memory(
        content="evergreen",
        category="test",
        importance=1.0,
        lifecycle="evergreen",
        created_at=(now - timedelta(days=7)).isoformat(),
    )
    stale_new = Memory(
        content="stale",
        category="test",
        importance=0.1,
        lifecycle="stale",
        created_at=now.isoformat(),
    )

    assert compiler._distill_weight(evergreen_old, now=now) > compiler._distill_weight(stale_new, now=now)


def test_distill_weight_fallbacks_for_missing_fields():
    compiler, _, _ = make_compiler()
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    memory = Memory(
        content="fallback",
        category="test",
        importance=None,
        lifecycle="unknown",
        created_at="not-a-date",
    )

    assert compiler._distill_weight(memory, now=now) == pytest.approx(1.0)


def test_compile_today_empty_memories():
    compiler, storage, _ = make_compiler()
    storage.get_memories_in_range.return_value = []
    result = compiler.compile_today()
    assert result == ""
    storage.get_memories_in_range.assert_called_once_with(days=1)


def test_compile_today_calls_llm(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    storage.get_memories_in_range.return_value = [
        Memory(content="learned X", category="test"),
    ]
    storage.get_last_distill_run.return_value = None

    result = compiler.compile_today()

    assert result == "compressed output"
    llm.compress.assert_called_once()
    call_kwargs = llm.compress.call_args
    assert call_kwargs[1]["level"] == "today"
    assert call_kwargs[1]["max_tokens"] == TOKEN_LIMITS["today"]


def test_compile_today_cache_hit(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    storage.get_memories_in_range.return_value = [
        Memory(content="learned X", category="test"),
    ]
    fp = compiler._fingerprint(compiler._memories_to_text(
        storage.get_memories_in_range.return_value
    ))
    storage.get_last_distill_run.return_value = {
        "fingerprint": fp,
        "output": "cached result",
    }

    result = compiler.compile_today()
    assert result == "cached result"
    llm.compress.assert_not_called()


def test_compile_week():
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    storage.get_memories_in_range.return_value = [
        Memory(content="pattern A", category="test"),
    ]
    storage.get_last_distill_run.return_value = None
    result = compiler.compile_week(days=7)
    assert result == "compressed output"
    storage.get_memories_in_range.assert_called_with(days=7)


def test_compile_week_sends_memories_in_weighted_order(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    now = datetime.now(timezone.utc)
    storage.get_memories_in_range.return_value = [
        Memory(
            content="stale new low value",
            category="test",
            importance=0.1,
            lifecycle="stale",
            created_at=now.isoformat(),
        ),
        Memory(
            content="evergreen older high value",
            category="test",
            importance=1.0,
            lifecycle="evergreen",
            created_at=(now - timedelta(days=7)).isoformat(),
        ),
    ]
    storage.get_last_distill_run.return_value = None

    compiler.compile_week(days=7)

    input_text = llm.compress.call_args[0][0]
    assert input_text.index("evergreen older high value") < input_text.index("stale new low value")


def test_compile_facts_sends_memories_in_weighted_order(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    now = datetime.now(timezone.utc)
    storage.get_memories_in_range.return_value = [
        Memory(
            content="low weight fact source",
            category="test",
            importance=0.1,
            lifecycle="stale",
            created_at=now.isoformat(),
        ),
        Memory(
            content="high weight fact source",
            category="test",
            importance=1.0,
            lifecycle="evergreen",
            created_at=(now - timedelta(days=7)).isoformat(),
        ),
    ]
    storage.get_last_distill_run.return_value = None
    llm.compress.return_value = "[]"

    compiler.compile_facts(days=7)

    input_text = llm.compress.call_args[0][0]
    assert input_text.index("high weight fact source") < input_text.index("low weight fact source")


def test_compile_longterm_reads_files(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    # Write week.md
    with open(os.path.join(d, "week.md"), "w") as f:
        f.write("weekly summary")
    with open(os.path.join(d, "longterm.md"), "w") as f:
        f.write("old profile")
    storage.get_last_distill_run.return_value = None

    result = compiler.compile_longterm()
    assert result == "compressed output"
    call_args = llm.compress.call_args[0][0]
    assert "weekly summary" in call_args
    assert "old profile" in call_args


def test_compile_longterm_marks_previous_profile_lower_authority(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    with open(os.path.join(d, "week.md"), "w") as f:
        f.write("new weekly pattern")
    with open(os.path.join(d, "longterm.md"), "w") as f:
        f.write("old profile")
    storage.get_last_distill_run.return_value = None

    compiler.compile_longterm()

    input_text = llm.compress.call_args[0][0]
    assert "[Lower-authority previous long-term profile]" in input_text
    assert "[Higher-authority current weekly patterns]" in input_text
    assert input_text.index("Higher-authority") < input_text.index("Lower-authority")


def test_assemble_active_layer_uses_weighted_order(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, _ = make_compiler(tmp_path=d)
    now = datetime.now(timezone.utc)
    storage.get_memories_in_range.return_value = [
        Memory(
            content="low active",
            category="test",
            importance=0.1,
            lifecycle="stale",
            created_at=now.isoformat(),
        ),
        Memory(
            content="high active",
            category="test",
            importance=1.0,
            lifecycle="evergreen",
            created_at=(now - timedelta(days=7)).isoformat(),
        ),
    ]
    storage.get_all_facts.return_value = []

    result = compiler.assemble()

    assert result.index("high active") < result.index("low active")


def test_parse_facts_valid_json():
    compiler, _, _ = make_compiler()
    raw = '[{"fact": "user likes Python", "tags": ["python", "preference"]}]'
    facts = compiler._parse_facts(raw)
    assert len(facts) == 1
    assert facts[0]["fact"] == "user likes Python"
    assert "python" in facts[0]["tags"]


def test_parse_facts_markdown_wrapped():
    compiler, _, _ = make_compiler()
    raw = '```json\n[{"fact": "test", "tags": ["a"]}]\n```'
    facts = compiler._parse_facts(raw)
    assert len(facts) == 1


def test_parse_facts_invalid():
    compiler, _, _ = make_compiler()
    assert compiler._parse_facts("not json") == []
    assert compiler._parse_facts("{}") == []
    assert compiler._parse_facts("") == []


def test_compile_facts_stores_to_db(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    storage.get_memories_in_range.return_value = [
        Memory(content="fact content", category="test"),
    ]
    storage.get_last_distill_run.return_value = None
    llm.compress.return_value = '[{"fact": "user is dev", "tags": ["dev"]}]'

    facts = compiler.compile_facts()
    assert len(facts) == 1
    storage.insert_facts_batch.assert_called_once_with(facts)


def test_assemble_reads_all_files(tmp_path):
    d = tempfile.mkdtemp()
    compiler, _, _ = make_compiler(tmp_path=d)
    with open(os.path.join(d, "today.md"), "w") as f:
        f.write("today content")
    with open(os.path.join(d, "week.md"), "w") as f:
        f.write("week content")
    with open(os.path.join(d, "longterm.md"), "w") as f:
        f.write("longterm content")

    result = compiler.assemble(format="legacy")
    assert "[Long-term profile]" in result
    assert "[This week]" in result
    assert "[Today]" in result
    assert "longterm content" in result
    assert "today content" in result


def test_distill_all_returns_stats(tmp_path):
    d = tempfile.mkdtemp()
    compiler, storage, llm = make_compiler(tmp_path=d)
    storage.get_memories_in_range.return_value = [
        Memory(content="test", category="test"),
    ]
    storage.get_last_distill_run.return_value = None

    stats = compiler.distill_all(days=7)
    assert "today" in stats
    assert "week" in stats
    assert "longterm" in stats
    assert "facts" in stats
    assert "context" in stats


def test_assemble_four_layers():
    """assemble() should output 4 layers: Active, Quick Access, Durable, Facts."""
    from evolver.models import Fact
    compiler, storage, _ = make_compiler()

    # Mock active memories (Layer 1)
    storage.get_memories_in_range.return_value = [
        Memory(id=1, content="recent fix", category="success", lifecycle="seed"),
    ]
    # Mock facts (Layer 4)
    storage.get_all_facts.return_value = [
        Fact(id=1, fact="pytest uses fixtures", tags=["testing"]),
    ]

    d = tempfile.mkdtemp()
    compiler.memory_dir = d

    # Write some distill files for layers 2-3
    with open(os.path.join(d, "today.md"), "w") as f:
        f.write("Today's lesson: always test edge cases")
    with open(os.path.join(d, "week.md"), "w") as f:
        f.write("This week: learned about RRF fusion")
    with open(os.path.join(d, "longterm.md"), "w") as f:
        f.write("Long-term: expert at knowledge retrieval")

    result = compiler.assemble()

    assert "[Active" in result
    assert "[Quick Access" in result
    assert "[Durable" in result
    assert "[Facts" in result


def test_assemble_legacy_format():
    """assemble(format='legacy') should output old 3-layer format."""
    compiler, storage, _ = make_compiler()
    storage.get_memories_in_range.return_value = []
    storage.get_all_facts.return_value = []

    d = tempfile.mkdtemp()
    compiler.memory_dir = d

    with open(os.path.join(d, "today.md"), "w") as f:
        f.write("Today's lesson")
    with open(os.path.join(d, "week.md"), "w") as f:
        f.write("This week")
    with open(os.path.join(d, "longterm.md"), "w") as f:
        f.write("Long-term")

    result = compiler.assemble(format="legacy")

    assert "[Long-term profile]" in result
    assert "[This week]" in result
    assert "[Today]" in result
    assert "[Active" not in result


def test_read_write_file(tmp_path):
    d = tempfile.mkdtemp()
    compiler, _, _ = make_compiler(tmp_path=d)
    compiler._write_file("test.md", "hello world")
    assert compiler._read_file("test.md") == "hello world"
    assert compiler._read_file("nonexistent.md") == ""
