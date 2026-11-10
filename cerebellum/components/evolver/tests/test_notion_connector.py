"""Tests for evolver.notion_connector."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from evolver.notion_connector import (
    NotionConnector,
    SyncResult,
    NOTION_API_BASE,
)
from evolver.exceptions import NotionConnectorError


# --- Fixtures ---

@pytest.fixture
def connector():
    return NotionConnector(token="ntn_test_token_12345")


@pytest.fixture
def no_token_connector():
    return NotionConnector(token="")


def _mock_response(data, headers=None, status=200):
    """Create a mock urllib response."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.headers = headers or {}
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = status
    return resp


# --- NotionConnector.__init__ ---

class TestInit:
    def test_token_from_parameter(self):
        c = NotionConnector(token="ntn_x")
        assert c.token == "ntn_x"

    def test_token_from_env(self):
        with patch.dict("os.environ", {"NOTION_TOKEN": "ntn_env"}, clear=False):
            c = NotionConnector()
            assert c.token == "ntn_env"

    def test_no_token_warning(self, caplog):
        c = NotionConnector(token="")
        assert c.token == ""
        assert "No NOTION_TOKEN" in caplog.text

    def test_default_base_url(self):
        c = NotionConnector(token="x")
        assert c.base_url == NOTION_API_BASE

    def test_custom_base_url(self):
        c = NotionConnector(token="x", base_url="https://notion-proxy.example.com/v1")
        assert c.base_url == "https://notion-proxy.example.com/v1"


# --- _build_headers ---

class TestBuildHeaders:
    def test_basic_headers(self, connector):
        h = connector._build_headers()
        assert h["Notion-Version"] == "2022-06-28"
        assert h["Authorization"] == "Bearer ntn_test_token_12345"
        assert h["Content-Type"] == "application/json"
        assert "User-Agent" in h

    def test_no_auth_without_token(self, no_token_connector):
        h = no_token_connector._build_headers()
        assert "Authorization" not in h


# --- _request ---

class TestRequest:
    @patch("evolver.notion_connector.urllib.request.urlopen")
    def test_successful_post(self, mock_urlopen, connector):
        data = {"results": [{"id": "page1"}], "has_more": False}
        mock_urlopen.return_value = _mock_response(data)
        result, headers = connector._request("POST", "search", body={"query": "test"})
        assert result["results"][0]["id"] == "page1"

    @patch("evolver.notion_connector.urllib.request.urlopen")
    def test_successful_get(self, mock_urlopen, connector):
        data = {"id": "page1", "object": "page"}
        mock_urlopen.return_value = _mock_response(data)
        result, headers = connector._request("GET", "pages/page1")
        assert result["id"] == "page1"

    @patch("evolver.notion_connector.urllib.request.urlopen")
    def test_401_error(self, mock_urlopen, connector):
        error = urllib.error.HTTPError(
            url="", code=401, msg="Unauthorized", hdrs={}, fp=None,
        )
        mock_urlopen.side_effect = error
        with pytest.raises(NotionConnectorError, match="Unauthorized"):
            connector._request("GET", "pages/test")

    @patch("evolver.notion_connector.urllib.request.urlopen")
    def test_404_error(self, mock_urlopen, connector):
        error = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs={}, fp=None,
        )
        mock_urlopen.side_effect = error
        with pytest.raises(NotionConnectorError, match="not found"):
            connector._request("GET", "pages/nonexistent")

    @patch("evolver.notion_connector.urllib.request.urlopen")
    def test_429_rate_limit(self, mock_urlopen, connector):
        error = urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests", hdrs={}, fp=None,
        )
        mock_urlopen.side_effect = error
        with pytest.raises(NotionConnectorError, match="rate limit"):
            connector._request("POST", "search")

    @patch("evolver.notion_connector.urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen, connector):
        mock_urlopen.side_effect = urllib.error.URLError(
            reason="Connection refused"
        )
        with pytest.raises(NotionConnectorError, match="connection failed"):
            connector._request("GET", "pages/test")


# --- _paginate ---

class TestPaginate:
    @patch.object(NotionConnector, "_request")
    def test_single_page(self, mock_request, connector):
        items = [{"id": f"page{i}"} for i in range(10)]
        mock_request.return_value = (
            {"results": items, "has_more": False, "next_cursor": None},
            {},
        )
        result = connector._paginate("search", body={"query": "test"})
        assert len(result.items) == 10
        assert result.has_more is False
        assert result.next_cursor is None

    @patch.object(NotionConnector, "_request")
    def test_multi_page(self, mock_request, connector):
        page1_items = [{"id": f"page{i}"} for i in range(100)]
        page2_items = [{"id": f"page{i + 100}"} for i in range(10)]
        mock_request.side_effect = [
            ({"results": page1_items, "has_more": True, "next_cursor": "cursor_abc"}, {}),
            ({"results": page2_items, "has_more": False, "next_cursor": None}, {}),
        ]
        result = connector._paginate("search", body={"query": "test"})
        assert len(result.items) == 110
        assert mock_request.call_count == 2
        assert result.has_more is False

    @patch.object(NotionConnector, "_request")
    def test_max_pages_limit(self, mock_request, connector):
        small_connector = NotionConnector(token="x", max_pages=2)
        items = [{"id": f"page{i}"} for i in range(100)]
        mock_request.return_value = (
            {"results": items, "has_more": True, "next_cursor": "cursor"},
            {},
        )
        result = small_connector._paginate("search", body={})
        assert mock_request.call_count == 2
        assert result.has_more is True

    @patch.object(NotionConnector, "_request")
    def test_start_cursor(self, mock_request, connector):
        items = [{"id": "page1"}]
        mock_request.return_value = (
            {"results": items, "has_more": False, "next_cursor": None},
            {},
        )
        result = connector._paginate("search", body={}, start_cursor="my_cursor")
        call_body = mock_request.call_args[0][2] if len(mock_request.call_args[0]) > 2 else mock_request.call_args[1].get("body")
        assert call_body["start_cursor"] == "my_cursor"


# --- sync_pages ---

class TestSyncPages:
    @patch.object(NotionConnector, "_paginate")
    def test_basic_sync(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(
            items=[{"id": "page1", "object": "page"}],
            has_more=False,
        )
        result = connector.sync_pages()
        assert len(result.items) == 1
        mock_paginate.assert_called_once()
        call_body = mock_paginate.call_args[1].get("body", {})
        assert call_body["filter"]["value"] == "page"

    @patch.object(NotionConnector, "_paginate")
    def test_with_query(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        connector.sync_pages(query="meeting notes")
        call_body = mock_paginate.call_args[1].get("body", {})
        assert call_body["query"] == "meeting notes"
        assert call_body["filter"]["value"] == "page"


# --- sync_databases ---

class TestSyncDatabases:
    @patch.object(NotionConnector, "_paginate")
    def test_basic_sync(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(
            items=[{"id": "db1", "object": "database"}],
            has_more=False,
        )
        result = connector.sync_databases()
        assert len(result.items) == 1
        call_body = mock_paginate.call_args[1].get("body", {})
        assert call_body["filter"]["value"] == "database"

    @patch.object(NotionConnector, "_paginate")
    def test_with_query(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        connector.sync_databases(query="projects")
        call_body = mock_paginate.call_args[1].get("body", {})
        assert call_body["query"] == "projects"
        assert call_body["filter"]["value"] == "database"


# --- sync_database_items ---

class TestSyncDatabaseItems:
    @patch.object(NotionConnector, "_paginate")
    def test_basic_sync(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(
            items=[{"id": "item1", "object": "page"}],
            has_more=False,
        )
        result = connector.sync_database_items("db_abc123")
        assert len(result.items) == 1
        assert "databases/db_abc123/query" in mock_paginate.call_args[0][0]

    @patch.object(NotionConnector, "_paginate")
    def test_with_filter(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        my_filter = {"property": "Status", "select": {"equals": "Done"}}
        connector.sync_database_items("db_abc123", filter=my_filter)
        call_body = mock_paginate.call_args[1].get("body", {})
        assert call_body["filter"] == my_filter

    @patch.object(NotionConnector, "_paginate")
    def test_with_sorts(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        sorts = [{"property": "Name", "direction": "ascending"}]
        connector.sync_database_items("db_abc123", sorts=sorts)
        call_body = mock_paginate.call_args[1].get("body", {})
        assert call_body["sorts"] == sorts


# --- get_page ---

class TestGetPage:
    @patch.object(NotionConnector, "_request")
    def test_returns_page(self, mock_request, connector):
        mock_request.return_value = ({"id": "page1", "object": "page"}, {})
        result = connector.get_page("page1")
        assert result["id"] == "page1"
        mock_request.assert_called_once_with("GET", "pages/page1")


# --- get_database ---

class TestGetDatabase:
    @patch.object(NotionConnector, "_request")
    def test_returns_database(self, mock_request, connector):
        mock_request.return_value = ({"id": "db1", "object": "database"}, {})
        result = connector.get_database("db1")
        assert result["id"] == "db1"
        mock_request.assert_called_once_with("GET", "databases/db1")


# --- SyncResult dataclass ---

class TestSyncResult:
    def test_default_values(self):
        r = SyncResult()
        assert r.items == []
        assert r.next_cursor is None
        assert r.has_more is False

    def test_with_values(self):
        r = SyncResult(items=[{"id": "1"}], next_cursor="abc", has_more=True)
        assert len(r.items) == 1
        assert r.next_cursor == "abc"
        assert r.has_more is True


# --- Retry decorator integration ---

class TestRetryIntegration:
    @patch("evolver.notion_connector.urllib.request.urlopen")
    def test_retry_on_503(self, mock_urlopen):
        error_503 = urllib.error.HTTPError(
            url="", code=503, msg="Service Unavailable", hdrs={}, fp=None,
        )
        success_resp = _mock_response({"results": [], "has_more": False})
        mock_urlopen.side_effect = [error_503, success_resp]
        connector = NotionConnector(token="x")
        # 503 is in retry_on, so it should retry and succeed
        result, _headers = connector._request("POST", "search")
        assert result == {"results": [], "has_more": False}
        assert mock_urlopen.call_count == 2
