# skill-wiki

把 skill-graph 的知识图谱蒸馏成 Karpathy LLM Wiki 格式的可训练知识库。

## 起因

skill-graph 有 1230 nodes、3498 edges、10 workflows——这些是 Agent 工程经验的结构化编码。
但 YAML 图谱只有机器能读，人看不懂，也没法当训练数据。

llm-wiki 用 interlinked markdown + frontmatter 组织知识，Obsidian 可浏览，
搜索引擎可索引，最重要的是：**格式化的文本可以直接喂给模型微调**。

## 核心思路

```
skill-graph (YAML graph)
    │
    │  export pipeline
    ▼
skill-wiki (interlinked markdown)
    │
    │  持续积累 + 人类策展
    ▼
训练数据 (任务 → 工作流 映射)
```

## 三层架构

### Layer 1: entities/skills/ — 每个 skill 一页

```yaml
---
title: code-review-and-quality
created: 2026-07-03
type: entity
tags: [agent, review, quality]
category: agent
related: [test-driven-development, security-and-hardening]
confidence: high
---
```

内容：skill 描述、触发条件、使用场景、与其他 skill 的关系。

### Layer 2: concepts/workflows/ — 每个工作流模式一页

从 skill-graph 的 10 个 workflow 提取，加上我们实战验证的模式：
- fire-and-forget 派发
- supervised orchestration
- parallel code review + test gen

### Layer 3: queries/patterns/ — 经验映射

把"什么任务用什么 skill 组合"记录成可训练的格式：
```
task: "审查 FastAPI 后端代码"
workflow: [codebase-recon → code-review-and-quality → security-and-hardening]
outcome: found 26 issues, 3 critical
```

## 数据来源

1. skill-graph export (nodes + edges + workflows)
2. 实战 session 记录 (Orca omp 军团的 dispatch + outcome)
3. 人工策展 (标注哪些组合效果好)

## 技术栈

- 存储：纯 markdown 文件（Obsidian 兼容）
- schema：llm-wiki 的 SCHEMA.md 规范
- 导出：Python 脚本读 skill-graph.yaml，生成 wiki 页面
- 查询：search_files + wikilinks
- 训练导出：markdown → JSONL (prompt/completion pairs)

## TODO

- [x] 初始化 wiki 结构 (SCHEMA.md, index.md, log.md) — export-pipeline 一并完成
- [x] 写 export pipeline (skill-graph → wiki pages) — scripts/export.py (511行)
- [x] 导入第一批 nodes + edges — 1230 skill pages + workflow-patterns.md
- [ ] 记录今天 omp 军团的实战 pattern
- [x] 设计 JSONL 训练数据导出格式 — scripts/export_jsonl.py (290行)
- [ ] 补充 SCHEMA.md（当前 index/log 由 export.py 自动生成，需人工策展）
