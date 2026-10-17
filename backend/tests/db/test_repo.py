from uuid import uuid4

import pytest
from sqlalchemy import func, select
from support import comparable, make_doc

from app.core.errors import AppError
from app.db import repo
from app.db.models import Campaign, FactRow, Identity, PostRow, PostVersionRow, User


def _user(db, email="a@example.org", subject=None) -> User:
    return repo.upsert_user_from_identity(
        db, "google", subject or email, email, "Asha", "https://img.example/a.png"
    )


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# create / get


def test_saved_then_loaded_document_is_deep_equal(db):
    user = _user(db)
    doc = make_doc(statuses=("draft", "needs_review", "approved", "scheduled", "published"))

    saved, created = repo.create_campaign(db, user.id, doc)
    loaded = repo.get_campaign(db, user.id, doc.id)

    assert created is True
    assert saved.version == 1
    assert loaded.version == 1
    assert comparable(loaded) == comparable(doc)
    assert (
        loaded.model_dump(mode="json", by_alias=True)["facts"]
        == doc.model_dump(mode="json", by_alias=True)["facts"]
    )


def test_list_order_is_kept_even_when_position_differs(db):
    user = _user(db)
    doc = make_doc(statuses=("draft", "draft", "draft"))

    repo.create_campaign(db, user.id, doc)
    loaded = repo.get_campaign(db, user.id, doc.id)

    assert [i.id for i in loaded.plan] == [i.id for i in doc.plan]
    assert [i.position for i in loaded.plan] == [1, 0]
    assert [p.id for p in loaded.posts] == [p.id for p in doc.posts]
    assert [v.reason for v in loaded.posts[0].versions] == ["generated", "revise:make_shorter"]


def test_create_is_idempotent_on_client_id(db):
    user = _user(db)
    doc = make_doc()
    repo.create_campaign(db, user.id, doc)
    changed = doc.model_copy(update={"name": "Something else"})

    again, created = repo.create_campaign(db, user.id, changed)

    assert created is False
    assert again.name == doc.name
    assert _count(db, Campaign) == 1


def test_two_users_can_hold_the_same_document(db):
    a, b = _user(db, "a@example.org"), _user(db, "b@example.org")
    doc = make_doc()

    repo.create_campaign(db, a.id, doc)
    _, created = repo.create_campaign(db, b.id, doc)

    assert created is True
    assert _count(db, Campaign) == 2


def test_get_returns_none_for_foreign_or_unknown_id(db):
    a, b = _user(db, "a@example.org"), _user(db, "b@example.org")
    doc = make_doc()
    repo.create_campaign(db, a.id, doc)

    assert repo.get_campaign(db, b.id, doc.id) is None
    assert repo.get_campaign(db, a.id, uuid4()) is None


def test_free_plan_limit_blocks_new_campaigns(db):
    user = _user(db)
    first = make_doc()
    repo.create_campaign(db, user.id, first, max_campaigns=1)

    with pytest.raises(AppError) as raised:
        repo.create_campaign(db, user.id, make_doc(), max_campaigns=1)

    assert raised.value.status == 409
    assert raised.value.code == "campaign_limit"
    assert raised.value.details == {"limit": 1}


def test_free_plan_limit_allows_idempotent_repeat(db):
    user = _user(db)
    doc = make_doc()
    repo.create_campaign(db, user.id, doc, max_campaigns=1)

    _, created = repo.create_campaign(db, user.id, doc, max_campaigns=1)

    assert created is False


def test_zero_limit_disables_the_check(db):
    user = _user(db)
    for _ in range(3):
        repo.create_campaign(db, user.id, make_doc(), max_campaigns=0)

    assert _count(db, Campaign) == 3


def test_limit_counts_only_own_campaigns(db):
    a, b = _user(db, "a@example.org"), _user(db, "b@example.org")
    repo.create_campaign(db, a.id, make_doc(), max_campaigns=1)

    _, created = repo.create_campaign(db, b.id, make_doc(), max_campaigns=1)

    assert created is True


# replace


def test_replace_swaps_the_tree_and_bumps_version(db):
    user = _user(db)
    doc = make_doc(statuses=("draft", "draft"))
    repo.create_campaign(db, user.id, doc)
    new_post = doc.posts[0].model_copy(update={"text": "Edited", "status": "approved"})
    edited = doc.model_copy(update={"name": "Renamed", "posts": [new_post], "facts": doc.facts[:1]})

    replaced = repo.replace_campaign(db, user.id, doc.id, edited, expected_version=1)
    loaded = repo.get_campaign(db, user.id, doc.id)

    assert replaced.version == 2
    assert loaded.version == 2
    assert comparable(loaded) == comparable(edited)
    assert _count(db, PostRow) == 1
    assert _count(db, FactRow) == 1
    assert _count(db, PostVersionRow) == 2


def test_replace_with_stale_version_conflicts(db):
    user = _user(db)
    doc = make_doc()
    repo.create_campaign(db, user.id, doc)
    repo.replace_campaign(db, user.id, doc.id, doc, expected_version=1)

    with pytest.raises(AppError) as raised:
        repo.replace_campaign(db, user.id, doc.id, doc, expected_version=1)

    assert raised.value.status == 409
    assert raised.value.code == "version_conflict"
    assert raised.value.details == {"current_version": 2}
    assert repo.get_campaign(db, user.id, doc.id).version == 2


def test_replace_foreign_campaign_returns_none_and_changes_nothing(db):
    a, b = _user(db, "a@example.org"), _user(db, "b@example.org")
    doc = make_doc()
    repo.create_campaign(db, a.id, doc)

    result = repo.replace_campaign(
        db, b.id, doc.id, doc.model_copy(update={"name": "Hijack"}), expected_version=1
    )

    assert result is None
    assert repo.get_campaign(db, a.id, doc.id).name == doc.name


# list / delete


def test_list_returns_own_campaigns_with_post_counts(db):
    a, b = _user(db, "a@example.org"), _user(db, "b@example.org")
    mine = make_doc(name="Mine", statuses=("draft", "draft", "published"))
    empty = make_doc(name="Empty", statuses=())
    repo.create_campaign(db, a.id, mine)
    repo.create_campaign(db, a.id, empty)
    repo.create_campaign(db, b.id, make_doc(name="Theirs"))

    rows = repo.list_campaigns(db, a.id)

    by_name = {row.name: row for row in rows}
    assert set(by_name) == {"Mine", "Empty"}
    assert by_name["Mine"].id == mine.id
    assert by_name["Mine"].version == 1
    assert by_name["Mine"].post_counts == {
        "draft": 2,
        "needs_review": 0,
        "approved": 0,
        "scheduled": 0,
        "published": 1,
    }
    assert sum(by_name["Empty"].post_counts.values()) == 0


def test_list_is_newest_first(db):
    user = _user(db)
    old = make_doc(name="Old")
    new = make_doc(name="New")
    new = new.model_copy(update={"updated_at": old.updated_at.replace(year=2027)})
    repo.create_campaign(db, user.id, old)
    repo.create_campaign(db, user.id, new)

    assert [row.name for row in repo.list_campaigns(db, user.id)] == ["New", "Old"]


def test_delete_campaign_only_touches_own(db):
    a, b = _user(db, "a@example.org"), _user(db, "b@example.org")
    doc = make_doc()
    repo.create_campaign(db, a.id, doc)

    assert repo.delete_campaign(db, b.id, doc.id) is False
    assert repo.get_campaign(db, a.id, doc.id) is not None
    assert repo.delete_campaign(db, a.id, doc.id) is True
    assert repo.get_campaign(db, a.id, doc.id) is None
    assert _count(db, PostRow) == 0


def test_delete_user_removes_identities_and_campaigns(db):
    user = _user(db)
    repo.create_campaign(db, user.id, make_doc())

    assert repo.delete_user(db, user.id) is True

    assert _count(db, User) == 0
    assert _count(db, Identity) == 0
    assert _count(db, Campaign) == 0
    assert repo.delete_user(db, user.id) is False


# users


def test_upsert_creates_user_and_identity(db):
    user = _user(db, "asha@example.org", subject="g-1")

    assert user.email == "asha@example.org"
    assert user.name == "Asha"
    assert user.last_login_at is not None
    identity = db.scalar(select(Identity))
    assert (identity.provider, identity.subject, identity.user_id) == ("google", "g-1", user.id)


def test_upsert_same_identity_updates_profile(db):
    first = _user(db, "asha@example.org", subject="g-1")

    again = repo.upsert_user_from_identity(db, "google", "g-1", "asha@new.org", "Asha V", None)

    assert again.id == first.id
    assert (again.email, again.name, again.avatar_url) == ("asha@new.org", "Asha V", None)
    assert _count(db, User) == 1


def test_upsert_links_new_identity_to_existing_email(db):
    first = _user(db, "Asha@Example.org", subject="g-1")

    linked = repo.upsert_user_from_identity(db, "test", "t-1", "asha@example.org", None, None)

    assert linked.id == first.id
    assert _count(db, Identity) == 2


def test_upsert_keeps_email_when_new_one_belongs_to_someone_else(db):
    _user(db, "taken@example.org", subject="g-2")
    mine = _user(db, "asha@example.org", subject="g-1")

    again = repo.upsert_user_from_identity(db, "google", "g-1", "taken@example.org", "A", None)

    assert again.id == mine.id
    assert again.email == "asha@example.org"


def test_get_user(db):
    user = _user(db)

    assert repo.get_user(db, user.id).email == "a@example.org"
    assert repo.get_user(db, uuid4()) is None
