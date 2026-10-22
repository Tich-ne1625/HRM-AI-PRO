"""Audience-separated AI advisory history; no evidence backfill."""

from alembic import op

revision = "20261022_0007"
down_revision = "20261022_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE ai_analyses (
    id UUID NOT NULL,
    review_id UUID NOT NULL,
    audience VARCHAR(10) NOT NULL,
    status VARCHAR(9) NOT NULL,
    generation_version INTEGER NOT NULL,
    calculation_version INTEGER NOT NULL,
    evidence_version INTEGER NOT NULL,
    engine_version VARCHAR(16) NOT NULL,
    evidence_hash VARCHAR(64) NOT NULL,
    input_hash VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(16) NOT NULL,
    redaction_version VARCHAR(16) NOT NULL,
    schema_version VARCHAR(16) NOT NULL,
    model VARCHAR(128) NOT NULL,
    actual_model VARCHAR(128),
    requested_by UUID NOT NULL,
    client_request_id UUID NOT NULL,
    request_fingerprint VARCHAR(64) NOT NULL,
    reserved_at TIMESTAMP WITH TIME ZONE NOT NULL,
    lease_until TIMESTAMP WITH TIME ZONE NOT NULL,
    fencing_token UUID NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    generated_at TIMESTAMP WITH TIME ZONE,
    error_code VARCHAR(64),
    output JSONB,
    input_sampled BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(review_id, calculation_version) REFERENCES performance_review_revisions
        (review_id, calculation_version) ON DELETE RESTRICT,
    CONSTRAINT uq_ai_generation UNIQUE (review_id, audience, generation_version),
    CONSTRAINT uq_ai_idempotency UNIQUE (requested_by, client_request_id),
    CONSTRAINT ck_ai_versions CHECK (generation_version >= 1 AND calculation_version >= 1 AND
        evidence_version >= 1),
    CONSTRAINT ck_ai_hashes CHECK (evidence_hash ~ '^[0-9a-f]{64}$' AND input_hash ~
        '^[0-9a-f]{64}$' AND request_fingerprint ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_ai_lease CHECK (lease_until > reserved_at),
    CONSTRAINT ck_ai_result CHECK ((status='RUNNING' AND output IS NULL AND error_code IS NULL
        AND completed_at IS NULL AND generated_at IS NULL) OR (status='SUCCEEDED' AND output IS
        NOT NULL AND jsonb_typeof(output)='object' AND error_code IS NULL AND completed_at IS
        NOT NULL AND generated_at IS NOT NULL AND generated_at=completed_at) OR
        (status='FAILED' AND output IS NULL AND
        error_code IS NOT NULL AND completed_at IS NOT NULL AND generated_at IS NULL)),
    CONSTRAINT ck_ai_completion CHECK (completed_at IS NULL OR completed_at >= reserved_at),
    FOREIGN KEY(review_id) REFERENCES performance_reviews (id) ON DELETE RESTRICT,
    CONSTRAINT ck_ai_audience CHECK (audience IN ('PUBLIC', 'HR_PRIVATE')),
    CONSTRAINT ck_ai_status CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE RESTRICT
)
""")
    op.execute(
        "CREATE UNIQUE INDEX uq_ai_running_review ON ai_analyses (review_id) WHERE status='RUNNING'"
    )


def downgrade() -> None:
    op.drop_table("ai_analyses")
