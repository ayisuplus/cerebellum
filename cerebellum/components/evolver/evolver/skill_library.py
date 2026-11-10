"""Evolver Skill Library - manages generated skills with deduplication and evolution."""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from evolver.utils import cosine_similarity, tokenize

logger = logging.getLogger(__name__)


class SkillLibrary:
    """Manages evolver-generated skills with deduplication and evolution."""

    def __init__(self, library_path: str = "./evolver-skills",
                 embedding_client=None, similarity_threshold: float = 0.85):
        self._library_path = Path(library_path)
        self._skills_dir = self._library_path / "skills"
        self._metadata_dir = self._library_path / "metadata"
        self._index_path = self._library_path / "index.json"
        self._embedding = embedding_client
        self._threshold = similarity_threshold
        self._lock = threading.Lock()

        # Ensure directories exist
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_dir.mkdir(parents=True, exist_ok=True)

        # Load or create index
        self._index = self._load_index()

    def _load_index(self) -> dict:
        """Load skill index from disk."""
        if self._index_path.exists():
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load skill index: %s", e)

        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "skills": []
        }

    def _save_index(self):
        """Save skill index to disk."""
        try:
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save skill index: %s", e)

    def find_similar_skill(self, topic: str, content: str = "") -> Optional[dict]:
        """Find similar skill in library using embedding similarity.

        Args:
            topic: Skill topic to search for.
            content: Optional skill content for better matching.

        Returns:
            Similar skill metadata or None if no similar skill found.
        """
        if not self._embedding:
            # Fallback: use keyword matching
            return self._find_by_keywords(topic)

        # Use embedding similarity
        query_text = f"{topic} {content}" if content else topic
        query_vec = self._embedding.embed_single(query_text)

        best_match = None
        best_similarity = 0.0

        for skill_meta in self._index.get("skills", []):
            skill_embedding = skill_meta.get("embedding")
            if not skill_embedding:
                continue

            # Calculate cosine similarity
            similarity = cosine_similarity(query_vec, skill_embedding)
            if similarity > best_similarity and similarity >= self._threshold:
                best_similarity = similarity
                best_match = skill_meta

        if best_match:
            logger.info("Found similar skill '%s' (similarity=%.3f)",
                       best_match.get("name"), best_similarity)
            return best_match

        return None

    def _find_by_keywords(self, topic: str) -> Optional[dict]:
        """Fallback: find skill by keyword matching."""
        topic_keywords = set(tokenize(topic))

        best_match = None
        best_overlap = 0

        for skill_meta in self._index.get("skills", []):
            skill_keywords = set(skill_meta.get("keywords", []))
            overlap = len(topic_keywords & skill_keywords)
            if overlap > best_overlap and overlap >= 2:
                best_overlap = overlap
                best_match = skill_meta

        return best_match

    def add_skill(self, name: str, description: str, content: str,
                  topic: str, version: int = 1,
                  memories_used: int = 0, graph_nodes_used: int = 0,
                  source: str = "evolver") -> dict:
        """Add a new skill to the library.

        Args:
            name: Skill name (will be prefixed with 'evolver-').
            description: Skill description.
            content: Full skill content (markdown).
            topic: Original topic.
            version: Skill version.
            memories_used: Number of memories used to generate.
            graph_nodes_used: Number of graph nodes used.
            source: Source identifier.

        Returns:
            Skill metadata dict.
        """
        # Add evolver prefix if not already present
        if not name.startswith("evolver-"):
            prefixed_name = f"evolver-{name}"
        else:
            prefixed_name = name

        # Generate embedding for deduplication
        embedding = None
        if self._embedding:
            try:
                embedding = self._embedding.embed_single(f"{topic} {description}")
            except Exception as e:
                logger.warning("Failed to generate embedding: %s", e)

        # Extract keywords
        keywords = tokenize(f"{topic} {description}")

        # Create metadata
        metadata = {
            "name": prefixed_name,
            "original_name": name,
            "description": description,
            "topic": topic,
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "memories_used": memories_used,
            "graph_nodes_used": graph_nodes_used,
            "source": source,
            "keywords": keywords,
            "embedding": embedding,
        }

        # Save skill content
        skill_path = self._skills_dir / f"{prefixed_name}.md"
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Save metadata
        meta_path = self._metadata_dir / f"{prefixed_name}.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # Update index
        with self._lock:
            self._index["skills"].append(metadata)
            self._save_index()

        logger.info("Added skill '%s' to library (v%d)", prefixed_name, version)
        return metadata

    def update_skill(self, name: str, content: str, description: str = None,
                     memories_used: int = 0, graph_nodes_used: int = 0) -> Optional[dict]:
        """Update an existing skill in the library.

        Args:
            name: Skill name (with evolver prefix).
            content: New skill content.
            description: Optional new description.
            memories_used: Additional memories used.
            graph_nodes_used: Additional graph nodes used.

        Returns:
            Updated skill metadata or None if not found.
        """
        # Find skill in index
        skill_meta = None
        for meta in self._index.get("skills", []):
            if meta.get("name") == name:
                skill_meta = meta
                break

        if not skill_meta:
            logger.warning("Skill '%s' not found in library", name)
            return None

        # Update version
        new_version = skill_meta.get("version", 1) + 1

        # Update metadata
        skill_meta["version"] = new_version
        skill_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        skill_meta["memories_used"] = skill_meta.get("memories_used", 0) + memories_used
        skill_meta["graph_nodes_used"] = skill_meta.get("graph_nodes_used", 0) + graph_nodes_used

        if description:
            skill_meta["description"] = description

        # Update embedding if available
        if self._embedding:
            try:
                topic = skill_meta.get("topic", "")
                skill_meta["embedding"] = self._embedding.embed_single(
                    f"{topic} {description or skill_meta.get('description', '')}"
                )
            except Exception as e:
                logger.warning("Failed to update embedding: %s", e)

        # Save updated skill content
        skill_path = self._skills_dir / f"{name}.md"
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Save updated metadata
        meta_path = self._metadata_dir / f"{name}.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(skill_meta, f, ensure_ascii=False, indent=2)

        # Save index
        with self._lock:
            self._save_index()

        logger.info("Updated skill '%s' to v%d", name, new_version)
        return skill_meta

    def get_skill(self, name: str) -> Optional[dict]:
        """Get skill metadata by name."""
        for meta in self._index.get("skills", []):
            if meta.get("name") == name:
                return meta
        return None

    def get_skill_content(self, name: str) -> Optional[str]:
        """Get skill content by name."""
        skill_path = self._skills_dir / f"{name}.md"
        if skill_path.exists():
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def list_skills(self) -> list[dict]:
        """List all skills in the library."""
        return self._index.get("skills", [])

    def search_skills(self, query: str, top_k: int = 5) -> list[dict]:
        """Search skills by query.

        Args:
            query: Search query.
            top_k: Number of results to return.

        Returns:
            List of matching skill metadata.
        """
        if not self._embedding:
            # Fallback: keyword search
            return self._search_by_keywords(query, top_k)

        # Use embedding similarity
        query_vec = self._embedding.embed_single(query)

        scored_skills = []
        for skill_meta in self._index.get("skills", []):
            skill_embedding = skill_meta.get("embedding")
            if not skill_embedding:
                continue

            similarity = cosine_similarity(query_vec, skill_embedding)
            scored_skills.append((similarity, skill_meta))

        # Sort by similarity
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored_skills[:top_k]]

    def _search_by_keywords(self, query: str, top_k: int) -> list[dict]:
        """Fallback: search by keywords."""
        query_keywords = set(tokenize(query))

        scored_skills = []
        for skill_meta in self._index.get("skills", []):
            skill_keywords = set(skill_meta.get("keywords", []))
            overlap = len(query_keywords & skill_keywords)
            if overlap > 0:
                scored_skills.append((overlap, skill_meta))

        # Sort by overlap
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored_skills[:top_k]]


class SkillIndex:
    """Library index for skills with deduplication and evolution.

    Same on-disk layout as SkillLibrary (./skills + ./metadata + index.json)
    but with an explicit ``upsert_skill(name, description, file_path, content)``
    entry point that the SkillEngine orchestrator calls.
    """

    def __init__(self, library_path: str = "./evolver-skills",
                 embedding_client=None, similarity_threshold: float = 0.85):
        self._library_path = Path(library_path)
        self._skills_dir = self._library_path / "skills"
        self._metadata_dir = self._library_path / "metadata"
        self._index_path = self._library_path / "index.json"
        self._embedding = embedding_client
        self._threshold = similarity_threshold
        self._lock = threading.Lock()

        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_dir.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()

    def _load_index(self) -> dict:
        if self._index_path.exists():
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load skill index: %s", e)
        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "skills": [],
        }

    def _save_index(self):
        try:
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save skill index: %s", e)

    def find_similar_skill(self, topic: str, content: str = "") -> Optional[dict]:
        if not self._embedding:
            return self._find_by_keywords(topic)
        query_text = f"{topic} {content}" if content else topic
        query_vec = self._embedding.embed_single(query_text)
        best_match, best_similarity = None, 0.0
        for skill_meta in self._index.get("skills", []):
            skill_embedding = skill_meta.get("embedding")
            if not skill_embedding:
                continue
            similarity = cosine_similarity(query_vec, skill_embedding)
            if similarity > best_similarity and similarity >= self._threshold:
                best_similarity = similarity
                best_match = skill_meta
        if best_match:
            logger.info("Found similar skill '%s' (similarity=%.3f)",
                        best_match.get("name"), best_similarity)
            return best_match
        return None

    def _find_by_keywords(self, topic: str) -> Optional[dict]:
        topic_keywords = set(tokenize(topic))
        best_match, best_overlap = None, 0
        for skill_meta in self._index.get("skills", []):
            skill_keywords = set(skill_meta.get("keywords", []))
            overlap = len(topic_keywords & skill_keywords)
            if overlap > best_overlap and overlap >= 2:
                best_overlap = overlap
                best_match = skill_meta
        return best_match

    def add_skill(self, name: str, description: str, content: str,
                  topic: str, version: int = 1,
                  memories_used: int = 0, graph_nodes_used: int = 0,
                  source: str = "evolver") -> dict:
        prefixed_name = name if name.startswith("evolver-") else f"evolver-{name}"
        embedding = None
        if self._embedding:
            try:
                embedding = self._embedding.embed_single(
                    f"{topic} {description}")
            except Exception as e:
                logger.warning("Failed to generate embedding: %s", e)
        keywords = tokenize(f"{topic} {description}")
        metadata = {
            "name": prefixed_name, "original_name": name,
            "description": description, "topic": topic, "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "memories_used": memories_used,
            "graph_nodes_used": graph_nodes_used, "source": source,
            "keywords": keywords, "embedding": embedding,
        }
        with open(self._skills_dir / f"{prefixed_name}.md", "w",
                  encoding="utf-8") as f:
            f.write(content)
        with open(self._metadata_dir / f"{prefixed_name}.json", "w",
                  encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        with self._lock:
            self._index["skills"].append(metadata)
            self._save_index()
        logger.info("Added skill '%s' to library (v%d)", prefixed_name, version)
        return metadata

    def update_skill(self, name: str, content: str, description: str = None,
                     memories_used: int = 0, graph_nodes_used: int = 0
                     ) -> Optional[dict]:
        skill_meta = None
        for meta in self._index.get("skills", []):
            if meta.get("name") == name:
                skill_meta = meta
                break
        if not skill_meta:
            logger.warning("Skill '%s' not found in library", name)
            return None
        skill_meta["version"] = skill_meta.get("version", 1) + 1
        skill_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        skill_meta["memories_used"] = (
            skill_meta.get("memories_used", 0) + memories_used)
        skill_meta["graph_nodes_used"] = (
            skill_meta.get("graph_nodes_used", 0) + graph_nodes_used)
        if description:
            skill_meta["description"] = description
        if self._embedding:
            try:
                topic = skill_meta.get("topic", "")
                skill_meta["embedding"] = self._embedding.embed_single(
                    f"{topic} {description or skill_meta.get('description', '')}")
            except Exception as e:
                logger.warning("Failed to update embedding: %s", e)
        with open(self._skills_dir / f"{name}.md", "w", encoding="utf-8") as f:
            f.write(content)
        with open(self._metadata_dir / f"{name}.json", "w",
                  encoding="utf-8") as f:
            json.dump(skill_meta, f, ensure_ascii=False, indent=2)
        with self._lock:
            self._save_index()
        logger.info("Updated skill '%s' to v%d", name, skill_meta["version"])
        return skill_meta

    def upsert_skill(self, name: str, description: str,
                     file_path: str, content: str) -> tuple[int, int]:
        """Index-side upsert: return (skill_id, version).

        Calls find_similar_skill and either evolves the match (returns its
        id and incremented version) or adds a new skill and returns the new
        id and version 1. The caller persists the storage row separately.
        """
        existing = self.find_similar_skill(name, content)
        if existing:
            updated = self.update_skill(
                existing["name"], content,
                description=description,
            )
            return (id(existing), updated["version"])
        meta = self.add_skill(
            name=name, description=description,
            content=content, topic=name,
        )
        return (id(meta), meta["version"])

    def get_skill(self, name: str) -> Optional[dict]:
        for meta in self._index.get("skills", []):
            if meta.get("name") == name:
                return meta
        return None

    def get_skill_content(self, name: str) -> Optional[str]:
        skill_path = self._skills_dir / f"{name}.md"
        if skill_path.exists():
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def list_skills(self) -> list[dict]:
        return self._index.get("skills", [])

    def search_skills(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._embedding:
            return self._search_by_keywords(query, top_k)
        query_vec = self._embedding.embed_single(query)
        scored = []
        for skill_meta in self._index.get("skills", []):
            skill_embedding = skill_meta.get("embedding")
            if not skill_embedding:
                continue
            similarity = cosine_similarity(query_vec, skill_embedding)
            scored.append((similarity, skill_meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored[:top_k]]

    def _search_by_keywords(self, query: str, top_k: int) -> list[dict]:
        query_keywords = set(tokenize(query))
        scored = []
        for skill_meta in self._index.get("skills", []):
            skill_keywords = set(skill_meta.get("keywords", []))
            overlap = len(query_keywords & skill_keywords)
            if overlap > 0:
                scored.append((overlap, skill_meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored[:top_k]]
