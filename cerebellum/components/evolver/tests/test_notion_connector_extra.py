"""Extra tests for evolver.notion_connector — filter/sort merging, sync_and_store."""

from unittest.mock import MagicMock, patch

import pytest

from evolver.notion_connector import NotionConnector, SyncResult
from evolver.exceptions import NotionConnectorError


@pytest.fixture
def connector():
    return NotionConnector(token="ntn_test_token")


class TestSearchBodyMerging:
    @patch.object(NotionConnector, "_paginate")
    def test_sync_pages_merges_filter_and_sort(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        extra_filter = {"property": "object", "value": "page", "extra": 1}
        sort = {"direction": "descending", "timestamp": "last_edited_time"}
        connector.sync_pages(query="q", filter=extra_filter, sort=sort)

        body = mock_paginate.call_args[1]["body"]
        assert body["filter"]["extra"] == 1
        assert body["filter"]["value"] == "page"  # base filter preserved
        assert body["sort"] == sort
        assert body["query"] == "q"

    @patch.object(NotionConnector, "_paginate")
    def test_sync_databases_merges_filter_and_sort(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        extra_filter = {"extra": "yes"}
        sort = {"direction": "ascending"}
        connector.sync_databases(filter=extra_filter, sort=sort)

        body = mock_paginate.call_args[1]["body"]
        assert body["filter"]["value"] == "database"
        assert body["filter"]["extra"] == "yes"
        assert body["sort"] == sort

    @patch.object(NotionConnector, "_paginate")
    def test_start_cursor_forwarded(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        connector.sync_pages(start_cursor="cursor-xyz")
        assert mock_paginate.call_args[1]["start_cursor"] == "cursor-xyz"


class TestSyncAndStore:
    def _page(self, title="Meeting Notes"):
        return {
            "id": "page-1",
            "object": "page",
            "url": "https://notion.so/page-1",
            "created_time": "2026-01-01T00:00:00.000Z",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": title}],
                },
                "Other": {"type": "rich_text", "rich_text": []},
            },
        }

    def _database(self, title="Projects DB"):
        return {
            "id": "db-1",
            "object": "database",
            "url": "https://notion.so/db-1",
            "created_time": "2026-01-01T00:00:00.000Z",
            "title": [{"plain_text": title}],
        }

    def test_full_sync_archives_and_extracts(self, connector):
        evolver = MagicMock()
        evolver.learn_extracted.return_value = [
            {"action": "add", "fact": "f"},
            {"action": "skip", "fact": "g"},
        ]
        with patch.object(connector, "sync_pages",
                          return_value=SyncResult(items=[self._page()])) as mock_pages, \
             patch.object(connector, "sync_databases",
                          return_value=SyncResult(items=[self._database()])) as mock_dbs:
            results = connector.sync_and_store(query="notes", evolver=evolver)

        assert results["pages"] == [self._page()]
        assert results["databases"] == [self._database()]
        assert results["archived"] == 2
        # one "add" per learn_extracted call (pages + databases)
        assert results["facts_added"] == 2

        kinds = [call[1]["kind"] for call in evolver.archive.call_args_list]
        assert kinds == ["notion_page", "notion_database"]
        page_archive = evolver.archive.call_args_list[0]
        assert "Meeting Notes" in page_archive[1]["content"]
        assert page_archive[1]["ref"] == "https://notion.so/page-1"
        db_archive = evolver.archive.call_args_list[1]
        assert "Projects DB" in db_archive[1]["content"]

        # query forwarded to both searches
        _, pages_kwargs = mock_pages.call_args
        _, dbs_kwargs = mock_dbs.call_args
        assert pages_kwargs["query"] == "notes"
        assert dbs_kwargs["query"] == "notes"

    def test_page_without_properties_gets_empty_title(self, connector):
        evolver = MagicMock()
        evolver.learn_extracted.return_value = []
        bare_page = {
            "id": "page-2",
            "url": "https://notion.so/page-2",
            "created_time": "2026-01-01T00:00:00.000Z",
        }
        bare_db = {"id": "db-2", "url": "https://notion.so/db-2",
                   "created_time": "2026-01-01T00:00:00.000Z"}
        with patch.object(connector, "sync_pages",
                          return_value=SyncResult(items=[bare_page])), \
             patch.object(connector, "sync_databases",
                          return_value=SyncResult(items=[bare_db])):
            results = connector.sync_and_store(evolver=evolver)

        assert results["archived"] == 2
        page_content = evolver.archive.call_args_list[0][1]["content"]
        assert "Notion Page: \n" in page_content
        db_content = evolver.archive.call_args_list[1][1]["content"]
        assert "Notion Database: \n" in db_content

    def test_no_evolver_only_syncs(self, connector):
        with patch.object(connector, "sync_pages",
                          return_value=SyncResult(items=[self._page()])), \
             patch.object(connector, "sync_databases",
                          return_value=SyncResult(items=[self._database()])):
            results = connector.sync_and_store(evolver=None)
        assert results["archived"] == 0
        assert results["facts_added"] == 0
        assert results["pages"] == [self._page()]
        assert results["databases"] == [self._database()]

    def test_empty_sync_archives_nothing(self, connector):
        evolver = MagicMock()
        with patch.object(connector, "sync_pages",
                          return_value=SyncResult(items=[])), \
             patch.object(connector, "sync_databases",
                          return_value=SyncResult(items=[])):
            results = connector.sync_and_store(evolver=evolver)
        assert results["archived"] == 0
        evolver.archive.assert_not_called()
        evolver.learn_extracted.assert_not_called()
