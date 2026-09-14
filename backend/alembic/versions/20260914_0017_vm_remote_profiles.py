"""VM-bound remote access profiles.

Revision ID: 20260914_0017
Revises: 20260911_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260914_0017"
down_revision = "20260911_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vm_remote_profiles",
        sa.Column("vm_id", sa.Integer(), sa.ForeignKey("student_vms.id"), primary_key=True),
        sa.Column("protocol", sa.String(8), nullable=False),
        sa.Column("address", sa.String(64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("mac_address", sa.String(17), nullable=False),
        sa.Column("server_identity", sa.Text(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_table("vm_remote_profiles")
