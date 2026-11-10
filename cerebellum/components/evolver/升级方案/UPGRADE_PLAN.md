# Evolver Project v3.0 升级方案

## 背景

Nous Research 发布了 hermes-agent-self-evolution 项目，使用 DSPy + GEPA 算法优化 Agent 的 skill 文本。

**我们的评估**：
- 该项目只做"文本润色"——优化已有 skill 的措辞和结构
- 我们的 evolver 做"认知涌现"——从记忆+知识图谱生成新技能
- **层次完全不同，不是竞品，是互补**

**核心结论**：借鉴其 GEPA 进化算法和约束框架，增强我们的 SkillEngine，而不是替代它。

---

## 升级目标

| 维度 | 当前 v2.3.0 | 目标 v3.0 |
|------|-------------|-----------|
| 技能生成 | LLM 一次性生成 | 生成 + GEPA 迭代优化 |
| 质量评估 | 基于规则的 8 维评分 | 规则 + LLM-as-judge 双轨制 |
| 进化方向 | 合并新记忆 | 合并记忆 + 执行反馈驱动 |
| 约束检查 | 基本结构检查 | 结构 + 大小 + 语义保持 + 测试门禁 |

---

## 模块设计

### 模块1: GEPA 进化引擎 (evolver/gepa_engine.py)
将 skill 文本作为可优化参数，通过 GEPA 算法迭代改进。
依赖: dspy>=3.0.0, gepa (DSPy 内置)

### 模块2: 评估数据集构建器 (evolver/eval_dataset.py)
构建 skill 评估所需的训练/验证/测试数据集。
三种数据源: synthetic(合成) / memory(记忆挖掘) / golden(人工标准)

### 模块3: LLM-as-Judge 评估器 (evolver/llm_judge.py)
使用 LLM 作为评委，评估 skill 的执行质量。
评估维度: 指令遵循、输出质量、效率、鲁棒性

### 模块4: 增强版约束验证器 (evolver/constraints.py)
验证进化后的 skill 是否满足硬性约束。
包括: 结构约束、大小约束、语义保持、测试门禁

### 模块5: 执行跟踪收集器 (evolver/execution_tracer.py)
收集 skill 执行时的轨迹，用于 GEPA 的反思分析。

---

## 集成点

### 与现有 SkillEngine 集成
- SkillEngine.__init__ 新增 gepa_engine 参数
- generate() 中当 evolve_iterations > 0 时调用 GEPA 优化
- 保持向后兼容 (gepa_engine=None 时走原有逻辑)

### 与 Hermes Agent 集成
- 新增 hermes_integration.py
- 提供 evolve_hermes_skill() 方法
- 自动备份、进化、验证、写入 ~/.hermes/skills/

---

## 实施计划

### Phase 1: 基础设施 (1-2 周)
- 安装配置 DSPy + GEPA (pyproject.toml)
- 实现 EvolutionConfig (evolution_config.py)
- 实现 ConstraintValidator (constraints.py)

### Phase 2: 核心引擎 (2-3 周)
- 实现 GEPAEngine (gepa_engine.py)
- 实现 EvalDatasetBuilder (eval_dataset.py)
- 实现 LLMJudge (llm_judge.py)
- 集成到 SkillEngine (skill.py 修改)

### Phase 3: Hermes 集成 (1-2 周)
- 实现 ExecutionTracer (execution_tracer.py)
- 实现 HermesIntegration (hermes_integration.py)
- CLI 命令扩展 (cli.py 修改)

### Phase 4: 优化与文档 (1 周)

---

## 成本估算

| 操作 | 模型 | 预估成本 |
|------|------|----------|
| 合成评估数据集 (20例) | gpt-4.1-mini | ~$0.05 |
| GEPA 优化 (10轮) | gpt-4.1 | ~$2-5 |
| LLM-as-Judge 评估 | gpt-4.1-mini | ~$0.10 |
| 单个 skill 完整进化 | - | ~$3-6 |

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| GEPA 质量不稳定 | 约束验证 + LLM-as-judge 双重检查 |
| API 调用失败 | 重试机制 + 本地缓存 |
| 语义漂移 | semantic_preservation 约束 |
| 成本超预算 | 设置 max_iterations |

---

## 成功指标

| 指标 | v2.3.0 | v3.0 |
|------|--------|------|
| 技能生成成功率 | ~70% | ~85% |
| 平均质量评分 | 7.2/10 | 8.5/10 |
| 迭代优化收益 | 无 | +15-25% |
| 约束通过率 | 60% | 90% |

---

*版本: 1.0 | 日期: 2026-06-05 | 作者: Hermes Agent*
