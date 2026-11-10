import re

# System tags to strip (line-anchored, lazy body, can't cross blank lines)
_NOISE_TAGS = (
    "system-reminder",
    "command-message",
    "command-name",
    "task-notification",
    "user-prompt-submit-hook",
    "hook_output",
)

_TAG_PATTERNS = [
    re.compile(
        rf"(?m)^<{name}(?:\s[^>]*)?>" rf"(?:(?!\n\s*\n)[\s\S])*?" rf"</{name}>[ \t]*\n?"
    )
    for name in _NOISE_TAGS
]

# Hook output lines (line-anchored)
_HOOK_LINE_RE = re.compile(
    r"(?m)^Ran \d+ (?:Stop|PreCompact|PreToolUse|PostToolUse|UserPromptSubmit|Notification|SessionStart|SessionEnd) hook[s]?.*\n?"
)

# Collapsed lines marker
_COLLAPSED_LINES_RE = re.compile(r"(?m)^…\s*\+\d+ lines.*\n?")


def strip_noise(text: str) -> str:
    """Remove system tags, hook output, and UI chrome from text.

    All patterns are line-anchored. Inline mentions in user prose are preserved.
    """
    for pat in _TAG_PATTERNS:
        text = pat.sub("", text)
    text = _HOOK_LINE_RE.sub("", text)
    text = _COLLAPSED_LINES_RE.sub("", text)
    return text


def normalize_input(text: str, source: str = "auto") -> str:
    """Normalize input text before storage.

    Args:
        text: Raw input text.
        source: Source type hint (auto, chat_export, raw).

    Returns:
        Cleaned text.
    """
    return strip_noise(text)
