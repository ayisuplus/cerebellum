from __future__ import annotations

import unittest

from cerebellum_social_acquisition.event_cluster import assign_cluster_ids, cluster_events
from cerebellum_social_acquisition.platforms.base import BoardItem


def item(title: str, platform: str, heat: int = 1000) -> BoardItem:
    return BoardItem(
        external_id=f"{platform}-{abs(hash(title)) % 1000}",
        title=title,
        url=f"https://{platform}.example/t/{abs(hash(title)) % 1000}",
        heat=heat,
        platform=platform,
    )


class EventClusterTests(unittest.TestCase):
    def test_cross_platform_event_gets_cluster_id(self) -> None:
        items = [
            item("某新模型正式发布引发热议", "weibo", 5000),
            item("如何看待某新模型正式发布", "zhihu", 3000),
            item("完全无关的另一条新闻", "weibo", 100),
        ]
        assign_cluster_ids(items)
        self.assertIn("cluster_id", items[0].extra)
        self.assertIn("cluster_id", items[1].extra)
        self.assertEqual(items[0].extra["cluster_id"], items[1].extra["cluster_id"])
        self.assertTrue(items[0].extra["cross_platform"])
        self.assertIn("weibo", items[0].extra["cluster_platforms"])
        self.assertIn("zhihu", items[0].extra["cluster_platforms"])
        self.assertNotIn("cluster_id", items[2].extra)

    def test_single_platform_batch_never_clusters(self) -> None:
        items = [
            item("某新模型正式发布引发热议", "weibo", 5000),
            item("如何看待某新模型正式发布", "weibo", 3000),
        ]
        assign_cluster_ids(items)
        self.assertNotIn("cluster_id", items[0].extra)
        self.assertNotIn("cluster_id", items[1].extra)

    def test_cluster_events_core_algorithm(self) -> None:
        posts = [
            {"post_id": "a", "platform": "weibo", "title": "某品牌新机发布会", "content": "", "url": "https://a", "like_count": 10_000, "comment_count": 0, "share_count": 0, "create_time": ""},
            {"post_id": "b", "platform": "douyin", "title": "某品牌新机发布会直播", "content": "", "url": "https://b", "like_count": 5_000, "comment_count": 0, "share_count": 0, "create_time": ""},
        ]
        events = cluster_events(posts)
        cross = [event for event in events if event.isCrossPlatform]
        self.assertEqual(len(cross), 1)
        self.assertEqual(set(cross[0].platform_codes), {"weibo", "douyin"})
        self.assertGreater(cross[0].heatIndex, 0)


if __name__ == "__main__":
    unittest.main()
