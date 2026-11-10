"""Small shared utilities."""

import json
import re

import numpy as np

try:
    import jieba
    # Stale/corrupt jieba installs (<0.42) lack lcut; treat them as absent
    # so tokenization falls back to the deterministic CJK extraction below.
    _HAS_JIEBA = hasattr(jieba, "lcut")
except ImportError:
    _HAS_JIEBA = False


def nonempty_lines(text: str) -> list[str]:
    """Split *text* into stripped, non-blank lines."""
    return [line.strip() for line in text.split("\n") if line.strip()]


def tokenize(text: str, *,
             min_len: int = 2,
             english_pattern: str = r"[\w一-鿿]+",
             max_items: int = 100,
             stopwords: set | frozenset = frozenset(),
             lowercase: bool = True) -> list[str]:
    """Extract tokens from text with jieba (Chinese) + regex (English).

    Shared tokenizer used by MemoryEngine, ClosetIndex, and GraphEngine.
    Each caller customizes via parameters rather than maintaining a
    separate implementation.

    Args:
        text: Input text.
        min_len: Minimum token length.
        english_pattern: Regex for English/ASCII token extraction
            (default matches word chars + CJK ideographs).
        max_items: Maximum number of tokens to return.
        stopwords: Set of tokens to exclude.
        lowercase: Whether to lowercase English tokens.

    Returns:
        Deduplicated list of tokens, preserving order.
    """
    text = text.lower() if lowercase else text
    tokens: list[str] = []

    if _HAS_JIEBA:
        # Split into Chinese and non-Chinese segments
        segments = re.split(r'([一-鿿]+)', text)
        for seg in segments:
            if not seg.strip():
                continue
            if re.match(r'[一-鿿]', seg):
                # Chinese — use jieba
                tokens.extend(w.strip() for w in jieba.lcut(seg)
                            if len(w.strip()) >= min_len)
            else:
                # English / mixed
                tokens.extend(re.findall(english_pattern, seg))
    else:
        # Callers may intentionally pass an ASCII-only pattern for code
        # artifacts.  Preserve Chinese tokenization when jieba is optional by
        # extracting contiguous CJK segments as a deterministic fallback.
        tokens = re.findall(r"[\u4e00-\u9fff]+", text)
        tokens.extend(re.findall(english_pattern, text))

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for w in tokens:
        w_clean = w.strip().lower() if lowercase else w.strip()
        if (len(w_clean) >= min_len
                and w_clean not in stopwords
                and w_clean not in seen):
            seen.add(w_clean)
            result.append(w_clean)
            if len(result) >= max_items:
                break
    return result


def cosine_similarity(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def embedder_tags_compatible(a: str | None, b: str | None) -> bool:
    """Whether two stored embedder identity tags may be vector-compared.

    Rows without a tag predate embedder tagging and stay comparable with
    everything (legacy behavior); two different non-null tags never
    compare (e.g. hash-fallback rows vs model rows).
    """
    return a is None or b is None or a == b

def embedder_identity_of(embedding) -> str | None:
    """Identity tag of an embedder; None for tagless or duck-typed doubles.

    MagicMock-style test doubles fabricate any attribute, so a plain
    getattr is not enough — only a real string counts as a tag.
    """
    identity = getattr(embedding, "identity", None)
    return identity if isinstance(identity, str) else None


def extract_json_from_llm(text: str | None) -> dict | list | None:
    """Extract JSON from LLM output text.

    Tries: direct parse, ```json code fence, regex extraction.
    Returns parsed dict/list or None.
    """
    if not text:
        return None
    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    # 2. Try ```json code fence
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass
    # 3. Try regex extraction of { ... } or [ ... ]
    # Note: This regex only matches flat (non-nested) JSON structures.
    # For nested JSON, the direct parse or code fence strategies are preferred.
    for pattern in [r'\{[^{}]*\}', r'\[[^\[\]]*\]']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                continue
    return None
