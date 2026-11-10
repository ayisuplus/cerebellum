from __future__ import annotations

import email.utils
import http.client
import ipaddress
import socket
import ssl
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

MAX_URL_LENGTH = 8_192
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 5
TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref_src",
}


class PolicyError(RuntimeError):
    def __init__(self, message: str, outcome: str = "policy_denied") -> None:
        super().__init__(message)
        self.outcome = outcome


@dataclass(frozen=True)
class FetchResponse:
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes


def _normalize_allowed_domain(value: str) -> str:
    value = value.strip().rstrip(".").lower()
    if ":" in value or "/" in value or "@" in value:
        raise PolicyError("source allowlist contains an invalid domain")
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise PolicyError("source allowlist contains an invalid domain") from error


def host_allowed(host: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return True
    normalized = [_normalize_allowed_domain(value) for value in allowed_domains]
    return any(host == allowed or host.endswith("." + allowed) for allowed in normalized)


def _public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.is_global and not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def canonicalize_url(value: str, allowed_domains: list[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_URL_LENGTH:
        raise PolicyError("URL is empty or exceeds the maximum length")
    if "\\" in value or "\x00" in value:
        raise PolicyError("URL contains a forbidden character")
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise PolicyError("only HTTP(S) URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise PolicyError("credential-bearing URLs are forbidden")
    if not parsed.hostname:
        raise PolicyError("URL must include a host")
    try:
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise PolicyError("URL host is invalid") from error
    if host in {"localhost", "localhost.localdomain"} or host.endswith(
        (".localhost", ".local", ".internal", ".home.arpa")
    ):
        raise PolicyError("local hostnames are forbidden")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not _public_ip(str(literal)):
        raise PolicyError("non-public IP addresses are forbidden")
    if not host_allowed(host, allowed_domains or []):
        raise PolicyError("URL host is outside the source policy allowlist")
    try:
        port = parsed.port
    except ValueError as error:
        raise PolicyError("URL port is invalid") from error
    if port is not None and not 1 <= port <= 65_535:
        raise PolicyError("URL port is invalid")
    default_port = (parsed.scheme.lower() == "https" and port == 443) or (
        parsed.scheme.lower() == "http" and port == 80
    )
    host_display = f"[{host}]" if ":" in host else host
    netloc = host_display if port is None or default_port else f"{host_display}:{port}"
    pairs = [
        (name, item)
        for name, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not name.lower().startswith("utm_") and name.lower() not in TRACKING_PARAMETERS
    ]
    pairs.sort()
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path or "/",
            urlencode(pairs, doseq=True),
            "",
        )
    )


def resolve_public_addresses(host: str, port: int) -> list[str]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        values = [str(literal)]
    else:
        try:
            values = sorted(
                {
                    item[4][0]
                    for item in socket.getaddrinfo(
                        host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
                    )
                }
            )
        except socket.gaierror as error:
            raise PolicyError("host DNS resolution failed", "timeout") from error
    if not values or any(not _public_ip(value) for value in values):
        raise PolicyError("host resolves to a forbidden address")
    return values


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(host, port=port, timeout=timeout)
        self._address = address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._address, self.port), self.timeout, self.source_address
        )
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._address = address

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._address, self.port), self.timeout, self.source_address
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _read_bounded(response: http.client.HTTPResponse, maximum: int) -> bytes:
    encoding = response.getheader("content-encoding", "").strip().lower()
    length = response.getheader("content-length")
    if encoding in {"", "identity"} and length:
        try:
            if int(length) > maximum:
                raise PolicyError("response exceeds the maximum size", "policy_denied")
        except ValueError as error:
            raise PolicyError("response has an invalid Content-Length", "parse_failed") from error
    if encoding not in {"", "identity", "gzip", "x-gzip", "deflate"}:
        raise PolicyError("unsupported content encoding", "parse_failed")
    decoder = None
    if encoding in {"gzip", "x-gzip"}:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif encoding == "deflate":
        decoder = zlib.decompressobj()
    output = bytearray()
    compressed = 0
    while True:
        chunk = response.read(65_536)
        if not chunk:
            break
        compressed += len(chunk)
        if compressed > maximum:
            raise PolicyError("compressed response exceeds the maximum size")
        if decoder is None:
            output.extend(chunk)
        else:
            remaining = maximum - len(output)
            decoded = decoder.decompress(chunk, remaining + 1)
            output.extend(decoded)
            if decoder.unconsumed_tail:
                raise PolicyError("decompressed response exceeds the maximum size")
        if len(output) > maximum:
            raise PolicyError("response exceeds the maximum size")
    if decoder is not None:
        remaining = maximum - len(output)
        output.extend(decoder.flush(remaining + 1))
        if len(output) > maximum:
            raise PolicyError("decompressed response exceeds the maximum size")
    return bytes(output)


def fetch_public_url(
    value: str,
    allowed_domains: list[str] | None = None,
    *,
    timeout_seconds: float = 30.0,
    headers: dict[str, str] | None = None,
) -> FetchResponse:
    current = canonicalize_url(value, allowed_domains)
    for redirect_count in range(MAX_REDIRECTS + 1):
        parsed = urlsplit(current)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = resolve_public_addresses(parsed.hostname or "", port)
        connection_type = (
            _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
        )
        connection = connection_type(
            parsed.hostname or "", port, addresses[0], timeout_seconds
        )
        request_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml,text/plain,application/json,*/*;q=0.1",
            "Accept-Encoding": "identity",
            "Connection": "close",
            "Host": parsed.hostname or "",
            "User-Agent": "cerebellum-web-acquisition-worker/0.1",
        }
        request_headers.update(headers or {})
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        try:
            connection.request("GET", path, headers=request_headers)
            response = connection.getresponse()
            response_headers = {name.lower(): item for name, item in response.getheaders()}
            if response.status in {301, 302, 303, 307, 308}:
                if redirect_count == MAX_REDIRECTS:
                    raise PolicyError("redirect limit exceeded")
                location = response_headers.get("location")
                if not location:
                    raise PolicyError("redirect lacks a Location header")
                current = canonicalize_url(urljoin(current, location), allowed_domains)
                response.read(4096)
                continue
            body = _read_bounded(response, MAX_DOCUMENT_BYTES)
            return FetchResponse(current, response.status, response_headers, body)
        except (TimeoutError, socket.timeout) as error:
            raise PolicyError("network request timed out", "timeout") from error
        except (OSError, http.client.HTTPException) as error:
            raise PolicyError("network request failed", "server_error") from error
        finally:
            connection.close()
    raise PolicyError("redirect limit exceeded")


def classify_http_status(status: int) -> str:
    if 200 <= status <= 299:
        return "success"
    if status in {401, 403}:
        return "auth_required"
    if status == 404:
        return "not_found"
    if status == 410:
        return "gone"
    if status == 429:
        return "rate_limited"
    if 500 <= status <= 599:
        return "server_error"
    return "policy_denied"


def parse_retry_after(value: str | None, default: int = 60) -> int:
    if not value:
        return default
    try:
        return max(1, min(int(value.strip()), 86_400))
    except ValueError:
        try:
            moment = email.utils.parsedate_to_datetime(value)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return max(
                1,
                min(int((moment - datetime.now(timezone.utc)).total_seconds()), 86_400),
            )
        except (TypeError, ValueError, OverflowError):
            return default


def escalation_action(method: str, outcome: str, access_mode: str) -> str | None:
    if outcome == "success":
        return None
    if outcome in {"rate_limited", "timeout", "server_error"}:
        return "retry"
    if outcome in {
        "robots_denied",
        "captcha",
        "explicit_challenge",
        "policy_denied",
        "not_found",
        "gone",
    }:
        return None
    if outcome == "auth_required":
        return "open_cli" if access_mode == "authenticated_local" else None
    if outcome not in {"partial_content", "js_shell", "parse_failed"}:
        return None
    return {
        "api": "crawl4ai",
        "rss": "crawl4ai",
        "direct_http": "crawl4ai",
        "crawl4ai": "firecrawl",
        "firecrawl": "link_mapper",
        "link_mapper": "scrapling",
        "scrapling": "mediacrawler",
        "mediacrawler": "open_cli" if access_mode == "authenticated_local" else None,
        "open_cli": None,
    }.get(method)
