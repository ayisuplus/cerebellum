# Supermemory → Evolver 整合方案

## 📊 Supermemory 核心特点分析

### 1. 记忆提取（Memory Extraction）
- 从对话中自动提取事实
- 处理时间变化、矛盾、自动遗忘
- 支持多模态（PDF、图片、视频、代码）

### 2. 用户画像（User Profiles）
- **静态画像**：长期稳定的事实（如"喜欢TypeScript"）
- **动态画像**：最近的上下文（如"正在做API集成"）
- 一次调用，~50ms

### 3. 混合搜索（Hybrid Search）
- RAG + 记忆在单个查询中
- 知识库文档和个性化上下文一起返回

### 4. 连接器（Connectors）
- Google Drive、Gmail、Notion、OneDrive、GitHub
- 自动同步，实时webhooks

### 5. 记忆图谱（Memory Graph）
- 可视化记忆关系
- 文档节点 + 记忆节点 + 关系边

---

## 🎯 Evolver 现有功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 记忆引擎 | ✅ 有 | 基础记忆存储和检索 |
| 图引擎 | ✅ 有 | 知识图谱 |
| 技能引擎 | ✅ 有 | 技能管理 |
| 链接引擎 | ✅ 有 | 记忆链接 |
| 质量检查器 | ✅ 有 | 记忆质量检查 |
| 嵌入索引 | ✅ 有 | 向量检索 |

---

## 🚀 整合方案

### Phase 1：用户画像系统（优先级：高）

**借鉴Supermemory的静态+动态画像模式：**

```python
class UserProfile:
    """用户画像"""
    static: List[str]   # 长期稳定的事实
    dynamic: List[str]  # 最近的上下文
    
    def to_prompt(self) -> str:
        """转换为系统提示"""
        return f"""
用户画像：
静态事实：{', '.join(self.static)}
最近上下文：{', '.join(self.dynamic)}
"""
```

**实现要点：**
- 从记忆中自动提取用户偏好
- 区分长期事实和短期上下文
- 一次调用，快速返回

### Phase 2：混合搜索（优先级：高）

**借鉴Supermemory的RAG + 记忆混合搜索：**

```python
class HybridSearch:
    """混合搜索"""
    def search(self, query: str, mode: str = "hybrid") -> SearchResult:
        if mode == "hybrid":
            # RAG搜索（文档）
            rag_results = self.rag_search(query)
            # 记忆搜索（个性化）
            memory_results = self.memory_search(query)
            # 合并排序
            return self.merge_results(rag_results, memory_results)
        elif mode == "memories":
            return self.memory_search(query)
```

**实现要点：**
- 支持三种搜索模式：hybrid、memories、rag
- 结果合并和排序
- 个性化权重

### Phase 3：时间感知记忆（优先级：中）

**借鉴Supermemory的时间处理机制：**

```python
class TemporalMemory:
    """时间感知记忆"""
    created_at: datetime
    last_accessed: datetime
    decay_rate: float  # 衰减率
    
    def is_expired(self) -> bool:
        """是否过期"""
        return self.decay_rate * (now - self.last_accessed) > threshold
    
    def update_access(self):
        """更新访问时间"""
        self.last_accessed = now
```

**实现要点：**
- 记忆衰减机制
- 自动遗忘过期信息
- 矛盾检测和处理

### Phase 4：连接器系统（优先级：中）

**借鉴Supermemory的连接器架构：**

```python
class Connector:
    """数据源连接器"""
    def sync(self):
        """同步数据"""
        pass
    
    def extract_memories(self, data):
        """从数据中提取记忆"""
        pass

class GitHubConnector(Connector):
    """GitHub连接器"""
    def sync_repos(self):
        """同步仓库"""
        pass
    
    def sync_issues(self):
        """同步Issue"""
        pass
```

**实现要点：**
- 模块化连接器架构
- 自动同步和增量更新
- 统一的数据提取接口

### Phase 5：记忆图谱可视化（优先级：低）

**借鉴Supermemory的Memory Graph：**

```python
class MemoryGraphVisualizer:
    """记忆图谱可视化"""
    def render(self, documents, memories):
        """渲染图谱"""
        # 文档节点（矩形）
        # 记忆节点（六边形）
        # 关系边（相似度、版本链）
        pass
```

**实现要点：**
- Canvas 2D渲染
- 交互式操作（平移、缩放、拖拽）
- 空间过滤

---

## 📋 实施计划

### 第一阶段：核心功能（1-2周）
- [ ] 用户画像系统
- [ ] 混合搜索
- [ ] 时间感知记忆

### 第二阶段：扩展功能（2-3周）
- [ ] GitHub连接器
- [ ] Notion连接器
- [ ] 记忆图谱可视化

### 第三阶段：优化完善（1周）
- [ ] 性能优化
- [ ] 测试覆盖
- [ ] 文档完善

---

## 🎯 预期效果

整合完成后，Evolver将具备：

1. **智能用户画像** - 自动了解用户偏好和上下文
2. **混合搜索** - RAG + 记忆，一次查询获取所有相关信息
3. **时间感知** - 自动遗忘过期信息，处理矛盾
4. **数据连接** - 接入GitHub、Notion等外部数据源
5. **可视化** - 记忆关系图谱，直观展示知识结构

---

## 💡 技术栈

- **后端**：Python（现有）
- **前端**：React + Canvas 2D（记忆图谱）
- **数据库**：SQLite/MySQL（现有）+ 向量数据库
- **API**：RESTful API（现有）

---

## 🚀 下一步

1. 确认方案是否可行
2. 让OpenCode开工实现
3. 分阶段验收
