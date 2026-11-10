---
title: code-review-and-quality
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [agent-skills]
category: agent-skills
related: [code-simplification, doubt-driven-development, karpathy-guidelines, pr-review, rails-code-review, receiving-code-review, requesting-code-review, review, ruby-on-rails-best-practices, skills-pr-review]
confidence: high
---

Conducts multi-axis code review. Use before merging any change. Use when reviewing code written by yourself, another agent, or a human. Use when you need to assess code quality across multiple dimensions before it enters the main branch.

## Metadata

- **ID:** `code-review-and-quality`
- **Source:** `agent-skills/skills/code-review-and-quality/SKILL.md`
- **Score:** 72.0
- **Edges:** 10

## Related Skills

- [[requesting-code-review]] *(complement)* — Use when completing tasks, implementing major features, or before merging to verify work meets requirements
- [[pr-review]] *(similar)* — Guidelines and tools for reviewing pull requests in the Angular repository.
- [[rails-code-review]] *(similar)* — Reviews Rails pull requests, focusing on controller/model conventions, migration safety, query performance, and Rails Way compliance. Covers routing, ActiveRecord, security, caching, and background jobs. Use when reviewing existing Rails code for quality, conducting a PR review, or doing a code revi
- [[receiving-code-review]] *(similar)* — Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation
- [[review]] *(similar)* — Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes — Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/PRD asked for?). Runs both reviews in parallel sub-agents and reports them s
- [[code-simplification]] *(similar)* — Simplifies code for clarity. Use when refactoring code for clarity without changing behavior. Use when code works but is harder to read, maintain, or extend than it should be. Use when reviewing code that has accumulated unnecessary complexity.
- [[doubt-driven-development]] *(similar)* — Subjects every non-trivial decision to a fresh-context adversarial review before it stands. Use when correctness matters more than speed, when working in unfamiliar code, when stakes are high (production, security-sensitive logic, irreversible operations), or any time a confident output would be che
- [[karpathy-guidelines]] *(similar)* — Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.
- [[ruby-on-rails-best-practices]] *(similar)* — Ruby on Rails architecture and coding patterns from Basecamp. Use when writing, reviewing, or refactoring Rails code to follow proven conventions for models, controllers, jobs, and concerns. Triggers on tasks involving Rails models, concerns, controllers, background jobs, or Turbo/Hotwire.
- [[skills-pr-review]] *(similar)* — Review pull requests for the MiniMax Skills repository. Use when reviewing PRs, validating new skill submissions, or checking existing skills for compliance. Run the validation script first for hard checks, then apply quality guidelines for content review. Triggers: PR review, pull request, validate

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
- [[frontend-ui-engineering]] — agent-skills
- [[git-workflow-and-versioning]] — agent-skills
- [[idea-refine]] — agent-skills
- [[incremental-implementation]] — agent-skills
