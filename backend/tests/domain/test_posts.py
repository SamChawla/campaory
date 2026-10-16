from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.posts import PublishedPostError, after_edit, can_transition
from app.domain.schemas import GuardFlag, Post

NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)
CONFIRMED = {"event_name", "start_date"}


def post(status="draft", **kw) -> Post:
    defaults = dict(
        id=uuid4(),
        plan_item_id=uuid4(),
        platform="x",
        text="Hello",
        status=status,
        facts_used=["event_name"],
    )
    defaults.update(kw)
    return Post(**defaults)


def check(p, to, *, validation_ok=True, confirmed=CONFIRMED, reminder_at=None):
    return can_transition(
        p,
        to,
        confirmed_keys=confirmed,
        validation_ok=validation_ok,
        now=NOW,
        reminder_at=reminder_at,
    )


@pytest.mark.parametrize("start", ["draft", "needs_review"])
def test_approve_when_all_preconditions_met(start):
    assert check(post(start), "approved").allowed


def test_br02_unconfirmed_fact_blocks_approval():
    result = check(post(facts_used=["event_name", "venue"]), "approved")

    assert not result.allowed
    assert result.reasons == ["Confirm these facts first: venue"]


def test_validation_error_blocks_approval():
    result = check(post(), "approved", validation_ok=False)

    assert not result.allowed
    assert "platform" in result.reasons[0].lower()


def test_blocking_guard_flag_blocks_approval():
    flag = GuardFlag(code="UNKNOWN_DATE", token="25 Oct", span=(0, 6))
    result = check(post(guard_flags=[flag]), "approved")

    assert not result.allowed
    assert "25 Oct" in result.reasons[0]


def test_relative_date_flag_does_not_block():
    flag = GuardFlag(code="RELATIVE_DATE", token="tomorrow", span=(0, 8), blocking=False)

    assert check(post(guard_flags=[flag]), "approved").allowed


def test_placeholder_blocks_approval():
    result = check(post(placeholders=["speaker name"]), "approved")

    assert not result.allowed
    assert "speaker name" in result.reasons[0]


def test_br06_schedule_needs_approved_and_future():
    future = NOW + timedelta(hours=1)
    assert check(post("approved"), "scheduled", reminder_at=future).allowed
    assert not check(post("draft"), "scheduled", reminder_at=future).allowed
    assert not check(post("approved"), "scheduled", reminder_at=NOW - timedelta(minutes=1)).allowed
    assert not check(post("approved"), "scheduled").allowed


def test_clearing_reminder_returns_to_approved():
    assert check(post("scheduled"), "approved").allowed


def test_br05_publish_only_from_approved_or_scheduled():
    assert check(post("approved"), "published").allowed
    assert check(post("scheduled"), "published").allowed
    assert not check(post("draft"), "published").allowed
    assert not check(post("needs_review"), "published").allowed


def test_br03_published_is_final():
    for to in ("draft", "needs_review", "approved", "scheduled"):
        assert not check(post("published"), to).allowed


def test_needs_review_from_any_unpublished():
    for start in ("draft", "approved", "scheduled"):
        assert check(post(start), "needs_review").allowed


def test_editing_approved_post_returns_to_draft():
    assert after_edit("approved") == "draft"
    assert after_edit("scheduled") == "draft"
    assert after_edit("needs_review") == "needs_review"
    assert after_edit("draft") == "draft"


def test_editing_published_post_refused():
    with pytest.raises(PublishedPostError):
        after_edit("published")
