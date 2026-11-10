---
name: evolver-verify
description: Iron rule — no completion claims without fresh verification evidence. Use whenever about to claim work is done, fixed, working, or passing. Run verification commands and show output before making any success statement.
---

# Evolver Verify Before Claim

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

## When to Use

- Before saying "done", "fixed", "complete", "passing", "working"
- Before committing or creating a PR
- When the user asks "is it working?"
- Any time the agent feels the urge to say "it should work"

## The Gate Function

```
1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim
```

**Skip any step = lying, not verifying.**

## Evolver-Specific Verification

| Action | Verification Required |
|--------|----------------------|
| skillgen complete | `evolver evaluate -f <file>` score ≥60 |
| distill complete | `evolver stats` shows updated fact count |
| learn complete | `evolver recall <query>` returns the stored memory |
| forget complete | `evolver stats` shows decreased memory count |
| lifecycle updated | `evolver stats` shows lifecycle distribution |

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test output: 0 failures | Previous run, "should pass" |
| Memory stored | recall() returns it | "learn() returned IDs" |
| Distill complete | stats() shows new facts | "distill() ran without error" |

## Red Flags — STOP

- Using "should", "probably", "seems to" about completion
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!")
- About to commit/push/PR without verification
- Trusting agent success reports without independent check

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Different context so rule doesn't apply" | Spirit over letter |

## Quality Gates

- [ ] Verification command identified and run
- [ ] Full output shown (exit code, failure count)
- [ ] Claim only made WITH evidence
- [ ] No "should", "probably", "I think" on completion status
