"""Record where each task graph proposal came from.

Ingestion now gates the builder roles — the only roles allowed to edit files and
run commands — on the proposal's origin: a graph the runtime built or one
compiled from an installed workflow package may name them, a model-authored
graph needs an allowing decision.  The column stores the origin the runtime
decided by, so a later audit can tell a compiled graph from one a model wrote.

Existing rows are backfilled as `agent`.  Every proposal ingested before this
revision came either from an orchestration turn or from the bootstrap that
issues a single coordinator task, and `agent` is the conservative label for
both.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_proposal_origin"
down_revision = "0007_retire_agenda_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earlier revisions build their schema from the live models rather than from
    # literal DDL, so a database created after this change already has the
    # column and a database created before it does not.
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("task_graph_proposals")}
    if "origin" not in columns:
        with op.batch_alter_table("task_graph_proposals") as batch:
            batch.add_column(
                sa.Column(
                    "origin",
                    sa.String(length=32),
                    nullable=False,
                    server_default="agent",
                )
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("task_graph_proposals")}
    if "origin" in columns:
        with op.batch_alter_table("task_graph_proposals") as batch:
            batch.drop_column("origin")
