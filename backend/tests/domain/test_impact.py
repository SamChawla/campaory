from datetime import date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.domain.facts import is_critical
from app.domain.impact import Change, analyze
from app.domain.schemas import Fact, PlanItem, Post
from app.domain.textdiff import changed_spans, word_diff

IST = ZoneInfo("Asia/Kolkata")


def fact(key, value) -> Fact:
    return Fact(id=uuid4(), key=key, value=value, status="confirmed", critical=is_critical(key))


def facts(**overrides):
    values = {
        "event_name": "Riverside Hack Day",
        "start_date": "2026-10-31",
        "start_time": "09:30",
        "timezone": "Asia/Kolkata",
        "audience": "Students",
        "venue": "Lakeview Hall",
        "registration_url": "https://example.org/r",
    }
    values.update(overrides)
    return [fact(k, v) for k, v in values.items()]


ANNOUNCE = PlanItem(
    id=uuid4(),
    title="Event announcement",
    stage="pre",
    position=0,
    scheduled_for=datetime(2026, 10, 1, 9, tzinfo=IST),
    fact_keys=["event_name", "start_date", "start_time"],
)
PARTNER = PlanItem(
    id=uuid4(),
    title="Partner announcement",
    stage="pre",
    position=1,
    scheduled_for=datetime(2026, 10, 23, 10, tzinfo=IST),
    fact_keys=["event_name", "partners"],
)
EVENT_DAY = PlanItem(
    id=uuid4(),
    title="Event-day live update",
    stage="event",
    position=2,
    scheduled_for=datetime(2026, 10, 31, 8, 30, tzinfo=IST),
    fact_keys=["event_name", "venue"],
)
PLAN = [ANNOUNCE, PARTNER, EVENT_DAY]


def post(item, platform, text, status="draft", facts_used=()) -> Post:
    return Post(
        id=uuid4(),
        plan_item_id=item.id,
        platform=platform,
        text=text,
        status=status,
        facts_used=list(facts_used),
    )


def ids(entries) -> list[UUID]:
    return [e.post_id for e in entries]


CHANGE = Change(key="start_time", old="10:00", new="09:30")


def test_facts_used_marks_post_affected():
    p = post(PARTNER, "x", "Thanks partners", facts_used=["start_time"])

    result = analyze(CHANGE, facts(), [p], PLAN, today=date(2026, 10, 1))

    assert [(a.post_id, a.reason) for a in result.affected] == [(p.id, "facts_used")]
    assert result.affected[0].detail == "start_time changed from 10:00 to 09:30"


def test_text_match_finds_unlisted_fact():
    p = post(PARTNER, "x", "Doors open at 10 AM sharp")

    result = analyze(CHANGE, facts(), [p], PLAN, today=date(2026, 10, 1))

    assert [(a.post_id, a.reason) for a in result.affected] == [(p.id, "text_match")]


def test_text_match_on_plain_value():
    change = Change(key="venue", old="Lakeview Hall", new="Station Hub")
    p = post(PARTNER, "linkedin", "See you at LAKEVIEW  hall!")

    result = analyze(change, facts(venue="Station Hub"), [p], PLAN, today=date(2026, 10, 1))

    assert ids(result.affected) == [p.id]


def test_short_plain_value_not_text_matched():
    change = Change(key="city", old="Ab", new="Cd")
    p = post(PARTNER, "x", "Ab and more")

    assert analyze(change, facts(), [p], PLAN, today=date(2026, 10, 1)).affected == []


def test_plan_item_keys_mark_posts():
    p = post(ANNOUNCE, "whatsapp", "Hi all")

    result = analyze(CHANGE, facts(), [p], PLAN, today=date(2026, 10, 1))

    assert [(a.post_id, a.reason) for a in result.affected] == [(p.id, "plan_item")]


def test_unrelated_post_untouched():
    p = post(PARTNER, "x", "Thanks partners", facts_used=["partners"])

    assert analyze(CHANGE, facts(), [p], PLAN, today=date(2026, 10, 1)).affected == []


def test_published_never_modified():
    published = post(
        ANNOUNCE, "linkedin", "Starts 10:00", status="published", facts_used=["start_time"]
    )
    draft = post(ANNOUNCE, "x", "Starts 10:00", facts_used=["start_time"])

    result = analyze(CHANGE, facts(), [published, draft], PLAN, today=date(2026, 10, 1))

    assert ids(result.affected) == [draft.id]
    assert [(p.post_id, p.status) for p in result.protected] == [(published.id, "published")]
    assert "correction" in result.protected[0].note.lower()


def test_ordering_by_plan_position_then_platform():
    a = post(EVENT_DAY, "linkedin", "x", facts_used=["start_time"])
    b = post(ANNOUNCE, "x", "x", facts_used=["start_time"])
    c = post(ANNOUNCE, "linkedin", "x", facts_used=["start_time"])

    result = analyze(CHANGE, facts(), [a, b, c], PLAN, today=date(2026, 10, 1))

    assert ids(result.affected) == [c.id, b.id, a.id]


def test_each_post_listed_once_with_strongest_reason():
    p = post(ANNOUNCE, "x", "Starts 10:00", facts_used=["start_time"])

    result = analyze(CHANGE, facts(), [p], PLAN, today=date(2026, 10, 1))

    assert [(a.post_id, a.reason) for a in result.affected] == [(p.id, "facts_used")]


def test_date_change_recomputes_plan_dates():
    change = Change(key="start_date", old="2026-10-31", new="2026-11-07")

    result = analyze(change, facts(start_date="2026-11-07"), [], PLAN, today=date(2026, 10, 1))

    changes = {(c.plan_item_id, c.field) for c in result.plan_changes}
    assert (EVENT_DAY.id, "scheduled_for") in changes
    event_change = next(c for c in result.plan_changes if c.plan_item_id == EVENT_DAY.id)
    assert event_change.new == datetime(2026, 11, 7, 8, 30, tzinfo=IST)
    assert ANNOUNCE.id not in {c.plan_item_id for c in result.plan_changes}


def test_non_date_change_has_no_plan_changes():
    change = Change(key="venue", old="Lakeview Hall", new="Station Hub")

    result = analyze(change, facts(venue="Station Hub"), [], PLAN, today=date(2026, 10, 1))

    assert result.plan_changes == []


def test_old_date_text_match():
    change = Change(key="start_date", old="2026-10-31", new="2026-11-07")
    p = post(PARTNER, "x", "See you on Oct 31!")

    result = analyze(change, facts(start_date="2026-11-07"), [p], PLAN, today=date(2026, 10, 1))

    assert ids(result.affected) == [p.id]


# ---- word diff ---------------------------------------------------------------------------


def test_word_diff_marks_changes():
    ops = word_diff("Doors open at 10:00 sharp", "Doors open at 09:30 sharp")

    assert [(o.op, o.text) for o in ops] == [
        ("equal", "Doors open at "),
        ("delete", "10:00"),
        ("insert", "09:30"),
        ("equal", " sharp"),
    ]


def test_word_diff_identical():
    assert [(o.op, o.text) for o in word_diff("same text", "same text")] == [("equal", "same text")]


def test_changed_spans():
    assert changed_spans("at 10:00 in Hall A", "at 09:30 in Hall B") == [
        ("10:00", "09:30"),
        ("A", "B"),
    ]
