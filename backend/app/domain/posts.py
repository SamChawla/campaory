"""Post status rules (LLD 7, ARCHITECTURE 6). BR02, BR03, BR05, BR06."""

from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.schemas import Post, PostStatus

_FROM: dict[PostStatus, frozenset[PostStatus]] = {
    "approved": frozenset({"draft", "needs_review", "scheduled"}),
    "scheduled": frozenset({"approved"}),
    "published": frozenset({"approved", "scheduled"}),
    "needs_review": frozenset({"draft", "approved", "scheduled"}),
    "draft": frozenset({"needs_review"}),
}


class PublishedPostError(ValueError):
    """Published posts are never modified (BR03)."""


@dataclass
class TransitionCheck:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


def can_transition(
    post: Post,
    to: PostStatus,
    *,
    confirmed_keys: Collection[str],
    validation_ok: bool,
    now: datetime,
    reminder_at: datetime | None = None,
) -> TransitionCheck:
    if post.status == "published":
        return TransitionCheck(False, ["This post is published and cannot change."])
    if post.status not in _FROM[to]:
        return TransitionCheck(False, [f"A {_label(post.status)} post cannot become {_label(to)}."])

    reasons: list[str] = []
    if to == "approved" and post.status != "scheduled":
        unconfirmed = [k for k in post.facts_used if k not in confirmed_keys]
        if unconfirmed:
            reasons.append("Confirm these facts first: " + ", ".join(unconfirmed))
        if not validation_ok:
            reasons.append("Fix the platform limits first.")
        blocking = [f.token for f in post.guard_flags if f.blocking]
        if blocking:
            reasons.append(
                "Check these details, they are not in your facts: " + ", ".join(blocking)
            )
        if post.placeholders:
            reasons.append("Fill in: " + ", ".join(post.placeholders))
    elif to == "scheduled":
        when = reminder_at or post.reminder_at
        if when is None or when <= now:
            reasons.append("Pick a reminder time in the future.")
    return TransitionCheck(not reasons, reasons)


def after_edit(status: PostStatus) -> PostStatus:
    """Status after the user edits the text."""
    if status == "published":
        raise PublishedPostError("published posts cannot be edited")
    if status in ("approved", "scheduled"):
        return "draft"
    return status


def _label(status: PostStatus) -> str:
    return status.replace("_", " ")
