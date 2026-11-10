# 数据归档层(Archive Layer)设计

日期:2026-05-29
状态:已认可,待实现
分支:dev

## 1. 背景与动机

Evolver 现有架构是**单后端**:`Evolver` 按 `db_url` 的 scheme 选 SQLite *或* MySQL,二选一。
`BaseStorage`(抽象)派生出 `SQLiteStorage` / `MySQLStorage`,两者 schema 完全相同、可互换
(SQLite=开发,MySQL=生产)。所有数据(memories / facts / skills / graph / interactions /
links / distill_runs)进同一个库。

记忆"分层"现状有两个维度:

- `Memory.category` 字段(success / failure / insight / pattern)是**语义分类**。
- `MemoryStack` 的 L0–L3 是**读取时的 token 预算分层**,不是存储分层。

Skill 生成(`SkillEngine.generate`)走 `memory.recall(topic)` + 图谱节点,从经验记忆里取素材。

### 动机(用户确认)

- **A 性能/容量**:纯数据(记录、图片)体量大,不应拖慢经验库的检索/embedding。
- **B 关注点分离**:经验是"活"的会被检索、生成 skill;数据是"死"的归档,概念上彻底隔离。

由此引入一个**独立、可选、懒连接**的数据归档层(Archive Layer),与经验层并行、互不依赖。

## 2. 决策回执

| 决策点 | 选择 |
|---|---|
| 动机 | A 性能/容量 + B 关注点分离 |
| 数据访问模式 | B 全文/结构化翻查,不要向量检索 |
| 归类机制 | A 显式双入口(`learn` 进经验库 vs `archive` 进数据库) |
| 跨库关联 | 无(经验与数据彻底独立,不互相引用) |
| 图片存储 | A 只存引用(路径/URL + 元数据),文件留磁盘/对象存储 |
| 配置/连接 | D 可选 + 懒连接 |
| 第一版 API | A 最小集:`archive` / `search_archive` / `get_archive` |
| 数据层实现 | 方案一:独立 `ArchiveStore` 类(不继承 BaseStorage) |
| 全文解析器 | A `ngram` parser + `LIKE` 兜底 |
| 返回类型 | A 裸 dict(不加 dataclass) |

## 3. 整体架构与数据流

```
                    ┌────────────────────────────────────────┐
                    │              Evolver (facade)            │
                    └────────────────────────────────────────┘
                       │                              │
         经验层(活)│                              │ 数据层(死/封存)
                       ▼                              ▼
        ┌──────────────────────────┐    ┌──────────────────────────┐
        │  self._storage           │    │  self._archive            │
        │  BaseStorage             │    │  ArchiveStore (新)        │
        │   → SQLiteStorage        │    │   → MySQL (LONGTEXT+引用) │
        │  memories/graph/skills/  │    │   archive 单表            │
        │  facts/links/...         │    │   FULLTEXT 全文检索        │
        │  embedding + ANN + skill │    │   懒连接、无向量、无 skill │
        └──────────────────────────┘    └──────────────────────────┘
              learn() / recall()              archive() / search_archive()
              / skillgen() ...                / get_archive()
```

三条路径彼此不交叉:

1. `evolver.learn(...)` → 经验层 SQLite(完全不变)。
2. `evolver.archive(content, kind, tags, source, ref, meta)` → 首次调用触发 MySQL 懒连接 → 写入 `archive` 表。
3. `evolver.search_archive(query)` / `get_archive(id)` → MySQL FULLTEXT / 主键查询。

关键边界:

- 两层**无跨库外键、无关联**,可独立备份、独立宕机互不影响。
- 数据层**不碰** embedding / ANN / graph / skill 生成。
- 没配 `data_url` 时 `self._archive = None`,调用 archive 类方法抛清晰错误,经验层照常工作。

## 4. 数据库 Schema(`archive` 表)

`MySQLStorage` 现状**没有自动建表逻辑**(只有 `connect()` 预热连接池),假设生产表已存在。
因此 `ArchiveStore` 必须**自己负责建表**(`CREATE TABLE IF NOT EXISTS`),首次懒连接时执行一次。

```sql
CREATE TABLE IF NOT EXISTS archive (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    content     LONGTEXT,                          -- 文本记录正文(日志/对话/结构化文本)
    kind        VARCHAR(64) NOT NULL,              -- 数据类别: 'record' | 'image' | 'log' | ...
    ref         VARCHAR(1024),                     -- 图片/大文件的路径或 URL(只存引用)
    tags        JSON,                              -- 标签数组,与经验层 tags 风格一致
    source      VARCHAR(255),                      -- 来源标识
    meta        JSON,                              -- 自由扩展元数据(尺寸、mime、原始时间戳等)
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FULLTEXT KEY ft_content (content) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

字段取舍:

- `content` 用 `LONGTEXT`:只存文本与引用,不存二进制。图片走 `ref`。
- `kind` 必填:调用方显式标注类别,字段留存便于后续按 kind 过滤(第一版不暴露过滤入口)。
- `ref` 可空:纯文本记录用不到。
- `tags` / `meta` 用 MySQL 原生 `JSON` 类型(MySQL 5.7+);读写 `json.dumps/loads`。
- `FULLTEXT KEY ft_content WITH PARSER ngram`:中文友好全文索引,需 MySQL 5.7.6+。

全文检索策略:优先 `MATCH(content) AGAINST(...)`,异常或无结果时回退 `LIKE '%kw%'`
(照搬经验层 `search_facts_fts` 已有的"FTS 失败回退 LIKE"成熟模式)。

## 5. `ArchiveStore` 类与 API

新文件 `evolver/archive_store.py`。**不继承 `BaseStorage`**,彻底独立。
复用 `storage.py` 的纯函数 `_parse_mysql_url` 与 `Connection` 包装类(import 复用,不重写)。
连接池采用**内嵌精简池**(零侵入优先,避免改动 `MySQLStorage`)。

```python
class ArchiveStore:
    """死数据归档层。MySQL 后端,懒连接,全文检索,无向量/无 skill。"""

    def __init__(self, mysql_url: str, pool_size: int = 2):
        # 仅解析+保存参数,不建连接(懒连接)
        self._url = mysql_url
        self._params = _parse_mysql_url(mysql_url)   # 复用 storage.py
        self._pool = None            # 首次使用时才建
        self._schema_ready = False
        self._lock = threading.Lock()

    def _ensure_connected(self):
        """首次调用时建连接池 + 建表(双重检查锁)。"""

    # --- 公开 API(最小集)---

    def archive(self, content: str, kind: str,
                tags: list = None, source: str = None,
                ref: str = None, meta: dict = None) -> int:
        """写入一条归档记录,返回 id。首次调用触发懒连接。"""

    def search_archive(self, query: str, limit: int = 20) -> list[dict]:
        """全文检索: MATCH...AGAINST,异常/空结果回退 LIKE。"""

    def get_archive(self, archive_id: int) -> dict | None:
        """按 id 取一条。"""

    def close(self):
        """关闭连接池(若已建)。未连接则 no-op。"""
```

设计要点:

- **懒连接**:构造函数零 I/O,只解析 URL;`_ensure_connected()` 双重检查锁,首次 `archive`/`search`/`get` 时才建池 + 建表。
- **连接池**:小池(默认 2),数据层访问频率低。内嵌精简池以保经验层零改动。
- **返回裸 dict**:`search_archive` 返回 `[{id, content, kind, ref, tags, source, meta, created_at}]`,`tags`/`meta` 已 `json.loads`。
- **不暴露** `begin/commit/rollback`:单条写入自动提交,数据层无多表事务需求。
- `models.py` **不加** `ArchiveRecord` dataclass,保持数据层轻量。

## 6. Evolver 装配与配置接线

`evolver/__init__.py` 改动,全部向后兼容——不传 `data_url` 时行为与现状完全一致。

### 6.1 构造函数新增参数

```python
def __init__(self, mysql_url=None, db_url=None,
             data_url: str = None,          # 新增:数据层 MySQL URL,可选
             ...):                          # 其余参数全不动
```

### 6.2 装配逻辑(在现有 storage 初始化之后)

```python
# 经验层:完全不变(现有 SQLite/MySQL 自动检测逻辑原样保留)

# 数据层:可选 + 懒连接
self._archive = None
if data_url:
    if not data_url.startswith("mysql://"):
        raise ValueError("data_url must be a mysql:// URL")
    if MySQLStorage is None:        # pymysql 未安装
        raise ImportError("pymysql is required for the archive layer. pip install evolver[mysql]")
    from evolver.archive_store import ArchiveStore
    self._archive = ArchiveStore(data_url)   # 构造零 I/O,不连接
```

- `data_url` 只接受 `mysql://`。
- 构造时不连接(懒连接);`pymysql` 缺失时立刻报错。
- `EvolverConfig` 加 `data_url: str | None = None`,`from_env` 读 `EVOLVER_DATA_URL`。

### 6.3 facade 方法(对齐现有 `add_fact`/`search_facts` 风格)

```python
def archive(self, content, kind, tags=None, source=None, ref=None, meta=None) -> int:
    if self._archive is None:
        raise EvolverError("Archive layer not configured. Pass data_url= to enable it.")
    return self._archive.archive(content, kind, tags=tags, source=source, ref=ref, meta=meta)

def search_archive(self, query, limit=20) -> list[dict]:
    if self._archive is None:
        raise EvolverError("Archive layer not configured. Pass data_url= to enable it.")
    return self._archive.search_archive(query, limit=limit)

def get_archive(self, archive_id) -> dict | None:
    if self._archive is None:
        raise EvolverError("Archive layer not configured. Pass data_url= to enable it.")
    return self._archive.get_archive(archive_id)
```

### 6.4 `close()` 改动

```python
def close(self):
    ...
    self._storage.close()
    if self._archive is not None:      # 仅当已配置才关
        self._archive.close()          # 内部:未连接则 no-op
```

`close_async()` 同样补一行。`__all__` 视需要导出 `ArchiveStore`。
未配置时的错误用 `EvolverError`,消息明确告知"传 `data_url=` 开启"。

## 7. 测试策略

新增 `tests/test_archive.py`,对齐现有 pytest 风格。

### 7.1 单元测试(不连真实 MySQL,用 mock/fake)

- `test_construct_no_io` — 构造不发起任何连接(`_pool is None`)。
- `test_lazy_connect_on_first_use` — 首次 `archive()` 才触发 `_ensure_connected`(只建一次)。
- `test_double_check_lock` — 并发首次调用只建一次池/表。
- `test_archive_returns_id` — 写入返回 lastrowid。
- `test_tags_meta_json_roundtrip` — `tags`/`meta` 写入 `json.dumps`、读取 `json.loads` 还原。
- `test_search_fallback_to_like` — `MATCH...AGAINST` 抛异常时回退 `LIKE`。
- `test_get_archive_not_found` — 返回 `None`。
- `test_close_when_never_connected` — 未连接时 `close()` no-op。

### 7.2 Evolver facade 集成测试(增补 `tests/test_evolver.py`)

- `test_archive_not_configured_raises` — 不传 `data_url` 调三个方法抛 `EvolverError`,消息含 "data_url"。
- `test_archive_layer_optional` — 不传 `data_url`,`learn`/`recall` 完全正常(向后兼容回归)。
- `test_invalid_data_url_scheme` — `data_url` 非 `mysql://` 抛 `ValueError`。
- `test_close_with_archive` — 配了 archive 时 `close()` 同时关两层。

### 7.3 可选真实 MySQL 测试(标记跳过)

`@pytest.mark.skipif(not os.environ.get("EVOLVER_TEST_MYSQL"))` 守卫,无 MySQL 时自动跳过。
覆盖真实建表(含 ngram parser)、中文全文检索、LIKE 兜底。

### 7.4 边界用例

- `pymysql` 未安装但传 `data_url` → 构造期 `ImportError`。
- 中文内容 + ngram 检索;ngram 不可用 → LIKE 兜底命中。
- `content` 为空但传 `ref`(纯图片记录)→ 允许,`kind='image'`。
- 超长 `content`(LONGTEXT 边界)→ 不截断。
- `tags=None` / `meta=None` → 存 NULL,读回 `[]` / `None`。

验证命令:`pytest tests/test_archive.py tests/test_evolver.py -v`

## 8. 不在本次范围(YAGNI)

- 数据层不做向量检索、不进 ANN、不参与 skill 生成。
- 不做跨库关联(经验引用数据)。
- 不做图片 BLOB 入库(只存引用)。
- 不做 `list_archive` 结构化过滤、`delete_archive`、批量清理。
- 不做 CLI 子命令。
- 不加 `ArchiveRecord` dataclass。
