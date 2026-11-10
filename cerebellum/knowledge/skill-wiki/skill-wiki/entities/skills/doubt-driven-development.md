---
title: doubt-driven-development
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [agent-skills]
category: agent-skills
related: [code-review-and-quality, karpathy-guidelines, receiving-code-review]
confidence: high
---

Subjects every non-trivial decision to a fresh-context adversarial review before it stands. Use when correctness matters more than speed, when working in unfamiliar code, when stakes are high (production, security-sensitive logic, irreversible operations), or any time a confident output would be che

## Metadata

- **ID:** `doubt-driven-development`
- **Source:** `agent-skills/skills/doubt-driven-development/SKILL.md`
- **Score:** 72.0
- **Edges:** 3

## Related Skills

- [[code-review-and-quality]] *(similar)* — Conducts multi-axis code review. Use before merging any change. Use when reviewing code written by yourself, another agent, or a human. Use when you need to assess code quality across multiple dimensions before it enters the main branch.
- [[karpathy-guidelines]] *(similar)* — Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.
- [[receiving-code-review]] *(similar)* — Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation

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
- [[code-simplification]] — agent-skills
- [[context-engineering]] — agent-skills
- [[deprecation-and-migration]] — agent-skills
- [[documentation-and-adrs]] — agent-skills
- [[frontend-ui-engineering]] — agent-skills
- [[git-workflow-and-versioning]] — agent-skills
- [[idea-refine]] — agent-skills
