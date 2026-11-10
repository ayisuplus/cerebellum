"""Search routing configuration — language packs for auto strategy selection."""
import os
from dataclasses import dataclass, field


@dataclass
class RoutingConfig:
    """Configuration for search strategy routing."""
    lang: str = "zh"
    default_strategy: str = "auto"
    time_keywords_zh: list[str] = field(default_factory=lambda: ["时间", "日期", "最近", "今天", "昨天"])
    time_keywords_en: list[str] = field(default_factory=lambda: ["time", "date", "recent", "today", "yesterday"])
    fact_keywords_zh: list[str] = field(default_factory=lambda: ["是什么", "定义", "含义", "为什么"])
    fact_keywords_en: list[str] = field(default_factory=lambda: ["what is", "definition", "meaning", "why"])
    time_keywords_ja: list[str] = field(default_factory=lambda: ["時間", "日付", "最近", "今日", "昨日"])
    fact_keywords_ja: list[str] = field(default_factory=lambda: ["とは", "定義", "意味", "なぜ"])
    time_keywords_ko: list[str] = field(default_factory=lambda: ["시간", "날짜", "최근", "오늘", "어제"])
    fact_keywords_ko: list[str] = field(default_factory=lambda: ["정의", "의미", "왜"])
    time_keywords_de: list[str] = field(default_factory=lambda: ["zeit", "datum", "heute", "gestern"])
    fact_keywords_de: list[str] = field(default_factory=lambda: ["was ist", "definition", "bedeutung", "warum"])

    @classmethod
    def from_env(cls) -> "RoutingConfig":
        lang = os.environ.get("EVOLVER_SEARCH_LANG", "zh")
        return cls(lang=lang)

    def get_time_keywords(self) -> list[str]:
        return getattr(self, f"time_keywords_{self.lang}", self.time_keywords_en)

    def get_fact_keywords(self) -> list[str]:
        return getattr(self, f"fact_keywords_{self.lang}", self.fact_keywords_en)


DEFAULT_ROUTING_CONFIG = {
    "zh": RoutingConfig(lang="zh"),
    "en": RoutingConfig(lang="en"),
    "ja": RoutingConfig(lang="ja"),
    "ko": RoutingConfig(lang="ko"),
    "de": RoutingConfig(lang="de"),
}
