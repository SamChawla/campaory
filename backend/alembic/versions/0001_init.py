"""init: users, identities, campaigns and the campaign tree

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("last_login_at", TS, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ux_users_email", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "identities",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_identities_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identities"),
        sa.UniqueConstraint("provider", "subject", name="uq_identities_provider"),
    )
    op.create_index("ix_identities_user_id", "identities", ["user_id"])

    op.create_table(
        "campaigns",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("event_mode", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("tone", sa.Text(), nullable=False),
        sa.Column("platforms", JSON, nullable=False),
        sa.Column("source", JSON, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.CheckConstraint(
            "event_mode IN ('online', 'offline', 'hybrid')", name="ck_campaigns_event_mode"
        ),
        sa.CheckConstraint("language IN ('en', 'hi', 'hinglish')", name="ck_campaigns_language"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_campaigns_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaigns"),
        sa.UniqueConstraint("user_id", "client_id", name="uq_campaigns_user_client"),
    )
    op.create_index("ix_campaigns_user", "campaigns", ["user_id", "updated_at"])

    op.create_table(
        "facts",
        _id(),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("doc_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", JSON, nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("not_applicable", sa.Boolean(), nullable=False),
        sa.Column("source_snippet", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('confirmed', 'needs_review', 'missing', 'superseded')",
            name="ck_facts_status",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_facts_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_facts"),
        sa.UniqueConstraint("campaign_id", "doc_id", name="uq_facts_campaign_doc"),
    )

    op.create_table(
        "plan_items",
        _id(),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("doc_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("scheduled_for", TS, nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("fact_keys", JSON, nullable=False),
        sa.CheckConstraint("stage IN ('pre', 'event', 'post')", name="ck_plan_items_stage"),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_plan_items_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plan_items"),
        sa.UniqueConstraint("campaign_id", "doc_id", name="uq_plan_items_campaign_doc"),
    )

    op.create_table(
        "posts",
        _id(),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("plan_item_id", sa.Uuid(), nullable=False),
        sa.Column("doc_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("facts_used", JSON, nullable=False),
        sa.Column("guard_flags", JSON, nullable=False),
        sa.Column("placeholders", JSON, nullable=False),
        sa.Column("reminder_at", TS, nullable=True),
        sa.Column("published_url", sa.Text(), nullable=True),
        sa.Column("published_at", TS, nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "platform IN ('linkedin', 'instagram', 'whatsapp', 'x')", name="ck_posts_platform"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'needs_review', 'approved', 'scheduled', 'published')",
            name="ck_posts_status",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_posts_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_item_id"],
            ["plan_items.id"],
            name="fk_posts_plan_item_id_plan_items",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_posts"),
        sa.UniqueConstraint("campaign_id", "doc_id", name="uq_posts_campaign_doc"),
    )
    op.create_index("ix_posts_plan_item_id", "posts", ["plan_item_id"])

    op.create_table(
        "post_versions",
        _id(),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("doc_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], name="fk_post_versions_post_id_posts", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_post_versions"),
    )
    op.create_index("ix_post_versions_post_id", "post_versions", ["post_id"])


def downgrade() -> None:
    op.drop_table("post_versions")
    op.drop_table("posts")
    op.drop_table("plan_items")
    op.drop_table("facts")
    op.drop_table("campaigns")
    op.drop_table("identities")
    op.drop_index("ux_users_email", table_name="users")
    op.drop_table("users")
