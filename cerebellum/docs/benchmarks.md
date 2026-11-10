# MVP benchmark receipt

Measured on the implementation workstation on 2026-08-22 using an optimized
release build:

```text
cargo run --release --quiet --example benchmark_registry
skills=10000 seed_ms=6259 query_p95_ms=14.841
gate_p95_ms=0.000
authorization_p95_ms=0.533
```

The benchmark inserts 10,000 versioned, routable Skill manifests into a fresh
SQLite WAL Registry, then performs 250 exact-target searches through the same
public `Registry::search_skills` path used by the HTTP API. The measured p95 is
below the MVP limit of 50 ms. It also evaluates an in-process deterministic
evidence gate 10,000 times; the measured p95 rounds below 0.001 ms and is below
the 20 ms target. Finally, it performs 1,000 authorization paths, including
run/workflow lookup, mandatory-gate verification, action hashing, HMAC signing
and permit persistence. Its p95 is also below the 20 ms target.

This is a local receipt, not a universal performance claim. Run the example on
each deployment target and retain the output with its hardware and build
metadata. Model inference is intentionally excluded and must be compared
separately against an equal-model Python baseline.
