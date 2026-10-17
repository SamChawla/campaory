"""Fetch a public web page without opening an SSRF hole (T2.4).

Only http(s) on the default ports, no credentials in the URL, no localhost names. The host is
resolved once, every address must be public, and the connection is pinned to that address
(Host header and TLS SNI keep the name), so a second DNS answer cannot redirect us inward.
Redirects are followed by hand and each hop is checked the same way. 1 MB cap, 5 s deadline.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from email.message import Message
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.core.errors import AppError

MAX_BYTES = 1_000_000
TIMEOUT_SECONDS = 5.0
MAX_REDIRECTS = 3
ALLOWED_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})
USER_AGENT = "CampaoryFetcher/1.0 (+reads one event page on request)"
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
_REDIRECTS = frozenset({301, 302, 303, 307, 308})

Resolver = Callable[[str], Awaitable[list[str]]]


class FetchFailed(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(422, "fetch_failed", message)


@dataclass(frozen=True)
class FetchedPage:
    url: str
    content_type: str
    text: str


async def system_resolver(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


async def safe_fetch(
    url: str,
    *,
    resolver: Resolver = system_resolver,
    timeout: float = TIMEOUT_SECONDS,
    max_bytes: int = MAX_BYTES,
) -> FetchedPage:
    try:
        async with asyncio.timeout(timeout):
            return await _fetch(url, resolver, timeout, max_bytes)
    except TimeoutError as exc:
        raise FetchFailed("The page took too long to load. Paste the text instead.") from exc


async def _fetch(url: str, resolver: Resolver, timeout: float, max_bytes: int) -> FetchedPage:
    parts, host = _check_url(url)
    ip = await _resolve_public(host, resolver)
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, trust_env=False
    ) as client:
        current = url
        for hop in range(MAX_REDIRECTS + 1):
            if hop:
                parts, host = _check_url(current)
                ip = await _resolve_public(host, resolver)
            request = _pinned_request(client, parts, host, ip)
            try:
                response = await client.send(request, stream=True)
            except httpx.HTTPError as exc:
                raise FetchFailed("Could not load that page. Paste the text instead.") from exc
            try:
                if response.status_code in _REDIRECTS and "location" in response.headers:
                    current = urljoin(current, response.headers["location"])
                    continue
                return await _read(response, current, max_bytes)
            finally:
                await response.aclose()
    raise FetchFailed("That link redirects too many times.")


def _check_url(url: str):
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise FetchFailed("That is not a valid web address.") from exc
    if parts.scheme not in ("http", "https"):
        raise FetchFailed("Only http and https links can be fetched.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise FetchFailed("That is not a valid web address.")
    if parts.username is not None or parts.password is not None:
        raise FetchFailed("Links with a user name or password are not allowed.")
    if port not in (None, 80, 443):
        raise FetchFailed("Only links on the standard web ports can be fetched.")
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        raise FetchFailed("That address is not allowed.")
    return parts, host


async def _resolve_public(host: str, resolver: Resolver) -> str:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            addresses = await resolver(host)
        except (OSError, UnicodeError) as exc:
            raise FetchFailed("Could not find that website.") from exc
    if not addresses or not all(_is_public(a) for a in addresses):
        raise FetchFailed("That address is not allowed.")
    return addresses[0]


def _is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _pinned_request(client: httpx.AsyncClient, parts, host: str, ip: str) -> httpx.Request:
    ip_host = f"[{ip}]" if ":" in ip else ip
    netloc = ip_host if parts.port is None else f"{ip_host}:{parts.port}"
    target = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    host_header = host if parts.port is None else f"{host}:{parts.port}"
    extensions = {"sni_hostname": host} if parts.scheme == "https" else {}
    return client.build_request(
        "GET",
        target,
        headers={
            "Host": host_header,
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
        },
        extensions=extensions,
    )


async def _read(response: httpx.Response, url: str, max_bytes: int) -> FetchedPage:
    if response.status_code >= 400:
        raise FetchFailed(f"The page answered with HTTP {response.status_code}.")
    if response.status_code != 200:
        raise FetchFailed("The page did not return content.")
    content_type, charset = _content_type(response.headers.get("content-type", "text/html"))
    if content_type not in ALLOWED_TYPES:
        raise FetchFailed("That link is not a web page. Paste the text instead.")
    too_big = FetchFailed("The page is larger than 1 MB. Paste the text instead.")
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise too_big
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise too_big
    try:
        text = bytes(body).decode(charset or "utf-8", errors="replace")
    except LookupError:
        text = bytes(body).decode("utf-8", errors="replace")
    return FetchedPage(url=url, content_type=content_type, text=text)


def _content_type(header: str) -> tuple[str, str | None]:
    message = Message()
    message["content-type"] = header
    return message.get_content_type(), message.get_content_charset()
