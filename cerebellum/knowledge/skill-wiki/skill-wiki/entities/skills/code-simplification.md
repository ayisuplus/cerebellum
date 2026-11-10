---
title: code-simplification
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [agent-skills]
category: agent-skills
related: [code-review-and-quality, karpathy-guidelines, receiving-code-review, rust-best-practices]
confidence: medium
---

Simplifies code for clarity. Use when refactoring code for clarity without changing behavior. Use when code works but is harder to read, maintain, or extend than it should be. Use when reviewing code that has accumulated unnecessary complexity.

## Metadata

- **ID:** `code-simplification`
- **Source:** `agent-skills/skills/code-simplification/SKILL.md`
- **Score:** 59.0
- **Edges:** 4

## Related Skills

- [[code-review-and-quality]] *(similar)* — Conducts multi-axis code review. Use before merging any change. Use when reviewing code written by yourself, another agent, or a human. Use when you need to assess code quality across multiple dimensions before it enters the main branch.
- [[karpathy-guidelines]] *(similar)* — Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.
- [[receiving-code-review]] *(similar)* — Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation
- [[rust-best-practices]] *(similar)* — Guide for writing idiomatic Rust code based on Apollo GraphQL's best practices handbook. Use this skill when: (1) writing new Rust code or functions, (2) reviewing or refactoring existing Rust code, (3) deciding between borrowing vs cloning or ownership patterns, (4) implementing error handling with

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
- [[context-engineering]] — agent-skills
- [[deprecation-and-migration]] — agent-skills
- [[documentation-and-adrs]] — agent-skills
- [[doubt-driven-development]] — agent-skills
- [[frontend-ui-engineering]] — agent-skills
- [[git-workflow-and-versioning]] — agent-skills
- [[idea-refine]] — agent-skills
