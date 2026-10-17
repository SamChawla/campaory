"""Repository for users and saved campaigns (LLD section 4).

Every campaign query is scoped by `user_id` (BR12). Campaigns are addressed by the document id
(`client_id`); server row ids never leave this module.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, get_args
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Campaign, FactRow, Identity, PlanItemRow, PostRow, PostVersionRow, User
from app.domain.schemas import CampaignDoc, PostStatus

POST_STATUSES: tuple[str, ...] = get_args(PostStatus)


@dataclass(frozen=True)
class CampaignSummary:
    id: UUID
    name: str
    version: int
    updated_at: datetime
    post_counts: dict[str, int]


# users


def get_user(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


def upsert_user_from_identity(
    db: Session,
    provider: str,
    subject: str,
    email: str,
    name: str | None,
    avatar_url: str | None,
) -> User:
    """Find the user by (provider, subject), else by email, else create one. Callers pass only
    verified emails, because a matching email links the identity to an existing account."""
    now = datetime.now(UTC)
    identity = db.scalar(
        select(Identity).where(Identity.provider == provider, Identity.subject == subject)
    )
    if identity is not None:
        user = db.get_one(User, identity.user_id)
        if email.lower() != user.email.lower() and _user_by_email(db, email) is None:
            user.email = email
    else:
        user = _user_by_email(db, email)
        if user is None:
            user = User(email=email)
            db.add(user)
            db.flush()
        db.add(Identity(user_id=user.id, provider=provider, subject=subject))
    user.name = name
    user.avatar_url = avatar_url
    user.last_login_at = now
    db.commit()
    return user


def _user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


def delete_user(db: Session, user_id: UUID) -> bool:
    deleted = db.execute(delete(User).where(User.id == user_id)).rowcount
    db.commit()
    return bool(deleted)


# campaigns


def _own(db: Session, user_id: UUID, campaign_id: UUID, *, lock: bool = False) -> Campaign | None:
    query = select(Campaign).where(Campaign.user_id == user_id, Campaign.client_id == campaign_id)
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def create_campaign(
    db: Session, user_id: UUID, doc: CampaignDoc, *, max_campaigns: int = 0
) -> tuple[CampaignDoc, bool]:
    """Insert the whole tree. A repeat with the same client id returns the stored campaign
    unchanged, with `created=False`. `max_campaigns=0` disables the free-plan limit."""
    existing = _own(db, user_id, doc.client_id)
    if existing is not None:
        return _load(db, existing), False
    if max_campaigns > 0:
        owned = db.scalar(
            select(func.count()).select_from(Campaign).where(Campaign.user_id == user_id)
        )
        if owned >= max_campaigns:
            raise AppError(
                409,
                "campaign_limit",
                f"Your plan keeps {max_campaigns} saved campaign(s). Delete one to save another.",
                details={"limit": max_campaigns},
            )
    campaign = Campaign(user_id=user_id, client_id=doc.client_id, version=1)
    _write_header(campaign, doc)
    db.add(campaign)
    try:
        db.flush()
        _insert_children(db, campaign, doc)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _own(db, user_id, doc.client_id)
        if existing is None:
            raise
        return _load(db, existing), False
    return _load(db, campaign), True


def replace_campaign(
    db: Session, user_id: UUID, campaign_id: UUID, doc: CampaignDoc, expected_version: int
) -> CampaignDoc | None:
    campaign = _own(db, user_id, campaign_id, lock=True)
    if campaign is None:
        return None
    if campaign.version != expected_version:
        current = campaign.version
        db.rollback()
        raise AppError(
            409,
            "version_conflict",
            "This campaign changed somewhere else. Reload it or overwrite.",
            details={"current_version": current},
        )
    _delete_children(db, campaign.id)
    _write_header(campaign, doc)
    campaign.version += 1
    _insert_children(db, campaign, doc)
    db.commit()
    return _load(db, campaign)


def get_campaign(db: Session, user_id: UUID, campaign_id: UUID) -> CampaignDoc | None:
    campaign = _own(db, user_id, campaign_id)
    return None if campaign is None else _load(db, campaign)


def list_campaigns(db: Session, user_id: UUID) -> list[CampaignSummary]:
    campaigns = db.scalars(
        select(Campaign)
        .where(Campaign.user_id == user_id)
        .order_by(Campaign.updated_at.desc(), Campaign.name)
    ).all()
    counts: dict[UUID, dict[str, int]] = {c.id: dict.fromkeys(POST_STATUSES, 0) for c in campaigns}
    rows = db.execute(
        select(PostRow.campaign_id, PostRow.status, func.count())
        .join(Campaign, Campaign.id == PostRow.campaign_id)
        .where(Campaign.user_id == user_id)
        .group_by(PostRow.campaign_id, PostRow.status)
    ).all()
    for campaign_pk, status, count in rows:
        counts[campaign_pk][status] = count
    return [
        CampaignSummary(
            id=c.client_id,
            name=c.name,
            version=c.version,
            updated_at=c.updated_at,
            post_counts=counts[c.id],
        )
        for c in campaigns
    ]


def delete_campaign(db: Session, user_id: UUID, campaign_id: UUID) -> bool:
    deleted = db.execute(
        delete(Campaign).where(Campaign.user_id == user_id, Campaign.client_id == campaign_id)
    ).rowcount
    db.commit()
    return bool(deleted)


# document <-> rows


def _write_header(campaign: Campaign, doc: CampaignDoc) -> None:
    campaign.name = doc.name
    campaign.event_mode = doc.event_mode
    campaign.language = doc.language
    campaign.tone = doc.tone
    campaign.platforms = list(doc.platforms)
    campaign.source = doc.source.model_dump(mode="json")
    campaign.created_at = doc.created_at
    campaign.updated_at = doc.updated_at


def _delete_children(db: Session, campaign_pk: UUID) -> None:
    post_ids = select(PostRow.id).where(PostRow.campaign_id == campaign_pk)
    db.execute(delete(PostVersionRow).where(PostVersionRow.post_id.in_(post_ids)))
    db.execute(delete(PostRow).where(PostRow.campaign_id == campaign_pk))
    db.execute(delete(PlanItemRow).where(PlanItemRow.campaign_id == campaign_pk))
    db.execute(delete(FactRow).where(FactRow.campaign_id == campaign_pk))


def _insert_children(db: Session, campaign: Campaign, doc: CampaignDoc) -> None:
    for position, fact in enumerate(doc.facts):
        dumped = fact.model_dump(mode="json")
        db.add(
            FactRow(
                campaign_id=campaign.id,
                doc_id=fact.id,
                key=fact.key,
                value=dumped["value"],
                status=fact.status,
                critical=fact.critical,
                not_applicable=fact.not_applicable,
                source_snippet=fact.source_snippet,
                source_ref=fact.source_ref,
                position=position,
            )
        )
    item_pks: dict[UUID, UUID] = {}
    for seq, item in enumerate(doc.plan):
        row = PlanItemRow(
            campaign_id=campaign.id,
            doc_id=item.id,
            title=item.title,
            purpose=item.purpose,
            stage=item.stage,
            scheduled_for=item.scheduled_for,
            position=item.position,
            seq=seq,
            fact_keys=list(item.fact_keys),
        )
        db.add(row)
        db.flush()
        item_pks[item.id] = row.id
    for seq, post in enumerate(doc.posts):
        dumped = post.model_dump(mode="json")
        row = PostRow(
            campaign_id=campaign.id,
            plan_item_id=item_pks[post.plan_item_id],
            doc_id=post.id,
            platform=post.platform,
            text=post.text,
            status=post.status,
            seq=seq,
            facts_used=list(post.facts_used),
            guard_flags=dumped["guard_flags"],
            placeholders=list(post.placeholders),
            reminder_at=post.reminder_at,
            published_url=post.published_url,
            published_at=post.published_at,
            change_reason=post.change_reason,
        )
        db.add(row)
        db.flush()
        for version_seq, version in enumerate(post.versions):
            db.add(
                PostVersionRow(
                    post_id=row.id,
                    doc_id=version.id,
                    text=version.text,
                    reason=version.reason,
                    seq=version_seq,
                    created_at=version.created_at,
                )
            )
    db.flush()


def _load(db: Session, campaign: Campaign) -> CampaignDoc:
    facts = db.scalars(
        select(FactRow).where(FactRow.campaign_id == campaign.id).order_by(FactRow.position)
    ).all()
    items = db.scalars(
        select(PlanItemRow).where(PlanItemRow.campaign_id == campaign.id).order_by(PlanItemRow.seq)
    ).all()
    posts = db.scalars(
        select(PostRow).where(PostRow.campaign_id == campaign.id).order_by(PostRow.seq)
    ).all()
    versions: dict[UUID, list[dict[str, Any]]] = {post.id: [] for post in posts}
    for version in db.scalars(
        select(PostVersionRow)
        .join(PostRow, PostRow.id == PostVersionRow.post_id)
        .where(PostRow.campaign_id == campaign.id)
        .order_by(PostVersionRow.seq)
    ):
        versions[version.post_id].append(
            {
                "id": version.doc_id,
                "text": version.text,
                "reason": version.reason,
                "created_at": version.created_at,
            }
        )
    item_doc_ids = {item.id: item.doc_id for item in items}
    return CampaignDoc.model_validate(
        {
            "schema": 1,
            "id": campaign.client_id,
            "client_id": campaign.client_id,
            "version": campaign.version,
            "name": campaign.name,
            "event_mode": campaign.event_mode,
            "language": campaign.language,
            "tone": campaign.tone,
            "platforms": campaign.platforms,
            "source": campaign.source,
            "facts": [
                {
                    "id": f.doc_id,
                    "key": f.key,
                    "value": f.value,
                    "status": f.status,
                    "critical": f.critical,
                    "not_applicable": f.not_applicable,
                    "source_snippet": f.source_snippet,
                    "source_ref": f.source_ref,
                }
                for f in facts
            ],
            "plan": [
                {
                    "id": i.doc_id,
                    "title": i.title,
                    "purpose": i.purpose,
                    "stage": i.stage,
                    "scheduled_for": i.scheduled_for,
                    "position": i.position,
                    "fact_keys": i.fact_keys,
                }
                for i in items
            ],
            "posts": [
                {
                    "id": p.doc_id,
                    "plan_item_id": item_doc_ids[p.plan_item_id],
                    "platform": p.platform,
                    "text": p.text,
                    "status": p.status,
                    "facts_used": p.facts_used,
                    "guard_flags": p.guard_flags,
                    "placeholders": p.placeholders,
                    "reminder_at": p.reminder_at,
                    "published_url": p.published_url,
                    "published_at": p.published_at,
                    "change_reason": p.change_reason,
                    "versions": versions[p.id],
                }
                for p in posts
            ],
            "created_at": campaign.created_at,
            "updated_at": campaign.updated_at,
        }
    )
