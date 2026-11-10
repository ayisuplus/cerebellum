//! Shared tokenization for retrieval surfaces. ASCII/digit runs split on
//! unicode61-like boundaries; contiguous CJK runs index as overlapping
//! bigrams (1–2 char runs stay whole), so unsegmented CJK text stays
//! matchable without a CJK-aware FTS tokenizer. Pure functions, no
//! crate-internal dependencies: the router, FTS indexing, and feature-hash
//! embeddings must all agree on what a token is.

use anyhow::{Context, Result, bail};
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
use url::{Host, Url};

/// Tokenize text into lowercase word tokens with CJK bigram expansion.
pub fn tokenize_text(value: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut run = String::new();
    let mut run_is_cjk = false;
    // Split on punctuation and on CJK<->non-CJK boundaries so mixed text
    // like "修复parser" yields both a CJK run and a Latin token.
    for ch in value.to_lowercase().chars() {
        let word_char = ch.is_alphanumeric() || ch == '-';
        let cjk = is_cjk(ch);
        if word_char && !run.is_empty() && cjk == run_is_cjk {
            run.push(ch);
            continue;
        }
        if !run.is_empty() {
            tokens.extend(cjk_aware_tokens(&run, run_is_cjk));
            run.clear();
        }
        if word_char {
            run.push(ch);
            run_is_cjk = cjk;
        }
    }
    if !run.is_empty() {
        tokens.extend(cjk_aware_tokens(&run, run_is_cjk));
    }
    tokens
}

/// Quote one raw term as an FTS5 string literal for use in MATCH queries.
pub fn fts_query_escape(term: &str) -> String {
    format!("\"{}\"", term.replace('"', "\"\""))
}

/// CJK text has no word boundaries, so a contiguous CJK run would otherwise
/// stay a single opaque token that only exact queries can match. Index
/// overlapping bigrams instead (a 1-2 char run is its own token).
fn cjk_aware_tokens(run: &str, is_cjk_run: bool) -> Vec<String> {
    let chars: Vec<char> = run.chars().collect();
    if is_cjk_run && chars.len() > 2 {
        chars.windows(2).map(|pair| pair.iter().collect()).collect()
    } else {
        vec![run.to_string()]
    }
}

fn is_cjk(ch: char) -> bool {
    matches!(
        ch,
        '一'..='\u{9fff}' | '\u{3400}'..='\u{4dbf}' | '\u{f900}'..='\u{faff}'
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cjk_runs_become_overlapping_bigrams() {
        assert_eq!(
            tokenize_text("回归测试"),
            vec!["回归".to_string(), "归测".to_string(), "测试".to_string()]
        );
        // 1-2 char runs stay whole.
        assert_eq!(tokenize_text("修复"), vec!["修复".to_string()]);
        assert_eq!(tokenize_text("修"), vec!["修".to_string()]);
    }

    #[test]
    fn mixed_text_splits_on_script_boundaries() {
        assert_eq!(
            tokenize_text("修复parser崩溃"),
            vec!["修复".to_string(), "parser".to_string(), "崩溃".to_string()]
        );
        assert_eq!(
            tokenize_text("Fix-Bug v2"),
            vec!["fix-bug".to_string(), "v2".to_string()]
        );
    }

    #[test]
    fn fts_escape_quotes_literals() {
        assert_eq!(fts_query_escape("say \"hi\""), "\"say \"\"hi\"\"\"");
    }
}

/// Normalize a source URL for fetching: credential-free HTTP(S) only, public
/// host inside the policy allowlist, default ports dropped, fragments
/// removed, tracking parameters stripped, and the remaining query sorted
/// for determinism.
pub fn canonicalize_public_url(input: &str, allowed_domains: &[String]) -> Result<String> {
    if input.len() > 8_192 {
        bail!("URL exceeds the maximum length");
    }
    let mut url = Url::parse(input).context("invalid URL")?;
    if !matches!(url.scheme(), "http" | "https")
        || !url.username().is_empty()
        || url.password().is_some()
    {
        bail!("only credential-free HTTP(S) URLs are allowed");
    }
    let host = match url.host().context("URL must include a host")? {
        Host::Domain(host) => {
            let host = host.trim_end_matches('.').to_ascii_lowercase();
            validate_host(&host)?;
            host
        }
        Host::Ipv4(ip) if is_global_v4(ip) => ip.to_string(),
        Host::Ipv6(ip) if is_global_v6(ip) => ip.to_string(),
        Host::Ipv4(_) | Host::Ipv6(_) => bail!("non-public IP address is forbidden"),
    };
    if !allowed_domains.is_empty()
        && !allowed_domains.iter().any(|allowed| {
            let allowed = allowed.trim().trim_end_matches('.').to_ascii_lowercase();
            host == allowed || host.ends_with(&format!(".{allowed}"))
        })
    {
        bail!("URL host is outside the source policy allowlist");
    }
    url.set_fragment(None);
    if (url.scheme() == "https" && url.port() == Some(443))
        || (url.scheme() == "http" && url.port() == Some(80))
    {
        let _ = url.set_port(None);
    }
    let mut pairs = url
        .query_pairs()
        .filter(|(name, _)| !is_tracking_parameter(name))
        .map(|(name, value)| (name.into_owned(), value.into_owned()))
        .collect::<Vec<_>>();
    pairs.sort();
    url.set_query(None);
    if !pairs.is_empty() {
        url.query_pairs_mut().extend_pairs(pairs);
    }
    Ok(url.to_string())
}

/// Cheap lexical prompt-injection screen (Chinese + English markers). This is
/// a deterministic tripwire, not a classifier: callers treat a hit as a
/// hard quarantine signal, never as proof of safety when absent.
pub fn detects_prompt_injection(content: &str) -> bool {
    let lower = content.to_lowercase();
    [
        "ignore previous instructions",
        "ignore all previous",
        "system prompt",
        "developer message",
        "jailbreak",
        "exfiltrate",
        "忽略之前",
        "忽略以上",
        "系统提示词",
        "开发者消息",
        "泄露密钥",
    ]
    .iter()
    .any(|pattern| lower.contains(pattern))
}

fn validate_host(host: &str) -> Result<()> {
    if host.is_empty()
        || host == "localhost"
        || host.ends_with(".localhost")
        || host.ends_with(".local")
        || host.ends_with(".internal")
        || host == "metadata.google.internal"
    {
        bail!("local and special-use hosts are forbidden");
    }
    if let Ok(ip) = host.parse::<IpAddr>()
        && !is_global_ip(ip)
    {
        bail!("non-public IP address is forbidden");
    }
    Ok(())
}
/// Whether an address is a globally routable public IP (SSRF predicate).
pub fn is_global_ip(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(ip) => is_global_v4(ip),
        IpAddr::V6(ip) => is_global_v6(ip),
    }
}

fn is_global_v4(ip: Ipv4Addr) -> bool {
    let octets = ip.octets();
    !(ip.is_private()
        || ip.is_loopback()
        || ip.is_link_local()
        || ip.is_multicast()
        || ip.is_unspecified()
        || octets[0] == 0
        || octets[0] >= 224
        || (octets[0] == 100 && (64..=127).contains(&octets[1]))
        || (octets[0] == 192 && octets[1] == 0 && octets[2] == 0)
        || (octets[0] == 192 && octets[1] == 0 && octets[2] == 2)
        || (octets[0] == 198 && (octets[1] == 18 || octets[1] == 19))
        || (octets[0] == 198 && octets[1] == 51 && octets[2] == 100)
        || (octets[0] == 203 && octets[1] == 0 && octets[2] == 113))
}

fn is_global_v6(ip: Ipv6Addr) -> bool {
    let segments = ip.segments();
    if let Some(mapped) = ip.to_ipv4_mapped() {
        return is_global_v4(mapped);
    }
    !(ip.is_loopback()
        || ip.is_unspecified()
        || ip.is_multicast()
        || (segments[0] & 0xfe00) == 0xfc00
        || (segments[0] & 0xffc0) == 0xfe80
        || (segments[0] == 0x2001 && segments[1] == 0x0db8))
}

fn is_tracking_parameter(name: &str) -> bool {
    let name = name.to_ascii_lowercase();
    name.starts_with("utm_")
        || matches!(
            name.as_str(),
            "fbclid" | "gclid" | "dclid" | "mc_cid" | "mc_eid"
        )
}

#[cfg(test)]
mod canonical_tests {
    use super::canonicalize_public_url;

    #[test]
    fn canonical_url_rejects_ssrf_and_normalizes_tracking() {
        assert_eq!(
            canonicalize_public_url(
                "HTTPS://Example.COM:443/path?utm_source=x&b=2&a=1#fragment",
                &["example.com".into()],
            )
            .unwrap(),
            "https://example.com/path?a=1&b=2"
        );
        for forbidden in [
            "http://127.0.0.1/admin",
            "http://[::1]/admin",
            "http://169.254.169.254/latest/meta-data",
            "file:///etc/passwd",
            "http://localhost/",
            "https://example.com@127.0.0.1/",
        ] {
            assert!(
                canonicalize_public_url(forbidden, &[]).is_err(),
                "{forbidden} must be rejected"
            );
        }
        assert!(
            canonicalize_public_url("https://example.com.evil.invalid/", &["example.com".into()])
                .is_err()
        );
    }
}
