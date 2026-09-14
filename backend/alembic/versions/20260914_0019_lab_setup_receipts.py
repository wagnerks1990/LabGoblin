"""Replay-safe unified lab setup submissions."""
from alembic import op
import sqlalchemy as sa

revision = "20260914_0019"
down_revision = "20260914_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lab_setup_receipts",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("lab_runs.id"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
    )


def downgrade():
    op.drop_table("lab_setup_receipts")
