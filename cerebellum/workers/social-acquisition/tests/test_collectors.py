from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_social_acquisition.collectors import arxiv, journal, openalex
from cerebellum_social_acquisition.policy import PolicyError

FIXTURES = Path(__file__).parent / "fixtures"


class CollectorParseTests(unittest.TestCase):
    def test_openalex_works(self) -> None:
        data = json.loads((FIXTURES / "openalex_works.json").read_text(encoding="utf-8"))
        items = openalex.parse_works(data, 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "A foundation model for continual learning")
        self.assertEqual(first.external_id, "10.1038/s41586-026-00001-x")
        self.assertEqual(first.url, "https://doi.org/10.1038/s41586-026-00001-x")
        self.assertEqual(first.summary, "Continual learning remains challenging.")
        self.assertEqual(first.author, "Alice Zhang, Bob Li")
        self.assertEqual(first.heat, 42)
        self.assertEqual(first.extra["venue"], "Nature")
        self.assertEqual(first.published_at, "2026-08-01T00:00:00Z")
        # 无 DOI 时回退 openalex 伪 DOI 与 openalex URL
        second = items[1]
        self.assertEqual(second.external_id, "openalex:W222")
        self.assertEqual(second.url, "https://openalex.org/W222")
        self.assertIsNone(second.summary)

    def test_openalex_query_builder(self) -> None:
        query = openalex.build_query(50, mailto="bot@example.org")
        self.assertIn("per_page=50", query)
        self.assertIn("cursor=%2A", query)
        self.assertIn("mailto=bot%40example.org", query)
        self.assertIn("publication_year%3A2024", query)

    def test_openalex_token_bucket_limits(self) -> None:
        bucket = openalex.TokenBucket(rate=100.0, burst=1)
        bucket.acquire()
        started = time.monotonic()
        bucket.acquire()
        self.assertGreaterEqual(time.monotonic() - started, 0.005)

    def test_arxiv_atom_feed(self) -> None:
        xml_text = (FIXTURES / "arxiv_feed.xml").read_text(encoding="utf-8")
        items = arxiv.parse_atom_feed(xml_text, "cs.AI", 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "Self-Evolving Agents with Dataset Flywheels")
        self.assertEqual(first.external_id, "arxiv:2608.12345v1")
        self.assertEqual(first.url, "http://arxiv.org/abs/2608.12345v1")
        self.assertEqual(first.author, "Carol Wu, Dan Zhou")
        self.assertIn("continual learning engine", first.summary or "")
        self.assertEqual(first.extra["primary_category"], "cs.AI")
        self.assertEqual(first.published_at, "2026-08-28T17:00:00Z")

    def test_journal_rss20(self) -> None:
        xml_text = (FIXTURES / "journal_science.rss").read_text(encoding="utf-8")
        items = journal.parse_feed(xml_text, "science", 50)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "Quantum error correction at scale")
        self.assertEqual(first.external_id, "10.1126/science.abn1234")
        self.assertEqual(first.extra["venue"], "Science")
        self.assertEqual(first.extra["year"], 2026)
        self.assertEqual(first.platform, "science")

    def test_journal_rdf(self) -> None:
        xml_text = (FIXTURES / "journal_nature.rdf").read_text(encoding="utf-8")
        items = journal.parse_feed(xml_text, "nature", 50)
        self.assertEqual(len(items), 1)
        first = items[0]
        self.assertEqual(first.title, "Deep learning for protein dynamics")
        # nature 文章 URL 不含 DOI 前缀，回退为 URL 本体
        self.assertEqual(first.external_id, "https://www.nature.com/articles/s41586-026-09001")
        self.assertEqual(first.author, "Grace Liu")
        self.assertEqual(first.extra["venue"], "Nature")

    def test_journal_invalid_xml(self) -> None:
        self.assertEqual(journal.parse_feed("not xml", "nature", 50), [])


class FakeResponse:
    def __init__(self, status: int, body: bytes, headers: dict | None = None, final_url: str = ""):
        self.status = status
        self.body = body
        self.headers = headers or {}
        self.final_url = final_url or "https://example.com/final"


class CollectorQueryTests(unittest.TestCase):
    def payload(self, query: str = "") -> dict:
        return {"source_policy": {"max_pages_per_run": 10}, "query": query}

    def test_openalex_query_builder_search(self) -> None:
        baseline = openalex.build_query(50, mailto="bot@example.org")
        # 空 search 输出与现状逐字节一致
        self.assertEqual(openalex.build_query(50, mailto="bot@example.org", search=""), baseline)
        self.assertNotIn("search=", baseline)
        query = openalex.build_query(50, mailto="bot@example.org", search="llm agents")
        self.assertIn("search=llm+agents", query)
        # 原 filter 与其他参数不动
        self.assertIn("publication_year%3A2024", query)
        self.assertIn("type%3Aarticle", query)
        self.assertIn("per_page=50", query)
        self.assertIn("cursor=%2A", query)

    def test_openalex_discover_passes_query(self) -> None:
        body = (FIXTURES / "openalex_works.json").read_bytes()
        calls: list[str] = []

        def fake_fetch(url, allowed, headers=None):
            calls.append(url)
            return FakeResponse(200, body)

        with mock.patch(
            "cerebellum_social_acquisition.collectors.openalex.fetch_public_url",
            side_effect=fake_fetch,
        ):
            result = openalex.OpenAlexProvider().discover(self.payload("llm agents"))
        self.assertEqual(result.outcome, "success")
        self.assertEqual(len(calls), 1)
        self.assertIn("search=llm+agents", calls[0])

    def test_arxiv_query_mode_single_request(self) -> None:
        xml_bytes = (FIXTURES / "arxiv_feed.xml").read_bytes()
        calls: list[str] = []

        def fake_fetch(url, allowed, headers=None):
            calls.append(url)
            return FakeResponse(200, xml_bytes)

        with mock.patch(
            "cerebellum_social_acquisition.collectors.arxiv.fetch_public_url",
            side_effect=fake_fetch,
        ):
            result = arxiv.ArxivProvider().discover(self.payload("continual learning"))
        self.assertEqual(len(calls), 1)
        self.assertIn("all%3A%22continual+learning%22", calls[0])
        self.assertIn("sortBy=submittedDate", calls[0])
        self.assertEqual(result.outcome, "success")
        self.assertEqual(len(result.items), 2)

    def test_arxiv_query_mode_failure_is_single_shot(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.collectors.arxiv.fetch_public_url",
            side_effect=PolicyError("dns blocked", outcome="timeout"),
        ) as fetch:
            result = arxiv.ArxivProvider().discover(self.payload("agents"))
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result.outcome, "timeout")

    def test_arxiv_empty_query_category_loop(self) -> None:
        xml_bytes = (FIXTURES / "arxiv_feed.xml").read_bytes()
        calls: list[str] = []

        def fake_fetch(url, allowed, headers=None):
            calls.append(url)
            return FakeResponse(200, xml_bytes)

        with mock.patch(
            "cerebellum_social_acquisition.collectors.arxiv.fetch_public_url",
            side_effect=fake_fetch,
        ), mock.patch(
            "cerebellum_social_acquisition.collectors.arxiv.time.sleep"
        ):
            result = arxiv.ArxivProvider().discover(self.payload(""))
        self.assertEqual(len(calls), len(arxiv.ARXIV_CATEGORIES))
        self.assertIn("cat%3Acs.AI", calls[0])
        self.assertEqual(result.outcome, "success")

if __name__ == "__main__":
    unittest.main()
