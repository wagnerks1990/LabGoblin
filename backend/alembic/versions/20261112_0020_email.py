"""Durable encrypted email, account recovery, and verified webhook receipts."""

from alembic import op
import sqlalchemy as sa

revision = "20261112_0020"
down_revision = "20260914_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("receiving_enabled", sa.Boolean(), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("public_origin", sa.String(255), nullable=False),
        sa.Column("sender", sa.String(255), nullable=False),
        sa.Column("support_address", sa.String(255), nullable=False),
        sa.Column("encrypted_api_key", sa.Text()),
        sa.Column("encrypted_webhook_secret", sa.Text()),
        sa.Column("notifications_since", sa.DateTime()),
    )
    op.execute(
        "INSERT INTO email_settings (id, enabled, receiving_enabled, notifications_enabled, public_origin, sender, support_address) VALUES (1, false, false, false, '', '', '')"
    )
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id")),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("provider_id", sa.String(128), unique=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime()),
        sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("event_at", sa.DateTime()),
        sa.Column("error", sa.String(120)),
    )
    op.create_index("ix_email_messages_state", "email_messages", ["state"])
    op.create_index("ix_email_messages_user_id", "email_messages", ["user_id"])
    op.create_table(
        "email_action_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime()),
    )
    op.create_index(
        "ix_email_action_tokens_user_id", "email_action_tokens", ["user_id"]
    )
    op.create_table(
        "email_webhook_events",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("provider_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("event_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_webhook_events_state", "email_webhook_events", ["state"])
    op.create_table(
        "email_suppressions",
        sa.Column("address_hash", sa.String(64), primary_key=True),
        sa.Column("reason", sa.String(32), nullable=False),
    )
    op.create_table(
        "email_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
    )


def downgrade():
    for table in [
        "email_preferences",
        "email_suppressions",
        "email_webhook_events",
        "email_action_tokens",
        "email_messages",
        "email_settings",
    ]:
        op.drop_table(table)
