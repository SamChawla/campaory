from uuid import UUID

from sqlalchemy import func, select
from support import XRW, make_doc

from app.db import repo
from app.db.models import Campaign, User


def _login(client, email="a@example.org") -> dict:
    response = client.post("/api/auth/test-login", json={"email": email}, headers=XRW)
    return response.json()["user"]


def test_me_is_null_for_guests(client):
    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {"user": None}


def test_me_returns_public_profile_only(client):
    user = _login(client)

    body = client.get("/api/me").json()

    assert body == {
        "user": {"id": user["id"], "email": "a@example.org", "name": "a", "avatar_url": None}
    }


def test_delete_me_removes_account_and_campaigns(client):
    user = _login(client)
    with client.app.state.db_sessions() as db:
        repo.create_campaign(db, UUID(user["id"]), make_doc())

    response = client.delete("/api/me", headers=XRW)

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert client.get("/api/me").json() == {"user": None}
    with client.app.state.db_sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(Campaign)) == 0


def test_delete_me_needs_a_session(client):
    response = client.delete("/api/me", headers=XRW)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_delete_me_leaves_other_users_alone(client):
    _login(client, "other@example.org")
    client.cookies.clear()
    _login(client, "me@example.org")

    client.delete("/api/me", headers=XRW)

    with client.app.state.db_sessions() as db:
        assert [u.email for u in db.scalars(select(User))] == ["other@example.org"]
