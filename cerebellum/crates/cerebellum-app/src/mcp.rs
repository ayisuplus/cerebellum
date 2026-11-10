use anyhow::{Context, Result};
use reqwest::Client;
use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncRead, AsyncWrite, AsyncWriteExt, BufReader};

pub async fn run_stdio(server_url: &str, token: &str) -> Result<()> {
    serve(
        Client::new(),
        server_url,
        token,
        tokio::io::stdin(),
        tokio::io::stdout(),
    )
    .await
}

async fn serve<R, W>(
    client: Client,
    server_url: &str,
    token: &str,
    stdin: R,
    mut stdout: W,
) -> Result<()>
where
    R: AsyncRead + Unpin,
    W: AsyncWrite + Unpin,
{
    let mut lines = BufReader::new(stdin).lines();
    while let Some(line) = lines.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }
        let request: Value = match serde_json::from_str(&line) {
            Ok(value) => value,
            Err(error) => {
                write_response(&mut stdout, &json!({"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":error.to_string()}})).await?;
                continue;
            }
        };
        let method = request.get("method").and_then(Value::as_str).unwrap_or("");
        if method.starts_with("notifications/") {
            continue;
        }
        let id = request.get("id").cloned().unwrap_or(Value::Null);
        let response = match dispatch(
            &client,
            server_url,
            token,
            method,
            request.get("params").cloned().unwrap_or(Value::Null),
        )
        .await
        {
            Ok(result) => json!({"jsonrpc":"2.0","id":id,"result":result}),
            Err(error) => {
                json!({"jsonrpc":"2.0","id":id,"error":{"code":-32000,"message":error.to_string()}})
            }
        };
        write_response(&mut stdout, &response).await?;
    }
    Ok(())
}

async fn dispatch(
    client: &Client,
    server_url: &str,
    token: &str,
    method: &str,
    params: Value,
) -> Result<Value> {
    match method {
        "initialize" => Ok(
            json!({"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"cerebellum","version":env!("CARGO_PKG_VERSION")}}),
        ),
        "ping" => Ok(json!({})),
        "tools/list" => Ok(json!({"tools":tools()})),
        "tools/call" => {
            let name = params
                .get("name")
                .and_then(Value::as_str)
                .context("missing tool name")?;
            let arguments = params
                .get("arguments")
                .cloned()
                .unwrap_or_else(|| json!({}));
            let result = call_tool(client, server_url, token, name, arguments).await?;
            Ok(
                json!({"content":[{"type":"text","text":serde_json::to_string_pretty(&result)?}],"structuredContent":result,"isError":false}),
            )
        }
        _ => anyhow::bail!("method not found: {method}"),
    }
}

fn tools() -> Vec<Value> {
    vec![
        tool(
            "cerebellum_plan",
            "Select a versioned workflow and return learned context as non-executable evidence; verify unverified, contested, or stale context before use",
            json!({"type":"object","required":["task"],"properties":{"task":{"type":"string"},"repository_path":{"type":"string"},"capabilities":{"type":"array","items":{"type":"string"}},"context":{"type":"object"}}}),
        ),
        tool(
            "cerebellum_start_run",
            "Start a recorded workflow execution",
            json!({"type":"object","required":["decision_id","workflow_id","workflow_version"],"properties":{"decision_id":{"type":"string"},"workflow_id":{"type":"string"},"workflow_version":{"type":"string"},"repository_path":{"type":"string"},"capabilities":{"type":"array","items":{"type":"string"}}}}),
        ),
        tool(
            "cerebellum_record_event",
            "Append an immutable execution event",
            json!({"type":"object","required":["run_id","kind","payload"],"properties":{"run_id":{"type":"string"},"kind":{"type":"string"},"payload":{}}}),
        ),
        tool(
            "cerebellum_evaluate_gate",
            "Evaluate a deterministic gate",
            json!({"type":"object","required":["run_id","gate_id","evidence"],"properties":{"run_id":{"type":"string"},"gate_id":{"type":"string"},"evidence":{"type":"object"}}}),
        ),
        tool(
            "cerebellum_authorize",
            "Issue a short-lived action-bound permit after all gates pass",
            json!({"type":"object","required":["run_id","action"],"properties":{"run_id":{"type":"string"},"action":{"type":"object"},"ttl_seconds":{"type":"integer"}}}),
        ),
        tool(
            "cerebellum_complete_run",
            "Complete a workflow execution",
            json!({"type":"object","required":["run_id","outcome"],"properties":{"run_id":{"type":"string"},"outcome":{"type":"string"},"summary":{"type":"string"},"metrics":{"type":"object"}}}),
        ),
        tool(
            "cerebellum_search_skills",
            "Search published or quarantined Skill manifests",
            json!({"type":"object","properties":{"q":{"type":"string"},"include_quarantined":{"type":"boolean"},"limit":{"type":"integer"}}}),
        ),
        tool(
            "cerebellum_record_experience",
            "Record a redacted immutable coding-agent experience and classify it",
            json!({"type":"object","required":["schema_version","experience_id","task","task_family","repository","agent_id","model_id","source","outcome","created_at"],"additionalProperties":true}),
        ),
        tool(
            "cerebellum_record_feedback",
            "Attach feedback to an experience and recompute its learning decision",
            json!({"type":"object","required":["schema_version","feedback_id","experience_id","kind","score","confidence","source","created_at"],"additionalProperties":true}),
        ),
        tool(
            "cerebellum_retrieve_context",
            "Retrieve consolidated experience, failure, and anti-skill context",
            json!({"type":"object","required":["query"],"properties":{"query":{"type":"string"},"repository_id":{"type":"string"},"task_family":{"type":"string"},"limit":{"type":"integer"}}}),
        ),
        tool(
            "cerebellum_learning_status",
            "Inspect continual-learning counts, queue state, and metrics",
            json!({"type":"object","properties":{}}),
        ),
        tool(
            "cerebellum_route_expert",
            "Select one active request-level LoRA expert with shared or dense fallback",
            json!({"type":"object","required":["task_kind"],"properties":{"task_kind":{"type":"string","enum":["relevance","noise_filter","deduplication","retrieval_ranking","claim_relationship","acquisition_escalation","curriculum_priority","expected_information_gain","skill_workflow_routing","skill_workflow_evolution","temporal_grounding","knowledge_boundary","search_planning"]},"input":{},"source_domain":{"type":"string"},"topic_family":{"type":"string"},"available_expert_ids":{"type":"array","items":{"type":"string"}}}}),
        ),
        tool(
            "cerebellum_search_knowledge",
            "Search time-aware technical knowledge cards with evidence provenance",
            json!({"type":"object","required":["query"],"properties":{"query":{"type":"string"},"topic_ids":{"type":"array","items":{"type":"string","format":"uuid"}},"statuses":{"type":"array","items":{"type":"string","enum":["unverified","corroborated","contested","superseded","retracted"]}},"since":{"type":"string","format":"date-time"},"as_of":{"type":"string","format":"date-time"},"freshness_hours":{"type":"integer","minimum":1},"limit":{"type":"integer","minimum":1,"maximum":100}}}),
        ),
        tool(
            "cerebellum_recent_knowledge",
            "Retrieve the newest technical knowledge cards, optionally filtered by topic",
            json!({"type":"object","properties":{"topic_ids":{"type":"array","items":{"type":"string","format":"uuid"}},"statuses":{"type":"array","items":{"type":"string","enum":["unverified","corroborated","contested","superseded","retracted"]}},"since":{"type":"string","format":"date-time"},"freshness_hours":{"type":"integer","minimum":1},"limit":{"type":"integer","minimum":1,"maximum":100}}}),
        ),
        tool(
            "cerebellum_get_knowledge_card",
            "Get the latest immutable revision of one knowledge card",
            json!({"type":"object","required":["card_id"],"properties":{"card_id":{"type":"string","format":"uuid"}}}),
        ),
    ]
}

fn tool(name: &str, description: &str, input_schema: Value) -> Value {
    json!({"name":name,"description":description,"inputSchema":input_schema})
}

async fn call_tool(
    client: &Client,
    server_url: &str,
    token: &str,
    name: &str,
    mut args: Value,
) -> Result<Value> {
    let base = server_url.trim_end_matches('/');
    let (method, url, body) = match name {
        "cerebellum_plan" => ("POST", format!("{base}/v1/decisions"), Some(args)),
        "cerebellum_start_run" => ("POST", format!("{base}/v1/runs"), Some(args)),
        "cerebellum_record_event" => {
            let id = take_string(&mut args, "run_id")?;
            ("POST", format!("{base}/v1/runs/{id}/events"), Some(args))
        }
        "cerebellum_evaluate_gate" => {
            let id = take_string(&mut args, "run_id")?;
            let gate = take_string(&mut args, "gate_id")?;
            let evidence = args.get("evidence").cloned().unwrap_or_else(|| json!({}));
            (
                "POST",
                format!("{base}/v1/runs/{id}/gates/{gate}:evaluate"),
                Some(json!({"evidence":evidence})),
            )
        }
        "cerebellum_authorize" => ("POST", format!("{base}/v1/authorize"), Some(args)),
        "cerebellum_complete_run" => {
            let id = take_string(&mut args, "run_id")?;
            ("POST", format!("{base}/v1/runs/{id}/complete"), Some(args))
        }
        "cerebellum_search_skills" => {
            let query = serde_urlencoded::to_string(&args)?;
            ("GET", format!("{base}/v1/skills?{query}"), None)
        }
        "cerebellum_record_experience" => ("POST", format!("{base}/v1/experiences"), Some(args)),
        "cerebellum_record_feedback" => {
            let id = args
                .get("experience_id")
                .and_then(Value::as_str)
                .context("missing experience_id")?
                .to_owned();
            (
                "POST",
                format!("{base}/v1/experiences/{id}/feedback"),
                Some(args),
            )
        }
        "cerebellum_retrieve_context" => {
            ("POST", format!("{base}/v1/context:retrieve"), Some(args))
        }
        "cerebellum_learning_status" => ("GET", format!("{base}/v1/learning/status"), None),
        "cerebellum_route_expert" => ("POST", format!("{base}/v1/experts:route"), Some(args)),
        "cerebellum_search_knowledge" => {
            ("POST", format!("{base}/v1/knowledge:retrieve"), Some(args))
        }
        "cerebellum_recent_knowledge" => {
            if !args.is_object() {
                args = json!({});
            }
            args["query"] = Value::String(String::new());
            ("POST", format!("{base}/v1/knowledge:retrieve"), Some(args))
        }
        "cerebellum_get_knowledge_card" => {
            let id = take_string(&mut args, "card_id")?;
            ("GET", format!("{base}/v1/knowledge/cards/{id}"), None)
        }
        _ => anyhow::bail!("unknown tool: {name}"),
    };
    let request = match method {
        "GET" => client.get(url),
        _ => client.post(url),
    }
    .bearer_auth(token);
    let response = if let Some(body) = body {
        request.json(&body)
    } else {
        request
    }
    .send()
    .await?;
    let status = response.status();
    let value: Value = response
        .json()
        .await
        .context("sidecar returned invalid JSON")?;
    if !status.is_success() {
        anyhow::bail!(
            "sidecar returned {status}: {}",
            value
                .get("error")
                .and_then(Value::as_str)
                .unwrap_or("request failed")
        );
    }
    Ok(value)
}

fn take_string(value: &mut Value, key: &str) -> Result<String> {
    value
        .as_object_mut()
        .and_then(|map| map.remove(key))
        .and_then(|v| v.as_str().map(str::to_owned))
        .with_context(|| format!("missing {key}"))
}

async fn write_response<W: AsyncWrite + Unpin>(stdout: &mut W, value: &Value) -> Result<()> {
    stdout
        .write_all(serde_json::to_string(value)?.as_bytes())
        .await?;
    stdout.write_all(b"\n").await?;
    stdout.flush().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn tool_names_are_unique_and_scoped() {
        let tools = tools();
        let names: Vec<_> = tools
            .iter()
            .filter_map(|tool| tool.get("name").and_then(Value::as_str))
            .collect();
        assert_eq!(names.len(), 15);
        assert_eq!(names.iter().copied().collect::<HashSet<_>>().len(), 15);
        assert!(names.iter().all(|name| name.starts_with("cerebellum_")));
    }

    #[tokio::test]
    async fn initialize_advertises_tools_only() {
        let result = dispatch(
            &Client::new(),
            "http://127.0.0.1:1",
            "unused",
            "initialize",
            Value::Null,
        )
        .await
        .unwrap();
        assert_eq!(result["serverInfo"]["name"], "cerebellum");
        assert!(result["capabilities"].get("tools").is_some());
    }

    #[tokio::test]
    async fn ping_returns_empty_object() {
        let result = dispatch(
            &Client::new(),
            "http://127.0.0.1:1",
            "unused",
            "ping",
            Value::Null,
        )
        .await
        .unwrap();
        assert_eq!(result, json!({}));
    }

    #[tokio::test]
    async fn tools_list_returns_every_tool_with_schema() {
        let result = dispatch(
            &Client::new(),
            "http://127.0.0.1:1",
            "unused",
            "tools/list",
            Value::Null,
        )
        .await
        .unwrap();
        let listed = result["tools"].as_array().unwrap();
        assert_eq!(listed.len(), 15);
        for entry in listed {
            assert!(entry["name"].as_str().unwrap().starts_with("cerebellum_"));
            assert!(entry["inputSchema"]["type"].as_str().is_some());
        }
    }

    #[tokio::test]
    async fn unknown_method_is_rejected() {
        let error = dispatch(
            &Client::new(),
            "http://127.0.0.1:1",
            "unused",
            "resources/list",
            Value::Null,
        )
        .await
        .unwrap_err();
        assert!(
            error
                .to_string()
                .contains("method not found: resources/list")
        );
    }

    #[tokio::test]
    async fn tools_call_requires_a_tool_name() {
        let error = dispatch(
            &Client::new(),
            "http://127.0.0.1:1",
            "unused",
            "tools/call",
            json!({"arguments":{}}),
        )
        .await
        .unwrap_err();
        assert!(error.to_string().contains("missing tool name"));
    }

    #[tokio::test]
    async fn tools_call_rejects_unknown_tool() {
        let error = dispatch(
            &Client::new(),
            "http://127.0.0.1:1",
            "unused",
            "tools/call",
            json!({"name":"cerebellum_nope","arguments":{}}),
        )
        .await
        .unwrap_err();
        assert!(error.to_string().contains("unknown tool: cerebellum_nope"));
    }

    mod http_mock {
        use axum::Router;
        use axum::body::to_bytes;
        use axum::extract::{Request, State};
        use axum::http::{StatusCode, header};
        use axum::response::IntoResponse;
        use serde_json::Value;
        use tokio::sync::mpsc::{UnboundedReceiver, UnboundedSender, unbounded_channel};

        #[derive(Debug, Clone)]
        pub struct Recorded {
            pub method: String,
            pub uri: String,
            pub authorization: Option<String>,
            pub body: Value,
        }

        #[derive(Clone)]
        struct MockState {
            requests: UnboundedSender<Recorded>,
            status: StatusCode,
            body: String,
            content_type: &'static str,
        }

        pub struct Mock {
            pub requests: UnboundedReceiver<Recorded>,
        }

        async fn record(State(mock): State<MockState>, request: Request) -> impl IntoResponse {
            let method = request.method().to_string();
            let uri = request.uri().to_string();
            let authorization = request
                .headers()
                .get("authorization")
                .and_then(|value| value.to_str().ok())
                .map(str::to_owned);
            let bytes = to_bytes(request.into_body(), 1024 * 1024).await.unwrap();
            let body = serde_json::from_slice(&bytes).unwrap_or(Value::Null);
            let _ = mock.requests.send(Recorded {
                method,
                uri,
                authorization,
                body,
            });
            (
                mock.status,
                [(header::CONTENT_TYPE, mock.content_type)],
                mock.body,
            )
        }

        async fn spawn_server(state: MockState) -> String {
            let app = Router::new().fallback(record).with_state(state);
            let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
            let addr = listener.local_addr().unwrap();
            tokio::spawn(async move {
                axum::serve(listener, app).await.unwrap();
            });
            format!("http://{addr}")
        }

        pub async fn start(status: StatusCode, response: Value) -> (String, Mock) {
            let (requests, receiver) = unbounded_channel();
            let url = spawn_server(MockState {
                requests,
                status,
                body: response.to_string(),
                content_type: "application/json",
            })
            .await;
            (url, Mock { requests: receiver })
        }

        pub async fn start_raw(status: StatusCode, body: &str) -> String {
            let (requests, _receiver) = unbounded_channel();
            spawn_server(MockState {
                requests,
                status,
                body: body.to_string(),
                content_type: "text/plain",
            })
            .await
        }
    }

    use http_mock::start;

    async fn serve_lines(input: &str) -> Vec<Value> {
        let mut output: Vec<u8> = Vec::new();
        serve(
            Client::new(),
            "http://127.0.0.1:1",
            "token",
            input.as_bytes(),
            &mut output,
        )
        .await
        .unwrap();
        String::from_utf8(output)
            .unwrap()
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect()
    }

    #[tokio::test]
    async fn stdio_reports_parse_error_and_keeps_serving() {
        let responses =
            serve_lines("not json\n{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\"}\n").await;
        assert_eq!(responses.len(), 2);
        assert_eq!(responses[0]["id"], Value::Null);
        assert_eq!(responses[0]["error"]["code"], -32700);
        assert_eq!(responses[1]["id"], 1);
        assert_eq!(responses[1]["result"], json!({}));
    }

    #[tokio::test]
    async fn stdio_skips_blank_lines_and_notifications() {
        let responses = serve_lines(
            "\n   \n{\"method\":\"notifications/initialized\"}\n{\"id\":\"a\",\"method\":\"ping\"}\n",
        )
        .await;
        assert_eq!(responses.len(), 1);
        assert_eq!(responses[0]["id"], "a");
        assert_eq!(responses[0]["result"], json!({}));
    }

    #[tokio::test]
    async fn stdio_wraps_dispatch_errors_with_request_id() {
        let responses =
            serve_lines("{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"bogus/method\"}\n").await;
        assert_eq!(responses.len(), 1);
        assert_eq!(responses[0]["id"], 7);
        assert_eq!(responses[0]["error"]["code"], -32000);
        assert!(
            responses[0]["error"]["message"]
                .as_str()
                .unwrap()
                .contains("method not found")
        );
    }

    #[tokio::test]
    async fn tools_call_wraps_result_as_content_and_structured_content() {
        let (url, mut mock) = start(axum::http::StatusCode::OK, json!({"experiences":3})).await;
        let result = dispatch(
            &Client::new(),
            &url,
            "secret",
            "tools/call",
            json!({"name":"cerebellum_learning_status","arguments":{}}),
        )
        .await
        .unwrap();
        assert_eq!(result["isError"], false);
        assert_eq!(result["structuredContent"], json!({"experiences":3}));
        let text = result["content"][0]["text"].as_str().unwrap();
        assert_eq!(result["content"][0]["type"], "text");
        assert_eq!(
            serde_json::from_str::<Value>(text).unwrap(),
            json!({"experiences":3})
        );
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.method, "GET");
        assert_eq!(request.uri, "/v1/learning/status");
        assert_eq!(request.authorization.as_deref(), Some("Bearer secret"));
        assert!(mock.requests.try_recv().is_err());
    }

    #[tokio::test]
    async fn plan_preserves_learned_context_in_structured_result() {
        let expected = json!({
            "selected":{"workflow_id":"bugfix"},
            "memory_context":[{"kind":"anti_skill","warning":"verify first"}],
            "knowledge_context":[{"card":{"status":"contested"},"stale":true}]
        });
        let (url, mut mock) = start(axum::http::StatusCode::OK, expected.clone()).await;
        let result = call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_plan",
            json!({"task":"fix regression"}),
        )
        .await
        .unwrap();
        assert_eq!(result, expected);
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.uri, "/v1/decisions");
        assert_eq!(request.body, json!({"task":"fix regression"}));
    }

    #[test]
    fn plan_description_marks_learned_context_as_evidence() {
        let plan = tools()
            .into_iter()
            .find(|tool| tool["name"] == "cerebellum_plan")
            .unwrap();
        let description = plan["description"].as_str().unwrap();
        assert!(description.contains("non-executable evidence"));
        assert!(description.contains("unverified, contested, or stale"));
    }

    #[tokio::test]
    async fn record_event_moves_run_id_into_path() {
        let (url, mut mock) = start(axum::http::StatusCode::OK, json!({"ok":true})).await;
        call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_record_event",
            json!({"run_id":"run-1","kind":"edit","payload":{"file":"a.rs"}}),
        )
        .await
        .unwrap();
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.method, "POST");
        assert_eq!(request.uri, "/v1/runs/run-1/events");
        assert_eq!(
            request.body,
            json!({"kind":"edit","payload":{"file":"a.rs"}})
        );
    }

    #[tokio::test]
    async fn record_event_requires_run_id() {
        let error = call_tool(
            &Client::new(),
            "http://127.0.0.1:1",
            "token",
            "cerebellum_record_event",
            json!({"kind":"edit"}),
        )
        .await
        .unwrap_err();
        assert!(error.to_string().contains("missing run_id"));
    }

    #[tokio::test]
    async fn evaluate_gate_builds_evidence_only_body() {
        let (url, mut mock) = start(axum::http::StatusCode::OK, json!({"passed":true})).await;
        call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_evaluate_gate",
            json!({"run_id":"r1","gate_id":"g1","evidence":{"tests":"green"}}),
        )
        .await
        .unwrap();
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.method, "POST");
        assert_eq!(request.uri, "/v1/runs/r1/gates/g1:evaluate");
        assert_eq!(request.body, json!({"evidence":{"tests":"green"}}));
    }

    #[tokio::test]
    async fn search_skills_uses_query_string() {
        let (url, mut mock) = start(axum::http::StatusCode::OK, json!([])).await;
        call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_search_skills",
            json!({"q":"refactor","limit":5}),
        )
        .await
        .unwrap();
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.method, "GET");
        assert!(request.uri.starts_with("/v1/skills?"));
        assert!(request.uri.contains("q=refactor"));
        assert!(request.uri.contains("limit=5"));
        assert_eq!(request.body, Value::Null);
    }

    #[tokio::test]
    async fn record_feedback_targets_experience() {
        let (url, mut mock) = start(axum::http::StatusCode::OK, json!({"ok":true})).await;
        call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_record_feedback",
            json!({"experience_id":"exp-9","score":0.5}),
        )
        .await
        .unwrap();
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.uri, "/v1/experiences/exp-9/feedback");
        assert_eq!(request.body["experience_id"], "exp-9");
    }

    #[tokio::test]
    async fn record_feedback_requires_experience_id() {
        let error = call_tool(
            &Client::new(),
            "http://127.0.0.1:1",
            "token",
            "cerebellum_record_feedback",
            json!({"score":0.5}),
        )
        .await
        .unwrap_err();
        assert!(error.to_string().contains("missing experience_id"));
    }

    #[tokio::test]
    async fn recent_knowledge_forces_an_empty_query() {
        let (url, mut mock) = start(axum::http::StatusCode::OK, json!({"cards":[]})).await;
        call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_recent_knowledge",
            json!({"limit":2}),
        )
        .await
        .unwrap();
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.uri, "/v1/knowledge:retrieve");
        assert_eq!(request.body["query"], "");
        assert_eq!(request.body["limit"], 2);
    }

    #[tokio::test]
    async fn knowledge_card_is_fetched_by_id() {
        let (url, mut mock) = start(axum::http::StatusCode::OK, json!({"card":{}})).await;
        call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_get_knowledge_card",
            json!({"card_id":"11111111-1111-1111-1111-111111111111"}),
        )
        .await
        .unwrap();
        let request = mock.requests.try_recv().unwrap();
        assert_eq!(request.method, "GET");
        assert_eq!(
            request.uri,
            "/v1/knowledge/cards/11111111-1111-1111-1111-111111111111"
        );
    }

    #[tokio::test]
    async fn sidecar_error_status_is_surfaced() {
        let (url, _requests) = start(
            axum::http::StatusCode::UNPROCESSABLE_ENTITY,
            json!({"error":"bad evidence"}),
        )
        .await;
        let error = call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_learning_status",
            json!({}),
        )
        .await
        .unwrap_err();
        let message = error.to_string();
        assert!(message.contains("422"), "unexpected message: {message}");
        assert!(
            message.contains("bad evidence"),
            "unexpected message: {message}"
        );
    }

    #[tokio::test]
    async fn sidecar_non_json_response_is_rejected() {
        let url = http_mock::start_raw(axum::http::StatusCode::OK, "not json at all").await;
        let error = call_tool(
            &Client::new(),
            &url,
            "token",
            "cerebellum_learning_status",
            json!({}),
        )
        .await
        .unwrap_err();
        assert!(error.to_string().contains("invalid JSON"));
    }

    #[test]
    fn take_string_extracts_and_removes() {
        let mut value = json!({"run_id":"r1","other":1});
        assert_eq!(take_string(&mut value, "run_id").unwrap(), "r1");
        assert_eq!(value, json!({"other":1}));
    }

    #[test]
    fn take_string_rejects_missing_and_non_string() {
        let mut value = json!({"other":1});
        assert!(take_string(&mut value, "run_id").is_err());
        let mut value = json!({"run_id":42});
        assert!(take_string(&mut value, "run_id").is_err());
        let mut value = json!("not an object");
        assert!(take_string(&mut value, "run_id").is_err());
    }
}
