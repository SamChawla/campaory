"""Plan proposal (LLD 6.1). Dates are computed here, never by the model."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.domain.facts import confirmed_map, generation_blockers, is_filled, parse_time
from app.domain.schemas import PLATFORM_ORDER, Fact, Platform, Stage

DEFAULT_START = time(9, 0)
POST_TIME = time(10, 0)
EVENT_DAY_UPDATE = time(8, 30)
DAY = timedelta(days=1)
TIGHT_GAP = timedelta(hours=2)

# Dropped first, in this order, when the pre-event window is too short.
DROP_ORDER = (
    "Why attend",
    "Participant preparation",
    "Partner announcement",
    "intro",
    "Registration update",
)
ESSENTIAL = ("Event announcement", "Final registration reminder")
PEOPLE_KEYS = ("speakers", "mentors", "judges")


type EventTiming = Literal["upcoming", "ongoing", "past"]


def event_timing(start_day: date, end_day: date, today: date) -> EventTiming:
    """Where today falls against the event days. A past event gets follow-up posts only."""
    if end_day < today:
        return "past"
    if start_day <= today:
        return "ongoing"
    return "upcoming"


def event_days(facts: list[Fact]) -> tuple[date, date]:
    """Confirmed start and end day; end falls back to start when missing or earlier."""
    by_key = confirmed_map(facts)
    start_day = date.fromisoformat(str(by_key["start_date"].value))
    end_day = start_day
    if "end_date" in by_key:
        try:
            end_day = max(start_day, date.fromisoformat(str(by_key["end_date"].value)))
        except ValueError:
            end_day = start_day
    return start_day, end_day


class PlanBlocked(ValueError):
    def __init__(self, missing: list[str]) -> None:
        super().__init__("confirm these facts first: " + ", ".join(missing))
        self.missing = missing


@dataclass
class ProposedItem:
    title: str
    purpose: str
    stage: Stage
    scheduled_for: datetime
    fact_keys: list[str]
    platforms: list[Platform] = field(default_factory=list)


@dataclass
class _Candidate:
    title: str
    purpose: str
    keys: tuple[str, ...]
    target: datetime
    drop_key: str = ""


def propose_plan(
    facts: list[Fact],
    platforms: list[Platform],
    *,
    today: date,
    timezone: str,
    language: str | None = "en",
) -> list[ProposedItem]:
    missing = generation_blockers(facts, language)
    if missing:
        raise PlanBlocked(missing)

    by_key = confirmed_map(facts)
    tz = ZoneInfo(timezone)
    start_day, end_day = event_days(facts)
    start_time = _fact_time(by_key, "start_time") or DEFAULT_START
    start = datetime.combine(start_day, start_time, tz)
    now = datetime.combine(today, time(0, 0), tz)
    earliest = _next_at(now, DEFAULT_START)
    days_out = (start_day - today).days
    timing = event_timing(start_day, end_day, today)

    if start_day < today:
        # Already under way (or over): the live update goes out at the first slot today.
        event_at = earliest
    else:
        event_at = max(
            min(datetime.combine(start_day, EVENT_DAY_UPDATE, tz), start - timedelta(hours=1)),
            now,
        )

    available = {k for k, f in by_key.items() if is_filled(f.value) and not f.not_applicable}
    has_registration = "registration_url" in available

    def at(day: date, t: time = POST_TIME) -> datetime:
        return datetime.combine(day, t, tz)

    candidates = [
        _Candidate(
            "Event announcement",
            "Tell people the event exists, when and where it is, and how to join.",
            (
                "event_name",
                "start_date",
                "start_time",
                "venue",
                "city",
                "event_mode",
                "registration_url",
                "audience",
            ),
            earliest,
        )
    ]
    if days_out >= 10:
        candidates.append(
            _Candidate(
                "Why attend",
                "Explain what attendees will gain and who it is for.",
                ("event_name", "audience", "short_description", "start_date"),
                at(start_day - 14 * DAY),
                "Why attend",
            )
        )
    people = [k for k in PEOPLE_KEYS if k in available]
    if people:
        candidates.append(
            _Candidate(
                "Meet the " + " and ".join(people),
                "Introduce the people attendees will learn from.",
                ("event_name", "start_date", *people),
                at(start_day - 10 * DAY),
                "intro",
            )
        )
    if "partners" in available:
        candidates.append(
            _Candidate(
                "Partner announcement",
                "Thank and introduce the partners supporting the event.",
                ("event_name", "partners", "handles"),
                at(start_day - 8 * DAY),
                "Partner announcement",
            )
        )
    final_target = None
    if has_registration:
        final_day = start_day - DAY
        if "registration_deadline" in available:
            try:
                deadline = date.fromisoformat(str(by_key["registration_deadline"].value))
                final_day = min(final_day, deadline - DAY)
            except ValueError:
                pass
        final_target = at(final_day)
        candidates.append(
            _Candidate(
                "Registration update",
                "Share how registration is going and remind people to sign up.",
                (
                    "event_name",
                    "registration_url",
                    "registration_status",
                    "capacity",
                    "registration_deadline",
                ),
                min(at(start_day - 7 * DAY), final_target - 3 * DAY),
                "Registration update",
            )
        )
    if days_out >= 4:
        candidates.append(
            _Candidate(
                "Participant preparation",
                "Tell registered attendees what to bring and how to prepare.",
                ("event_name", "start_date", "start_time", "venue", "address"),
                at(start_day - 3 * DAY),
                "Participant preparation",
            )
        )
    if final_target is not None:
        candidates.append(
            _Candidate(
                "Final registration reminder",
                "Last call before registration closes.",
                ("event_name", "registration_url", "registration_deadline", "start_date"),
                final_target,
            )
        )

    selected = [p for p in PLATFORM_ORDER if p in platforms]

    def item(title: str, purpose: str, stage: Stage, when: datetime, keys) -> ProposedItem:
        return ProposedItem(
            title, purpose, stage, when, [k for k in keys if k in available], list(selected)
        )

    items: list[ProposedItem] = []
    if timing != "past":
        pre = _schedule_pre(candidates, earliest, event_at)
        items = [item(c.title, c.purpose, "pre", when, c.keys) for c, when in pre]
        items.append(
            item(
                "Event-day live update",
                "Share that the event is happening today, with times and place.",
                "event",
                event_at,
                ("event_name", "start_time", "end_time", "venue", "hashtags"),
            )
        )
    # Follow-ups never land in the past: a finished event gets them from today, a day apart.
    thanks_at = max(at(end_day + DAY), earliest)
    highlights_at = max(at(end_day + 3 * DAY), thanks_at + DAY)
    items.append(
        item(
            "Post-event thank-you",
            "Thank attendees, mentors, speakers and partners.",
            "post",
            thanks_at,
            ("event_name", "speakers", "mentors", "judges", "partners", "hashtags"),
        )
    )
    items.append(
        item(
            "Highlights and resources",
            "Share winners, highlights or resources from the event.",
            "post",
            highlights_at,
            ("event_name", "hashtags"),
        )
    )
    return sorted(items, key=lambda i: i.scheduled_for)


def _schedule_pre(
    candidates: list[_Candidate], earliest: datetime, limit: datetime
) -> list[tuple[_Candidate, datetime]]:
    """Fit pre-event items before `limit`, keeping order, dropping optional items first."""
    ordered = [candidates[0]] + sorted(candidates[1:], key=lambda c: c.target)

    current = list(ordered)
    for drop in (None, *DROP_ORDER):
        if drop:
            current = [c for c in current if c.drop_key != drop]
        fitted = _assign(current, earliest, limit, DAY)
        if fitted is not None:
            return fitted

    essentials = [c for c in ordered if c.title in ESSENTIAL]
    fitted = _assign(essentials, earliest, limit, TIGHT_GAP)
    if fitted is not None:
        return fitted
    return _assign(essentials, earliest, limit, TIGHT_GAP, partial=True) or []


def _assign(
    items: list[_Candidate],
    earliest: datetime,
    limit: datetime,
    gap: timedelta,
    *,
    partial: bool = False,
) -> list[tuple[_Candidate, datetime]] | None:
    out: list[tuple[_Candidate, datetime]] = []
    prev: datetime | None = None
    for c in items:
        when = max(c.target, earliest)
        if prev is not None:
            when = max(when, prev + gap)
        if when >= limit:
            if partial:
                continue
            return None
        out.append((c, when))
        prev = when
    return out


def _next_at(now: datetime, at: time) -> datetime:
    candidate = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return candidate if candidate >= now else candidate + DAY


def _fact_time(by_key: dict[str, Fact], key: str) -> time | None:
    fact = by_key.get(key)
    if fact is None or not isinstance(fact.value, str):
        return None
    parsed = parse_time(fact.value)
    return time(*parsed) if parsed else None
