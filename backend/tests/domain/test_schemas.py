import copy
import json

import pytest
from pydantic import ValidationError

from app.domain.schemas import MAX_DOCUMENT_BYTES, CampaignDoc, DocumentTooLarge, parse_document

CID = "2b9f7e3c-1d4a-4c8e-9f00-0a1b2c3d4e5f"
ITEM = "6f1c2d3e-4b5a-4c6d-8e7f-001122334455"
POST = "9a8b7c6d-5e4f-4a3b-9c2d-1e0f00112233"


def sample_doc() -> dict:
    return {
        "schema": 1,
        "id": CID,
        "client_id": CID,
        "version": 0,
        "name": "Riverside Open Source Hack Day 2026",
        "event_mode": "offline",
        "language": "en",
        "tone": "friendly",
        "platforms": ["linkedin", "instagram", "whatsapp", "x"],
        "source": {"kind": "sample", "url": None, "fetched_at": None, "text_hash": None},
        "facts": [
            {
                "id": "f0000000-0000-4000-8000-000000000001",
                "key": "event_name",
                "value": "Riverside Open Source Hack Day 2026",
                "status": "confirmed",
                "critical": True,
                "source_snippet": "Riverside Open Source Hack Day 2026",
                "source_ref": "paste",
            },
            {
                "id": "f0000000-0000-4000-8000-000000000002",
                "key": "mentors",
                "value": [{"name": "Asha Verma", "role": "Python"}],
                "status": "needs_review",
                "critical": False,
                "source_snippet": "Mentors: Asha Verma (Python)",
                "source_ref": "paste",
            },
            {
                "id": "f0000000-0000-4000-8000-000000000003",
                "key": "hashtags",
                "value": ["#RiversideHack", "#Hacktoberfest"],
                "status": "confirmed",
                "critical": False,
                "source_snippet": None,
                "source_ref": "manual",
            },
        ],
        "plan": [
            {
                "id": ITEM,
                "title": "Announcement",
                "purpose": "Tell people the event exists",
                "stage": "pre",
                "scheduled_for": "2026-10-17T09:00:00+05:30",
                "position": 0,
                "fact_keys": ["event_name", "start_date"],
            }
        ],
        "posts": [
            {
                "id": POST,
                "plan_item_id": ITEM,
                "platform": "x",
                "text": "Riverside Open Source Hack Day 2026 is on 24 Oct.",
                "status": "draft",
                "facts_used": ["event_name", "start_date"],
                "guard_flags": [],
                "placeholders": [],
                "reminder_at": None,
                "published_url": None,
                "published_at": None,
                "change_reason": None,
                "versions": [
                    {
                        "id": "a0000000-0000-4000-8000-000000000001",
                        "text": "Riverside Open Source Hack Day 2026 is on 24 Oct.",
                        "reason": "generated",
                        "created_at": "2026-10-16T10:00:00Z",
                    }
                ],
            }
        ],
        "created_at": "2026-10-16T10:00:00Z",
        "updated_at": "2026-10-16T10:00:00Z",
    }


def test_valid_document_parses():
    doc = CampaignDoc.model_validate(sample_doc())

    assert doc.facts[1].value[0].name == "Asha Verma"
    assert doc.facts[2].value == ["#RiversideHack", "#Hacktoberfest"]
    assert doc.plan[0].scheduled_for.utcoffset().total_seconds() == 5.5 * 3600


def test_round_trip_is_lossless():
    raw = sample_doc()
    dumped = CampaignDoc.model_validate(raw).model_dump(mode="json", by_alias=True)

    again = CampaignDoc.model_validate(dumped).model_dump(mode="json", by_alias=True)
    assert dumped == again
    assert dumped["schema"] == 1


@pytest.mark.parametrize(
    "path",
    [
        ("extra_top",),
        ("facts", 0, "extra"),
        ("plan", 0, "extra"),
        ("posts", 0, "extra"),
        ("posts", 0, "versions", 0, "extra"),
        ("source", "extra"),
    ],
)
def test_unknown_fields_rejected(path):
    raw = sample_doc()
    target = raw
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = "x"

    with pytest.raises(ValidationError):
        CampaignDoc.model_validate(raw)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(event_mode="virtual"),
        lambda d: d.update(language="fr"),
        lambda d: d.update(platforms=["facebook"]),
        lambda d: d["facts"][0].update(status="maybe"),
        lambda d: d["facts"][0].update(key="favourite_colour"),
        lambda d: d["plan"][0].update(stage="later"),
        lambda d: d["posts"][0].update(status="live"),
        lambda d: d["posts"][0].update(platform="threads"),
        lambda d: d["source"].update(kind="pdf"),
        lambda d: d.update(schema=2),
    ],
)
def test_bad_enums_rejected(mutate):
    raw = sample_doc()
    mutate(raw)

    with pytest.raises(ValidationError):
        CampaignDoc.model_validate(raw)


def test_tone_limited_to_40_chars():
    raw = sample_doc()
    raw["tone"] = "x" * 41

    with pytest.raises(ValidationError):
        CampaignDoc.model_validate(raw)


def test_client_id_must_equal_id():
    raw = sample_doc()
    raw["client_id"] = "3c9f7e3c-1d4a-4c8e-9f00-0a1b2c3d4e5f"

    with pytest.raises(ValidationError):
        CampaignDoc.model_validate(raw)


def test_naive_datetime_rejected():
    raw = sample_doc()
    raw["plan"][0]["scheduled_for"] = "2026-10-17T09:00:00"

    with pytest.raises(ValidationError):
        CampaignDoc.model_validate(raw)


def test_duplicate_platforms_rejected():
    raw = sample_doc()
    raw["platforms"] = ["x", "x"]

    with pytest.raises(ValidationError):
        CampaignDoc.model_validate(raw)


def test_post_must_reference_existing_plan_item():
    raw = sample_doc()
    raw["posts"][0]["plan_item_id"] = "00000000-0000-4000-8000-00000000dead"

    with pytest.raises(ValidationError):
        CampaignDoc.model_validate(raw)


def test_parse_document_accepts_json_text():
    doc = parse_document(json.dumps(sample_doc()))

    assert doc.name.startswith("Riverside")


def test_parse_document_rejects_over_512_kb():
    raw = sample_doc()
    post = raw["posts"][0]
    raw["posts"] = []
    for i in range(400):
        p = copy.deepcopy(post)
        p["id"] = f"9a8b7c6d-5e4f-4a3b-9c2d-{i:012d}"
        p["text"] = "y" * 1400
        raw["posts"].append(p)
    text = json.dumps(raw)
    assert len(text.encode()) > MAX_DOCUMENT_BYTES

    with pytest.raises(DocumentTooLarge):
        parse_document(text)
