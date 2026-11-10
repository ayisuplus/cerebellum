# 升级方案目录说明

## 文件结构

```
升级方案/
├── UPGRADE_PLAN.md          # 主升级方案文档
│                            # 包含: 背景、目标、模块设计、实施计划、成本估算
│
├── ARCHITECTURE.md          # 架构设计图
│                            # 包含: 系统架构、数据流、GEPA循环、模块依赖
│
└── examples/
    └── evolve_hermes_skill.py  # 使用示例脚本
                                # 包含: 7个完整示例，展示各种用法
```

## 文档用途

### UPGRADE_PLAN.md
**给谁看**: 开发团队、代码智能体
**核心内容**:
- 为什么要做这个升级 (背景)
- 升级后是什么样子 (目标)
- 每个模块怎么设计 (模块设计)
- 具体怎么实施 (实施计划)
- 需要多少钱 (成本估算)
- 有什么风险 (风险与缓解)

### ARCHITECTURE.md
**给谁看**: 架构师、高级开发
**核心内容**:
- 系统整体架构图
- 数据流向图
- GEPA 进化循环详解
- 模块依赖关系
- 数据库 Schema 扩展
- API 接口设计
- CLI 命令扩展

### examples/evolve_hermes_skill.py
**给谁看**: 开发者、测试人员
**核心内容**:
- 7 个完整可运行的示例
- 从简单到复杂的渐进式演示
- 包含注释和输出说明

## 如何使用

### 让代码智能体执行

1. **先读 UPGRADE_PLAN.md** — 理解整体目标和模块设计
2. **再读 ARCHITECTURE.md** — 理解架构细节和接口设计
3. **按 Phase 顺序实施**:
   - Phase 1: 基础设施 (config + constraints)
   - Phase 2: 核心引擎 (GEPA + eval + judge)
   - Phase 3: Hermes 集成 (integration + CLI)
   - Phase 4: 优化文档 (performance + docs)

4. **参考 examples/ 验证** — 用示例测试实现是否正确

### 关键文件优先级

```
P0 (必须先实现):
├── evolution_config.py      # 配置
├── constraints.py           # 约束验证
├── gepa_engine.py           # GEPA 引擎
└── skill.py (修改)          # 集成

P1 (核心功能):
├── eval_dataset.py          # 评估数据集
├── llm_judge.py             # LLM 评委
└── hermes_integration.py    # Hermes 集成

P2 (增强功能):
├── execution_tracer.py      # 执行跟踪
└── cli.py (修改)            # CLI 扩展
```

## 依赖关系

```
evolution_config.py
       │
       ▼
constraints.py ──────────────┐
       │                      │
       ▼                      │
eval_dataset.py               │
       │                      │
       ▼                      │
llm_judge.py                  │
       │                      │
       ▼                      │
gepa_engine.py ◄──────────────┘
       │
       ▼
skill.py (修改)
       │
       ▼
hermes_integration.py
       │
       ▼
cli.py (修改)
```

## 注意事项

1. **不要跳过 Phase** — 每个 Phase 都有验证门禁
2. **先实现测试** — 每个模块都要有单元测试
3. **保持向后兼容** — 现有 v2.3.0 功能不能破坏
4. **文档同步** — 实现后更新 README 和文档

## 成本控制

- 默认使用 `gpt-4.1-mini` 做评估 (便宜)
- 迭代次数默认 5 轮 (省成本)
- 支持本地 Ollama 模型 (免费)
- 设置 cost_limit 防止超支

---

*版本: 1.0*
*更新日期: 2026-06-05*
