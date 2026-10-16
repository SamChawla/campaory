"""Change impact (ADR-006, LLD 6.4). Deterministic: correct even when the model is down."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.domain.facts import (
    confirmed_map,
    extract_tokens,
    normalize_text,
    normalize_url,
    parse_date,
    parse_time,
)
from app.domain.planning import PlanBlocked, propose_plan
from app.domain.schemas import PLATFORM_ORDER, Fact, Person, PlanItem, Post

DATE_KEYS = frozenset({"start_date", "end_date", "start_time", "timezone", "registration_deadline"})
MIN_TEXT_MATCH = 3
Reason = Literal["facts_used", "text_match", "plan_item"]
_REASON_RANK = {"facts_used": 0, "text_match": 1, "plan_item": 2}

PUBLISHED_NOTE = "Already public. Consider a correction post."


@dataclass(frozen=True)
class Change:
    key: str
    old: str | list
    new: str | list


@dataclass
class Affected:
    post_id: UUID
    reason: Reason
    detail: str


@dataclass
class Protected:
    post_id: UUID
    status: str
    note: str = PUBLISHED_NOTE


@dataclass
class PlanChange:
    plan_item_id: UUID
    field: str
    old: datetime | None
    new: datetime


@dataclass
class ImpactResult:
    affected: list[Affected] = field(default_factory=list)
    protected: list[Protected] = field(default_factory=list)
    plan_changes: list[PlanChange] = field(default_factory=list)


def analyze(
    change: Change,
    facts: list[Fact],
    posts: list[Post],
    plan: list[PlanItem],
    *,
    today: date,
    language: str | None = "en",
) -> ImpactResult:
    detail = f"{change.key} changed from {_show(change.old)} to {_show(change.new)}"
    items_with_key = {item.id for item in plan if change.key in item.fact_keys}
    position = {item.id: item.position for item in plan}

    hits: dict[UUID, tuple[Post, Reason]] = {}
    for post in posts:
        reason: Reason | None = None
        if change.key in post.facts_used:
            reason = "facts_used"
        elif _text_mentions(post.text, change):
            reason = "text_match"
        elif post.plan_item_id in items_with_key:
            reason = "plan_item"
        if reason:
            hits[post.id] = (post, reason)

    def order(entry: tuple[Post, Reason]) -> tuple[int, int]:
        post = entry[0]
        return (position.get(post.plan_item_id, 10_000), PLATFORM_ORDER.index(post.platform))

    result = ImpactResult()
    for post, reason in sorted(hits.values(), key=order):
        if post.status == "published":
            result.protected.append(Protected(post.id, post.status))
        else:
            result.affected.append(Affected(post.id, reason, detail))

    if change.key in DATE_KEYS:
        result.plan_changes = _plan_changes(facts, posts, plan, today, language)
    return result


def _text_mentions(text: str, change: Change) -> bool:
    olds = _removed_values(change.old, change.new)
    tokens = extract_tokens(text)
    for old in olds:
        old_date = parse_date(old) if change.key in DATE_KEYS or len(old) <= 30 else None
        old_time = parse_time(old)
        old_url = normalize_url(old) if "." in old else None
        if old_url and any(t.kind == "url" and t.value == old_url for t in tokens):
            return True
        if old_date and any(
            t.kind == "date"
            and (t.value.month, t.value.day) == (old_date.month, old_date.day)
            and (t.value.year is None or old_date.year is None or t.value.year == old_date.year)
            for t in tokens
        ):
            return True
        if old_time and any(t.kind == "time" and t.value == old_time for t in tokens):
            return True
        norm = normalize_text(old)
        if len(norm) >= MIN_TEXT_MATCH and norm in normalize_text(text):
            return True
    return False


def _removed_values(old: str | list, new: str | list) -> list[str]:
    if isinstance(old, list):
        new_names = {_name(v) for v in (new if isinstance(new, list) else [])}
        return [_name(v) for v in old if _name(v) not in new_names]
    return [str(old)] if str(old).strip() else []


def _name(value: object) -> str:
    if isinstance(value, Person):
        return value.name
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value)


def _show(value: str | list) -> str:
    if isinstance(value, list):
        return ", ".join(_name(v) for v in value) or "nothing"
    return value or "nothing"


def _plan_changes(
    facts: list[Fact], posts: list[Post], plan: list[PlanItem], today: date, language: str | None
) -> list[PlanChange]:
    by_key = confirmed_map(facts)
    tz = by_key.get("timezone")
    if tz is None:
        return []
    platforms = sorted({p.platform for p in posts}, key=PLATFORM_ORDER.index) or list(
        PLATFORM_ORDER
    )
    try:
        proposed = propose_plan(
            facts, platforms, today=today, timezone=str(tz.value), language=language
        )
    except PlanBlocked:
        return []
    new_by_title = {item.title: item.scheduled_for for item in proposed}
    changes = []
    for item in sorted(plan, key=lambda i: i.position):
        new = new_by_title.get(item.title)
        if new is not None and new != item.scheduled_for:
            changes.append(PlanChange(item.id, "scheduled_for", item.scheduled_for, new))
    return changes
