"""Make planning decisions findable by the shape of the problem they addressed.

A planning episode recorded the goal's identifier and description but not its predicates,
so nothing about the problem could be recomputed from the record.  Retrieval that matched
on description would match prose rather than structure: two projects asking for the same
predicates in different words would look unrelated, and two asking for different
predicates in the same words would look identical.

The digest is indexed for exact recall; the full fingerprint is kept alongside it so that
partial overlap can be scored without reconstructing the goal.  Both are nullable:
episodes recorded before this revision have no fingerprint, and inventing one for them
would fabricate evidence about problems nobody characterised.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_planning_episode_fingerprint"
down_revision = "0010_scaffold_registrations"
branch_labels = None
depends_on = None

_INDEX = "ix_planning_episodes_problem_digest"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("planning_episodes")}
    with op.batch_alter_table("planning_episodes") as batch:
        if "problem_digest" not in columns:
            batch.add_column(sa.Column("problem_digest", sa.String(length=64), nullable=True))
        if "problem_fingerprint" not in columns:
            batch.add_column(sa.Column("problem_fingerprint", sa.JSON(), nullable=True))

    inspector = sa.inspect(bind)
    existing = {index["name"] for index in inspector.get_indexes("planning_episodes")}
    if _INDEX not in existing:
        op.create_index(_INDEX, "planning_episodes", ["problem_digest"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {index["name"] for index in inspector.get_indexes("planning_episodes")}
    if _INDEX in existing:
        op.drop_index(_INDEX, table_name="planning_episodes")
    columns = {column["name"] for column in inspector.get_columns("planning_episodes")}
    with op.batch_alter_table("planning_episodes") as batch:
        if "problem_fingerprint" in columns:
            batch.drop_column("problem_fingerprint")
        if "problem_digest" in columns:
            batch.drop_column("problem_digest")
