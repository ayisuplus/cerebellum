from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class RecallResult:
    content: str
    score: float
    source: str
    category: str
    related_nodes: list = field(default_factory=list)
    snippet: str = ""
    lifecycle: str = "seed"
    created_at: Optional[str] = None


@dataclass
class SkillResult:
    name: str
    path: str
    content: str
    version: int


@dataclass
class Memory:
    content: str
    category: str
    tags: list = field(default_factory=list)
    embedding: Optional[list] = None
    source: Optional[str] = None
    importance: float = 0.5
    access_count: int = 0
    content_hash: Optional[str] = None
    lifecycle: str = "seed"  # seed | growing | evergreen | stale | distilled
    id: Optional[int] = None
    created_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
    # Embedder identity tag (e.g. "fastembed:BAAI/bge-small-en-v1.5",
    # "hash-fallback:v2"); None = written before tagging existed.
    embedder: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "tags": json.dumps(self.tags),
            "embedding": self.embedding,
            "source": self.source,
            "importance": self.importance,
            "access_count": self.access_count,
            "lifecycle": self.lifecycle,
            "created_at": self.created_at,
        }


@dataclass
class GraphNode:
    label: str
    node_type: str
    properties: Optional[dict] = None
    id: Optional[int] = None


@dataclass
class GraphEdge:
    source_id: int
    target_id: int
    relation: str
    weight: float = 1.0
    properties: Optional[dict] = None
    id: Optional[int] = None


@dataclass
class Link:
    id: Optional[int] = None
    source_type: str = ""
    source_id: int = 0
    target_type: str = ""
    target_id: int = 0
    link_type: str = "auto_similar"
    weight: float = 1.0


@dataclass
class EvalResult:
    total_score: float = 0.0
    dim_scores: dict = field(default_factory=dict)
    round: int = 1
    status: str = "pass"


@dataclass
class Fact:
    fact: str
    tags: list = field(default_factory=list)
    time: Optional[str] = None
    session_id: Optional[str] = None
    id: Optional[int] = None
