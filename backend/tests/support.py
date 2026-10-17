"""Shared helpers for DB and saved-campaign tests. Importable because tests/ is on sys.path."""

from uuid import uuid4

from app.domain.schemas import CampaignDoc

XRW = {"X-Requested-With": "campaory"}


def make_doc_dict(*, name: str = "Riverside Open Source Hack Day", statuses=("draft",)) -> dict:
    """A full, valid campaign document with fresh ids. One post per entry in `statuses`."""
    cid = str(uuid4())
    item_a, item_b = str(uuid4()), str(uuid4())
    posts = []
    for index, status in enumerate(statuses):
        published = status == "published"
        posts.append(
            {
                "id": str(uuid4()),
                "plan_item_id": item_a if index % 2 == 0 else item_b,
                "platform": ("x", "linkedin", "instagram", "whatsapp")[index % 4],
                "text": f"{name} is on 24 Oct. Post {index}.",
                "status": status,
                "facts_used": ["event_name", "start_date"],
                "guard_flags": [{"code": "unknown_date", "token": "25 Oct", "span": [3, 9]}],
                "placeholders": ["[venue]"],
                "reminder_at": "2026-10-20T09:00:00+05:30" if status == "scheduled" else None,
                "published_url": "https://x.com/a/status/1" if published else None,
                "published_at": "2026-10-18T04:00:00Z" if published else None,
                "change_reason": None,
                "versions": [
                    {
                        "id": str(uuid4()),
                        "text": "First draft",
                        "reason": "generated",
                        "created_at": "2026-10-16T10:00:00Z",
                    },
                    {
                        "id": str(uuid4()),
                        "text": "Second draft",
                        "reason": "revise:make_shorter",
                        "created_at": "2026-10-16T10:00:00Z",
                    },
                ],
            }
        )
    return {
        "schema": 1,
        "id": cid,
        "client_id": cid,
        "version": 0,
        "name": name,
        "event_mode": "offline",
        "language": "en",
        "tone": "friendly",
        "platforms": ["x", "linkedin", "instagram", "whatsapp"],
        "source": {
            "kind": "url",
            "url": "https://example.org/event",
            "fetched_at": "2026-10-16T05:00:00Z",
            "text_hash": "sha256:abc",
        },
        "facts": [
            {
                "id": str(uuid4()),
                "key": "event_name",
                "value": name,
                "status": "confirmed",
                "critical": True,
                "source_snippet": name,
                "source_ref": "paste",
            },
            {
                "id": str(uuid4()),
                "key": "mentors",
                "value": [{"name": "Asha Verma", "role": "Python", "url": None, "handle": "@asha"}],
                "status": "needs_review",
                "critical": False,
                "source_snippet": None,
                "source_ref": None,
            },
            {
                "id": str(uuid4()),
                "key": "hashtags",
                "value": ["#RiversideHack", "#Hacktoberfest"],
                "status": "confirmed",
                "critical": False,
                "source_snippet": None,
                "source_ref": "manual",
            },
            {
                "id": str(uuid4()),
                "key": "registration_url",
                "value": "",
                "status": "confirmed",
                "critical": False,
                "not_applicable": True,
            },
        ],
        "plan": [
            {
                "id": item_b,
                "title": "Reminder",
                "purpose": "Nudge late sign-ups",
                "stage": "pre",
                "scheduled_for": "2026-10-22T18:30:00+05:30",
                "position": 1,
                "fact_keys": ["event_name"],
            },
            {
                "id": item_a,
                "title": "Announcement",
                "purpose": "Tell people the event exists",
                "stage": "pre",
                "scheduled_for": None,
                "position": 0,
                "fact_keys": [],
            },
        ],
        "posts": posts,
        "created_at": "2026-10-16T10:00:00Z",
        "updated_at": "2026-10-16T11:00:00+05:30",
    }


def make_doc(**kwargs) -> CampaignDoc:
    return CampaignDoc.model_validate(make_doc_dict(**kwargs))


def comparable(doc: CampaignDoc) -> CampaignDoc:
    """Drop the server-managed version so two docs can be compared field by field."""
    return doc.model_copy(update={"version": 0})
