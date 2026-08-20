"""Record which template revision produced each generated tree.

Projects and packages are scaffolded from governed templates, and those templates change
as the system learns.  A workspace therefore carries a revision, and two workspaces built
from different revisions are not structurally comparable.  Recording the revision makes
that difference visible to anything that compares evidence across projects, instead of
leaving it to be inferred from the filesystem.

`project_id` is nullable because capability, component, and workflow packages are
scaffolded from the same mechanism but are not project-scoped.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_scaffold_registrations"
down_revision = "0009_planning_episodes"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_scaffold_registrations_template", "template"),
    ("ix_scaffold_registrations_project_id", "project_id"),
)


def upgrade() -> None:
    # Revision 0001 builds its schema from the live ORM metadata, so a database created
    # after this change already has the table and its indexes, while one created before
    # it has neither.  Both are reconciled here rather than assumed.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "scaffold_registrations" not in set(inspector.get_table_names()):
        op.create_table(
            "scaffold_registrations",
            sa.Column("scaffold_registration_id", sa.String(length=255), primary_key=True),
            sa.Column("template", sa.String(length=128), nullable=False),
            sa.Column("revision", sa.String(length=32), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column(
                "project_id",
                sa.String(length=255),
                sa.ForeignKey("projects.project_id"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        inspector = sa.inspect(bind)

    existing = {index["name"] for index in inspector.get_indexes("scaffold_registrations")}
    for name, column in _INDEXES:
        if name not in existing:
            op.create_index(name, "scaffold_registrations", [column], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "scaffold_registrations" not in set(inspector.get_table_names()):
        return
    existing = {index["name"] for index in inspector.get_indexes("scaffold_registrations")}
    for name, _column in _INDEXES:
        if name in existing:
            op.drop_index(name, table_name="scaffold_registrations")
    op.drop_table("scaffold_registrations")
