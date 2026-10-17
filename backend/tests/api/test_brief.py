import functools

import httpx
import pytest
import respx
from helpers import CapturingProvider

from app.fetch.safe_fetch import safe_fetch
from app.llm.base import Completion
from app.llm.mock import MockProvider

PUBLIC_IP = "93.184.216.34"


def by_key(body: dict) -> dict[str, dict]:
    return {f["key"]: f for f in body["facts"]}


def test_sample_returns_canned_facts_without_model_or_limit(client, app):
    provider = CapturingProvider()
    app.state.gate.provider = provider

    for _ in range(app.state.settings.rate_guest_per_hour + 2):
        response = client.post("/api/brief/extract", json={"source": {"kind": "sample"}})
        assert response.status_code == 200

    body = response.json()
    facts = by_key(body)
    assert facts["event_name"]["value"] == "Riverside Open Source Hack Day 2026"
    assert facts["event_name"]["status"] == "needs_review"
    assert facts["event_name"]["critical"] is True
    assert facts["event_name"]["source_ref"] == "sample"
    assert facts["start_date"]["value"] == "2026-10-24"
    assert body["source"]["kind"] == "sample"
    assert body["source"]["text_hash"].startswith("sha256:")
    assert body["meta"]["provider"] == "none"
    assert provider.prompts == []
    assert "x-llm-provider" not in response.headers


def test_text_extraction_uses_model_and_marks_needs_review(client, sample_text):
    response = client.post(
        "/api/brief/extract", json={"source": {"kind": "text", "text": sample_text}}
    )

    assert response.status_code == 200
    body = response.json()
    facts = by_key(body)
    assert all(f["status"] in ("needs_review", "missing") for f in body["facts"])
    assert facts["registration_url"]["value"] == "https://example.org/riverside-hackday/register"
    assert facts["registration_url"]["source_ref"] == "paste"
    assert facts["mentors"]["value"][0] == {
        "name": "Asha Verma",
        "role": "Python",
        "url": None,
        "handle": None,
    }
    assert body["source"] == {
        "kind": "text",
        "url": None,
        "fetched_at": None,
        "text_hash": body["source"]["text_hash"],
    }
    assert body["meta"]["provider"] == "mock"
    assert body["meta"]["is_mock"] is True
    assert body["meta"]["prompt_version"] == "extract.v1"
    assert response.headers["x-llm-provider"] == "mock"


def test_missing_critical_keys_come_back_as_missing(client):
    text = "Pune Python Meetup. A friendly evening of talks for everyone who likes Python."

    body = client.post("/api/brief/extract", json={"source": {"kind": "text", "text": text}}).json()

    facts = by_key(body)
    for key in ("start_date", "timezone", "audience", "registration_url", "language"):
        assert facts[key]["status"] == "missing"
        assert facts[key]["value"] == ""
        assert facts[key]["critical"] is True


def test_text_too_short_is_rejected(client):
    response = client.post(
        "/api/brief/extract", json={"source": {"kind": "text", "text": " short "}}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "text_too_short"


def test_long_text_is_truncated_with_warning(client, app, sample_text):
    provider = CapturingProvider()
    app.state.gate.provider = provider
    text = sample_text + "\n" + ("filler words " * 3000)

    response = client.post("/api/brief/extract", json={"source": {"kind": "text", "text": text}})

    assert response.status_code == 200
    assert any("20,000" in w for w in response.json()["warnings"])
    assert len(provider.prompts[0]) < 22_000


class InventingProvider(MockProvider):
    """Returns one real fact, one invented snippet, an unknown key and a messy date."""

    async def complete(self, **kwargs):
        text = (
            '```json\n{"facts": ['
            '{"key": "event_name", "value": "Riverside Open Source Hack Day 2026",'
            ' "source_snippet": "Riverside   Open Source Hack Day 2026"},'
            '{"key": "venue", "value": "Grand Palace", "source_snippet": "at the Grand Palace"},'
            '{"key": "mentor_asha_verma_specialty", "value": "Python", "source_snippet": "Python"},'
            '{"key": "start_date", "value": "24 October 2026",'
            ' "source_snippet": "24 October 2026"},'
            '{"key": "start_time", "value": "10:00 AM", "source_snippet": "10:00 AM"},'
            '{"key": "capacity", "value": 80, "source_snippet": "80 participants"},'
            '{"key": "judges", "value": ["Meera Iyer"], "source_snippet": "Meera Iyer"}'
            "]}\n```"
        )
        return Completion(text, "euri", "gemma", 10, 5, 5)


def test_snippet_not_in_source_is_downgraded_and_values_normalised(client, app, sample_text):
    app.state.gate.provider = InventingProvider()

    response = client.post(
        "/api/brief/extract", json={"source": {"kind": "text", "text": sample_text}}
    )

    body = response.json()
    facts = by_key(body)
    assert facts["event_name"]["status"] == "needs_review"
    assert facts["venue"]["status"] == "missing"
    assert facts["venue"]["value"] == ""
    assert "Grand Palace" not in response.text
    assert any("venue" in w for w in body["warnings"])
    assert "mentor_asha_verma_specialty" not in facts
    assert facts["start_date"]["value"] == "2026-10-24"
    assert facts["start_time"]["value"] == "10:00"
    assert facts["capacity"]["value"] == "80"
    assert facts["judges"]["value"][0]["name"] == "Meera Iyer"
    assert body["meta"]["provider"] == "euri"
    assert body["meta"]["is_mock"] is False


@respx.mock
def test_url_extraction_fetches_page(client, app):
    async def resolve(host):
        return [PUBLIC_IP]

    app.state.fetch_page = functools.partial(safe_fetch, resolver=resolve)
    html = (
        "<html><head><title>Riverside Open Source Hack Day 2026</title></head><body>"
        "<p>Saturday, 24 October 2026, 10:00 AM to 5:30 PM IST</p>"
        "<p>Who should come: students and early-career developers.</p>"
        "<p>Registration: https://example.org/riverside-hackday/register</p></body></html>"
    )
    respx.get(f"https://{PUBLIC_IP}/hackday").mock(
        return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"})
    )

    response = client.post(
        "/api/brief/extract",
        json={"source": {"kind": "url", "url": "https://events.example.com/hackday"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"]["kind"] == "url"
    assert body["source"]["url"] == "https://events.example.com/hackday"
    assert body["source"]["fetched_at"] is not None
    facts = by_key(body)
    assert facts["event_name"]["source_ref"] == "https://events.example.com/hackday"
    assert facts["start_date"]["value"] == "2026-10-24"


@respx.mock
def test_javascript_page_gets_a_warning(client, app):
    async def resolve(host):
        return [PUBLIC_IP]

    app.state.fetch_page = functools.partial(safe_fetch, resolver=resolve)
    html = (
        "<html><head><title>Hack Day</title><script src='/a.js'></script></head>"
        "<body><div id='root'>Riverside Open Source Hack Day 2026 is loading, please wait.</div>"
        "</body></html>"
    )
    respx.get(f"https://{PUBLIC_IP}/").mock(
        return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"})
    )

    response = client.post(
        "/api/brief/extract", json={"source": {"kind": "url", "url": "https://events.example.com/"}}
    )

    assert response.status_code == 200
    assert any("JavaScript" in w for w in response.json()["warnings"])


def test_blocked_url_returns_fetch_failed(client):
    response = client.post(
        "/api/brief/extract", json={"source": {"kind": "url", "url": "http://127.0.0.1/admin"}}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "fetch_failed"


@pytest.mark.parametrize(
    "body",
    [
        {"source": {"kind": "url"}},
        {"source": {"kind": "text"}},
        {"source": {"kind": "pdf"}},
        {"source": {"kind": "sample"}, "extra": 1},
        {},
    ],
)
def test_bad_requests_are_validation_errors(client, body):
    response = client.post("/api/brief/extract", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_extract_counts_against_guest_limit(client, app, sample_text):
    limit = app.state.settings.rate_guest_per_hour
    payload = {"source": {"kind": "text", "text": sample_text}}
    client.get("/api/config")  # receive the cid cookie first

    for _ in range(limit):
        assert client.post("/api/brief/extract", json=payload).status_code == 200
    response = client.post("/api/brief/extract", json=payload)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response.headers["retry-after"]) > 0
