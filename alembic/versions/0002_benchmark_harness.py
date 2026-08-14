"""Add challenge, prediction, submission, and evaluator operational records."""

from alembic import op

revision = "0002_benchmark_harness"
down_revision = "0001_operational_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The ORM models are the typed persistence boundary. create_all is safe here
    # because this migration is also used against existing local SQLite stores.
    from services.memory import models  # noqa: F401
    from services.memory.database import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from services.memory.models import Challenge, EvaluationRun, EvaluationScore, Prediction, Submission

    bind = op.get_bind()
    tables = (
        EvaluationScore.__table__,
        EvaluationRun.__table__,
        Submission.__table__,
        Prediction.__table__,
        Challenge.__table__,
    )
    for table in tables:
        table.drop(bind=bind, checkfirst=True)
