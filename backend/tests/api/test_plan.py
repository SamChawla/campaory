from helpers import facts_json

ALL = ["linkedin", "instagram", "whatsapp", "x"]


def test_plan_proposes_dated_items(client, sample_facts):
    response = client.post(
        "/api/plan/propose",
        json={
            "facts": facts_json(sample_facts),
            "platforms": ALL,
            "today": "2026-10-01",
            "timezone": "Asia/Kolkata",
        },
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["title"] == "Event announcement"
    assert items[0]["scheduled_for"] == "2026-10-01T09:00:00+05:30"
    assert items[0]["stage"] == "pre"
    assert items[0]["platforms"] == ALL
    assert "event_name" in items[0]["fact_keys"]
    titles = [i["title"] for i in items]
    assert "Event-day live update" in titles
    assert titles[-1] == "Highlights and resources"
    assert [i["scheduled_for"] for i in items] == sorted(i["scheduled_for"] for i in items)


def test_timezone_defaults_to_confirmed_fact(client, sample_facts):
    response = client.post(
        "/api/plan/propose",
        json={"facts": facts_json(sample_facts), "platforms": ["x"], "today": "2026-10-01"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["scheduled_for"].endswith("+05:30")


def test_today_defaults_to_server_clock(client, sample_facts):
    response = client.post(
        "/api/plan/propose", json={"facts": facts_json(sample_facts), "platforms": ["x"]}
    )

    assert response.status_code == 200


def test_unconfirmed_gate_facts_block(client, sample_facts):
    facts = [
        f.model_copy(update={"status": "needs_review"}) if f.key == "audience" else f
        for f in sample_facts
    ]

    response = client.post(
        "/api/plan/propose",
        json={"facts": facts_json(facts), "platforms": ALL, "today": "2026-10-01"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "blocked"
    assert error["details"]["missing"] == ["audience"]


def test_invalid_timezone_is_validation_error(client, sample_facts):
    response = client.post(
        "/api/plan/propose",
        json={
            "facts": facts_json(sample_facts),
            "platforms": ALL,
            "today": "2026-10-01",
            "timezone": "Mars/Olympus",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_plan_is_not_model_limited(client, app, sample_facts):
    body = {"facts": facts_json(sample_facts), "platforms": ALL, "today": "2026-10-01"}

    for _ in range(app.state.settings.rate_guest_per_hour + 3):
        assert client.post("/api/plan/propose", json=body).status_code == 200


def test_past_event_gets_follow_ups_and_a_notice(client, sample_facts):
    response = client.post(
        "/api/plan/propose",
        json={"facts": facts_json(sample_facts), "platforms": ALL, "today": "2026-11-30"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_status"] == "past"
    assert "ended on Saturday, 24 October 2026" in body["notice"]
    assert [i["stage"] for i in body["items"]] == ["post", "post"]
    assert all(i["scheduled_for"] >= "2026-11-30" for i in body["items"])


def test_upcoming_event_has_no_notice(client, sample_facts):
    response = client.post(
        "/api/plan/propose",
        json={"facts": facts_json(sample_facts), "platforms": ALL, "today": "2026-10-01"},
    )

    assert response.json()["event_status"] == "upcoming"
    assert response.json()["notice"] is None
