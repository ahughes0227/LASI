"""Add durable research assignment control and event records."""

from alembic import op

revision = "0004_research_assignments"
down_revision = "0003_action_usage_telemetry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from services.memory import models  # noqa: F401
    from services.memory.database import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from services.memory.models import AssignmentEvent, ResearchAssignmentRecord

    bind = op.get_bind()
    AssignmentEvent.__table__.drop(bind=bind, checkfirst=True)
    ResearchAssignmentRecord.__table__.drop(bind=bind, checkfirst=True)
