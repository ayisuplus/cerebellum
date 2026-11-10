use anyhow::{Context, Result, bail};
use cerebellum_core::{
    AcquisitionMethod, AcquisitionOutcome, SourceAccessMode, SourceKind, SourcePolicy,
};
use chrono::{DateTime, Utc};
use regex::Regex;
use reqwest::header::{
    ACCEPT, AUTHORIZATION, ETAG, HeaderMap, HeaderValue, IF_MODIFIED_SINCE, IF_NONE_MATCH,
    LAST_MODIFIED, LOCATION, USER_AGENT,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::net::SocketAddr;
use std::time::Duration;
use tokio::net::lookup_host;
use url::Url;

pub const MAX_DOCUMENT_BYTES: u64 = 10 * 1024 * 1024;
const MAX_REDIRECTS: usize = 5;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DiscoveryItem {
    pub external_id: Option<String>,
    pub title: String,
    pub url: String,
    pub author: Option<String>,
    pub published_at: Option<DateTime<Utc>>,
    pub summary: Option<String>,
    pub language: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ConditionalHeaders {
    pub etag: Option<String>,
    pub last_modified: Option<String>,
}

#[derive(Debug, Clone)]
pub struct DiscoveryBatch {
    pub items: Vec<DiscoveryItem>,
    pub cursor: Option<String>,
    pub etag: Option<String>,
    pub last_modified: Option<String>,
    pub not_modified: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EscalationDecision {
    Complete,
    Retry,
    Next(AcquisitionMethod),
    Stop,
}

#[derive(Debug, Clone)]
pub enum HttpFetch {
    NotModified {
        final_url: String,
        etag: Option<String>,
        last_modified: Option<String>,
    },
    Content {
        final_url: String,
        status: u16,
        content_type: Option<String>,
        etag: Option<String>,
        last_modified: Option<String>,
        body: Vec<u8>,
    },
    Failed {
        final_url: String,
        status: Option<u16>,
        outcome: AcquisitionOutcome,
        retry_after_seconds: Option<u64>,
    },
}

pub fn escalation_decision(
    method: AcquisitionMethod,
    outcome: AcquisitionOutcome,
    access_mode: SourceAccessMode,
) -> EscalationDecision {
    if outcome == AcquisitionOutcome::Success {
        return EscalationDecision::Complete;
    }
    if outcome.is_retryable() {
        return EscalationDecision::Retry;
    }
    if outcome.is_terminal_policy_failure() {
        return EscalationDecision::Stop;
    }
    if outcome == AcquisitionOutcome::AuthRequired {
        return if access_mode == SourceAccessMode::AuthenticatedLocal {
            EscalationDecision::Next(AcquisitionMethod::OpenCli)
        } else {
            EscalationDecision::Stop
        };
    }
    if !outcome.may_escalate_extractor() {
        return EscalationDecision::Stop;
    }
    let next = match method {
        AcquisitionMethod::Api | AcquisitionMethod::Rss | AcquisitionMethod::DirectHttp => {
            AcquisitionMethod::Crawl4ai
        }
        AcquisitionMethod::Crawl4ai => AcquisitionMethod::Firecrawl,
        AcquisitionMethod::Firecrawl => AcquisitionMethod::LinkMapper,
        AcquisitionMethod::LinkMapper => AcquisitionMethod::Scrapling,
        AcquisitionMethod::Scrapling => AcquisitionMethod::Mediacrawler,
        AcquisitionMethod::Mediacrawler if access_mode == SourceAccessMode::AuthenticatedLocal => {
            AcquisitionMethod::OpenCli
        }
        AcquisitionMethod::Mediacrawler | AcquisitionMethod::OpenCli => {
            return EscalationDecision::Stop;
        }
    };
    EscalationDecision::Next(next)
}

pub fn classify_http_status(status: u16) -> AcquisitionOutcome {
    match status {
        200..=299 => AcquisitionOutcome::Success,
        401 | 403 => AcquisitionOutcome::AuthRequired,
        404 => AcquisitionOutcome::NotFound,
        410 => AcquisitionOutcome::Gone,
        429 => AcquisitionOutcome::RateLimited,
        500..=599 => AcquisitionOutcome::ServerError,
        _ => AcquisitionOutcome::PolicyDenied,
    }
}

pub fn topic_matches(item: &DiscoveryItem, query: &str, keywords: &[String]) -> bool {
    let haystack = format!(
        "{} {}",
        item.title,
        item.summary.as_deref().unwrap_or_default()
    )
    .to_lowercase();
    let terms = query
        .split_whitespace()
        .chain(keywords.iter().map(String::as_str))
        .map(str::trim)
        .filter(|term| term.len() >= 2)
        .map(str::to_lowercase)
        .collect::<Vec<_>>();
    terms.is_empty() || terms.iter().any(|term| haystack.contains(term))
}

pub fn parse_hn_updates(value: &Value) -> Result<Vec<u64>> {
    let mut ids = value
        .get("items")
        .and_then(Value::as_array)
        .context("HN updates response lacks items")?
        .iter()
        .filter_map(Value::as_u64)
        .collect::<Vec<_>>();
    ids.sort_unstable();
    ids.dedup();
    Ok(ids)
}

pub fn parse_hn_item(value: &Value) -> Result<Option<DiscoveryItem>> {
    if value.get("deleted").and_then(Value::as_bool) == Some(true)
        || value.get("dead").and_then(Value::as_bool) == Some(true)
        || value.get("type").and_then(Value::as_str) != Some("story")
    {
        return Ok(None);
    }
    let id = value
        .get("id")
        .and_then(Value::as_u64)
        .context("HN item lacks id")?;
    let title = value
        .get("title")
        .and_then(Value::as_str)
        .unwrap_or("Untitled HN story")
        .trim()
        .to_owned();
    let url = value
        .get("url")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .unwrap_or_else(|| format!("https://news.ycombinator.com/item?id={id}"));
    let published_at = value
        .get("time")
        .and_then(Value::as_i64)
        .and_then(|timestamp| DateTime::from_timestamp(timestamp, 0));
    Ok(Some(DiscoveryItem {
        external_id: Some(id.to_string()),
        title,
        url,
        author: value.get("by").and_then(Value::as_str).map(str::to_owned),
        published_at,
        summary: value.get("text").and_then(Value::as_str).map(strip_markup),
        language: Some("en".into()),
    }))
}

pub fn parse_rss_or_atom(xml: &str, feed_url: &str) -> Result<Vec<DiscoveryItem>> {
    if xml.len() as u64 > MAX_DOCUMENT_BYTES {
        bail!("feed exceeds maximum size");
    }
    let feed_base = Url::parse(feed_url).context("invalid feed URL")?;
    let item_pattern = Regex::new(r"(?is)<item(?:\s[^>]*)?>(.*?)</item>")?;
    let entry_pattern = Regex::new(r"(?is)<entry(?:\s[^>]*)?>(.*?)</entry>")?;
    let blocks = item_pattern
        .captures_iter(xml)
        .filter_map(|capture| capture.get(1).map(|value| value.as_str().to_owned()))
        .chain(
            entry_pattern
                .captures_iter(xml)
                .filter_map(|capture| capture.get(1).map(|value| value.as_str().to_owned())),
        )
        .take(1_000)
        .collect::<Vec<_>>();
    let mut items = Vec::new();
    for block in blocks {
        let title = extract_tag(&block, "title")
            .map(|value| strip_markup(&value))
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "Untitled feed entry".into());
        let raw_url = extract_atom_link(&block)
            .or_else(|| extract_tag(&block, "link"))
            .map(|value| strip_markup(&value));
        let Some(raw_url) = raw_url else { continue };
        let url = feed_base
            .join(raw_url.trim())
            .context("feed entry has invalid URL")?
            .to_string();
        let external_id = extract_tag(&block, "guid")
            .or_else(|| extract_tag(&block, "id"))
            .map(|value| strip_markup(&value));
        let author = extract_tag(&block, "author")
            .or_else(|| extract_tag(&block, "dc:creator"))
            .map(|value| strip_markup(&value));
        let summary = extract_tag(&block, "description")
            .or_else(|| extract_tag(&block, "summary"))
            .or_else(|| extract_tag(&block, "content"))
            .map(|value| strip_markup(&value));
        let published_at = extract_tag(&block, "pubDate")
            .or_else(|| extract_tag(&block, "published"))
            .or_else(|| extract_tag(&block, "updated"))
            .and_then(|value| parse_feed_time(&strip_markup(&value)));
        items.push(DiscoveryItem {
            external_id,
            title,
            url,
            author,
            published_at,
            summary,
            language: None,
        });
    }
    Ok(items)
}

pub async fn fetch_public_url(
    input: &str,
    allowed_domains: &[String],
    conditional: &ConditionalHeaders,
    bearer_token: Option<&str>,
) -> Result<HttpFetch> {
    let mut current = crate::text::canonicalize_public_url(input, allowed_domains)?;
    let original_host = Url::parse(&current)?
        .host_str()
        .context("URL lacks host")?
        .to_owned();
    for redirect_count in 0..=MAX_REDIRECTS {
        let url = Url::parse(&current)?;
        let host = url.host_str().context("URL lacks host")?.to_owned();
        let addresses = resolve_public_addresses(&url).await?;
        let pinned = *addresses.first().context("host resolved to no addresses")?;
        let client = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .connect_timeout(Duration::from_secs(10))
            .timeout(Duration::from_secs(30))
            .no_proxy()
            .resolve(&host, pinned)
            .build()?;
        let mut headers = HeaderMap::new();
        headers.insert(
            USER_AGENT,
            HeaderValue::from_static("cerebellum-acquisition/0.1"),
        );
        headers.insert(ACCEPT, HeaderValue::from_static("*/*"));
        if redirect_count == 0 {
            if let Some(etag) = &conditional.etag {
                headers.insert(IF_NONE_MATCH, HeaderValue::from_str(etag)?);
            }
            if let Some(last_modified) = &conditional.last_modified {
                headers.insert(IF_MODIFIED_SINCE, HeaderValue::from_str(last_modified)?);
            }
        }
        if host.eq_ignore_ascii_case(&original_host)
            && let Some(token) = bearer_token
        {
            headers.insert(
                AUTHORIZATION,
                HeaderValue::from_str(&format!("Bearer {token}"))?,
            );
        }
        let mut response = client.get(url.clone()).headers(headers).send().await?;
        let status = response.status();
        let etag = header_string(response.headers(), ETAG);
        let last_modified = header_string(response.headers(), LAST_MODIFIED);
        if status.as_u16() == 304 {
            return Ok(HttpFetch::NotModified {
                final_url: current,
                etag,
                last_modified,
            });
        }
        if status.is_redirection() {
            if redirect_count == MAX_REDIRECTS {
                bail!("redirect limit exceeded");
            }
            let location = response
                .headers()
                .get(LOCATION)
                .and_then(|value| value.to_str().ok())
                .context("redirect lacks a valid Location header")?;
            let next = url.join(location).context("invalid redirect target")?;
            current = crate::text::canonicalize_public_url(next.as_str(), allowed_domains)?;
            continue;
        }
        if !status.is_success() {
            return Ok(HttpFetch::Failed {
                final_url: current,
                status: Some(status.as_u16()),
                outcome: classify_http_status(status.as_u16()),
                retry_after_seconds: response
                    .headers()
                    .get("retry-after")
                    .and_then(|value| value.to_str().ok())
                    .and_then(|value| value.parse().ok()),
            });
        }
        if response
            .content_length()
            .is_some_and(|length| length > MAX_DOCUMENT_BYTES)
        {
            bail!("response exceeds maximum document size");
        }
        let content_type = response
            .headers()
            .get("content-type")
            .and_then(|value| value.to_str().ok())
            .map(str::to_owned);
        let mut body = Vec::new();
        while let Some(chunk) = response.chunk().await? {
            if body.len() as u64 + chunk.len() as u64 > MAX_DOCUMENT_BYTES {
                bail!("streamed response exceeds maximum document size");
            }
            body.extend_from_slice(&chunk);
        }
        return Ok(HttpFetch::Content {
            final_url: current,
            status: status.as_u16(),
            content_type,
            etag,
            last_modified,
            body,
        });
    }
    unreachable!("redirect loop returns or fails")
}

#[cfg(test)]
static TEST_PINNED_ADDRESS: std::sync::Mutex<Option<SocketAddr>> = std::sync::Mutex::new(None);

/// Hermetic test seam: when set, every host "resolves" to this loopback
/// address so mock-HTTP tests never touch real DNS or the network. The
/// public-IP SSRF checks above stay in force for production paths.
#[cfg(test)]
fn test_pinned_address() -> Option<SocketAddr> {
    *TEST_PINNED_ADDRESS.lock().unwrap()
}

async fn resolve_public_addresses(url: &Url) -> Result<Vec<SocketAddr>> {
    #[cfg(test)]
    if let Some(pinned) = test_pinned_address() {
        return Ok(vec![pinned]);
    }
    let host = url.host_str().context("URL lacks host")?;
    let port = url
        .port_or_known_default()
        .context("URL lacks a known port")?;
    let addresses = lookup_host((host, port))
        .await
        .with_context(|| format!("resolve host {host}"))?
        .collect::<Vec<_>>();
    if addresses.is_empty()
        || addresses
            .iter()
            .any(|address| !crate::text::is_global_ip(address.ip()))
    {
        bail!("URL resolves to a non-public address");
    }
    Ok(addresses)
}

fn header_string(headers: &HeaderMap, name: reqwest::header::HeaderName) -> Option<String> {
    headers
        .get(name)
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned)
}

fn extract_tag(block: &str, tag: &str) -> Option<String> {
    let pattern = Regex::new(&format!(
        r"(?is)<{}(?:\s[^>]*)?>(.*?)</{}>",
        regex::escape(tag),
        regex::escape(tag)
    ))
    .ok()?;
    pattern
        .captures(block)
        .and_then(|capture| capture.get(1))
        .map(|value| value.as_str().to_owned())
}

fn extract_atom_link(block: &str) -> Option<String> {
    let pattern = Regex::new(r#"(?is)<link\b[^>]*\bhref\s*=\s*["']([^"']+)["'][^>]*/?>"#).ok()?;
    pattern
        .captures(block)
        .and_then(|capture| capture.get(1))
        .map(|value| decode_xml_entities(value.as_str()))
}

fn strip_markup(value: &str) -> String {
    let value = value
        .trim()
        .strip_prefix("<![CDATA[")
        .and_then(|value| value.strip_suffix("]]>"))
        .unwrap_or(value);
    let without_tags = Regex::new(r"(?is)<[^>]+>")
        .expect("static markup regex")
        .replace_all(value, " ");
    decode_xml_entities(&without_tags)
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn decode_xml_entities(value: &str) -> String {
    value
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&#39;", "'")
        .replace("&amp;", "&")
}

fn parse_feed_time(value: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(value)
        .or_else(|_| DateTime::parse_from_rfc2822(value))
        .ok()
        .map(|value| value.with_timezone(&Utc))
}

pub async fn discover_source(
    policy: &SourcePolicy,
    cursor: Option<&str>,
    conditional: &ConditionalHeaders,
    github_token: Option<&str>,
) -> Result<DiscoveryBatch> {
    if !policy.enabled {
        bail!("source policy is disabled");
    }
    let mut allowed_domains = policy.allowed_domains.clone();
    if let Some(host) = Url::parse(&policy.base_url)
        .ok()
        .and_then(|url| url.host_str().map(str::to_owned))
        && !allowed_domains.iter().any(|item| item == &host)
    {
        allowed_domains.push(host);
    }
    match policy.kind {
        SourceKind::RssAtom => {
            let fetched =
                fetch_public_url(&policy.base_url, &allowed_domains, conditional, None).await?;
            match fetched {
                HttpFetch::NotModified {
                    etag,
                    last_modified,
                    ..
                } => Ok(DiscoveryBatch {
                    items: vec![],
                    cursor: cursor.map(str::to_owned),
                    etag,
                    last_modified,
                    not_modified: true,
                }),
                HttpFetch::Content {
                    final_url,
                    body,
                    etag,
                    last_modified,
                    ..
                } => {
                    let text = String::from_utf8(body).context("RSS/Atom feed is not UTF-8")?;
                    let mut items = parse_rss_or_atom(&text, &final_url)?;
                    items.truncate(policy.max_pages_per_run as usize);
                    Ok(DiscoveryBatch {
                        cursor: items
                            .first()
                            .and_then(|item| item.external_id.clone())
                            .or_else(|| cursor.map(str::to_owned)),
                        items,
                        etag,
                        last_modified,
                        not_modified: false,
                    })
                }
                HttpFetch::Failed {
                    outcome, status, ..
                } => bail!("RSS fetch failed with {outcome:?} ({status:?})"),
            }
        }
        SourceKind::HackerNews => {
            let updates_url = join_endpoint(&policy.base_url, "v0/updates.json")?;
            let updates = fetch_public_url(
                &updates_url,
                &allowed_domains,
                &ConditionalHeaders::default(),
                None,
            )
            .await?;
            let body = content_body(updates, "HN updates")?;
            let value: Value = serde_json::from_slice(&body)?;
            let last_id = cursor.and_then(|value| value.parse::<u64>().ok());
            let mut ids = parse_hn_updates(&value)?
                .into_iter()
                .filter(|id| last_id.is_none_or(|last| *id > last))
                .collect::<Vec<_>>();
            ids.sort_unstable_by(|left, right| right.cmp(left));
            ids.truncate(
                policy
                    .max_pages_per_run
                    .min(policy.rate_limit_per_minute.saturating_sub(1)) as usize,
            );
            let newest = ids.iter().copied().max().or(last_id);
            let mut items = Vec::new();
            for id in ids {
                let item_url = join_endpoint(&policy.base_url, &format!("v0/item/{id}.json"))?;
                let fetched = fetch_public_url(
                    &item_url,
                    &allowed_domains,
                    &ConditionalHeaders::default(),
                    None,
                )
                .await?;
                let body = content_body(fetched, "HN item")?;
                if let Some(mut item) = parse_hn_item(&serde_json::from_slice(&body)?)? {
                    item.url = crate::text::canonicalize_public_url(&item.url, &[])?;
                    items.push(item);
                }
            }
            Ok(DiscoveryBatch {
                items,
                cursor: newest.map(|value| value.to_string()),
                etag: None,
                last_modified: None,
                not_modified: false,
            })
        }
        SourceKind::Github => {
            let events_url = github_events_url(&policy.base_url, policy.max_pages_per_run)?;
            let mut github_domains = allowed_domains;
            if !github_domains.iter().any(|item| item == "api.github.com") {
                github_domains.push("api.github.com".into());
            }
            let fetched =
                fetch_public_url(&events_url, &github_domains, conditional, github_token).await?;
            match fetched {
                HttpFetch::NotModified {
                    etag,
                    last_modified,
                    ..
                } => Ok(DiscoveryBatch {
                    items: vec![],
                    cursor: cursor.map(str::to_owned),
                    etag,
                    last_modified,
                    not_modified: true,
                }),
                HttpFetch::Content {
                    body,
                    etag,
                    last_modified,
                    ..
                } => {
                    let value: Value = serde_json::from_slice(&body)?;
                    let mut items = parse_github_events(&value, cursor)?;
                    items.truncate(policy.max_pages_per_run as usize);
                    Ok(DiscoveryBatch {
                        cursor: items
                            .first()
                            .and_then(|item| item.external_id.clone())
                            .or_else(|| cursor.map(str::to_owned)),
                        items,
                        etag,
                        last_modified,
                        not_modified: false,
                    })
                }
                HttpFetch::Failed {
                    outcome, status, ..
                } => bail!("GitHub fetch failed with {outcome:?} ({status:?})"),
            }
        }
        SourceKind::Http => Ok(DiscoveryBatch {
            items: vec![DiscoveryItem {
                external_id: None,
                title: policy.name.clone(),
                url: crate::text::canonicalize_public_url(&policy.base_url, &allowed_domains)?,
                author: None,
                published_at: None,
                summary: None,
                language: None,
            }],
            cursor: cursor.map(str::to_owned),
            etag: conditional.etag.clone(),
            last_modified: conditional.last_modified.clone(),
            not_modified: false,
        }),
        SourceKind::Tavily
        | SourceKind::Firecrawl
        | SourceKind::Crawl4ai
        | SourceKind::Scrapling
        | SourceKind::OpenCli => {
            bail!(
                "source kind {:?} requires the isolated acquisition worker",
                policy.kind
            )
        }
        SourceKind::Weibo
        | SourceKind::Zhihu
        | SourceKind::Douyin
        | SourceKind::Bilibili
        | SourceKind::Xhs
        | SourceKind::Baidu
        | SourceKind::Kuaishou
        | SourceKind::Tieba
        | SourceKind::OpenAlex
        | SourceKind::Arxiv
        | SourceKind::Journal => {
            bail!(
                "source kind {:?} requires the isolated social acquisition worker",
                policy.kind
            )
        }
    }
}

pub fn parse_github_events(value: &Value, stop_at_id: Option<&str>) -> Result<Vec<DiscoveryItem>> {
    let events = value
        .as_array()
        .context("GitHub events response must be an array")?;
    let mut items = Vec::new();
    for event in events {
        let id = event.get("id").and_then(Value::as_str).unwrap_or_default();
        if stop_at_id.is_some_and(|cursor| cursor == id) {
            break;
        }
        let repository = event
            .pointer("/repo/name")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if id.is_empty() || repository.is_empty() {
            continue;
        }
        let event_type = event
            .get("type")
            .and_then(Value::as_str)
            .unwrap_or("GitHubEvent");
        let head = event.pointer("/payload/head").and_then(Value::as_str);
        let url = head
            .map(|head| format!("https://github.com/{repository}/commit/{head}"))
            .unwrap_or_else(|| format!("https://github.com/{repository}"));
        let summary = event
            .pointer("/payload/commits/0/message")
            .and_then(Value::as_str)
            .or_else(|| event.pointer("/payload/ref").and_then(Value::as_str))
            .map(str::to_owned);
        let published_at = event
            .get("created_at")
            .and_then(Value::as_str)
            .and_then(parse_feed_time);
        items.push(DiscoveryItem {
            external_id: Some(id.to_owned()),
            title: format!("{event_type} in {repository}"),
            url,
            author: event
                .pointer("/actor/login")
                .and_then(Value::as_str)
                .map(str::to_owned),
            published_at,
            summary,
            language: Some("en".into()),
        });
    }
    Ok(items)
}

fn github_events_url(base_url: &str, limit: u32) -> Result<String> {
    let url = Url::parse(base_url).context("invalid GitHub source URL")?;
    if url.host_str() == Some("api.github.com") {
        return Ok(url.to_string());
    }
    if url.host_str() != Some("github.com") {
        bail!("GitHub source must use github.com or api.github.com");
    }
    let segments = url
        .path_segments()
        .context("GitHub URL lacks repository path")?
        .filter(|segment| !segment.is_empty())
        .take(2)
        .collect::<Vec<_>>();
    if segments.len() != 2 {
        bail!("GitHub source must identify owner/repository");
    }
    Ok(format!(
        "https://api.github.com/repos/{}/{}/events?per_page={}",
        segments[0],
        segments[1].trim_end_matches(".git"),
        limit.clamp(1, 100)
    ))
}

fn join_endpoint(base: &str, path: &str) -> Result<String> {
    let mut base = base.trim_end_matches('/').to_owned();
    base.push('/');
    Ok(Url::parse(&base)?.join(path)?.to_string())
}

fn content_body(fetch: HttpFetch, label: &str) -> Result<Vec<u8>> {
    match fetch {
        HttpFetch::Content { body, .. } => Ok(body),
        HttpFetch::NotModified { .. } => bail!("{label} unexpectedly returned not modified"),
        HttpFetch::Failed {
            outcome, status, ..
        } => bail!("{label} failed with {outcome:?} ({status:?})"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn acquisition_escalation_is_failure_driven_and_policy_bound() {
        assert_eq!(
            escalation_decision(
                AcquisitionMethod::DirectHttp,
                AcquisitionOutcome::PartialContent,
                SourceAccessMode::Public,
            ),
            EscalationDecision::Next(AcquisitionMethod::Crawl4ai)
        );
        assert_eq!(
            escalation_decision(
                AcquisitionMethod::Crawl4ai,
                AcquisitionOutcome::RateLimited,
                SourceAccessMode::Public,
            ),
            EscalationDecision::Retry
        );
        assert_eq!(
            escalation_decision(
                AcquisitionMethod::Scrapling,
                AcquisitionOutcome::AuthRequired,
                SourceAccessMode::Public,
            ),
            EscalationDecision::Stop
        );
        assert_eq!(
            escalation_decision(
                AcquisitionMethod::Scrapling,
                AcquisitionOutcome::AuthRequired,
                SourceAccessMode::AuthenticatedLocal,
            ),
            EscalationDecision::Next(AcquisitionMethod::OpenCli)
        );
        for outcome in [
            AcquisitionOutcome::RobotsDenied,
            AcquisitionOutcome::Captcha,
            AcquisitionOutcome::ExplicitChallenge,
            AcquisitionOutcome::PolicyDenied,
        ] {
            assert_eq!(
                escalation_decision(
                    AcquisitionMethod::DirectHttp,
                    outcome,
                    SourceAccessMode::Public
                ),
                EscalationDecision::Stop
            );
        }
    }

    #[test]
    fn parses_rss_and_atom_without_cross_entry_leakage() {
        let feed = r#"
          <rss><channel>
            <item>
              <guid>one</guid><title>Agent &amp; Memory</title>
              <link>https://example.com/a</link>
              <description><![CDATA[<p>Fresh verification</p>]]></description>
              <pubDate>Sat, 22 Aug 2026 10:00:00 +0000</pubDate>
            </item>
          </channel></rss>
          <feed xmlns="http://www.w3.org/2005/Atom">
            <entry><id>two</id><title>Workflow update</title>
              <link href="/b"/><summary>New &lt;gate&gt;</summary>
              <updated>2026-08-22T11:00:00Z</updated>
            </entry>
          </feed>
        "#;
        let items = parse_rss_or_atom(feed, "https://example.com/feed.xml").unwrap();
        assert_eq!(items.len(), 2);
        assert_eq!(items[0].title, "Agent & Memory");
        assert_eq!(items[0].summary.as_deref(), Some("Fresh verification"));
        assert_eq!(items[1].url, "https://example.com/b");
        assert_eq!(items[1].external_id.as_deref(), Some("two"));
    }

    #[test]
    fn parses_hn_and_github_incremental_events() {
        let updates = serde_json::json!({"items":[3,2,3,1],"profiles":[]});
        assert_eq!(parse_hn_updates(&updates).unwrap(), vec![1, 2, 3]);
        let story = serde_json::json!({
            "id": 42,
            "type": "story",
            "title": "Agent memory",
            "by": "alice",
            "time": 1_787_392_800,
            "url": "https://example.com/post"
        });
        assert_eq!(
            parse_hn_item(&story)
                .unwrap()
                .unwrap()
                .external_id
                .as_deref(),
            Some("42")
        );
        let events = serde_json::json!([
            {
                "id":"new",
                "type":"PushEvent",
                "created_at":"2026-08-22T10:00:00Z",
                "repo":{"name":"owner/repo"},
                "actor":{"login":"alice"},
                "payload":{"head":"abcdef","commits":[{"message":"Improve router"}]}
            },
            {
                "id":"old",
                "type":"WatchEvent",
                "repo":{"name":"owner/repo"},
                "actor":{"login":"bob"},
                "payload":{}
            }
        ]);
        let items = parse_github_events(&events, Some("old")).unwrap();
        assert_eq!(items.len(), 1);
        assert!(items[0].url.ends_with("/commit/abcdef"));
    }

    #[test]
    fn topic_matching_is_deterministic_and_bilingual() {
        let item = DiscoveryItem {
            external_id: None,
            title: "Agent 持续学习的新方法".into(),
            url: "https://example.com".into(),
            author: None,
            published_at: None,
            summary: Some("workflow memory benchmark".into()),
            language: None,
        };
        assert!(topic_matches(
            &item,
            "retrieval",
            &["持续学习".into(), "gate".into()]
        ));
        assert!(!topic_matches(&item, "database", &["compiler".into()]));
    }

    struct PinnedAddressGuard;
    impl PinnedAddressGuard {
        fn pin(address: SocketAddr) -> Self {
            *TEST_PINNED_ADDRESS.lock().unwrap() = Some(address);
            Self
        }
    }
    impl Drop for PinnedAddressGuard {
        fn drop(&mut self) {
            *TEST_PINNED_ADDRESS.lock().unwrap() = None;
        }
    }

    #[tokio::test]
    async fn fetch_maps_429_and_403_and_enforces_document_cap() {
        use axum::{Router, http::StatusCode, routing::get};

        async fn limited() -> (
            StatusCode,
            [(axum::http::HeaderName, &'static str); 1],
            &'static str,
        ) {
            (
                StatusCode::TOO_MANY_REQUESTS,
                [(axum::http::header::RETRY_AFTER, "7")],
                "slow down",
            )
        }
        async fn forbidden() -> StatusCode {
            StatusCode::FORBIDDEN
        }
        async fn oversized() -> Vec<u8> {
            vec![b'x'; (MAX_DOCUMENT_BYTES + 1) as usize]
        }

        let app = Router::new()
            .route("/limited", get(limited))
            .route("/forbidden", get(forbidden))
            .route("/oversized", get(oversized));
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });

        // `mock.test` passes the lexical host checks; the seam pins it to the
        // loopback mock so no real DNS or network is involved.
        let _pinned = PinnedAddressGuard::pin(address);
        let domains = vec!["mock.test".to_string()];
        let conditional = ConditionalHeaders::default();
        let url = |path: &str| format!("http://mock.test:{}{path}", address.port());

        let limited = fetch_public_url(&url("/limited"), &domains, &conditional, None)
            .await
            .unwrap();
        match limited {
            HttpFetch::Failed {
                status,
                outcome,
                retry_after_seconds,
                ..
            } => {
                assert_eq!(status, Some(429));
                assert_eq!(outcome, AcquisitionOutcome::RateLimited);
                assert_eq!(retry_after_seconds, Some(7));
            }
            other => panic!("expected 429 failure, got {other:?}"),
        }

        let forbidden = fetch_public_url(&url("/forbidden"), &domains, &conditional, None)
            .await
            .unwrap();
        match forbidden {
            HttpFetch::Failed {
                status,
                outcome,
                retry_after_seconds,
                ..
            } => {
                assert_eq!(status, Some(403));
                assert_eq!(outcome, AcquisitionOutcome::AuthRequired);
                assert_eq!(retry_after_seconds, None);
            }
            other => panic!("expected 403 failure, got {other:?}"),
        }

        let error = fetch_public_url(&url("/oversized"), &domains, &conditional, None)
            .await
            .unwrap_err();
        assert!(
            error.to_string().contains("maximum document size"),
            "unexpected error: {error}"
        );
    }
}
