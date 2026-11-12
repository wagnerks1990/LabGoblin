"""Unique case/whitespace-insensitive account emails, without rewriting identities."""

from alembic import op
import sqlalchemy as sa

revision = "20261112_0021"
down_revision = "20261112_0020"
branch_labels = None
depends_on = None


def upgrade():
    # Never choose an account or rewrite/delete colliding records automatically.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE")
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate:
        raise RuntimeError(
            "Duplicate normalized account emails; review accounts before enabling email sign-in"
        )
    op.create_index(
        "uq_users_email_normalized",
        "users",
        [sa.text("lower(rtrim(ltrim(email)))")],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_users_email_normalized", table_name="users")
