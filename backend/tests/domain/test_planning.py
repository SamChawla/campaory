from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domain.facts import is_critical
from app.domain.planning import event_timing, propose_plan
from app.domain.schemas import Fact, Person

IST = ZoneInfo("Asia/Kolkata")
PLATFORMS = ["linkedin", "instagram", "whatsapp", "x"]


def fact(key, value) -> Fact:
    return Fact(id=uuid4(), key=key, value=value, status="confirmed", critical=is_critical(key))


def facts_for(
    start: str,
    *,
    end=None,
    time="10:00",
    registration=True,
    deadline=None,
    people=True,
    partners=True,
):
    out = [
        fact("event_name", "Riverside Hack Day"),
        fact("start_date", start),
        fact("start_time", time),
        fact("timezone", "Asia/Kolkata"),
        fact("audience", "Students"),
    ]
    if end:
        out.append(fact("end_date", end))
    if registration:
        out.append(fact("registration_url", "https://example.org/r"))
    else:
        out.append(
            Fact(
                id=uuid4(),
                key="registration_url",
                value="",
                status="confirmed",
                critical=True,
                not_applicable=True,
            )
        )
    if deadline:
        out.append(fact("registration_deadline", deadline))
    if people:
        out.append(fact("mentors", [Person(name="Asha Verma")]))
    if partners:
        out.append(fact("partners", [Person(name="Lakeview")]))
    return out


TODAY = date(2026, 10, 1)


def plan(start, today=TODAY, **kw):
    return propose_plan(facts_for(start, **kw), PLATFORMS, today=today, timezone="Asia/Kolkata")


def titles(items):
    return [i.title for i in items]


def assert_invariants(items, start: datetime, end_day: date, today: date):
    assert items, "plan should not be empty"
    times = [i.scheduled_for for i in items]
    assert times == sorted(times)
    assert all(t.tzinfo is not None for t in times)
    assert all(t.date() >= today for t in times)
    for item in items:
        if item.stage in ("pre", "event"):
            assert item.scheduled_for < start or item.stage == "event", item.title
            assert item.scheduled_for.date() <= start.date(), item.title
        if item.stage == "pre":
            assert item.scheduled_for < start, item.title
        if item.stage == "post":
            assert item.scheduled_for.date() > end_day, item.title
    events = [i for i in items if i.stage == "event"]
    assert len(events) == 1 and events[0].scheduled_for <= start


def test_thirty_days_out_has_full_campaign():
    items = plan("2026-10-31")

    assert titles(items) == [
        "Event announcement",
        "Why attend",
        "Meet the mentors",
        "Partner announcement",
        "Registration update",
        "Participant preparation",
        "Final registration reminder",
        "Event-day live update",
        "Post-event thank-you",
        "Highlights and resources",
    ]
    by_title = {i.title: i.scheduled_for for i in items}
    assert by_title["Event announcement"] == datetime(2026, 10, 1, 9, 0, tzinfo=IST)
    assert by_title["Why attend"] == datetime(2026, 10, 17, 10, 0, tzinfo=IST)
    assert by_title["Final registration reminder"] == datetime(2026, 10, 30, 10, 0, tzinfo=IST)
    assert by_title["Event-day live update"] == datetime(2026, 10, 31, 8, 30, tzinfo=IST)
    assert by_title["Post-event thank-you"] == datetime(2026, 11, 1, 10, 0, tzinfo=IST)
    assert by_title["Highlights and resources"] == datetime(2026, 11, 3, 10, 0, tzinfo=IST)
    assert_invariants(items, datetime(2026, 10, 31, 10, tzinfo=IST), date(2026, 10, 31), TODAY)


def test_nine_days_out_drops_why_attend_and_compresses():
    items = plan("2026-10-10")

    assert "Why attend" not in titles(items)
    assert "Participant preparation" in titles(items)
    assert_invariants(items, datetime(2026, 10, 10, 10, tzinfo=IST), date(2026, 10, 10), TODAY)
    pre = [i.scheduled_for for i in items if i.stage == "pre"]
    assert all(b - a >= timedelta(days=1) for a, b in zip(pre, pre[1:], strict=False))


def test_three_days_out_drops_optional_items():
    items = plan("2026-10-04")

    assert "Why attend" not in titles(items)
    assert "Participant preparation" not in titles(items)
    assert titles(items)[0] == "Event announcement"
    assert "Final registration reminder" in titles(items)
    assert_invariants(items, datetime(2026, 10, 4, 10, tzinfo=IST), date(2026, 10, 4), TODAY)


def test_event_tomorrow_keeps_announcement_and_final_reminder():
    items = plan("2026-10-02")

    pre = [i.title for i in items if i.stage == "pre"]
    assert pre[0] == "Event announcement"
    assert pre[-1] == "Final registration reminder"
    assert_invariants(items, datetime(2026, 10, 2, 10, tzinfo=IST), date(2026, 10, 2), TODAY)


def test_event_today_has_only_event_day_and_post_items():
    items = plan("2026-10-01")

    assert [i.stage for i in items] == ["event", "post", "post"]
    assert_invariants(items, datetime(2026, 10, 1, 10, tzinfo=IST), date(2026, 10, 1), TODAY)


def test_multi_day_event_post_items_after_end():
    items = plan("2026-10-20", end="2026-10-22")

    by_title = {i.title: i.scheduled_for for i in items}
    assert by_title["Post-event thank-you"] == datetime(2026, 10, 23, 10, 0, tzinfo=IST)
    assert_invariants(items, datetime(2026, 10, 20, 10, tzinfo=IST), date(2026, 10, 22), TODAY)


def test_no_registration_drops_registration_items():
    items = plan("2026-10-31", registration=False)

    assert "Registration update" not in titles(items)
    assert "Final registration reminder" not in titles(items)


def test_registration_deadline_earlier_than_start():
    items = plan("2026-10-31", deadline="2026-10-25")

    by_title = {i.title: i.scheduled_for for i in items}
    assert by_title["Final registration reminder"] == datetime(2026, 10, 24, 10, 0, tzinfo=IST)


def test_no_people_no_intro_item():
    items = plan("2026-10-31", people=False, partners=False)

    assert "Meet the mentors" not in titles(items)
    assert "Partner announcement" not in titles(items)


def test_intro_title_follows_people_present():
    facts = facts_for("2026-10-31", people=False) + [
        fact("speakers", [Person(name="Ravi")]),
        fact("judges", [Person(name="Meera")]),
    ]
    items = propose_plan(facts, PLATFORMS, today=TODAY, timezone="Asia/Kolkata")

    assert "Meet the speakers and judges" in titles(items)


def test_early_start_moves_event_day_update_before_start():
    items = plan("2026-10-31", time="08:00")

    (event,) = [i for i in items if i.stage == "event"]
    assert event.scheduled_for == datetime(2026, 10, 31, 7, 0, tzinfo=IST)


def test_fact_keys_only_name_confirmed_facts():
    items = plan("2026-10-31", registration=False)

    for item in items:
        assert "registration_url" not in item.fact_keys
    assert "event_name" in items[0].fact_keys


def test_item_platforms_follow_selection():
    items = propose_plan(
        facts_for("2026-10-31"), ["x", "linkedin"], today=TODAY, timezone="Asia/Kolkata"
    )

    assert all(i.platforms == ["linkedin", "x"] for i in items)


def test_other_timezone():
    facts = [f for f in facts_for("2026-10-31") if f.key != "timezone"]
    facts.append(fact("timezone", "Europe/London"))
    items = propose_plan(facts, PLATFORMS, today=TODAY, timezone="Europe/London")

    assert items[0].scheduled_for.tzinfo == ZoneInfo("Europe/London")


def test_blocked_facts_raise():
    with pytest.raises(ValueError, match="audience"):
        propose_plan(
            [f for f in facts_for("2026-10-31") if f.key != "audience"],
            PLATFORMS,
            today=TODAY,
            timezone="Asia/Kolkata",
        )


def test_event_timing_classifies_past_ongoing_and_upcoming():
    assert event_timing(date(2026, 9, 20), date(2026, 9, 20), TODAY) == "past"
    assert event_timing(date(2026, 9, 30), date(2026, 10, 2), TODAY) == "ongoing"
    assert event_timing(TODAY, TODAY, TODAY) == "ongoing"
    assert event_timing(date(2026, 10, 2), date(2026, 10, 2), TODAY) == "upcoming"


def test_past_event_gets_only_follow_up_posts_from_today():
    items = plan("2026-09-20")

    assert [i.stage for i in items] == ["post", "post"]
    times = [i.scheduled_for for i in items]
    assert times[0] == datetime(2026, 10, 1, 9, 0, tzinfo=IST)
    assert times[1] - times[0] >= timedelta(days=1)
    assert all(t.date() >= TODAY for t in times)


def test_event_that_ended_yesterday_keeps_normal_follow_up_dates():
    items = plan("2026-09-30")

    by_title = {i.title: i.scheduled_for for i in items}
    assert titles(items) == ["Post-event thank-you", "Highlights and resources"]
    assert by_title["Post-event thank-you"] == datetime(2026, 10, 1, 10, 0, tzinfo=IST)
    assert by_title["Highlights and resources"] == datetime(2026, 10, 3, 10, 0, tzinfo=IST)


def test_ongoing_multi_day_event_starts_with_todays_update():
    items = plan("2026-09-30", end="2026-10-02")

    assert [i.stage for i in items] == ["event", "post", "post"]
    assert items[0].scheduled_for == datetime(2026, 10, 1, 9, 0, tzinfo=IST)
    assert items[1].scheduled_for == datetime(2026, 10, 3, 10, 0, tzinfo=IST)
