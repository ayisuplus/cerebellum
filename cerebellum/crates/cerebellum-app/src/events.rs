//! Event threading: board-document hot items are stored as `EventItem` rows and
//! incrementally clustered into cross-day `TrackedEvent`s using the same CJK
//! bigram + Jaccard/containment + rare-term greedy algorithm as the Python
//! worker (`workers/social-acquisition/.../event_cluster.py`). Events reaching
//! at least two platforms synthesize a deterministic knowledge card that flows
//! through the regular quality-assess and promotion loop.

use crate::Registry;
use anyhow::{Context, Result};
use cerebellum_core::{
    DocumentEnvelope, EventItem, EventStatus, EvidenceRelationship, KnowledgeCard, KnowledgeClaim,
    KnowledgeEvidenceRef, KnowledgeScores, KnowledgeStatus, SCHEMA_VERSION, TrackedEvent,
    validate_event_item, validate_tracked_event,
};
use chrono::{DateTime, Duration, Utc};
use rusqlite::{OptionalExtension, params};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use url::Url;
use uuid::Uuid;

/// Open events older than this many days no longer accept new members.
const OPEN_EVENT_WINDOW_DAYS: i64 = 7;
/// Per-event member cap for attach comparisons (performance guard).
const ATTACH_MEMBER_CAP: usize = 50;
/// Observations kept per item; oldest are dropped past this.
const OBSERVATION_CAP: usize = 90;

/// Question/lead-in prefixes stripped before feature extraction, so that
/// 「如何看待X」 and 「X」 can cluster together. Verbatim copy of the Python
/// `_QUESTION_PREFIXES`.
const QUESTION_PREFIXES: [&str; 16] = [
    "如何看待",
    "如何评价",
    "怎么看",
    "怎么评价",
    "怎么样",
    "为什么",
    "为啥",
    "啥是",
    "什么是",
    "请问",
    "怎样看待",
    "如何理解",
    "怎么看待",
    "大家觉得",
    "有没有",
    "是否",
];

/// Meaningless high-frequency bigrams (platform names / generic words) that
/// would otherwise fabricate false similarity. Verbatim copy of the Python
/// `_STOPWORD_BIGRAMS` (including its duplicate entry, which is harmless in a
/// membership test).
const STOPWORD_BIGRAMS: &[&str] = &[
    "如何", "何看", "看待", "如何", "评价", "为什", "什么", "大家", "我们", "他们", "这个", "那个",
    "一个", "就是", "可以", "因为", "所以", "但是", "而且", "或者", "如果", "虽然", "已经", "现在",
    "今天", "昨天", "明天", "时候", "问题", "事情", "情况", "相关",
];

fn platform_display_name(code: &str) -> &str {
    match code {
        "weibo" => "微博",
        "zhihu" => "知乎",
        "douyin" => "抖音",
        "bilibili" => "B站",
        "xhs" => "小红书",
        "tieba" => "贴吧",
        "kuaishou" => "快手",
        "baidu" => "百度",
        other => other,
    }
}

fn is_cjk(ch: char) -> bool {
    let cp = ch as u32;
    (0x4E00..=0x9FFF).contains(&cp) || (0x3400..=0x4DBF).contains(&cp)
}

/// Strip question prefixes (repeatedly, they can stack) and drop every
/// character that is not CJK or ASCII alphanumeric; lowercase the remainder.
/// Distinct from `knowledge::normalize_title`, which keeps no bigram-usable
/// text.
fn normalize_title(title: &str) -> String {
    if title.is_empty() {
        return String::new();
    }
    let mut text = title.trim().to_owned();
    loop {
        let mut changed = false;
        for prefix in QUESTION_PREFIXES {
            if let Some(rest) = text.strip_prefix(prefix) {
                text = rest
                    .trim_start_matches(|ch: char| {
                        matches!(ch, '，' | '。' | ',' | '.' | '：' | ':' | '？' | '?' | ' ')
                    })
                    .to_owned();
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    text.chars()
        .filter(|ch| is_cjk(*ch) || ch.is_ascii_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

/// Topic fingerprint of a title: CJK bigrams over each maximal CJK run
/// (single CJK chars kept so very short titles still have features) plus
/// ASCII words of length >= 2 starting with a letter.
fn extract_features(title: &str) -> BTreeSet<String> {
    let normalized = normalize_title(title);
    if normalized.is_empty() {
        return BTreeSet::new();
    }
    let chars: Vec<char> = normalized.chars().collect();
    let mut features = BTreeSet::new();
    let mut index = 0;
    while index < chars.len() {
        if is_cjk(chars[index]) {
            let start = index;
            while index < chars.len() && is_cjk(chars[index]) {
                index += 1;
            }
            let run = &chars[start..index];
            if run.len() == 1 {
                features.insert(run[0].to_string());
            } else {
                for window in run.windows(2) {
                    let bigram: String = window.iter().collect();
                    if !STOPWORD_BIGRAMS.contains(&bigram.as_str()) {
                        features.insert(bigram);
                    }
                }
            }
        } else {
            index += 1;
        }
    }
    let mut index = 0;
    while index < chars.len() {
        if chars[index].is_ascii_alphabetic() {
            let start = index;
            while index < chars.len() && chars[index].is_ascii_alphanumeric() {
                index += 1;
            }
            if index - start >= 2 {
                features.insert(chars[start..index].iter().collect());
            }
        } else {
            index += 1;
        }
    }
    features
}

fn jaccard(a: &BTreeSet<String>, b: &BTreeSet<String>) -> f64 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let intersection = a.intersection(b).count() as f64;
    let union = a.union(b).count() as f64;
    if union == 0.0 {
        0.0
    } else {
        intersection / union
    }
}

/// Intersection over the smaller set; catches 「short title ⊂ long title」.
fn containment(a: &BTreeSet<String>, b: &BTreeSet<String>) -> f64 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let intersection = a.intersection(b).count() as f64;
    let smaller = a.len().min(b.len()) as f64;
    if smaller == 0.0 {
        0.0
    } else {
        intersection / smaller
    }
}

/// Combined similarity: the better of Jaccard and slightly down-weighted
/// containment.
fn similarity(a: &BTreeSet<String>, b: &BTreeSet<String>) -> f64 {
    jaccard(a, b).max(containment(a, b) * 0.85)
}

struct EventMember {
    heat: i64,
    last_observed_at: DateTime<Utc>,
    features: BTreeSet<String>,
    rare: BTreeSet<String>,
}

struct OpenEvent {
    event_id: Uuid,
    members: Vec<EventMember>,
}

impl OpenEvent {
    /// Peak-heat member; ties resolve to the most recently observed.
    fn representative(&self) -> &EventMember {
        self.members
            .iter()
            .max_by_key(|member| (member.heat, member.last_observed_at))
            .expect("open events always have at least one member")
    }

    fn push_member(&mut self, member: EventMember) {
        self.members.push(member);
        if self.members.len() > ATTACH_MEMBER_CAP {
            let lowest = self
                .members
                .iter()
                .enumerate()
                .min_by_key(|(_, member)| (member.heat, member.last_observed_at))
                .map(|(index, _)| index)
                .expect("non-empty member list");
            self.members.remove(lowest);
        }
    }
}

/// Greedy attach: compare against every member of every open event, tracking
/// the member with the most shared rare features (ties broken by similarity).
/// Attach directly at sim >= 0.35; otherwise a shared rare term still attaches
/// when sim >= 0.15 and the event representative reaches 0.10.
fn attach(
    features: &BTreeSet<String>,
    rare: &BTreeSet<String>,
    open_events: &[OpenEvent],
) -> Option<Uuid> {
    let mut best: Option<usize> = None;
    let mut best_sim = 0.0_f64;
    let mut best_rare = 0_usize;
    for (index, event) in open_events.iter().enumerate() {
        for member in &event.members {
            let sim = similarity(features, &member.features);
            let shared_rare = rare.intersection(&member.rare).count();
            if shared_rare > best_rare || (shared_rare == best_rare && sim > best_sim) {
                best_rare = shared_rare;
                best_sim = sim;
                best = Some(index);
            }
        }
    }
    let index = best?;
    if best_sim >= 0.35 {
        return Some(open_events[index].event_id);
    }
    if best_rare >= 1 && best_sim >= 0.15 {
        let rep_sim = similarity(features, &open_events[index].representative().features);
        if rep_sim >= 0.10 {
            return Some(open_events[index].event_id);
        }
    }
    None
}

/// Lifecycle status from observation timestamps alone.
pub fn current_status(
    first_seen: DateTime<Utc>,
    last_seen: DateTime<Utc>,
    now: DateTime<Utc>,
) -> EventStatus {
    let silent = now - last_seen;
    if silent > Duration::hours(72) {
        EventStatus::Resolved
    } else if silent > Duration::hours(24) {
        EventStatus::Fading
    } else if now - first_seen > Duration::hours(24) {
        EventStatus::Peak
    } else {
        EventStatus::Emerging
    }
}

fn event_status_name(status: EventStatus) -> &'static str {
    match status {
        EventStatus::Emerging => "emerging",
        EventStatus::Peak => "peak",
        EventStatus::Fading => "fading",
        EventStatus::Resolved => "resolved",
    }
}

pub fn stable_event_card_id(event_id: Uuid) -> Uuid {
    stable_uuid(format!("knowledge-event:{event_id}").as_bytes())
}

/// Deterministic UUID v5-style derivation; byte-identical copy of
/// `knowledge.rs`'s private `stable_uuid` (kept local to preserve module
/// boundaries).
fn stable_uuid(value: &[u8]) -> Uuid {
    let digest = Sha256::digest(value);
    let mut bytes = [0_u8; 16];
    bytes.copy_from_slice(&digest[..16]);
    bytes[6] = (bytes[6] & 0x0f) | 0x50;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    Uuid::from_bytes(bytes)
}

fn parse_time(value: &str) -> Result<DateTime<Utc>> {
    Ok(DateTime::parse_from_rfc3339(value)?.with_timezone(&Utc))
}

/// Truncate to `max_chars`, appending an ellipsis when truncated; same rule as
/// `knowledge.rs`'s `bounded_summary`.
fn bounded(text: &str, max_chars: usize) -> String {
    let mut out = text.chars().take(max_chars).collect::<String>();
    if text.chars().count() > max_chars {
        out.push('…');
    }
    out
}

struct BoardItemSeed {
    platform: String,
    external_id: String,
    title: String,
    url: String,
    author: Option<String>,
    published_at: Option<DateTime<Utc>>,
    summary: Option<String>,
    heat: i64,
    rank: i64,
    features: BTreeSet<String>,
}

/// Ingest one board document's `metadata.items` into the event store. Returns
/// the number of items written (inserted or updated). Missing or malformed
/// `items` metadata is a no-op.
pub fn ingest_board_document(registry: &Registry, document: &DocumentEnvelope) -> Result<usize> {
    ingest_board_document_at(registry, document, Utc::now())
}

fn ingest_board_document_at(
    registry: &Registry,
    document: &DocumentEnvelope,
    now: DateTime<Utc>,
) -> Result<usize> {
    let Some(values) = document.metadata.get("items").and_then(Value::as_array) else {
        return Ok(0);
    };
    let mut batch: Vec<BoardItemSeed> = Vec::new();
    for value in values {
        let platform = value
            .get("platform")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim();
        let title = value
            .get("title")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim();
        let url = value
            .get("url")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim();
        if platform.is_empty() || title.is_empty() || url.is_empty() {
            continue;
        }
        let external_id = value
            .get("external_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|raw| !raw.is_empty())
            .unwrap_or(url)
            .to_owned();
        let published_at = value
            .get("published_at")
            .and_then(Value::as_str)
            .and_then(|raw| DateTime::parse_from_rfc3339(raw).ok())
            .map(|parsed| parsed.with_timezone(&Utc));
        batch.push(BoardItemSeed {
            platform: platform.to_owned(),
            external_id,
            title: title.to_owned(),
            url: url.to_owned(),
            author: value
                .get("author")
                .and_then(Value::as_str)
                .map(str::to_owned),
            published_at,
            summary: value
                .get("summary")
                .and_then(Value::as_str)
                .map(str::to_owned),
            heat: value.get("heat").and_then(Value::as_i64).unwrap_or(0),
            rank: value.get("rank").and_then(Value::as_i64).unwrap_or(0),
            features: extract_features(title),
        });
    }
    if batch.is_empty() {
        return Ok(0);
    }
    batch.sort_by_key(|item| item.rank);

    let cutoff = (now - Duration::days(OPEN_EVENT_WINDOW_DAYS)).to_rfc3339();
    let mut open_events = load_open_events(registry, &cutoff)?;

    // Rare-feature pool: this batch plus every open event's representative.
    let mut doc_freq: BTreeMap<&str, usize> = BTreeMap::new();
    for item in &batch {
        for feature in &item.features {
            *doc_freq.entry(feature.as_str()).or_insert(0) += 1;
        }
    }
    for event in &open_events {
        for feature in &event.representative().features {
            *doc_freq.entry(feature.as_str()).or_insert(0) += 1;
        }
    }
    let n_docs = batch.len() + open_events.len();
    let rare_cutoff = (2.0_f64).max(n_docs as f64 * 0.5);
    let rare: BTreeSet<String> = doc_freq
        .iter()
        .filter(|(_, count)| **count <= 3 && (**count as f64) < rare_cutoff)
        .map(|(feature, _)| (*feature).to_owned())
        .collect();
    for event in &mut open_events {
        for member in &mut event.members {
            member.rare = member
                .features
                .iter()
                .filter(|feature| rare.contains(feature.as_str()))
                .cloned()
                .collect();
        }
    }

    let day = now.date_naive().format("%Y-%m-%d").to_string();
    let mut touched: BTreeSet<Uuid> = BTreeSet::new();
    let mut ingested = 0_usize;
    // One transaction for the whole board: item upserts, placeholder events,
    // and aggregate refreshes commit or roll back together.
    let mut refreshed: Vec<(TrackedEvent, Vec<EventItem>)> = Vec::new();
    {
        let mut conn = registry.lock_conn();
        let tx = conn.transaction()?;
        for item in &batch {
            if let Some((event_id, mut stored)) =
                load_event_item(&tx, &item.platform, &item.external_id)?
            {
                // Already threaded: never re-cluster, just refresh the observation.
                stored.heat = stored.heat.max(item.heat);
                stored.rank = merge_rank(stored.rank, item.rank);
                if !stored.observations.iter().any(|(seen, _)| seen == &day) {
                    stored.observations.push((day.clone(), item.heat));
                    if stored.observations.len() > OBSERVATION_CAP {
                        let excess = stored.observations.len() - OBSERVATION_CAP;
                        stored.observations.drain(..excess);
                    }
                }
                stored.title = item.title.clone();
                stored.url = item.url.clone();
                stored.author = item.author.clone();
                stored.published_at = item.published_at.or(stored.published_at);
                stored.summary = item.summary.clone().or(stored.summary.take());
                stored.last_observed_at = stored.last_observed_at.max(now);
                stored.document_id = document.document_id;
                save_event_item(&tx, event_id, &stored)?;
                touched.insert(event_id);
                ingested += 1;
                continue;
            }

            let item_rare: BTreeSet<String> = item
                .features
                .iter()
                .filter(|feature| rare.contains(feature.as_str()))
                .cloned()
                .collect();
            let event_id = match attach(&item.features, &item_rare, &open_events) {
                Some(event_id) => event_id,
                None => {
                    let event_id = Uuid::new_v4();
                    insert_event_placeholder(&tx, event_id, item, now)?;
                    open_events.push(OpenEvent {
                        event_id,
                        members: Vec::new(),
                    });
                    event_id
                }
            };
            let member = EventMember {
                heat: item.heat,
                last_observed_at: now,
                features: item.features.clone(),
                rare: item_rare,
            };
            if let Some(event) = open_events
                .iter_mut()
                .find(|event| event.event_id == event_id)
            {
                event.push_member(member);
            }
            save_event_item(
                &tx,
                event_id,
                &EventItem {
                    schema_version: SCHEMA_VERSION.into(),
                    platform: item.platform.clone(),
                    external_id: item.external_id.clone(),
                    title: item.title.clone(),
                    url: item.url.clone(),
                    author: item.author.clone(),
                    published_at: item.published_at,
                    summary: item.summary.clone(),
                    heat: item.heat,
                    rank: item.rank,
                    observations: vec![(day.clone(), item.heat)],
                    document_id: document.document_id,
                    first_observed_at: now,
                    last_observed_at: now,
                },
            )?;
            touched.insert(event_id);
            ingested += 1;
        }
        for event_id in touched {
            let items = event_items(&tx, event_id)?;
            if let Some(event) = refresh_event_aggregates(&tx, event_id, now, &items)? {
                refreshed.push((event, items));
            }
        }
        tx.commit()?;
    }
    // Card synthesis reads knowledge/documents through the registry (never
    // inside the item transaction); event and items come from memory.
    for (event, items) in refreshed {
        maybe_refresh_event_card(registry, &event, now, &items)?;
    }
    Ok(ingested)
}

/// Rank merge on re-observation: keep the best (lowest) rank, treating 0 as
/// "not ranked".
fn merge_rank(stored: i64, incoming: i64) -> i64 {
    match (stored, incoming) {
        (0, 0) => 0,
        (0, incoming) => incoming,
        (stored, 0) => stored,
        _ => stored.min(incoming),
    }
}

fn load_open_events(registry: &Registry, cutoff_rfc3339: &str) -> Result<Vec<OpenEvent>> {
    let conn = registry.lock_conn();
    // One JOIN with a per-event member cap (correlated rowid subquery),
    // replacing the previous per-event query loop.
    let mut statement = conn.prepare(
        "SELECT e.event_id, i.title, i.heat, i.last_observed_at
         FROM tracked_events e
         JOIN event_items i ON i.event_id = e.event_id
         WHERE e.last_seen_at>=?1
           AND i.rowid IN (
             SELECT rowid FROM event_items i2
             WHERE i2.event_id = i.event_id
             ORDER BY heat DESC, last_observed_at DESC LIMIT ?2
           )
         ORDER BY e.last_seen_at DESC, i.heat DESC, i.last_observed_at DESC",
    )?;
    let rows = statement
        .query_map(params![cutoff_rfc3339, ATTACH_MEMBER_CAP as i64], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, String>(3)?,
            ))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let mut events: Vec<OpenEvent> = Vec::new();
    for (id, title, heat, last_observed_at) in rows {
        let member = EventMember {
            heat,
            last_observed_at: parse_time(&last_observed_at)?,
            features: extract_features(&title),
            rare: BTreeSet::new(),
        };
        match events.last_mut() {
            Some(event) if event.event_id.to_string() == id => {
                event.members.push(member);
            }
            _ => events.push(OpenEvent {
                event_id: Uuid::parse_str(&id).context("stored event id is not a UUID")?,
                members: vec![member],
            }),
        }
    }
    Ok(events)
}

fn load_event_item(
    conn: &rusqlite::Connection,
    platform: &str,
    external_id: &str,
) -> Result<Option<(Uuid, EventItem)>> {
    let row = conn
        .query_row(
            "SELECT event_id,title,url,author,published_at,summary,heat,rank,observations,
                    document_id,first_observed_at,last_observed_at
             FROM event_items WHERE platform=?1 AND external_id=?2",
            params![platform, external_id],
            |row| {
                Ok(EventItemRow {
                    event_id: row.get(0)?,
                    title: row.get(1)?,
                    url: row.get(2)?,
                    author: row.get(3)?,
                    published_at: row.get(4)?,
                    summary: row.get(5)?,
                    heat: row.get(6)?,
                    rank: row.get(7)?,
                    observations: row.get(8)?,
                    document_id: row.get(9)?,
                    first_observed_at: row.get(10)?,
                    last_observed_at: row.get(11)?,
                })
            },
        )
        .optional()?;
    row.map(|row| {
        let event_id =
            Uuid::parse_str(&row.event_id).context("stored item event id is not a UUID")?;
        row.into_item(platform.to_owned(), external_id.to_owned())
            .map(|item| (event_id, item))
    })
    .transpose()
}

struct EventItemRow {
    event_id: String,
    title: String,
    url: String,
    author: Option<String>,
    published_at: Option<String>,
    summary: Option<String>,
    heat: i64,
    rank: i64,
    observations: String,
    document_id: String,
    first_observed_at: String,
    last_observed_at: String,
}

impl EventItemRow {
    fn into_item(self, platform: String, external_id: String) -> Result<EventItem> {
        Ok(EventItem {
            schema_version: SCHEMA_VERSION.into(),
            platform,
            external_id,
            title: self.title,
            url: self.url,
            author: self.author,
            published_at: self.published_at.map(|raw| parse_time(&raw)).transpose()?,
            summary: self.summary,
            heat: self.heat,
            rank: self.rank,
            observations: serde_json::from_str(&self.observations)?,
            document_id: Uuid::parse_str(&self.document_id)?,
            first_observed_at: parse_time(&self.first_observed_at)?,
            last_observed_at: parse_time(&self.last_observed_at)?,
        })
    }
}

/// Upsert one item row. `event_id` is only written on insert: a threaded item
/// never changes events (the ON CONFLICT clause deliberately omits event_id).
fn save_event_item(conn: &rusqlite::Connection, event_id: Uuid, item: &EventItem) -> Result<()> {
    validate_event_item(item)?;
    conn.execute(
        "INSERT INTO event_items(
           platform,external_id,event_id,title,url,author,published_at,summary,heat,rank,
           observations,document_id,first_observed_at,last_observed_at
         ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14)
         ON CONFLICT(platform,external_id) DO UPDATE SET
           title=excluded.title,url=excluded.url,author=excluded.author,
           published_at=excluded.published_at,summary=excluded.summary,heat=excluded.heat,
           rank=excluded.rank,observations=excluded.observations,document_id=excluded.document_id,
           last_observed_at=excluded.last_observed_at",
        params![
            item.platform,
            item.external_id,
            event_id.to_string(),
            item.title,
            item.url,
            item.author,
            item.published_at.map(|value| value.to_rfc3339()),
            item.summary,
            item.heat,
            item.rank,
            serde_json::to_string(&item.observations)?,
            item.document_id.to_string(),
            item.first_observed_at.to_rfc3339(),
            item.last_observed_at.to_rfc3339(),
        ],
    )?;
    Ok(())
}

fn insert_event_placeholder(
    conn: &rusqlite::Connection,
    event_id: Uuid,
    item: &BoardItemSeed,
    now: DateTime<Utc>,
) -> Result<()> {
    let event = TrackedEvent {
        schema_version: SCHEMA_VERSION.into(),
        event_id,
        title: item.title.clone(),
        status: EventStatus::Emerging,
        first_seen_at: now,
        last_seen_at: now,
        peak_heat: item.heat,
        platforms: vec![item.platform.clone()],
        item_count: 1,
        card_id: None,
        created_at: now,
        updated_at: now,
    };
    write_event_row(conn, &event)
}

fn write_event_row(conn: &rusqlite::Connection, event: &TrackedEvent) -> Result<()> {
    validate_tracked_event(event)?;
    conn.execute(
        "INSERT INTO tracked_events(
           event_id,title,status,first_seen_at,last_seen_at,peak_heat,platforms,item_count,
           card_id,event_json,created_at,updated_at
         ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12)
         ON CONFLICT(event_id) DO UPDATE SET
           title=excluded.title,status=excluded.status,first_seen_at=excluded.first_seen_at,
           last_seen_at=excluded.last_seen_at,peak_heat=excluded.peak_heat,
           platforms=excluded.platforms,item_count=excluded.item_count,card_id=excluded.card_id,
           event_json=excluded.event_json,updated_at=excluded.updated_at",
        params![
            event.event_id.to_string(),
            event.title,
            event_status_name(event.status),
            event.first_seen_at.to_rfc3339(),
            event.last_seen_at.to_rfc3339(),
            event.peak_heat,
            serde_json::to_string(&event.platforms)?,
            event.item_count as i64,
            event.card_id.map(|id| id.to_string()),
            serde_json::to_string(event)?,
            event.created_at.to_rfc3339(),
            event.updated_at.to_rfc3339(),
        ],
    )?;
    Ok(())
}

fn read_event(conn: &rusqlite::Connection, event_id: Uuid) -> Result<Option<TrackedEvent>> {
    let json: Option<String> = conn
        .query_row(
            "SELECT event_json FROM tracked_events WHERE event_id=?1",
            params![event_id.to_string()],
            |row| row.get(0),
        )
        .optional()?;
    json.map(|json| serde_json::from_str(&json).map_err(Into::into))
        .transpose()
}

fn event_items(conn: &rusqlite::Connection, event_id: Uuid) -> Result<Vec<EventItem>> {
    let mut statement = conn.prepare(
        "SELECT platform,external_id,event_id,title,url,author,published_at,summary,heat,rank,
                observations,document_id,first_observed_at,last_observed_at
         FROM event_items WHERE event_id=?1 ORDER BY platform,external_id",
    )?;
    let rows = statement
        .query_map(params![event_id.to_string()], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                EventItemRow {
                    event_id: row.get(2)?,
                    title: row.get(3)?,
                    url: row.get(4)?,
                    author: row.get(5)?,
                    published_at: row.get(6)?,
                    summary: row.get(7)?,
                    heat: row.get(8)?,
                    rank: row.get(9)?,
                    observations: row.get(10)?,
                    document_id: row.get(11)?,
                    first_observed_at: row.get(12)?,
                    last_observed_at: row.get(13)?,
                },
            ))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    rows.into_iter()
        .map(|(platform, external_id, row)| row.into_item(platform, external_id))
        .collect()
}

/// Recompute an event's aggregate columns from the caller-supplied items and
/// persist the row. `updated_at` only moves when the event content actually
/// changed. Returns the refreshed event for downstream card synthesis.
fn refresh_event_aggregates(
    conn: &rusqlite::Connection,
    event_id: Uuid,
    now: DateTime<Utc>,
    items: &[EventItem],
) -> Result<Option<TrackedEvent>> {
    let Some(existing) = read_event(conn, event_id)? else {
        return Ok(None);
    };
    if items.is_empty() {
        return Ok(None);
    }
    let lead = items
        .iter()
        .max_by_key(|item| (item.heat, item.last_observed_at))
        .expect("non-empty item list");
    let mut event = TrackedEvent {
        title: lead.title.clone(),
        platforms: items
            .iter()
            .map(|item| item.platform.clone())
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect(),
        peak_heat: items.iter().map(|item| item.heat).max().unwrap_or(0),
        item_count: items.len() as u64,
        first_seen_at: items
            .iter()
            .map(|item| item.first_observed_at)
            .min()
            .expect("non-empty item list"),
        last_seen_at: items
            .iter()
            .map(|item| item.last_observed_at)
            .max()
            .expect("non-empty item list"),
        ..existing.clone()
    };
    event.status = current_status(event.first_seen_at, event.last_seen_at, now);
    if serde_json::to_string(&event)? != serde_json::to_string(&existing)? {
        event.updated_at = now;
    }
    write_event_row(conn, &event)?;
    Ok(Some(event))
}

/// Deterministic knowledge card synthesis for cross-platform events. No LLM;
/// identical inputs produce identical card content, so re-ingesting the same
/// boards never mints a new revision. Caller supplies the refreshed event
/// and its items (no re-reads here).
fn maybe_refresh_event_card(
    registry: &Registry,
    event: &TrackedEvent,
    now: DateTime<Utc>,
    items: &[EventItem],
) -> Result<()> {
    if event.platforms.len() < 2 || items.len() < 2 {
        return Ok(());
    }
    let card_id = stable_event_card_id(event.event_id);
    let latest = registry.get_knowledge_card(card_id)?;

    let mut per_platform: BTreeMap<String, EventItem> = BTreeMap::new();
    for item in items {
        per_platform
            .entry(item.platform.clone())
            .and_modify(|current| {
                if (item.heat, item.last_observed_at) > (current.heat, current.last_observed_at) {
                    *current = item.clone();
                }
            })
            .or_insert(item.clone());
    }

    let platform_names = event
        .platforms
        .iter()
        .map(|code| platform_display_name(code))
        .collect::<Vec<_>>()
        .join("、");
    let representatives = per_platform
        .values()
        .take(5)
        .map(|item| item.title.as_str())
        .collect::<Vec<_>>()
        .join("；");
    let summary = bounded(
        &format!(
            "事件「{}」自 {} 起登上 {} 个平台热榜（{}），峰值热度 {}，当前状态 {}。各平台代表条目：{}",
            event.title,
            event.first_seen_at.date_naive().format("%Y-%m-%d"),
            event.platforms.len(),
            platform_names,
            event.peak_heat,
            event_status_name(event.status),
            representatives,
        ),
        700,
    );

    let mut evidence = Vec::with_capacity(per_platform.len());
    let mut topic_ids: BTreeSet<Uuid> = BTreeSet::new();
    for item in per_platform.values() {
        let document = registry
            .get_document(item.document_id)?
            .with_context(|| format!("event evidence document {} missing", item.document_id))?;
        topic_ids.extend(document.topic_ids.iter().copied());
        evidence.push(KnowledgeEvidenceRef {
            document_id: document.document_id,
            canonical_url: document.canonical_url.clone(),
            content_hash: document.cleaned_content_hash.clone(),
            excerpt: Some(bounded(
                item.summary.as_deref().unwrap_or(item.title.as_str()),
                280,
            )),
            relationship: EvidenceRelationship::Supports,
            observed_at: item.last_observed_at,
        });
    }

    if let Some(latest) = &latest {
        let latest_documents: BTreeSet<Uuid> = latest
            .evidence
            .iter()
            .map(|entry| entry.document_id)
            .collect();
        let next_documents: BTreeSet<Uuid> =
            evidence.iter().map(|entry| entry.document_id).collect();
        if latest.summary == summary && latest_documents == next_documents {
            if event.card_id != Some(card_id) {
                let mut event = event.clone();
                event.card_id = Some(card_id);
                write_event_row(&registry.lock_conn(), &event)?;
            }
            return Ok(());
        }
    }

    let distinct_hosts = evidence
        .iter()
        .filter_map(|entry| {
            Url::parse(&entry.canonical_url)
                .ok()
                .and_then(|url| url.host_str().map(str::to_owned))
        })
        .collect::<BTreeSet<_>>()
        .len();
    let status = if distinct_hosts >= 2 {
        KnowledgeStatus::Corroborated
    } else {
        KnowledgeStatus::Unverified
    };
    let entities = extract_features(&event.title)
        .into_iter()
        .take(5)
        .collect::<Vec<_>>();
    let claim = KnowledgeClaim {
        claim_id: stable_uuid(
            format!("knowledge-event-claim:{}:{summary}", event.event_id).as_bytes(),
        ),
        subject: event.title.clone(),
        predicate: "trending_on".into(),
        object: event.platforms.join("/"),
        valid_from: Some(event.first_seen_at),
        valid_until: None,
        confidence: 0.7,
    };
    let card = KnowledgeCard {
        schema_version: SCHEMA_VERSION.into(),
        card_id,
        revision: latest.as_ref().map_or(1, |card| card.revision + 1),
        topic_ids: topic_ids.into_iter().take(4).collect(),
        title: event.title.clone(),
        summary,
        entities,
        claims: vec![claim],
        evidence,
        status,
        published_at: None,
        observed_at: now,
        valid_until: None,
        supersedes: latest.as_ref().map(|card| card.card_id),
        model_id: "deterministic-events-v1".into(),
        prompt_hash: format!("{:x}", Sha256::digest(b"deterministic-events-v1")),
        scores: KnowledgeScores {
            relevance: 0.8,
            novelty: if latest.is_some() { 0.4 } else { 0.8 },
            source_reliability: 0.7,
            extraction_completeness: 1.0,
            confidence: 0.7,
            risk: 0.2,
            cost: 0.0,
        },
        training_eligible: false,
        created_at: now,
    };
    registry.save_knowledge_card(&card)?;
    let mut event = event.clone();
    event.card_id = Some(card_id);
    write_event_row(&registry.lock_conn(), &event)
}

impl Registry {
    /// List events newest-first. Stored status is refreshed in-memory against
    /// `now` (never written back) before status/platform filters apply.
    pub fn list_events(
        &self,
        status: Option<EventStatus>,
        platform: Option<&str>,
        limit: usize,
    ) -> Result<Vec<TrackedEvent>> {
        let limit = limit.clamp(1, 500);
        let fetch = (limit * 4).min(2000);
        let rows: Vec<String> = {
            let conn = self.lock_conn();
            let mut statement = conn.prepare(
                "SELECT event_json FROM tracked_events ORDER BY last_seen_at DESC LIMIT ?1",
            )?;
            statement
                .query_map(params![fetch as i64], |row| row.get::<_, String>(0))?
                .collect::<rusqlite::Result<Vec<_>>>()?
        };
        let now = Utc::now();
        let mut events = Vec::new();
        for json in rows {
            let mut event: TrackedEvent = serde_json::from_str(&json)?;
            event.status = current_status(event.first_seen_at, event.last_seen_at, now);
            if status.is_some_and(|want| event.status != want) {
                continue;
            }
            if platform.is_some_and(|want| !event.platforms.iter().any(|have| have == want)) {
                continue;
            }
            events.push(event);
            if events.len() >= limit {
                break;
            }
        }
        Ok(events)
    }

    pub fn get_event(&self, event_id: Uuid) -> Result<Option<TrackedEvent>> {
        let Some(mut event) = read_event(&self.lock_conn(), event_id)? else {
            return Ok(None);
        };
        event.status = current_status(event.first_seen_at, event.last_seen_at, Utc::now());
        Ok(Some(event))
    }

    pub fn list_event_items(&self, event_id: Uuid) -> Result<Vec<EventItem>> {
        let mut items = event_items(&self.lock_conn(), event_id)?;
        items.sort_by(|left, right| {
            right
                .heat
                .cmp(&left.heat)
                .then_with(|| left.platform.cmp(&right.platform))
                .then_with(|| left.external_id.cmp(&right.external_id))
        });
        Ok(items)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cerebellum_core::{
        AcquisitionMethod, CreateSourcePolicyRequest, DataClassification, DocumentRights,
        ExternalProcessingPermission, SourceAccessMode, SourceKind,
    };
    use serde_json::json;
    use tempfile::tempdir;

    fn at(iso: &str) -> DateTime<Utc> {
        DateTime::parse_from_rfc3339(iso)
            .unwrap()
            .with_timezone(&Utc)
    }

    fn seed_policy(registry: &Registry) -> Uuid {
        registry
            .create_source_policy(&CreateSourcePolicyRequest {
                name: "微博热榜".into(),
                kind: SourceKind::Weibo,
                base_url: "https://weibo.com/ajax/side/hotSearch".into(),
                access_mode: SourceAccessMode::Public,
                allowed_domains: vec!["weibo.com".into()],
                obey_robots: true,
                max_depth: 1,
                max_pages_per_run: 50,
                rate_limit_per_minute: 10,
                raw_retention_days: 30,
                training_license: Some("CC0-1.0".into()),
                model_terms_allow_training: true,
                auth_secret_ref: None,
                enabled: true,
                data_classification: DataClassification::Public,
                external_processing: ExternalProcessingPermission::Redacted,
            })
            .unwrap()
            .policy_id
    }

    fn board_item(platform: &str, external_id: &str, title: &str, heat: i64, rank: i64) -> Value {
        json!({
            "platform": platform,
            "external_id": external_id,
            "title": title,
            "url": format!("https://{platform}.example.com/t/{external_id}"),
            "author": null,
            "published_at": null,
            "summary": null,
            "heat": heat,
            "rank": rank,
        })
    }

    fn board_document(
        policy_id: Uuid,
        topic: Uuid,
        host: &str,
        slug: &str,
        title: &str,
        items: Vec<Value>,
        now: DateTime<Utc>,
    ) -> (DocumentEnvelope, Vec<u8>) {
        let cleaned = format!("board-content-{slug}").into_bytes();
        let document = DocumentEnvelope {
            schema_version: SCHEMA_VERSION.into(),
            document_id: Uuid::new_v4(),
            topic_ids: vec![topic],
            source_policy_id: policy_id,
            external_id: None,
            url: format!("https://{host}/hot/{slug}"),
            canonical_url: format!("https://{host}/hot/{slug}"),
            author: None,
            title: title.into(),
            published_at: None,
            observed_at: now,
            fetched_at: now,
            raw_content_hash: None,
            cleaned_content_hash: format!("{:x}", Sha256::digest(&cleaned)),
            extraction_method: AcquisitionMethod::Api,
            extractor_version: "social-board/0.1".into(),
            language: "zh".into(),
            content_type: "application/json".into(),
            rights: DocumentRights {
                license: Some("CC0-1.0".into()),
                retrieval_allowed: true,
                storage_allowed: true,
                redistribution_allowed: true,
                explicit_training_permission: true,
                model_terms_allow_training: true,
                training_eligible: true,
                rights_source: "fixture".into(),
            },
            prompt_injection_detected: false,
            pii_detected: false,
            secret_detected: false,
            raw_expires_at: now + Duration::days(30),
            tombstoned: false,
            metadata: json!({"items": items}),
        };
        (document, cleaned)
    }

    fn event_of_item(registry: &Registry, platform: &str, external_id: &str) -> Uuid {
        let conn = registry.lock_conn();
        conn.query_row(
            "SELECT event_id FROM event_items WHERE platform=?1 AND external_id=?2",
            params![platform, external_id],
            |row| row.get::<_, String>(0),
        )
        .map(|raw| Uuid::parse_str(&raw).unwrap())
        .unwrap()
    }

    // Parity with worker test_cluster.py::test_cross_platform_event_gets_cluster_id.
    #[test]
    fn cross_platform_items_thread_into_one_event() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = seed_policy(&registry);
        let topic = Uuid::new_v4();
        let now = at("2026-08-29T08:00:00Z");
        let (weibo_doc, weibo_bytes) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![
                board_item("weibo", "wb-1", "某新模型正式发布引发热议", 5000, 1),
                board_item("weibo", "wb-2", "完全无关的另一条新闻", 100, 2),
            ],
            now,
        );
        registry
            .save_document(&weibo_doc, &weibo_bytes, None)
            .unwrap();
        let (zhihu_doc, zhihu_bytes) = board_document(
            policy,
            topic,
            "api.zhihu.com",
            "zhihu-2026-08-29",
            "知乎热榜 2026-08-29",
            vec![board_item(
                "zhihu",
                "zh-1",
                "如何看待某新模型正式发布",
                3000,
                1,
            )],
            now,
        );
        registry
            .save_document(&zhihu_doc, &zhihu_bytes, None)
            .unwrap();

        let shared = event_of_item(&registry, "weibo", "wb-1");
        assert_eq!(shared, event_of_item(&registry, "zhihu", "zh-1"));
        let unrelated = event_of_item(&registry, "weibo", "wb-2");
        assert_ne!(shared, unrelated);

        let event = registry.get_event(shared).unwrap().unwrap();
        assert_eq!(
            event.platforms,
            vec!["weibo".to_string(), "zhihu".to_string()]
        );
        assert_eq!(event.item_count, 2);
        assert_eq!(event.peak_heat, 5000);
        assert_eq!(event.title, "某新模型正式发布引发热议");
        assert!(event.card_id.is_some());
        let unrelated_event = registry.get_event(unrelated).unwrap().unwrap();
        assert_eq!(unrelated_event.platforms, vec!["weibo".to_string()]);
        assert!(unrelated_event.card_id.is_none());
    }

    // Parity with worker test_cluster.py::test_single_platform_batch_never_clusters:
    // similar items on one platform share an event, but no cross-platform
    // marker (here: no synthesized card) is produced.
    #[test]
    fn single_platform_items_merge_without_card() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = seed_policy(&registry);
        let topic = Uuid::new_v4();
        let now = at("2026-08-29T08:00:00Z");
        let (doc, bytes) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![
                board_item("weibo", "wb-1", "某新模型正式发布引发热议", 5000, 1),
                board_item("weibo", "wb-2", "如何看待某新模型正式发布", 3000, 2),
            ],
            now,
        );
        registry.save_document(&doc, &bytes, None).unwrap();

        let event_id = event_of_item(&registry, "weibo", "wb-1");
        assert_eq!(event_id, event_of_item(&registry, "weibo", "wb-2"));
        let event = registry.get_event(event_id).unwrap().unwrap();
        assert_eq!(event.platforms, vec!["weibo".to_string()]);
        assert_eq!(event.item_count, 2);
        assert!(event.card_id.is_none());
        assert!(
            registry
                .get_knowledge_card(stable_event_card_id(event_id))
                .unwrap()
                .is_none()
        );
    }

    // Parity with worker test_cluster.py::test_cluster_events_core_algorithm
    // (containment: short title ⊂ long title).
    #[test]
    fn core_algorithm_parity_containment_merge() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = seed_policy(&registry);
        let topic = Uuid::new_v4();
        let now = at("2026-08-29T08:00:00Z");
        let (weibo_doc, weibo_bytes) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![board_item("weibo", "wb-1", "某品牌新机发布会", 10000, 1)],
            now,
        );
        registry
            .save_document(&weibo_doc, &weibo_bytes, None)
            .unwrap();
        let (douyin_doc, douyin_bytes) = board_document(
            policy,
            topic,
            "www.douyin.com",
            "douyin-2026-08-29",
            "抖音热榜 2026-08-29",
            vec![board_item(
                "douyin",
                "dy-1",
                "某品牌新机发布会直播",
                5000,
                1,
            )],
            now,
        );
        registry
            .save_document(&douyin_doc, &douyin_bytes, None)
            .unwrap();

        let event_id = event_of_item(&registry, "weibo", "wb-1");
        assert_eq!(event_id, event_of_item(&registry, "douyin", "dy-1"));
        let event = registry.get_event(event_id).unwrap().unwrap();
        assert_eq!(
            event.platforms,
            vec!["douyin".to_string(), "weibo".to_string()]
        );
    }

    // Same (platform, external_id) re-ingested on day 1 and day 3 stays in the
    // same event, accumulates daily observations, and moves Emerging → Peak.
    #[test]
    fn cross_day_reobservation_threads_same_event() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = Uuid::new_v4();
        let topic = Uuid::new_v4();
        let day1 = at("2026-08-27T08:00:00Z");
        let day3 = at("2026-08-29T08:00:00Z");
        let (doc1, _) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-27",
            "微博实时热搜榜 2026-08-27",
            vec![board_item(
                "weibo",
                "wb-1",
                "某新模型正式发布引发热议",
                5000,
                1,
            )],
            day1,
        );
        assert_eq!(ingest_board_document_at(&registry, &doc1, day1).unwrap(), 1);
        let event_id = event_of_item(&registry, "weibo", "wb-1");
        let event = read_event(&registry.lock_conn(), event_id)
            .unwrap()
            .unwrap();
        assert_eq!(event.status, EventStatus::Emerging);

        let (doc3, _) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![board_item(
                "weibo",
                "wb-1",
                "某新模型正式发布引发热议",
                8000,
                2,
            )],
            day3,
        );
        assert_eq!(ingest_board_document_at(&registry, &doc3, day3).unwrap(), 1);
        assert_eq!(event_id, event_of_item(&registry, "weibo", "wb-1"));

        let items = registry.list_event_items(event_id).unwrap();
        assert_eq!(items.len(), 1);
        let item = &items[0];
        assert_eq!(
            item.observations,
            vec![
                ("2026-08-27".to_string(), 5000),
                ("2026-08-29".to_string(), 8000),
            ]
        );
        assert_eq!(item.heat, 8000);
        assert_eq!(item.rank, 1);
        assert_eq!(item.first_observed_at, day1);
        assert_eq!(item.last_observed_at, day3);
        assert_eq!(item.document_id, doc3.document_id);

        let event = read_event(&registry.lock_conn(), event_id)
            .unwrap()
            .unwrap();
        assert_eq!(event.status, EventStatus::Peak);
        assert_eq!(event.first_seen_at, day1);
        assert_eq!(event.last_seen_at, day3);
        assert_eq!(event.peak_heat, 8000);
    }

    // Two boards carrying the same event on different platforms synthesize one
    // deterministic corroborated card; re-ingesting identical content mints no
    // new revision.
    #[test]
    fn multi_platform_event_synthesizes_corroborated_card() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = seed_policy(&registry);
        let topic = Uuid::new_v4();
        let now = at("2026-08-29T08:00:00Z");
        let (weibo_doc, weibo_bytes) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![board_item(
                "weibo",
                "wb-1",
                "某新模型正式发布引发热议",
                5000,
                1,
            )],
            now,
        );
        registry
            .save_document(&weibo_doc, &weibo_bytes, None)
            .unwrap();
        let (zhihu_doc, zhihu_bytes) = board_document(
            policy,
            topic,
            "api.zhihu.com",
            "zhihu-2026-08-29",
            "知乎热榜 2026-08-29",
            vec![board_item(
                "zhihu",
                "zh-1",
                "如何看待某新模型正式发布",
                3000,
                1,
            )],
            now,
        );
        registry
            .save_document(&zhihu_doc, &zhihu_bytes, None)
            .unwrap();

        let event_id = event_of_item(&registry, "weibo", "wb-1");
        let event = registry.get_event(event_id).unwrap().unwrap();
        let card_id = stable_event_card_id(event_id);
        assert_eq!(event.card_id, Some(card_id));
        let card = registry.get_knowledge_card(card_id).unwrap().unwrap();
        assert_eq!(card.revision, 1);
        assert_eq!(card.status, KnowledgeStatus::Corroborated);
        assert!(!card.training_eligible);
        assert_eq!(card.model_id, "deterministic-events-v1");
        assert_eq!(card.claims.len(), 1);
        assert_eq!(card.claims[0].predicate, "trending_on");
        assert_eq!(card.claims[0].object, "weibo/zhihu");
        let evidence_docs: BTreeSet<Uuid> = card
            .evidence
            .iter()
            .map(|entry| entry.document_id)
            .collect();
        assert_eq!(
            evidence_docs,
            BTreeSet::from([weibo_doc.document_id, zhihu_doc.document_id])
        );
        assert!(
            card.evidence
                .iter()
                .all(|entry| entry.relationship == EvidenceRelationship::Supports)
        );

        // Idempotent: identical re-ingest must not mint a new revision.
        ingest_board_document_at(&registry, &weibo_doc, now).unwrap();
        ingest_board_document_at(&registry, &zhihu_doc, now).unwrap();
        assert_eq!(
            registry.get_knowledge_card_history(card_id).unwrap().len(),
            1
        );
    }

    // The rare-term path: similarity below the 0.35 direct threshold but a
    // shared low-frequency term plus the 0.15/0.10 floors still attaches.
    #[test]
    fn rare_term_path_attaches_low_similarity_item() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = seed_policy(&registry);
        let topic = Uuid::new_v4();
        let now = at("2026-08-29T08:00:00Z");
        let (weibo_doc, weibo_bytes) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![
                board_item("weibo", "wb-1", "耐克发布新款跑鞋", 5000, 1),
                board_item("weibo", "wb-2", "另一场足球比赛结束", 400, 2),
                board_item("weibo", "wb-3", "某地举办户外音乐会", 300, 3),
                board_item("weibo", "wb-4", "科技公司公布季度业绩", 200, 4),
            ],
            now,
        );
        registry
            .save_document(&weibo_doc, &weibo_bytes, None)
            .unwrap();
        let (zhihu_doc, zhihu_bytes) = board_document(
            policy,
            topic,
            "api.zhihu.com",
            "zhihu-2026-08-29",
            "知乎热榜 2026-08-29",
            vec![board_item("zhihu", "zh-1", "耐克股价大涨", 3000, 1)],
            now,
        );
        registry
            .save_document(&zhihu_doc, &zhihu_bytes, None)
            .unwrap();

        let event_id = event_of_item(&registry, "weibo", "wb-1");
        assert_eq!(event_id, event_of_item(&registry, "zhihu", "zh-1"));
        for unrelated in ["wb-2", "wb-3", "wb-4"] {
            assert_ne!(event_id, event_of_item(&registry, "weibo", unrelated));
        }
        let event = registry.get_event(event_id).unwrap().unwrap();
        assert_eq!(
            event.platforms,
            vec!["weibo".to_string(), "zhihu".to_string()]
        );
        let card = registry
            .get_knowledge_card(stable_event_card_id(event_id))
            .unwrap()
            .unwrap();
        assert_eq!(card.status, KnowledgeStatus::Corroborated);
    }

    #[test]
    fn current_status_transitions() {
        let t0 = at("2026-08-27T08:00:00Z");
        assert_eq!(current_status(t0, t0, t0), EventStatus::Emerging);
        assert_eq!(
            current_status(t0, t0, t0 + Duration::hours(12)),
            EventStatus::Emerging
        );
        assert_eq!(
            current_status(t0, t0 + Duration::hours(2), t0 + Duration::hours(25)),
            EventStatus::Peak
        );
        assert_eq!(
            current_status(t0, t0, t0 + Duration::hours(25)),
            EventStatus::Fading
        );
        assert_eq!(
            current_status(t0, t0, t0 + Duration::hours(73)),
            EventStatus::Resolved
        );
    }

    // The save_document hook threads board items; documents without items are
    // a no-op and still save normally.
    #[test]
    fn save_document_hook_ingests_board_items() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = seed_policy(&registry);
        let topic = Uuid::new_v4();
        let now = at("2026-08-29T08:00:00Z");
        let (doc, bytes) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![board_item(
                "weibo",
                "wb-1",
                "某新模型正式发布引发热议",
                5000,
                1,
            )],
            now,
        );
        registry.save_document(&doc, &bytes, None).unwrap();
        assert_eq!(registry.list_events(None, None, 100).unwrap().len(), 1);

        let mut plain = doc.clone();
        plain.document_id = Uuid::new_v4();
        plain.url = "https://weibo.com/detail/1".into();
        plain.canonical_url = plain.url.clone();
        plain.cleaned_content_hash = format!("{:x}", Sha256::digest(b"plain-detail"));
        plain.metadata = json!({"source_kind": "web"});
        registry
            .save_document(&plain, b"plain-detail", None)
            .unwrap();
        assert_eq!(registry.list_events(None, None, 100).unwrap().len(), 1);
        assert!(registry.get_document(plain.document_id).unwrap().is_some());
    }

    // A synthesized event card enters the automatic quality loop: the backfill
    // enqueues a quality_assess_v1 learning job for it.
    #[test]
    fn event_card_is_picked_up_by_quality_backfill() {
        let dir = tempdir().unwrap();
        let registry = Registry::open(dir.path()).unwrap();
        let policy = seed_policy(&registry);
        let topic = Uuid::new_v4();
        let now = at("2026-08-29T08:00:00Z");
        let (weibo_doc, weibo_bytes) = board_document(
            policy,
            topic,
            "weibo.com",
            "weibo-2026-08-29",
            "微博实时热搜榜 2026-08-29",
            vec![board_item(
                "weibo",
                "wb-1",
                "某新模型正式发布引发热议",
                5000,
                1,
            )],
            now,
        );
        registry
            .save_document(&weibo_doc, &weibo_bytes, None)
            .unwrap();
        let (zhihu_doc, zhihu_bytes) = board_document(
            policy,
            topic,
            "api.zhihu.com",
            "zhihu-2026-08-29",
            "知乎热榜 2026-08-29",
            vec![board_item(
                "zhihu",
                "zh-1",
                "如何看待某新模型正式发布",
                3000,
                1,
            )],
            now,
        );
        registry
            .save_document(&zhihu_doc, &zhihu_bytes, None)
            .unwrap();

        let event_id = event_of_item(&registry, "weibo", "wb-1");
        let card_id = stable_event_card_id(event_id);
        let scheduled = registry.enqueue_quality_backfill(100).unwrap();
        assert!(scheduled >= 1);
        let conn = registry.lock_conn();
        let jobs: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM learning_jobs
                 WHERE kind='quality_assess_v1' AND payload_json LIKE ?1",
                params![format!("%{card_id}%")],
                |row| row.get(0),
            )
            .unwrap();
        assert!(jobs >= 1);
    }
}
