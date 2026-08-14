"""Add SQL-authoritative semantic task runtime and knowledge graph projection."""

from alembic import op

revision = "0006_semantic_task_runtime"
down_revision = "0005_research_control_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from services.memory import models  # noqa: F401
    from services.memory.database import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from services.memory.models import (
        ContextSnapshotRecord,
        CriticAssessmentRecord,
        KnowledgeEdgeRecord,
        KnowledgeNodeRecord,
        ReasoningRubricRecord,
        RubricEvaluationRecord,
        RuntimeTaskRecord,
        TaskAttemptRecord,
        TaskDependencyRecord,
        TaskEventRecord,
        TaskGraphProposalRecord,
    )

    bind = op.get_bind()
    for model in (
        KnowledgeEdgeRecord,
        CriticAssessmentRecord,
        KnowledgeNodeRecord,
        RubricEvaluationRecord,
        TaskEventRecord,
        ContextSnapshotRecord,
        TaskAttemptRecord,
        TaskDependencyRecord,
        RuntimeTaskRecord,
        ReasoningRubricRecord,
        TaskGraphProposalRecord,
    ):
        model.__table__.drop(bind=bind, checkfirst=True)
