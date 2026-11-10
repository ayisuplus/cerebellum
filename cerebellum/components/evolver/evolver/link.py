import logging
import numpy as np
from evolver.models import Link, RecallResult, GraphNode
from evolver.utils import embedder_identity_of, embedder_tags_compatible

logger = logging.getLogger(__name__)


class LinkEngine:
    _SIMILARITY_THRESHOLD = 0.6
    _MAX_LINKS_PER_MEMORY = 10
    # Cap candidates to keep search bounded even when ANN is not yet built
    _MAX_CANDIDATES = 500

    def __init__(self, storage, embedding, memory_engine, graph_engine):
        self._storage = storage
        self._embedding = embedding
        self._memory = memory_engine
        self._graph = graph_engine

    def auto_link_memory(self, memory_id: int, content: str):
        """Auto-infer bidirectional links for a newly stored memory."""
        sim_count = self._create_similarity_links(memory_id, content)
        ent_count = self._create_entity_links(memory_id, content)
        logger.info(
            "Auto-linked memory %d: %d similarity, %d entity links",
            memory_id, sim_count, ent_count,
        )

    def auto_link_batch(self, memory_ids: list[int], contents: list[str]):
        """Batch auto-link for multiple memories."""
        for mid, content in zip(memory_ids, contents):
            if content:
                self.auto_link_memory(mid, content)

    def backlinks(self, target_type: str, target_id: int) -> list[Link]:
        """Find all links pointing to a target."""
        return self._storage.get_backlinks(target_type, target_id)

    def outgoing(self, source_type: str, source_id: int) -> list[Link]:
        """Find all links originating from a source."""
        return self._storage.get_outgoing(source_type, source_id)

    def linked_memories(self, memory_id: int, top_k: int = 10) -> list[RecallResult]:
        """Get memories linked to a given memory."""
        links = self._storage.get_outgoing("memory", memory_id)
        memory_links = [link for link in links if link.target_type == "memory"][:top_k]
        if not memory_links:
            return []
        target_ids = [link.target_id for link in memory_links]
        weight_map = {link.target_id: link.weight for link in memory_links}
        memories = self._storage.get_memories_by_ids(target_ids)
        results = []
        for mem in memories:
            results.append(RecallResult(
                content=mem.content,
                score=round(weight_map.get(mem.id, 0.0), 4),
                source="link",
                category=mem.category,
                related_nodes=[],
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def linked_graph_nodes(self, memory_id: int) -> list[GraphNode]:
        """Get graph nodes linked to a memory."""
        links = self._storage.get_outgoing("memory", memory_id)
        node_links = [link for link in links if link.target_type == "graph_node"]
        if not node_links:
            return []
        nodes = []
        for link in node_links:
            node = self._storage.get_graph_node(link.target_id)
            if node is not None:
                nodes.append(node)
        return nodes

    def compute_link_score(self, memory_id: int,
                           query_related_ids: list[int]) -> float:
        """Compute link-based score for recall boost."""
        if not query_related_ids:
            return 0.0
        links = self._storage.get_outgoing("memory", memory_id)
        if not links:
            return 0.0
        linked_target_ids = {link.target_id for link in links}
        overlap = linked_target_ids & set(query_related_ids)
        if not overlap:
            return 0.0
        total_weight = sum(link.weight for link in links if link.target_id in overlap)
        max_weight = len(query_related_ids)
        return min(total_weight / max_weight, 1.0)

    def decay_links(self, factor: float = 0.95, min_weight: float = 0.01):
        """Decay link weights over time."""
        self._storage.decay_links(factor=factor, min_weight=min_weight)

    # --- Internal ---

    def _create_similarity_links(self, memory_id: int, content: str) -> int:
        """Find similar memories via ANN (if available) or sampled brute-force.

        Strategy:
        1. If ANN index is built: use ANN search O(log n) to find candidates.
        2. Otherwise: sample up to _MAX_CANDIDATES recent memories for brute-force.
        Then score candidates, create links for those above similarity threshold.
        """
        query_vec = np.array(self._embedding.embed_single(content))

        # Path 1: ANN — fast O(log n) lookup
        if self._memory.ann_ready:
            ann_results = self._memory.search_similar(query_vec, top_k=self._MAX_LINKS_PER_MEMORY + 5)
            # Filter out self-reference and convert distance → similarity
            candidates = []
            for mid, dist in ann_results:
                if mid == memory_id:
                    continue
                sim = max(0.0, 1.0 - dist)  # hnswlib cosine distance
                if sim >= self._SIMILARITY_THRESHOLD:
                    candidates.append((mid, sim))
                if len(candidates) >= self._MAX_LINKS_PER_MEMORY:
                    break
            logger.debug("ANN found %d similar candidates for memory %d", len(candidates), memory_id)

        else:
            # Path 2: Sampled brute-force — O(k) where k = min(n, MAX_CANDIDATES)
            all_mems = self._storage.get_all_memories_with_embeddings(max_scan=self._MAX_CANDIDATES)
            candidates = []
            for mem in all_mems:
                if mem.id == memory_id or mem.embedding is None:
                    continue
                if not embedder_tags_compatible(mem.embedder, embedder_identity_of(self._embedding)):
                    continue
                mem_vec = np.array(self._embedding.bytes_to_vector(mem.embedding))
                dot = np.dot(query_vec, mem_vec)
                norm = np.linalg.norm(query_vec) * np.linalg.norm(mem_vec)
                sim = float(dot / norm) if norm > 0 else 0.0
                if sim >= self._SIMILARITY_THRESHOLD:
                    candidates.append((mem.id, sim))
                    if len(candidates) >= self._MAX_LINKS_PER_MEMORY:
                        break
            # Sort by similarity descending, take top _MAX_LINKS_PER_MEMORY
            candidates.sort(key=lambda x: x[1], reverse=True)
            candidates = candidates[:self._MAX_LINKS_PER_MEMORY]
            logger.debug("Sampled brute-force found %d candidates for memory %d", len(candidates), memory_id)

        # Store bidirectional links (batch)
        if candidates:
            links = []
            for target_id, sim in candidates:
                links.append(("memory", memory_id, "memory", target_id, "auto_similar", sim))
                links.append(("memory", target_id, "memory", memory_id, "auto_similar", sim))
            count = self._storage.insert_links_batch(links) // 2
            return count
        return 0

    def _create_entity_links(self, memory_id: int, content: str) -> int:
        """Extract entities and link to matching graph nodes (batch lookup)."""
        entities = self._graph._extract_entities(content)
        if not entities:
            return 0
        # Single batch query instead of per-entity LIKE scan
        nodes = self._storage.get_nodes_by_labels(entities)
        label_to_nodes: dict[str, list] = {}
        for node in nodes:
            label_to_nodes.setdefault(node.label.lower(), []).append(node)
        count = 0
        for entity in entities:
            for node in label_to_nodes.get(entity.lower(), []):
                self._storage.insert_link("memory", memory_id,
                                          "graph_node", node.id,
                                          "auto_entity", 1.0)
                count += 1
        return count
