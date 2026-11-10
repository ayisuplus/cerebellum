### Task 6: Apply the loopback-local privacy interpretation without weakening scanners

**Files:**
- Modify: `crates/cerebellum-app/src/quality.rs:276-310, 2059-2162, 2576-2620, 3120-3235`
- Modify: `crates/cerebellum-app/src/knowledge.rs:67-127, 655-930`
- Modify: `crates/cerebellum-app/src/router.rs:102-230, 293-370`
- Modify: `crates/cerebellum-app/src/api.rs:3957-4015`
- Modify: `crates/cerebellum-app/src/dataset_factory.rs:380`

**Interfaces:**
- Keeps: `ExternalProcessingPermission` in stored records as provenance.
- Changes: local inference eligibility no longer requires `ExternalProcessingPermission::Redacted` and no longer rejects `AuthenticatedLocal` solely for access mode.
- Keeps: deterministic eligibility, document secret/PII/injection flags, `validate_export_payload`, redaction attestation, private-echo scanning, licensing, quality-clear, and human approval.
- Adds: router input scanning before the shared client sees task/context/capabilities; a rejected router input uses the existing deterministic fallback.

- [ ] **Step 1: Write failing quality tests for local-only permission semantics**

Split the old `denied_or_deterministically_ineligible_records_never_call_the_model` expectation into:

```rust
#[tokio::test]
async fn eligible_local_record_can_be_reviewed_when_external_transfer_is_denied() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let calls = Arc::new(AtomicUsize::new(0));
    let model = FakeModel { calls: calls.clone() };
    let item = trace(ExternalProcessingPermission::Denied, true);
    registry.record_meta_decision(&item).unwrap();
    assess_subject(
        &registry,
        &model,
        QualityAssessmentTarget {
            subject_kind: QualitySubjectKind::MetaDecision,
            subject_id: &item.decision_id.to_string(),
            stage: QualityModelStage::Flash,
            parent_assessment_id: None,
            now: Utc::now(),
        },
    ).await.unwrap();
    assert_eq!(calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn local_permission_bypass_does_not_bypass_deterministic_or_secret_gates() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let calls = Arc::new(AtomicUsize::new(0));
    let model = FakeModel { calls: calls.clone() };
    let mut item = trace(ExternalProcessingPermission::Denied, false);
    registry.record_meta_decision(&item).unwrap();
    assert!(assess_subject(&registry, &model, target(&item)).await.is_err());
    item.decision_id = Uuid::new_v4();
    item.training_eligible = true;
    item.input = json!({"api_key": "sk-abcdefghijklmnop1234"});
    registry.record_meta_decision(&item).unwrap();
    assert!(assess_subject(&registry, &model, target(&item)).await.is_err());
    assert_eq!(calls.load(Ordering::SeqCst), 0);
}
```

Add a router test whose task contains `api_key=sk-abcdefghijklmnop1234`.
The fake structured client call count must stay zero, and `rank_with_fallback`
must return a deterministic result with `fallback_used=true`.

- [ ] **Step 2: Add a failing knowledge test for cleaned authenticated-local content**

Create an authenticated-local source with `external_processing=Denied`, a document with all three detection flags false, and a fake structured model. Assert structured extraction is attempted. Then set `secret_detected=true` on a second document and assert deterministic fallback with no additional model call.

- [ ] **Step 3: Run the new tests and verify current permission checks reject them**

Run:

```powershell
cargo test -p cerebellum-app eligible_local_record_can_be_reviewed -- --nocapture
cargo test -p cerebellum-app cleaned_authenticated_local -- --nocapture
```

Expected: the safe local cases fail before calling the model.

- [ ] **Step 4: Remove only external-transfer blockers from local paths**

In `assess_subject_inner`, remove:

```rust
if subject.permission != ExternalProcessingPermission::Redacted {
    bail!("external processing permission is denied");
}
```

Do not remove `deterministic_eligible`, `validate_export_payload`, redaction attestation, echo, secret, PII, injection, endpoint approval, or quality-clear checks.

In `consolidate_document_with_structured_model_fallback`, remove only `AuthenticatedLocal` and `source.external_processing` from the early fallback condition. Keep document injection/PII/secret flags.

In API enqueue and `enqueue_quality_backfill`, remove only the `external_processing == Redacted` predicates. Keep training eligibility, safety, policy, and prompt-injection predicates.

Make `validate_export_payload` `pub(crate)` without changing its scanner logic.
Before building the router request, call it on exactly:

```rust
json!({
    "task": request.task,
    "context": request.context,
    "capabilities": request.capabilities,
})
```

Discard the returned serialization; this is a local trust-boundary check. An
error naturally reaches `rank_with_fallback`, which selects the deterministic
router. Do not scan the generated JSON Schema or workflow manifests as user
data.

- [ ] **Step 5: Update stale provider-authority comments**

Change the KnowledgeCard source comment to state that cards may derive from cleaned local or public content, while training eligibility remains deterministic and quality-gated. Change the dataset-factory comment from “DeepSeek quality gate” to “active structured quality gate”. Do not alter dataset selection logic.

- [ ] **Step 6: Run privacy, knowledge, API, and dataset tests**

Run:

```powershell
cargo test -p cerebellum-app quality::tests -- --nocapture
cargo test -p cerebellum-app knowledge::tests -- --nocapture
cargo test -p cerebellum-app router::tests -- --nocapture
cargo test -p cerebellum-app api::tests -- --nocapture
cargo test -p cerebellum-app dataset_factory::tests -- --nocapture
```

Expected: safe loopback-local records can reach the model; ineligible, secret, PII, injection, and private-echo cases never become trusted knowledge.

- [ ] **Step 7: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/quality.rs crates/cerebellum-app/src/knowledge.rs crates/cerebellum-app/src/router.rs crates/cerebellum-app/src/api.rs crates/cerebellum-app/src/dataset_factory.rs
```

Expected: no whitespace errors.

---

