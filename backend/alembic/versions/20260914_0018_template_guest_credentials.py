"""Encrypted template guest credentials and explicit student disclosure policy."""
from alembic import op
import sqlalchemy as sa

revision = "20260914_0018"
down_revision = "20260914_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "template_guest_credentials",
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("vm_templates.id"), primary_key=True),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("auto_connect", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("student_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_table("template_guest_credentials")
