import asyncio

import httpx
import pytest
import respx

from app.core.errors import AppError
from app.fetch.safe_fetch import MAX_BYTES, safe_fetch

PUBLIC_IP = "93.184.216.34"
HTML = "<html><body><h1>Hack Day</h1></body></html>"


def resolver_for(mapping: dict[str, list[str]]):
    calls: list[str] = []

    async def resolve(host: str) -> list[str]:
        calls.append(host)
        if host not in mapping:
            raise OSError("no such host")
        return mapping[host]

    resolve.calls = calls
    return resolve


PUBLIC = resolver_for({"events.example.com": [PUBLIC_IP], "other.example.net": ["93.184.216.35"]})


def html_response(body: str = HTML, **kw) -> httpx.Response:
    headers = {"content-type": "text/html; charset=utf-8", **kw.pop("headers", {})}
    return httpx.Response(200, text=body, headers=headers, **kw)


@respx.mock
async def test_fetches_public_page_pinned_to_resolved_ip():
    route = respx.get(f"http://{PUBLIC_IP}/hack-day").mock(return_value=html_response())

    page = await safe_fetch("http://events.example.com/hack-day", resolver=PUBLIC)

    assert page.text == HTML
    assert page.url == "http://events.example.com/hack-day"
    assert page.content_type == "text/html"
    assert route.calls.last.request.headers["host"] == "events.example.com"


@respx.mock
async def test_https_keeps_hostname_for_tls():
    route = respx.get(f"https://{PUBLIC_IP}/e?x=1").mock(return_value=html_response())

    await safe_fetch("https://events.example.com/e?x=1", resolver=PUBLIC)

    request = route.calls.last.request
    assert request.headers["host"] == "events.example.com"
    assert request.extensions["sni_hostname"] == "events.example.com"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://localhost/",
        "http://localhost:8000/api/health",
        "http://app.localhost/",
        "file:///etc/passwd",
        "ftp://events.example.com/file",
        "gopher://events.example.com/",
        "javascript:alert(1)",
        "http://user:pass@events.example.com/",
        "http://events.example.com:22/",
        "not a url",
        "http://",
    ],
)
async def test_blocks_unsafe_targets(url):
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(AppError) as exc:
            await safe_fetch(url, resolver=PUBLIC)

    assert exc.value.status == 422
    assert exc.value.code == "fetch_failed"
    assert not mock.calls


@pytest.mark.parametrize("ips", [["10.1.2.3"], [PUBLIC_IP, "127.0.0.1"], ["::1"]])
async def test_blocks_hostnames_resolving_to_private_addresses(ips):
    resolver = resolver_for({"rebind.example.com": ips})

    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(AppError) as exc:
            await safe_fetch("http://rebind.example.com/", resolver=resolver)

    assert exc.value.code == "fetch_failed"
    assert not mock.calls


async def test_unresolvable_host_fails():
    with pytest.raises(AppError) as exc:
        await safe_fetch("http://missing.example.org/", resolver=PUBLIC)

    assert exc.value.code == "fetch_failed"


@respx.mock
async def test_redirect_to_private_address_is_blocked():
    respx.get(f"http://{PUBLIC_IP}/go").mock(
        return_value=httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
    )
    internal = respx.get("http://127.0.0.1/secret").mock(return_value=html_response())

    with pytest.raises(AppError) as exc:
        await safe_fetch("http://events.example.com/go", resolver=PUBLIC)

    assert exc.value.code == "fetch_failed"
    assert not internal.called


@respx.mock
async def test_redirect_to_metadata_hostname_is_blocked():
    resolver = resolver_for({"events.example.com": [PUBLIC_IP], "meta.evil": ["169.254.169.254"]})
    respx.get(f"http://{PUBLIC_IP}/go").mock(
        return_value=httpx.Response(301, headers={"location": "http://meta.evil/latest"})
    )

    with pytest.raises(AppError):
        await safe_fetch("http://events.example.com/go", resolver=resolver)


@respx.mock
async def test_follows_safe_relative_and_absolute_redirects():
    respx.get(f"http://{PUBLIC_IP}/a").mock(
        return_value=httpx.Response(302, headers={"location": "/b"})
    )
    respx.get(f"http://{PUBLIC_IP}/b").mock(
        return_value=httpx.Response(307, headers={"location": "https://other.example.net/c"})
    )
    respx.get("https://93.184.216.35/c").mock(return_value=html_response())

    page = await safe_fetch("http://events.example.com/a", resolver=PUBLIC)

    assert page.url == "https://other.example.net/c"
    assert page.text == HTML


@respx.mock
async def test_too_many_redirects_fail():
    respx.get(f"http://{PUBLIC_IP}/loop").mock(
        return_value=httpx.Response(302, headers={"location": "/loop"})
    )

    with pytest.raises(AppError):
        await safe_fetch("http://events.example.com/loop", resolver=PUBLIC)


@respx.mock
async def test_declared_size_over_cap_fails():
    respx.get(f"http://{PUBLIC_IP}/big").mock(
        return_value=html_response(headers={"content-length": str(MAX_BYTES + 1)})
    )

    with pytest.raises(AppError) as exc:
        await safe_fetch("http://events.example.com/big", resolver=PUBLIC)

    assert "1 MB" in exc.value.message


@respx.mock
async def test_streamed_size_over_cap_fails():
    async def chunks():
        for _ in range(20):
            yield b"x" * 60_000

    respx.get(f"http://{PUBLIC_IP}/big").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, content=chunks())
    )

    with pytest.raises(AppError):
        await safe_fetch("http://events.example.com/big", resolver=PUBLIC)


@respx.mock
async def test_network_timeout_fails():
    respx.get(f"http://{PUBLIC_IP}/slow").mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(AppError) as exc:
        await safe_fetch("http://events.example.com/slow", resolver=PUBLIC)

    assert exc.value.code == "fetch_failed"


async def test_overall_deadline_applies():
    async def slow(host: str) -> list[str]:
        await asyncio.sleep(1)
        return [PUBLIC_IP]

    with pytest.raises(AppError) as exc:
        await safe_fetch("http://events.example.com/", resolver=slow, timeout=0.05)

    assert exc.value.code == "fetch_failed"


@respx.mock
async def test_default_timeout_is_five_seconds():
    from app.fetch import safe_fetch as module

    assert module.TIMEOUT_SECONDS == 5


@respx.mock
@pytest.mark.parametrize("status", [404, 500])
async def test_error_status_fails(status):
    respx.get(f"http://{PUBLIC_IP}/x").mock(return_value=httpx.Response(status))

    with pytest.raises(AppError):
        await safe_fetch("http://events.example.com/x", resolver=PUBLIC)


@respx.mock
async def test_non_text_content_fails():
    respx.get(f"http://{PUBLIC_IP}/x.pdf").mock(
        return_value=httpx.Response(
            200, content=b"%PDF", headers={"content-type": "application/pdf"}
        )
    )

    with pytest.raises(AppError):
        await safe_fetch("http://events.example.com/x.pdf", resolver=PUBLIC)


@respx.mock
async def test_plain_text_is_accepted_and_decoded_with_charset():
    respx.get(f"http://{PUBLIC_IP}/t").mock(
        return_value=httpx.Response(
            200,
            content="Café meetup".encode("latin-1"),
            headers={"content-type": "text/plain; charset=iso-8859-1"},
        )
    )

    page = await safe_fetch("http://events.example.com/t", resolver=PUBLIC)

    assert page.text == "Café meetup"
    assert page.content_type == "text/plain"
