# Evolver v2.3.0 全面优化设计

**日期：** 2026-05-26
**版本：** v2.3.0
**方案：** 增量重构（3阶段）

---

## 1. 背景

Evolver v2.3.0 是一个 agent 自进化引擎，包含记忆存储、知识图谱、技能生成等功能。项目经过快速迭代后，存在以下问题：

- 启动慢（`import evolver` 加载所有可选依赖）
- 写入延迟高（3次独立embedding调用）
- 模块职责不清（memory.py 970行）
- 代码重复（5个余弦相似度实现）
- 生产就绪不足（无重试、无连接池管理）

## 2. 优化方案

### 方案选择：增量重构

分3个阶段独立实施，每阶段可独立测试和交付：

| 阶段 | 内容 | 风险 | 收益 |
|------|------|------|------|
| Phase 1 | 性能优化 | 低 | 写入速度3x、启动时间50%↓ |
| Phase 2 | 架构重构 | 中 | 可维护性大幅提升 |
| Phase 3 | 生产就绪 | 中 | 生产环境可用 |

---

## Phase 1: 性能优化

### 1.1 延迟导入 `__init__.py`

**问题：** `import evolver` 触发加载所有子模块（fastembed、FlagEmbedding、sentence_transformers、jieba、pymysql），启动慢且可能崩溃。

**方案：** 用 `__getattr__` + `__dir__` 实现延迟加载：

```python
# __init__.py 末尾
_LAZY_IMPORTS = {
    "MySQLStorage": "evolver.storage",
    "EvolverConfig": "evolver.config",
    # ... 所有公开类
}

def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module = __import__(_LAZY_IMPORTS[name], fromlist=[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return list(globals().keys()) + list(_LAZY_IMPORTS.keys())
```

**影响：** `from evolver import Evolver` 仍然可用，但 `import evolver` 不再加载可选依赖。

### 1.2 批量embedding

**问题：** `memory.py:store()` 对 task、lessons、context 分别调用 `embed_single()`，3次嵌入开销。

**方案：** 改为 `embed_batch()`：

```python
# memory.py:store()
texts = [task_content]
if lessons:
    texts.append(lessons)
if context:
    texts.append(context)
vecs = self._embedding.embed_batch(texts)
task_vec = vecs[0]
lessons_vec = vecs[1] if len(vecs) > 1 else None
context_vec = vecs[2] if len(vecs) > 2 else None
```

**影响：** 写入延迟降低 ~60%（3次→1次调用）。

### 1.3 提取公共工具函数

**问题：** 5个余弦相似度实现、4个JSON提取实现、3个tokenize实现。

**方案：** 统一到 `utils.py`：

```python
# utils.py 新增
def cosine_similarity(a, b):
    """统一余弦相似度计算"""
    a, b = np.asarray(a), np.asarray(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def extract_json_from_llm(text):
    """从LLM输出中提取JSON"""
    # 1. 尝试直接解析
    # 2. 尝试```json```代码块
    # 3. 尝试正则提取
    ...
```

**清理：**
- 删除 `memory.py:_cosine_similarity`、`dedup.py:_cosine_distance`、`skill_library.py:_cosine_similarity`
- 删除 `graph.py:_parse_json`、`extraction.py:_parse_json`、`compiler.py:_parse_facts`
- 统一调用 `utils.cosine_similarity()` 和 `utils.extract_json_from_llm()`

### Phase 1 验收标准

| 指标 | 当前 | 目标 |
|------|------|------|
| `import evolver` 时间 | ~3s | <1s |
| `learn()` 写入延迟 | ~2s | <1s |
| 余弦相似度实现数 | 5 | 1 |
| JSON提取实现数 | 4 | 1 |

---

## Phase 2: 架构重构

### 2.1 拆分 `memory.py`（970行）

**问题：** `memory.py` 同时承担存储CRUD和多信号检索管道，职责过多。

**方案：** 拆分为两个模块：

```
memory.py (存储/CRUD, ~500行)
├── store()          — 事务性写入
├── forget()         — 删除记忆
├── reconsolidate()  — 修正记忆
├── suggest()        — 主动建议
├── interference_decay() — 干扰衰减
├── update_lifecycle()   — 生命周期更新
├── build_index()    — 构建ANN索引
└── set_deduplicator(), set_closet()

retrieval.py (检索管道, ~470行)
├── recall()         — 主检索入口
├── recall_light()   — L2轻量检索
├── recall_deep()    — L3深度检索
├── _recall_semantic()  — 语义向量检索
├── _recall_graph()     — 知识图谱检索
├── _recall_links()     — 链接 boost 检索
├── _recall_bm25()      — BM25关键词检索
├── _rrf_fusion()       — 倒数排名融合
├── _weighted_fusion()  — 加权融合
├── _rerank()           — 二阶段重排
└── _bm25_score()       — BM25评分
```

**依赖关系：** `retrieval.py` 依赖 `memory.py`（通过 `MemoryEngine` 实例），`memory.py` 不依赖 `retrieval.py`。

### 2.2 清理 `storage_base.py`

**问题：** SELECT 列列表在8处重复，修改字段需改8个地方。

**方案：** 定义列常量：

```python
# storage_base.py
_MEMORY_COLUMNS = (
    "id, content, category, tags, embedding, source, importance, "
    "access_count, content_hash, lifecycle, created_at, updated_at"
)

# 所有 SELECT 语句使用
f"SELECT {_MEMORY_COLUMNS} FROM memories WHERE ..."
```

### 2.3 修复封装

**问题：** `LinkEngine._create_entity_links()` 直接访问 `self._memory._ann`，破坏封装。

**方案：** 在 `MemoryEngine` 新增公共方法：

```python
# memory.py
def search_similar(self, query_vec, top_k=10, threshold=0.0):
    """公共相似度搜索接口"""
    if not self._ann_built:
        self.build_index()
    return self._ann.search(query_vec, top_k, threshold)
```

```python
# link.py — 改为调用公共方法
similar = self._memory.search_similar(vec, top_k=20)
```

### 2.4 修复 `learn_extracted()` 事务安全

**问题：** `__init__.py:learn_extracted()` 绕过 `MemoryEngine.store()` 事务，直接调用 `storage.insert_memory()`。

**方案：** 改为调用 `MemoryEngine.store()` 或复用其事务逻辑：

```python
# __init__.py
def learn_extracted(self, text, source="extract"):
    facts = self._extractor.extract(text)
    # 复用 MemoryEngine 的事务写入
    ids = self._memory.store(
        task=fact_text, outcome="extracted",
        source=source, tags=tags,
    )
```

### Phase 2 验收标准

| 指标 | 当前 | 目标 |
|------|------|------|
| memory.py 行数 | 970 | <500 |
| retrieval.py 行数 | — | <500 |
| storage_base.py SELECT重复 | 8 | 1 |
| LinkEngine 直接访问私有属性 | 2处 | 0 |
| learn_extracted 事务安全 | 否 | 是 |

---

## Phase 3: 生产就绪

### 3.1 LLM重试机制

**问题：** `LLMClient` 使用 `urllib.request` 无重试逻辑，429/503 直接失败。

**方案：** 添加重试装饰器：

```python
# llm_client.py
import time
from functools import wraps

def retry(max_retries=3, backoff=1.0, retry_on=(429, 503)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    if hasattr(e, 'code') and e.code in retry_on:
                        wait = backoff * (2 ** attempt)
                        logger.warning(f"Retry {attempt+1}/{max_retries} after {wait}s")
                        time.sleep(wait)
                    else:
                        raise
        return wrapper
    return decorator

@retry(max_retries=3, backoff=1.0, retry_on=(429, 503))
def _call_openai(self, ...):
    ...
```

### 3.2 连接池改进

**问题：** `MySQLStorage` 手写连接池缺少最大存活时间、健康检查、指标。

**方案：** 添加连接生命周期管理：

```python
# storage.py
class Connection:
    def __init__(self, conn, created_at):
        self.conn = conn
        self.created_at = created_at
    
    @property
    def is_expired(self):
        return time.time() - self.created_at > MAX_CONNECTION_AGE  # 3600s

class MySQLStorage:
    def _get_connection(self):
        with self._lock:
            while not self._pool.empty():
                conn = self._pool.get_nowait()
                if conn.is_expired:
                    self._close_connection(conn)
                    continue
                return conn
            return self._create_connection()
    
    def stats(self):
        return {
            "pool_size": self._pool.qsize(),
            "active": self._active_count,
            "total_created": self._total_created,
        }
```

### 3.3 Schema迁移

**问题：** `SQLiteStorage._ensure_schema()` 使用 silent `ALTER TABLE` 吞所有异常。

**方案：** 添加版本跟踪：

```python
# storage_sqlite.py
SCHEMA_VERSION = 2  # 递增

MIGRATIONS = [
    # version 1 → 2: 添加 confidence 列
    "ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 1.0",
]

def _migrate_schema(self):
    current = self._get_schema_version()
    for i, sql in enumerate(MIGRATIONS[current:], start=current):
        try:
            self._execute(sql)
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                raise StorageError(f"Migration {i+1} failed: {e}")
        self._set_schema_version(i + 1)
```

### 3.4 错误处理改进

**问题：** 多处 `except Exception` 吞掉真实错误。

**方案：** 缩小异常捕获范围：

```python
# __init__.py:auto_distill()
except (OSError, ValueError) as e:  # 替代 except Exception
    logger.warning("Auto-distill check failed: %s", e)
except Exception:
    logger.exception("Unexpected error in auto-distill")
    raise  # 不吞掉未知错误
```

### Phase 3 验收标准

| 指标 | 当前 | 目标 |
|------|------|------|
| LLM重试 | 无 | 3次重试+指数退避 |
| 连接最大存活时间 | 无 | 3600s |
| Schema迁移 | silent ALTER | 版本跟踪 |
| except Exception 吞错误 | ~15处 | <5处 |

---

## 4. 实施计划

### Phase 1（预计2-3小时）
1. 延迟导入 `__init__.py`
2. 批量embedding `memory.py`
3. 提取公共工具函数到 `utils.py`
4. 清理重复实现
5. 运行测试验证

### Phase 2（预计3-4小时）
1. 拆分 `memory.py` → `memory.py` + `retrieval.py`
2. 清理 `storage_base.py` SELECT重复
3. 修复 `LinkEngine` 封装
4. 修复 `learn_extracted()` 事务安全
5. 运行测试验证

### Phase 3（预计2-3小时）
1. 添加LLM重试机制
2. 改进连接池管理
3. 添加Schema迁移
4. 改进错误处理
5. 运行测试验证

---

## 5. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 拆分memory.py引入循环依赖 | 高 | 使用TYPE_CHECKING guard，保持单向依赖 |
| 批量embedding API不兼容 | 中 | 检查所有embedding provider的batch接口 |
| Schema迁移破坏现有数据 | 中 | 先备份再迁移，添加回滚机制 |
| 延迟导入破坏现有import | 中 | 保留 `__all__` 定义，确保向后兼容 |

---

## 6. 相关文档

- [Evolver v2 Design](2026-05-23-evolver-v2-design.md)
- [Progressive Memory Design](2026-05-22-progressive-memory-design.md)
- [Evolver v0.10 Analysis](../../v010-analysis-report.md)
