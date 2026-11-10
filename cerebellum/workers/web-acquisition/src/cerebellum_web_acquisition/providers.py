from __future__ import annotations

import asyncio
import html
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from .mediacrawler_bridge import (
    MC_PLATFORM_CODES,
    MC_PROVIDER_VERSION,
    compose_detail_text,
    configured_dir,
    kind_for_url,
    read_jsonl,
    run_mediacrawler,
)
from .policy import (
    MAX_DOCUMENT_BYTES,
    PolicyError,
    canonicalize_url,
    classify_http_status,
    fetch_public_url,
    parse_retry_after,
)


@dataclass
class ProviderResult:
    method: str
    outcome: str
    url: str
    title: str = ""
    cleaned_content: str | None = None
    raw_content: bytes | None = None
    content_type: str = "text/plain"
    discovered_urls: list[str] = field(default_factory=list)
    http_status: int | None = None
    retry_after_seconds: int | None = None
    error_code: str | None = None
    metadata: dict = field(default_factory=dict)


class _ContentParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self.canonical: str | None = None
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): value for name, value in attrs}
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._ignored_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a" and values.get("href"):
            self.links.append(urljoin(self.base_url, values["href"] or ""))
        if tag == "link" and (values.get("rel") or "").lower() == "canonical":
            if values.get("href"):
                self.canonical = urljoin(self.base_url, values["href"] or "")
        if tag in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        value = " ".join(data.split())
        if not value:
            return
        if self._in_title:
            self.title_parts.append(value)
        self.text_parts.append(value)

    def result(self) -> tuple[str, str, list[str], str | None]:
        title = " ".join(self.title_parts).strip()
        text = "\n".join(
            line.strip()
            for line in " ".join(self.text_parts).splitlines()
            if line.strip()
        )
        return title, text, self.links, self.canonical


def _decode_body(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset\s*=\s*['\"]?([^;'\"\s]+)", content_type, re.I)
    if match:
        charset = match.group(1)
    try:
        return body.decode(charset, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def _challenge_outcome(text: str) -> str | None:
    sample = text[:100_000].lower()
    if any(
        value in sample
        for value in (
            "g-recaptcha",
            "hcaptcha",
            "cf-turnstile",
            "captcha challenge",
            "verify you are human",
        )
    ):
        return "captcha"
    if any(
        value in sample
        for value in (
            "checking your browser",
            "just a moment...",
            "enable javascript and cookies to continue",
            "access denied |",
        )
    ):
        return "explicit_challenge"
    return None


def _safe_links(values: list[str], allowed_domains: list[str], limit: int = 500) -> list[str]:
    result: list[str] = []
    for value in values:
        try:
            canonical = canonicalize_url(value, allowed_domains)
        except PolicyError:
            continue
        if canonical not in result:
            result.append(canonical)
        if len(result) >= limit:
            break
    return result


def _robots_allowed(url: str, policy: dict) -> ProviderResult | None:
    if not policy.get("obey_robots", True):
        return None
    parsed = urlsplit(url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    try:
        response = fetch_public_url(robots_url, policy.get("allowed_domains", []))
    except PolicyError as error:
        if error.outcome in {"timeout", "server_error"}:
            return ProviderResult(
                "direct_http", error.outcome, url, error_code="robots_unavailable"
            )
        return ProviderResult("direct_http", "robots_denied", url, error_code="robots_policy")
    if response.status in {404, 410}:
        return None
    if response.status in {401, 403}:
        return ProviderResult(
            "direct_http",
            "robots_denied",
            url,
            http_status=response.status,
            error_code="robots_forbidden",
        )
    outcome = classify_http_status(response.status)
    if outcome != "success":
        return ProviderResult(
            "direct_http",
            outcome,
            url,
            http_status=response.status,
            retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
            error_code="robots_fetch_failed",
        )
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(_decode_body(response.body, response.headers.get("content-type", "")).splitlines())
    if not parser.can_fetch("cerebellum-web-acquisition-worker/0.1", url):
        return ProviderResult(
            "direct_http", "robots_denied", url, error_code="robots_disallow"
        )
    return None


class DirectProvider:
    method = "direct_http"

    def run(self, url: str, payload: dict, previous: ProviderResult | None = None) -> ProviderResult:
        policy = payload["source_policy"]
        denied = _robots_allowed(url, policy)
        if denied is not None:
            return denied
        try:
            response = fetch_public_url(url, policy.get("allowed_domains", []))
        except PolicyError as error:
            return ProviderResult(
                self.method, error.outcome, url, error_code=error.outcome
            )
        outcome = classify_http_status(response.status)
        if outcome != "success":
            return ProviderResult(
                self.method,
                outcome,
                response.final_url,
                http_status=response.status,
                retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
                error_code=f"http_{response.status}",
            )
        content_type = response.headers.get("content-type", "application/octet-stream")
        text = _decode_body(response.body, content_type)
        challenge = _challenge_outcome(text)
        if challenge:
            return ProviderResult(
                self.method,
                challenge,
                response.final_url,
                raw_content=response.body,
                content_type=content_type,
                http_status=response.status,
                error_code=challenge,
            )
        if "html" in content_type.lower() or "<html" in text[:1000].lower():
            parser = _ContentParser(response.final_url)
            try:
                parser.feed(text)
            except Exception:
                return ProviderResult(
                    self.method,
                    "parse_failed",
                    response.final_url,
                    raw_content=response.body,
                    content_type=content_type,
                    http_status=response.status,
                    error_code="invalid_html",
                )
            title, cleaned, links, canonical = parser.result()
            if canonical:
                try:
                    canonicalize_url(canonical, policy.get("allowed_domains", []))
                except PolicyError:
                    canonical = None
            safe_links = _safe_links(links, policy.get("allowed_domains", []))
            script_count = len(re.findall(r"<script\b", text, re.I))
            if len(cleaned) < 80:
                page_outcome = "js_shell" if script_count >= 2 else "partial_content"
            else:
                page_outcome = "success"
            return ProviderResult(
                self.method,
                page_outcome,
                canonical or response.final_url,
                title=title,
                cleaned_content=cleaned or None,
                raw_content=response.body,
                content_type=content_type,
                discovered_urls=safe_links,
                http_status=response.status,
                metadata={"canonical_hint": canonical, "script_count": script_count},
            )
        cleaned = text.strip()
        return ProviderResult(
            self.method,
            "success" if len(cleaned) >= 20 else "partial_content",
            response.final_url,
            cleaned_content=cleaned or None,
            raw_content=response.body,
            content_type=content_type,
            http_status=response.status,
        )


class Crawl4AIProvider:
    method = "crawl4ai"

    def run(self, url: str, payload: dict, previous: ProviderResult | None = None) -> ProviderResult:
        if os.environ.get("CEREBELLUM_ENABLE_CRAWL4AI") != "1":
            return ProviderResult(
                self.method, "parse_failed", url, error_code="provider_disabled"
            )
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        except ImportError:
            return ProviderResult(
                self.method, "parse_failed", url, error_code="provider_unavailable"
            )

        async def crawl() -> object:
            config = CrawlerRunConfig(
                word_count_threshold=10,
                exclude_external_links=False,
                remove_overlay_elements=False,
            )
            async with AsyncWebCrawler() as crawler:
                return await crawler.arun(url=url, config=config)

        try:
            result = asyncio.run(crawl())
            if not getattr(result, "success", False):
                message = str(getattr(result, "error_message", "crawl failed")).lower()
                outcome = "explicit_challenge" if "challenge" in message else "parse_failed"
                return ProviderResult(self.method, outcome, url, error_code="crawl_failed")
            markdown = getattr(result, "markdown", None)
            if hasattr(markdown, "raw_markdown"):
                markdown = markdown.raw_markdown
            cleaned = str(markdown or "").strip()
            html_value = str(getattr(result, "html", "") or "")
            challenge = _challenge_outcome(html_value)
            if challenge:
                return ProviderResult(self.method, challenge, url, error_code=challenge)
            links_value = getattr(result, "links", {}) or {}
            links: list[str] = []
            if isinstance(links_value, dict):
                for group in links_value.values():
                    if isinstance(group, list):
                        for item in group:
                            if isinstance(item, dict) and isinstance(item.get("href"), str):
                                links.append(item["href"])
            safe = _safe_links(links, payload["source_policy"].get("allowed_domains", []))
            return ProviderResult(
                self.method,
                "success" if len(cleaned) >= 80 else "partial_content",
                url,
                title=str(getattr(result, "title", "") or ""),
                cleaned_content=cleaned or None,
                raw_content=html_value.encode("utf-8")[:MAX_DOCUMENT_BYTES] or None,
                content_type="text/html; charset=utf-8",
                discovered_urls=safe,
                metadata={"provider_version": "0.9.2"},
            )
        except Exception:
            return ProviderResult(
                self.method, "parse_failed", url, error_code="provider_error"
            )


def _configured_service_url(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default or "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured")
    parsed = urlsplit(value)
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError(f"{name} must use HTTPS or loopback")
    return value.rstrip("/")


def _json_service_request(
    base_url: str,
    path: str,
    body: dict,
    headers: dict[str, str],
    timeout: float = 120.0,
) -> tuple[int, dict[str, str], dict]:
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_DOCUMENT_BYTES + 1)
            if len(data) > MAX_DOCUMENT_BYTES:
                raise RuntimeError("provider response exceeds the maximum size")
            return (
                response.status,
                {name.lower(): value for name, value in response.headers.items()},
                json.loads(data or b"{}"),
            )
    except urllib.error.HTTPError as error:
        data = error.read(min(MAX_DOCUMENT_BYTES, 65_536))
        try:
            value = json.loads(data or b"{}")
        except json.JSONDecodeError:
            value = {}
        return error.code, {name.lower(): value for name, value in error.headers.items()}, value


class FirecrawlProvider:
    method = "firecrawl"

    def run(self, url: str, payload: dict, previous: ProviderResult | None = None) -> ProviderResult:
        try:
            base_url = _configured_service_url("FIRECRAWL_BASE_URL")
        except RuntimeError:
            return ProviderResult(
                self.method, "parse_failed", url, error_code="provider_disabled"
            )
        key = os.environ.get("FIRECRAWL_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            status, response_headers, value = _json_service_request(
                base_url,
                "/v1/scrape",
                {"url": url, "formats": ["markdown", "links"], "onlyMainContent": True},
                headers,
            )
        except Exception:
            return ProviderResult(
                self.method, "server_error", url, retry_after_seconds=60, error_code="provider_error"
            )
        outcome = classify_http_status(status)
        if outcome != "success":
            return ProviderResult(
                self.method,
                outcome,
                url,
                http_status=status,
                retry_after_seconds=parse_retry_after(response_headers.get("retry-after")),
                error_code=f"provider_http_{status}",
            )
        data = value.get("data", value) if isinstance(value, dict) else {}
        markdown = data.get("markdown", "") if isinstance(data, dict) else ""
        metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
        links = data.get("links", []) if isinstance(data, dict) else []
        cleaned = str(markdown or "").strip()
        if _challenge_outcome(cleaned):
            challenge = _challenge_outcome(cleaned) or "explicit_challenge"
            return ProviderResult(self.method, challenge, url, error_code=challenge)
        return ProviderResult(
            self.method,
            "success" if len(cleaned) >= 80 else "partial_content",
            url,
            title=str(metadata.get("title", "")) if isinstance(metadata, dict) else "",
            cleaned_content=cleaned or None,
            content_type="text/markdown; charset=utf-8",
            discovered_urls=_safe_links(
                [str(item) for item in links if isinstance(item, str)],
                payload["source_policy"].get("allowed_domains", []),
            ),
            http_status=status,
            metadata={"provider_version": "2.10"},
        )

    def search(self, query: str, payload: dict) -> ProviderResult:
        try:
            base_url = _configured_service_url("FIRECRAWL_BASE_URL")
        except RuntimeError:
            return ProviderResult(self.method, "parse_failed", payload["source_policy"]["base_url"], error_code="provider_disabled")
        key = os.environ.get("FIRECRAWL_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            status, response_headers, value = _json_service_request(
                base_url,
                "/v1/search",
                {"query": query, "limit": min(int(payload["source_policy"].get("max_pages_per_run", 10)), 100)},
                headers,
            )
        except Exception:
            return ProviderResult(self.method, "server_error", payload["source_policy"]["base_url"], retry_after_seconds=60, error_code="provider_error")
        outcome = classify_http_status(status)
        if outcome != "success":
            return ProviderResult(
                self.method,
                outcome,
                payload["source_policy"]["base_url"],
                http_status=status,
                retry_after_seconds=parse_retry_after(response_headers.get("retry-after")),
                error_code=f"provider_http_{status}",
            )
        data = value.get("data", []) if isinstance(value, dict) else []
        urls = [item.get("url") for item in data if isinstance(item, dict)]
        return ProviderResult(
            self.method,
            "partial_content",
            payload["source_policy"]["base_url"],
            discovered_urls=_safe_links(
                [str(item) for item in urls if isinstance(item, str)],
                payload["source_policy"].get("allowed_domains", []),
            ),
            http_status=status,
            error_code="search_results_only",
        )


class LinkMapperProvider:
    method = "link_mapper"

    def run(self, url: str, payload: dict, previous: ProviderResult | None = None) -> ProviderResult:
        policy = payload["source_policy"]
        parsed = urlsplit(url)
        sitemap_url = urlunsplit((parsed.scheme, parsed.netloc, "/sitemap.xml", "", ""))
        links = list(previous.discovered_urls if previous else [])
        try:
            response = fetch_public_url(sitemap_url, policy.get("allowed_domains", []))
            if response.status == 200:
                xml = _decode_body(response.body, response.headers.get("content-type", ""))
                links.extend(html.unescape(item) for item in re.findall(r"(?is)<loc>\s*(.*?)\s*</loc>", xml))
            elif response.status == 429 or response.status >= 500:
                return ProviderResult(
                    self.method,
                    classify_http_status(response.status),
                    url,
                    retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
                    http_status=response.status,
                    error_code="sitemap_unavailable",
                )
        except PolicyError as error:
            if error.outcome in {"timeout", "server_error"}:
                return ProviderResult(
                    self.method,
                    error.outcome,
                    url,
                    retry_after_seconds=60,
                    error_code="sitemap_unavailable",
                )
        safe = _safe_links(links, policy.get("allowed_domains", []))
        return ProviderResult(
            self.method,
            "partial_content",
            url,
            cleaned_content=previous.cleaned_content if previous else None,
            raw_content=previous.raw_content if previous else None,
            content_type=previous.content_type if previous else "text/plain",
            discovered_urls=safe,
            error_code="link_map_only",
        )


class ScraplingProvider:
    method = "scrapling"

    def run(self, url: str, payload: dict, previous: ProviderResult | None = None) -> ProviderResult:
        if os.environ.get("CEREBELLUM_ENABLE_SCRAPLING") != "1":
            return ProviderResult(self.method, "parse_failed", url, error_code="provider_disabled")
        try:
            from scrapling.fetchers import StealthyFetcher
        except ImportError:
            return ProviderResult(self.method, "parse_failed", url, error_code="provider_unavailable")
        try:
            page = StealthyFetcher.fetch(
                url,
                headless=True,
                network_idle=True,
                disable_resources=True,
            )
            text = str(getattr(page, "text", "") or "")
            html_value = str(getattr(page, "html_content", "") or page)
            challenge = _challenge_outcome(html_value)
            if challenge:
                return ProviderResult(self.method, challenge, url, error_code=challenge)
            links = []
            try:
                links = [str(item.attrib.get("href")) for item in page.css("a[href]")]
            except Exception:
                links = []
            return ProviderResult(
                self.method,
                "success" if len(text.strip()) >= 80 else "partial_content",
                url,
                cleaned_content=text.strip() or None,
                raw_content=html_value.encode("utf-8")[:MAX_DOCUMENT_BYTES] or None,
                content_type="text/html; charset=utf-8",
                discovered_urls=_safe_links(links, payload["source_policy"].get("allowed_domains", [])),
                metadata={"provider_version": "0.4.8", "identity_rotation": False},
            )
        except Exception:
            return ProviderResult(self.method, "parse_failed", url, error_code="provider_error")


class OpenCLIProvider:
    method = "open_cli"

    def run(self, url: str, payload: dict, previous: ProviderResult | None = None) -> ProviderResult:
        if payload["source_policy"].get("access_mode") != "authenticated_local":
            return ProviderResult(self.method, "policy_denied", url, error_code="local_auth_not_allowed")
        executable = os.environ.get("OPENCLI_BRIDGE_EXECUTABLE", "").strip()
        session = os.environ.get("OPENCLI_SESSION", "").strip()
        if (
            os.environ.get("CEREBELLUM_ENABLE_OPENCLI") != "1"
            or not executable
            or not Path(executable).is_absolute()
            or not Path(executable).is_file()
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", session)
        ):
            return ProviderResult(self.method, "auth_required", url, error_code="local_bridge_disabled")
        safe_environment = {
            name: os.environ[name]
            for name in ("PATH", "SYSTEMROOT", "WINDIR", "LOCALAPPDATA", "APPDATA", "HOME")
            if name in os.environ
        }
        command = [executable, "--session", session, "--url", url, "--json"]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
                shell=False,
                env=safe_environment,
            )
            if completed.returncode != 0:
                return ProviderResult(self.method, "parse_failed", url, error_code="local_bridge_failed")
            if len(completed.stdout) > MAX_DOCUMENT_BYTES:
                return ProviderResult(self.method, "policy_denied", url, error_code="bridge_output_too_large")
            value = json.loads(completed.stdout or b"{}")
            final_url = canonicalize_url(
                str(value.get("url", url)), payload["source_policy"].get("allowed_domains", [])
            )
            cleaned = str(value.get("markdown", "") or "").strip()
            challenge = _challenge_outcome(cleaned)
            if challenge:
                return ProviderResult(self.method, challenge, final_url, error_code=challenge)
            links = value.get("links", []) if isinstance(value.get("links", []), list) else []
            return ProviderResult(
                self.method,
                "success" if len(cleaned) >= 80 else "partial_content",
                final_url,
                title=str(value.get("title", "") or ""),
                cleaned_content=cleaned or None,
                content_type="text/markdown; charset=utf-8",
                discovered_urls=_safe_links(
                    [str(item) for item in links if isinstance(item, str)],
                    payload["source_policy"].get("allowed_domains", []),
                ),
                metadata={"provider_version": "1.8.4", "local_session": True},
            )
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, PolicyError):
            return ProviderResult(self.method, "parse_failed", url, error_code="local_bridge_error")


class MediaCrawlerDetailProvider:
    """Login-walled platform detail + comments via the pinned MediaCrawler CLI.

    Final ladder rung before open_cli: only applicable to hosts MediaCrawler
    covers, only for authenticated_local policies (content lives behind the
    operator's local login session), only when explicitly enabled.
    """

    method = "mediacrawler"

    def run(self, url: str, payload: dict, previous: ProviderResult | None = None) -> ProviderResult:
        if payload["source_policy"].get("access_mode") != "authenticated_local":
            return ProviderResult(self.method, "policy_denied", url, error_code="local_auth_not_allowed")
        if os.environ.get("CEREBELLUM_ENABLE_MEDIACRAWLER") != "1" or configured_dir() is None:
            return ProviderResult(self.method, "parse_failed", url, error_code="provider_disabled")
        kind = kind_for_url(url)
        if kind is None:
            return ProviderResult(self.method, "parse_failed", url, error_code="provider_not_applicable")
        if kind == "xhs" and "xsec_token=" not in url:
            # MC xhs detail requires the signed token; board SSR links carry it.
            return ProviderResult(self.method, "parse_failed", url, error_code="provider_not_applicable")
        code = MC_PLATFORM_CODES[kind]
        try:
            tmp = run_mediacrawler(code, "detail", specified=url, notes_limit=1)
        except RuntimeError:
            return ProviderResult(self.method, "parse_failed", url, error_code="mediacrawler_failed")
        contents = read_jsonl(tmp, code, "detail", "contents")
        if not contents:
            return ProviderResult(self.method, "parse_failed", url, error_code="empty_detail")
        comments = read_jsonl(tmp, code, "detail", "comments")
        title, text = compose_detail_text(contents, comments, max_comments=20)
        return ProviderResult(
            self.method,
            "success" if len(text) >= 80 else "partial_content",
            url,
            title=title,
            cleaned_content=text or None,
            content_type="text/markdown; charset=utf-8",
            discovered_urls=[],
            metadata={"provider_version": MC_PROVIDER_VERSION, "local_session": True},
        )


class TavilyProvider:
    method = "api"

    def search(self, query: str, payload: dict) -> ProviderResult:
        key = os.environ.get("TAVILY_API_KEY", "").strip()
        if not key:
            return ProviderResult(self.method, "auth_required", payload["source_policy"]["base_url"], error_code="provider_disabled")
        try:
            base_url = _configured_service_url("TAVILY_BASE_URL", "https://api.tavily.com")
            status, response_headers, value = _json_service_request(
                base_url,
                "/search",
                {
                    "api_key": key,
                    "query": query,
                    "max_results": min(int(payload["source_policy"].get("max_pages_per_run", 10)), 20),
                    "search_depth": "advanced",
                },
                {},
                timeout=60,
            )
        except Exception:
            return ProviderResult(self.method, "server_error", payload["source_policy"]["base_url"], retry_after_seconds=60, error_code="provider_error")
        outcome = classify_http_status(status)
        if outcome != "success":
            return ProviderResult(
                self.method,
                outcome,
                payload["source_policy"]["base_url"],
                http_status=status,
                retry_after_seconds=parse_retry_after(response_headers.get("retry-after")),
                error_code=f"provider_http_{status}",
            )
        results = value.get("results", []) if isinstance(value, dict) else []
        urls = [item.get("url") for item in results if isinstance(item, dict)]
        return ProviderResult(
            self.method,
            "partial_content",
            payload["source_policy"]["base_url"],
            discovered_urls=_safe_links(
                [str(item) for item in urls if isinstance(item, str)],
                payload["source_policy"].get("allowed_domains", []),
            ),
            http_status=status,
            error_code="search_results_only",
        )
