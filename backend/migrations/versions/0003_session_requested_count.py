"""Remember requested session size without guessing configurations of old sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("study_sessions") as batch:
        batch.add_column(sa.Column("requested_count", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_session_requested_count", "requested_count IN (0, 10, 20)"
        )


def downgrade():
    with op.batch_alter_table("study_sessions") as batch:
        batch.drop_constraint("ck_session_requested_count", type_="check")
        batch.drop_column("requested_count")
