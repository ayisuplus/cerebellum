pub mod acquisition;
pub mod api;
pub mod builtins;
pub mod collector;
pub mod config;
pub mod dataset_factory;
pub mod eval;
pub mod events;
pub mod experts;
pub mod gates;
pub mod importer;
pub mod knowledge;
pub mod knowledge_store;
pub mod learning;
mod learning_store;
pub mod mcp;
pub mod meta_training;
pub mod optimization;
mod optimization_store;
pub mod permit;
pub mod quality;
pub mod router;
pub mod sandbox;
pub mod scheduler;
pub mod schemas;
pub mod store;
pub mod training;

pub use config::AppConfig;
pub use store::Registry;
/// Fixed UTC+8 civil time (Asia/Shanghai, no DST). This is the single source
/// of the +8 offset so schedule-day markers and dedup keys cannot drift.
pub(crate) fn shanghai_time(now: chrono::DateTime<chrono::Utc>) -> chrono::DateTime<chrono::Utc> {
    now + chrono::Duration::hours(8)
}

/// Asia/Shanghai calendar day for schedule days and dedup keys; every caller
/// must derive the day through this helper.
pub(crate) fn shanghai_day(now: chrono::DateTime<chrono::Utc>) -> chrono::NaiveDate {
    shanghai_time(now).date_naive()
}

/// Join an OpenAI-compatible base URL to its chat-completions route.
///
/// Accepts a bare host root (`http://host:port`), a versioned root
/// (`http://host:port/v1`), or a full route; each maps to exactly one
/// `/chat/completions` suffix. Trailing slashes are ignored.
pub fn chat_completions_url(endpoint: &str) -> String {
    let base = endpoint.trim_end_matches('/');
    if base.ends_with("/chat/completions") {
        base.to_string()
    } else if base.ends_with("/v1") {
        format!("{base}/chat/completions")
    } else {
        format!("{base}/v1/chat/completions")
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn chat_completions_url_normalizes_each_base_shape() {
        assert_eq!(
            super::chat_completions_url("http://127.0.0.1:1234"),
            "http://127.0.0.1:1234/v1/chat/completions"
        );
        assert_eq!(
            super::chat_completions_url("http://127.0.0.1:1234/"),
            "http://127.0.0.1:1234/v1/chat/completions"
        );
        assert_eq!(
            super::chat_completions_url("http://127.0.0.1:1234/v1"),
            "http://127.0.0.1:1234/v1/chat/completions"
        );
        assert_eq!(
            super::chat_completions_url("http://127.0.0.1:1234/v1/chat/completions"),
            "http://127.0.0.1:1234/v1/chat/completions"
        );
        assert_eq!(
            super::chat_completions_url("http://127.0.0.1:1234/v1/chat/completions/"),
            "http://127.0.0.1:1234/v1/chat/completions"
        );
    }
}
