from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.models import (
    Campaign,
    FactRow,
    Identity,
    PlanItemRow,
    PostRow,
    PostVersionRow,
    User,
)


def _user(db, email="a@example.org") -> User:
    user = User(email=email, name="A")
    db.add(user)
    db.flush()
    return user


def _campaign_values(user: User, **overrides) -> dict:
    values = dict(
        user_id=user.id,
        client_id=uuid4(),
        name="Hack Day",
        event_mode="offline",
        language="en",
        tone="",
        platforms=["x", "linkedin"],
        source={"kind": "manual"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    values.update(overrides)
    return values


def _campaign_tree(db, user: User) -> Campaign:
    campaign = Campaign(**_campaign_values(user))
    db.add(campaign)
    db.flush()
    item = PlanItemRow(
        campaign_id=campaign.id,
        doc_id=uuid4(),
        title="Announcement",
        stage="pre",
        position=0,
        seq=0,
        fact_keys=["event_name"],
    )
    db.add_all(
        [
            FactRow(
                campaign_id=campaign.id,
                doc_id=uuid4(),
                key="event_name",
                value="Hack Day",
                status="confirmed",
                critical=True,
                position=0,
            ),
            item,
        ]
    )
    db.flush()
    post = PostRow(
        campaign_id=campaign.id,
        plan_item_id=item.id,
        doc_id=uuid4(),
        platform="x",
        text="Hello",
        status="draft",
        seq=0,
        facts_used=["event_name"],
        guard_flags=[],
        placeholders=[],
    )
    db.add(post)
    db.flush()
    db.add(
        PostVersionRow(
            post_id=post.id,
            doc_id=uuid4(),
            text="Hello",
            reason="generated",
            seq=0,
            created_at=datetime.now(UTC),
        )
    )
    db.add(Identity(user_id=user.id, provider="google", subject="sub-1"))
    db.commit()
    return campaign


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


CAMPAIGN_TREE = (Campaign, FactRow, PlanItemRow, PostRow, PostVersionRow)


def test_deleting_user_cascades_to_everything(db):
    user = _user(db)
    _campaign_tree(db, user)
    assert all(_count(db, m) == 1 for m in (*CAMPAIGN_TREE, Identity))

    db.delete(user)
    db.commit()

    assert all(_count(db, m) == 0 for m in (*CAMPAIGN_TREE, Identity))


def test_deleting_campaign_cascades_to_children_only(db):
    campaign = _campaign_tree(db, _user(db))

    db.delete(campaign)
    db.commit()

    assert all(_count(db, m) == 0 for m in CAMPAIGN_TREE)
    assert _count(db, User) == 1
    assert _count(db, Identity) == 1


def test_deleting_plan_item_cascades_to_its_posts(db):
    campaign = _campaign_tree(db, _user(db))
    item = db.scalar(select(PlanItemRow).where(PlanItemRow.campaign_id == campaign.id))

    db.delete(item)
    db.commit()

    assert _count(db, PostRow) == 0
    assert _count(db, PostVersionRow) == 0
    assert _count(db, FactRow) == 1


def test_email_is_unique_ignoring_case(db):
    _user(db, "Asha@Example.org")
    with pytest.raises(IntegrityError):
        _user(db, "asha@example.org")


def test_identity_is_unique_per_provider_and_subject(db):
    user = _user(db)
    db.add(Identity(user_id=user.id, provider="google", subject="s"))
    db.flush()
    db.add(Identity(user_id=user.id, provider="google", subject="s"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_client_id_is_unique_per_user(db):
    user = _user(db)
    campaign = _campaign_tree(db, user)
    db.add(Campaign(**_campaign_values(user, client_id=campaign.client_id)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_client_id_is_fine_for_two_users(db):
    a, b = _user(db, "a@example.org"), _user(db, "b@example.org")
    client_id = uuid4()
    db.add(Campaign(**_campaign_values(a, client_id=client_id)))
    db.add(Campaign(**_campaign_values(b, client_id=client_id)))
    db.flush()

    assert _count(db, Campaign) == 2


@pytest.mark.parametrize("field,value", [("event_mode", "virtual"), ("language", "fr")])
def test_campaign_enum_checks(db, field, value):
    db.add(Campaign(**_campaign_values(_user(db), **{field: value})))
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "model,field,value",
    [
        (FactRow, "status", "maybe"),
        (PlanItemRow, "stage", "later"),
        (PostRow, "status", "sent"),
        (PostRow, "platform", "facebook"),
    ],
)
def test_child_enum_checks(db, model, field, value):
    campaign = _campaign_tree(db, _user(db))
    row = db.scalar(select(model).where(model.campaign_id == campaign.id))
    setattr(row, field, value)
    with pytest.raises(IntegrityError):
        db.flush()


def test_platforms_and_json_columns_round_trip(db):
    campaign = _campaign_tree(db, _user(db))
    db.expire_all()

    loaded = db.get(Campaign, campaign.id)
    post = db.scalar(select(PostRow))
    assert loaded.platforms == ["x", "linkedin"]
    assert loaded.source == {"kind": "manual"}
    assert post.facts_used == ["event_name"]


def test_timestamps_come_back_aware_utc(db):
    campaign = _campaign_tree(db, _user(db))
    ist = timezone(timedelta(hours=5, minutes=30))
    campaign.updated_at = datetime(2026, 10, 20, 9, 0, tzinfo=ist)
    db.commit()
    db.expire_all()

    loaded = db.get(Campaign, campaign.id)
    assert loaded.updated_at == datetime(2026, 10, 20, 3, 30, tzinfo=UTC)
    assert loaded.updated_at.utcoffset() == timedelta(0)


def test_naive_timestamps_are_rejected(db):
    campaign = _campaign_tree(db, _user(db))
    campaign.updated_at = datetime(2026, 10, 20, 9, 0)
    with pytest.raises(StatementError, match="timezone"):
        db.flush()
