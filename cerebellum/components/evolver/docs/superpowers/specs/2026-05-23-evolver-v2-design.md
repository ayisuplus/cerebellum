# Evolver v2.0 — 五大改进设计文档

> 日期：2026-05-23 | 方案：渐进增强 | 状态：待审阅

---

## 一、执行摘要

Evolver v2.0 是一次**架构级增强**，核心目标：生产就绪。五大改进覆盖嵌入模型、并发安全、图谱能力、向量存储、SkillEngine 降级。整体方案保持现有接口不变，内部实现升级，外部无感。

**依赖顺序**：嵌入模型 → 并发安全 → 图谱能力 → ANN 持久化 → SkillEngine 降级

---

## 二、改进 1：嵌入模型支持

### 2.1 现状

`EmbeddingClient` 硬编码 `BAAI/bge-small-en-v1.5`，384 维，本地 fastembed。中文场景偏弱。

### 2.2 设计

`EmbeddingClient` 内部抽象出 provider 接口，通过配置切换。

```
EmbeddingClient
├── FastEmbedProvider（现有，本地模型）
├── VoyageProvider（默认，voyage-3，1024维）
└── OpenAIProvider（备选，text-embedding-3-small）
```

### 2.3 配置

```python
evolver = Evolver(
    db_url="sqlite:///evolver.db",
    embedding_provider="voyage",  # or "fastembed", "openai"
    embedding_model="voyage-3",   # provider-specific
    embedding_dim=1024,           # 自动检测，可覆盖
    voyage_api_key="pa-...",      # or VOYAGE_API_KEY env
)
```

### 2.4 关键点

- `embed_single()` 和 `embed_batch()` 接口不变，外部无感
- `vector_to_bytes()` / `bytes_to_vector()` 根据 dim 自动适配
- 降级：API 失败 → 重试 2 次 → 回退 fastembed（如果安装了）
- 维度变更时自动检测：现有数据库 dim 和新 provider dim 不匹配 → 警告 + 建议重建

### 2.5 新增文件

- `evolver/embedding_providers.py` — provider 接口 + 三个实现
- `evolver/embedding.py` — 修改为使用 provider

---

## 三、改进 2：并发安全（MySQL 生产后端）

### 3.1 现状

`SQLiteStorage` 单连接，无锁保护。多 agent 写入会冲突。

### 3.2 设计

```
Storage (ABC) — 已有，不变
├── SQLiteStorage — 开发用，加 WAL + 线程锁
└── MySQLStorage — 生产用，连接池 + 读写分离
```

### 3.3 MySQL 改进

- `SQLAlchemy` 连接池（pool_size=10, max_overflow=20）
- 写操作自动重试（DeadlockError → 重试 3 次）
- 读操作走 replica（如果配置了 read_url）
- 事务隔离级别：READ COMMITTED（MySQL 默认）

### 3.4 SQLite 改进（开发体验优化）

- 启用 WAL 模式（`PRAGMA journal_mode=WAL`）
- 写操作加 `threading.Lock()`
- 读操作不加锁（WAL 支持并发读）

### 3.5 配置

```python
# 生产
evolver = Evolver(db_url="mysql://user:pass@host:3306/evolver?charset=utf8mb4")

# 开发（不变）
evolver = Evolver(db_url="sqlite:///evolver.db")
```

### 3.6 关键点

- `BaseStorage` 接口不变，MemoryEngine/GraphEngine 无感
- MySQL 表结构用 Alembic 管理迁移
- 连接池在 `evolver.close()` 时正确释放

### 3.7 新增/修改文件

- `evolver/storage_mysql.py` — 新增，MySQL 实现
- `evolver/storage_sqlite.py` — 修改，加 WAL + 锁
- `evolver/migrations/` — 新增，Alembic 迁移脚本
- `evolver/storage_base.py` — 可能新增方法签名

---

## 四、改进 3：图谱能力升级（LLM 驱动实体提取）

### 4.1 现状

`GraphEngine._extract_entities()` 用正则 `r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b'`，只能抓英文大写词，中文失效。

### 4.2 设计

```
GraphEngine.build_from_text(text)
    ↓
MemoryExtractor.extract(text, llm_client)
    ↓
返回 entities[] + relations[]
    ↓
storage.insert_node() / insert_edge()
```

### 4.3 Prompt 设计

```
从以下文本中提取实体和关系。返回 JSON：
{
  "entities": [
    {"name": "实体名", "type": "person|tool|concept|file|api", "description": "简述"}
  ],
  "relations": [
    {"source": "实体A", "target": "实体B", "relation": "uses|creates|depends_on|implements|triggers"}
  ]
}
```

### 4.4 关键点

- `MemoryExtractor` 复用现有 `LLMClient`，不需要新 API key
- 提取结果去重：同名实体合并，同边关系合并权重
- 中文支持：LLM 天然支持中文实体提取
- 降级：LLM 失败 → 回退正则（现有逻辑保留）
- 批量优化：多条记忆打包成一个 prompt 提取，减少 API 调用

### 4.5 修改文件

- `evolver/extraction.py` — 修改，加入 LLM 提取逻辑
- `evolver/graph.py` — 修改，使用 MemoryExtractor

---

## 五、改进 4：ANN 索引持久化（Qdrant）

### 5.1 现状

`ANNIndex` 用 hnswlib，内存中构建，重启后需要全量重建。

### 5.2 设计

```
VectorStore (ABC)
├── QdrantVectorStore（生产，默认）
└── InMemoryVectorStore（开发，兼容现有）
```

### 5.3 Qdrant 集成

- Collection 按项目隔离（`evolver_{slugify(memory_dir)}`，默认 `evolver_memory`）
- 向量维度自动检测（从 embedding provider 获取）
- 支持 metadata 过滤（category, tags, lifecycle）
- 持久化：Qdrant 自带磁盘持久化，重启不丢数据

### 5.4 配置

```python
evolver = Evolver(
    db_url="mysql://...",
    vector_store="qdrant",
    qdrant_url="http://localhost:6333",  # or QDRANT_URL env
    qdrant_api_key="...",               # 可选，云服务用
)
```

### 5.5 关键点

- `recall()` 内部改为调用 `VectorStore.search()`
- `store()` 内部改为调用 `VectorStore.upsert()`
- `interference_decay()` 用 Qdrant 的 `search` 替代全量矩阵
- 迁移工具：现有 `evolver.ann` → Qdrant 一次性导入
- 降级：Qdrant 不可用 → 回退内存 hnswlib

### 5.6 新增文件

- `evolver/vector_store.py` — VectorStore ABC + QdrantVectorStore + InMemoryVectorStore
- `evolver/migrations/ann_to_qdrant.py` — 迁移工具

---

## 六、改进 5：SkillEngine 降级（LLM + 模板混合）

### 6.1 现状

`_synthesize_with_llm()` 是核心路径，无 LLM 时退化为模板拼接，质量差距大。

### 6.2 设计

```
SkillEngine.generate(topic)
    ↓
_try_llm_synthesis(topic, memories)
    ├─ 成功 → 返回高质量 skill
    └─ 失败 → _template_synthesis(topic, memories)
                ├─ 从 memories 提取步骤（已有 _extract_steps）
                ├─ 从 graph 提取相关实体和关系
                ├─ 组装成结构化 skill（步骤 + 上下文 + 注意事项）
                └─ 返回中等质量 skill
```

### 6.3 模板提升点

- 从 graph 提取相关实体，加入 skill 上下文
- 从 memories 提取成功/失败模式，生成"注意事项"
- 支持 skill 模板变量（`{{steps}}`, `{{context}}`, `{{warnings}}`）
- 模板文件可用户自定义（`templates/skill_default.md`）

### 6.4 关键点

- `_synthesize_with_llm` 加 try-except，捕获所有 LLM 错误
- 模板质量提升不依赖 LLM，零 API 成本
- 用户可通过 `skill_output_dir/templates/` 自定义模板

### 6.5 修改文件

- `evolver/skill.py` — 修改，加入模板合成逻辑
- `evolver/templates/skill_default.md` — 新增，默认模板

---

## 七、依赖顺序

```
1. 嵌入模型支持 ← 基础层，其他都依赖它
2. 并发安全 ← 基础设施，写入安全
3. 图谱能力升级 ← 依赖 1（更好的嵌入）+ 2（安全写入）
4. ANN 索引持久化 ← 依赖 2
5. SkillEngine 降级 ← 可随时做
```

---

## 八、测试策略

每个改进独立测试：

1. **嵌入模型** — 测试 provider 切换、降级、维度检测
2. **并发安全** — 测试 MySQL 连接池、SQLite WAL、多线程写入
3. **图谱能力** — 测试 LLM 提取、去重、中文支持、降级
4. **ANN 持久化** — 测试 Qdrant 存储/检索、迁移工具、降级
5. **SkillEngine** — 测试模板合成、graph 上下文、降级

集成测试：端到端 learn → recall → skillgen 流程。

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Qdrant 服务不可用 | 向量搜索降级 | 回退内存 hnswlib |
| LLM API 限流 | 图谱提取变慢 | 批量 prompt + 重试 |
| MySQL 连接池耗尽 | 写入失败 | 连接池监控 + 自动回收 |
| 嵌入维度变更 | 现有数据不兼容 | 迁移工具 + 警告 |
