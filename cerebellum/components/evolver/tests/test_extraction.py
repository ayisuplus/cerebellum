from evolver.extraction import MemoryExtractor, EXTRACTION_PROMPTS, DEDUP_PROMPTS


class FakeLLM:
    def __init__(self, available=True):
        self._available = available
        self.calls = []

    @property
    def available(self):
        return self._available

    def call_llm(self, text, prompt, max_tokens=500):
        self.calls.append({"text": text, "prompt": prompt, "max_tokens": max_tokens})
        return "dummy response"

    def extract_final_answer(self, text):
        return text


def test_extract_empty_text():
    extractor = MemoryExtractor(FakeLLM())
    assert extractor.extract("") == []
    assert extractor.extract("   ") == []


def test_extract_llm_unavailable_falls_back():
    extractor = MemoryExtractor(FakeLLM(available=False))
    result = extractor.extract("This is a long enough line to be a fact here")
    assert len(result) >= 1
    assert "text" in result[0]
    assert "tags" in result[0]


def test_extract_llm_none_falls_back():
    extractor = MemoryExtractor(None)
    result = extractor.extract("This is a long enough line of text")
    assert len(result) >= 1


def test_fact_hash_deterministic():
    h1 = MemoryExtractor._fact_hash("  Hello  World  ")
    h2 = MemoryExtractor._fact_hash("hello world")
    assert h1 == h2


def test_fact_hash_different():
    h1 = MemoryExtractor._fact_hash("hello world")
    h2 = MemoryExtractor._fact_hash("goodbye world")
    assert h1 != h2


def test_parse_json_direct():
    result = MemoryExtractor._parse_json('{"facts": [{"text": "hi", "tags": ["t"]}]}')
    assert result["facts"][0]["text"] == "hi"


def test_parse_json_code_fence():
    result = MemoryExtractor._parse_json('```json\n{"facts": [{"text": "x"}]}\n```')
    assert result["facts"][0]["text"] == "x"


def test_parse_json_invalid():
    result = MemoryExtractor._parse_json("not json at all")
    assert result == {}


def test_parse_json_array():
    result = MemoryExtractor._parse_json('[{"text": "direct array", "tags": []}]')
    assert isinstance(result, list)
    assert result[0]["text"] == "direct array"


def test_parse_facts_dict():
    extractor = MemoryExtractor(FakeLLM())
    facts = extractor._parse_facts('{"facts": [{"text": "a fact", "tags": ["x"]}]}')
    assert len(facts) == 1
    assert facts[0]["text"] == "a fact"


def test_parse_facts_array():
    extractor = MemoryExtractor(FakeLLM())
    facts = extractor._parse_facts('[{"text": "b", "tags": []}]')
    assert len(facts) == 1
    assert facts[0]["text"] == "b"


def test_parse_facts_empty():
    extractor = MemoryExtractor(FakeLLM())
    assert extractor._parse_facts("not json") == []


def test_heuristic_extract_skips_short_lines():
    extractor = MemoryExtractor(FakeLLM())
    result = extractor._heuristic_extract("hi\na long enough line here\nok")
    assert len(result) == 1
    assert "long enough" in result[0]["text"]


def test_should_update_hash_match():
    extractor = MemoryExtractor(FakeLLM())
    existing_hashes = {MemoryExtractor._fact_hash("hello world")}
    result = extractor.should_update("hello world", [], existing_hashes)
    assert result == "skip"


def test_should_update_no_llm():
    extractor = MemoryExtractor(FakeLLM(available=False))
    result = extractor.should_update("new fact", [], set())
    assert result == "add"


def test_should_update_no_existing():
    extractor = MemoryExtractor(FakeLLM())
    result = extractor.should_update("new fact", [], set())
    assert result == "add"


def test_extraction_prompts_have_both_langs():
    for lang in ("zh", "en"):
        assert lang in EXTRACTION_PROMPTS
        assert lang in DEDUP_PROMPTS


def test_extract_with_llm_parse_facts():
    llm = FakeLLM()
    llm.extract_final_answer = lambda t: '{"facts": [{"text": "User likes Python", "tags": ["preference", "language"]}]}'
    extractor = MemoryExtractor(llm)
    result = extractor.extract("User likes Python a lot")
    assert len(result) == 1
    assert result[0]["text"] == "User likes Python"
    assert "preference" in result[0]["tags"]
