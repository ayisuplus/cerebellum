---
title: codebase-inject
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [codebase]
category: codebase
related: [codegraph]
confidence: low
---

Inject codebase context before planning. Tool selection: <10k lines use codegraph (lightweight, fast, auto-sync MCP); >10k lines use codebase-memory-mcp (heavy but deep analysis). Always check LOC first with wc -l.

## Metadata

- **ID:** `codebase-inject`
- **Source:** `github/codebase-inspection/SKILL.md`
- **Score:** 0.0
- **Edges:** 1

## Related Skills

- [[codegraph]] *(sequence)* — Lightweight local code knowledge graph with auto-sync via MCP. Use for projects <10k lines. Provides semantic code intelligence (symbol lookup, call paths, dependency analysis). 100% local, auto-syncs on file changes.

## Appears In Workflows

- [add-reasonix-tui-agent-to](workflow-patterns.md#add-reasonix-tui-agent-to)
- [afac-doc-parsing](workflow-patterns.md#afac-doc-parsing)
- [build-a-saas-website-with](workflow-patterns.md#build-a-saas-website-with)
- [hello-world-test](workflow-patterns.md#hello-world-test)
- [optimize-dailyglider](workflow-patterns.md#optimize-dailyglider)
- [test-q](workflow-patterns.md#test-q)
- [verify-test](workflow-patterns.md#verify-test)
- [vf](workflow-patterns.md#vf)
- [wf-optimize-dailyglider](workflow-patterns.md#wf-optimize-dailyglider)
