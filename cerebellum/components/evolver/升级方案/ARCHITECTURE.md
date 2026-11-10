# 架构设计图

## 系统架构

MemoryEngine + GraphEngine + SkillLibrary
              |
              v
        SkillEngine (v2.3.0 核心)
              |
    +---------+---------+
    |                   |
    v                   v
QualityChecker     GEPAEngine (v3.0 新增)
(v2.3.0 保留)      (DSPy + GEPA 迭代优化)
    |                   |
    +---------+---------+
              |
              v
      ConstraintValidator (v3.0 新增)
              |
              v
          LLMJudge (v3.0 新增)
              |
              v
        输出 & 部署

## GEPA 进化循环

1. 初始化: 加载 baseline -> 构建评估数据集 -> 包装为 DSPy Module
2. 迭代 N 轮:
   a. GEPA 读取执行跟踪, 分析失败模式, 生成候选变体
   b. train set 评估 + LLM-as-judge 打分
   c. 选择最佳变体
   d. 检查停止条件
3. 验证输出: holdout 评估 + 约束验证 + 语义保持

## 模块依赖

evolution_config.py -> constraints.py -> eval_dataset.py -> llm_judge.py -> gepa_engine.py -> skill.py(改) -> hermes_integration.py -> cli.py(改)

## 数据库扩展

新增 3 张表:
- evolution_history: 进化历史记录
- execution_traces: 执行跟踪
- constraint_validations: 约束验证记录
