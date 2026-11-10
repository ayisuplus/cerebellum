"""GitHub API connector for syncing issues, pull requests, and repos.

Uses GitHub REST API v3 with token auth, automatic pagination,
rate limit handling, and incremental sync via ETag/since parameters.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

from evolver.exceptions import GitHubConnectorError
from evolver.llm_client import retry

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_PER_PAGE = 100
DEFAULT_MAX_PAGES = 50


@dataclass
class SyncResult:
    """Result of a sync operation."""
    items: list[dict] = field(default_factory=list)
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    rate_limit_remaining: int = 0
    rate_limit_reset: float = 0.0


class GitHubConnector:
    """GitHub REST API connector with pagination, rate limiting, and incremental sync.

    Usage:
        conn = GitHubConnector(token="ghp_...")
        repos = conn.sync_repos("myorg")
        issues = conn.sync_issues("myorg", "myrepo", since="2024-01-01T00:00:00Z")
    """

    def __init__(self, token: str = None, base_url: str = GITHUB_API_BASE,
                 per_page: int = DEFAULT_PER_PAGE, max_pages: int = DEFAULT_MAX_PAGES):
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.per_page = per_page
        self.max_pages = max_pages
        if not self.token:
            logger.warning("No GITHUB_TOKEN set; rate limits will be very low")

    def _build_headers(self, etag: str = None, if_modified_since: str = None) -> dict:
        """Build request headers including auth and optional conditional headers."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "evolver-github-connector",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag
        if if_modified_since:
            headers["If-Modified-Since"] = if_modified_since
        return headers

    @retry(max_retries=3, backoff=1.0, retry_on=(429, 502, 503))
    def _request(self, method: str, path: str, params: dict = None,
                  headers: dict = None) -> tuple[dict | list, dict]:
        """Execute a single GitHub API request.

        Returns:
            (response_data, response_headers) tuple

        Raises:
            GitHubConnectorError: On API errors
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            if qs:
                url = f"{url}?{qs}"

        req = urllib.request.Request(url, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                resp_headers = dict(resp.headers)
                return data, resp_headers
        except urllib.error.HTTPError as e:
            if e.code == 304:
                raise GitHubConnectorError(f"Not Modified (304)")
            if e.code == 403:
                body = ""
                try:
                    body = e.read().decode("utf-8")
                except Exception:
                    pass
                if "rate limit" in body.lower():
                    raise GitHubConnectorError(
                        f"GitHub API rate limit exceeded: {body}"
                    ) from e
                raise GitHubConnectorError(
                    f"GitHub API forbidden (403): {body}"
                ) from e
            if e.code == 404:
                raise GitHubConnectorError(
                    f"GitHub resource not found: {path}"
                ) from e
            raise GitHubConnectorError(
                f"GitHub API error {e.code}: {e.reason}"
            ) from e
        except urllib.error.URLError as e:
            raise GitHubConnectorError(
                f"GitHub API connection failed: {e.reason}"
            ) from e

    def _paginate(self, path: str, params: dict = None,
                   etag: str = None) -> SyncResult:
        """Paginate through all pages of a GitHub API endpoint.

        Automatically follows Link headers for pagination.
        Respects rate limits by sleeping when remaining = 0.
        """
        all_items = []
        current_params = dict(params or {})
        current_params["per_page"] = self.per_page
        current_etag = etag
        last_modified = None

        for page_num in range(1, self.max_pages + 1):
            current_params["page"] = page_num
            headers = self._build_headers(etag=current_etag if page_num == 1 else None)

            data, resp_headers = self._request("GET", path, params=current_params, headers=headers)

            if page_num == 1:
                if not current_etag:
                    current_etag = resp_headers.get("ETag", "").strip('"')
                last_modified = resp_headers.get("Last-Modified")

            if isinstance(data, list):
                all_items.extend(data)
            else:
                return SyncResult(
                    items=[data],
                    etag=current_etag,
                    last_modified=last_modified,
                    rate_limit_remaining=int(resp_headers.get("X-RateLimit-Remaining", "0")),
                    rate_limit_reset=float(resp_headers.get("X-RateLimit-Reset", "0")),
                )

            link_header = resp_headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break

            remaining = int(resp_headers.get("X-RateLimit-Remaining", "5000"))
            if remaining <= 1:
                reset_ts = float(resp_headers.get("X-RateLimit-Reset", "0"))
                wait = max(reset_ts - time.time(), 0) + 1
                logger.warning("Rate limit near exhaustion, sleeping %.0fs", wait)
                time.sleep(wait)

        return SyncResult(
            items=all_items,
            etag=current_etag,
            last_modified=last_modified,
            rate_limit_remaining=int(resp_headers.get("X-RateLimit-Remaining", "0")),
            rate_limit_reset=float(resp_headers.get("X-RateLimit-Reset", "0")),
        )

    def sync_repos(self, owner: str, since: str = None,
                    etag: str = None) -> SyncResult:
        """Sync repositories for an org or user.

        Args:
            owner: GitHub org or username.
            since: ISO 8601 timestamp for incremental sync (repos pushed after this time).
            etag: ETag for conditional request.

        Returns:
            SyncResult with list of repo dicts.
        """
        params = {}
        if since:
            params["since"] = since
        params["sort"] = "updated"
        params["direction"] = "desc"

        try:
            return self._paginate(f"orgs/{owner}/repos", params=params, etag=etag)
        except GitHubConnectorError as e:
            if "not found" in str(e).lower():
                logger.info("Org %s not found, trying user endpoint", owner)
                return self._paginate(f"users/{owner}/repos", params=params, etag=etag)
            raise

    def sync_issues(self, owner: str, repo: str, since: str = None,
                     etag: str = None, state: str = "all") -> SyncResult:
        """Sync issues (excluding PRs) for a repository.

        Args:
            owner: Repo owner/org.
            repo: Repository name.
            since: ISO 8601 timestamp — only issues updated after this time.
            etag: ETag for conditional request.
            state: "open", "closed", or "all".

        Returns:
            SyncResult with list of issue dicts (PRs filtered out).
        """
        params = {
            "state": state,
            "sort": "updated",
            "direction": "desc",
        }
        if since:
            params["since"] = since

        result = self._paginate(
            f"repos/{owner}/{repo}/issues", params=params, etag=etag
        )
        result.items = [
            item for item in result.items
            if "pull_request" not in item
        ]
        return result

    def sync_pull_requests(self, owner: str, repo: str, since: str = None,
                            etag: str = None, state: str = "all") -> SyncResult:
        """Sync pull requests for a repository.

        Args:
            owner: Repo owner/org.
            repo: Repository name.
            since: ISO 8601 timestamp (PRs updated after this time — note:
                   GitHub PRs API doesn't support 'since' natively, so we
                   filter client-side).
            etag: ETag for conditional request.
            state: "open", "closed", or "all".

        Returns:
            SyncResult with list of PR dicts.
        """
        params = {
            "state": state,
            "sort": "updated",
            "direction": "desc",
        }

        result = self._paginate(
            f"repos/{owner}/{repo}/pulls", params=params, etag=etag
        )

        if since:
            from datetime import datetime, timezone
            cutoff = datetime.fromisoformat(since.replace("Z", "+00:00"))
            filtered = []
            for pr in result.items:
                updated_str = pr.get("updated_at", "")
                if not updated_str:
                    filtered.append(pr)
                    continue
                try:
                    updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    if updated >= cutoff:
                        filtered.append(pr)
                except (ValueError, TypeError):
                    filtered.append(pr)
            result.items = filtered

        return result

    def sync_and_store(self, owner: str, repo: str = None,
                       evolver=None, source_prefix: str = "github") -> dict:
        """Sync GitHub data and store in Evolver.

        Steps:
        1. Sync raw data from GitHub API
        2. Archive raw data to ArchiveStore (dead data)
        3. Extract facts and store in MemoryEngine (experience)

        Args:
            owner: GitHub org or user
            repo: Repository name (optional, for issues/PRs)
            evolver: Evolver instance with archive() and learn_extracted()
            source_prefix: Source label prefix

        Returns:
            dict with sync results and storage stats
        """
        results = {
            "repos": None,
            "issues": None,
            "pull_requests": None,
            "archived": 0,
            "facts_added": 0,
        }

        # Sync repos
        repos_result = self.sync_repos(owner)
        results["repos"] = repos_result.items

        # Archive repos
        if evolver and repos_result.items:
            for item in repos_result.items:
                content = f"Repo: {item.get('full_name', '')}\n"
                content += f"Description: {item.get('description', '')}\n"
                content += f"Language: {item.get('language', '')}\n"
                content += f"Stars: {item.get('stargazers_count', 0)}\n"
                evolver.archive(
                    content=content,
                    kind="github_repo",
                    source=f"{source_prefix}:repos",
                    ref=item.get("html_url", ""),
                    meta=item
                )
                results["archived"] += 1

            # Extract facts from repos
            repo_text = "\n".join([
                f"GitHub repo: {r.get('full_name', '')} - {r.get('description', '')}"
                for r in repos_result.items
            ])
            facts = evolver.learn_extracted(repo_text, source=f"{source_prefix}:repos")
            results["facts_added"] += sum(1 for f in facts if f.get("action") == "add")

        # Sync issues if repo specified
        if repo:
            issues_result = self.sync_issues(owner, repo)
            results["issues"] = issues_result.items

            # Archive issues
            if evolver and issues_result.items:
                for item in issues_result.items:
                    content = f"Issue #{item.get('number', '')}: {item.get('title', '')}\n"
                    content += f"State: {item.get('state', '')}\n"
                    content += f"Body: {item.get('body', '')[:500]}\n"
                    evolver.archive(
                        content=content,
                        kind="github_issue",
                        source=f"{source_prefix}:issues",
                        ref=item.get("html_url", ""),
                        meta=item
                    )
                    results["archived"] += 1

                # Extract facts from issues
                issue_text = "\n".join([
                    f"GitHub issue #{i.get('number', '')}: {i.get('title', '')} - {i.get('body', '')[:200]}"
                    for i in issues_result.items
                ])
                facts = evolver.learn_extracted(issue_text, source=f"{source_prefix}:issues")
                results["facts_added"] += sum(1 for f in facts if f.get("action") == "add")

            # Sync PRs
            prs_result = self.sync_pull_requests(owner, repo)
            results["pull_requests"] = prs_result.items

            # Archive PRs
            if evolver and prs_result.items:
                for item in prs_result.items:
                    content = f"PR #{item.get('number', '')}: {item.get('title', '')}\n"
                    content += f"State: {item.get('state', '')}\n"
                    content += f"Body: {item.get('body', '')[:500]}\n"
                    evolver.archive(
                        content=content,
                        kind="github_pr",
                        source=f"{source_prefix}:pull_requests",
                        ref=item.get("html_url", ""),
                        meta=item
                    )
                    results["archived"] += 1

                # Extract facts from PRs
                pr_text = "\n".join([
                    f"GitHub PR #{p.get('number', '')}: {p.get('title', '')} - {p.get('body', '')[:200]}"
                    for p in prs_result.items
                ])
                facts = evolver.learn_extracted(pr_text, source=f"{source_prefix}:pull_requests")
                results["facts_added"] += sum(1 for f in facts if f.get("action") == "add")

        return results
