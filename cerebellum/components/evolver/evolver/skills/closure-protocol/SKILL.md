---
name: evolver-closure
description: Close agent sessions with structured knowledge extraction. Ensures no value leaks from sessions — every significant output feeds back into Evolver via learn(). Use at session end or when user says "save session" / "close session".
---

# Evolver Closure Protocol

Every significant agent session must close with knowledge extraction. No value leakage.

## When to Use

- Agent completed ≥3 tool calls in the session
- User says "save session" / "close session" / "extract knowledge"
- After completing a substantive task (code fix, research, design)
- User corrects the agent's understanding of a topic

## The 3-Step Closure Cycle

```
Step 1: FORMAT
  Extract key outputs from the session into evolver.learn() parameters:
  - task: what was the session objective?
  - outcome: success or failure?
  - solution: what was the core approach?
  - lessons: what pitfalls, insights, or patterns emerged?

Step 2: LINK
  Check for related history before storing:
  - Call evolver.recall() with a summary of the task
  - If related memories found → note connections in lessons
  - If conflicts detected → mark conflict, do NOT overwrite old memories
  - If knowledge gaps found → note them

Step 3: LOG
  Persist to Evolver:
  - Call evolver.learn() with structured parameters
  - Verify storage by calling evolver.recall() to confirm retrievability
  - Report stored memory IDs to user
```

## Extraction Quality Rules

- **Don't over-extract**: trivial sessions (<3 tool calls) skip learning
- **Be specific**: "learned that pytest fixtures need scope='session' for DB setup" not "learned about testing"
- **Capture failures**: failed solutions are as valuable as successful ones
- **Note conflicts**: if new learning contradicts existing memory, annotate it

## Anti-patterns

- Extracting from shallow sessions (<3 tool calls)
- Too vague ("learned many things") or too granular (every tool call)
- Storing without checking for duplicates via recall() first
- Overwriting existing memories without conflict annotation
- Saying "done" without verifying learn() succeeded

## Quality Gates

- [ ] Session depth check passed (≥3 tool calls or user-initiated)
- [ ] Extraction is specific and actionable
- [ ] No duplicate memories created (recall() check before learn())
- [ ] Conflicts annotated, not silently overwritten
- [ ] Memory IDs confirmed via output
