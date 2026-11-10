//! Deterministic metacognition trace generator (work package
//! `metacognition-core`, M1 of the approved metacognition research plan).
//!
//! Emits training-eligible `MetaDecisionTrace` records for the three
//! metacognition task kinds plus matching `MetaReplayEvaluation` records.
//! Gold outputs are constructed by rule from the scenario, never model-judged.
//! Generator entities are deliberately disjoint from every
//! `benchmarks/metacognition/` probe family so later adapter evaluation stays
//! honest. Everything is derived from fixed constants: the same `--count` on a
//! fresh registry produces byte-identical record hashes.
//!
//! Split placement: traces spread round-robin over fixed
//! (topic_family, month) groups and land ~80/10/10 under the unified split
//! policy; replays are placed into precomputed validation/holdout-landing
//! groups so the metacognition expert clears `MIN_EXPERT_REPLAY_RECORDS`.

use anyhow::{Result, bail};
use cerebellum_core::{
    MetaDecisionTrace, MetaReplayEvaluation, MetaTaskKind, MetacognitionAction, MetacognitionBasis,
    MetacognitionDecision, SCHEMA_VERSION, canonical_json_hash,
};
use chrono::{DateTime, TimeZone, Utc};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::Registry;

pub const METACOGNITION_SOURCE_DOMAIN: &str = "metacognition-generator";
pub const METACOGNITION_POLICY_VERSION: &str = "metacognition-generator-v2";
const TIMEZONE: &str = "Asia/Shanghai";
const TRACE_CLUSTERS: u32 = 20;
const TRACE_MONTHS: [&str; 3] = ["2026-06", "2026-07", "2026-08"];
const REPLAY_MONTH: &str = "2026-08";
/// Replay `task_id` embeds one of these per kind so `classify_replay`'s
/// keyword router resolves exactly the metacognition candidate group.
const ROUTING_KEYWORDS: [&str; 3] = ["time", "current", "stale"];

/// One synthetic volatile-fact entity. Values are authored fixtures; only
/// their internal dates drive gold construction.
struct Entity {
    slug: &'static str,
    query_zh: &'static str,
    query_en: &'static str,
    claim: &'static str,
    observed_at: &'static str,
    valid_until: &'static str,
    search: &'static str,
}

// Training pool: disjoint from every TG/KB/ST probe family.
const ENTITIES: &[Entity] = &[
    Entity {
        slug: "go-stable",
        query_zh: "Go 语言目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable Go release?",
        claim: "1.24.5",
        observed_at: "2026-06-02T10:00:00+08:00",
        valid_until: "2026-12-31T23:59:00+08:00",
        search: "Go 最新稳定版本",
    },
    Entity {
        slug: "node-lts",
        query_zh: "Node.js 当前的 LTS 版本线是什么？",
        query_en: "What is the current Node.js LTS release line?",
        claim: "22.x (Jod)",
        observed_at: "2026-05-12T10:00:00+08:00",
        valid_until: "2026-10-31T23:59:00+08:00",
        search: "Node.js current LTS line",
    },
    Entity {
        slug: "typescript-stable",
        query_zh: "TypeScript 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable TypeScript version right now?",
        claim: "5.9",
        observed_at: "2026-07-01T10:00:00+08:00",
        valid_until: "2027-01-31T23:59:00+08:00",
        search: "TypeScript 最新稳定版本",
    },
    Entity {
        slug: "react-latest",
        query_zh: "React 目前的最新主版本是什么？",
        query_en: "What is the latest React major release right now?",
        claim: "19.1",
        observed_at: "2026-05-28T10:00:00+08:00",
        valid_until: "2026-11-30T23:59:00+08:00",
        search: "latest React major version",
    },
    Entity {
        slug: "angular-latest",
        query_zh: "Angular 目前的最新主版本是什么？",
        query_en: "What is the latest Angular major version currently?",
        claim: "20",
        observed_at: "2026-06-11T10:00:00+08:00",
        valid_until: "2026-12-15T23:59:00+08:00",
        search: "Angular 最新主版本",
    },
    Entity {
        slug: "django-stable",
        query_zh: "Django 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable Django release?",
        claim: "5.2",
        observed_at: "2026-04-22T10:00:00+08:00",
        valid_until: "2026-10-31T23:59:00+08:00",
        search: "Django 最新稳定版本",
    },
    Entity {
        slug: "flask-latest",
        query_zh: "Flask 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Flask version currently?",
        claim: "3.1",
        observed_at: "2026-03-15T10:00:00+08:00",
        valid_until: "2026-09-30T23:59:00+08:00",
        search: "Flask latest stable version",
    },
    Entity {
        slug: "springboot",
        query_zh: "Spring Boot 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable Spring Boot release?",
        claim: "3.5",
        observed_at: "2026-06-20T10:00:00+08:00",
        valid_until: "2026-12-31T23:59:00+08:00",
        search: "Spring Boot 最新稳定版本",
    },
    Entity {
        slug: "dotnet-lts",
        query_zh: ".NET 目前的最新 LTS 版本是什么？",
        query_en: "What is the current latest .NET LTS release?",
        claim: ".NET 10",
        observed_at: "2025-11-11T10:00:00+08:00",
        valid_until: "2026-11-11T23:59:00+08:00",
        search: ".NET 最新 LTS 版本",
    },
    Entity {
        slug: "kotlin-stable",
        query_zh: "Kotlin 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Kotlin version right now?",
        claim: "2.2",
        observed_at: "2026-06-23T10:00:00+08:00",
        valid_until: "2026-12-31T23:59:00+08:00",
        search: "Kotlin 最新稳定版本",
    },
    Entity {
        slug: "swift-latest",
        query_zh: "Swift 目前的最新版本是什么？",
        query_en: "What is the current latest Swift release?",
        claim: "6.1",
        observed_at: "2026-04-01T10:00:00+08:00",
        valid_until: "2026-10-01T23:59:00+08:00",
        search: "Swift 最新版本",
    },
    Entity {
        slug: "terraform",
        query_zh: "Terraform 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Terraform version currently?",
        claim: "1.12",
        observed_at: "2026-05-14T10:00:00+08:00",
        valid_until: "2026-11-30T23:59:00+08:00",
        search: "Terraform latest stable",
    },
    Entity {
        slug: "ansible",
        query_zh: "Ansible 目前的最新社区版本是什么？",
        query_en: "What is the current latest Ansible community release?",
        claim: "11",
        observed_at: "2026-02-18T10:00:00+08:00",
        valid_until: "2026-08-31T23:59:00+08:00",
        search: "Ansible 最新社区版本",
    },
    Entity {
        slug: "prometheus",
        query_zh: "Prometheus 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Prometheus release right now?",
        claim: "3.4",
        observed_at: "2026-05-06T10:00:00+08:00",
        valid_until: "2026-11-30T23:59:00+08:00",
        search: "Prometheus 最新稳定版本",
    },
    Entity {
        slug: "grafana",
        query_zh: "Grafana 目前的最新主版本是什么？",
        query_en: "What is the latest Grafana major version currently?",
        claim: "12",
        observed_at: "2026-05-21T10:00:00+08:00",
        valid_until: "2026-12-31T23:59:00+08:00",
        search: "Grafana latest major version",
    },
    Entity {
        slug: "redis",
        query_zh: "Redis 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable Redis release?",
        claim: "8.0",
        observed_at: "2026-05-02T10:00:00+08:00",
        valid_until: "2026-11-01T23:59:00+08:00",
        search: "Redis 最新稳定版本",
    },
    Entity {
        slug: "mysql-lts",
        query_zh: "MySQL 目前的最新 LTS 版本线是什么？",
        query_en: "What is the current latest MySQL LTS release line?",
        claim: "8.4",
        observed_at: "2026-01-20T10:00:00+08:00",
        valid_until: "2026-07-31T23:59:00+08:00",
        search: "MySQL 最新 LTS",
    },
    Entity {
        slug: "mongodb",
        query_zh: "MongoDB 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable MongoDB release right now?",
        claim: "8.1",
        observed_at: "2026-06-05T10:00:00+08:00",
        valid_until: "2026-12-31T23:59:00+08:00",
        search: "MongoDB latest stable",
    },
    Entity {
        slug: "elasticsearch",
        query_zh: "Elasticsearch 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable Elasticsearch release?",
        claim: "9.0",
        observed_at: "2026-04-15T10:00:00+08:00",
        valid_until: "2026-10-15T23:59:00+08:00",
        search: "Elasticsearch 最新稳定版本",
    },
    Entity {
        slug: "kafka",
        query_zh: "Apache Kafka 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Apache Kafka release currently?",
        claim: "4.0",
        observed_at: "2026-03-28T10:00:00+08:00",
        valid_until: "2026-09-30T23:59:00+08:00",
        search: "Kafka latest stable version",
    },
    Entity {
        slug: "rabbitmq",
        query_zh: "RabbitMQ 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable RabbitMQ release?",
        claim: "4.1",
        observed_at: "2026-05-30T10:00:00+08:00",
        valid_until: "2026-11-30T23:59:00+08:00",
        search: "RabbitMQ 最新稳定版本",
    },
    Entity {
        slug: "nginx",
        query_zh: "Nginx 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Nginx version right now?",
        claim: "1.28",
        observed_at: "2026-04-23T10:00:00+08:00",
        valid_until: "2026-10-31T23:59:00+08:00",
        search: "Nginx latest stable version",
    },
    Entity {
        slug: "caddy",
        query_zh: "Caddy 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable Caddy release?",
        claim: "2.10",
        observed_at: "2026-06-18T10:00:00+08:00",
        valid_until: "2026-12-31T23:59:00+08:00",
        search: "Caddy 最新稳定版本",
    },
    Entity {
        slug: "docker-engine",
        query_zh: "Docker Engine 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Docker Engine release currently?",
        claim: "28.3",
        observed_at: "2026-07-08T10:00:00+08:00",
        valid_until: "2027-01-31T23:59:00+08:00",
        search: "Docker Engine latest stable",
    },
    Entity {
        slug: "containerd",
        query_zh: "containerd 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable containerd release?",
        claim: "2.1",
        observed_at: "2026-05-17T10:00:00+08:00",
        valid_until: "2026-11-17T23:59:00+08:00",
        search: "containerd 最新稳定版本",
    },
    Entity {
        slug: "github-ceo",
        query_zh: "GitHub 现任 CEO 是谁？",
        query_en: "Who is the current CEO of GitHub?",
        claim: "Thomas Dohmke",
        observed_at: "2026-02-10T10:00:00+08:00",
        valid_until: "2027-02-10T23:59:00+08:00",
        search: "GitHub current CEO",
    },
    Entity {
        slug: "gitlab-ceo",
        query_zh: "GitLab 现任 CEO 是谁？",
        query_en: "Who is the current CEO of GitLab?",
        claim: "Bill Staples",
        observed_at: "2026-03-01T10:00:00+08:00",
        valid_until: "2027-03-01T23:59:00+08:00",
        search: "GitLab 现任 CEO",
    },
    Entity {
        slug: "apache-chair",
        query_zh: "Apache 软件基金会现任主席是谁？",
        query_en: "Who is the current chair of the Apache Software Foundation?",
        claim: "（现任主席姓名）",
        observed_at: "2026-04-01T10:00:00+08:00",
        valid_until: "2027-04-01T23:59:00+08:00",
        search: "Apache Software Foundation chair",
    },
    Entity {
        slug: "harmonyos",
        query_zh: "华为鸿蒙目前的最新版本是什么？",
        query_en: "What is the latest HarmonyOS version right now?",
        claim: "HarmonyOS 6.0",
        observed_at: "2026-06-21T10:00:00+08:00",
        valid_until: "2026-12-31T23:59:00+08:00",
        search: "鸿蒙 最新版本",
    },
    Entity {
        slug: "wechat",
        query_zh: "微信目前的最新版本号是多少？",
        query_en: "What is the current latest WeChat version number?",
        claim: "8.0.62",
        observed_at: "2026-07-15T10:00:00+08:00",
        valid_until: "2027-01-15T23:59:00+08:00",
        search: "微信 最新版本号",
    },
    Entity {
        slug: "chrome",
        query_zh: "Chrome 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable Chrome version right now?",
        claim: "138",
        observed_at: "2026-07-22T10:00:00+08:00",
        valid_until: "2027-01-31T23:59:00+08:00",
        search: "Chrome latest stable version",
    },
    Entity {
        slug: "firefox",
        query_zh: "Firefox 目前的最新稳定版本是多少？",
        query_en: "What is the current latest stable Firefox release?",
        claim: "141",
        observed_at: "2026-07-28T10:00:00+08:00",
        valid_until: "2027-01-31T23:59:00+08:00",
        search: "Firefox 最新稳定版本",
    },
    Entity {
        slug: "vscode",
        query_zh: "VS Code 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable VS Code release right now?",
        claim: "1.102",
        observed_at: "2026-07-10T10:00:00+08:00",
        valid_until: "2027-01-10T23:59:00+08:00",
        search: "VS Code latest stable",
    },
    Entity {
        slug: "intellij",
        query_zh: "IntelliJ IDEA 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable IntelliJ IDEA release?",
        claim: "2025.2",
        observed_at: "2026-07-30T10:00:00+08:00",
        valid_until: "2027-01-31T23:59:00+08:00",
        search: "IntelliJ IDEA 最新稳定版本",
    },
    Entity {
        slug: "laliga-top",
        query_zh: "现任西甲联赛金靴得主是谁？",
        query_en: "Who is the current La Liga top scorer title holder?",
        claim: "（现任金靴球员）",
        observed_at: "2026-06-01T10:00:00+08:00",
        valid_until: "2027-06-01T23:59:00+08:00",
        search: "西甲 现任 金靴",
    },
    Entity {
        slug: "nba-mvp",
        query_zh: "现任 NBA 常规赛 MVP 是谁？",
        query_en: "Who is the current NBA regular-season MVP?",
        claim: "（现任 MVP 球员）",
        observed_at: "2026-05-25T10:00:00+08:00",
        valid_until: "2027-05-25T23:59:00+08:00",
        search: "NBA current MVP",
    },
    Entity {
        slug: "tailwind",
        query_zh: "Tailwind CSS 目前的最新主版本是什么？",
        query_en: "What is the latest Tailwind CSS major version right now?",
        claim: "4.1",
        observed_at: "2026-04-29T10:00:00+08:00",
        valid_until: "2026-10-29T23:59:00+08:00",
        search: "Tailwind CSS 最新主版本",
    },
    Entity {
        slug: "vite",
        query_zh: "Vite 目前的最新主版本是多少？",
        query_en: "What is the latest Vite major version currently?",
        claim: "7.0",
        observed_at: "2026-06-24T10:00:00+08:00",
        valid_until: "2026-12-24T23:59:00+08:00",
        search: "Vite latest major version",
    },
    Entity {
        slug: "pytorch",
        query_zh: "PyTorch 目前的最新稳定版本是什么？",
        query_en: "What is the current latest stable PyTorch release?",
        claim: "2.8",
        observed_at: "2026-07-25T10:00:00+08:00",
        valid_until: "2027-01-25T23:59:00+08:00",
        search: "PyTorch 最新稳定版本",
    },
    Entity {
        slug: "cuda",
        query_zh: "CUDA 目前的最新稳定版本是多少？",
        query_en: "What is the latest stable CUDA version right now?",
        claim: "13.0",
        observed_at: "2026-06-08T10:00:00+08:00",
        valid_until: "2026-12-08T23:59:00+08:00",
        search: "CUDA latest stable version",
    },
];

/// General-knowledge facts for knowledge-boundary "known" scenarios;
/// disjoint from the KB probe candidate set. W1: every entry verified 3/3
/// against the pinned base (.coordination/work/metacognition-w1/
/// kb-pool-verification.json); failures moved to UNKNOWN_FACTS.
const KNOWN_FACTS: &[(&str, &str, &str)] = &[
    ("ssh-port", "SSH 协议的默认端口是多少？", "22"),
    (
        "ascii-a",
        "ASCII 编码中大写字母 A 的十进制码值是多少？",
        "65",
    ),
    ("water-boiling", "标准大气压下水的沸点是多少摄氏度？", "100"),
    ("earth-rotation", "地球自转一周大约需要多少小时？", "24"),
    (
        "java-sponsor",
        "What company originally released Java?",
        "Sun Microsystems",
    ),
    (
        "linux-author",
        "Linux 内核的最初作者是谁？",
        "Linus Torvalds",
    ),
    ("regex-digit", "正则表达式中 \\d 匹配什么字符类别？", "数字"),
    ("html-br", "HTML 中 <br> 标签的作用是什么？", "换行"),
    (
        "css-meaning",
        "What does CSS stand for?",
        "Cascading Style Sheets",
    ),
    (
        "sha256-len",
        "What is the SHA-256 output length in bits?",
        "256",
    ),
    ("byte-bits", "一个字节包含多少位？", "8"),
    ("absolute-zero", "绝对零度是多少摄氏度？", "-273.15"),
    ("olympic-rings", "奥运五环标志中有几个环？", "5"),
    ("v8-engine", "What JavaScript engine powers Node.js?", "V8"),
];

/// Post-cutoff-style facts for "unknown -> search_internal" scenarios;
/// disjoint from the KB probe post-cutoff set.
const UNKNOWN_FACTS: &[(&str, &str)] = &[
    ("turing-2026", "2026 年图灵奖得主是谁？"),
    ("fields-2026", "Who won the 2026 Fields Medals?"),
    ("g20-2026", "2026 年 G20 峰会的主办国是哪个？"),
    (
        "iphone-2025",
        "2025 年苹果秋季发布会推出的 iPhone 旗舰型号是什么？",
    ),
    ("tesla-2026", "What is Tesla's best-selling model in 2026?"),
    ("booker-2025", "2025 年布克奖得主是哪部作品？"),
    ("csl-2026", "2026 年中超联赛冠军是哪支球队？"),
    (
        "nba-draft-2025",
        "Who was the first pick of the 2025 NBA draft?",
    ),
    ("ces-2026", "2026 年 CES 最佳创新奖颁给了哪款产品？"),
    (
        "spacex-2025",
        "How many launches did SpaceX complete in 2025?",
    ),
    ("nintendo-2026", "2026 年任天堂新一代主机的首发销量是多少？"),
    ("boxoffice-2025", "2025 年全球票房最高的电影是哪部？"),
    (
        "msbuild-2026",
        "What was the theme of Microsoft Build 2026?",
    ),
    ("wwdc-2026", "2026 年 WWDC 发布的 iOS 大版本号是多少？"),
    ("olympic-2028", "2028 年奥运会新增比赛项目有哪些？"),
    // W1: demoted from KNOWN_FACTS — the pinned base answered these < 3/3 in
    // kb-pool-verification.json, so their gold becomes search_internal.
    ("http-port", "What port does plain HTTP use by default?"),
    ("largest-country", "世界上面积最大的国家是哪个？"),
    ("c-main", "What is the return type of main in C?"),
    ("www-inventor", "万维网（WWW）的发明者是谁？"),
    (
        "eniac",
        "What was the first general-purpose electronic computer?",
    ),
    ("turing-machine", "图灵机的提出者是谁？"),
    ("ruby-author", "Ruby 语言的作者是谁？"),
    ("linux-mascot", "Linux 的吉祥物是什么动物？"),
    ("photosynthesis", "光合作用的两种主要原料是什么？"),
    ("ohm-law", "欧姆定律的公式是什么？"),
    ("pi-digits", "圆周率 π 的前三位小数是多少？"),
    ("longest-river-cn", "中国最长的河流是哪条？"),
    ("deepest-ocean", "世界上最深的大洋是哪个？"),
    ("vitamin-c", "缺乏维生素 C 会导致什么疾病？"),
    (
        "sound-speed",
        "What is the approximate speed of sound in air at sea level?",
    ),
    ("first-element", "元素周期表中原子序数 1 的元素是什么？"),
];

/// Invented entities for "unknown -> insufficient" scenarios; disjoint from
/// the KB probe invented set.
const INVENTED_FACTS: &[&str] = &[
    "ZX-Quantum 芯片的制程是多少纳米？",
    "What is the aperture of the Lumina-9 telescope?",
    "蓝海协议 BLP-3 的握手需要几轮？",
    "What is the melting point of Crystallon alloy?",
    "NebulaOS 的默认 shell 是什么？",
    "What is the thrust of the Atlas-Prime rocket engine?",
    "钛金合金 TX-42 的抗拉强度是多少？",
    "What is the latest version of the Aurora programming language?",
    "Pegasus-5 卫星的轨道高度是多少公里？",
    "玄武数据库的默认事务隔离级别是什么？",
    "What is the time complexity of the QuantumLeaf algorithm?",
    "Emerald-7 电池的能量密度是多少 Wh/kg？",
    "What port does the Phantom protocol use by default?",
    "Olympus 穹顶殖民地的常住人口是多少？",
    "What is the clock speed of the Chronos-3 processor?",
];

fn stable_uuid(key: &str) -> Uuid {
    let digest = Sha256::digest(key.as_bytes());
    let mut bytes = [0_u8; 16];
    bytes.copy_from_slice(&digest[..16]);
    Uuid::from_bytes(bytes)
}

fn snap_id(group_key: &str) -> String {
    format!("{:x}", Sha256::digest(group_key.as_bytes()))
}

fn parse_fixed(value: &str) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(value)
        .expect("fixed rfc3339")
        .with_timezone(&Utc)
}

fn ts(month: &str, day: u32, second: u32) -> DateTime<Utc> {
    let (year, month_num) = month.split_once('-').expect("month shape");
    Utc.with_ymd_and_hms(
        year.parse().expect("year"),
        month_num.parse().expect("month"),
        1 + day % 28,
        second / 3600 % 24,
        second / 60 % 60,
        second % 60,
    )
    .single()
    .expect("valid timestamp")
}

fn freshness_hours(valid_until: &str, now: &DateTime<Utc>) -> u32 {
    let delta = (*now - parse_fixed(valid_until)).num_seconds().max(0) as u64;
    delta.div_ceil(3600).clamp(1, 8760) as u32
}

fn environment(now: Option<&DateTime<Utc>>, group_key: &str) -> Value {
    match now {
        Some(now) => json!({
            "now": now.to_rfc3339_opts(chrono::SecondsFormat::AutoSi, true),
            "timezone": TIMEZONE,
            "registry_snapshot": snap_id(group_key),
        }),
        None => Value::Null,
    }
}

fn card_json(entity: &Entity) -> Value {
    json!({
        "title": entity.slug,
        "claim": entity.claim,
        "observed_at": entity.observed_at,
        "valid_until": entity.valid_until,
        "status": "corroborated",
    })
}

fn decision_json(decision: MetacognitionDecision) -> Value {
    serde_json::to_value(decision).expect("decision serializes")
}

fn answer(
    claim: &str,
    now: Option<&DateTime<Utc>>,
    basis: MetacognitionBasis,
    confidence: f64,
) -> MetacognitionDecision {
    MetacognitionDecision {
        action: MetacognitionAction::Answer,
        as_of_used: now.copied(),
        query: None,
        freshness_hours: None,
        answer: Some(claim.into()),
        answer_basis: basis,
        confidence,
    }
}

fn search(
    query: &str,
    now: Option<&DateTime<Utc>>,
    freshness: Option<u32>,
    confidence: f64,
) -> MetacognitionDecision {
    MetacognitionDecision {
        action: MetacognitionAction::SearchInternal,
        as_of_used: now.copied(),
        query: Some(query.into()),
        freshness_hours: freshness,
        answer: None,
        answer_basis: MetacognitionBasis::None,
        confidence,
    }
}

fn acquire(
    query: &str,
    now: Option<&DateTime<Utc>>,
    freshness: u32,
    confidence: f64,
) -> MetacognitionDecision {
    MetacognitionDecision {
        action: MetacognitionAction::RequestAcquisition,
        as_of_used: now.copied(),
        query: Some(query.into()),
        freshness_hours: Some(freshness),
        answer: None,
        answer_basis: MetacognitionBasis::None,
        confidence,
    }
}

fn insufficient(now: Option<&DateTime<Utc>>, confidence: f64) -> MetacognitionDecision {
    MetacognitionDecision {
        action: MetacognitionAction::Insufficient,
        as_of_used: now.copied(),
        query: None,
        freshness_hours: None,
        answer: None,
        answer_basis: MetacognitionBasis::None,
        confidence,
    }
}

/// Unified-split replica of `meta_training`/`dataset_factory` group hashing:
/// sha256 of the split group key, first byte mod 10 (0-7 train, 8 validation,
/// 9 holdout). Used to place replay groups deterministically.
fn group_split(topic_family: &str, month: &str) -> u8 {
    let digest = Sha256::digest(
        crate::dataset_factory::split_group_key(METACOGNITION_SOURCE_DOMAIN, topic_family, month)
            .as_bytes(),
    );
    digest[0] % 10
}

/// Map the split digit (0-7 train, 8 validation, 9 holdout) to a bucket index.
fn split_bucket(split: u8) -> usize {
    if split < 8 { 0 } else { usize::from(split - 7) }
}

fn trace_family(kind: &str, cluster: u32) -> String {
    format!("metacognition/{kind}/c{cluster:02}")
}

fn replay_family(kind: &str, slot: u32) -> String {
    format!("metacognition/{kind}/r{slot:03}")
}

struct Scenario {
    kind: MetaTaskKind,
    kind_name: &'static str,
    input: Value,
    output: MetacognitionDecision,
}

/// Time-aware wrapper templates applied to a base query (`{q}` placeholder).
const WRAPPERS: [&str; 8] = [
    "{q}",
    "请用当前时间回答：{q}",
    "As of right now: {q}",
    "注意今天的日期再回答：{q}",
    "Given the current date, answer: {q}",
    "请结合环境时间回答：{q}",
    "Using the provided environment time, answer: {q}",
    "先确认时间再回答：{q}",
];

/// Fixed `now` anchors spread over two months for knowledge-boundary inputs.
const KB_NOWS: [&str; 20] = [
    "2026-06-15T10:00:00+08:00",
    "2026-06-18T10:00:00+08:00",
    "2026-06-22T10:00:00+08:00",
    "2026-06-25T10:00:00+08:00",
    "2026-06-29T10:00:00+08:00",
    "2026-07-01T10:00:00+08:00",
    "2026-07-06T10:00:00+08:00",
    "2026-07-08T10:00:00+08:00",
    "2026-07-13T10:00:00+08:00",
    "2026-07-15T10:00:00+08:00",
    "2026-07-20T10:00:00+08:00",
    "2026-07-22T10:00:00+08:00",
    "2026-07-27T10:00:00+08:00",
    "2026-07-29T10:00:00+08:00",
    "2026-08-03T10:00:00+08:00",
    "2026-08-05T10:00:00+08:00",
    "2026-08-10T10:00:00+08:00",
    "2026-08-12T10:00:00+08:00",
    "2026-08-17T10:00:00+08:00",
    "2026-08-19T10:00:00+08:00",
];

/// Fresh/stale `now` offsets (days) applied to entity validity windows.
const TG_FRESH_SHIFTS: [i64; 8] = [2, 5, 9, 14, 21, 45, 60, 120];
const TG_STALE_SHIFTS: [i64; 8] = [30, 60, 90, 120, 180, 270, 330, 365];

fn wrap(template_index: usize, query: &str) -> String {
    WRAPPERS[template_index % WRAPPERS.len()].replace("{q}", query)
}

/// Unique-input space per kind. Dataset ingest dedups by input hash, so the
/// generator never cycles: every emitted record is a distinct template
/// combination, and `plan_generation` rejects counts beyond the space.
pub(crate) fn kind_space(kind_index: usize) -> u64 {
    match kind_index {
        0 => 4_160,
        // KB: 4-cycle of 2 known + 1 unknown + 1 invented; bottleneck arm is
        // KNOWN_FACTS (14 x 6 wrappers x 20 dates = 1680) -> 4 x 840.
        1 => 3_360,
        _ => 2_560,
    }
}

/// Build the `index`-th scenario of one kind by mixed-radix enumeration over
/// entity x wrapper x condition x shift. Gold is constructed by rule.
fn scenario(kind_index: usize, index: u64) -> Scenario {
    match kind_index {
        0 => {
            // Cycle of 13: 6 fresh, 6 stale, 1 no-environment (matches the
            // 1920:1920:320 unique-space ratio).
            let cycle = index % 13;
            let n = index / 13;
            if cycle == 12 {
                let entity = &ENTITIES[(n as usize) % ENTITIES.len()];
                let template = ((n as usize) / ENTITIES.len()) % WRAPPERS.len();
                let query = wrap(
                    template,
                    if template.is_multiple_of(2) {
                        entity.query_zh
                    } else {
                        entity.query_en
                    },
                );
                return Scenario {
                    kind: MetaTaskKind::TemporalGrounding,
                    kind_name: "temporal_grounding",
                    input: json!({"query": query, "card": card_json(entity)}),
                    output: search(entity.search, None, None, 0.7),
                };
            }
            let m = (n * 6 + cycle / 2) as usize;
            let entity = &ENTITIES[m % ENTITIES.len()];
            let template = (m / ENTITIES.len()) % WRAPPERS.len();
            let shift = (m / (ENTITIES.len() * WRAPPERS.len())) % 8;
            let query = wrap(
                template,
                if template.is_multiple_of(2) {
                    entity.query_zh
                } else {
                    entity.query_en
                },
            );
            if cycle.is_multiple_of(2) {
                let now = parse_fixed(entity.observed_at)
                    + chrono::Duration::days(TG_FRESH_SHIFTS[shift]);
                Scenario {
                    kind: MetaTaskKind::TemporalGrounding,
                    kind_name: "temporal_grounding",
                    input: json!({"query": query, "environment": environment(Some(&now), entity.slug),
                               "card": card_json(entity)}),
                    output: answer(entity.claim, Some(&now), MetacognitionBasis::Evidence, 0.9),
                }
            } else {
                let now = parse_fixed(entity.valid_until)
                    + chrono::Duration::days(TG_STALE_SHIFTS[shift]);
                Scenario {
                    kind: MetaTaskKind::TemporalGrounding,
                    kind_name: "temporal_grounding",
                    input: json!({"query": query, "environment": environment(Some(&now), entity.slug),
                               "card": card_json(entity)}),
                    output: search(
                        entity.search,
                        Some(&now),
                        Some(freshness_hours(entity.valid_until, &now)),
                        0.8,
                    ),
                }
            }
        }
        1 => {
            // Cycle of 4: 2 known, 1 unknown (post-cutoff), 1 invented.
            let cycle = index % 4;
            let n = (index / 4) as usize;
            let (base_query, gold_kind) = match cycle {
                0 | 1 => {
                    let m = n * 2 + cycle as usize;
                    let (_slug, query, fact) = KNOWN_FACTS[m % KNOWN_FACTS.len()];
                    let wrapper = (m / KNOWN_FACTS.len()) % 6;
                    let date = (m / (KNOWN_FACTS.len() * 6)) % KB_NOWS.len();
                    let now = parse_fixed(KB_NOWS[date]);
                    return Scenario {
                        kind: MetaTaskKind::KnowledgeBoundary,
                        kind_name: "knowledge_boundary",
                        input: json!({"query": wrap(wrapper, query),
                                   "environment": environment(Some(&now), "kb")}),
                        output: answer(fact, Some(&now), MetacognitionBasis::Parametric, 0.85),
                    };
                }
                2 => {
                    let (_slug, query) = UNKNOWN_FACTS[n % UNKNOWN_FACTS.len()];
                    (query, "search")
                }
                _ => (INVENTED_FACTS[n % INVENTED_FACTS.len()], "insufficient"),
            };
            let pool = match cycle {
                2 => UNKNOWN_FACTS.len(),
                _ => INVENTED_FACTS.len(),
            };
            let wrapper = (n / pool) % 6;
            let date = (n / (pool * 6)) % KB_NOWS.len();
            let now = parse_fixed(KB_NOWS[date]);
            let output = if gold_kind == "search" {
                search(base_query, Some(&now), None, 0.75)
            } else {
                insufficient(Some(&now), 0.8)
            };
            Scenario {
                kind: MetaTaskKind::KnowledgeBoundary,
                kind_name: "knowledge_boundary",
                input: json!({"query": wrap(wrapper, base_query),
                           "environment": environment(Some(&now), "kb")}),
                output,
            }
        }
        _ => {
            // Cycle of 4: fresh, stale, contested, empty; two score variants.
            let condition = index % 4;
            let n = (index / 4) as usize;
            let entity = &ENTITIES[n % ENTITIES.len()];
            let template = (n / ENTITIES.len()) % WRAPPERS.len();
            let variant = (n / (ENTITIES.len() * WRAPPERS.len())) % 2;
            let query = wrap(
                template,
                if template.is_multiple_of(2) {
                    entity.query_zh
                } else {
                    entity.query_en
                },
            );
            let score_hi = if variant == 0 { 0.91 } else { 0.87 };
            let score_lo = if variant == 0 { 0.79 } else { 0.75 };
            let contested_now = Utc
                .with_ymd_and_hms(2026, 9, 1, 10, 0, 0)
                .single()
                .expect("fixed");
            let fresh_card = json!([{
                "title": entity.slug, "claim": entity.claim,
                "observed_at": entity.observed_at, "valid_until": entity.valid_until,
                "status": "corroborated", "score": score_hi,
            }]);
            // `now` moves per condition and variant: fresh presents the card
            // inside its validity window, stale past it; inputs never collide.
            let (now, retrieval, output) = match condition {
                0 => {
                    let now = parse_fixed(entity.observed_at)
                        + chrono::Duration::days(5 + 2 * variant as i64);
                    (
                        now,
                        json!({"result_count": 1, "results": fresh_card}),
                        answer(entity.claim, Some(&now), MetacognitionBasis::Evidence, 0.9),
                    )
                }
                1 => {
                    let now = parse_fixed(entity.valid_until)
                        + chrono::Duration::days(30 + 15 * variant as i64);
                    (
                        now,
                        json!({"result_count": 1, "results": [{
                            "title": entity.slug, "claim": entity.claim,
                            "observed_at": entity.observed_at, "valid_until": entity.valid_until,
                            "status": "corroborated", "score": score_hi,
                        }]}),
                        search(
                            entity.search,
                            Some(&now),
                            Some(freshness_hours(entity.valid_until, &now)),
                            0.8,
                        ),
                    )
                }
                2 => (
                    contested_now,
                    json!({"result_count": 2, "results": [
                        {"title": entity.slug, "claim": entity.claim,
                         "observed_at": entity.observed_at, "valid_until": entity.valid_until,
                         "status": "contested", "score": score_hi},
                        {"title": entity.slug, "claim": "（冲突说法）",
                         "observed_at": entity.observed_at, "valid_until": entity.valid_until,
                         "status": "contested", "score": score_lo},
                    ]}),
                    acquire(entity.search, Some(&contested_now), 72, 0.75),
                ),
                _ => {
                    let now = contested_now + chrono::Duration::days(7 * variant as i64);
                    (
                        now,
                        json!({"result_count": 0, "results": []}),
                        search(entity.search, Some(&now), None, 0.7),
                    )
                }
            };
            Scenario {
                kind: MetaTaskKind::SearchPlanning,
                kind_name: "search_planning",
                input: json!({"query": query, "environment": environment(Some(&now), entity.slug),
                             "retrieval": retrieval}),
                output,
            }
        }
    }
}

pub(crate) struct GenerationPlan {
    pub traces: Vec<MetaDecisionTrace>,
    pub replays: Vec<MetaReplayEvaluation>,
    pub trace_split_counts: [u64; 3],
    pub replay_split_counts: [u64; 3],
}

/// Pure, deterministic plan for `--count N`: N traces per kind plus
/// ceil(N/4) replays per kind (40% placed in validation/holdout groups).
pub(crate) fn plan_generation(count: u64) -> Result<GenerationPlan> {
    if count == 0 {
        bail!("count must be positive");
    }
    for kind_index in 0..3 {
        if count > kind_space(kind_index) {
            bail!(
                "count {count} exceeds the unique-input space {} for kind {kind_index}",
                kind_space(kind_index)
            );
        }
    }
    let kind_names = [
        "temporal_grounding",
        "knowledge_boundary",
        "search_planning",
    ];
    let mut traces = Vec::with_capacity((3 * count) as usize);
    let mut trace_split_counts = [0_u64; 3];
    for kind_index in 0..3 {
        for index in 0..count {
            let scenario = scenario(kind_index, index);
            let cluster = (index as u32) % TRACE_CLUSTERS;
            let month = TRACE_MONTHS[((index as u32 / TRACE_CLUSTERS) % 3) as usize];
            let family = trace_family(scenario.kind_name, cluster);
            let split = group_split(&family, month);
            trace_split_counts[split_bucket(split)] += 1;
            let created = ts(month, index as u32, (index as u32) * 7);
            let input = scenario.input;
            let input_hash = canonical_json_hash(&input);
            traces.push(MetaDecisionTrace {
                schema_version: SCHEMA_VERSION.into(),
                decision_id: stable_uuid(&format!("metacognition:{}:{index}", scenario.kind_name)),
                task_kind: scenario.kind,
                input_hash,
                input,
                output: decision_json(scenario.output),
                source_domain: METACOGNITION_SOURCE_DOMAIN.into(),
                topic_family: family,
                policy_version: METACOGNITION_POLICY_VERSION.into(),
                controller_version: METACOGNITION_POLICY_VERSION.into(),
                confidence: 0.9,
                cost: 0.0,
                useful: true,
                training_eligible: true,
                policy_violations: 0,
                prompt_injection_detected: false,
                data_classification: Default::default(),
                external_processing: Default::default(),
                redaction_attestation_hash: None,
                created_at: created,
            });
        }
    }

    let replay_per_kind = count / 4 + u64::from(!count.is_multiple_of(4));
    let mut replays = Vec::with_capacity((3 * replay_per_kind) as usize);
    let mut replay_split_counts = [0_u64; 3];
    for (kind_index, kind_name) in kind_names.iter().enumerate() {
        let keyword = ROUTING_KEYWORDS[kind_index];
        // Precompute replay groups by landing split: placement order is
        // validation 40%, holdout 40%, train 20% of each kind's replays.
        let mut by_split: [Vec<String>; 3] = [vec![], vec![], vec![]];
        for slot in 0..200_u32 {
            let family = replay_family(kind_name, slot);
            by_split[split_bucket(group_split(&family, REPLAY_MONTH))].push(family);
        }
        for index in 0..replay_per_kind {
            let target = match index % 5 {
                0 | 1 => 1_usize, // validation
                2 | 3 => 2,       // holdout
                _ => 0,           // train
            };
            let bucket = &by_split[target];
            if bucket.is_empty() {
                bail!("no replay group lands in split {target} for {kind_name}");
            }
            let family = &bucket[(index as usize / 5) % bucket.len()];
            replay_split_counts[target] += 1;
            let baseline = 0.50 + (index % 10) as f64 * 0.01;
            replays.push(MetaReplayEvaluation {
                schema_version: SCHEMA_VERSION.into(),
                evaluation_id: stable_uuid(&format!("metacognition-replay:{kind_name}:{index}")),
                candidate_id: None,
                task_id: format!("metacognition-{keyword}-{kind_name}-replay-{index:05}"),
                source_domain: METACOGNITION_SOURCE_DOMAIN.into(),
                topic_family: family.clone(),
                baseline_score: baseline,
                candidate_score: (baseline + 0.10).min(1.0),
                fact_correct: true,
                safety_passed: true,
                data_classification: Default::default(),
                external_processing: Default::default(),
                redaction_attestation_hash: None,
                created_at: ts(REPLAY_MONTH, index as u32, (index as u32) * 11),
            });
        }
    }
    Ok(GenerationPlan {
        traces,
        replays,
        trace_split_counts,
        replay_split_counts,
    })
}

/// `cerebellum simulate-metacognition`: insert one deterministic plan.
pub fn simulate_metacognition(registry: &Registry, count: u64) -> Result<Value> {
    let plan = plan_generation(count)?;
    let mut inserted_traces = 0_u64;
    for trace in &plan.traces {
        inserted_traces += u64::from(registry.record_meta_decision(trace)?);
    }
    let mut inserted_replays = 0_u64;
    for replay in &plan.replays {
        inserted_replays += u64::from(registry.record_meta_replay(replay)?);
    }
    Ok(json!({
        "simulated": count,
        "traces": plan.traces.len(),
        "replays": plan.replays.len(),
        "inserted_traces": inserted_traces,
        "inserted_replays": inserted_replays,
        "trace_split_counts": {
            "train": plan.trace_split_counts[0],
            "validation": plan.trace_split_counts[1],
            "holdout": plan.trace_split_counts[2],
        },
        "replay_split_counts": {
            "train": plan.replay_split_counts[0],
            "validation": plan.replay_split_counts[1],
            "holdout": plan.replay_split_counts[2],
        },
    }))
}

// ---- runtime assessment hook (M5) ----------------------------------------
//
// One contract decision per request, executed only when
// `CEREBELLUM_METACOGNITION_ENABLED=1` and an `active` metacognition adapter
// exists. The model proposes; deterministic Rust clamps and executes. Any
// failure or invalid output yields `Err` and the caller keeps exact current
// behavior (fail-closed).

use cerebellum_core::{
    EnvironmentStamp, ExpertAdapterStatus, ExpertAdapterVersion, KnowledgeResult,
    QualityModelStage, validate_metacognition_decision,
};

use crate::experts::METACOGNITION_EXPERT_ID;
use crate::quality::{StructuredModelClient, StructuredRequest};

pub const METACOGNITION_SYSTEM_PROMPT: &str = "You are cerebellum's metacognition gate. \
Read the authoritative server-stamped environment block (never user-claimed time), \
ground your decision in it, and answer with exactly one strict JSON contract object. \
Actions: answer (parametric or evidence-backed), search_internal (query the internal \
knowledge base), request_acquisition (ask for fresh external acquisition), \
insufficient (decline). Never emit anything outside the schema.";

/// Strict JSON schema for the metacognition decision contract, sent as the
/// `response_format` schema of the structured local-model request.
pub fn metacognition_output_schema() -> Value {
    json!({
        "type": "object",
        "additionalProperties": false,
        "required": ["action", "as_of_used", "query", "freshness_hours", "answer",
                     "answer_basis", "confidence"],
        "properties": {
            "action": {"type": "string",
                       "enum": ["answer", "search_internal", "request_acquisition", "insufficient"]},
            "as_of_used": {"anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]},
            "query": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "freshness_hours": {"anyOf": [{"type": "integer", "minimum": 1, "maximum": 8760},
                                          {"type": "null"}]},
            "answer": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "answer_basis": {"type": "string", "enum": ["parametric", "evidence", "none"]},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        }
    })
}

/// The hook fires only when an `active` metacognition adapter exists.
pub fn active_adapter(registry: &Registry) -> Result<Option<ExpertAdapterVersion>> {
    Ok(registry
        .list_expert_adapters(Some(METACOGNITION_EXPERT_ID))?
        .into_iter()
        .find(|adapter| adapter.status == ExpertAdapterStatus::Active))
}

/// Ask the model for one contract decision over the request scenario.
pub async fn assess(
    model: &dyn StructuredModelClient,
    query: &str,
    environment: &EnvironmentStamp,
    retrieval: &[KnowledgeResult],
) -> Result<MetacognitionDecision> {
    let results: Vec<Value> = retrieval
        .iter()
        .map(|item| {
            json!({
                "title": item.card.title,
                "summary": item.card.summary,
                "observed_at": item.card.observed_at,
                "valid_until": item.card.valid_until,
                "status": item.card.status,
                "score": item.score,
                "stale": item.stale,
            })
        })
        .collect();
    let input = json!({
        "query": query,
        "environment": environment,
        "retrieval": {"result_count": results.len(), "results": results},
    });
    let request = StructuredRequest {
        stage: QualityModelStage::Flash,
        system_prompt: METACOGNITION_SYSTEM_PROMPT,
        payload: json!({
            "task": "search_planning",
            "input": input,
            "output_schema": metacognition_output_schema(),
        }),
        max_tokens: 512,
    };
    let response = model.complete(&request).await?;
    let decision: MetacognitionDecision = serde_json::from_value(response.value)?;
    validate_metacognition_decision(&decision)?;
    Ok(decision)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::experts::{METACOGNITION_EXPERT_ID, task_expert};
    use cerebellum_core::{validate_meta_decision_trace, validate_meta_replay_evaluation};
    use tempfile::tempdir;

    #[test]
    fn metacognition_kinds_route_to_the_metacognition_expert() {
        for kind in [
            MetaTaskKind::TemporalGrounding,
            MetaTaskKind::KnowledgeBoundary,
            MetaTaskKind::SearchPlanning,
        ] {
            assert_eq!(task_expert(kind), METACOGNITION_EXPERT_ID);
        }
    }

    #[test]
    fn generated_records_pass_fail_closed_validation() {
        let plan = plan_generation(20).expect("plan");
        for trace in &plan.traces {
            validate_meta_decision_trace(trace).expect("trace valid");
        }
        for replay in &plan.replays {
            validate_meta_replay_evaluation(replay).expect("replay valid");
        }
        assert_eq!(plan.traces.len(), 60);
        assert_eq!(plan.replays.len(), 15);
    }

    #[test]
    fn generated_gold_echoes_environment_time_exactly() {
        let plan = plan_generation(2_500).expect("plan");
        for trace in &plan.traces {
            let now = trace
                .input
                .pointer("/environment/now")
                .cloned()
                .unwrap_or(Value::Null);
            assert_eq!(
                trace.output["as_of_used"], now,
                "time echo differs for {}",
                trace.decision_id
            );
        }
    }

    #[test]
    fn invalid_contract_outputs_are_rejected() {
        let plan = plan_generation(1).expect("plan");
        let mut trace = plan.traces[0].clone();
        trace.output = json!({"action": "answer", "answer": null});
        assert!(validate_meta_decision_trace(&trace).is_err());
        let mut missing_query = plan.traces[0].clone();
        missing_query.task_kind = MetaTaskKind::SearchPlanning;
        missing_query.output = decision_json(search("q", None, None, 0.8));
        let mut value = missing_query.output.clone();
        value["query"] = Value::Null;
        missing_query.output = value;
        assert!(validate_meta_decision_trace(&missing_query).is_err());
    }

    #[test]
    fn generation_is_deterministic() {
        let left = plan_generation(40).expect("plan");
        let right = plan_generation(40).expect("plan");
        let hashes = |plan: &GenerationPlan| -> Vec<String> {
            plan.traces
                .iter()
                .map(|trace| canonical_json_hash(&serde_json::to_value(trace).unwrap()))
                .chain(
                    plan.replays
                        .iter()
                        .map(|replay| canonical_json_hash(&serde_json::to_value(replay).unwrap())),
                )
                .collect()
        };
        assert_eq!(hashes(&left), hashes(&right));
    }

    #[test]
    fn default_volume_clears_every_gate() {
        let plan = plan_generation(2_500).expect("plan");
        // Dataset ingest dedups by (task_kind, input_hash): every planned
        // trace must be a unique input.
        let unique: std::collections::BTreeSet<(String, &str)> = plan
            .traces
            .iter()
            .map(|trace| (format!("{:?}", trace.task_kind), trace.input_hash.as_str()))
            .collect();
        assert_eq!(unique.len(), plan.traces.len(), "duplicate inputs planned");
        let train_traces = plan.trace_split_counts[0];
        assert!(
            train_traces >= crate::experts::MIN_ROUTER_TRAIN_RECORDS,
            "router train {train_traces} below {}",
            crate::experts::MIN_ROUTER_TRAIN_RECORDS
        );
        let evaluation_replays = plan.replay_split_counts[1] + plan.replay_split_counts[2];
        assert!(
            evaluation_replays >= crate::experts::MIN_EXPERT_REPLAY_RECORDS,
            "evaluation replays {evaluation_replays} below {}",
            crate::experts::MIN_EXPERT_REPLAY_RECORDS
        );
        assert!(plan.traces.len() >= crate::meta_training::MIN_META_DECISIONS);
        assert!(plan.replays.len() >= crate::meta_training::MIN_META_REPLAYS);
    }

    #[test]
    fn simulate_inserts_into_a_fresh_registry_deterministically() {
        let left_dir = tempdir().unwrap();
        let right_dir = tempdir().unwrap();
        let left = simulate_metacognition(&Registry::open(left_dir.path()).unwrap(), 30).unwrap();
        let right = simulate_metacognition(&Registry::open(right_dir.path()).unwrap(), 30).unwrap();
        assert_eq!(left["inserted_traces"], json!(90));
        assert_eq!(left["inserted_replays"], json!(24));
        // Re-running on the same registry dedups instead of duplicating.
        let registry = Registry::open(left_dir.path()).unwrap();
        let again = simulate_metacognition(&registry, 30).unwrap();
        assert_eq!(again["inserted_traces"], json!(0));
        assert_eq!(again["inserted_replays"], json!(0));
        drop(right);
    }
}
