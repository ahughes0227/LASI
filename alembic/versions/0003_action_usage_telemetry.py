"""Add immutable action-level token usage telemetry."""

from alembic import op

revision = "0003_action_usage_telemetry"
down_revision = "0002_benchmark_harness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from services.memory import models  # noqa: F401
    from services.memory.database import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from services.memory.models import ActionUsage

    ActionUsage.__table__.drop(bind=op.get_bind(), checkfirst=True)
