# Task 3 review package

Task brief: task-3-brief.md
Implementer report: task-3-implementer.md
Comparison: task-start snapshot to current working tree; no commits or staging.

warning: in the working copy of '.superpowers\sdd\2026-09-01-local-ornith-cognitive-gateway\task-3-baseline\crates\cerebellum-app\src\quality.rs', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'crates\cerebellum-app\src\quality.rs', LF will be replaced by CRLF the next time Git touches it
diff --git "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-3-baseline\\crates\\cerebellum-app\\src\\quality.rs" "b/crates\\cerebellum-app\\src\\quality.rs"
index 219c062..8783524 100644
--- "a/.superpowers\\sdd\\2026-09-01-local-ornith-cognitive-gateway\\task-3-baseline\\crates\\cerebellum-app\\src\\quality.rs"
+++ "b/crates\\cerebellum-app\\src\\quality.rs"
@@ -27,15 +27,16 @@ use std::sync::LazyLock;
 use std::time::Duration;
 use uuid::Uuid;
 
-pub const QUALITY_POLICY_VERSION: &str = "deepseek-quality-v1";
-pub const QUALITY_PROMPT_VERSION: &str = "deepseek-quality-rubric-v1";
-pub const SYNTHETIC_PROMPT_VERSION: &str = "deepseek-synthetic-v1";
+pub const QUALITY_POLICY_VERSION: &str = "ornith-local-quality-v1";
+pub const QUALITY_PROMPT_VERSION: &str = "ornith-local-quality-rubric-v1";
+pub const SYNTHETIC_PROMPT_VERSION: &str = "ornith-local-synthetic-v1";
 pub const REDACTION_SCANNER_VERSION: &str = "cerebellum-export-redactor-v1";
 pub const MAX_EXPORTED_CHARACTERS: usize = 16_000;
 pub const MAX_PRIVATE_ECHO_CHARACTERS: usize = 64;
 pub const FLASH_ARBITRATION_CONFIDENCE: f64 = 0.85;
 pub const MAX_SYNTHETIC_RATIO: f64 = 0.20;
 pub const DEEPSEEK_PROVIDER: &str = "deepseek";
+pub const LOCAL_MODEL_PROVIDER: &str = "local-openai-compatible";
 
 type UsageLedgerRow = (u64, u64, u64, u64, u64, u64, u64, u64, u64, u64, String);
 
@@ -1041,36 +1042,108 @@ mod tests {
     }
 
     #[test]
-    fn concurrent_budget_reservations_stop_at_the_daily_ceiling() {
+    fn local_usage_records_tokens_with_zero_cost() {
         let directory = tempdir().unwrap();
-        let registry = Arc::new(Registry::open(directory.path()).unwrap());
-        let mut policy = pricing();
-        policy.policy_id = "tiny-concurrent-budget".into();
-        policy.daily_max_cny = 0.0015;
-        registry.save_provider_pricing_policy(&policy).unwrap();
+        let registry = Registry::open(directory.path()).unwrap();
         let now = Utc::now();
-        let handles = (0..16)
-            .map(|_| {
-                let registry = registry.clone();
-                std::thread::spawn(move || {
-                    registry
-                        .reserve_model_usage(
-                            Uuid::new_v4(),
-                            QualityModelStage::Flash,
-                            1_000,
-                            0,
-                            now,
-                        )
-                        .is_ok()
-                })
-            })
-            .collect::<Vec<_>>();
-        let accepted = handles
-            .into_iter()
-            .map(|handle| handle.join().unwrap())
-            .filter(|accepted| *accepted)
-            .count();
-        assert_eq!(accepted, 1);
+        let request_id = Uuid::new_v4();
+        assert_eq!(
+            registry
+                .reserve_model_usage(request_id, QualityModelStage::Flash, 1_000, 200, now)
+                .unwrap(),
+            0
+        );
+        let usage = ModelTokenUsage {
+            prompt_tokens: 10,
+            prompt_cache_hit_tokens: 2,
+            prompt_cache_miss_tokens: 8,
+            completion_tokens: 4,
+            reasoning_tokens: 0,
+            total_tokens: 14,
+        };
+        assert_eq!(
+            registry
+                .settle_model_usage(request_id, Some(&usage), now)
+                .unwrap(),
+            0
+        );
+        let ledger = registry
+            .model_usage_ledger(LOCAL_MODEL_PROVIDER, now)
+            .unwrap()
+            .unwrap();
+        assert_eq!(ledger.spent_microusd, 0);
+        assert_eq!(ledger.estimated_cny, 0.0);
+        assert_eq!(ledger.usage, usage);
+    }
+
+    #[test]
+    fn registering_local_identity_does_not_rewrite_historical_deepseek_rows() {
+        let directory = tempdir().unwrap();
+        let registry = Registry::open(directory.path()).unwrap();
+        let historical = ModelEndpointVersion {
+            schema_version: SCHEMA_VERSION.into(),
+            endpoint_version_id: Uuid::new_v4(),
+            provider: "deepseek".into(),
+            model_id: "deepseek-v4-flash".into(),
+            system_fingerprint: "historical-fingerprint".into(),
+            prompt_version: "deepseek-quality-rubric-v1".into(),
+            schema_hash: "a".repeat(64),
+            status: ModelEndpointStatus::PendingApproval,
+            metrics: ModelCalibrationMetrics::default(),
+            approved_by: None,
+            approval_reason: None,
+            first_seen_at: Utc::now(),
+            updated_at: Utc::now(),
+        };
+        let historical_json = serde_json::to_string(&historical).unwrap();
+        registry
+            .conn
+            .lock()
+            .unwrap()
+            .execute(
+                "INSERT INTO quality_model_versions(
+                   id,provider,model_id,system_fingerprint,prompt_version,status,version_json,updated_at
+                 ) VALUES(?1,?2,?3,?4,?5,'pending_approval',?6,?7)",
+                params![
+                    historical.endpoint_version_id.to_string(),
+                    historical.provider,
+                    historical.model_id,
+                    historical.system_fingerprint,
+                    historical.prompt_version,
+                    historical_json,
+                    historical.updated_at.to_rfc3339(),
+                ],
+            )
+            .unwrap();
+        let before: String = registry
+            .conn
+            .lock()
+            .unwrap()
+            .query_row(
+                "SELECT version_json FROM quality_model_versions WHERE id=?1",
+                params![historical.endpoint_version_id.to_string()],
+                |row| row.get(0),
+            )
+            .unwrap();
+        registry
+            .ensure_model_endpoint_version(
+                "ornith-1.5-9b",
+                &"b".repeat(64),
+                &"c".repeat(64),
+                Utc::now(),
+            )
+            .unwrap();
+        let after: String = registry
+            .conn
+            .lock()
+            .unwrap()
+            .query_row(
+                "SELECT version_json FROM quality_model_versions WHERE id=?1",
+                params![historical.endpoint_version_id.to_string()],
+                |row| row.get(0),
+            )
+            .unwrap();
+        assert_eq!(before, after);
     }
 
     #[test]
@@ -1862,15 +1935,12 @@ impl Registry {
         &self,
         request_id: Uuid,
         stage: QualityModelStage,
-        worst_input_tokens: u64,
-        max_output_tokens: u64,
+        _worst_input_tokens: u64,
+        _max_output_tokens: u64,
         now: DateTime<Utc>,
     ) -> Result<u64> {
-        let pricing = self.current_provider_pricing(DEEPSEEK_PROVIDER)?;
-        let reserved = estimate_microusd(&pricing, stage, 0, worst_input_tokens, max_output_tokens);
+        let reserved = 0;
         let day = crate::shanghai_day(now).to_string();
-        let max_microusd =
-            (pricing.daily_max_cny / pricing.usd_to_cny_ceiling * 1_000_000.0).floor() as u64;
         let mut conn = self.conn.lock().expect("registry mutex poisoned");
         let transaction = conn.transaction()?;
         if let Some(existing) = transaction
@@ -1887,35 +1957,21 @@ impl Registry {
         transaction.execute(
             "INSERT INTO model_usage_ledger(provider,shanghai_day,updated_at)
              VALUES(?1,?2,?3) ON CONFLICT(provider,shanghai_day) DO NOTHING",
-            params![DEEPSEEK_PROVIDER, day, now.to_rfc3339()],
-        )?;
-        let (outstanding, spent): (u64, u64) = transaction.query_row(
-            "SELECT reserved_microusd,spent_microusd FROM model_usage_ledger
-             WHERE provider=?1 AND shanghai_day=?2",
-            params![DEEPSEEK_PROVIDER, day],
-            |row| Ok((row.get(0)?, row.get(1)?)),
+            params![LOCAL_MODEL_PROVIDER, day, now.to_rfc3339()],
         )?;
-        if outstanding.saturating_add(spent).saturating_add(reserved) > max_microusd {
-            bail!("DeepSeek daily CNY budget would be exceeded");
-        }
         transaction.execute(
             "INSERT INTO model_usage_reservations(
                request_id,provider,shanghai_day,stage,reserved_microusd,created_at
              ) VALUES(?1,?2,?3,?4,?5,?6)",
             params![
                 request_id.to_string(),
-                DEEPSEEK_PROVIDER,
+                LOCAL_MODEL_PROVIDER,
                 day,
                 stage_name(stage),
                 reserved,
                 now.to_rfc3339()
             ],
         )?;
-        transaction.execute(
-            "UPDATE model_usage_ledger SET reserved_microusd=reserved_microusd+?3,
-               updated_at=?4 WHERE provider=?1 AND shanghai_day=?2",
-            params![DEEPSEEK_PROVIDER, day, reserved, now.to_rfc3339()],
-        )?;
         transaction.commit()?;
         Ok(reserved)
     }
@@ -1926,7 +1982,6 @@ impl Registry {
         usage: Option<&ModelTokenUsage>,
         now: DateTime<Utc>,
     ) -> Result<u64> {
-        let pricing = self.current_provider_pricing(DEEPSEEK_PROVIDER)?;
         let mut conn = self.conn.lock().expect("registry mutex poisoned");
         let transaction = conn.transaction()?;
         let row: Option<(String, String, String, u64, Option<u64>)> = transaction
@@ -1956,15 +2011,32 @@ impl Registry {
         } else {
             QualityModelStage::Pro
         };
-        let spent = usage.map_or(reserved, |usage| {
-            estimate_microusd(
-                &pricing,
-                stage,
-                usage.prompt_cache_hit_tokens,
-                usage.prompt_cache_miss_tokens,
-                usage.completion_tokens,
-            )
-        });
+        let spent = if provider == LOCAL_MODEL_PROVIDER {
+            0
+        } else {
+            let value: String = transaction
+                .query_row(
+                    "SELECT policy_json FROM provider_pricing_policies WHERE provider=?1
+                     ORDER BY confirmed_at DESC,id LIMIT 1",
+                    params![provider],
+                    |row| row.get(0),
+                )
+                .context("provider pricing policy is missing")?;
+            let pricing: ProviderPricingPolicy = serde_json::from_str(&value)?;
+            validate_provider_pricing_policy(&pricing)?;
+            if Utc::now() - pricing.confirmed_at > ChronoDuration::days(30) {
+                bail!("provider pricing confirmation is older than 30 days");
+            }
+            usage.map_or(reserved, |usage| {
+                estimate_microusd(
+                    &pricing,
+                    stage,
+                    usage.prompt_cache_hit_tokens,
+                    usage.prompt_cache_miss_tokens,
+                    usage.completion_tokens,
+                )
+            })
+        };
         let usage = usage.cloned().unwrap_or_default();
         transaction.execute(
             "UPDATE model_usage_reservations SET spent_microusd=?2,settled_at=?3
@@ -2006,7 +2078,9 @@ impl Registry {
         provider: &str,
         now: DateTime<Utc>,
     ) -> Result<Option<ModelUsageLedger>> {
-        let pricing = self.current_provider_pricing(provider)?;
+        let pricing = (provider != LOCAL_MODEL_PROVIDER)
+            .then(|| self.current_provider_pricing(provider))
+            .transpose()?;
         let day = crate::shanghai_day(now).to_string();
         let conn = self.conn.lock().expect("registry mutex poisoned");
         let row: Option<UsageLedgerRow> = conn
@@ -2049,7 +2123,9 @@ impl Registry {
                 },
                 reserved_microusd: row.8,
                 spent_microusd: row.9,
-                estimated_cny: row.9 as f64 / 1_000_000.0 * pricing.usd_to_cny_ceiling,
+                estimated_cny: pricing
+                    .as_ref()
+                    .map_or(0.0, |pricing| row.9 as f64 / 1_000_000.0 * pricing.usd_to_cny_ceiling),
                 updated_at: DateTime::parse_from_rfc3339(&row.10)?.with_timezone(&Utc),
             })
         })
@@ -2237,7 +2313,7 @@ impl Registry {
                  WHERE provider=?1 AND model_id=?2 AND system_fingerprint=?3
                    AND prompt_version=?4",
                 params![
-                    DEEPSEEK_PROVIDER,
+                    LOCAL_MODEL_PROVIDER,
                     model_id,
                     fingerprint,
                     QUALITY_PROMPT_VERSION
@@ -2253,7 +2329,7 @@ impl Registry {
         let version = ModelEndpointVersion {
             schema_version: SCHEMA_VERSION.into(),
             endpoint_version_id: Uuid::new_v4(),
-            provider: DEEPSEEK_PROVIDER.into(),
+            provider: LOCAL_MODEL_PROVIDER.into(),
             model_id: model_id.into(),
             system_fingerprint: fingerprint.into(),
             prompt_version: QUALITY_PROMPT_VERSION.into(),
@@ -2304,7 +2380,7 @@ impl Registry {
             "SELECT version_json FROM quality_model_versions
              WHERE provider=?1 AND model_id=?2 AND status='active'
              ORDER BY updated_at DESC,id LIMIT 1",
-            params![DEEPSEEK_PROVIDER, model_id],
+            params![LOCAL_MODEL_PROVIDER, model_id],
             |row| row.get::<_, String>(0),
         )
         .optional()?
@@ -3285,7 +3361,7 @@ impl Registry {
         Ok(QualityStatus {
             enabled: true,
             enforcement_required: config.enforcement_required,
-            provider: DEEPSEEK_PROVIDER.into(),
+            provider: LOCAL_MODEL_PROVIDER.into(),
             flash_model: config.flash_model.clone(),
             pro_model: config.pro_model.clone(),
             pending_assessments,
@@ -3293,7 +3369,7 @@ impl Registry {
             quarantined_records,
             synthetic_candidates,
             latest_passed_build_id,
-            usage: self.model_usage_ledger(DEEPSEEK_PROVIDER, now)?,
+            usage: self.model_usage_ledger(LOCAL_MODEL_PROVIDER, now)?,
             active_model_versions: self
                 .list_model_endpoint_versions()?
                 .into_iter()
@@ -3715,7 +3791,7 @@ impl Registry {
             disagreements as f64 / sample_size as f64
         };
         let usage = self
-            .model_usage_ledger(DEEPSEEK_PROVIDER, now)?
+            .model_usage_ledger(LOCAL_MODEL_PROVIDER, now)?
             .unwrap_or_default();
         let gate_passed = total > 0
             && assessed == total
