"""Retire the research agenda plane and version the task graph on the assignment.

The agenda tables described a second, parallel control plane that no worker ever
executed: `ProjectRunner` and `ResearchControlService` were the only writers and
nothing launched them.  The SQL task runtime is the surviving control plane, so
the agenda and its actions are dropped.

`research_assignments.graph_revision` replaces `research_agendas.revision`.  The
old column was compared against every incoming proposal's `observed_revision`,
but only the unreachable agenda plane ever incremented it, so the staleness
guard could not fire.  The new column is advanced by the runtime on every
accepted proposal, which is what the guard was always meant to measure.

`orchestrator_turns` and `consecutive_orchestrator_errors` counted turns of the
retired runner loop.  Autonomy is now bounded by the turn cap and token ceiling
the runtime enforces when it leases work.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_retire_agenda_plane"
down_revision = "0006_semantic_task_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earlier revisions build their schema from the live models rather than from
    # literal DDL, so a database created after this change never had the agenda
    # tables or turn counters in the first place.  Both shapes have to converge
    # here: an existing database drops them, a fresh one has nothing to drop.
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    columns = {column["name"] for column in inspector.get_columns("research_assignments")}

    with op.batch_alter_table("research_assignments") as batch:
        if "graph_revision" not in columns:
            batch.add_column(
                sa.Column("graph_revision", sa.Integer(), nullable=False, server_default="1")
            )
        for stale in ("orchestrator_turns", "consecutive_orchestrator_errors"):
            if stale in columns:
                batch.drop_column(stale)
    for table in ("research_actions", "research_agendas"):
        if table in tables:
            op.drop_table(table)


def downgrade() -> None:
    op.create_table(
        "research_agendas",
        sa.Column("agenda_id", sa.String(length=255), primary_key=True),
        sa.Column(
            "assignment_id",
            sa.String(length=255),
            sa.ForeignKey("research_assignments.assignment_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "project_id", sa.String(length=255), sa.ForeignKey("projects.project_id"), nullable=False
        ),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_action_id", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "research_actions",
        sa.Column("action_id", sa.String(length=255), primary_key=True),
        sa.Column(
            "agenda_id",
            sa.String(length=255),
            sa.ForeignKey("research_agendas.agenda_id"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.String(length=255), sa.ForeignKey("projects.project_id"), nullable=False
        ),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "experiment_plan_id",
            sa.String(length=255),
            sa.ForeignKey("experiment_plans.experiment_plan_id"),
            nullable=True,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    with op.batch_alter_table("research_assignments") as batch:
        batch.add_column(
            sa.Column("orchestrator_turns", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column(
                "consecutive_orchestrator_errors",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.drop_column("graph_revision")
