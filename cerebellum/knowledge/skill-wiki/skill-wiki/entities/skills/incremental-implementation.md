---
title: incremental-implementation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [agent-skills]
category: agent-skills
related: [deprecation-and-migration, finishing-a-development-branch, request-refactor-plan, tdd, using-git-worktrees]
confidence: medium
---

Delivers changes incrementally. Use when implementing any feature or change that touches more than one file. Use when you're about to write a large amount of code at once, or when a task feels too big to land in one step.

## Metadata

- **ID:** `incremental-implementation`
- **Source:** `agent-skills/skills/incremental-implementation/SKILL.md`
- **Score:** 56.0
- **Edges:** 5

## Related Skills

- [[finishing-a-development-branch]] *(similar)* — Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup
- [[request-refactor-plan]] *(similar)* — Create a detailed refactor plan with tiny commits via user interview, then file it as a GitHub issue. Use when user wants to plan a refactor, create a refactoring RFC, or break a refactor into safe incremental steps.
- [[tdd]] *(similar)* — Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests.
- [[using-git-worktrees]] *(similar)* — Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated workspace exists via native tools or git worktree fallback
- [[deprecation-and-migration]] *(similar)* — Manages deprecation and migration. Use when removing old systems, APIs, or features. Use when migrating users from one implementation to another. Use when deciding whether to maintain or sunset existing code.

## Appears In Workflows

- [add-reasonix-tui-agent-to](workflow-patterns.md#add-reasonix-tui-agent-to)
- [afac-doc-parsing](workflow-patterns.md#afac-doc-parsing)
- [build-a-saas-website-with](workflow-patterns.md#build-a-saas-website-with)
- [final-smoke](workflow-patterns.md#final-smoke)
- [hello-world-test](workflow-patterns.md#hello-world-test)
- [optimize-dailyglider](workflow-patterns.md#optimize-dailyglider)
- [test-q](workflow-patterns.md#test-q)
- [verify-test](workflow-patterns.md#verify-test)
- [vf](workflow-patterns.md#vf)
- [wf-optimize-dailyglider](workflow-patterns.md#wf-optimize-dailyglider)

## See Also

- [[api-and-interface-design]] — agent-skills
- [[browser-testing-with-devtools]] — agent-skills
- [[ci-cd-and-automation]] — agent-skills
- [[code-review-and-quality]] — agent-skills
- [[code-simplification]] — agent-skills
- [[context-engineering]] — agent-skills
- [[documentation-and-adrs]] — agent-skills
- [[doubt-driven-development]] — agent-skills
- [[frontend-ui-engineering]] — agent-skills
- [[git-workflow-and-versioning]] — agent-skills
