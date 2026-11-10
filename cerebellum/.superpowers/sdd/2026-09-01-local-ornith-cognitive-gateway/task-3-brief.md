### Task 3: Convert usage and model-version records to local zero-cost semantics

**Files:**
- Modify: `crates/cerebellum-app/src/quality.rs:25-45, 1044-1080, 1701-2057, 2226-2315, 3235-3305, 3690-3740`

**Interfaces:**
- Produces: `pub const LOCAL_MODEL_PROVIDER: &str = "local-openai-compatible"`.
- Keeps: `Registry::reserve_model_usage`, `settle_model_usage`, `model_usage_ledger`, quality/version/calibration tables and public API shapes.
- Historical compatibility: non-local ledger rows still use their stored provider pricing; local rows never require a pricing policy.

- [ ] **Step 1: Replace the daily-budget test with failing zero-cost/history tests**

Remove `concurrent_budget_reservations_stop_at_the_daily_ceiling`; that policy belongs to the removed paid provider. Add:

```rust
#[test]
fn local_usage_records_tokens_with_zero_cost() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let now = Utc::now();
    let request_id = Uuid::new_v4();
    assert_eq!(registry.reserve_model_usage(
        request_id,
        QualityModelStage::Flash,
        1_000,
        200,
        now,
    ).unwrap(), 0);
    let usage = ModelTokenUsage {
        prompt_tokens: 10,
        prompt_cache_hit_tokens: 2,
        prompt_cache_miss_tokens: 8,
        completion_tokens: 4,
        reasoning_tokens: 0,
        total_tokens: 14,
    };
    assert_eq!(registry.settle_model_usage(request_id, Some(&usage), now).unwrap(), 0);
    let ledger = registry.model_usage_ledger(LOCAL_MODEL_PROVIDER, now).unwrap().unwrap();
    assert_eq!(ledger.spent_microusd, 0);
    assert_eq!(ledger.estimated_cny, 0.0);
    assert_eq!(ledger.usage, usage);
}

#[test]
fn registering_local_identity_does_not_rewrite_historical_deepseek_rows() {
    let directory = tempdir().unwrap();
    let registry = Registry::open(directory.path()).unwrap();
    let historical = ModelEndpointVersion {
        schema_version: SCHEMA_VERSION.into(),
        endpoint_version_id: Uuid::new_v4(),
        provider: "deepseek".into(),
        model_id: "deepseek-v4-flash".into(),
        system_fingerprint: "historical-fingerprint".into(),
        prompt_version: "deepseek-quality-rubric-v1".into(),
        schema_hash: "a".repeat(64),
        status: ModelEndpointStatus::PendingApproval,
        metrics: ModelCalibrationMetrics::default(),
        approved_by: None,
        approval_reason: None,
        first_seen_at: Utc::now(),
        updated_at: Utc::now(),
    };
    let historical_json = serde_json::to_string(&historical).unwrap();
    registry.conn.lock().unwrap().execute(
        "INSERT INTO quality_model_versions(
           id,provider,model_id,system_fingerprint,prompt_version,status,version_json,updated_at
         ) VALUES(?1,?2,?3,?4,?5,'pending_approval',?6,?7)",
        params![
            historical.endpoint_version_id.to_string(),
            historical.provider,
            historical.model_id,
            historical.system_fingerprint,
            historical.prompt_version,
            historical_json,
            historical.updated_at.to_rfc3339(),
        ],
    ).unwrap();
    let before: String = registry.conn.lock().unwrap().query_row(
        "SELECT version_json FROM quality_model_versions WHERE id=?1",
        params![historical.endpoint_version_id.to_string()],
        |row| row.get(0),
    ).unwrap();
    registry.ensure_model_endpoint_version(
        "ornith-1.5-9b",
        &"b".repeat(64),
        &"c".repeat(64),
        Utc::now(),
    ).unwrap();
    let after: String = registry.conn.lock().unwrap().query_row(
        "SELECT version_json FROM quality_model_versions WHERE id=?1",
        params![historical.endpoint_version_id.to_string()],
        |row| row.get(0),
    ).unwrap();
    assert_eq!(before, after);
}
```

- [ ] **Step 2: Run the focused tests and verify the local ledger test fails**

Run:

```powershell
cargo test -p cerebellum-app quality::tests::local_usage_records_tokens_with_zero_cost -- --nocapture
```

Expected: failure because reservation still requires DeepSeek pricing.

- [ ] **Step 3: Implement local zero-cost reservations without a schema migration**

Rename active constants:

```rust
pub const QUALITY_POLICY_VERSION: &str = "ornith-local-quality-v1";
pub const QUALITY_PROMPT_VERSION: &str = "ornith-local-quality-rubric-v1";
pub const SYNTHETIC_PROMPT_VERSION: &str = "ornith-local-synthetic-v1";
pub const LOCAL_MODEL_PROVIDER: &str = "local-openai-compatible";
```

Change `reserve_model_usage` to insert `provider=LOCAL_MODEL_PROVIDER` with
`reserved_microusd=0`; remove paid-price lookup and ceiling enforcement from
this method. Keep the existing transaction and idempotent request-ID behavior.
Do not start the application until Task 5 has removed the temporary DeepSeek
client that still exists in the source tree at this checkpoint.

Change `settle_model_usage` to query the reservation before selecting pricing:

```rust
let spent = if provider == LOCAL_MODEL_PROVIDER {
    0
} else {
    let pricing = self.current_provider_pricing(&provider)?;
    usage.map_or(reserved, |usage| {
        estimate_microusd(
            &pricing,
            stage,
            usage.prompt_cache_hit_tokens,
            usage.prompt_cache_miss_tokens,
            usage.completion_tokens,
        )
    })
};
```

Change `model_usage_ledger` so local `estimated_cny` is `0.0`; only load pricing for a non-local provider. This preserves readable historical DeepSeek ledgers and unsettled reservations.

- [ ] **Step 4: Store new endpoint versions under the local provider only**

Replace `DEEPSEEK_PROVIDER` with `LOCAL_MODEL_PROVIDER` in:

- `ensure_model_endpoint_version`;
- `active_model_endpoint`;
- `quality_status` usage/provider values;
- `audit_dataset_quality` usage lookup.

Do not update existing rows. The unique lookup includes provider, so the same model/fingerprint under the new provider creates a distinct record.

- [ ] **Step 5: Run quality lifecycle tests**

Run:

```powershell
cargo test -p cerebellum-app quality::tests -- --nocapture
```

Expected: all quality tests pass, including zero-cost usage and unchanged historical JSON.

- [ ] **Step 6: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/quality.rs
Get-FileHash crates/cerebellum-app/src/quality.rs -Algorithm SHA256
```

Expected: no whitespace errors. Do not stage the already-dirty file.

---

