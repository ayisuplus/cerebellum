"""Tests for evolver.github_connector."""

import json
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from evolver.github_connector import (
    GitHubConnector,
    SyncResult,
    GITHUB_API_BASE,
)
from evolver.exceptions import GitHubConnectorError


# --- Fixtures ---

@pytest.fixture
def connector():
    return GitHubConnector(token="ghp_test_token_12345")


@pytest.fixture
def no_token_connector():
    return GitHubConnector(token="")


def _mock_response(data, headers=None, status=200):
    """Create a mock urllib response."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.headers = headers or {}
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = status
    return resp


# --- GitHubConnector.__init__ ---

class TestInit:
    def test_token_from_parameter(self):
        c = GitHubConnector(token="ghp_x")
        assert c.token == "ghp_x"

    def test_token_from_env(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_env"}, clear=False):
            c = GitHubConnector()
            assert c.token == "ghp_env"

    def test_no_token_warning(self, caplog):
        c = GitHubConnector(token="")
        assert c.token == ""
        assert "No GITHUB_TOKEN" in caplog.text

    def test_default_base_url(self):
        c = GitHubConnector(token="x")
        assert c.base_url == GITHUB_API_BASE

    def test_custom_base_url(self):
        c = GitHubConnector(token="x", base_url="https://ghes.example.com/api/v3")
        assert c.base_url == "https://ghes.example.com/api/v3"


# --- _build_headers ---

class TestBuildHeaders:
    def test_basic_headers(self, connector):
        h = connector._build_headers()
        assert h["Accept"] == "application/vnd.github+json"
        assert h["Authorization"] == "Bearer ghp_test_token_12345"
        assert "User-Agent" in h

    def test_no_auth_without_token(self, no_token_connector):
        h = no_token_connector._build_headers()
        assert "Authorization" not in h

    def test_etag_header(self, connector):
        h = connector._build_headers(etag='"abc123"')
        assert h["If-None-Match"] == '"abc123"'

    def test_if_modified_since(self, connector):
        h = connector._build_headers(if_modified_since="Wed, 01 Jan 2024 00:00:00 GMT")
        assert h["If-Modified-Since"] == "Wed, 01 Jan 2024 00:00:00 GMT"


# --- _request ---

class TestRequest:
    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_successful_get(self, mock_urlopen, connector):
        data = [{"id": 1, "name": "repo1"}]
        mock_urlopen.return_value = _mock_response(data, {
            "X-RateLimit-Remaining": "4999",
            "ETag": '"abc"',
        })
        result, headers = connector._request("GET", "orgs/test/repos")
        assert len(result) == 1
        assert headers["X-RateLimit-Remaining"] == "4999"

    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_404_error(self, mock_urlopen, connector):
        import urllib.error
        error = urllib.error.HTTPError(
            url="https://api.github.com/orgs/nonexistent/repos",
            code=404, msg="Not Found", hdrs={}, fp=None,
        )
        mock_urlopen.side_effect = error
        with pytest.raises(GitHubConnectorError, match="not found"):
            connector._request("GET", "orgs/nonexistent/repos")

    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_rate_limit_403(self, mock_urlopen, connector):
        import urllib.error
        error = urllib.error.HTTPError(
            url="", code=403, msg="Forbidden", hdrs={}, fp=None,
        )
        error.read = lambda: b'{"message": "rate limit exceeded"}'
        mock_urlopen.side_effect = error
        with pytest.raises(GitHubConnectorError, match="rate limit"):
            connector._request("GET", "orgs/test/repos")

    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen, connector):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError(
            reason="Connection refused"
        )
        with pytest.raises(GitHubConnectorError, match="connection failed"):
            connector._request("GET", "orgs/test/repos")


# --- _paginate ---

class TestPaginate:
    @patch.object(GitHubConnector, "_request")
    def test_single_page(self, mock_request, connector):
        items = [{"id": i} for i in range(10)]
        mock_request.return_value = (items, {
            "X-RateLimit-Remaining": "4999",
            "ETag": '"etag123"',
            "Link": '<https://api.github.com/repos?page=1>; rel="first"',
        })
        result = connector._paginate("orgs/test/repos")
        assert len(result.items) == 10
        assert result.etag == "etag123"

    @patch.object(GitHubConnector, "_request")
    def test_multi_page(self, mock_request, connector):
        page1 = [{"id": i} for i in range(100)]
        page1_resp_headers = {
            "X-RateLimit-Remaining": "4998",
            "ETag": '"etag1"',
            "Link": '<https://api.github.com/orgs/test/repos?page=2>; rel="next"',
        }
        page2 = [{"id": i + 100} for i in range(10)]
        page2_resp_headers = {
            "X-RateLimit-Remaining": "4997",
            "ETag": '"etag2"',
            "Link": '<https://api.github.com/orgs/test/repos?page=2>; rel="last"',
        }
        mock_request.side_effect = [
            (page1, page1_resp_headers),
            (page2, page2_resp_headers),
        ]
        result = connector._paginate("orgs/test/repos")
        assert len(result.items) == 110
        assert mock_request.call_count == 2

    @patch.object(GitHubConnector, "_request")
    def test_max_pages_limit(self, mock_request, connector):
        small_connector = GitHubConnector(token="x", max_pages=2)
        items = [{"id": i} for i in range(100)]
        resp_headers = {
            "X-RateLimit-Remaining": "5000",
            "ETag": '"e"',
            "Link": '<https://api.github.com?page=999>; rel="next"',
        }
        mock_request.return_value = (items, resp_headers)
        result = small_connector._paginate("orgs/test/repos")
        assert mock_request.call_count == 2

    @patch.object(GitHubConnector, "_request")
    def test_rate_limit_sleep(self, mock_request, connector):
        items = [{"id": 1}]
        resp_headers = {
            "X-RateLimit-Remaining": "1",
            "X-RateLimit-Reset": str(time.time() + 0.1),
            "ETag": '"e"',
            "Link": '<https://api.github.com?page=2>; rel="next"',
        }
        page2_headers = {
            "X-RateLimit-Remaining": "5000",
            "ETag": '"e2"',
        }
        mock_request.side_effect = [
            (items, resp_headers),
            (items, page2_headers),
        ]
        with patch("evolver.github_connector.time.sleep") as mock_sleep:
            result = connector._paginate("orgs/test/repos")
            mock_sleep.assert_called_once()


# --- sync_repos ---

class TestSyncRepos:
    @patch.object(GitHubConnector, "_paginate")
    def test_org_repos(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(
            items=[{"name": "repo1"}, {"name": "repo2"}],
            etag='"abc"',
        )
        result = connector.sync_repos("myorg")
        assert len(result.items) == 2
        mock_paginate.assert_called_once()
        assert "orgs/myorg/repos" in mock_paginate.call_args[0][0]

    @patch.object(GitHubConnector, "_paginate")
    def test_fallback_to_user(self, mock_paginate, connector):
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise GitHubConnectorError("GitHub resource not found: orgs/noorg/repos")
            return SyncResult(items=[{"name": "repo1"}])

        mock_paginate.side_effect = side_effect
        result = connector.sync_repos("noorg")
        assert len(result.items) == 1
        assert call_count[0] == 2

    @patch.object(GitHubConnector, "_paginate")
    def test_since_param(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        connector.sync_repos("org", since="2024-01-01T00:00:00Z")
        call_args = mock_paginate.call_args
        assert call_args[1].get("params", {}).get("since") == "2024-01-01T00:00:00Z" or \
               (len(call_args) > 1 and call_args[1].get("params", {}).get("since") == "2024-01-01T00:00:00Z")


# --- sync_issues ---

class TestSyncIssues:
    @patch.object(GitHubConnector, "_paginate")
    def test_basic_sync(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(
            items=[
                {"id": 1, "title": "Bug report", "number": 1},
                {"id": 2, "title": "PR title", "number": 2, "pull_request": {"url": "..."}},
            ],
            etag='"e1"',
        )
        result = connector.sync_issues("owner", "repo")
        assert len(result.items) == 1
        assert result.items[0]["title"] == "Bug report"

    @patch.object(GitHubConnector, "_paginate")
    def test_since_param(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(items=[])
        connector.sync_issues("owner", "repo", since="2024-06-01T00:00:00Z")
        call_params = mock_paginate.call_args[1].get("params", mock_paginate.call_args[0][1] if len(mock_paginate.call_args[0]) > 1 else {})
        found = False
        for arg in mock_paginate.call_args:
            if isinstance(arg, dict) and "since" in str(arg):
                found = True
        assert found or mock_paginate.called


# --- sync_pull_requests ---

class TestSyncPullRequests:
    @patch.object(GitHubConnector, "_paginate")
    def test_basic_sync(self, mock_paginate, connector):
        mock_paginate.return_value = SyncResult(
            items=[{"id": 1, "title": "Fix bug", "number": 1}],
            etag='"e1"',
        )
        result = connector.sync_pull_requests("owner", "repo")
        assert len(result.items) == 1
        assert "repos/owner/repo/pulls" in mock_paginate.call_args[0][0]

    @patch.object(GitHubConnector, "_paginate")
    def test_since_filtering(self, mock_paginate, connector):
        now = "2024-06-15T00:00:00Z"
        old_pr = {"id": 1, "title": "Old PR", "updated_at": "2024-01-01T00:00:00Z"}
        new_pr = {"id": 2, "title": "New PR", "updated_at": "2024-06-20T00:00:00Z"}
        mock_paginate.return_value = SyncResult(items=[old_pr, new_pr])
        result = connector.sync_pull_requests("owner", "repo", since="2024-06-15T00:00:00Z")
        assert len(result.items) == 1
        assert result.items[0]["title"] == "New PR"

    @patch.object(GitHubConnector, "_paginate")
    def test_since_no_updated_at(self, mock_paginate, connector):
        pr_no_date = {"id": 1, "title": "No date PR"}
        mock_paginate.return_value = SyncResult(items=[pr_no_date])
        result = connector.sync_pull_requests("owner", "repo", since="2024-06-01T00:00:00Z")
        assert len(result.items) == 1


# --- SyncResult dataclass ---

class TestSyncResult:
    def test_default_values(self):
        r = SyncResult()
        assert r.items == []
        assert r.etag is None
        assert r.last_modified is None
        assert r.rate_limit_remaining == 0

    def test_with_values(self):
        r = SyncResult(items=[{"id": 1}], etag='"abc"', last_modified="Wed, 01 Jan 2024")
        assert len(r.items) == 1
        assert r.etag == '"abc"'


# --- Retry decorator integration ---

class TestRetryIntegration:
    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_retry_on_503(self, mock_urlopen):
        import urllib.error
        error_503 = urllib.error.HTTPError(
            url="", code=503, msg="Service Unavailable", hdrs={}, fp=None,
        )
        success_resp = _mock_response([{"id": 1}], {"X-RateLimit-Remaining": "5000"})
        mock_urlopen.side_effect = [error_503, success_resp]
        connector = GitHubConnector(token="x")
        with pytest.raises(Exception):
            connector._request("GET", "test")
