"""Platform discovery provider registry (hot boards)."""

from __future__ import annotations

from .baidu import BaiduProvider
from .bilibili import BilibiliProvider
from .douyin import DouyinProvider
from .kuaishou import KuaishouProvider
from .tieba import TiebaProvider
from .weibo import WeiboProvider
from .xhs import XhsProvider
from .zhihu import ZhihuProvider

BOARD_PROVIDERS = {
    provider.kind: provider
    for provider in (
        WeiboProvider(),
        ZhihuProvider(),
        DouyinProvider(),
        BilibiliProvider(),
        XhsProvider(),
        BaiduProvider(),
        KuaishouProvider(),
        TiebaProvider(),
    )
}

__all__ = ["BOARD_PROVIDERS"]
