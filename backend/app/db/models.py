"""SQLAlchemy models (LLD section 4).

Every table has a server-generated `id`. The ids that come from the browser document are kept in
`client_id` (campaigns) and `doc_id` (children), unique per parent, so two accounts can hold the
same document without primary-key clashes and server ids never leave the server.
"""

from datetime import UTC, datetime
from typing import Any, get_args
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.schemas import EventMode, FactStatus, Language, Platform, PostStatus, Stage

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Json = JSON().with_variant(JSONB(), "postgresql")


class UtcDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetime stored in UTC. SQLite drops tzinfo, so UTC is re-attached on load."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must carry a timezone")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _one_of(column: str, literal: Any) -> str:
    values = ", ".join(f"'{v}'" for v in get_args(literal))
    return f"{column} IN ({values})"


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


Index("ux_users_email", func.lower(User.email), unique=True)


class Identity(Base):
    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_identities_provider"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_campaigns_user_client"),
        Index("ix_campaigns_user", "user_id", "updated_at"),
        CheckConstraint(_one_of("event_mode", EventMode), name="event_mode"),
        CheckConstraint(_one_of("language", Language), name="language"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    event_mode: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(Text, default="")
    platforms: Mapped[list[str]] = mapped_column(Json)
    source: Mapped[dict[str, Any]] = mapped_column(Json)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)


class FactRow(Base):
    __tablename__ = "facts"
    __table_args__ = (
        UniqueConstraint("campaign_id", "doc_id", name="uq_facts_campaign_doc"),
        CheckConstraint(_one_of("status", FactStatus), name="status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    doc_id: Mapped[UUID] = mapped_column(Uuid)
    key: Mapped[str] = mapped_column(Text)
    value: Mapped[Any] = mapped_column(Json)
    status: Mapped[str] = mapped_column(Text)
    critical: Mapped[bool] = mapped_column(Boolean)
    not_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    source_snippet: Mapped[str | None] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class PlanItemRow(Base):
    __tablename__ = "plan_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "doc_id", name="uq_plan_items_campaign_doc"),
        CheckConstraint(_one_of("stage", Stage), name="stage"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    doc_id: Mapped[UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text, default="")
    stage: Mapped[str] = mapped_column(Text)
    scheduled_for: Mapped[datetime | None] = mapped_column(UtcDateTime)
    position: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    fact_keys: Mapped[list[str]] = mapped_column(Json, default=list)


class PostRow(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("campaign_id", "doc_id", name="uq_posts_campaign_doc"),
        CheckConstraint(_one_of("status", PostStatus), name="status"),
        CheckConstraint(_one_of("platform", Platform), name="platform"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    plan_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("plan_items.id", ondelete="CASCADE"), index=True
    )
    doc_id: Mapped[UUID] = mapped_column(Uuid)
    platform: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    seq: Mapped[int] = mapped_column(Integer)
    facts_used: Mapped[list[str]] = mapped_column(Json, default=list)
    guard_flags: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    placeholders: Mapped[list[str]] = mapped_column(Json, default=list)
    reminder_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    published_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    change_reason: Mapped[str | None] = mapped_column(Text)


class PostVersionRow(Base):
    __tablename__ = "post_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    doc_id: Mapped[UUID] = mapped_column(Uuid)
    text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    seq: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
