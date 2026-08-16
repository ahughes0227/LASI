"""Add authoritative research agendas, actions, and loop state."""

from alembic import op

revision = "0005_research_control_plane"
down_revision = "0004_research_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from services.memory import models  # noqa: F401
    from services.memory.database import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Named literally rather than through the models: the agenda tables were
    # retired in 0007, so importing their mappers here would fail.
    import sqlalchemy as sa

    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table in ("research_loop_states", "research_actions", "research_agendas"):
        if table in tables:
            op.drop_table(table)
