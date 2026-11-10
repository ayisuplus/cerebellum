### Task 4: Route decisions through the shared structured client

**Files:**
- Modify: `crates/cerebellum-app/src/router.rs:1-230, 293-455`

**Interfaces:**
- Consumes: `Arc<Registry>`, `Arc<dyn StructuredModelClient>`, `complete_budgeted`.
- Produces: `OpenAiCompatibleRouter::new(registry, client)`.
- Keeps: `RouterModel`, `rank_with_fallback`, and deterministic BM25 behavior.

- [ ] **Step 1: Add a failing structured-router test**

Use a fake `StructuredModelClient` that captures its request and returns a valid selection:

```rust
#[tokio::test]
async fn local_router_uses_candidate_bounded_schema() {
    let directory = tempdir().unwrap();
    let registry = Arc::new(Registry::open(directory.path()).unwrap());
    let captured = Arc::new(Mutex::new(None));
    let client = Arc::new(FakeStructuredRouter { captured: captured.clone() });
    let router = OpenAiCompatibleRouter::new(registry, client);
    let request = DecisionRequest {
        task: "review this pull request".into(),
        repository_path: None,
        capabilities: vec![],
        context: Value::Null,
    };
    let ranked = router.rank(&request, &builtins::workflows()).await.unwrap();
    assert_eq!(ranked[0].workflow_id, "code-review");
    let request = captured.lock().unwrap().clone().unwrap();
    let allowed = request.payload
        .pointer("/output_schema/properties/workflow_id/enum")
        .unwrap()
        .as_array()
        .unwrap();
    assert!(allowed.iter().any(|id| id == "code-review"));
}
```

The fake response must include internally consistent zero-cost usage and a 64-character derived-style fingerprint.

- [ ] **Step 2: Run the test and verify it fails against the direct HTTP router**

Run:

```powershell
cargo test -p cerebellum-app router::tests::local_router_uses_candidate_bounded_schema -- --nocapture
```

Expected: compilation fails because the constructor still takes endpoint/model/key/backend strings.

- [ ] **Step 3: Replace direct reqwest routing with `StructuredRequest`**

Make the router hold only:

```rust
pub struct OpenAiCompatibleRouter {
    registry: Arc<Registry>,
    client: Arc<dyn StructuredModelClient>,
}

impl OpenAiCompatibleRouter {
    pub fn new(registry: Arc<Registry>, client: Arc<dyn StructuredModelClient>) -> Self {
        Self { registry, client }
    }
}
```

Build a dynamic strict schema with `workflow_id.enum` equal to the supplied IDs, `confidence` bounded to `0..1`, `reasons` bounded to short strings, all three fields required, and `additionalProperties=false`. Put it under `payload.output_schema`, then call:

```rust
let response = complete_budgeted(
    &self.registry,
    self.client.as_ref(),
    &StructuredRequest {
        stage: QualityModelStage::Flash,
        system_prompt: ROUTER_SYSTEM_PROMPT,
        payload: json!({
            "output_schema": schema,
            "task": request.task,
            "context": request.context,
            "capabilities": request.capabilities,
            "candidates": candidates,
        }),
        max_tokens: 512,
    },
    Utc::now(),
).await?;
```

Parse `response.value` and retain existing local checks for confidence and invented IDs. Return `"local-openai-compatible"` from `name()`.

- [ ] **Step 4: Verify strict routing and deterministic failure fallback**

Run:

```powershell
cargo test -p cerebellum-app router::tests -- --nocapture
```

Expected: structured router test passes, and `model_failure_falls_back_without_losing_a_decision` still selects `code-review` through `deterministic-bm25`.

- [ ] **Step 5: Record the checkpoint**

Run:

```powershell
git diff --check -- crates/cerebellum-app/src/router.rs
```

Expected: no whitespace errors; do not stage the already-dirty file.

---

