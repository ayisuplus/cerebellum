from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from evolver.memory import MemoryEngine

logger = logging.getLogger(__name__)

LIFECYCLE_DECAY_RATES = {
    "seed": 0.02,
    "growing": 0.01,
    "evergreen": 0.003,
    "stale": 0.05,
}

EXPIRY_THRESHOLD = 0.05


@dataclass
class TemporalEntry:
    memory_id: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decay_rate: float = 0.01
    base_importance: float = 1.0
    lifecycle: str = "seed"

    def is_expired(self) -> bool:
        if self.decay_rate <= 0:
            return False
        age_days = (datetime.now(timezone.utc) - self.last_accessed).total_seconds() / 86400
        effective = self.base_importance * math.exp(-self.decay_rate * age_days)
        return effective < EXPIRY_THRESHOLD

    def update_access(self):
        self.last_accessed = datetime.now(timezone.utc)

    def effective_importance(self) -> float:
        age_days = (datetime.now(timezone.utc) - self.last_accessed).total_seconds() / 86400
        return self.base_importance * math.exp(-self.decay_rate * age_days)


class TemporalMemory:
    def __init__(self):
        self._entries: dict[int, TemporalEntry] = {}
        self._lock = threading.Lock()

    def register(self, memory_id: int,
                 created_at: Optional[datetime] = None,
                 last_accessed: Optional[datetime] = None,
                 decay_rate: Optional[float] = None,
                 base_importance: float = 1.0,
                 lifecycle: str = "seed"):
        dr = decay_rate if decay_rate is not None else LIFECYCLE_DECAY_RATES.get(lifecycle, 0.01)
        now = datetime.now(timezone.utc)
        with self._lock:
            self._entries[memory_id] = TemporalEntry(
                memory_id=memory_id,
                created_at=created_at or now,
                last_accessed=last_accessed or now,
                decay_rate=dr,
                base_importance=base_importance,
                lifecycle=lifecycle,
            )

    def get(self, memory_id: int) -> Optional[TemporalEntry]:
        with self._lock:
            return self._entries.get(memory_id)

    def touch(self, memory_id: int) -> bool:
        with self._lock:
            entry = self._entries.get(memory_id)
            if entry is None:
                return False
            entry.update_access()
            return True

    def remove(self, memory_id: int) -> bool:
        with self._lock:
            if memory_id in self._entries:
                del self._entries[memory_id]
                return True
            return False

    def remove_expired(self) -> int:
        """Prune expired entries. Operator-invoked (no scheduler):
        call via Evolver.expire_stale_memories()."""
        with self._lock:
            # Snapshot the expired ids first: never delete while iterating.
            expired = [mid for mid, e in self._entries.items() if e.is_expired()]
            for mid in expired:
                del self._entries[mid]
            return len(expired)

    def apply_decay(self, storage):
        """Write decayed importance back to storage. Operator-invoked
        (no scheduler): call via Evolver.apply_temporal_decay().

        Batches the UPDATEs into a single executemany when the storage
        class provides the _executemany/_placeholder primitives
        (StorageBase and subclasses); otherwise falls back to per-row
        update_memory_importance calls.
        """
        with self._lock:
            pending = []
            for mid, entry in self._entries.items():
                eff = entry.effective_importance()
                if eff < entry.base_importance:
                    pending.append((mid, round(eff, 4)))
        if not pending:
            return
        executemany = getattr(type(storage), "_executemany", None)
        placeholder = getattr(type(storage), "_placeholder", None)
        if callable(executemany) and callable(placeholder):
            p = storage._placeholder()
            storage._executemany(
                f"UPDATE memories SET importance = {p}, "
                f"last_accessed_at = CURRENT_TIMESTAMP WHERE id = {p}",
                [(imp, mid) for mid, imp in pending],
            )
        else:
            for mid, imp in pending:
                storage.update_memory_importance(mid, imp)

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._entries)
            expired = sum(1 for e in self._entries.values() if e.is_expired())
            by_lifecycle = {}
            for e in self._entries.values():
                by_lifecycle[e.lifecycle] = by_lifecycle.get(e.lifecycle, 0) + 1
            return {"total": total, "expired": expired, "by_lifecycle": by_lifecycle}

    @staticmethod
    def _col(mem, name, default=None):
        """Read a column from a Memory dataclass or a dict-like row."""
        if hasattr(mem, name):
            return getattr(mem, name)
        if hasattr(mem, "get"):
            return mem.get(name, default)
        return default

    @staticmethod
    def _parse_dt(value) -> Optional[datetime]:
        if not value:
            return None
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            if isinstance(value, datetime):
                return value
        except (ValueError, TypeError):
            pass
        return None

    def sync_from_memories(self, storage):
        """Rebuild temporal entries from storage.

        Passes each memory's decay clock through as last_accessed
        (last_accessed_at when available, else updated_at, else created_at)
        instead of resetting the clock to now — Evolver re-syncs on every
        init, so resetting would mean restarted processes never decay.
        last_accessed_at is written only by decay checkpoints, so unrelated
        content/tag writes no longer erase accumulated decay time. Entries
        whose ids no longer exist in storage are pruned.
        """
        memories = storage.get_all_memories_columns(
            columns=["id", "importance", "created_at", "updated_at",
                     "last_accessed_at", "lifecycle", "category"]
        )
        storage_ids = set()
        for mem in memories:
            category = self._col(mem, "category")
            mid = self._col(mem, "id")
            if mid is not None:
                storage_ids.add(mid)
            # Cerebellum v2 keeps facts, failures-as-rules, anti-skills, and
            # published artifacts stable. Time decay is only an episodic
            # retrieval hint for raw success/failure interactions.
            if category not in {"success", "failure"}:
                continue
            importance = self._col(mem, "importance", 1.0)
            lifecycle = self._col(mem, "lifecycle", "seed")
            created_dt = self._parse_dt(self._col(mem, "created_at"))
            updated_dt = self._parse_dt(self._col(mem, "updated_at"))
            accessed_dt = self._parse_dt(self._col(mem, "last_accessed_at"))
            self.register(
                memory_id=mid,
                created_at=created_dt,
                last_accessed=accessed_dt or updated_dt or created_dt,
                base_importance=importance,
                lifecycle=lifecycle,
                decay_rate=LIFECYCLE_DECAY_RATES.get(lifecycle, 0.01),
            )
        with self._lock:
            stale = [mid for mid in self._entries if mid not in storage_ids]
            for mid in stale:
                del self._entries[mid]
            total = len(self._entries)
        logger.info(
            "sync_from_memories registered %d entries, pruned %d stale",
            total, len(stale),
        )
