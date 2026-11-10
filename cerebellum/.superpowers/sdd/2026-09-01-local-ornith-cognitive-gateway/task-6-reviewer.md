# Task 6 independent review

## Spec compliance: PASS

The task-start snapshot to current-tree increment matches the frozen Task 6
brief. `ExternalProcessingPermission` remains stored provenance and is still
loaded into quality subjects/model policy (`quality.rs:1834-1933,2385-2398`),
while only the external-transfer eligibility predicates were removed from
assessment, quality backfill, and API enqueue paths (`quality.rs:2350-2367,2951-2989`;
`api.rs:3940-3997`). The remaining deterministic eligibility, policy, injection,
safety, inserted/model-enabled, and duplicate-assessment/job conditions remain
fail-closed.

Knowledge now permits safe `AuthenticatedLocal` / `Denied` documents to reach
the loopback structured model, but any stored document injection, PII, or secret
flag still selects deterministic fallback before the call (`knowledge.rs:59-77`).
Cards remain initially ineligible, and the document-derived trace retains the
existing licence/flag eligibility calculation (`knowledge.rs:261-311,332-391`).

The router reuses the sole `validate_export_payload` implementation before
constructing or sending the structured request and scans exactly `task`,
`context`, and `capabilities`; candidates/schema are excluded (`router.rs:118-163`).
Scanner failure reaches the existing `rank_with_fallback`, so the structured
client is not called and deterministic routing is selected (`router.rs:209-241,
426-451`).

The quality scanner body is unchanged apart from `pub(crate)` visibility and
still rejects oversize, likely-secret, PII, and injection payloads before
redaction attestation/model invocation (`quality.rs:1545-1561,2350-2401`).
Private echo and secret/PII output quarantine, `quality_clear`, calibration,
endpoint approval, promotion, synthetic-parent gating, and rollback paths were
not weakened. The dataset-factory production delta is comment-only; the only
additional changes are the approved `#[cfg(test)]` local provider/model fixture,
with production selection still requiring `quality_clear`
(`dataset_factory.rs:377-412,1721-1751`).

## Code quality: APPROVED

No P0-P2 findings. The delta is surgical, reuses existing scanner/fallback/client
interfaces, introduces no dependency or production abstraction, and the test-only
SQL mutation deliberately bypasses ingestion so the real shared quality export
scanner—not duplicated test logic—is exercised.

Ponytail review: Lean already. Ship.

## Verification evidence

Tests were not rerun, per assignment. The implementer report is accepted as
evidence for 12 quality, 4 knowledge, 8 router, 36 API, and 9 dataset-factory
tests passing, plus scoped `git diff --check` exit 0. Current hashes of all five
reviewed files match the implementer report and review package.
