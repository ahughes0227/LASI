"""Space out retries instead of retrying a failing task as fast as the loop allows.

A task whose result is rejected returns to `ready` in the same transaction, so a task
that fails deterministically consumed all of its attempts back to back. Nothing about
the world changed between those attempts: the same input met the same code and failed
the same way, three times, and the attempt budget meant to protect the assignment was
spent in milliseconds.

`next_eligible_at` gates when a retry may be leased. Null means eligible now, which is
the state of every task that has not failed, so existing rows need no backfill.

Expired-lease recovery deliberately does not set it: that path is already spaced by the
lease duration, and adding a second delay would compound them.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_task_retry_backoff"
down_revision = "0011_planning_episode_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("runtime_tasks")}
    if "next_eligible_at" not in columns:
        with op.batch_alter_table("runtime_tasks") as batch:
            batch.add_column(sa.Column("next_eligible_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("runtime_tasks")}
    if "next_eligible_at" in columns:
        with op.batch_alter_table("runtime_tasks") as batch:
            batch.drop_column("next_eligible_at")
