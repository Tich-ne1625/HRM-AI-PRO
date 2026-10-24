"""Shared login throttling; no changes to existing evidence or authentication families."""

from alembic import op

revision = "20261024_0008"
down_revision = "20261022_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE auth_login_limits (
        bucket_key VARCHAR(64) PRIMARY KEY,
        attempts INTEGER NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT ck_login_limit_attempts CHECK (attempts >= 1),
        CONSTRAINT ck_login_limit_key CHECK (bucket_key ~ '^[0-9a-f]{64}$')
    )""")
    op.create_index("ix_auth_login_limits_expires_at", "auth_login_limits", ["expires_at"])


def downgrade() -> None:
    op.drop_table("auth_login_limits")
