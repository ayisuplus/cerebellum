"""Notion API connector for syncing pages, databases, and database items.

Uses Notion API v1 with token auth, cursor-based pagination,
rate limit handling, and search/query endpoints.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

from evolver.exceptions import NotionConnectorError
from evolver.llm_client import retry

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 50


@dataclass
class SyncResult:
    """Result of a sync operation."""
    items: list[dict] = field(default_factory=list)
    next_cursor: Optional[str] = None
    has_more: bool = False


class NotionConnector:
    """Notion REST API connector with pagination, rate limiting, and search.

    Usage:
        conn = NotionConnector(token="ntn_...")
        pages = conn.sync_pages(query="meeting notes")
        dbs = conn.sync_databases()
        items = conn.sync_database_items("database_id")
    """

    def __init__(self, token: str = None, base_url: str = NOTION_API_BASE,
                 page_size: int = DEFAULT_PAGE_SIZE, max_pages: int = DEFAULT_MAX_PAGES):
        self.token = token if token is not None else os.environ.get("NOTION_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self.max_pages = max_pages
        if not self.token:
            logger.warning("No NOTION_TOKEN set; API calls will fail")

    def _build_headers(self) -> dict:
        """Build request headers including auth and Notion version."""
        headers = {
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
            "User-Agent": "evolver-notion-connector",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @retry(max_retries=3, backoff=1.0, retry_on=(429, 502, 503))
    def _request(self, method: str, path: str, body: dict = None) -> tuple[dict, dict]:
        """Execute a single Notion API request.

        Returns:
            (response_data, response_headers) tuple

        Raises:
            NotionConnectorError: On API errors
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._build_headers()
        data = json.dumps(body).encode("utf-8") if body else None

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                resp_headers = dict(resp.headers)
                return resp_data, resp_headers
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise NotionConnectorError(
                    "Unauthorized: check NOTION_TOKEN", code=e.code
                ) from e
            if e.code == 404:
                raise NotionConnectorError(
                    f"Notion resource not found: {path}", code=e.code
                ) from e
            if e.code == 429:
                raise NotionConnectorError(
                    "Notion API rate limit exceeded", code=e.code
                ) from e
            raise NotionConnectorError(
                f"Notion API error {e.code}: {e.reason}", code=e.code
            ) from e
        except urllib.error.URLError as e:
            raise NotionConnectorError(
                f"Notion API connection failed: {e.reason}"
            ) from e

    def _paginate(self, path: str, body: dict = None,
                  start_cursor: str = None) -> SyncResult:
        """Paginate through all pages of a Notion API endpoint.

        Uses cursor-based pagination via start_cursor and has_more.
        """
        all_items = []
        current_cursor = start_cursor
        has_more = True

        for page_num in range(1, self.max_pages + 1):
            current_body = dict(body or {})
            current_body["page_size"] = self.page_size
            if current_cursor:
                current_body["start_cursor"] = current_cursor

            data, resp_headers = self._request("POST", path, body=current_body)

            results = data.get("results", [])
            all_items.extend(results)

            has_more = data.get("has_more", False)
            current_cursor = data.get("next_cursor")

            if not has_more:
                break

        return SyncResult(
            items=all_items,
            next_cursor=current_cursor,
            has_more=has_more,
        )

    def sync_pages(self, query: str = None, filter: dict = None,
                   sort: dict = None, start_cursor: str = None) -> SyncResult:
        """Sync pages via Notion search endpoint.

        Args:
            query: Search query string.
            filter: Additional filter (object type filter is applied automatically).
            sort: Sort configuration.
            start_cursor: Cursor for pagination.

        Returns:
            SyncResult with list of page dicts.
        """
        body = {
            "filter": {"property": "object", "value": "page"},
        }
        if query:
            body["query"] = query
        if filter:
            body["filter"] = {**body["filter"], **filter}
        if sort:
            body["sort"] = sort

        return self._paginate("search", body=body, start_cursor=start_cursor)

    def sync_databases(self, query: str = None, filter: dict = None,
                       sort: dict = None, start_cursor: str = None) -> SyncResult:
        """Sync databases via Notion search endpoint.

        Args:
            query: Search query string.
            filter: Additional filter (object type filter is applied automatically).
            sort: Sort configuration.
            start_cursor: Cursor for pagination.

        Returns:
            SyncResult with list of database dicts.
        """
        body = {
            "filter": {"property": "object", "value": "database"},
        }
        if query:
            body["query"] = query
        if filter:
            body["filter"] = {**body["filter"], **filter}
        if sort:
            body["sort"] = sort

        return self._paginate("search", body=body, start_cursor=start_cursor)

    def sync_database_items(self, database_id: str, filter: dict = None,
                            sorts: list = None, start_cursor: str = None) -> SyncResult:
        """Query a specific database for its items (rows).

        Args:
            database_id: The database ID to query.
            filter: Notion filter object for row filtering.
            sorts: List of sort objects.
            start_cursor: Cursor for pagination.

        Returns:
            SyncResult with list of page/item dicts.
        """
        body = {}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts

        return self._paginate(
            f"databases/{database_id}/query", body=body, start_cursor=start_cursor
        )

    def get_page(self, page_id: str) -> dict:
        """Fetch a single page by ID.

        Args:
            page_id: The page ID.

        Returns:
            Page dict.

        Raises:
            NotionConnectorError: On API errors.
        """
        data, _ = self._request("GET", f"pages/{page_id}")
        return data

    def get_database(self, database_id: str) -> dict:
        """Fetch a single database by ID.

        Args:
            database_id: The database ID.

        Returns:
            Database dict.

        Raises:
            NotionConnectorError: On API errors.
        """
        data, _ = self._request("GET", f"databases/{database_id}")
        return data

    def sync_and_store(self, query: str = None,
                       evolver=None, source_prefix: str = "notion") -> dict:
        """Sync Notion data and store in Evolver.

        Steps:
        1. Sync raw data from Notion API
        2. Archive raw data to ArchiveStore (dead data)
        3. Extract facts and store in MemoryEngine (experience)

        Args:
            query: Search query (optional)
            evolver: Evolver instance with archive() and learn_extracted()
            source_prefix: Source label prefix

        Returns:
            dict with sync results and storage stats
        """
        results = {
            "pages": None,
            "databases": None,
            "archived": 0,
            "facts_added": 0,
        }

        # Sync pages
        pages_result = self.sync_pages(query=query)
        results["pages"] = pages_result.items

        # Archive pages
        if evolver and pages_result.items:
            for item in pages_result.items:
                title = ""
                if "properties" in item:
                    for prop in item["properties"].values():
                        if prop.get("type") == "title":
                            title = "".join([
                                t.get("plain_text", "")
                                for t in prop.get("title", [])
                            ])
                            break

                content = f"Notion Page: {title}\n"
                content += f"URL: {item.get('url', '')}\n"
                content += f"Created: {item.get('created_time', '')}\n"
                evolver.archive(
                    content=content,
                    kind="notion_page",
                    source=f"{source_prefix}:pages",
                    ref=item.get("url", ""),
                    meta=item
                )
                results["archived"] += 1

            # Extract facts from pages
            page_text = "\n".join([
                f"Notion page: {p.get('url', '')}"
                for p in pages_result.items
            ])
            facts = evolver.learn_extracted(page_text, source=f"{source_prefix}:pages")
            results["facts_added"] += sum(1 for f in facts if f.get("action") == "add")

        # Sync databases
        dbs_result = self.sync_databases(query=query)
        results["databases"] = dbs_result.items

        # Archive databases
        if evolver and dbs_result.items:
            for item in dbs_result.items:
                title = ""
                if "title" in item:
                    title = "".join([
                        t.get("plain_text", "")
                        for t in item.get("title", [])
                    ])

                content = f"Notion Database: {title}\n"
                content += f"URL: {item.get('url', '')}\n"
                content += f"Created: {item.get('created_time', '')}\n"
                evolver.archive(
                    content=content,
                    kind="notion_database",
                    source=f"{source_prefix}:databases",
                    ref=item.get("url", ""),
                    meta=item
                )
                results["archived"] += 1

            # Extract facts from databases
            db_text = "\n".join([
                f"Notion database: {d.get('url', '')}"
                for d in dbs_result.items
            ])
            facts = evolver.learn_extracted(db_text, source=f"{source_prefix}:databases")
            results["facts_added"] += sum(1 for f in facts if f.get("action") == "add")

        return results
