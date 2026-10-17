from uuid import uuid4

import pytest
from helpers import CapturingProvider, facts_json
from support import make_fact

from app.llm.base import Completion
from app.llm.mock import MockProvider
from app.llm.prompts import json_block

ALL = ["linkedin", "instagram", "whatsapp", "x"]


def item(title="Event announcement", **kw) -> dict:
    return {
        "id": str(uuid4()),
        "title": title,
        "purpose": "Tell people",
        "stage": "pre",
        "fact_keys": ["event_name", "start_date", "start_time", "venue", "registration_url"],
        **kw,
    }


def generate(client, facts, items, platforms=ALL, **kw):
    body = {"facts": facts_json(facts), "language": "en", "tone": "friendly", "items": items}
    return client.post("/api/posts/generate", json={**body, "platforms": platforms, **kw})


def test_generate_returns_checked_posts(client, sample_facts):
    first = item()

    response = generate(client, sample_facts, [first])

    assert response.status_code == 200
    body = response.json()
    assert body["failed"] == []
    assert [p["platform"] for p in body["posts"]] == ALL
    for post in body["posts"]:
        assert post["plan_item_id"] == first["id"]
        assert post["status"] == "draft"
        assert post["guard_flags"] == []
        assert post["placeholders"] == []
        assert post["validation"]["ok"] is True
        assert post["validation"]["limit"] > 0
        assert "event_name" in post["facts_used"]
    assert body["meta"]["provider"] == "mock"
    assert body["meta"]["prompt_version"] == "generate.v2"
    assert response.headers["x-llm-provider"] == "mock"


def test_unconfirmed_facts_never_reach_the_prompt(client, app, sample_facts):
    provider = CapturingProvider()
    app.state.gate.provider = provider
    facts = sample_facts + [
        make_fact("short_description", "SECRET UNREVIEWED CLAIM", status="needs_review"),
        make_fact("speakers", "", status="missing"),
    ]
    facts = [
        f.model_copy(update={"status": "needs_review", "value": "Hidden Venue Hall"})
        if f.key == "venue"
        else f
        for f in facts
    ]

    response = generate(client, facts, [item()])

    assert response.status_code == 200
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert "SECRET UNREVIEWED CLAIM" not in prompt
    assert "Hidden Venue Hall" not in prompt
    sent = json_block(prompt, "facts")
    assert "venue" not in sent and "short_description" not in sent and "speakers" not in sent
    assert sent["event_name"] == "Riverside Open Source Hack Day 2026"
    assert all("Hidden Venue Hall" not in p["text"] for p in response.json()["posts"])


def test_gate_facts_missing_blocks_generation(client, sample_facts):
    facts = [f for f in sample_facts if f.key != "timezone"]

    response = generate(client, facts, [item()])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "blocked"
    assert response.json()["error"]["details"]["missing"] == ["timezone"]


def test_more_than_four_items_is_rejected(client, sample_facts):
    response = generate(client, sample_facts, [item() for _ in range(5)])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_partial_failure_lists_failed_items(client, app, sample_facts):
    app.state.gate.provider = CapturingProvider(garbage_when='"title": "Broken"')
    good, broken = item(), item("Broken")

    response = generate(client, sample_facts, [good, broken])

    assert response.status_code == 200
    body = response.json()
    assert {p["plan_item_id"] for p in body["posts"]} == {good["id"]}
    assert body["failed"] == [{"plan_item_id": broken["id"], "error": "llm_invalid_output"}]


def test_all_items_failing_returns_the_error(client, app, sample_facts):
    app.state.gate.provider = CapturingProvider(garbage_when="TASK:")

    response = generate(client, sample_facts, [item()])

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_invalid_output"


def test_limit_is_counted_once_per_request(client, app, sample_facts):
    limit = app.state.settings.rate_guest_per_hour
    four = [item() for _ in range(4)]
    client.get("/api/config")  # receive the cid cookie first

    for _ in range(limit):
        assert generate(client, sample_facts, four).status_code == 200
    assert generate(client, sample_facts, four).status_code == 429


class InventingWriter(MockProvider):
    async def complete(self, **kwargs):
        text = (
            '{"posts": [{"platform": "x", "text": "Riverside Open Source Hack Day 2026 on 25 Oct '
            'at 11:00 AM! 500 seats. [ADD: venue] https://evil.example.com", '
            '"facts_used": ["event_name", "venue", "made_up"]}]}'
        )
        return Completion(text, "euri", "gemma", 1, 1, 1)


def test_guard_and_validators_run_on_model_output(client, app, sample_facts):
    app.state.gate.provider = InventingWriter()

    response = generate(client, sample_facts, [item()], platforms=["x"])

    post = response.json()["posts"][0]
    assert post["status"] == "needs_review"
    codes = {f["code"] for f in post["guard_flags"]}
    assert {"UNKNOWN_DATE", "UNKNOWN_TIME", "UNKNOWN_URL", "UNKNOWN_COUNT"} <= codes
    assert post["placeholders"] == ["venue"]
    assert post["facts_used"] == ["event_name", "venue"]


def test_missing_platform_in_output_is_repaired_or_failed(client, app, sample_facts):
    app.state.gate.provider = InventingWriter()

    response = generate(client, sample_facts, [item()], platforms=["x", "linkedin"])

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_invalid_output"


def test_plan_item_date_is_allowed_in_posts(client, app, sample_facts):
    class DateWriter(MockProvider):
        async def complete(self, **kwargs):
            text = '{"posts": [{"platform": "x", "text": "See you on 20 Oct!", "facts_used": []}]}'
            return Completion(text, "mock", "m", 1, 1, 1)

    app.state.gate.provider = DateWriter()
    dated = item(scheduled_for="2026-10-20T10:00:00+05:30")

    post = generate(client, sample_facts, [dated], platforms=["x"]).json()["posts"][0]

    assert post["guard_flags"] == []


def revise(client, facts, text, instruction="make_shorter", **post):
    return client.post(
        "/api/posts/revise",
        json={
            "facts": facts_json(facts),
            "post": {"platform": "linkedin", "text": text, "facts_used": ["event_name"], **post},
            "instruction": instruction,
            "custom_instruction": "",
        },
    )


def _first_text(client, sample_facts):
    return generate(client, sample_facts, [item()], platforms=["linkedin"]).json()["posts"][0][
        "text"
    ]


def test_revise_returns_checked_text(client, sample_facts):
    text = _first_text(client, sample_facts)

    response = revise(client, sample_facts, text, "make_longer")

    assert response.status_code == 200
    body = response.json()
    assert body["text"] != text
    assert body["status"] == "draft"
    assert body["guard_flags"] == []
    assert body["validation"]["ok"] is True
    assert body["meta"]["prompt_version"] == "revise.v2"


def test_custom_instruction_requires_text(client, sample_facts):
    response = revise(client, sample_facts, "Some post text here", "custom")

    assert response.status_code == 422


def test_custom_instruction_is_capped(client, sample_facts):
    response = client.post(
        "/api/posts/revise",
        json={
            "facts": facts_json(sample_facts),
            "post": {"platform": "x", "text": "Hello", "facts_used": []},
            "instruction": "custom",
            "custom_instruction": "x" * 201,
        },
    )

    assert response.status_code == 422


def test_revise_refuses_published_post(client, sample_facts):
    response = revise(client, sample_facts, "Live now", status="published")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "published_post"


def test_revise_prompt_has_only_confirmed_facts(client, app, sample_facts):
    provider = CapturingProvider()
    app.state.gate.provider = provider
    facts = sample_facts + [make_fact("short_description", "UNREVIEWED", status="needs_review")]

    revise(client, facts, "Riverside Open Source Hack Day 2026 is coming.")

    assert "UNREVIEWED" not in provider.prompts[0]


def test_validate_runs_rules_without_model(client, app, sample_facts):
    provider = CapturingProvider()
    app.state.gate.provider = provider

    response = client.post(
        "/api/posts/validate",
        json={
            "platform": "x",
            "text": "Join us on 30 Oct at https://evil.example.com [ADD: venue] " + "x" * 280,
            "facts": facts_json(sample_facts),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["ok"] is False
    assert body["validation"]["issues"][0]["code"] == "too_long"
    assert {f["code"] for f in body["guard_flags"]} == {"UNKNOWN_DATE", "UNKNOWN_URL"}
    assert body["placeholders"] == ["venue"]
    assert provider.prompts == []


@pytest.mark.parametrize("path", ["/api/posts/validate", "/api/plan/propose"])
def test_rule_endpoints_reject_bad_platform(client, path):
    response = client.post(path, json={"platform": "myspace", "text": "x", "facts": []})

    assert response.status_code == 422
