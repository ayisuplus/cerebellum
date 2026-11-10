from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PREFERENCE_PATTERNS = [
    (re.compile(r"(?:prefer|like|love|enjoy|favor|always use|always choose)\s+(\w+)", re.I), "static"),
    (re.compile(r"(?:dislike|hate|avoid|never use)\s+(\w+)", re.I), "static"),
    (re.compile(r"(?:working on|currently|right now|now doing)\s+(.+?)(?:\.|,|$)", re.I), "dynamic"),
    (re.compile(r"(?:switched to|migrated to|moved to)\s+(\w+)", re.I), "dynamic"),
]

CATEGORY_WEIGHTS = {
    "success": 1.2,
    "insight": 1.3,
    "failure": 1.0,
    "pattern": 0.9,
}


@dataclass
class ProfileTrait:
    key: str
    value: str
    source: str = "inferred"
    is_static: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decay_rate: float = 0.01
    base_importance: float = 0.5

    EXPIRY_THRESHOLD = 0.1

    def is_expired(self) -> bool:
        if self.is_static:
            return False
        if self.decay_rate <= 0:
            return False
        age_days = (datetime.now(timezone.utc) - self.last_accessed).total_seconds() / 86400
        effective = self.base_importance * math.exp(-self.decay_rate * age_days)
        return effective < self.EXPIRY_THRESHOLD

    def update_access(self):
        self.last_accessed = datetime.now(timezone.utc)

    def effective_importance(self) -> float:
        age_days = (datetime.now(timezone.utc) - self.last_accessed).total_seconds() / 86400
        return self.base_importance * math.exp(-self.decay_rate * age_days)


class UserProfile:
    def __init__(self):
        self.static: dict[str, ProfileTrait] = {}
        self.dynamic: dict[str, ProfileTrait] = {}

    def add_static(self, key: str, value: str, source: str = "explicit"):
        self.static[key] = ProfileTrait(
            key=key, value=value, source=source, is_static=True, decay_rate=0.0
        )

    def add_dynamic(self, key: str, value: str, source: str = "inferred"):
        self.dynamic[key] = ProfileTrait(
            key=key, value=value, source=source, is_static=False
        )

    def to_prompt(self) -> str:
        lines = ["## User Profile"]
        active_static = [t for t in self.static.values()]
        active_dynamic = [t for t in self.dynamic.values() if not t.is_expired()]
        if active_static:
            lines.append("")
            lines.append("### Stable Preferences")
            for t in active_static:
                lines.append(f"- **{t.key}**: {t.value}")
        if active_dynamic:
            lines.append("")
            lines.append("### Current Context")
            for t in active_dynamic:
                lines.append(f"- **{t.key}**: {t.value}")
        if not active_static and not active_dynamic:
            lines.append("")
            lines.append("(No profile data yet)")
        return "\n".join(lines)

    def from_memories(self, storage) -> int:
        memories = storage.get_all_memories_columns(
            columns=["id", "content", "category", "importance", "tags", "created_at"]
        )
        extracted = 0
        for mem in memories:
            tags = mem.tags if hasattr(mem, "tags") and mem.tags else []
            category = mem.category if hasattr(mem, "category") else ""
            importance = mem.importance if hasattr(mem, "importance") else 0.5
            content = mem.content if hasattr(mem, "content") else ""
            if not content:
                continue
            for pattern, trait_type in PREFERENCE_PATTERNS:
                match = pattern.search(content)
                if match:
                    key = match.group(1).strip().lower()
                    value = match.group(0)
                    if trait_type == "static":
                        self.add_static(key, value, source="inferred")
                    else:
                        self.add_dynamic(key, value, source="inferred")
                    extracted += 1
                    break
            tag_strs = tags if isinstance(tags, list) else []
            for tag in tag_strs:
                if tag.lower() in ("typescript", "python", "docker", "react", "rust",
                                    "kubernetes", "linux", "git"):
                    score = CATEGORY_WEIGHTS.get(category, 1.0) * importance
                    if score > 0.6:
                        self.add_static(tag.lower(), f"uses {tag}", source="inferred")
                        extracted += 1
                        break
        logger.info("from_memories extracted %d traits", extracted)
        return extracted

    def remove_expired(self) -> int:
        expired = [k for k, t in self.dynamic.items() if t.is_expired()]
        for k in expired:
            del self.dynamic[k]
        return len(expired)

    def touch(self, key: str) -> bool:
        if key in self.static:
            self.static[key].update_access()
            return True
        if key in self.dynamic:
            self.dynamic[key].update_access()
            return True
        return False