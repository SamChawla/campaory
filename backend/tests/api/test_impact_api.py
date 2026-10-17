from datetime import UTC, datetime
from uuid import uuid4

from helpers import CapturingProvider, facts_json
from support import make_fact

from app.domain.schemas import PlanItem, Post

NOW = datetime(2026, 10, 1, 4, 0, tzinfo=UTC)


def plan_item(title="Event announcement", keys=("event_name", "start_time"), position=0):
    return PlanItem(
        id=uuid4(),
        title=title,
        stage="pre",
        position=position,
        scheduled_for=datetime(2026, 10, 1, 3, 30, tzinfo=UTC),
        fact_keys=list(keys),
    )


def post(item, text, status="draft", platform="linkedin", facts_used=("event_name", "start_time")):
    return Post(
        id=uuid4(),
        plan_item_id=item.id,
        platform=platform,
        text=text,
        status=status,
        facts_used=list(facts_used),
    )


def changed_facts(sample_facts, key, value):
    return [f.model_copy(update={"value": value}) if f.key == key else f for f in sample_facts]


def dump(models):
    return [m.model_dump(mode="json") for m in models]


def test_analyze_splits_affected_and_protected(client, sample_facts):
    item = plan_item()
    draft = post(item, "Riverside Open Source Hack Day 2026 starts at 10:00 AM.")
    published = post(item, "Starts at 10:00 AM.", status="published", platform="x")
    other = post(plan_item(keys=("event_name",)), "Hello", facts_used=("event_name",))

    response = client.post(
        "/api/impact/analyze",
        json={
            "changed": {"key": "start_time", "old": "10:00", "new": "09:30"},
            "facts": facts_json(changed_facts(sample_facts, "start_time", "09:30")),
            "posts": dump([draft, published, other]),
            "plan": dump([item]),
            "today": "2026-10-01",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["affected"] == [
        {
            "post_id": str(draft.id),
            "reason": "facts_used",
            "detail": "start_time changed from 10:00 to 09:30",
        }
    ]
    assert body["protected"] == [
        {
            "post_id": str(published.id),
            "status": "published",
            "note": "Already public. Consider a correction post.",
        }
    ]
    assert isinstance(body["plan_changes"], list)


def test_analyze_reports_plan_date_changes(client, sample_facts):
    item = plan_item(title="Event-day live update", keys=("event_name", "start_time"))
    new_facts = changed_facts(sample_facts, "start_date", "2026-10-25")

    body = client.post(
        "/api/impact/analyze",
        json={
            "changed": {"key": "start_date", "old": "2026-10-24", "new": "2026-10-25"},
            "facts": facts_json(new_facts),
            "posts": [],
            "plan": dump([item]),
            "today": "2026-10-01",
        },
    ).json()

    assert body["plan_changes"] == [
        {
            "plan_item_id": str(item.id),
            "field": "scheduled_for",
            "old": "2026-10-01T03:30:00Z",
            "new": "2026-10-25T08:30:00+05:30",
        }
    ]


def test_analyze_accepts_people_lists(client, sample_facts):
    response = client.post(
        "/api/impact/analyze",
        json={
            "changed": {
                "key": "judges",
                "old": [{"name": "Meera Iyer", "role": ""}],
                "new": [{"name": "Ravi Rao", "role": ""}],
            },
            "facts": facts_json(sample_facts),
            "posts": [],
            "plan": [],
        },
    )

    assert response.status_code == 200


def redraft(client, facts, the_post, change):
    return client.post(
        "/api/impact/redraft",
        json={
            "changed": change,
            "facts": facts_json(facts),
            "post": the_post.model_dump(mode="json"),
        },
    )


def test_redraft_proposes_minimal_change_that_passes_guard(client, sample_facts):
    item = plan_item()
    old = post(item, "Riverside Open Source Hack Day 2026 starts at 10:00 AM sharp.")
    new_facts = changed_facts(sample_facts, "start_time", "09:30")

    response = redraft(
        client, new_facts, old, {"key": "start_time", "old": "10:00", "new": "09:30"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["proposed_text"] == "Riverside Open Source Hack Day 2026 starts at 9:30 AM sharp."
    assert body["changed_spans"] == [{"from": "10:00", "to": "9:30"}]
    assert body["reason"] == "start_time changed from 10:00 to 09:30"
    assert body["guard_flags"] == []
    assert body["validation"]["ok"] is True
    assert body["status"] == "draft"
    assert "start_time" in body["facts_used"]
    assert body["meta"]["prompt_version"] == "redraft.v2"


def test_redraft_refuses_published_post(client, app, sample_facts):
    provider = CapturingProvider()
    app.state.gate.provider = provider
    published = post(plan_item(), "Starts at 10:00 AM.", status="published")

    response = redraft(
        client, sample_facts, published, {"key": "start_time", "old": "10:00", "new": "09:30"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "published_post"
    assert provider.prompts == []


def test_redraft_prompt_has_only_confirmed_facts(client, app, sample_facts):
    provider = CapturingProvider()
    app.state.gate.provider = provider
    facts = sample_facts + [make_fact("short_description", "UNREVIEWED", status="needs_review")]

    redraft(
        client,
        facts,
        post(plan_item(), "At 10:00 AM."),
        {"key": "start_time", "old": "10:00", "new": "09:30"},
    )

    assert "UNREVIEWED" not in provider.prompts[0]
