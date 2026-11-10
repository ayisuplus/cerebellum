import os
from dataclasses import dataclass


def _parse_weights_env(val: str | None, default: tuple) -> tuple:
    """Parse comma-separated float weights from env var."""
    if not val:
        return default
    try:
        return tuple(float(x.strip()) for x in val.split(","))
    except (ValueError, TypeError):
        return default



# Single source for the recall brute-force scan cap and the ANN auto-build
# threshold. Keeping them equal closes the blind zone where memories older
# than the newest `max_scan` rows were unreachable until 5000 vectors
# triggered the ANN build.
DEFAULT_MAX_SCAN = 2000

@dataclass
class LifecycleRule:
    """Single lifecycle transition rule. All conditions must pass for the
    transition to fire. ``max_*`` fields default to infinity / MAXINT so that
    omitting them means "no upper bound"."""
    from_stage: str | None  # None = matches any stage
    to_stage: str
    min_age_days: int = 0
    max_age_days: int = 2**31
    min_importance: float = 0.0
    max_importance: float = 1.0
    min_access_count: int = 0
    max_access_count: int = 2**31
    priority: int = 0  # higher = checked first


DEFAULT_LIFECYCLE_RULES = [
    LifecycleRule(from_stage=None, to_stage="stale",
                  min_age_days=90, max_importance=0.5, max_access_count=0,
                  priority=10),
    LifecycleRule(from_stage="seed", to_stage="growing",
                  min_access_count=2, priority=1),
    LifecycleRule(from_stage="growing", to_stage="evergreen",
                  min_age_days=30, min_importance=0.8, priority=2),
    LifecycleRule(from_stage="growing", to_stage="seed",
                  max_importance=0.3, priority=3),
    LifecycleRule(from_stage="evergreen", to_stage="growing",
                  max_importance=0.5, priority=4),
]


@dataclass
class RerankerConfig:
    """Weights for second-stage recall reranker (all signals sum to ~1.0)."""
    fusion_score: float = 0.40   # original fusion score
    jaccard: float = 0.20        # token overlap with query
    len_penalty: float = 0.10    # conciseness bonus
    category: float = 0.10       # category relevance
    recency: float = 0.10        # temporal grounding
    lifecycle: float = 0.10      # lifecycle stage boost


@dataclass
class EvolverConfig:
    mysql_url: str
    data_url: str | None = None
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_provider: str = "flagembedding"  # "flagembedding", "fastembed", "voyage", "openai"
    embedding_api_key: str | None = None   # API key for voyage/openai providers
    vector_store: str = "memory"           # "memory" or "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "evolver_memory"
    recall_top_k: int = 5
    recall_weights: tuple = (0.6, 0.15, 0.1, 0.15)
    recall_bm25_weight: float = 0.15
    skill_output_dir: str = "./skills"
    log_level: str = "INFO"
    ann_index_path: str = "evolver.ann"
    auto_distill_hours: int = 24
    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    memory_dir: str = "./memory"
    distill_lang: str = "zh"
    fallback_embeddings: bool = False
    enable_dedup: bool = True
    dedup_threshold: float = 0.15
    enable_closet: bool = True
    identity_path: str | None = None
    lifecycle_rules: list[LifecycleRule] = None  # type: ignore
    reranker: RerankerConfig = None  # type: ignore

    def __post_init__(self):
        if self.lifecycle_rules is None:
            self.lifecycle_rules = DEFAULT_LIFECYCLE_RULES
        if self.reranker is None:
            self.reranker = RerankerConfig()
        # If EVOLVER_EMBEDDING_MODEL is set in the environment, it takes
        # priority over the default "BAAI/bge-m3" so local model paths work.
        env_model = os.environ.get("EVOLVER_EMBEDDING_MODEL")
        if env_model:
            object.__setattr__(self, 'embedding_model', env_model)

    @classmethod
    def from_env(cls) -> "EvolverConfig":
        url = os.environ.get("EVOLVER_DB_URL", "") or os.environ.get("EVOLVER_MYSQL_URL", "")
        if not url:
            raise ValueError("EVOLVER_DB_URL or EVOLVER_MYSQL_URL environment variable is required")

        def _safe_int(env_key: str, default: int) -> int:
            raw = os.environ.get(env_key, "")
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError:
                raise ValueError(f"Invalid integer for {env_key}: {raw!r}") from None

        def _safe_float(env_key: str, default: float) -> float:
            raw = os.environ.get(env_key, "")
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError:
                raise ValueError(f"Invalid float for {env_key}: {raw!r}") from None

        return cls(
            mysql_url=url,
            data_url=os.environ.get("EVOLVER_DATA_URL"),
            embedding_model=os.environ.get("EVOLVER_EMBEDDING_MODEL", cls.embedding_model),
            embedding_dim=_safe_int("EVOLVER_EMBEDDING_DIM", cls.embedding_dim),
            embedding_provider=os.environ.get("EVOLVER_EMBEDDING_PROVIDER", cls.embedding_provider),
            recall_top_k=_safe_int("EVOLVER_RECALL_TOP_K", cls.recall_top_k),
            recall_weights=_parse_weights_env(
                os.environ.get("EVOLVER_RECALL_WEIGHTS"), cls.recall_weights,
            ),
            recall_bm25_weight=_safe_float("EVOLVER_RECALL_BM25_WEIGHT", cls.recall_bm25_weight),
            skill_output_dir=os.environ.get("EVOLVER_SKILL_OUTPUT_DIR", cls.skill_output_dir),
            ann_index_path=os.environ.get("EVOLVER_ANN_INDEX_PATH", cls.ann_index_path),
            log_level=os.environ.get("EVOLVER_LOG_LEVEL", cls.log_level),
            auto_distill_hours=_safe_int("EVOLVER_AUTO_DISTILL_HOURS", cls.auto_distill_hours),
            llm_provider=os.environ.get("EVOLVER_LLM_PROVIDER", cls.llm_provider),
            llm_api_key=os.environ.get("EVOLVER_LLM_API_KEY"),
            llm_model=os.environ.get("EVOLVER_LLM_MODEL"),
            llm_base_url=os.environ.get("EVOLVER_LLM_BASE_URL"),
            memory_dir=os.environ.get("EVOLVER_MEMORY_DIR", cls.memory_dir),
            distill_lang=os.environ.get("EVOLVER_DISTILL_LANG", cls.distill_lang),
            fallback_embeddings=os.environ.get("EVOLVER_FALLBACK_EMBEDDINGS", "").lower() in ("1", "true", "yes"),
            enable_dedup=os.environ.get("EVOLVER_ENABLE_DEDUP", "true").lower() in ("1", "true", "yes"),
            dedup_threshold=_safe_float("EVOLVER_DEDUP_THRESHOLD", cls.dedup_threshold),
            enable_closet=os.environ.get("EVOLVER_ENABLE_CLOSET", "true").lower() in ("1", "true", "yes"),
            identity_path=os.environ.get("EVOLVER_IDENTITY_PATH"),
        )
