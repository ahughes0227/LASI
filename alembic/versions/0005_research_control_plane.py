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
    from services.memory.models import (
        ResearchActionRecord,
        ResearchAgendaRecord,
        ResearchLoopStateRecord,
    )

    bind = op.get_bind()
    ResearchLoopStateRecord.__table__.drop(bind=bind, checkfirst=True)
    ResearchActionRecord.__table__.drop(bind=bind, checkfirst=True)
    ResearchAgendaRecord.__table__.drop(bind=bind, checkfirst=True)
