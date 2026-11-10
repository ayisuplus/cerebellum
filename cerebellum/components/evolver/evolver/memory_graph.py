from dataclasses import dataclass
from typing import Optional
import json
import logging
import random
import math

logger = logging.getLogger(__name__)


@dataclass
class MemoryNode:
    id: int
    label: str
    node_type: str
    importance: float
    properties: Optional[dict] = None
    category: Optional[str] = None
    lifecycle: Optional[str] = None
    x: float = 0
    y: float = 0


@dataclass
class DocNode:
    id: int
    label: str
    node_type: str
    properties: Optional[dict] = None
    x: float = 0
    y: float = 0


@dataclass
class VisEdge:
    source: int
    target: int
    edge_type: str
    weight: float = 1.0


class MemoryGraph:
    def __init__(self, storage, embedding=None):
        self._storage = storage
        self._embedding = embedding

    def build(self) -> dict:
        memories = self._storage.get_all_memories_with_embeddings()
        graph_nodes = self._storage.query_nodes("")

        memory_prefixes = {}
        for mem in memories:
            if mem.content:
                prefix = mem.content[:50]
                memory_prefixes[prefix] = mem.id

        nodes = []
        for mem in memories:
            nodes.append(MemoryNode(
                id=mem.id,
                label=mem.content,
                node_type="memory",
                properties=None,
                importance=mem.importance,
                category=mem.category,
                lifecycle=mem.lifecycle,
            ))

        for gn in graph_nodes:
            if gn.label:
                prefix = gn.label[:50]
                if prefix in memory_prefixes:
                    continue
            nodes.append(DocNode(
                id=gn.id,
                label=gn.label,
                node_type="document",
                properties=gn.properties,
            ))

        edges = []

        graph_edges = self._storage._fetchall(
            "SELECT source_id, target_id, relation, weight FROM graph_edges"
        )
        for ge in graph_edges:
            edges.append(VisEdge(
                source=ge["source_id"],
                target=ge["target_id"],
                edge_type="reference",
                weight=ge["weight"],
            ))

        links = self._storage._fetchall(
            "SELECT source_id, target_id, link_type, weight FROM links WHERE link_type = 'auto_similar'"
        )
        for lnk in links:
            edges.append(VisEdge(
                source=lnk["source_id"],
                target=lnk["target_id"],
                edge_type="similarity",
                weight=lnk["weight"],
            ))

        hash_groups = {}
        for mem in memories:
            if mem.content_hash:
                hash_groups.setdefault(mem.content_hash, []).append(mem)

        for content_hash, group in hash_groups.items():
            if len(group) < 2:
                continue
            sorted_group = sorted(group, key=lambda m: m.created_at or "")
            for i in range(len(sorted_group) - 1):
                edges.append(VisEdge(
                    source=sorted_group[i].id,
                    target=sorted_group[i + 1].id,
                    edge_type="version_chain",
                    weight=1.0,
                ))

        edges = self._dedup_edges(edges)

        return {"nodes": nodes, "edges": edges}

    def _dedup_edges(self, edges):
        edge_map = {}
        for e in edges:
            key = (e.source, e.target, e.edge_type)
            if key not in edge_map or e.weight > edge_map[key].weight:
                edge_map[key] = e
        return list(edge_map.values())

    def layout(self, iterations: int = 50, width: float = 800.0, height: float = 600.0) -> dict:
        data = self.build()
        nodes = data["nodes"]
        edges = data["edges"]

        if not nodes:
            return {"nodes": [], "edges": []}

        margin = 30
        k_rep = 500
        k_attr = 0.05
        rest_len = 80
        damping = 0.85

        for node in nodes:
            node.x = random.uniform(margin, width - margin)
            node.y = random.uniform(margin, height - margin)

        node_map = {n.id: n for n in nodes}

        for _ in range(iterations):
            forces = {n.id: [0.0, 0.0] for n in nodes}

            for i, n1 in enumerate(nodes):
                for n2 in nodes[i + 1:]:
                    dx = n1.x - n2.x
                    dy = n1.y - n2.y
                    dist = math.sqrt(dx * dx + dy * dy) or 1
                    force = k_rep / (dist * dist)
                    fx = force * dx / dist
                    fy = force * dy / dist
                    forces[n1.id][0] += fx
                    forces[n1.id][1] += fy
                    forces[n2.id][0] -= fx
                    forces[n2.id][1] -= fy

            for edge in edges:
                src = node_map.get(edge.source)
                tgt = node_map.get(edge.target)
                if not src or not tgt:
                    continue
                dx = src.x - tgt.x
                dy = src.y - tgt.y
                dist = math.sqrt(dx * dx + dy * dy) or 1
                force = k_attr * (dist - rest_len)
                fx = force * dx / dist
                fy = force * dy / dist
                forces[src.id][0] -= fx
                forces[src.id][1] -= fy
                forces[tgt.id][0] += fx
                forces[tgt.id][1] += fy

            for node in nodes:
                vx, vy = forces[node.id]
                vx *= damping
                vy *= damping
                node.x = max(margin, min(width - margin, node.x + vx))
                node.y = max(margin, min(height - margin, node.y + vy))

        return {"nodes": nodes, "edges": edges}

    def to_json(self, iterations: int = 50, width: float = 800.0, height: float = 600.0) -> str:
        data = self.layout(iterations=iterations, width=width, height=height)
        result = {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "node_type": n.node_type,
                    "importance": getattr(n, "importance", None),
                    "category": getattr(n, "category", None),
                    "lifecycle": getattr(n, "lifecycle", None),
                    "x": n.x,
                    "y": n.y,
                }
                for n in data["nodes"]
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type,
                    "weight": e.weight,
                }
                for e in data["edges"]
            ],
            "meta": {
                "node_count": len(data["nodes"]),
                "edge_count": len(data["edges"]),
                "layout_iterations": iterations,
            },
        }
        return json.dumps(result)

    def to_dict(self, iterations: int = 50, width: float = 800.0, height: float = 600.0) -> dict:
        data = self.layout(iterations=iterations, width=width, height=height)
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "node_type": n.node_type,
                    "importance": getattr(n, "importance", None),
                    "category": getattr(n, "category", None),
                    "lifecycle": getattr(n, "lifecycle", None),
                    "x": n.x,
                    "y": n.y,
                }
                for n in data["nodes"]
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type,
                    "weight": e.weight,
                }
                for e in data["edges"]
            ],
            "meta": {
                "node_count": len(data["nodes"]),
                "edge_count": len(data["edges"]),
                "layout_iterations": iterations,
            },
        }
