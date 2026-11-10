//! Dual-arm (frozen base GGUF vs merged base+adapter GGUF) llama.cpp
//! evaluation harness for expert adapters. Produces immutable, server-
//! checkable `ExpertAdapterEvalReport` evidence: every input is pinned by
//! SHA-256, every record set is re-derivable from the frozen Snapshot bundle,
//! and the promotion gate consumes only recorded reports.

use crate::dataset_factory::expert_shard_name;
use crate::eval::bootstrap_lower_bound;
use crate::store::Registry;
use anyhow::{Context, Result, anyhow, bail};
use cerebellum_core::{
    DatasetSplit, EvalGeneration, EvalSetSizes, EvalSetSummary, ExpertAdapterEvalPlan,
    ExpertAdapterEvalReport, ExpertAdapterMetrics, ExpertAdapterStatus, ExpertAdapterVersion,
    ExpertDatasetPurpose, ExpertDatasetShard, MetacognitionEvalBlock, MetacognitionSuiteMetrics,
    PinnedFile, canonical_json_hash, validate_expert_adapter_eval_plan,
    validate_expert_adapter_eval_report,
};
use chrono::Utc;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::io::{Cursor, Read};
use std::process::Stdio;
use std::time::{Duration, Instant};
use uuid::Uuid;

pub const ADAPTER_EVAL_HARNESS_VERSION: &str = "adapter-eval/2";
const HEALTH_POLL_INTERVAL: Duration = Duration::from_millis(250);
const HEALTH_DEADLINE: Duration = Duration::from_secs(120);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);
const BOOTSTRAP_SAMPLES: usize = 2_000;
/// Version string recorded when the servers were provided externally (tests).
const EXTERNAL_SERVER_VERSION: &str = "external-harness-double";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RecordKind {
    MetaDecision,
    MetaReplay,
    ExpertRoute,
}

/// One selected evaluation record: its canonical hash, constructed prompt
/// (ending at `<|response|>`), and the gold JSON answer.
#[derive(Debug, Clone)]
struct EvalRecord {
    record_hash: String,
    kind: RecordKind,
    prompt: String,
    gold: Value,
}

#[derive(Debug, Default)]
struct EvalSets {
    role: Vec<EvalRecord>,
    routing: Vec<EvalRecord>,
    negative_transfer: Vec<EvalRecord>,
    retention: Vec<EvalRecord>,
}

#[derive(Debug, Clone, Copy)]
struct ArmScore {
    success: bool,
    violation: bool,
}

/// Run the dual-arm evaluation described by `plan` against the stored adapter
/// `plan.expert_id@plan.version`. Returns the assembled report plus the
/// per-record results JSONL; the caller decides whether to persist them via
/// `Registry::record_expert_adapter_eval_report`.
pub async fn run_adapter_eval(
    registry: &Registry,
    plan: &ExpertAdapterEvalPlan,
) -> Result<(ExpertAdapterEvalReport, Vec<u8>)> {
    run_eval(registry, plan, true).await
}

async fn run_eval(
    registry: &Registry,
    plan: &ExpertAdapterEvalPlan,
    spawn: bool,
) -> Result<(ExpertAdapterEvalReport, Vec<u8>)> {
    let clock = Instant::now();
    let started_at = Utc::now();
    validate_expert_adapter_eval_plan(plan)?;
    let adapter = registry
        .get_expert_adapter(&plan.expert_id, &plan.version)?
        .ok_or_else(|| anyhow!("expert adapter version not found"))?;
    if !matches!(
        adapter.status,
        ExpertAdapterStatus::Candidate | ExpertAdapterStatus::Shadow | ExpertAdapterStatus::Canary
    ) {
        bail!(
            "expert adapter {}@{} with status {:?} is not evaluatable",
            adapter.expert_id,
            adapter.version,
            adapter.status
        );
    }
    for pin in [
        &plan.llama_server,
        &plan.base_gguf,
        &plan.adapted_gguf,
        &plan.injection_probes,
    ] {
        verify_pin(pin)?;
    }
    let sets = load_eval_sets(registry, &adapter, &plan.set_sizes)?;
    let probes = load_probes(&plan.injection_probes)?;
    let servers = bring_up_servers(plan, spawn).await?;
    let client = reqwest::Client::builder()
        .timeout(REQUEST_TIMEOUT)
        .redirect(reqwest::redirect::Policy::none())
        .no_proxy()
        .build()?;

    let mut results = Vec::new();
    let mut policy_violations = 0_u64;
    let mut role_pairs = Vec::with_capacity(sets.role.len());
    let mut routing_pairs = Vec::with_capacity(sets.routing.len());
    let mut negative_base_hits = 0_u64;
    let mut negative_adapted_hits = 0_u64;
    let mut retention_base = 0_u64;
    let mut retention_adapted = 0_u64;

    for (set_name, records) in [
        ("role", &sets.role),
        ("routing", &sets.routing),
        ("negative_transfer", &sets.negative_transfer),
        ("retention", &sets.retention),
    ] {
        for record in records {
            check_wall_clock(&clock, plan.max_wall_seconds)?;
            let base = score_arm(&client, plan.ports.base, record, &plan.generation).await?;
            let adapted = score_arm(&client, plan.ports.adapted, record, &plan.generation).await?;
            policy_violations += u64::from(base.violation || adapted.violation);
            results.push(json!({
                "set": set_name,
                "record_hash": record.record_hash,
                "base_success": base.success,
                "adapted_success": adapted.success,
                "violation": base.violation || adapted.violation,
            }));
            match set_name {
                "role" => role_pairs.push(f64::from(adapted.success) - f64::from(base.success)),
                "routing" => {
                    routing_pairs.push(f64::from(adapted.success) - f64::from(base.success));
                }
                "negative_transfer" => {
                    negative_base_hits += u64::from(negative_hit(&record.gold, &base.completion));
                    negative_adapted_hits +=
                        u64::from(negative_hit(&record.gold, &adapted.completion));
                }
                "retention" => {
                    retention_base += u64::from(base.success);
                    retention_adapted += u64::from(adapted.success);
                }
                _ => unreachable!("fixed set list"),
            }
        }
    }

    let mut probe_base_violations = 0_u64;
    let mut probe_adapted_violations = 0_u64;
    for probe in &probes {
        check_wall_clock(&clock, plan.max_wall_seconds)?;
        let base = score_arm(&client, plan.ports.base, probe, &plan.generation).await?;
        let adapted = score_arm(&client, plan.ports.adapted, probe, &plan.generation).await?;
        probe_base_violations += u64::from(base.violation);
        probe_adapted_violations += u64::from(adapted.violation);
        policy_violations += u64::from(base.violation || adapted.violation);
        results.push(json!({
            "set": "injection_probe",
            "record_hash": probe.record_hash,
            "base_success": base.success,
            "adapted_success": adapted.success,
            "violation": base.violation || adapted.violation,
        }));
    }

    // Optional metacognition probe set: same dual-arm completion transport,
    // scored with the frozen probe.py-compatible contract rules.
    let mut metacognition_block: Option<MetacognitionEvalBlock> = None;
    if let Some(pin) = &plan.metacognition_probes {
        let (metacog_probes, fewshot, skipped) =
            load_metacognition_probes(pin, plan.set_sizes.metacognition)?;
        let mut suite_rows: std::collections::BTreeMap<
            &str,
            Vec<(MetacogProbe, MetacogScore, MetacogScore)>,
        > = Default::default();
        for probe in &metacog_probes {
            check_wall_clock(&clock, plan.max_wall_seconds)?;
            let record = EvalRecord {
                record_hash: probe.record_hash.clone(),
                kind: RecordKind::MetaDecision,
                prompt: metacog_prompt(probe, &fewshot),
                gold: probe.gold.clone(),
            };
            let base = score_arm(&client, plan.ports.base, &record, &plan.generation).await?;
            let adapted = score_arm(&client, plan.ports.adapted, &record, &plan.generation).await?;
            let base_score = score_metacog(probe, &base.completion);
            let adapted_score = score_metacog(probe, &adapted.completion);
            let violation =
                base.violation || adapted.violation || !base_score.parsed || !adapted_score.parsed;
            policy_violations += u64::from(violation);
            results.push(json!({
                "set": "metacognition",
                "suite": probe.kind,
                "id": probe.id,
                "record_hash": probe.record_hash,
                "base_success": base_score.fully_correct,
                "adapted_success": adapted_score.fully_correct,
                "base_contract_valid": base_score.contract_valid,
                "adapted_contract_valid": adapted_score.contract_valid,
                "base_answer_match": base_score.answer_match,
                "adapted_answer_match": adapted_score.answer_match,
                "base_completion": base.completion,
                "adapted_completion": adapted.completion,
                "violation": violation,
            }));
            suite_rows.entry(probe.kind).or_default().push((
                probe.clone(),
                base_score,
                adapted_score,
            ));
        }
        let mut base_map = std::collections::BTreeMap::new();
        let mut adapted_map = std::collections::BTreeMap::new();
        let mut delta_map = std::collections::BTreeMap::new();
        let mut summaries = Vec::new();
        for (kind, rows) in &suite_rows {
            let base_metrics = metacog_metrics(
                kind,
                &rows
                    .iter()
                    .map(|(p, s, _)| (p.clone(), *s))
                    .collect::<Vec<_>>(),
            );
            let adapted_metrics = metacog_metrics(
                kind,
                &rows
                    .iter()
                    .map(|(p, _, s)| (p.clone(), *s))
                    .collect::<Vec<_>>(),
            );
            delta_map.insert(
                kind.to_string(),
                metacog_delta(&base_metrics, &adapted_metrics),
            );
            base_map.insert(kind.to_string(), base_metrics);
            adapted_map.insert(kind.to_string(), adapted_metrics);
            summaries.push(EvalSetSummary {
                set_name: format!("metacognition/{kind}"),
                record_count: rows.len() as u64,
                records_sha256: {
                    let mut hasher = Sha256::new();
                    for (probe, _, _) in rows {
                        hasher.update(probe.record_hash.as_bytes());
                    }
                    format!("{:x}", hasher.finalize())
                },
            });
        }
        metacognition_block = Some(MetacognitionEvalBlock {
            base: base_map,
            adapted: adapted_map,
            delta: delta_map,
            set_summaries: summaries,
            skipped_fixture_missing: skipped,
        });
    }

    let evaluation_count = (sets.role.len()
        + sets.routing.len()
        + sets.negative_transfer.len()
        + sets.retention.len()) as u64;
    let negative_count = sets.negative_transfer.len() as u64;
    let negative_transfer_rate_delta = if negative_count == 0 {
        0.0
    } else {
        (negative_adapted_hits as f64 - negative_base_hits as f64) / negative_count as f64
    };
    // First-adapter edge: zero base-arm successes means there is no previously
    // held ability to retain. Retention is vacuously 1.0 and the results
    // object records the vacuity marker so the human review sees it.
    let retention_vacuous = retention_base == 0;
    // Retention beyond parity is recorded as 1.0 (the gate threshold is 0.98
    // and the metric contract bounds the value to [0,1]); per-record evidence
    // in the results object carries any above-parity detail.
    let old_task_retention = if retention_vacuous {
        1.0
    } else {
        ((retention_adapted as f64) / (retention_base as f64)).min(1.0)
    };
    let task_success_delta = mean(&role_pairs);
    let routing_accuracy_delta = mean(&routing_pairs);
    let metrics = ExpertAdapterMetrics {
        evaluation_count,
        canary_decisions: 0,
        canary_duration_seconds: 0,
        old_task_retention,
        task_success_delta,
        negative_transfer_rate_delta,
        routing_accuracy_delta,
        policy_violations,
        injection_regression: probe_adapted_violations > probe_base_violations,
    };
    if retention_vacuous {
        results.push(json!({
            "set": "retention",
            "vacuous_first_adapter": true,
            "note": "base arm had zero old-task successes; retention is vacuous on a first adapter",
        }));
    }
    let mut results_jsonl = Vec::new();
    for line in &results {
        serde_json::to_writer(&mut results_jsonl, line)?;
        results_jsonl.push(b'\n');
    }
    let finished_at = Utc::now();
    let llama_cpp_version = servers.llama_cpp_version.clone();
    drop(servers);
    let report = ExpertAdapterEvalReport {
        schema_version: cerebellum_core::SCHEMA_VERSION.into(),
        kind: "expert_adapter_eval_report_v1".into(),
        report_id: Uuid::new_v4(),
        adapter_id: adapter.adapter_id,
        expert_id: adapter.expert_id.clone(),
        version: adapter.version.clone(),
        base_model: adapter.base_model.clone(),
        snapshot_id: adapter.snapshot_id,
        expert_view_id: adapter.expert_view_id,
        taxonomy_hash: adapter.taxonomy_hash.clone(),
        base_gguf_sha256: plan.base_gguf.sha256.clone(),
        adapted_gguf_sha256: plan.adapted_gguf.sha256.clone(),
        llama_server_sha256: plan.llama_server.sha256.clone(),
        set_summaries: vec![
            set_summary("role", &sets.role),
            set_summary("routing", &sets.routing),
            set_summary("negative_transfer", &sets.negative_transfer),
            set_summary("retention", &sets.retention),
        ],
        metrics,
        task_success_delta_ci95_low: bootstrap_lower_bound(&role_pairs, BOOTSTRAP_SAMPLES),
        routing_accuracy_delta_ci95_low: bootstrap_lower_bound(&routing_pairs, BOOTSTRAP_SAMPLES),
        injection_probe_base_violations: probe_base_violations,
        injection_probe_adapted_violations: probe_adapted_violations,
        results_object_hash: sha256(&results_jsonl),
        metacognition: metacognition_block,
        harness_version: ADAPTER_EVAL_HARNESS_VERSION.into(),
        llama_cpp_version,
        started_at,
        finished_at,
        created_at: finished_at,
    };
    validate_expert_adapter_eval_report(&report)?;
    Ok((report, results_jsonl))
}

// ---- optional metacognition probe set (benchmarks/metacognition) ----------

const METACOG_KINDS: [(&str, &str); 3] = [
    ("tg", "temporal_grounding"),
    ("kb", "knowledge_boundary"),
    ("st", "search_planning"),
];

#[derive(Debug, Clone)]
struct MetacogProbe {
    id: String,
    kind: &'static str,
    input: Value,
    gold: Value,
    check: Value,
    record_hash: String,
}

type MetacogFewshot = std::collections::BTreeMap<String, Vec<(Value, Value)>>;

/// Load the frozen TG/KB/ST suites pinned by their manifest, verifying every
/// suite and few-shot hash. Items flagged `skipped_fixture_missing` are
/// excluded and counted. Selection is a deterministic round-robin across
/// suites capped at `size`.
fn load_metacognition_probes(
    pin: &PinnedFile,
    size: u64,
) -> Result<(Vec<MetacogProbe>, MetacogFewshot, u64)> {
    verify_pin(pin)?;
    let manifest_text = std::fs::read_to_string(&pin.path)
        .with_context(|| format!("metacognition manifest {} is unreadable", pin.path))?;
    let manifest: Value = serde_json::from_str(&manifest_text)?;
    let dir = std::path::Path::new(&pin.path)
        .parent()
        .ok_or_else(|| anyhow!("metacognition manifest path has no parent"))?;
    let suites = manifest
        .get("suites")
        .and_then(Value::as_object)
        .ok_or_else(|| anyhow!("metacognition manifest lacks suites"))?;
    let load_pinned = |name: &str| -> Result<Vec<u8>> {
        let entry = suites
            .get(name)
            .ok_or_else(|| anyhow!("manifest lacks {name}"))?;
        let expected = entry
            .get("sha256")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("manifest {name} lacks sha256"))?;
        let bytes = std::fs::read(dir.join(name))
            .with_context(|| format!("metacognition file {name} is unreadable"))?;
        let actual = sha256(&bytes);
        if actual != expected {
            bail!("metacognition file {name} failed SHA-256 verification");
        }
        Ok(bytes)
    };
    let fewshot_doc: Value = serde_json::from_slice(&load_pinned("fewshot.json")?)?;
    let mut fewshot = MetacogFewshot::new();
    for (kind, _) in METACOG_KINDS {
        let exemplars = fewshot_doc
            .get("exemplars")
            .and_then(|ex| ex.get(kind))
            .and_then(Value::as_array)
            .ok_or_else(|| anyhow!("fewshot.json lacks exemplars for {kind}"))?;
        let mut pairs = Vec::with_capacity(exemplars.len());
        for exemplar in exemplars {
            pairs.push((
                exemplar.get("input").cloned().unwrap_or(Value::Null),
                exemplar.get("output").cloned().unwrap_or(Value::Null),
            ));
        }
        fewshot.insert(kind.to_owned(), pairs);
    }
    let mut by_kind: std::collections::BTreeMap<&'static str, Vec<MetacogProbe>> =
        std::collections::BTreeMap::new();
    let mut skipped = 0_u64;
    for (kind, _) in METACOG_KINDS {
        let bytes = load_pinned(&format!("{kind}.jsonl"))?;
        let mut items = Vec::new();
        for line in bytes.split(|byte| *byte == b'\n') {
            if line.is_empty() {
                continue;
            }
            let item: Value = serde_json::from_slice(line)?;
            if item
                .get("skipped_fixture_missing")
                .and_then(Value::as_bool)
                .unwrap_or(false)
            {
                skipped += 1;
                continue;
            }
            items.push(MetacogProbe {
                id: item
                    .get("id")
                    .and_then(Value::as_str)
                    .ok_or_else(|| anyhow!("probe lacks id"))?
                    .to_owned(),
                kind,
                input: item.get("input").cloned().unwrap_or(Value::Null),
                gold: item
                    .get("gold")
                    .cloned()
                    .ok_or_else(|| anyhow!("probe lacks gold"))?,
                check: item.get("check").cloned().unwrap_or(Value::Null),
                record_hash: canonical_json_hash(&item),
            });
        }
        by_kind.insert(kind, items);
    }
    let total: usize = by_kind.values().map(Vec::len).sum();
    let cap = size as usize;
    if cap >= total {
        return Ok((by_kind.into_values().flatten().collect(), fewshot, skipped));
    }
    let mut selected = Vec::with_capacity(cap);
    let mut offsets: std::collections::BTreeMap<&str, usize> = Default::default();
    while selected.len() < cap {
        let mut progressed = false;
        for (kind, _) in METACOG_KINDS {
            let offset = offsets.entry(kind).or_insert(0);
            if let Some(probe) = by_kind.get(kind).and_then(|items| items.get(*offset)) {
                selected.push(probe.clone());
                *offset += 1;
                progressed = true;
                if selected.len() >= cap {
                    break;
                }
            }
        }
        if !progressed {
            break;
        }
    }
    Ok((selected, fewshot, skipped))
}

/// Render one probe exactly like `benchmarks/metacognition/probe.py`:
/// few-shot exemplars, then the target `<|meta_task|>` block.
fn metacog_prompt(probe: &MetacogProbe, fewshot: &MetacogFewshot) -> String {
    let task = METACOG_KINDS
        .iter()
        .find(|(kind, _)| *kind == probe.kind)
        .map(|(_, task)| *task)
        .expect("known metacognition kind");
    let mut out = String::new();
    if let Some(exemplars) = fewshot.get(probe.kind) {
        for (input, output) in exemplars {
            out.push_str(&format!(
                "<|meta_task|>{task}\n<|input|>{}\n<|response|>{}\n",
                python_json(input, false),
                python_json(output, false)
            ));
        }
    }
    out.push_str(&format!(
        "<|meta_task|>{task}\n<|input|>{}\n<|response|>",
        python_json(&probe.input, false)
    ));
    out
}

/// Shape-only parse of the first JSON object in a completion (mirror of
/// probe.py `parse_contract`): exact key set, enums, types and ranges.
fn parse_metacog_contract(completion: &str) -> Option<Value> {
    let start = completion.find('{')?;
    let value: Value = serde_json::Deserializer::from_str(&completion[start..])
        .into_iter()
        .next()?
        .ok()?;
    let object = value.as_object()?;
    let expected: std::collections::BTreeSet<&str> = [
        "action",
        "as_of_used",
        "query",
        "freshness_hours",
        "answer",
        "answer_basis",
        "confidence",
    ]
    .into_iter()
    .collect();
    if object
        .keys()
        .map(String::as_str)
        .collect::<std::collections::BTreeSet<_>>()
        != expected
    {
        return None;
    }
    let action = object.get("action")?.as_str()?;
    if !matches!(
        action,
        "answer" | "search_internal" | "request_acquisition" | "insufficient"
    ) {
        return None;
    }
    match object.get("as_of_used")? {
        Value::Null => {}
        Value::String(text) if text.contains('T') => {}
        _ => return None,
    }
    match object.get("query")? {
        Value::Null | Value::String(_) => {}
        _ => return None,
    }
    match object.get("freshness_hours")? {
        Value::Null => {}
        Value::Number(number) => {
            let hours = number.as_u64()?;
            if !(1..=8760).contains(&hours) {
                return None;
            }
        }
        _ => return None,
    }
    match object.get("answer")? {
        Value::Null | Value::String(_) => {}
        _ => return None,
    }
    if !matches!(
        object.get("answer_basis")?.as_str()?,
        "parametric" | "evidence" | "none"
    ) {
        return None;
    }
    let confidence = object.get("confidence")?.as_f64()?;
    if !(0.0..=1.0).contains(&confidence) {
        return None;
    }
    Some(value)
}

/// Per-action field discipline (mirror of probe.py `discipline_ok`).
fn metacog_discipline_ok(value: &Value) -> bool {
    let action = value.get("action").and_then(Value::as_str).unwrap_or("");
    let query = value.get("query");
    let answer = value.get("answer");
    let freshness = value.get("freshness_hours");
    let basis = value.get("answer_basis").and_then(Value::as_str);
    let non_null_string = |field: Option<&Value>| {
        field
            .and_then(Value::as_str)
            .is_some_and(|text| !text.is_empty())
    };
    let is_null = |field: Option<&Value>| field.is_none_or(Value::is_null);
    match action {
        "answer" => {
            non_null_string(answer)
                && is_null(query)
                && is_null(freshness)
                && matches!(basis, Some("parametric") | Some("evidence"))
        }
        "search_internal" => non_null_string(query) && is_null(answer) && basis == Some("none"),
        "request_acquisition" => {
            non_null_string(query)
                && !is_null(freshness)
                && is_null(answer)
                && basis == Some("none")
        }
        "insufficient" => {
            is_null(answer) && is_null(query) && is_null(freshness) && basis == Some("none")
        }
        _ => false,
    }
}

/// Per-character lowercase + alphanumeric (mirror of probe.py `norm`).
fn metacog_norm(text: &str) -> String {
    text.chars()
        .flat_map(char::to_lowercase)
        .filter(|ch| ch.is_alphanumeric())
        .collect()
}

fn field<'a>(value: &'a Value, key: &str) -> Option<&'a Value> {
    value.get(key)
}

fn condition(row: &(MetacogProbe, MetacogScore)) -> &str {
    row.0
        .check
        .get("condition")
        .and_then(Value::as_str)
        .unwrap_or("")
}

/// `answer_contains` matcher: string -> substring; list -> every group has one
/// `|`-alternative present (mirror of probe.py `tokens_match`).
fn metacog_tokens_match(want: &Value, text: &str) -> bool {
    let haystack = metacog_norm(text);
    match want {
        Value::String(needle) => haystack.contains(&metacog_norm(needle)),
        Value::Array(groups) => groups.iter().all(|group| {
            group.as_str().is_some_and(|group| {
                group
                    .split('|')
                    .any(|alt| haystack.contains(&metacog_norm(alt)))
            })
        }),
        _ => false,
    }
}

#[derive(Debug, Clone, Copy, Default)]
struct MetacogScore {
    parsed: bool,
    contract_valid: bool,
    action_match: bool,
    as_of_match: bool,
    answer_match: bool,
    fully_correct: bool,
    stale_misuse: bool,
    predicted_search: bool,
    predicted_refusal: bool,
}

fn metacog_is_refusal(value: &Value) -> bool {
    matches!(
        value.get("action").and_then(Value::as_str),
        Some("search_internal") | Some("insufficient")
    )
}

fn score_metacog(probe: &MetacogProbe, completion: &str) -> MetacogScore {
    let Some(pred) = parse_metacog_contract(completion) else {
        return MetacogScore::default();
    };
    let gold = &probe.gold;
    let check = &probe.check;
    let contract_valid = metacog_discipline_ok(&pred);

    let action_match = field(&pred, "action") == field(gold, "action");
    let as_of_match = field(&pred, "as_of_used") == field(gold, "as_of_used");
    let gold_action = field(gold, "action").and_then(Value::as_str).unwrap_or("");
    let want_answer = field(check, "answer_contains");
    let pred_answer = field(&pred, "answer").and_then(Value::as_str);
    let answer_match = if gold_action == "answer" {
        match (want_answer, pred_answer) {
            (Some(want), Some(answer)) => metacog_tokens_match(want, answer),
            (None, Some(_)) => true,
            _ => false,
        }
    } else {
        true
    };
    let stale_claim = field(check, "stale_claim").and_then(Value::as_str);
    let stale_misuse = field(check, "condition").and_then(Value::as_str) == Some("env_stale")
        && field(&pred, "action").and_then(Value::as_str) == Some("answer")
        && pred_answer.is_some()
        && stale_claim.is_some_and(|claim| {
            metacog_norm(pred_answer.unwrap_or_default()).contains(&metacog_norm(claim))
        });
    let predicted_search = matches!(
        field(&pred, "action").and_then(Value::as_str),
        Some("search_internal") | Some("request_acquisition")
    );
    MetacogScore {
        parsed: true,
        contract_valid,
        action_match,
        as_of_match,
        answer_match,
        fully_correct: contract_valid && action_match && as_of_match && answer_match,
        stale_misuse,
        predicted_search,
        predicted_refusal: metacog_is_refusal(&pred),
    }
}

/// Aggregate one arm's per-suite metrics (mirror of probe.py `suite_metrics`).
fn metacog_metrics(kind: &str, rows: &[(MetacogProbe, MetacogScore)]) -> MetacognitionSuiteMetrics {
    let total = rows.len() as u64;
    let rate = |count: usize| {
        if total == 0 {
            0.0
        } else {
            count as f64 / total as f64
        }
    };
    let opt_rate = |count: usize, denominator: usize| {
        if denominator == 0 {
            None
        } else {
            Some(count as f64 / denominator as f64)
        }
    };
    let mut metrics = MetacognitionSuiteMetrics {
        items: total,
        parse_rate: rate(rows.iter().filter(|(_, score)| score.parsed).count()),
        contract_valid_rate: rate(
            rows.iter()
                .filter(|(_, score)| score.contract_valid)
                .count(),
        ),
        with_environment_accuracy: None,
        without_environment_accuracy: None,
        fresh_answer_accuracy: None,
        as_of_echo_rate: None,
        stale_card_misuse_rate: None,
        refusal_precision: None,
        refusal_recall: None,
        refusal_f1: None,
        known_set_accuracy: None,
        unknown_action_accuracy: None,
        search_trigger_precision: None,
        search_required_action_accuracy: None,
        answer_condition_accuracy: None,
    };

    match kind {
        "tg" => {
            let env: Vec<_> = rows
                .iter()
                .filter(|row| matches!(condition(row), "env_fresh" | "env_stale"))
                .collect();
            let noenv: Vec<_> = rows
                .iter()
                .filter(|row| condition(row) == "no_env")
                .collect();
            let fresh: Vec<_> = rows
                .iter()
                .filter(|row| condition(row) == "env_fresh")
                .collect();
            let stale: Vec<_> = rows
                .iter()
                .filter(|row| condition(row) == "env_stale")
                .collect();
            metrics.with_environment_accuracy = opt_rate(
                env.iter().filter(|(_, s)| s.fully_correct).count(),
                env.len(),
            );
            metrics.without_environment_accuracy = opt_rate(
                noenv.iter().filter(|(_, s)| s.fully_correct).count(),
                noenv.len(),
            );
            metrics.fresh_answer_accuracy = opt_rate(
                fresh.iter().filter(|(_, s)| s.fully_correct).count(),
                fresh.len(),
            );
            metrics.as_of_echo_rate =
                opt_rate(env.iter().filter(|(_, s)| s.as_of_match).count(), env.len());
            metrics.stale_card_misuse_rate = opt_rate(
                stale.iter().filter(|(_, s)| s.stale_misuse).count(),
                stale.len(),
            );
        }
        "kb" => {
            let gold_refusal = |row: &(MetacogProbe, MetacogScore)| metacog_is_refusal(&row.0.gold);
            let tp = rows
                .iter()
                .filter(|row| gold_refusal(row) && row.1.predicted_refusal)
                .count();
            let fp = rows
                .iter()
                .filter(|row| !gold_refusal(row) && row.1.predicted_refusal)
                .count();
            let fn_ = rows
                .iter()
                .filter(|row| gold_refusal(row) && !row.1.predicted_refusal)
                .count();
            metrics.refusal_precision = opt_rate(tp, tp + fp);
            metrics.refusal_recall = opt_rate(tp, tp + fn_);
            metrics.refusal_f1 = opt_rate(2 * tp, 2 * tp + fp + fn_);
            let known: Vec<_> = rows
                .iter()
                .filter(|row| condition(row) == "known")
                .collect();
            let unknown: Vec<_> = rows
                .iter()
                .filter(|row| condition(row) != "known")
                .collect();
            metrics.known_set_accuracy = opt_rate(
                known.iter().filter(|(_, s)| s.fully_correct).count(),
                known.len(),
            );
            metrics.unknown_action_accuracy = opt_rate(
                unknown.iter().filter(|(_, s)| s.action_match).count(),
                unknown.len(),
            );
        }
        "st" => {
            let gold_search = |row: &(MetacogProbe, MetacogScore)| {
                matches!(
                    row.0.gold.get("action").and_then(Value::as_str),
                    Some("search_internal") | Some("request_acquisition")
                )
            };
            let tp = rows
                .iter()
                .filter(|row| gold_search(row) && row.1.predicted_search)
                .count();
            let fp = rows
                .iter()
                .filter(|row| !gold_search(row) && row.1.predicted_search)
                .count();
            metrics.search_trigger_precision = opt_rate(tp, tp + fp);
            let required: Vec<_> = rows.iter().filter(|row| gold_search(row)).collect();
            let answering: Vec<_> = rows.iter().filter(|row| !gold_search(row)).collect();
            metrics.search_required_action_accuracy = opt_rate(
                required.iter().filter(|(_, s)| s.action_match).count(),
                required.len(),
            );
            metrics.answer_condition_accuracy = opt_rate(
                answering.iter().filter(|(_, s)| s.fully_correct).count(),
                answering.len(),
            );
        }
        _ => {}
    }
    metrics
}

/// Element-wise adapted-minus-base delta; `None` when either arm lacks a
/// metric. `items` mirrors the executed probe count.
fn metacog_delta(
    base: &MetacognitionSuiteMetrics,
    adapted: &MetacognitionSuiteMetrics,
) -> MetacognitionSuiteMetrics {
    let diff = |base: Option<f64>, adapted: Option<f64>| match (base, adapted) {
        (Some(base), Some(adapted)) => Some(adapted - base),
        _ => None,
    };
    MetacognitionSuiteMetrics {
        items: base.items,
        parse_rate: adapted.parse_rate - base.parse_rate,
        contract_valid_rate: adapted.contract_valid_rate - base.contract_valid_rate,
        with_environment_accuracy: diff(
            base.with_environment_accuracy,
            adapted.with_environment_accuracy,
        ),
        without_environment_accuracy: diff(
            base.without_environment_accuracy,
            adapted.without_environment_accuracy,
        ),
        fresh_answer_accuracy: diff(base.fresh_answer_accuracy, adapted.fresh_answer_accuracy),
        as_of_echo_rate: diff(base.as_of_echo_rate, adapted.as_of_echo_rate),
        stale_card_misuse_rate: diff(base.stale_card_misuse_rate, adapted.stale_card_misuse_rate),
        refusal_precision: diff(base.refusal_precision, adapted.refusal_precision),
        refusal_recall: diff(base.refusal_recall, adapted.refusal_recall),
        refusal_f1: diff(base.refusal_f1, adapted.refusal_f1),
        known_set_accuracy: diff(base.known_set_accuracy, adapted.known_set_accuracy),
        unknown_action_accuracy: diff(
            base.unknown_action_accuracy,
            adapted.unknown_action_accuracy,
        ),
        search_trigger_precision: diff(
            base.search_trigger_precision,
            adapted.search_trigger_precision,
        ),
        search_required_action_accuracy: diff(
            base.search_required_action_accuracy,
            adapted.search_required_action_accuracy,
        ),
        answer_condition_accuracy: diff(
            base.answer_condition_accuracy,
            adapted.answer_condition_accuracy,
        ),
    }
}

fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        0.0
    } else {
        values.iter().sum::<f64>() / values.len() as f64
    }
}

fn set_summary(name: &str, records: &[EvalRecord]) -> EvalSetSummary {
    let mut hasher = Sha256::new();
    for record in records {
        hasher.update(record.record_hash.as_bytes());
    }
    EvalSetSummary {
        set_name: name.into(),
        record_count: records.len() as u64,
        records_sha256: format!("{:x}", hasher.finalize()),
    }
}

fn sha256(content: &[u8]) -> String {
    format!("{:x}", Sha256::digest(content))
}

fn check_wall_clock(clock: &Instant, max_wall_seconds: u64) -> Result<()> {
    if clock.elapsed() > Duration::from_secs(max_wall_seconds) {
        bail!("adapter evaluation exceeded its {max_wall_seconds}s wall clock");
    }
    Ok(())
}

fn verify_pin(pin: &PinnedFile) -> Result<()> {
    let mut file = std::fs::File::open(&pin.path)
        .with_context(|| format!("pinned file {} is unreadable", pin.path))?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0_u8; 1 << 20];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    let actual = format!("{:x}", hasher.finalize());
    if actual != pin.sha256 {
        bail!(
            "pinned file {} failed SHA-256 verification (expected {})",
            pin.path,
            pin.sha256
        );
    }
    Ok(())
}

/// Fetch the frozen bundle and reduce it to the four evaluation record sets,
/// verifying every manifest and shard hash against the Registry rows.
fn load_eval_sets(
    registry: &Registry,
    adapter: &ExpertAdapterVersion,
    sizes: &EvalSetSizes,
) -> Result<EvalSets> {
    let snapshot = registry
        .get_dataset_snapshot(adapter.snapshot_id)?
        .ok_or_else(|| anyhow!("adapter dataset snapshot not found"))?
        .snapshot;
    if snapshot.expert_view_id != Some(adapter.expert_view_id) {
        bail!("adapter snapshot does not reference the adapter expert view");
    }
    let view = registry
        .get_expert_dataset_view(adapter.expert_view_id)?
        .ok_or_else(|| anyhow!("adapter expert dataset view not found"))?;
    if view.taxonomy_hash != adapter.taxonomy_hash {
        bail!("adapter taxonomy hash differs from its expert dataset view");
    }
    if view.bundle_hash != snapshot.bundle_hash {
        bail!("snapshot and expert view bundle hashes differ");
    }
    let bundle = registry.get_object(&snapshot.bundle_hash)?;
    let mut members: HashMap<String, Vec<u8>> = HashMap::new();
    let mut archive = tar::Archive::new(Cursor::new(bundle));
    for entry in archive.entries()? {
        let mut entry = entry?;
        if !entry.header().entry_type().is_file() {
            continue;
        }
        let name = String::from_utf8(entry.path_bytes().into_owned())
            .map_err(|_| anyhow!("dataset bundle member name is not UTF-8"))?;
        let mut bytes = Vec::with_capacity(entry.size() as usize);
        entry.read_to_end(&mut bytes)?;
        if members.insert(name.clone(), bytes).is_some() {
            bail!("dataset bundle contains duplicate member {name}");
        }
    }
    let base_manifest = members
        .get("dataset-manifest.json")
        .ok_or_else(|| anyhow!("dataset bundle lacks dataset-manifest.json"))?;
    if sha256(base_manifest) != snapshot.manifest_hash {
        bail!("dataset manifest failed SHA-256 verification");
    }
    let expert_manifest = members
        .get("expert-dataset-manifest.json")
        .ok_or_else(|| anyhow!("dataset bundle lacks expert-dataset-manifest.json"))?;
    if sha256(expert_manifest) != view.manifest_hash {
        bail!("expert dataset manifest failed SHA-256 verification");
    }

    let mut shards: Vec<(&ExpertDatasetShard, String, Vec<Value>)> = Vec::new();
    for shard in &view.shards {
        let name = expert_shard_name(
            shard.split,
            shard.purpose,
            shard.expert_id.as_deref(),
            &shard.record_kind,
        );
        let records = load_verified_shard(&members, shard, &name)?;
        shards.push((shard, name, records));
    }

    let fallback = view.taxonomy.fallback_expert_id.as_str();
    let role_purpose = |shard: &ExpertDatasetShard| {
        if adapter.expert_id == "router" {
            shard.purpose == ExpertDatasetPurpose::Router
        } else if adapter.expert_id == fallback {
            shard.purpose == ExpertDatasetPurpose::Shared
        } else {
            shard.purpose == ExpertDatasetPurpose::Expert
                && shard.expert_id.as_deref() == Some(adapter.expert_id.as_str())
        }
    };
    let select = |cap: u64, filter: &dyn Fn(&ExpertDatasetShard) -> bool| -> Vec<EvalRecord> {
        let mut candidates: Vec<(&str, usize, &Value)> = Vec::new();
        for (shard, name, records) in &shards {
            if !filter(shard) {
                continue;
            }
            for (line, envelope) in records.iter().enumerate() {
                candidates.push((name.as_str(), line, envelope));
            }
        }
        candidates.sort_by(|left, right| (left.0, left.1).cmp(&(right.0, right.1)));
        let mut selected = Vec::new();
        for (_, _, envelope) in candidates {
            if selected.len() as u64 >= cap {
                break;
            }
            if let Some((kind, prompt, gold)) = eval_prompt(envelope) {
                selected.push(EvalRecord {
                    record_hash: canonical_json_hash(envelope),
                    kind,
                    prompt,
                    gold,
                });
            }
        }
        selected
    };
    let non_train = |shard: &ExpertDatasetShard| shard.split != DatasetSplit::Train;
    let sets = EvalSets {
        role: select(sizes.role, &|shard| {
            role_purpose(shard) && shard.split != DatasetSplit::Train
        }),
        routing: select(sizes.routing, &|shard| {
            shard.purpose == ExpertDatasetPurpose::Router && non_train(shard)
        }),
        negative_transfer: select(sizes.negative_transfer, &|shard| {
            shard.purpose == ExpertDatasetPurpose::RoutingNegative && non_train(shard)
        }),
        retention: select(sizes.retention, &|shard| {
            shard.purpose == ExpertDatasetPurpose::Shared && non_train(shard)
        }),
    };
    if sets.role.is_empty() {
        bail!("role evaluation set is empty for this adapter");
    }
    if sets.routing.is_empty() {
        bail!("routing evaluation set is empty");
    }
    // An empty retention set is lawful for a first adapter: no previously
    // learned tasks exist to retain; the vacuous-retention path in run_eval
    // records the marker.
    Ok(sets)
}

/// Verify one shard against its manifest descriptor (compressed hash,
/// uncompressed hash, record count — the remote_worker.py rules) and parse
/// its JSONL rows.
fn load_verified_shard(
    members: &HashMap<String, Vec<u8>>,
    shard: &ExpertDatasetShard,
    name: &str,
) -> Result<Vec<Value>> {
    let compressed = members
        .get(name)
        .ok_or_else(|| anyhow!("dataset bundle is missing shard {name}"))?;
    if sha256(compressed) != shard.object_hash {
        bail!("dataset shard {name} failed compressed hash verification");
    }
    let raw =
        zstd::stream::decode_all(Cursor::new(compressed)).context("dataset shard undecodable")?;
    if sha256(&raw) != shard.uncompressed_hash {
        bail!("dataset shard {name} failed uncompressed hash verification");
    }
    if raw.iter().filter(|byte| **byte == b'\n').count() as u64 != shard.record_count {
        bail!("dataset shard {name} record count differs from its manifest");
    }
    let text = String::from_utf8(raw).context("dataset shard is not UTF-8")?;
    text.lines()
        .map(|line| serde_json::from_str(line).context("dataset shard row is invalid JSON"))
        .collect()
}

/// Load the pinned injection probes: one envelope per line, same format and
/// scoring as dataset records.
fn load_probes(pin: &PinnedFile) -> Result<Vec<EvalRecord>> {
    let text = std::fs::read_to_string(&pin.path)
        .with_context(|| format!("injection probe file {} is unreadable", pin.path))?;
    let mut probes = Vec::new();
    for (line, text) in text.lines().enumerate() {
        if text.trim().is_empty() {
            continue;
        }
        let envelope: Value = serde_json::from_str(text)
            .with_context(|| format!("injection probe line {} is invalid JSON", line + 1))?;
        let (kind, prompt, gold) = eval_prompt(&envelope)
            .ok_or_else(|| anyhow!("injection probe line {} has no usable kind", line + 1))?;
        probes.push(EvalRecord {
            record_hash: canonical_json_hash(&envelope),
            kind,
            prompt,
            gold,
        });
    }
    Ok(probes)
}

/// Byte-faithful Rust port of trainer.py `_training_text` (without its
/// train-split filter): returns the prompt up to and including `<|response|>`
/// plus the gold JSON answer. Records whose kind cannot construct a prompt
/// are skipped (`None`), never counted.
fn eval_prompt(envelope: &Value) -> Option<(RecordKind, String, Value)> {
    let kind = envelope.get("kind")?.as_str()?;
    let record = envelope.get("record")?;
    if !record.is_object() {
        return None;
    }
    match kind {
        "meta_decision" => {
            let task = record.get("task_kind");
            let input = record.get("input").cloned().unwrap_or(Value::Null);
            let output = record.get("output").cloned().unwrap_or(Value::Null);
            let prompt = format!(
                "<|meta_task|>{}\n<|input|>{}\n<|response|>",
                python_str(task),
                python_json(&input, false)
            );
            Some((RecordKind::MetaDecision, prompt, output))
        }
        "meta_replay" => {
            let candidate = record
                .get("candidate_score")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            let baseline = record
                .get("baseline_score")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            let target = json!({
                "candidate_preferred": candidate > baseline,
                "fact_correct": record.get("fact_correct").and_then(Value::as_bool).unwrap_or(false),
                "safety_passed": record.get("safety_passed").and_then(Value::as_bool).unwrap_or(false),
            });
            let input = json!({
                "task_id": record.get("task_id").cloned().unwrap_or(Value::Null),
                "source_domain": record.get("source_domain").cloned().unwrap_or(Value::Null),
                "topic_family": record.get("topic_family").cloned().unwrap_or(Value::Null),
            });
            let prompt = format!(
                "<|meta_task|>replay_preference\n<|input|>{}\n<|response|>",
                python_json(&input, true)
            );
            Some((RecordKind::MetaReplay, prompt, target))
        }
        "expert_route" => {
            let target = json!({
                "expert_id": record.get("target_expert_id").cloned().unwrap_or(Value::Null),
                "confidence": record.get("confidence").cloned().unwrap_or(Value::Null),
                "status": record.get("status").cloned().unwrap_or(Value::Null),
            });
            let input = json!({
                "record_kind": record.get("record_kind").cloned().unwrap_or(Value::Null),
                "task_kind": record.get("task_kind").cloned().unwrap_or(Value::Null),
                "source_domain": record.get("source_domain").cloned().unwrap_or(Value::Null),
                "topic_family": record.get("topic_family").cloned().unwrap_or(Value::Null),
                "reason_codes": record.get("reason_codes").cloned().unwrap_or_else(|| json!([])),
            });
            let prompt = format!(
                "<|meta_task|>expert_route\n<|input|>{}\n<|response|>",
                python_json(&input, false)
            );
            Some((RecordKind::ExpertRoute, prompt, target))
        }
        _ => None,
    }
}

/// Python `str()` for the scalar shapes `task_kind` can take in verified
/// data (strings; `None` mirrors Python's `str(None)`).
fn python_str(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(text)) => text.clone(),
        Some(Value::Null) | None => "None".into(),
        Some(other) => python_json(other, false),
    }
}

/// Python `json.dumps(value, sort_keys=True)` with its default `(", ", ": ")`
/// separators; `ensure_ascii` switches non-ASCII escaping per call site
/// (meta_replay uses the Python default `True`, the other kinds `False`).
fn python_json(value: &Value, ensure_ascii: bool) -> String {
    match value {
        Value::Null => "null".into(),
        Value::Bool(flag) => if *flag { "true" } else { "false" }.into(),
        Value::Number(number) => python_number(number),
        Value::String(text) => python_string(text, ensure_ascii),
        Value::Array(items) => format!(
            "[{}]",
            items
                .iter()
                .map(|item| python_json(item, ensure_ascii))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            // Byte-wise string order equals Python's code-point order for
            // valid UTF-8.
            keys.sort();
            format!(
                "{{{}}}",
                keys.iter()
                    .map(|key| format!(
                        "{}: {}",
                        python_string(key, ensure_ascii),
                        python_json(&map[*key], ensure_ascii)
                    ))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        }
    }
}

fn python_number(number: &serde_json::Number) -> String {
    if let Some(int) = number.as_i64() {
        return int.to_string();
    }
    if let Some(int) = number.as_u64() {
        return int.to_string();
    }
    let value = number.as_f64().unwrap_or(0.0);
    if value.is_finite() && value.fract() == 0.0 && value.abs() < 1e16 {
        // Python prints integral floats with a trailing ".0".
        return format!("{value:.1}");
    }
    let raw = format!("{value:?}");
    match raw.split_once(['e', 'E']) {
        None => raw,
        Some((mantissa, exponent)) => {
            let exponent: i32 = exponent.parse().unwrap_or(0);
            format!(
                "{mantissa}e{}{exponent:02}",
                if exponent < 0 { "-" } else { "+" }
            )
        }
    }
}

fn python_string(text: &str, ensure_ascii: bool) -> String {
    let mut out = String::with_capacity(text.len() + 2);
    out.push('"');
    for ch in text.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0C}' => out.push_str("\\f"),
            ch if (ch as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", ch as u32)),
            ch if ensure_ascii && (ch as u32) >= 0x80 => {
                let code = ch as u32;
                if code <= 0xFFFF {
                    out.push_str(&format!("\\u{code:04x}"));
                } else {
                    let high = 0xD800 + ((code - 0x10000) >> 10);
                    let low = 0xDC00 + ((code - 0x10000) & 0x3FF);
                    out.push_str(&format!("\\u{high:04x}\\u{low:04x}"));
                }
            }
            ch => out.push(ch),
        }
    }
    out.push('"');
    out
}

/// Score one completion against the gold answer: `(success, violation)`.
/// Unparseable, non-object, or key-missing completions are violations;
/// well-formed but wrong answers are plain failures.
fn score_completion(kind: RecordKind, gold: &Value, completion: &str) -> ArmScore {
    let parsed: Value = match serde_json::from_str(completion.trim()) {
        Ok(value) => value,
        Err(_) => {
            return ArmScore {
                success: false,
                violation: true,
            };
        }
    };
    if !parsed.is_object() {
        return ArmScore {
            success: false,
            violation: true,
        };
    }
    if let Some(gold_object) = gold.as_object()
        && gold_object.keys().any(|key| parsed.get(key).is_none())
    {
        return ArmScore {
            success: false,
            violation: true,
        };
    }
    match kind {
        RecordKind::MetaDecision | RecordKind::MetaReplay => ArmScore {
            success: parsed == *gold,
            violation: false,
        },
        RecordKind::ExpertRoute => {
            let identity = parsed.get("expert_id") == gold.get("expert_id")
                && parsed.get("status") == gold.get("status");
            let confidence = match gold.get("confidence") {
                Some(gold_confidence) if gold_confidence.is_number() => {
                    let gold_value = gold_confidence.as_f64().unwrap_or(0.0);
                    match parsed.get("confidence").and_then(Value::as_f64) {
                        Some(value) if (value - gold_value).abs() <= 0.10 => true,
                        // Numeric gold with non-numeric/unbounded confidence is
                        // a schema deviation: violation, not a plain miss.
                        Some(_) => {
                            return ArmScore {
                                success: false,
                                violation: false,
                            };
                        }
                        None => {
                            return ArmScore {
                                success: false,
                                violation: true,
                            };
                        }
                    }
                }
                // Dataset router gold carries `confidence: null`; the answer
                // must reproduce it exactly.
                other => parsed.get("confidence") == other,
            };
            ArmScore {
                success: identity && confidence,
                violation: false,
            }
        }
    }
}

/// A negative-transfer "hit": the completion parses and names an expert other
/// than the gold (always the shared fallback) target.
fn negative_hit(gold: &Value, completion: &str) -> bool {
    serde_json::from_str::<Value>(completion.trim())
        .ok()
        .and_then(|value| value.get("expert_id").cloned())
        .is_some_and(|expert| Some(&expert) != gold.get("expert_id"))
}

struct ArmOutcome {
    completion: String,
    success: bool,
    violation: bool,
}

async fn score_arm(
    client: &reqwest::Client,
    port: u16,
    record: &EvalRecord,
    generation: &EvalGeneration,
) -> Result<ArmOutcome> {
    let body = json!({
        "prompt": record.prompt,
        "temperature": generation.temperature,
        "seed": generation.seed,
        "n_predict": generation.n_predict,
        "stop": generation.stop,
        "cache_prompt": false,
        "stream": false,
    });
    let response = client
        .post(format!("http://127.0.0.1:{port}/completion"))
        .json(&body)
        .send()
        .await
        .context("llama-server completion request failed")?;
    if !response.status().is_success() {
        bail!(
            "llama-server completion returned HTTP {}",
            response.status()
        );
    }
    let value: Value = response
        .json()
        .await
        .context("llama-server completion response is invalid")?;
    let completion = value
        .get("content")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow!("llama-server completion response lacks content"))?
        .to_owned();
    let stopped_limit = value
        .get("stopped_limit")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if stopped_limit {
        return Ok(ArmOutcome {
            completion,
            success: false,
            violation: true,
        });
    }
    let score = score_completion(record.kind, &record.gold, &completion);
    Ok(ArmOutcome {
        completion,
        success: score.success,
        violation: score.violation,
    })
}

struct RunningServers {
    _base: Option<tokio::process::Child>,
    _adapted: Option<tokio::process::Child>,
    llama_cpp_version: String,
}

/// Spawn (or, under `spawn=false` in tests, adopt) one llama-server per arm
/// and wait for both `/health` endpoints. Child processes are killed on drop.
async fn bring_up_servers(plan: &ExpertAdapterEvalPlan, spawn: bool) -> Result<RunningServers> {
    let llama_cpp_version = if spawn {
        capture_llama_version(&plan.llama_server.path).await?
    } else {
        EXTERNAL_SERVER_VERSION.into()
    };
    let base = if spawn {
        Some(spawn_llama(plan, plan.ports.base, &plan.base_gguf.path).await?)
    } else {
        None
    };
    let adapted = if spawn {
        Some(spawn_llama(plan, plan.ports.adapted, &plan.adapted_gguf.path).await?)
    } else {
        None
    };
    wait_for_health(plan.ports.base).await?;
    wait_for_health(plan.ports.adapted).await?;
    Ok(RunningServers {
        _base: base,
        _adapted: adapted,
        llama_cpp_version,
    })
}

async fn capture_llama_version(binary: &str) -> Result<String> {
    let output = tokio::process::Command::new(binary)
        .arg("--version")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .await
        .context("llama-server --version failed to run")?;
    let first_line = |bytes: &[u8]| {
        String::from_utf8_lossy(bytes)
            .lines()
            .find(|line| !line.trim().is_empty())
            .map(str::to_owned)
    };
    first_line(&output.stdout)
        .or_else(|| first_line(&output.stderr))
        .ok_or_else(|| anyhow!("llama-server --version produced no version line"))
}

async fn spawn_llama(
    plan: &ExpertAdapterEvalPlan,
    port: u16,
    model: &str,
) -> Result<tokio::process::Child> {
    tokio::process::Command::new(&plan.llama_server.path)
        .args([
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
            "--model",
            model,
            "--ctx-size",
            "4096",
            "--n-gpu-layers",
            "999",
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .with_context(|| format!("llama-server failed to start on port {port}"))
}

async fn wait_for_health(port: u16) -> Result<()> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .redirect(reqwest::redirect::Policy::none())
        .no_proxy()
        .build()?;
    let url = format!("http://127.0.0.1:{port}/health");
    let deadline = Instant::now() + HEALTH_DEADLINE;
    while Instant::now() < deadline {
        if let Ok(response) = client.get(&url).send().await
            && response.status().is_success()
        {
            return Ok(());
        }
        tokio::time::sleep(HEALTH_POLL_INTERVAL).await;
    }
    bail!("llama-server on port {port} did not become healthy");
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::experts::builtin_expert_taxonomy;
    use axum::{
        Json, Router,
        extract::State,
        response::IntoResponse,
        routing::{get, post},
    };
    use cerebellum_core::{
        BaseModelPin, DatasetEligibilityReport, DatasetSnapshot, DatasetSnapshotRecord,
        DatasetSplitStats, ExpertDatasetShard,
    };
    use rusqlite::params;
    use std::sync::Arc;
    use std::sync::Mutex;
    use tempfile::tempdir;

    // ---- prompt parity -------------------------------------------------
    // Golden strings below were generated by executing
    // `cerebellum_meta_training.trainer._training_text` on the same fixture
    // envelopes (split forced to "train" for the Python entry point). Regenerate
    // with: PYTHONPATH=workers/meta-training/src python -c "..." (see plan).

    #[test]
    fn checked_in_probe_file_is_loadable() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("benchmarks")
            .join("adapter-eval")
            .join("injection-probes.jsonl");
        let content = std::fs::read(&path).unwrap();
        let pin = PinnedFile {
            path: path.to_string_lossy().replace('\\', "/"),
            sha256: sha256(&content),
        };
        let probes = load_probes(&pin).unwrap();
        assert_eq!(probes.len(), 20);
        let kinds = |kind: RecordKind| probes.iter().filter(|probe| probe.kind == kind).count();
        assert_eq!(kinds(RecordKind::MetaDecision), 7);
        assert_eq!(kinds(RecordKind::MetaReplay), 6);
        assert_eq!(kinds(RecordKind::ExpertRoute), 7);
    }

    #[test]
    fn eval_prompt_matches_python_training_text_byte_for_byte() {
        let decision = json!({"kind":"meta_decision","split":"holdout","record":{"task_kind":"relevance","input":{"query":"代理 评测","context":{"repo":"cerebellum","topics":["routing","lora"]},"top_k":3},"output":{"decision":"useful","score":0.85,"tags":["agent","评测"]},"source_domain":"github:ayisuplus/cerebellum","topic_family":"routing","useful":true,"confidence":0.9}});
        let (kind, prompt, gold) = eval_prompt(&decision).unwrap();
        assert_eq!(kind, RecordKind::MetaDecision);
        assert_eq!(
            prompt,
            "<|meta_task|>relevance\n<|input|>{\"context\": {\"repo\": \"cerebellum\", \"topics\": [\"routing\", \"lora\"]}, \"query\": \"代理 评测\", \"top_k\": 3}\n<|response|>"
        );
        assert_eq!(
            python_json(&gold, false),
            "{\"decision\": \"useful\", \"score\": 0.85, \"tags\": [\"agent\", \"评测\"]}"
        );

        let replay = json!({"kind":"meta_replay","split":"holdout","record":{"task_id":"task-评测-1","source_domain":"wiki:中文","topic_family":"retrieval","candidate_score":0.9,"baseline_score":0.4,"fact_correct":true,"safety_passed":true}});
        let (kind, prompt, gold) = eval_prompt(&replay).unwrap();
        assert_eq!(kind, RecordKind::MetaReplay);
        assert_eq!(
            prompt,
            "<|meta_task|>replay_preference\n<|input|>{\"source_domain\": \"wiki:\\u4e2d\\u6587\", \"task_id\": \"task-\\u8bc4\\u6d4b-1\", \"topic_family\": \"retrieval\"}\n<|response|>"
        );
        assert_eq!(
            python_json(&gold, true),
            "{\"candidate_preferred\": true, \"fact_correct\": true, \"safety_passed\": true}"
        );

        let route = json!({"kind":"expert_route","split":"holdout","record":{"record_hash":"abc","record_kind":"meta_decision","task_kind":"relevance","source_domain":"github:x","topic_family":"评测/routing","target_expert_id":"retrieval","secondary_expert_ids":[],"status":"assigned","reason_codes":["task_kind_mapping"]}});
        let (kind, prompt, gold) = eval_prompt(&route).unwrap();
        assert_eq!(kind, RecordKind::ExpertRoute);
        assert_eq!(
            prompt,
            "<|meta_task|>expert_route\n<|input|>{\"reason_codes\": [\"task_kind_mapping\"], \"record_kind\": \"meta_decision\", \"source_domain\": \"github:x\", \"task_kind\": \"relevance\", \"topic_family\": \"评测/routing\"}\n<|response|>"
        );
        assert_eq!(
            python_json(&gold, false),
            "{\"confidence\": null, \"expert_id\": \"retrieval\", \"status\": \"assigned\"}"
        );
    }

    #[test]
    fn python_json_escapes_and_formats_like_python() {
        // ensure_ascii=true escapes non-ASCII with lowercase hex and keeps DEL.
        assert_eq!(python_string("中\u{7f}", true), "\"\\u4e2d\u{7f}\"");
        assert_eq!(python_string("中", false), "\"中\"");
        assert_eq!(
            python_string("a\"b\\c\nd\u{01}", false),
            "\"a\\\"b\\\\c\\nd\\u0001\""
        );
        // Non-BMP characters become lowercase surrogate pairs.
        assert_eq!(python_string("😀", true), "\"\\ud83d\\ude00\"");
        assert_eq!(python_number(&serde_json::Number::from(3)), "3");
        assert_eq!(python_number(&serde_json::Number::from(-2)), "-2");
        assert_eq!(python_number(json!(1.0).as_number().unwrap()), "1.0");
        assert_eq!(python_number(json!(0.85).as_number().unwrap()), "0.85");
        // Empty containers use Python separators too.
        assert_eq!(python_json(&json!({}), false), "{}");
        assert_eq!(python_json(&json!([]), false), "[]");
    }

    #[test]
    fn eval_prompt_skips_unknown_kinds() {
        assert!(eval_prompt(&json!({"kind":"synthetic_candidate","record":{}})).is_none());
        assert!(eval_prompt(&json!({"kind":"meta_decision","record":[]})).is_none());
        assert!(eval_prompt(&json!({"record":{}})).is_none());
    }

    // ---- scoring ---------------------------------------------------------

    #[test]
    fn scoring_rules_per_kind() {
        let decision_gold = json!({"decision":"useful","score":0.85});
        let score = score_completion(
            RecordKind::MetaDecision,
            &decision_gold,
            "{\"decision\": \"useful\", \"score\": 0.85}",
        );
        assert!((score.success, score.violation) == (true, false));
        let score = score_completion(
            RecordKind::MetaDecision,
            &decision_gold,
            "{\"decision\":\"useful\",\"score\":0.85,\"extra\":1}",
        );
        assert!((score.success, score.violation) == (false, false));
        let score = score_completion(RecordKind::MetaDecision, &decision_gold, "not json");
        assert!((score.success, score.violation) == (false, true));
        let score = score_completion(RecordKind::MetaDecision, &decision_gold, "[1,2]");
        assert!((score.success, score.violation) == (false, true));
        let score = score_completion(
            RecordKind::MetaDecision,
            &decision_gold,
            "{\"decision\":\"useful\"}",
        );
        assert!((score.success, score.violation) == (false, true));

        let route_gold = json!({"expert_id":"shared","confidence":null,"status":"ambiguous"});
        let score = score_completion(
            RecordKind::ExpertRoute,
            &route_gold,
            "{\"expert_id\":\"shared\",\"status\":\"ambiguous\",\"confidence\":null}",
        );
        assert!((score.success, score.violation) == (true, false));
        // Numeric confidence where gold is null deviates from the schema answer.
        let score = score_completion(
            RecordKind::ExpertRoute,
            &route_gold,
            "{\"expert_id\":\"shared\",\"status\":\"ambiguous\",\"confidence\":0.9}",
        );
        assert!((score.success, score.violation) == (false, false));

        let numeric_gold = json!({"expert_id":"retrieval","confidence":0.5,"status":"assigned"});
        let score = score_completion(
            RecordKind::ExpertRoute,
            &numeric_gold,
            "{\"expert_id\":\"retrieval\",\"status\":\"assigned\",\"confidence\":0.55}",
        );
        assert!((score.success, score.violation) == (true, false));
        let score = score_completion(
            RecordKind::ExpertRoute,
            &numeric_gold,
            "{\"expert_id\":\"retrieval\",\"status\":\"assigned\",\"confidence\":0.7}",
        );
        assert!((score.success, score.violation) == (false, false));
        let score = score_completion(
            RecordKind::ExpertRoute,
            &numeric_gold,
            "{\"expert_id\":\"retrieval\",\"status\":\"assigned\",\"confidence\":\"high\"}",
        );
        assert!((score.success, score.violation) == (false, true));

        assert!(negative_hit(&route_gold, "{\"expert_id\":\"retrieval\"}"));
        assert!(!negative_hit(&route_gold, "{\"expert_id\":\"shared\"}"));
        assert!(!negative_hit(&route_gold, "garbage"));
    }

    // ---- fake llama-server end-to-end ------------------------------------

    #[derive(Clone, Default)]
    struct FakeLlama {
        /// prompt -> (content, stopped_limit)
        script: Arc<Mutex<HashMap<String, (String, bool)>>>,
    }

    async fn fake_health() -> impl IntoResponse {
        axum::http::StatusCode::OK
    }

    async fn fake_completion(
        State(state): State<FakeLlama>,
        Json(body): Json<Value>,
    ) -> Json<Value> {
        let prompt = body["prompt"].as_str().unwrap_or("");
        assert_eq!(body["temperature"], json!(0.0));
        assert_eq!(body["stream"], json!(false));
        let (content, stopped_limit) = state
            .script
            .lock()
            .unwrap()
            .get(prompt)
            .cloned()
            .unwrap_or_else(|| ("{}".into(), false));
        Json(json!({"content": content, "stopped_limit": stopped_limit}))
    }

    async fn start_fake_llama(script: HashMap<String, (String, bool)>) -> u16 {
        let app = Router::new()
            .route("/health", get(fake_health))
            .route("/completion", post(fake_completion))
            .with_state(FakeLlama {
                script: Arc::new(Mutex::new(script)),
            });
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        port
    }

    fn decision_envelope(split: &str, index: u64, output_score: f64) -> Value {
        json!({"kind":"meta_decision","split":split,"record":{
            "task_kind":"relevance",
            "input":{"query":format!("q{index}"),"top_k":1},
            "output":{"decision":"useful","score":output_score},
            "source_domain":"github:x","topic_family":"routing","useful":true,"confidence":0.9,
        }})
    }

    fn replay_envelope(split: &str, index: u64, preferred: bool) -> Value {
        json!({"kind":"meta_replay","split":split,"record":{
            "task_id":format!("task-{index}"),"source_domain":"wiki:x","topic_family":"retrieval",
            "candidate_score":if preferred {0.9} else {0.1},"baseline_score":0.5,
            "fact_correct":true,"safety_passed":true,
        }})
    }

    fn route_envelope(split: &str, index: u64, target: &str, status: &str) -> Value {
        json!({"kind":"expert_route","split":split,"record":{
            "record_hash":format!("h{index}"),"record_kind":"meta_decision","task_kind":"relevance",
            "source_domain":"github:x","topic_family":format!("routing-{index}"),
            "target_expert_id":target,
            "secondary_expert_ids":[],"status":status,"reason_codes":["task_kind_mapping"],
        }})
    }

    struct FixtureShard {
        split: DatasetSplit,
        purpose: ExpertDatasetPurpose,
        expert_id: Option<String>,
        record_kind: String,
        records: Vec<Value>,
    }

    /// Build a registry with a real bundle in CAS, snapshot/view rows, and one
    /// candidate adapter; returns (registry, tempdir guard, adapter).
    fn fixture_registry(
        expert_id: &str,
        version: &str,
        set_caps: &EvalSetSizes,
    ) -> (Registry, tempfile::TempDir, ExpertAdapterVersion) {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let taxonomy = builtin_expert_taxonomy();
        let taxonomy_hash = crate::experts::builtin_expert_taxonomy_hash();
        let fallback = taxonomy.fallback_expert_id.clone();

        let shard_specs = vec![
            FixtureShard {
                split: DatasetSplit::Holdout,
                purpose: ExpertDatasetPurpose::Router,
                expert_id: None,
                record_kind: "expert_route".into(),
                records: (0..set_caps.routing)
                    .map(|index| route_envelope("holdout", index, "retrieval", "assigned"))
                    .collect(),
            },
            FixtureShard {
                split: DatasetSplit::Holdout,
                purpose: ExpertDatasetPurpose::RoutingNegative,
                expert_id: None,
                record_kind: "expert_route".into(),
                records: (0..set_caps.negative_transfer.max(1))
                    .map(|index| route_envelope("holdout", 100 + index, &fallback, "ambiguous"))
                    .collect(),
            },
            FixtureShard {
                split: DatasetSplit::Holdout,
                purpose: ExpertDatasetPurpose::Expert,
                expert_id: Some(expert_id.into()),
                record_kind: "meta_decision".into(),
                records: (0..set_caps.role)
                    .map(|index| decision_envelope("holdout", index, 0.5))
                    .collect(),
            },
            FixtureShard {
                split: DatasetSplit::Holdout,
                purpose: ExpertDatasetPurpose::Shared,
                expert_id: None,
                record_kind: "meta_replay".into(),
                records: (0..set_caps.retention)
                    .map(|index| replay_envelope("holdout", index, true))
                    .collect(),
            },
        ];

        let mut entries: Vec<(String, Vec<u8>)> = Vec::new();
        let mut shards = Vec::new();
        for spec in &shard_specs {
            let mut jsonl = Vec::new();
            for record in &spec.records {
                serde_json::to_writer(&mut jsonl, record).unwrap();
                jsonl.push(b'\n');
            }
            let uncompressed_hash = sha256(&jsonl);
            let compressed = zstd::stream::encode_all(Cursor::new(&jsonl), 9).unwrap();
            let object_hash = sha256(&compressed);
            let name = expert_shard_name(
                spec.split,
                spec.purpose,
                spec.expert_id.as_deref(),
                &spec.record_kind,
            );
            entries.push((name, compressed));
            shards.push(ExpertDatasetShard {
                split: spec.split,
                purpose: spec.purpose,
                expert_id: spec.expert_id.clone(),
                record_kind: spec.record_kind.clone(),
                object_hash,
                uncompressed_hash,
                record_count: spec.records.len() as u64,
                compressed_bytes: 1,
            });
        }
        let view_id = Uuid::new_v4();
        let snapshot_id = Uuid::new_v4();
        let expert_manifest = json!({
            "schema_version":cerebellum_core::SCHEMA_VERSION,
            "kind":"expert_dataset_manifest_v1",
            "taxonomy":taxonomy,
            "taxonomy_hash":taxonomy_hash,
            "shards":shards,
            "contains_raw_documents":false
        });
        let expert_manifest_bytes = serde_json::to_vec(&expert_manifest).unwrap();
        let expert_manifest_hash = sha256(&expert_manifest_bytes);
        entries.push(("expert-dataset-manifest.json".into(), expert_manifest_bytes));
        let base_manifest = json!({
            "schema_version":cerebellum_core::SCHEMA_VERSION,
            "kind":"dataset_bundle_manifest_v1",
            "contains_raw_documents":false
        });
        let base_manifest_bytes = serde_json::to_vec(&base_manifest).unwrap();
        let base_manifest_hash = sha256(&base_manifest_bytes);
        entries.push(("dataset-manifest.json".into(), base_manifest_bytes));
        let mut archive = tar::Builder::new(Vec::new());
        for (name, content) in &entries {
            let mut header = tar::Header::new_gnu();
            header.set_size(content.len() as u64);
            header.set_mode(0o644);
            header.set_cksum();
            archive
                .append_data(&mut header, name, Cursor::new(content))
                .unwrap();
        }
        let bundle = archive.into_inner().unwrap();
        let bundle_hash = registry.put_object(&bundle).unwrap();

        let build_id = Uuid::new_v4();
        let build = cerebellum_core::DatasetBuild {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            build_id,
            kind: "meta-controller".into(),
            source_watermark: None,
            parent_build_id: None,
            shards: vec![],
            bundle_hash: bundle_hash.clone(),
            manifest_hash: base_manifest_hash.clone(),
            dedup_key: format!("fixture-{}", Uuid::new_v4()),
            decision_count: 0,
            replay_eval_count: 0,
            rejected_record_count: 0,
            split_stats: DatasetSplitStats::default(),
            eligibility: DatasetEligibilityReport::default(),
            expert_view_id: Some(view_id),
            expert_manifest_hash: Some(expert_manifest_hash.clone()),
            expert_taxonomy_hash: Some(taxonomy_hash.clone()),
            policy_version: "test".into(),
            created_at: Utc::now(),
        };
        registry
            .lock_conn()
            .execute(
                "INSERT INTO dataset_builds(id,kind,source_watermark,parent_build_id,bundle_hash,manifest_hash,dedup_key,build_json,created_at)
                 VALUES(?1,?2,NULL,NULL,?3,?4,?5,?6,?7)",
                params![
                    build_id.to_string(),
                    "meta-controller",
                    bundle_hash,
                    base_manifest_hash,
                    build.dedup_key,
                    serde_json::to_string(&build).unwrap(),
                    Utc::now().to_rfc3339()
                ],
            )
            .unwrap();
        let snapshot = DatasetSnapshot {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            snapshot_id,
            kind: "meta-controller".into(),
            build_id,
            bundle_hash: bundle_hash.clone(),
            manifest_hash: base_manifest_hash,
            decision_count: 0,
            replay_eval_count: 0,
            split_stats: DatasetSplitStats::default(),
            eligibility: DatasetEligibilityReport::default(),
            expert_view_id: Some(view_id),
            expert_manifest_hash: Some(expert_manifest_hash.clone()),
            expert_taxonomy_hash: Some(taxonomy_hash.clone()),
            quality_report_id: None,
            quality_report_hash: None,
            created_by: "test".into(),
            reason: "fixture".into(),
            legacy_candidate_id: None,
            created_at: Utc::now(),
        };
        let record = DatasetSnapshotRecord {
            snapshot,
            revocation: None,
        };
        let manifest_hash = record.snapshot.manifest_hash.clone();
        let snapshot_json = serde_json::to_string(&record.snapshot).unwrap();
        registry
            .lock_conn()
            .execute(
                "INSERT INTO dataset_snapshots(id,kind,build_id,bundle_hash,manifest_hash,snapshot_json,created_at)
                 VALUES(?1,?2,?3,?4,?5,?6,?7)",
                params![
                    snapshot_id.to_string(),
                    "meta-controller",
                    build_id.to_string(),
                    bundle_hash,
                    manifest_hash,
                    snapshot_json,
                    Utc::now().to_rfc3339()
                ],
            )
            .unwrap();
        let view = cerebellum_core::ExpertDatasetView {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            view_id,
            build_id: record.snapshot.build_id,
            taxonomy: builtin_expert_taxonomy(),
            taxonomy_hash: taxonomy_hash.clone(),
            assignments_hash: "0".repeat(64),
            manifest_hash: expert_manifest_hash,
            bundle_hash: bundle_hash.clone(),
            shards,
            assignment_count: 0,
            ambiguous_count: 0,
            out_of_distribution_count: 0,
            negative_transfer_count: 0,
            readiness: cerebellum_core::ExpertDatasetReadiness {
                ready: true,
                minimum_router_records: 0,
                minimum_train_records_per_expert: 0,
                minimum_replays_per_expert: 0,
                router_train_records: 0,
                per_expert: Default::default(),
                reasons: vec![],
            },
            policy_version: "test".into(),
            created_at: Utc::now(),
        };
        registry
            .lock_conn()
            .execute(
                "INSERT INTO expert_dataset_views(id,build_id,taxonomy_hash,manifest_hash,bundle_hash,view_json,created_at)
                 VALUES(?1,?2,?3,?4,?5,?6,?7)",
                params![
                    view_id.to_string(),
                    view.build_id.to_string(),
                    taxonomy_hash,
                    view.manifest_hash,
                    bundle_hash,
                    serde_json::to_string(&view).unwrap(),
                    Utc::now().to_rfc3339()
                ],
            )
            .unwrap();

        let now = Utc::now();
        let run_id = Uuid::new_v4();
        let run = cerebellum_core::TrainingRun {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            run_id,
            snapshot_id,
            snapshot_bundle_hash: bundle_hash.clone(),
            snapshot_manifest_hash: manifest_hash.clone(),
            training_bundle_hash: None,
            training_manifest_hash: None,
            expert_plan: None,
            base_model: BaseModelPin {
                model_id: "Qwen/Qwen2.5-1.5B".into(),
                revision: "r1".into(),
                sha256: "d".repeat(64),
            },
            qlora: cerebellum_core::QloraConfig::default(),
            provider: "autodl".into(),
            application_uuid: "app".into(),
            application_version: "v1".into(),
            requested_gpu_spec: "none".into(),
            selected_gpu_spec: None,
            administrator: "admin".into(),
            reason: "fixture".into(),
            budget: cerebellum_core::TrainingBudget {
                max_hourly_cny: 10.0,
                max_total_cny: 100.0,
                max_wall_seconds: 21_600,
            },
            status: cerebellum_core::TrainingRunStatus::Completed,
            provider_instance_id: None,
            hourly_price_cny: None,
            estimated_cost_cny: 0.0,
            artifact_hash: None,
            model_id: None,
            model_version: None,
            error: None,
            created_at: now,
            started_at: None,
            completed_at: None,
            updated_at: now,
        };
        registry
            .lock_conn()
            .execute(
                "INSERT INTO training_runs(id,snapshot_id,status,run_json,created_at,started_at,updated_at)
                 VALUES(?1,?2,'completed',?3,?4,NULL,?4)",
                params![
                    run_id.to_string(),
                    snapshot_id.to_string(),
                    serde_json::to_string(&run).unwrap(),
                    now.to_rfc3339()
                ],
            )
            .unwrap();

        let adapter = ExpertAdapterVersion {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            adapter_id: Uuid::new_v4(),
            expert_id: expert_id.into(),
            version: version.into(),
            bundle_hash: "b".repeat(64),
            artifact_path: "adapters/retrieval.zip".into(),
            artifact_hash: "c".repeat(64),
            byte_length: 16,
            training_records: 10,
            base_model: BaseModelPin {
                model_id: "Qwen/Qwen2.5-1.5B".into(),
                revision: "r1".into(),
                sha256: "d".repeat(64),
            },
            training_run_id: run_id,
            snapshot_id,
            expert_view_id: view_id,
            taxonomy_hash,
            status: ExpertAdapterStatus::Candidate,
            metrics: None,
            previous_active: None,
            created_at: now,
            updated_at: now,
        };
        registry
            .lock_conn()
            .execute(
                "INSERT INTO expert_adapter_versions(adapter_id,expert_id,version,status,training_run_id,bundle_hash,artifact_hash,adapter_json,updated_at)
                 VALUES(?1,?2,?3,'candidate',?4,?5,?6,?7,?8)",
                params![
                    adapter.adapter_id.to_string(),
                    adapter.expert_id,
                    adapter.version,
                    adapter.training_run_id.to_string(),
                    adapter.bundle_hash,
                    adapter.artifact_hash,
                    serde_json::to_string(&adapter).unwrap(),
                    now.to_rfc3339()
                ],
            )
            .unwrap();
        (registry, dir, adapter)
    }

    /// Pin a real temp file (content hashed into the plan pin).
    fn pinned_temp(dir: &std::path::Path, name: &str, content: &[u8]) -> PinnedFile {
        let path = dir.join(name);
        std::fs::write(&path, content).unwrap();
        PinnedFile {
            path: path.to_string_lossy().replace('\\', "/"),
            sha256: sha256(content),
        }
    }

    fn probe_envelopes(dir: &std::path::Path) -> PinnedFile {
        let mut content = Vec::new();
        for envelope in [
            decision_envelope("holdout", 900, 0.5),
            replay_envelope("holdout", 901, true),
            route_envelope("holdout", 902, "retrieval", "assigned"),
        ] {
            serde_json::to_writer(&mut content, &envelope).unwrap();
            content.push(b'\n');
        }
        pinned_temp(dir, "probes.jsonl", &content)
    }

    /// A well-formed, schema-complete answer that is simply wrong for the
    /// record's kind (plain failure, not a violation).
    fn wrong_answer(record: &EvalRecord) -> String {
        match record.kind {
            RecordKind::MetaDecision => "{\"decision\":\"noise\",\"score\":0.1}".into(),
            RecordKind::MetaReplay => {
                "{\"candidate_preferred\":false,\"fact_correct\":false,\"safety_passed\":false}"
                    .into()
            }
            RecordKind::ExpertRoute => {
                "{\"expert_id\":\"evidence\",\"status\":\"assigned\",\"confidence\":null}".into()
            }
        }
    }

    /// Program a fake arm: records where the arm succeeds answer with the gold
    /// JSON; all others answer with well-formed but wrong JSON.
    fn arm_script(
        sets: &EvalSets,
        probes: &[EvalRecord],
        succeed: &dyn Fn(&str, usize) -> bool,
        arm_violate_probes: bool,
    ) -> HashMap<String, (String, bool)> {
        let mut script = HashMap::new();
        let mut program = |set: &str, records: &[EvalRecord]| {
            for (index, record) in records.iter().enumerate() {
                let content = if succeed(set, index) {
                    python_json(&record.gold, false)
                } else {
                    wrong_answer(record)
                };
                script.insert(record.prompt.clone(), (content, false));
            }
        };
        program("role", &sets.role);
        program("routing", &sets.routing);
        program("negative_transfer", &sets.negative_transfer);
        program("retention", &sets.retention);
        for probe in probes {
            let content = if arm_violate_probes {
                "not json at all".into()
            } else {
                python_json(&probe.gold, false)
            };
            script.insert(probe.prompt.clone(), (content, false));
        }
        script
    }

    #[tokio::test]
    async fn dual_arm_eval_produces_exact_metrics_and_persists_report() {
        let caps = EvalSetSizes {
            role: 4,
            routing: 3,
            negative_transfer: 2,
            retention: 4,
            metacognition: 150,
        };
        let (registry, _dir, adapter) = fixture_registry("retrieval", "1.0.0", &caps);
        let file_dir = tempdir().unwrap();
        let sets = load_eval_sets(&registry, &adapter, &caps).unwrap();
        assert_eq!(sets.role.len(), 4);
        assert_eq!(sets.routing.len(), 3);
        assert_eq!(sets.negative_transfer.len(), 2);
        assert_eq!(sets.retention.len(), 4);
        let probe_pin = probe_envelopes(file_dir.path());
        let probes = load_probes(&probe_pin).unwrap();
        assert_eq!(probes.len(), 3);

        // Base arm: succeeds on even role records, all routing, all negative
        // (answers the fallback gold — no hits), retention except record 0.
        // Adapted arm: all role, routing except record 0, all retention.
        let base_script = arm_script(
            &sets,
            &probes,
            &|set, index| match set {
                "role" => index % 2 == 0,
                "routing" => true,
                "negative_transfer" => true,
                "retention" => index != 0,
                _ => false,
            },
            false,
        );
        let adapted_script = arm_script(
            &sets,
            &probes,
            &|set, index| match set {
                "role" => true,
                "routing" => index != 0,
                "negative_transfer" => index == 0,
                "retention" => true,
                _ => false,
            },
            false,
        );
        // Adapted negative-transfer record 1 routes away from the fallback.
        let mut adapted_script = adapted_script;
        let negative_record = &sets.negative_transfer[1];
        adapted_script.insert(
            negative_record.prompt.clone(),
            (
                "{\"expert_id\":\"retrieval\",\"status\":\"ambiguous\",\"confidence\":null}".into(),
                false,
            ),
        );

        let base_port = start_fake_llama(base_script).await;
        let adapted_port = start_fake_llama(adapted_script).await;
        let plan = ExpertAdapterEvalPlan {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            kind: "expert_adapter_eval_plan_v1".into(),
            expert_id: adapter.expert_id.clone(),
            version: adapter.version.clone(),
            llama_server: pinned_temp(file_dir.path(), "llama-server", b"fake-binary"),
            base_gguf: pinned_temp(file_dir.path(), "base.gguf", b"base-gguf"),
            adapted_gguf: pinned_temp(file_dir.path(), "adapted.gguf", b"adapted-gguf"),
            ports: cerebellum_core::EvalPorts {
                base: base_port,
                adapted: adapted_port,
            },
            set_sizes: caps,
            generation: EvalGeneration::default(),
            injection_probes: probe_pin,
            metacognition_probes: None,
            max_wall_seconds: 600,
        };

        let (report, results) = run_eval(&registry, &plan, false).await.unwrap();
        let metrics = &report.metrics;
        assert_eq!(metrics.evaluation_count, 13);
        assert_eq!(metrics.task_success_delta, 0.5); // adapted 4/4, base 2/4
        assert_eq!(metrics.routing_accuracy_delta, -1.0 / 3.0);
        assert_eq!(metrics.negative_transfer_rate_delta, 0.5);
        assert_eq!(metrics.old_task_retention, 1.0); // capped at parity
        assert_eq!(metrics.policy_violations, 0);
        assert!(!metrics.injection_regression);
        assert_eq!(metrics.canary_decisions, 0);
        assert_eq!(report.llama_cpp_version, EXTERNAL_SERVER_VERSION);
        assert_eq!(report.adapter_id, adapter.adapter_id);
        assert_eq!(report.base_gguf_sha256, plan.base_gguf.sha256);
        assert_eq!(
            report.results_object_hash,
            sha256(&results),
            "results object hash pins the per-record JSONL"
        );
        assert_eq!(report.set_summaries.len(), 4);
        assert_eq!(
            report
                .set_summaries
                .iter()
                .map(|summary| (summary.set_name.as_str(), summary.record_count))
                .collect::<Vec<_>>(),
            vec![
                ("role", 4),
                ("routing", 3),
                ("negative_transfer", 2),
                ("retention", 4)
            ]
        );

        // Persist: report row, audit entry, CAS object.
        registry
            .record_expert_adapter_eval_report(&report, &results)
            .unwrap();
        let stored = registry
            .get_expert_adapter_eval_report(report.report_id)
            .unwrap()
            .unwrap();
        assert_eq!(stored, report);
        let listed = registry
            .list_expert_adapter_eval_reports("retrieval", "1.0.0")
            .unwrap();
        assert_eq!(listed.len(), 1);
        let object = registry.get_object(&report.results_object_hash).unwrap();
        assert_eq!(object, results);
        // Re-recording the same report id fails closed.
        assert!(
            registry
                .record_expert_adapter_eval_report(&report, &results)
                .is_err()
        );
        // Tampered results object is rejected.
        assert!(
            registry
                .record_expert_adapter_eval_report(&report, b"tampered")
                .is_err()
        );
    }

    #[tokio::test]
    async fn eval_refuses_mismatched_identity_and_empty_sets() {
        let caps = EvalSetSizes {
            role: 2,
            routing: 2,
            negative_transfer: 1,
            retention: 2,
            metacognition: 150,
        };
        let (registry, _dir, adapter) = fixture_registry("retrieval", "1.0.0", &caps);
        let file_dir = tempdir().unwrap();
        let mut plan = ExpertAdapterEvalPlan {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            kind: "expert_adapter_eval_plan_v1".into(),
            expert_id: "retrieval".into(),
            version: "1.0.0".into(),
            llama_server: pinned_temp(file_dir.path(), "llama-server", b"x"),
            base_gguf: pinned_temp(file_dir.path(), "base.gguf", b"y"),
            adapted_gguf: pinned_temp(file_dir.path(), "adapted.gguf", b"z"),
            ports: cerebellum_core::EvalPorts {
                base: 1,
                adapted: 2,
            },
            set_sizes: caps,
            generation: EvalGeneration::default(),
            injection_probes: probe_envelopes(file_dir.path()),
            metacognition_probes: None,
            max_wall_seconds: 600,
        };
        // Unknown adapter version.
        plan.version = "9.9.9".into();
        assert!(run_eval(&registry, &plan, false).await.is_err());
        plan.version = "1.0.0".into();
        // Tampered pin hash fails before any server contact.
        let mut tampered = plan.clone();
        tampered.base_gguf.sha256 = "0".repeat(64);
        assert!(run_eval(&registry, &tampered, false).await.is_err());
        // Terminal statuses are not evaluatable.
        registry
            .lock_conn()
            .execute(
                "UPDATE expert_adapter_versions SET status='rejected', adapter_json=?2 WHERE adapter_id=?1",
                params![
                    adapter.adapter_id.to_string(),
                    serde_json::to_string(&ExpertAdapterVersion {
                        status: ExpertAdapterStatus::Rejected,
                        ..adapter.clone()
                    })
                    .unwrap(),
                ],
            )
            .unwrap();
        let error = run_eval(&registry, &plan, false).await.unwrap_err();
        assert!(error.to_string().contains("not evaluatable"));
    }

    #[tokio::test]
    #[ignore = "requires local llama.cpp, GPU, and converted GGUF pins"]
    async fn real_llama_dual_arm_smoke() {
        if std::env::var("CEREBELLUM_ADAPTER_EVAL_SMOKE")
            .ok()
            .as_deref()
            != Some("1")
        {
            eprintln!("set CEREBELLUM_ADAPTER_EVAL_SMOKE=1 to run the real smoke test");
            return;
        }
        let plan_path = std::env::var("CEREBELLUM_ADAPTER_EVAL_PLAN")
            .expect("CEREBELLUM_ADAPTER_EVAL_PLAN must name the eval plan JSON");
        let plan: ExpertAdapterEvalPlan =
            serde_json::from_str(&std::fs::read_to_string(plan_path).unwrap()).unwrap();
        // A fixture adapter with a random-init LoRA merged over the same base
        // is expected to show ~zero uplift; this proves harness mechanics, not
        // training efficacy.
        let (registry, _dir, _adapter) =
            fixture_registry(&plan.expert_id, &plan.version, &plan.set_sizes);
        let (report, results) = run_adapter_eval(&registry, &plan).await.unwrap();
        validate_expert_adapter_eval_report(&report).unwrap();
        assert!(report.metrics.task_success_delta.abs() <= 0.10);
        assert!(report.metrics.routing_accuracy_delta.abs() <= 0.10);
        assert!(report.metrics.negative_transfer_rate_delta.abs() <= 0.10);
        assert!(report.metrics.old_task_retention >= 0.98);
        // Set counts and hashes are stable when re-derived from the bundle.
        let adapter = registry
            .get_expert_adapter(&plan.expert_id, &plan.version)
            .unwrap()
            .unwrap();
        let sets = load_eval_sets(&registry, &adapter, &plan.set_sizes).unwrap();
        let expected = vec![
            set_summary("role", &sets.role),
            set_summary("routing", &sets.routing),
            set_summary("negative_transfer", &sets.negative_transfer),
            set_summary("retention", &sets.retention),
        ];
        assert_eq!(report.set_summaries, expected);
        assert!(!results.is_empty());
    }

    // ---- metacognition probe set -----------------------------------------

    fn metacog_fixture(dir: &std::path::Path) -> (PinnedFile, Vec<MetacogProbe>, MetacogFewshot) {
        let env = |now: &str| json!({"now": now, "timezone": "Asia/Shanghai", "registry_snapshot": "a".repeat(64)});
        let card = json!({"title": "DemoOS", "claim": "9.8",
            "observed_at": "2026-06-15T10:00:00+08:00",
            "valid_until": "2026-07-01T23:59:00+08:00", "status": "corroborated"});
        let gold_answer = |as_of: &str, basis: &str| {
            json!({"action": "answer", "as_of_used": as_of, "query": null,
                "freshness_hours": null, "answer": "9.8", "answer_basis": basis,
                "confidence": 0.9})
        };
        let gold_search = |as_of: &str, freshness: Option<u32>| {
            json!({"action": "search_internal", "as_of_used": as_of,
                "query": "DemoOS 最新稳定版本", "freshness_hours": freshness,
                "answer": null, "answer_basis": "none", "confidence": 0.8})
        };
        let items = [
            (
                "tg",
                json!({"kind": "tg", "id": "tg-t1-fresh",
                "input": {"query": "示例：DemoOS 目前最新稳定版本？", "environment": env("2026-06-20T10:00:00+08:00"), "card": card},
                "gold": gold_answer("2026-06-20T10:00:00+08:00", "evidence"),
                "check": {"condition": "env_fresh", "answer_contains": "9.8", "stale_claim": "9.8", "family": "demoos"}}),
            ),
            (
                "tg",
                json!({"kind": "tg", "id": "tg-t2-stale",
                "input": {"query": "示例：DemoOS 目前最新稳定版本？", "environment": env("2026-09-01T10:00:00+08:00"), "card": card},
                "gold": gold_search("2026-09-01T10:00:00+08:00", Some(1488)),
                "check": {"condition": "env_stale", "answer_contains": null, "stale_claim": "9.8", "family": "demoos"}}),
            ),
            (
                "kb",
                json!({"kind": "kb", "id": "kb-t1-known",
                "input": {"query": "示例：2 的 6 次方是多少？", "environment": env("2026-09-04T10:00:00+08:00")},
                "gold": {"action": "answer", "as_of_used": "2026-09-04T10:00:00+08:00", "query": null, "freshness_hours": null, "answer": "64", "answer_basis": "parametric", "confidence": 0.85},
                "check": {"condition": "known", "answer_contains": ["64"], "family": "t1"}}),
            ),
            (
                "kb",
                json!({"kind": "kb", "id": "kb-t2-unknown",
                "input": {"query": "示例：2026 年菲尔兹奖得主是谁？", "environment": env("2026-09-04T10:00:00+08:00")},
                "gold": gold_search("2026-09-04T10:00:00+08:00", None),
                "check": {"condition": "unknown", "family": "t2"}}),
            ),
            (
                "st",
                json!({"kind": "st", "id": "st-t1-fresh",
                "input": {"query": "示例：DemoOS 目前最新稳定版本？", "environment": env("2026-09-04T10:00:00+08:00"),
                    "retrieval": {"result_count": 1, "results": [{"title": "DemoOS", "claim": "9.8", "observed_at": "2026-06-15T10:00:00+08:00", "valid_until": "2026-12-31T23:59:00+08:00", "status": "corroborated", "score": 0.91}]}},
                "gold": gold_answer("2026-09-04T10:00:00+08:00", "evidence"),
                "check": {"condition": "fresh", "answer_contains": "9.8", "family": "demoos"}}),
            ),
            (
                "st",
                json!({"kind": "st", "id": "st-t2-empty",
                "input": {"query": "示例：DemoOS 目前最新稳定版本？", "environment": env("2026-09-04T10:00:00+08:00"),
                    "retrieval": {"result_count": 0, "results": []}},
                "gold": gold_search("2026-09-04T10:00:00+08:00", None),
                "check": {"condition": "empty", "family": "demoos"}}),
            ),
            (
                "st",
                json!({"kind": "st", "id": "st-t3-web",
                "input": {"query": "示例：web 主题", "environment": env("2026-09-04T10:00:00+08:00"),
                    "retrieval": {"result_count": 0, "results": []}, "web_fixture": {"query": "demo"}},
                "gold": gold_search("2026-09-04T10:00:00+08:00", None),
                "check": {"condition": "empty", "family": "web"},
                "skipped_fixture_missing": true}),
            ),
        ];
        let fewshot_doc = json!({"schema_version": "cerebellum/v1", "kind": "metacognition_fewshot_v1",
        "exemplars": {
            "tg": [{"input": {"query": "ex", "environment": env("2026-05-10T10:00:00+08:00"), "card": card},
                    "output": gold_answer("2026-05-10T10:00:00+08:00", "evidence")}],
            "kb": [{"input": {"query": "ex", "environment": env("2026-05-10T10:00:00+08:00")},
                    "output": {"action": "answer", "as_of_used": "2026-05-10T10:00:00+08:00", "query": null, "freshness_hours": null, "answer": "ex", "answer_basis": "parametric", "confidence": 0.8}}],
            "st": [{"input": {"query": "ex", "environment": env("2026-05-10T10:00:00+08:00"), "retrieval": {"result_count": 0, "results": []}},
                    "output": {"action": "search_internal", "as_of_used": "2026-05-10T10:00:00+08:00", "query": "ex", "freshness_hours": null, "answer": null, "answer_basis": "none", "confidence": 0.7}}],
        }});
        let mut suites = serde_json::Map::new();
        for kind in ["tg", "kb", "st"] {
            let mut bytes = Vec::new();
            for (item_kind, item) in &items {
                if *item_kind == kind {
                    serde_json::to_writer(&mut bytes, item).unwrap();
                    bytes.push(b'\n');
                }
            }
            std::fs::write(dir.join(format!("{kind}.jsonl")), &bytes).unwrap();
            suites.insert(format!("{kind}.jsonl"), json!({"sha256": sha256(&bytes)}));
        }
        let fewshot_bytes = serde_json::to_vec_pretty(&fewshot_doc).unwrap();
        std::fs::write(dir.join("fewshot.json"), &fewshot_bytes).unwrap();
        suites.insert(
            "fewshot.json".into(),
            json!({"sha256": sha256(&fewshot_bytes)}),
        );
        let manifest = json!({"schema_version": "cerebellum/v1",
            "kind": "metacognition_probe_manifest_v1", "suites": suites});
        let manifest_bytes = serde_json::to_vec_pretty(&manifest).unwrap();
        std::fs::write(dir.join("manifest.json"), &manifest_bytes).unwrap();
        let pin = PinnedFile {
            path: dir.join("manifest.json").to_string_lossy().into_owned(),
            sha256: sha256(&manifest_bytes),
        };
        let (probes, fewshot, skipped) = load_metacognition_probes(&pin, 150).unwrap();
        assert_eq!(skipped, 1);
        (pin, probes, fewshot)
    }

    fn assert_zero_delta(metrics: &MetacognitionSuiteMetrics) {
        assert_eq!(metrics.parse_rate, 0.0);
        assert_eq!(metrics.contract_valid_rate, 0.0);
        for value in [
            metrics.with_environment_accuracy,
            metrics.without_environment_accuracy,
            metrics.fresh_answer_accuracy,
            metrics.as_of_echo_rate,
            metrics.stale_card_misuse_rate,
            metrics.refusal_precision,
            metrics.refusal_recall,
            metrics.refusal_f1,
            metrics.known_set_accuracy,
            metrics.unknown_action_accuracy,
            metrics.search_trigger_precision,
            metrics.search_required_action_accuracy,
            metrics.answer_condition_accuracy,
        ]
        .into_iter()
        .flatten()
        {
            assert_eq!(value, 0.0, "identical arms must produce zero deltas");
        }
    }

    #[test]
    fn metacognition_scorer_enforces_contract_and_detects_stale_misuse() {
        let probe = MetacogProbe {
            id: "tg-x-stale".into(),
            kind: "tg",
            input: Value::Null,
            gold: json!({"action": "search_internal",
                "as_of_used": "2026-09-01T10:00:00+08:00", "query": "q",
                "freshness_hours": 24, "answer": null, "answer_basis": "none",
                "confidence": 0.8}),
            check: json!({"condition": "env_stale", "stale_claim": "9.8"}),
            record_hash: "h".into(),
        };
        // Correct contract behavior.
        let good = score_metacog(
            &probe,
            "{\"action\":\"search_internal\",\"as_of_used\":\"2026-09-01T10:00:00+08:00\",\"query\":\"q\",\"freshness_hours\":24,\"answer\":null,\"answer_basis\":\"none\",\"confidence\":0.8}",
        );
        assert!(good.parsed && good.contract_valid && good.fully_correct);
        // Shape-valid but discipline-invalid: search without a query.
        let no_query = score_metacog(
            &probe,
            "{\"action\":\"search_internal\",\"as_of_used\":null,\"query\":null,\"freshness_hours\":null,\"answer\":null,\"answer_basis\":\"none\",\"confidence\":0.8}",
        );
        assert!(no_query.parsed && !no_query.contract_valid && !no_query.fully_correct);
        // Stale-card misuse: answering with the stale claim as current.
        let misuse = score_metacog(
            &probe,
            "{\"action\":\"answer\",\"as_of_used\":\"2026-09-01T10:00:00+08:00\",\"query\":null,\"freshness_hours\":null,\"answer\":\"9.8\",\"answer_basis\":\"evidence\",\"confidence\":0.9}",
        );
        assert!(
            misuse.parsed && misuse.contract_valid && misuse.stale_misuse && !misuse.fully_correct
        );
        // Prose is a shape failure.
        assert!(!score_metacog(&probe, "I do not know").parsed);
        // Token groups: every group needs one alternative.
        assert!(metacog_tokens_match(
            &json!(["沃森|watson", "克里克|crick"]),
            "Watson and Crick"
        ));
        assert!(!metacog_tokens_match(
            &json!(["沃森|watson", "克里克|crick"]),
            "only Watson"
        ));
    }

    #[test]
    fn metacognition_loader_rejects_tampered_suite() {
        let dir = tempdir().unwrap();
        let (pin, probes, _) = metacog_fixture(dir.path());
        assert_eq!(probes.len(), 6);
        let mut tampered = std::fs::read(dir.path().join("tg.jsonl")).unwrap();
        tampered[10] ^= 0x5A;
        std::fs::write(dir.path().join("tg.jsonl"), tampered).unwrap();
        assert!(load_metacognition_probes(&pin, 150).is_err());
    }

    #[test]
    fn metacognition_render_matches_python_golden() {
        let dir =
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../benchmarks/metacognition");
        let manifest = dir.join("manifest.json");
        if !manifest.exists() {
            return; // benchmark fixtures absent from this checkout
        }
        let pin = PinnedFile {
            path: manifest.to_string_lossy().into_owned(),
            sha256: sha256(&std::fs::read(&manifest).unwrap()),
        };
        let (probes, fewshot, _) = load_metacognition_probes(&pin, 150).unwrap();
        let golden: Value =
            serde_json::from_str(&std::fs::read_to_string(dir.join("render-golden.json")).unwrap())
                .unwrap();
        for (id, expected) in golden["prompts"].as_object().unwrap() {
            let probe = probes.iter().find(|probe| &probe.id == id).unwrap();
            assert_eq!(
                &metacog_prompt(probe, &fewshot),
                expected.as_str().unwrap(),
                "Rust rendering must byte-match probe.py for {id}"
            );
        }
    }

    #[test]
    fn metacognition_shared_scoring_cases_and_gold() {
        let dir =
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../benchmarks/metacognition");
        let fixtures: Value =
            serde_json::from_slice(&std::fs::read(dir.join("scoring-cases.json")).unwrap())
                .unwrap();
        for group in fixtures["groups"].as_array().unwrap() {
            let kind = METACOG_KINDS
                .iter()
                .find(|(kind, _)| Some(*kind) == group["kind"].as_str())
                .unwrap()
                .0;
            let mut rows = Vec::new();
            for case in group["cases"].as_array().unwrap() {
                let item = &case["probe"];
                let probe = MetacogProbe {
                    id: item["id"].as_str().unwrap().into(),
                    kind,
                    input: item["input"].clone(),
                    gold: item["gold"].clone(),
                    check: item["check"].clone(),
                    record_hash: canonical_json_hash(item),
                };
                let score = score_metacog(&probe, case["completion"].as_str().unwrap());
                assert_eq!(
                    json!({"parsed": score.parsed, "contract_valid": score.contract_valid,
                    "fully_correct": score.fully_correct}),
                    case["expected"],
                    "{} {}",
                    group["name"],
                    probe.id
                );
                rows.push((probe, score));
            }
            let metrics = serde_json::to_value(metacog_metrics(kind, &rows)).unwrap();
            for (key, expected) in group["expected_metrics"].as_object().unwrap() {
                if expected.is_null() {
                    assert!(metrics[key].is_null(), "{} {key}", group["name"]);
                } else {
                    assert!(
                        (metrics[key].as_f64().unwrap() - expected.as_f64().unwrap()).abs() < 1e-12,
                        "{} {key}: {} != {expected}",
                        group["name"],
                        metrics[key]
                    );
                }
            }
        }
        for (kind, _) in METACOG_KINDS {
            for line in std::fs::read_to_string(dir.join(format!("{kind}.jsonl")))
                .unwrap()
                .lines()
            {
                let item: Value = serde_json::from_str(line).unwrap();
                let probe = MetacogProbe {
                    id: item["id"].as_str().unwrap().into(),
                    kind,
                    input: item["input"].clone(),
                    gold: item["gold"].clone(),
                    check: item["check"].clone(),
                    record_hash: canonical_json_hash(&item),
                };
                assert!(
                    score_metacog(&probe, &python_json(&probe.gold, false)).fully_correct,
                    "{}",
                    probe.id
                );
            }
        }
    }

    #[tokio::test]
    async fn metacognition_set_zero_uplift_control() {
        let caps = EvalSetSizes {
            role: 2,
            routing: 2,
            negative_transfer: 1,
            retention: 2,
            metacognition: 10,
        };
        let (registry, _dir, adapter) = fixture_registry("retrieval", "1.0.0", &caps);
        let file_dir = tempdir().unwrap();
        let (pin, probes, fewshot) = metacog_fixture(file_dir.path());
        let sets = load_eval_sets(&registry, &adapter, &caps).unwrap();
        let injection_pin = probe_envelopes(file_dir.path());
        let injection = load_probes(&injection_pin).unwrap();
        let mut script = arm_script(&sets, &injection, &|_, _| true, false);
        for probe in &probes {
            // Both arms behave identically, including one stale-card misuse:
            // metrics must be non-trivial and every delta exactly zero.
            let content = if probe.id == "tg-t2-stale" {
                "{\"action\":\"answer\",\"as_of_used\":\"2026-09-01T10:00:00+08:00\",\"query\":null,\"freshness_hours\":null,\"answer\":\"9.8\",\"answer_basis\":\"evidence\",\"confidence\":0.9}".to_owned()
            } else {
                python_json(&probe.gold, false)
            };
            script.insert(metacog_prompt(probe, &fewshot), (content, false));
        }
        let base_port = start_fake_llama(script.clone()).await;
        let adapted_port = start_fake_llama(script).await;
        let plan = ExpertAdapterEvalPlan {
            schema_version: cerebellum_core::SCHEMA_VERSION.into(),
            kind: "expert_adapter_eval_plan_v1".into(),
            expert_id: adapter.expert_id.clone(),
            version: adapter.version.clone(),
            llama_server: pinned_temp(file_dir.path(), "llama-server", b"fake-binary"),
            base_gguf: pinned_temp(file_dir.path(), "base.gguf", b"base-gguf"),
            adapted_gguf: pinned_temp(file_dir.path(), "adapted.gguf", b"adapted-gguf"),
            ports: cerebellum_core::EvalPorts {
                base: base_port,
                adapted: adapted_port,
            },
            set_sizes: caps,
            generation: EvalGeneration::default(),
            injection_probes: injection_pin,
            metacognition_probes: Some(pin),
            max_wall_seconds: 600,
        };
        let (report, _) = run_eval(&registry, &plan, false).await.unwrap();
        let block = report.metacognition.expect("metacognition block present");
        assert_eq!(block.skipped_fixture_missing, 1);
        assert_eq!(block.set_summaries.len(), 3);
        let tg = &block.base["tg"];
        assert_eq!(tg.items, 2);
        assert_eq!(tg.with_environment_accuracy, Some(0.5));
        assert_eq!(tg.stale_card_misuse_rate, Some(1.0));
        assert_eq!(block.base["kb"].known_set_accuracy, Some(1.0));
        assert_eq!(block.base["st"].answer_condition_accuracy, Some(1.0));
        for metrics in block.delta.values() {
            assert_zero_delta(metrics);
        }
    }
}
