---
title: omp-in-orca
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [orca]
category: orca
related: [dispatching-parallel-agents, orca-cli, orchestration]
confidence: medium
---

Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Covers worktree creation, parallel orchestration, CLI skill installation, task dispatch, and session interaction for multi-agent workflows with omp workers.

## Metadata

- **ID:** `omp-in-orca`
- **Source:** `orca/skills/omp-in-orca/SKILL.md`
- **Score:** 50.0
- **Edges:** 3

## Related Skills

- [[dispatching-parallel-agents]] *(extends)* — Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies
- [[orca-cli]] *(requires)* — Use the public orca CLI to operate Orca-managed worktrees, folder contexts, terminals, repos, automations, worktree comments, and the browser embedded inside the Orca app. Full handoff, handover, spawn codex/claude in a worktree.
- [[orchestration]] *(requires)* — Use Orca orchestration for structured multi-agent coordination: threaded messages, blocking ask/reply flows, task dispatch, worker_done/escalation waits, task DAGs, decision gates, coordinator loops, or decomposing work across agents.

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

- [[linear-tickets]] — orca
- [[orca-emulator]] — orca
- [[orca-emulator-android]] — orca
- [[orca-linear]] — orca
