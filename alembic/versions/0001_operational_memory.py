"""Create LASI operational memory tables."""

from alembic import op

revision = "0001_operational_memory"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The ORM metadata is the schema contract; this migration is intentionally explicit.
    from services.memory import models  # noqa: F401
    from services.memory.database import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from services.memory import models  # noqa: F401
    from services.memory.database import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
