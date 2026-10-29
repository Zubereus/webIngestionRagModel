from __future__ import annotations

import ipaddress
import socket
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Iterator
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx

from webrag.fetch.http import DEFAULT_HEADERS
from webrag.models import RawPage

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
MAX_SITEMAP_URLS = 500
MAX_RETRIES = 3
MAX_RETRY_DELAY_SECONDS = 60.0
DEFAULT_REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "WebRAGBot/1.0"
_host_pacing_lock = threading.Lock()
_host_locks_guard = threading.Lock()
_host_request_locks: dict[str, threading.Lock] = {}
_next_host_request: dict[str, float] = {}
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid",
}
DENIED_QUERY_PARAMS = {
    "p", "offset", "limit", "sort", "filter", "category", "search",
    "query", "q",
}


class CrawlFetchError(ValueError):
    pass


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.canonical_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value for key, value in attrs}
        if tag.lower() == "a" and attributes.get("href"):
            self.links.append(attributes["href"] or "")
        if tag.lower() == "link":
            rel = (attributes.get("rel") or "").lower().split()
            href = attributes.get("href")
            if "canonical" in rel and href:
                self.canonical_url = href


def validate_public_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrawlFetchError("Only HTTP and HTTPS URLs with a hostname can be crawled.")
    if parsed.username or parsed.password:
        raise CrawlFetchError("URLs containing credentials cannot be crawled.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise CrawlFetchError("Local and private network addresses cannot be crawled.")

    try:
        addresses = {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            resolved = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise CrawlFetchError(f"Could not resolve host: {hostname}") from exc
        addresses = {ipaddress.ip_address(item[4][0]) for item in resolved}

    if not addresses or any(not address.is_global for address in addresses):
        raise CrawlFetchError("Local and private network addresses cannot be crawled.")
    return hostname


def normalize_crawl_url(url: str, query_allowlist: set[str] | None = None) -> str:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise CrawlFetchError("URL has no hostname.")
    query_allowlist = {key.casefold() for key in (query_allowlist or {"id"})}
    pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        folded_key = key.casefold()
        if folded_key in TRACKING_PARAMS or folded_key in DENIED_QUERY_PARAMS:
            continue
        if folded_key in query_allowlist:
            pairs.append((key, value))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        "",
        urlencode(sorted(pairs)),
        "",
    ))


def should_follow(
    url: str,
    start_host: str,
    allow_paths: list[str] | None = None,
    deny_paths: list[str] | None = None,
) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != start_host:
        return False
    path = parsed.path or "/"
    if any(path.startswith(prefix) for prefix in (deny_paths or [])):
        return False
    return not allow_paths or any(path.startswith(prefix) for prefix in allow_paths)


def _read_limited(response: httpx.Response, max_bytes: int) -> bytes:
    result = bytearray()
    for block in response.iter_bytes():
        result.extend(block)
        if len(result) > max_bytes:
            raise CrawlFetchError(f"Response exceeds the {max_bytes}-byte limit.")
    return bytes(result)


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), MAX_RETRY_DELAY_SECONDS)
        except ValueError:
            try:
                retry_time = parsedate_to_datetime(retry_after)
                if retry_time.tzinfo is None:
                    retry_time = retry_time.replace(tzinfo=timezone.utc)
                delay = (retry_time - datetime.now(timezone.utc)).total_seconds()
                return min(max(delay, 0.0), MAX_RETRY_DELAY_SECONDS)
            except (TypeError, ValueError, OverflowError):
                pass
    return min(0.5 * (2**attempt), MAX_RETRY_DELAY_SECONDS)


def _wait_for_host(host: str, delay: float) -> None:
    with _host_pacing_lock:
        now = time.monotonic()
        next_allowed = _next_host_request.get(host, now)
        wait_seconds = max(0.0, next_allowed - now)
    if wait_seconds:
        time.sleep(wait_seconds)


@contextmanager
def _host_request_slot(host: str, delay: float) -> Iterator[None]:
    with _host_locks_guard:
        host_lock = _host_request_locks.setdefault(host, threading.Lock())
    with host_lock:
        _wait_for_host(host, delay)
        try:
            yield
        finally:
            with _host_pacing_lock:
                _next_host_request[host] = time.monotonic() + max(delay, 0.0)


def _safe_get(
    url: str,
    start_host: str,
    accept: str,
    max_bytes: int = MAX_RESPONSE_BYTES,
    html_only: bool = False,
    same_host: bool = True,
    headers: dict[str, str] | None = None,
    request_delay: float = DEFAULT_REQUEST_DELAY_SECONDS,
) -> tuple[int, str, bytes, str]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": accept}
    if headers:
        request_headers.update(headers)
    current_url = url
    with httpx.Client(
        follow_redirects=False,
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers=request_headers,
        trust_env=False,
    ) as client:
        for redirect_count in range(MAX_REDIRECTS + 1):
            current_host = validate_public_host(current_url)
            if same_host and current_host != start_host:
                raise CrawlFetchError("Redirect or URL leaves the starting host.")
            redirect_url: str | None = None
            for attempt in range(MAX_RETRIES):
                retry_delay: float | None = None
                try:
                    with _host_request_slot(current_host, request_delay):
                        with client.stream("GET", current_url) as response:
                            if (
                                response.status_code == 429
                                or 500 <= response.status_code < 600
                            ) and attempt + 1 < MAX_RETRIES:
                                retry_delay = _retry_delay(
                                    response.headers.get("Retry-After"), attempt
                                )
                            elif response.status_code in {301, 302, 303, 307, 308}:
                                location = response.headers.get("location")
                                if not location or redirect_count == MAX_REDIRECTS:
                                    raise CrawlFetchError(
                                        "Too many redirects or missing redirect target."
                                    )
                                redirect_url = urljoin(current_url, location)
                            else:
                                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                                if html_only and content_type not in {"text/html", "application/xhtml+xml"}:
                                    raise CrawlFetchError(f"Skipped non-HTML content type: {content_type or 'unknown'}.")
                                body = _read_limited(response, max_bytes)
                                return response.status_code, content_type, body, str(response.url)
                except httpx.TransportError:
                    if attempt + 1 == MAX_RETRIES:
                        raise
                    time.sleep(_retry_delay(None, attempt))
                if retry_delay is not None:
                    time.sleep(retry_delay)
                    continue
                if redirect_url:
                    break
            if redirect_url:
                current_url = redirect_url
                continue
            raise CrawlFetchError("Unable to fetch URL after transient failures.")
    raise CrawlFetchError("Unable to fetch URL.")


def fetch_safe_page(url: str) -> RawPage:
    """Fetch one public HTML page safely for the single-page ingestion flow."""
    start_host = validate_public_host(url)
    status, content_type, body, final_url = _safe_get(
        url,
        start_host,
        "text/html,application/xhtml+xml",
        html_only=True,
        same_host=False,
        headers=DEFAULT_HEADERS,
    )
    return RawPage(
        url=url,
        final_url=final_url,
        status=status,
        content_type=content_type,
        body=body,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def fetch_robots(start_url: str, start_host: str) -> RobotFileParser:
    parsed = urlparse(start_url)
    robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    status, _, body, final_url = _safe_get(
        robots_url, start_host, "text/plain", max_bytes=512 * 1024
    )
    parser = RobotFileParser()
    parser.set_url(final_url)
    if status == 404:
        parser.parse([])
    elif status < 400:
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
    else:
        raise CrawlFetchError(f"Could not read robots.txt (HTTP {status}).")
    return parser


def fetch_page(
    url: str,
    start_host: str,
    robots: RobotFileParser,
    request_delay: float | None = None,
) -> tuple[RawPage, list[str], str | None]:
    if not robots.can_fetch(USER_AGENT, url):
        raise CrawlFetchError("Blocked by robots.txt.")
    status, content_type, body, final_url = _safe_get(
        url,
        start_host,
        "text/html,application/xhtml+xml",
        html_only=True,
        request_delay=(
            request_delay
            if request_delay is not None
            else (
                robots.crawl_delay(USER_AGENT)
                or DEFAULT_REQUEST_DELAY_SECONDS
            )
        ),
    )
    raw_page = RawPage(
        url=url,
        final_url=final_url,
        status=status,
        content_type=content_type,
        body=body,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    if status != 200:
        raise CrawlFetchError(f"HTTP {status}.")

    parser = LinkParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    links = [urljoin(final_url, href) for href in parser.links]
    canonical = urljoin(final_url, parser.canonical_url) if parser.canonical_url else None
    return raw_page, links, canonical


def discover_sitemap_urls(
    start_url: str, start_host: str, robots: RobotFileParser | None = None
) -> list[str]:
    robots = robots or fetch_robots(start_url, start_host)
    candidates = robots.site_maps() or [urljoin(start_url, "/sitemap.xml")]
    discovered: list[str] = []
    pending = list(candidates)
    visited_sitemaps: set[str] = set()

    while pending and len(discovered) < MAX_SITEMAP_URLS:
        sitemap_url = pending.pop(0)
        try:
            if validate_public_host(sitemap_url) != start_host:
                continue
            status, _, body, _ = _safe_get(
                sitemap_url,
                start_host,
                "application/xml,text/xml,text/plain",
                max_bytes=2 * 1024 * 1024,
            )
        except (CrawlFetchError, httpx.HTTPError):
            continue
        if status != 200:
            continue
        visited_sitemaps.add(sitemap_url)
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            continue
        root_name = root.tag.rsplit("}", 1)[-1].lower()
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1].lower() != "loc" or not element.text:
                continue
            location = element.text.strip()
            if root_name == "sitemapindex" and location not in visited_sitemaps:
                pending.append(location)
            elif should_follow(location, start_host):
                discovered.append(location)
                if len(discovered) >= MAX_SITEMAP_URLS:
                    break
    return discovered


def normalize_children(
    links: Iterable[str],
    start_host: str,
    query_allowlist: set[str],
    allow_paths: list[str],
    deny_paths: list[str],
) -> list[str]:
    normalized = set()
    for link in links:
        try:
            candidate = normalize_crawl_url(link, query_allowlist)
            if should_follow(candidate, start_host, allow_paths, deny_paths):
                normalized.add(candidate)
        except CrawlFetchError:
            continue
    return sorted(normalized)
