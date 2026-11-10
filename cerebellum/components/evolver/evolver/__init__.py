"""Evolver: Agent self-evolution engine."""

from __future__ import annotations

__version__ = "2.3.0"

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

# Imports required by Evolver class internals
from evolver.config import EvolverConfig, RerankerConfig, LifecycleRule, DEFAULT_LIFECYCLE_RULES
from evolver.storage_sqlite import SQLiteStorage
from evolver.embedding import EmbeddingClient
from evolver.llm_client import LLMClient
from evolver.compiler import MemoryCompiler
from evolver.extraction import MemoryExtractor
from evolver.dedup import Deduplicator
from evolver.closet import ClosetIndex
from evolver.stack import MemoryStack
from evolver.memory import MemoryEngine
from evolver.graph import GraphEngine
from evolver.memory_graph import MemoryGraph
from evolver.skill import SkillEngine
from evolver.skill_library import SkillLibrary
from evolver.link import LinkEngine
from evolver.checker import QualityChecker
from evolver.user_profile import UserProfile
from evolver.hybrid_search import HybridSearch
from evolver.temporal_memory import TemporalMemory
from evolver.exceptions import EvolverError, EvolverConnectionError, EmbeddingError, NotionConnectorError

try:
    import pymysql
except ImportError:
    pymysql = None

if pymysql:
    from evolver.storage import MySQLStorage
else:
    MySQLStorage = None

logger = logging.getLogger(__name__)


def _archive_not_configured_msg() -> str:
    """Return a clear, OS-agnostic error message for unconfigured archive layer."""
    return (
        "EVOLVER_DATA_URL is not configured.\n\n"
        "Please configure a MySQL URL:\n"
        "  Bash:       export EVOLVER_DATA_URL='mysql://user:pass@host:3306/evolver_archive'\n"
        "  PowerShell: $env:EVOLVER_DATA_URL='mysql://user:pass@host:3306/evolver_archive'\n\n"
        "Or pass data_url= when constructing Evolver(...).\n"
        "Add to ~/.bashrc (Bash) or $PROFILE (PowerShell) for permanent configuration."
    )


class Evolver:
    """Main facade for the evolver engine.

    Usage::

        # SQLite (zero-config, great for dev)
        evolver = Evolver(db_url="sqlite:///evolver.db")

        # MySQL (production)
        evolver = Evolver(db_url="mysql://user:pass@localhost:3306/evolver")

        evolver.learn(task="fix bug", outcome="success", solution="...")
        results = evolver.recall("git merge conflict")
        skill = evolver.skillgen("git workflow")
        evolver.close()
    """

    def __init__(self, mysql_url: str = None, db_url: str = None,
                 data_url: str = None,
                 embedding_model: str = "BAAI/bge-m3",
                 embedding_dim: int = 1024, recall_top_k: int = 5,
                 recall_weights: tuple = (0.6, 0.15, 0.1, 0.15),
                 recall_bm25_weight: float = 0.15,
                 skill_output_dir: str = "./skills", log_level: str = "INFO",
                 ann_index_path: str = "evolver.ann",
                 llm_provider: str = "openai", llm_api_key: str = None,
                 llm_model: str = None, llm_base_url: str = None,
                 memory_dir: str = "./memory", distill_lang: str = "zh",
                 auto_distill_hours: int = 24, fallback_embeddings: bool = False,
                 enable_dedup: bool = True, dedup_threshold: float = 0.15,
                 enable_closet: bool = True, identity_path: str = None,
                 reranker_config: RerankerConfig = None,
                 lifecycle_rules: list = None,
                 embedding_provider: str = "flagembedding",
                 embedding_api_key: str = None,
                 vector_store: str = "memory",
                 qdrant_url: str = "http://localhost:6333",
                 qdrant_api_key: str = None,
                 qdrant_collection: str = "evolver_memory"):
        url = db_url or mysql_url
        if not url:
            raise ValueError("db_url or mysql_url is required")

        self.config = EvolverConfig(
            mysql_url=url,
            data_url=data_url,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            embedding_provider=embedding_provider,
            embedding_api_key=embedding_api_key,
            vector_store=vector_store,
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            qdrant_collection=qdrant_collection,
            recall_top_k=recall_top_k,
            recall_weights=recall_weights,
            recall_bm25_weight=recall_bm25_weight,
            skill_output_dir=skill_output_dir,
            ann_index_path=ann_index_path,
            log_level=log_level,
            auto_distill_hours=auto_distill_hours,
            llm_provider=llm_provider,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            memory_dir=memory_dir,
            distill_lang=distill_lang,
            fallback_embeddings=fallback_embeddings,
            enable_dedup=enable_dedup,
            dedup_threshold=dedup_threshold,
            enable_closet=enable_closet,
            identity_path=identity_path,
            lifecycle_rules=lifecycle_rules,
            reranker=reranker_config,
        )

        # Set up logging
        self._setup_logging(log_level)

        # Auto-detect storage backend from URL scheme
        if url.startswith("sqlite://") or url.startswith("sqlite:///"):
            db_path = url.replace("sqlite:///", "").replace("sqlite://", "")
            self._storage = SQLiteStorage(db_path)
        elif url.startswith("mysql://"):
            if MySQLStorage is None:
                raise ImportError(
                    "pymysql is required for MySQL. Install with: pip install evolver[mysql]"
                )
            self._storage = MySQLStorage(url)
        else:
            # Default to SQLite for anything else (file paths, etc.)
            self._storage = SQLiteStorage(url)

        # Archive layer (optional, lazy-connected). Independent of experience layer.
        self._archive = None
        if data_url:
            if not data_url.startswith("mysql://"):
                raise ValueError("data_url must be a mysql:// URL")
            if MySQLStorage is None:
                raise ImportError(
                    "pymysql is required for the archive layer. "
                    "Install with: pip install evolver[mysql]"
                )
            from evolver.archive_store import ArchiveStore
            self._archive = ArchiveStore(data_url)

        self._embedding = EmbeddingClient(
            model_name=self.config.embedding_model, dim=embedding_dim,
            fallback=fallback_embeddings,
            provider=embedding_provider,
            api_key=embedding_api_key,
        )
        # Initialize VectorStore (Qdrant or InMemory)
        from evolver.vector_store import create_vector_store
        self._vector_store = create_vector_store(
            store_type=vector_store,
            url=qdrant_url,
            collection=qdrant_collection,
            dimension=embedding_dim,
            api_key=qdrant_api_key,
        )
        self._memory = MemoryEngine(self._storage, self._embedding, ann_index_path=ann_index_path,
                                     recall_bm25_weight=recall_bm25_weight,
                                     reranker_config=self.config.reranker,
                                     lifecycle_rules=self.config.lifecycle_rules,
                                     vector_store=self._vector_store)
        # LLM clients: main (skill synthesis) + distill (fast compression)
        self._llm = LLMClient(provider=llm_provider, api_key=llm_api_key,
                               model=llm_model, base_url=llm_base_url)
        self.graph = GraphEngine(self._storage, llm_client=self._llm, lang=distill_lang)
        # Distill uses the same LLM as main (no separate fast model)
        self._llm_distill = self._llm
        # Initialize SkillLibrary for deduplication and evolution
        from evolver.artifact_writer import ArtifactWriter
        from evolver.skill_library import SkillIndex
        self._skill_library = SkillIndex(
            library_path="./evolver-skills",
            embedding_client=self._embedding,
            similarity_threshold=0.85,
        )
        self._skill = SkillEngine(
            self._storage, self._memory, self.graph,
            llm_client=self._llm,
            skill_library=self._skill_library,
            artifact_writer=ArtifactWriter(),
        )
        self._link = LinkEngine(self._storage, self._embedding, self._memory, self.graph)
        self._memory_graph = MemoryGraph(self._storage, embedding=self._embedding)
        self._checker = QualityChecker(self._storage)
        self._compiler = MemoryCompiler(self._storage, self._llm_distill,
                                        memory_dir=memory_dir, lang=distill_lang)
        self._distill_lang = distill_lang
        # Memory extractor for LLM-based fact extraction
        self._extractor = MemoryExtractor(self._llm_distill, lang=distill_lang)
        # Wire into sub-engines
        self._memory._link = self._link
        self._skill._checker = self._checker

        # Deduplicator + ClosetIndex (v0.10)
        if enable_dedup:
            def _get_ann():
                return self._memory._ann if self._memory._ann_built else None
            self._deduplicator = Deduplicator(
                self._storage, self._embedding,
                threshold=dedup_threshold, get_ann=_get_ann,
            )
            self._memory.set_deduplicator(self._deduplicator)
        else:
            self._deduplicator = None

        if enable_closet:
            self._closet = ClosetIndex()
            self._memory.set_closet(self._closet)
        else:
            self._closet = None

        # MemoryStack (4-layer progressive memory)
        self._stack = MemoryStack(self._memory, identity_path=identity_path)

        # UserProfile (static + dynamic user traits)
        self._profile = UserProfile()

        # HybridSearch (memory + RAG combined)
        self._hybrid = HybridSearch(self._memory, rag_source=self._storage)

        # TemporalMemory (time-aware decay and access tracking)
        self._temporal = TemporalMemory()

        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="evolver")
        self._lock = threading.Lock()
        self._closed = False
        self._distill_pending = False
        self._distill_future = None

        # Pre-populate closet index from stored memories
        self._populate_closet_from_storage()

        # Sync temporal memory entries from stored memories
        try:
            self._temporal.sync_from_memories(self._storage)
        except Exception:
            logger.warning("Failed to sync temporal memory", exc_info=True)

    def _populate_closet_from_storage(self):
        """Populate ClosetIndex from existing memories on startup."""
        if self._closet is None:
            return
        try:
            memories = self._storage.get_all_memories_with_embeddings()
            for mem in memories:
                self._closet.add(mem.id, mem.content, mem.category)
            logger.debug("ClosetIndex populated with %d memories", len(memories))
        except Exception:
            logger.warning("Failed to populate ClosetIndex", exc_info=True)

    @staticmethod
    def _setup_logging(level: str):
        """Configure the evolver logger hierarchy."""
        logger = logging.getLogger("evolver")
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            logger.addHandler(handler)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    def learn(self, task: str, outcome: str, context: str = "",
              solution: str = "", lessons: str = "") -> list[int]:
        """Learn from an interaction. Explicitly triggered by user."""
        ids = self._memory.store(
            task=task, outcome=outcome, context=context,
            solution=solution, lessons=lessons,
        )
        # Build graph only when there is meaningful content
        graph_text = " ".join(p for p in [task, solution, lessons] if p and len(p) > 10)
        if graph_text:
            self.graph.build_from_text(graph_text)
        # Auto-distill in background if configured and stale
        self._auto_distill()
        return ids

    def learn_extracted(self, text: str, source: str = "extract") -> list[dict]:
        """Learn by extracting atomic facts via LLM.

        Unlike learn() which stores raw text, this uses LLM to extract
        self-contained facts, deduplicates via hash, and updates stale facts.

        Args:
            text: Raw text to extract facts from.
            source: Source identifier.

        Returns:
            List of {"action": "add"|"skip"|"update", "fact": str, "id": int}.
        """
        import hashlib
        import re

        facts = self._extractor.extract(text)
        if not facts:
            return []

        # Get existing hashes for fast dedup (lightweight query)
        existing_hashes = self._storage.get_all_content_hashes()

        results = []
        for fact in facts:
            fact_text = fact.get("text", "")
            if not fact_text or len(fact_text) < 5:
                continue

            # Hash dedup
            normalized = re.sub(r'\s+', ' ', fact_text.strip().lower())
            fact_hash = hashlib.md5(normalized.encode()).hexdigest()

            if fact_hash in existing_hashes:
                results.append({"action": "skip", "fact": fact_text[:50]})
                continue

            # Use MemoryEngine.store for transaction safety
            tags = fact.get("tags", [])
            ids = self._memory.store(
                task=fact_text,
                outcome="extracted",
                source=source,
            )
            existing_hashes.add(fact_hash)
            results.append({"action": "add", "fact": fact_text[:50], "id": ids[0] if ids else None})

        # Build graph from extracted facts
        graph_text = " ".join(f.get("text", "") for f in facts)
        if graph_text:
            self.graph.build_from_text(graph_text)

        logger.info("learn_extracted: %d facts extracted, %d added, %d skipped",
                     len(facts),
                     sum(1 for r in results if r["action"] == "add"),
                     sum(1 for r in results if r["action"] == "skip"))
        return results

    def _distill_safe(self):
        """Wrapper that logs exceptions from background distillation."""
        try:
            self._compiler.distill_all()
        except Exception:
            logger.exception("Background distillation failed")
        finally:
            self._distill_pending = False

    def recall(self, query: str, top_k: int = None,
               method: str = "rrf") -> list[RecallResult]:
        """Recall relevant memories.

        Args:
            query: Search query.
            top_k: Max results.
            method: "rrf" (Reciprocal Rank Fusion, default) or "weighted" (legacy).
        """
        k = top_k or self.config.recall_top_k
        return self._memory.recall(
            query, top_k=k, recall_weights=self.config.recall_weights,
            method=method,
        )

    def skillgen(self, topic: str, output_dir: str = None,
                 lang: str = None) -> SkillResult | None:
        """Generate a skill.md file.

        This method generates a skill and adds it to the SkillLibrary.
        If a similar skill exists, it will be evolved instead of creating a new one.
        """
        out = output_dir or self.config.skill_output_dir
        result = self._skill.generate(topic, output_dir=out,
                                      lang=lang or self._distill_lang)

        # Add to skill library if not already added (by _evolve_skill)
        if result and self._skill_library:
            existing = self._skill_library.get_skill(result.name)
            if not existing:
                self._skill_library.add_skill(
                    name=result.name,
                    description=f"Auto-generated skill for: {topic}",
                    content=result.content,
                    topic=topic,
                    version=result.version,
                    memories_used=0,   # counts already tracked in generate()
                    graph_nodes_used=0
                )

        return result

    def export_candidates(self, path: str = None, limit: int = 1000,
                          categories: list[str] = None) -> dict:
        """Export memories through the stable CandidateExport v1 contract.

        The returned candidates are evidence-bearing inputs for an external
        registry. They are not trusted or executable Skills.
        """
        from evolver.candidate_export import build_candidate_export, write_candidate_export

        export = build_candidate_export(
            self._storage,
            producer=f"evolver/{__version__}",
            limit=limit,
            categories=categories,
        )
        if path:
            write_candidate_export(export, path)
        return export

    def consolidate_experience(self, request: dict, path: str = None,
                               store: bool = True) -> dict:
        """Consolidate a Cerebellum request through the stable JSON v1 boundary.

        Returned Skill and Workflow items are proposals only. They are never
        added to the executable SkillLibrary by this method.
        """
        from evolver.consolidation import (
            consolidate_request, write_consolidation_response,
        )

        response = consolidate_request(request, producer=f"evolver/{__version__}")
        if store:
            experience = request["experience"]
            outcome = experience.get("outcome", {})
            for proposal in response["proposals"]:
                self.learn(
                    task=proposal["title"],
                    outcome="success" if outcome.get("success") else "failure",
                    context=f"cerebellum experience {proposal['experience_id']}",
                    solution=proposal["content"] if outcome.get("success") else "",
                    lessons=proposal["content"],
                )
        if path:
            write_consolidation_response(response, path)
        return response

    def forget(self, memory_id: int = None, older_than_days: int = None,
               low_importance: float = None):
        """Forget memories."""
        self._memory.forget(memory_id=memory_id, older_than_days=older_than_days,
                            low_importance=low_importance)

    def build_index(self):
        """Build/rebuild the ANN index for fast recall."""
        self._memory.build_index()

    def sync_vector_store(self, batch_size: int = 500, prune: bool = True) -> dict:
        """Reconcile the configured VectorStore with the memory database."""
        return self._memory.sync_vector_store(batch_size=batch_size, prune=prune)

    def _auto_distill(self):
        """Trigger background distillation if last run is stale."""
        if self._distill_pending:
            return
        hours = self.config.auto_distill_hours
        if hours <= 0:
            return
        try:
            last = self._storage.get_last_distill_run("today")
            if last:
                from datetime import datetime, timezone
                created = last.get("created_at", "")
                if created:
                    try:
                        last_dt = datetime.fromisoformat(str(created))
                    except ValueError:
                        return
                    if last_dt.tzinfo is not None:
                        last_dt = last_dt.astimezone(timezone.utc).replace(tzinfo=None)
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    if (now - last_dt).total_seconds() < hours * 3600:
                        return
            logger.info("Auto-distill triggered (last run stale or missing)")
            self._distill_pending = True
            self._distill_future = self._executor.submit(self._distill_safe)
        except (OSError, ValueError) as e:
            logger.warning("Auto-distill check failed: %s", e)
        except Exception:
            logger.exception("Unexpected error in auto-distill")
            raise

    def distill(self, level: str = "all", days: int = 7) -> dict | str:
        """Run memory distillation pipeline.

        Args:
            level: 'today'|'week'|'longterm'|'facts'|'all'
            days: Time range for week/facts compilation.
        """
        if level == "all":
            return self._compiler.distill_all(days=days)
        method = {
            "today": lambda: self._compiler.compile_today(days=1),
            "week": lambda: self._compiler.compile_week(days=days),
            "longterm": lambda: self._compiler.compile_longterm(),
            "facts": lambda: self._compiler.compile_facts(days=days),
        }.get(level)
        if method is None:
            raise ValueError(f"Unknown distill level: {level}")
        return method()

    def memory_context(self) -> str:
        """Return assembled memory context (for prompt injection)."""
        return self._compiler.assemble()

    def search_facts(self, query: str, limit: int = 10) -> list:
        """Full-text search facts."""
        return self._storage.search_facts_fts(query, limit=limit)

    def add_fact(self, fact: str, tags: list = None):
        """Manually add a fact."""
        self._storage.insert_fact(fact, tags=tags)

    def archive(self, content: str, kind: str, tags: list = None,
                source: str = None, ref: str = None, meta: dict = None) -> int:
        """Store a dead-data record in the archive layer (MySQL)."""
        if self._archive is None:
            raise EvolverError(_archive_not_configured_msg())
        return self._archive.archive(content, kind, tags=tags,
                                     source=source, ref=ref, meta=meta)

    def search_archive(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search the archive layer."""
        if self._archive is None:
            raise EvolverError(_archive_not_configured_msg())
        return self._archive.search_archive(query, limit=limit)

    def get_archive(self, archive_id: int) -> dict | None:
        """Fetch one archive record by id."""
        if self._archive is None:
            raise EvolverError(_archive_not_configured_msg())
        return self._archive.get_archive(archive_id)

    def stats(self) -> dict:
        """Get engine statistics."""
        return self._storage.stats()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — ensures close is always called."""
        self.close()
        return False  # Re-raise any exception

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_async()
        return False

    def close(self):
        """Close database connection and thread pool. Idempotent."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if self._distill_future:
            try:
                self._distill_future.result(timeout=30)
            except Exception:
                logger.exception("Distill future did not complete cleanly")
            self._distill_future = None
        self._executor.shutdown(wait=False)
        self._storage.close()
        if self._archive is not None:
            self._archive.close()

    def backlinks(self, target_type: str, target_id: int) -> list:
        """Find all links pointing to a target."""
        return self._link.backlinks(target_type, target_id)

    def linked_memories(self, memory_id: int, top_k: int = 10) -> list:
        """Get memories linked to a given memory."""
        return self._link.linked_memories(memory_id, top_k)

    def eval_skill(self, skill_content: str, topic: str):
        """Evaluate skill quality without modifying it."""
        return self._checker.evaluate(skill_content, topic)

    def decay_links(self, factor: float = 0.95, min_weight: float = 0.01):
        """Decay link weights over time."""
        self._storage.decay_links(factor=factor, min_weight=min_weight)

    def decay_edges(self, factor: float = 0.9, min_weight: float = 0.01):
        """Decay graph edge weights over time."""
        self._storage.decay_edges(factor=factor, min_weight=min_weight)

    def reconsolidate(self, memory_id: int, correction: str) -> bool:
        """修正记忆内容，重新计算 embedding 和 tags。"""
        return self._memory.reconsolidate(memory_id, correction)

    def suggest(self, context: str, top_k: int = 3) -> list[RecallResult]:
        """主动记忆：给当前上下文，搜索可能相关的历史教训。"""
        return self._memory.suggest(context, top_k=top_k)

    def memory_graph(self, iterations: int = 50, width: float = 800.0, height: float = 600.0) -> dict:
        """Build and lay out the memory graph for visualization.

        Returns:
            dict with 'nodes', 'edges', 'meta' keys.
        """
        return self._memory_graph.to_dict(iterations=iterations, width=width, height=height)

    def ingest(self, directory: str, recursive: bool = True,
               source_prefix: str = "ingest",
               max_file_size: int = 10 * 1024 * 1024,
               on_progress=None):
        """Batch ingest documents from a directory.

        Scans for .txt, .md, .pdf, .docx files, extracts text,
        and feeds into learn_extracted for intelligent fact extraction.

        Args:
            directory: Path to scan.
            recursive: Scan subdirectories (default True).
            source_prefix: Source label prefix (default "ingest").
            max_file_size: Skip files larger than this (default 10MB).
            on_progress: Optional callback(idx, total, path).

        Returns:
            IngestStats with aggregate results.
        """
        from evolver.ingest import ingest_directory
        return ingest_directory(
            self, directory,
            recursive=recursive,
            source_prefix=source_prefix,
            max_file_size=max_file_size,
            on_progress=on_progress,
        )

    def interference_decay(self, similarity_threshold: float = 0.85,
                           decay_factor: float = 0.8) -> int:
        """干扰模型遗忘：高相似度旧记忆的 importance 衰减。"""
        return self._memory.interference_decay(similarity_threshold, decay_factor)

    def update_lifecycle(self) -> dict:
        """Auto-migrate memory lifecycle stages (seed→growing→evergreen→stale)."""
        return self._memory.update_lifecycle()

    def compose_skills(self, skill_a: str, skill_b: str, topic: str) -> SkillResult | None:
        """组合两个相关技能为一个新技能。"""
        return self._skill.compose(skill_a, skill_b, topic)

    def find_composable_pairs(self, min_shared_nodes: int = 3) -> list:
        """找出共享超过 N 个图谱节点的技能对。"""
        return self._skill.find_composable_pairs(min_shared_nodes)

    # ---- Progressive Memory Stack (v0.10) ----

    def wake_up(self, category: str = None) -> str:
        """L0+L1 progressive memory context (~600-900 tokens)."""
        return self._stack.wake_up(category=category)

    def recall_light(self, query: str, category: str = None,
                     top_k: int = 10) -> str:
        """L2 on-demand recall with truncated snippets."""
        return self._stack.recall_light(query, category=category, top_k=top_k)

    def recall_deep(self, query: str, top_k: int = 5):
        """L3 full recall with all fusion signals."""
        return self._stack.recall_deep(query, top_k=top_k)

    def closet_query(self, text: str) -> list[int]:
        """Keyword lookup via ClosetIndex. Returns memory IDs."""
        if self._closet is None:
            return []
        return self._closet.query(text)

    # ---- User Profile (Phase 1) ----

    def build_profile(self) -> "UserProfile":
        """Build user profile from stored memories."""
        self._profile.from_memories(self._storage)
        return self._profile

    def profile_prompt(self) -> str:
        """Return user profile as system prompt."""
        return self._profile.to_prompt()

    def get_profile(self) -> "UserProfile":
        """Return the current UserProfile object."""
        return self._profile

    # ---- Hybrid Search (Phase 1) ----

    def hybrid_search(self, query: str, mode: str = "hybrid",
                      top_k: int = 5, **kwargs) -> list[RecallResult]:
        """Search across memories and/or RAG sources.

        Args:
            query: Search query.
            mode: "hybrid" (both), "memories" (memory only), or "rag" (RAG only).
            top_k: Max results.
        """
        return self._hybrid.search(query, mode=mode, top_k=top_k, **kwargs)

    # ---- Temporal Memory (Phase 1) ----

    def temporal_stats(self) -> dict:
        """Get temporal memory statistics (expired count, lifecycle distribution)."""
        return self._temporal.get_stats()

    def apply_temporal_decay(self):
        """Apply time-based importance decay to all tracked memories."""
        self._temporal.apply_decay(self._storage)

    def expire_stale_memories(self) -> int:
        """Remove expired entries from temporal tracking. Returns count removed."""
        return self._temporal.remove_expired()

    # ---- Async API ----

    async def _run_async(self, _method: str, *args, **kwargs):
        """Run a sync method in the thread pool."""
        loop = asyncio.get_running_loop()
        method = getattr(self, _method)
        return await loop.run_in_executor(self._executor, lambda: method(*args, **kwargs))

    async def close_async(self):
        """Async variant of :meth:`close`.

        Note: runs storage close directly (not via executor) because
        ``shutdown(wait=True)`` from within an executor task would deadlock.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=False)
        self._storage.close()
        if self._archive is not None:
            self._archive.close()


_ASYNC_EXPOSED = [
    "learn", "recall", "skillgen", "stats", "backlinks", "linked_memories",
    "eval_skill", "distill", "memory_context", "search_facts", "reconsolidate",
    "suggest", "interference_decay", "update_lifecycle", "ingest", "memory_graph",
    "export_candidates", "consolidate_experience",
]

for _name in _ASYNC_EXPOSED:
    def _make_async(name):
        async def wrapper(self, *args, **kwargs):
            return await self._run_async(name, *args, **kwargs)
        wrapper.__name__ = f"{name}_async"
        wrapper.__qualname__ = f"Evolver.{name}_async"
        wrapper.__doc__ = f"Async variant of :meth:`{name}`."
        return wrapper
    setattr(Evolver, f"{_name}_async", _make_async(_name))


__all__ = [
    "Evolver", "EvolverConfig", "RerankerConfig", "LifecycleRule",
    "DEFAULT_LIFECYCLE_RULES", "RecallResult", "SkillResult",
    "BaseStorage", "MySQLStorage", "SQLiteStorage", "Link", "EvalResult", "Fact",
    "LLMClient", "MemoryCompiler", "MemoryGraph",
    "EvolverError", "EvolverConnectionError", "EmbeddingError", "NotionConnectorError",
    "UserProfile", "ProfileTrait", "HybridSearch", "SearchMode",
    "TemporalMemory", "TemporalEntry",
    "_archive_not_configured_msg",
]

_LAZY_IMPORTS = {
    "RecallResult": "evolver.models",
    "SkillResult": "evolver.models",
    "Link": "evolver.models",
    "EvalResult": "evolver.models",
    "Fact": "evolver.models",
    "Memory": "evolver.models",
    "BaseStorage": "evolver.storage_base",
    "MemoryGraph": "evolver.memory_graph",
    "RetrievalEngine": "evolver.retrieval",
    "UserProfile": "evolver.user_profile",
    "ProfileTrait": "evolver.user_profile",
    "HybridSearch": "evolver.hybrid_search",
    "SearchMode": "evolver.hybrid_search",
    "TemporalMemory": "evolver.temporal_memory",
    "TemporalEntry": "evolver.temporal_memory",
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module = __import__(_LAZY_IMPORTS[name], fromlist=[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return list(globals().keys()) + list(_LAZY_IMPORTS.keys())
