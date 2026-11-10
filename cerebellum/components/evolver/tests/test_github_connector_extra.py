"""Extra tests for evolver.github_connector — query params, error edges, sync_and_store."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from evolver.github_connector import GitHubConnector, SyncResult
from evolver.exceptions import GitHubConnectorError


@pytest.fixture
def connector():
    return GitHubConnector(token="ghp_test_token")


def _mock_response(data, headers=None):
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.headers = headers or {}
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestRequestQueryParams:
    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_params_are_encoded_and_none_values_dropped(self, mock_urlopen, connector):
        mock_urlopen.return_value = _mock_response([], {})
        connector._request("GET", "orgs/o/repos", params={"state": "all", "since": None})
        url = mock_urlopen.call_args[0][0].full_url
        assert "state=all" in url
        assert "since" not in url

    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_no_params_leaves_plain_url(self, mock_urlopen, connector):
        mock_urlopen.return_value = _mock_response([], {})
        connector._request("GET", "orgs/o/repos")
        url = mock_urlopen.call_args[0][0].full_url
        assert url.endswith("/orgs/o/repos")
        assert "?" not in url


class TestRequestErrorEdges:
    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_304_raises_not_modified(self, mock_urlopen, connector):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=304, msg="Not Modified", hdrs={}, fp=None,
        )
        with pytest.raises(GitHubConnectorError, match="Not Modified"):
            connector._request("GET", "orgs/o/repos")

    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_403_with_unreadable_body_reports_forbidden(self, mock_urlopen, connector):
        error = urllib.error.HTTPError(
            url="", code=403, msg="Forbidden", hdrs={}, fp=None,
        )
        error.read = MagicMock(side_effect=OSError("no body"))
        mock_urlopen.side_effect = error
        with pytest.raises(GitHubConnectorError, match="forbidden"):
            connector._request("GET", "orgs/o/repos")

    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_403_without_rate_limit_message_reports_forbidden(self, mock_urlopen, connector):
        error = urllib.error.HTTPError(
            url="", code=403, msg="Forbidden", hdrs={}, fp=None,
        )
        error.read = lambda: b'{"message": "Repository access blocked"}'
        mock_urlopen.side_effect = error
        with pytest.raises(GitHubConnectorError, match="forbidden"):
            connector._request("GET", "orgs/o/repos")

    @patch("evolver.github_connector.urllib.request.urlopen")
    def test_other_http_error_reports_code(self, mock_urlopen, connector):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=500, msg="Internal Server Error", hdrs={}, fp=None,
        )
        with pytest.raises(GitHubConnectorError, match="500"):
            connector._request("GET", "orgs/o/repos")


class TestPaginateEdges:
    @patch.object(GitHubConnector, "_request")
    def test_non_list_response_returns_single_item(self, mock_request, connector):
        payload = {"id": 1, "name": "single"}
        mock_request.return_value = (payload, {
            "X-RateLimit-Remaining": "42",
            "X-RateLimit-Reset": "1234567.0",
        })
        result = connector._paginate("repos/o/r")
        assert result.items == [payload]
        assert result.rate_limit_remaining == 42
        assert result.rate_limit_reset == 1234567.0

    @patch.object(GitHubConnector, "_request")
    def test_last_modified_captured_from_first_page(self, mock_request, connector):
        mock_request.return_value = ([{"id": 1}], {
            "ETag": '"e1"',
            "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT",
            "X-RateLimit-Remaining": "100",
        })
        result = connector._paginate("orgs/o/repos")
        assert result.last_modified == "Wed, 01 Jan 2025 00:00:00 GMT"
        assert result.etag == "e1"


class TestSyncReposReraise:
    @patch.object(GitHubConnector, "_paginate")
    def test_non_not_found_error_propagates(self, mock_paginate, connector):
        mock_paginate.side_effect = GitHubConnectorError("GitHub API error 500: boom")
        with pytest.raises(GitHubConnectorError, match="500"):
            connector.sync_repos("myorg")
        mock_paginate.assert_called_once()


class TestSyncPullRequestsSince:
    @patch.object(GitHubConnector, "_paginate")
    def test_malformed_updated_at_is_kept(self, mock_paginate, connector):
        prs = [
            {"id": 1, "title": "garbage date", "updated_at": "not-a-date"},
            {"id": 2, "title": "old", "updated_at": "2020-01-01T00:00:00Z"},
            {"id": 3, "title": "new", "updated_at": "2026-08-01T00:00:00Z"},
        ]
        mock_paginate.return_value = SyncResult(items=prs)
        result = connector.sync_pull_requests("o", "r", since="2026-01-01T00:00:00Z")
        titles = [p["title"] for p in result.items]
        assert titles == ["garbage date", "new"]


class TestSyncAndStore:
    def _repo(self):
        return {
            "full_name": "org/repo",
            "description": "a repo",
            "language": "Python",
            "stargazers_count": 42,
            "html_url": "https://github.com/org/repo",
        }

    def _issue(self):
        return {
            "number": 5,
            "title": "Bug in parser",
            "state": "open",
            "body": "it crashes on empty input",
            "html_url": "https://github.com/org/repo/issues/5",
        }

    def _pr(self):
        return {
            "number": 7,
            "title": "Fix parser",
            "state": "closed",
            "body": "adds a guard clause",
            "html_url": "https://github.com/org/repo/pull/7",
        }

    def test_full_sync_archives_and_extracts(self, connector):
        evolver = MagicMock()
        evolver.learn_extracted.return_value = [
            {"action": "add", "fact": "f"},
            {"action": "skip", "fact": "g"},
        ]
        with patch.object(connector, "sync_repos",
                          return_value=SyncResult(items=[self._repo()])), \
             patch.object(connector, "sync_issues",
                          return_value=SyncResult(items=[self._issue()])), \
             patch.object(connector, "sync_pull_requests",
                          return_value=SyncResult(items=[self._pr()])):
            results = connector.sync_and_store("org", repo="repo", evolver=evolver)

        assert results["repos"] == [self._repo()]
        assert results["issues"] == [self._issue()]
        assert results["pull_requests"] == [self._pr()]
        assert results["archived"] == 3
        # one "add" per learn_extracted call (repos + issues + PRs)
        assert results["facts_added"] == 3
        kinds = [call[1]["kind"] for call in evolver.archive.call_args_list]
        assert kinds == ["github_repo", "github_issue", "github_pr"]
        repo_archive = evolver.archive.call_args_list[0]
        assert "org/repo" in repo_archive[1]["content"]
        assert repo_archive[1]["ref"] == "https://github.com/org/repo"
        assert repo_archive[1]["meta"] == self._repo()

    def test_repo_none_skips_issues_and_prs(self, connector):
        with patch.object(connector, "sync_repos",
                          return_value=SyncResult(items=[self._repo()])), \
             patch.object(connector, "sync_issues") as mock_issues, \
             patch.object(connector, "sync_pull_requests") as mock_prs:
            results = connector.sync_and_store("org")

        assert results["issues"] is None
        assert results["pull_requests"] is None
        mock_issues.assert_not_called()
        mock_prs.assert_not_called()

    def test_no_evolver_only_syncs(self, connector):
        with patch.object(connector, "sync_repos",
                          return_value=SyncResult(items=[self._repo()])):
            results = connector.sync_and_store("org", evolver=None)
        assert results["archived"] == 0
        assert results["facts_added"] == 0
        assert results["repos"] == [self._repo()]

    def test_empty_sync_archives_nothing(self, connector):
        evolver = MagicMock()
        with patch.object(connector, "sync_repos",
                          return_value=SyncResult(items=[])), \
             patch.object(connector, "sync_issues",
                          return_value=SyncResult(items=[])), \
             patch.object(connector, "sync_pull_requests",
                          return_value=SyncResult(items=[])):
            results = connector.sync_and_store("org", repo="repo", evolver=evolver)
        assert results["archived"] == 0
        evolver.archive.assert_not_called()
        evolver.learn_extracted.assert_not_called()
