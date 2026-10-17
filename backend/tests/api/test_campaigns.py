import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from support import XRW, comparable, make_doc, make_doc_dict

from app.core.config import Settings
from app.db.models import Base
from app.domain.schemas import MAX_DOCUMENT_BYTES, CampaignDoc
from app.main import create_app


def _app(tmp_path, **overrides):
    values = dict(
        app_env="test",
        llm_provider="mock",
        static_dir=str(tmp_path / "static"),
        database_url="sqlite://",
    )
    values.update(overrides)
    app = create_app(Settings(**values))
    Base.metadata.create_all(app.state.db_engine)
    return app


def _signed_in(app, email: str) -> TestClient:
    client = TestClient(app)
    client.headers.update(XRW)
    assert client.post("/api/auth/test-login", json={"email": email}).status_code == 200
    return client


@pytest.fixture
def app(tmp_path):
    return _app(tmp_path, free_plan_max_campaigns=0)


@pytest.fixture
def alice(app) -> TestClient:
    return _signed_in(app, "alice@example.org")


@pytest.fixture
def bob(app) -> TestClient:
    return _signed_in(app, "bob@example.org")


def _post(client, doc: dict):
    return client.post("/api/campaigns", json=doc)


def _put(client, doc: dict, expected_version: int):
    return client.put(
        f"/api/campaigns/{doc['id']}", json={"expected_version": expected_version, "doc": doc}
    )


# auth


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/campaigns"),
        ("POST", "/api/campaigns"),
        ("GET", f"/api/campaigns/{uuid4()}"),
        ("PUT", f"/api/campaigns/{uuid4()}"),
        ("DELETE", f"/api/campaigns/{uuid4()}"),
    ],
)
def test_every_route_needs_a_session(app, method, path):
    response = TestClient(app).request(method, path, headers=XRW, json=make_doc_dict())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


# create


def test_import_creates_then_is_idempotent(alice):
    doc = make_doc_dict()

    first = _post(alice, doc)
    again = _post(alice, {**doc, "name": "Changed in the meantime"})

    assert first.status_code == 201
    assert first.json() == {"id": doc["id"], "version": 1}
    assert again.status_code == 200
    assert again.json() == {"id": doc["id"], "version": 1}
    assert alice.get(f"/api/campaigns/{doc['id']}").json()["name"] == doc["name"]


def test_saved_document_comes_back_equal(alice):
    doc = make_doc_dict(statuses=("draft", "approved", "scheduled", "published"))
    _post(alice, doc)

    body = alice.get(f"/api/campaigns/{doc['id']}").json()

    assert body["version"] == 1
    assert body["schema"] == 1
    assert comparable(CampaignDoc.model_validate(body)) == comparable(
        CampaignDoc.model_validate(doc)
    )


def test_invalid_document_is_rejected(alice):
    doc = make_doc_dict()
    doc["posts"][0]["status"] = "sent"

    response = _post(alice, doc)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["fields"]


def test_unknown_fields_are_rejected(alice):
    response = _post(alice, {**make_doc_dict(), "owner": "someone"})

    assert response.status_code == 422


def test_body_that_is_not_json_is_rejected(alice):
    response = alice.post(
        "/api/campaigns", content=b"{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_document_over_512_kb_is_rejected(alice):
    raw = json.dumps(make_doc_dict()) + " " * MAX_DOCUMENT_BYTES

    response = alice.post(
        "/api/campaigns", content=raw.encode(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_document_just_under_the_cap_is_accepted(alice):
    raw = json.dumps(make_doc_dict())
    raw = raw + " " * (MAX_DOCUMENT_BYTES - len(raw.encode()))

    response = alice.post(
        "/api/campaigns", content=raw.encode(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 201


# free plan


def test_free_plan_limit(tmp_path):
    client = _signed_in(_app(tmp_path, free_plan_max_campaigns=1), "a@example.org")
    first = make_doc_dict()
    _post(client, first)

    blocked = _post(client, make_doc_dict())
    repeat = _post(client, first)

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "campaign_limit"
    assert blocked.json()["error"]["details"] == {"limit": 1}
    assert "Delete one" in blocked.json()["error"]["message"]
    assert repeat.status_code == 200


def test_limit_frees_up_after_delete(tmp_path):
    client = _signed_in(_app(tmp_path, free_plan_max_campaigns=1), "a@example.org")
    first = make_doc_dict()
    _post(client, first)
    client.delete(f"/api/campaigns/{first['id']}")

    assert _post(client, make_doc_dict()).status_code == 201


def test_zero_disables_the_limit(alice):
    for _ in range(3):
        assert _post(alice, make_doc_dict()).status_code == 201


# list


def test_list_shows_own_campaigns_with_counts(alice, bob):
    mine = make_doc_dict(name="Mine", statuses=("draft", "published", "published"))
    _post(alice, mine)
    _post(bob, make_doc_dict(name="Bob's"))

    body = alice.get("/api/campaigns").json()

    assert body == {
        "campaigns": [
            {
                "id": mine["id"],
                "name": "Mine",
                "version": 1,
                "updated_at": "2026-10-16T05:30:00Z",
                "post_counts": {
                    "draft": 1,
                    "needs_review": 0,
                    "approved": 0,
                    "scheduled": 0,
                    "published": 2,
                },
            }
        ]
    }


def test_list_is_empty_for_new_user(alice):
    assert alice.get("/api/campaigns").json() == {"campaigns": []}


# replace


def test_replace_bumps_version(alice):
    doc = make_doc_dict()
    _post(alice, doc)
    edited = {**doc, "name": "Renamed", "tone": "formal"}

    response = _put(alice, edited, 1)

    assert response.status_code == 200
    assert response.json() == {"version": 2}
    body = alice.get(f"/api/campaigns/{doc['id']}").json()
    assert (body["name"], body["tone"], body["version"]) == ("Renamed", "formal", 2)


def test_replace_with_stale_version_conflicts(alice):
    doc = make_doc_dict()
    _post(alice, doc)
    _put(alice, doc, 1)

    response = _put(alice, {**doc, "name": "Old tab"}, 1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    assert response.json()["error"]["details"] == {"current_version": 2}
    assert alice.get(f"/api/campaigns/{doc['id']}").json()["name"] == doc["name"]


def test_replace_with_mismatched_id_is_rejected(alice):
    doc = make_doc_dict()
    other = make_doc_dict()
    _post(alice, doc)

    response = alice.put(f"/api/campaigns/{doc['id']}", json={"expected_version": 1, "doc": other})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_replace_needs_expected_version(alice):
    doc = make_doc_dict()
    _post(alice, doc)

    response = alice.put(f"/api/campaigns/{doc['id']}", json={"doc": doc})

    assert response.status_code == 422


def test_replace_unknown_campaign_is_404(alice):
    response = _put(alice, make_doc_dict(), 1)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_replace_body_over_cap_is_rejected(alice):
    doc = make_doc_dict()
    _post(alice, doc)
    raw = json.dumps({"expected_version": 1, "doc": doc}) + " " * MAX_DOCUMENT_BYTES * 2

    response = alice.put(
        f"/api/campaigns/{doc['id']}",
        content=raw.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


# delete


def test_delete_then_get_is_404(alice):
    doc = make_doc_dict()
    _post(alice, doc)

    assert alice.delete(f"/api/campaigns/{doc['id']}").status_code == 204
    assert alice.get(f"/api/campaigns/{doc['id']}").status_code == 404
    assert alice.delete(f"/api/campaigns/{doc['id']}").status_code == 404


# BR12 ownership


def test_other_user_gets_404_on_get_put_delete(alice, bob):
    doc = make_doc_dict()
    _post(alice, doc)
    url = f"/api/campaigns/{doc['id']}"

    responses = [
        bob.get(url),
        _put(bob, {**doc, "name": "Hijacked"}, 1),
        bob.delete(url),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    body = alice.get(url).json()
    assert (body["name"], body["version"]) == (doc["name"], 1)
    assert bob.get("/api/campaigns").json() == {"campaigns": []}


def test_other_user_importing_same_document_gets_their_own_copy(alice, bob):
    doc = make_doc_dict()
    _post(alice, doc)

    response = _post(bob, {**doc, "name": "Bob's copy"})

    assert response.status_code == 201
    assert alice.get(f"/api/campaigns/{doc['id']}").json()["name"] == doc["name"]
    assert bob.get(f"/api/campaigns/{doc['id']}").json()["name"] == "Bob's copy"


@pytest.mark.parametrize("bad", ["not-a-uuid", "123"])
def test_malformed_id_is_404(alice, bad):
    assert alice.get(f"/api/campaigns/{bad}").status_code == 404
    assert alice.delete(f"/api/campaigns/{bad}").status_code == 404


def test_make_doc_helper_is_valid():
    assert make_doc().version == 0


@pytest.mark.parametrize("raw", [b'{"name": "\xff"}', b"[1, 2]", b"null"])
def test_odd_bodies_are_422_not_500(alice, raw):
    headers = {"Content-Type": "application/json"}

    response = alice.post("/api/campaigns", content=raw, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
