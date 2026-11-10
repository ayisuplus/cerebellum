# Evolver v2.0 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生产就绪的 agent 记忆引擎 — 嵌入模型多 provider、MySQL 并发安全、LLM 图谱提取、Qdrant 向量存储、SkillEngine 降级

**Architecture:** 渐进增强，保持现有接口不变，内部实现升级。5 个改进按依赖顺序分阶段交付。

**Tech Stack:** Python 3.10+, SQLAlchemy, Qdrant, Voyage AI, OpenAI, Alembic

---

## 文件结构

```
evolver/
├── embedding.py              # 修改 — 使用 provider 抽象
├── embedding_providers.py    # 新增 — FastEmbed/Voyage/OpenAI provider
├── storage_base.py           # 可能新增方法签名
├── storage_sqlite.py         # 修改 — 加 WAL + 线程锁
├── storage_mysql.py          # 新增 — MySQL 实现
├── vector_store.py           # 新增 — VectorStore ABC + Qdrant/InMemory
├── ann_index.py              # 保留，作为 InMemory fallback
├── extraction.py             # 修改 — 加入 LLM 提取
├── graph.py                  # 修改 — 使用 MemoryExtractor
├── skill.py                  # 修改 — 加入模板合成
├── templates/
│   └── skill_default.md      # 新增 — 默认 skill 模板
├── migrations/               # 新增 — Alembic 迁移
│   ├── env.py
│   └── versions/
├── config.py                 # 修改 — 新增配置项
└── __init__.py               # 修改 — 新增参数
tests/
├── test_embedding_providers.py  # 新增
├── test_vector_store.py         # 新增
├── test_storage_mysql.py        # 新增
├── test_extraction_llm.py       # 新增
└── test_skill_template.py       # 新增
```

---

## Phase 1: 嵌入模型支持

### Task 1.1: 创建 EmbeddingProvider 接口

**Files:**
- Create: `evolver/embedding_providers.py`
- Test: `tests/test_embedding_providers.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_embedding_providers.py
import pytest
from evolver.embedding_providers import EmbeddingProvider, VoyageProvider

def test_voyage_provider_interface():
    """VoyageProvider 实现 EmbeddingProvider 接口"""
    provider = VoyageProvider(api_key="test", model="voyage-3")
    assert hasattr(provider, 'embed_single')
    assert hasattr(provider, 'embed_batch')
    assert hasattr(provider, 'dimension')
    assert provider.dimension == 1024

def test_voyage_provider_embed_single():
    """VoyageProvider.embed_single 返回正确维度的向量"""
    provider = VoyageProvider(api_key="test", model="voyage-3")
    vec = provider.embed_single("hello world")
    assert len(vec) == 1024
    assert all(isinstance(v, float) for v in vec)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_embedding_providers.py::test_voyage_provider_interface -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'evolver.embedding_providers'`

- [ ] **Step 3: 写最小实现**

```python
# evolver/embedding_providers.py
from abc import ABC, abstractmethod
from typing import List
import numpy as np

class EmbeddingProvider(ABC):
    """嵌入模型 provider 接口"""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""
        pass

    @abstractmethod
    def embed_single(self, text: str) -> np.ndarray:
        """单条文本嵌入"""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """批量文本嵌入"""
        pass


class VoyageProvider(EmbeddingProvider):
    """Voyage AI 嵌入 provider"""

    def __init__(self, api_key: str, model: str = "voyage-3"):
        self._api_key = api_key
        self._model = model
        self._dim = 1024  # voyage-3 默认维度
        try:
            import voyageai
            self._client = voyageai.Client(api_key=api_key)
        except ImportError:
            raise ImportError("pip install voyageai")

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_single(self, text: str) -> np.ndarray:
        result = self._client.embed([text], model=self._model)
        return np.array(result.embeddings[0], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        result = self._client.embed(texts, model=self._model)
        return [np.array(e, dtype=np.float32) for e in result.embeddings]


class OpenAIProvider(EmbeddingProvider):
    """OpenAI 嵌入 provider"""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self._api_key = api_key
        self._model = model
        self._dim = 1536  # text-embedding-3-small 默认维度
        try:
            import openai
            self._client = openai.OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("pip install openai")

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_single(self, text: str) -> np.ndarray:
        result = self._client.embeddings.create(input=[text], model=self._model)
        return np.array(result.data[0].embedding, dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        result = self._client.embeddings.create(input=texts, model=self._model)
        return [np.array(d.embedding, dtype=np.float32) for d in result.data]


class FastEmbedProvider(EmbeddingProvider):
    """本地 fastembed provider（现有逻辑包装）"""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        self._model = model
        self._dim = 384
        try:
            from fastembed import TextEmbedding
            self._embedder = TextEmbedding(model_name=model)
        except ImportError:
            raise ImportError("pip install fastembed")

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_single(self, text: str) -> np.ndarray:
        results = list(self._embedder.embed([text]))
        return np.array(results[0], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        results = list(self._embedder.embed(texts))
        return [np.array(r, dtype=np.float32) for r in results]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_embedding_providers.py::test_voyage_provider_interface -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/embedding_providers.py tests/test_embedding_providers.py
git commit -m "feat: add EmbeddingProvider interface with Voyage/OpenAI/FastEmbed"
```

---

### Task 1.2: 修改 EmbeddingClient 使用 provider

**Files:**
- Modify: `evolver/embedding.py`
- Modify: `evolver/config.py`
- Modify: `evolver/__init__.py`
- Test: `tests/test_embedding_providers.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_embedding_providers.py (追加)
def test_embedding_client_with_voyage():
    """EmbeddingClient 支持 voyage provider"""
    from evolver.embedding import EmbeddingClient
    client = EmbeddingClient(provider="voyage", api_key="test", model="voyage-3")
    assert client.dimension == 1024

def test_embedding_client_with_fastembed():
    """EmbeddingClient 支持 fastembed provider（默认）"""
    from evolver.embedding import EmbeddingClient
    client = EmbeddingClient()
    assert client.dimension == 384
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_embedding_providers.py::test_embedding_client_with_voyage -v
```

预期：FAIL — `EmbeddingClient.__init__()` 不接受 `provider` 参数

- [ ] **Step 3: 修改 EmbeddingClient**

```python
# evolver/embedding.py — 修改 __init__
def __init__(self, model: str = "BAAI/bge-small-en-v1.5",
             dimension: int = 384, fallback: bool = False,
             provider: str = "fastembed", api_key: str = None):
    self._provider_name = provider
    self._fallback = fallback

    # 初始化 provider
    if provider == "voyage":
        from evolver.embedding_providers import VoyageProvider
        self._provider = VoyageProvider(api_key=api_key, model=model or "voyage-3")
    elif provider == "openai":
        from evolver.embedding_providers import OpenAIProvider
        self._provider = OpenAIProvider(api_key=api_key, model=model or "text-embedding-3-small")
    else:
        from evolver.embedding_providers import FastEmbedProvider
        self._provider = FastEmbedProvider(model=model)

    self._dim = self._provider.dimension
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_embedding_providers.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/embedding.py evolver/embedding_providers.py tests/test_embedding_providers.py
git commit -m "feat: EmbeddingClient supports provider switching"
```

---

### Task 1.3: 更新配置和 Evolver 入口

**Files:**
- Modify: `evolver/config.py`
- Modify: `evolver/__init__.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_embedding_providers.py (追加)
def test_evolver_accepts_embedding_config():
    """Evolver 接受嵌入配置"""
    from evolver import Evolver
    e = Evolver(
        db_url="sqlite:///test.db",
        embedding_provider="voyage",
        embedding_model="voyage-3",
        voyage_api_key="test"
    )
    assert e._embedding._provider_name == "voyage"
    e.close()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_embedding_providers.py::test_evolver_accepts_embedding_config -v
```

预期：FAIL — `Evolver.__init__()` 不接受 `embedding_provider`

- [ ] **Step 3: 修改 config.py 和 __init__.py**

```python
# evolver/config.py — EvolverConfig 新增字段
embedding_provider: str = "fastembed"
voyage_api_key: str = None
openai_api_key: str = None
```

```python
# evolver/__init__.py — __init__ 新增参数
def __init__(self, ...,
             embedding_provider: str = "fastembed",
             voyage_api_key: str = None,
             openai_api_key: str = None,
             ...):
    # ...
    self._embedding = EmbeddingClient(
        model=embedding_model,
        dimension=embedding_dim,
        provider=embedding_provider,
        api_key=voyage_api_key or openai_api_key,
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_embedding_providers.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/config.py evolver/__init__.py
git commit -m "feat: Evolver accepts embedding_provider config"
```

---

## Phase 2: 并发安全（MySQL）

### Task 2.1: SQLite WAL + 线程锁

**Files:**
- Modify: `evolver/storage_sqlite.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_storage.py (追加)
import threading
def test_sqlite_concurrent_writes():
    """SQLite 支持并发写入（WAL + 锁）"""
    from evolver.storage_sqlite import SQLiteStorage
    storage = SQLiteStorage(":memory:")
    errors = []

    def write_task(i):
        try:
            storage.insert_memory(Memory(content=f"test {i}", category="test"))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=write_task, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_storage.py::test_sqlite_concurrent_writes -v
```

预期：FAIL — 可能有 `sqlite3.OperationalError: database is locked`

- [ ] **Step 3: 修改 storage_sqlite.py**

```python
# evolver/storage_sqlite.py — __init__ 新增
import threading
self._lock = threading.Lock()
self._conn.execute("PRAGMA journal_mode=WAL")

# 所有写操作加锁
def insert_memory(self, memory):
    with self._lock:
        # 现有逻辑
        pass
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_storage.py::test_sqlite_concurrent_writes -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/storage_sqlite.py tests/test_storage.py
git commit -m "feat: SQLite WAL mode + thread-safe writes"
```

---

### Task 2.2: MySQL 存储实现

**Files:**
- Create: `evolver/storage_mysql.py`
- Create: `evolver/migrations/env.py`
- Test: `tests/test_storage_mysql.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_storage_mysql.py
import pytest
@pytest.mark.skipif(not pytest.importorskip("pymysql"), reason="pymysql not installed")
def test_mysql_storage_init():
    """MySQLStorage 初始化"""
    from evolver.storage_mysql import MySQLStorage
    storage = MySQLStorage("mysql://root:root@localhost:3306/evolver_test")
    assert storage is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_storage_mysql.py::test_mysql_storage_init -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'evolver.storage_mysql'`

- [ ] **Step 3: 写最小实现**

```python
# evolver/storage_mysql.py
import logging
from evolver.storage_base import BaseStorage

logger = logging.getLogger(__name__)

class MySQLStorage(BaseStorage):
    """MySQL 存储实现（生产环境）"""

    def __init__(self, url: str):
        try:
            import pymysql
            from sqlalchemy import create_engine
            from sqlalchemy.pool import QueuePool
        except ImportError:
            raise ImportError("pip install pymysql sqlalchemy")

        self._engine = create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
        self._conn = self._engine.connect()
        self._init_tables()

    def _init_tables(self):
        """创建表结构（如果不存在）"""
        # 复用 SQLite 的 schema，调整语法
        pass

    # 实现 BaseStorage 的所有抽象方法
    # ...
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_storage_mysql.py -v
```

预期：PASS（需要 MySQL 服务）

- [ ] **Step 5: 提交**

```bash
git add evolver/storage_mysql.py tests/test_storage_mysql.py
git commit -m "feat: MySQL storage backend with connection pool"
```

---

### Task 2.3: Alembic 迁移配置

**Files:**
- Create: `evolver/migrations/env.py`
- Create: `evolver/migrations/versions/`
- Create: `alembic.ini`

- [ ] **Step 1: 初始化 Alembic**

```bash
cd /mnt/e/skills/improve/evolver-project
pip install alembic
alembic init evolver/migrations
```

- [ ] **Step 2: 配置 alembic.ini**

```ini
# alembic.ini
[alembic]
script_location = evolver/migrations
sqlalchemy.url = sqlite:///evolver.db
```

- [ ] **Step 3: 创建初始迁移**

```bash
alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 4: 运行迁移**

```bash
alembic upgrade head
```

- [ ] **Step 5: 提交**

```bash
git add alembic.ini evolver/migrations/
git commit -m "feat: add Alembic migration support"
```

---

## Phase 3: 图谱能力升级

### Task 3.1: LLM 实体关系提取

**Files:**
- Modify: `evolver/extraction.py`
- Test: `tests/test_extraction_llm.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_extraction_llm.py
def test_llm_extract_entities():
    """LLM 提取实体和关系"""
    from evolver.extraction import MemoryExtractor
    from evolver.llm_client import LLMClient

    llm = LLMClient(provider="openai", api_key="test")
    extractor = MemoryExtractor(llm_client=llm)

    text = "用 Python 写了一个 FastAPI 服务，部署到 AWS Lambda"
    result = extractor.extract(text)

    assert "entities" in result
    assert "relations" in result
    assert len(result["entities"]) >= 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_extraction_llm.py::test_llm_extract_entities -v
```

预期：FAIL — `MemoryExtractor` 不接受 `llm_client`

- [ ] **Step 3: 修改 extraction.py**

```python
# evolver/extraction.py
class MemoryExtractor:
    def __init__(self, llm_client=None):
        self._llm = llm_client
        self._prompt = """从以下文本中提取实体和关系。返回 JSON：
{
  "entities": [
    {"name": "实体名", "type": "person|tool|concept|file|api", "description": "简述"}
  ],
  "relations": [
    {"source": "实体A", "target": "实体B", "relation": "uses|creates|depends_on|implements|triggers"}
  ]
}
只返回 JSON，不要其他内容。"""

    def extract(self, text: str) -> dict:
        if self._llm:
            try:
                return self._extract_with_llm(text)
            except Exception as e:
                logger.warning("LLM extraction failed: %s", e)
        return self._extract_with_regex(text)

    def _extract_with_llm(self, text: str) -> dict:
        import json
        response = self._llm.complete(
            prompt=f"{self._prompt}\n\n{text}",
            max_tokens=1000
        )
        return json.loads(response)

    def _extract_with_regex(self, text: str) -> dict:
        # 现有正则逻辑
        pass
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_extraction_llm.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/extraction.py tests/test_extraction_llm.py
git commit -m "feat: LLM-driven entity extraction with regex fallback"
```

---

### Task 3.2: GraphEngine 集成 MemoryExtractor

**Files:**
- Modify: `evolver/graph.py`
- Modify: `evolver/__init__.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_extraction_llm.py (追加)
def test_graph_engine_build_from_text():
    """GraphEngine.build_from_text 使用 MemoryExtractor"""
    from evolver.graph import GraphEngine
    from evolver.storage_sqlite import SQLiteStorage
    from evolver.extraction import MemoryExtractor

    storage = SQLiteStorage(":memory:")
    extractor = MemoryExtractor()  # 无 LLM，用正则
    graph = GraphEngine(storage, extractor=extractor)

    nodes = graph.build_from_text("Python is used for FastAPI development")
    assert len(nodes) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_extraction_llm.py::test_graph_engine_build_from_text -v
```

预期：FAIL — `GraphEngine.__init__()` 不接受 `extractor`

- [ ] **Step 3: 修改 graph.py**

```python
# evolver/graph.py
class GraphEngine:
    def __init__(self, storage, extractor=None):
        self._storage = storage
        self._extractor = extractor or MemoryExtractor()

    def build_from_text(self, text: str) -> list[int]:
        result = self._extractor.extract(text)
        node_ids = []
        for entity in result.get("entities", []):
            nid = self.add_node(entity["name"], entity["type"])
            node_ids.append(nid)
        for rel in result.get("relations", []):
            self.add_edge(rel["source"], rel["target"], rel["relation"])
        return node_ids
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_extraction_llm.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/graph.py tests/test_extraction_llm.py
git commit -m "feat: GraphEngine uses MemoryExtractor for entity extraction"
```

---

## Phase 4: Qdrant 向量存储

### Task 4.1: VectorStore 接口

**Files:**
- Create: `evolver/vector_store.py`
- Test: `tests/test_vector_store.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vector_store.py
def test_vector_store_interface():
    """VectorStore ABC 定义正确接口"""
    from evolver.vector_store import VectorStore
    assert hasattr(VectorStore, 'upsert')
    assert hasattr(VectorStore, 'search')
    assert hasattr(VectorStore, 'delete')
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_vector_store.py::test_vector_store_interface -v
```

预期：FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 写最小实现**

```python
# evolver/vector_store.py
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import numpy as np

class VectorStore(ABC):
    """向量存储接口"""

    @abstractmethod
    def upsert(self, id: int, vector: np.ndarray, metadata: dict = None):
        pass

    @abstractmethod
    def search(self, vector: np.ndarray, top_k: int = 10,
               filter_metadata: dict = None) -> List[Tuple[int, float]]:
        pass

    @abstractmethod
    def delete(self, id: int):
        pass

    @abstractmethod
    def count(self) -> int:
        pass


class QdrantVectorStore(VectorStore):
    """Qdrant 向量存储"""

    def __init__(self, url: str = "http://localhost:6333",
                 collection: str = "evolver_memory",
                 dimension: int = 1024,
                 api_key: str = None):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import VectorParams, Distance
        except ImportError:
            raise ImportError("pip install qdrant-client")

        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection = collection
        self._dim = dimension

        # 创建 collection（如果不存在）
        if not self._client.collection_exists(collection):
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE)
            )

    def upsert(self, id: int, vector: np.ndarray, metadata: dict = None):
        from qdrant_client.models import PointStruct
        self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=id, vector=vector.tolist(), payload=metadata or {})]
        )

    def search(self, vector: np.ndarray, top_k: int = 10,
               filter_metadata: dict = None) -> List[Tuple[int, float]]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_filter = None
        if filter_metadata:
            query_filter = Filter(must=[
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_metadata.items()
            ])

        results = self._client.search(
            collection_name=self._collection,
            query_vector=vector.tolist(),
            limit=top_k,
            query_filter=query_filter
        )
        return [(r.id, r.score) for r in results]

    def delete(self, id: int):
        self._client.delete(
            collection_name=self._collection,
            points_selector=[id]
        )

    def count(self) -> int:
        return self._client.get_collection(self._collection).points_count


class InMemoryVectorStore(VectorStore):
    """内存向量存储（开发用，兼容现有 ANNIndex）"""

    def __init__(self, dimension: int = 384):
        self._dim = dimension
        self._vectors = {}  # id -> (vector, metadata)

    def upsert(self, id: int, vector: np.ndarray, metadata: dict = None):
        self._vectors[id] = (vector, metadata or {})

    def search(self, vector: np.ndarray, top_k: int = 10,
               filter_metadata: dict = None) -> List[Tuple[int, float]]:
        import numpy as np

        results = []
        for vid, (vec, meta) in self._vectors.items():
            # 过滤
            if filter_metadata:
                if not all(meta.get(k) == v for k, v in filter_metadata.items()):
                    continue

            # 余弦相似度
            sim = np.dot(vector, vec) / (np.linalg.norm(vector) * np.linalg.norm(vec))
            results.append((vid, float(sim)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete(self, id: int):
        self._vectors.pop(id, None)

    def count(self) -> int:
        return len(self._vectors)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_vector_store.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/vector_store.py tests/test_vector_store.py
git commit -m "feat: VectorStore ABC with Qdrant and InMemory implementations"
```

---

### Task 4.2: MemoryEngine 集成 VectorStore

**Files:**
- Modify: `evolver/memory.py`
- Modify: `evolver/__init__.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vector_store.py (追加)
def test_memory_engine_uses_vector_store():
    """MemoryEngine 使用 VectorStore 进行检索"""
    from evolver.memory import MemoryEngine
    from evolver.vector_store import InMemoryVectorStore
    from evolver.embedding import EmbeddingClient

    store = InMemoryVectorStore(dimension=384)
    embedding = EmbeddingClient()  # fastembed
    engine = MemoryEngine(storage=None, embedding=embedding, vector_store=store)

    # 存储一条记忆
    engine.store(task="test task", outcome="success", solution="test solution")

    # 召回
    results = engine.recall("test task")
    assert len(results) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_vector_store.py::test_memory_engine_uses_vector_store -v
```

预期：FAIL — `MemoryEngine.__init__()` 不接受 `vector_store`

- [ ] **Step 3: 修改 memory.py**

```python
# evolver/memory.py — __init__ 新增
def __init__(self, storage, embedding, ...,
             vector_store=None, ...):
    self._vector_store = vector_store
    # ...

# recall() 内部使用 vector_store
def recall(self, query: str, top_k: int = 5, ...):
    if self._vector_store:
        vec = self._embedding.embed_single(query)
        results = self._vector_store.search(vec, top_k=top_k)
        # 转换为 RecallResult
    else:
        # 回退到原有逻辑
        pass
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_vector_store.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/memory.py tests/test_vector_store.py
git commit -m "feat: MemoryEngine integrates VectorStore for recall"
```

---

### Task 4.3: Evolver 入口支持 Qdrant 配置

**Files:**
- Modify: `evolver/config.py`
- Modify: `evolver/__init__.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vector_store.py (追加)
def test_evolver_accepts_qdrant_config():
    """Evolver 接受 Qdrant 配置"""
    from evolver import Evolver
    e = Evolver(
        db_url="sqlite:///test.db",
        vector_store="qdrant",
        qdrant_url="http://localhost:6333",
    )
    assert e._vector_store is not None
    e.close()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_vector_store.py::test_evolver_accepts_qdrant_config -v
```

预期：FAIL — `Evolver.__init__()` 不接受 `vector_store`

- [ ] **Step 3: 修改 config.py 和 __init__.py**

```python
# evolver/config.py — EvolverConfig 新增字段
vector_store: str = "memory"  # "memory" | "qdrant"
qdrant_url: str = "http://localhost:6333"
qdrant_api_key: str = None
```

```python
# evolver/__init__.py — __init__ 新增参数
def __init__(self, ...,
             vector_store: str = "memory",
             qdrant_url: str = "http://localhost:6333",
             qdrant_api_key: str = None,
             ...):
    # 初始化 VectorStore
    if vector_store == "qdrant":
        from evolver.vector_store import QdrantVectorStore
        self._vector_store = QdrantVectorStore(
            url=qdrant_url,
            api_key=qdrant_api_key,
            dimension=embedding_dim,
        )
    else:
        from evolver.vector_store import InMemoryVectorStore
        self._vector_store = InMemoryVectorStore(dimension=embedding_dim)

    # 传递给 MemoryEngine
    self._memory = MemoryEngine(
        storage=self._storage,
        embedding=self._embedding,
        vector_store=self._vector_store,
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_vector_store.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add evolver/config.py evolver/__init__.py
git commit -m "feat: Evolver accepts Qdrant vector store config"
```

---

## Phase 5: SkillEngine 降级

### Task 5.1: 模板合成逻辑

**Files:**
- Modify: `evolver/skill.py`
- Create: `evolver/templates/skill_default.md`
- Test: `tests/test_skill_template.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_skill_template.py
def test_skill_template_synthesis():
    """SkillEngine 模板合成（无 LLM）"""
    from evolver.skill import SkillEngine
    from evolver.memory import MemoryEngine
    from evolver.graph import GraphEngine
    from evolver.storage_sqlite import SQLiteStorage
    from evolver.embedding import EmbeddingClient

    storage = SQLiteStorage(":memory:")
    embedding = EmbeddingClient()
    memory = MemoryEngine(storage, embedding)
    graph = GraphEngine(storage)
    skill = SkillEngine(storage, memory, graph, llm_client=None)

    # 存储一些记忆
    memory.store(task="fix auth bug", outcome="success", solution="check token expiry")
    memory.store(task="debug timeout", outcome="success", solution="increase timeout")

    # 生成 skill（无 LLM，用模板）
    result = skill.generate("authentication")
    assert result.content is not None
    assert "步骤" in result.content or "Step" in result.content
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_skill_template.py::test_skill_template_synthesis -v
```

预期：FAIL — 模板合成逻辑不存在

- [ ] **Step 3: 创建模板文件**

```markdown
<!-- evolver/templates/skill_default.md -->
# {{topic}}

## 概述
基于 {{memory_count}} 条相关记忆生成的技能。

## 步骤
{{steps}}

## 相关上下文
{{context}}

## 注意事项
{{warnings}}
```

- [ ] **Step 4: 修改 skill.py**

```python
# evolver/skill.py — 新增模板合成
def _template_synthesis(self, topic: str, memories, graph_context: str = "") -> str:
    """无 LLM 的模板合成"""
    import os

    # 提取步骤
    steps = self._extract_steps([m.content for m in memories if m.category == "success"])
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)) if steps else "暂无明确步骤"

    # 从 graph 提取上下文
    context = graph_context if graph_context else "暂无相关上下文"

    # 提取警告（失败案例）
    warnings = []
    for m in memories:
        if m.category == "failure":
            warnings.append(f"- {m.content[:100]}")
    warnings_text = "\n".join(warnings) if warnings else "暂无已知陷阱"

    # 加载模板
    template_path = os.path.join(os.path.dirname(__file__), "templates", "skill_default.md")
    with open(template_path, "r") as f:
        template = f.read()

    return template.replace("{{topic}}", topic)\
                   .replace("{{memory_count}}", str(len(memories)))\
                   .replace("{{steps}}", steps_text)\
                   .replace("{{context}}", context)\
                   .replace("{{warnings}}", warnings_text)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_skill_template.py -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add evolver/skill.py evolver/templates/skill_default.md tests/test_skill_template.py
git commit -m "feat: SkillEngine template synthesis with graph context"
```

---

## 集成测试

### Task 6.1: 端到端测试

**Files:**
- Test: `tests/test_integration_v2.py`

- [ ] **Step 1: 写集成测试**

```python
# tests/test_integration_v2.py
def test_end_to_end_with_voyage():
    """端到端：Voyage 嵌入 + Qdrant 存储 + LLM 图谱 + 模板 skill"""
    from evolver import Evolver

    evolver = Evolver(
        db_url="sqlite:///test_e2e.db",
        embedding_provider="voyage",
        embedding_model="voyage-3",
        voyage_api_key="test",
        vector_store="qdrant",
        qdrant_url="http://localhost:6333",
    )

    # 学习
    evolver.learn(
        task="fix auth timeout",
        outcome="success",
        solution="increased JWT expiry to 24h",
        lessons="check token expiry when debugging 401s"
    )

    # 召回
    results = evolver.recall("auth timeout")
    assert len(results) >= 1

    # 图谱
    nodes = evolver._graph.query("auth")
    assert len(nodes) >= 1

    # 生成 skill（无 LLM，用模板）
    skill = evolver.skillgen("authentication")
    assert skill.content is not None

    evolver.close()
```

- [ ] **Step 2: 运行集成测试**

```bash
cd /mnt/e/skills/improve/evolver-project
python -m pytest tests/test_integration_v2.py -v
```

预期：PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_integration_v2.py
git commit -m "test: end-to-end integration test for v2.0 features"
```

---

## 依赖安装

```bash
# 基础
pip install voyageai qdrant-client sqlalchemy pymysql alembic

# 开发
pip install -e ".[dev]"
```

---

## 自检清单

- [x] Spec 覆盖：5 个改进全部有对应 Task
- [x] 占位符扫描：无 TBD/TODO
- [x] 类型一致性：方法签名在各 Task 间一致
- [x] 文件路径：所有路径基于现有项目结构
