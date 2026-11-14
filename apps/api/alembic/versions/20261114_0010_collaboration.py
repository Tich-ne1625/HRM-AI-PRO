"""Internal feed, comments and private direct messages; no existing data rewritten."""

import sqlalchemy as sa

from alembic import op

revision = "20261114_0010"
down_revision = "20261114_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internal_posts",
        sa.Column("mention_ids", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_internal_posts_feed", "internal_posts", ["department_id", "created_at", "id"]
    )
    op.create_table(
        "post_comments",
        sa.Column("mention_ids", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "post_id",
            sa.Uuid(),
            sa.ForeignKey("internal_posts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_post_comments_post", "post_comments", ["post_id", "created_at", "id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sender_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "recipient_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("sender_id <> recipient_id", name="ck_chat_distinct_people"),
    )
    op.create_index("ix_chat_recipient", "chat_messages", ["recipient_id", "created_at", "id"])
    op.create_index("ix_chat_sender", "chat_messages", ["sender_id", "created_at", "id"])
    op.add_column(
        "notifications",
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("internal_posts.id", ondelete="RESTRICT")),
    )
    op.add_column(
        "notifications",
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("chat_messages.id", ondelete="RESTRICT")),
    )


def downgrade() -> None:
    op.drop_column("notifications", "message_id")
    op.drop_column("notifications", "post_id")
    op.drop_table("chat_messages")
    op.drop_table("post_comments")
    op.drop_table("internal_posts")
