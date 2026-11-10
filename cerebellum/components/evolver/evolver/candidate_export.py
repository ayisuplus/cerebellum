"""Stable CandidateExport v1 boundary for external consumers.

The export deliberately contains no storage URLs, embeddings, graph internals,
or table-specific fields. Consumers must treat every item as quarantined input.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


SCHEMA_VERSION = "cerebellum/v1"


def build_candidate_export(storage, *, producer: str,
                           limit: int = 1000,
                           categories: Optional[Iterable[str]] = None) -> dict:
    """Build a storage-independent CandidateExport dictionary."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    allowed = {value for value in (categories or []) if value}
    memories = storage.get_all_memories_columns()
    candidates = []
    for memory in memories:
        if allowed and memory.category not in allowed:
            continue
        content = (memory.content or "").strip()
        if not content:
            continue
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        tags = memory.tags if isinstance(memory.tags, list) else []
        candidates.append({
            "candidate_id": f"memory:{memory.id if memory.id is not None else content_hash[:16]}",
            "kind": "memory",
            "content": content,
            "category": memory.category or "",
            "tags": tags,
            "source": memory.source,
            "evidence": {
                "importance": float(memory.importance),
                "access_count": int(memory.access_count),
                "lifecycle": memory.lifecycle,
                "created_at": memory.created_at,
            },
            "content_hash": content_hash,
        })
        if len(candidates) >= limit:
            break
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "producer": producer,
        "candidates": candidates,
    }


def write_candidate_export(export: dict, path: str | Path) -> Path:
    """Atomically write a CandidateExport JSON document."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(export, ensure_ascii=False, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return target

