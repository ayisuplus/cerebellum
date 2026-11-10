import re
import logging

from evolver.models import GraphNode, GraphEdge
from evolver.stopwords import STOPWORDS, TOOL_KEYWORDS, TECHNIQUE_KEYWORDS
from evolver.utils import extract_json_from_llm, tokenize

logger = logging.getLogger(__name__)

ENTITY_EXTRACTION_PROMPTS = {
    "zh": (
        "从以下文本中提取实体和关系。返回纯 JSON：\n"
        '{"entities": [{"name": "实体名", "type": "person|tool|concept|file|api|technique", '
        '"description": "简述"}], '
        '"relations": [{"source": "实体A", "target": "实体B", '
        '"relation": "uses|creates|depends_on|implements|triggers|related_to"}]}\n\n'
        "只返回 JSON，不要其他内容。如果没有实体，返回 {\"entities\": [], \"relations\": []}"
    ),
    "en": (
        "Extract entities and relations from this text. Return pure JSON:\n"
        '{"entities": [{"name": "entity name", "type": "person|tool|concept|file|api|technique", '
        '"description": "brief description"}], '
        '"relations": [{"source": "entity A", "target": "entity B", '
        '"relation": "uses|creates|depends_on|implements|triggers|related_to"}]}\n\n'
        "Return JSON only, no other content. If no entities, return {\"entities\": [], \"relations\": []}"
    ),
}


class GraphEngine:
    _MAX_ENTITIES = 15

    def __init__(self, storage, llm_client=None, lang: str = "zh"):
        self._storage = storage
        self._llm = llm_client
        self._lang = lang

    def add_node(self, label: str, node_type: str = "concept",
                 properties: dict = None) -> int:
        node = GraphNode(label=label, node_type=node_type, properties=properties)
        return self._storage.upsert_node(node)

    def add_edge(self, source_label: str, target_label: str,
                 relation: str = "related_to", weight: float = 1.0) -> int:
        source_id = self.add_node(source_label, self._infer_type(source_label))
        target_id = self.add_node(target_label, self._infer_type(target_label))
        edge = GraphEdge(source_id=source_id, target_id=target_id,
                         relation=relation, weight=weight)
        return self._storage.upsert_edge(edge)

    def query(self, label: str, relation: str = None) -> list[GraphNode]:
        return self._storage.query_nodes(label, relation)

    def get_neighbors(self, node_id: int, hops: int = 1) -> list[GraphNode]:
        return self._storage.get_neighbors(node_id, hops)

    def build_from_text(self, text: str) -> list[int]:
        """Extract entities from text and build graph relations.

        Uses LLM if available, falls back to regex extraction.
        """
        if not text.strip():
            return []

        # Try LLM extraction first
        if self._llm and self._llm.available:
            try:
                return self._build_with_llm(text)
            except Exception as e:
                logger.warning("LLM entity extraction failed, falling back to regex: %s", e)

        # Fallback: regex extraction
        return self._build_with_regex(text)

    def _build_with_llm(self, text: str) -> list[int]:
        """LLM-driven entity and relation extraction."""
        prompt = ENTITY_EXTRACTION_PROMPTS.get(self._lang, ENTITY_EXTRACTION_PROMPTS["en"])

        result = self._llm.call_llm(text, prompt, max_tokens=1500)
        result = self._llm.extract_final_answer(result)
        parsed = extract_json_from_llm(result) or {}

        entities = parsed.get("entities", [])
        relations = parsed.get("relations", [])

        node_ids = []
        node_id_map = {}  # name -> node_id

        # Create nodes
        for entity in entities:
            name = entity.get("name", "").strip()
            if not name:
                continue
            etype = entity.get("type", "concept")
            desc = entity.get("description", "")
            properties = {"description": desc} if desc else None
            nid = self.add_node(name, etype, properties)
            node_ids.append(nid)
            node_id_map[name.lower()] = nid

        # Create edges
        for rel in relations:
            source = rel.get("source", "").strip()
            target = rel.get("target", "").strip()
            relation = rel.get("relation", "related_to")

            if not source or not target:
                continue

            # Get or create nodes for relation endpoints
            source_id = node_id_map.get(source.lower())
            if source_id is None:
                source_id = self.add_node(source, self._infer_type(source))
                node_id_map[source.lower()] = source_id

            target_id = node_id_map.get(target.lower())
            if target_id is None:
                target_id = self.add_node(target, self._infer_type(target))
                node_id_map[target.lower()] = target_id

            self._storage.upsert_edge(
                GraphEdge(source_id=source_id, target_id=target_id, relation=relation)
            )

        return node_ids

    def _build_with_regex(self, text: str) -> list[int]:
        """Regex-based entity extraction (legacy fallback)."""
        tokens = self._extract_entities(text)
        node_ids = []

        for token in tokens:
            node_type = self._infer_type(token)
            nid = self.add_node(token, node_type)
            node_ids.append(nid)

        # Build relations between consecutive entities
        for i in range(len(node_ids) - 1):
            self._storage.upsert_edge(
                GraphEdge(
                    source_id=node_ids[i], target_id=node_ids[i + 1],
                    relation="related_to",
                )
            )

        return node_ids

    def _extract_entities(self, text: str) -> list[str]:
        """Extract potential entity labels from text (regex-based).

        Uses shared tokenizer for base extraction, adds camelCase/snake_case
        splitting on top for code artifacts.
        """
        # Pre-process: split camelCase and snake_case for code artifacts
        processed = re.sub(r'([a-z])([A-Z])', r'\1_\2', text)
        processed = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', processed)

        return tokenize(processed, min_len=2, stopwords=STOPWORDS,
                       max_items=self._MAX_ENTITIES,
                       english_pattern=r'[a-zA-Z][a-zA-Z0-9_]{1,}')

    def _infer_type(self, label: str) -> str:
        label_lower = label.lower()
        if label_lower in TOOL_KEYWORDS:
            return "tool"
        if label_lower in TECHNIQUE_KEYWORDS:
            return "technique"
        # Heuristic: if it looks like a code artifact (has dots, slashes, or underscores)
        if re.search(r'[./\\_]', label) or re.match(r'^[A-Z][a-z]+[A-Z]', label):
            return "artifact"
        return "concept"

    def decay_edges(self, factor: float = 0.9, min_weight: float = 0.01):
        """Decay all edge weights, removing edges that fall below min_weight.

        Args:
            factor: Multiplicative decay (e.g. 0.9 = 10% decay).
            min_weight: Edges below this threshold are removed.
        """
        self._storage.decay_edges(factor=factor, min_weight=min_weight)


