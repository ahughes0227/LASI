"""Record planning decisions, including the admissible plans that were not chosen.

`DomainStatePlanner` enumerates every policy-compliant plan that reaches the goal and
then keeps one.  Until now the rejected plans existed only inside a single search call,
so the durable record showed what LASI did without showing what else it could have done.

That gap matters twice.  An audit cannot tell a forced move from a preference, and any
later attempt to learn selection would train on chosen plans alone — a sample shaped by
the very policy under evaluation.  This table stores the choice, the ranker that made
it, and the bounded set of alternatives it declined.

`assignment_id` is nullable by design: a plan is recorded when it is produced, and only
acquires an execution to be judged against once it is compiled and dispatched.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_planning_episodes"
down_revision = "0008_proposal_origin"
branch_labels = None
depends_on = None

#: Attributing an outcome to the decision that caused it is the read this table exists
#: for, and it is always keyed by project or assignment.
_INDEXES = (
    ("ix_planning_episodes_project_id", "project_id"),
    ("ix_planning_episodes_assignment_id", "assignment_id"),
)


def upgrade() -> None:
    # Revision 0001 builds its schema from the live ORM metadata, so a database created
    # after this change already has the table and its indexes, while one created before
    # it has neither.  Both are reconciled here rather than assumed.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "planning_episodes" not in set(inspector.get_table_names()):
        op.create_table(
            "planning_episodes",
            sa.Column("plan_id", sa.String(length=255), primary_key=True),
            sa.Column(
                "project_id",
                sa.String(length=255),
                sa.ForeignKey("projects.project_id"),
                nullable=False,
            ),
            sa.Column("goal_id", sa.String(length=255), nullable=False),
            sa.Column("goal_description", sa.Text(), nullable=False),
            sa.Column("observed_revision", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=64), nullable=False),
            sa.Column("ranker_id", sa.String(length=128), nullable=False),
            sa.Column("ranker_version", sa.String(length=64), nullable=False),
            sa.Column("chosen_capability_ids", sa.JSON(), nullable=False),
            sa.Column("considered_alternatives", sa.JSON(), nullable=False),
            sa.Column("admissible_count", sa.Integer(), nullable=False),
            sa.Column(
                "assignment_id",
                sa.String(length=255),
                sa.ForeignKey("research_assignments.assignment_id"),
                nullable=True,
            ),
            sa.Column("workflow_id", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        inspector = sa.inspect(bind)

    existing = {index["name"] for index in inspector.get_indexes("planning_episodes")}
    for name, column in _INDEXES:
        if name not in existing:
            op.create_index(name, "planning_episodes", [column], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "planning_episodes" not in set(inspector.get_table_names()):
        return
    existing = {index["name"] for index in inspector.get_indexes("planning_episodes")}
    for name, _column in _INDEXES:
        if name in existing:
            op.drop_index(name, table_name="planning_episodes")
    op.drop_table("planning_episodes")
