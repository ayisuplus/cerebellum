"""跨平台话题聚类

将不同平台上讨论同一现实事件的帖子聚成一个"事件簇"。
仅当某话题出现在 ≥2 个平台时，才判定为「跨平台爆发事件」。

算法流程：
1. 标题归一化：剥离问句前缀（如何看待/如何评价/为什么…），去除标点表情。
2. 特征提取：中文二元组（bigram）+ ASCII 词，构成话题指纹集合。
3. 相似度：Jaccard 与包含度（containment）的组合，兼顾长短标题。
4. 贪心聚类：每个帖子归入与之最相似的已有簇，否则新建簇。
5. 聚合输出：平台集合、跨平台标记、聚合热度、各平台代表来源链接。
"""

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# 平台代码 → 中文名（与 api_server 保持一致）
_PLATFORM_CODE_TO_NAME = {
    "weibo": "微博", "zhihu": "知乎", "douyin": "抖音",
    "bilibili": "B站", "xhs": "小红书", "tieba": "贴吧",
    "kuaishou": "快手", "baidu": "百度",
}

# 问句/引导前缀：剥离后让「如何看待X」与「X」可被聚到一起
_QUESTION_PREFIXES = (
    "如何看待", "如何评价", "怎么看", "怎么评价", "怎么样",
    "为什么", "为啥", "啥是", "什么是", "请问", "怎样看待",
    "如何理解", "怎么看待", "大家觉得", "有没有", "是否",
)

# 归一化：仅保留 CJK、ASCII 字母与数字
_CLEAN_RE = re.compile(r"[^\u4e00-\u9fff\u3400-\u4dbfa-zA-Z0-9]+")
_ASCII_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]{1,}")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")

# 无意义高频停用二元组（平台名/通用词），避免它们制造虚假相似
_STOPWORD_BIGRAMS = {
    "如何", "何看", "看待", "如何", "评价", "为什", "什么", "大家",
    "我们", "他们", "这个", "那个", "一个", "就是", "可以", "因为",
    "所以", "但是", "而且", "或者", "如果", "虽然", "已经", "现在",
    "今天", "昨天", "明天", "时候", "问题", "事情", "情况", "相关",
}


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF


def _normalize_title(title: str) -> str:
    """剥离问句前缀并去除标点表情，得到用于特征提取的纯文本"""
    if not title:
        return ""
    text = title.strip()
    # 反复剥离前缀（可能叠加：如何看待为什么…）
    changed = True
    while changed:
        changed = False
        for prefix in _QUESTION_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip("，。,.：:？? ")
                changed = True
    # 去除标点、表情、空白
    text = _CLEAN_RE.sub("", text)
    return text.lower()


def extract_features(title: str) -> Set[str]:
    """从标题提取话题指纹：中文二元组 + ASCII 词"""
    norm = _normalize_title(title)
    if not norm:
        return set()

    features: Set[str] = set()

    # 中文二元组（在每段连续 CJK 内滑窗取 2-gram）
    for run in _CJK_RUN_RE.findall(norm):
        if len(run) == 1:
            features.add(run)  # 单字也保留，避免极短标题无特征
        else:
            for i in range(len(run) - 1):
                bg = run[i:i + 2]
                if bg not in _STOPWORD_BIGRAMS:
                    features.add(bg)

    # ASCII 词（品牌/人名/缩写，如 AI、BLG、Faker）
    for word in _ASCII_WORD_RE.findall(norm):
        features.add(word.lower())

    return features


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _containment(a: Set[str], b: Set[str]) -> float:
    """包含度：交集占较小集合的比例，捕捉「短标题 ⊂ 长标题」"""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    smaller = min(len(a), len(b))
    return inter / smaller if smaller else 0.0


def _similarity(a: Set[str], b: Set[str]) -> float:
    """组合相似度：Jaccard 与包含度取较优者（包含度略降权防过松）"""
    return max(_jaccard(a, b), _containment(a, b) * 0.85)


def _compute_heat(like: int, comment: int, share: int) -> float:
    """对数热度公式（与 api_server 一致，跨平台可比）"""
    raw = (like or 0) + (comment or 0) * 2 + (share or 0) * 3
    if raw > 0:
        return min(10.0, max(0.5, round(math.log10(raw + 10) * 1.3, 1)))
    return 0.5


@dataclass
class ClusteredEvent:
    """聚类后的事件簇"""
    id: str
    title: str                       # 代表标题（热度最高成员）
    description: str
    platforms: List[str]             # 中文平台名（去重）
    platform_codes: List[str]        # 平台代码（去重）
    heatIndex: float
    isCrossPlatform: bool            # 出现在 ≥2 个平台
    time: str
    sourceLinks: List[Dict[str, str]] = field(default_factory=list)
    postCount: int = 0
    tags: List[str] = field(default_factory=list)
    # cerebellum worker glue 用：簇成员帖子字典（算法本身不读）
    members: List[Dict[str, Any]] = field(default_factory=list)


def cluster_events(
    posts: List[Dict[str, Any]],
    threshold: float = 0.35,
    min_cluster_size: int = 1,
) -> List[ClusteredEvent]:
    """对帖子列表做跨平台话题聚类

    Args:
        posts: 帖子字典列表（含 title/platform/like_count/url 等字段）
        threshold: 聚类相似度阈值
        min_cluster_size: 输出的最小簇成员数（默认 1，即保留所有簇）

    Returns:
        按聚合热度降序排列的 ClusteredEvent 列表
    """
    # 预计算每个帖子的特征与热度
    enriched: List[Dict[str, Any]] = []
    for post in posts:
        title = post.get("title", "") or post.get("content", "")[:60]
        if not title:
            continue
        feats = extract_features(title)
        if not feats:
            continue
        heat = _compute_heat(
            post.get("like_count", 0),
            post.get("comment_count", 0),
            post.get("share_count", 0),
        )
        enriched.append({
            "post": post,
            "title": title,
            "features": feats,
            "heat": heat,
            "platform_code": post.get("platform", ""),
        })

    # ---- 稀有实体指纹：低频但共享的词是强话题信号（如"耐克"只在耐克相关标题出现）----
    # 统计每个特征出现在多少个帖子里（文档频率）
    doc_freq: Dict[str, int] = {}
    for item in enriched:
        for feat in item["features"]:
            doc_freq[feat] = doc_freq.get(feat, 0) + 1
    n_docs = len(enriched)
    # 稀有特征：出现次数 ≤3 且占比 <50%（排除"今天""网友"等高频通用词）
    _rare: Set[str] = {
        f for f, c in doc_freq.items()
        if c <= 3 and c < max(2, n_docs * 0.5)
    }
    for item in enriched:
        item["rare"] = item["features"] & _rare

    # 贪心聚类：每个帖子归入与之最相似的已有簇
    clusters: List[List[Dict[str, Any]]] = []
    for item in enriched:
        best_idx = -1
        best_sim = 0.0
        best_rare = 0
        for idx, cluster in enumerate(clusters):
            # 与簇内每个成员比较，取最大相似度（短标题场景下更鲁棒）
            for member in cluster:
                sim = _similarity(item["features"], member["features"])
                shared_rare = len(item["rare"] & member["rare"])
                # 共享稀有实体（≥1个低频词）→ 强烈话题信号，直接聚合
                if shared_rare > best_rare or (shared_rare == best_rare and sim > best_sim):
                    best_rare = shared_rare
                    best_sim = sim
                    best_idx = idx
        # 聚合判据（修复：防止无关帖子被强行合并）：
        # 1. 相似度达阈值 → 直接聚合
        # 2. 共享稀有实体 → 需最低相似度门槛 0.15（防偶然共享低频词强行合并）
        #    且与簇代表也需有基本相似度 0.10（防 A→B→C 传递性链式污染）
        if best_sim >= threshold and best_idx >= 0:
            clusters[best_idx].append(item)
        elif best_rare >= 1 and best_sim >= 0.15 and best_idx >= 0:
            rep = max(clusters[best_idx], key=lambda x: x["heat"])
            rep_sim = _similarity(item["features"], rep["features"])
            if rep_sim >= 0.10:
                clusters[best_idx].append(item)
            else:
                clusters.append([item])
        else:
            clusters.append([item])

    # 聚合每个簇为 ClusteredEvent
    events: List[ClusteredEvent] = []
    for cluster in clusters:
        if len(cluster) < min_cluster_size:
            continue

        # 代表成员：热度最高者
        representative = max(cluster, key=lambda x: x["heat"])

        # 平台集合（去重，保留首次出现顺序）
        platform_codes: List[str] = []
        platform_names: List[str] = []
        for member in cluster:
            code = member["platform_code"]
            if code and code not in platform_codes:
                platform_codes.append(code)
                platform_names.append(
                    _PLATFORM_CODE_TO_NAME.get(code, code)
                )

        # 各平台代表来源链接（每平台取热度最高成员）
        best_per_platform: Dict[str, Dict[str, Any]] = {}
        for member in cluster:
            code = member["platform_code"]
            if code not in best_per_platform or member["heat"] > best_per_platform[code]["heat"]:
                best_per_platform[code] = member

        source_links: List[Dict[str, str]] = []
        for code, member in best_per_platform.items():
            p = member["post"]
            url = p.get("url", "") or p.get("source_url", "") or p.get("detail_url", "")
            source_links.append({
                "platform": _PLATFORM_CODE_TO_NAME.get(code, code),
                "title": member["title"],
                "url": url,
                "author": p.get("author", ""),
                "time": p.get("create_time", "") or p.get("created_at", ""),
            })

        # 聚合热度：以代表热度为基础，跨平台传播给予适度加成
        base_heat = representative["heat"]
        spread_bonus = 0.3 * (len(platform_codes) - 1)
        agg_heat = min(10.0, round(base_heat + spread_bonus, 1))

        is_cross = len(platform_codes) >= 2

        events.append(ClusteredEvent(
            id=str(representative["post"].get("post_id", representative["post"].get("id", ""))),
            title=representative["title"],
            description=(representative["post"].get("content", "") or representative["title"])[:200],
            platforms=platform_names,
            platform_codes=platform_codes,
            heatIndex=agg_heat,
            isCrossPlatform=is_cross,
            time=representative["post"].get("create_time", "") or representative["post"].get("created_at", ""),
            sourceLinks=source_links,
            postCount=len(cluster),
            tags=[],
            members=[member["post"] for member in cluster],
        ))

    # 按聚合热度降序
    events.sort(key=lambda e: e.heatIndex, reverse=True)
    return events

# ---------------------------------------------------------------------------
# cerebellum worker glue：BoardItem 批次 → 跨平台 cluster_id 扩展字段
# ---------------------------------------------------------------------------

def assign_cluster_ids(items: list, threshold: float = 0.35) -> list:
    """跨平台事件聚类 enrichment（可选，不改控制面契约）。

    同批次内出现在 ≥2 个平台（BoardItem.platform 不同）的相似条目
    打同一个 cluster_id（写进 item.extra["cluster_id"]）并标记
    extra["cross_platform"]=True；单平台批天然不产生 cluster_id。
    返回原列表（就地更新 extra）。
    """
    posts = []
    for index, item in enumerate(items):
        posts.append(
            {
                "post_id": str(index),
                "platform": getattr(item, "platform", "") or "",
                "title": getattr(item, "title", "") or "",
                "content": getattr(item, "summary", None) or getattr(item, "title", "") or "",
                "url": getattr(item, "url", "") or "",
                "author": getattr(item, "author", None) or "",
                "like_count": getattr(item, "heat", 0) or 0,
                "comment_count": 0,
                "share_count": 0,
                "create_time": getattr(item, "published_at", None) or "",
            }
        )
    for cluster_seq, event in enumerate(cluster_events(posts, threshold=threshold), 1):
        if not event.isCrossPlatform:
            continue
        cluster_id = f"cluster-{cluster_seq}-{event.id or 'event'}"
        member_indexes = {
            int(member["post_id"])
            for member in event.members
            if str(member.get("post_id", "")).isdigit()
        }
        for index in member_indexes:
            items[index].extra["cluster_id"] = cluster_id
            items[index].extra["cross_platform"] = True
            items[index].extra["cluster_platforms"] = list(event.platform_codes)
    return items
