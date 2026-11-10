# 双后端统一抽象 — Archive Layer Dual Backend

## Requirement

**What**: Archive layer（死数据归档层）当前仅支持 MySQL 后端。用户需要开发环境零配置、生产环境高性能。必须支持 SQLite（轻量/开发）和 MySQL（生产）两种后端，统一接口。

**For whom**: 
- 开发者：本地开发不需要 MySQL，SQLite 零配置
- 生产用户：MySQL 保持高性能和全文检索

**Constraints**:
- `store()` 接口对两端统一，调用者不需要关心后端类型
- SQLite 不需要额外依赖（Python 内置 sqlite3）
- MySQL 继续保持可选的 `pymysql` 依赖
- `data_url` 参数自动检测 URL scheme 选择后端
- 向后兼容：现有 MySQL-only 用户不受影响，`data_url="mysql://..."` 继续工作

## Specification

### 1. Abstract Backend Interface

```python
class ArchiveBackend(ABC):
    @abstractmethod
    def archive(self, content: str, kind: str, tags=None, source=None, ref=None, meta=None) -> int: ...
    @abstractmethod
    def get_archive(self, archive_id: int) -> dict | None: ...
    @abstractmethod
    def search_archive(self, query: str, limit: int = 20) -> list[dict]: ...
    @abstractmethod
    def close(self): ...
```

**Rationale**: ABC 让两种实现保证接口一致。不需要更多方法——当前三种操作（写、按 id 读、全文搜）覆盖所有需求。

### 2. SQLiteArchiveBackend

新建 `evolver/archive_sqlite.py`：

- URL scheme: `sqlite:///path/to/archive.db` 或 `sqlite:///:memory:`
- 表结构与 MySQL 等价（id BIGINT PK, content TEXT, kind VARCHAR, ref, tags TEXT as JSON, source, meta TEXT as JSON, created_at DATETIME）
- FTS5 full-text index on content
- `archive()`: INSERT + return lastrowid
- `get_archive()`: SELECT by id, JSON decode tags/meta
- `search_archive()`: FTS5 MATCH, fallback to LIKE
- `close()`: close connection
- 无连接池（SQLite 单连接，WAL 模式）
- 线程安全：threading.Lock 保护写操作

**Rationale**: SQLite FTS5 是内置全文检索方案，零依赖。单连接 + WAL 模式适合单进程归档场景。

### 3. MySQLArchiveBackend

将现有 `ArchiveStore` 重命名为 `MySQLArchiveBackend`，放在 `evolver/archive_mysql.py`：

- 现有逻辑不动，仅类名和文件重命名
- 保持连接池、pymysql、ngram 全文索引

**Rationale**: 最小化现有代码变动，只改类名和文件名，内部逻辑完全不变。

### 4. Factory Function

```python
def create_archive_backend(data_url: str) -> ArchiveBackend:
    if data_url.startswith("mysql://"):
        from .archive_mysql import MySQLArchiveBackend
        return MySQLArchiveBackend(data_url)
    elif data_url.startswith("sqlite://"):
        from .archive_sqlite import SQLiteArchiveBackend
        return SQLiteArchiveBackend(data_url)
    else:
        raise ValueError("data_url must start with mysql:// or sqlite://")
```

**Rationale**: 自动检测 URL scheme，调用者零配置。保持 lazy import，MySQL 和 pymysql 仍然是可选依赖。

### 5. Evolver.__init__ Changes

当前 `__init__` 强制 `data_url` 必须是 `mysql://`。改为：

```python
if data_url:
    from .archive_store import create_archive_backend
    self._archive = create_archive_backend(data_url)
```

去掉对 MySQL 的强制校验，让 factory 处理。

### 6. CLI Changes

`evolver archive` 和 `evolver query-archive` 命令的 `--data-url` 选项现在同时支持 `mysql://` 和 `sqlite://`。

自动检测，不需要用户改命令行参数。

### 7. Test Changes

- 现有 MySQL mock tests 保持，改 import 路径
- 新增 `tests/test_archive_sqlite.py`：SQLiteArchiveBackend 的实库测试
  - `:memory:` 模式下测试 archive → get → search 全流程
  - 测试 tags/meta JSON 序列化
  - 测试 null 字段
  - 测试 FTS5 搜索

### Non-Functional

| Concern | Criterion |
|---------|-----------|
| 性能 | SQLite WAL 模式，FTS5 索引。MySQL 保持连接池。 |
| 兼容性 | 现有 `data_url="mysql://..."` 调用完全向后兼容 |
| 可测试性 | SQLite 用 `:memory:` 零配置测试，MySQL 用 mock |
| 依赖 | SQLite 零新增依赖。MySQL 保持可选 `pymysql` |

### Out of Scope (Deferred)

- archive record update / delete 操作（没有此需求）
- archive layer migration between backends（首次实现不包含）
- S3/blob archive backend（不在需求内）

## Architecture Decision

**Why dual-backend over single abstraction**: 两个后端代码量小（SQLite < 150 行），不增加维护负担。共同接口保证互换性。不需要额外的适配层或 ORM。

**Why not SQLAlchemy**: 增加依赖，两头不讨好（SQLite 和 MySQL 的 SQL 差异需要处理，SQLAlchemy 抽象层反而不如直接写 SQL 简洁）。
