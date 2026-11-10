# Evolver

Agent self-evolution engine. Learn from interactions, recall memories, build
knowledge graphs, generate skills, and distill knowledge over time.

## Installation

```bash
pip install -e .

# With optional dependencies
pip install -e ".[all]"     # MySQL + jieba + HNSW
pip install -e ".[dev]"     # pytest + MySQL
pip install -e ".[chinese]" # jieba Chinese word segmentation
pip install -e ".[ann]"     # HNSW approximate nearest neighbor
```

## Quick Start

### CLI

```bash
# Learn from an interaction
evolver --fallback learn --db-url sqlite:///evolver.db \
  --task "fix auth timeout" --outcome success \
  --solution "increased JWT expiry to 24h" \
  --lessons "check token expiry when debugging 401s"

# Recall relevant memories
evolver --fallback recall --db-url sqlite:///evolver.db --query "auth timeout"

# Generate a reusable skill
evolver --fallback skillgen --db-url sqlite:///evolver.db \
  --topic "git workflow" --output-dir ./skills

# Distill knowledge (today → week → longterm → facts)
evolver --fallback distill --db-url sqlite:///evolver.db --level all

# Show stats
evolver stats --db-url sqlite:///evolver.db

# Export a storage-independent, quarantined candidate feed for Cerebellum
evolver --fallback export-candidates --db-url sqlite:///evolver.db \
  --output candidates.json --limit 1000

# Run the versioned, lease-based Cerebellum consolidation worker
evolver --fallback cerebellum-worker --db-url sqlite:///evolver.db \
  --server-url http://127.0.0.1:3927 --token "$CEREBELLUM_AUTH_TOKEN"
```

Write commands print a storage receipt. For deterministic storage, always pass
`--db-url`; otherwise relative SQLite paths resolve from the current working
directory.

### Python API

```python
from evolver import Evolver

evolver = Evolver(db_url="sqlite:///evolver.db")

# Store an experience
evolver.learn(
    task="fix bug",
    outcome="success",
    solution="fixed null pointer",
    lessons="always null-check input",
)

# Recall relevant memories
results = evolver.recall("null pointer bug")
for r in results:
    print(f"[{r.score:.2f}] {r.memory.content}")

# Generate a skill
skill = evolver.skillgen("error handling")

# Apply interference decay (biological forgetting model)
evolver.interference_decay()

# Distill accumulated knowledge
evolver.distill(level="all")
print(evolver.memory_context())

# CandidateExport v1 contains no embeddings, DB URLs, or internal table fields.
export = evolver.export_candidates(path="candidates.json", limit=1000)

# ConsolidationRequest/Response v1 is a pure JSON boundary. Skill and Workflow
# outputs remain non-executable proposals until Cerebellum evaluation/review.
response = evolver.consolidate_experience(request, path="response.json")

evolver.close()
```

## Architecture

Evolver uses a 3-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Evolver Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Layer 1: Dead Data Layer                │   │
│  │                                                     │   │
│  │                    MySQL                            │   │
│  │                                                     │   │
│  │  • archives (raw records)                           │   │
│  │  • logs                                             │   │
│  │  • transcripts                                      │   │
│  │  • images (references)                              │   │
│  │                                                     │   │
│  │  Features: Full-text search (FULLTEXT + ngram)      │   │
│  │  Lifecycle: Weight decays over time                 │   │
│  └────────────────────────│────────────────────────────┘   │
│                           │                                │
│                           │  DistillationEngine            │
│                           │  (LLM extraction)              │
│                           ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Layer 2: Experience Layer               │   │
│  │                                                     │   │
│  │                    SQLite                           │   │
│  │                                                     │   │
│  │  • memories (distilled, lifecycle=distilled)        │   │
│  │  • facts (atomic)                                   │   │
│  │  • graph (knowledge graph)                          │   │
│  │  • links (memory connections)                       │   │
│  │                                                     │   │
│  │  Features: Semantic search + BM25                   │   │
│  │  Lifecycle: Never decays (distilled)                │   │
│  └────────────────────────│────────────────────────────┘   │
│                           │                                │
│                           │  SkillGenerator                │
│                           ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Layer 3: Skill Layer                    │   │
│  │                                                     │   │
│  │              SKILL.md files                          │   │
│  │                                                     │   │
│  │  Reusable operational skill documents               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Raw Data → MySQL (dead data) → LLM Extraction → SQLite (experience) → Skill Generation
```

### Configuration

```bash
# Required: MySQL for dead data layer
export EVOLVER_DATA_URL='mysql://root:***@localhost:3306/evolver_archive'

# Required: SQLite for experience layer
export EVOLVER_DB_URL='sqlite:///evolver.db'
```

### Migration from SQLite

If you have existing SQLite archive data:

1. Backup: `cp evolver_archive.db evolver_archive.db.backup`
2. Run migration check: `python evolver/migrate_archive.py`
3. Configure MySQL: `export EVOLVER_DATA_URL='mysql://...'`
4. Import data (manual)

### MySQL Requirements

- Version: 5.7+ or 8.0+
- Character set: utf8mb4
- Parser: ngram (for Chinese full-text search)
- Engine: InnoDB (required for FULLTEXT index)

## Features

| Feature | Description |
|---------|-------------|
| Memory | Store, recall (semantic + keyword + link boost), forget, reconsolidate |
| Interference decay | Biological forgetting model — similar new memories suppress old ones |
| Knowledge graph | Auto-extract entities, build relations, decay edges |
| Skill generation | LLM-powered skill synthesis with fallback templates |
| Skill composition | Combine related skills into comprehensive ones |
| Memory distillation | Progressive compression: today → week → longterm → facts |
| Auto-distillation | Background distillation when last run is stale |
| Quality checking | Automated skill evaluation with ratchet mechanism |
| Dual LLM | Main model for synthesis + smaller model for fast distillation |
| Async API | Full async variant of all public methods |
| CLI | Click-based CLI with all features exposed |

## Database Backends

| Layer | Backend | URL Format | Purpose |
|-------|---------|-----------|---------|
| **Dead Data** | MySQL | `mysql://user:***@host:3306/db` | Raw records, logs, transcripts |
| **Experience** | SQLite | `sqlite:///evolver.db` | Distilled memories, facts, graph |

### Why Two Backends?

- **MySQL**: Better full-text search (FULLTEXT + ngram), handles large datasets, production-ready
- **SQLite**: Zero-config, fast for small datasets, perfect for experience layer

### Configuration

```bash
# Environment variables
export EVOLVER_DATA_URL='mysql://root:***@localhost:3306/evolver_archive'  # Dead data layer
export EVOLVER_DB_URL='sqlite:///evolver.db'                               # Experience layer
```

## Configuration

```python
evolver = Evolver(
    db_url="sqlite:///evolver.db",
    embedding_model="BAAI/bge-small-en-v1.5",  # fastembed model
    embedding_dim=384,
    recall_top_k=5,
    llm_provider="openai",                      # or "anthropic"
    llm_model="gpt-4o-mini",                    # main LLM
    distill_llm_model="gemma2:2b",              # fast distillation LLM
    auto_distill_hours=24,                      # background distill interval
    fallback_embeddings=False,                  # hash-based fallback (offline)
    memory_dir="./memory",
)
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
PYTHONPATH=. python -m pytest tests/ -v

# Run specific test file
PYTHONPATH=. python -m pytest tests/test_memory.py -v
```

## License

MIT
